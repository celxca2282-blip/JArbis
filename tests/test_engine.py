# tests/test_engine.py
"""Тесты AssistantEngine."""

from unittest.mock import patch

import config
from jarvis.core.assistant_engine import AssistantEngine, is_unreliable_stt
from jarvis.core.event_bus import EventBus


def test_llm_no_key_fallback_message() -> None:
    engine = AssistantEngine(EventBus.instance())
    with patch.object(config, "API_KEY", ""), patch.object(config, "FAST_MODE", False), patch(
        "jarvis.core.assistant_engine.get_ai_response",
        return_value="ИИ недоступен: не задан OPENAI_API_KEY в .env, сэр.",
    ), patch(
        "jarvis.core.assistant_engine.handle_post_llm",
        return_value=("ИИ недоступен: не задан OPENAI_API_KEY в .env, сэр.", False, False),
    ), patch.object(engine, "_speak"):
        ok = engine._process_command_text("что такое python", None)
    assert ok is True
    assert "OPENAI_API_KEY" in engine.state.last_response


def test_call_llm_safe_wrapper() -> None:
    engine = AssistantEngine(EventBus.instance())
    with patch("jarvis.core.assistant_engine.get_ai_response", side_effect=RuntimeError("boom")):
        text = engine._call_llm("test")
    assert "недоступен" in text.lower()


def test_is_unreliable_stt_low_confidence() -> None:
    with patch("jarvis.core.assistant_engine.stt_module.is_confidence_acceptable", return_value=False):
        assert is_unreliable_stt("открой настройки", -0.95) is True
