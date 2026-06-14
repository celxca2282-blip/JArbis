# logs_page.py
"""Просмотр лога jarvis.log с автообновлением — терминальный стиль."""

import customtkinter as ctk
from tkinter import filedialog, messagebox

import config
from jarvis.gui import theme
from jarvis.gui.widgets.page_toolbar import PageToolbar

_AUTO_REFRESH_MS = 2000


class LogsPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._auto_refresh_job: str | None = None
        self._visible = False

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=theme.PADDING, pady=(8, theme.PADDING))

        toolbar = PageToolbar(wrap)
        toolbar.pack(fill="x", pady=(0, 12))
        self._lbl_info = ctk.CTkLabel(
            toolbar._left, text="jarvis.log", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM
        )
        self._lbl_info.pack(side="left")
        self._live_badge = theme.badge_label(toolbar._left, "LIVE", theme.COLOR_SUCCESS)
        self._live_badge.pack(side="left", padx=(12, 0))
        toolbar.add_right(theme.ghost_button(toolbar._right, "Экспорт", self._export, width=90))
        toolbar.add_right(theme.ghost_button(toolbar._right, "Обновить", self.refresh, accent=True, width=100))

        terminal = theme.panel_frame(wrap)
        terminal.pack(fill="both", expand=True)

        term_header = ctk.CTkFrame(terminal, fg_color=theme.COLOR_BG_ELEVATED, corner_radius=0, height=36)
        term_header.pack(fill="x")
        term_header.pack_propagate(False)
        ctk.CTkLabel(
            term_header, text="  ● ● ●", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_MUTED
        ).pack(side="left", padx=12)
        ctk.CTkLabel(
            term_header, text="tail -f data/jarvis.log", font=theme.FONT_MONO_SM, text_color=theme.COLOR_TEXT_DIM
        ).pack(side="left", padx=8)

        self.text = theme.styled_textbox(terminal)
        self.text.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        self.refresh()

    def on_show(self) -> None:
        self._visible = True
        self.refresh()
        self._schedule_auto_refresh()

    def on_hide(self) -> None:
        self._visible = False
        if self._auto_refresh_job is not None:
            try:
                self.after_cancel(self._auto_refresh_job)
            except Exception:
                pass
            self._auto_refresh_job = None

    def _schedule_auto_refresh(self) -> None:
        if not self._visible:
            return
        self._auto_refresh_job = self.after(_AUTO_REFRESH_MS, self._auto_refresh_tick)

    def _auto_refresh_tick(self) -> None:
        if not self._visible:
            return
        try:
            self.refresh()
        finally:
            self._schedule_auto_refresh()

    def refresh(self) -> None:
        try:
            if config.LOG_FILE_PATH.is_file():
                content = config.LOG_FILE_PATH.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()[-500:]
                self.text.delete("1.0", "end")
                for line in lines:
                    color_tag = self._line_color(line)
                    self.text.insert("end", line + "\n")
                self._lbl_info.configure(text=f"{config.LOG_FILE_PATH.name} · {len(lines)} строк")
                self.text.see("end")
            else:
                self.text.delete("1.0", "end")
                self.text.insert("end", "# Файл лога пока не создан.\n# Запустите ассистент для записи событий.\n")
                self._lbl_info.configure(text="лог не найден")
        except Exception as e:
            self.text.delete("1.0", "end")
            self.text.insert("end", f"# Ошибка чтения лога: {e}\n")

    @staticmethod
    def _line_color(line: str) -> str:
        low = line.lower()
        if "error" in low or "ошибка" in low:
            return theme.COLOR_ERROR
        if "warn" in low or "warning" in low:
            return theme.COLOR_WARNING
        return theme.COLOR_TEXT_DIM

    def _export(self) -> None:
        try:
            path = filedialog.asksaveasfilename(defaultextension=".log", filetypes=[("Log", "*.log")])
            if path and config.LOG_FILE_PATH.is_file():
                path_obj = __import__("pathlib").Path(path)
                path_obj.write_text(
                    config.LOG_FILE_PATH.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
                )
                messagebox.showinfo("Экспорт", f"Сохранено: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
