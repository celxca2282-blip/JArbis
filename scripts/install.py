#!/usr/bin/env python3
"""
Установка JArbis в один клик (Windows): venv, зависимости, .env, голос Piper.
Запуск: install.bat  или  python scripts/install.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / "venv"
PYTHON_MIN = (3, 11)


# Запускает команду и проверяет код возврата
def _run(cmd: list[str], *, step: str) -> None:
    print(f"\n>>> {step}")
    print("    ", " ".join(cmd))
    try:
        result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    except OSError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    if result.returncode != 0:
        print(f"Ошибка на шаге «{step}» (код {result.returncode})")
        sys.exit(result.returncode)


# Ищет подходящий Python 3.11/3.12 в системе
def find_python_launcher() -> list[str]:
    candidates = [
        ["py", "-3.12"],
        ["py", "-3.11"],
        ["py", "-3"],
        ["python"],
        ["python3"],
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(
                [*cmd, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if result.returncode != 0:
            continue
        version_str = (result.stdout or "").strip()
        try:
            major_s, minor_s = version_str.split(".", 1)
            major, minor = int(major_s), int(minor_s.split(".")[0])
        except ValueError:
            continue
        if (major, minor) < PYTHON_MIN:
            print(f"Пропуск {' '.join(cmd)}: версия {version_str} слишком старая (нужен 3.11+)")
            continue
        if (major, minor) >= (3, 13):
            print(
                f"Внимание: Python {version_str} не тестировался. "
                "Рекомендуем 3.11 или 3.12."
            )
        return cmd
    return []


def venv_python() -> Path:
    exe = VENV_DIR / "Scripts" / "python.exe"
    if not exe.is_file():
        print("Не найден venv\\Scripts\\python.exe — сначала создайте окружение.")
        sys.exit(1)
    return exe


# Создаёт .env из шаблона, если его ещё нет
def ensure_env_file() -> None:
    env_path = ROOT / ".env"
    example = ROOT / ".env.example"
    if env_path.is_file():
        print("\n>>> .env уже есть — не перезаписываем")
        return
    if not example.is_file():
        print("\n>>> Нет .env.example — пропуск")
        return
    shutil.copy2(example, env_path)
    print("\n>>> Создан .env из .env.example")
    print("    При необходимости откройте .env и вставьте OPENAI_API_KEY (OpenRouter).")
    print("    Без ключа работают локальные команды; ИИ — нет.")


# Пишет ЗАПУСТИТЬ.bat для быстрого старта после установки
def write_launcher_bat() -> None:
    bat = ROOT / "ЗАПУСТИТЬ.bat"
    bat.write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "cd /d \"%~dp0\"\r\n"
        "if not exist \"venv\\Scripts\\python.exe\" (\r\n"
        "  echo Сначала запустите install.bat\r\n"
        "  pause\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        "call \"%~dp0launch_hybrid.bat\" %*\r\n",
        encoding="utf-8",
    )
    print(f"\n>>> Создан ярлык запуска: {bat.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Установка JArbis (venv + deps + голос)")
    parser.add_argument("--skip-voice", action="store_true", help="Не скачивать Piper (~60 МБ)")
    parser.add_argument("--launch", action="store_true", help="Запустить main.py после установки")
    args = parser.parse_args()

    print("=" * 50)
    print("  JArbis — установка в один клик")
    print("=" * 50)
    print(f"Папка: {ROOT}")

    py_cmd = find_python_launcher()
    if not py_cmd:
        print(
            "\nНе найден Python 3.11 или 3.12.\n"
            "Скачайте: https://www.python.org/downloads/\n"
            "При установке отметьте «Add python.exe to PATH»."
        )
        sys.exit(1)

    print(f"\nИспользуем: {' '.join(py_cmd)}")

    if not VENV_DIR.is_dir():
        _run([*py_cmd, "-m", "venv", str(VENV_DIR)], step="Создание venv")
    else:
        print("\n>>> venv уже есть — пропуск создания")

    py = venv_python()

    # На Windows pip.exe нельзя обновлять напрямую — только через python -m pip
    _run([str(py), "-m", "pip", "install", "--upgrade", "pip"], step="Обновление pip")
    _run(
        [str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements-dev.txt")],
        step="Установка зависимостей (может занять несколько минут)",
    )

    ensure_env_file()
    config.ensure_data_dirs()

    if not args.skip_voice:
        _run([str(py), str(ROOT / "scripts" / "download_voice.py")], step="Скачивание голоса Piper")
    else:
        print("\n>>> Пропуск download_voice (--skip-voice)")

    write_launcher_bat()

    print("\n" + "=" * 50)
    print("  Готово!")
    print("  Запуск: двойной клик ЗАПУСТИТЬ.bat")
    print("  или:    venv\\Scripts\\python.exe main.py")
    print("=" * 50)

    if args.launch:
        _run([str(py), str(ROOT / "main.py")], step="Запуск JArbis")


if __name__ == "__main__":
    # config только для ensure_data_dirs при импорте из корня
    sys.path.insert(0, str(ROOT))
    import config  # noqa: E402

    main()
