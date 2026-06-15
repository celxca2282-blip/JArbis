# app.py
"""
Главное окно JArbis — премиальный HUD на CustomTkinter.
"""

import logging
import os
import threading
from datetime import datetime

import customtkinter as ctk

import config
from jarvis.core.hybrid_assistant_engine import BootEngine, HybridAssistantEngine
from jarvis.core.sidecar_manager import SidecarManager
from jarvis.core.event_bus import EventBus, EventType
from jarvis.gui import theme
from jarvis.gui.ensure_assets import ensure_assets
from jarvis.gui.pages.apps_page import AppsPage
from jarvis.gui.pages.dashboard_page import DashboardPage
from jarvis.gui.pages.logs_page import LogsPage
from jarvis.gui.pages.scenarios_page import ScenariosPage
from jarvis.gui.pages.settings_page import SettingsPage
from jarvis.gui.tray import run_tray, stop_tray
from jarvis.gui.widgets.hud_background import HudBackground
from jarvis.gui.widgets.nav_item import NavItem
from jarvis.gui.widgets.top_bar import TopBar

logger = logging.getLogger(__name__)


class JarvisApp:
    def __init__(self) -> None:
        config.ensure_data_dirs()
        config.load_gui_settings()
        ensure_assets()
        theme.apply_theme()

        self.event_bus = EventBus.instance()
        # Сначала заглушка — окно рисуется сразу; C++ core подключится в фоне
        self.engine: BootEngine | HybridAssistantEngine = BootEngine(self.event_bus)
        self._engine_ready = False
        self._tray_holder = None
        self._minimize_to_tray = True
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._current_page = ""  # пусто — иначе _show_page("dashboard") не упакует страницу

        self.root = ctk.CTk()
        self.root.title("JArbis — голосовой ассистент")
        self.root.minsize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self.root.geometry("1280x800")
        self.root.configure(fg_color=theme.COLOR_BG)

        icon_path = __import__("pathlib").Path(__file__).resolve().parent / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        self._build_layout()
        try:
            self._hud.lower()
        except Exception:
            pass
        self.root.update_idletasks()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Control-s>", lambda e: self._ctrl_save())

        self._tray_holder = run_tray(
            on_show=self._show_window,
            on_toggle_engine=self._toggle_engine,
            on_toggle_mute=self._toggle_mute,
            on_quit=self._quit,
            get_status=lambda: self.engine.state.status.value,
        )

        self.root.after(80, self._poll_events)
        self.root.after(1000, self._tick_clock)
        self.root.after(120, self._start_engine_init)

    def _wire_engine(self, engine: BootEngine | HybridAssistantEngine) -> None:
        """Подключает движок ко всем виджетам после загрузки."""
        self.engine = engine
        self.top_bar.engine = engine
        for page in self._pages.values():
            if hasattr(page, "engine"):
                page.engine = engine
        self.top_bar.refresh()
        dashboard = self._pages.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.refresh()

    def _start_engine_init(self) -> None:
        """Поднимает C++ core в фоне, чтобы не блокировать отрисовку GUI."""

        def worker() -> None:
            try:
                os.environ.setdefault("JARBIS_HYBRID", "1")
                engine = HybridAssistantEngine(self.event_bus)
                self.root.after(0, lambda: self._on_engine_ready(engine))
            except Exception as e:
                logger.exception("Ошибка инициализации движка")
                self.root.after(0, lambda: self._on_engine_failed(str(e)))

        threading.Thread(target=worker, daemon=True, name="JarvisEngineInit").start()

    def _on_engine_ready(self, engine: HybridAssistantEngine) -> None:
        self._engine_ready = True
        self._wire_engine(engine)
        settings = self._pages.get("settings")
        if isinstance(settings, SettingsPage) and settings.get_bool_setting("auto_start_assistant"):
            if not engine.is_running:
                engine.start()
        logger.info("GUI: движок подключён")
        sidecars = SidecarManager.instance().status()
        logger.info(
            "Sidecar'ы: Node=%s Go=%s PowerShell=%s",
            sidecars.get("edge_tts_node"),
            sidecars.get("llm_proxy_go"),
            sidecars.get("powershell"),
        )

    def _on_engine_failed(self, message: str) -> None:
        dashboard = self._pages.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard._append_log(f"Ошибка движка: {message}")
        logger.error("GUI: движок недоступен: %s", message)

    def _build_layout(self) -> None:
        # HUD-фон под всем интерфейсом
        self._hud = HudBackground(self.root)
        self._hud.place(x=0, y=0, relwidth=1, relheight=1)

        shell = ctk.CTkFrame(self.root, fg_color="transparent")
        shell.pack(fill="both", expand=True)

        # ── Sidebar ──
        self.sidebar = ctk.CTkFrame(
            shell,
            width=theme.SIDEBAR_WIDTH,
            fg_color=theme.COLOR_BG_ALT,
            corner_radius=0,
            border_width=0,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        theme.divider(self.sidebar, vertical=True).pack(side="right", fill="y")

        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo.pack(fill="x", pady=(32, 24), padx=22)
        logo_row = ctk.CTkFrame(logo, fg_color="transparent")
        logo_row.pack(anchor="w")
        ctk.CTkLabel(logo_row, text="◆", font=(theme.FONT_FAMILY, 18), text_color=theme.COLOR_ACCENT).pack(side="left")
        ctk.CTkLabel(logo_row, text=" JArbis", font=theme.FONT_LOGO, text_color=theme.COLOR_TEXT).pack(side="left")
        ctk.CTkLabel(
            logo, text="VOICE ASSISTANT HUD", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(4, 0))
        theme.divider(logo).pack(fill="x", pady=(16, 0))

        nav_wrap = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_wrap.pack(fill="x", padx=10, pady=(8, 0))

        self._nav_items: dict[str, NavItem] = {}
        for key, label, icon in theme.NAV_ITEMS:
            item = NavItem(nav_wrap, label, icon=icon, command=lambda k=key: self._show_page(k))
            item.pack(fill="x", pady=2)
            self._nav_items[key] = item

        # Footer sidebar
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=18, pady=20)
        theme.divider(footer).pack(fill="x", pady=(0, 12))
        self.lbl_clock = ctk.CTkLabel(footer, text="--:--", font=theme.FONT_HEADING, text_color=theme.COLOR_TEXT_SEC)
        self.lbl_clock.pack(anchor="w")
        self.lbl_sidebar_status = ctk.CTkLabel(
            footer, text="Движок: остановлен", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM
        )
        self.lbl_sidebar_status.pack(anchor="w", pady=(4, 0))
        version_label = f"v{config.VERSION}"
        if "beta" in config.VERSION.lower():
            version_label += " · BETA"
        version_label += " · Windows"
        ctk.CTkLabel(footer, text=version_label, font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_MUTED).pack(
            anchor="w", pady=(8, 0)
        )

        # ── Правая колонка ──
        right_col = ctk.CTkFrame(shell, fg_color="transparent")
        right_col.pack(side="left", fill="both", expand=True)

        self.top_bar = TopBar(right_col, self.engine, on_mute_toggle=self._on_mute_changed)
        self.top_bar.pack(fill="x")

        self.content = ctk.CTkFrame(right_col, fg_color="transparent", corner_radius=0)
        self.content.pack(fill="both", expand=True)

        self._pages["dashboard"] = DashboardPage(self.content, self.engine)
        self._pages["apps"] = AppsPage(self.content, self.engine)
        self._pages["scenarios"] = ScenariosPage(self.content, self.engine)
        self._pages["settings"] = SettingsPage(self.content, self.engine, on_settings_saved=self._on_settings_saved)
        self._pages["logs"] = LogsPage(self.content)

        self._show_page("dashboard")

    def _tick_clock(self) -> None:
        try:
            if self.root.winfo_exists():
                now = datetime.now().strftime("%H:%M")
                self.lbl_clock.configure(text=now)
                if self.engine.is_running:
                    status = self.engine.state.status.value
                    label = theme.ORB_LABELS.get(status, status)
                    if status == "idle":
                        label = theme.ENGINE_READY_LABEL
                    self.lbl_sidebar_status.configure(
                        text=f"Движок: {label}",
                        text_color=theme.COLOR_SUCCESS,
                    )
                else:
                    self.lbl_sidebar_status.configure(text="Движок: остановлен", text_color=theme.COLOR_TEXT_DIM)
                self.top_bar.refresh()
        except Exception:
            pass
        self.root.after(1000, self._tick_clock)

    def _show_page(self, key: str) -> None:
        prev = self._current_page
        page = self._pages.get(key)
        if prev == key and page is not None:
            try:
                if page.winfo_ismapped():
                    return
            except Exception:
                pass
        self._current_page = key
        self.top_bar.set_page(key)
        for name, item in self._nav_items.items():
            item.set_active(name == key)
        for name, page in self._pages.items():
            if name == key:
                page.pack(fill="both", expand=True)
            else:
                if name == prev and hasattr(page, "on_hide"):
                    try:
                        page.on_hide()
                    except Exception as e:
                        logger.warning("on_hide %s: %s", name, e)
                page.pack_forget()
        page = self._pages.get(key)
        if page is not None:
            try:
                if hasattr(page, "on_show"):
                    page.on_show()
                elif hasattr(page, "refresh"):
                    self.root.after_idle(page.refresh)
            except Exception as e:
                logger.error("on_show %s: %s", key, e)
        try:
            self.content.update_idletasks()
        except Exception:
            pass

    def _poll_events(self) -> None:
        try:
            dashboard = self._pages.get("dashboard")
            for event in self.event_bus.poll_all():
                if event.type == EventType.STATUS_CHANGED and isinstance(dashboard, DashboardPage):
                    dashboard.orb.set_status(event.data.get("status", "idle"))
                    dashboard.refresh_stats()
                elif event.type == EventType.LOG_LINE and isinstance(dashboard, DashboardPage):
                    dashboard._append_log(event.data.get("message", ""))
                elif event.type == EventType.MIC_LEVEL and isinstance(dashboard, DashboardPage):
                    dashboard.orb.set_voice_level(float(event.data.get("level", 0.0)))
                elif event.type in {EventType.STT_RAW, EventType.STT_NORMALIZED, EventType.RESPONSE}:
                    if isinstance(dashboard, DashboardPage):
                        dashboard.refresh()
                elif event.type == EventType.SCENARIO_STEP_STARTED:
                    scenarios = self._pages.get("scenarios")
                    if isinstance(scenarios, ScenariosPage):
                        idx = event.data.get("step_index", 0)
                        total = event.data.get("step_total", 1)
                        scenarios.progress.set(idx / max(total, 1))
                elif event.type == EventType.SCENARIO_COMPLETED:
                    scenarios = self._pages.get("scenarios")
                    if isinstance(scenarios, ScenariosPage):
                        scenarios.progress.set(1.0 if event.data.get("success", True) else 0.0)
        except Exception as e:
            logger.error("poll_events: %s", e)
        self.root.after(80, self._poll_events)

    def _on_mute_changed(self, muted: bool) -> None:
        dashboard = self._pages.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.refresh_stats()

    def _on_settings_saved(self, payload: dict) -> None:
        self._minimize_to_tray = bool(payload.get("minimize_to_tray", True))
        dashboard = self._pages.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.refresh_stats()
        self.top_bar.refresh()
        if payload.get("auto_start_assistant", True) and not self.engine.is_running:
            self.engine.start()

    def _ctrl_save(self) -> None:
        if self._current_page == "scenarios":
            page = self._pages.get("scenarios")
            if isinstance(page, ScenariosPage):
                page._save()

    def _show_window(self) -> None:
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _toggle_engine(self) -> None:
        if self.engine.is_running:
            self.engine.stop()
        else:
            self.engine.start()
        self.top_bar.refresh()

    def _toggle_mute(self) -> None:
        self.engine.tts_muted = not self.engine.tts_muted
        self.top_bar.refresh()

    def _on_close(self) -> None:
        settings = self._pages.get("settings")
        if isinstance(settings, SettingsPage):
            self._minimize_to_tray = settings.get_bool_setting("minimize_to_tray")
        if self._minimize_to_tray:
            self.root.withdraw()
            self._show_tray_hint_once()
        else:
            self._quit()

    def _show_tray_hint_once(self) -> None:
        """Один раз объясняет, что приложение не закрылось, а ушло в трей."""
        hint_flag = config.DATA_DIR / ".tray_hint_shown"
        if hint_flag.exists():
            return
        try:
            from tkinter import messagebox

            messagebox.showinfo(
                "JArbis в трее",
                "Окно свёрнуто в системный трей (справа внизу, у часов).\n\n"
                "Клик по иконке JArbis — открыть снова.\n"
                "ПКМ по иконке → «Выход» — полностью закрыть программу.",
            )
            hint_flag.parent.mkdir(parents=True, exist_ok=True)
            hint_flag.write_text("1", encoding="utf-8")
        except Exception as e:
            logger.warning("Не удалось показать подсказку трея: %s", e)

    def _quit(self) -> None:
        if hasattr(self.engine, "shutdown"):
            self.engine.shutdown()
        else:
            self.engine.stop()
        stop_tray(self._tray_holder)
        try:
            SidecarManager.instance().stop_all()
        except Exception:
            pass
        try:
            self._hud.destroy()
        except Exception:
            pass
        self.root.after(0, self.root.destroy)

    def run(self) -> None:
        self.top_bar.refresh()
        self.root.mainloop()
