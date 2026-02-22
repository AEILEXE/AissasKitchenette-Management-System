# app/ui/theme.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Theme:
    # ===== ALISSA'S PALETTE (SYSTEM-WIDE) =====
    BG = "#F5EFE6"              # beige background
    CARD = "#FFFFFF"            # white card
    PRIMARY = "#8B5E3C"         # brown
    PRIMARY_DARK = "#6F472D"    # darker brown
    ACCENT = "#C8A27C"          # light brown accent
    TEXT = "#3E2C23"            # dark brown text
    MUTED = "#9E8B7A"           # muted text
    BORDER = "#E0D6C8"          # soft border
    SUCCESS = "#5A8F5A"         # muted green
    DANGER = "#B0413E"          # muted red
    INPUT_BG = "#EFE6DD"        # input beige


def apply_ttk_theme(root: tk.Tk) -> None:
    """
    Applies a consistent ttk theme so default widgets don't go blue.
    """
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except Exception:
        pass

    # General
    s.configure(".", font=("Segoe UI", 10))
    s.configure("TFrame", background=Theme.BG)
    s.configure("TLabel", background=Theme.BG, foreground=Theme.TEXT)

    # Cards / headers
    s.configure("Card.TFrame", background=Theme.CARD)
    s.configure("CardTitle.TLabel", background=Theme.CARD, foreground=Theme.TEXT, font=("Segoe UI", 12, "bold"))
    s.configure("Muted.TLabel", background=Theme.CARD, foreground=Theme.MUTED, font=("Segoe UI", 9))

    # Buttons
    s.configure(
        "Primary.TButton",
        background=Theme.PRIMARY,
        foreground="white",
        padding=(14, 10),
        borderwidth=0
    )
    s.map(
        "Primary.TButton",
        background=[("active", Theme.PRIMARY_DARK)],
        foreground=[("active", "white")]
    )

    s.configure(
        "Danger.TButton",
        background=Theme.DANGER,
        foreground="white",
        padding=(14, 10),
        borderwidth=0
    )
    s.map(
        "Danger.TButton",
        background=[("active", "#8E2F2C")],
        foreground=[("active", "white")]
    )

    s.configure(
        "Ghost.TButton",
        background=Theme.CARD,
        foreground=Theme.TEXT,
        padding=(12, 9)
    )
    s.map(
        "Ghost.TButton",
        background=[("active", Theme.INPUT_BG)]
    )

    # Entry
    s.configure(
        "TEntry",
        fieldbackground=Theme.INPUT_BG,
        foreground=Theme.TEXT,
        bordercolor=Theme.BORDER,
        lightcolor=Theme.BORDER,
        darkcolor=Theme.BORDER
    )

    # Treeview
    s.configure(
        "Cart.Treeview",
        background=Theme.CARD,
        fieldbackground=Theme.CARD,
        foreground=Theme.TEXT,
        rowheight=26,
        bordercolor=Theme.BORDER
    )
    s.configure(
        "Cart.Treeview.Heading",
        font=("Segoe UI", 9, "bold")
    )
