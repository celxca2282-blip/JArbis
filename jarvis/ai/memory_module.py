# memory_module.py
"""
Модуль долговременной памяти Джарвиса.
Хранит факты о пользователе в локальном JSON-файле.
"""

import json
import logging
from typing import Any

import config

logger = logging.getLogger(__name__)

# Файл профиля пользователя задаётся в едином конфиге
USER_PROFILE_PATH = config.USER_PROFILE_PATH


# Возвращает пустую структуру профиля по умолчанию
def _empty_profile() -> dict[str, dict[str, str]]:
    return {"user_info": {}}


# Безопасно читает профиль пользователя из JSON
def load_user_profile() -> dict[str, Any]:
    try:
        if not USER_PROFILE_PATH.exists():
            logger.info("Файл профиля не найден, используется пустая память")
            return {}

        with USER_PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
            profile = json.load(profile_file)

        if not isinstance(profile, dict):
            logger.warning("Файл профиля повреждён: корень JSON не является словарём")
            return {}

        user_info = profile.get("user_info", {})
        if not isinstance(user_info, dict):
            logger.warning("Файл профиля повреждён: user_info не является словарём")
            return {}

        return profile

    except (json.JSONDecodeError, OSError) as e:
        logger.error("Не удалось прочитать профиль пользователя: %s", e)
        return {}
    except Exception as e:
        logger.error("Неожиданная ошибка чтения профиля пользователя: %s", e)
        return {}


# Сохраняет профиль пользователя в JSON-файл
def _write_user_profile(profile: dict[str, Any]) -> None:
    try:
        with USER_PROFILE_PATH.open("w", encoding="utf-8") as profile_file:
            json.dump(profile, profile_file, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("Не удалось записать профиль пользователя: %s", e)
        raise


# Сохраняет или обновляет один факт о пользователе
def save_memory_fact(key: str, value: str) -> bool:
    try:
        clean_key = str(key).strip()
        clean_value = str(value).strip()

        if not clean_key or not clean_value:
            logger.warning("Пустой ключ или значение памяти: %r = %r", key, value)
            return False

        profile = load_user_profile() or _empty_profile()
        user_info = profile.setdefault("user_info", {})

        if not isinstance(user_info, dict):
            profile["user_info"] = {}
            user_info = profile["user_info"]

        user_info[clean_key] = clean_value
        _write_user_profile(profile)
        logger.info("Факт памяти сохранён: %s = %s", clean_key, clean_value)
        return True

    except Exception as e:
        logger.error("Не удалось сохранить факт памяти: %s", e)
        return False


# Формирует текстовый блок памяти для системного промпта LLM
def get_memory_string() -> str:
    try:
        profile = load_user_profile()
        user_info = profile.get("user_info", {}) if isinstance(profile, dict) else {}

        if not user_info:
            return "Известные факты о пользователе: нет сохранённых данных."

        lines = ["Известные факты о пользователе:"]
        for key, value in user_info.items():
            lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    except Exception as e:
        logger.error("Не удалось сформировать строку памяти: %s", e)
        return "Известные факты о пользователе: нет сохранённых данных."
