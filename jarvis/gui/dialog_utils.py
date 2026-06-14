# dialog_utils.py
"""Модальные диалоги с рабочим Ctrl+V (вместо CTkInputDialog)."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from jarvis.gui import theme
from jarvis.gui.clipboard_utils import bind_all_entries_in, setup_modal_dialog_clipboard


def ask_string(
    parent,
    title: str,
    prompt: str,
    *,
    initial: str = "",
    width: int = 420,
) -> str | None:
    """
    Модальный ввод строки. Enter — OK, Escape — отмена.
    Возвращает текст или None.
    """
    result: dict[str, str | None] = {"value": None}

    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("520x200")
    dialog.configure(fg_color=theme.COLOR_BG_ALT)
    dialog.resizable(False, False)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    setup_modal_dialog_clipboard(dialog)

    panel = theme.panel_frame(dialog)
    panel.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(
        panel,
        text=prompt,
        font=theme.FONT_BODY,
        text_color=theme.COLOR_TEXT,
        wraplength=460,
        justify="left",
    ).pack(anchor="w", padx=16, pady=(14, 8))

    var = ctk.StringVar(value=initial)
    entry = theme.styled_entry(panel, textvariable=var, width=width)
    entry.pack(padx=16, pady=(0, 12))
    entry.focus_set()
    entry.select_range(0, "end")

    btn_row = ctk.CTkFrame(panel, fg_color="transparent")
    btn_row.pack(pady=(0, 14))

    def confirm(_event=None) -> None:
        result["value"] = var.get().strip()
        dialog.destroy()

    def cancel(_event=None) -> None:
        result["value"] = None
        dialog.destroy()

    theme.ghost_button(btn_row, "OK", confirm, accent=True, width=100).pack(side="left", padx=6)
    theme.ghost_button(btn_row, "Отмена", cancel, width=100).pack(side="left", padx=6)

    entry.bind("<Return>", confirm)
    dialog.bind("<Escape>", cancel)

    bind_all_entries_in(panel, dialog)
    dialog.after(50, lambda: _tk_focus_entry(entry))

    dialog.wait_window()
    return result["value"]


def _tk_focus_entry(entry: ctk.CTkEntry) -> None:
    """Фокус на внутренний tk.Entry — иначе Ctrl+V может не доходить."""
    try:
        inner = getattr(entry, "_entry", None)
        if inner is not None:
            inner.focus_set()
            inner.select_range(0, "end")
            return
    except tk.TclError:
        pass
    try:
        entry.focus_set()
    except tk.TclError:
        pass
