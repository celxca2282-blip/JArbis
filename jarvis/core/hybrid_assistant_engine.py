# hybrid_assistant_engine.py
"""
Гибридный движок: Python CustomTkinter GUI + C++ core-server (голос, команды).
При недоступности C++ — fallback на чистый Python AssistantEngine.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable

import config
from jarvis.core.app_state import AppStateSnapshot, AssistantStatus
from jarvis.core.assistant_engine import AssistantEngine
from jarvis.core.cpp_core_client import CppCoreClient
from jarvis.core.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)


class BootEngine:
    """Заглушка движка — окно GUI рисуется сразу, C++ подключается в фоне."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self._state = AppStateSnapshot()
        self._tts_muted = False

    @property
    def state(self) -> AppStateSnapshot:
        return self._state

    @property
    def tts_muted(self) -> bool:
        return self._tts_muted

    @tts_muted.setter
    def tts_muted(self, value: bool) -> None:
        self._tts_muted = value

    @property
    def is_running(self) -> bool:
        return self._state.is_running

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def submit_text_command(self, text: str) -> None:
        logger.info("Движок ещё загружается, команда отложена: %s", text[:80])

    def run_scenario(self, scenario_id: str) -> str:
        return "Движок ещё загружается, подождите несколько секунд."

    def run_scenario_async(self, scenario_id: str, on_complete: Callable[[str], None]) -> None:
        on_complete("Движок ещё загружается, подождите несколько секунд.")

    def reload_app_index(self, *, force_rescan: bool = True, delete: bool = False) -> None:
        pass

    def request_mic_test(self, on_complete: Callable[[str], None]) -> None:
        on_complete("Движок ещё загружается, подождите несколько секунд.")

    def reload_config(self, *, reload_stt: bool = True, reload_tts: bool = True) -> None:
        pass

    def shutdown(self) -> None:
        pass


