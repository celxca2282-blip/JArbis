#!/usr/bin/env python3
"""
Готовит dist/JArbis для передачи тестеру: без ключей, логов и личных данных.
Запуск: python scripts/prepare_tester_dist.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist" / "JArbis"

# Файлы в корне dist/JArbis, которые нельзя отдавать тестеру
ROOT_FILES_TO_REMOVE = (
    ".env",
    "crash.log",
)

# Личные/временные файлы в data/
DATA_FILES_TO_REMOVE = (
    "jarvis.log",
    "gui_settings.json",
    "user_profile.json",
    "user_apps.json",
    "apps_index.json",
    ".tray_hint_shown",
)

# Случайные копии конфига внутри bundle
INTERNAL_FILES_TO_REMOVE = (
    "_internal/.env",
    "_internal/.env.example",
)

TESTER_GUIDE = """JArbis — гайд для тестера
================================

Спасибо, что помогаешь протестировать! Это тестовая сборка голосового
ассистента для Windows. Ниже — всё, что нужно для первого запуска.


1. ЧТО В АРХИВЕ
---------------
Передавай и распаковывай ЦЕЛУЮ папку JArbis целиком.
Обязательно должны лежать рядом:
  • JArbis.exe
  • папка _internal
  • папка engine\ (если есть jarbis.exe — быстрый C++ движок)
  • файл .env.example
  • этот файл (КАК_ТЕСТИРОВАТЬ.txt)

Не запускай только exe без _internal — не заработает.


2. СИСТЕМНЫЕ ТРЕБОВАНИЯ
-----------------------
  • Windows 10 / 11 (64-bit)
  • Микрофон (встроенный или внешний)
  • Интернет на первом запуске (скачивание голоса Piper и моделей распознавания)
  • Ключ OpenRouter для «умных» ответов (см. ниже)


3. ПЕРВЫЙ ЗАПУСК (в 1 клик)
---------------------------
  1) Распакуй папку JArbis в удобное место (например, C:\\JArbis-test).
  2) Дважды кликни **УСТАНОВИТЬ.bat** — создаст .env из шаблона.
  3) Открой .env блокнотом и вставь OPENAI_API_KEY от OpenRouter (если нужен ИИ):
       https://openrouter.ai/
     Без ключа работают простые команды; сложные вопросы к ИИ — нет.
  4) Дважды кликни **ЗАПУСТИТЬ.bat** (или JArbis.exe).
  5) Разреши доступ к микрофону, если Windows спросит.
  6) При первом запуске подожди 1–2 минуты — скачиваются голос и модели.


4. КАК ПОЛЬЗОВАТЬСЯ
-------------------
  • Скажи: «Джарвис» — услышишь короткий сигнал.
  • Сразу после сигнала произнеси команду, например:
      «открой настройки»
      «открой калькулятор»
      «открой браузер»
      «какая погода» (нужен API-ключ)
  • Крестик (X) в окне НЕ закрывает программу — сворачивает в трей.
  • Полный выход: правый клик по иконке JArbis в трее → «Выход».
  • Настройки: вкладка «Настройки» в окне или через голос «открой настройки JArbis».


5. ЧТО ПРОВЕРИТЬ (чеклист)
--------------------------
Отметь, что сработало / не сработало:

  [ ] Программа запускается без ошибки «Ошибка» в статусе
  [ ] Слышит wake-word «Джарвис»
  [ ] Распознаёт короткую команду («открой калькулятор»)
  [ ] Озвучивает ответ (голос Piper)
  [ ] Открывает системные настройки / приложения
  [ ] Сворачивается в трей по крестику
  [ ] Выходит из трея через «Выход»
  [ ] (если есть ключ) отвечает на свободный вопрос через ИИ
  [ ] Тест микрофона в настройках показывает нормальный уровень

Если микрофон тихий: Параметры Windows → Система → Звук → Ввод →
громкость микрофона и усиление. В JArbis: Настройки → устройство ввода.


6. ЕСЛИ ЧТО-ТО СЛОМАЛОСЬ (PUBLIC BETA)
--------------------------------------
  • Это beta — баги возможны, feedback очень помогает.
  • Скачать обновление beta:
      https://github.com/celxca2282-blip/JArbis/releases/tag/v1.0.0-beta.6
  • GitHub Issues (нужен аккаунт):
      https://github.com/celxca2282-blip/JArbis/issues
  • Шаблон «Сообщение о баге» + приложи data/jarvis.log
  • Идеи: шаблон «Идея или feedback»
  • НЕ присылай .env — в нём секретный ключ!


7. ВАЖНО ПРО БЕЗОПАСНОСТЬ
-------------------------
  • .env с ключом — только у тебя на ПК.
  • Исходный код проекта открыт (MIT) на GitHub — exe собран из него.


Удачного теста!
"""

# Bat-файлы для тестера (exe-сборка)
DIST_INSTALL_BAT = """@echo off
chcp 65001 >nul
title JArbis — установка
cd /d "%~dp0"

echo.
echo  JArbis — подготовка к первому запуску
echo.

