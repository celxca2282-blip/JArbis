# config.py
"""
Единая конфигурация проекта Джарвис.
Загружает переменные окружения из .env и хранит общие пути/настройки.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Корневая папка: при сборке exe — папка с JArbis.exe, иначе корень репозитория
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# Загружаем .env один раз для всего проекта
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# Надёжно преобразует строку из .env в bool
def _get_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default

# OpenRouter
API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-chat")

# Распознавание речи (Whisper / faster-whisper)
STT_MODEL_NAME = os.getenv("STT_MODEL_NAME", "medium")
STT_COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "auto").strip().lower()
STT_FORCE_CPU = _get_bool("STT_FORCE_CPU", default=False)
STT_BEAM_SIZE = int(os.getenv("STT_BEAM_SIZE", "3"))
STT_USE_VAD_FILTER = _get_bool("STT_USE_VAD_FILTER", default=True)
STT_INPUT_DEVICE = os.getenv("STT_INPUT_DEVICE", "").strip()
STT_SILENCE_DURATION_SEC = float(os.getenv("STT_SILENCE_DURATION_SEC", "1.0"))
STT_ENERGY_THRESHOLD = float(os.getenv("STT_ENERGY_THRESHOLD", "0.008"))
STT_WAIT_SPEECH_TIMEOUT_SEC = float(os.getenv("STT_WAIT_SPEECH_TIMEOUT_SEC", "4.0"))
STT_MAX_RECORD_DURATION_SEC = float(os.getenv("STT_MAX_RECORD_DURATION_SEC", "12.0"))
STT_POST_ACTIVATION_DELAY_SEC = float(os.getenv("STT_POST_ACTIVATION_DELAY_SEC", "0.35"))
STT_LOW_CONFIDENCE_THRESHOLD = float(os.getenv("STT_LOW_CONFIDENCE_THRESHOLD", "-0.82"))
STT_LOW_CONFIDENCE_MARGIN = float(os.getenv("STT_LOW_CONFIDENCE_MARGIN", "0.06"))
STT_RETRY_ON_LOW_CONFIDENCE = _get_bool("STT_RETRY_ON_LOW_CONFIDENCE", default=False)
STT_PROMPT_APP_LIMIT = int(os.getenv("STT_PROMPT_APP_LIMIT", "40"))

# В exe Whisper на CPU: medium заметно медленнее; small — если модель не задана в .env
if getattr(sys, "frozen", False) and STT_FORCE_CPU and os.getenv("STT_MODEL_NAME") is None:
    STT_MODEL_NAME = "small"

# Синтез речи
TTS_ENGINE = os.getenv("TTS_ENGINE", "piper").strip().lower()  # piper | edge | sapi | silero
PIPER_VOICE = os.getenv("PIPER_VOICE", "ru_RU-ruslan-medium").strip()
TTS_VOICE = os.getenv("TTS_VOICE", "ru-RU-DmitryNeural")
TTS_RATE = os.getenv("TTS_RATE", "+0%")
TTS_PITCH = os.getenv("TTS_PITCH", "+0Hz")
TTS_SAPI_VOICE = os.getenv("TTS_SAPI_VOICE", "").strip()
TTS_START_PAUSE_MS = int(os.getenv("TTS_START_PAUSE_MS", "150"))
SILERO_SPEAKER = os.getenv("SILERO_SPEAKER", "eugene").strip()
SILERO_MODEL = os.getenv("SILERO_MODEL", "v4_ru").strip()
SILERO_SPEED = float(os.getenv("SILERO_SPEED", "1.0"))
EDGE_TTS_LOCALE = os.getenv("EDGE_TTS_LOCALE", "ru").strip().lower()

# Голосовая активация
WAKE_WORD_ENGINE = os.getenv("WAKE_WORD_ENGINE", "vosk").strip().lower()
WAKE_WORD_NAME = os.getenv("WAKE_WORD_NAME", "джарвис").strip()

# Пути к локальным данным
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = DATA_DIR / "temp"
VOICES_DIR = DATA_DIR / "voices"
USER_PROFILE_PATH = DATA_DIR / "user_profile.json"
LOG_FILE_PATH = DATA_DIR / "jarvis.log"

# Индекс установленных приложений
APP_INDEX_PATH = DATA_DIR / "apps_index.json"
APP_INDEX_MAX_AGE_HOURS = float(os.getenv("APP_INDEX_MAX_AGE_HOURS", "24"))
APP_SCAN_ON_STARTUP = _get_bool("APP_SCAN_ON_STARTUP", default=True)
APP_SCAN_UWP = _get_bool("APP_SCAN_UWP", default=True)
APP_FUZZY_MIN_SCORE = float(os.getenv("APP_FUZZY_MIN_SCORE", "0.6"))
APP_FUZZY_MIN_SCORE_MULTIWORD = float(os.getenv("APP_FUZZY_MIN_SCORE_MULTIWORD", "0.72"))

USER_APPS_PATH = DATA_DIR / "user_apps.json"
SCENARIOS_PATH = DATA_DIR / "scenarios.json"
GUI_SETTINGS_PATH = DATA_DIR / "gui_settings.json"

# Режим отладки без голосового ввода
DEBUG_TEXT_MODE = _get_bool("DEBUG_TEXT_MODE", default=False)

# Быстрый режим: только local-команды, лёгкий STT, локальный TTS (Piper HD)
FAST_MODE = _get_bool("FAST_MODE", default=False)

# Снимок «качественных» STT-настроек до применения fast profile
_quality_stt_snapshot: dict = {}

# Ключи GUI-настроек (переопределяют .env в runtime)
_GUI_SETTING_KEYS = (
    "WAKE_WORD_NAME",
    "WAKE_WORD_ENGINE",
    "TTS_ENGINE",
    "PIPER_VOICE",
    "TTS_VOICE",
    "TTS_RATE",
    "TTS_PITCH",
    "TTS_SAPI_VOICE",
    "SILERO_SPEAKER",
    "SILERO_MODEL",
    "SILERO_SPEED",
    "EDGE_TTS_LOCALE",
    "STT_MODEL_NAME",
    "STT_FORCE_CPU",
    "STT_INPUT_DEVICE",
    "STT_POST_ACTIVATION_DELAY_SEC",
    "MODEL_NAME",
    "OPENAI_API_KEY",
)


# Создаёт папки data/ и data/temp/ при старте приложения
def ensure_data_dirs() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        VOICES_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Не удалось создать папку data: {e}")


# Переносит user_profile.json и jarvis.log из корня в data/, если они ещё там
def migrate_legacy_data() -> None:
    try:
        legacy_profile = BASE_DIR / "user_profile.json"
        if legacy_profile.exists() and not USER_PROFILE_PATH.exists():
            legacy_profile.replace(USER_PROFILE_PATH)

        legacy_log = BASE_DIR / "jarvis.log"
        if legacy_log.exists() and not LOG_FILE_PATH.exists():
            legacy_log.replace(LOG_FILE_PATH)
    except Exception as e:
        print(f"Не удалось перенести данные в data/: {e}")


# Загружает GUI-настройки из data/gui_settings.json в runtime
def load_gui_settings() -> None:
    global WAKE_WORD_NAME, WAKE_WORD_ENGINE
    global TTS_ENGINE, PIPER_VOICE, TTS_VOICE, TTS_RATE, TTS_PITCH, TTS_SAPI_VOICE
    global SILERO_SPEAKER, SILERO_MODEL, SILERO_SPEED, EDGE_TTS_LOCALE
    global STT_MODEL_NAME, STT_FORCE_CPU, STT_INPUT_DEVICE, STT_POST_ACTIVATION_DELAY_SEC
    global MODEL_NAME, API_KEY

    try:
        if not GUI_SETTINGS_PATH.is_file():
            return

        import json

        with GUI_SETTINGS_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)

        # Миграция: Silero заменён на Piper HD
        if str(data.get("TTS_ENGINE", "")).strip().lower() == "silero":
            data["TTS_ENGINE"] = "piper"
            data.setdefault("PIPER_VOICE", "ru_RU-ruslan-medium")
            data["TTS_RATE"] = "+0%"
            data["TTS_PITCH"] = "+0Hz"

        mapping = {
            "WAKE_WORD_NAME": ("WAKE_WORD_NAME", str),
            "WAKE_WORD_ENGINE": ("WAKE_WORD_ENGINE", str),
            "TTS_ENGINE": ("TTS_ENGINE", str),
            "PIPER_VOICE": ("PIPER_VOICE", str),
            "TTS_VOICE": ("TTS_VOICE", str),
            "TTS_RATE": ("TTS_RATE", str),
            "TTS_PITCH": ("TTS_PITCH", str),
            "TTS_SAPI_VOICE": ("TTS_SAPI_VOICE", str),
            "SILERO_SPEAKER": ("SILERO_SPEAKER", str),
            "SILERO_MODEL": ("SILERO_MODEL", str),
            "SILERO_SPEED": ("SILERO_SPEED", float),
            "EDGE_TTS_LOCALE": ("EDGE_TTS_LOCALE", str),
            "STT_MODEL_NAME": ("STT_MODEL_NAME", str),
            "STT_FORCE_CPU": ("STT_FORCE_CPU", _get_bool),
            "STT_INPUT_DEVICE": ("STT_INPUT_DEVICE", str),
            "STT_POST_ACTIVATION_DELAY_SEC": ("STT_POST_ACTIVATION_DELAY_SEC", float),
            "MODEL_NAME": ("MODEL_NAME", str),
            "OPENAI_API_KEY": ("API_KEY", str),
        }

        for key, (attr, caster) in mapping.items():
            if key not in data or data[key] in (None, ""):
                continue
            value = data[key]
            if caster is _get_bool:
                value = bool(value)
            elif caster is float:
                value = float(value)
            else:
                value = str(value).strip()
            globals()[attr] = value

        _apply_fast_mode_from_gui(data)
    except Exception as e:
        print(f"Не удалось загрузить gui_settings: {e}")


def _config_module():
    """Возвращает модуль config (не dict globals())."""
    return sys.modules[__name__]


def _capture_quality_stt_snapshot() -> None:
    """Запоминает STT-настройки качества из .env / GUI до fast override."""
    global _quality_stt_snapshot
    from jarvis.core.performance_profiles import _STT_PROFILE_KEYS

    mod = _config_module()
    _quality_stt_snapshot = {key: getattr(mod, key) for key in _STT_PROFILE_KEYS}


def _apply_fast_mode_from_gui(data: dict) -> None:
    """Применяет fast_mode из gui_settings.json."""
    from jarvis.core.performance_profiles import set_fast_mode

    mod = _config_module()

    if not data.get("fast_mode", False):
        _capture_quality_stt_snapshot()

    if "fast_mode" not in data:
        if FAST_MODE:
            set_fast_mode(mod, True, _quality_stt_snapshot or None)
        return

    enabled = bool(data.get("fast_mode", False))
    if enabled and not _quality_stt_snapshot:
        _capture_quality_stt_snapshot()
    set_fast_mode(mod, enabled, _quality_stt_snapshot or None)


def apply_fast_mode(enabled: bool) -> None:
    """Переключает быстрый режим из GUI."""
    from jarvis.core.performance_profiles import set_fast_mode

    if not _quality_stt_snapshot:
        _capture_quality_stt_snapshot()
    set_fast_mode(_config_module(), enabled, _quality_stt_snapshot or None)


# Сохраняет GUI-настройки в JSON и опционально в .env
def save_gui_settings(settings: dict, write_env: bool = False) -> bool:
    try:
        ensure_data_dirs()
        import json

        with GUI_SETTINGS_PATH.open("w", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=2)

        load_gui_settings()

        if write_env and ENV_PATH.is_file():
            lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
            keys_written = set()
            new_lines: list[str] = []
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=", 1)[0].strip()
                    if key in settings:
                        new_lines.append(f"{key}={settings[key]}")
                        keys_written.add(key)
                        continue
                new_lines.append(line)
            for key, value in settings.items():
                if key not in keys_written:
                    new_lines.append(f"{key}={value}")
            ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        return True
    except Exception as e:
        print(f"Не удалось сохранить gui_settings: {e}")
        return False
