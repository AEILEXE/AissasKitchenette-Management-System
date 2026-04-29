# app/ui/theme.py  — Warm Café Palette (mirrors config.THEME)
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Theme:
    BG           = "#F4EFEA"   # warm cream background
    CARD         = "#FFFFFF"   # white card
    PRIMARY      = "#8B5E3C"   # warm wood brown
    PRIMARY_DARK = "#7A5030"   # darker brown (hover)
    ACCENT       = "#C08A6B"   # warm terracotta
    TEXT         = "#2B2B2B"   # near-black text
    MUTED        = "#6A6A6A"   # neutral muted gray
    BORDER       = "#D9C5B2"   # soft warm border
    SUCCESS      = "#4A7C59"   # muted green
    DANGER       = "#B55B52"   # muted warm red
    INPUT_BG     = "#EDE4D8"   # warm beige input
    SIDEBAR      = "#8B5E3C"   # rich coffee brown sidebar


def apply_ttk_theme(root: tk.Tk) -> None:
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except Exception:
        pass

    s.configure(".", font=("Segoe UI", 10))
    s.configure("TFrame", background=Theme.BG)
    s.configure("TLabel", background=Theme.BG, foreground=Theme.TEXT)

    s.configure("Card.TFrame", background=Theme.CARD)
    s.configure("CardTitle.TLabel", background=Theme.CARD, foreground=Theme.TEXT,
                font=("Segoe UI", 12, "bold"))
    s.configure("Muted.TLabel", background=Theme.CARD, foreground=Theme.MUTED,
                font=("Segoe UI", 9))

    s.configure("Primary.TButton",
                background=Theme.PRIMARY, foreground="white",
                padding=(14, 10), borderwidth=0)
    s.map("Primary.TButton",
          background=[("active", Theme.PRIMARY_DARK)],
          foreground=[("active", "white")])

    s.configure("Danger.TButton",
                background=Theme.DANGER, foreground="white",
                padding=(14, 10), borderwidth=0)
    s.map("Danger.TButton",
          background=[("active", "#8E3A35")],
          foreground=[("active", "white")])

    s.configure("Ghost.TButton",
                background=Theme.CARD, foreground=Theme.TEXT,
                padding=(12, 9))
    s.map("Ghost.TButton",
          background=[("active", Theme.INPUT_BG)])

    s.configure("TEntry",
                fieldbackground=Theme.INPUT_BG,
                foreground=Theme.TEXT,
                bordercolor=Theme.BORDER,
                lightcolor=Theme.BORDER,
                darkcolor=Theme.BORDER)

    s.configure("Cart.Treeview",
                background=Theme.CARD,
                fieldbackground=Theme.CARD,
                foreground=Theme.TEXT,
                rowheight=26,
                bordercolor=Theme.BORDER)
    s.configure("Cart.Treeview.Heading",
                font=("Segoe UI", 9, "bold"))
