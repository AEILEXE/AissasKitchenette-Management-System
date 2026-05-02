"""
ui_styles.py — Centralized ttk style definitions for Aissa's Kitchenette
Theme: warm café / cozy restaurant aesthetic.
Soft beige backgrounds, warm wood browns, terra cotta accents.
"""
from __future__ import annotations

from tkinter import ttk
from app.config import THEME

_SB     = THEME["sidebar"]        # #8B5E3C  rich warm coffee brown
_BROWN  = THEME["primary"]        # #8B5E3C  warm wood brown
_TERRA  = THEME["accent"]         # #C08A6B  warm terracotta
_GREEN  = THEME["success"]        # #4A7C59
_BG     = THEME["bg"]             # #F4EFEA  warm cream
_PANEL  = THEME["panel"]          # #FFFFFF
_BEIGE  = THEME["beige"]          # #EDE4D8  warm input beige
_TEXT   = THEME["text"]           # #2B2B2B  near-black text
_MUTED  = THEME["muted"]          # #6A6A6A  neutral muted gray
_BORDER = THEME["border"]         # #D9C5B2  soft warm border


def apply_global_styles() -> None:
    """Apply the warm café ttk theme globally."""
    s = ttk.Style()
    try:
        s.theme_use("clam")   # clam allows full fg/bg override on all platforms
    except Exception:
        pass

    # ── Scrollbar ──────────────────────────────────────────────────────────
    s.configure("Vertical.TScrollbar",
                troughcolor=_BG, background=_BORDER,
                arrowcolor=_MUTED, borderwidth=0, relief="flat")
    s.configure("Horizontal.TScrollbar",
                troughcolor=_BG, background=_BORDER,
                arrowcolor=_MUTED, borderwidth=0, relief="flat")
    s.configure("Thick.Vertical.TScrollbar",
                troughcolor=_BG, background=_BORDER,
                arrowcolor=_MUTED, borderwidth=0, relief="flat",
                width=10)

    # ── Base Treeview ──────────────────────────────────────────────────────
    s.configure("Treeview",
                rowheight=34,
                font=("Segoe UI", 9),
                background=_PANEL,
                fieldbackground=_PANEL,
                foreground=_TEXT,
                borderwidth=0,
                relief="flat")
    s.configure("Treeview.Heading",
                font=("Segoe UI", 9, "bold"),
                background=_BEIGE,
                foreground=_TEXT,
                relief="flat",
                padding=(10, 8))
    # Use a darker brown for selected rows to guarantee white text is always
    # readable regardless of what tag foreground colour the row carries.
    s.map("Treeview",
          background=[("selected", "#5C3D2E"), ("!selected", _PANEL)],
          foreground=[("selected", "#FFFFFF"), ("!selected", _TEXT)])
    s.map("Treeview.Heading",
          background=[("active", _BORDER)],
          foreground=[("active", _TEXT)])

    # ── TButton — default uses warm brown ──────────────────────────────────
    s.configure("TButton",
                font=("Segoe UI", 9, "bold"),
                padding=(12, 8),
                relief="flat",
                background=_BROWN,
                foreground="#FFFFFF")
    s.map("TButton",
          background=[("active", THEME["primary_dark"])],
          foreground=[("active", "#FFFFFF")])

    s.configure("Primary.TButton",
                background=_BROWN, foreground="#FFFFFF")
    s.map("Primary.TButton",
          background=[("active", THEME["primary_dark"])],
          foreground=[("active", "#FFFFFF")])

    s.configure("Accent.TButton",
                background=_TERRA, foreground="#FFFFFF")
    s.map("Accent.TButton",
          background=[("active", THEME["accent_dark"])],
          foreground=[("active", "#FFFFFF")])

    s.configure("Success.TButton",
                background=_GREEN, foreground="#FFFFFF")
    s.map("Success.TButton",
          background=[("active", "#3A6347")],
          foreground=[("active", "#FFFFFF")])

    s.configure("Danger.TButton",
                background=THEME["danger"], foreground="#FFFFFF")
    s.map("Danger.TButton",
          background=[("active", "#8E3A35")],
          foreground=[("active", "#FFFFFF")])

    # ── TEntry ─────────────────────────────────────────────────────────────
    s.configure("TEntry",
                fieldbackground=_BEIGE,
                foreground=_TEXT,
                bordercolor=_BORDER,
                lightcolor=_BORDER,
                darkcolor=_BORDER,
                insertcolor=_TEXT,
                padding=(8, 6))

    # ── TCombobox ──────────────────────────────────────────────────────────
    s.configure("TCombobox",
                fieldbackground=_BEIGE,
                foreground=_TEXT,
                background=_PANEL,
                arrowcolor=_MUTED,
                bordercolor=_BORDER,
                padding=(6, 5))

    # ── TFrame ─────────────────────────────────────────────────────────────
    s.configure("Card.TFrame",
                background=_PANEL,
                relief="flat",
                borderwidth=1)

    # ── TLabel ─────────────────────────────────────────────────────────────
    s.configure("Muted.TLabel",
                background=_PANEL,
                foreground=_MUTED,
                font=("Segoe UI", 9))
    s.configure("Heading.TLabel",
                background=_PANEL,
                foreground=_TEXT,
                font=("Segoe UI", 12, "bold"))

    # ── TNotebook (tabs) ───────────────────────────────────────────────────
    s.configure("TNotebook",
                background=_BG, borderwidth=0)
    s.configure("TNotebook.Tab",
                background=_BORDER,
                foreground=_TEXT,
                font=("Segoe UI", 9),
                padding=(14, 6))
    s.map("TNotebook.Tab",
          background=[("selected", _PANEL)],
          foreground=[("selected", _BROWN)],
          expand=[("selected", [1, 1, 1, 0])])

    # ── Separator ──────────────────────────────────────────────────────────
    s.configure("TSeparator", background=_BORDER)
