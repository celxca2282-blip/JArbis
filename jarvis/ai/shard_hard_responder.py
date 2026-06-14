# shard_hard_responder.py
"""
Ответы режима shard_hard: пул локальных фраз + опционально Ollama.
OpenRouter не используется.
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

import config
from jarvis.ai import ollama_module

logger = logging.getLogger(__name__)

# Запрещённые шаблоны (родственники и т.п.) — фильтр пользовательского пула
_BLOCKED_PATTERNS = (
    r"\bмам[аеуы]?\b",
    r"\bмать\b",
    r"\bбат[ьяи]\b",
    r"\bотец\b",
    r"\bродител",
    r"\bбабуш",
    r"\bдедуш",
    r"\bсестр",
    r"\bбрат\b",
    r"\bсемь[ейюя]",
)

_BLOCKED_RE = re.compile("|".join(_BLOCKED_PATTERNS), re.IGNORECASE)

_pool_cache: dict[str, Any] | None = None
_pool_mtime: float = 0.0

_DEFAULT_LINES = {
    "startup": ["Shard Hard активен. Заполните data/shard_hard_lines.json своими фразами."],
    "command_ok": ["Готово. Дальше без меня справитесь, наверное."],
    "command_fail": ["Не вышло. Попробуйте ещё раз."],
    "unknown": ["Не понял. Скажите проще или добавьте фразы в локальный пул."],
    "no_pool": [
        "Локальный пул пуст. Скопируйте data/shard_hard_lines.json.example "
        "в data/shard_hard_lines.json и добавьте свои фразы."
    ],
}


def _lines_path() -> Path:
    return config.SHARD_HARD_LINES_PATH


def _example_path() -> Path:
    return config.SHARD_HARD_LINES_EXAMPLE_PATH


def _filter_line(line: str) -> bool:
    """Отбрасывает строки с запрещёнными темами."""
    return not _BLOCKED_RE.search(line or "")


def _load_pool(force: bool = False) -> dict[str, Any]:
    """Загружает JSON-пул (кэш по mtime)."""
    global _pool_cache, _pool_mtime

    path = _lines_path()
    if not path.is_file():
        _pool_cache = {"categories": dict(_DEFAULT_LINES), "_source": "builtin"}
        _pool_mtime = 0.0
        return _pool_cache

    mtime = path.stat().st_mtime
    if not force and _pool_cache is not None and mtime == _pool_mtime:
        return _pool_cache

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("корень JSON должен быть объектом")
        categories = data.get("categories")
        if not isinstance(categories, dict):
            categories = {}
        # Фильтруем каждую категорию
        cleaned: dict[str, list[str]] = {}
        for key, items in categories.items():
            if not isinstance(items, list):
                continue
            lines = [str(x).strip() for x in items if str(x).strip() and _filter_line(str(x))]
            if lines:
                cleaned[str(key)] = lines
        _pool_cache = {"categories": cleaned, "_source": str(path)}
        _pool_mtime = mtime
        logger.info("Загружен shard_hard пул: %s категорий", len(cleaned))
    except Exception as exc:
        logger.error("Не удалось прочитать %s: %s", path, exc)
        _pool_cache = {"categories": dict(_DEFAULT_LINES), "_source": "error"}
        _pool_mtime = mtime if path.is_file() else 0.0

    return _pool_cache


def pick_line(category: str, *, fallback: str = "unknown") -> str:
    """Случайная фраза из категории пула."""
    pool = _load_pool()
    categories: dict[str, list[str]] = pool.get("categories") or {}

    for key in (category, fallback, "unknown", "no_pool"):
        lines = categories.get(key) or _DEFAULT_LINES.get(key)
        if lines:
            return random.choice(lines)

    return _DEFAULT_LINES["unknown"][0]


def pool_is_empty() -> bool:
    """True, если пользовательский файл отсутствует или все категории пусты."""
    path = _lines_path()
    if not path.is_file():
        return True
    pool = _load_pool()
    return not (pool.get("categories") or {})


def respond(
    user_text: str,
    *,
    local_result: str | None = None,
    local_failed: bool = False,
) -> str:
    """
    Формирует ответ shard_hard.
    local_result — текст после локальной команды; local_failed — команда не сработала.
    """
    if local_failed:
        return pick_line("command_fail")

    if local_result is not None:
        # Если в пуле есть command_ok — используем его; иначе функциональный ответ
        pool = _load_pool()
        ok_lines = (pool.get("categories") or {}).get("command_ok")
        if ok_lines:
            return pick_line("command_ok")
        return local_result

    # Свободная фраза: сначала Ollama (локально), иначе пул
    if ollama_module.is_available():
        ollama_text = ollama_module.chat(user_text)
        if ollama_text and _filter_line(ollama_text):
            return ollama_text

    if pool_is_empty():
        return pick_line("no_pool")

    return pick_line("unknown")


def startup_line() -> str:
    """Приветствие при включении shard_hard."""
    return pick_line("startup", fallback="unknown")
