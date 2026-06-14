# tests/test_clipboard_utils.py
"""Тесты буфера обмена в полях GUI."""

import customtkinter as ctk

from jarvis.gui.clipboard_utils import (
    _tk_entry,
    bind_all_entries_in,
    bind_entry_clipboard,
    paste_into_ctk_entry,
    setup_modal_dialog_clipboard,
)


def test_tk_entry_inner_exists() -> None:
    root = ctk.CTk()
    try:
        entry = ctk.CTkEntry(root)
        inner = _tk_entry(entry)
        assert inner is not None
        bind_entry_clipboard(entry, root)
    finally:
        root.destroy()


def test_paste_updates_textvariable() -> None:
    root = ctk.CTk()
    try:
        var = ctk.StringVar(value="")
        entry = ctk.CTkEntry(root, textvariable=var, width=200)
        entry.pack()
        root.update()
        root.clipboard_clear()
        root.clipboard_append("https://test.local")
        root.update()
        assert paste_into_ctk_entry(entry, root) is True
        root.update()
        assert var.get() == "https://test.local"
        assert entry.get() == "https://test.local"
    finally:
        root.destroy()


def test_modal_entry_has_clipboard_bindtag() -> None:
    """Модальное поле получает bindtag; вставка через API работает с textvariable."""
    root = ctk.CTk()
    try:
        dialog = ctk.CTkToplevel(root)
        dialog.withdraw()
        setup_modal_dialog_clipboard(dialog)
        var = ctk.StringVar(value="")
        entry = ctk.CTkEntry(dialog, textvariable=var, width=200)
        entry.pack()
        bind_all_entries_in(dialog, dialog)
        root.update()
        inner = _tk_entry(entry)
        assert inner.bindtags()[0] == "JarvisCtkEntry"
        root.clipboard_clear()
        root.clipboard_append("paste-ok")
        root.update()
        assert paste_into_ctk_entry(entry, root) is True
        assert var.get() == "paste-ok"
        dialog.destroy()
        root.update()
    finally:
        root.destroy()
