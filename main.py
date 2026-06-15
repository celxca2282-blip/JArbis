# main.py
"""
Точка входа JArbis.
По умолчанию — GUI. Консольный голосовой режим: python main.py --cli
"""

import argparse
import logging
import sys

import config

config.ensure_data_dirs()
config.migrate_legacy_data()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(module)s]: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE_PATH, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

# Алиас для тестов — логика в assistant_engine, не дублируем здесь
from jarvis.core.assistant_engine import handle_post_llm as _handle_post_llm


def run_gui() -> None:
    """Запуск премиального HUD-интерфейса."""
    from jarvis.core.sidecar_manager import SidecarManager
    from jarvis.gui.app import JarvisApp

    sm = SidecarManager.instance()
    sm.start_all()
    sm.warmup(max_wait=4.0)
    JarvisApp().run()


def run_cli() -> None:
    """Консольный режим без GUI (как раньше)."""
    from jarvis.core.assistant_engine import AssistantEngine
    from jarvis.core.event_bus import EventBus
    from jarvis.core.sidecar_manager import SidecarManager

    sm = SidecarManager.instance()
    sm.start_all()
    sm.warmup(max_wait=3.0)
    EventBus.reset()
    engine = AssistantEngine(EventBus.instance())
    engine.run_cli_loop()


def _write_crash_log(text: str) -> None:
    """Пишет текст падения рядом с exe — на случай, если GUI не успел показать окно."""
    try:
        crash_path = config.BASE_DIR / "crash.log"
        crash_path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def _show_fatal_error(message: str) -> None:
    """Показывает окно с ошибкой (для windowed exe без консоли)."""
    _write_crash_log(message)
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "JArbis — ошибка",
            message + "\n\nПодробности: data/jarvis.log и crash.log",
        )
        root.destroy()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="JArbis — голосовой ассистент")
    parser.add_argument("--cli", action="store_true", help="Консольный режим без GUI")
    args = parser.parse_args()
    try:
        if args.cli:
            run_cli()
        else:
            run_gui()
    except Exception as e:
        import traceback

        logger.exception("Критическая ошибка запуска")
        _show_fatal_error(f"JArbis не смог запуститься:\n\n{e}\n\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
