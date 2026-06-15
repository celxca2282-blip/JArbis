# theme.py
"""
Дизайн-система JArbis HUD — премиальный тёмный интерфейс (Luxify-уровень).
"""

import customtkinter as ctk

# ── Палитра ──────────────────────────────────────────────────────────
COLOR_BG = "#05080d"
COLOR_BG_ALT = "#0a0f16"
COLOR_BG_ELEVATED = "#0e141c"
COLOR_PANEL = "#101822"
COLOR_PANEL_GLASS = "#121c28"
COLOR_PANEL_HOVER = "#182230"
COLOR_BORDER = "#1a2838"
COLOR_BORDER_LIGHT = "#243448"
COLOR_ACCENT = "#00d4ff"
COLOR_ACCENT_DIM = "#0099b8"
COLOR_ACCENT_HOVER = "#4de4ff"
COLOR_SUCCESS = "#2ee6a0"
COLOR_ERROR = "#ff4d6d"
COLOR_WARNING = "#ffb020"
COLOR_PURPLE = "#9b8cff"
COLOR_TEXT = "#eef4fa"
COLOR_TEXT_SEC = "#b8c5d6"
COLOR_TEXT_DIM = "#5c7088"
COLOR_TEXT_MUTED = "#3d4f63"
COLOR_NAV_ACTIVE = "#0f1a28"
COLOR_TERMINAL_BG = "#060a10"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """RGB из #RRGGBB (CTk не понимает #RRGGBBAA)."""
    h = hex_color.lstrip("#")[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def blend_colors(fg: str, bg: str, alpha: float) -> str:
    """Имитация прозрачности — смешивание двух цветов."""
    fr, fg_g, fb = _hex_to_rgb(fg)
    br, bg_g, bb = _hex_to_rgb(bg)
    r = int(br * (1 - alpha) + fr * alpha)
    g = int(bg_g * (1 - alpha) + fg_g * alpha)
    b = int(bb * (1 - alpha) + fb * alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


def soft_tint(color: str, alpha: float = 0.14, bg: str | None = None) -> str:
    """Мягкий фон бейджа/подсветки на тёмном фоне."""
    return blend_colors(color, bg or COLOR_BG_ALT, alpha)


COLOR_BORDER_GLOW = blend_colors("#00c8e8", COLOR_BG_ALT, 0.22)
COLOR_ACCENT_SOFT = soft_tint(COLOR_ACCENT)
COLOR_WARNING_SOFT = soft_tint(COLOR_WARNING)
COLOR_SUCCESS_SOFT = soft_tint(COLOR_SUCCESS)
COLOR_ERROR_SOFT = soft_tint(COLOR_ERROR)

# ── Типографика ──────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_DISPLAY = (FONT_FAMILY, 28, "bold")
FONT_LOGO = (FONT_FAMILY, 22, "bold")
FONT_TITLE = (FONT_FAMILY, 20, "bold")
FONT_HEADING = (FONT_FAMILY, 15, "bold")
FONT_SUBHEAD = (FONT_FAMILY, 13, "bold")
FONT_BODY = (FONT_FAMILY, 13)
FONT_SMALL = (FONT_FAMILY, 11)
FONT_CAPTION = (FONT_FAMILY, 10)
FONT_NAV = (FONT_FAMILY, 13)
FONT_MONO = ("Consolas", 11)
FONT_MONO_SM = ("Consolas", 10)

# ── Размеры ──────────────────────────────────────────────────────────
SIDEBAR_WIDTH = 248
TOPBAR_HEIGHT = 56
WINDOW_MIN_WIDTH = 1180
WINDOW_MIN_HEIGHT = 740
CORNER_RADIUS = 12
CORNER_RADIUS_SM = 8
PADDING = 24
PADDING_SM = 16
BTN_HEIGHT = 38
BTN_HEIGHT_SM = 32
INPUT_HEIGHT = 40

# ── Орб ──────────────────────────────────────────────────────────────
ORB_COLORS = {
    "idle": "#1e3348",
    "wake": COLOR_WARNING,
    "listening": COLOR_ACCENT,
    "thinking": COLOR_PURPLE,
    "speaking": COLOR_SUCCESS,
    "error": COLOR_ERROR,
}

ORB_LABELS = {
    "idle": "Ожидание",
    "wake": "Активация",
    "listening": "Слушаю",
    "thinking": "Обработка",
    "speaking": "Ответ",
    "error": "Ошибка",
}

# Подпись плитки «Движок», когда ассистент запущен и ждёт wake-word
ENGINE_READY_LABEL = "Готов"

# icon — декоративный символ в навигации
NAV_ITEMS = (
    ("dashboard", "Обзор", "◉"),
    ("apps", "Ярлыки", "⬡"),
    ("scenarios", "Сценарии", "⤴"),
    ("settings", "Настройки", "⚙"),
    ("logs", "Логи", "☰"),
)

PAGE_TITLES = {
    "dashboard": ("Центр управления", "Статус ассистента в реальном времени"),
    "apps": ("Ярлыки", "Программы, ссылки и папки с голосовыми триггерами"),
    "scenarios": ("Сценарии", "Цепочки автоматизации и голосовые триггеры"),
    "settings": ("Настройки", "Голос, STT, LLM и системные параметры"),
    "logs": ("Логи", "Журнал событий data/jarvis.log"),
}


def apply_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


def panel_frame(parent, *, glass: bool = False, **kwargs) -> ctk.CTkFrame:
    """Карточка-панель с тонкой обводкой."""
    fg = COLOR_PANEL_GLASS if glass else COLOR_PANEL
    return ctk.CTkFrame(
        parent,
        fg_color=fg,
        border_color=COLOR_BORDER,
        border_width=1,
        corner_radius=CORNER_RADIUS,
        **kwargs,
    )


def accent_panel(parent, **kwargs) -> ctk.CTkFrame:
    """Панель с акцентной подсветкой."""
    return ctk.CTkFrame(
        parent,
        fg_color=COLOR_PANEL,
        border_color=COLOR_ACCENT_DIM,
        border_width=1,
        corner_radius=CORNER_RADIUS,
        **kwargs,
    )


def ghost_button(parent, text: str, command=None, accent: bool = False, danger: bool = False, **kwargs) -> ctk.CTkButton:
    """Плоская HUD-кнопка."""
    if accent:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=BTN_HEIGHT,
            corner_radius=CORNER_RADIUS_SM,
            fg_color=COLOR_ACCENT_DIM,
            hover_color=COLOR_ACCENT,
            text_color=COLOR_BG,
            font=FONT_SUBHEAD,
            **kwargs,
        )
    if danger:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=BTN_HEIGHT,
            corner_radius=CORNER_RADIUS_SM,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_ERROR,
            hover_color=COLOR_ERROR_SOFT,
            text_color=COLOR_ERROR,
            font=FONT_BODY,
            **kwargs,
        )
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        height=BTN_HEIGHT,
        corner_radius=CORNER_RADIUS_SM,
        fg_color="transparent",
        border_width=1,
        border_color=COLOR_BORDER_LIGHT,
        hover_color=COLOR_PANEL_HOVER,
        text_color=COLOR_TEXT_SEC,
        font=FONT_BODY,
        **kwargs,
    )


