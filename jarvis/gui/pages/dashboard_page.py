# dashboard_page.py
"""Главная панель — орб, метрики, диалог, терминал событий."""

import customtkinter as ctk

import config
from jarvis.commands import user_apps_store
from jarvis.core.performance_profiles import get_mode_badge
from jarvis.core.assistant_engine import AssistantEngine
from jarvis.gui import theme
from jarvis.gui.widgets.conversation_bubble import ConversationBubble
from jarvis.gui.widgets.stat_tile import StatTile
from jarvis.gui.widgets.status_orb import StatusOrb


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, engine: AssistantEngine, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.engine = engine
        self._mic_testing = False

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=theme.PADDING, pady=(12, theme.PADDING))

        # ── Строка метрик ──
        stats_row = ctk.CTkFrame(outer, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, 16))
        for i in range(4):
            stats_row.columnconfigure(i, weight=1, uniform="stat")

        self.tile_engine = StatTile(stats_row, "Движок", "Остановлен", "⏻", theme.COLOR_TEXT_DIM)
        self.tile_engine.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.tile_mode = StatTile(stats_row, "Режим", "QUALITY", "⚡", theme.COLOR_ACCENT)
        self.tile_mode.grid(row=0, column=1, sticky="nsew", padx=6)
        self.tile_apps = StatTile(stats_row, "Ярлыки", "0", "⬡", theme.COLOR_PURPLE)
        self.tile_apps.grid(row=0, column=2, sticky="nsew", padx=6)
        self.tile_wake = StatTile(stats_row, "Wake-word", "—", "◎", theme.COLOR_WARNING)
        self.tile_wake.grid(row=0, column=3, sticky="nsew", padx=(6, 0))

        # ── Hero: орб + диалог ──
        hero = ctk.CTkFrame(outer, fg_color="transparent")
        hero.pack(fill="x", pady=(0, 16))
        hero.columnconfigure(1, weight=1)

        orb_card = theme.accent_panel(hero)
        orb_card.grid(row=0, column=0, sticky="ns", padx=(0, 12))

        ctk.CTkLabel(
            orb_card, text="СТАТУС АССИСТЕНТА", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM
        ).pack(pady=(20, 0))
        self.orb = StatusOrb(orb_card)
        self.orb.pack(padx=28, pady=(8, 4))

        btn_row = ctk.CTkFrame(orb_card, fg_color="transparent")
        btn_row.pack(pady=(8, 20), padx=20)
        self.btn_start = theme.ghost_button(btn_row, "▶  Старт", self._start, accent=True, width=130)
        self.btn_start.pack(pady=3)
        self.btn_stop = theme.ghost_button(btn_row, "■  Стоп", self._stop, width=130)
        self.btn_stop.pack(pady=3)
        self.btn_mic = theme.ghost_button(btn_row, "🎤  Микрофон", self._test_mic, width=130)
        self.btn_mic.pack(pady=3)

        dialog_card = theme.panel_frame(hero, glass=True)
        dialog_card.grid(row=0, column=1, sticky="nsew")
        dialog_inner = ctk.CTkFrame(dialog_card, fg_color="transparent")
        dialog_inner.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            dialog_inner, text="ДИАЛОГ", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM
        ).pack(anchor="w", pady=(0, 12))

        self.bubble_user = ConversationBubble(dialog_inner, "user")
        self.bubble_user.pack(fill="x", pady=(0, 12))
        self.bubble_assistant = ConversationBubble(dialog_inner, "assistant")
        self.bubble_assistant.pack(fill="x")

        self.lbl_mic_status = ctk.CTkLabel(
            dialog_inner, text="", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM
        )
        self.lbl_mic_status.pack(anchor="w", pady=(16, 0))

        # ── Нижняя зона: команда + лог ──
        bottom = theme.panel_frame(outer)
        bottom.pack(fill="both", expand=True)

        cmd_header = ctk.CTkFrame(bottom, fg_color="transparent")
        cmd_header.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(cmd_header, text="ТЕКСТОВАЯ КОМАНДА", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left"
        )
        ctk.CTkLabel(
            cmd_header, text="Enter — отправить", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_MUTED
        ).pack(side="right")

        cmd_row = ctk.CTkFrame(bottom, fg_color="transparent")
        cmd_row.pack(fill="x", padx=18, pady=(0, 12))
        self.text_cmd = theme.styled_entry(cmd_row, placeholder="Скажите текстом, что нужно сделать…")
        self.text_cmd.pack(side="left", fill="x", expand=True, padx=(0, 10))
        theme.ghost_button(cmd_row, "→", self._send_text, accent=True, width=48).pack(side="left")
        self.text_cmd.bind("<Return>", lambda e: self._send_text())

        theme.divider(bottom).pack(fill="x", padx=18)

        log_header = ctk.CTkFrame(bottom, fg_color="transparent")
        log_header.pack(fill="x", padx=18, pady=(12, 6))
        ctk.CTkLabel(log_header, text="ЛЕНТА СОБЫТИЙ", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left"
        )
        theme.ghost_button(log_header, "Очистить", self._clear_log, width=80).pack(side="right")

        self.log_box = theme.styled_textbox(bottom, height=180)
        self.log_box.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self.log_box.configure(state="disabled")

        self.refresh_stats()

    def _start(self) -> None:
        self.engine.start()
        self.refresh_stats()

    def _stop(self) -> None:
        self.engine.stop()
        self.refresh_stats()

    def _test_mic(self) -> None:
        if self._mic_testing:
            return
        if not self.engine.is_running:
            self.lbl_mic_status.configure(
                text="Сначала нажмите «Старт» — тест идёт в фоне, без зависания окна.",
                text_color=theme.COLOR_WARNING,
            )
            return

        self._mic_testing = True
        self.btn_mic.configure(state="disabled", text="🎤  Слушаю…")
        self.orb.set_status("listening")
        self.lbl_mic_status.configure(text="Скажите фразу в течение 4 секунд…", text_color=theme.COLOR_ACCENT)

        def on_done(result: str) -> None:
            self.after(0, lambda: self._mic_done(result))

        self.engine.request_mic_test(on_done)

    def _mic_done(self, result: str) -> None:
        self._mic_testing = False
        self.btn_mic.configure(state="normal", text="🎤  Микрофон")
        self.orb.set_voice_level(0.0)
        self.orb.set_status(self.engine.state.status.value)
        self.lbl_mic_status.configure(text=result, text_color=theme.COLOR_TEXT_DIM)
        self._append_log(f"Тест микрофона: {result}")

    def _send_text(self) -> None:
        text = self.text_cmd.get().strip()
        if text:
            self.engine.submit_text_command(text)
            self.text_cmd.delete(0, "end")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _append_log(self, line: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        lines = self.log_box.get("1.0", "end").splitlines()
        if len(lines) > 30:
            self.log_box.delete("1.0", "end")
            self.log_box.insert("end", "\n".join(lines[-30:]) + "\n")
        self.log_box.configure(state="disabled")

    def refresh_stats(self) -> None:
        """Обновляет плитки метрик без полного refresh диалога."""
        if self.engine.is_running:
            status = self.engine.state.status.value
            label = theme.ORB_LABELS.get(status, status)
            self.tile_engine.set_value(label, theme.COLOR_SUCCESS)
        else:
            self.tile_engine.set_value("Остановлен", theme.COLOR_TEXT_DIM)

        badge, color = get_mode_badge(config.PERFORMANCE_MODE)
        self.tile_mode.set_value(badge, color)

        try:
            count = len(user_apps_store.load_user_apps())
            self.tile_apps.set_value(str(count))
        except Exception:
            self.tile_apps.set_value("—")

        wake = config.WAKE_WORD_NAME or "—"
        self.tile_wake.set_value(wake[:12])

    def refresh(self, full_log: bool = False) -> None:
        state = self.engine.state
        self.orb.set_status(state.status.value)
        self.refresh_stats()
        stt = state.last_stt_normalized or state.last_stt_raw or "—"
        response = state.last_response or "—"
        self.bubble_user.set_text(stt)
        self.bubble_assistant.set_text(response)
        if full_log:
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            for line in state.event_log[-30:]:
                self.log_box.insert("end", line + "\n")
            self.log_box.configure(state="disabled")

    def refresh_mode_badge(self) -> None:
        """Совместимость со старым API — делегирует в refresh_stats."""
        self.refresh_stats()
