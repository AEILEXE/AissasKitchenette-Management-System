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
        self.title("Add discount")
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[tuple[str, float]] = None

        tk.Label(self, text="Discount Type", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 10, "bold")).pack(padx=18, pady=(16, 6), anchor="w")

        self._mode = tk.StringVar(value="amount")

        row = tk.Frame(self, bg=THEME["panel"])
        row.pack(padx=18, pady=(0, 10), fill="x")

        tk.Radiobutton(row, text="₱ Amount", variable=self._mode, value="amount",
                       bg=THEME["panel"], fg=THEME["text"], selectcolor=THEME["panel"]).pack(side="left")
        tk.Radiobutton(row, text="% Percent", variable=self._mode, value="percent",
                       bg=THEME["panel"], fg=THEME["text"], selectcolor=THEME["panel"]).pack(side="left", padx=(14, 0))

        tk.Label(self, text="Value", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 10, "bold")).pack(padx=18, pady=(6, 6), anchor="w")

        self.value_var = tk.StringVar(value="0")
        self.entry = tk.Entry(self, textvariable=self.value_var, font=("Segoe UI", 11),
                              bg=THEME["panel2"], bd=0)
        self.entry.pack(padx=18, pady=(0, 12), fill="x", ipady=8)
        self.entry.focus_set()

        btns = tk.Frame(self, bg=THEME["panel"])
        btns.pack(padx=18, pady=(0, 16), fill="x")

        tk.Button(btns, text="Close", command=self.destroy,
                  bg=THEME["panel2"], fg=THEME["text"], bd=0,
                  padx=14, pady=8, cursor="hand2").pack(side="right")

        tk.Button(btns, text="Confirm", command=self._confirm,
                  bg=THEME["brown2"], fg="white", bd=0,
                  padx=14, pady=8, cursor="hand2").pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
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
        self.title("Save order as draft")
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[str] = None

        tk.Label(self, text="Draft title", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 10, "bold")).pack(padx=18, pady=(16, 6), anchor="w")

        self.var = tk.StringVar(value=default_title)
        self.entry = tk.Entry(self, textvariable=self.var, font=("Segoe UI", 11),
                              bg=THEME["panel2"], bd=0)
        self.entry.pack(padx=18, pady=(0, 12), fill="x", ipady=8)
        self.entry.focus_set()
        self.entry.select_range(0, "end")

        btns = tk.Frame(self, bg=THEME["panel"])
        btns.pack(padx=18, pady=(0, 16), fill="x")

        tk.Button(btns, text="Close", command=self.destroy,
                  bg=THEME["panel2"], fg=THEME["text"], bd=0,
                  padx=14, pady=8, cursor="hand2").pack(side="right")

        tk.Button(btns, text="Save", command=self._save,
                  bg=THEME["brown2"], fg="white", bd=0,
                  padx=14, pady=8, cursor="hand2").pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
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

        # Single heading label (uses the passed `label` parameter)
        tk.Label(self, text=label, bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 10, "bold")).pack(padx=18, pady=(16, 10), anchor="w")

        # Reference Number
        tk.Label(self, text="Reference Number", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(padx=18, pady=(0, 2), anchor="w")
        self.ref_var = tk.StringVar(value=default)
        self.ref_entry = tk.Entry(self, textvariable=self.ref_var, font=("Segoe UI", 11),
                                  bg=THEME["panel2"], bd=0)
        self.ref_entry.pack(padx=18, pady=(0, 10), fill="x", ipady=8)
        self.ref_entry.focus_set()
        if default:
            self.ref_entry.select_range(0, "end")

        # Amount Paid
        tk.Label(self, text="Amount Paid", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(padx=18, pady=(0, 2), anchor="w")
        self.amount_var = tk.StringVar(value="")
        self.amount_entry = tk.Entry(self, textvariable=self.amount_var, font=("Segoe UI", 11),
                                     bg=THEME["panel2"], bd=0)
        self.amount_entry.pack(padx=18, pady=(0, 12), fill="x", ipady=8)

        btns = tk.Frame(self, bg=THEME["panel"])
        btns.pack(padx=18, pady=(0, 16), fill="x")

        tk.Button(btns, text="Close", command=self.destroy,
                  bg=THEME["panel2"], fg=THEME["text"], bd=0,
                  padx=14, pady=8, cursor="hand2").pack(side="right")

        tk.Button(btns, text="Confirm", command=self._confirm,
                  bg=THEME["brown2"], fg="white", bd=0,
                  padx=14, pady=8, cursor="hand2").pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
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
