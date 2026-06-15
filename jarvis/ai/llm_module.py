# llm_module.py
"""
Модуль общения с LLM через OpenRouter API.
Отправляет текст пользователя и возвращает ответ ассистента.
"""

import datetime
import logging
from typing import Optional

from openai import OpenAI

import config
from jarvis.ai.personality_profiles import get_llm_personality_addon, is_shard_hard, uses_openrouter
from jarvis.ai import memory_module
from jarvis.commands.command_registry import build_llm_commands_section

logger = logging.getLogger(__name__)
logger.info("API-ключ в окружении: %s", "да" if config.has_api_key() else "нет")

# Сообщения при недоступности LLM (не падаем, возвращаем текст)
MSG_NO_API_KEY = (
    "ИИ недоступен: не задан OPENAI_API_KEY в .env, сэр. "
    "Локальные команды работают, сложные вопросы — нет."
)
MSG_LLM_UNAVAILABLE = "ИИ сейчас недоступен, сэр. Проверьте интернет или ключ OpenRouter."

SYSTEM_PROMPT_BASE = """
Ты — Джарвис, ИИ-ассистент.
ТВОИ ПРАВИЛА:
1. Если запрос требует поиска актуальной информации, отвечай ТОЛЬКО тегом: [SEARCH:твой запрос].
2. Если нужно выполнить команду, используй тег [EXEC:команда].
3. Если ты не знаешь ответа или данные могут устареть — используй [SEARCH:...], не выдумывай.
4. Если есть тег, не пиши лишнего текста до или после него.
5. После получения результата поиска от системы, кратко резюмируй ответ для пользователя.
6. Отвечай строго в 1-2 коротких предложениях, чистым текстом для живой речи.
7. Не используй смайлики, эмодзи, списки и маркеры форматирования вроде звёздочек (*).
8. Если называешь время, пиши его через двоеточие (например, 15:40) или словами.
9. Если пользователь просит открыть/запустить/включить программу — ТОЛЬКО [OPEN_APP:имя] или [EXEC:...].
   ЗАПРЕЩЕНО [SEARCH:...] для таких запросов. Не отказывай — всегда пробуй OPEN_APP.
   WeMod → [OPEN_APP:wemod], Vanguard → [OPEN_APP:riot client], Yandex Music → [OPEN_APP:yandex music].
   Только латиница в [OPEN_APP:...]. Теги только в квадратных скобках.
"""

_client: Optional[OpenAI] = None
_client_base_url: str = ""
CONVERSATION_HISTORY: list[dict[str, str]] = []

_CLEAR_MEMORY_PHRASES = (
    "очисти память",
    "забудь все",
    "забудь всё",
    "начнем заново",
    "начнём заново",
)


class LlmUnavailableError(Exception):
    """LLM недоступен (нет ключа, сеть, ошибка API)."""


# Возвращает понятный текст ошибки LLM для пользователя
def friendly_llm_error(exc: Exception | None = None) -> str:
    if not config.has_api_key():
        return MSG_NO_API_KEY
    if exc is not None:
        logger.error("Ошибка LLM: %s", exc)
    return MSG_LLM_UNAVAILABLE


# Возвращает base_url: Go proxy (если жив) или OpenRouter напрямую
def _resolve_llm_base_url() -> str:
    try:
        from jarvis.core.sidecar_manager import SidecarManager

        sm = SidecarManager.instance()
        if sm.llm_proxy_available():
            logger.debug("LLM через Go proxy %s", sm.llm_proxy_base_url)
            return sm.llm_proxy_base_url
    except Exception as e:
        logger.debug("Go LLM proxy недоступен: %s", e)
    return config.OPENROUTER_BASE_URL


# Создаёт и возвращает клиент OpenAI для OpenRouter API
def _get_client() -> OpenAI:
    global _client, _client_base_url
    base_url = _resolve_llm_base_url()
    if _client is None or _client_base_url != base_url:
        api_key = config.API_KEY
        if not api_key:
            raise LlmUnavailableError("Не задан OPENAI_API_KEY")
        logger.info("Инициализация LLM клиента (%s)", base_url)
        _client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/my-jarvis",
                "X-Title": "My-Jarvis",
            },
        )
        _client_base_url = base_url
        logger.info("LLM клиент готов")
    return _client


