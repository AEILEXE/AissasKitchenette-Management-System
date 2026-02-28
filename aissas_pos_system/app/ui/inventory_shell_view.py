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
from app.ui.transactions_view import TransactionDetailsDialog
from app.utils import money


def _safe(r, key, default=None):
    try:
        v = r[key]
        return default if v is None else v
    except Exception:
        return default


def _bind_mousewheel(canvas: tk.Canvas) -> None:
    """Bind scroll only while mouse is inside canvas (avoids stale-widget crash)."""
    def _scroll(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))


class InventoryShellView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService,
                 go_transactions_cb, go_pos_cb):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.go_transactions_cb = go_transactions_cb
        self.go_pos_cb = go_pos_cb

        self.orders   = OrderDAO(db)
        self.drafts   = DraftDAO(db)
        self.products = ProductDAO(db)

        # ── Sidebar ───────────────────────────────────────────────────────────
        self.sidebar = tk.Frame(self, bg=THEME["panel"],
                                highlightthickness=1,
                                highlightbackground=THEME["border"],
                                width=170)
        self.main = tk.Frame(self, bg=THEME["bg"])

        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.main.pack(side="left", fill="both", expand=True)

        self._active: str | None = None
        self._btns: dict[str, tk.Frame] = {}

        self._build_sidebar()
        self.show_overview()

    # Sidebar

    def _build_sidebar(self):
        hdr = tk.Frame(self.sidebar, bg=THEME["brown_dark"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Inventory",
            bg=THEME["brown_dark"], fg="white",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=14, pady=14)

        nav_items = [
            ("overview", "Overview",  self.show_overview),
            ("sales",    "Sales",     self.show_sales),
            ("products", "Products",  self.show_products),
        ]
        for key, text, cmd in nav_items:
            row = tk.Frame(self.sidebar, bg=THEME["panel"], cursor="hand2")
            row.pack(fill="x", pady=1)

            lbl = tk.Label(
                row, text=text,
                bg=THEME["panel"], fg=THEME["text"],
                font=("Segoe UI", 10),
                anchor="w", padx=14, pady=10,
            )
            lbl.pack(fill="x")

            # Make entire row clickable
            row.bind("<Button-1>", lambda _e, c=cmd: c())
            lbl.bind("<Button-1>", lambda _e, c=cmd: c())

            self._btns[key] = row

    def _set_active(self, key: str):
        self._active = key
        for k, row in self._btns.items():
            is_active = k == key
            bg = THEME["beige"] if is_active else THEME["panel"]
            fg = THEME["brown"] if is_active else THEME["text"]
            fw = "bold" if is_active else "normal"
            row.configure(bg=bg)
            for w in row.winfo_children():
                if isinstance(w, tk.Label):
                    w.configure(bg=bg, fg=fg, font=("Segoe UI", 10, fw))

    def _clear_main(self):
        for w in self.main.winfo_children():
            w.destroy()

    # Overview / Dashboard

    def show_overview(self):
        self._set_active("overview")
        self._clear_main()

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
        win  = canvas.create_window((0, 0), window=wrap, anchor="nw")
        wrap.bind("<Configure>",
                  lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win, width=e.width))
        _bind_mousewheel(canvas)

        self._build_dashboard_content(wrap)

    def _build_dashboard_content(self, wrap: tk.Frame):
        # Header
        hdr = tk.Frame(wrap, bg=THEME["bg"])
        hdr.pack(fill="x", padx=20, pady=(18, 14))
        hdr.columnconfigure(0, weight=1)

        tk.Label(
            hdr, text="Dashboard",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Button(
            hdr, text="\u21ba  Refresh",
            command=self.show_overview,
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=12, pady=6, cursor="hand2",
            font=("Segoe UI", 9),
        ).grid(row=0, column=1, sticky="e")

        # ── Fetch data ────────────────────────────────────────────────────────
        today_row = self.orders.summary_today() or {}
        month_row = self.orders.summary_month() or {}

        today_sales = float(_safe(today_row, "total_sales", 0.0))
        today_count = int(_safe(today_row, "order_count", 0))
        month_sales = float(_safe(month_row, "total_sales", 0.0))
        month_count = int(_safe(month_row, "order_count", 0))

        completed_all = self.orders.count_by_status("Completed")
        pending_all   = self.orders.count_by_status("Pending")
        total_txns    = completed_all + pending_all

        try:
            active_products = self.products.count_active()
        except Exception:
            active_products = 0

        try:
            draft_count = self.drafts.count_drafts()
        except Exception:
            draft_count = 0

        try:
            unavail_count = self.products.count_unavailable()
        except Exception:
            unavail_count = 0

        # ── Row 1: 4 cards ────────────────────────────────────────────────────
        row1 = tk.Frame(wrap, bg=THEME["bg"])
        row1.pack(fill="x", padx=20, pady=(0, 10))
        for i in range(4):
            row1.columnconfigure(i, weight=1, uniform="card1")

        cards_row1 = [
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
                f"{pending_all} pending",
                THEME["warning"],
                self.go_transactions_cb,
            ),
        ]
        for col, (title, value, sub, accent, cmd) in enumerate(cards_row1):
            self._make_summary_card(row1, col, title, value, sub, accent, cmd)

        # ── Row 2: Draft Count + Not Available ────────────────────────────────
        row2 = tk.Frame(wrap, bg=THEME["bg"])
        row2.pack(fill="x", padx=20, pady=(0, 20))
        for i in range(2):
            row2.columnconfigure(i, weight=1, uniform="card2")

        cards_row2 = [
            (
                "Draft Orders",
                str(draft_count),
                "saved in POS drafts",
                "#7c3aed",
                self.go_pos_cb,
            ),
            (
                "Not Available",
                str(unavail_count),
                "products hidden from POS",
                THEME["danger"],
                self.show_products,
            ),
        ]
        for col, (title, value, sub, accent, cmd) in enumerate(cards_row2):
            self._make_summary_card(row2, col, title, value, sub, accent, cmd)

        # ── Recent Transactions ───────────────────────────────────────────────
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
            sec_hdr, text="View all \u2192",
            command=self.go_transactions_cb,
            bg=THEME["bg"], fg=THEME["brown"],
            bd=0, cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        ).pack(side="right", padx=(0, 2))

        tbl_frame = tk.Frame(sec, bg=THEME["panel"],
                             highlightthickness=1, highlightbackground=THEME["border"])
        tbl_frame.pack(fill="both", expand=True)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Dash.Treeview", rowheight=30, font=("Segoe UI", 9),
                         background=THEME["panel"], fieldbackground=THEME["panel"])
        style.configure("Dash.Treeview.Heading", font=("Segoe UI", 9, "bold"),
                         background=THEME["beige"], foreground=THEME["text"])
        style.map("Dash.Treeview",
                  background=[("selected", THEME["select_bg"])],
                  foreground=[("selected", THEME["select_fg"])])

        cols = ("id", "date", "payment", "total", "status")
        tbl = ttk.Treeview(tbl_frame, columns=cols, show="headings",
                           style="Dash.Treeview", height=11)
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
            tbl.column(cid, width=width, minwidth=width, anchor=anchor, stretch=stretch)

        tbl.tag_configure("Completed", foreground=THEME["success"])
        tbl.tag_configure("Pending",   foreground=THEME["warning"])
        tbl.tag_configure("Cancelled", foreground=THEME["muted"])
        tbl.tag_configure("best_today", background="#FFF3CD", foreground=THEME["brown_dark"])

        def _open_order(_event=None):
            sel = tbl.selection()
            if not sel:
                return
            try:
                oid = int(sel[0])
                TransactionDetailsDialog(self, self.db, oid)
            except Exception:
                pass

        tbl.bind("<Double-Button-1>", _open_order)
        tbl.bind("<Return>", _open_order)

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
            pay    = str(_safe(r, "payment_method", "\u2014"))
            total  = float(_safe(r, "total", 0.0))
            status = str(_safe(r, "status", ""))
            try:
                order_date = _dt.datetime.fromisoformat(dt_str).date()
                if (order_date == today_date and status == "Completed"
                        and total > highest_today_total):
                    highest_today_total = total
                    highest_today_id = oid
            except Exception:
                pass
            tag = status if status in ("Completed", "Pending", "Cancelled") else ""
            tbl.insert("", tk.END, iid=str(oid),
                       values=(f"#{oid}", dt_str, pay, money(total), status),
                       tags=(tag,))

        if highest_today_id is not None:
            tbl.item(str(highest_today_id), tags=("best_today",))

        if recent:
            r0        = recent[0]
            latest_id = int(_safe(r0, "order_id", 0))
            latest_dt = str(_safe(r0, "start_dt", ""))
            info = f"Latest: #{latest_id}  \u00b7  {latest_dt}"
            if highest_today_id is not None:
                info += f"     |     Highest today: #{highest_today_id}  ({money(highest_today_total)})"
            tk.Label(sec, text=info, bg=THEME["bg"], fg=THEME["muted"],
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))

    # ── Summary card ──────────────────────────────────────────────────────────

    def _make_summary_card(self, parent: tk.Frame, col: int,
                           title: str, value: str, subtitle: str,
                           accent: str, cmd):
        pad_left = 0 if col == 0 else 8
        card = tk.Frame(parent, bg=THEME["panel"],
                        highlightthickness=1, highlightbackground=THEME["border"],
                        cursor="hand2")
        card.grid(row=0, column=col, sticky="ew", padx=(pad_left, 0), pady=4)
        card.bind("<Button-1>", lambda _e: cmd())

        bar = tk.Frame(card, bg=accent, height=4)
        bar.pack(fill="x")
        bar.bind("<Button-1>", lambda _e: cmd())

        lbl_title = tk.Label(card, text=title, bg=THEME["panel"], fg=THEME["muted"],
                             font=("Segoe UI", 9))
        lbl_title.pack(anchor="w", padx=14, pady=(10, 2))
        lbl_title.bind("<Button-1>", lambda _e: cmd())

        lbl_value = tk.Label(card, text=value, bg=THEME["panel"], fg=accent,
                             font=("Segoe UI", 18, "bold"))
        lbl_value.pack(anchor="w", padx=14)
        lbl_value.bind("<Button-1>", lambda _e: cmd())

        lbl_sub = tk.Label(card, text=subtitle, bg=THEME["panel"], fg=THEME["muted"],
                           font=("Segoe UI", 8))
        lbl_sub.pack(anchor="w", padx=14, pady=(2, 12))
        lbl_sub.bind("<Button-1>", lambda _e: cmd())

    # =========================================================================
    # Navigation helpers
    # =========================================================================

    def _go_transactions_filtered(self, status: str):
        self.go_transactions_cb()

    def show_sales(self):
        self._set_active("sales")
        self._clear_main()
        InventorySalesView(self.main, self.db, self.auth).pack(fill="both", expand=True)

    def show_products(self):
        self._set_active("products")
        self._clear_main()
        InventoryProductsView(self.main, self.db, self.auth).pack(fill="both", expand=True)
