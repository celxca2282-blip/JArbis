# search_module.py
"""
Модуль веб-поиска через DuckDuckGo.
Используется, когда LLM возвращает тег [SEARCH:запрос].
"""

import logging

from ddgs import DDGS

logger = logging.getLogger(__name__)


# Выполняет короткий веб-поиск и возвращает текстовые результаты
def search_web(query: str, max_results: int = 3) -> str:
    logger.info("Ищу в сети: %s", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return "Ничего не найдено."

        return "\n".join(f"- {result['title']}: {result['body']}" for result in results)

    except Exception as e:
        logger.error("Ошибка поиска: %s", e)
        return "Ошибка доступа к сети."
