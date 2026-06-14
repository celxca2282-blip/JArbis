# personality_profiles.py
"""
Режимы личности JArbis: normal, shard_soft, shard_hard.
shard_hard — только локальные фразы / Ollama, без OpenRouter.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PERSONALITY_NORMAL = "normal"
PERSONALITY_SHARD_SOFT = "shard_soft"
PERSONALITY_SHARD_HARD = "shard_hard"

VALID_PERSONALITIES = (PERSONALITY_NORMAL, PERSONALITY_SHARD_SOFT, PERSONALITY_SHARD_HARD)
DEFAULT_PERSONALITY = PERSONALITY_NORMAL

MODE_UI: dict[str, dict[str, str]] = {
    PERSONALITY_NORMAL: {
        "badge": "◆ NORMAL",
        "title": "Normal",
        "icon": "◆",
        "tagline": "Стандартный Джарвис",
        "hint": "OpenRouter · команды · поиск · без лишней дерзости",
        "color": "#00d4ff",
    },
    PERSONALITY_SHARD_SOFT: {
        "badge": "😏 SHARD SOFT",
        "title": "Shard Soft",
        "icon": "😏",
        "tagline": "Самоирония",
        "hint": "OpenRouter · шутит над собой, лёгкий сарказм",
        "color": "#9b8cff",
    },
    PERSONALITY_SHARD_HARD: {
        "badge": "💀 SHARD HARD",
        "title": "Shard Hard",
        "icon": "💀",
        "tagline": "18+ · локально",
        "hint": "Без OpenRouter · фразы из data/shard_hard_lines.json или Ollama",
        "color": "#ff4d6d",
    },
}

# Дополнение к системному промпту (normal / shard_soft)
_PERSONALITY_LLM_ADDON: dict[str, str] = {
    PERSONALITY_NORMAL: (
        "Тон: вежливый лаконичный ассистент. Лёгкая ирония допустима, без грубости и мата."
    ),
    PERSONALITY_SHARD_SOFT: (
        "Тон: самоироничный ассистент. Шути в первую очередь над СОБОЙ и своими «багами», "
        "не оскорбляй пользователя. Лёгкий сарказм, 1–2 коротких предложения."
    ),
}


def normalize_personality(value: Any) -> str:
    """Приводит значение к normal | shard_soft | shard_hard."""
    if value is None:
        return DEFAULT_PERSONALITY
    text = str(value).strip().lower().replace("-", "_")
    aliases = {
        "default": PERSONALITY_NORMAL,
        "standard": PERSONALITY_NORMAL,
        "soft": PERSONALITY_SHARD_SOFT,
        "shard": PERSONALITY_SHARD_SOFT,
        "hard": PERSONALITY_SHARD_HARD,
        "toxic": PERSONALITY_SHARD_HARD,
    }
    if text in aliases:
        return aliases[text]
    if text in VALID_PERSONALITIES:
        return text
    return DEFAULT_PERSONALITY


def get_personality_badge(mode: str | None = None) -> tuple[str, str]:
    """Текст бейджа и цвет для GUI."""
    import config

    key = normalize_personality(mode or getattr(config, "PERSONALITY_MODE", DEFAULT_PERSONALITY))
    meta = MODE_UI[key]
    return meta["badge"], meta["color"]


def is_shard_hard(config_module=None) -> bool:
    """True, если активен shard_hard (OpenRouter запрещён)."""
    mod = config_module or __import__("config")
    return normalize_personality(getattr(mod, "PERSONALITY_MODE", DEFAULT_PERSONALITY)) == PERSONALITY_SHARD_HARD


def uses_openrouter(config_module=None) -> bool:
    """OpenRouter только для normal и shard_soft."""
    return not is_shard_hard(config_module)


def get_llm_personality_addon(config_module=None) -> str:
    """Фрагмент system prompt для OpenRouter."""
    mod = config_module or __import__("config")
    mode = normalize_personality(getattr(mod, "PERSONALITY_MODE", DEFAULT_PERSONALITY))
    if mode == PERSONALITY_SHARD_HARD:
        return ""
    return _PERSONALITY_LLM_ADDON.get(mode, _PERSONALITY_LLM_ADDON[PERSONALITY_NORMAL])


def parse_personality_from_gui(data: dict) -> str:
    """Читает personality_mode из gui_settings с проверкой consent для hard."""
    mode = normalize_personality(data.get("personality_mode", DEFAULT_PERSONALITY))
    if mode != PERSONALITY_SHARD_HARD:
        return mode
    if not data.get("shard_hard_consent"):
        logger.warning("shard_hard без consent — откат на normal")
        return PERSONALITY_NORMAL
    return PERSONALITY_SHARD_HARD
