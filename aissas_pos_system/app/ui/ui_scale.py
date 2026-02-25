"""
app/ui/ui_scale.py
──────────────────
Application-wide UI zoom manager (Part 1).

Usage:
    from app.ui import ui_scale

    ui_scale.get_scale()          → float  (current scale, 1.0 = 100%)
    ui_scale.scale_font(base)     → int    (scaled font size)
    ui_scale.s(value)             → int    (scaled pixel/padding value)
    ui_scale.zoom_in()            → bumps scale up by STEP
    ui_scale.zoom_out()           → bumps scale down by STEP
    ui_scale.zoom_reset()         → resets scale to 1.0
    ui_scale.add_listener(cb)     → cb() is called whenever scale changes
    ui_scale.remove_listener(cb)  → unregister a listener
"""
from __future__ import annotations

MIN_SCALE: float = 0.8
MAX_SCALE: float = 1.6
STEP: float = 0.1
DEFAULT_SCALE: float = 1.0

_scale: float = DEFAULT_SCALE
_listeners: list = []


def get_scale() -> float:
    """Return the current UI scale factor."""
    return _scale


def set_scale(v: float) -> None:
    """Set the scale (clamped to [MIN_SCALE, MAX_SCALE]) and notify listeners."""
    global _scale
    _scale = round(max(MIN_SCALE, min(MAX_SCALE, float(v))), 1)
    _notify()


def zoom_in() -> None:
    """Increase scale by one step (Ctrl + / Ctrl =)."""
    set_scale(_scale + STEP)


def zoom_out() -> None:
    """Decrease scale by one step (Ctrl -)."""
    set_scale(_scale - STEP)


def zoom_reset() -> None:
    """Reset scale to 1.0 (Ctrl 0)."""
    set_scale(DEFAULT_SCALE)


def scale_font(base_size: int) -> int:
    """Return base_size scaled by the current scale factor (minimum 7)."""
    return max(7, int(round(base_size * _scale)))


def s(value: int | float) -> int:
    """Return a pixel/padding value scaled by the current scale factor (minimum 0)."""
    return max(0, int(round(float(value) * _scale)))


def add_listener(cb) -> None:
    """Register a zero-argument callback invoked whenever scale changes."""
    if cb not in _listeners:
        _listeners.append(cb)


def remove_listener(cb) -> None:
    """Unregister a previously registered callback."""
    if cb in _listeners:
        _listeners.remove(cb)


def _notify() -> None:
    for cb in list(_listeners):
        try:
            cb()
        except Exception:
            pass
