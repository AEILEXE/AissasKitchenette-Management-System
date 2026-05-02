"""
reports_view.py — Reports & Analytics View
"""
from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, timedelta

from app.config import THEME
from app.db.database import Database
from app.services.auth_service import AuthService

_SB     = THEME["sidebar"]
_RED    = THEME["primary"]
_SLATE  = THEME["accent"]
_GREEN  = THEME["success"]
_BG     = THEME["bg"]
_PANEL  = THEME["panel"]
_TEXT   = THEME["text"]
_MUTED  = THEME["muted"]
_BORDER = THEME["border"]


def _money(v):
    try:
        return f"₱{float(v):,.2f}"
    except Exception:
        return "₱0.00"


class ReportsView(tk.Frame):
    def __init__(self, parent, db: Database, auth: AuthService):
        super().__init__(parent, bg=_BG)
        self.db   = db
        self.auth = auth
        self._active_tab: str = "reports"
        self._tab_btns: dict[str, tk.Button] = {}
        self._content: tk.Frame | None = None
        self._build()

    # ── Top navigation ────────────────────────────────────────────────────────
    def _build(self):
        hdr_bar = tk.Frame(self, bg=_SB)
        hdr_bar.pack(fill="x")
        tk.Frame(hdr_bar, bg=_RED, width=5).pack(side="left", fill="y")
        tk.Label(hdr_bar, text="Reports & Analytics",
                 bg=_SB, fg="#FFFFFF",
                 font=("Segoe UI", 14, "bold"),
                 padx=14, pady=12).pack(side="left")

        # Tab buttons
        tk.Frame(hdr_bar, bg="#7A6050", width=1).pack(side="left", fill="y", pady=8)
        tabs = [
            ("reports",      "Overview"),
            ("sales",        "Sales Analytics"),
            ("top_sellers",  "Top Sellers"),
            ("raw_materials","Raw Materials"),
        ]
        for key, label in tabs:
            btn = tk.Button(
                hdr_bar, text=f"  {label}  ",
                command=lambda k=key: self._show_tab(k),
                bg=_SB, fg="#FFFFFF",
                activebackground=_SB, activeforeground="#FFFFFF",
                bd=0, padx=4, pady=0,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
                height=2,
                relief="flat",
            )
            btn.pack(side="left", padx=2)
            self._tab_btns[key] = btn
        self._update_tab_style()

        self._content = tk.Frame(self, bg=_BG)
        self._content.pack(fill="both", expand=True)

        self._show_tab("reports")

    def _update_tab_style(self):
        for key, btn in self._tab_btns.items():
            if key == self._active_tab:
                btn.configure(bg=THEME["primary_dark"], fg="#FFFFFF",
                               font=("Segoe UI", 9, "bold"))
            else:
                btn.configure(bg=_SB, fg="#C9B09A",
                               font=("Segoe UI", 9))

    def refresh(self):
        self._show_tab(self._active_tab)

    def _show_tab(self, key: str):
        self._active_tab = key
        self._update_tab_style()
        if self._content:
            for w in self._content.winfo_children():
                w.destroy()
        if key == "sales":
            self._build_sales_tab()
        elif key == "top_sellers":
            self._build_top_sellers_tab()
        elif key == "raw_materials":
            self._build_raw_materials_tab()
        else:
            self._build_reports_tab()

    def _build_sales_tab(self):
        from app.ui.inventory_sales_view import InventorySalesView
        InventorySalesView(self._content, self.db, self.auth).pack(fill="both", expand=True)

    # ── Overview tab ──────────────────────────────────────────────────────────

    def _build_reports_tab(self):
        outer = tk.Frame(self._content, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=_BG, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vsb.set)

        body = tk.Frame(canvas, bg=_BG)
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")

        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))

        def _scroll(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        # KPI cards
        kpi_row = tk.Frame(body, bg=_BG)
        kpi_row.pack(fill="x", padx=20, pady=(16, 12))

        kpi_data = self._fetch_kpis()
        kpi_cards = [
            ("Today's Sales", _money(kpi_data["today_sales"]), _RED),
            ("This Month",    _money(kpi_data["month_sales"]), _SLATE),
            ("Total Orders",  str(kpi_data["total_orders"]),   _SB),
            ("Avg. Order",    _money(kpi_data["avg_order"]),   _GREEN),
        ]
        for i, (label, val, accent) in enumerate(kpi_cards):
            card = tk.Frame(kpi_row, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            kpi_row.columnconfigure(i, weight=1)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=label, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9), anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, text=val, bg=_PANEL, fg=accent,
                     font=("Segoe UI", 18, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

        def _section_hdr(text: str):
            row = tk.Frame(body, bg=_BG)
            row.pack(fill="x", padx=20, pady=(14, 4))
            tk.Label(row, text=text.upper(), bg=_BG, fg=_MUTED,
                     font=("Segoe UI", 8, "bold")).pack(side="left")
            tk.Frame(row, bg=_BORDER, height=1).pack(
                side="left", fill="x", expand=True, padx=(8, 0), pady=6)

        def _alert_card(parent, name, qty, threshold, unit="pcs"):
            row = tk.Frame(parent, bg=_PANEL,
                           highlightthickness=1, highlightbackground=_BORDER)
            row.pack(fill="x", padx=16, pady=2)
            row.columnconfigure(1, weight=1)

            status_color = THEME["danger"] if qty <= 0 else THEME["warning"]
            tag = "OUT" if qty <= 0 else "LOW"
            tk.Label(row, text=f"  {tag}  ", bg=status_color, fg="white",
                     font=("Segoe UI", 7, "bold"),
                     padx=4, pady=3).grid(row=0, column=0, padx=(10, 8), pady=8, sticky="w")
            tk.Label(row, text=name, bg=_PANEL, fg=_TEXT,
                     font=("Segoe UI", 10, "bold"), anchor="w").grid(
                     row=0, column=1, sticky="ew", pady=8)
            tk.Label(row, text=f"{qty} {unit}  (min {threshold})",
                     bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9)).grid(row=0, column=2, padx=(0, 14), pady=8)

        # Product Stock Alerts — only stock-tracked products (low_stock > 0)
        _section_hdr("Inventory Alerts — Products")
        prod_card = tk.Frame(body, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        prod_card.pack(fill="x", padx=20, pady=(0, 4))
        tk.Frame(prod_card, bg=THEME["danger"], height=3).pack(fill="x")

        low_prods = self._fetch_low_stock_products()
        if low_prods:
            for p in low_prods:
                _alert_card(prod_card, p["name"], p["stock"], p["low_stock"])
        else:
            tk.Label(prod_card,
                     text="No stock-tracked products with low inventory.",
                     bg=_PANEL, fg=_GREEN,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=12)

        # Raw Materials Alerts
        _section_hdr("Inventory Alerts — Raw Materials")
        mat_card = tk.Frame(body, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
        mat_card.pack(fill="x", padx=20, pady=(0, 4))
        tk.Frame(mat_card, bg=THEME["warning"], height=3).pack(fill="x")

        low_mats = self._fetch_low_stock_materials()
        if low_mats:
            for m in low_mats:
                unit = m.get("unit", "pcs") or "pcs"
                _alert_card(mat_card, m["name"], m["quantity"], m["low_stock"], unit)
        else:
            tk.Label(mat_card, text="All raw materials have sufficient stock.",
                     bg=_PANEL, fg=_GREEN,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=12)

        # Top Products (summary, all-time)
        _section_hdr("Top Selling Products — All Time")
        top_card = tk.Frame(body, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
        top_card.pack(fill="x", padx=20, pady=(0, 4))
        tk.Frame(top_card, bg=_SLATE, height=3).pack(fill="x")

        top_prods = self._fetch_top_products_alltime()
        if top_prods:
            hdr_row = tk.Frame(top_card, bg=THEME["beige"])
            hdr_row.pack(fill="x", padx=16, pady=(6, 0))
            for txt, w in [("Product", 0), ("Units Sold", 100), ("Revenue", 120)]:
                expand = w == 0
                tk.Label(hdr_row, text=txt, bg=THEME["beige"], fg=_MUTED,
                         font=("Segoe UI", 8, "bold"),
                         anchor="w" if expand else "e",
                         width=0 if expand else w // 8).pack(
                    side="left", fill="x" if expand else None,
                    expand=expand, padx=8, pady=4)
            for p in top_prods:
                r = tk.Frame(top_card, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
                r.pack(fill="x", padx=16, pady=2)
                r.columnconfigure(0, weight=1)
                tk.Label(r, text=p["name"], bg=_PANEL, fg=_TEXT,
                         font=("Segoe UI", 9, "bold"), anchor="w").grid(
                    row=0, column=0, sticky="ew", padx=10, pady=6)
                tk.Label(r, text=str(p["units"]), bg=_PANEL, fg=_MUTED,
                         font=("Segoe UI", 9), width=12, anchor="e").grid(
                    row=0, column=1, padx=4)
                tk.Label(r, text=_money(p["revenue"]), bg=_PANEL, fg=_GREEN,
                         font=("Segoe UI", 9, "bold"), width=14, anchor="e").grid(
                    row=0, column=2, padx=(4, 10))
        else:
            tk.Label(top_card, text="No completed orders yet.",
                     bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=12)

        tk.Frame(body, bg=_BG, height=20).pack()

    # ── Top Sellers tab ───────────────────────────────────────────────────────

    def _build_top_sellers_tab(self):
        outer = tk.Frame(self._content, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        # Filter bar
        bar = tk.Frame(outer, bg=_PANEL,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))

        tk.Label(bar, text="Period:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)

        period_var = tk.StringVar(value="month")
        periods = [("Today", "today"), ("This Week", "week"),
                   ("This Month", "month"), ("This Year", "year")]
        for lbl, val in periods:
            tk.Radiobutton(bar, text=lbl, variable=period_var, value=val,
                           bg=_PANEL, fg=_TEXT, selectcolor=_PANEL,
                           activebackground=_PANEL, font=("Segoe UI", 9),
                           ).pack(side="left", padx=6, pady=8)

        # Custom date range
        tk.Label(bar, text="From:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=11,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT)
        from_ent.pack(side="left", ipady=5, pady=8)

        tk.Label(bar, text="To:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=11,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT)
        to_ent.pack(side="left", ipady=5, pady=8)

        # Table
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("TS.Treeview",
                    rowheight=30, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT)
        s.configure("TS.Treeview.Heading",
                    font=("Segoe UI", 9, "bold"),
                    background=_SB, foreground="#FFFFFF", relief="flat")
        s.map("TS.Treeview",
              background=[("selected", _RED)],
              foreground=[("selected", "#FFFFFF")])

        ts_cols = ("rank", "name", "category", "qty", "revenue")
        tbl = ttk.Treeview(tbl_frame, columns=ts_cols, show="headings",
                           style="TS.Treeview")
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        col_cfg = [
            ("rank",     "#",         50,  "center", False),
            ("name",     "Product",  220,  "w",      True),
            ("category", "Category", 140,  "w",      False),
            ("qty",      "Qty Sold",  90,  "center", False),
            ("revenue",  "Revenue",  130,  "e",      False),
        ]
        for cid, hdr, w, anc, stretch in col_cfg:
            tbl.heading(cid, text=hdr, anchor="center")
            tbl.column(cid, width=w, minwidth=50, anchor=anc, stretch=stretch)

        rank_tags = ["rank1", "rank2", "rank3"]
        tbl.tag_configure("rank1", background="#FFF5F5", foreground="#7f1d1d",
                          font=("Segoe UI", 9, "bold"))
        tbl.tag_configure("rank2", background="#FAFAFA", font=("Segoe UI", 9, "bold"))
        tbl.tag_configure("rank3", background="#FAFAFA", font=("Segoe UI", 9, "bold"))
        tbl.tag_configure("odd",  background=_PANEL)
        tbl.tag_configure("even", background="#FAFAF8")

        # Footer bar
        foot = tk.Frame(outer, bg=_BG)
        foot.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        rows_cache: list[dict] = []

        def export():
            if not rows_cache:
                messagebox.showinfo("Export", "No data to export.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="top_sellers.csv",
                title="Save CSV",
            )
            if not path:
                return
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Rank", "Product", "Category", "Qty Sold", "Revenue"])
                    for i, r in enumerate(rows_cache, 1):
                        w.writerow([i, r["name"], r["category"],
                                    r["total_qty"], _money(r["total_revenue"])])
                messagebox.showinfo("Export", f"Saved to:\n{path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

        tk.Button(foot, text="Export CSV",
                  bg=THEME["success"], fg="white",
                  activebackground="#16a34a", activeforeground="white",
                  bd=0, padx=12, pady=5, cursor="hand2",
                  font=("Segoe UI", 8, "bold"),
                  command=export).pack(side="right")

        empty_lbl = tk.Label(tbl_frame, text="No sales data for the selected period.",
                              bg=_PANEL, fg=_MUTED,
                              font=("Segoe UI", 11, "italic"))

        def load(_e=None):
            nonlocal rows_cache
            for iid in tbl.get_children():
                tbl.delete(iid)

            p = period_var.get()
            df = from_var.get().strip()
            dt = to_var.get().strip()

            if df and dt:
                date_clause = f"DATE(o.datetime) BETWEEN DATE('{df}') AND DATE('{dt}')"
            elif p == "today":
                date_clause = "DATE(o.datetime) = DATE('now','localtime')"
            elif p == "week":
                date_clause = "DATE(o.datetime) >= DATE('now','localtime','-6 days')"
            elif p == "year":
                date_clause = "strftime('%Y',o.datetime) = strftime('%Y','now','localtime')"
            else:
                date_clause = "strftime('%Y-%m',o.datetime) = strftime('%Y-%m','now','localtime')"

            try:
                raw = self.db.fetchall(
                    f"""
                    SELECT p.name,
                           COALESCE(c.name, 'Uncategorized') AS category,
                           SUM(oi.qty)      AS total_qty,
                           SUM(oi.subtotal) AS total_revenue
                    FROM order_items oi
                    JOIN products p  ON p.id = oi.product_id
                    LEFT JOIN categories c ON c.id = p.category_id
                    JOIN orders o    ON o.id = oi.order_id
                    WHERE o.status = 'Completed'
                      AND oi.voided = 0
                      AND {date_clause}
                    GROUP BY p.id, p.name, c.name
                    ORDER BY total_qty DESC
                    LIMIT 50;
                    """
                )
                rows_cache = [dict(r) for r in raw]
            except Exception:
                rows_cache = []

            if not rows_cache:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                empty_lbl.place_forget()

            for i, r in enumerate(rows_cache, 1):
                tag = rank_tags[i - 1] if i <= 3 else ("odd" if i % 2 else "even")
                tbl.insert("", tk.END, tags=(tag,), values=(
                    f"#{i}", r["name"], r["category"],
                    int(r["total_qty"] or 0), _money(r["total_revenue"]),
                ))
            n = len(rows_cache)
            count_lbl.configure(text=f"{n} product{'s' if n != 1 else ''} shown")

        period_var.trace_add("write", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>",   load)
        load()

    # ── Raw Materials Movement Report tab ─────────────────────────────────────

    def _build_raw_materials_tab(self):
        outer = tk.Frame(self._content, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        # Filter bar
        bar = tk.Frame(outer, bg=_PANEL,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))

        # Date period
        tk.Label(bar, text="Period:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)
        period_var = tk.StringVar(value="month")
        for lbl, val in [("Today","today"),("This Week","week"),
                          ("This Month","month"),("This Year","year")]:
            tk.Radiobutton(bar, text=lbl, variable=period_var, value=val,
                           bg=_PANEL, fg=_TEXT, selectcolor=_PANEL,
                           activebackground=_PANEL, font=("Segoe UI", 9),
                           ).pack(side="left", padx=4, pady=8)

        # Custom from/to
        tk.Label(bar, text="From:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=11,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT)
        from_ent.pack(side="left", ipady=5, pady=8)
        tk.Label(bar, text="To:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=11,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT)
        to_ent.pack(side="left", ipady=5, pady=8)

        # Second filter row
        bar2 = tk.Frame(outer, bg=_PANEL,
                        highlightthickness=1, highlightbackground=_BORDER)
        bar2.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        # Reuse bar for both filter rows by putting everything in one bar
        tk.Frame(bar, bg=_BORDER, width=1, height=30).pack(side="left", padx=10, pady=4)

        tk.Label(bar, text="Type:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 4), pady=8)
        type_var = tk.StringVar(value="All")
        type_cb = ttk.Combobox(bar, textvariable=type_var,
                               values=["All", "DRY", "WET"],
                               state="readonly", width=7)
        type_cb.pack(side="left", padx=(0, 10), pady=8)

        tk.Label(bar, text="Action:", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4), pady=8)
        action_var = tk.StringVar(value="All")
        action_cb = ttk.Combobox(bar, textvariable=action_var,
                                 values=["All", "ADD", "DEDUCT", "Initial"],
                                 state="readonly", width=9)
        action_cb.pack(side="left", padx=(0, 10), pady=8)
        bar2.pack_forget()  # hide the dummy bar2

        # Table
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("RM.Treeview",
                    rowheight=30, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT)
        s.configure("RM.Treeview.Heading",
                    font=("Segoe UI", 9, "bold"),
                    background=_SB, foreground="#FFFFFF", relief="flat")
        s.map("RM.Treeview",
              background=[("selected", _RED)],
              foreground=[("selected", "#FFFFFF")])

        rm_cols = ("dt", "material", "mat_type", "action", "qty_change", "notes")
        tbl = ttk.Treeview(tbl_frame, columns=rm_cols, show="headings",
                           style="RM.Treeview")
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        xsb = ttk.Scrollbar(tbl_frame, orient="horizontal", command=tbl.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        tbl.configure(xscrollcommand=xsb.set)

        rm_col_cfg = [
            ("dt",         "Date & Time",     160, "center", False),
            ("material",   "Material Name",   200, "w",      True),
            ("mat_type",   "Type",             70, "center", False),
            ("action",     "Action",          100, "center", False),
            ("qty_change", "Qty Change",      110, "center", False),
            ("notes",      "Notes/Reason",    200, "w",      True),
        ]
        for cid, hdr, w, anc, stretch in rm_col_cfg:
            tbl.heading(cid, text=hdr, anchor="center")
            tbl.column(cid, width=w, minwidth=60, anchor=anc, stretch=stretch)

        tbl.tag_configure("add",    foreground="#16a34a")
        tbl.tag_configure("deduct", foreground=THEME["danger"])
        tbl.tag_configure("odd",    background=_PANEL)
        tbl.tag_configure("even",   background="#FAFAF8")

        # Footer
        foot = tk.Frame(outer, bg=_BG)
        foot.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        rows_cache: list[dict] = []

        def export():
            if not rows_cache:
                messagebox.showinfo("Export", "No data to export.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="raw_materials_movement.csv",
                title="Save CSV",
            )
            if not path:
                return
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Date & Time", "Material", "Type",
                                "Action", "Qty Change", "Notes"])
                    for r in rows_cache:
                        act = r["action_type"]
                        sign = "+" if act in ("ADD", "Initial") else "-"
                        w.writerow([
                            str(r["created_at"])[:16],
                            r["name"], r["material_type"],
                            act, f"{sign}{r['quantity']}",
                            r["reason"] or "",
                        ])
                messagebox.showinfo("Export", f"Saved to:\n{path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

        tk.Button(foot, text="Export CSV",
                  bg=THEME["success"], fg="white",
                  activebackground="#16a34a", activeforeground="white",
                  bd=0, padx=12, pady=5, cursor="hand2",
                  font=("Segoe UI", 8, "bold"),
                  command=export).pack(side="right")

        empty_lbl = tk.Label(tbl_frame, text="No raw material movements for the selected period.",
                              bg=_PANEL, fg=_MUTED,
                              font=("Segoe UI", 11, "italic"))

        def load(_e=None):
            nonlocal rows_cache
            for iid in tbl.get_children():
                tbl.delete(iid)

            p = period_var.get()
            df = from_var.get().strip()
            dt = to_var.get().strip()

            if df and dt:
                date_clause = f"DATE(rml.created_at) BETWEEN DATE('{df}') AND DATE('{dt}')"
            elif p == "today":
                date_clause = "DATE(rml.created_at) = DATE('now','localtime')"
            elif p == "week":
                date_clause = "DATE(rml.created_at) >= DATE('now','localtime','-6 days')"
            elif p == "year":
                date_clause = "strftime('%Y',rml.created_at) = strftime('%Y','now','localtime')"
            else:
                date_clause = "strftime('%Y-%m',rml.created_at) = strftime('%Y-%m','now','localtime')"

            type_filter   = type_var.get()
            action_filter = action_var.get()

            extra = ""
            if type_filter != "All":
                extra += f" AND rm.material_type = '{type_filter}'"
            if action_filter != "All":
                extra += f" AND rml.action_type = '{action_filter}'"

            try:
                raw = self.db.fetchall(
                    f"""
                    SELECT rml.created_at,
                           rm.name,
                           rm.material_type,
                           rml.action_type,
                           rml.quantity,
                           rml.reason
                    FROM raw_material_logs rml
                    JOIN raw_materials rm ON rm.id = rml.material_id
                    WHERE {date_clause}{extra}
                    ORDER BY rml.created_at DESC
                    LIMIT 500;
                    """
                )
                rows_cache = [dict(r) for r in raw]
            except Exception:
                rows_cache = []

            if not rows_cache:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                empty_lbl.place_forget()

            for i, r in enumerate(rows_cache):
                act = r["action_type"] or ""
                sign = "+" if act in ("ADD", "Initial") else "-"
                qty_disp = f"{sign}{r['quantity']}"
                color_tag = "add" if sign == "+" else "deduct"
                row_tag   = "odd" if i % 2 else "even"
                tbl.insert("", tk.END, tags=(color_tag, row_tag), values=(
                    str(r["created_at"])[:16],
                    r["name"],
                    r["material_type"],
                    act,
                    qty_disp,
                    r["reason"] or "",
                ))
            n = len(rows_cache)
            count_lbl.configure(text=f"{n} record{'s' if n != 1 else ''} shown")

        period_var.trace_add("write", load)
        type_cb.bind("<<ComboboxSelected>>",   load)
        action_cb.bind("<<ComboboxSelected>>", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>",   load)
        load()

    # ── Data fetchers ──────────────────────────────────────────────────────────

    def _fetch_kpis(self) -> dict:
        result = {"today_sales": 0, "month_sales": 0, "total_orders": 0, "avg_order": 0}
        try:
            row = self.db.fetchone(
                "SELECT COALESCE(SUM(total),0) AS s FROM orders "
                "WHERE DATE(datetime)=DATE('now','localtime') AND status='Completed';"
            )
            if row:
                result["today_sales"] = float(row["s"] or 0)
        except Exception:
            pass
        try:
            row = self.db.fetchone(
                "SELECT COALESCE(SUM(total),0) AS s FROM orders "
                "WHERE strftime('%Y-%m',datetime)=strftime('%Y-%m','now','localtime') "
                "AND status='Completed';"
            )
            if row:
                result["month_sales"] = float(row["s"] or 0)
        except Exception:
            pass
        try:
            row = self.db.fetchone(
                "SELECT COUNT(*) AS c, COALESCE(AVG(total),0) AS a FROM orders WHERE status='Completed';"
            )
            if row:
                result["total_orders"] = int(row["c"] or 0)
                result["avg_order"] = float(row["a"] or 0)
        except Exception:
            pass
        return result

    def _fetch_low_stock_products(self) -> list:
        """Only returns products that have stock tracking enabled (low_stock > 0)."""
        try:
            rows = self.db.fetchall(
                "SELECT name, stock, low_stock FROM products "
                "WHERE active=1 AND low_stock > 0 AND stock <= low_stock "
                "ORDER BY stock ASC LIMIT 20;"
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _fetch_low_stock_materials(self) -> list:
        try:
            rows = self.db.fetchall(
                "SELECT name, quantity, low_stock, unit FROM raw_materials "
                "WHERE active=1 AND quantity <= low_stock "
                "ORDER BY quantity ASC LIMIT 20;"
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _fetch_top_products_alltime(self) -> list:
        """Top sellers across all time — used by Overview tab."""
        try:
            rows = self.db.fetchall(
                """
                SELECT p.name,
                       SUM(oi.qty)      AS units,
                       SUM(oi.subtotal) AS revenue
                FROM order_items oi
                JOIN products p ON p.id = oi.product_id
                JOIN orders o   ON o.id = oi.order_id
                WHERE o.status = 'Completed' AND oi.voided = 0
                GROUP BY p.id, p.name
                ORDER BY units DESC LIMIT 10;
                """
            )
            return [dict(r) for r in rows]
        except Exception:
            return []
