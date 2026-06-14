# commands_module.py
"""
Модуль локального управления компьютером (Вектор 1: Руки).
Ступень 1: ключевые слова. Ступень 2: теги [EXEC:...] из ответа ИИ.
"""

import json
import logging
import os
import re
import webbrowser
from typing import Callable, Optional
from urllib.request import Request, urlopen

import keyboard
from pycaw.pycaw import AudioUtilities

from jarvis.commands import app_scanner
from jarvis.commands.app_scanner import AppEntry
from jarvis.commands import command_registry
from jarvis.ai import memory_module
from jarvis.commands.skills import get_time
from jarvis.core import stt_text_utils

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("commands_module")

WEATHER_URL = "https://wttr.in/?lang=ru&format=%C,+%t"
WEATHER_TIMEOUT = 3
WEATHER_HEADERS = {"User-Agent": "curl/7.64.1"}

CommandResult = str | bool
NEEDS_LOCK_CONFIRMATION = command_registry.NEEDS_LOCK_CONFIRMATION

# Реэкспорт для обратной совместимости тестов и main
normalize_stt_text = stt_text_utils.normalize_stt_text
is_prompt_hallucination = stt_text_utils.is_prompt_hallucination
is_garbage_stt = stt_text_utils.is_garbage_stt


# Сохраняет профиль пользователя в JSON-файл
def _write_user_profile(profile: dict) -> None:
    with memory_module.USER_PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
        json.dump(profile, profile_file, ensure_ascii=False, indent=2)


# Физически очищает долговременную память пользователя
def clear_user_memory() -> str:
    try:
        empty_profile = {"user_info": {}}
        _write_user_profile(empty_profile)
        logger.info("Локальный профиль пользователя полностью очищен")
        return "Вся память о вас успешно стёрта, сэр. Локальный профиль пуст."
    except Exception as e:
        logger.error("Ошибка очистки профиля пользователя: %s", e)
        return "Не удалось очистить профиль, сэр."


