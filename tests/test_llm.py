# tests/test_llm.py
"""Тесты LLM-модуля (без реальных запросов к OpenRouter)."""

from unittest.mock import MagicMock, patch

import config
from jarvis.ai import llm_module


def test_get_ai_response_no_api_key() -> None:
    with patch.object(config, "API_KEY", ""):
        assert llm_module.get_ai_response("привет") == llm_module.MSG_NO_API_KEY


def test_get_ai_response_success() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="  Ответ, сэр.  "))
    ]
    with patch.object(config, "API_KEY", "test-key"), patch.object(
        llm_module, "_get_client", return_value=mock_client
    ):
        llm_module.CONVERSATION_HISTORY.clear()
        result = llm_module.get_ai_response("как дела")
    assert result == "Ответ, сэр."


def test_get_ai_response_api_error_fallback() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("network down")
    with patch.object(config, "API_KEY", "test-key"), patch.object(
        llm_module, "_get_client", return_value=mock_client
    ):
        llm_module.CONVERSATION_HISTORY.clear()
        result = llm_module.get_ai_response("погода")
    assert "недоступен" in result.lower()


def test_clear_memory_phrase() -> None:
    with patch.object(config, "API_KEY", ""):
        llm_module.CONVERSATION_HISTORY.clear()
        result = llm_module.get_ai_response("очисти память")
    assert "очищена" in result.lower()


def test_has_api_key_helper() -> None:
    with patch.object(config, "API_KEY", "  sk-test  "):
        assert config.has_api_key() is True
    with patch.object(config, "API_KEY", "   "):
        assert config.has_api_key() is False
