# response_processor.py
"""
Модуль разбора ответов LLM.
Извлекает служебные теги из текста, чтобы Джарвис не озвучивал их вслух.
"""

import re

# Теги в квадратных скобках (приоритетный формат)
_EXEC_TAG_BRACKET = re.compile(r"\[EXEC:(\w+)\]")
_SAVE_MEMORY_TAG_BRACKET = re.compile(r"\[SAVE_MEMORY:([^=\]]+)=([^\]]+)\]")
_SEARCH_TAG_BRACKET = re.compile(r"\[SEARCH:([^\]]+)\]")
_OPEN_APP_TAG_BRACKET = re.compile(r"\[OPEN_APP:([^\]]+)\]")

# Голые теги без скобок (fallback, парсятся после удаления [...])
_EXEC_TAG_BARE = re.compile(r"\bEXEC:(\w+)\b")
_SAVE_MEMORY_TAG_BARE = re.compile(r"\bSAVE_MEMORY:([^=\s\[\]]+)=([^\s\[\]]+)\b")
_SEARCH_TAG_BARE = re.compile(r"\bSEARCH:([^\s\[\]]+)\b")
_OPEN_APP_TAG_BARE = re.compile(r"\bOPEN_APP:([^\s\[\],.!?]+)\b")

_ALL_TAG_PATTERNS = (
    _EXEC_TAG_BRACKET,
    _SAVE_MEMORY_TAG_BRACKET,
    _SEARCH_TAG_BRACKET,
    _OPEN_APP_TAG_BRACKET,
    _EXEC_TAG_BARE,
    _SAVE_MEMORY_TAG_BARE,
    _SEARCH_TAG_BARE,
    _OPEN_APP_TAG_BARE,
)


# Извлекает значения тега: сначала из [...], затем голые (без дублирования)
def _extract_tag_values(text: str, bracket_pattern: re.Pattern, bare_pattern: re.Pattern) -> list[str]:
    values = [value.strip() for value in bracket_pattern.findall(text) if value.strip()]
    remainder = bracket_pattern.sub("", text)
    for value in bare_pattern.findall(remainder):
        cleaned = value.strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values


# Извлекает пары ключ=значение для SAVE_MEMORY
def _extract_memory_tags(text: str) -> list[tuple[str, str]]:
    memories: list[tuple[str, str]] = []

    for key, value in _SAVE_MEMORY_TAG_BRACKET.findall(text):
        key, value = key.strip(), value.strip()
        if key and value:
            memories.append((key, value))

    remainder = _SAVE_MEMORY_TAG_BRACKET.sub("", text)
    for key, value in _SAVE_MEMORY_TAG_BARE.findall(remainder):
        key, value = key.strip(), value.strip()
        if key and value and (key, value) not in memories:
            memories.append((key, value))

    return memories


# Удаляет все служебные теги из текста для озвучки
def _strip_service_tags(text: str) -> str:
    cleaned = text
    for pattern in _ALL_TAG_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# Извлекает поисковые запросы из ответа LLM
def extract_search_queries(text: str) -> list[str]:
    return _extract_tag_values(text, _SEARCH_TAG_BRACKET, _SEARCH_TAG_BARE)


# Разбирает ответ LLM на чистый текст, команды, память и запросы приложений
def process_llm_response(
    text: str,
) -> tuple[str, list[str], list[tuple[str, str]], list[str]]:
    commands_to_run = _extract_tag_values(text, _EXEC_TAG_BRACKET, _EXEC_TAG_BARE)
    memories_to_save = _extract_memory_tags(text)
    open_app_queries = _extract_tag_values(text, _OPEN_APP_TAG_BRACKET, _OPEN_APP_TAG_BARE)
    clean_text = _strip_service_tags(text)

    return clean_text, commands_to_run, memories_to_save, open_app_queries
