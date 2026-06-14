# conversation_bubble.py
"""Пузырьки диалога STT / ответ ассистента."""

import customtkinter as ctk

from jarvis.gui import theme


class ConversationBubble(ctk.CTkFrame):
    """Один блок реплики в стиле чата."""

    def __init__(self, master, role: str, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        is_user = role == "user"
        accent = theme.COLOR_TEXT_DIM if is_user else theme.COLOR_ACCENT
        bg = theme.COLOR_BG_ELEVATED if is_user else theme.COLOR_PANEL_GLASS
        border = theme.COLOR_BORDER if is_user else theme.COLOR_ACCENT_DIM

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        role_text = "ВЫ" if is_user else "ДЖАРВИС"
        ctk.CTkLabel(header, text=role_text, font=theme.FONT_CAPTION, text_color=accent).pack(side="left")

        self.body = ctk.CTkFrame(
            self,
            fg_color=bg,
            border_color=border,
            border_width=1,
            corner_radius=theme.CORNER_RADIUS_SM,
        )
        self.body.pack(fill="x")

        self.lbl = ctk.CTkLabel(
            self.body,
            text="—",
            font=theme.FONT_BODY,
            text_color=theme.COLOR_TEXT_SEC if is_user else theme.COLOR_TEXT,
            wraplength=520,
            justify="left",
            anchor="w",
        )
        self.lbl.pack(anchor="w", padx=16, pady=14)

    def set_text(self, text: str) -> None:
        self.lbl.configure(text=text or "—")
