# tests/test_performance_modes.py
"""Тесты трёх режимов производительности."""

import json
from unittest.mock import patch

import config
from jarvis.core.performance_profiles import (
    HARD_STT_OVERRIDES,
    MODE_FAST,
    MODE_HARD,
    MODE_QUALITY,
    FAST_STT_OVERRIDES,
    get_mode_badge,
    normalize_mode,
    parse_mode_from_gui_settings,
    set_performance_mode,
)


def test_normalize_mode() -> None:
    assert normalize_mode("fast") == MODE_FAST
    assert normalize_mode("HARD") == MODE_HARD
    assert normalize_mode(True) == MODE_FAST
    assert normalize_mode(False) == MODE_QUALITY
    assert normalize_mode("unknown") == MODE_QUALITY


def test_parse_gui_settings_migration() -> None:
    assert parse_mode_from_gui_settings({"performance_mode": "hard"}) == MODE_HARD
    assert parse_mode_from_gui_settings({"fast_mode": True}) == MODE_FAST
    assert parse_mode_from_gui_settings({}) == MODE_QUALITY


def test_fast_profile() -> None:
    snapshot = {
        "STT_MODEL_NAME": "medium",
        "STT_SILENCE_DURATION_SEC": 1.0,
        "STT_POST_ACTIVATION_DELAY_SEC": 0.35,
        "STT_BEAM_SIZE": 3,
        "STT_RETRY_ON_LOW_CONFIDENCE": False,
        "STT_WAIT_SPEECH_TIMEOUT_SEC": 4.0,
        "STT_MAX_RECORD_DURATION_SEC": 12.0,
        "STT_LOW_CONFIDENCE_THRESHOLD": -0.82,
    }
    set_performance_mode(config, MODE_FAST, snapshot)
    assert config.PERFORMANCE_MODE == MODE_FAST
    assert config.FAST_MODE is True
    assert config.STT_MODEL_NAME == FAST_STT_OVERRIDES["STT_MODEL_NAME"]


def test_hard_profile_upgrades_small_model() -> None:
    snapshot = {
        "STT_MODEL_NAME": "small",
        "STT_SILENCE_DURATION_SEC": 1.0,
        "STT_POST_ACTIVATION_DELAY_SEC": 0.35,
        "STT_BEAM_SIZE": 3,
        "STT_RETRY_ON_LOW_CONFIDENCE": False,
        "STT_WAIT_SPEECH_TIMEOUT_SEC": 4.0,
        "STT_MAX_RECORD_DURATION_SEC": 12.0,
        "STT_LOW_CONFIDENCE_THRESHOLD": -0.82,
    }
    set_performance_mode(config, MODE_HARD, snapshot)
    assert config.PERFORMANCE_MODE == MODE_HARD
    assert config.FAST_MODE is False
    assert config.STT_MODEL_NAME == "medium"
    assert config.STT_BEAM_SIZE == HARD_STT_OVERRIDES["STT_BEAM_SIZE"]
    assert config.STT_RETRY_ON_LOW_CONFIDENCE is True


def test_quality_restores_snapshot() -> None:
    snapshot = {
        "STT_MODEL_NAME": "medium",
        "STT_SILENCE_DURATION_SEC": 1.6,
        "STT_POST_ACTIVATION_DELAY_SEC": 0.65,
        "STT_BEAM_SIZE": 5,
        "STT_RETRY_ON_LOW_CONFIDENCE": True,
        "STT_WAIT_SPEECH_TIMEOUT_SEC": 6.0,
        "STT_MAX_RECORD_DURATION_SEC": 18.0,
        "STT_LOW_CONFIDENCE_THRESHOLD": -0.82,
    }
    set_performance_mode(config, MODE_FAST, snapshot)
    set_performance_mode(config, MODE_QUALITY, snapshot)
    assert config.STT_MODEL_NAME == "medium"
    assert config.STT_SILENCE_DURATION_SEC == 1.6


def test_load_gui_settings_performance_mode(tmp_path) -> None:
    gui_path = tmp_path / "gui_settings.json"
    gui_path.write_text(
        json.dumps({"performance_mode": "hard", "STT_MODEL_NAME": "medium"}, ensure_ascii=False),
        encoding="utf-8",
    )
    with patch.object(config, "GUI_SETTINGS_PATH", gui_path):
        config.load_gui_settings()
    assert config.PERFORMANCE_MODE == MODE_HARD
    config.apply_performance_mode(MODE_QUALITY)


def test_mode_badges() -> None:
    assert get_mode_badge(MODE_FAST)[0].startswith("⚡")
    assert get_mode_badge(MODE_HARD)[0].startswith("🔥")
