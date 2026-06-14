# scenarios_page.py
"""Редактор сценариев — двухколоночный HUD."""

import customtkinter as ctk
from tkinter import filedialog, messagebox

import jarvis.commands.app_scanner as app_scanner
import jarvis.commands.command_registry as command_registry
from jarvis.commands import scenario_store, user_apps_store
from jarvis.core.assistant_engine import AssistantEngine
from jarvis.gui import theme


class ScenariosPage(ctk.CTkFrame):
    def __init__(self, master, engine: AssistantEngine, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.engine = engine
        self._selected_id: str | None = None
        self._steps: list[scenario_store.ScenarioStep] = []

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=theme.PADDING, pady=(8, theme.PADDING))

        # ── Левая колонка: список ──
        left = theme.panel_frame(body, width=260)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        left_hdr = ctk.CTkFrame(left, fg_color="transparent")
        left_hdr.pack(fill="x", padx=14, pady=(14, 8))
        ctk.CTkLabel(left_hdr, text="⤴", font=theme.FONT_BODY, text_color=theme.COLOR_ACCENT).pack(side="left")
        ctk.CTkLabel(left_hdr, text="СЦЕНАРИИ", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left", padx=(8, 0)
        )
        theme.ghost_button(left_hdr, "+", self._new, accent=True, width=36).pack(side="right")

        self.list_frame = theme.scroll_area(left)
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # ── Правая колонка: редактор ──
        right = theme.panel_frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.name_var = ctk.StringVar()
        self.desc_var = ctk.StringVar()
        self.triggers_var = ctk.StringVar()
        self.enabled_var = ctk.BooleanVar(value=True)
        self.stop_err_var = ctk.BooleanVar(value=False)

        form = ctk.CTkFrame(right, fg_color="transparent")
        form.pack(fill="x", padx=18, pady=(18, 12))
        form.columnconfigure(1, weight=1)

        fields = [
            ("Название", self.name_var),
            ("Описание", self.desc_var),
            ("Триггеры", self.triggers_var),
        ]
        for row_i, (lbl, var) in enumerate(fields):
            ctk.CTkLabel(form, text=lbl, font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM).grid(
                row=row_i, column=0, sticky="w", pady=5
            )
            theme.styled_entry(form, textvariable=var, width=420).grid(row=row_i, column=1, padx=(12, 0), pady=5, sticky="ew")

        flags = ctk.CTkFrame(form, fg_color="transparent")
        flags.grid(row=3, column=1, sticky="w", padx=(12, 0), pady=6)
        ctk.CTkCheckBox(flags, text="Включён", variable=self.enabled_var, fg_color=theme.COLOR_ACCENT).pack(
            side="left", padx=(0, 16)
        )
        ctk.CTkCheckBox(flags, text="Остановить при ошибке", variable=self.stop_err_var, fg_color=theme.COLOR_ACCENT).pack(
            side="left"
        )

        theme.divider(right).pack(fill="x", padx=18)

        steps_hdr = ctk.CTkFrame(right, fg_color="transparent")
        steps_hdr.pack(fill="x", padx=18, pady=(12, 6))
        ctk.CTkLabel(steps_hdr, text="ШАГИ", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(side="left")

        self.steps_scroll = theme.scroll_area(right, height=200)
        self.steps_scroll.pack(fill="both", expand=True, padx=14, pady=8)

        add_row = ctk.CTkFrame(right, fg_color="transparent")
        add_row.pack(fill="x", padx=18, pady=4)
        for label, cmd in [
            ("+ EXE", self._add_exe),
            ("+ URL", self._add_url),
            ("+ App", self._add_app_index),
            ("+ User App", self._add_user_app),
            ("+ Command", self._add_command),
            ("+ Пауза", self._add_delay),
        ]:
            theme.ghost_button(add_row, label, cmd, width=88).pack(side="left", padx=2, pady=4)

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(8, 12))
        theme.ghost_button(actions, "Сохранить (Ctrl+S)", self._save, accent=True, width=160).pack(side="left", padx=(0, 6))
        theme.ghost_button(actions, "Запустить", self._run, width=100).pack(side="left", padx=4)
        theme.ghost_button(actions, "Дублировать", self._duplicate, width=110).pack(side="left", padx=4)
        theme.ghost_button(actions, "Удалить", self._delete, danger=True, width=90).pack(side="left", padx=4)

        prog_row = ctk.CTkFrame(right, fg_color="transparent")
        prog_row.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkLabel(prog_row, text="Прогресс", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left", padx=(0, 10)
        )
        self.progress = ctk.CTkProgressBar(
            prog_row,
            width=400,
            height=8,
            fg_color=theme.COLOR_BG_ELEVATED,
            progress_color=theme.COLOR_ACCENT,
        )
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress.set(0)

        self.refresh()

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        scenario_store.ensure_scenarios_file()
        for scenario in scenario_store.load_scenarios():
            active = scenario.id == self._selected_id
            btn = ctk.CTkButton(
                self.list_frame,
                text=scenario.name,
                anchor="w",
                height=36,
                corner_radius=theme.CORNER_RADIUS_SM,
                fg_color=theme.COLOR_NAV_ACTIVE if active else "transparent",
                border_width=1 if active else 0,
                border_color=theme.COLOR_ACCENT_DIM if active else theme.COLOR_BORDER,
                hover_color=theme.COLOR_PANEL_HOVER,
                text_color=theme.COLOR_TEXT if active else theme.COLOR_TEXT_SEC,
                command=lambda s=scenario: self._select(s),
            )
            btn.pack(fill="x", pady=2)

    def _select(self, scenario: scenario_store.Scenario) -> None:
        self._selected_id = scenario.id
        self.name_var.set(scenario.name)
        self.desc_var.set(scenario.description)
        self.triggers_var.set(", ".join(scenario.voice_triggers))
        self.enabled_var.set(scenario.enabled)
        self.stop_err_var.set(scenario.stop_on_error)
        self._steps = list(scenario.steps)
        self._render_steps()
        self.refresh()

    def _new(self) -> None:
        self._selected_id = None
        self.name_var.set("Новый сценарий")
        self.desc_var.set("")
        self.triggers_var.set("")
        self._steps = []
        self._render_steps()
        self.refresh()

    def _render_steps(self) -> None:
        for child in self.steps_scroll.winfo_children():
            child.destroy()
        if not self._steps:
            ctk.CTkLabel(
                self.steps_scroll,
                text="Добавьте шаги сценария кнопками ниже",
                font=theme.FONT_SMALL,
                text_color=theme.COLOR_TEXT_DIM,
            ).pack(pady=20)
            return
        for index, step in enumerate(self._steps):
            row = ctk.CTkFrame(
                self.steps_scroll,
                fg_color=theme.COLOR_BG_ELEVATED,
                corner_radius=theme.CORNER_RADIUS_SM,
                border_width=1,
                border_color=theme.COLOR_BORDER,
            )
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(
                row,
                text=f"{index + 1:02d}",
                font=theme.FONT_CAPTION,
                text_color=theme.COLOR_ACCENT,
                width=28,
            ).pack(side="left", padx=(10, 4), pady=8)
            label = self._step_label(step)
            ctk.CTkLabel(row, text=label, font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_SEC).pack(
                side="left", fill="x", expand=True, padx=4, pady=8
            )
            theme.icon_button(row, "↑", lambda i=index: self._move(i, -1)).pack(side="right", padx=2, pady=4)
            theme.icon_button(row, "↓", lambda i=index: self._move(i, 1)).pack(side="right", padx=2, pady=4)
            theme.ghost_button(row, "✕", lambda i=index: self._remove(i), danger=True, width=36).pack(
                side="right", padx=(4, 8), pady=4
            )

    def _step_label(self, step: scenario_store.ScenarioStep) -> str:
        if step.type == "exe":
            return f"EXE: {step.path} (+{step.delay_sec}s)"
        if step.type == "url":
            return f"URL: {step.url}"
        if step.type == "app_index":
            return f"App: {step.query}"
        if step.type == "command":
            return f"Cmd: {step.command_id}"
        if step.type == "user_app":
            return f"UserApp: {step.user_app_id}"
        if step.type == "delay":
            return f"Пауза {step.delay_sec} сек"
        return step.type

    def _move(self, index: int, delta: int) -> None:
        new_index = index + delta
        if 0 <= new_index < len(self._steps):
            self._steps[index], self._steps[new_index] = self._steps[new_index], self._steps[index]
            self._render_steps()

    def _remove(self, index: int) -> None:
        self._steps.pop(index)
        self._render_steps()

    def _add_exe(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("EXE", "*.exe")])
        if path:
            self._steps.append(scenario_store.ScenarioStep(type="exe", path=path, delay_sec=1))
            self._render_steps()

    def _add_url(self) -> None:
        dialog = ctk.CTkInputDialog(text="URL:", title="Добавить URL")
        url = dialog.get_input()
        if url:
            self._steps.append(scenario_store.ScenarioStep(type="url", url=url, delay_sec=0))
            self._render_steps()

    def _add_app_index(self) -> None:
        entries = app_scanner.load_or_build_index()[:80]
        names = [e.display_name for e in entries]
        if not names:
            return
        picker = ctk.CTkInputDialog(text=f"Приложение (например {names[0]}):", title="App index")
        query = picker.get_input()
        if query:
            self._steps.append(scenario_store.ScenarioStep(type="app_index", query=query, delay_sec=0))
            self._render_steps()

    def _add_user_app(self) -> None:
        apps = user_apps_store.load_user_apps()
        if not apps:
            messagebox.showwarning("Нет ярлыков", "Добавьте ярлык на вкладке «Ярлыки»")
            return
        self._steps.append(scenario_store.ScenarioStep(type="user_app", user_app_id=apps[0].id, delay_sec=0))
        self._render_steps()

    def _add_command(self) -> None:
        ids = command_registry.get_allowed_command_ids()
        picker = ctk.CTkInputDialog(text=f"command_id (например {ids[0]}):", title="Системная команда")
        cmd = picker.get_input()
        if cmd:
            self._steps.append(scenario_store.ScenarioStep(type="command", command_id=cmd, delay_sec=0))
            self._render_steps()

    def _add_delay(self) -> None:
        picker = ctk.CTkInputDialog(text="Секунды:", title="Пауза")
        raw = picker.get_input()
        try:
            sec = float(raw or "1")
        except ValueError:
            sec = 1.0
        self._steps.append(scenario_store.ScenarioStep(type="delay", delay_sec=sec))
        self._render_steps()

    def _save(self) -> None:
        triggers = [t.strip() for t in self.triggers_var.get().split(",") if t.strip()]
        if self._selected_id:
            scenario_store.update_scenario(
                self._selected_id,
                name=self.name_var.get(),
                description=self.desc_var.get(),
                voice_triggers=triggers,
                enabled=self.enabled_var.get(),
                stop_on_error=self.stop_err_var.get(),
                steps=self._steps,
            )
        else:
            created, err = scenario_store.add_scenario(
                self.name_var.get(),
                triggers,
                self._steps,
                description=self.desc_var.get(),
                enabled=self.enabled_var.get(),
                stop_on_error=self.stop_err_var.get(),
            )
            if err:
                messagebox.showerror("Ошибка", err)
                return
            self._selected_id = created.id if created else None
        messagebox.showinfo("Сохранено", "Сценарий сохранён")
        self.refresh()

    def _run(self) -> None:
        if not self._selected_id:
            messagebox.showwarning("Сценарий", "Сначала сохраните сценарий")
            return
        self.progress.set(0.2)
        result = self.engine.run_scenario(self._selected_id)
        self.progress.set(1.0)
        messagebox.showinfo("Сценарий", result)

    def _duplicate(self) -> None:
        if not self._selected_id:
            return
        scenario_store.add_scenario(
            self.name_var.get() + " (копия)",
            [t.strip() for t in self.triggers_var.get().split(",") if t.strip()],
            list(self._steps),
            description=self.desc_var.get(),
        )
        self.refresh()

    def _delete(self) -> None:
        if self._selected_id and messagebox.askyesno("Удаление", "Удалить сценарий?"):
            scenario_store.delete_scenario(self._selected_id)
            self._new()
            self.refresh()
