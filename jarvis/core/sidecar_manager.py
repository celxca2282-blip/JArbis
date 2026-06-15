# sidecar_manager.py
"""Запуск полигlot sidecar'ов: Node.js (Edge-TTS), Go (LLM proxy), PowerShell (Windows)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

EDGE_TTS_PORT = int(os.environ.get("JARBIS_EDGE_TTS_PORT", "17848"))
LLM_PROXY_PORT = int(os.environ.get("JARBIS_LLM_PROXY_PORT", "17849"))
NODE_DIR = config.BASE_DIR / "services" / "node_edge_tts"
GO_DIR = config.BASE_DIR / "services" / "go_llm_proxy"
GO_EXE = GO_DIR / "go_llm_proxy.exe"
PS1_BRIDGE = config.BASE_DIR / "services" / "powershell" / "win_bridge.ps1"


class SidecarManager:
    """Держит фоновые процессы Node/Go/PowerShell."""

    _instance: SidecarManager | None = None

    def __init__(self) -> None:
        self._node_proc: subprocess.Popen | None = None
        self._go_proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self.edge_tts_url = f"http://127.0.0.1:{EDGE_TTS_PORT}"
        self.llm_proxy_url = f"http://127.0.0.1:{LLM_PROXY_PORT}"
        self.llm_proxy_base_url = f"{self.llm_proxy_url}/v1"

    @classmethod
    def instance(cls) -> SidecarManager:
        if cls._instance is None:
            cls._instance = SidecarManager()
        return cls._instance

    def start_all(self) -> None:
        """Поднимает доступные sidecar'ы в фоне."""
        threading.Thread(target=self._start_node_edge_tts, daemon=True, name="SidecarNode").start()
        threading.Thread(target=self._start_go_llm_proxy, daemon=True, name="SidecarGo").start()

    def warmup(self, max_wait: float = 4.0) -> None:
        """Ждёт готовности sidecar'ов (не блокирует GUI надолго)."""
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            if self.edge_tts_available() or not shutil.which("node"):
                if self.llm_proxy_available() or not self._go_launchable():
                    break
            time.sleep(0.12)

    def stop_all(self) -> None:
        with self._lock:
            for proc in (self._node_proc, self._go_proc):
                if proc:
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        pass
            self._node_proc = None
            self._go_proc = None

    @staticmethod
    def _win_flags() -> int:
        return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]

    def _go_launchable(self) -> bool:
        return GO_EXE.is_file() or shutil.which("go") is not None

    def _start_node_edge_tts(self) -> None:
        if not shutil.which("node"):
            logger.info("Node.js не найден — Edge-TTS через Python edge-tts")
            return
        server = NODE_DIR / "server.mjs"
        if not server.is_file():
            logger.warning("Node sidecar не найден: %s", server)
            return
        if self._ping_url(f"{self.edge_tts_url}/ping"):
            logger.info("Node Edge-TTS уже слушает :%s", EDGE_TTS_PORT)
            return
        try:
            env = os.environ.copy()
            env["JARBIS_EDGE_TTS_PORT"] = str(EDGE_TTS_PORT)
            with self._lock:
                self._node_proc = subprocess.Popen(
                    ["node", str(server)],
                    cwd=str(NODE_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    creationflags=self._win_flags(),
                )
            if self._wait_ping(f"{self.edge_tts_url}/ping", self._node_proc):
                logger.info("Node Edge-TTS sidecar :%s", EDGE_TTS_PORT)
        except Exception as e:
            logger.warning("Node Edge-TTS: %s", e)

    def _start_go_llm_proxy(self) -> None:
        if self._ping_url(f"{self.llm_proxy_url}/ping"):
            logger.info("Go LLM proxy уже слушает :%s", LLM_PROXY_PORT)
            return
        if not self._go_launchable():
            logger.info("Go LLM proxy недоступен — прямой OpenRouter из Python")
            return
        try:
            env = os.environ.copy()
            env["JARBIS_LLM_PROXY_PORT"] = str(LLM_PROXY_PORT)
            env.setdefault("OPENROUTER_BASE_URL", config.OPENROUTER_BASE_URL)
            if config.API_KEY:
                env.setdefault("OPENAI_API_KEY", config.API_KEY)

            if GO_EXE.is_file():
                cmd = [str(GO_EXE)]
                cwd = str(GO_DIR)
            else:
                cmd = ["go", "run", "."]
                cwd = str(GO_DIR)

            with self._lock:
                self._go_proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    creationflags=self._win_flags(),
                )
            if self._wait_ping(f"{self.llm_proxy_url}/ping", self._go_proc):
                logger.info("Go LLM proxy sidecar :%s", LLM_PROXY_PORT)
        except Exception as e:
            logger.warning("Go LLM proxy: %s", e)

    def _wait_ping(self, url: str, proc: subprocess.Popen | None, attempts: int = 40) -> bool:
        for _ in range(attempts):
            if self._ping_url(url):
                return True
            if proc and proc.poll() is not None:
                logger.warning("Sidecar завершился при старте: %s", url)
                return False
            time.sleep(0.15)
        return False

    @staticmethod
    def _ping_url(url: str, timeout: float = 0.4) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def edge_tts_available(self) -> bool:
        return self._ping_url(f"{self.edge_tts_url}/ping")

    def llm_proxy_available(self) -> bool:
        return self._ping_url(f"{self.llm_proxy_url}/ping")

    def speak_edge(self, text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> str | None:
        """Озвучка через Node sidecar; возвращает путь к mp3 или None."""
        if not text.strip() or not self.edge_tts_available():
            return None
        try:
            payload = json.dumps(
                {"text": text, "voice": voice, "rate": rate, "pitch": pitch},
                ensure_ascii=False,
            ).encode("utf-8")
            req = urllib.request.Request(
                f"{self.edge_tts_url}/speak",
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok") and data.get("path"):
                return str(data["path"])
        except Exception as e:
            logger.warning("Node speak_edge: %s", e)
        return None

    def powershell_call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Вызов win_bridge.ps1 (JSON stdin → JSON stdout)."""
        if not PS1_BRIDGE.is_file():
            return {"ok": False, "error": "win_bridge.ps1 missing"}
        try:
            payload = json.dumps({"method": method, "params": params or {}}, ensure_ascii=False)
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(PS1_BRIDGE),
                ],
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                creationflags=self._win_flags(),
            )
            line = (proc.stdout or "").strip().splitlines()
            if not line:
                return {"ok": False, "error": proc.stderr or "empty ps output"}
            return json.loads(line[-1])
        except Exception as e:
            logger.warning("powershell_call %s: %s", method, e)
            return {"ok": False, "error": str(e)}

    def status(self) -> dict[str, Any]:
        ps = self.powershell_call("ping")
        return {
            "edge_tts_node": self.edge_tts_available(),
            "llm_proxy_go": self.llm_proxy_available(),
            "powershell": bool(ps.get("ok")),
            "edge_tts_port": EDGE_TTS_PORT,
            "llm_proxy_port": LLM_PROXY_PORT,
        }
