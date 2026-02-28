from __future__ import annotations

import datetime as _dt
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO, DraftDAO, ProductDAO
from app.services.auth_service import AuthService
from app.ui.inventory_products_view import InventoryProductsView
from app.ui.inventory_sales_view import InventorySalesView
from app.ui.transactions_view import TransactionDetailsDialog
from app.utils import money
from app.constants import P_MANAGE_PRODS, P_MANAGE_USERS, P_DATABASE, P_EXPORT


def _safe(r, key, default=None):
    try:
        v = r[key]
        return default if v is None else v
    except Exception:
        return default


def _bind_mousewheel(canvas: tk.Canvas) -> None:
    """Bind scroll only while mouse is inside canvas."""
    def _scroll(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))


class InventoryShellView(tk.Frame):
    """
    B: Inventory shell with a TOP navigation bar (Overview / Sales / Products).
    No left sidebar — content uses full width.
    """

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

        self._active: str | None = None
        self._tab_btns: dict[str, tk.Button] = {}

        self._build_topnav()

        self.content = tk.Frame(self, bg=THEME["bg"])
        self.content.pack(fill="both", expand=True)

        self.show_overview()

    # ── Top navigation bar ────────────────────────────────────────────────────

    def _build_topnav(self):
        nav = tk.Frame(self, bg=THEME["brown_dark"])
        nav.pack(fill="x")

        tk.Label(
            nav, text="Inventory",
            bg=THEME["brown_dark"], fg="white",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=(16, 20), pady=12)

        tab_items = [
            ("overview", "Overview",  self.show_overview),
            ("sales",    "Sales",     self.show_sales),
            ("products", "Products",  self.show_products),
        ]
        for key, text, cmd in tab_items:
            btn = tk.Button(
                nav, text=text,
                command=cmd,
                bg=THEME["brown_dark"],
                fg="white",
                activebackground=THEME["brown"],
                activeforeground="white",
                bd=0, padx=16, pady=10,
                cursor="hand2",
                font=("Segoe UI", 10),
                relief="flat",
            )
            btn.pack(side="left", padx=2, pady=4)
            self._tab_btns[key] = btn

    def _set_active(self, key: str):
        self._active = key
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.configure(bg=THEME["brown"], font=("Segoe UI", 10, "bold"))
            else:
                btn.configure(bg=THEME["brown_dark"], font=("Segoe UI", 10))

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    # ── Sub-view navigation ───────────────────────────────────────────────────

    def show_overview(self):
        self._set_active("overview")
        self._clear_content()
        self._build_overview()

    def show_sales(self):
        self._set_active("sales")
        self._clear_content()
        InventorySalesView(self.content, self.db, self.auth).pack(fill="both", expand=True)

    def show_products(self):
        self._set_active("products")
        self._clear_content()
        InventoryProductsView(self.content, self.db, self.auth).pack(fill="both", expand=True)

    # ── Overview (dashboard) ──────────────────────────────────────────────────

    def _build_overview(self):
        outer = tk.Frame(self.content, bg=THEME["bg"])
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
        wrap.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        _bind_mousewheel(canvas)

        self._build_dashboard_content(wrap)

    def _build_dashboard_content(self, wrap: tk.Frame):
        # Header
        hdr = tk.Frame(wrap, bg=THEME["bg"])
        hdr.pack(fill="x", padx=20, pady=(18, 14))
        hdr.columnconfigure(0, weight=1)
        tk.Label(hdr, text="Dashboard", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        tk.Button(hdr, text="\u21ba  Refresh", command=self.show_overview,
                  bg=THEME["panel2"], fg=THEME["text"],
                  bd=0, padx=12, pady=6, cursor="hand2",
                  font=("Segoe UI", 9)).grid(row=0, column=1, sticky="e")

        # Fetch data
        today_row  = self.orders.summary_today()  or {}
        month_row  = self.orders.summary_month()  or {}
        today_sales = float(_safe(today_row, "total_sales", 0.0))
        today_count = int(_safe(today_row, "order_count", 0))
        month_sales = float(_safe(month_row, "total_sales", 0.0))
        month_count = int(_safe(month_row, "order_count", 0))

        completed_all = self.orders.count_by_status("Completed")
        pending_all   = self.orders.count_by_status("Pending")
        total_txns    = completed_all + pending_all

        try: active_products = self.products.count_active()
        except Exception: active_products = 0
        try: draft_count = self.drafts.count_drafts()
        except Exception: draft_count = 0
        try: unavail_count = self.products.count_unavailable()
        except Exception: unavail_count = 0

        # Row 1: 4 KPI cards
        row1 = tk.Frame(wrap, bg=THEME["bg"])
        row1.pack(fill="x", padx=20, pady=(0, 10))
        for i in range(4): row1.columnconfigure(i, weight=1, uniform="card1")

        cards_row1 = [
            ("Sales Today",       money(today_sales),
             f"{today_count} order{'s' if today_count != 1 else ''}",
             THEME["success"],  lambda: self._go_transactions_filtered("Completed")),
            ("Sales This Month",  money(month_sales),
             f"{month_count} order{'s' if month_count != 1 else ''}",
             THEME["brown"],    lambda: self._go_transactions_filtered("Completed")),
            ("Active Products",   str(active_products), "in menu",
             THEME["accent"],   self.show_products),
            ("Total Transactions", str(total_txns), f"{pending_all} pending",
             THEME["warning"],  self.go_transactions_cb),
        ]
        for col, (title, value, sub, accent, cmd) in enumerate(cards_row1):
            self._make_summary_card(row1, col, title, value, sub, accent, cmd)

        # Row 2: Draft + Not Available
        row2 = tk.Frame(wrap, bg=THEME["bg"])
        row2.pack(fill="x", padx=20, pady=(0, 20))
        for i in range(2): row2.columnconfigure(i, weight=1, uniform="card2")

        cards_row2 = [
            ("Draft Orders",  str(draft_count),   "saved in POS drafts",
             "#7c3aed", self.go_pos_cb),
            ("Not Available", str(unavail_count), "products hidden from POS",
             THEME["danger"], self.show_products),
        ]
        for col, (title, value, sub, accent, cmd) in enumerate(cards_row2):
            self._make_summary_card(row2, col, title, value, sub, accent, cmd)

        self._build_recent_transactions(wrap)
        self._build_top_sellers(wrap)
        self._build_quick_actions(wrap)

    # ── Summary card ──────────────────────────────────────────────────────────

    def _make_summary_card(self, parent, col, title, value, subtitle, accent, cmd):
        pad_left = 0 if col == 0 else 8
        card = tk.Frame(parent, bg=THEME["panel"],
                        highlightthickness=1, highlightbackground=THEME["border"],
                        cursor="hand2")
        card.grid(row=0, column=col, sticky="ew", padx=(pad_left, 0), pady=4)
        card.bind("<Button-1>", lambda _e: cmd())

        bar = tk.Frame(card, bg=accent, height=4)
        bar.pack(fill="x")
        bar.bind("<Button-1>", lambda _e: cmd())

        for text, fg, fnt in [
            (title,    THEME["muted"], ("Segoe UI", 9)),
            (value,    accent,         ("Segoe UI", 18, "bold")),
            (subtitle, THEME["muted"], ("Segoe UI", 8)),
        ]:
            pady_val = (10, 2) if text == title else ((2, 12) if text == subtitle else 0)
            lbl = tk.Label(card, text=text, bg=THEME["panel"], fg=fg, font=fnt)
            lbl.pack(anchor="w", padx=14, pady=pady_val)
            lbl.bind("<Button-1>", lambda _e: cmd())

    # ── Recent Transactions ───────────────────────────────────────────────────

    def _build_recent_transactions(self, wrap: tk.Frame):
        sec = tk.Frame(wrap, bg=THEME["bg"])
        sec.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        sec_hdr = tk.Frame(sec, bg=THEME["bg"])
        sec_hdr.pack(fill="x", pady=(0, 8))
        tk.Label(sec_hdr, text="Recent Transactions", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Button(sec_hdr, text="View all \u2192", command=self.go_transactions_cb,
                  bg=THEME["bg"], fg=THEME["brown"], bd=0, cursor="hand2",
                  font=("Segoe UI", 9, "underline")).pack(side="right", padx=(0, 2))

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
                           style="Dash.Treeview", height=9)
        tbl.grid(row=0, column=0, sticky="nsew")
        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        # C: Aligned columns
        col_cfg = [
            ("id",      "#",           60,  "center", False),
            ("date",    "Date & Time", 180, "center", True),
            ("payment", "Payment",     130, "center", False),
            ("total",   "Total",       110, "e",      False),
            ("status",  "Status",      100, "center", False),
        ]
        for cid, heading, width, anchor, stretch in col_cfg:
            tbl.heading(cid, text=heading, anchor="center")
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
                TransactionDetailsDialog(self, self.db, int(sel[0]))
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
                if order_date == today_date and status == "Completed" and total > highest_today_total:
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

    # ── G: Top Sellers Today ──────────────────────────────────────────────────

    def _build_top_sellers(self, wrap: tk.Frame):
        sec = tk.Frame(wrap, bg=THEME["bg"])
        sec.pack(fill="x", padx=20, pady=(0, 16))

        sec_hdr = tk.Frame(sec, bg=THEME["bg"])
        sec_hdr.pack(fill="x", pady=(0, 8))
        tk.Label(sec_hdr, text="Top Sellers — Today",
                 bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Button(sec_hdr, text="All Transactions \u2192",
                  command=self.go_transactions_cb,
                  bg=THEME["bg"], fg=THEME["brown"], bd=0, cursor="hand2",
                  font=("Segoe UI", 9, "underline")).pack(side="right")

        card = tk.Frame(sec, bg=THEME["panel"],
                        highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="x")

        try:
            rows = self.orders.best_sellers_today(5)
        except Exception:
            rows = []

        if not rows:
            tk.Label(card, text="No sales recorded today yet.",
                     bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", 9, "italic"), pady=14,
                     ).pack(anchor="w", padx=16)
            return

        # Header
        hdr = tk.Frame(card, bg=THEME["beige"])
        hdr.pack(fill="x")
        hdr.columnconfigure(1, weight=1)
        tk.Label(hdr, text="#",       bg=THEME["beige"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold"), width=3, anchor="center",
                 ).grid(row=0, column=0, padx=(14, 4), pady=6)
        tk.Label(hdr, text="Product", bg=THEME["beige"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold"), anchor="w",
                 ).grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        tk.Label(hdr, text="Qty",     bg=THEME["beige"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold"), width=8, anchor="center",
                 ).grid(row=0, column=2, padx=4, pady=6)
        tk.Label(hdr, text="Revenue", bg=THEME["beige"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold"), width=11, anchor="e",
                 ).grid(row=0, column=3, padx=(4, 14), pady=6)

        rank_colors = ["#d4ac0d", "#aab7b8", "#ca6f1e", THEME["muted"], THEME["muted"]]
        for i, r in enumerate(rows, 1):
            name    = str(_safe(r, "name", "—"))
            qty     = int(_safe(r, "total_qty", 0))
            revenue = float(_safe(r, "total_sales", 0.0))
            row_bg  = THEME["panel"] if i % 2 else "#f9f5f1"

            fr = tk.Frame(card, bg=row_bg, cursor="hand2")
            fr.pack(fill="x", padx=2, pady=1)
            fr.columnconfigure(1, weight=1)

            tk.Label(fr, text=f"#{i}", bg=row_bg,
                     fg=rank_colors[i - 1] if i <= 5 else THEME["muted"],
                     font=("Segoe UI", 9, "bold"), width=3, anchor="center",
                     ).grid(row=0, column=0, padx=(14, 4), pady=7)
            tk.Label(fr, text=name, bg=row_bg, fg=THEME["text"],
                     font=("Segoe UI", 9), anchor="w",
                     ).grid(row=0, column=1, sticky="ew", padx=4, pady=7)
            tk.Label(fr, text=str(qty), bg=row_bg, fg=THEME["accent"],
                     font=("Segoe UI", 9, "bold"), width=8, anchor="center",
                     ).grid(row=0, column=2, padx=4, pady=7)
            tk.Label(fr, text=money(revenue), bg=row_bg, fg=THEME["success"],
                     font=("Segoe UI", 9, "bold"), width=11, anchor="e",
                     ).grid(row=0, column=3, padx=(4, 14), pady=7)

            fr.bind("<Button-1>", lambda _e: self.go_transactions_cb())

    # ── G: Quick Actions ──────────────────────────────────────────────────────

    def _build_quick_actions(self, wrap: tk.Frame):
        sec = tk.Frame(wrap, bg=THEME["bg"])
        sec.pack(fill="x", padx=20, pady=(0, 28))

        tk.Label(sec, text="Quick Actions", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 8))

        card = tk.Frame(sec, bg=THEME["panel"],
                        highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="x")
        btn_row = tk.Frame(card, bg=THEME["panel"])
        btn_row.pack(fill="x", padx=16, pady=14)

        can_manage = self.auth.has_permission(P_MANAGE_PRODS)
        can_export = self.auth.has_permission(P_EXPORT)
        can_db     = self.auth.has_permission(P_DATABASE)
        can_users  = self.auth.has_permission(P_MANAGE_USERS)

        def _qa_btn(text: str, color: str, cmd):
            tk.Button(
                btn_row, text=text,
                bg=color, fg="white",
                activebackground=color, activeforeground="white",
                bd=0, padx=14, pady=10, cursor="hand2",
                font=("Segoe UI", 9, "bold"),
                command=cmd,
            ).pack(side="left", padx=(0, 10))

        if can_manage:
            _qa_btn("+ Add Product", THEME["success"], self.show_products)
        if can_export:
            _qa_btn("Export Sales", THEME["brown"], self.show_sales)
        if can_db:
            _qa_btn("Backup Database", THEME["accent"], self._quick_backup_db)
        if can_users:
            _qa_btn("Manage Users", "#7c3aed", self._quick_manage_users)

        if not (can_manage or can_export or can_db or can_users):
            tk.Label(card, text="No quick actions available for your role.",
                     bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", 9, "italic"), pady=10,
                     ).pack(padx=16, anchor="w")

    def _quick_backup_db(self):
        from app.config import DB_PATH
        dest = filedialog.asksaveasfilename(
            title="Export Database Backup",
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialfile="pos_backup.db",
        )
        if not dest:
            return
        try:
            shutil.copy2(str(DB_PATH), dest)
            messagebox.showinfo("Backup Complete", f"Database exported to:\n{dest}")
        except Exception as e:
            messagebox.showerror("Backup Failed", f"Could not export database:\n{e}")

    def _quick_manage_users(self):
        from app.ui.account_settings_view import AccountSettingsDialog
        AccountSettingsDialog(self.winfo_toplevel(), self.db, self.auth)

    def _go_transactions_filtered(self, status: str):
        self.go_transactions_cb()
