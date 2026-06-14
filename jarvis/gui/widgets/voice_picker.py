# voice_picker.py
"""Интерактивный выбор голоса — карточки, фильтры, превью."""

from __future__ import annotations

import threading
from typing import Callable

import customtkinter as ctk
from tkinter import messagebox

import config
import jarvis.voice.tts_module as tts_module
from jarvis.gui import theme

# Теги фильтра для пресетов
FILTER_ALL = "all"
FILTER_OFFLINE = "offline"
FILTER_RU = "ru"
FILTER_EN = "en"

_FILTER_LABELS = {
    FILTER_ALL: "Все",
    FILTER_OFFLINE: "Офлайн",
    FILTER_RU: "RU",
    FILTER_EN: "EN",
}

_ENGINE_COLORS = {
    "piper": theme.COLOR_ACCENT,
    "silero": theme.COLOR_PURPLE,
    "edge": theme.COLOR_SUCCESS,
    "sapi": theme.COLOR_TEXT_DIM,
}

_ENGINE_BADGES = {
    "piper": "HD офлайн",
    "silero": "лёгкий",
    "edge": "онлайн",
    "sapi": "запасной",
}


def _preset_tags(settings: dict) -> set[str]:
    """Теги пресета для фильтрации карточек."""
    engine = (settings.get("TTS_ENGINE") or "silero").strip().lower()
    locale = (settings.get("EDGE_TTS_LOCALE") or "ru").strip().lower()
    tags = {FILTER_ALL}
    if engine == "piper" or engine == "silero":
        tags.add(FILTER_OFFLINE)
        tags.add(FILTER_RU)
    elif engine == "edge":
        if locale == "en" or str(settings.get("TTS_VOICE", "")).lower().startswith("en-"):
            tags.add(FILTER_EN)
        else:
            tags.add(FILTER_RU)
    elif engine == "sapi":
        tags.add(FILTER_RU)
    return tags


def _split_preset_label(label: str) -> tuple[str, str]:
    """Делит подпись пресета на короткий заголовок и описание."""
    text = label.strip()
    if "—" in text:
        left, right = text.split("—", 1)
        title = left.strip().lstrip("◆●○ ").strip()
        return title, right.strip()
    return text.lstrip("◆●○ ").strip(), ""


def _match_current_preset(vars_map: dict) -> str | None:
    """Находит пресет, совпадающий с текущими настройками."""
    for preset_id, _label, settings in tts_module.VOICE_PRESETS:
        ok = True
        for key, value in settings.items():
            if key not in vars_map:
                continue
            current = vars_map[key].get()
            if key == "SILERO_SPEED":
                try:
                    if abs(float(current) - float(value)) > 0.02:
                        ok = False
                        break
                except ValueError:
                    ok = False
                    break
            elif str(current).strip() != str(value).strip():
                ok = False
                break
        if ok:
            return preset_id
    return None


