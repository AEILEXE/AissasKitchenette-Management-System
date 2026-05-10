"""
inventory_raw_materials_view.py
Raw Materials Inventory: expiration tracking, manual stock movements, audit log.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from datetime import date

from app.config import THEME
from app.db.database import Database
from app.services.auth_service import AuthService
from app.ui.dialogs import show_toast


def _safe(row, key, default=None):
    try:
        v = row[key]
        return default if v is None else v
    except Exception:
        return default


def _open_date_picker(parent: tk.Widget, var: tk.StringVar) -> None:
    """Pop the shared pure-Tk DatePickerDialog and write its result to var."""
    try:
        from app.ui.transactions_view import DatePickerDialog
        dlg = DatePickerDialog(parent, initial=var.get() or None)
        if dlg.result:
            var.set(dlg.result)
    except Exception:
        pass


def _exp_status(exp_str: Optional[str]) -> tuple[str, str]:
    """Return (label, tag). tag is 'expired', 'expiring_soon', or ''."""
    if not exp_str:
        return "—", ""
    try:
        exp_dt = date.fromisoformat(str(exp_str).strip())
        days_left = (exp_dt - date.today()).days
        if days_left < 0:
            return "❌ Expired", "expired"
        if days_left <= 3:
            return "⚠ Expiring Soon", "expiring_soon"
        return "✓ OK", ""
    except (ValueError, TypeError):
        return "—", ""


# ── Dialogs ───────────────────────────────────────────────────────────────────

class _MaterialDialog(tk.Toplevel):
    """Add / Edit a raw material."""

    def __init__(self, parent, db: Database, material: Optional[dict] = None):
        super().__init__(parent)
        self.db = db
        self.result: Optional[dict] = None

        self.title("Edit Material" if material else "Add Raw Material")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.grab_set()

        pad = 14
        UNIT_CHOICES = ["pcs", "grams", "kilograms", "liters", "milliliters",
                        "bottles", "packs", "boxes", "cans", "trays"]

        # ── Plain text/dropdown fields ────────────────────────────────────────
        fields = [
            ("Name *",          "var_name", _safe(material, "name", ""),              "entry"),
            ("Unit",             "var_unit", _safe(material, "unit", "pcs"),           "unit"),
            ("Quantity",         "var_qty",  str(_safe(material, "quantity", 0)),     "entry"),
            ("Low Stock Alert",  "var_low",  str(_safe(material, "low_stock", 5)),    "entry"),
        ]
        for row_i, (lbl_txt, attr, default, kind) in enumerate(fields):
            tk.Label(self, text=lbl_txt, bg=THEME["bg"], fg=THEME["text"],
                     font=("Segoe UI", 10)).grid(
                row=row_i, column=0, sticky="w",
                padx=pad, pady=(pad if row_i == 0 else 4, 4))
            sv = tk.StringVar(value=default)
            setattr(self, attr, sv)
            if kind == "unit":
                cb = ttk.Combobox(
                    self, textvariable=sv, values=UNIT_CHOICES,
                    width=26, font=("Segoe UI", 10), state="normal",
                )
                cb.grid(row=row_i, column=1, padx=pad,
                        pady=(pad if row_i == 0 else 4, 4), sticky="w")
            else:
                tk.Entry(self, textvariable=sv, width=28,
                         bg=THEME["beige"], fg=THEME["text"],
                         insertbackground="#3d2b1f", insertwidth=2,
                         font=("Segoe UI", 10)).grid(
                    row=row_i, column=1, padx=pad,
                    pady=(pad if row_i == 0 else 4, 4), sticky="w")

        n = len(fields)

        # ── Delivered Date (calendar picker) ──────────────────────────────────
        self.var_delivered = tk.StringVar(value=_safe(material, "delivered_date", "") or "")
        tk.Label(self, text="Delivered Date", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=n, column=0, sticky="w", padx=pad, pady=4)
        del_row = tk.Frame(self, bg=THEME["bg"])
        del_row.grid(row=n, column=1, sticky="w", padx=pad, pady=4)
        ent_del = tk.Entry(del_row, textvariable=self.var_delivered, width=16,
                           bg=THEME["beige"], fg=THEME["text"],
                           insertbackground="#3d2b1f", insertwidth=2,
                           font=("Segoe UI", 10))
        ent_del.pack(side="left")
        tk.Button(del_row, text="📅 Pick",
                  command=lambda: _open_date_picker(self, self.var_delivered),
                  bg=THEME["panel2"], fg=THEME["text"],
                  bd=0, padx=10, pady=3, cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))
        tk.Button(del_row, text="Clear",
                  command=lambda: self.var_delivered.set(""),
                  bg=THEME["border"], fg=THEME["text"],
                  bd=0, padx=8, pady=3, cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left", padx=(4, 0))

        # ── Expiration Date (calendar picker) ─────────────────────────────────
        self.var_expiration = tk.StringVar(value=_safe(material, "expiration_date", "") or "")
        tk.Label(self, text="Expiration Date", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=n + 1, column=0, sticky="w", padx=pad, pady=4)
        exp_row = tk.Frame(self, bg=THEME["bg"])
        exp_row.grid(row=n + 1, column=1, sticky="w", padx=pad, pady=4)
        ent_exp = tk.Entry(exp_row, textvariable=self.var_expiration, width=16,
                           bg=THEME["beige"], fg=THEME["text"],
                           insertbackground="#3d2b1f", insertwidth=2,
                           font=("Segoe UI", 10))
        ent_exp.pack(side="left")
        tk.Button(exp_row, text="📅 Pick",
                  command=lambda: _open_date_picker(self, self.var_expiration),
                  bg=THEME["panel2"], fg=THEME["text"],
                  bd=0, padx=10, pady=3, cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))
        tk.Button(exp_row, text="Clear",
                  command=lambda: self.var_expiration.set(""),
                  bg=THEME["border"], fg=THEME["text"],
                  bd=0, padx=8, pady=3, cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left", padx=(4, 0))

        n2 = n + 2

        # ── Type segmented buttons (Dry / Wet) ───────────────────────────────
        tk.Label(self, text="Type", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=n2, column=0, sticky="w", padx=pad, pady=(8, 4))
        self.var_type = tk.StringVar(value=_safe(material, "material_type", "DRY"))
        seg = tk.Frame(self, bg=THEME["bg"])
        seg.grid(row=n2, column=1, sticky="w", padx=pad, pady=(8, 4))
        self._type_seg_btns: dict[str, tk.Button] = {}
        for val, lbl in (("DRY", "🌾  Dry"), ("WET", "💧  Wet")):
            b = tk.Button(seg, text=lbl,
                          command=lambda v=val: self._set_type(v),
                          bd=0, padx=18, pady=8, cursor="hand2",
                          font=("Segoe UI", 10, "bold"),
                          relief="flat")
            b.pack(side="left", padx=(0, 6))
            self._type_seg_btns[val] = b
        self._set_type(self.var_type.get())

        # ── Active checkbox ──────────────────────────────────────────────────
        self.var_active = tk.BooleanVar(value=bool(_safe(material, "active", 1)))
        tk.Checkbutton(self, text="Active", variable=self.var_active,
                       bg=THEME["bg"], fg=THEME["text"], selectcolor=THEME["bg"],
                       font=("Segoe UI", 10)).grid(
            row=n2 + 1, column=1, sticky="w", padx=pad, pady=4)

        # ── Buttons (clearer / aligned) ──────────────────────────────────────
        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.grid(row=n2 + 2, column=0, columnspan=2,
                     sticky="ew", padx=pad, pady=(14, pad))
        btn_row.columnconfigure(0, weight=1)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=THEME["panel2"], fg=THEME["text"],
                  activebackground=THEME["border"], activeforeground=THEME["text"],
                  padx=22, pady=10, bd=0,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10)).grid(row=0, column=1, padx=(0, 8))
        save_lbl = "Update" if material else "Save"
        tk.Button(btn_row, text=save_lbl, command=self._save,
                  bg=THEME["success"], fg="white",
                  activebackground=THEME["primary_dark"], activeforeground="white",
                  padx=22, pady=10, bd=0,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=2)

        self.transient(parent)
        self.wait_window()

    def _set_type(self, val: str):
        self.var_type.set(val)
        for v, b in self._type_seg_btns.items():
            if v == val:
                b.configure(bg=THEME["primary"], fg="white",
                            activebackground=THEME["primary_dark"], activeforeground="white")
            else:
                b.configure(bg=THEME["panel2"], fg=THEME["text"],
                            activebackground=THEME["border"], activeforeground=THEME["text"])

    def _validate_date(self, val: str) -> Optional[str]:
        v = val.strip()
        if not v:
            return None
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid date '{v}' — use YYYY-MM-DD.")

    def _save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("Validation", "Name is required.", parent=self)
            return
        try:
            qty = float(self.var_qty.get())
            low = float(self.var_low.get())
        except ValueError:
            messagebox.showerror("Validation", "Quantity and Low Stock must be numbers.", parent=self)
            return
        try:
            delivered = self._validate_date(self.var_delivered.get())
            expiration = self._validate_date(self.var_expiration.get())
        except ValueError as exc:
            messagebox.showerror("Validation", str(exc), parent=self)
            return
        self.result = {
            "name":            name,
            "material_type":   self.var_type.get(),
            "unit":            self.var_unit.get().strip() or "pcs",
            "quantity":        qty,
            "low_stock":       low,
            "active":          1 if self.var_active.get() else 0,
            "delivered_date":  delivered,
            "expiration_date": expiration,
        }
        self.destroy()


class _StockMovementDialog(tk.Toplevel):
    """Prompt for Add Stock or Deduct / Use Stock."""

    _REASONS_ADD    = ["Restock", "Delivery", "Adjustment", "Initial Stock", "Other"]
    _REASONS_DEDUCT = ["Cooking", "Spoilage", "Expired", "Adjustment", "Other"]

    def __init__(self, parent, mat_name: str, current_qty: float, unit: str,
                 action: str):
        super().__init__(parent)
        self.action      = action
        self.current_qty = current_qty
        self.result: Optional[dict] = None

        title = "Add Stock" if action == "ADD" else "Deduct / Use Stock"
        self.title(f"{title} — {mat_name}")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.grab_set()

        pad = 14
        info_bg = THEME["success_bg"] if action == "ADD" else THEME["danger_bg"]
        info_fg = THEME["success"]    if action == "ADD" else THEME["danger"]
        tk.Label(self, text=f"Current stock: {current_qty:.2f} {unit}",
                 bg=info_bg, fg=info_fg, font=("Segoe UI", 10, "bold"),
                 padx=12, pady=8).grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=pad, pady=(pad, 6))

        tk.Label(self, text="Quantity:", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", padx=pad, pady=4)
        self.var_qty = tk.StringVar(value="1")
        tk.Entry(self, textvariable=self.var_qty, width=16,
                 bg=THEME["beige"], fg=THEME["text"],
                 insertbackground="#3d2b1f", insertwidth=2,
                 font=("Segoe UI", 11, "bold")).grid(
            row=1, column=1, padx=pad, pady=4, sticky="w")

        tk.Label(self, text="Reason:", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", padx=pad, pady=4)
        self.var_reason = tk.StringVar()
        reasons = self._REASONS_ADD if action == "ADD" else self._REASONS_DEDUCT
        cb = ttk.Combobox(self, textvariable=self.var_reason,
                          values=reasons, width=22, font=("Segoe UI", 10), state="readonly")
        cb.grid(row=2, column=1, padx=pad, pady=4, sticky="w")
        cb.current(0)

        tk.Label(self, text="Reference (opt.):", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=3, column=0, sticky="w", padx=pad, pady=4)
        self.var_ref = tk.StringVar()
        tk.Entry(self, textvariable=self.var_ref, width=24,
                 bg=THEME["beige"], fg=THEME["text"],
                 insertbackground="#3d2b1f", insertwidth=2,
                 font=("Segoe UI", 10)).grid(row=3, column=1, padx=pad, pady=4, sticky="w")

        btn_bg = THEME["success"] if action == "ADD" else THEME["danger"]
        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.grid(row=4, column=0, columnspan=2, pady=(8, pad))
        tk.Button(btn_row, text="Confirm", command=self._confirm,
                  bg=btn_bg, fg="white", padx=16, pady=6,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=THEME["border"], fg=THEME["text"], padx=16, pady=6,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10)).pack(side="left", padx=6)

        self.transient(parent)
        self.wait_window()

    def _confirm(self):
        try:
            qty = float(self.var_qty.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation", "Enter a valid positive quantity.", parent=self)
            return
        if self.action == "DEDUCT" and qty > self.current_qty:
            messagebox.showerror(
                "Insufficient Stock",
                f"Cannot deduct {qty} — only {self.current_qty:.2f} available.",
                parent=self,
            )
            return
        self.result = {
            "quantity":  qty,
            "reason":    self.var_reason.get().strip() or "Other",
            "reference": self.var_ref.get().strip(),
        }
        self.destroy()


class _HistoryDialog(tk.Toplevel):
    """Show stock movement log for one material."""

    def __init__(self, parent, db: Database, material_id: int, mat_name: str):
        super().__init__(parent)
        self.title(f"Stock History — {mat_name}")
        self.configure(bg=THEME["bg"])
        self.resizable(True, True)
        self.geometry("960x460")
        self.grab_set()

        tk.Label(self, text=f"Stock History: {mat_name}",
                 bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 4))

        frm = tk.Frame(self, bg=THEME["bg"])
        frm.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        cols = ("created_at", "action_type", "quantity",
                "old_qty", "new_qty", "reason", "user", "reference")
        hdrs = ("Date & Time", "Action", "Δ Qty",
                "Old Qty", "New Qty", "Reason", "User", "Reference")
        widths = (155, 80, 80, 80, 80, 150, 110, 140)

        tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        for col, hdr, w in zip(cols, hdrs, widths):
            tree.heading(col, text=hdr)
            tree.column(col, width=w, minwidth=50)
        sb_y = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
        sb_x = ttk.Scrollbar(frm, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        tree.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")

        tree.tag_configure("ADD",    foreground=THEME["success"])
        tree.tag_configure("DEDUCT", foreground=THEME["danger"])

        # Tolerate older rows that lack the new columns.
        try:
            rows = db.fetchall(
                """SELECT created_at, action_type, quantity, reason, reference,
                          COALESCE(old_quantity, 0) AS old_quantity,
                          COALESCE(new_quantity, 0) AS new_quantity,
                          COALESCE(username, '')    AS username
                   FROM raw_material_logs WHERE material_id=?
                   ORDER BY datetime(created_at) DESC;""",
                (material_id,),
            )
        except Exception:
            rows = db.fetchall(
                """SELECT created_at, action_type, quantity, reason, reference
                   FROM raw_material_logs WHERE material_id=?
                   ORDER BY datetime(created_at) DESC;""",
                (material_id,),
            )

        for r in rows:
            action = str(_safe(r, "action_type", ""))
            qty = float(_safe(r, "quantity", 0))
            old_q = float(_safe(r, "old_quantity", 0))
            new_q = float(_safe(r, "new_quantity", 0))
            tree.insert("", "end", tags=(action,), values=(
                _safe(r, "created_at", ""),
                action,
                f"{qty:.3f}",
                f"{old_q:.3f}",
                f"{new_q:.3f}",
                _safe(r, "reason", ""),
                _safe(r, "username", ""),
                _safe(r, "reference", ""),
            ))
        if not rows:
            tree.insert("", "end", values=(
                "No stock movements yet.", "", "", "", "", "", "", ""))

        # Pack horizontal scrollbar after rows exist so layout is final
        sb_x.pack(side="bottom", fill="x")

        tk.Button(self, text="Close", command=self.destroy,
                  bg=THEME["primary"], fg="white", padx=14, pady=6,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(pady=(0, 12))

        self.transient(parent)
        self.wait_window()


# ── Main view ─────────────────────────────────────────────────────────────────

class InventoryRawMaterialsView(tk.Frame):
    _LOW_BG      = "#fff3cd"
    _LOW_FG      = "#856404"
    _SOON_BG     = "#fff3cd"
    _SOON_FG     = "#856404"
    _EXPIRED_BG  = "#ffcccc"
    _EXPIRED_FG  = "#8b0000"

    COLS   = ("id", "name", "type", "unit", "quantity", "low_stock",
              "delivered_date", "expiration_date", "exp_status", "status")
    HDRS   = ("ID", "Name", "Type", "Unit", "Qty", "Low Alert",
              "Delivered", "Expires", "Expiration Status", "Active")
    WIDTHS = (60, 160, 62, 62, 82, 78, 105, 105, 135, 65)

    # Maps COLS key → SQL expression for ORDER BY
    _DB_SORT = {
        "id":              "id",
        "name":            "LOWER(name)",
        "type":            "material_type",
        "unit":            "unit",
        "quantity":        "quantity",
        "low_stock":       "low_stock",
        "delivered_date":  "COALESCE(delivered_date, '9999-99-99')",
        "expiration_date": "COALESCE(expiration_date, '9999-99-99')",
        "status":          "active",
    }

    def __init__(self, parent, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db   = db
        self.auth = auth

        self._type_filter:   str = "ALL"
        self._status_filter: str = "Active"
        self._sort_col:      Optional[str] = None
        self._sort_asc:      bool = True
        self._search_q:      str = ""
        # Mode: "menu" | "list" | "low" | "edit" | "deduct" | "logs"
        self._mode: str = "menu"

        # Build menu picker + list panel; show menu first.
        self._build_root()
        self._show_menu()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_root(self):
        """Create container frames for the menu picker and the list view."""
        self._menu_frame = tk.Frame(self, bg=THEME["bg"])
        self._list_frame = tk.Frame(self, bg=THEME["bg"])
        self._logs_frame = tk.Frame(self, bg=THEME["bg"])
        self._build_menu()
        self._build_list_ui()
        # Logs frame is built lazily on first display.

    def _show_menu(self):
        self._mode = "menu"
        try:
            self._list_frame.pack_forget()
        except Exception:
            pass
        try:
            self._logs_frame.pack_forget()
        except Exception:
            pass
        self._menu_frame.pack(fill="both", expand=True)

    def _show_list(self, mode: str = "list"):
        """Show the stock list. mode controls hint banner & default filter:
        list / low / edit / deduct."""
        self._mode = mode
        try:
            self._menu_frame.pack_forget()
        except Exception:
            pass
        try:
            self._logs_frame.pack_forget()
        except Exception:
            pass
        # Default filters per mode
        if mode == "low":
            self._status_filter = "Active"
        # Hint banner text
        hints = {
            "list":   "Stock List — all raw materials.",
            "low":    "Low Stock — items at or below their low-stock alert.",
            "edit":   "Update / Edit — select a row, then click Edit (or double-click).",
            "deduct": "Deduct / Use Stock — select a row, then click Deduct.",
        }
        self._hint_lbl.configure(text=hints.get(mode, ""))
        self._list_frame.pack(fill="both", expand=True)
        self.refresh_materials()

    def _show_logs(self):
        self._mode = "logs"
        try:
            self._menu_frame.pack_forget()
        except Exception:
            pass
        try:
            self._list_frame.pack_forget()
        except Exception:
            pass
        # Build / rebuild logs UI on each open so it shows latest entries
        for w in self._logs_frame.winfo_children():
            w.destroy()
        self._build_logs_ui(self._logs_frame)
        self._logs_frame.pack(fill="both", expand=True)

    # ── Menu picker ────────────────────────────────────────────────────────────

    def _build_menu(self):
        outer = self._menu_frame
        for w in outer.winfo_children():
            w.destroy()

        tk.Label(outer, text="Raw Materials", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(outer, text="Pick what you want to do. Each action opens its own panel.",
                 bg=THEME["bg"], fg=THEME["muted"],
                 font=("Segoe UI", 10)).pack(anchor="w", padx=22, pady=(0, 16))

        grid = tk.Frame(outer, bg=THEME["bg"])
        grid.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="rmcards")

        cards = [
            ("Add Raw Material",        "Create a new raw material entry.",
             THEME["success"], self._add_material_from_menu),
            ("Update / Edit",           "Edit details of an existing material.",
             THEME["primary"], lambda: self._show_list("edit")),
            ("Deduct / Use Stock",      "Reduce quantity used for cooking, spoilage, etc.",
             THEME["warning"], lambda: self._show_list("deduct")),
            ("Stock List",              "Browse and search the full materials list.",
             THEME["accent"], lambda: self._show_list("list")),
            ("Low Stock",               "Items at or below their low-stock alert.",
             THEME["danger"], lambda: self._show_list("low")),
            ("Movement History",        "Audit log of every stock movement.",
             THEME["brown"], self._show_logs),
        ]
        for i, (title, sub, accent, cmd) in enumerate(cards):
            r, c = divmod(i, 3)
            card = tk.Frame(grid, bg=THEME["panel"],
                            highlightthickness=1, highlightbackground=THEME["border"],
                            cursor="hand2")
            card.grid(row=r, column=c, sticky="nsew", padx=8, pady=8)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=title, bg=THEME["panel"], fg=THEME["text"],
                     font=("Segoe UI", 13, "bold"), anchor="w"
                     ).pack(anchor="w", padx=16, pady=(14, 4))
            tk.Label(card, text=sub, bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", 9), anchor="w", justify="left",
                     wraplength=240).pack(anchor="w", padx=16, pady=(0, 14))
            tk.Label(card, text="Open  →", bg=THEME["panel"], fg=accent,
                     font=("Segoe UI", 9, "bold")
                     ).pack(anchor="e", padx=16, pady=(0, 12))
            for w in (card, *card.winfo_children()):
                w.bind("<Button-1>", lambda _e, c=cmd: c())
            for w in card.winfo_children():
                for ch in w.winfo_children():
                    ch.bind("<Button-1>", lambda _e, c=cmd: c())

    def _add_material_from_menu(self):
        """Open Add dialog directly from the menu, then return to menu."""
        self._add_material()
        # Stay on menu — user can pick another action.

    # ── List UI (Stock List / Low Stock / Edit / Deduct modes) ─────────────────

    def _build_list_ui(self):
        host = self._list_frame
        # ── Top bar: Back + title + hint banner + filters ─────────────────────
        top = tk.Frame(host, bg=THEME["bg"])
        top.pack(fill="x", padx=16, pady=(12, 4))

        tk.Button(top, text="←  Back", command=self._show_menu,
                  bg=THEME["panel2"], fg=THEME["text"],
                  activebackground=THEME["border"], activeforeground=THEME["text"],
                  bd=0, padx=12, pady=6, cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="left")

        tk.Label(top, text="Raw Materials", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=(14, 0))

        self._hint_lbl = tk.Label(host, text="",
                                  bg=THEME["panel2"], fg=THEME["text"],
                                  font=("Segoe UI", 9, "italic"),
                                  anchor="w", padx=12, pady=6)
        self._hint_lbl.pack(fill="x", padx=16, pady=(0, 4))

        # ── Search row ────────────────────────────────────────────────────────
        srch = tk.Frame(host, bg=THEME["panel"],
                        highlightthickness=1, highlightbackground=THEME["border"])
        srch.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(srch, text="Search by Product ID or Name",
                 bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 6), pady=4)
        self.var_search = tk.StringVar()
        ent = tk.Entry(srch, textvariable=self.var_search, bd=0,
                       bg=THEME["panel"], fg=THEME["text"],
                       insertbackground="#3d2b1f", insertwidth=2,
                       font=("Segoe UI", 10))
        ent.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        ent.bind("<KeyRelease>", lambda _e: self._on_search_change())

        # ── Filter chips row ──────────────────────────────────────────────────
        chips = tk.Frame(host, bg=THEME["bg"])
        chips.pack(fill="x", padx=16, pady=(2, 4))

        ff = tk.Frame(chips, bg=THEME["bg"])
        ff.pack(side="left")
        self._type_btns: dict[str, tk.Button] = {}
        for key, lbl in (("ALL", "All Types"), ("DRY", "Dry"), ("WET", "Wet")):
            b = tk.Button(ff, text=lbl,
                          command=lambda k=key: self._set_type_filter(k),
                          bg=THEME["primary"] if key == self._type_filter else THEME["border"],
                          fg="white" if key == self._type_filter else THEME["text"],
                          padx=12, pady=4, relief="flat", cursor="hand2",
                          font=("Segoe UI", 9))
            b.pack(side="left", padx=2)
            self._type_btns[key] = b

        sf = tk.Frame(chips, bg=THEME["bg"])
        sf.pack(side="left", padx=14)
        tk.Label(sf, text="Show:", bg=THEME["bg"], fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._status_btns: dict[str, tk.Button] = {}
        for key in ("Active", "Inactive", "All"):
            b = tk.Button(sf, text=key,
                          command=lambda k=key: self._set_status_filter(k),
                          bg=THEME["primary"] if key == self._status_filter else THEME["border"],
                          fg="white" if key == self._status_filter else THEME["text"],
                          padx=10, pady=4, relief="flat", cursor="hand2",
                          font=("Segoe UI", 9))
            b.pack(side="left", padx=2)
            self._status_btns[key] = b

        # ── Action toolbar ────────────────────────────────────────────────────
        toolbar = tk.Frame(host, bg=THEME["panel"],
                           highlightthickness=1, highlightbackground=THEME["border"])
        toolbar.pack(fill="x", padx=16, pady=(0, 6))

        left = tk.Frame(toolbar, bg=THEME["panel"])
        left.pack(side="left", padx=8, pady=6)

        tk.Button(left, text="+ Add Material", command=self._add_material,
                  bg=THEME["primary"], fg="white", padx=12, pady=5,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))

        self._btn_edit = tk.Button(left, text="Edit", command=self._edit_material,
                                   bg=THEME["border"], fg=THEME["text"], padx=10, pady=5,
                                   relief="flat", cursor="hand2", font=("Segoe UI", 9))
        self._btn_edit.pack(side="left", padx=2)

        self._btn_add_stock = tk.Button(left, text="Add Stock", command=self._add_stock,
                                        bg=THEME["border"], fg=THEME["text"], padx=10, pady=5,
                                        relief="flat", cursor="hand2", font=("Segoe UI", 9))
        self._btn_add_stock.pack(side="left", padx=2)

        self._btn_deduct = tk.Button(left, text="Deduct", command=self._deduct_stock,
                                     bg=THEME["border"], fg=THEME["text"], padx=10, pady=5,
                                     relief="flat", cursor="hand2", font=("Segoe UI", 9))
        self._btn_deduct.pack(side="left", padx=2)

        self._btn_history = tk.Button(left, text="History", command=self._view_history,
                                      bg=THEME["border"], fg=THEME["text"], padx=10, pady=5,
                                      relief="flat", cursor="hand2", font=("Segoe UI", 9))
        self._btn_history.pack(side="left", padx=2)

        tk.Frame(toolbar, bg=THEME["border"], width=1).pack(side="left", fill="y", pady=4)

        right = tk.Frame(toolbar, bg=THEME["panel"])
        right.pack(side="left", padx=8, pady=6)

        self._toggle_btn = tk.Button(right, text="Deactivate",
                                     command=self._toggle_active,
                                     bg=THEME["border"], fg=THEME["text"],
                                     padx=10, pady=5, relief="flat", cursor="hand2",
                                     font=("Segoe UI", 9))
        self._toggle_btn.pack(side="left", padx=2)

        self._btn_delete = tk.Button(right, text="Delete", command=self._delete_material,
                                     bg=THEME["border"], fg=THEME["text"], padx=10, pady=5,
                                     relief="flat", cursor="hand2", font=("Segoe UI", 9))
        self._btn_delete.pack(side="left", padx=2)

        util = tk.Frame(toolbar, bg=THEME["panel"])
        util.pack(side="right", padx=8, pady=6)

        tk.Button(util, text="Sort FIFO", command=self._sort_by_expiry,
                  bg=THEME["border"], fg=THEME["text"], padx=10, pady=5,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left", padx=2)

        tk.Button(util, text="Refresh", command=self.refresh_materials,
                  bg=THEME["border"], fg=THEME["text"], padx=10, pady=5,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="left", padx=2)

        # ── Treeview ──────────────────────────────────────────────────────────
        tf = tk.Frame(host, bg=THEME["bg"])
        tf.pack(fill="both", expand=True, padx=16, pady=(0, 2))

        style = ttk.Style()
        style.configure("RM.Treeview",
                        rowheight=32,
                        font=("Segoe UI", 9),
                        background=THEME["panel"],
                        fieldbackground=THEME["panel"],
                        foreground=THEME["text"],
                        borderwidth=0, relief="flat")
        style.configure("RM.Treeview.Heading",
                        font=("Segoe UI", 9, "bold"),
                        background=THEME["beige"],
                        foreground=THEME["text"],
                        relief="flat", padding=(10, 8))
        style.map("RM.Treeview",
                  background=[("selected", "#5C3D2E")],
                  foreground=[("selected", "#FFFFFF")])
        style.map("RM.Treeview.Heading",
                  background=[("active", THEME["border"])],
                  foreground=[("active", THEME["text"])])

        self.tree = ttk.Treeview(tf, columns=self.COLS, show="headings",
                                 style="RM.Treeview", height=18)
        for col, hdr, w in zip(self.COLS, self.HDRS, self.WIDTHS):
            self.tree.heading(col, text=hdr,
                              command=lambda c=col: self._on_header_click(c))
            self.tree.column(col, width=w, minwidth=40,
                             anchor="center" if col == "id" else "w")

        sb_y = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")

        self.tree.tag_configure("expired",
                                background=self._EXPIRED_BG, foreground=self._EXPIRED_FG)
        self.tree.tag_configure("expiring_soon",
                                background=self._SOON_BG, foreground=self._SOON_FG)
        self.tree.tag_configure("low",
                                background=self._LOW_BG, foreground=self._LOW_FG)
        self.tree.tag_configure("empty",
                                foreground=THEME["muted"])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit_material())

        # ── Legend ────────────────────────────────────────────────────────────
        leg = tk.Frame(host, bg=THEME["bg"])
        leg.pack(fill="x", padx=16, pady=(2, 8))
        tk.Label(leg, text=" ⚠ Expiring Soon ",
                 bg=self._SOON_BG, fg=self._SOON_FG,
                 font=("Segoe UI", 9), padx=4).pack(side="left", padx=(0, 4))
        tk.Label(leg, text=" ❌ Expired ",
                 bg=self._EXPIRED_BG, fg=self._EXPIRED_FG,
                 font=("Segoe UI", 9), padx=4).pack(side="left", padx=(0, 4))
        tk.Label(leg, text=" ⚠ Low Stock ",
                 bg=self._LOW_BG, fg=self._LOW_FG,
                 font=("Segoe UI", 9), padx=4).pack(side="left")
        tk.Label(leg, text="  Click column header to sort  •  Double-click row to edit",
                 bg=THEME["bg"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "italic")).pack(side="left", padx=12)

        self._update_action_btns(selected=False)

    def _on_search_change(self):
        self._search_q = (self.var_search.get() or "").strip().lower()
        self.refresh_materials()

    # ── Movement History (global log) ──────────────────────────────────────────

    def _build_logs_ui(self, host: tk.Frame):
        top = tk.Frame(host, bg=THEME["bg"])
        top.pack(fill="x", padx=16, pady=(12, 4))
        tk.Button(top, text="←  Back", command=self._show_menu,
                  bg=THEME["panel2"], fg=THEME["text"],
                  bd=0, padx=12, pady=6, cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(top, text="Movement History", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=(14, 0))

        tk.Label(host, text="All raw-material stock movements (most recent first).",
                 bg=THEME["bg"], fg=THEME["muted"],
                 font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=16, pady=(0, 4))

        tf = tk.Frame(host, bg=THEME["bg"])
        tf.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        cols = ("created_at", "name", "action_type", "quantity",
                "old_qty", "new_qty", "reason", "user", "reference")
        hdrs = ("Date & Time", "Material", "Action", "Δ Qty",
                "Old", "New", "Reason", "User", "Reference")
        widths = (155, 180, 80, 80, 80, 80, 130, 110, 130)
        tree = ttk.Treeview(tf, columns=cols, show="headings",
                            style="RM.Treeview", height=18)
        for c, h, w in zip(cols, hdrs, widths):
            tree.heading(c, text=h)
            tree.column(c, width=w, minwidth=50)
        sb_y = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb_y.set)
        tree.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")

        tree.tag_configure("ADD",    foreground=THEME["success"])
        tree.tag_configure("DEDUCT", foreground=THEME["danger"])

        try:
            rows = self.db.fetchall(
                """SELECT l.created_at, l.action_type, l.quantity, l.reason, l.reference,
                          COALESCE(l.old_quantity, 0) AS old_quantity,
                          COALESCE(l.new_quantity, 0) AS new_quantity,
                          COALESCE(l.username, '')    AS username,
                          COALESCE(m.name, '—')       AS material_name
                   FROM raw_material_logs l
                   LEFT JOIN raw_materials m ON m.id = l.material_id
                   ORDER BY datetime(l.created_at) DESC
                   LIMIT 500;""",
            )
        except Exception:
            rows = []

        if not rows:
            tree.insert("", "end", values=(
                "No stock movements recorded yet.", "", "", "", "", "", "", "", ""))
            return

        for r in rows:
            action = str(_safe(r, "action_type", ""))
            tree.insert("", "end", tags=(action,), values=(
                _safe(r, "created_at", ""),
                _safe(r, "material_name", ""),
                action,
                f"{float(_safe(r, 'quantity', 0)):.3f}",
                f"{float(_safe(r, 'old_quantity', 0)):.3f}",
                f"{float(_safe(r, 'new_quantity', 0)):.3f}",
                _safe(r, "reason", ""),
                _safe(r, "username", ""),
                _safe(r, "reference", ""),
            ))

    # ── Sorting ────────────────────────────────────────────────────────────────

    def _on_header_click(self, col: str):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._update_headings()
        self.refresh_materials()

    def _sort_by_expiry(self):
        self._sort_col = "expiration_date"
        self._sort_asc = True
        self._update_headings()
        self.refresh_materials()

    def _update_headings(self):
        for col, hdr in zip(self.COLS, self.HDRS):
            arrow = ""
            if col == self._sort_col:
                arrow = " ↑" if self._sort_asc else " ↓"
            self.tree.heading(col, text=hdr + arrow)

    # ── Filters ────────────────────────────────────────────────────────────────

    def _set_type_filter(self, key: str):
        self._type_filter = key
        for k, btn in self._type_btns.items():
            btn.configure(
                bg=THEME["primary"] if k == key else THEME["border"],
                fg="white" if k == key else THEME["text"],
            )
        self.refresh_materials()

    def _set_status_filter(self, key: str):
        self._status_filter = key
        for k, btn in self._status_btns.items():
            btn.configure(
                bg=THEME["primary"] if k == key else THEME["border"],
                fg="white" if k == key else THEME["text"],
            )
        self.refresh_materials()

    def _update_action_btns(self, selected: bool, is_active: bool = True):
        """Enable/style selection-dependent buttons based on whether a row is selected."""
        if selected:
            self._btn_edit.configure(
                state="normal", bg=THEME["primary"], fg="white", cursor="hand2")
            self._btn_add_stock.configure(
                state="normal", bg=THEME["success"], fg="white", cursor="hand2")
            self._btn_deduct.configure(
                state="normal", bg=THEME["warning"], fg="white", cursor="hand2")
            self._btn_history.configure(
                state="normal", bg=THEME["accent"], fg="white", cursor="hand2")
            self._toggle_btn.configure(
                state="normal",
                text="Deactivate" if is_active else "Activate",
                bg=THEME["warning"] if is_active else THEME["success"],
                fg="white",
                cursor="hand2",
            )
            self._btn_delete.configure(
                state="normal", bg=THEME["danger"], fg="white", cursor="hand2")
        else:
            for btn in (self._btn_edit, self._btn_add_stock, self._btn_deduct,
                        self._btn_history, self._toggle_btn, self._btn_delete):
                btn.configure(
                    state="disabled", bg=THEME["border"],
                    fg=THEME["muted"], cursor="arrow")
            self._toggle_btn.configure(text="Deactivate")

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self._update_action_btns(selected=False)
            return
        try:
            mat = self._get_material(int(sel[0]))
            is_active = int(_safe(mat, "active", 1)) if mat else 1
            self._update_action_btns(selected=True, is_active=bool(is_active))
        except Exception:
            self._update_action_btns(selected=True)

    # ── Refresh / display ──────────────────────────────────────────────────────

    def refresh_materials(self):
        # Only refresh when the list view is visible
        if getattr(self, "tree", None) is None or not self.tree.winfo_exists():
            return
        self.tree.delete(*self.tree.get_children())

        where, params = [], []
        if self._type_filter != "ALL":
            where.append("material_type=?")
            params.append(self._type_filter)
        if self._status_filter == "Active":
            where.append("active=1")
        elif self._status_filter == "Inactive":
            where.append("active=0")
        if self._mode == "low":
            where.append("low_stock > 0 AND quantity <= low_stock")

        # Search by ID or name
        q = (self._search_q or "").strip()
        if q:
            q_id = q.lstrip("#").strip()
            try:
                int(q_id)
                where.append("(id = ? OR LOWER(name) LIKE ?)")
                params.extend([int(q_id), f"%{q.lower()}%"])
            except ValueError:
                where.append("LOWER(name) LIKE ?")
                params.append(f"%{q.lower()}%")

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        if self._sort_col and self._sort_col in self._DB_SORT:
            dir_sql = "ASC" if self._sort_asc else "DESC"
            order_sql = f"ORDER BY {self._DB_SORT[self._sort_col]} {dir_sql}"
        else:
            order_sql = "ORDER BY material_type, LOWER(name)"

        rows = self.db.fetchall(
            f"SELECT * FROM raw_materials {where_sql} {order_sql};",
            tuple(params),
        )

        for r in rows:
            qty     = float(_safe(r, "quantity", 0))
            low     = float(_safe(r, "low_stock", 0))
            exp_str = _safe(r, "expiration_date", None)
            del_str = _safe(r, "delivered_date", None) or ""
            exp_label, exp_tag = _exp_status(exp_str)
            active_label = "Active" if _safe(r, "active", 1) else "Inactive"

            if exp_tag == "expired":
                tag = ("expired",)
            elif exp_tag == "expiring_soon":
                tag = ("expiring_soon",)
            elif low > 0 and qty <= low:
                tag = ("low",)
            else:
                tag = ()

            self.tree.insert("", "end", iid=str(r["id"]), tags=tag, values=(
                str(r["id"]),
                _safe(r, "name", ""),
                _safe(r, "material_type", ""),
                _safe(r, "unit", ""),
                f"{qty:.2f}",
                f"{low:.2f}",
                del_str or "—",
                exp_str or "—",
                exp_label,
                active_label,
            ))

        if self._sort_col == "exp_status":
            idx = list(self.COLS).index("exp_status")
            children = list(self.tree.get_children())
            children.sort(
                key=lambda iid: self.tree.item(iid)["values"][idx],
                reverse=not self._sort_asc,
            )
            for pos, iid in enumerate(children):
                self.tree.move(iid, "", pos)

        # Empty-state row
        if not rows:
            empty_msg = {
                "low":   "No items at or below their low-stock alert.",
                "edit":  "No materials match your filters / search.",
                "deduct":"No materials match your filters / search.",
            }.get(self._mode, "No raw materials found.")
            self.tree.insert("", "end", tags=("empty",), values=(
                "", empty_msg, "", "", "", "", "", "", "", ""))

        self._update_action_btns(selected=False)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _selected_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a material first.")
            return None
        return int(sel[0])

    def _get_material(self, mid: int) -> Optional[dict]:
        row = self.db.fetchone("SELECT * FROM raw_materials WHERE id=?;", (mid,))
        return dict(row) if row else None

    def _current_username(self) -> str:
        try:
            u = self.auth.get_current_user() if self.auth else None
            return getattr(u, "username", "") or ""
        except Exception:
            return ""

    def _log_movement(self, material_id: int, action_type: str,
                      quantity: float, reason: str, reference: str,
                      old_quantity: float = 0.0,
                      new_quantity: float = 0.0,
                      username: str = "") -> None:
        try:
            self.db.execute(
                """INSERT INTO raw_material_logs
                       (material_id, action_type, quantity, reason, reference,
                        old_quantity, new_quantity, username)
                   VALUES(?,?,?,?,?,?,?,?);""",
                (material_id, action_type, quantity, reason, reference,
                 float(old_quantity), float(new_quantity), str(username)),
            )
        except Exception:
            pass  # audit failures must never crash the app

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def _add_material(self):
        dlg = _MaterialDialog(self, self.db)
        if not dlg.result:
            return
        r = dlg.result
        try:
            self.db.execute(
                """INSERT INTO raw_materials
                       (name, material_type, unit, quantity, low_stock, active,
                        delivered_date, expiration_date)
                   VALUES(?,?,?,?,?,?,?,?);""",
                (r["name"], r["material_type"], r["unit"],
                 r["quantity"], r["low_stock"], r["active"],
                 r["delivered_date"], r["expiration_date"]),
            )
            if r["quantity"] > 0:
                new_id = self.db.fetchone(
                    "SELECT id FROM raw_materials WHERE name=?;", (r["name"],))
                if new_id:
                    self._log_movement(
                        int(new_id["id"]), "ADD",
                        r["quantity"], "Initial Stock", "",
                        old_quantity=0.0, new_quantity=float(r["quantity"]),
                        username=self._current_username(),
                    )
            self.refresh_materials()
            show_toast(self, f"Added '{r['name']}' successfully.")
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                messagebox.showwarning(
                    "Duplicate Name",
                    f"A material named \"{r['name']}\" already exists.\n"
                    "Please use a different name.",
                )
            else:
                messagebox.showerror("Error", f"Could not add material:\n{exc}")

    def _edit_material(self):
        mid = self._selected_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        dlg = _MaterialDialog(self, self.db, material=mat)
        if not dlg.result:
            return
        r = dlg.result
        try:
            self.db.execute(
                """UPDATE raw_materials
                   SET name=?, material_type=?, unit=?, quantity=?, low_stock=?,
                       active=?, delivered_date=?, expiration_date=?,
                       updated_at=datetime('now','localtime')
                   WHERE id=?;""",
                (r["name"], r["material_type"], r["unit"],
                 r["quantity"], r["low_stock"], r["active"],
                 r["delivered_date"], r["expiration_date"], mid),
            )
            self.refresh_materials()
            show_toast(self, f"Updated '{r['name']}' successfully.")
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                messagebox.showwarning(
                    "Duplicate Name",
                    f"A material named \"{r['name']}\" already exists.\n"
                    "Please use a different name.",
                )
            else:
                messagebox.showerror("Error", f"Could not update material:\n{exc}")

    def _toggle_active(self):
        mid = self._selected_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        cur = int(_safe(mat, "active", 1))
        action = "Deactivate" if cur else "Activate"
        name = _safe(mat, "name", "")
        if not messagebox.askyesno(action, f"{action} '{name}'?"):
            return
        try:
            self.db.execute(
                "UPDATE raw_materials SET active=? WHERE id=?;",
                (0 if cur else 1, mid),
            )
            self.refresh_materials()
            show_toast(self, f"'{name}' {'activated' if not cur else 'deactivated'}.")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not update:\n{exc}")

    def _delete_material(self):
        mid = self._selected_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        name = _safe(mat, "name", "material")
        if not messagebox.askyesno("Delete Material",
                                   f"Permanently delete '{name}'?\n\nThis cannot be undone."):
            return
        try:
            self.db.execute("DELETE FROM raw_materials WHERE id=?;", (mid,))
            self.refresh_materials()
            show_toast(self, f"'{name}' deleted successfully.")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not delete:\n{exc}")

    # ── Stock movements ────────────────────────────────────────────────────────

    def _add_stock(self):
        mid = self._selected_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        cur  = float(_safe(mat, "quantity", 0))
        unit = _safe(mat, "unit", "")
        name = _safe(mat, "name", "")
        dlg = _StockMovementDialog(self, mat_name=name, current_qty=cur,
                                   unit=unit, action="ADD")
        if not dlg.result:
            return
        qty = dlg.result["quantity"]
        try:
            self.db.execute(
                "UPDATE raw_materials SET quantity=quantity+?, "
                "updated_at=datetime('now','localtime') WHERE id=?;",
                (qty, mid),
            )
            self._log_movement(
                mid, "ADD", qty,
                dlg.result["reason"], dlg.result["reference"],
                old_quantity=float(cur),
                new_quantity=float(cur + qty),
                username=self._current_username(),
            )
            self.refresh_materials()
            show_toast(
                self,
                f"Added {qty:.2f} {unit} to '{name}' — new total {cur + qty:.2f} {unit}",
            )
        except Exception as exc:
            from app.utils import log_error
            log_error("Add stock", exc)
            messagebox.showerror("Error", "Could not add stock. Please try again.")

    def _deduct_stock(self):
        mid = self._selected_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        cur  = float(_safe(mat, "quantity", 0))
        unit = _safe(mat, "unit", "")
        name = _safe(mat, "name", "")
        dlg = _StockMovementDialog(self, mat_name=name, current_qty=cur,
                                   unit=unit, action="DEDUCT")
        if not dlg.result:
            return
        qty = dlg.result["quantity"]

        # Re-read stock in case it changed while dialog was open
        fresh_row = self.db.fetchone(
            "SELECT quantity FROM raw_materials WHERE id=?;", (mid,))
        fresh = float(fresh_row["quantity"]) if fresh_row else 0.0
        if qty > fresh:
            messagebox.showerror(
                "Insufficient Stock",
                f"Cannot deduct {qty:.2f} — only {fresh:.2f} {unit} available now.",
            )
            return
        try:
            new_total = max(0.0, fresh - qty)
            self.db.execute(
                "UPDATE raw_materials SET quantity=MAX(0, quantity-?), "
                "updated_at=datetime('now','localtime') WHERE id=?;",
                (qty, mid),
            )
            self._log_movement(
                mid, "DEDUCT", qty,
                dlg.result["reason"], dlg.result["reference"],
                old_quantity=float(fresh),
                new_quantity=float(new_total),
                username=self._current_username(),
            )
            self.refresh_materials()
            show_toast(
                self,
                f"Deducted {qty:.2f} {unit} from '{name}' — new total {new_total:.2f} {unit}",
            )
        except Exception as exc:
            from app.utils import log_error
            log_error("Deduct stock", exc)
            messagebox.showerror("Error", "Could not deduct stock. Please try again.")

    def _view_history(self):
        mid = self._selected_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        _HistoryDialog(self, self.db, mid, _safe(mat, "name", "Material"))
