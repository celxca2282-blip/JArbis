# ensure_assets.py
"""
Создаёт иконки GUI, если их ещё нет.
Если есть source_icon.png — собирает набор через scripts/build_icons.py.
"""

import subprocess
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
SOURCE_ICON = ASSETS_DIR / "source_icon.png"
BUILD_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_icons.py"


def _build_from_source() -> bool:
    """Пересобирает иконки из source_icon.png, если скрипт доступен."""
    if not SOURCE_ICON.is_file() or not BUILD_SCRIPT.is_file():
        return False
    try:
        subprocess.run(
            [sys.executable, str(BUILD_SCRIPT)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return True
    except Exception:
        return False


def ensure_assets() -> None:
    try:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        # Кастомный HUD-арт: один раз генерируем полный набор
        if SOURCE_ICON.is_file() and not (ASSETS_DIR / "icon.ico").is_file():
            if _build_from_source():
                return

        from PIL import Image, ImageDraw

        specs = {
            "icon.png": (COLOR := (0, 212, 255), 256),
            "tray_idle.png": ((30, 60, 90), 64),
            "tray_listen.png": ((0, 212, 255), 64),
            "mic.png": ((0, 212, 255), 48),
            "settings.png": ((0, 212, 255), 48),
            "play.png": ((0, 255, 136), 48),
            "app.png": ((0, 212, 255), 48),
            "scenario.png": ((255, 170, 0), 48),
        }

        for name, (rgb, size) in specs.items():
            path = ASSETS_DIR / name
            if path.exists():
                continue
            img = Image.new("RGBA", (size, size), (10, 14, 20, 255))
            draw = ImageDraw.Draw(img)
            margin = size // 6
            draw.ellipse(
                [margin, margin, size - margin, size - margin],
                fill=(*rgb, 220),
                outline=(30, 58, 95, 255),
                width=max(2, size // 32),
            )
            img.save(path)

        ico_path = ASSETS_DIR / "icon.ico"
        if not ico_path.exists() and (ASSETS_DIR / "icon.png").exists():
            icon_img = Image.open(ASSETS_DIR / "icon.png")
            icon_img.save(ico_path, format="ICO", sizes=[(256, 256), (64, 64), (32, 32)])
    except Exception:
        pass
