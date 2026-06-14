# clipboard_utils.py
"""
Буфер обмена для CTkEntry — Windows, modal CTkToplevel, textvariable.
CustomTkinter не пробрасывает Ctrl+V; grab_set усугубляет проблему.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable
from weakref import WeakKeyDictionary, WeakSet

import customtkinter as ctk

# bindtag для внутреннего tk.Entry — перехват Ctrl+V до стандартных биндов Windows
_CLIPBOARD_TAG = "JarvisCtkEntry"
_roots_with_class_bind: WeakSet = WeakSet()

# Счётчик открытых модалок (bind_all снимаем, когда последняя закрылась)
_modal_clipboard_depth = 0
_modal_unbind: Callable[[], None] | None = None

# dialog -> cleanup для nested modals
_dialog_cleanups: WeakKeyDictionary = WeakKeyDictionary()
# dialog -> последнее поле с фокусом (grab_set часто ломает focus_get)
_dialog_last_entry: WeakKeyDictionary = WeakKeyDictionary()


def _tk_entry(widget: ctk.CTkEntry) -> tk.Entry:
    inner = getattr(widget, "_entry", None)
    if inner is not None:
        return inner
    return widget  # type: ignore[return-value]


def _clipboard_root(widget: tk.Misc) -> tk.Misc:
    try:
        return widget.winfo_toplevel()
    except tk.TclError:
        return widget


# Вставка через API CTkEntry (корректно с textvariable)
def paste_into_ctk_entry(entry: ctk.CTkEntry, clipboard_root: tk.Misc | None = None) -> bool:
    root = clipboard_root or _clipboard_root(entry)
    try:
        text = root.clipboard_get()
    except tk.TclError:
        return False
    if not text:
        return False

    try:
        if entry.index("sel.first") != entry.index("sel.last"):
            entry.delete("sel.first", "sel.last")
    except (tk.TclError, ValueError):
        pass

    try:
        entry.insert("insert", text)
    except tk.TclError:
        return False
    return True


def _copy_from_ctk_entry(entry: ctk.CTkEntry, clipboard_root: tk.Misc) -> None:
    try:
        if entry.index("sel.first") == entry.index("sel.last"):
            return
        text = entry.get()[entry.index("sel.first") : entry.index("sel.last")]
        clipboard_root.clipboard_clear()
        clipboard_root.clipboard_append(text)
    except (tk.TclError, ValueError):
        pass


def _cut_from_ctk_entry(entry: ctk.CTkEntry, clipboard_root: tk.Misc) -> None:
    _copy_from_ctk_entry(entry, clipboard_root)
    try:
        if entry.index("sel.first") != entry.index("sel.last"):
            entry.delete("sel.first", "sel.last")
    except (tk.TclError, ValueError):
        pass


def _select_all_ctk_entry(entry: ctk.CTkEntry) -> None:
    try:
        entry.select_range(0, "end")
        entry.icursor("end")
        _tk_entry(entry).focus_set()
    except tk.TclError:
        pass


def _register_entry_focus(entry: ctk.CTkEntry, dialog: tk.Misc | None = None) -> None:
    """Запоминаем поле при FocusIn — для global paste при сломанном focus_get."""
    dlg = dialog or _clipboard_root(entry)

    def on_focus_in(_event=None) -> None:
        _dialog_last_entry[dlg] = entry

    tk_entry = _tk_entry(entry)
    for w in (entry, tk_entry):
        w.bind("<FocusIn>", on_focus_in, add="+")


def _scan_focused_entry(dialog: tk.Misc) -> ctk.CTkEntry | None:
    """Ищем CTkEntry, у которого внутренний tk.Entry в фокусе."""
    found: ctk.CTkEntry | None = None

    def walk(widget: tk.Misc) -> None:
        nonlocal found
        if found is not None:
            return
        if isinstance(widget, ctk.CTkEntry):
            try:
                inner = _tk_entry(widget)
                if inner.focus_displayof() == inner:
                    found = widget
                    return
            except tk.TclError:
                pass
        try:
            for child in widget.winfo_children():
                walk(child)
        except tk.TclError:
            pass

    walk(dialog)
    return found


def _resolve_target_entry(dialog: tk.Misc, root: tk.Misc) -> ctk.CTkEntry | None:
    """Поле для вставки: focus_get → scan → последнее FocusIn."""
    try:
        focus = dialog.focus_get()
    except tk.TclError:
        focus = None
    if focus is None:
        try:
            focus = root.focus_get()
        except tk.TclError:
            focus = None

    if focus is not None:
        entry = _ctk_entry_from_focus(focus, dialog)
        if entry is not None:
            return entry

    scanned = _scan_focused_entry(dialog)
    if scanned is not None:
        return scanned

    last = _dialog_last_entry.get(dialog)
    if last is not None:
        try:
            if last.winfo_exists():
                return last
        except tk.TclError:
            pass
    return None


def _ctk_from_tk_entry(widget: tk.Misc) -> ctk.CTkEntry | None:
    """CTkEntry-родитель для внутреннего tk.Entry."""
    try:
        parent = widget.master
    except (tk.TclError, AttributeError):
        return None
    if isinstance(parent, ctk.CTkEntry):
        return parent
    return None


def _ensure_class_bindings(root: tk.Misc) -> None:
    """Один раз на окно: bind_class на наш тег (надёжно на Windows)."""
    if root in _roots_with_class_bind:
        return
    _roots_with_class_bind.add(root)

    def paste_handler(event) -> str:
        entry = _ctk_from_tk_entry(event.widget)
        if entry is None:
            return "break"
        paste_into_ctk_entry(entry, root)
        return "break"

    def copy_handler(event) -> str:
        entry = _ctk_from_tk_entry(event.widget)
        if entry is None:
            return "break"
        _copy_from_ctk_entry(entry, root)
        return "break"

    def cut_handler(event) -> str:
        entry = _ctk_from_tk_entry(event.widget)
        if entry is None:
            return "break"
        _cut_from_ctk_entry(entry, root)
        return "break"

    def select_all_handler(event) -> str:
        entry = _ctk_from_tk_entry(event.widget)
        if entry is None:
            return "break"
        _select_all_ctk_entry(entry)
        return "break"

    def ctrl_key_handler(event) -> str | None:
        entry = _ctk_from_tk_entry(event.widget)
        if entry is None:
            return None
        if not (event.state & 0x4):
            return None
        key = (event.keysym or "").lower()
        kc = getattr(event, "keycode", 0)
        if key == "v" or kc == 86:
            paste_into_ctk_entry(entry, root)
            return "break"
        if key == "c" or kc == 67:
            _copy_from_ctk_entry(entry, root)
            return "break"
        if key == "x" or kc == 88:
            _cut_from_ctk_entry(entry, root)
            return "break"
        if key == "a" or kc == 65:
            _select_all_ctk_entry(entry)
            return "break"
        return None

    class_bindings = (
        ("<Control-v>", paste_handler),
        ("<Control-V>", paste_handler),
        ("<Control-Key-v>", paste_handler),
        ("<Control-Key-V>", paste_handler),
        ("<Shift-Insert>", paste_handler),
        ("<Control-c>", copy_handler),
        ("<Control-C>", copy_handler),
        ("<Control-x>", cut_handler),
        ("<Control-X>", cut_handler),
        ("<Control-a>", select_all_handler),
        ("<Control-A>", select_all_handler),
        ("<Control-KeyPress>", ctrl_key_handler),
    )
    for sequence, handler in class_bindings:
        root.bind_class(_CLIPBOARD_TAG, sequence, handler, add="+")


def _apply_clipboard_bindtag(tk_entry: tk.Entry) -> None:
    """Ставим наш bindtag первым — иначе Windows перехватывает Ctrl+V."""
    try:
        tags = list(tk_entry.bindtags())
    except tk.TclError:
        return
    if _CLIPBOARD_TAG in tags:
        tags.remove(_CLIPBOARD_TAG)
    tags.insert(0, _CLIPBOARD_TAG)
    tk_entry.bindtags(tags)


def _ctk_entry_from_focus(focus: tk.Misc | str | None, dialog: tk.Misc) -> ctk.CTkEntry | None:
    """Находит CTkEntry по виджету в фокусе внутри dialog."""
    if focus is None:
        return None
    try:
        widget = dialog.nametowidget(focus) if isinstance(focus, str) else focus
    except (tk.TclError, KeyError):
        return None

    current: tk.Misc | None = widget
    while current is not None:
        if isinstance(current, ctk.CTkEntry):
            try:
                if current.winfo_exists() and _widget_is_descendant(current, dialog):
                    return current
            except tk.TclError:
                return None
        try:
            current = current.master
        except (tk.TclError, AttributeError):
            break
    return None


def _widget_is_descendant(widget: tk.Misc, ancestor: tk.Misc) -> bool:
    current: tk.Misc | None = widget
    while current is not None:
        if current == ancestor:
            return True
        try:
            current = current.master
        except (tk.TclError, AttributeError):
            break
    return False


def _add_context_menu(entry: ctk.CTkEntry) -> None:
    """ПКМ → Вставить / Копировать / Вырезать."""
    root = _clipboard_root(entry)
    tk_entry = _tk_entry(entry)
    menu = tk.Menu(tk_entry, tearoff=0)

    menu.add_command(
        label="Вставить",
        command=lambda: paste_into_ctk_entry(entry, root),
    )
    menu.add_command(
        label="Копировать",
        command=lambda: _copy_from_ctk_entry(entry, root),
    )
    menu.add_command(
        label="Вырезать",
        command=lambda: _cut_from_ctk_entry(entry, root),
    )
    menu.add_separator()
    menu.add_command(
        label="Выделить всё",
        command=lambda: _select_all_ctk_entry(entry),
    )

    def show_menu(event) -> str:
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    for seq in ("<Button-3>", "<Button-2>"):
        tk_entry.bind(seq, show_menu, add="+")
        entry.bind(seq, show_menu, add="+")


def bind_entry_clipboard(
    entry: ctk.CTkEntry,
    clipboard_root: tk.Misc | None = None,
    *,
    dialog: tk.Misc | None = None,
) -> None:
    """Локальные горячие клавиши + контекстное меню на одном поле."""
    root = clipboard_root or _clipboard_root(entry)
    focus_dialog = dialog or (root if isinstance(root, ctk.CTkToplevel) else _clipboard_root(entry))

    if getattr(entry, "_jarvis_clipboard_bound", False):
        _ensure_class_bindings(root)
        _apply_clipboard_bindtag(_tk_entry(entry))
        _register_entry_focus(entry, focus_dialog)
        return

    entry._jarvis_clipboard_bound = True  # type: ignore[attr-defined]
    tk_entry = _tk_entry(entry)
    _ensure_class_bindings(root)
    _apply_clipboard_bindtag(tk_entry)

    def paste(_event=None) -> str:
        paste_into_ctk_entry(entry, root)
        return "break"

    def copy(_event=None) -> str:
        _copy_from_ctk_entry(entry, root)
        return "break"

    def cut(_event=None) -> str:
        _cut_from_ctk_entry(entry, root)
        return "break"

    def select_all(_event=None) -> str:
        _select_all_ctk_entry(entry)
        return "break"

    # KeyPress надёжнее на Windows при modal grab; keycode — запасной путь
    def on_ctrl_key(event) -> str | None:
        if not (event.state & 0x4):
            return None
        key = (event.keysym or "").lower()
        kc = getattr(event, "keycode", 0)
        if key == "v" or kc == 86:
            return paste()
        if key == "c" or kc == 67:
            return copy()
        if key == "x" or kc == 88:
            return cut()
        if key == "a" or kc == 65:
            return select_all()
        return None

    shortcuts = (
        ("<Control-v>", paste),
        ("<Control-V>", paste),
        ("<Control-Key-v>", paste),
        ("<Control-Key-V>", paste),
        ("<Control-c>", copy),
        ("<Control-C>", copy),
        ("<Control-x>", cut),
        ("<Control-X>", cut),
        ("<Control-a>", select_all),
        ("<Control-A>", select_all),
        ("<Shift-Insert>", paste),
        ("<Control-KeyPress>", on_ctrl_key),
    )
    for sequence, handler in shortcuts:
        tk_entry.bind(sequence, handler, add="+")
        entry.bind(sequence, handler, add="+")

    _add_context_menu(entry)
    _register_entry_focus(entry, focus_dialog)


def setup_modal_dialog_clipboard(dialog: ctk.CTkToplevel) -> None:
    """
    Пока открыто модальное окно — глобальный Ctrl+V / Shift+Insert для полей внутри него.
    Вызывать сразу после grab_set().
    """
    global _modal_clipboard_depth, _modal_unbind

    root = dialog.winfo_toplevel()

    def target_entry() -> ctk.CTkEntry | None:
        return _resolve_target_entry(dialog, root)

    def global_paste(_event=None) -> str | None:
        entry = target_entry()
        if entry is None:
            return None
        paste_into_ctk_entry(entry, root)
        return "break"

    def global_ctrl_key(event) -> str | None:
        entry = target_entry()
        if entry is None:
            return None
        if not (event.state & 0x4):
            return None
        key = (event.keysym or "").lower()
        kc = getattr(event, "keycode", 0)
        if key == "v" or kc == 86:
            paste_into_ctk_entry(entry, root)
            return "break"
        if key == "c" or kc == 67:
            _copy_from_ctk_entry(entry, root)
            return "break"
        if key == "x" or kc == 88:
            _cut_from_ctk_entry(entry, root)
            return "break"
        if key == "a" or kc == 65:
            _select_all_ctk_entry(entry)
            return "break"
        return None

    modal_shortcuts = (
        ("<Control-v>", global_paste),
        ("<Control-V>", global_paste),
        ("<Control-Key-v>", global_paste),
        ("<Control-Key-V>", global_paste),
        ("<Shift-Insert>", global_paste),
        ("<Control-KeyPress>", global_ctrl_key),
    )

    def activate() -> None:
        global _modal_clipboard_depth, _modal_unbind
        _modal_clipboard_depth += 1
        for sequence, handler in modal_shortcuts:
            dialog.bind(sequence, handler, add="+")
        if _modal_clipboard_depth == 1:
            for sequence, handler in modal_shortcuts:
                root.bind_all(sequence, handler, add="+")

            def deactivate() -> None:
                global _modal_clipboard_depth, _modal_unbind
                _modal_clipboard_depth = max(0, _modal_clipboard_depth - 1)
                for sequence, _handler in modal_shortcuts:
                    try:
                        dialog.unbind(sequence)
                    except tk.TclError:
                        pass
                if _modal_clipboard_depth == 0:
                    for sequence, _handler in modal_shortcuts:
                        try:
                            root.unbind_all(sequence)
                        except tk.TclError:
                            pass
                    _modal_unbind = None

            _modal_unbind = deactivate

    def on_destroy(_event=None) -> None:
        cleanup = _dialog_cleanups.pop(dialog, None)
        if cleanup:
            cleanup()

    def cleanup() -> None:
        if _modal_unbind:
            _modal_unbind()

    _dialog_cleanups[dialog] = cleanup
    dialog.bind("<Destroy>", on_destroy, add="+")
    activate()


def bind_all_entries_in(container: tk.Misc, clipboard_root: tk.Misc | None = None) -> None:
    """Рекурсивно вешает clipboard на все CTkEntry внутри контейнера."""
    root = clipboard_root or _clipboard_root(container)
    dialog = root if isinstance(root, ctk.CTkToplevel) else None

    def walk(widget: tk.Misc) -> None:
        if isinstance(widget, ctk.CTkEntry):
            bind_entry_clipboard(widget, root, dialog=dialog)
        try:
            for child in widget.winfo_children():
                walk(child)
        except tk.TclError:
            pass

    walk(container)
