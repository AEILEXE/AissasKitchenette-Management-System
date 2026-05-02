"""
dashboard_view.py — Premium Modern Restaurant POS Dashboard
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import tkinter as tk
from tkinter import ttk, messagebox

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO, ProductDAO, DraftDAO
from app.services.auth_service import AuthService
from app.utils import money

_SB    = THEME["sidebar"]    # warm coffee brown
_RED   = THEME["primary"]    # warm wood brown
_GOLD  = THEME["accent"]     # terra cotta accent
_NEU   = THEME["accent"]
_BG    = THEME["bg"]
_PANEL = THEME["panel"]
_TEXT  = THEME["text"]
_MUTED = THEME["muted"]
_BORDER= THEME["border"]


def _safe(row, key, default=None):
    try:
        v = row[key]
        return default if v is None else v
    except Exception:
        return default


def _bind_mw(canvas: tk.Canvas) -> None:
    def _scroll(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))


_DASH_STYLE = "Dash.Treeview"


def _apply_dash_style() -> None:
    s = ttk.Style()
    s.configure(_DASH_STYLE,
        rowheight=28,
        font=("Segoe UI", 9),
        background=_PANEL,
        fieldbackground=_PANEL,
        foreground=_TEXT,
        borderwidth=0,
        relief="flat",
    )
    s.configure(f"{_DASH_STYLE}.Heading",
        font=("Segoe UI", 9, "bold"),
        background=_SB,
        foreground="#FFFFFF",
        relief="flat",
        padding=(8, 7),
    )
    s.map(_DASH_STYLE,
        background=[("selected", _RED), ("!selected", _PANEL)],
        foreground=[("selected", "#FFFFFF"), ("!selected", _TEXT)],
    )
    s.map(f"{_DASH_STYLE}.Heading",
        background=[("active", THEME["primary_dark"])],
        foreground=[("active", "#FFFFFF")],
    )


class DashboardView(tk.Frame):
    def __init__(self, parent, db: Database, auth: AuthService, **callbacks):
        super().__init__(parent, bg=_BG)
        self.db   = db
        self.auth = auth
        self.go_transactions = callbacks.get("go_transactions_cb", lambda: None)
        self.go_pos          = callbacks.get("go_pos_cb",          lambda: None)

        self.orders   = OrderDAO(db)
        self.products = ProductDAO(db)
        self.drafts   = DraftDAO(db)

        _apply_dash_style()
        self._build()

    # ── Scrollable shell ──────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=_BG, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=sb.set)

        wrap = tk.Frame(canvas, bg=_BG)
        win  = canvas.create_window((0, 0), window=wrap, anchor="nw")
        wrap.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        _bind_mw(canvas)

        self._populate(wrap)

    # ── Main populate ─────────────────────────────────────────────────────

    def _populate(self, wrap: tk.Frame):
        PAD = 24

        # ── Page header ───────────────────────────────────────────────────
        hdr_bar = tk.Frame(wrap, bg=_SB)
        hdr_bar.pack(fill="x")

        tk.Frame(hdr_bar, bg=_RED, width=5).pack(side="left", fill="y")

        hdr_inner = tk.Frame(hdr_bar, bg=_SB)
        hdr_inner.pack(fill="x", padx=(14, 16), pady=12)
        hdr_inner.columnconfigure(0, weight=1)

        tk.Label(
            hdr_inner, text="Dashboard  —  Overview",
            bg=_SB, fg="#FFFFFF",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            hdr_inner, text=_dt.datetime.now().strftime("%A, %B %d, %Y"),
            bg=_SB, fg="#F5DFB8",
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky="w")

        refresh_btn = tk.Button(
            hdr_inner, text="↺  Refresh",
            command=self._refresh,
            bg=_RED, fg="white",
            activebackground=THEME["primary_dark"], activeforeground="white",
            bd=0, padx=16, pady=7,
            cursor="hand2", relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        refresh_btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))

        # ── Data fetch ────────────────────────────────────────────────────
        today_row   = self.orders.summary_today() or {}
        today_sales = float(_safe(today_row, "total_sales", 0))
        today_count = int(_safe(today_row, "order_count", 0))
        pending_cnt = self.orders.count_by_status("Pending")

        try:
            weekly_row   = self.orders.summary_month() or {}
            weekly_sales = float(_safe(weekly_row, "total_sales", 0))
        except Exception:
            weekly_sales = 0.0

        try:
            void_today = self.db.fetchone(
                "SELECT COUNT(*) AS c FROM void_records WHERE DATE(created_at) = DATE('now','localtime');"
            )
            void_count = int(_safe(void_today, "c", 0))
        except Exception:
            void_count = 0

        try:
            low_prods = self.db.fetchall(
                "SELECT name, stock FROM products WHERE active=1 AND low_stock > 0 AND stock <= low_stock ORDER BY stock;", ())
        except Exception:
            low_prods = []

        try:
            low_mats = self.db.fetchall(
                "SELECT name, material_type, quantity, unit FROM raw_materials "
                "WHERE active=1 AND quantity <= low_stock ORDER BY quantity;", ())
        except Exception:
            low_mats = []

        # ── KPI Cards row ─────────────────────────────────────────────────
        self._section_header(wrap, "Today's Performance", PAD, top_pady=(20, 8))

        row1 = tk.Frame(wrap, bg=_BG)
        row1.pack(fill="x", padx=PAD, pady=(0, 8))
        for i in range(4):
            row1.columnconfigure(i, weight=1, uniform="kpi")

        kpi_data = [
            ("Sales Today",        money(today_sales),
             f"{today_count} completed order{'s' if today_count != 1 else ''}",
             _RED, "\U0001f4b0", self.go_transactions),
            ("Orders Today",       str(today_count),
             "completed orders",
             _SB, "\U0001f9fe", self.go_transactions),
            ("Pending Orders",     str(pending_cnt),
             "awaiting payment",
             THEME["accent"], "⏳", self.go_transactions),
            ("Voids Today",        str(void_count),
             "⚠ suspicious if high" if void_count >= 3 else "click to view details",
             THEME["danger"] if void_count >= 3 else _NEU, "\U0001f6ab", self._open_voids_popup),
        ]
        for col, (title, val, sub, accent, icon, cmd) in enumerate(kpi_data):
            self._kpi_card(row1, col, title, val, sub, accent, icon, cmd)

        # ── Monthly summary banner ─────────────────────────────────────────
        banner = tk.Frame(wrap, bg=_SB, highlightthickness=0)
        banner.pack(fill="x", padx=PAD, pady=(4, 20))

        tk.Frame(banner, bg=THEME["accent"], width=4).pack(side="left", fill="y")

        tk.Label(
            banner,
            text="  This Month's Revenue",
            bg=_SB, fg="#F5DFB8",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(12, 0), pady=10)

        tk.Label(
            banner,
            text=money(weekly_sales),
            bg=_SB, fg="#FFFFFF",
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left", padx=(6, 0), pady=10)

        tk.Button(
            banner, text="View Transactions →",
            command=self.go_transactions,
            bg=_RED, fg="white",
            activebackground=THEME["primary_dark"], activeforeground="white",
            bd=0, padx=14, pady=6,
            cursor="hand2", relief="flat",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right", padx=14, pady=10)

        # ── Low Stock alert cards ─────────────────────────────────────────
        self._section_header(wrap, "Inventory Alerts", PAD, top_pady=(0, 8))

        row2 = tk.Frame(wrap, bg=_BG)
        row2.pack(fill="x", padx=PAD, pady=(0, 20))
        for i in range(2):
            row2.columnconfigure(i, weight=1, uniform="low")

        low_data = [
            ("Low Stock Products",
             str(len(low_prods)), "products below threshold",
             _RED, "\U0001f4e6"),
            ("Low Stock Raw Materials",
             str(len(low_mats)), "materials below threshold",
             THEME["warning"], "\U0001f9c2"),
        ]
        for col, (title, val, sub, accent, icon) in enumerate(low_data):
            self._kpi_card(row2, col, title, val, sub, accent, icon, None)

        # ── Top Sellers ───────────────────────────────────────────────────
        top_sellers = []
        try:
            top_sellers = self.orders.best_sellers_today(limit=8)
        except Exception:
            pass
        self._build_top_sellers(wrap, top_sellers, PAD)

        # ── Recent Transactions ───────────────────────────────────────────
        recent = []
        try:
            recent = self.orders.list_recent(limit=10)
        except Exception:
            pass
        self._build_recent_transactions(wrap, recent, PAD)

        # ── Low stock detail tables ───────────────────────────────────────
        if low_prods:
            self._section_header(wrap, "⚠  Low Stock Products", PAD, top_pady=(4, 8))
            self._detail_table(
                wrap,
                ("Product", "Current Stock"),
                [(r["name"], r["stock"]) for r in low_prods],
                col_widths=(320, 140),
                anchors=("w", "center"),
                PAD=PAD,
            )

        if low_mats:
            self._section_header(wrap, "⚠  Low Stock Raw Materials", PAD, top_pady=(4, 8))
            self._detail_table(
                wrap,
                ("Material", "Type", "Quantity"),
                [(r["name"], r["material_type"],
                  f"{r['quantity']} {r['unit']}") for r in low_mats],
                col_widths=(260, 100, 160),
                anchors=("w", "center", "center"),
                PAD=PAD,
            )

        tk.Frame(wrap, bg=_BG, height=32).pack()

    # ── Section header ────────────────────────────────────────────────────

    def _section_header(self, wrap, title, PAD, top_pady=(0, 8)):
        row = tk.Frame(wrap, bg=_BG)
        row.pack(fill="x", padx=PAD, pady=top_pady)

        tk.Frame(row, bg=_RED, width=3, height=22).pack(side="left", padx=(0, 10))

        tk.Label(
            row, text=title,
            bg=_BG, fg=_TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

    # ── KPI Card ──────────────────────────────────────────────────────────

    def _kpi_card(self, parent, col, title, value, sub, accent, icon, cmd):
        pad_left = 0 if col == 0 else 10

        outer = tk.Frame(parent, bg=_BG)
        outer.grid(row=0, column=col, sticky="nsew", padx=(pad_left, 0), pady=4)

        card = tk.Frame(
            outer,
            bg=_PANEL,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            cursor="hand2" if cmd else "",
        )
        card.pack(fill="both", expand=True)

        if cmd:
            card.bind("<Button-1>", lambda _e: cmd())

        top_bar = tk.Frame(card, bg=accent, height=4)
        top_bar.pack(fill="x")
        if cmd:
            top_bar.bind("<Button-1>", lambda _e: cmd())

        title_row = tk.Frame(card, bg=_PANEL)
        title_row.pack(fill="x", padx=16, pady=(14, 0))
        if cmd:
            title_row.bind("<Button-1>", lambda _e: cmd())

        tk.Label(
            title_row, text=icon,
            bg=_PANEL, fg=accent,
            font=("Segoe UI", 11),
        ).pack(side="left", padx=(0, 6))

        tk.Label(
            title_row, text=title,
            bg=_PANEL, fg=_MUTED,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        if cmd:
            for w in title_row.winfo_children():
                w.bind("<Button-1>", lambda _e: cmd())

        val_lbl = tk.Label(
            card, text=value,
            bg=_PANEL, fg=accent,
            font=("Segoe UI", 22, "bold"),
            anchor="w",
        )
        val_lbl.pack(anchor="w", padx=16, pady=(6, 2))
        if cmd:
            val_lbl.bind("<Button-1>", lambda _e: cmd())

        sub_lbl = tk.Label(
            card, text=sub,
            bg=_PANEL, fg=_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        )
        sub_lbl.pack(anchor="w", padx=16, pady=(0, 16))
        if cmd:
            sub_lbl.bind("<Button-1>", lambda _e: cmd())

    # ── Top Sellers ───────────────────────────────────────────────────────

    def _build_top_sellers(self, wrap, rows, PAD):
        self._section_header(wrap, "Top Selling Products — Today", PAD, top_pady=(0, 8))

        sec = tk.Frame(wrap, bg=_BG)
        sec.pack(fill="x", padx=PAD, pady=(0, 20))

        link_row = tk.Frame(sec, bg=_BG)
        link_row.pack(fill="x", pady=(0, 6))
        tk.Button(
            link_row, text="View All Transactions →",
            command=self.go_transactions,
            bg=_BG, fg=_RED,
            activebackground=_BG, activeforeground=THEME["primary_dark"],
            bd=0, cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right")

        card = tk.Frame(
            sec, bg=_PANEL,
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        card.pack(fill="x")

        if not rows:
            tk.Label(
                card, text="  No sales recorded today yet.",
                bg=_PANEL, fg=_MUTED,
                font=("Segoe UI", 9, "italic"), pady=20,
            ).pack(anchor="w", padx=16)
            return

        hdr = tk.Frame(card, bg=_SB)
        hdr.pack(fill="x")
        hdr.columnconfigure(1, weight=1)

        hdr_data = [
            ("#",        28,  "center", 0),
            ("Product",  0,   "w",      1),
            ("Qty Sold", 80,  "center", 2),
            ("Revenue",  120, "e",      3),
        ]
        for txt, w, anc, ci in hdr_data:
            kw = {"width": w} if w else {}
            px = (14 if ci == 0 else 6, 14 if ci == 3 else 6)
            lbl = tk.Label(
                hdr, text=txt,
                bg=_SB, fg="#FFFFFF",
                font=("Segoe UI", 8, "bold"),
                anchor=anc, **kw,
            )
            lbl.grid(row=0, column=ci, padx=px, pady=10, sticky="ew" if ci == 1 else "")

        rank_colors = ["#D4AC0D", "#AAB7B8", "#CA6F1E", _MUTED, _MUTED]

        for i, r in enumerate(rows, 1):
            name    = str(_safe(r, "name",        "—"))
            qty     = int(_safe(r, "total_qty",   0))
            revenue = float(_safe(r, "total_sales", 0.0))
            row_bg  = _PANEL if i % 2 else "#FAFAF8"

            if i == 1:
                row_bg = "#FFF5F5"

            fr = tk.Frame(card, bg=row_bg)
            fr.pack(fill="x")
            fr.columnconfigure(1, weight=1)
            fr.bind("<Button-1>", lambda _e: self.go_transactions())

            rank_fg = rank_colors[i - 1] if i <= 5 else _MUTED

            tk.Label(fr, text=f"#{i}",
                     bg=row_bg, fg=rank_fg,
                     font=("Segoe UI", 9, "bold"),
                     width=3, anchor="center",
                     ).grid(row=0, column=0, padx=(14, 4), pady=10)

            tk.Label(fr, text=name,
                     bg=row_bg, fg=_TEXT,
                     font=("Segoe UI", 9), anchor="w",
                     ).grid(row=0, column=1, sticky="ew", padx=4, pady=10)

            tk.Label(fr, text=str(qty),
                     bg=row_bg, fg=THEME["accent"],
                     font=("Segoe UI", 9, "bold"),
                     width=8, anchor="center",
                     ).grid(row=0, column=2, padx=6, pady=10)

            tk.Label(fr, text=money(revenue),
                     bg=row_bg, fg=THEME["success"],
                     font=("Segoe UI", 9, "bold"),
                     width=12, anchor="e",
                     ).grid(row=0, column=3, padx=(6, 14), pady=10)

            tk.Frame(card, bg=THEME["border"], height=1).pack(fill="x")

    # ── Recent Transactions ────────────────────────────────────────────────

    def _build_recent_transactions(self, wrap, recent, PAD):
        self._section_header(wrap, "Recent Transactions", PAD, top_pady=(0, 8))

        sec = tk.Frame(wrap, bg=_BG)
        sec.pack(fill="both", expand=True, padx=PAD, pady=(0, 20))

        link_row = tk.Frame(sec, bg=_BG)
        link_row.pack(fill="x", pady=(0, 6))
        tk.Button(
            link_row, text="View All →",
            command=self.go_transactions,
            bg=_BG, fg=_RED,
            activebackground=_BG, activeforeground=THEME["primary_dark"],
            bd=0, cursor="hand2",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right", padx=(0, 2))

        tbl_frame = tk.Frame(
            sec, bg=_PANEL,
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        tbl_frame.pack(fill="both", expand=True)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        if not recent:
            tk.Label(
                tbl_frame, text="  No recent transactions.",
                bg=_PANEL, fg=_MUTED,
                font=("Segoe UI", 9, "italic"), pady=20,
            ).pack(anchor="w", padx=16)
            return

        cols = ("id", "date", "payment", "total", "status")
        tbl = ttk.Treeview(
            tbl_frame, columns=cols, show="headings",
            style=_DASH_STYLE, height=min(len(recent), 9),
        )
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        col_cfg = [
            ("id",      "#",            50, "center", False),
            ("date",    "Date & Time", 140, "center", True),
            ("payment", "Payment",     120, "center", False),
            ("total",   "Total",       100, "e",      False),
            ("status",  "Status",       90, "center", False),
        ]
        for cid, heading, width, anchor, stretch in col_cfg:
            tbl.heading(cid, text=heading, anchor="center")
            tbl.column(cid, width=width, minwidth=width,
                        anchor=anchor, stretch=stretch)

        tbl.tag_configure("Completed",  foreground=THEME["success"], font=("Segoe UI", 9))
        tbl.tag_configure("Pending",    foreground=_GOLD,            font=("Segoe UI", 9))
        tbl.tag_configure("Cancelled",  foreground=_MUTED,           font=("Segoe UI", 9, "italic"))
        tbl.tag_configure("best_today",
                          background="#FFF0F0",
                          foreground=_RED,
                          font=("Segoe UI", 9, "bold"))

        today_date = _dt.date.today()
        highest_today_id: int | None = None
        highest_today_total: float   = -1.0

        for r in recent:
            oid    = int(_safe(r, "order_id", 0))
            dt_str = str(_safe(r, "start_dt", ""))
            pay    = str(_safe(r, "payment_method", "—"))
            total  = float(_safe(r, "total", 0.0))
            status = str(_safe(r, "status", ""))

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
                values=(f"#{oid}", dt_str[:16], pay, money(total), status),
                tags=(tag,),
            )

        if highest_today_id is not None:
            tbl.item(str(highest_today_id), tags=("best_today",))

    # ── Detail table ──────────────────────────────────────────────────────

    def _detail_table(self, wrap, headers, rows, col_widths, anchors, PAD):
        frame = tk.Frame(
            wrap, bg=_PANEL,
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        frame.pack(fill="x", padx=PAD, pady=(0, 16))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        cols   = [str(h).lower().replace(" ", "_") for h in headers]
        height = min(len(rows), 6)

        tree = ttk.Treeview(
            frame, columns=cols, show="headings",
            style=_DASH_STYLE, height=height,
        )
        tree.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=ysb.set)

        for col, hdr, width, anchor in zip(cols, headers, col_widths, anchors):
            tree.heading(col, text=hdr, anchor="center")
            tree.column(col, width=width, minwidth=60,
                         anchor=anchor, stretch=(anchor == "w"))

        for i, row in enumerate(rows):
            bg_tag = "odd" if i % 2 else "even"
            tree.insert("", "end", values=row, tags=(bg_tag,))

        tree.tag_configure("odd",  background=_PANEL)
        tree.tag_configure("even", background="#FAFAF8")

    # ── Voids popup ───────────────────────────────────────────────────────

    def _open_voids_popup(self):
        VoidsPopup(self, self.db)

    # ── Refresh ───────────────────────────────────────────────────────────

    def _refresh(self):
        for w in self.winfo_children():
            w.destroy()
        _apply_dash_style()
        self._build()


# ── Voided Orders Popup ───────────────────────────────────────────────────────

class VoidsPopup(tk.Toplevel):
    """Shows voided orders for a selectable date period."""

    _PERIODS = [
        ("Today",      "today"),
        ("This Week",  "week"),
        ("This Month", "month"),
    ]

    _COLS = [
        ("order_id", "Order ID",   80,  "center"),
        ("cashier",  "Cashier",   130,  "w"),
        ("items",    "Items",     260,  "w"),
        ("total",    "Total",     100,  "e"),
        ("void_time","Time of Void",160,"center"),
        ("reason",   "Reason",    180,  "w"),
    ]

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent)
        self.db = db
        self._period = tk.StringVar(value="today")

        self.title("Voided Orders")
        self.configure(bg=_BG)
        self.geometry("960x520")
        self.minsize(760, 400)
        self.transient(parent)
        self.grab_set()

        self._build()

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(960, sw - 80)
        h = min(580, sh - 100)
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=_SB)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=_RED, width=5).pack(side="left", fill="y")
        tk.Label(hdr, text="Voided Orders — Today",
                 bg=_SB, fg="#FFFFFF",
                 font=("Segoe UI", 13, "bold"),
                 padx=14, pady=12).pack(side="left")

        # Period filter bar
        bar = tk.Frame(self, bg=_PANEL,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.pack(fill="x", padx=16, pady=(12, 0))

        tk.Label(bar, text="Period:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)

        for label, key in self._PERIODS:
            tk.Radiobutton(
                bar, text=label, variable=self._period, value=key,
                bg=_PANEL, fg=_TEXT, selectcolor=_PANEL,
                activebackground=_PANEL,
                font=("Segoe UI", 9),
                command=self._refresh,
            ).pack(side="left", padx=6, pady=8)

        # Export button
        tk.Button(
            bar, text="Export CSV",
            bg=THEME["success"], fg="white",
            activebackground="#16a34a", activeforeground="white",
            bd=0, padx=12, pady=5, cursor="hand2",
            font=("Segoe UI", 8, "bold"),
            command=self._export_csv,
        ).pack(side="right", padx=12, pady=6)

        # Table area
        tbl_frame = tk.Frame(self, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("Voids.Treeview",
                    rowheight=28, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT,
                    borderwidth=0, relief="flat")
        s.configure("Voids.Treeview.Heading",
                    font=("Segoe UI", 9, "bold"),
                    background=_SB, foreground="#FFFFFF", relief="flat",
                    padding=(8, 7))
        s.map("Voids.Treeview",
              background=[("selected", _RED), ("!selected", _PANEL)],
              foreground=[("selected", "#FFFFFF"), ("!selected", _TEXT)])

        cols = [c[0] for c in self._COLS]
        self._tbl = ttk.Treeview(tbl_frame, columns=cols, show="headings",
                                  style="Voids.Treeview")
        self._tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self._tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self._tbl.configure(yscrollcommand=ysb.set)

        xsb = ttk.Scrollbar(tbl_frame, orient="horizontal", command=self._tbl.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        self._tbl.configure(xscrollcommand=xsb.set)

        for cid, heading, width, anchor in self._COLS:
            self._tbl.heading(cid, text=heading, anchor="center")
            self._tbl.column(cid, width=width, minwidth=60, anchor=anchor,
                              stretch=(anchor == "w"))

        self._empty_lbl = tk.Label(tbl_frame, text="No voided orders found.",
                                    bg=_PANEL, fg=_MUTED,
                                    font=("Segoe UI", 11, "italic"))

        # Footer
        foot = tk.Frame(self, bg=_BG)
        foot.pack(fill="x", padx=16, pady=(0, 12))
        self._count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED,
                                    font=("Segoe UI", 9))
        self._count_lbl.pack(side="left")
        tk.Button(foot, text="Close", bg=THEME["panel2"], fg=_TEXT,
                  bd=0, padx=14, pady=7, cursor="hand2",
                  font=("Segoe UI", 9),
                  command=self.destroy).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self._rows_cache: list[dict] = []
        self._refresh()

    def _date_filter(self) -> str:
        p = self._period.get()
        if p == "today":
            return "DATE(vr.created_at, 'localtime') = DATE('now', 'localtime')"
        if p == "week":
            return "DATE(vr.created_at, 'localtime') >= DATE('now', 'localtime', '-6 days')"
        return "strftime('%Y-%m', vr.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')"

    def _refresh(self):
        for iid in self._tbl.get_children():
            self._tbl.delete(iid)

        period_label = {p[1]: p[0] for p in self._PERIODS}.get(self._period.get(), "")
        # Update header title
        for w in self.winfo_children():
            if isinstance(w, tk.Frame) and w.cget("bg") == _SB:
                for child in w.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(text=f"Voided Orders — {period_label}")
                break

        rows = self._fetch()
        self._rows_cache = rows

        if not rows:
            self._empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self._empty_lbl.place_forget()

        for i, r in enumerate(rows):
            bg_tag = "odd" if i % 2 else "even"
            self._tbl.insert("", tk.END, tags=(bg_tag,), values=(
                f"#{r['order_id']}",
                r["cashier"],
                r["items"],
                money(r["total"]),
                str(r["void_time"])[:16],
                r["reason"] or "—",
            ))

        self._tbl.tag_configure("odd",  background=_PANEL)
        self._tbl.tag_configure("even", background="#FAFAF8")

        n = len(rows)
        self._count_lbl.configure(text=f"{n} voided order{'s' if n != 1 else ''}")

    def _fetch(self) -> list[dict]:
        df = self._date_filter()
        try:
            raw = self.db.fetchall(
                f"""
                SELECT vr.original_order_id AS order_id,
                       MAX(vr.voided_by_username) AS cashier,
                       MAX(vr.created_at)         AS void_time,
                       COALESCE(GROUP_CONCAT(DISTINCT NULLIF(vr.reason, '')), '') AS reason,
                       COALESCE(o.total, 0)        AS total,
                       (SELECT GROUP_CONCAT(COALESCE(p.name, '?'), ', ')
                        FROM order_items oi
                        LEFT JOIN products p ON p.id = oi.product_id
                        WHERE oi.order_id = vr.original_order_id) AS items
                FROM void_records vr
                JOIN orders o ON o.id = vr.original_order_id
                WHERE {df}
                GROUP BY vr.original_order_id
                ORDER BY void_time DESC;
                """
            )
            return [dict(r) for r in raw]
        except Exception:
            return []

    def _export_csv(self):
        rows = self._rows_cache
        if not rows:
            messagebox.showinfo("Export", "No data to export.", parent=self)
            return
        try:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                parent=self,
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"voided_orders_{self._period.get()}.csv",
                title="Save CSV",
            )
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Order ID", "Cashier", "Items", "Total", "Time of Void", "Reason"])
                for r in rows:
                    w.writerow([
                        f"#{r['order_id']}", r["cashier"], r["items"],
                        money(r["total"]), str(r["void_time"])[:16],
                        r["reason"] or "",
                    ])
            messagebox.showinfo("Export", f"Saved to:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)
