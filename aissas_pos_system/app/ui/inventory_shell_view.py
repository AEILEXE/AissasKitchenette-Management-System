from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO, DraftDAO, ProductDAO
from app.services.auth_service import AuthService
from app.ui.inventory_products_view import InventoryProductsView
from app.ui.inventory_sales_view import InventorySalesView
from app.utils import money


def _safe(r, key, default=None):
    """Safe access for sqlite3.Row (no .get())."""
    try:
        v = r[key]
        return default if v is None else v
    except Exception:
        return default


class InventoryShellView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService, go_transactions_cb, go_pos_cb):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.go_transactions_cb = go_transactions_cb
        self.go_pos_cb = go_pos_cb

        self.orders = OrderDAO(db)
        self.drafts = DraftDAO(db)
        self.products = ProductDAO(db)

        # Fixed-width sidebar
        self.sidebar = tk.Frame(self, bg="#ffffff", width=160)
        self.main = tk.Frame(self, bg=THEME["bg"])

        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.main.pack(side="left", fill="both", expand=True)

        self._active: str | None = None
        self._btns: dict[str, tk.Button] = {}

        self._build_sidebar()
        self.show_overview()

    # =========================================================================
    # Sidebar
    # =========================================================================

    def _build_sidebar(self):
        # Dark header strip in sidebar
        hdr = tk.Frame(self.sidebar, bg=THEME["brown_dark"], height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="Inventory",
            bg=THEME["brown_dark"], fg="white",
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=14)

        nav_items = [
            ("overview", "  Overview",  self.show_overview),
            ("sales",    "  Sales",     self.show_sales),
            ("products", "  Products",  self.show_products),
        ]
        for key, text, cmd in nav_items:
            b = tk.Button(
                self.sidebar, text=text, command=cmd,
                bg="#ffffff", fg=THEME["text"], bd=0,
                padx=8, pady=10,
                anchor="w", cursor="hand2",
                font=("Segoe UI", 10),
            )
            b.pack(fill="x", padx=6, pady=2)
            self._btns[key] = b

    def _set_active(self, key: str):
        self._active = key
        for k, b in self._btns.items():
            if k == key:
                b.configure(
                    bg=THEME["beige"],
                    fg=THEME["brown"],
                    font=("Segoe UI", 10, "bold"),
                )
            else:
                b.configure(
                    bg="#ffffff",
                    fg=THEME["text"],
                    font=("Segoe UI", 10),
                )

    def _clear_main(self):
        for w in self.main.winfo_children():
            w.destroy()

    # =========================================================================
    # Overview / Dashboard
    # =========================================================================

    def show_overview(self):
        self._set_active("overview")
        self._clear_main()

        # Wrap in a scrollable canvas so the dashboard works on small screens
        outer = tk.Frame(self.main, bg=THEME["bg"])
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=THEME["bg"], highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=sb.set)

        wrap = tk.Frame(canvas, bg=THEME["bg"])
        win = canvas.create_window((0, 0), window=wrap, anchor="nw")
        wrap.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win, width=e.width),
        )

        def _mw(e):
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        canvas.bind_all("<MouseWheel>", _mw)

        self._build_dashboard_content(wrap)

    def _build_dashboard_content(self, wrap: tk.Frame):
        # ------------------------------------------------------------------ #
        # Header row                                                           #
        # ------------------------------------------------------------------ #
        hdr = tk.Frame(wrap, bg=THEME["bg"])
        hdr.pack(fill="x", padx=20, pady=(18, 14))
        hdr.columnconfigure(0, weight=1)

        tk.Label(
            hdr, text="Dashboard",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Button(
            hdr, text="↺  Refresh",
            command=self.show_overview,
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=12, pady=6, cursor="hand2",
            font=("Segoe UI", 9),
        ).grid(row=0, column=1, sticky="e")

        # ------------------------------------------------------------------ #
        # Fetch summary data                                                   #
        # ------------------------------------------------------------------ #
        today_row = self.orders.summary_today() or {}
        month_row = self.orders.summary_month() or {}

        today_sales  = float(_safe(today_row, "total_sales", 0.0))
        today_count  = int(_safe(today_row, "order_count", 0))
        month_sales  = float(_safe(month_row, "total_sales", 0.0))
        month_count  = int(_safe(month_row, "order_count", 0))

        completed_all = self.orders.count_by_status("Completed")
        pending_all   = self.orders.count_by_status("Pending")
        total_txns    = completed_all + pending_all

        try:
            active_products = self.products.count_active()
        except Exception:
            active_products = 0

        # ------------------------------------------------------------------ #
        # Summary cards (4 across)                                            #
        # ------------------------------------------------------------------ #
        cards_row = tk.Frame(wrap, bg=THEME["bg"])
        cards_row.pack(fill="x", padx=20, pady=(0, 20))
        for i in range(4):
            cards_row.columnconfigure(i, weight=1, uniform="scard")

        txn_sub = f"{pending_all} pending"
        cards_data = [
            (
                "Sales Today",
                money(today_sales),
                f"{today_count} order{'s' if today_count != 1 else ''}",
                THEME["success"],
                lambda: self._go_transactions_filtered("Completed"),
            ),
            (
                "Sales This Month",
                money(month_sales),
                f"{month_count} order{'s' if month_count != 1 else ''}",
                THEME["brown"],
                lambda: self._go_transactions_filtered("Completed"),
            ),
            (
                "Active Products",
                str(active_products),
                "in menu",
                THEME["accent"],
                self.show_products,
            ),
            (
                "Total Transactions",
                str(total_txns),
                txn_sub,
                THEME["warning"],
                self.go_transactions_cb,
            ),
        ]

        for col, (title, value, subtitle, accent, cmd) in enumerate(cards_data):
            self._make_summary_card(cards_row, col, title, value, subtitle, accent, cmd)

        # ------------------------------------------------------------------ #
        # Recent Transactions section                                          #
        # ------------------------------------------------------------------ #
        sec = tk.Frame(wrap, bg=THEME["bg"])
        sec.pack(fill="both", expand=True, padx=20, pady=(0, 22))

        sec_hdr = tk.Frame(sec, bg=THEME["bg"])
        sec_hdr.pack(fill="x", pady=(0, 8))

        tk.Label(
            sec_hdr, text="Recent Transactions",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")

        tk.Button(
            sec_hdr, text="View all →",
            command=self.go_transactions_cb,
            bg=THEME["bg"], fg=THEME["brown"],
            bd=0, cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        ).pack(side="right", padx=(0, 2))

        # Table container
        tbl_frame = tk.Frame(
            sec, bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        tbl_frame.pack(fill="both", expand=True)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        # Configure ttk style for the table
        style = ttk.Style()
        style.configure(
            "Dash.Treeview",
            rowheight=30,
            font=("Segoe UI", 9),
            background=THEME["panel"],
            fieldbackground=THEME["panel"],
        )
        style.configure(
            "Dash.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=THEME["beige"],
            foreground=THEME["text"],
        )
        style.map(
            "Dash.Treeview",
            background=[("selected", THEME["select_bg"])],
            foreground=[("selected", THEME["select_fg"])],
        )

        cols = ("id", "date", "payment", "total", "status")
        tbl = ttk.Treeview(
            tbl_frame, columns=cols, show="headings",
            style="Dash.Treeview", height=11,
        )
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        col_cfg = [
            ("id",      "#",           55,  "center", False),
            ("date",    "Date & Time", 170, "w",      True),
            ("payment", "Payment",     130, "center", False),
            ("total",   "Total",       105, "e",      False),
            ("status",  "Status",      100, "center", False),
        ]
        for cid, heading, width, anchor, stretch in col_cfg:
            tbl.heading(cid, text=heading)
            tbl.column(cid, width=width, minwidth=width,
                       anchor=anchor, stretch=stretch)

        # Row colour tags
        tbl.tag_configure("Completed", foreground=THEME["success"])
        tbl.tag_configure("Pending",   foreground=THEME["warning"])
        tbl.tag_configure("Cancelled", foreground=THEME["muted"])
        tbl.tag_configure(
            "best_today",
            background="#FFF3CD",
            foreground=THEME["brown_dark"],
        )

        # ------ Populate table ------ #
        try:
            recent = self.orders.list_recent(10)
        except Exception:
            recent = []

        today_date = _dt.date.today()
        highest_today_id: int | None = None
        highest_today_total: float = -1.0

        for r in recent:
            oid    = int(_safe(r, "order_id", 0))
            dt_str = str(_safe(r, "start_dt", ""))
            pay    = str(_safe(r, "payment_method", "—"))
            total  = float(_safe(r, "total", 0.0))
            status = str(_safe(r, "status", ""))

            # Check if this is the highest-value completed order today
            try:
                order_date = _dt.datetime.fromisoformat(dt_str).date()
                if (order_date == today_date
                        and status == "Completed"
                        and total > highest_today_total):
                    highest_today_total = total
                    highest_today_id = oid
            except Exception:
                pass

            tag = status if status in ("Completed", "Pending", "Cancelled") else ""
            tbl.insert(
                "", tk.END, iid=str(oid),
                values=(f"#{oid}", dt_str, pay, money(total), status),
                tags=(tag,),
            )

        # Re-tag the best-today row (overrides the status colour)
        if highest_today_id is not None:
            tbl.item(str(highest_today_id), tags=("best_today",))

        # Info strip below table
        if recent:
            r0      = recent[0]
            latest_id  = int(_safe(r0, "order_id", 0))
            latest_dt  = str(_safe(r0, "start_dt", ""))
            info = f"Latest: #{latest_id}  ·  {latest_dt}"
            if highest_today_id is not None:
                info += (
                    f"     |     Highest today: "
                    f"#{highest_today_id}  ({money(highest_today_total)})"
                )
            tk.Label(
                sec, text=info,
                bg=THEME["bg"], fg=THEME["muted"],
                font=("Segoe UI", 8),
            ).pack(anchor="w", pady=(6, 0))

    # -------------------------------------------------------------------------
    # Summary card helper
    # -------------------------------------------------------------------------

    def _make_summary_card(
        self, parent: tk.Frame, col: int,
        title: str, value: str, subtitle: str,
        accent: str, cmd,
    ):
        pad_left = 0 if col == 0 else 8
        card = tk.Frame(
            parent, bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
            cursor="hand2",
        )
        card.grid(row=0, column=col, sticky="ew",
                  padx=(pad_left, 0), pady=4)
        card.bind("<Button-1>", lambda _e: cmd())

        # Thin coloured top bar
        bar = tk.Frame(card, bg=accent, height=4)
        bar.pack(fill="x")
        bar.bind("<Button-1>", lambda _e: cmd())

        tk.Label(
            card, text=title,
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=14, pady=(10, 2))

        tk.Label(
            card, text=value,
            bg=THEME["panel"], fg=accent,
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", padx=14)

        tk.Label(
            card, text=subtitle,
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=14, pady=(2, 12))

    # =========================================================================
    # Navigation helpers
    # =========================================================================

    def _go_transactions_filtered(self, status: str):
        # Navigate to Transactions tab; filtering is up to the user there
        self.go_transactions_cb()

    def show_sales(self):
        self._set_active("sales")
        self._clear_main()
        InventorySalesView(self.main, self.db, self.auth).pack(fill="both", expand=True)

    def show_products(self):
        self._set_active("products")
        self._clear_main()
        InventoryProductsView(self.main, self.db, self.auth).pack(fill="both", expand=True)
