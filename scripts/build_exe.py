#!/usr/bin/env python3
"""
Собирает JArbis.exe для Windows (PyInstaller, папка dist/JArbis/).
Запуск: python scripts/build_exe.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    print("=== JArbis: иконки ===")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_icons.py")], check=True)

    icon_ico = ROOT / "jarvis" / "gui" / "assets" / "icon.ico"
    if not icon_ico.is_file():
        print("Ошибка: нет icon.ico")
        sys.exit(1)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Установите PyInstaller: pip install pyinstaller")
        sys.exit(1)

    print("\n=== JArbis: сборка exe (5–15 мин) ===")
    spec = ROOT / "jarbis.spec"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)

    out_dir = ROOT / "dist" / "JArbis"
    exe = out_dir / "JArbis.exe"
    if exe.is_file():
        print("\n=== JArbis: проверка bundle ===")
        verify = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_exe_bundle.py")],
            check=False,
        )
        if verify.returncode != 0:
            print("Ошибка: сборка неполная, см. список выше")
            sys.exit(1)

        # Чистая сборка для тестера: без .env, логов и личных data/
        sys.path.insert(0, str(ROOT / "scripts"))
        from prepare_tester_dist import prepare_tester_dist

        removed = prepare_tester_dist(out_dir)
        if removed:
            print("Очищено для тестера:", ", ".join(removed))
        print(f"\nГотово: {exe}")
        print("Для друга: заархивируйте всю папку dist/JArbis (см. КАК_ТЕСТИРОВАТЬ.txt).")
        print("Свой .env в dist не копируется — тестер создаёт свой из .env.example.")
    else:
        print("Сборка завершилась, но JArbis.exe не найден")
        sys.exit(1)


if __name__ == "__main__":
    main()
