# stat_tile.py
"""Плитка метрики для dashboard."""

import customtkinter as ctk

from jarvis.gui import theme


class StatTile(ctk.CTkFrame):
    """Компактная карточка статистики."""

    def __init__(
        self,
        master,
        label: str,
        value: str = "—",
        icon: str = "●",
        accent: str = theme.COLOR_ACCENT,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=theme.COLOR_PANEL,
            border_color=theme.COLOR_BORDER,
            border_width=1,
            corner_radius=theme.CORNER_RADIUS_SM,
            **kwargs,
        )

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(12, 4))

        ctk.CTkLabel(row, text=icon, font=theme.FONT_BODY, text_color=accent).pack(side="left")
        ctk.CTkLabel(row, text=label.upper(), font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left", padx=(8, 0)
        )

        self.lbl_value = ctk.CTkLabel(
            self, text=value, font=theme.FONT_HEADING, text_color=theme.COLOR_TEXT, anchor="w"
        )
        self.lbl_value.pack(anchor="w", padx=14, pady=(0, 12))

    def set_value(self, value: str, color: str | None = None) -> None:
        self.lbl_value.configure(text=value)
        if color:
            self.lbl_value.configure(text_color=color)
