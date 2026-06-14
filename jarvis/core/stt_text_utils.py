# stt_text_utils.py
"""
Утилиты пост-обработки текста распознавания речи (STT).
"""

import logging
import re
import time

logger = logging.getLogger(__name__)

# Слова из initial_prompt Whisper — для детекции галлюцинаций
STT_HALLUCINATION_KEYWORDS = (
    "настройки",
    "калькулятор",
    "bluetooth",
    "wifi",
    "проводник",
    "блокнот",
    "paint",
    "уведомления",
    "неполадок",
    "диспетчер",
)

# Фонетические и типичные ошибки STT для имён приложений
PHONETIC_STT_FIXES: tuple[tuple[str, str], ...] = (
    (r"троек\s+капкат", "capcut"),
    (r"проект\s+cupcut", "capcut"),
    (r"проект\s+capcut", "capcut"),
    (r"\bкапкат\b", "capcut"),
    (r"\bcupcut\b", "capcut"),
    (r"\bварp\b", "warp"),
    (r"\bварп\b", "warp"),
    (r"\bwnd\b", "warp"),
    (r"\bw\.\s*under\b", "warp"),
    (r"\bw\s+under\b", "warp"),
    (r"wie[\s-]?модор", "wemod"),
    (r"wie\s+модор", "wemod"),
    (r"v[\s-]?моды", "wemod"),
    (r"v\s+моды", "wemod"),
    (r"\bv[\s-]?mod\b", "wemod"),
    (r"\bwiemod\b", "wemod"),
    (r"\bwunder\b", "wemod"),
    (r"\bvmods\b", "wemod"),
    (r"\bванн\b", "vanguard"),
    (r"\bванд\b", "vanguard"),
    (r"\bванны\b", "vanguard"),
    (r"\bван[\s-]?др\b", "vanguard"),
    (r"\bванда\b", "vanguard"),
    (r"троевандр", "vanguard"),
    (r"яндекс\.?\s*музык\w*", "yandex music"),
    (r"яндекс\s+музык\w*", "yandex music"),
    (r"\byandex\s+music\b", "yandex music"),
    (r"электроник\s+arts", "ea"),
    (r"electronic\s+arts", "ea"),
    (r"грой\s+ea\b", "ea"),
    (r"\bгвс\b", "hiddify"),
    (r"\bгевес\b", "hiddify"),
    (r"tag\s+ws", "hiddify"),
    (r"\bproxon\b", "hiddify"),
    (r"\bвалорант\b", "valorant"),
)

# Кэш индекса приложений для looks_like_launch_intent (секунды)
_INDEX_CACHE_TTL_SEC = 60.0
_index_cache: tuple[list, float] | None = None


# Нормализует текст для сравнения триггеров
def _normalize_text(text: str) -> str:
    normalized = text.lower().replace("ё", "е")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


# Проверяет, есть ли в тексте глагол открытия/запуска
def has_open_verb(text: str) -> bool:
    cleaned = _normalize_text(text)
    if re.search(
        r"\b(откр|откро|откры|запуст|запуск|крой|крою|кроет|"
        r"пусти|грой|гроем|гроет|вруби|строи|строй)\w*",
        cleaned,
    ):
        return True

    # «включи» считаем только если после глагола есть объект
    if re.search(r"\b(включи|включай|включить)\w*\s+(\S+)", cleaned):
        return True

    return False


# Возвращает кэшированный индекс приложений для лёгких проверок intent
def _get_cached_app_index() -> list:
    global _index_cache

    try:
        now = time.time()
        if _index_cache is not None and (now - _index_cache[1]) < _INDEX_CACHE_TTL_SEC:
            return _index_cache[0]

        from jarvis.commands import app_scanner

        index = app_scanner.load_or_build_index()
        _index_cache = (index, now)
        return index
    except Exception as e:
        logger.warning("Не удалось загрузить индекс для intent: %s", e)
        return []


# Сбрасывает кэш индекса (для тестов)
def clear_app_index_cache() -> None:
    global _index_cache
    _index_cache = None


# Проверяет, похож ли запрос на намерение запустить программу
def looks_like_launch_intent(text: str) -> bool:
    try:
        cleaned = _normalize_text(text)
        if not cleaned:
            return False

        if has_open_verb(cleaned):
            return True

        from jarvis.commands import app_scanner

        if app_scanner.matches_known_app_alias(cleaned):
            return True

        if matches_phonetic_app_hint(cleaned):
            return True

        index = _get_cached_app_index()
        if not index:
            return False

        entry, ambiguous = app_scanner.find_app(cleaned, index, min_score=0.85, original_query=cleaned)
        return entry is not None and not ambiguous
    except Exception as e:
        logger.error("Ошибка looks_like_launch_intent: %s", e)
        return False


