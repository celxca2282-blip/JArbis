# ollama_module.py
"""
Локальный LLM через Ollama (только для shard_hard, без OpenRouter).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import config

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Ollama настроен и модель указана."""
    return bool((config.OLLAMA_MODEL or "").strip() and (config.OLLAMA_BASE_URL or "").strip())


# Отправляет запрос в Ollama /api/chat
def chat(user_text: str, system_prompt: str | None = None) -> str | None:
    if not is_available():
        return None

    base = config.OLLAMA_BASE_URL.rstrip("/")
    model = config.OLLAMA_MODEL.strip()
    system = (system_prompt or config.SHARD_HARD_OLLAMA_PROMPT or "").strip()

    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
    }

    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(
            f"{base}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=config.OLLAMA_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        message = data.get("message") or {}
        text = (message.get("content") or "").strip()
        if text:
            logger.info("Ollama ответ (%s символов)", len(text))
            return text
    except URLError as exc:
        logger.warning("Ollama недоступен: %s", exc)
    except Exception as exc:
        logger.error("Ошибка Ollama: %s", exc)
    return None
