# audio_mixer.py
"""
Звуковая матрица: громкость отдельных приложений и переключение устройств Windows (pycaw).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from pycaw.pycaw import AudioUtilities

logger = logging.getLogger(__name__)

# Ключ команды -> имена процессов (.exe)
APP_PROCESS_ALIASES: dict[str, tuple[str, ...]] = {
    "discord": ("discord.exe",),
    "chrome": ("chrome.exe",),
    "edge": ("msedge.exe",),
    "firefox": ("firefox.exe",),
    "steam": ("steam.exe", "steamwebhelper.exe"),
    "spotify": ("spotify.exe",),
    "telegram": ("telegram.exe",),
    "opera": ("opera.exe",),
    "obs": ("obs64.exe", "obs32.exe"),
    "valorant": ("valorant.exe", "valorant-win64-shipping.exe"),
    "cs2": ("cs2.exe",),
    "minecraft": ("minecraft.exe",),
}

# Голосовые синонимы -> ключ APP_PROCESS_ALIASES (или game)
APP_VOICE_ALIASES: dict[str, str] = {
    "discord": "discord",
    "дискорд": "discord",
    "дисcord": "discord",
    "chrome": "chrome",
    "хром": "chrome",
    "edge": "edge",
    "эдж": "edge",
    "firefox": "firefox",
    "steam": "steam",
    "стим": "steam",
    "spotify": "spotify",
    "спотифай": "spotify",
    "telegram": "telegram",
    "телеграм": "telegram",
    "opera": "opera",
    "obs": "obs",
    "valorant": "valorant",
    "валорант": "valorant",
    "cs2": "cs2",
    "minecraft": "minecraft",
    "майнкрафт": "minecraft",
    "игра": "game",
    "игру": "game",
    "игры": "game",
}

# Тип устройства -> подстроки в FriendlyName
DEVICE_KIND_HINTS: dict[str, tuple[str, ...]] = {
    "headphones": (
        "headphone",
        "headset",
        "гарнитур",
        "наушник",
        "airpods",
        "buds",
    ),
    "speakers": (
        "speaker",
        "speakers",
        "realtek",
        "колонк",
        "динамик",
        "display",
        "monitor",
        "nvidia",
        "hdmi",
    ),
}

_NON_GAME_PROCESSES = (
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "discord.exe",
    "spotify.exe",
    "telegram.exe",
    "explorer.exe",
    "searchhost.exe",
    "systemsettings.exe",
    "applicationframehost.exe",
    "audiodg.exe",
    "svchost.exe",
)

_GAME_PROCESS_HINTS = (
    "game",
    "shipping",
    "unity",
    "unreal",
    "cs2",
    "valorant",
    "dota",
    "minecraft",
    "steamwebhelper",
    "r5apex",
    "fortnite",
    "gta",
)


@dataclass(frozen=True)
class AudioSessionInfo:
    """Краткая информация об активной аудиосессии."""

    process_name: str
    display_name: str
    volume_percent: int
    muted: bool


# Возвращает список активных аудиосессий с громкостью
def list_sessions() -> list[AudioSessionInfo]:
    result: list[AudioSessionInfo] = []
    try:
        for session in AudioUtilities.GetAllSessions():
            try:
                process = session.Process
                if process is None:
                    continue
                process_name = (process.name() or "").lower()
                if not process_name:
                    continue
                volume_iface = session.SimpleAudioVolume
                level = float(volume_iface.GetMasterVolume())
                muted = bool(volume_iface.GetMute())
                display = process_name
                try:
                    display = process.name() or process_name
                except Exception:
                    pass
                result.append(
                    AudioSessionInfo(
                        process_name=process_name,
                        display_name=display,
                        volume_percent=int(round(level * 100)),
                        muted=muted,
                    )
                )
            except Exception as exc:
                logger.debug("Пропуск сессии: %s", exc)
    except Exception as exc:
        logger.error("Ошибка list_sessions: %s", exc)
    return result


# Проверяет, подходит ли процесс под алиас приложения
def _process_matches_alias(process_name: str, alias_key: str) -> bool:
    proc = (process_name or "").lower()
    if not proc:
        return False

    if alias_key == "game":
        if proc in _NON_GAME_PROCESSES:
            return False
        if any(hint in proc for hint in _GAME_PROCESS_HINTS):
            return True
        return proc.endswith(".exe") and proc not in ("dllhost.exe", "runtimebroker.exe")

    patterns = APP_PROCESS_ALIASES.get(alias_key, ())
    return any(proc == pattern or proc.endswith(pattern) for pattern in patterns)


# Находит аудиосессии по ключу приложения
def _find_sessions_for_alias(alias_key: str) -> list:
    matched = []
    try:
        for session in AudioUtilities.GetAllSessions():
            try:
                process = session.Process
                if process is None:
                    continue
                name = (process.name() or "").lower()
                if _process_matches_alias(name, alias_key):
                    matched.append(session)
            except Exception:
                continue
    except Exception as exc:
        logger.error("Ошибка поиска сессий для %s: %s", alias_key, exc)
    return matched


# Устанавливает громкость всех сессий приложения (0–100 %)
def set_app_volume(alias_key: str, percent: int) -> str:
    alias = normalize_app_alias(alias_key)
    if alias is None:
        return f"Не знаю приложение «{alias_key}», сэр."

    level = max(0, min(100, int(percent)))
    sessions = _find_sessions_for_alias(alias)
    if not sessions:
        return f"Не вижу активный звук от «{alias}», сэр. Запустите приложение и повторите."

    updated = 0
    names: set[str] = set()
    try:
        for session in sessions:
            volume_iface = session.SimpleAudioVolume
            volume_iface.SetMute(0, None)
            volume_iface.SetMasterVolume(level / 100.0, None)
            updated += 1
            try:
                if session.Process and session.Process.name():
                    names.add(session.Process.name())
            except Exception:
                pass
    except Exception as exc:
        logger.error("Ошибка set_app_volume(%s, %s): %s", alias, level, exc)
        return "Не удалось изменить громкость приложения, сэр."

    label = ", ".join(sorted(names)) or alias
    return f"Громкость {label} — {level} процентов, сэр."


# Включает или выключает звук приложения
def mute_app(alias_key: str, mute: bool = True) -> str:
    alias = normalize_app_alias(alias_key)
    if alias is None:
        return f"Не знаю приложение «{alias_key}», сэр."

    sessions = _find_sessions_for_alias(alias)
    if not sessions:
        return f"Не вижу активный звук от «{alias}», сэр."

    flag = 1 if mute else 0
    names: set[str] = set()
    try:
        for session in sessions:
            session.SimpleAudioVolume.SetMute(flag, None)
            try:
                if session.Process and session.Process.name():
                    names.add(session.Process.name())
            except Exception:
                pass
    except Exception as exc:
        logger.error("Ошибка mute_app(%s): %s", alias, exc)
        return "Не удалось переключить звук приложения, сэр."

    label = ", ".join(sorted(names)) or alias
    if mute:
        return f"Заглушил {label}, сэр."
    return f"Включил звук {label}, сэр."


# Переключает устройство вывода по типу (headphones / speakers)
def switch_output_device(device_kind: str) -> str:
    kind = (device_kind or "").lower().strip()
    hints = DEVICE_KIND_HINTS.get(kind)
    if not hints:
        return "Неизвестный тип устройства, сэр."

    try:
        from jarvis.commands.audio_device_switch import set_default_playback_device
    except ImportError:
        logger.error("Модуль audio_device_switch недоступен")
        return "Переключение устройств недоступно, сэр."

    try:
        device_name = set_default_playback_device(hints)
    except Exception as exc:
        logger.error("Ошибка switch_output_device(%s): %s", kind, exc)
        return "Не удалось переключить устройство вывода, сэр."

    if not device_name:
        label = "наушники" if kind == "headphones" else "колонки"
        return f"Не нашёл {label} среди активных устройств, сэр."
    return f"Переключил звук на {device_name}, сэр."


# Список приложений, которые сейчас играют звук (для голосового ответа)
def describe_active_sessions(limit: int = 5) -> str:
    sessions = list_sessions()
    if not sessions:
        return "Сейчас нет активных аудиопотоков, сэр."

    parts = []
    for info in sessions[:limit]:
        state = "без звука" if info.muted else f"{info.volume_percent} процентов"
        parts.append(f"{info.display_name} — {state}")
    tail = ""
    if len(sessions) > limit:
        tail = f" и ещё {len(sessions) - limit}."
    return "Слышу: " + "; ".join(parts) + tail + ", сэр."


# Нормализует имя приложения для команд app_volume_*
def normalize_app_alias(raw: str) -> str | None:
    key = (raw or "").lower().strip().replace("ё", "е")
    if not key:
        return None

    if key in APP_VOICE_ALIASES:
        return APP_VOICE_ALIASES[key]
    if key in APP_PROCESS_ALIASES or key == "game":
        return key

    latin = re.sub(r"[^a-z0-9_\-]", "", key.replace(" ", ""))
    if latin in APP_PROCESS_ALIASES or latin == "game":
        return latin
    if latin in APP_VOICE_ALIASES:
        return APP_VOICE_ALIASES[latin]

    for voice, canonical in APP_VOICE_ALIASES.items():
        if voice in key or key in voice:
            return canonical
    return None


# Извлекает ключ приложения из текста пользователя
def _detect_app_alias(cleaned_text: str) -> str | None:
    for voice_key, canonical in sorted(APP_VOICE_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(voice_key)}\b", cleaned_text):
            return canonical
    for app_key in APP_PROCESS_ALIASES:
        if re.search(rf"\b{re.escape(app_key)}\b", cleaned_text):
            return app_key
    return None


# Извлекает процент громкости из фразы
def _detect_percent(cleaned_text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*(?:%|процент|percent)?", cleaned_text)
    if not match:
        return None
    value = int(match.group(1))
    if 0 <= value <= 100:
        return value
    return None


# Парсит локальную голосовую команду звуковой матрицы; возвращает id для execute
def parse_local_audio_command(text: str) -> str | None:
    cleaned = (text or "").lower().replace("ё", "е")
    cleaned = re.sub(r"[^\w\s%]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None

    if re.search(r"\b(какие|что|кто)\b.*\b(звук|игра|громк)\b", cleaned) or re.search(
        r"\b(список|перечисли).*(приложен|звук|громк)", cleaned
    ):
        return "list_audio_sessions"

    if re.search(r"переключ.*звук|звук.*на\s+(наушник|колонк|динамик|speaker|headphone)", cleaned):
        if any(h in cleaned for h in DEVICE_KIND_HINTS["headphones"]):
            return "audio_device_headphones"
        if any(h in cleaned for h in DEVICE_KIND_HINTS["speakers"]):
            return "audio_device_speakers"

    app_alias = _detect_app_alias(cleaned)
    if not app_alias:
        return None

    if re.search(r"\b(заглуш\w*|выключ\w*|mute|без звука)\b", cleaned):
        return f"app_mute_{app_alias}"

    if re.search(r"\b(включи звук|со звуком|unmute)\b", cleaned):
        return f"app_unmute_{app_alias}"

    percent = _detect_percent(cleaned)
    if percent is not None and re.search(
        r"\b(громк\w*|приглуш\w*|потише|громче|volume|звук|сделай|постав\w*|установ\w*)\b",
        cleaned,
    ):
        return f"app_volume_{app_alias}_{percent}"

    if re.search(r"\b(приглуш\w*|потише|громче)\b", cleaned):
        return f"app_volume_{app_alias}_30"

    return None


# Выполняет команду звуковой матрицы по id (app_volume_discord_40 и т.д.)
def execute_audio_command(command_name: str) -> str | bool:
    if command_name == "list_audio_sessions":
        return describe_active_sessions()

    if command_name.startswith("audio_device_"):
        kind = command_name.replace("audio_device_", "", 1)
        return switch_output_device(kind)

    if command_name.startswith("app_mute_"):
        alias = command_name[len("app_mute_") :]
        return mute_app(alias, mute=True)

    if command_name.startswith("app_unmute_"):
        alias = command_name[len("app_unmute_") :]
        return mute_app(alias, mute=False)

    if command_name.startswith("app_volume_"):
        tail = command_name[len("app_volume_") :]
        match = re.match(r"^([a-z0-9_]+)_(\d{1,3})$", tail)
        if not match:
            logger.warning("Некорректная команда громкости приложения: %s", command_name)
            return False
        alias_key, percent_text = match.groups()
        return set_app_volume(alias_key, int(percent_text))

    return False
