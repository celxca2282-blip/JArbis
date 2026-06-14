# assistant_engine.py
"""
Голосовой движок ассистента — цикл wake-word → STT → local → LLM.
Связь с GUI через EventBus.
"""

import logging
import re
import threading
import time
from typing import Callable, Optional

import config
import jarvis.commands.app_scanner as app_scanner
import jarvis.commands.commands_module as commands_module
import jarvis.commands.confirmations as confirmations
import jarvis.commands.scenario_runner as scenario_runner
import jarvis.ai.memory_module as memory_module
import jarvis.ai.response_processor as response_processor
import jarvis.ai.search_module as search_module
import jarvis.voice.stt_module as stt_module
import jarvis.core.stt_text_utils as stt_text_utils
from jarvis.core.app_state import AppStateSnapshot, AssistantStatus
from jarvis.core.event_bus import EventBus, EventType
from jarvis.core.performance_profiles import FAST_MODE_FALLBACK
from jarvis.voice.tts_module import cleanup_temp_audio, play_activation_sound, reload_tts_settings, speak, stop_speech
from jarvis.ai.llm_module import clear_conversation_history, get_ai_response, get_final_answer
from jarvis.voice.wake_word_module import (
    clear_wake_stop,
    get_wait_mode_message,
    get_wake_word_display_name,
    request_wake_stop,
    wait_for_jarvis,
)

logger = logging.getLogger(__name__)


# Проверяет, можно ли доверять распознанному тексту
def is_unreliable_stt(text: str, avg_logprob: float | None) -> bool:
    if stt_text_utils.is_prompt_hallucination(text):
        logger.warning("STT отклонён: похоже на галлюцинацию prompt")
        return True
    if stt_text_utils.is_garbage_stt(text):
        logger.warning("STT отклонён: бессмысленный текст")
        return True
    if not stt_module.is_confidence_acceptable(avg_logprob):
        logger.warning("STT отклонён: низкая уверенность (%.3f)", avg_logprob)
        return True
    return False


# Запрашивает голосовое подтверждение блокировки компьютера
def handle_lock_confirmation(engine: Optional["AssistantEngine"] = None) -> str:
    try:
        logger.info("Запрошено подтверждение блокировки компьютера")
        if engine:
            engine._set_status(AssistantStatus.SPEAKING)
        speak("Сэр, вы подтверждаете блокировку компьютера?", muted=engine.tts_muted if engine else False)

        if config.DEBUG_TEXT_MODE:
            confirmation_text = input("Подтверждение (да/нет): ").strip()
            avg_logprob = None
        else:
            if engine:
                engine._set_status(AssistantStatus.LISTENING)
            confirmation_text, avg_logprob = stt_module.listen_with_confidence(
                on_level=engine._publish_mic_level if engine else None,
                on_recording_done=(
                    lambda: engine._set_status(AssistantStatus.THINKING) if engine else None
                ),
            )
            if engine:
                engine._publish_mic_level(0.0)

        if not confirmation_text:
            speak("Действие отменено, сэр.", muted=engine.tts_muted if engine else False)
            return "Действие отменено, сэр."

        parsed = confirmations.parse_confirmation(confirmation_text)
        if parsed is True:
            return commands_module.lock_workstation()

        speak("Действие отменено, сэр.", muted=engine.tts_muted if engine else False)
        return "Действие отменено, сэр."
    except Exception as e:
        logger.error("Ошибка подтверждения блокировки: %s", e)
        speak("Действие отменено, сэр.", muted=engine.tts_muted if engine else False)
        return "Действие отменено, сэр."


# Преобразует результат команды в текст для озвучки
def resolve_command_result(result: str | bool, engine: Optional["AssistantEngine"] = None) -> str:
    if result == commands_module.NEEDS_LOCK_CONFIRMATION:
        return handle_lock_confirmation(engine)
    if isinstance(result, str):
        return result
    return "Не удалось выполнить команду, сэр."