class VoiceCard(ctk.CTkFrame):
    """Кликабельная карточка голосового образа."""

    def __init__(
        self,
        master,
        preset_id: str,
        title: str,
        subtitle: str,
        engine: str,
        on_select: Callable[[str, bool], None],
        **kwargs,
    ) -> None:
        color = _ENGINE_COLORS.get(engine, theme.COLOR_ACCENT)
        super().__init__(
            master,
            fg_color=theme.COLOR_PANEL,
            border_color=theme.COLOR_BORDER,
            border_width=1,
            corner_radius=theme.CORNER_RADIUS_SM,
            **kwargs,
        )
        self.preset_id = preset_id
        self._on_select = on_select
        self._selected = False
        self._accent = color

        self._stripe = ctk.CTkFrame(self, width=4, fg_color=color, corner_radius=2)
        self._stripe.pack(side="left", fill="y")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(
            top,
            text=title,
            font=theme.FONT_SUBHEAD,
            text_color=theme.COLOR_TEXT,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        self._play_btn = ctk.CTkButton(
            top,
            text="▶",
            width=30,
            height=28,
            corner_radius=8,
            fg_color=theme.COLOR_BG_ELEVATED,
            hover_color=theme.COLOR_PANEL_HOVER,
            border_width=1,
            border_color=theme.COLOR_BORDER_LIGHT,
            text_color=theme.COLOR_ACCENT,
            font=theme.FONT_BODY,
            command=lambda: on_select(preset_id, True),
        )
        self._play_btn.pack(side="right")

        if subtitle:
            ctk.CTkLabel(
                body,
                text=subtitle,
                font=theme.FONT_SMALL,
                text_color=theme.COLOR_TEXT_DIM,
                anchor="w",
                wraplength=170,
                justify="left",
            ).pack(anchor="w", pady=(4, 6))

        theme.badge_label(body, _ENGINE_BADGES.get(engine, engine), color).pack(anchor="w")

        for widget in (self, body, top):
            widget.bind("<Button-1>", self._handle_click)
        self._play_btn.bind("<Button-1>", lambda e: "break")

    def _handle_click(self, _event=None) -> None:
        self._on_select(self.preset_id, True)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        if selected:
            self.configure(
                fg_color=theme.COLOR_NAV_ACTIVE,
                border_color=theme.COLOR_ACCENT_DIM,
                border_width=2,
            )
            self._stripe.configure(fg_color=theme.COLOR_ACCENT_HOVER)
        else:
            self.configure(
                fg_color=theme.COLOR_PANEL,
                border_color=theme.COLOR_BORDER,
                border_width=1,
            )
            self._stripe.configure(fg_color=self._accent)


class VoicePickerPanel(ctk.CTkFrame):
    """Панель выбора голоса с карточками и тонкой настройкой."""

    def __init__(self, master, vars_map: dict, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.vars = vars_map
        self._cards: dict[str, VoiceCard] = {}
        self._active_filter = FILTER_ALL
        self._selected_preset: str | None = None
        self._advanced_visible = False

        self._init_vars()
        self._build_ui()
        self._selected_preset = _match_current_preset(self.vars)
        self._rebuild_cards()
        self._update_hero()

    def _init_vars(self) -> None:
        """Создаёт переменные настроек TTS, если их ещё нет."""
        defaults = {
            "TTS_ENGINE": (config.TTS_ENGINE or "piper").strip().lower(),
            "PIPER_VOICE": config.PIPER_VOICE or "ru_RU-ruslan-medium",
            "SILERO_MODEL": config.SILERO_MODEL or "v4_ru",
            "SILERO_SPEAKER": config.SILERO_SPEAKER or "eugene",
            "SILERO_SPEED": str(config.SILERO_SPEED),
            "EDGE_TTS_LOCALE": (config.EDGE_TTS_LOCALE or "ru").strip().lower(),
            "TTS_VOICE": config.TTS_VOICE,
            "TTS_SAPI_VOICE": config.TTS_SAPI_VOICE or "",
        }
        for key, value in defaults.items():
            if key not in self.vars:
                self.vars[key] = ctk.StringVar(value=str(value))

    def _build_ui(self) -> None:
        panel = theme.accent_panel(self)
        panel.pack(fill="x")

        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(hdr, text="🔊", font=theme.FONT_BODY, text_color=theme.COLOR_ACCENT).pack(side="left")
        ctk.CTkLabel(hdr, text="ГОЛОСА ОЗВУЧКИ", font=theme.FONT_CAPTION, text_color=theme.COLOR_TEXT_DIM).pack(
            side="left", padx=(8, 0)
        )
        theme.divider(panel).pack(fill="x", padx=16, pady=(0, 8))

        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))

        # Текущий выбор — крупная карточка
        self._hero = theme.panel_frame(body, glass=True)
        self._hero.pack(fill="x", pady=(0, 12))

        hero_inner = ctk.CTkFrame(self._hero, fg_color="transparent")
        hero_inner.pack(fill="x", padx=16, pady=14)

        left = ctk.CTkFrame(hero_inner, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(left, text="Сейчас выбран", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM, anchor="w").pack(
            anchor="w"
        )
        self._hero_title = ctk.CTkLabel(left, text="—", font=theme.FONT_HEADING, text_color=theme.COLOR_TEXT, anchor="w")
        self._hero_title.pack(anchor="w", pady=(2, 0))
        self._hero_sub = ctk.CTkLabel(
            left, text="", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_SEC, anchor="w", wraplength=420, justify="left"
        )
        self._hero_sub.pack(anchor="w", pady=(4, 0))
        self._hero_badge_row = ctk.CTkFrame(left, fg_color="transparent")
        self._hero_badge_row.pack(anchor="w", pady=(8, 0))

        right = ctk.CTkFrame(hero_inner, fg_color="transparent")
        right.pack(side="right")
        theme.ghost_button(right, "▶  Прослушать", self.preview_current, accent=True, width=150).pack(pady=(0, 6))
        theme.ghost_button(right, "⬇  Скачать HD", self.download_piper, width=150).pack()

        # Фильтры
        filter_row = ctk.CTkFrame(body, fg_color="transparent")
        filter_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            filter_row, text="Показать:", font=theme.FONT_SMALL, text_color=theme.COLOR_TEXT_DIM
        ).pack(side="left", padx=(0, 10))
        self._filter_buttons: dict[str, ctk.CTkButton] = {}
        for key in (FILTER_ALL, FILTER_OFFLINE, FILTER_RU, FILTER_EN):
            btn = theme.ghost_button(
                filter_row,
                _FILTER_LABELS[key],
                command=lambda k=key: self._set_filter(k),
                width=72,
            )
            btn.pack(side="left", padx=(0, 6))
            self._filter_buttons[key] = btn
        self._sync_filter_styles()

        # Сетка карточек
        self._cards_host = ctk.CTkScrollableFrame(
            body,
            fg_color=theme.COLOR_BG_ALT,
            corner_radius=theme.CORNER_RADIUS_SM,
            height=300,
            border_width=1,
            border_color=theme.COLOR_BORDER,
        )
        self._cards_host.pack(fill="x", pady=(0, 10))
        self._cards_grid = ctk.CTkFrame(self._cards_host, fg_color="transparent")
        self._cards_grid.pack(fill="x", padx=8, pady=8)

        from jarvis.gui.scroll_utils import register_nested_scroll

        register_nested_scroll(self._cards_host)

        # Тонкая настройка (свёрнута по умолчанию)
        self._advanced_toggle = theme.ghost_button(
            body,
            "⚙  Тонкая настройка  ▼",
            self._toggle_advanced,
            width=200,
        )
        self._advanced_toggle.pack(anchor="w", pady=(0, 8))

        self._advanced = ctk.CTkFrame(body, fg_color="transparent")
        self._build_advanced(self._advanced)

        from jarvis.voice import piper_tts

        if piper_tts.model_on_disk():
            status = f"Piper HD готов · {piper_tts.voice_label(self.vars['PIPER_VOICE'].get())}"
        elif piper_tts.piper_available():
            status = "Нажмите «Скачать HD» (~60 МБ, мужской Руслан)"
        else:
            status = "Нужен: pip install piper-tts onnxruntime"
        self.lbl_status = ctk.CTkLabel(
            body,
            text=f"Клик по карточке — выбор и прослушивание. {status}",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_DIM,
            wraplength=700,
            justify="left",
        )
        self.lbl_status.pack(anchor="w")

    def _build_advanced(self, parent) -> None:
        """Ручные настройки — Piper / Edge / SAPI."""
        from jarvis.voice import piper_tts

        box = theme.panel_frame(parent, glass=True)
        box.pack(fill="x")

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        self._piper_ids = [vid for vid, _ in piper_tts.PIPER_VOICE_OPTIONS]
        self._piper_labels = [lbl for _, lbl in piper_tts.PIPER_VOICE_OPTIONS]
        self._piper_combo = self._add_advanced_row(
            inner, "Piper голос", self._piper_labels, self._on_piper_voice_picked
        )

        edge_locale_row = ctk.CTkFrame(inner, fg_color="transparent")
        edge_locale_row.pack(fill="x", pady=4)
        ctk.CTkLabel(
            edge_locale_row, text="Edge язык", width=140, anchor="w", font=theme.FONT_BODY, text_color=theme.COLOR_TEXT_SEC
        ).pack(side="left")
        self._edge_locale_combo = ctk.CTkComboBox(
            edge_locale_row,
            values=["Русские", "English", "Все"],
            width=200,
            height=theme.INPUT_HEIGHT,
            state="readonly",
            fg_color=theme.COLOR_BG_ELEVATED,
            border_color=theme.COLOR_BORDER_LIGHT,
            command=self._on_edge_locale_picked,
        )
        self._edge_locale_combo.pack(side="left", padx=(8, 0))
        self._sync_edge_locale_combo()

        self._edge_ids: list[str] = []
        self._edge_labels: list[str] = []
        self._reload_edge_list()
        self._add_advanced_row(inner, "Edge голос", self._edge_labels, self._on_edge_voice_picked, attr="_edge_combo")

        sapi_list = tts_module.list_sapi_voices()
        self._sapi_ids = [sid for sid, _ in sapi_list]
        self._sapi_labels = [lbl for _, lbl in sapi_list]
        if self.vars["TTS_SAPI_VOICE"].get() not in self._sapi_ids and self._sapi_ids:
            self.vars["TTS_SAPI_VOICE"].set(self._sapi_ids[0])
        self._add_advanced_row(inner, "SAPI голос", self._sapi_labels, self._on_sapi_voice_picked, attr="_sapi_combo")

        theme.ghost_button(inner, "↻ Обновить Edge-голоса", self.refresh_edge_voices, width=180).pack(anchor="w", pady=(8, 0))

        self._sync_piper_voice_combo()
        self._sync_edge_locale_combo()
        self._sync_edge_voice_combo()
        self._sync_sapi_voice_combo()

    def _add_advanced_row(
        self,
        parent,
        label: str,
        values: list[str],
        command: Callable[[str], None],
        attr: str | None = None,
    ) -> ctk.CTkComboBox:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(
            row, text=label, width=140, anchor="w", font=theme.FONT_BODY, text_color=theme.COLOR_TEXT_SEC
        ).pack(side="left")
        combo = ctk.CTkComboBox(
            row,
            values=values or ["—"],
            width=320,
            height=theme.INPUT_HEIGHT,
            state="readonly",
            fg_color=theme.COLOR_BG_ELEVATED,
            border_color=theme.COLOR_BORDER_LIGHT,
            command=command,
        )
        combo.pack(side="left", padx=(8, 0))
        if attr:
            setattr(self, attr, combo)
        return combo

    def _set_filter(self, key: str) -> None:
        self._active_filter = key
        self._sync_filter_styles()
        self._rebuild_cards()

    def _sync_filter_styles(self) -> None:
        for key, btn in self._filter_buttons.items():
            if key == self._active_filter:
                btn.configure(
                    fg_color=theme.COLOR_ACCENT_DIM,
                    hover_color=theme.COLOR_ACCENT,
                    text_color=theme.COLOR_BG,
                    border_width=0,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    hover_color=theme.COLOR_PANEL_HOVER,
                    text_color=theme.COLOR_TEXT_SEC,
                    border_width=1,
                    border_color=theme.COLOR_BORDER_LIGHT,
                )

    def _filtered_presets(self) -> list[tuple[str, str, dict]]:
        result = []
        for preset_id, label, settings in tts_module.VOICE_PRESETS:
            tags = _preset_tags(settings)
            if self._active_filter == FILTER_ALL or self._active_filter in tags:
                result.append((preset_id, label, settings))
        return result

    def _rebuild_cards(self) -> None:
        for child in self._cards_grid.winfo_children():
            child.destroy()
        self._cards.clear()

        presets = self._filtered_presets()
        columns = 3
        for col in range(columns):
            self._cards_grid.grid_columnconfigure(col, weight=1, uniform="voice")

        for index, (preset_id, label, settings) in enumerate(presets):
            title, subtitle = _split_preset_label(label)
            engine = (settings.get("TTS_ENGINE") or "silero").strip().lower()
            card = VoiceCard(
                self._cards_grid,
                preset_id=preset_id,
                title=title,
                subtitle=subtitle,
                engine=engine,
                on_select=self._on_card_select,
            )
            row, col = divmod(index, columns)
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            card.set_selected(preset_id == self._selected_preset)
            self._cards[preset_id] = card

        if not presets:
            ctk.CTkLabel(
                self._cards_grid,
                text="Нет голосов в этой категории",
                font=theme.FONT_BODY,
                text_color=theme.COLOR_TEXT_DIM,
            ).grid(row=0, column=0, columnspan=3, pady=30)

    def _on_card_select(self, preset_id: str, preview: bool) -> None:
        self.apply_preset(preset_id, preview=preview)

    def apply_preset(self, preset_id: str, preview: bool = False) -> None:
        preset = tts_module.get_voice_preset(preset_id)
        if not preset:
            return

        mapping = {
            "TTS_ENGINE": "TTS_ENGINE",
            "PIPER_VOICE": "PIPER_VOICE",
            "TTS_VOICE": "TTS_VOICE",
            "TTS_RATE": "TTS_RATE",
            "TTS_PITCH": "TTS_PITCH",
            "EDGE_TTS_LOCALE": "EDGE_TTS_LOCALE",
        }
        for key, var_key in mapping.items():
            if key not in preset or var_key not in self.vars:
                continue
            self.vars[var_key].set(str(preset[key]))

        self._selected_preset = preset_id
        for pid, card in self._cards.items():
            card.set_selected(pid == preset_id)

        self._reload_edge_list()
        self._sync_advanced_combos()
        self._update_hero()
        if preview:
            self.preview_current()

    def _update_hero(self) -> None:
        preset_id = self._selected_preset or _match_current_preset(self.vars)
        if preset_id:
            for pid, label, settings in tts_module.VOICE_PRESETS:
                if pid == preset_id:
                    title, subtitle = _split_preset_label(label)
                    engine = (settings.get("TTS_ENGINE") or "piper").strip().lower()
                    self._hero_title.configure(text=title)
                    self._hero_sub.configure(text=subtitle or "Готовый образ")
                    for child in self._hero_badge_row.winfo_children():
                        child.destroy()
                    theme.badge_label(
                        self._hero_badge_row, _ENGINE_BADGES.get(engine, engine), _ENGINE_COLORS.get(engine, theme.COLOR_ACCENT)
                    ).pack(side="left")
                    return

        engine = self.vars["TTS_ENGINE"].get()
        self._hero_title.configure(text="Своя настройка")
        self._hero_sub.configure(text="Параметры заданы вручную в тонкой настройке")
        for child in self._hero_badge_row.winfo_children():
            child.destroy()
        theme.badge_label(self._hero_badge_row, _ENGINE_BADGES.get(engine, engine), _ENGINE_COLORS.get(engine, theme.COLOR_ACCENT)).pack(
            side="left"
        )

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self._advanced.pack(fill="x", pady=(0, 8))
            self._advanced_toggle.configure(text="⚙  Тонкая настройка  ▲")
        else:
            self._advanced.pack_forget()
            self._advanced_toggle.configure(text="⚙  Тонкая настройка  ▼")

    def preview_current(self) -> None:
        threading.Thread(
            target=lambda: tts_module.preview_voice(
                engine=self.vars["TTS_ENGINE"].get(),
                edge_voice=self.vars["TTS_VOICE"].get(),
                sapi_voice=self.vars["TTS_SAPI_VOICE"].get(),
                piper_voice=self.vars["PIPER_VOICE"].get(),
                rate=self.vars.get("TTS_RATE", ctk.StringVar(value=config.TTS_RATE)).get(),
                pitch=self.vars.get("TTS_PITCH", ctk.StringVar(value=config.TTS_PITCH)).get(),
            ),
            daemon=True,
        ).start()

    def download_piper(self) -> None:
        threading.Thread(target=self._download_piper_worker, daemon=True).start()

    def _download_piper_worker(self) -> None:
        from jarvis.voice import piper_tts

        if not piper_tts.piper_available():
            self.after(
                0,
                lambda: messagebox.showerror("Piper HD", "Установите:\npip install piper-tts onnxruntime"),
            )
            return
        vid = self.vars["PIPER_VOICE"].get()
        ok = piper_tts.download_model(vid) and piper_tts.load_model(voice_id=vid)

        def done() -> None:
            if ok:
                self.lbl_status.configure(text=f"Piper HD готов · {piper_tts.voice_label(vid)}")
                messagebox.showinfo("Piper HD", "Мужской голос загружен. Нажмите «Прослушать».")
            else:
                messagebox.showerror("Piper HD", "Не удалось скачать. Проверьте интернет.")

        self.after(0, done)

    def refresh_edge_voices(self) -> None:
        locale = self.vars["EDGE_TTS_LOCALE"].get()
        edge_list = tts_module.list_edge_voices(locale=locale, refresh=True)
        self._edge_ids = [sid for sid, _ in edge_list]
        self._edge_labels = [lbl for _, lbl in edge_list]
        if hasattr(self, "_edge_combo"):
            self._edge_combo.configure(values=self._edge_labels or ["—"])
        self._sync_edge_voice_combo()
        messagebox.showinfo("Edge-TTS", f"Загружено голосов: {len(self._edge_ids)}")

    def _reload_edge_list(self) -> None:
        locale = self.vars["EDGE_TTS_LOCALE"].get()
        edge_list = tts_module.list_edge_voices(locale=locale)
        self._edge_ids = [sid for sid, _ in edge_list]
        self._edge_labels = [lbl for _, lbl in edge_list]
        if hasattr(self, "_edge_combo"):
            self._edge_combo.configure(values=self._edge_labels or ["—"])
        if self.vars["TTS_VOICE"].get() not in self._edge_ids and self._edge_ids:
            self.vars["TTS_VOICE"].set(self._edge_ids[0])

    def _sync_advanced_combos(self) -> None:
        self._sync_piper_voice_combo()
        self._sync_edge_locale_combo()
        self._sync_edge_voice_combo()
        self._sync_sapi_voice_combo()

    def _sync_piper_voice_combo(self) -> None:
        if not hasattr(self, "_piper_combo"):
            return
        current = self.vars["PIPER_VOICE"].get()
        try:
            idx = self._piper_ids.index(current)
            self._piper_combo.set(self._piper_labels[idx])
        except (ValueError, KeyError):
            if self._piper_labels:
                self._piper_combo.set(self._piper_labels[0])

    def _sync_edge_locale_combo(self) -> None:
        if not hasattr(self, "_edge_locale_combo"):
            return
        mapping = {"ru": "Русские", "en": "English", "all": "Все"}
        self._edge_locale_combo.set(mapping.get(self.vars["EDGE_TTS_LOCALE"].get(), "Русские"))

    def _sync_edge_voice_combo(self) -> None:
        if not hasattr(self, "_edge_combo"):
            return
        current = self.vars["TTS_VOICE"].get()
        try:
            idx = self._edge_ids.index(current)
            self._edge_combo.set(self._edge_labels[idx])
        except (ValueError, KeyError):
            if self._edge_labels:
                self._edge_combo.set(self._edge_labels[0])

    def _sync_sapi_voice_combo(self) -> None:
        if not hasattr(self, "_sapi_combo"):
            return
        current = self.vars["TTS_SAPI_VOICE"].get()
        try:
            idx = self._sapi_ids.index(current)
            self._sapi_combo.set(self._sapi_labels[idx])
        except (ValueError, KeyError):
            if self._sapi_labels:
                self._sapi_combo.set(self._sapi_labels[0])

    def _on_piper_voice_picked(self, label: str) -> None:
        try:
            idx = self._piper_labels.index(label)
            self.vars["PIPER_VOICE"].set(self._piper_ids[idx])
            self.vars["TTS_ENGINE"].set("piper")
            self._selected_preset = None
            self._update_hero()
        except ValueError:
            pass

    def _on_edge_locale_picked(self, label: str) -> None:
        mapping = {"Русские": "ru", "English": "en", "Все": "all"}
        self.vars["EDGE_TTS_LOCALE"].set(mapping.get(label, "ru"))
        self._reload_edge_list()
        self._sync_edge_voice_combo()
        self._selected_preset = None
        self._update_hero()

    def _on_edge_voice_picked(self, label: str) -> None:
        try:
            idx = self._edge_labels.index(label)
            self.vars["TTS_VOICE"].set(self._edge_ids[idx])
            self.vars["TTS_ENGINE"].set("edge")
            self._selected_preset = None
            self._update_hero()
        except ValueError:
            pass

    def _on_sapi_voice_picked(self, label: str) -> None:
        try:
            idx = self._sapi_labels.index(label)
            self.vars["TTS_SAPI_VOICE"].set(self._sapi_ids[idx])
            self.vars["TTS_ENGINE"].set("sapi")
            self._selected_preset = None
            self._update_hero()
        except ValueError:
            pass
