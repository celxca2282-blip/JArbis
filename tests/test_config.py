# tests/test_config.py
"""Тесты конфигурации и gui_settings."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import config
from jarvis.config_env import env_bool, env_float, env_int, env_str


def test_env_helpers() -> None:
    with patch.dict("os.environ", {"JARBIS_TEST_INT": "42", "JARBIS_TEST_BOOL": "yes"}, clear=False):
        assert env_int("JARBIS_TEST_INT", 0) == 42
        assert env_bool("JARBIS_TEST_BOOL", False) is True
        assert env_str("JARBIS_MISSING_XYZ", "def") == "def"
        assert env_float("JARBIS_MISSING_FLOAT", 1.5) == 1.5


def test_load_gui_settings_silero_migration(tmp_path: Path) -> None:
    gui_path = tmp_path / "gui_settings.json"
    gui_path.write_text(
        json.dumps(
            {
                "TTS_ENGINE": "silero",
                "SILERO_SPEAKER": "eugene",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with patch.object(config, "GUI_SETTINGS_PATH", gui_path):
        config.load_gui_settings()
    assert config.TTS_ENGINE == "piper"
    assert config.PIPER_VOICE == "ru_RU-ruslan-medium"


def test_frozen_base_dir_is_path() -> None:
    assert isinstance(config.BASE_DIR, Path)
    if getattr(sys, "frozen", False):
        assert config.BASE_DIR.name != "_internal"


def test_version_defined() -> None:
    assert config.VERSION
    assert config.VERSION.count(".") >= 1