# Выполняет команды и сохранение памяти из ответа LLM
def apply_llm_actions(
    commands_to_run: list[str],
    memories_to_save: list[tuple[str, str]],
    open_app_queries: list[str],
    original_text: str = "",
    engine: Optional["AssistantEngine"] = None,
) -> tuple[str | None, bool, bool, bool]:
    command_response = None
    control_executed = False
    command_failed = False

    if len(open_app_queries) > 1:
        logger.warning(
            "LLM вернул несколько OPEN_APP (%s), выполняю только первый: %s",
            len(open_app_queries),
            open_app_queries[0],
        )
        open_app_queries = open_app_queries[:1]

    for app_query in open_app_queries:
        command_response = commands_module.open_app_by_query(app_query, stt_text=original_text)
        control_executed = True
        logger.info("Команда распознана через ИИ (Ступень 2): OPEN_APP:%s", app_query)

    if open_app_queries:
        memory_executed = False
        for key, value in memories_to_save:
            if memory_module.save_memory_fact(key, value):
                memory_executed = True
                logger.info("Факт памяти сохранён через ИИ: %s = %s", key, value)
        return command_response, control_executed, memory_executed, command_failed

    if len(commands_to_run) > 1:
        logger.warning(
            "LLM вернул несколько команд (%s), выполняю только первую: %s",
            len(commands_to_run),
            commands_to_run[0],
        )
        commands_to_run = commands_to_run[:1]

    for command_name in commands_to_run:
        if command_name == "start_work" or command_name.startswith("run_scenario:"):
            scenario_id = command_name.split(":", 1)[1] if ":" in command_name else "preset-start-work"
            command_result = scenario_runner.run_scenario(scenario_id, engine.event_bus if engine else None)
            logger.info("Команда распознана через ИИ (Ступень 2): сценарий %s", scenario_id)
            control_executed = True
            command_response = command_result
            continue

        command_result = commands_module.execute_system_command(command_name)
        logger.info("Команда распознана через ИИ (Ступень 2): %s", command_name)

        if command_result is False:
            logger.warning("Команда из тега не выполнена или запрещена: %s", command_name)
            command_failed = True
            command_response = "Не удалось выполнить команду, сэр."
            continue

        if command_result == commands_module.NEEDS_LOCK_CONFIRMATION:
            control_executed = True
            command_response = handle_lock_confirmation(engine)
            continue

        if commands_module.is_control_action(command_name):
            control_executed = True
        if isinstance(command_result, str):
            command_response = command_result

    memory_executed = False
    for key, value in memories_to_save:
        if memory_module.save_memory_fact(key, value):
            memory_executed = True
            logger.info("Факт памяти сохранён через ИИ: %s = %s", key, value)

    return command_response, control_executed, memory_executed, command_failed


# Определяет, что пользователь хочет открыть программу
def is_launch_intent(text: str) -> bool:
    return (
        stt_text_utils.has_open_verb(text)
        or stt_text_utils.looks_like_launch_intent(text)
        or stt_text_utils.matches_phonetic_app_hint(text)
    )


# Обрабатывает ответ LLM: блокирует SEARCH при intent открытия, fallback на STT
def handle_post_llm(text: str, ai_response: str, engine: Optional["AssistantEngine"] = None) -> tuple[str, bool, bool]:
    launch_intent = is_launch_intent(text)

    raw_search_queries = response_processor.extract_search_queries(ai_response)

    if raw_search_queries and not launch_intent:
        search_query = raw_search_queries[0]
        logger.info("LLM запросил веб-поиск: %s", search_query)
        search_results = search_module.search_web(search_query)
        ai_response = get_final_answer(search_results, original_query=text)
    elif raw_search_queries and launch_intent:
        logger.warning(
            "LLM вернул SEARCH при запросе открытия приложения — поиск пропущен: %s",
            raw_search_queries[0],
        )

    response, commands_to_run, memories_to_save, open_app_queries = (
        response_processor.process_llm_response(ai_response)
    )
    command_response, control_executed, memory_executed, command_failed = apply_llm_actions(
        commands_to_run,
        memories_to_save,
        open_app_queries,
        original_text=text,
        engine=engine,
    )

    need_stt_fallback = (
        launch_intent
        and not open_app_queries
        and not commands_to_run
        and command_response is None
    )
    if need_stt_fallback and (raw_search_queries or not response.strip()):
        command_response = commands_module.open_app_from_stt_text(text)
        control_executed = True
        logger.info("Fallback OPEN_APP из STT (SEARCH или пустой ответ LLM)")

    if command_response is not None:
        response = command_response
    elif command_failed:
        response = "Не удалось выполнить команду, сэр."
    elif memory_executed and not response:
        response = "Запомнил это, сэр."
    elif launch_intent and not response.strip():
        response = commands_module.open_app_from_stt_text(text)
        control_executed = True
    elif not response:
        response = "Выполняю, сэр."

    return response, control_executed, memory_executed


