# shortcut_tile.py
"""Карточка ярлыка для страницы Apps."""

import customtkinter as ctk

from jarvis.commands import user_apps_store
from jarvis.gui import theme

_TYPE_ICONS = {
    user_apps_store.ACTION_EXE: "▶",
    user_apps_store.ACTION_URL: "🔗",
    user_apps_store.ACTION_FOLDER: "📁",
}

_TYPE_COLORS = {
    user_apps_store.ACTION_EXE: theme.COLOR_ACCENT,
    user_apps_store.ACTION_URL: theme.COLOR_PURPLE,
    user_apps_store.ACTION_FOLDER: theme.COLOR_WARNING,
}


class ShortcutTile(ctk.CTkFrame):
    """Премиальная плитка ярлыка с действиями."""

    def __init__(
        self,
        master,
        app: user_apps_store.UserApp,
        type_label: str,
        on_launch,
        on_voice,
        on_edit,
        on_delete,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=theme.COLOR_PANEL,
            border_color=theme.COLOR_BORDER,
            border_width=1,
            corner_radius=theme.CORNER_RADIUS,
            **kwargs,
        )
        accent = _TYPE_COLORS.get(app.action_type, theme.COLOR_ACCENT)
        icon = _TYPE_ICONS.get(app.action_type, "⬡")

        # Левая акцентная полоска
        stripe = ctk.CTkFrame(self, width=4, fg_color=accent if app.enabled else theme.COLOR_TEXT_MUTED, corner_radius=2)
        stripe.pack(side="left", fill="y", padx=(0, 0), pady=0)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")

        title_row = ctk.CTkFrame(top, fg_color="transparent")
        title_row.pack(side="left", fill="x", expand=True)
        status_dot = "●" if app.enabled else "○"
        ctk.CTkLabel(
            title_row,
            text=f"{icon}  {status_dot} {app.display_name}",
            font=theme.FONT_HEADING,
            text_color=theme.COLOR_TEXT if app.enabled else theme.COLOR_TEXT_DIM,
            anchor="w",
        ).pack(anchor="w")

        badge_text = type_label
        if app.source == "game_scan":
            badge_text += " · SCAN"
        theme.badge_label(top, badge_text, accent).pack(side="right")

        ctk.CTkLabel(
            body,
            text=app.target_label(),
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_DIM,
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(6, 0))

        triggers = ", ".join(app.voice_triggers) or "—"
        trigger_frame = ctk.CTkFrame(body, fg_color=theme.COLOR_BG_ELEVATED, corner_radius=6)
        trigger_frame.pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(
            trigger_frame,
            text=f"🎤  «{triggers}»",
            font=theme.FONT_SMALL,
            text_color=theme.COLOR_TEXT_SEC,
        ).pack(padx=10, pady=5)

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(anchor="e", pady=(10, 0))
        theme.ghost_button(actions, "Открыть", lambda: on_launch(app), width=78).pack(side="left", padx=2)
        theme.ghost_button(actions, "Голос", lambda: on_voice(app), width=68).pack(side="left", padx=2)
        theme.ghost_button(actions, "Изменить", lambda: on_edit(app), width=78).pack(side="left", padx=2)
        theme.ghost_button(actions, "✕", lambda: on_delete(app), danger=True, width=44).pack(side="left", padx=2)
