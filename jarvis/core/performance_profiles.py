# performance_profiles.py
"""
Профили производительности JArbis: FAST / QUALITY / HARD.
Управляют STT, маршрутизацией LLM и подсказками в GUI.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MODE_FAST = "fast"
MODE_QUALITY = "quality"
MODE_HARD = "hard"

VALID_MODES = (MODE_FAST, MODE_QUALITY, MODE_HARD)
DEFAULT_MODE = MODE_QUALITY

# Текст, если в fast mode команда не распознана локально
FAST_MODE_FALLBACK = (
    "В быстром режиме доступны только заготовленные команды, сэр. "
    "Переключите режим на «Качество» или «Хард» для диалога с ИИ."
)

# Параметры STT в быстром режиме
FAST_STT_OVERRIDES: dict[str, Any] = {
    "STT_MODEL_NAME": "small",
    "STT_SILENCE_DURATION_SEC": 0.9,
    "STT_POST_ACTIVATION_DELAY_SEC": 0.3,
    "STT_BEAM_SIZE": 3,
    "STT_RETRY_ON_LOW_CONFIDENCE": False,
    "STT_WAIT_SPEECH_TIMEOUT_SEC": 4.0,
    "STT_MAX_RECORD_DURATION_SEC": 12.0,
    "STT_LOW_CONFIDENCE_THRESHOLD": -0.82,
}

# Максимальное качество распознавания — медленнее, но точнее
HARD_STT_OVERRIDES: dict[str, Any] = {
    "STT_SILENCE_DURATION_SEC": 1.25,
    "STT_POST_ACTIVATION_DELAY_SEC": 0.5,
    "STT_BEAM_SIZE": 5,
    "STT_RETRY_ON_LOW_CONFIDENCE": True,
    "STT_WAIT_SPEECH_TIMEOUT_SEC": 6.5,
    "STT_MAX_RECORD_DURATION_SEC": 18.0,
    "STT_LOW_CONFIDENCE_THRESHOLD": -0.88,
}

# Ключи STT, которые сохраняем при переключении профилей
_STT_PROFILE_KEYS = tuple(
    dict.fromkeys(
        list(FAST_STT_OVERRIDES.keys())
        + list(HARD_STT_OVERRIDES.keys())
        + ["STT_MODEL_NAME"]
    )
)

_MODEL_RANK = {
    "tiny": 0,
    "base": 1,
    "small": 2,
    "medium": 3,
    "large": 4,
    "large-v2": 4,
    "large-v3": 4,
}

# Метаданные для GUI (hex без импорта theme)
MODE_UI: dict[str, dict[str, str]] = {
    MODE_FAST: {
        "badge": "⚡ FAST",
        "title": "Быстрый",
        "icon": "⚡",
        "tagline": "Мгновенный отклик",
        "hint": "Whisper small · Piper HD офлайн · без LLM",
        "color": "#ffb020",
    },
    MODE_QUALITY: {
        "badge": "◆ QUALITY",
        "title": "Качество",
        "icon": "◆",
        "tagline": "Баланс скорости и точности",
        "hint": "Whisper medium · LLM · ваши настройки STT",
        "color": "#00d4ff",
    },
    MODE_HARD: {
        "badge": "🔥 HARD",
        "title": "Хард",
        "icon": "🔥",
        "tagline": "Максимум точности",
        "hint": "Whisper medium+ · повтор STT · полный LLM",
        "color": "#ff6b35",
    },
}


def normalize_mode(value: Any) -> str:
    """Приводит строку/bool к одному из fast | quality | hard."""
    if isinstance(value, bool):
        return MODE_FAST if value else MODE_QUALITY
    if value is None:
        return DEFAULT_MODE
    text = str(value).strip().lower()
    if text in VALID_MODES:
        return text
    if text in ("1", "fast", "быстрый", "быстрый режим"):
        return MODE_FAST
    if text in ("3", "hard", "хард", "max", "maximum"):
        return MODE_HARD
    return DEFAULT_MODE


def is_fast_mode(config_module=None) -> bool:
    """True, если активен только быстрый режим (без LLM)."""
    mod = config_module or __import__("config")
    return normalize_mode(getattr(mod, "PERFORMANCE_MODE", MODE_QUALITY)) == MODE_FAST


def snapshot_quality_stt(config_module) -> dict[str, Any]:
    """Сохраняет текущие «базовые» значения STT из .env / GUI."""
    return {key: getattr(config_module, key) for key in _STT_PROFILE_KEYS}


def _hard_whisper_model(quality_snapshot: dict[str, Any] | None) -> str:
    """Для HARD — минимум medium, иначе модель из снимка."""
    source = quality_snapshot or {}
    model = str(source.get("STT_MODEL_NAME", "medium")).strip().lower()
    if _MODEL_RANK.get(model, 3) < _MODEL_RANK["medium"]:
        return "medium"
    return model or "medium"


def apply_stt_profile(
    config_module,
    mode: str,
    quality_snapshot: dict[str, Any] | None = None,
) -> None:
    """Применяет STT-профиль fast / quality / hard."""
    mode = normalize_mode(mode)
    if mode == MODE_FAST:
        for key, value in FAST_STT_OVERRIDES.items():
            setattr(config_module, key, value)
        logger.info("Профиль STT: FAST (model=%s)", config_module.STT_MODEL_NAME)
        return

    if mode == MODE_HARD:
        overrides = dict(HARD_STT_OVERRIDES)
        overrides["STT_MODEL_NAME"] = _hard_whisper_model(quality_snapshot)
        for key, value in overrides.items():
            setattr(config_module, key, value)
        logger.info("Профиль STT: HARD (model=%s)", config_module.STT_MODEL_NAME)
        return

    source = quality_snapshot or {}
    for key in _STT_PROFILE_KEYS:
        if key in source:
            setattr(config_module, key, source[key])
    logger.info("Профиль STT: QUALITY (model=%s)", config_module.STT_MODEL_NAME)


def set_performance_mode(
    config_module,
    mode: str,
    quality_snapshot: dict[str, Any] | None = None,
) -> None:
    """Включает один из трёх режимов и синхронизирует FAST_MODE для совместимости."""
    mode = normalize_mode(mode)
    config_module.PERFORMANCE_MODE = mode
    config_module.FAST_MODE = mode == MODE_FAST
    apply_stt_profile(config_module, mode, quality_snapshot)
    logger.info("Режим JArbis: %s", MODE_UI[mode]["badge"])


def set_fast_mode(config_module, enabled: bool, quality_snapshot: dict[str, Any] | None = None) -> None:
    """Обратная совместимость: bool → fast / quality."""
    set_performance_mode(
        config_module,
        MODE_FAST if enabled else MODE_QUALITY,
        quality_snapshot,
    )


def get_mode_badge(mode: str | None = None) -> tuple[str, str]:
    """Возвращает (текст бейджа, цвет) для GUI."""
    key = normalize_mode(mode)
    meta = MODE_UI[key]
    return meta["badge"], meta["color"]


def parse_mode_from_gui_settings(data: dict) -> str:
    """Читает режим из gui_settings с миграцией fast_mode → performance_mode."""
    if "performance_mode" in data:
        return normalize_mode(data.get("performance_mode"))
    if data.get("fast_mode"):
        return MODE_FAST
    return DEFAULT_MODE
