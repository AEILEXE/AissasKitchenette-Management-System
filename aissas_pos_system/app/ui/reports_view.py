"""
reports_view.py — Sales Reports View
Modern Bistro POS theme.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
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
        self._build()

    def _build(self):
        # ── Page header bar ───────────────────────────────────────────────────
        hdr_bar = tk.Frame(self, bg=_SB)
        hdr_bar.pack(fill="x")
        tk.Frame(hdr_bar, bg=_RED, width=5).pack(side="left", fill="y")
        hdr_inner = tk.Frame(hdr_bar, bg=_SB)
        hdr_inner.pack(fill="x", padx=(14, 16), pady=12)
        tk.Label(hdr_inner, text="Sales Reports",
                 bg=_SB, fg="#FFFFFF",
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=_BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        # KPI cards row
        kpi_row = tk.Frame(body, bg=_BG)
        kpi_row.pack(fill="x", pady=(0, 16))

        kpi_data = self._fetch_kpis()
        kpi_cards = [
            ("Today's Sales", _money(kpi_data["today_sales"]), _RED),
            ("This Month",    _money(kpi_data["month_sales"]), _SLATE),
            ("Total Orders",  str(kpi_data["total_orders"]),   _SB),
            ("Avg. Order",    _money(kpi_data["avg_order"]),   _GREEN),
        ]
        for i, (label, val, accent) in enumerate(kpi_cards):
            card = tk.Frame(kpi_row, bg=_PANEL,
                            highlightthickness=1,
                            highlightbackground=_BORDER)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            kpi_row.columnconfigure(i, weight=1)

            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=label, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9), anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, text=val, bg=_PANEL, fg=accent,
                     font=("Segoe UI", 18, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

        # Placeholder notice
        note_card = tk.Frame(body, bg=_PANEL,
                             highlightthickness=1,
                             highlightbackground=_BORDER)
        note_card.pack(fill="both", expand=True)
        tk.Frame(note_card, bg=_RED, height=3).pack(fill="x")
        inner = tk.Frame(note_card, bg=_PANEL)
        inner.pack(fill="both", expand=True, padx=32, pady=48)
        tk.Label(inner,
                 text="📊",
                 bg=_PANEL, fg=_RED,
                 font=("Segoe UI", 40)).pack(pady=(0, 12))
        tk.Label(inner,
                 text="Reports Module",
                 bg=_PANEL, fg=_TEXT,
                 font=("Segoe UI", 18, "bold")).pack()
        tk.Label(inner,
                 text="Sales analytics, product performance, and export tools\nwill appear here once connected to the reporting service.",
                 bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 10),
                 justify="center").pack(pady=(8, 0))

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
