"""
reports_view.py — Reports & Analytics View
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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
        self._build()

    def _build(self):
        # ── Page header bar ───────────────────────────────────────────────────
        hdr_bar = tk.Frame(self, bg=_SB)
        hdr_bar.pack(fill="x")
        tk.Frame(hdr_bar, bg=_RED, width=5).pack(side="left", fill="y")
        hdr_inner = tk.Frame(hdr_bar, bg=_SB)
        hdr_inner.pack(fill="x", padx=(14, 16), pady=12)
        tk.Label(hdr_inner, text="Reports & Analytics",
                 bg=_SB, fg="#FFFFFF",
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        # ── Scrollable body ───────────────────────────────────────────────────
        outer = tk.Frame(self, bg=_BG)
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

        def _on_body_cfg(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_cfg(e):
            canvas.itemconfigure(win_id, width=e.width)

        body.bind("<Configure>", _on_body_cfg)
        canvas.bind("<Configure>", _on_canvas_cfg)

        def _scroll(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        pad = dict(padx=20, pady=(0, 0))

        # ── KPI cards ─────────────────────────────────────────────────────────
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

        # ── Section helper ────────────────────────────────────────────────────
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

        # ── Product Stock Alerts ──────────────────────────────────────────────
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
            tk.Label(prod_card, text="All products have sufficient stock.",
                     bg=_PANEL, fg=_GREEN,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=12)

        # ── Raw Materials Alerts ──────────────────────────────────────────────
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

        # ── Top Products ──────────────────────────────────────────────────────
        _section_hdr("Top Selling Products")
        top_card = tk.Frame(body, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
        top_card.pack(fill="x", padx=20, pady=(0, 4))
        tk.Frame(top_card, bg=_SLATE, height=3).pack(fill="x")

        top_prods = self._fetch_top_products()
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
        try:
            rows = self.db.fetchall(
                "SELECT name, stock, low_stock FROM products "
                "WHERE active=1 AND stock <= low_stock "
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

    def _fetch_top_products(self) -> list:
        try:
            rows = self.db.fetchall(
                "SELECT p.name, "
                "       SUM(oi.quantity) AS units, "
                "       SUM(oi.quantity * oi.unit_price) AS revenue "
                "FROM order_items oi "
                "JOIN products p ON p.product_id = oi.product_id "
                "JOIN orders o ON o.order_id = oi.order_id "
                "WHERE o.status = 'Completed' "
                "GROUP BY oi.product_id "
                "ORDER BY units DESC LIMIT 10;"
            )
            return [dict(r) for r in rows]
        except Exception:
            return []