# Подготавливает текст погоды для озвучки
def _format_weather_for_speech(weather_text: str) -> str:
    cleaned = weather_text.strip()
    cleaned = cleaned.replace("+", "плюс ")
    cleaned = cleaned.replace("-", "минус ")
    cleaned = cleaned.replace("°C", " градусов")
    cleaned = re.sub(r"(?<=\d)\s*C\b", " градусов", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# Запрашивает погоду с wttr.in
def _fetch_weather() -> str:
    if requests is not None:
        response = requests.get(WEATHER_URL, timeout=WEATHER_TIMEOUT, headers=WEATHER_HEADERS)
        response.raise_for_status()
        return response.text.strip()

    request = Request(WEATHER_URL, headers=WEATHER_HEADERS)
    with urlopen(request, timeout=WEATHER_TIMEOUT) as response:
        return response.read().decode("utf-8").strip()


# Открывает браузер с поисковой страницей
def _cmd_open_browser() -> str:
    try:
        logger.info("Запуск команды: open_browser")
        webbrowser.open("https://google.com")
        return "Открываю браузер, сэр."
    except Exception as e:
        logger.error("Ошибка открытия браузера: %s", e)
        return "Не удалось открыть браузер, сэр."


# Запрашивает подтверждение блокировки (выполняется в main.py)
def _cmd_lock_pc() -> str:
    logger.info("Запуск команды: lock_pc (требуется подтверждение)")
    return NEEDS_LOCK_CONFIRMATION


# Блокирует рабочую станцию Windows
def lock_workstation() -> str:
    try:
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Система заблокирована, сэр."
    except Exception as e:
        logger.error("Ошибка блокировки компьютера: %s", e)
        return "Не удалось заблокировать систему, сэр."


# Получает погоду через wttr.in
def _cmd_get_weather() -> str:
    try:
        logger.info("Запуск команды: get_weather")
        weather_text = _fetch_weather()
        cleaned_weather_text = _format_weather_for_speech(weather_text)
        return f"По данным метеослужбы, сейчас на улице {cleaned_weather_text}, сэр."
    except Exception as e:
        logger.error("Ошибка получения погоды: %s", e)
        return "Не удалось связаться со спутником погоды, сэр."


# Переключает паузу/воспроизведение в медиаплеере
def _cmd_media_play_pause() -> str:
    try:
        logger.info("Запуск команды: media_play_pause")
        keyboard.send("play/pause media")
        return "Выполняю, сэр."
    except Exception as e:
        logger.error("Ошибка команды play/pause: %s", e)
        return "Не удалось управлять воспроизведением, сэр."


# Переключает медиаплеер на следующий трек
def _cmd_media_next() -> str:
    try:
        logger.info("Запуск команды: media_next")
        keyboard.send("next track")
        return "Включаю следующий трек."
    except Exception as e:
        logger.error("Ошибка переключения трека: %s", e)
        return "Не удалось переключить трек, сэр."


# Полностью отключает системный звук
def _cmd_volume_mute() -> str:
    try:
        logger.info("Запуск команды: volume_mute")
        devices = AudioUtilities.GetSpeakers()
        volume = devices.EndpointVolume
        volume.SetMute(1, None)
        return "Звук выключен, сэр."
    except Exception as e:
        logger.error("Ошибка COM-интерфейса при отключении звука: %s", e)
        return "Не удалось отключить звук, сэр."


# Устанавливает системную громкость в процентах
def _cmd_set_volume(percent: int) -> str:
    try:
        vol_level = float(max(0, min(100, int(percent))))
        logger.info("Запуск команды: volume_%s", int(vol_level))
        devices = AudioUtilities.GetSpeakers()
        volume = devices.EndpointVolume
        volume.SetMute(0, None)
        volume.SetMasterVolumeLevelScalar(vol_level / 100.0, None)
        return f"Установил громкость на {int(vol_level)} процентов, сэр."
    except Exception as e:
        logger.error("Ошибка COM-интерфейса при установке громкости: %s", e)
        return "Не удалось установить громкость, сэр."


# Открывает раздел настроек или приложение Windows
def _cmd_open_target(target_key: str) -> str:
    target = command_registry.SYSTEM_TARGETS.get(target_key)
    if target is None:
        logger.warning("Неизвестная системная цель: %s", target_key)
        return "Не удалось выполнить команду, сэр."

    try:
        uri = target["uri"]
        logger.info("Запуск системной цели: %s (%s)", target_key, uri)
        os.startfile(uri)
        return target["response"]
    except Exception as e:
        logger.error("Ошибка запуска цели %s: %s", target_key, e)
        return f"Не удалось открыть {target['description']}, сэр."


# Создаёт обработчик whitelist-команды для системной цели
def _make_target_command(target_key: str) -> Callable[[], str]:
    def _command() -> str:
        return _cmd_open_target(target_key)

    return _command


# Запускает сценарий workflow (делегирует в scenario_runner)
def execute_workflow(workflow_name: str) -> str:
    try:
        from jarvis.commands import scenario_runner, scenario_store

        scenario_store.ensure_scenarios_file()
        scenario = scenario_store.find_by_id_or_legacy_name(workflow_name)
        if scenario:
            return scenario_runner.run_scenario(scenario.id)

        workflows = command_registry.WORKFLOWS
        if workflow_name not in workflows:
            return f"Сценарий '{workflow_name}' не найден."

        workflow = workflows[workflow_name]
        logger.info("Запуск legacy-сценария: %s", workflow_name)

        for site in workflow["sites"]:
            webbrowser.open(site)

        for app in workflow["apps"]:
            try:
                os.startfile(app)
            except Exception as e:
                logger.error("Ошибка запуска %s: %s", app, e)

        return f"Сценарий '{workflow_name}' выполнен. Всё готово, сэр."
    except Exception as e:
        logger.error("Ошибка выполнения сценария %s: %s", workflow_name, e)
        return f"Не удалось выполнить сценарий '{workflow_name}', сэр."


# Шаблоны запросов, которые обрабатываются фиксированными командами, а не сканером
_RESERVED_APP_QUERY_PATTERNS: tuple[str, ...] = (
    r"настрой",
    r"стройк",
    r"калькулятор|calc",
    r"блокнот",
    r"paint|паинт|пейнт",
    r"проводник",
    r"командн.*строк|консоль|терминал",
    r"диспетчер|task manager|taskmgr",
    r"браузер",
    r"browser",
)


# Извлекает имя приложения из фразы «открой X», если X не зарезервировано
def _extract_app_query(text: str) -> str | None:
    cleaned = _normalize_text(text)

    if not stt_text_utils.has_open_verb(cleaned):
        return None

    if _match_fuzzy_settings(text):
        return None

    for pattern in _RESERVED_APP_QUERY_PATTERNS:
        if re.search(pattern, cleaned):
            return None

    query = app_scanner.normalize_app_query(text)
    if not query or len(query) < 2:
        return None

    return query


# Ищет приложение в индексе и запускает его или протокол Windows
def _resolve_and_launch_app(
    query: str,
    index: list[AppEntry],
    original_query: str | None = None,
) -> tuple[Optional[str], bool]:
    original = original_query or query

    for candidate in (original, query):
        protocol_result = app_scanner.try_launch_known_protocol(candidate)
        if protocol_result:
            return protocol_result, False

    for candidate in (original, query):
        uwp_result = app_scanner.try_launch_known_uwp(candidate)
        if uwp_result:
            return uwp_result, False

    entry, ambiguous = app_scanner.find_app(query, index, original_query=original)
    if ambiguous:
        return "Уточните, какое приложение открыть, сэр.", True
    if entry:
        return app_scanner.launch_app(entry), False

    vanguard_result = app_scanner.try_resolve_vanguard(query, index, original_query=original)
    if vanguard_result:
        return vanguard_result, False

    for candidate in (original, query):
        protocol_result = app_scanner.try_launch_known_protocol(candidate)
        if protocol_result:
            return protocol_result, False

    for candidate in (original, query):
        uwp_result = app_scanner.try_launch_known_uwp(candidate)
        if uwp_result:
            return uwp_result, False

    return None, False


# Ищет и запускает приложение из просканированного индекса (Ступень 1)
def try_open_scanned_app(text: str) -> str | None:
    query = _extract_app_query(text)
    if not query:
        return None

    try:
        index = app_scanner.load_or_build_index()
        result, ambiguous = _resolve_and_launch_app(query, index, original_query=text)
        if ambiguous:
            return result
        if result:
            logger.info("Локальный запуск приложения (запрос «%s»)", query)
            return result
    except Exception as e:
        logger.error("Ошибка try_open_scanned_app: %s", e)

    return None


# Пробует открыть приложение без глагола («capcut», «проект cupcut»)
def _try_open_app_by_intent(text: str) -> str | None:
    if not stt_text_utils.looks_like_launch_intent(text):
        return None

    if stt_text_utils.has_open_verb(_normalize_text(text)):
        return None

    if _match_fuzzy_settings(text):
        return None

    cleaned = _normalize_text(text)
    for pattern in _RESERVED_APP_QUERY_PATTERNS:
        if re.search(pattern, cleaned):
            return None

    try:
        index = app_scanner.load_or_build_index()
        result, ambiguous = _resolve_and_launch_app(text, index, original_query=text)
        if ambiguous:
            return "Уточните, какое приложение открыть, сэр."
        if result:
            logger.info("Локальный запуск приложения по intent: «%s»", text)
            return result
    except Exception as e:
        logger.error("Ошибка _try_open_app_by_intent: %s", e)

    return None


# Fallback: открыть приложение по STT, если LLM ошибочно вернул SEARCH
def open_app_from_stt_text(text: str) -> str:
    try:
        index = app_scanner.load_or_build_index()

        for token in app_scanner.extract_app_tokens(text):
            result, ambiguous = _resolve_and_launch_app(token, index, original_query=text)
            if ambiguous:
                return "Уточните, какое приложение открыть, сэр."
            if result:
                logger.info("Fallback OPEN_APP из STT-токена «%s»", token)
                return result

        result, ambiguous = _resolve_and_launch_app(text, index, original_query=text)
        if ambiguous:
            return "Уточните, какое приложение открыть, сэр."
        if result:
            return result

        query = app_scanner.normalize_app_query(text) or text.strip()
        return f'Приложение «{query}» не найдено, сэр.'
    except Exception as e:
        logger.error("Ошибка open_app_from_stt_text: %s", e)
        return "Не удалось открыть приложение, сэр."


# Публичная обёртка для LLM-тега [OPEN_APP:название]
def open_app_by_query(app_query: str, stt_text: str | None = None) -> str:
    try:
        query = app_query.strip()
        if not query:
            return "Не удалось определить приложение, сэр."

        index = app_scanner.load_or_build_index()

        if stt_text:
            stt_entry, _ = app_scanner.find_app(stt_text, index, original_query=stt_text)
            llm_entry, _ = app_scanner.find_app(query, index, original_query=stt_text)
            if stt_entry and llm_entry and stt_entry.normalized_name != llm_entry.normalized_name:
                logger.warning(
                    "LLM OPEN_APP:%s не совпал со STT «%s», предпочитаю STT: %s",
                    query,
                    stt_text,
                    stt_entry.display_name,
                )
                return app_scanner.launch_app(stt_entry)

        result, ambiguous = _resolve_and_launch_app(
            query, index, original_query=stt_text or query
        )
        if ambiguous:
            return "Уточните, какое приложение открыть, сэр."
        if result:
            logger.info("Запуск приложения через LLM (запрос «%s»)", query)
            return result

        return f'Приложение «{query}» не найдено, сэр.'
    except Exception as e:
        logger.error("Ошибка open_app_by_query: %s", e)
        return "Не удалось открыть приложение, сэр."


# Обработчик whitelist-команды open_app (только имя, без пути)
def _cmd_open_app(app_query: str) -> str:
    return open_app_by_query(app_query)


ALLOWED_COMMANDS: dict[str, Callable[..., str]] = {
    "open_app": _cmd_open_app,
    "open_browser": _cmd_open_browser,
    "lock_pc": _cmd_lock_pc,
    "get_weather": _cmd_get_weather,
    "media_play_pause": _cmd_media_play_pause,
    "media_next": _cmd_media_next,
    "volume_mute": _cmd_volume_mute,
    "volume": _cmd_set_volume,
}

for _command_name, _target_key in command_registry.OPEN_COMMAND_TARGETS.items():
    ALLOWED_COMMANDS[_command_name] = _make_target_command(_target_key)


# Безопасная единая точка входа для выполнения системных команд
def execute_system_command(command_name: str, *args, **kwargs) -> CommandResult:
    try:
        if command_name.startswith("volume_"):
            percent_text = command_name.split("_", 1)[1]
            if not percent_text.isdigit():
                logger.warning("Некорректный уровень громкости: %s", command_name)
                return False
            command = ALLOWED_COMMANDS.get("volume")
            return command(int(percent_text)) if command else False

        command = ALLOWED_COMMANDS.get(command_name)
        if command is None:
            logger.warning("Попытка вызвать незарегистрированную команду: %s", command_name)
            return False

        if command_name == "open_app":
            app_query = kwargs.get("app_query") or (args[0] if args else "")
            if not app_query:
                logger.warning("open_app вызван без имени приложения")
                return False
            return command(app_query)

        return command(*args, **kwargs)

    except Exception as e:
        logger.error("Ошибка выполнения команды %s: %s", command_name, e)
        return False


# Совместимый алиас для локальной логики
def execute_action(action_name: str) -> str:
    result = execute_system_command(action_name)
    if result is False:
        return "Не удалось выполнить команду, сэр."
    return result


def _normalize_text(text: str) -> str:
    return stt_text_utils._normalize_text(text)


def _has_word(words: list[str], trigger: str) -> bool:
    return trigger.replace("ё", "е") in words


def _has_phrase(cleaned_text: str, phrase: str) -> bool:
    normalized_phrase = _normalize_text(phrase)
    if not normalized_phrase:
        return False
    return re.search(rf"\b{re.escape(normalized_phrase)}\b", cleaned_text) is not None


def _matches_any_trigger(cleaned_text: str, words: list[str], triggers: tuple[str, ...]) -> bool:
    for trigger in triggers:
        normalized_trigger = _normalize_text(trigger)
        if not normalized_trigger:
            continue

        if " " in normalized_trigger:
            if _has_phrase(cleaned_text, normalized_trigger):
                return True
        elif _has_word(words, normalized_trigger):
            return True

    return False


def _match_fuzzy_settings(text: str) -> str | None:
    cleaned = _normalize_text(text)

    for keywords, command_name in command_registry.get_fuzzy_rules():
        if any(keyword in cleaned for keyword in keywords):
            return command_name

    if stt_text_utils.has_open_verb(cleaned) and re.search(r"калькулятор|calc", cleaned):
        return "open_calculator"
    if stt_text_utils.has_open_verb(cleaned) and "блокнот" in cleaned:
        return "open_notepad"
    if stt_text_utils.has_open_verb(cleaned) and re.search(r"paint|паинт|пейнт", cleaned):
        return "open_paint"
    if stt_text_utils.has_open_verb(cleaned) and "проводник" in cleaned:
        return "open_explorer"
    if re.search(r"командная строка|консоль|терминал", cleaned) or (
        re.search(r"командн", cleaned) and "строк" in cleaned
    ):
        return "open_cmd"
    if re.search(r"диспетчер|task manager|taskmgr", cleaned) or (
        "задач" in cleaned and re.search(r"диспетчер|вечер", cleaned)
    ):
        return "open_task_manager"

    if stt_text_utils.has_open_verb(cleaned) and re.search(r"настрой|стройк", cleaned):
        return "open_settings"

    return None


def _run_local_skill(skill_id: str) -> Optional[str]:
    if skill_id == "clear_memory":
        return clear_user_memory()
    if skill_id == "get_time":
        return get_time()
    return None


# Проверяет текст на локальные ключевые слова (Ступень 1)
def check_local_keywords(text: str) -> Optional[str]:
    text = normalize_stt_text(text)
    cleaned_text = _normalize_text(text)
    words = cleaned_text.split()

    for triggers, action_id in command_registry.get_local_triggers():
        if action_id in {"clear_memory", "get_time"}:
            if _matches_any_trigger(cleaned_text, words, triggers):
                logger.info("Локальное совпадение: навык %s", action_id)
                return _run_local_skill(action_id)
            continue

    weather_cmd = command_registry.get_simple_command("get_weather")
    if weather_cmd and weather_cmd.fuzzy_keywords:
        if any(word.startswith(kw) for word in words for kw in ("погод", "температур")) or _has_phrase(
            cleaned_text, "на улице"
        ):
            logger.info("Локальное совпадение: запрос погоды")
            return execute_action("get_weather")

    fuzzy_command = _match_fuzzy_settings(text)
    if fuzzy_command:
        logger.info("Локальное нечёткое совпадение: %s", fuzzy_command)
        return execute_action(fuzzy_command)

    try:
        from jarvis.commands import scenario_store, scenario_runner, user_apps_store
        from jarvis.core.event_bus import EventBus, EventType

        user_app = user_apps_store.find_by_voice(text)
        if user_app:
            logger.info("Локальное совпадение: пользовательское приложение %s", user_app.display_name)
            result = user_apps_store.launch_user_app(user_app)
            EventBus.instance().publish(
                EventType.APP_LAUNCHED,
                {"name": user_app.display_name, "source": "user_app"},
            )
            return result

        scenario = scenario_store.find_by_voice(text)
        if scenario:
            logger.info("Локальное совпадение: сценарий %s", scenario.name)
            return scenario_runner.run_scenario(scenario.id)
    except Exception as e:
        logger.error("Ошибка user_apps/scenario local match: %s", e)

    if stt_text_utils.has_open_verb(cleaned_text) or stt_text_utils.looks_like_launch_intent(text):
        app_result = try_open_scanned_app(text)
        if app_result is not None:
            return app_result

        app_result = _try_open_app_by_intent(text)
        if app_result is not None:
            return app_result

    for triggers, action_id in command_registry.get_local_triggers():
        if action_id in {"clear_memory", "get_time"}:
            continue

        if action_id == "media_play_pause" and (
            stt_text_utils.has_open_verb(cleaned_text)
            or stt_text_utils.looks_like_launch_intent(text)
        ):
            continue

        if _matches_any_trigger(cleaned_text, words, triggers):
            logger.info("Локальное совпадение: %s", action_id)
            return execute_action(action_id)

    return None


def is_control_action(action_name: str) -> bool:
    return action_name in command_registry.get_control_action_ids() or action_name.startswith("volume_")
