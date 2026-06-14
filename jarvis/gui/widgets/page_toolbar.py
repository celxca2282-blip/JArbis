# page_toolbar.py
"""Панель действий страницы (поиск, кнопки)."""

import customtkinter as ctk

from jarvis.gui import theme


class PageToolbar(ctk.CTkFrame):
    """Горизонтальная панель с поиском и кнопками."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._left = ctk.CTkFrame(self, fg_color="transparent")
        self._left.pack(side="left", fill="x", expand=True)
        self._right = ctk.CTkFrame(self, fg_color="transparent")
        self._right.pack(side="right")

    def add_left(self, widget) -> None:
        widget.pack(in_=self._left, side="left", padx=(0, 8))

    def add_right(self, widget) -> None:
        widget.pack(in_=self._right, side="right", padx=(6, 0))

    @staticmethod
    def search_entry(parent, textvariable, placeholder: str = "Поиск…", width: int = 200) -> ctk.CTkEntry:
        return theme.styled_entry(parent, placeholder=placeholder, textvariable=textvariable, width=width)
