from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from app.config import THEME


class DiscountDialog(tk.Toplevel):
    """
    Checkout discount dialog — supports PWD 20%, Senior 20%, or custom Special amount.
    Returns:
        self.result = ("NONE", 0.0), ("PWD", 0.0), ("SENIOR", 0.0), or ("SPECIAL", value)
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.title("Add Discount")
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[tuple[str, float]] = None

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["sidebar"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Add Discount",
            bg=THEME["sidebar"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=10,
        ).pack(side="left")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(
            body, text="Discount Type",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        self._mode = tk.StringVar(value="NONE")

        radio_box = tk.Frame(body, bg="#FFFFFF")
        radio_box.pack(fill="x", pady=(4, 14))

        for value, label in (
            ("NONE",    "No Discount"),
            ("PWD",     "PWD 20%"),
            ("SENIOR",  "Senior 20%"),
            ("SPECIAL", "Special Discount"),
        ):
            tk.Radiobutton(
                radio_box, text=f"  {label}", variable=self._mode, value=value,
                bg="#FFFFFF", fg=THEME["text"],
                selectcolor="#FFFFFF",
                font=("Segoe UI", 10),
                activebackground="#FFFFFF",
                padx=10, pady=4,
                anchor="w",
                command=self._sync_special_entry,
            ).pack(fill="x", anchor="w")

        tk.Label(
            body, text="Special Discount Amount",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 4))

        self.value_var = tk.StringVar(value="")
        self.entry = tk.Entry(
            body, textvariable=self.value_var,
            font=("Segoe UI", 13),
            bg="#FFFFFF", bd=0,
            insertbackground=THEME["text"],
        )
        self.entry.pack(fill="x", ipady=10)
        self._sync_special_entry()

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = tk.Frame(body, bg=THEME["panel"])
        btns.pack(fill="x", pady=(16, 0))

        tk.Button(
            btns, text="Cancel", command=self.destroy,
            bg="#FFFFFF", fg=THEME["text"], bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Button(
            btns, text="Apply Discount", command=self._confirm,
            bg=THEME["accent"], fg="white", bd=0,
            padx=16, pady=10, cursor="hand2",
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

    def _sync_special_entry(self) -> None:
        is_special = self._mode.get() == "SPECIAL"
        self.entry.configure(state="normal" if is_special else "disabled")
        if is_special:
            self.entry.focus_set()

    def _confirm(self) -> None:
        mode = self._mode.get()
        if mode in ("NONE", "PWD", "SENIOR"):
            self.result = (mode, 0.0)
            self.destroy()
            return

        try:
            v = float(self.value_var.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Discount", "Please enter a valid number.")
            return
        if v <= 0:
            messagebox.showerror("Discount", "Please enter a discount amount greater than zero.")
            return

        self.result = ("SPECIAL", v)
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
        hdr = tk.Frame(self, bg=THEME["sidebar"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Save Order as Draft",
            bg=THEME["sidebar"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=10,
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
            bg="#FFFFFF", bd=0,
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
            bg="#FFFFFF", fg=THEME["text"], bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Button(
            btns, text="Save Draft", command=self._save,
            bg=THEME["sidebar"], fg="white", bd=0,
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

        self.result: Optional[dict[str, str]] = None

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["sidebar"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=label,
            bg=THEME["sidebar"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=10,
        ).pack(side="left")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(
            body, text="Reference Number",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 4))

        self.ref_var = tk.StringVar(value=default)
        self.ref_entry = tk.Entry(
            body, textvariable=self.ref_var,
            font=("Segoe UI", 11),
            bg="#FFFFFF", bd=0,
            insertbackground=THEME["text"],
        )
        self.ref_entry.pack(fill="x", ipady=9)
        self.ref_entry.focus_set()
        if default:
            self.ref_entry.select_range(0, "end")

        tk.Label(
            body, text="Amount Paid",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(12, 4))

        self.amount_var = tk.StringVar(value="")
        self.amount_entry = tk.Entry(
            body, textvariable=self.amount_var,
            font=("Segoe UI", 11),
            bg="#FFFFFF", bd=0,
            insertbackground=THEME["text"],
        )
        self.amount_entry.pack(fill="x", ipady=9)

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = tk.Frame(body, bg=THEME["panel"])
        btns.pack(fill="x", pady=(18, 0))

        tk.Button(
            btns, text="Cancel", command=self.destroy,
            bg="#FFFFFF", fg=THEME["text"], bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Button(
            btns, text="Confirm", command=self._confirm,
            bg=THEME["accent"], fg="white", bd=0,
            padx=16, pady=10, cursor="hand2",
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


class EWalletDialog(tk.Toplevel):
    """
    GCash / E-Wallet reference number dialog.
    Displays the order total and payment method; only asks for reference number.
    Returns:
        self.result = str (reference number) or None if cancelled/skipped.
    """

    def __init__(self, parent: tk.Widget, order_id: int, total: float,
                 payment_method: str = "GCash / E-Wallet"):
        super().__init__(parent)
        self.title("E-Wallet / GCash Payment")
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[str] = None

        from app.utils import money as _money

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["sidebar"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=f"Order #{order_id}  —  {payment_method}",
            bg=THEME["sidebar"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=10,
        ).pack(side="left")

        # ── Order total display ───────────────────────────────────────────────
        body = tk.Frame(self, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        total_frame = tk.Frame(body, bg=THEME["panel2"], padx=12, pady=10)
        total_frame.pack(fill="x", pady=(0, 14))
        tk.Label(
            total_frame, text="Order Total",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w")
        tk.Label(
            total_frame, text=_money(total),
            bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            total_frame, text=payment_method,
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 0))

        # ── Reference number input ────────────────────────────────────────────
        tk.Label(
            body, text="Reference Number",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 4))

        self.ref_var = tk.StringVar()
        self.ref_entry = tk.Entry(
            body, textvariable=self.ref_var,
            font=("Segoe UI", 12),
            bg="#FFFFFF", bd=0,
            insertbackground=THEME["text"],
        )
        self.ref_entry.pack(fill="x", ipady=9)
        self.ref_entry.focus_set()

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = tk.Frame(body, bg=THEME["panel"])
        btns.pack(fill="x", pady=(18, 0))

        tk.Button(
            btns, text="Skip (Keep Pending)", command=self.destroy,
            bg="#FFFFFF", fg=THEME["muted"], bd=0,
            padx=12, pady=9, cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side="left")

        tk.Button(
            btns, text="Confirm Payment", command=self._confirm,
            bg=THEME["accent"], fg="white", bd=0,
            padx=16, pady=10, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        if self.winfo_width() < 400:
            self.geometry(f"400x{self.winfo_height()}")
        self._center(parent)

    def _center(self, parent: tk.Widget) -> None:
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        except Exception:
            pass

    def _confirm(self) -> None:
        ref = (self.ref_var.get() or "").strip()
        if not ref:
            from tkinter import messagebox as _mb
            _mb.showwarning("Reference Required", "Please enter a reference number.", parent=self)
            return
        self.result = ref
        self.destroy()


class PasswordConfirmDialog(tk.Toplevel):
    """
    Small password prompt used for sensitive actions such as voiding or restoring backups.
    Returns self.result (str) or None if cancelled.
    """

    def __init__(self, parent: tk.Widget, title: str = "Confirm Password",
                 label: str = "Enter your password to continue."):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=THEME["panel"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        self.result: Optional[str] = None
        self._password_var = tk.StringVar()

        hdr = tk.Frame(self, bg=THEME["sidebar"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=title,
            bg=THEME["sidebar"], fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=18, pady=10,
        ).pack(side="left")

        body = tk.Frame(self, bg=THEME["panel"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        tk.Label(
            body, text=label,
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
            justify="left", wraplength=320,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            body, text="Password",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(0, 4))

        self.entry = tk.Entry(
            body, textvariable=self._password_var,
            font=("Segoe UI", 11),
            bg="#FFFFFF", bd=0,
            insertbackground=THEME["text"],
            show="*",
        )
        self.entry.pack(fill="x", ipady=9)
        self.entry.focus_set()

        btns = tk.Frame(body, bg=THEME["panel"])
        btns.pack(fill="x", pady=(18, 0))

        tk.Button(
            btns, text="Cancel", command=self.destroy,
            bg="#FFFFFF", fg=THEME["text"], bd=0,
            padx=16, pady=9, cursor="hand2",
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Button(
            btns, text="Confirm", command=self._confirm,
            bg=THEME["accent"], fg="white", bd=0,
            padx=16, pady=10, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        self.bind("<Return>", lambda _e: self._confirm())
        self.bind("<Escape>", lambda _e: self.destroy())

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
        password = self._password_var.get()
        if not password:
            messagebox.showerror("Password", "Password is required.")
            return
        self.result = password
        self.destroy()
