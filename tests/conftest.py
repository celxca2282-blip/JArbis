# conftest.py
"""Общие fixtures для pytest."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def temp_data_dir(tmp_path: Path):
    """Временная папка data/ с подменой путей config."""
    import config

    data = tmp_path / "data"
    data.mkdir()
    (data / "temp").mkdir()
    originals = {
        "DATA_DIR": config.DATA_DIR,
        "TEMP_DIR": config.TEMP_DIR,
        "USER_PROFILE_PATH": config.USER_PROFILE_PATH,
        "GUI_SETTINGS_PATH": config.GUI_SETTINGS_PATH,
        "USER_APPS_PATH": config.USER_APPS_PATH,
        "SCENARIOS_PATH": config.SCENARIOS_PATH,
        "APP_INDEX_PATH": config.APP_INDEX_PATH,
        "LOG_FILE_PATH": config.LOG_FILE_PATH,
    }
    config.DATA_DIR = data
    config.TEMP_DIR = data / "temp"
    config.USER_PROFILE_PATH = data / "user_profile.json"
    config.GUI_SETTINGS_PATH = data / "gui_settings.json"
    config.USER_APPS_PATH = data / "user_apps.json"
    config.SCENARIOS_PATH = data / "scenarios.json"
    config.APP_INDEX_PATH = data / "apps_index.json"
    config.LOG_FILE_PATH = data / "jarvis.log"
    yield data
    for key, value in originals.items():
        setattr(config, key, value)


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Сбрасывает EventBus между тестами."""
    from jarvis.core.event_bus import EventBus

    EventBus.reset()
    yield
    EventBus.reset()
