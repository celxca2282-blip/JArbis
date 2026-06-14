# setting_group.py
"""Группа настроек в стиле HUD."""

import customtkinter as ctk

from jarvis.gui import theme


class SettingGroup(ctk.CTkFrame):
    """Панель с заголовком и строками настроек."""

    def __init__(self, master, title: str, icon: str = "⚙", **kwargs) -> None:
        super().__init__(
            master,
            fg_color=theme.COLOR_PANEL,
            border_color=theme.COLOR_BORDER,
            border_width=1,
            corner_radius=theme.CORNER_RADIUS,
            **kwargs,
        )
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(header, text=icon, font=theme.FONT_BODY, text_color=theme.COLOR_ACCENT).pack(side="left")
        ctk.CTkLabel(header, text=title.upper(), font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left", padx=(8, 0)
        )
        theme.divider(self).pack(fill="x", padx=16, pady=(0, 4))
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="x", padx=12, pady=(4, 12))

    def add_row(self, label: str, widget) -> None:
        row = ctk.CTkFrame(self._body, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(
            row, text=label, width=200, anchor="w", font=theme.FONT_BODY, text_color=theme.COLOR_TEXT_SEC
        ).pack(side="left")
        widget.pack(side="left", padx=(8, 0))