# Проверяет, содержит ли текст подсказку об известном приложении после phonetic-fix
def matches_phonetic_app_hint(text: str) -> bool:
    normalized = normalize_stt_text(text)
    from jarvis.commands import app_scanner

    return app_scanner.matches_known_app_alias(normalized)


# Исправляет типичные ошибки Whisper для русских команд
def normalize_stt_text(text: str) -> str:
    if not text:
        return text

    try:
        normalized = text.lower().replace("ё", "е")

        stt_fixes = (
            (r"как\s*-\s*то\s+видело", "как дела"),
            (r"както\s+видело", "как дела"),
            (r"на\s+стройке", "настройки"),
            (r"на\s+стройках", "настройки"),
            (r"в\s+стройке", "настройки"),
            (r"\bстройках\b", "настройки"),
            (r"в\s+i\s*fi", "wifi"),
            (r"\bвifi\b", "wifi"),
            (r"wi\s*fi", "wifi"),
            (r"вай\s*fi", "wifi"),
            (r"вай\s*фай", "wifi"),
            (r"\bблютуз\b", "bluetooth"),
            (r"\bблюту\b", "bluetooth"),
            (r"\bпейнт\b", "paint"),
            (r"\bпаинт\b", "paint"),
            (r"\bдеспетчер\b", "диспетчер"),
            (r"вечер\s+задач", "диспетчер задач"),
            (r"\bcupcut\b", "capcut"),
            (r"\bcap cut\b", "capcut"),
        )
        for pattern, replacement in stt_fixes:
            normalized = re.sub(pattern, replacement, normalized)

        for pattern, replacement in PHONETIC_STT_FIXES:
            normalized = re.sub(pattern, replacement, normalized)

        if re.search(r"командн", normalized) and re.search(r"строк", normalized):
            normalized = re.sub(r"командн\w*.*?\s*строк\w*", "командная строка", normalized)

        if re.search(r"уведомлен", normalized):
            normalized = re.sub(r"уведомлен\w*", "уведомления", normalized)

        if re.search(r"устранен", normalized) and re.search(r"неполад", normalized):
            normalized = re.sub(r"устранен\w*.*неполад\w*", "устранение неполадок", normalized)

        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
    except Exception as e:
        logger.error("Ошибка нормализации STT-текста: %s", e)
        return text.lower().replace("ё", "е").strip()


# Проверяет, похож ли текст на галлюцинацию Whisper из initial_prompt
def is_prompt_hallucination(text: str) -> bool:
    try:
        if not text:
            return False

        cleaned = _normalize_text(text)
        if has_open_verb(cleaned):
            return False

        matched_keywords = sum(
            1 for keyword in STT_HALLUCINATION_KEYWORDS if keyword in cleaned
        )
        return matched_keywords >= 2
    except Exception as e:
        logger.error("Ошибка проверки галлюцинации STT: %s", e)
        return False


# Проверяет, похож ли текст на бессмысленный результат STT
def is_garbage_stt(text: str, fuzzy_command: str | None = None) -> bool:
    try:
        if not text:
            return True

        cleaned = _normalize_text(text)
        if not cleaned:
            return True

        if has_open_verb(cleaned) or fuzzy_command or looks_like_launch_intent(cleaned):
            return False

        command_markers = (
            "откр", "запуст", "крой", "настрой", "стройк", "погод",
            "пауз", "плей", "блокир", "стоп", "выход", "браузер", "громк",
            "включ", "выключ", "привет", "как дела", "время", "памят", "запомни",
            "меня зовут", "я люблю", "джарвис", "jarvis", "который час", "сколько времени",
            "wemod", "warp", "capcut", "spotify", "steam", "yandex",
        )
        if any(marker in cleaned for marker in command_markers):
            return False

        words = cleaned.split()
        if len(words) < 2:
            return False

        russian_like = 0
        for word in words:
            if re.search(r"[а-я]", word) and re.search(r"[аеёиоуыэюя]", word) and len(word) >= 4:
                russian_like += 1

        return russian_like == 0
    except Exception as e:
        logger.error("Ошибка проверки мусорного STT: %s", e)
        return False