class HybridAssistantEngine:
    """Обёртка с API как у AssistantEngine для GUI."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus or EventBus.instance()
        self._state = AppStateSnapshot()
        self._tts_muted = False
        self._client = CppCoreClient()
        self._fallback: AssistantEngine | None = None
        self._use_cpp = os.environ.get("JARBIS_HYBRID", "1").lower() not in ("0", "false", "no")
        self._state_lock = threading.Lock()

        if self._use_cpp and self._client.start_process():
            self._client.on_event = self._on_cpp_event
            self._sync_state_from_cpp()
            ping = self._client.call("ping")
            ver = ping.get("version", "?")
            self._verify_shared_paths(ping)
            logger.info("Гибрид: UI Python + движок C++ %s", ver)
        else:
            self._fallback = AssistantEngine(self.event_bus)
            logger.info("Гибрид: fallback на Python AssistantEngine")

    def _verify_shared_paths(self, ping: dict) -> None:
        """Предупреждает, если C++ читает не тот data/, что Python GUI."""
        try:
            py_apps = str(config.DATA_DIR / "user_apps.json")
            cpp_apps = ping.get("user_apps_path", "")
            if cpp_apps and Path(cpp_apps).resolve() != Path(py_apps).resolve():
                logger.warning("C++ data ≠ Python: %s vs %s", cpp_apps, py_apps)
        except Exception as e:
            logger.debug("verify paths: %s", e)

    @property
    def state(self) -> AppStateSnapshot:
        if self._fallback:
            return self._fallback.state
        return self._state

    @property
    def tts_muted(self) -> bool:
        if self._fallback:
            return self._fallback.tts_muted
        return self._tts_muted

    @tts_muted.setter
    def tts_muted(self, value: bool) -> None:
        if self._fallback:
            self._fallback.tts_muted = value
            return
        self._tts_muted = value
        self._run_rpc_async("set_mute", {"muted": value}, timeout=5.0)

    @property
    def is_running(self) -> bool:
        return self.state.is_running

    def _on_cpp_event(self, msg: dict) -> None:
        """Пробрасывает события C++ в Python EventBus."""
        name = msg.get("event", "")
        data = msg.get("data") or {}
        try:
            if name == "status_changed":
                status = data.get("status", "idle")
                with self._state_lock:
                    try:
                        self._state.status = AssistantStatus(status)
                    except ValueError:
                        self._state.status = AssistantStatus.IDLE
                self.event_bus.publish(EventType.STATUS_CHANGED, {"status": status})
            elif name == "log_line":
                text = data.get("message") or data.get("text") or ""
                with self._state_lock:
                    self._state.append_event(text)
                self.event_bus.publish(EventType.LOG_LINE, {"message": text})
            elif name == "mic_level":
                level = float(data.get("level", 0.0))
                self.event_bus.publish(EventType.MIC_LEVEL, {"level": level})
            elif name == "response":
                text = data.get("text") or ""
                with self._state_lock:
                    self._state.last_response = text
                self.event_bus.publish(EventType.RESPONSE, {"text": text})
            elif name == "stt_raw":
                with self._state_lock:
                    self._state.last_stt_raw = data.get("text") or ""
                self.event_bus.publish(EventType.STT_RAW, {"text": self._state.last_stt_raw})
            elif name == "stt_normalized":
                with self._state_lock:
                    self._state.last_stt_normalized = data.get("text") or ""
                self.event_bus.publish(EventType.STT_NORMALIZED, {"text": self._state.last_stt_normalized})
            elif name == "engine_started":
                with self._state_lock:
                    self._state.is_running = True
                self.event_bus.publish(EventType.ENGINE_STARTED, {})
            elif name == "engine_stopped":
                with self._state_lock:
                    self._state.is_running = False
                self.event_bus.publish(EventType.ENGINE_STOPPED, {})
            elif name == "scenario_step_started":
                self.event_bus.publish(
                    EventType.SCENARIO_STEP_STARTED,
                    {
                        "scenario_id": data.get("scenario_id", ""),
                        "scenario_name": data.get("scenario_name", ""),
                        "step_index": int(data.get("step_index", 0)),
                        "step_total": int(data.get("step_total", 1)),
                    },
                )
            elif name == "scenario_completed":
                self.event_bus.publish(
                    EventType.SCENARIO_COMPLETED,
                    {
                        "scenario_id": data.get("scenario_id", ""),
                        "success": bool(data.get("success", True)),
                    },
                )
            elif name == "error":
                text = data.get("message") or data.get("text") or "Ошибка C++"
                self.event_bus.publish(EventType.LOG_LINE, {"message": text})
        except Exception as e:
            logger.error("cpp event: %s", e)

    def _sync_state_from_cpp(self) -> None:
        try:
            snap = self._client.call("get_state", timeout=5.0)
            with self._state_lock:
                self._state.is_running = bool(snap.get("is_running"))
                self._tts_muted = bool(snap.get("tts_muted"))
                self._state.last_stt_raw = snap.get("last_stt_raw") or ""
                self._state.last_stt_normalized = snap.get("last_stt_normalized") or ""
                self._state.last_response = snap.get("last_response") or ""
                self._state.event_log = list(snap.get("event_log") or [])
                try:
                    self._state.status = AssistantStatus(snap.get("status", "idle"))
                except ValueError:
                    self._state.status = AssistantStatus.IDLE
        except Exception as e:
            logger.warning("sync state: %s", e)

    def reload_config(self, *, reload_stt: bool = True, reload_tts: bool = True) -> None:
        if self._fallback:
            self._fallback.reload_config(reload_stt=reload_stt, reload_tts=reload_tts)
            return
        try:
            config.load_gui_settings()

            def worker() -> None:
                try:
                    self._client.call(
                        "reload_runtime",
                        {"reload_stt": reload_stt, "reload_tts": reload_tts},
                        timeout=60.0,
                    )
                    self._sync_state_from_cpp()
                except Exception as e:
                    logger.error("reload_config hybrid: %s", e)

            threading.Thread(target=worker, daemon=True, name="CppReload").start()
        except Exception as e:
            logger.error("reload_config hybrid: %s", e)

    def reload_app_index(self, *, force_rescan: bool = True, delete: bool = False) -> None:
        """Синхронизирует индекс приложений C++ с Python data/."""
        if self._fallback:
            return
        self._run_rpc_async(
            "reload_app_index",
            {"force_rescan": force_rescan, "delete": delete},
            timeout=120.0,
        )

    def _run_rpc_async(self, method: str, params: dict | None = None, timeout: float = 30.0) -> None:
        """RPC к C++ без блокировки GUI-потока."""

        def worker() -> None:
            try:
                self._client.call(method, params, timeout=timeout)
            except Exception as e:
                logger.warning("cpp %s: %s", method, e)

        threading.Thread(target=worker, daemon=True, name=f"CppRpc-{method}").start()

    def start(self) -> None:
        if self._fallback:
            self._fallback.start()
            return
        if self.state.is_running:
            return
        with self._state_lock:
            self._state.is_running = True
        self.event_bus.publish(EventType.ENGINE_STARTED, {})
        self._run_rpc_async("start", timeout=60.0)

    def stop(self) -> None:
        if self._fallback:
            self._fallback.stop()
            return
        with self._state_lock:
            self._state.is_running = False
            self._state.status = AssistantStatus.IDLE
        self.event_bus.publish(EventType.ENGINE_STOPPED, {})
        self.event_bus.publish(EventType.STATUS_CHANGED, {"status": "idle"})
        self._run_rpc_async("stop", timeout=30.0)

    def submit_text_command(self, text: str) -> None:
        if self._fallback:
            self._fallback.submit_text_command(text)
            return
        self._run_rpc_async("submit_text", {"text": text.strip()}, timeout=120.0)

    def run_scenario(self, scenario_id: str) -> str:
        """Синхронный запуск — для fallback; в гибриде используйте run_scenario_async."""
        if self._fallback:
            return self._fallback.run_scenario(scenario_id)
        done = threading.Event()
        result_holder: list[str] = [""]

        def on_complete(text: str) -> None:
            result_holder[0] = text
            done.set()

        self.run_scenario_async(scenario_id, on_complete)
        done.wait(timeout=300.0)
        return result_holder[0] or "Таймаут сценария."

    def run_scenario_async(self, scenario_id: str, on_complete: Callable[[str], None]) -> None:
        """Запуск сценария в C++ без блокировки GUI."""
        if self._fallback:
            result = self._fallback.run_scenario(scenario_id)
            on_complete(result)
            return

        with self._state_lock:
            self._state.status = AssistantStatus.THINKING
        self.event_bus.publish(EventType.STATUS_CHANGED, {"status": "thinking"})

        def worker() -> None:
            try:
                resp = self._client.call("run_scenario", {"scenario_id": scenario_id}, timeout=300.0)
                text = resp.get("text") or "Сценарий завершён."
            except Exception as e:
                text = f"Ошибка: {e}"
            with self._state_lock:
                self._state.last_response = text
                self._state.status = AssistantStatus.IDLE
            self.event_bus.publish(EventType.RESPONSE, {"text": text})
            self.event_bus.publish(EventType.STATUS_CHANGED, {"status": "idle"})
            on_complete(text)

        threading.Thread(target=worker, daemon=True, name="CppScenario").start()

    def request_mic_test(self, on_complete: Callable[[str], None]) -> None:
        if self._fallback:
            self._fallback.request_mic_test(on_complete)
            return

        def worker() -> None:
            try:
                result = self._client.call("mic_test", timeout=35.0)
                text = result.get("text") or "Ошибка теста микрофона."
                on_complete(text)
            except Exception as e:
                on_complete(f"Ошибка: {e}")

        threading.Thread(target=worker, daemon=True, name="MicTestHybrid").start()

    def shutdown(self) -> None:
        if self._fallback:
            self._fallback.stop()
        else:
            try:
                self._client.shutdown()
            except Exception:
                pass
