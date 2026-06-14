# top_bar.py
"""Верхняя панель: заголовок страницы, статус движка, быстрые действия."""

import customtkinter as ctk

import config
from jarvis.core.assistant_engine import AssistantEngine
from jarvis.gui import theme


class TopBar(ctk.CTkFrame):
    def __init__(
        self,
        master,
        engine: AssistantEngine,
        on_mute_toggle=None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            height=theme.TOPBAR_HEIGHT,
            fg_color=theme.COLOR_BG_ALT,
            corner_radius=0,
            border_width=0,
            **kwargs,
        )
        self.pack_propagate(False)
        self.engine = engine
        self._on_mute_toggle = on_mute_toggle
        self._page_key = "dashboard"

        theme.divider(self).pack(side="bottom", fill="x")

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=theme.PADDING, pady=8)

        # Заголовок страницы
        title_col = ctk.CTkFrame(inner, fg_color="transparent")
        title_col.pack(side="left", fill="y")
        self.lbl_title = ctk.CTkLabel(title_col, text="", font=theme.FONT_HEADING, text_color=theme.COLOR_TEXT)
        self.lbl_title.pack(anchor="w")
        self.lbl_subtitle = ctk.CTkLabel(title_col, text="", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM)
        self.lbl_subtitle.pack(anchor="w")

        # Правая часть — индикаторы
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")

        self._mode_badge = ctk.CTkLabel(
            right,
            text="QUALITY",
            font=theme.FONT_CAPTION,
            text_color=theme.COLOR_ACCENT,
            fg_color=theme.COLOR_ACCENT_SOFT,
            corner_radius=6,
            width=72,
            height=24,
        )
        self._mode_badge.pack(side="right", padx=(8, 0))

        self._engine_dot = ctk.CTkFrame(right, width=8, height=8, corner_radius=4, fg_color=theme.COLOR_TEXT_MUTED)
        self._engine_dot.pack(side="right", padx=(0, 6), pady=10)
        self.lbl_engine = ctk.CTkLabel(right, text="Остановлен", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM)
        self.lbl_engine.pack(side="right", padx=(12, 0))

        self.btn_mute = theme.icon_button(right, "🔇", self._toggle_mute)
        self.btn_mute.pack(side="right", padx=6)

        self.set_page("dashboard")
        self.refresh()

    def set_page(self, page_key: str) -> None:
        self._page_key = page_key
        title, subtitle = theme.PAGE_TITLES.get(page_key, ("JArbis", ""))
        self.lbl_title.configure(text=title)
        self.lbl_subtitle.configure(text=subtitle)

    def _toggle_mute(self) -> None:
        self.engine.tts_muted = not self.engine.tts_muted
        self.refresh()
        if self._on_mute_toggle:
            self._on_mute_toggle(self.engine.tts_muted)

    def refresh(self) -> None:
        if self.engine.is_running:
            self.lbl_engine.configure(text="Активен", text_color=theme.COLOR_SUCCESS)
            self._engine_dot.configure(fg_color=theme.COLOR_SUCCESS)
        else:
            self.lbl_engine.configure(text="Остановлен", text_color=theme.COLOR_TEXT_DIM)
            self._engine_dot.configure(fg_color=theme.COLOR_TEXT_MUTED)

        if config.FAST_MODE:
            self._mode_badge.configure(
                text="⚡ FAST", text_color=theme.COLOR_WARNING, fg_color=theme.COLOR_WARNING_SOFT
            )
        else:
            self._mode_badge.configure(
                text="◆ QUALITY", text_color=theme.COLOR_ACCENT, fg_color=theme.COLOR_ACCENT_SOFT
            )

        self.btn_mute.configure(text="🔇" if self.engine.tts_muted else "🔊")
