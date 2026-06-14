# confirmations.py
"""
Разбор голосовых и текстовых подтверждений опасных действий.
"""

import re

_CONFIRM_WORDS = {"да", "подтверждаю", "давай", "вали"}
_CANCEL_WORDS = {"нет", "отмена"}


# Разбирает короткий ответ пользователя: True — да, False — нет, None — неясно
def parse_confirmation(text: str) -> bool | None:
    try:
        cleaned = text.lower().replace("ё", "е")
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        words = cleaned.split()

        if not words:
            return None

        if any(word in words for word in _CONFIRM_WORDS):
            return True
        if any(word in words for word in _CANCEL_WORDS):
            return False
        return None
    except Exception:
        return None
