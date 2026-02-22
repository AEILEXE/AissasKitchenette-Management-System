from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from app.config import THEME
from app.db.database import Database
from app.db.dao import ProductDAO
from app.services.auth_service import AuthService
from app.services.inventory_service import InventoryService
from app.constants import P_INV_MANAGE
from app.utils import money


def _row_value(r, key: str, default=None):
    """Safe access for sqlite3.Row (no .get())."""
    try:
        v = r[key]
        return default if v is None else v
    except Exception:
        return default


class InventoryView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.prod_dao = ProductDAO(db)
        self.inv = InventoryService(db)

        self.search_var = tk.StringVar()

        self._build()
        self.refresh()

    def _build(self):
        # responsive
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header row
        header = tk.Frame(self, bg=THEME["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        header.columnconfigure(1, weight=1)

        tk.Label(
            header, text="Inventory",
            font=("Segoe UI", 18, "bold"),
            bg=THEME["bg"], fg=THEME["text"]
        ).grid(row=0, column=0, sticky="w")

        search = tk.Entry(
            header, textvariable=self.search_var,
            bd=0, bg=THEME["panel2"], fg=THEME["text"]
        )
        search.grid(row=0, column=1, sticky="ew", padx=(14, 0), ipady=8)
        search.bind("<KeyRelease>", lambda _e: self.refresh())

        # Table wrapper
        table_wrap = tk.Frame(self, bg=THEME["bg"])
        table_wrap.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Treeview", rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        # ✅ Removed "Stock" column
        cols = ("name", "cat", "price", "status", "low", "active")
        self.tbl = ttk.Treeview(table_wrap, columns=cols, show="headings")
        self.tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        xsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tbl.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        self.tbl.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        headings = [
            ("name", "Item"),
            ("cat", "Category"),
            ("price", "Price"),
            ("status", "Status"),   # Available / Not Available
            ("low", "Low"),
            ("active", "Active"),
        ]
        for c, t in headings:
            self.tbl.heading(c, text=t)

        self.tbl.column("name", width=280, minwidth=180, stretch=True)
        self.tbl.column("cat", width=180, minwidth=140, stretch=True)
        self.tbl.column("price", width=100, minwidth=90, stretch=False, anchor="e")
        self.tbl.column("status", width=140, minwidth=120, stretch=False, anchor="center")
        self.tbl.column("low", width=70, minwidth=60, stretch=False, anchor="center")
        self.tbl.column("active", width=70, minwidth=60, stretch=False, anchor="center")

        # ✅ Tag colors: inactive = red, low stock = red-ish
        # (Treeview allows tag_configure directly)
        self.tbl.tag_configure("inactive", background="#c0392b", foreground="white")  # RED
        self.tbl.tag_configure("low", background="#e74c3c", foreground="white")       # RED (low stock)
        self.tbl.tag_configure("out", background="#8e44ad", foreground="white")       # optional (out of stock)

        # Controls
        controls = tk.Frame(self, bg=THEME["bg"])
        controls.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        controls.columnconfigure(10, weight=1)

        tk.Label(controls, text="Qty:", bg=THEME["bg"], fg=THEME["text"]).grid(row=0, column=0, sticky="w")
        self.ent_qty = tk.Entry(controls, width=10, bd=0, bg=THEME["panel2"], fg=THEME["text"])
        self.ent_qty.grid(row=0, column=1, sticky="w", padx=(6, 14), ipady=6)

        tk.Button(
            controls, text="Restock (+)", command=self.restock,
            bg=THEME["brown"], fg="white", bd=0, padx=12, pady=8, cursor="hand2"
        ).grid(row=0, column=2, sticky="w", padx=(0, 10))

        tk.Button(
            controls, text="Set Stock", command=self.set_stock,
            bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, cursor="hand2"
        ).grid(row=0, column=3, sticky="w")

        tk.Button(
            controls, text="Refresh", command=self.refresh,
            bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, cursor="hand2"
        ).grid(row=0, column=11, sticky="e")

    def refresh(self):
        for iid in self.tbl.get_children():
            self.tbl.delete(iid)

        q = (self.search_var.get() or "").strip().lower()

        rows = self.prod_dao.list_all()
        for r in rows:
            pid = int(r["product_id"])
            name = str(_row_value(r, "name", ""))
            cat = str(_row_value(r, "category", ""))
            price = float(_row_value(r, "price", 0.0))
            stock_qty = int(_row_value(r, "stock_qty", 0))
            low_stock = int(_row_value(r, "low_stock", 0))
            active = int(_row_value(r, "active", 1))

            if q and (q not in name.lower() and q not in cat.lower()):
                continue

            status = "Available" if stock_qty > 0 else "Not Available"

            tags = []
            # ✅ Inactive items = RED
            if active == 0:
                tags.append("inactive")
            else:
                # ✅ Low stock highlighting (stock <= low) BUT we removed stock column, still works visually
                if stock_qty == 0:
                    tags.append("out")
                elif stock_qty <= low_stock and low_stock > 0:
                    tags.append("low")

            self.tbl.insert(
                "",
                tk.END,
                iid=str(pid),
                values=(name, cat, money(price), status, low_stock, active),
                tags=tuple(tags),
            )

    def restock(self):
        if not self.auth.has_permission(P_INV_MANAGE):
            messagebox.showerror("Access denied", "You cannot modify inventory.")
            return
        sel = self.tbl.selection()
        if not sel:
            return
        pid = int(sel[0])

        try:
            qty = int(self.ent_qty.get().strip())
            if qty <= 0:
                raise ValueError()
        except Exception:
            messagebox.showerror("Qty", "Invalid qty. Enter a number greater than 0.")
            return

        self.inv.restock(pid, qty)
        self.refresh()

    def set_stock(self):
        if not self.auth.has_permission(P_INV_MANAGE):
            messagebox.showerror("Access denied", "You cannot modify inventory.")
            return
        sel = self.tbl.selection()
        if not sel:
            return
        pid = int(sel[0])

        try:
            qty = int(self.ent_qty.get().strip())
            if qty < 0:
                raise ValueError()
        except Exception:
            messagebox.showerror("Qty", "Invalid qty. Enter a number 0 or higher.")
            return

        self.inv.adjust(pid, qty)
        self.refresh()