# scroll_utils.py
"""Изоляция вложенной прокрутки CustomTkinter (колесо не уходит в родителя)."""

from __future__ import annotations

import customtkinter as ctk

# Вложенные скроллы (например, сетка голосов внутри страницы настроек)
_nested_scrolls: list[ctk.CTkScrollableFrame] = []


def register_nested_scroll(scrollable: ctk.CTkScrollableFrame) -> None:
    """Помечает вложенный скролл — родитель не будет крутиться, пока курсор над ним."""
    if scrollable not in _nested_scrolls:
        _nested_scrolls.append(scrollable)


def unregister_nested_scroll(scrollable: ctk.CTkScrollableFrame) -> None:
    """Убирает вложенный скролл из реестра (при уничтожении виджета)."""
    if scrollable in _nested_scrolls:
        _nested_scrolls.remove(scrollable)


def event_in_nested_scroll(event) -> bool:
    """True, если событие колеса пришло из вложенного скролла."""
    widget = getattr(event, "widget", None)
    if widget is None:
        return False
    for scroll in list(_nested_scrolls):
        try:
            if not scroll.winfo_exists():
                unregister_nested_scroll(scroll)
                continue
            if scroll.check_if_master_is_canvas(widget):
                return True
        except Exception:
            continue
    return False


class SmartScrollableFrame(ctk.CTkScrollableFrame):
    """Страничный скролл: не крутится, если курсор над вложенным списком."""

    def _mouse_wheel_all(self, event) -> None:
        try:
            if event_in_nested_scroll(event):
                return
        except Exception:
            pass
        super()._mouse_wheel_all(event)
