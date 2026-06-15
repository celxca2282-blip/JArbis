# tests/test_jarvis.py
"""
Простые тесты ключевых модулей Джарвиса.
Запуск: python -m pytest tests/  или  python tests/test_jarvis.py
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Корень проекта в sys.path для прямого запуска файла
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import jarvis.ai.search_module as search_module
import jarvis.commands.app_scanner as app_scanner
import jarvis.commands.commands_module as commands_module
import jarvis.ai.memory_module as memory_module
import jarvis.ai.response_processor as response_processor
import jarvis.core.stt_text_utils as stt_text_utils
import jarvis.voice.stt_module as stt_module
import jarvis.voice.wake_word_module as wake_word_module
from jarvis.commands.app_scanner import AppEntry
from jarvis.commands.command_registry import build_llm_commands_section


def test_response_processor() -> None:
    clean_text, commands, memories, open_apps = response_processor.process_llm_response(
        "[EXEC:say_hello] [SAVE_MEMORY:test=123] Привет мир!"
    )

    assert clean_text == "Привет мир!"
    assert commands == ["say_hello"]
    assert dict(memories) == {"test": "123"}
    assert open_apps == []


def test_memory_module() -> None:
    original_path = memory_module.USER_PROFILE_PATH

    with tempfile.TemporaryDirectory() as temp_dir:
        memory_module.USER_PROFILE_PATH = Path(temp_dir) / "user_profile.json"

        assert memory_module.save_memory_fact("test_key", "test_value") is True
        profile = memory_module.load_user_profile()
        assert profile["user_info"]["test_key"] == "test_value"

    memory_module.USER_PROFILE_PATH = original_path


def test_commands_whitelist() -> None:
    assert "lock_pc" in commands_module.ALLOWED_COMMANDS
    assert "open_settings_wifi" in commands_module.ALLOWED_COMMANDS
    assert "open_settings_notifications" in commands_module.ALLOWED_COMMANDS
    assert "open_settings_troubleshoot" in commands_module.ALLOWED_COMMANDS
    assert "open_app" in commands_module.ALLOWED_COMMANDS
    assert commands_module.execute_system_command("hacker_attack") is False


def test_config_stt_defaults() -> None:
    assert config.STT_MODEL_NAME == "medium"
    assert config.STT_USE_VAD_FILTER is True
    assert config.STT_LOW_CONFIDENCE_THRESHOLD == -0.82
    assert config.STT_LOW_CONFIDENCE_MARGIN == 0.06
    assert config.STT_BEAM_SIZE == 3
    assert config.STT_SILENCE_DURATION_SEC == 1.0
    assert config.STT_RETRY_ON_LOW_CONFIDENCE is False


def test_stt_confidence_margin() -> None:
    assert stt_module.is_confidence_acceptable(-0.83) is True
    assert stt_module.is_confidence_acceptable(-0.848) is True
    assert stt_module.is_confidence_acceptable(-0.89) is False
    assert stt_module.is_confidence_acceptable(None) is True


def test_llm_commands_section() -> None:
    section = build_llm_commands_section()
    assert "open_settings" in section
    assert "open_calculator" in section
    assert "OPEN_APP" in section


def test_prompt_hallucination() -> None:
    assert stt_text_utils.is_prompt_hallucination("настройки, калькулятор") is True
    assert stt_text_utils.is_prompt_hallucination("открой настройки") is False


def test_wake_word_detection() -> None:
    assert wake_word_module.contains_wake_word("джарвис", "джарвис") is True
    assert wake_word_module.contains_wake_word("jarvis", "джарвис") is True
    assert wake_word_module.contains_wake_word("джарвис открой настройки", "джарвис") is True
    assert wake_word_module.contains_wake_word("поздно сказал джарвис", "джарвис") is False
    assert wake_word_module.get_wake_word_display_name() == "Джарвис"


def test_normalize_stt_text() -> None:
    assert "настройки" in stt_text_utils.normalize_stt_text("открой на стройке")
    assert "wifi" in stt_text_utils.normalize_stt_text("открой на стройке вай fi")
    assert "устранение неполадок" in stt_text_utils.normalize_stt_text(
        "крой устранения неполадок"
    )
    assert "как дела" in stt_text_utils.normalize_stt_text("как-то видело")


def test_fuzzy_settings_triggers() -> None:
    original_execute_action = commands_module.execute_action

    try:
        commands_module.execute_action = lambda action_name: action_name
        assert commands_module.check_local_keywords("открой на стройке вай fi") == "open_settings_wifi"
        assert commands_module.check_local_keywords("открою уведомления") == "open_settings_notifications"
        assert commands_module.check_local_keywords("крой устранения неполадок") == "open_settings_troubleshoot"
    finally:
        commands_module.execute_action = original_execute_action


def test_open_target_command() -> None:
    with patch.object(commands_module.os, "startfile") as mock_startfile:
        wifi_result = commands_module.execute_system_command("open_settings_wifi")
        notifications_result = commands_module.execute_system_command("open_settings_notifications")
        troubleshoot_result = commands_module.execute_system_command("open_settings_troubleshoot")

    assert wifi_result == "Открываю настройки Wi‑Fi, сэр."
    assert notifications_result == "Открываю настройки уведомлений, сэр."
    assert troubleshoot_result == "Открываю средство устранения неполадок, сэр."
    assert mock_startfile.call_count == 3


def test_local_triggers() -> None:
    original_execute_action = commands_module.execute_action

    try:
        commands_module.execute_action = lambda action_name: action_name

        assert commands_module.check_local_keywords("включи плейлист") is None
        assert commands_module.check_local_keywords("джарвис плей") == "media_play_pause"
        assert commands_module.check_local_keywords("открой настройки") == "open_settings"
        assert commands_module.check_local_keywords("тройка калькулятор") is None
        assert commands_module.check_local_keywords("открой калькулятор") == "open_calculator"
        time_response = commands_module.check_local_keywords("который час")
        assert time_response is not None and "часов" in time_response

    finally:
        commands_module.execute_action = original_execute_action


def test_app_scanner_normalize_and_find() -> None:
    fake_index = [
        AppEntry("Discord", "discord", r"C:\fake\Discord.lnk", "start_menu"),
        AppEntry("Steam", "steam", r"C:\fake\Steam.lnk", "start_menu"),
    ]

    entry_discord, ambiguous = app_scanner.find_app("discord", fake_index)
    assert ambiguous is False
    assert entry_discord is not None
    assert entry_discord.display_name == "Discord"

    entry_ru, ambiguous_ru = app_scanner.find_app("дискорд", fake_index)
    assert ambiguous_ru is False
    assert entry_ru is not None
    assert entry_ru.display_name == "Discord"


def test_try_open_scanned_app_mock() -> None:
    fake_entry = AppEntry("Telegram", "telegram", r"C:\fake\Telegram.lnk", "start_menu")

    with patch.object(app_scanner, "load_or_build_index", return_value=[fake_entry]):
        with patch.object(app_scanner, "launch_app", return_value="Открываю Telegram, сэр.") as mock_launch:
            result = commands_module.try_open_scanned_app("открой telegram")

    assert result == "Открываю Telegram, сэр."
    mock_launch.assert_called_once()


def test_open_app_tag_parser() -> None:
    clean_text, commands, memories, open_apps = response_processor.process_llm_response(
        "[OPEN_APP:steam] Открываю Steam, сэр."
    )

    assert clean_text == "Открываю Steam, сэр."
    assert commands == []
    assert memories == []
    assert open_apps == ["steam"]


def test_bare_open_app_tag_parser() -> None:
    clean_text, commands, memories, open_apps = response_processor.process_llm_response(
        "OPEN_APP:spotify"
    )

    assert clean_text == ""
    assert commands == []
    assert memories == []
    assert open_apps == ["spotify"]


def test_bare_exec_tag_parser() -> None:
    clean_text, commands, memories, open_apps = response_processor.process_llm_response(
        "EXEC:open_browser"
    )

    assert clean_text == ""
    assert commands == ["open_browser"]
    assert memories == []
    assert open_apps == []


def test_microsoft_store_not_edge() -> None:
    fake_index = [
        AppEntry("Microsoft Edge", "microsoft edge", r"C:\fake\Edge.lnk", "start_menu"),
        AppEntry("Microsoft Store", "microsoft store", r"C:\fake\Store.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("microsoft store", fake_index)
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "Microsoft Store"


def test_garbage_stt_discord_query() -> None:
    fake_index = [
        AppEntry("Discord", "discord", r"C:\fake\Discord.lnk", "start_menu"),
        AppEntry("YouTube", "youtube", r"C:\fake\YouTube.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("запрет discord youtube", fake_index)
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "Discord"


def test_abs_studio_alias() -> None:
    fake_index = [
        AppEntry("OBS Studio", "obs studio", r"C:\fake\OBS.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("abs studio", fake_index)
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "OBS Studio"


def test_cursor_alias() -> None:
    fake_index = [
        AppEntry("Cursor", "cursor", r"C:\fake\Cursor.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("курсор", fake_index)
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "Cursor"


def test_uwp_launch_path() -> None:
    entry = AppEntry(
        "Spotify",
        "spotify",
        r"shell:AppsFolder\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
        "uwp",
    )

    with patch.object(app_scanner.os, "startfile") as mock_startfile:
        result = app_scanner.launch_app(entry)

    assert "Spotify" in result
    mock_startfile.assert_called_once_with(entry.launch_path)


def test_open_player_not_media_pause() -> None:
    fake_entry = AppEntry("MuMu Player", "mumu player", r"C:\fake\MuMu.lnk", "start_menu")

    with patch.object(app_scanner, "load_or_build_index", return_value=[fake_entry]):
        with patch.object(app_scanner, "launch_app", return_value="Открываю MuMu Player, сэр.") as mock_launch:
            result = commands_module.check_local_keywords("откроем ему плеер")

    assert result == "Открываю MuMu Player, сэр."
    mock_launch.assert_called_once()


def test_vanguard_alias_local() -> None:
    fake_entry = AppEntry("VALORANT", "valorant", r"C:\fake\Valorant.lnk", "start_menu")
    vanguard_entry = AppEntry("Riot Client", "riot client", r"C:\fake\Riot.lnk", "start_menu")

    with patch.object(app_scanner, "load_or_build_index", return_value=[fake_entry, vanguard_entry]):
        with patch.object(app_scanner, "launch_app", return_value="Открываю Riot Client, сэр.") as mock_launch:
            result = commands_module.try_open_scanned_app("крой вандр")

    assert result == "Открываю Riot Client, сэр."
    mock_launch.assert_called_once()


def test_has_open_verb_pusti() -> None:
    assert stt_text_utils.has_open_verb("пусти spotify") is True
    assert stt_text_utils.has_open_verb("включи spotify") is True
    assert stt_text_utils.has_open_verb("включи") is False


def test_launch_intent_blocks_search() -> None:
    from jarvis.core.assistant_engine import handle_post_llm

    with patch.object(search_module, "search_web") as mock_search:
        with patch.object(commands_module, "open_app_from_stt_text", return_value="Открываю CapCut, сэр."):
            response, control_executed, _ = handle_post_llm(
                "проект cupcut",
                "[SEARCH:capcut]",
            )

    mock_search.assert_not_called()
    assert "CapCut" in response
    assert control_executed is True


def test_yandex_music_not_browser() -> None:
    fake_index = [
        AppEntry("Yandex Browser", "yandex browser", r"C:\fake\Browser.lnk", "start_menu"),
        AppEntry("Yandex Music", "yandex music", r"C:\fake\Music.lnk", "uwp"),
    ]

    entry, ambiguous = app_scanner.find_app("яндекс музыку", fake_index)
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "Yandex Music"


def test_warp_not_wand() -> None:
    fake_index = [
        AppEntry("Wand", "wand", r"C:\fake\Wand.lnk", "start_menu"),
        AppEntry("Cloudflare One Client", "cloudflare one client", r"C:\fake\CF.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("wnd", fake_index)
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "Cloudflare One Client"


def test_warp_cyrillic_not_wand() -> None:
    fake_index = [
        AppEntry("Wand", "wand", r"C:\fake\Wand.lnk", "start_menu"),
        AppEntry("WeMod", "wemod", r"C:\fake\WeMod.lnk", "start_menu"),
        AppEntry("Cloudflare One Client", "cloudflare one client", r"C:\fake\CF.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("варp", fake_index)
    if entry is not None:
        assert "wand" not in entry.normalized_name
        assert "wemod" not in entry.normalized_name
    assert ambiguous is False


def test_capcut_without_verb() -> None:
    fake_entry = AppEntry("CapCut", "capcut", r"C:\fake\CapCut.lnk", "start_menu")

    with patch.object(app_scanner, "load_or_build_index", return_value=[fake_entry]):
        with patch.object(app_scanner, "launch_app", return_value="Открываю CapCut, сэр.") as mock_launch:
            result = commands_module.check_local_keywords("проект cupcut")

    assert result == "Открываю CapCut, сэр."
    mock_launch.assert_called_once()


def test_phonetic_vanguard() -> None:
    assert "vanguard" in stt_text_utils.normalize_stt_text("ванны")


def test_phonetic_wemod() -> None:
    assert "wemod" in stt_text_utils.normalize_stt_text("v-моды")


def test_yandex_browser_real_name() -> None:
    fake_index = [
        AppEntry("Яндекс Браузер с Алисой AI", "яндекс браузер с алисой ai", r"C:\fake\Browser.lnk", "start_menu"),
        AppEntry("Yandex Music", "yandex music", r"C:\fake\Music.lnk", "uwp"),
    ]

    entry, ambiguous = app_scanner.find_app("яндекс музыку", fake_index, original_query="яндекс музыку")
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "Yandex Music"


def test_yandex_music_not_wand() -> None:
    fake_index = [
        AppEntry("Wand", "wand", r"C:\fake\Wand.lnk", "start_menu"),
        AppEntry("Yandex Browser", "yandex browser", r"C:\fake\Browser.lnk", "start_menu"),
        AppEntry("Yandex Music", "yandex music", r"C:\fake\Music.lnk", "uwp"),
    ]

    entry, ambiguous = app_scanner.find_app("yandex music", fake_index, original_query="yandex music")
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "Yandex Music"


def test_microsoft_store_protocol_before_edge() -> None:
    fake_index = [
        AppEntry("Microsoft Edge", "microsoft edge", r"C:\fake\Edge.lnk", "start_menu"),
    ]

    with patch.object(app_scanner.os, "startfile") as mock_startfile:
        result, ambiguous = commands_module._resolve_and_launch_app(
            "microsoft store",
            fake_index,
            original_query="microsoft store",
        )

    assert ambiguous is False
    assert result is not None
    assert "Microsoft Store" in result
    mock_startfile.assert_called_once_with("ms-windows-store:")


def test_low_confidence_returns_none() -> None:
    with patch.object(stt_module, "_listen_once", return_value=("test", -0.95)):
        text, logprob = stt_module.listen_with_confidence()
    assert text is None
    assert logprob == -0.95


def test_launch_intent_stroi_wunder() -> None:
    from jarvis.core.assistant_engine import handle_post_llm

    normalized = stt_text_utils.normalize_stt_text("строи wunder")
    assert "wemod" in normalized

    with patch.object(search_module, "search_web") as mock_search:
        with patch.object(commands_module, "open_app_from_stt_text", return_value="Открываю WeMod, сэр."):
            response, control_executed, _ = handle_post_llm(
                normalized,
                "[SEARCH:wemod]",
            )

    mock_search.assert_not_called()
    assert "WeMod" in response
    assert control_executed is True


def test_tts_config_from_env() -> None:
    import jarvis.voice.tts_module as tts_module

    assert tts_module.VOICE == config.TTS_VOICE
    assert tts_module.SPEECH_RATE == config.TTS_RATE
    assert tts_module.START_PAUSE_MS == config.TTS_START_PAUSE_MS


def test_index_version_four() -> None:
    assert app_scanner.INDEX_VERSION == 4


def test_phonetic_yandex_dot_music() -> None:
    assert "yandex music" in stt_text_utils.normalize_stt_text("яндекс.музыку")


def test_phonetic_vann_vand() -> None:
    assert "vanguard" in stt_text_utils.normalize_stt_text("ванн")
    assert "vanguard" in stt_text_utils.normalize_stt_text("ванд")


def test_phonetic_v_mod() -> None:
    assert "wemod" in stt_text_utils.normalize_stt_text("v-mod")


def test_v_mod_not_python_module_docs() -> None:
    fake_index = [
        AppEntry(
            "Python 3.11 Module Docs (64-bit)",
            "python 3 11 module docs 64 bit",
            r"shell:AppsFolder\fake",
            "uwp",
        ),
        AppEntry("WeMod", "wemod", r"C:\fake\WeMod.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("v mod", fake_index, original_query="открой v mod")
    assert ambiguous is False
    assert entry is not None
    assert entry.display_name == "WeMod"


def test_vanguard_not_installed() -> None:
    fake_index = [
        AppEntry("VALORANT", "valorant", r"C:\fake\Valorant.lnk", "start_menu"),
    ]

    with patch.object(app_scanner, "load_or_build_index", return_value=fake_index):
        result = commands_module.try_open_scanned_app("крой вандр")

    assert result == "Riot Client не установлен, сэр."


def test_yandex_music_known_uwp_appid() -> None:
    fake_index = [
        AppEntry("Yandex Browser", "yandex browser", r"C:\fake\Browser.lnk", "start_menu"),
    ]

    with patch.object(app_scanner.os, "startfile") as mock_startfile:
        result, ambiguous = commands_module._resolve_and_launch_app(
            "yandex music",
            fake_index,
            original_query="открой yandex music",
        )

    assert ambiguous is False
    assert result is not None
    assert "Yandex Music" in result
    mock_startfile.assert_called_once_with(
        r"shell:AppsFolder\A025C540.Yandex.Music_vfvw9svesycw6!App"
    )


def test_uwp_scan_utf8_powershell() -> None:
    from unittest.mock import MagicMock, patch

    with patch("jarvis.core.sidecar_manager.SidecarManager") as mock_sm:
        mock_sm.instance.return_value.powershell_call.return_value = {"ok": False}
        with patch.object(app_scanner.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")
            app_scanner._scan_uwp_apps()

    ps_args = mock_run.call_args[0][0]
    command_text = ps_args[-1]
    assert "65001" in command_text
    assert "UTF8" in command_text
    assert mock_run.call_args[1].get("encoding") == "utf-8"


def test_inject_known_uwp_yandex_music() -> None:
    broken = [
        AppEntry("???", "yandex music", r"shell:AppsFolder\\broken", "uwp"),
    ]
    fixed = app_scanner._inject_known_uwp_entries(broken)
    music = next(e for e in fixed if e.normalized_name == "yandex music")
    assert music.display_name == "Yandex Music"
    assert "Yandex.Music" in music.launch_path


def test_blacklist() -> None:
    fake_index = [
        AppEntry("Command Prompt", "cmd", r"C:\fake\cmd.lnk", "start_menu"),
        AppEntry("Discord", "discord", r"C:\fake\Discord.lnk", "start_menu"),
    ]

    entry, ambiguous = app_scanner.find_app("cmd", fake_index)
    assert entry is None
    assert ambiguous is False

    assert app_scanner._is_blacklisted("Uninstall Discord", "uninstall discord") is True


def test_settings_not_app_scanner() -> None:
    original_execute_action = commands_module.execute_action

    try:
        commands_module.execute_action = lambda action_name: action_name
        with patch.object(commands_module, "try_open_scanned_app") as mock_scanner:
            result = commands_module.check_local_keywords("открой настройки")
            mock_scanner.assert_not_called()
            assert result == "open_settings"
    finally:
        commands_module.execute_action = original_execute_action


def test_user_apps_store_crud(tmp_path) -> None:
    import jarvis.commands.user_apps_store as user_apps_store

    fake_exe = tmp_path / "testapp.exe"
    fake_exe.write_bytes(b"MZ")

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        app, err = user_apps_store.add_app("Test App", str(fake_exe), ["открой тест апп"])
        assert err == ""
        assert app is not None

        found = user_apps_store.find_by_voice("открой тест апп")
        assert found is not None
        assert found.id == app.id

        assert user_apps_store.delete_app(app.id) is True
        assert user_apps_store.find_by_voice("открой тест апп") is None


def test_user_apps_voice_match(tmp_path) -> None:
    import jarvis.commands.user_apps_store as user_apps_store

    fake_exe = tmp_path / "game.exe"
    fake_exe.write_bytes(b"MZ")

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        user_apps_store.add_app("Моя игра", str(fake_exe), ["запусти мою игру"])
        app = user_apps_store.find_by_voice("запусти мою игру")
        assert app is not None
        assert app.display_name == "Моя игра"


def test_user_shortcut_url(tmp_path) -> None:
    import jarvis.commands.user_apps_store as user_apps_store

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        app, err = user_apps_store.add_shortcut(
            "Google",
            user_apps_store.ACTION_URL,
            ["открой гугл"],
            url="https://google.com",
        )
        assert err == ""
        assert app is not None
        assert app.action_type == user_apps_store.ACTION_URL

        with patch("jarvis.commands.user_apps_store.webbrowser.open") as mock_open:
            result = user_apps_store.launch_user_app(app)
        mock_open.assert_called_once_with("https://google.com")
        assert "Google" in result


def test_user_shortcut_folder(tmp_path) -> None:
    import jarvis.commands.user_apps_store as user_apps_store

    folder = tmp_path / "docs"
    folder.mkdir()

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        app, err = user_apps_store.add_shortcut(
            "Документы",
            user_apps_store.ACTION_FOLDER,
            ["открой документы"],
            folder_path=str(folder),
        )
        assert err == ""
        assert app is not None
        assert app.action_type == user_apps_store.ACTION_FOLDER

        with patch("jarvis.commands.user_apps_store.os.startfile") as mock_start:
            result = user_apps_store.launch_user_app(app)
        mock_start.assert_called_once_with(str(folder.resolve()))
        assert "Документы" in result


def test_game_scanner_dedupe() -> None:
    import jarvis.commands.game_scanner as game_scanner

    candidates = [
        game_scanner.GameCandidate("Game A", r"C:\Games\A\a.exe", "steam"),
        game_scanner.GameCandidate("Game A dup", r"c:\games\a\a.exe", "folder_scan"),
        game_scanner.GameCandidate("Game B", r"C:\Games\B\b.exe", "epic"),
    ]
    result = game_scanner._dedupe(candidates)
    assert len(result) == 2
    assert result[0].display_name == "Game A"
    assert result[1].display_name == "Game B"


def test_import_game_candidates(tmp_path) -> None:
    import jarvis.commands.game_scanner as game_scanner
    import jarvis.commands.user_apps_store as user_apps_store

    fake_exe = tmp_path / "cyber.exe"
    fake_exe.write_bytes(b"MZ")
    cand = game_scanner.GameCandidate("Cyber Game", str(fake_exe), "steam")

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        count, msg = user_apps_store.import_game_candidates([cand])
        assert count == 1
        assert "1" in msg

        apps = user_apps_store.load_user_apps()
        assert len(apps) == 1
        assert apps[0].source == "game_scan"
        assert apps[0].exe_path.lower() == str(fake_exe.resolve()).lower()

        count2, _ = user_apps_store.import_game_candidates([cand])
        assert count2 == 0


def test_delete_scanned_apps(tmp_path) -> None:
    import jarvis.commands.game_scanner as game_scanner
    import jarvis.commands.user_apps_store as user_apps_store

    fake_exe = tmp_path / "game.exe"
    fake_exe.write_bytes(b"MZ")
    manual_exe = tmp_path / "manual.exe"
    manual_exe.write_bytes(b"MZ")
    cand = game_scanner.GameCandidate("Scanned", str(fake_exe), "steam")

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        user_apps_store.import_game_candidates([cand])
        user_apps_store.add_app("Manual", str(manual_exe), ["открой ручной"])
        assert user_apps_store.count_scanned_apps() == 1

        removed, msg = user_apps_store.delete_scanned_apps()
        assert removed == 1
        assert "1" in msg

        apps = user_apps_store.load_user_apps()
        assert len(apps) == 1
        assert apps[0].display_name == "Manual"
        assert apps[0].source == "manual"

        removed2, _ = user_apps_store.delete_scanned_apps()
        assert removed2 == 0


def test_fast_mode_stt_profile() -> None:
    from jarvis.core.performance_profiles import FAST_STT_OVERRIDES, set_fast_mode

    snapshot = {
        "STT_MODEL_NAME": "medium",
        "STT_SILENCE_DURATION_SEC": 1.6,
        "STT_POST_ACTIVATION_DELAY_SEC": 0.65,
        "STT_BEAM_SIZE": 5,
        "STT_RETRY_ON_LOW_CONFIDENCE": True,
        "STT_WAIT_SPEECH_TIMEOUT_SEC": 6.0,
        "STT_MAX_RECORD_DURATION_SEC": 18.0,
    }
    set_fast_mode(config, True, snapshot)
    assert config.FAST_MODE is True
    assert config.STT_MODEL_NAME == FAST_STT_OVERRIDES["STT_MODEL_NAME"]
    set_fast_mode(config, False, snapshot)
    assert config.FAST_MODE is False
    assert config.STT_MODEL_NAME == "medium"


def test_load_gui_settings_fast_mode(tmp_path) -> None:
    gui_path = tmp_path / "gui_settings.json"
    gui_path.write_text(
        '{"fast_mode": true, "STT_MODEL_NAME": "medium"}',
        encoding="utf-8",
    )
    with patch.object(config, "GUI_SETTINGS_PATH", gui_path):
        config.load_gui_settings()
    assert config.FAST_MODE is True
    assert config.STT_MODEL_NAME == "small"
    config.apply_fast_mode(False)


def test_fast_mode_skips_llm() -> None:
    from jarvis.core.assistant_engine import AssistantEngine
    from jarvis.core.event_bus import EventBus
    from jarvis.core.performance_profiles import FAST_MODE_FALLBACK

    EventBus.reset()
    with patch.object(config, "FAST_MODE", True):
        engine = AssistantEngine()
        with patch("jarvis.core.assistant_engine.get_ai_response") as mock_llm, patch(
            "jarvis.core.assistant_engine.is_unreliable_stt", return_value=False
        ), patch.object(engine, "_speak"):
            engine._process_command_text("какой смысл жизни вселенной", -0.5)
    mock_llm.assert_not_called()
    assert engine.state.last_response == FAST_MODE_FALLBACK
    EventBus.reset()


def test_scenario_store_crud(tmp_path) -> None:
    import jarvis.commands.scenario_store as scenario_store

    with patch.object(config, "SCENARIOS_PATH", tmp_path / "scenarios.json"):
        scenario_store.ensure_scenarios_file()
        created, err = scenario_store.add_scenario(
            "Тест",
            ["тест сценарий"],
            [scenario_store.ScenarioStep(type="delay", delay_sec=0.01)],
        )
        assert err == ""
        assert created is not None
        loaded = scenario_store.get_scenario_by_id(created.id)
        assert loaded is not None
        assert loaded.steps[0].type == "delay"
        assert scenario_store.delete_scenario(created.id) is True


def test_scenario_runner_url_step(tmp_path) -> None:
    import jarvis.commands.scenario_runner as scenario_runner
    import jarvis.commands.scenario_store as scenario_store

    with patch.object(config, "SCENARIOS_PATH", tmp_path / "scenarios.json"):
        created, _ = scenario_store.add_scenario(
            "URL test",
            ["url test"],
            [scenario_store.ScenarioStep(type="url", url="https://example.com", delay_sec=0)],
        )
        with patch("jarvis.commands.scenario_runner.webbrowser.open") as mock_open:
            result = scenario_runner.run_scenario(created.id)
        mock_open.assert_called_once_with("https://example.com")
        assert "выполнен" in result.lower() or "готово" in result.lower()


def test_scenario_runner_exe_step(tmp_path) -> None:
    import jarvis.commands.scenario_runner as scenario_runner
    import jarvis.commands.scenario_store as scenario_store

    fake_exe = tmp_path / "step.exe"
    fake_exe.write_bytes(b"MZ")

    with patch.object(config, "SCENARIOS_PATH", tmp_path / "scenarios.json"):
        created, _ = scenario_store.add_scenario(
            "EXE test",
            ["exe test"],
            [scenario_store.ScenarioStep(type="exe", path=str(fake_exe), delay_sec=0)],
        )
        with patch("jarvis.commands.scenario_runner.subprocess.Popen") as mock_popen:
            scenario_runner.run_scenario(created.id)
        mock_popen.assert_called_once()


def test_check_local_keywords_user_app(tmp_path) -> None:
    import jarvis.commands.user_apps_store as user_apps_store

    fake_exe = tmp_path / "custom.exe"
    fake_exe.write_bytes(b"MZ")

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        user_apps_store.add_app("Custom", str(fake_exe), ["открой кастом"])
        with patch.object(user_apps_store, "launch_user_app", return_value="Открываю Custom, сэр.") as mock_launch:
            result = commands_module.check_local_keywords("открой кастом")
    assert result == "Открываю Custom, сэр."
    mock_launch.assert_called_once()


def test_check_local_keywords_scenario_trigger(tmp_path) -> None:
    import jarvis.commands.scenario_store as scenario_store

    with patch.object(config, "SCENARIOS_PATH", tmp_path / "scenarios.json"):
        scenario_store.ensure_scenarios_file()
        with patch("jarvis.commands.scenario_runner.run_scenario", return_value="Сценарий выполнен.") as mock_run:
            result = commands_module.check_local_keywords("начать работу")
    assert "Сценарий" in result
    mock_run.assert_called_once()


def test_event_bus_publish_subscribe() -> None:
    from jarvis.core.event_bus import EventBus, EventType

    EventBus.reset()
    bus = EventBus.instance()
    bus.publish(EventType.LOG_LINE, {"message": "test"})
    events = bus.poll_all()
    assert len(events) == 1
    assert events[0].type == EventType.LOG_LINE
    EventBus.reset()


def test_list_input_devices() -> None:
    import jarvis.voice.stt_module as stt_module

    fake_devices = [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "Mic USB", "max_input_channels": 2},
    ]
    with patch.object(stt_module.sd, "query_devices", return_value=fake_devices):
        devices = stt_module.list_input_devices()
    assert devices[0] == ("", "По умолчанию")
    assert devices[1] == ("1", "[1] Mic USB")


def test_frame_level() -> None:
    import numpy as np

    import jarvis.voice.stt_module as stt_module

    silent = np.zeros(160, dtype=np.float32)
    loud = np.full(160, 0.05, dtype=np.float32)
    assert stt_module._frame_level(silent) == 0.0
    assert stt_module._frame_level(loud) > 0.5


def test_event_bus_mic_level() -> None:
    from jarvis.core.event_bus import EventBus, EventType

    EventBus.reset()
    bus = EventBus.instance()
    bus.publish(EventType.MIC_LEVEL, {"level": 0.42})
    events = bus.poll_all()
    assert events[0].type == EventType.MIC_LEVEL
    assert events[0].data["level"] == 0.42
    EventBus.reset()


def test_stop_speech() -> None:
    import jarvis.voice.tts_module as tts_module

    tts_module._reset_speech_cancel()
    with patch.object(tts_module.pygame.mixer, "get_init", return_value=True), patch.object(
        tts_module.pygame.mixer.music, "stop"
    ) as mock_stop, patch.object(tts_module.pygame.mixer.music, "unload"):
        tts_module.stop_speech()
    assert tts_module._speech_cancel.is_set()
    mock_stop.assert_called_once()
    tts_module._reset_speech_cancel()


def test_delete_app_index(tmp_path) -> None:
    import jarvis.commands.app_scanner as app_scanner

    index_path = tmp_path / "apps_index.json"
    index_path.write_text('{"index_version": 4, "apps": [{"a": 1}]}', encoding="utf-8")

    with patch.object(config, "APP_INDEX_PATH", index_path):
        assert app_scanner.get_cached_index_count() >= 0
        ok, msg = app_scanner.delete_app_index()
        assert ok is True
        assert not index_path.is_file()
        ok2, _ = app_scanner.delete_app_index()
        assert ok2 is False


def test_delete_manual_apps(tmp_path) -> None:
    import jarvis.commands.game_scanner as game_scanner
    import jarvis.commands.user_apps_store as user_apps_store

    fake_exe = tmp_path / "manual.exe"
    fake_exe.write_bytes(b"MZ")
    game_exe = tmp_path / "game.exe"
    game_exe.write_bytes(b"MZ")

    with patch.object(config, "USER_APPS_PATH", tmp_path / "user_apps.json"):
        user_apps_store.add_app("Manual", str(fake_exe), ["открой ручной"])
        user_apps_store.import_game_candidates(
            [game_scanner.GameCandidate("Game", str(game_exe), "steam")]
        )
        assert user_apps_store.count_manual_apps() == 1

        removed, msg = user_apps_store.delete_manual_apps()
        assert removed == 1
        assert user_apps_store.count_manual_apps() == 0
        assert user_apps_store.count_scanned_apps() == 1


def test_assistant_engine_submit_text() -> None:
    from jarvis.core.assistant_engine import AssistantEngine
    from jarvis.core.event_bus import EventBus

    EventBus.reset()
    engine = AssistantEngine()
    with patch.object(engine, "_process_command_text", return_value=True) as mock_proc:
        engine.submit_text_command("открой spotify")
        with engine._text_lock:
            assert engine._text_queue == ["открой spotify"]
            text = engine._text_queue.pop(0)
        engine._process_command_text(text, None)
        mock_proc.assert_called_once_with("открой spotify", None)
    EventBus.reset()


def test_tts_fallback_ru_voices() -> None:
    import jarvis.voice.tts_module as tts_module

    voices = tts_module.list_russian_edge_voices(refresh=True)
    assert len(voices) >= 2
    ids = [sid for sid, _ in voices]
    assert "ru-RU-DmitryNeural" in ids


def test_edge_voice_label() -> None:
    import jarvis.voice.tts_module as tts_module

    label = tts_module.edge_voice_label("ru-RU-DmitryNeural")
    assert "Дмитрий" in label or "Dmitry" in label


def test_reload_tts_settings() -> None:
    import jarvis.voice.tts_module as tts_module

    old_voice = tts_module.VOICE
    config.TTS_VOICE = "ru-RU-SvetlanaNeural"
    tts_module.reload_tts_settings()
    assert tts_module.VOICE == "ru-RU-SvetlanaNeural"
    config.TTS_VOICE = old_voice
    tts_module.reload_tts_settings()
    assert tts_module.VOICE == old_voice


def test_list_sapi_voices() -> None:
    import jarvis.voice.tts_module as tts_module

    with patch("pyttsx3.init") as mock_init:
        fake_voice = type("V", (), {"id": "HKEY_TEST", "name": "Russian Voice"})()
        engine = mock_init.return_value
        engine.getProperty.return_value = [fake_voice]
        voices = tts_module.list_sapi_voices()
    assert voices
    assert voices[0][0] == "HKEY_TEST"


def test_preview_voice_edge_path() -> None:
    import jarvis.voice.tts_module as tts_module

    with patch.object(tts_module, "speak_edge") as mock_edge:
        tts_module.preview_voice(engine="edge", edge_voice="ru-RU-DmitryNeural")
    mock_edge.assert_called_once()


def test_resolve_tts_engine_piper_default() -> None:
    import jarvis.voice.tts_module as tts_module

    with patch.object(config, "TTS_ENGINE", "piper"), patch.object(config, "FAST_MODE", False):
        assert tts_module.resolve_tts_engine() == "piper"


def test_fast_mode_uses_piper_not_edge() -> None:
    import jarvis.voice.tts_module as tts_module

    with patch.object(config, "TTS_ENGINE", "edge"), patch.object(config, "FAST_MODE", True):
        assert tts_module.resolve_tts_engine() == "piper"


def test_silero_speakers() -> None:
    from jarvis.voice import silero_tts

    ids = [s[0] for s in silero_tts.SILERO_SPEAKERS]
    assert "eugene" in ids
    assert "aidar" in ids


def test_speak_routes_to_piper() -> None:
    import jarvis.voice.tts_module as tts_module

    with patch.object(config, "TTS_ENGINE", "piper"), patch.object(config, "FAST_MODE", False), patch.object(
        tts_module, "speak_piper", return_value=True
    ) as mock_piper:
        tts_module.speak("привет")
    mock_piper.assert_called_once()


def test_silero_prepare_text() -> None:
    from jarvis.voice.silero_tts import _prepare_text

    assert _prepare_text("  тест  ").endswith(".")


def test_voice_presets() -> None:
    import jarvis.voice.tts_module as tts_module

    assert len(tts_module.VOICE_PRESETS) >= 5
    preset = tts_module.get_voice_preset("jarvis_hd")
    assert preset is not None
    assert preset["TTS_ENGINE"] == "piper"
    assert preset["PIPER_VOICE"] == "ru_RU-ruslan-medium"


def test_apply_voice_preset() -> None:
    import jarvis.voice.tts_module as tts_module

    payload = tts_module.apply_voice_preset("edge_guy_en", {"fast_mode": True})
    assert payload["TTS_ENGINE"] == "edge"
    assert payload["TTS_VOICE"] == "en-US-GuyNeural"
    assert payload["fast_mode"] is True


def test_list_edge_voices_locales() -> None:
    import jarvis.voice.tts_module as tts_module

    ru = tts_module.list_edge_voices(locale="ru", refresh=True)
    en = tts_module.list_edge_voices(locale="en", refresh=True)
    assert any(sid.startswith("ru-") for sid, _ in ru)
    assert any(sid.startswith("en-") for sid, _ in en)


def test_preview_phrase_english() -> None:
    import jarvis.voice.tts_module as tts_module

    phrase = tts_module.preview_phrase_for_voice(edge_voice="en-US-GuyNeural", engine="edge")
    assert "Sir" in phrase


def test_piper_voices() -> None:
    from jarvis.voice import piper_tts

    assert "ru_RU-ruslan-medium" in piper_tts.PIPER_VOICES
    assert piper_tts.resolve_voice_id("unknown") == "ru_RU-ruslan-medium"


def test_piper_prepare_text() -> None:
    from jarvis.voice.piper_tts import _prepare_text

    assert _prepare_text("  тест  ").endswith(".")


def test_voice_picker_preset_tags() -> None:
    from jarvis.gui.widgets.voice_picker import _preset_tags, FILTER_OFFLINE, FILTER_EN

    piper = _preset_tags({"TTS_ENGINE": "piper", "EDGE_TTS_LOCALE": "ru"})
    assert FILTER_OFFLINE in piper
    en = _preset_tags({"TTS_ENGINE": "edge", "TTS_VOICE": "en-US-GuyNeural", "EDGE_TTS_LOCALE": "en"})
    assert FILTER_EN in en


def test_scroll_nested_isolation() -> None:
    from jarvis.gui import scroll_utils

    class FakeScroll:
        def winfo_exists(self):
            return True

        def check_if_master_is_canvas(self, widget):
            return widget == "inner"

    scroll_utils._nested_scrolls.clear()
    fake = FakeScroll()
    scroll_utils.register_nested_scroll(fake)

    class E:
        widget = "inner"

    assert scroll_utils.event_in_nested_scroll(E()) is True

    class E2:
        widget = "outer"

    assert scroll_utils.event_in_nested_scroll(E2()) is False
    scroll_utils._nested_scrolls.clear()


def test_gui_imports() -> None:
    import jarvis.gui.theme
    import jarvis.gui.scroll_utils
    import jarvis.gui.pages.dashboard_page
    import jarvis.gui.pages.apps_page
    import jarvis.gui.pages.scenarios_page
    import jarvis.gui.pages.settings_page
    import jarvis.gui.pages.logs_page
    import jarvis.gui.widgets.voice_picker


def run_test(number: int, test_func) -> None:
    try:
        test_func()
        print(f"Тест {number}: OK")
    except Exception as e:
        print(f"Тест {number}: FAIL — {e}")
        raise


if __name__ == "__main__":
    run_test(1, test_response_processor)
    run_test(2, test_memory_module)
    run_test(3, test_commands_whitelist)
    run_test(4, test_config_stt_defaults)
    run_test(5, test_llm_commands_section)
    run_test(6, test_prompt_hallucination)
    run_test(7, test_wake_word_detection)
    run_test(8, test_normalize_stt_text)
    run_test(9, test_fuzzy_settings_triggers)
    run_test(10, test_open_target_command)
    run_test(11, test_local_triggers)
    run_test(12, test_app_scanner_normalize_and_find)
    run_test(13, test_try_open_scanned_app_mock)
    run_test(14, test_open_app_tag_parser)
    run_test(15, test_bare_open_app_tag_parser)
    run_test(16, test_bare_exec_tag_parser)
    run_test(17, test_blacklist)
    run_test(18, test_settings_not_app_scanner)
    run_test(19, test_microsoft_store_not_edge)
    run_test(20, test_garbage_stt_discord_query)
    run_test(21, test_abs_studio_alias)
    run_test(22, test_cursor_alias)
    run_test(23, test_uwp_launch_path)
    run_test(24, test_open_player_not_media_pause)
    run_test(25, test_vanguard_alias_local)
    run_test(26, test_has_open_verb_pusti)
    run_test(27, test_launch_intent_blocks_search)
    run_test(28, test_yandex_music_not_browser)
    run_test(29, test_warp_not_wand)
    run_test(30, test_warp_cyrillic_not_wand)
    run_test(31, test_capcut_without_verb)
    run_test(32, test_phonetic_vanguard)
    run_test(33, test_phonetic_wemod)
    run_test(34, test_yandex_browser_real_name)
    run_test(35, test_yandex_music_not_wand)
    run_test(36, test_microsoft_store_protocol_before_edge)
    run_test(37, test_low_confidence_returns_none)
    run_test(38, test_launch_intent_stroi_wunder)
    run_test(39, test_tts_config_from_env)
    run_test(40, test_index_version_four)
    run_test(41, test_phonetic_yandex_dot_music)
    run_test(42, test_phonetic_vann_vand)
    run_test(43, test_phonetic_v_mod)
    run_test(44, test_v_mod_not_python_module_docs)
    run_test(45, test_vanguard_not_installed)
    run_test(46, test_yandex_music_known_uwp_appid)
    run_test(47, test_uwp_scan_utf8_powershell)
    run_test(48, test_inject_known_uwp_yandex_music)
    run_test(49, test_user_apps_store_crud)
    run_test(50, test_user_apps_voice_match)
    run_test(51, test_user_shortcut_url)
    run_test(52, test_user_shortcut_folder)
    run_test(53, test_game_scanner_dedupe)
    run_test(54, test_import_game_candidates)
    run_test(55, test_delete_scanned_apps)
    run_test(56, test_fast_mode_stt_profile)
    run_test(57, test_load_gui_settings_fast_mode)
    run_test(58, test_fast_mode_skips_llm)
    run_test(59, test_scenario_store_crud)
    run_test(60, test_scenario_runner_url_step)
    run_test(61, test_scenario_runner_exe_step)
    run_test(62, test_check_local_keywords_user_app)
    run_test(63, test_check_local_keywords_scenario_trigger)
    run_test(64, test_event_bus_publish_subscribe)
    run_test(65, test_list_input_devices)
    run_test(66, test_frame_level)
    run_test(67, test_event_bus_mic_level)
    run_test(68, test_stop_speech)
    run_test(69, test_delete_app_index)
    run_test(70, test_delete_manual_apps)
    run_test(71, test_assistant_engine_submit_text)
    run_test(72, test_gui_imports)
    run_test(73, test_tts_fallback_ru_voices)
    run_test(74, test_edge_voice_label)
    run_test(75, test_reload_tts_settings)
    run_test(76, test_list_sapi_voices)
    run_test(77, test_preview_voice_edge_path)
    run_test(78, test_resolve_tts_engine_piper_default)
    run_test(79, test_fast_mode_uses_piper_not_edge)
    run_test(80, test_silero_speakers)
    run_test(81, test_speak_routes_to_piper)
    run_test(82, test_silero_prepare_text)
    run_test(83, test_voice_presets)
    run_test(84, test_apply_voice_preset)
    run_test(85, test_list_edge_voices_locales)
    run_test(86, test_preview_phrase_english)
    run_test(87, test_piper_voices)
    run_test(88, test_piper_prepare_text)
    run_test(89, test_voice_picker_preset_tags)
    run_test(90, test_scroll_nested_isolation)
    run_test(91, test_exe_bundle_manifest_detects_missing)