# Сбрасывает кэш клиента (после смены ключа в настройках)
def reset_client() -> None:
    global _client, _client_base_url
    _client = None
    _client_base_url = ""


def _build_system_message() -> str:
    current_time = datetime.datetime.now().strftime("%H:%M")
    memory_text = memory_module.get_memory_string()
    commands_section = build_llm_commands_section()
    personality = get_llm_personality_addon()
    parts = [
        SYSTEM_PROMPT_BASE.strip(),
        personality,
        commands_section,
        "18. Если пользователь говорит 'Меня зовут [Имя]' или 'Я люблю [Хобби]', добавь тег "
        "[SAVE_MEMORY:ключ=значение] без лишнего текста вокруг тега.",
        memory_text,
        f"Текущее время: {current_time}.",
    ]
    return "\n".join(part for part in parts if part)


def _is_clear_memory_request(user_text: str) -> bool:
    normalized = user_text.lower().strip().replace("ё", "е")
    return any(phrase.replace("ё", "е") in normalized for phrase in _CLEAR_MEMORY_PHRASES)


def clear_conversation_history() -> None:
    global CONVERSATION_HISTORY
    CONVERSATION_HISTORY.clear()
    logger.info("История диалога очищена после команды управления")


# Получает текстовый ответ от модели; при ошибке — дружелюбный текст, без raise
def get_ai_response(user_text: str) -> str:
    global CONVERSATION_HISTORY

    try:
        if is_shard_hard():
            logger.warning("get_ai_response вызван в shard_hard — OpenRouter заблокирован")
            from jarvis.ai.shard_hard_responder import respond

            return respond(user_text)

        if _is_clear_memory_request(user_text):
            CONVERSATION_HISTORY.clear()
            logger.info("История диалога очищена")
            return "Память очищена, сэр. Начинаем с чистого листа."

        if not config.has_api_key():
            logger.warning("Запрос LLM без API-ключа")
            return MSG_NO_API_KEY

        if not uses_openrouter():
            return MSG_LLM_UNAVAILABLE

        CONVERSATION_HISTORY.append({"role": "user", "content": user_text})
        CONVERSATION_HISTORY[:] = CONVERSATION_HISTORY[-10:]

        messages = [{"role": "system", "content": _build_system_message()}, *CONVERSATION_HISTORY]
        logger.info("Запрос LLM с контекстом из %s сообщений", len(CONVERSATION_HISTORY))

        client = _get_client()
        response = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=messages,
        )
        response_text = (response.choices[0].message.content or "").strip()
        logger.info("Ответ OpenRouter получен (%s символов)", len(response_text))

        CONVERSATION_HISTORY.append({"role": "assistant", "content": response_text})
        CONVERSATION_HISTORY[:] = CONVERSATION_HISTORY[-10:]

        return response_text
    except LlmUnavailableError:
        return MSG_NO_API_KEY
    except Exception as e:
        logger.error("Ошибка API OpenRouter: %s", e)
        return friendly_llm_error(e)


def get_final_answer(search_results: str, original_query: str) -> str:
    try:
        if is_shard_hard():
            from jarvis.ai.shard_hard_responder import respond

            return respond(original_query)
        if not config.has_api_key():
            return MSG_NO_API_KEY
        client = _get_client()
        response = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{_build_system_message()}\n"
                        f"Ты получил результаты поиска по запросу '{original_query}'. "
                        "Ответь пользователю кратко и точно, основываясь ТОЛЬКО на этих данных."
                    ),
                },
                {"role": "user", "content": search_results},
            ],
        )
        response_text = (response.choices[0].message.content or "").strip()
        logger.info("Финальный ответ после поиска получен (%s символов)", len(response_text))
        return response_text
    except Exception as e:
        logger.error("Ошибка формирования финального ответа после поиска: %s", e)
        return friendly_llm_error(e)
