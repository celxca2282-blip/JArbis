# tests/test_personality_modes.py
"""Тесты личности: normal, shard_soft, shard_hard."""

import json
from unittest.mock import patch

import config
from jarvis.ai.personality_profiles import (
    PERSONALITY_NORMAL,
    PERSONALITY_SHARD_HARD,
    PERSONALITY_SHARD_SOFT,
    is_shard_hard,
    normalize_personality,
    parse_personality_from_gui,
    uses_openrouter,
)
from jarvis.ai.shard_hard_responder import _filter_line, pick_line, pool_is_empty, respond


def test_normalize_personality() -> None:
    assert normalize_personality("normal") == PERSONALITY_NORMAL
    assert normalize_personality("shard_soft") == PERSONALITY_SHARD_SOFT
    assert normalize_personality("hard") == PERSONALITY_SHARD_HARD


def test_shard_hard_requires_consent() -> None:
    assert parse_personality_from_gui({"personality_mode": "shard_hard"}) == PERSONALITY_NORMAL
    assert (
        parse_personality_from_gui({"personality_mode": "shard_hard", "shard_hard_consent": True})
        == PERSONALITY_SHARD_HARD
    )


def test_openrouter_blocked_in_shard_hard() -> None:
    with patch.object(config, "PERSONALITY_MODE", PERSONALITY_SHARD_HARD):
        assert is_shard_hard() is True
        assert uses_openrouter() is False


def test_filter_relative_insults() -> None:
    assert _filter_line("обычная фраза") is True
    assert _filter_line("что-то про маму") is False


def test_pick_line_from_example(tmp_path) -> None:
    example = tmp_path / "shard_hard_lines.json"
    example.write_text(
        json.dumps({"categories": {"unknown": ["Тестовая локальная фраза."]}}, ensure_ascii=False),
        encoding="utf-8",
    )
    with patch.object(config, "SHARD_HARD_LINES_PATH", example):
        from jarvis.ai import shard_hard_responder

        shard_hard_responder._pool_cache = None
        line = pick_line("unknown")
        assert "локальная" in line.lower()


def test_respond_without_openrouter() -> None:
    with patch.object(config, "PERSONALITY_MODE", PERSONALITY_SHARD_HARD), patch(
        "jarvis.ai.ollama_module.is_available", return_value=False
    ), patch("jarvis.ai.shard_hard_responder.pool_is_empty", return_value=True):
        text = respond("расскажи анекдот")
        assert text


def test_get_ai_response_blocks_openrouter_in_shard_hard() -> None:
    from jarvis.ai.llm_module import get_ai_response

    with patch.object(config, "PERSONALITY_MODE", PERSONALITY_SHARD_HARD), patch(
        "jarvis.ai.llm_module.is_shard_hard", return_value=True
    ), patch("jarvis.ai.shard_hard_responder.respond", return_value="локально") as mock_resp:
        assert get_ai_response("привет") == "локально"
        mock_resp.assert_called_once()
