from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from app.config import THEME


class DiscountDialog(tk.Toplevel):
    """
    Simple discount dialog (Amount or Percent)
    Returns:
        self.result = ("amount", value) or ("percent", value)
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.title("Add Discount")
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[tuple[str, float]] = None

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["brown_dark"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Add Discount",
            bg=THEME["brown_dark"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=12,
        ).pack(side="left")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(
            body, text="Discount Type",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        self._mode = tk.StringVar(value="amount")

        radio_row = tk.Frame(body, bg=THEME["panel2"])
        radio_row.pack(fill="x", pady=(4, 14))

        tk.Radiobutton(
            radio_row, text="  ₱  Peso Amount", variable=self._mode, value="amount",
            bg=THEME["panel2"], fg=THEME["text"],
            selectcolor=THEME["beige"],
            font=("Segoe UI", 10),
            activebackground=THEME["panel2"],
            padx=10, pady=8,
        ).pack(side="left")
        tk.Radiobutton(
            radio_row, text="  %  Percent", variable=self._mode, value="percent",
            bg=THEME["panel2"], fg=THEME["text"],
            selectcolor=THEME["beige"],
            font=("Segoe UI", 10),
            activebackground=THEME["panel2"],
            padx=10, pady=8,
        ).pack(side="left")

        tk.Label(
            body, text="Value",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 4))

        # Value field starts EMPTY — not prefilled with 0
        self.value_var = tk.StringVar(value="")
        self.entry = tk.Entry(
            body, textvariable=self.value_var,
            font=("Segoe UI", 13),
            bg=THEME["panel2"], bd=0,
            insertbackground=THEME["text"],
        )
        self.entry.pack(fill="x", ipady=10)
        self.entry.focus_set()

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = tk.Frame(body, bg=THEME["panel"])
        btns.pack(fill="x", pady=(16, 0))

        tk.Button(
            btns, text="Cancel", command=self.destroy,
            bg=THEME["panel2"], fg=THEME["text"], bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Button(
            btns, text="Apply Discount", command=self._confirm,
            bg=THEME["brown2"], fg="white", bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        # Enforce minimum width — auto-height from content
        if self.winfo_width() < 360:
            self.geometry(f"360x{self.winfo_height()}")
        self._center(parent)

    def _center(self, parent: tk.Widget) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
        except Exception:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _confirm(self) -> None:
        try:
            v = float(self.value_var.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Discount", "Please enter a valid number.")
            return

        mode = self._mode.get()
        if mode == "percent" and (v < 0 or v > 100):
            messagebox.showerror("Discount", "Percent must be between 0 and 100.")
            return
        if v < 0:
            messagebox.showerror("Discount", "Value cannot be negative.")
            return

        self.result = (mode, v)
        self.destroy()


class DraftTitleDialog(tk.Toplevel):
    """
    Asks for a draft title.
    Returns: self.result (str) or None
    """

    def __init__(self, parent: tk.Widget, default_title: str = "Draft"):
        super().__init__(parent)
        self.title("Save Order as Draft")
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[str] = None

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["brown_dark"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Save Order as Draft",
            bg=THEME["brown_dark"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=12,
        ).pack(side="left")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(
            body, text="Draft Title",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 4))

        self.var = tk.StringVar(value=default_title)
        self.entry = tk.Entry(
            body, textvariable=self.var,
            font=("Segoe UI", 12),
            bg=THEME["panel2"], bd=0,
            insertbackground=THEME["text"],
        )
        self.entry.pack(fill="x", ipady=10)
        self.entry.focus_set()
        self.entry.select_range(0, "end")

        tk.Label(
            body, text='e.g. "Table 3" or "Takeout - Maria"',
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 8, "italic"),
        ).pack(anchor="w", pady=(4, 0))

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = tk.Frame(body, bg=THEME["panel"])
        btns.pack(fill="x", pady=(18, 0))

        tk.Button(
            btns, text="Cancel", command=self.destroy,
            bg=THEME["panel2"], fg=THEME["text"], bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Button(
            btns, text="Save Draft", command=self._save,
            bg=THEME["brown_dark"], fg="white", bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        if self.winfo_width() < 380:
            self.geometry(f"380x{self.winfo_height()}")
        self._center(parent)

    def _center(self, parent: tk.Widget) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
        except Exception:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _save(self) -> None:
        title = (self.var.get() or "").strip()
        if not title:
            messagebox.showerror("Draft", "Please enter a title.")
            return
        self.result = title
        self.destroy()


class TextPromptDialog(tk.Toplevel):
    """
    Generic text prompt for collecting a reference number and amount paid.

    Returns:
        self.result = {"ref": str, "amount": str}  or None if cancelled.
    """

    def __init__(self, parent: tk.Widget, title: str, label: str, default: str = ""):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[dict] = None

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["brown_dark"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=label,
            bg=THEME["brown_dark"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=12,
        ).pack(side="left")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        # Reference Number
        tk.Label(
            body, text="Reference Number",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 4))

        self.ref_var = tk.StringVar(value=default)
        self.ref_entry = tk.Entry(
            body, textvariable=self.ref_var,
            font=("Segoe UI", 11),
            bg=THEME["panel2"], bd=0,
            insertbackground=THEME["text"],
        )
        self.ref_entry.pack(fill="x", ipady=9)
        self.ref_entry.focus_set()
        if default:
            self.ref_entry.select_range(0, "end")

        # Amount Paid
        tk.Label(
            body, text="Amount Paid",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(12, 4))

        self.amount_var = tk.StringVar(value="")
        self.amount_entry = tk.Entry(
            body, textvariable=self.amount_var,
            font=("Segoe UI", 11),
            bg=THEME["panel2"], bd=0,
            insertbackground=THEME["text"],
        )
        self.amount_entry.pack(fill="x", ipady=9)

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = tk.Frame(body, bg=THEME["panel"])
        btns.pack(fill="x", pady=(18, 0))

        tk.Button(
            btns, text="Cancel", command=self.destroy,
            bg=THEME["panel2"], fg=THEME["text"], bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Button(
            btns, text="Confirm", command=self._confirm,
            bg=THEME["brown2"], fg="white", bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        if self.winfo_width() < 380:
            self.geometry(f"380x{self.winfo_height()}")
        self._center(parent)

    def _center(self, parent: tk.Widget) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
        except Exception:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _confirm(self) -> None:
        ref = (self.ref_var.get() or "").strip()
        amount = (self.amount_var.get() or "").strip()
        self.result = {"ref": ref, "amount": amount}
        self.destroy()
