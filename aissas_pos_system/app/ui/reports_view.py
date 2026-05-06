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
from app.ui.transactions_view import DatePickerDialog


def _bind_date_picker(entry: tk.Entry, var: tk.StringVar) -> None:
    """Attach a calendar popup to a date Entry widget."""
    def _open(e=None):
        parent = entry.winfo_toplevel()
        dlg = DatePickerDialog(parent, initial=var.get() or None)
        if dlg.result:
            var.set(dlg.result)
    entry.bind("<Button-1>", _open)
    entry.configure(cursor="hand2")

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
    _POLL_INTERVAL_MS = 5000  # check for new data every 5 s

    def __init__(self, parent, db: Database, auth: AuthService):
        super().__init__(parent, bg=_BG)
        self.db   = db
        self.auth = auth
        self._active_tab: str = "reports"
        self._tab_btns: dict[str, tk.Button] = {}
        self._content: tk.Frame | None = None
        self._tab_frames: dict[str, tk.Frame] = {}   # cached tab content
        self._poll_after: int | None = None
        self._poll_version: int = -1
        self._build()
        self._start_polling()
        self.bind("<Destroy>", lambda _e: self._cancel_poll())

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
                btn.configure(bg=_SB, fg="#F5DFB8",
                               font=("Segoe UI", 9))

    def refresh(self):
        # Force-rebuild only the active tab so stale data is never shown
        old = self._tab_frames.pop(self._active_tab, None)
        if old and old.winfo_exists():
            old.destroy()
        self._show_tab(self._active_tab)

    # ── Polling (cross-device auto-refresh) ──────────────────────────────────

    def _start_polling(self) -> None:
        self._cancel_poll()
        self._poll_after = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    def _cancel_poll(self) -> None:
        if self._poll_after is not None:
            try:
                self.after_cancel(self._poll_after)
            except Exception:
                pass
            self._poll_after = None

    def _poll_tick(self) -> None:
        self._poll_after = None
        try:
            if not self.winfo_exists():
                return
            if self.winfo_ismapped():
                v = self.db.get_data_version()
                if v != self._poll_version:
                    self._poll_version = v
                    self.refresh()  # synchronous; re-arm below after it returns
        except Exception:
            pass
        self._poll_after = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    def _show_tab(self, key: str):
        self._active_tab = key
        self._update_tab_style()
        if not self._content:
            return

        # Hide every cached tab frame
        for frame in self._tab_frames.values():
            if frame.winfo_exists():
                frame.pack_forget()

        # Return cached frame if it exists
        cached = self._tab_frames.get(key)
        if cached and cached.winfo_exists():
            cached.pack(fill="both", expand=True)
            return

        # Build fresh tab content inside a wrapper frame
        tab_frame = tk.Frame(self._content, bg=_BG)
        tab_frame.pack(fill="both", expand=True)
        self._tab_frames[key] = tab_frame

        if key == "sales":
            self._build_sales_tab(tab_frame)
        elif key == "top_sellers":
            self._build_top_sellers_tab(tab_frame)
        elif key == "raw_materials":
            self._build_raw_materials_tab(tab_frame)
        else:
            self._build_reports_tab(tab_frame)

    def _build_sales_tab(self, parent: tk.Frame):
        from app.ui.inventory_sales_view import InventorySalesView
        InventorySalesView(parent, self.db, self.auth).pack(fill="both", expand=True)

    # ── Overview tab ──────────────────────────────────────────────────────────

    def _build_reports_tab(self, parent: tk.Frame):
        outer = tk.Frame(parent, bg=_BG)
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
        kpi_row.pack(fill="x", padx=24, pady=(16, 8))
        kpi_row.rowconfigure(0, weight=1)

        kpi_data = self._fetch_kpis()
        kpi_cards = [
            ("Today's Sales", _money(kpi_data["today_sales"]), _RED),
            ("This Month",    _money(kpi_data["month_sales"]), _SLATE),
            ("Total Orders",  str(kpi_data["total_orders"]),   _SB),
            ("Avg. Order",    _money(kpi_data["avg_order"]),   _GREEN),
        ]
        for i, (label, val, accent) in enumerate(kpi_cards):
            kpi_row.columnconfigure(i, weight=1, uniform="kpi")
            outer_cell = tk.Frame(kpi_row, bg=_BG)
            outer_cell.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            card = tk.Frame(outer_cell, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
            card.pack(fill="both", expand=True)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=label, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9), anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, text=val, bg=_PANEL, fg=accent,
                     font=("Segoe UI", 18, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

        def _section_hdr(text: str):
            row = tk.Frame(body, bg=_BG)
            row.pack(fill="x", padx=24, pady=(14, 4))
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

        # Raw Materials Alerts
        _section_hdr("Inventory Alerts — Raw Materials")
        mat_card = tk.Frame(body, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
        mat_card.pack(fill="x", padx=24, pady=(0, 4))
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
        top_card.pack(fill="x", padx=24, pady=(0, 4))
        tk.Frame(top_card, bg=_SLATE, height=3).pack(fill="x")

        top_prods = self._fetch_top_products_alltime()
        if top_prods:
            hdr_row = tk.Frame(top_card, bg=_SB)
            hdr_row.pack(fill="x", padx=16, pady=(6, 0))
            for txt, w in [("Product", 0), ("Units Sold", 100), ("Revenue", 120)]:
                expand = w == 0
                tk.Label(hdr_row, text=txt, bg=_SB, fg="#FFFFFF",
                         font=("Segoe UI", 8, "bold"),
                         anchor="w" if expand else "e",
                         width=0 if expand else w // 8).pack(
                    side="left", fill="x" if expand else None,
                    expand=expand, padx=8, pady=6)
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

    def _build_top_sellers_tab(self, parent: tk.Frame):
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        _FILTER_BG = "#f5f0e8"
        _LABEL_FG  = "#3d2b1f"

        # Filter bar
        bar = tk.Frame(outer, bg=_FILTER_BG,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))

        tk.Label(bar, text="Period:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)

        period_var = tk.StringVar(value="month")

        _SEL_BG   = "#8c6e3b"
        _SEL_FG   = "white"
        _UNSEL_BG = _FILTER_BG   # "#f5f0e8"
        _UNSEL_FG = _LABEL_FG    # "#3d2b1f"

        _period_btns: dict[str, tk.Button] = {}

        def _set_period(val: str) -> None:
            period_var.set(val)
            for v, b in _period_btns.items():
                b.configure(
                    bg=_SEL_BG if v == val else _UNSEL_BG,
                    fg=_SEL_FG if v == val else _UNSEL_FG,
                )

        periods = [("Today", "today"), ("This Week", "week"),
                   ("This Month", "month"), ("This Year", "year")]
        for lbl, val in periods:
            is_default = val == "month"
            btn = tk.Button(
                bar, text=lbl,
                command=lambda v=val: _set_period(v),
                bg=_SEL_BG   if is_default else _UNSEL_BG,
                fg=_SEL_FG   if is_default else _UNSEL_FG,
                activebackground=_SEL_BG, activeforeground=_SEL_FG,
                relief="flat", bd=0,
                padx=12, pady=5,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            btn.pack(side="left", padx=2, pady=8)
            _period_btns[val] = btn

        # Custom date range
        tk.Label(bar, text="From:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=11,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT, insertwidth=2)
        from_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(from_ent, from_var)

        tk.Label(bar, text="To:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=11,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT, insertwidth=2)
        to_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(to_ent, to_var)

        # Table
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("TS.Treeview",
                    rowheight=28, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT,
                    borderwidth=0, relief="flat")
        s.configure("TS.Treeview.Heading",
                    font=("Segoe UI", 9, "bold"),
                    background=_SB, foreground="#FFFFFF", relief="flat",
                    padding=(8, 7))
        s.map("TS.Treeview",
              background=[("selected", _RED), ("!selected", _PANEL)],
              foreground=[("selected", "#FFFFFF"), ("!selected", _TEXT)])

        ts_cols = ("rank", "name", "category", "qty", "revenue")
        tbl = ttk.Treeview(tbl_frame, columns=ts_cols, show="headings",
                           style="TS.Treeview")
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        col_cfg = [
            ("rank",     "#",         50,  "center", False),
            ("name",     "Product",  200,  "w",      True),
            ("category", "Category", 120,  "w",      False),
            ("qty",      "Qty Sold",  90,  "center", False),
            ("revenue",  "Revenue",  100,  "e",      False),
        ]
        _ts_col_labels = {cid: hdr for cid, hdr, *_ in col_cfg}
        for cid, hdr, w, anc, stretch in col_cfg:
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
        foot.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        rows_cache: list[dict] = []
        _ts_sort: dict = {"col": None, "reverse": False}

        def _ts_display(rows: list[dict]) -> None:
            for iid in tbl.get_children():
                tbl.delete(iid)
            if not rows:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                empty_lbl.place_forget()
            for i, r in enumerate(rows, 1):
                tag = rank_tags[i - 1] if i <= 3 else ("odd" if i % 2 else "even")
                tbl.insert("", tk.END, tags=(tag,), values=(
                    f"#{i}", r["name"], r["category"],
                    int(r["total_qty"] or 0), _money(r["total_revenue"]),
                ))
            n = len(rows)
            count_lbl.configure(text=f"{n} product{'s' if n != 1 else ''} shown")

        def _ts_sort_by(col: str) -> None:
            if _ts_sort["col"] == col:
                _ts_sort["reverse"] = not _ts_sort["reverse"]
            else:
                _ts_sort["col"] = col
                _ts_sort["reverse"] = False
            rev = _ts_sort["reverse"]
            ind = "▲" if not rev else "▼"
            for cid, hdr in _ts_col_labels.items():
                tbl.heading(cid, text=(hdr + " " + ind) if cid == col else hdr,
                            anchor="center",
                            command=lambda c=cid: _ts_sort_by(c))
            key_map = {
                "rank": lambda r: float(r.get("total_qty") or 0),
                "name": lambda r: str(r.get("name") or "").lower(),
                "category": lambda r: str(r.get("category") or "").lower(),
                "qty": lambda r: float(r.get("total_qty") or 0),
                "revenue": lambda r: float(r.get("total_revenue") or 0),
            }
            kf = key_map.get(col, lambda r: 0)
            sorted_rows = sorted(rows_cache, key=kf, reverse=rev)
            _ts_display(sorted_rows)

        for cid, hdr, *_ in col_cfg:
            tbl.heading(cid, text=hdr, anchor="center",
                        command=lambda c=cid: _ts_sort_by(c))

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
                from datetime import datetime as _datetime
                now_str = _datetime.now().strftime("%Y-%m-%d %H:%M")
                p = period_var.get()
                df_v = from_var.get().strip()
                dt_v = to_var.get().strip()
                period_label = df_v and dt_v and f"{df_v} to {dt_v}" or {
                    "today": "Today", "week": "This Week",
                    "month": "This Month", "year": "This Year"}.get(p, p)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Aissa's Kitchenette"])
                    w.writerow(["Top Sellers Report"])
                    w.writerow([f"Period: {period_label}"])
                    w.writerow([f"Generated: {now_str}"])
                    w.writerow([])
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

        def load(*args):
            nonlocal rows_cache
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

            # Reset sort state on fresh load
            _ts_sort["col"] = None
            _ts_sort["reverse"] = False
            for cid, hdr in _ts_col_labels.items():
                tbl.heading(cid, text=hdr, anchor="center",
                            command=lambda c=cid: _ts_sort_by(c))
            _ts_display(rows_cache)

        period_var.trace_add("write", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>",   load)
        load()

    # ── Raw Materials Movement Report tab ─────────────────────────────────────

    def _build_raw_materials_tab(self, parent: tk.Frame):
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        _FILTER_BG  = "#f5f0e8"   # warm beige for filter bar
        _LABEL_FG   = "#3d2b1f"   # dark brown — high contrast on beige

        # Filter bar
        bar = tk.Frame(outer, bg=_FILTER_BG,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))

        # Date period
        tk.Label(bar, text="Period:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)
        period_var = tk.StringVar(value="month")

        _SEL_BG   = "#8c6e3b"
        _SEL_FG   = "white"
        _UNSEL_BG = _FILTER_BG   # "#f5f0e8"
        _UNSEL_FG = _LABEL_FG    # "#3d2b1f"

        _period_btns: dict[str, tk.Button] = {}

        def _set_period(val: str) -> None:
            period_var.set(val)
            for v, b in _period_btns.items():
                b.configure(
                    bg=_SEL_BG if v == val else _UNSEL_BG,
                    fg=_SEL_FG if v == val else _UNSEL_FG,
                )

        for lbl, val in [("Today", "today"), ("This Week", "week"),
                          ("This Month", "month"), ("This Year", "year")]:
            is_default = val == "month"
            btn = tk.Button(
                bar, text=lbl,
                command=lambda v=val: _set_period(v),
                bg=_SEL_BG   if is_default else _UNSEL_BG,
                fg=_SEL_FG   if is_default else _UNSEL_FG,
                activebackground=_SEL_BG, activeforeground=_SEL_FG,
                relief="flat", bd=0,
                padx=12, pady=5,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            btn.pack(side="left", padx=2, pady=8)
            _period_btns[val] = btn

        # Custom from/to
        tk.Label(bar, text="From:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=11,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT, insertwidth=2)
        from_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(from_ent, from_var)
        tk.Label(bar, text="To:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=11,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT, insertwidth=2)
        to_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(to_ent, to_var)

        # Type and Action filters — same bar, separated by a divider
        tk.Frame(bar, bg=_BORDER, width=1, height=30).pack(side="left", padx=10, pady=4)

        tk.Label(bar, text="Type:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 4), pady=8)
        type_var = tk.StringVar(value="All")
        type_cb = ttk.Combobox(bar, textvariable=type_var,
                               values=["All", "DRY", "WET"],
                               state="readonly", width=7)
        type_cb.pack(side="left", padx=(0, 10), pady=8)

        tk.Label(bar, text="Action:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4), pady=8)
        action_var = tk.StringVar(value="All")
        action_cb = ttk.Combobox(bar, textvariable=action_var,
                                 values=["All", "ADD", "DEDUCT", "Initial"],
                                 state="readonly", width=9)
        action_cb.pack(side="left", padx=(0, 10), pady=8)

        # Table
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("RM.Treeview",
                    rowheight=28, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT,
                    borderwidth=0, relief="flat")
        s.configure("RM.Treeview.Heading",
                    font=("Segoe UI", 9, "bold"),
                    background=_SB, foreground="#FFFFFF", relief="flat",
                    padding=(8, 7))
        s.map("RM.Treeview",
              background=[("selected", _RED), ("!selected", _PANEL)],
              foreground=[("selected", "#FFFFFF"), ("!selected", _TEXT)])

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
            ("dt",         "Date & Time",     140, "center", False),
            ("material",   "Material Name",   180, "w",      True),
            ("mat_type",   "Type",             70, "center", False),
            ("action",     "Action",           90, "center", False),
            ("qty_change", "Qty Change",      100, "center", False),
            ("notes",      "Notes/Reason",    180, "w",      True),
        ]
        _rm_col_labels = {cid: hdr for cid, hdr, *_ in rm_col_cfg}
        for cid, hdr, w, anc, stretch in rm_col_cfg:
            tbl.column(cid, width=w, minwidth=60, anchor=anc, stretch=stretch)

        tbl.tag_configure("add",    foreground="#16a34a")
        tbl.tag_configure("deduct", foreground=THEME["danger"])
        tbl.tag_configure("odd",    background=_PANEL)
        tbl.tag_configure("even",   background="#FAFAF8")

        # Footer
        foot = tk.Frame(outer, bg=_BG)
        foot.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        rows_cache: list[dict] = []
        _rm_sort: dict = {"col": None, "reverse": False}

        def _rm_display(rows: list[dict]) -> None:
            for iid in tbl.get_children():
                tbl.delete(iid)
            if not rows:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                empty_lbl.place_forget()
            for i, r in enumerate(rows):
                act = r["action_type"] or ""
                sign = "+" if act in ("ADD", "Initial") else "-"
                qty_disp = f"{sign}{r['quantity']}"
                color_tag = "add" if sign == "+" else "deduct"
                row_tag   = "odd" if i % 2 else "even"
                tbl.insert("", tk.END, tags=(color_tag, row_tag), values=(
                    str(r["created_at"])[:16],
                    r["name"], r["material_type"], act, qty_disp,
                    r["reason"] or "",
                ))
            n = len(rows)
            count_lbl.configure(text=f"{n} record{'s' if n != 1 else ''} shown")

        def _rm_sort_by(col: str) -> None:
            if _rm_sort["col"] == col:
                _rm_sort["reverse"] = not _rm_sort["reverse"]
            else:
                _rm_sort["col"] = col
                _rm_sort["reverse"] = False
            rev = _rm_sort["reverse"]
            ind = "▲" if not rev else "▼"
            for cid, hdr in _rm_col_labels.items():
                tbl.heading(cid, text=(hdr + " " + ind) if cid == col else hdr,
                            anchor="center",
                            command=lambda c=cid: _rm_sort_by(c))
            key_map = {
                "dt":         lambda r: str(r.get("created_at") or ""),
                "material":   lambda r: str(r.get("name") or "").lower(),
                "mat_type":   lambda r: str(r.get("material_type") or "").lower(),
                "action":     lambda r: str(r.get("action_type") or "").lower(),
                "qty_change": lambda r: float(r.get("quantity") or 0),
                "notes":      lambda r: str(r.get("reason") or "").lower(),
            }
            kf = key_map.get(col, lambda r: "")
            sorted_rows = sorted(rows_cache, key=kf, reverse=rev)
            _rm_display(sorted_rows)

        for cid, hdr, *_ in rm_col_cfg:
            tbl.heading(cid, text=hdr, anchor="center",
                        command=lambda c=cid: _rm_sort_by(c))

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
                from datetime import datetime as _datetime
                now_str = _datetime.now().strftime("%Y-%m-%d %H:%M")
                p = period_var.get()
                df_v = from_var.get().strip()
                dt_v = to_var.get().strip()
                period_label = df_v and dt_v and f"{df_v} to {dt_v}" or {
                    "today": "Today", "week": "This Week",
                    "month": "This Month", "year": "This Year"}.get(p, p)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Aissa's Kitchenette"])
                    w.writerow(["Raw Materials Movement Report"])
                    w.writerow([f"Period: {period_label}"])
                    w.writerow([f"Generated: {now_str}"])
                    w.writerow([])
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

        def load(*args):
            nonlocal rows_cache
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

            # Reset sort state on fresh load
            _rm_sort["col"] = None
            _rm_sort["reverse"] = False
            for cid, hdr in _rm_col_labels.items():
                tbl.heading(cid, text=hdr, anchor="center",
                            command=lambda c=cid: _rm_sort_by(c))
            _rm_display(rows_cache)

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