def icon_button(parent, text: str, command=None, **kwargs) -> ctk.CTkButton:
    """Компактная квадратная кнопка."""
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        width=40,
        height=40,
        corner_radius=CORNER_RADIUS_SM,
        fg_color=COLOR_BG_ELEVATED,
        hover_color=COLOR_PANEL_HOVER,
        border_width=1,
        border_color=COLOR_BORDER,
        text_color=COLOR_TEXT_SEC,
        font=FONT_BODY,
        **kwargs,
    )


def styled_entry(parent, placeholder: str = "", **kwargs) -> ctk.CTkEntry:
    """Поле ввода в стиле HUD."""
    from jarvis.gui.clipboard_utils import bind_entry_clipboard

    entry = ctk.CTkEntry(
        parent,
        placeholder_text=placeholder,
        height=INPUT_HEIGHT,
        corner_radius=CORNER_RADIUS_SM,
        fg_color=COLOR_BG_ELEVATED,
        border_color=COLOR_BORDER_LIGHT,
        border_width=1,
        text_color=COLOR_TEXT,
        placeholder_text_color=COLOR_TEXT_MUTED,
        font=FONT_BODY,
        **kwargs,
    )
    try:
        # after_idle — _entry уже создан; иначе бинды могут не сработать
        entry.after_idle(lambda e=entry: bind_entry_clipboard(e))
    except Exception:
        pass
    return entry


def styled_textbox(parent, **kwargs) -> ctk.CTkTextbox:
    """Терминальный лог-бокс."""
    return ctk.CTkTextbox(
        parent,
        font=FONT_MONO,
        fg_color=COLOR_TERMINAL_BG,
        border_color=COLOR_BORDER,
        border_width=1,
        corner_radius=CORNER_RADIUS_SM,
        text_color=COLOR_TEXT_DIM,
        **kwargs,
    )


def badge_label(parent, text: str, color: str = COLOR_ACCENT, **kwargs) -> ctk.CTkLabel:
    """Маленький цветной бейдж."""
    wrap = ctk.CTkFrame(parent, fg_color=soft_tint(color), corner_radius=6, **kwargs)
    lbl = ctk.CTkLabel(wrap, text=text, font=FONT_CAPTION, text_color=color)
    lbl.pack(padx=8, pady=3)
    return wrap


def section_header(parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
    """Заголовок секции страницы."""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(frame, text=title, font=FONT_TITLE, text_color=COLOR_TEXT, anchor="w").pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(
            frame, text=subtitle, font=FONT_SMALL, text_color=COLOR_TEXT_DIM, anchor="w"
        ).pack(anchor="w", pady=(2, 0))
    return frame


def divider(parent, vertical: bool = False) -> ctk.CTkFrame:
    """Тонкий разделитель."""
    if vertical:
        return ctk.CTkFrame(parent, width=1, fg_color=COLOR_BORDER)
    return ctk.CTkFrame(parent, height=1, fg_color=COLOR_BORDER)


def scroll_area(parent, **kwargs) -> ctk.CTkScrollableFrame:
    """Прокручиваемая область без лишнего фона (с поддержкой вложенных скроллов)."""
    from jarvis.gui.scroll_utils import SmartScrollableFrame

    return SmartScrollableFrame(parent, fg_color="transparent", **kwargs)
