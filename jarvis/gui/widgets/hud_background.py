# hud_background.py
"""Анимированный HUD-фон: сетка, сканлайн, угловые маркеры."""

import math
import tkinter as tk

from jarvis.gui import theme

_ANIM_MS = 50


class HudBackground(tk.Canvas):
    """Рисует премиальный фон за всем интерфейсом."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master,
            highlightthickness=0,
            bd=0,
            bg=theme.COLOR_BG,
            **kwargs,
        )
        self._phase = 0.0
        self._running = True
        self.bind("<Configure>", lambda _e: self._paint())
        self._tick()

    def destroy(self) -> None:
        self._running = False
        super().destroy()

    def _tick(self) -> None:
        if not self._running:
            return
        try:
            if self.winfo_exists():
                self._phase += 0.04
                self._paint()
                self.after(_ANIM_MS, self._tick)
        except Exception:
            self._running = False

    def _paint(self) -> None:
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        self.delete("all")

        # Радиальный vignette
        steps = 8
        for i in range(steps, 0, -1):
            t = i / steps
            gray = int(5 + t * 8)
            color = f"#{gray:02x}{gray+2:02x}{gray+4:02x}"
            pad = int((1 - t) * min(w, h) * 0.15)
            self.create_rectangle(pad, pad, w - pad, h - pad, outline=color, width=1)

        # Сетка
        grid = 48
        grid_color = "#142030"
        for x in range(0, w + grid, grid):
            self.create_line(x, 0, x, h, fill=grid_color, width=1)
        for y in range(0, h + grid, grid):
            self.create_line(0, y, w, y, fill=grid_color, width=1)

        # Горизонтальный сканлайн
        scan_y = int((math.sin(self._phase) * 0.5 + 0.5) * h)
        self.create_line(0, scan_y, w, scan_y, fill=theme.soft_tint(theme.COLOR_ACCENT, 0.09, theme.COLOR_BG), width=2)
        self.create_line(
            0, scan_y + 1, w, scan_y + 1, fill=theme.soft_tint(theme.COLOR_ACCENT, 0.04, theme.COLOR_BG), width=1
        )

        # Угловые HUD-маркеры
        corner = 28
        accent = theme.COLOR_ACCENT_DIM
        for cx, cy, dx, dy in (
            (12, 12, 1, 1),
            (w - 12, 12, -1, 1),
            (12, h - 12, 1, -1),
            (w - 12, h - 12, -1, -1),
        ):
            self.create_line(cx, cy, cx + dx * corner, cy, fill=accent, width=2)
            self.create_line(cx, cy, cx, cy + dy * corner, fill=accent, width=2)

        # Мягкое свечение слева (sidebar zone)
        self.create_rectangle(
            0, 0, theme.SIDEBAR_WIDTH, h, fill=theme.soft_tint(theme.COLOR_ACCENT, 0.03, theme.COLOR_BG), outline=""
        )
