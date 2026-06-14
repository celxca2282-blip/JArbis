# status_orb.py
"""
Анимированный статус-орб ассистента — пульс, волны, hex-кольцо, реакция на речь.
"""

import math

import customtkinter as ctk

from jarvis.gui import theme

_ANIM_MS = 33
_SIZE = 220
_CX = _CY = _SIZE // 2
_BASE_R = 52

_ANIM_PROFILE: dict[str, dict] = {
    "idle": {"speed": 0.045, "pulse": 0.07, "ripples": 0, "bars": False, "spin": False, "hex": False},
    "wake": {"speed": 0.14, "pulse": 0.18, "ripples": 2, "bars": False, "spin": False, "hex": True},
    "listening": {"speed": 0.11, "pulse": 0.16, "ripples": 4, "bars": True, "spin": False, "hex": True},
    "thinking": {"speed": 0.09, "pulse": 0.08, "ripples": 0, "bars": False, "spin": True, "hex": True},
    "speaking": {"speed": 0.13, "pulse": 0.14, "ripples": 3, "bars": True, "spin": False, "hex": True},
    "error": {"speed": 0.06, "pulse": 0.12, "ripples": 0, "bars": False, "spin": False, "hex": False},
}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _blend(hex_color: str, factor: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    if factor >= 0:
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
    else:
        k = 1.0 + factor
        r, g, b = int(r * k), int(g * k), int(b * k)
    return _rgb_to_hex(r, g, b)


def _hex_points(cx: float, cy: float, radius: float, rotation: float = 0.0) -> list[float]:
    """Вершины шестиугольника для HUD-кольца."""
    pts: list[float] = []
    for i in range(6):
        angle = rotation + i * math.pi / 3
        pts.extend([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
    return pts


class StatusOrb(ctk.CTkFrame):
    """Круглый индикатор с плавной анимацией по статусу."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._status = "idle"
        self._phase = 0.0
        self._voice_level = 0.0
        self._external_level = False
        self._animating = True

        self._canvas = ctk.CTkCanvas(
            self,
            width=_SIZE,
            height=_SIZE,
            bg=theme.COLOR_PANEL_GLASS,
            highlightthickness=0,
        )
        self._canvas.pack()

        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(pady=(8, 0))
        self._dot = ctk.CTkFrame(status_row, width=8, height=8, corner_radius=4, fg_color=theme.COLOR_TEXT_MUTED)
        self._dot.pack(side="left", padx=(0, 8))
        self._label = ctk.CTkLabel(
            status_row,
            text=theme.ORB_LABELS["idle"],
            font=theme.FONT_SUBHEAD,
            text_color=theme.COLOR_TEXT_DIM,
        )
        self._label.pack(side="left")

        self._tick()

    def set_status(self, status: str) -> None:
        new_status = status if status in theme.ORB_COLORS else "idle"
        if new_status != self._status:
            self._phase = 0.0
        self._status = new_status
        self._label.configure(text=theme.ORB_LABELS.get(self._status, self._status))
        accent = theme.ORB_COLORS.get(self._status, theme.COLOR_TEXT_DIM)
        self._label.configure(text_color=accent if self._status != "idle" else theme.COLOR_TEXT_DIM)
        self._dot.configure(fg_color=accent)

    def set_voice_level(self, level: float) -> None:
        self._voice_level = max(0.0, min(1.0, level))
        self._external_level = True

    def destroy(self) -> None:
        self._animating = False
        super().destroy()

    def _profile(self) -> dict:
        return _ANIM_PROFILE.get(self._status, _ANIM_PROFILE["idle"])

    def _tick(self) -> None:
        if not self._animating:
            return
        try:
            if not self.winfo_exists():
                return
            prof = self._profile()
            self._phase += prof["speed"]
            if not self._external_level:
                if self._status in ("listening", "speaking"):
                    self._voice_level = 0.2 + 0.45 * abs(math.sin(self._phase * 3.5))
                elif self._status == "wake":
                    self._voice_level = 0.15 + 0.2 * abs(math.sin(self._phase * 5))
                elif self._status == "idle":
                    self._voice_level = 0.0
            elif self._voice_level <= 0.0:
                self._external_level = False
            self._paint_orb()
            self.after(_ANIM_MS, self._tick)
        except Exception:
            self._animating = False

    def _paint_orb(self) -> None:
        canvas = self._canvas
        canvas.delete("all")

        color = theme.ORB_COLORS.get(self._status, theme.ORB_COLORS["idle"])
        prof = self._profile()
        pulse = math.sin(self._phase) * prof["pulse"]
        voice_boost = self._voice_level * 0.22
        inner_r = _BASE_R + pulse * 10 + voice_boost * 14

        # Тонкие орбитальные линии
        for orbit_i, orbit_r in enumerate((_BASE_R + 28, _BASE_R + 38)):
            rot = self._phase * (0.4 if orbit_i == 0 else -0.25)
            pts = _hex_points(_CX, _CY, orbit_r + pulse * 4, rot)
            canvas.create_polygon(
                *pts,
                outline=_blend(color, 0.08 + orbit_i * 0.05),
                fill="",
                width=1,
            )

        # Hex HUD-кольцо при активности
        if prof.get("hex"):
            hex_r = _BASE_R + 18 + pulse * 6 + voice_boost * 10
            hex_pts = _hex_points(_CX, _CY, hex_r, self._phase * 0.15)
            canvas.create_polygon(
                *hex_pts,
                outline=_blend(color, 0.25),
                fill="",
                width=2,
            )

        ripple_count = prof["ripples"]
        for i in range(ripple_count):
            offset = i * (2 * math.pi / max(ripple_count, 1))
            t = (math.sin(self._phase * 1.4 + offset) + 1) * 0.5
            ring_r = _BASE_R + 8 + t * 36 + voice_boost * 22
            width = max(1, int(2.5 * (1.0 - t) + 0.5))
            ring_color = _blend(color, 0.35 * (1.0 - t))
            canvas.create_oval(
                _CX - ring_r, _CY - ring_r, _CX + ring_r, _CY + ring_r,
                outline=ring_color, width=width,
            )

        glow_r = inner_r + 16 + pulse * 8
        for step, fade in enumerate((0.28, 0.14, 0.06, 0.02)):
            gr = glow_r + step * 6
            gc = _blend(color, fade)
            canvas.create_oval(
                _CX - gr, _CY - gr, _CX + gr, _CY + gr,
                outline=gc, width=1,
            )

        canvas.create_oval(
            _CX - _BASE_R - 6, _CY - _BASE_R - 6,
            _CX + _BASE_R + 6, _CY + _BASE_R + 6,
            fill=theme.COLOR_BG_ELEVATED, outline=_blend(color, 0.18), width=2,
        )

        core_dark = _blend(color, -0.35) if self._status != "idle" else color
        canvas.create_oval(
            _CX - inner_r, _CY - inner_r, _CX + inner_r, _CY + inner_r,
            fill=core_dark, outline="",
        )
        highlight_r = inner_r * (0.52 + 0.12 * math.sin(self._phase * 1.2))
        canvas.create_oval(
            _CX - highlight_r, _CY - highlight_r,
            _CX + highlight_r, _CY + highlight_r,
            fill=color, outline="",
        )

        if prof["spin"]:
            spin_r = _BASE_R + 20
            for i in range(4):
                start = (math.degrees(self._phase * 2.2) + i * 90) % 360
                canvas.create_arc(
                    _CX - spin_r, _CY - spin_r, _CX + spin_r, _CY + spin_r,
                    start=start, extent=55,
                    style="arc", outline=_blend(color, 0.15 + i * 0.1), width=2,
                )

        if prof["bars"]:
            bar_count = 9
            bar_spacing = 8
            total_w = (bar_count - 1) * bar_spacing
            start_x = _CX - total_w / 2
            base_y = _CY + _BASE_R + 22
            for i in range(bar_count):
                wave = abs(math.sin(self._phase * 2.8 + i * 0.85))
                voice = self._voice_level * (0.6 + 0.4 * abs(math.sin(i)))
                bar_h = 4 + wave * 20 + voice * 24 + pulse * 8
                bx = start_x + i * bar_spacing
                bar_color = _blend(color, 0.1 + wave * 0.25)
                canvas.create_rectangle(
                    bx - 2, base_y - bar_h, bx + 2, base_y,
                    fill=bar_color, outline="",
                )

        if self._status in ("wake", "listening"):
            dot_pulse = 3 + abs(math.sin(self._phase * 3)) * 2.5
            canvas.create_oval(
                _CX - dot_pulse, _CY - dot_pulse,
                _CX + dot_pulse, _CY + dot_pulse,
                fill="#ffffff", outline="",
            )
