# mode_picker.py
"""Выбор режима производительности: FAST / QUALITY / HARD."""

from __future__ import annotations

import customtkinter as ctk

from jarvis.core.performance_profiles import MODE_UI, VALID_MODES, normalize_mode
from jarvis.gui import theme


class ModeCard(ctk.CTkFrame):
    """Карточка одного режима."""

    def __init__(
        self,
        master,
        mode_id: str,
        on_select,
        **kwargs,
    ) -> None:
        meta = MODE_UI[mode_id]
        self.mode_id = mode_id
        self._accent = meta["color"]
        self._on_select = on_select
        super().__init__(
            master,
            fg_color=theme.COLOR_BG_ELEVATED,
            corner_radius=theme.CORNER_RADIUS,
            border_width=1,
            border_color=theme.COLOR_BORDER,
            **kwargs,
        )

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(
            top,
            text=meta["icon"],
            font=(theme.FONT_FAMILY, 22),
        ).pack(side="left")

        ctk.CTkLabel(
            top,
            text=meta["title"].upper(),
            font=theme.FONT_CAPTION,
            text_color=theme.COLOR_TEXT_DIM,
        ).pack(side="right")

        ctk.CTkLabel(
            inner,
            text=meta["tagline"],
            font=theme.FONT_SUBHEAD,
            text_color=theme.COLOR_TEXT,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(10, 4))

        ctk.CTkLabel(
            inner,
            text=meta["hint"],
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_SEC,
            wraplength=200,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self._dot = ctk.CTkFrame(inner, width=10, height=10, corner_radius=5, fg_color=theme.COLOR_BORDER)
        self._dot.pack(anchor="w", pady=(4, 0))

        for widget in (self, inner, top):
            widget.bind("<Button-1>", self._click)
        for child in inner.winfo_children():
            child.bind("<Button-1>", self._click)

    def _click(self, _event=None) -> None:
        self._on_select(self.mode_id)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.configure(border_color=self._accent, border_width=2)
            self.configure(fg_color=theme.blend_colors(self._accent, theme.COLOR_BG_ELEVATED, 0.12))
            self._dot.configure(fg_color=self._accent)
        else:
            self.configure(border_color=theme.COLOR_BORDER, border_width=1)
            self.configure(fg_color=theme.COLOR_BG_ELEVATED)
            self._dot.configure(fg_color=theme.COLOR_BORDER)


class ModePickerPanel(ctk.CTkFrame):
    """Три карточки режима в одну строку."""

    def __init__(self, master, initial_mode: str = "quality", **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._mode_var = ctk.StringVar(value=normalize_mode(initial_mode))
        self._cards: dict[str, ModeCard] = {}

        panel = theme.panel_frame(self)
        panel.pack(fill="x", pady=8)

        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(hdr, text="⬡", font=theme.FONT_BODY).pack(side="left")
        ctk.CTkLabel(
            hdr,
            text="РЕЖИМ РАБОТЫ",
            font=theme.FONT_CAPTION,
            text_color=theme.COLOR_TEXT_DIM,
        ).pack(side="left", padx=(8, 0))

        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 14))
        for col, mode_id in enumerate(VALID_MODES):
            row.columnconfigure(col, weight=1, uniform="mode")
            card = ModeCard(row, mode_id, self._select_mode)
            card.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)
            self._cards[mode_id] = card

        self._refresh_selection()

    def _select_mode(self, mode_id: str) -> None:
        self._mode_var.set(normalize_mode(mode_id))
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        current = self.get_mode()
        for mode_id, card in self._cards.items():
            card.set_selected(mode_id == current)

    def get_mode(self) -> str:
        return normalize_mode(self._mode_var.get())

    def set_mode(self, mode: str) -> None:
        self._mode_var.set(normalize_mode(mode))
        self._refresh_selection()
