# apps_page.py
"""Ярлыки: программа, ссылка, папка + опциональный скан игр."""

import customtkinter as ctk
from tkinter import filedialog, messagebox

from jarvis.commands import game_scanner, user_apps_store
from jarvis.core.assistant_engine import AssistantEngine
from jarvis.gui import theme
from jarvis.gui.widgets.page_toolbar import PageToolbar
from jarvis.gui.widgets.shortcut_tile import ShortcutTile

TYPE_LABELS = {
    user_apps_store.ACTION_EXE: "Программа",
    user_apps_store.ACTION_URL: "Ссылка",
    user_apps_store.ACTION_FOLDER: "Папка",
}


class AppsPage(ctk.CTkFrame):
    def __init__(self, master, engine: AssistantEngine, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.engine = engine
        self._search_var = ctk.StringVar(value="")
        self._search_var.trace_add("write", lambda *_: self.refresh())

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=theme.PADDING, pady=(8, theme.PADDING))

        toolbar = PageToolbar(wrap)
        toolbar.pack(fill="x", pady=(0, 12))
        self._lbl_count = ctk.CTkLabel(
            toolbar._left, text="0 ярлыков", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM
        )
        self._lbl_count.pack(side="left")
        toolbar.add_right(theme.ghost_button(toolbar._right, "+ Добавить", self._add_dialog, accent=True, width=120))
        toolbar.add_right(theme.ghost_button(toolbar._right, "Удалить скан", self._delete_scanned_dialog, width=120))
        toolbar.add_right(theme.ghost_button(toolbar._right, "Скан игр", self._scan_games_dialog, width=100))
        toolbar.add_right(
            PageToolbar.search_entry(toolbar._right, self._search_var, placeholder="Поиск по названию…", width=200)
        )

        self.scroll = theme.scroll_area(wrap)
        self.scroll.pack(fill="both", expand=True)

    def refresh(self) -> None:
        for child in self.scroll.winfo_children():
            child.destroy()

        query = self._search_var.get().lower().strip()
        apps = user_apps_store.load_user_apps()
        visible = []
        for app in apps:
            target = app.target_label().lower()
            if query and query not in app.display_name.lower() and query not in target:
                continue
            visible.append(app)

        self._lbl_count.configure(text=f"{len(visible)} из {len(apps)} ярлыков")

        if not visible:
            empty = theme.panel_frame(self.scroll)
            empty.pack(fill="x", pady=12)
            inner = ctk.CTkFrame(empty, fg_color="transparent")
            inner.pack(padx=24, pady=28)
            ctk.CTkLabel(inner, text="⬡", font=(theme.FONT_FAMILY, 32), text_color=theme.COLOR_TEXT_MUTED).pack()
            ctk.CTkLabel(
                inner,
                text="Пока пусто",
                font=theme.FONT_HEADING,
                text_color=theme.COLOR_TEXT_SEC,
            ).pack(pady=(8, 4))
            ctk.CTkLabel(
                inner,
                text="Добавьте ярлык вручную или воспользуйтесь сканом игр.",
                font=theme.FONT_BODY,
                text_color=theme.COLOR_TEXT_DIM,
            ).pack()
            theme.ghost_button(inner, "+ Добавить ярлык", self._add_dialog, accent=True).pack(pady=(16, 0))
            return

        for app in visible:
            tile = ShortcutTile(
                self.scroll,
                app,
                TYPE_LABELS.get(app.action_type, "Ярлык"),
                on_launch=self._launch,
                on_voice=self._test_voice,
                on_edit=self._edit_dialog,
                on_delete=self._delete,
            )
            tile.pack(fill="x", pady=6)

    def _launch(self, app: user_apps_store.UserApp) -> None:
        messagebox.showinfo("Запуск", user_apps_store.launch_user_app(app))

    def _test_voice(self, app: user_apps_store.UserApp) -> None:
        if app.voice_triggers:
            self.engine.submit_text_command(app.voice_triggers[0])

    def _delete(self, app: user_apps_store.UserApp) -> None:
        if messagebox.askyesno("Удаление", f"Удалить «{app.display_name}»?"):
            user_apps_store.delete_app(app.id)
            self.refresh()

    def _delete_scanned_dialog(self) -> None:
        count = user_apps_store.count_scanned_apps()
        if count == 0:
            messagebox.showinfo("Удаление скана", "Нет ярлыков, добавленных через скан игр.")
            return
        if not messagebox.askyesno(
            "Удалить скан",
            f"Удалить все ярлыки из скана игр ({count})?\n"
            "Ручные ярлыки (программы, ссылки, папки) не затронуты.",
        ):
            return
        removed, msg = user_apps_store.delete_scanned_apps()
        messagebox.showinfo("Удаление скана", msg)
        if removed:
            self.refresh()

    def _scan_games_dialog(self) -> None:
        if not messagebox.askokcancel(
            "Скан игр",
            "Автопоиск может найти не всё, дубли или лишнее.\n"
            "Надёжнее добавлять .exe вручную.\n\n"
            "Продолжить сканирование?",
        ):
            return

        candidates = game_scanner.scan_games()
        if not candidates:
            messagebox.showinfo("Скан игр", "Игры не найдены. Проверьте Steam/Epic или добавьте вручную.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Импорт игр")
        dialog.geometry("680x520")
        dialog.configure(fg_color=theme.COLOR_BG_ALT)
        dialog.grab_set()

        header = theme.panel_frame(dialog)
        header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            header,
            text=f"Найдено: {len(candidates)}",
            font=theme.FONT_HEADING,
            text_color=theme.COLOR_TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            header,
            text="Отметьте игры для импорта как голосовые ярлыки.",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=16, pady=(0, 12))

        scroll = theme.scroll_area(dialog)
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        checks: list[tuple[ctk.BooleanVar, object]] = []
        for cand in candidates:
            var = ctk.BooleanVar(value=True)
            row = ctk.CTkFrame(scroll, fg_color=theme.COLOR_PANEL, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkCheckBox(row, text="", variable=var, width=28, fg_color=theme.COLOR_ACCENT).pack(
                side="left", padx=(12, 4), pady=10
            )
            label = f"{cand.display_name}  [{cand.source}]"
            ctk.CTkLabel(row, text=label, font=theme.FONT_BODY, anchor="w").pack(
                side="left", fill="x", expand=True, padx=(0, 12), pady=10
            )
            checks.append((var, cand))

        def import_selected() -> None:
            selected = [cand for var, cand in checks if var.get()]
            count, msg = user_apps_store.import_game_candidates(selected)
            messagebox.showinfo("Импорт", msg)
            dialog.destroy()
            self.refresh()

        theme.ghost_button(dialog, "Импортировать выбранные", import_selected, accent=True).pack(pady=16)

    def _add_dialog(self) -> None:
        self._open_dialog(None)

    def _edit_dialog(self, app: user_apps_store.UserApp) -> None:
        self._open_dialog(app)

    def _open_dialog(self, app: user_apps_store.UserApp | None) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Ярлык")
        dialog.geometry("560x540")
        dialog.configure(fg_color=theme.COLOR_BG_ALT)
        dialog.grab_set()

        type_var = ctk.StringVar(value=app.action_type if app else user_apps_store.ACTION_EXE)
        name_var = ctk.StringVar(value=app.display_name if app else "")
        path_var = ctk.StringVar(value=app.exe_path if app else "")
        url_var = ctk.StringVar(value=app.url if app else "")
        folder_var = ctk.StringVar(value=app.folder_path if app else "")
        wd_var = ctk.StringVar(value=app.working_dir if app else "")
        args_var = ctk.StringVar(value=app.args if app else "")
        triggers_var = ctk.StringVar(value=", ".join(app.voice_triggers) if app else "")
        enabled_var = ctk.BooleanVar(value=app.enabled if app else True)
        err_lbl = ctk.CTkLabel(dialog, text="", text_color=theme.COLOR_ERROR, font=theme.FONT_SMALL)

        form = theme.panel_frame(dialog)
        form.pack(fill="both", expand=True, padx=16, pady=16)

        path_lbl = ctk.CTkLabel(form, text="Путь к .exe", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM)
        path_row = ctk.CTkFrame(form, fg_color="transparent")
        path_entry = theme.styled_entry(path_row, textvariable=path_var, width=360)
        url_lbl = ctk.CTkLabel(form, text="Ссылка (https://…)", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM)
        url_entry = theme.styled_entry(form, textvariable=url_var, width=460)
        folder_lbl = ctk.CTkLabel(form, text="Папка", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM)
        folder_row = ctk.CTkFrame(form, fg_color="transparent")
        folder_entry = theme.styled_entry(folder_row, textvariable=folder_var, width=360)
        extra_frame = ctk.CTkFrame(form, fg_color="transparent")

        def rebuild_fields(*_args) -> None:
            for w in (path_lbl, path_row, url_lbl, url_entry, folder_lbl, folder_row, extra_frame):
                w.pack_forget()

            t = type_var.get()
            if t == user_apps_store.ACTION_EXE:
                path_lbl.pack(anchor="w", padx=16, pady=(8, 0))
                path_row.pack(fill="x", padx=16)
                extra_frame.pack(fill="x", padx=16)
                ctk.CTkLabel(extra_frame, text="Рабочая папка", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM).pack(
                    anchor="w", pady=(8, 0)
                )
                theme.styled_entry(extra_frame, textvariable=wd_var, width=460).pack(anchor="w")
                ctk.CTkLabel(extra_frame, text="Аргументы", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM).pack(
                    anchor="w", pady=(8, 0)
                )
                theme.styled_entry(extra_frame, textvariable=args_var, width=460).pack(anchor="w")
            elif t == user_apps_store.ACTION_URL:
                url_lbl.pack(anchor="w", padx=16, pady=(8, 0))
                url_entry.pack(padx=16)
            else:
                folder_lbl.pack(anchor="w", padx=16, pady=(8, 0))
                folder_row.pack(fill="x", padx=16)

        def browse_exe() -> None:
            p = filedialog.askopenfilename(filetypes=[("EXE", "*.exe")])
            if p:
                path_var.set(p)

        def browse_folder() -> None:
            p = filedialog.askdirectory()
            if p:
                folder_var.set(p)

        ctk.CTkLabel(form, text="РЕДАКТОР ЯРЛЫКА", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            anchor="w", padx=16, pady=(14, 8)
        )
        ctk.CTkLabel(form, text="Тип", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM).pack(anchor="w", padx=16)
        type_row = ctk.CTkFrame(form, fg_color="transparent")
        type_row.pack(fill="x", padx=16, pady=4)
        for key, label in TYPE_LABELS.items():
            ctk.CTkRadioButton(
                type_row,
                text=label,
                variable=type_var,
                value=key,
                command=rebuild_fields,
                fg_color=theme.COLOR_ACCENT,
            ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(form, text="Название", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM).pack(
            anchor="w", padx=16, pady=(8, 0)
        )
        theme.styled_entry(form, textvariable=name_var, width=460).pack(padx=16)

        theme.ghost_button(path_row, "Обзор…", browse_exe, width=80).pack(side="left", padx=(0, 6))
        path_entry.pack(side="left")
        theme.ghost_button(folder_row, "Обзор…", browse_folder, width=80).pack(side="left", padx=(0, 6))
        folder_entry.pack(side="left")

        type_var.trace_add("write", rebuild_fields)
        rebuild_fields()

        ctk.CTkLabel(form, text="Триггеры (через запятую)", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM).pack(
            anchor="w", padx=16, pady=(8, 0)
        )
        theme.styled_entry(form, textvariable=triggers_var, width=460).pack(padx=16)
        ctk.CTkCheckBox(form, text="Включено", variable=enabled_var, fg_color=theme.COLOR_ACCENT).pack(
            anchor="w", padx=16, pady=10
        )
        err_lbl.pack(padx=16)

        def save() -> None:
            triggers = [t.strip() for t in triggers_var.get().split(",") if t.strip()]
            t = type_var.get()
            fields = {
                "display_name": name_var.get(),
                "action_type": t,
                "voice_triggers": triggers,
                "enabled": enabled_var.get(),
                "exe_path": path_var.get(),
                "url": url_var.get(),
                "folder_path": folder_var.get(),
                "working_dir": wd_var.get(),
                "args": args_var.get(),
            }
            if app:
                _, err = user_apps_store.update_app(app.id, **fields)
            else:
                _, err = user_apps_store.add_shortcut(
                    fields["display_name"],
                    t,
                    triggers,
                    exe_path=fields["exe_path"],
                    url=fields["url"],
                    folder_path=fields["folder_path"],
                    working_dir=fields["working_dir"],
                    args=fields["args"],
                )
            if err:
                err_lbl.configure(text=err)
                return
            dialog.destroy()
            self.refresh()

        theme.ghost_button(form, "Сохранить", save, accent=True).pack(pady=14)
