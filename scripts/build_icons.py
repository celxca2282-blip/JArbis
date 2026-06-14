#!/usr/bin/env python3
"""
Генерирует иконки JArbis из source_icon.png (HUD-орб).
Запуск: python scripts/build_icons.py
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "jarvis" / "gui" / "assets"
SOURCE = ASSETS / "source_icon.png"

# Запасной источник — картинка из чата Cursor (вне репозитория)
_CURSOR_ASSETS = Path.home() / ".cursor" / "projects" / "c-JArbis" / "assets"
CURSOR_SOURCE = (
    _CURSOR_ASSETS
    / "c__Users_celxc_AppData_Roaming_Cursor_User_workspaceStorage_e34209ba30df343758baff0c7651dea5_images_icon-1423f812-6c17-459c-a44f-617963fc38b2.png"
)


def _ensure_source() -> Path:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not SOURCE.is_file() and CURSOR_SOURCE.is_file():
        shutil.copy2(CURSOR_SOURCE, SOURCE)
        print("Скопирован source_icon.png из assets чата")
    if not SOURCE.is_file():
        print("Ошибка: положите PNG 512x512+ в jarvis/gui/assets/source_icon.png")
        sys.exit(1)
    return SOURCE


def main() -> None:
    from PIL import Image, ImageEnhance

    src_path = _ensure_source()
    src = Image.open(src_path).convert("RGBA")

    # Квадрат 512 — основа для всех размеров
    size = min(src.size)
    left = (src.width - size) // 2
    top = (src.height - size) // 2
    square = src.crop((left, top, left + size, top + size))

    def save_scaled(name: str, px: int) -> None:
        img = square.resize((px, px), Image.Resampling.LANCZOS)
        img.save(ASSETS / name, format="PNG")
        print(f"  {name} ({px}px)")

    print("Генерация иконок JArbis…")
    save_scaled("icon.png", 256)
    save_scaled("icon_512.png", 512)

    # Трей: idle — как есть, listen — ярче
    tray_idle = square.resize((64, 64), Image.Resampling.LANCZOS)
    tray_idle.save(ASSETS / "tray_idle.png")
    tray_listen = ImageEnhance.Brightness(tray_idle).enhance(1.35)
    tray_listen = ImageEnhance.Color(tray_listen).enhance(1.2)
    tray_listen.save(ASSETS / "tray_listen.png")
    print("  tray_idle.png / tray_listen.png (64px)")

    # Мелкие UI-иконки (из центрального орба)
    for name, px in (
        ("mic.png", 48),
        ("settings.png", 48),
        ("play.png", 48),
        ("app.png", 48),
        ("scenario.png", 48),
    ):
        save_scaled(name, px)

    # ICO для Windows (окно + exe + ярлык)
    ico_img = square.resize((256, 256), Image.Resampling.LANCZOS)
    ico_path = ASSETS / "icon.ico"
    ico_img.save(
        ico_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"  icon.ico")

    print(f"\nГотово: {ASSETS}")


if __name__ == "__main__":
    main()