class AssistantEngine:
    """Фоновый голосовой цикл ассистента."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus or EventBus.instance()
        self.state = AppStateSnapshot()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._text_queue: list[str] = []
        self._text_lock = threading.Lock()
        self.tts_muted = False
        self._mic_test_pending = False
        self._mic_test_callback: Callable[[str], None] | None = None

    @property
    def is_running(self) -> bool:
        return self.state.is_running

    def _set_status(self, status: AssistantStatus) -> None:
        self.state.status = status
        self.event_bus.publish(EventType.STATUS_CHANGED, {"status": status.value})

    def _log_event(self, message: str) -> None:
        self.state.append_event(message)
        self.event_bus.publish(EventType.LOG_LINE, {"message": message})
        logger.info(message)

    def _publish_mic_level(self, level: float) -> None:
        """Отправляет уровень микрофона в GUI для орба."""
        try:
            self.event_bus.publish(EventType.MIC_LEVEL, {"level": max(0.0, min(1.0, level))})
        except Exception:
            pass

    def reload_config(self) -> None:
        try:
            config.load_gui_settings()
            reload_tts_settings()
            stt_module.reload_stt_model_if_needed()
            self._log_event("Настройки перезагружены")
        except Exception as e:
            logger.error("Ошибка reload_config: %s", e)

    def start(self) -> None:
        if self.state.is_running:
            return
        self._stop_event.clear()
        self.state.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AssistantEngine")
        self._thread.start()
        self.event_bus.publish(EventType.ENGINE_STARTED, {})
        self._log_event("Ассистент запущен")

    def stop(self) -> None:
        self._stop_event.set()
        stop_speech()
        request_wake_stop()
        self.state.is_running = False
        self._set_status(AssistantStatus.IDLE)
        self.event_bus.publish(EventType.ENGINE_STOPPED, {})
        self._log_event("Ассистент остановлен")

    def submit_text_command(self, text: str) -> None:
        with self._text_lock:
            self._text_queue.append(text.strip())

    def run_scenario(self, scenario_id: str) -> str:
        self._set_status(AssistantStatus.THINKING)
        result = scenario_runner.run_scenario(scenario_id, self.event_bus)
        self.state.last_response = result
        self.event_bus.publish(EventType.RESPONSE, {"text": result})
        self._set_status(AssistantStatus.IDLE)
        return result

    def request_mic_test(self, on_complete: Callable[[str], None]) -> None:
        """Запрашивает тест микрофона в потоке движка (не блокирует GUI)."""
        self._mic_test_callback = on_complete
        self._mic_test_pending = True
        request_wake_stop()

    def _run_mic_test(self) -> str:
        try:
            self._set_status(AssistantStatus.LISTENING)
            self.state.last_response = "Скажите что-нибудь (4 сек)…"
            self.event_bus.publish(EventType.RESPONSE, {"text": self.state.last_response})

            mic = stt_module.get_mic_info()
            level_hint = ""
            if not mic["level_ok"]:
                level_hint = " Уровень тихий — поднимите громкость микрофона."

            text, logprob = stt_module.listen_mic_test(
                max_duration_sec=4.0,
                on_level=self._publish_mic_level,
            )
            self._publish_mic_level(0.0)
            self._set_status(AssistantStatus.IDLE)

            base = f"{mic['name']} · {mic['sample_rate']} Hz · peak {mic['peak']:.4f}"
            if not text:
                return f"Речь не распознана.{level_hint} ({base})"
            prob = f", уверенность {logprob:.2f}" if logprob is not None else ""
            return f"«{text}»{prob}. {base}"
        except Exception as e:
            self._set_status(AssistantStatus.ERROR)
            return f"Ошибка микрофона: {e}"
        finally:
            clear_wake_stop()

    def test_microphone(self) -> str:
        """Синхронный тест (для CLI). В GUI используйте request_mic_test."""
        return self._run_mic_test()

    def _speak(self, text: str) -> None:
        if self.tts_muted or self._stop_event.is_set():
            return
        self._set_status(AssistantStatus.SPEAKING)
        speak(text, muted=False)
        if not self._stop_event.is_set():
            self._set_status(AssistantStatus.IDLE)

    def _process_command_text(self, text: str, avg_logprob: float | None = None) -> bool:
        """Обрабатывает одну команду. False = выход из цикла."""
        if not text:
            self._log_event("STT: тишина или низкая уверенность")
            self.state.last_response = "Не расслышал, повторите, сэр."
            self.event_bus.publish(EventType.RESPONSE, {"text": self.state.last_response})
            self._speak(self.state.last_response)
            return True

        raw_stt = text
        self.state.last_stt_raw = raw_stt
        self.event_bus.publish(EventType.STT_RAW, {"text": raw_stt})
        self._log_event(f"STT raw: {raw_stt}")

        if not config.DEBUG_TEXT_MODE and is_unreliable_stt(text, avg_logprob):
            self.state.last_response = "Не расслышал, повторите, сэр."
            self.event_bus.publish(EventType.RESPONSE, {"text": self.state.last_response})
            self._speak(self.state.last_response)
            return True

        text = stt_text_utils.normalize_stt_text(text)
        self.state.last_stt_normalized = text
        self.event_bus.publish(EventType.STT_NORMALIZED, {"text": text})
        self._log_event(f"STT normalized: {text}")

        if config.DEBUG_TEXT_MODE and (
            stt_text_utils.is_prompt_hallucination(text)
            or stt_text_utils.is_garbage_stt(text)
        ):
            self.state.last_response = "Не расслышал, повторите, сэр."
            self.event_bus.publish(EventType.RESPONSE, {"text": self.state.last_response})
            return True

        clean_text = re.sub(r"[^\w\s]", "", text.lower())
        if any(cmd in clean_text for cmd in ["стоп", "выход", "завершить", "пока"]):
            self._log_event("Команда выхода")
            self.state.last_response = "Отключаюсь, сэр."
            self._speak(self.state.last_response)
            return False

        local_response = commands_module.check_local_keywords(text)
        if local_response is not None:
            self._log_event("path=local (ступень 1)")
            final_response = resolve_command_result(local_response, self)
            self.state.last_response = final_response
            self.event_bus.publish(EventType.RESPONSE, {"text": final_response})
            self._speak(final_response)
            clear_conversation_history()
            return True

        if raw_stt != text and is_launch_intent(text):
            pre_llm = commands_module.open_app_from_stt_text(text)
            if pre_llm and "не найдено" not in pre_llm.lower():
                self._log_event("path=local (phonetic retry)")
                self.state.last_response = pre_llm
                self.event_bus.publish(EventType.RESPONSE, {"text": pre_llm})
                self._speak(pre_llm)
                clear_conversation_history()
                return True

        # Быстрый режим: без LLM — только local + открытие приложений
        if config.FAST_MODE:
            if is_launch_intent(text) or stt_text_utils.has_open_verb(text):
                app_result = commands_module.open_app_from_stt_text(text)
                if app_result and "не найдено" not in app_result.lower():
                    self._log_event("path=local (fast open app)")
                    self.state.last_response = app_result
                    self.event_bus.publish(EventType.RESPONSE, {"text": app_result})
                    self._speak(app_result)
                    return True

            self._log_event("path=fast (LLM пропущен)")
            self.state.last_response = FAST_MODE_FALLBACK
            self.event_bus.publish(EventType.RESPONSE, {"text": self.state.last_response})
            self._speak(self.state.last_response)
            return True

        self._set_status(AssistantStatus.THINKING)
        self._log_event("path=LLM (ступень 2)")
        ai_response = get_ai_response(text)
        response, control_executed, memory_executed = handle_post_llm(text, ai_response, engine=self)

        self.state.last_response = response
        self.event_bus.publish(EventType.RESPONSE, {"text": response})
        self._speak(response)
        if control_executed or memory_executed:
            clear_conversation_history()
        return True

    def _run_loop(self) -> None:
        try:
            cleanup_temp_audio()
            if config.APP_SCAN_ON_STARTUP:
                try:
                    app_scanner.load_or_build_index()
                except Exception as e:
                    logger.warning("Индекс приложений при старте: %s", e)

            if not config.DEBUG_TEXT_MODE:
                stt_module.init_stt()
                wake_word = get_wake_word_display_name()
                greeting = f"Сэр, системы в норме. Скажите «{wake_word}», когда будете готовы."
                self._speak(greeting)

            self._set_status(AssistantStatus.IDLE)

            while not self._stop_event.is_set():
                with self._text_lock:
                    if self._text_queue:
                        queued = self._text_queue.pop(0)
                        self._process_command_text(queued, None)
                        continue

                if config.DEBUG_TEXT_MODE:
                    time.sleep(0.2)
                    continue

                self._set_status(AssistantStatus.IDLE)
                self._log_event(get_wait_mode_message())
                woke = wait_for_jarvis()
                clear_wake_stop()

                if self._mic_test_pending:
                    self._mic_test_pending = False
                    result = self._run_mic_test()
                    self.state.last_response = result
                    self._log_event(f"Тест микрофона: {result}")
                    self.event_bus.publish(EventType.RESPONSE, {"text": result})
                    if self._mic_test_callback:
                        cb = self._mic_test_callback
                        self._mic_test_callback = None
                        cb(result)
                    continue

                if not woke:
                    continue

                self._set_status(AssistantStatus.WAKE)
                play_activation_sound()
                self._set_status(AssistantStatus.LISTENING)
                time.sleep(config.STT_POST_ACTIVATION_DELAY_SEC)
                text, avg_logprob = stt_module.listen_with_confidence(
                    on_level=self._publish_mic_level,
                    on_recording_done=lambda: self._set_status(AssistantStatus.THINKING),
                )
                self._publish_mic_level(0.0)

                if not self._process_command_text(text, avg_logprob):
                    self.stop()
                    break

        except Exception as e:
            logger.exception("Критическая ошибка в движке")
            self._set_status(AssistantStatus.ERROR)
            self.event_bus.publish(EventType.ERROR, {"message": str(e)})

    def run_cli_loop(self) -> None:
        """Блокирующий консольный режим (как старый main)."""
        logger.info("=== Джарвис — консольный режим ===")
        cleanup_temp_audio()
        if config.APP_SCAN_ON_STARTUP:
            try:
                app_scanner.load_or_build_index()
            except Exception as e:
                logger.warning("Индекс: %s", e)

        if config.DEBUG_TEXT_MODE:
            print("DEBUG_TEXT_MODE. Пишите команды текстом.")
        else:
            stt_module.init_stt()
            wake_word = get_wake_word_display_name()
            speak(f"Сэр, системы в норме. Скажите «{wake_word}», когда будете готовы.")

        self.state.is_running = True
        try:
            while True:
                with self._text_lock:
                    if self._text_queue:
                        if not self._process_command_text(self._text_queue.pop(0), None):
                            break
                        continue

                if config.DEBUG_TEXT_MODE:
                    text = input("Вы (текст): ").strip()
                    avg_logprob = None
                else:
                    print(get_wait_mode_message())
                    wait_for_jarvis()
                    play_activation_sound()
                    print("Слушаю вас, сэр...")
                    time.sleep(config.STT_POST_ACTIVATION_DELAY_SEC)
                    text, avg_logprob = stt_module.listen_with_confidence(
                        on_level=self._publish_mic_level,
                        on_recording_done=lambda: self._set_status(AssistantStatus.THINKING),
                    )
                    self._publish_mic_level(0.0)

                if not self._process_command_text(text, avg_logprob):
                    break
        except Exception:
            logger.exception("Критическая ошибка в CLI")
        finally:
            self.state.is_running = False
            self._set_status(AssistantStatus.IDLE)
