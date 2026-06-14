# performance_profiles.py
"""
Профили «Быстрый режим» / «Качество» для STT и маршрутизации команд.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Текст, если в fast mode команда не распознана локально
FAST_MODE_FALLBACK = (
    "В быстром режиме доступны только заготовленные команды, сэр. "
    "Выключите быстрый режим в настройках для сложных вопросов."
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
}

# Ключи STT, которые сохраняем при переключении профилей
_STT_PROFILE_KEYS = tuple(FAST_STT_OVERRIDES.keys())


# Сохраняет текущие «качественные» значения STT перед fast override
def snapshot_quality_stt(config_module) -> dict[str, Any]:
    return {key: getattr(config_module, key) for key in _STT_PROFILE_KEYS}


# Применяет быстрый или качественный профиль STT в runtime config
def apply_stt_profile(config_module, fast_mode: bool, quality_snapshot: dict[str, Any] | None = None) -> None:
    if fast_mode:
        for key, value in FAST_STT_OVERRIDES.items():
            setattr(config_module, key, value)
        logger.info("Профиль STT: быстрый (model=%s)", config_module.STT_MODEL_NAME)
        return

    source = quality_snapshot or {}
    for key in _STT_PROFILE_KEYS:
        if key in source:
            setattr(config_module, key, source[key])
    logger.info("Профиль STT: качество (model=%s)", config_module.STT_MODEL_NAME)


# Включает или выключает быстрый режим целиком
def set_fast_mode(config_module, enabled: bool, quality_snapshot: dict[str, Any] | None = None) -> None:
    config_module.FAST_MODE = bool(enabled)
    apply_stt_profile(config_module, config_module.FAST_MODE, quality_snapshot)
    logger.info("Режим: %s", "FAST" if config_module.FAST_MODE else "QUALITY")
