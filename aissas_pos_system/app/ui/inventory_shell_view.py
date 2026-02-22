from __future__ import annotations

import tkinter as tk

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO, DraftDAO
from app.services.auth_service import AuthService
from app.ui.inventory_products_view import InventoryProductsView
from app.ui.inventory_sales_view import InventorySalesView


class InventoryShellView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService, go_transactions_cb, go_pos_cb):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.go_transactions_cb = go_transactions_cb
        self.go_pos_cb = go_pos_cb

        self.orders = OrderDAO(db)
        self.drafts = DraftDAO(db)

        self.sidebar = tk.Frame(self, bg="#ffffff")
        self.main = tk.Frame(self, bg=THEME["bg"])

        self.sidebar.pack(side="left", fill="y")
        self.main.pack(side="left", fill="both", expand=True)

        self._active = None
        self._btns = {}

        self._build_sidebar()
        self.show_overview()

    def _build_sidebar(self):
        items = [
            ("overview", "Overview", self.show_overview),
            ("sales", "Sales", self.show_sales),
            ("products", "Products", self.show_products),
        ]
        for key, text, cmd in items:
            b = tk.Button(
                self.sidebar, text=text, command=cmd,
                bg="#ffffff", fg=THEME["text"], bd=0, padx=16, pady=10,
                anchor="w", cursor="hand2", font=("Segoe UI", 10, "bold" if key == "overview" else "normal"),
            )
            b.pack(fill="x", padx=10, pady=4)
            self._btns[key] = b

    def _set_active(self, key: str):
        self._active = key
        for k, b in self._btns.items():
            b.configure(bg="#e9efff" if k == key else "#ffffff")

    def _clear_main(self):
        for w in self.main.winfo_children():
            w.destroy()

    def show_overview(self):
        self._set_active("overview")
        self._clear_main()

        wrap = tk.Frame(self.main, bg=THEME["bg"])
        wrap.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(wrap, text="Dashboard", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(0, 14))

        # REAL COUNTS
        completed = self.orders.count_by_status("Completed")
        pending = self.orders.count_by_status("Pending")
        drafts = self.drafts.count_drafts()

        cards = tk.Frame(wrap, bg=THEME["bg"])
        cards.pack(fill="x")

        def card(title: str, value: int, subtitle: str, cmd):
            c = tk.Frame(cards, bg="#ffffff", highlightthickness=1, highlightbackground="#e6e6e6")
            c.pack(side="left", expand=True, fill="x", padx=8)
            c.bind("<Button-1>", lambda _e: cmd())
            tk.Label(c, text=title, bg="#ffffff", fg=THEME["muted"]).pack(pady=(12, 6))
            tk.Label(c, text=str(value), bg="#ffffff", fg=THEME["text"], font=("Segoe UI", 18, "bold")).pack()
            tk.Label(c, text=subtitle, bg="#ffffff", fg=THEME["muted"]).pack(pady=(6, 12))

        # Clicking cards directs to related tab
        card("Completed orders", completed, "Success", lambda: self._go_transactions_filtered("Completed"))
        card("Drafts", drafts, "In Progress", self.go_pos_cb)  # Navigate to POS to see/manage drafts
        card("Pending Payment", pending, "Attention", lambda: self._go_transactions_filtered("Pending"))

    def _go_transactions_filtered(self, status: str):
        # send user to Transactions tab; filtering is handled there by user (we can extend later to auto-filter)
        self.go_transactions_cb()

    def show_sales(self):
        self._set_active("sales")
        self._clear_main()
        InventorySalesView(self.main, self.db, self.auth).pack(fill="both", expand=True)

    def show_products(self):
        self._set_active("products")
        self._clear_main()
        InventoryProductsView(self.main, self.db, self.auth).pack(fill="both", expand=True)