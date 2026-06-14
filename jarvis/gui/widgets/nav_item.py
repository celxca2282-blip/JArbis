# nav_item.py
"""Пункт бокового меню с иконкой и glow-эффектом."""

import customtkinter as ctk

from jarvis.gui import theme


class NavItem(ctk.CTkFrame):
    def __init__(self, master, text: str, icon: str = "●", command=None, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", height=44, corner_radius=theme.CORNER_RADIUS_SM, **kwargs)
        self.pack_propagate(False)
        self._command = command
        self._active = False
        self._icon_char = icon

        self._bar = ctk.CTkFrame(self, width=3, height=28, fg_color="transparent", corner_radius=2)
        self._bar.pack(side="left", padx=(10, 0), pady=8)

        icon_wrap = ctk.CTkFrame(self, width=32, height=32, corner_radius=8, fg_color="transparent")
        icon_wrap.pack(side="left", padx=(8, 0), pady=6)
        icon_wrap.pack_propagate(False)
        self._icon = ctk.CTkLabel(icon_wrap, text=icon, font=theme.FONT_BODY, text_color=theme.COLOR_TEXT_DIM)
        self._icon.pack(expand=True)

        self._label = ctk.CTkLabel(
            self,
            text=text,
            font=theme.FONT_NAV,
            text_color=theme.COLOR_TEXT_DIM,
            anchor="w",
        )
        self._label.pack(side="left", padx=(10, 0), fill="x", expand=True)

        for widget in (self, self._label, self._icon, icon_wrap):
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_click(self, _event=None) -> None:
        if self._command:
            self._command()

    def _on_enter(self, _event=None) -> None:
        if not self._active:
            self.configure(fg_color=theme.COLOR_PANEL_HOVER)

    def _on_leave(self, _event=None) -> None:
        if not self._active:
            self.configure(fg_color="transparent")

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self.configure(fg_color=theme.COLOR_NAV_ACTIVE, border_width=1, border_color=theme.COLOR_BORDER_GLOW)
            self._bar.configure(fg_color=theme.COLOR_ACCENT)
            self._label.configure(text_color=theme.COLOR_TEXT)
            self._icon.configure(text_color=theme.COLOR_ACCENT)
        else:
            self.configure(fg_color="transparent", border_width=0)
            self._bar.configure(fg_color="transparent")
            self._label.configure(text_color=theme.COLOR_TEXT_DIM)
            self._icon.configure(text_color=theme.COLOR_TEXT_DIM)
