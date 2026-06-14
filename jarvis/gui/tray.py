# tray.py
"""Системный трей Windows."""

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ASSETS = Path(__file__).resolve().parent / "assets"


def run_tray(
    on_show: Callable[[], None],
    on_toggle_engine: Callable[[], None],
    on_toggle_mute: Callable[[], None],
    on_quit: Callable[[], None],
    get_status: Callable[[], str],
) -> Optional[object]:
    try:
        import pystray
        from PIL import Image

        def load_icon(name: str) -> Image.Image:
            path = ASSETS / name
            if path.exists():
                return Image.open(path)
            return Image.new("RGBA", (64, 64), (0, 212, 255, 255))

        icon_holder: dict = {"icon": None}

        def _build(status: str):
            img_name = "tray_listen.png" if status in ("listening", "wake", "speaking") else "tray_idle.png"
            return pystray.Icon(
                "jarbis",
                load_icon(img_name),
                "JArbis",
                menu=pystray.Menu(
                    pystray.MenuItem("Открыть", lambda icon, item: on_show(), default=True),
                    pystray.MenuItem("Запустить/Остановить", lambda icon, item: on_toggle_engine()),
                    pystray.MenuItem("Mute TTS", lambda icon, item: on_toggle_mute()),
                    pystray.MenuItem("Выход", lambda icon, item: on_quit()),
                ),
            )

        def run() -> None:
            try:
                icon_holder["icon"] = _build(get_status())
                icon_holder["icon"].run()
            except Exception as e:
                logger.error("Ошибка трея: %s", e)

        thread = threading.Thread(target=run, daemon=True, name="TrayIcon")
        thread.start()
        return icon_holder
    except Exception as e:
        logger.warning("Трей недоступен: %s", e)
        return None


def stop_tray(icon_holder: Optional[dict]) -> None:
    try:
        if icon_holder and icon_holder.get("icon"):
            icon_holder["icon"].stop()
    except Exception:
        pass
