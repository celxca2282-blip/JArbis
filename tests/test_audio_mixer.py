# test_audio_mixer.py
"""Тесты звуковой матрицы (pycaw) — парсинг фраз и маршрутизация команд."""

from unittest.mock import MagicMock, patch

import pytest

from jarvis.commands import audio_mixer


def test_normalize_app_alias_russian() -> None:
    assert audio_mixer.normalize_app_alias("дискорд") == "discord"
    assert audio_mixer.normalize_app_alias("стим") == "steam"
    assert audio_mixer.normalize_app_alias("игра") == "game"


def test_parse_local_app_volume() -> None:
    cmd = audio_mixer.parse_local_audio_command("приглуши дискорд на 40 процентов")
    assert cmd == "app_volume_discord_40"

    cmd = audio_mixer.parse_local_audio_command("громкость chrome 25")
    assert cmd == "app_volume_chrome_25"


def test_parse_local_app_mute() -> None:
    cmd = audio_mixer.parse_local_audio_command("заглуши spotify")
    assert cmd == "app_mute_spotify"


def test_parse_local_device_switch() -> None:
    cmd = audio_mixer.parse_local_audio_command("переключи звук на наушники")
    assert cmd == "audio_device_headphones"

    cmd = audio_mixer.parse_local_audio_command("звук на колонки")
    assert cmd == "audio_device_speakers"


def test_parse_list_sessions() -> None:
    cmd = audio_mixer.parse_local_audio_command("какие приложения играют звук")
    assert cmd == "list_audio_sessions"


@patch("jarvis.commands.audio_mixer._find_sessions_for_alias")
def test_set_app_volume_mock(mock_find: MagicMock) -> None:
    session = MagicMock()
    volume_iface = MagicMock()
    session.SimpleAudioVolume = volume_iface
    session.Process.name.return_value = "Discord.exe"
    mock_find.return_value = [session]

    result = audio_mixer.set_app_volume("discord", 40)
    assert "40" in result
    volume_iface.SetMasterVolume.assert_called_once()
    mock_find.assert_called_once_with("discord")


@patch("jarvis.commands.audio_mixer.set_app_volume")
def test_execute_audio_command_volume(mock_set: MagicMock) -> None:
    mock_set.return_value = "ok"
    assert audio_mixer.execute_audio_command("app_volume_discord_50") == "ok"
    mock_set.assert_called_once_with("discord", 50)


def test_execute_audio_command_invalid() -> None:
    assert audio_mixer.execute_audio_command("app_volume_bad") is False
