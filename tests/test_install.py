# tests/test_install.py
"""Тесты скриптов установки в 1 клик."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_install_bat_exists() -> None:
    assert (ROOT / "install.bat").is_file()
    assert (ROOT / "ЗАПУСТИТЬ.bat").is_file()
    assert (ROOT / "scripts" / "install.py").is_file()


def test_prepare_tester_dist_launchers(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from prepare_tester_dist import _write_dist_launchers

    _write_dist_launchers(tmp_path)
    assert (tmp_path / "УСТАНОВИТЬ.bat").is_file()
    assert (tmp_path / "ЗАПУСТИТЬ.bat").is_file()
    text = (tmp_path / "УСТАНОВИТЬ.bat").read_text(encoding="utf-8")
    assert ".env.example" in text


def test_find_python_launcher_returns_list() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from install import find_python_launcher

    cmd = find_python_launcher()
    # На CI и dev-машине Python обычно есть
    assert isinstance(cmd, list)
