# config_env.py
"""Безопасные хелперы чтения настроек из os.environ и gui_settings.json."""

from __future__ import annotations

import os
from typing import Any, Callable


# Читает строку из окружения
def env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip()


# Читает bool из окружения (1/true/yes/on)
def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


# Читает int из окружения с запасным значением
def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


# Читает float из окружения с запасным значением
def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


# Приводит значение из gui_settings к нужному типу
def cast_gui_value(value: Any, caster: Callable[..., Any]) -> Any:
    if caster is env_bool:
        return bool(value)
    if caster is float:
        return float(value)
    if caster is int:
        return int(value)
    return str(value).strip()


# Записывает ключи из JSON в атрибуты модуля config
def apply_gui_mapping(config_module: Any, mapping: dict[str, tuple[str, Callable]], data: dict) -> None:
    for key, (attr, caster) in mapping.items():
        if key not in data or data[key] in (None, ""):
            continue
        setattr(config_module, attr, cast_gui_value(data[key], caster))
