# settings_page.py
"""Настройки ассистента — HUD-панели."""

import customtkinter as ctk
from tkinter import messagebox

import config
import jarvis.commands.app_scanner as app_scanner
import jarvis.commands.user_apps_store as user_apps_store
import jarvis.voice.stt_module as stt_module
from jarvis.core.assistant_engine import AssistantEngine
from jarvis.core.performance_profiles import MODE_FAST, MODE_HARD
from jarvis.gui import theme
from jarvis.gui.widgets.mode_picker import ModePickerPanel
from jarvis.gui.widgets.personality_picker import PersonalityPickerPanel
from jarvis.gui.widgets.setting_group import SettingGroup


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, engine: AssistantEngine, on_settings_saved=None, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.engine = engine
        self.on_settings_saved = on_settings_saved

        scroll = theme.scroll_area(self)
        scroll.pack(fill="both", expand=True, padx=theme.PADDING, pady=(8, theme.PADDING))

        self.vars: dict[str, ctk.Variable] = {}
        config.load_gui_settings()

        self._add_group(scroll, "Голос", "🎤", [
            ("WAKE_WORD_NAME", "Wake-word", config.WAKE_WORD_NAME),
            ("WAKE_WORD_ENGINE", "Движок wake-word", config.WAKE_WORD_ENGINE),
            ("TTS_RATE", "TTS скорость", config.TTS_RATE),
            ("TTS_PITCH", "TTS pitch", config.TTS_PITCH),
        ])
        self._add_tts_voice_panel(scroll)
        self._add_group(scroll, "STT", "🎙", [
            ("STT_MODEL_NAME", "Модель Whisper", config.STT_MODEL_NAME),
            ("STT_FORCE_CPU", "Force CPU", config.STT_FORCE_CPU, "bool"),
            ("STT_INPUT_DEVICE", "Микрофон", config.STT_INPUT_DEVICE or "", "mic"),
            ("STT_POST_ACTIVATION_DELAY_SEC", "Пауза после бипа", str(config.STT_POST_ACTIVATION_DELAY_SEC)),
        ])
        self._add_group(scroll, "LLM", "🧠", [
            ("MODEL_NAME", "Модель", config.MODEL_NAME),
            ("OPENAI_API_KEY", "API key", config.API_KEY, "password"),
        ])

        gui_data = config.read_gui_settings_dict()
        self.personality_picker = PersonalityPickerPanel(
            scroll,
            initial_mode=config.PERSONALITY_MODE,
            initial_consent=bool(gui_data.get("shard_hard_consent", config.SHARD_HARD_CONSENT)),
        )
        self.personality_picker.pack(fill="x")

        self.mode_picker = ModePickerPanel(scroll, initial_mode=config.PERFORMANCE_MODE)
        self.mode_picker.pack(fill="x")

        self._add_group(scroll, "Общее", "⚙", [
            ("auto_start_assistant", "Автозапуск ассистента", True, "bool"),
            ("minimize_to_tray", "Сворачивать в трей", True, "bool"),
        ])

        apps_panel = theme.panel_frame(scroll)
        apps_panel.pack(fill="x", pady=10)
        hdr = ctk.CTkFrame(apps_panel, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(hdr, text="📦", font=theme.FONT_BODY).pack(side="left")
        ctk.CTkLabel(hdr, text="ИНДЕКС ПРИЛОЖЕНИЙ", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left", padx=(8, 0)
        )
        self.lbl_index_count = ctk.CTkLabel(apps_panel, text="Записей: …", font=theme.FONT_BODY, text_color=theme.COLOR_TEXT_SEC)
        self.lbl_index_count.pack(anchor="w", padx=16)
        index_btns = ctk.CTkFrame(apps_panel, fg_color="transparent")
        index_btns.pack(anchor="w", padx=16, pady=(10, 16))
        theme.ghost_button(index_btns, "Пересканировать", self._rescan, accent=True, width=150).pack(side="left", padx=(0, 8))
        theme.ghost_button(index_btns, "Удалить индекс", self._delete_index, danger=True, width=150).pack(side="left")

        shortcuts_panel = theme.panel_frame(scroll)
        shortcuts_panel.pack(fill="x", pady=10)
        hdr2 = ctk.CTkFrame(shortcuts_panel, fg_color="transparent")
        hdr2.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(hdr2, text="⬡", font=theme.FONT_BODY).pack(side="left")
        ctk.CTkLabel(hdr2, text="РУЧНЫЕ ЯРЛЫКИ", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left", padx=(8, 0)
        )
        self.lbl_manual_count = ctk.CTkLabel(
            shortcuts_panel, text="Ручных: …", font=theme.FONT_BODY, text_color=theme.COLOR_TEXT_SEC
        )
        self.lbl_manual_count.pack(anchor="w", padx=16)
        ctk.CTkLabel(
            shortcuts_panel,
            text="Удаляются только ярлыки, добавленные вручную. Скан игр — на вкладке «Ярлыки».",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_DIM,
            wraplength=620,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        theme.ghost_button(
            shortcuts_panel,
            "Удалить все ручные ярлыки",
            self._delete_manual_shortcuts,
            danger=True,
            width=220,
        ).pack(anchor="w", padx=16, pady=(0, 16))

        row = ctk.CTkFrame(scroll, fg_color="transparent")
        row.pack(fill="x", pady=16)
        theme.ghost_button(row, "Сохранить", self._save, accent=True, width=140).pack(side="left", padx=(0, 8))
        theme.ghost_button(row, "Сбросить по умолчанию", self._reset, width=180).pack(side="left")

        self._update_index_count()
        self._update_manual_count()

    @staticmethod
    def _triple_ok(title: str, message: str) -> bool:
        for step in range(1, 4):
            if not messagebox.askokcancel(title, f"{message}\n\nПодтверждение {step} из 3"):
                return False
        return True

    def _add_tts_voice_panel(self, parent) -> None:
        """Интерактивный выбор голоса — карточки, фильтры, превью."""
        from jarvis.gui.widgets.voice_picker import VoicePickerPanel

        self.voice_picker = VoicePickerPanel(parent, self.vars)
        self.voice_picker.pack(fill="x", pady=8)

    def _add_group(self, parent, title: str, icon: str, fields: list) -> None:
        panel = SettingGroup(parent, title, icon=icon)
        panel.pack(fill="x", pady=8)
        for item in fields:
            key, label = item[0], item[1]
            default = item[2] if len(item) > 2 else ""
            kind = item[3] if len(item) > 3 else "str"
            if kind == "bool":
                var = ctk.BooleanVar(value=bool(default))
                widget = ctk.CTkCheckBox(panel._body, text="", variable=var, fg_color=theme.COLOR_ACCENT)
            elif kind == "mic":
                devices = stt_module.list_input_devices()
                self._mic_values = [value for value, _label in devices]
                self._mic_labels = [label for _value, label in devices]
                current = str(default or "")
                if current not in self._mic_values:
                    current = ""
                var = ctk.StringVar(value=current)
                widget = ctk.CTkComboBox(
                    panel._body,
                    values=self._mic_labels,
                    width=340,
                    height=theme.INPUT_HEIGHT,
                    state="readonly",
                    fg_color=theme.COLOR_BG_ELEVATED,
                    border_color=theme.COLOR_BORDER_LIGHT,
                    command=lambda lbl, v=var: self._on_mic_selected(lbl, v),
                )
                self._mic_combo = widget
                self._mic_var = var
                self._sync_mic_combo_display()
            else:
                show = "*" if kind == "password" else None
                var = ctk.StringVar(value=str(default))
                widget = theme.styled_entry(panel._body, textvariable=var, width=340, show=show)
            self.vars[key] = var
            panel.add_row(label, widget)

    def _sync_mic_combo_display(self) -> None:
        if not hasattr(self, "_mic_combo"):
            return
        current = self._mic_var.get()
        try:
            index = self._mic_values.index(current)
            self._mic_combo.set(self._mic_labels[index])
        except ValueError:
            self._mic_combo.set(self._mic_labels[0] if self._mic_labels else "По умолчанию")

    def _on_mic_selected(self, label: str, var: ctk.StringVar) -> None:
        try:
            index = self._mic_labels.index(label)
            var.set(self._mic_values[index])
        except ValueError:
            var.set("")

    def _rescan(self) -> None:
        try:
            entries = app_scanner.load_or_build_index(force_rescan=True)
            if hasattr(self.engine, "reload_app_index"):
                self.engine.reload_app_index(force_rescan=True)
            self.lbl_index_count.configure(text=f"Записей: {len(entries)}")
            messagebox.showinfo("Индекс", f"Пересканировано: {len(entries)} приложений")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _delete_index(self) -> None:
        if not messagebox.askyesno(
            "Удаление индекса",
            "Удалить файл индекса приложений?\n"
            "Джарвис перестанет знать установленные программы до пересканирования.",
        ):
            return
        ok, msg = app_scanner.delete_app_index()
        if ok:
            if hasattr(self.engine, "reload_app_index"):
                self.engine.reload_app_index(delete=True)
            self.lbl_index_count.configure(text="Записей: 0 (удалён)")
            messagebox.showinfo("Индекс", msg)
        else:
            messagebox.showwarning("Индекс", msg)

    def _delete_manual_shortcuts(self) -> None:
        count = user_apps_store.count_manual_apps()
        if count == 0:
            messagebox.showinfo("Ярлыки", "Нет ручных ярлыков для удаления.")
            return
        if not self._triple_ok(
            "Удаление ярлыков",
            f"Будут удалены все ручные ярлыки ({count} шт.):\n"
            "программы, ссылки и папки, добавленные вручную.\n"
            "Ярлыки из скана игр не затронуты.",
        ):
            return
        removed, msg = user_apps_store.delete_manual_apps()
        self._update_manual_count()
        messagebox.showinfo("Ярлыки", msg if removed else "Ничего не удалено")

    def _update_manual_count(self) -> None:
        try:
            manual = user_apps_store.count_manual_apps()
            scanned = user_apps_store.count_scanned_apps()
            self.lbl_manual_count.configure(text=f"Ручных: {manual} · из скана: {scanned}")
        except Exception:
            self.lbl_manual_count.configure(text="Ручных: —")

    def _update_index_count(self) -> None:
        try:
            count = app_scanner.get_cached_index_count()
            if count == 0 and not config.APP_INDEX_PATH.is_file():
                self.lbl_index_count.configure(text="Записей: 0 (нет файла)")
            else:
                self.lbl_index_count.configure(text=f"Записей: {count}")
        except Exception:
            self.lbl_index_count.configure(text="Записей: —")

    def _save(self) -> None:
        before = {
            "performance_mode": config.PERFORMANCE_MODE,
            "personality_mode": config.PERSONALITY_MODE,
            "stt_model": config.STT_MODEL_NAME,
            "stt_force_cpu": config.STT_FORCE_CPU,
            "stt_input": config.STT_INPUT_DEVICE or "",
            "stt_delay": str(config.STT_POST_ACTIVATION_DELAY_SEC),
            "wake_word": config.WAKE_WORD_NAME,
            "wake_engine": config.WAKE_WORD_ENGINE,
            "tts_engine": config.TTS_ENGINE,
            "piper_voice": getattr(config, "PIPER_VOICE", ""),
            "edge_voice": config.TTS_VOICE,
            "sapi_voice": getattr(config, "TTS_SAPI_VOICE", ""),
            "model_name": config.MODEL_NAME,
            "api_key": config.API_KEY,
        }
        payload = {}
        for key, var in self.vars.items():
            if isinstance(var, ctk.BooleanVar):
                payload[key] = var.get()
            else:
                payload[key] = var.get()

        new_mode = self.mode_picker.get_mode()
        old_mode = config.PERFORMANCE_MODE
        payload["performance_mode"] = new_mode
        payload.pop("fast_mode", None)

        payload["personality_mode"] = self.personality_picker.get_mode()
        payload["shard_hard_consent"] = self.personality_picker.get_shard_hard_consent()

        if new_mode == MODE_FAST and old_mode != MODE_FAST:
            if not messagebox.askokcancel(
                "⚡ Быстрый режим",
                "Whisper small, Piper HD офлайн, без LLM.\n"
                "Только локальные команды и открытие приложений.\n\n"
                "Whisper перезагрузится (~5–15 сек). Продолжить?",
            ):
                self.mode_picker.set_mode(old_mode)
                payload["performance_mode"] = old_mode

        elif new_mode == MODE_HARD and old_mode != MODE_HARD:
            if not messagebox.askokcancel(
                "🔥 Хард режим",
                "Максимальная точность STT: medium+, повтор при «не расслышал», "
                "дольше слушает микрофон.\n"
                "Может быть медленнее на CPU. LLM и все функции включены.\n\n"
                "Whisper перезагрузится (~5–30 сек). Продолжить?",
            ):
                self.mode_picker.set_mode(old_mode)
                payload["performance_mode"] = old_mode

        config.save_gui_settings(payload, write_env=False)
        config.load_gui_settings()
        reload_stt = (
            config.STT_MODEL_NAME != before["stt_model"]
            or bool(config.STT_FORCE_CPU) != bool(before["stt_force_cpu"])
            or (config.STT_INPUT_DEVICE or "") != before["stt_input"]
            or str(config.STT_POST_ACTIVATION_DELAY_SEC) != before["stt_delay"]
            or config.PERFORMANCE_MODE != before["performance_mode"]
        )
        reload_tts = (
            config.TTS_ENGINE != before["tts_engine"]
            or getattr(config, "PIPER_VOICE", "") != before["piper_voice"]
            or config.TTS_VOICE != before["edge_voice"]
            or getattr(config, "TTS_SAPI_VOICE", "") != before["sapi_voice"]
            or config.WAKE_WORD_NAME != before["wake_word"]
            or config.WAKE_WORD_ENGINE != before["wake_engine"]
        )
        reload_runtime = (
            reload_stt
            or reload_tts
            or config.PERSONALITY_MODE != before["personality_mode"]
            or config.MODEL_NAME != before["model_name"]
            or config.API_KEY != before["api_key"]
        )
        if reload_runtime:
            self.engine.reload_config(reload_stt=reload_stt, reload_tts=reload_tts)
        if self.on_settings_saved:
            self.on_settings_saved(payload)
        messagebox.showinfo("Настройки", "Сохранено")

    def _reset(self) -> None:
        if messagebox.askyesno("Сброс", "Сбросить GUI-настройки?"):
            if config.GUI_SETTINGS_PATH.exists():
                config.GUI_SETTINGS_PATH.unlink()
            config.load_gui_settings()
            messagebox.showinfo("Сброс", "Настройки сброшены. Перезапустите вкладку.")

    def refresh(self) -> None:
        self._update_index_count()
        self._update_manual_count()

    def get_bool_setting(self, key: str) -> bool:
        var = self.vars.get(key)
        return bool(var.get()) if isinstance(var, ctk.BooleanVar) else False