if not exist ".env" (
    if exist ".env.example" (
        copy /Y ".env.example" ".env" >nul
        echo  [OK] Создан файл .env
    ) else (
        echo  [!!] Нет .env.example
    )
) else (
    echo  [OK] Файл .env уже есть
)

echo.
echo  Дальше:
echo    1. При необходимости откройте .env и вставьте OPENAI_API_KEY
echo    2. Запустите ЗАПУСТИТЬ.bat
echo.
echo  Подробности: КАК_ТЕСТИРОВАТЬ.txt
echo.
pause
"""

DIST_RUN_BAT = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "JArbis.exe" (
    echo Не найден JArbis.exe — распакуйте архив полностью.
    pause
    exit /b 1
)
set JARBIS_HYBRID=1
if exist "%~dp0engine\\jarbis.exe" set JARBIS_CPP_EXE=%~dp0engine\\jarbis.exe
start "" "JArbis.exe"
"""


def _write_dist_launchers(dist_dir: Path) -> None:
    """Создаёт УСТАНОВИТЬ.bat и ЗАПУСТИТЬ.bat для exe-сборки."""
    (dist_dir / "УСТАНОВИТЬ.bat").write_text(DIST_INSTALL_BAT, encoding="utf-8")
    (dist_dir / "ЗАПУСТИТЬ.bat").write_text(DIST_RUN_BAT, encoding="utf-8")


def _remove_path(path: Path) -> bool:
    """Удаляет файл или папку; возвращает True, если что-то удалили."""
    if not path.exists():
        return False
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except OSError as exc:
        # Лог может быть занят запущенным JArbis.exe — очищаем содержимое
        if path.is_file() and path.name == "jarvis.log":
            try:
                path.write_text("", encoding="utf-8")
                print(f"Лог занят процессом, очищен: {path}")
                return True
            except OSError:
                print(f"Не удалось очистить {path}: {exc}")
                return False
        print(f"Не удалось удалить {path}: {exc}")
        return False


# Убирает личные данные и секреты из папки dist/JArbis
def prepare_tester_dist(dist_dir: Path = DIST_DIR) -> list[str]:
    if not dist_dir.is_dir():
        raise FileNotFoundError(f"Нет папки сборки: {dist_dir}")

    removed: list[str] = []

    for name in ROOT_FILES_TO_REMOVE:
        path = dist_dir / name
        if _remove_path(path):
            removed.append(name)

    for name in INTERNAL_FILES_TO_REMOVE:
        path = dist_dir / name
        if _remove_path(path):
            removed.append(name)

    data_dir = dist_dir / "data"
    if data_dir.is_dir():
        for name in DATA_FILES_TO_REMOVE:
            path = data_dir / name
            if _remove_path(path):
                removed.append(f"data/{name}")

        temp_dir = data_dir / "temp"
        if temp_dir.is_dir():
            shutil.rmtree(temp_dir, ignore_errors=True)
            removed.append("data/temp/")

    env_example_src = ROOT / ".env.example"
    if env_example_src.is_file():
        shutil.copy2(env_example_src, dist_dir / ".env.example")

    # Шаблон фраз shard_hard (локальный файл пользователя — в .gitignore)
    shard_example = ROOT / "data" / "shard_hard_lines.json.example"
    data_dir.mkdir(parents=True, exist_ok=True)
    if shard_example.is_file():
        shutil.copy2(shard_example, data_dir / "shard_hard_lines.json.example")

    guide_path = dist_dir / "КАК_ТЕСТИРОВАТЬ.txt"
    guide_path.write_text(TESTER_GUIDE, encoding="utf-8")

    _write_dist_launchers(dist_dir)

    # Опционально: C++ движок рядом с exe (гибрид без отдельной установки JArbisCpp)
    cpp_candidates = [
        ROOT.parent / "JArbisC++" / "build" / "Release" / "jarbis.exe",
        Path(r"C:\JArbisC++\build\Release\jarbis.exe"),
    ]
    for cpp_exe in cpp_candidates:
        if cpp_exe.is_file():
            engine_dir = dist_dir / "engine"
            engine_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cpp_exe, engine_dir / "jarbis.exe")
            print(f"В bundle добавлен C++ движок: {engine_dir / 'jarbis.exe'}")
            break

    old_guide = dist_dir / "КАК_ЗАПУСТИТЬ.txt"
    if old_guide.is_file():
        old_guide.unlink()
        removed.append("КАК_ЗАПУСТИТЬ.txt")

    return removed


def main() -> None:
    try:
        removed = prepare_tester_dist()
    except FileNotFoundError as exc:
        print(exc)
        print("Сначала соберите exe: python scripts/build_exe.py")
        sys.exit(1)

    print("=== JArbis: подготовка для тестера ===")
    if removed:
        print("Удалено:")
        for item in removed:
            print(f"  - {item}")
    else:
        print("Личных файлов не найдено (уже чисто).")

    print(f"\nГотово: {DIST_DIR}")
    print("Передай другу всю папку JArbis (лучше zip).")
    print("Внутри есть КАК_ТЕСТИРОВАТЬ.txt — пусть прочитает перед запуском.")


if __name__ == "__main__":
    main()
