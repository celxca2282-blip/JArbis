# cpp_core_client.py
"""TCP-клиент к C++ jarbis.exe --core-server (гибридный режим)."""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_PORT = 17847
DEFAULT_HOST = "127.0.0.1"


def find_cpp_exe() -> Path | None:
    """Ищет jarbis.exe: env → соседняя папка JArbisC++ → legacy C:\\ путь."""
    import config

    env = os.environ.get("JARBIS_CPP_EXE", "").strip()
    if env:
        path = Path(env)
        if path.is_file():
            return path
    candidates = [
        config.BASE_DIR.parent / "JArbisC++" / "build" / "Release" / "jarbis.exe",
        config.BASE_DIR / "engine-cpp" / "build" / "Release" / "jarbis.exe",
        Path(r"C:\JArbisC++\build\Release\jarbis.exe"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


class CppCoreClient:
    """Держит процесс C++ core-server и JSON-RPC по одному TCP-сокету."""

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self.port = port
        self.host = DEFAULT_HOST
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._next_id = 1
        self._pending: dict[int, threading.Event] = {}
        self._responses: dict[int, dict[str, Any]] = {}
        self._reader: threading.Thread | None = None
        self._running = False
        self.on_event: Callable[[dict[str, Any]], None] | None = None
        self.available = False

    def start_process(self) -> bool:
        """Запускает jarbis.exe --core-server и подключается."""
        if self._sock:
            self.available = True
            return True

        if not self._connect_with_retry(start_server=True):
            return False
        self.available = True
        logger.info("C++ core-server: %s:%s", self.host, self.port)
        return True

    def _connect_with_retry(self, start_server: bool = False) -> bool:
        # Сначала пробуем подключиться к уже запущенному core-server
        for _ in range(5):
            try:
                sock = socket.create_connection((self.host, self.port), timeout=0.3)
                self._sock = sock
                self._running = True
                self._reader = threading.Thread(target=self._read_loop, daemon=True, name="CppCoreReader")
                self._reader.start()
                return True
            except OSError:
                time.sleep(0.08)

        if start_server and not self._proc:
            exe = find_cpp_exe()
            if not exe:
                logger.warning("jarbis.exe не найден")
                return False
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
                env = os.environ.copy()
                try:
                    import config as _cfg

                    env["JARBIS_PYTHON_ROOT"] = str(_cfg.BASE_DIR)
                except Exception:
                    pass
                self._proc = subprocess.Popen(
                    [str(exe), "--core-server", str(self.port)],
                    cwd=str(exe.parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    env=env,
                )
            except Exception as e:
                logger.error("Запуск C++ core: %s", e)
                return False

        for _ in range(50):
            try:
                sock = socket.create_connection((self.host, self.port), timeout=0.3)
                self._sock = sock
                self._running = True
                self._reader = threading.Thread(target=self._read_loop, daemon=True, name="CppCoreReader")
                self._reader.start()
                return True
            except OSError:
                if self._proc and self._proc.poll() is not None:
                    return False
                time.sleep(0.12)
        return False

    def _read_loop(self) -> None:
        buffer = ""
        sock = self._sock
        if not sock:
            return
        while self._running:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "event":
                        if self.on_event:
                            self.on_event(msg)
                    elif msg.get("type") == "resp":
                        rid = int(msg.get("id", 0))
                        with self._send_lock:
                            self._responses[rid] = msg
                            ev = self._pending.pop(rid, None)
                        if ev:
                            ev.set()
            except OSError:
                break
        self._running = False
        self.available = False

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 120.0) -> dict[str, Any]:
        """JSON-RPC вызов с ожиданием ответа."""
        if not self._sock and not self.start_process():
            raise RuntimeError("C++ core недоступен")

        with self._send_lock:
            req_id = self._next_id
            self._next_id += 1
            event = threading.Event()
            self._pending[req_id] = event
            payload = json.dumps(
                {"type": "req", "id": req_id, "method": method, "params": params or {}},
                ensure_ascii=False,
            ) + "\n"

        try:
            assert self._sock is not None
            self._sock.sendall(payload.encode("utf-8"))
            if not event.wait(timeout):
                raise TimeoutError(f"C++ core timeout: {method}")
            with self._send_lock:
                msg = self._responses.pop(req_id, {})
            if "error" in msg:
                raise RuntimeError(str(msg["error"]))
            return msg.get("result") or {}
        finally:
            with self._send_lock:
                self._pending.pop(req_id, None)
                self._responses.pop(req_id, None)

    def shutdown(self) -> None:
        self._running = False
        try:
            if self.available and self._sock:
                self.call("shutdown", timeout=5.0)
        except Exception:
            pass
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                pass
        self.available = False
