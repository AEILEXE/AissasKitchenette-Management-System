# app/ui/theme.py  — Warm Café Palette (stable + fixed ttk behavior)
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Theme:
    BG           = "#FFF8E7"
    CARD         = "#FFFFFF"
    PRIMARY      = "#8B5E3C"
    PRIMARY_DARK = "#7A5030"
    ACCENT       = "#C08A6B"
    TEXT         = "#2B2B2B"
    MUTED        = "#6A6A6A"
    BORDER       = "#D9C5B2"
    SUCCESS      = "#4A7C59"
    DANGER       = "#B55B52"
    INPUT_BG     = "#FFF8E7"
    SIDEBAR      = "#EED9C4"


def apply_ttk_theme(root: tk.Tk) -> None:
    s = ttk.Style(root)

    try:
        s.theme_use("clam")
    except Exception:
        pass

    # ================= BASE =================
    s.configure(".", font=("Segoe UI", 10))

    s.configure("TFrame", background=Theme.BG)
    s.configure("TLabel", background=Theme.BG, foreground=Theme.TEXT)

    # ================= CARDS =================
    s.configure("Card.TFrame", background=Theme.CARD)

    s.configure("CardTitle.TLabel",
                background=Theme.CARD,
                foreground=Theme.TEXT,
                font=("Segoe UI", 12, "bold"))

    s.configure("Muted.TLabel",
                background=Theme.CARD,
                foreground=Theme.MUTED,
                font=("Segoe UI", 9))

    # ================= BUTTONS =================
    s.configure("Primary.TButton",
                background=Theme.PRIMARY,
                foreground="white",
                padding=(14, 10),
                borderwidth=0)

    s.map("Primary.TButton",
          background=[("active", Theme.PRIMARY_DARK),
                      ("pressed", Theme.PRIMARY_DARK),
                      ("disabled", "#D3B8A3")],
          foreground=[("disabled", "#F2E8E0")])

    s.configure("Danger.TButton",
                background=Theme.DANGER,
                foreground="white",
                padding=(14, 10),
                borderwidth=0)

    s.map("Danger.TButton",
          background=[("active", "#8E3A35"),
                      ("pressed", "#8E3A35")],
          foreground=[("disabled", "#F2E8E0")])

    s.configure("Ghost.TButton",
                background=Theme.CARD,
                foreground=Theme.TEXT,
                padding=(12, 9))

    s.map("Ghost.TButton",
          background=[("active", Theme.INPUT_BG)])

    # ================= ENTRY =================
    s.configure("TEntry",
                fieldbackground=Theme.INPUT_BG,
                foreground=Theme.TEXT,
                padding=6)

    # ================= TREEVIEW =================
    # BODY
    s.configure("Treeview",
                background=Theme.CARD,
                fieldbackground=Theme.CARD,
                foreground=Theme.TEXT,
                rowheight=26)

    # HEADER (FIXED: visible white text + stable brown background)
    s.configure("Treeview.Heading",
                background=Theme.PRIMARY,
                foreground="white",
                font=("Segoe UI", 9, "bold"),
                relief="flat")

    s.map("Treeview.Heading",
          background=[("active", Theme.PRIMARY_DARK),
                      ("pressed", Theme.PRIMARY_DARK)],
          foreground=[("active", "white"),
                      ("pressed", "white")])

    # Row selection
    s.map("Treeview",
          background=[("selected", Theme.ACCENT)],
          foreground=[("selected", "white")])