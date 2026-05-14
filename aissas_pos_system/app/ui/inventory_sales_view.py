"""
app/ui/inventory_sales_view.py
────────────────────────────────
Part 4 — Sales page redesign.
- KPI summary cards: Total Sales, Total Orders, Average Order Value
- Chart wrapped in a styled card container
- Improved Daily / Monthly / Yearly toggle (pill-style radio buttons)
- Modern export buttons
- matplotlib logic is 100% unchanged
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

import openpyxl
import os

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO
from app.services.auth_service import AuthService
from app.ui import ui_scale
from app.utils import money
from app.constants import P_EXPORT


class InventorySalesView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db         = db
        self.auth       = auth
        self.order_dao  = OrderDAO(db)

        self.var_view_type  = tk.StringVar(value="Daily")
        self.canvas_figure  = None

        # Custom date range (only used when view_type = "Custom")
        self.var_from = tk.StringVar()
        self.var_to   = tk.StringVar()
        self._custom_bar: tk.Frame | None = None

        # ── Scrollable wrapper ────────────────────────────────────────────────
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._scroll_canvas = tk.Canvas(self, bg=THEME["bg"],
                                        highlightthickness=0)
        self._scroll_canvas.grid(row=0, column=0, sticky="nsew")

        _vsb = ttk.Scrollbar(self, orient="vertical",
                             command=self._scroll_canvas.yview)
        _vsb.grid(row=0, column=1, sticky="ns")
        self._scroll_canvas.configure(yscrollcommand=_vsb.set)

        # Inner frame — _build() grids everything here instead of on self
        self._inner = tk.Frame(self._scroll_canvas, bg=THEME["bg"])
        self._inner_id = self._scroll_canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )

        # Resize helpers
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse-wheel scrolling (Windows / Linux / macOS)
        self._scroll_canvas.bind_all("<MouseWheel>",   self._on_mousewheel)
        self._scroll_canvas.bind_all("<Button-4>",     self._on_mousewheel)
        self._scroll_canvas.bind_all("<Button-5>",     self._on_mousewheel)

        self._build()
        self._refresh_data()

    # ── Scroll helpers ────────────────────────────────────────────────────────

    def _on_inner_configure(self, _event=None):
        self._scroll_canvas.configure(
            scrollregion=self._scroll_canvas.bbox("all")
        )

    def _on_canvas_configure(self, event):
        self._scroll_canvas.itemconfig(self._inner_id, width=event.width)

    def _on_mousewheel(self, event):
        # Only scroll when the pointer is over this canvas
        if str(event.widget).startswith(str(self._scroll_canvas)):
            return
        if event.num == 4:
            self._scroll_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._scroll_canvas.yview_scroll(1, "units")
        else:
            self._scroll_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        # Layout is on the scrollable inner frame, not on self
        _inner = self._inner
        _inner.columnconfigure(0, weight=1)
        # chart row still gets a minimum height; scroll canvas handles vertical expansion
        _inner.rowconfigure(3, minsize=520)

        # ── Page header ───────────────────────────────────────────────────────
        hdr = tk.Frame(_inner, bg=THEME["bg"])
        hdr.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 10))
        hdr.columnconfigure(0, weight=1)

        tk.Label(
            hdr, text="Sales Analytics",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", f(20), "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            hdr, text="Overview of completed order revenue",
            bg=THEME["bg"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
        ).grid(row=1, column=0, sticky="w")

        # View-type toggle (pill radio buttons)
        toggle_frame = tk.Frame(hdr, bg=THEME["beige"],
                                highlightthickness=1, highlightbackground=THEME["border"])
        toggle_frame.grid(row=0, column=1, rowspan=2, sticky="e")

        self._toggle_btns: dict[str, tk.Button] = {}
        for vt in ["Daily", "Weekly", "Monthly", "Yearly", "Custom"]:
            btn = tk.Button(
                toggle_frame, text=vt,
                bg=THEME["beige"], fg=THEME["muted"],
                bd=0, padx=sp(12), pady=sp(6),
                cursor="hand2",
                font=("Segoe UI", f(9)),
                command=lambda v=vt: self._set_view_type(v),
            )
            btn.pack(side="left", padx=2, pady=2)
            self._toggle_btns[vt] = btn
        self._update_toggle_style()

        # ── Custom date range bar (visible only when view_type = "Custom") ───
        self._custom_bar = tk.Frame(_inner, bg=THEME["panel"],
                                     highlightthickness=1,
                                     highlightbackground=THEME["border"])
        # Not gridded yet — _set_view_type controls visibility.
        self._custom_bar.columnconfigure(99, weight=1)

        tk.Label(self._custom_bar, text="From:",
                 bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", f(9))
                 ).pack(side="left", padx=(12, 4), pady=8)
        ent_from = tk.Entry(self._custom_bar, textvariable=self.var_from,
                            width=12, bd=0,
                            bg=THEME["beige"], fg=THEME["text"],
                            insertbackground="#3d2b1f", insertwidth=2,
                            font=("Segoe UI", f(9)))
        ent_from.pack(side="left", ipady=5, pady=8)
        tk.Button(self._custom_bar, text="📅",
                  command=lambda: self._open_picker(self.var_from),
                  bg=THEME["primary"], fg="white",
                  bd=0, padx=10, cursor="hand2",
                  font=("Segoe UI", f(10), "bold")
                  ).pack(side="left", padx=(4, 12), ipady=4, pady=8)

        tk.Label(self._custom_bar, text="To:",
                 bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", f(9))
                 ).pack(side="left", padx=(0, 4), pady=8)
        ent_to = tk.Entry(self._custom_bar, textvariable=self.var_to,
                          width=12, bd=0,
                          bg=THEME["beige"], fg=THEME["text"],
                          insertbackground="#3d2b1f", insertwidth=2,
                          font=("Segoe UI", f(9)))
        ent_to.pack(side="left", ipady=5, pady=8)
        tk.Button(self._custom_bar, text="📅",
                  command=lambda: self._open_picker(self.var_to),
                  bg=THEME["primary"], fg="white",
                  bd=0, padx=10, cursor="hand2",
                  font=("Segoe UI", f(10), "bold")
                  ).pack(side="left", padx=(4, 8), ipady=4, pady=8)

        tk.Button(self._custom_bar, text="Apply",
                  command=self._apply_custom_range,
                  bg=THEME["success"], fg="white",
                  activebackground=THEME["primary_dark"],
                  activeforeground="white",
                  bd=0, padx=sp(14), pady=sp(6), cursor="hand2",
                  font=("Segoe UI", f(9), "bold")
                  ).pack(side="left", padx=(8, 12), pady=8)

        # ── KPI cards row ─────────────────────────────────────────────────────
        self.kpi_row = tk.Frame(_inner, bg=THEME["bg"])
        self.kpi_row.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
        for i in range(3):
            self.kpi_row.columnconfigure(i, weight=1, uniform="kpi")

        # KPI placeholders (populated in _refresh_data)
        self._kpi_frames: list[tk.Frame] = []
        for i in range(3):
            pad = (0, 8) if i < 2 else (0, 0)
            card = tk.Frame(
                self.kpi_row, bg=THEME["panel"],
                highlightthickness=1, highlightbackground=THEME["border"],
            )
            card.grid(row=0, column=i, sticky="ew", padx=pad)
            self._kpi_frames.append(card)

        # ── Chart card ────────────────────────────────────────────────────────
        chart_card = tk.Frame(
            _inner, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        chart_card.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 10))
        chart_card.rowconfigure(1, weight=1)
        chart_card.columnconfigure(0, weight=1)

        # Chart header
        chart_hdr = tk.Frame(chart_card, bg=THEME["panel"])
        chart_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 6))
        chart_hdr.columnconfigure(0, weight=1)

        self._chart_title_lbl = tk.Label(
            chart_hdr, text="Sales Chart",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", f(11), "bold"), anchor="w",
        )
        self._chart_title_lbl.grid(row=0, column=0, sticky="w")

        # Chart canvas container
        self.canvas_frame = tk.Frame(chart_card, bg="white", height=500)
        self.canvas_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))
        self.canvas_frame.pack_propagate(False)

        # ── Payment breakdown card ────────────────────────────────────────────
        # Mirrors the dashboard's "Payment Methods" widget but scoped to the
        # currently-selected period (Daily / Weekly / Monthly / Yearly /
        # Custom).  Refreshed by _refresh_data() alongside the KPI cards.
        self._pay_card = tk.Frame(
            _inner, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        self._pay_card.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 10))

        pay_hdr = tk.Frame(self._pay_card, bg=THEME["panel"])
        pay_hdr.pack(fill="x", padx=14, pady=(10, 4))
        self._pay_title_lbl = tk.Label(
            pay_hdr, text="Payment Breakdown",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", f(11), "bold"), anchor="w",
        )
        self._pay_title_lbl.pack(side="left")
        tk.Label(
            pay_hdr,
            text="Totals per payment method for the selected period",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
        ).pack(side="left", padx=(10, 0))

        self._pay_body = tk.Frame(self._pay_card, bg=THEME["panel"])
        self._pay_body.pack(fill="x", padx=14, pady=(0, 12))

        # ── Export bar (only shown if user has export permission) ─────────────
        if self.auth.has_permission(P_EXPORT):
            export_bar = tk.Frame(
                _inner, bg=THEME["panel"],
                highlightthickness=1, highlightbackground=THEME["border"],
            )
            export_bar.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 16))

            tk.Label(
                export_bar, text="Export",
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", f(9), "bold"),
            ).pack(side="left", padx=(14, 10), pady=10)

            # separator
            tk.Frame(export_bar, bg=THEME["border"], width=1).pack(side="left", fill="y", pady=6)

            tk.Button(
                export_bar, text="⬇  Save as PDF",
                command=self._export_pdf,
                bg=THEME["brown"], fg="white",
                activebackground=THEME["brown_dark"], activeforeground="white",
                bd=0, padx=sp(14), pady=sp(8), cursor="hand2",
                font=("Segoe UI", f(9), "bold"),
            ).pack(side="left", padx=(12, 8), pady=8)

            tk.Button(
                export_bar, text="⬇  Save as Excel",
                command=self._export_excel,
                bg=THEME["accent"], fg="white",
                activebackground=THEME["brown"], activeforeground="white",
                bd=0, padx=sp(14), pady=sp(8), cursor="hand2",
                font=("Segoe UI", f(9), "bold"),
            ).pack(side="left", pady=8)

    # ──────────────────────────────────────────────────────────────────────────
    # Toggle helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _set_view_type(self, vt: str):
        self.var_view_type.set(vt)
        self._update_toggle_style()
        self._toggle_custom_bar()
        self._refresh_data()

    def _toggle_custom_bar(self):
        """Show the date-range bar only when Custom is active."""
        bar = getattr(self, "_custom_bar", None)
        if bar is None:
            return
        try:
            if self.var_view_type.get() == "Custom":
                bar.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
            else:
                bar.grid_remove()
        except Exception:
            pass

    def _open_picker(self, target: tk.StringVar):
        """Open the shared pure-Tk DatePickerDialog for a date entry."""
        try:
            from app.ui.transactions_view import DatePickerDialog
            dlg = DatePickerDialog(self, initial=target.get() or None)
            if dlg.result:
                target.set(dlg.result)
        except Exception:
            pass

    def _apply_custom_range(self):
        """Validate and re-render with the chosen [from, to] range."""
        from datetime import date as _date
        f = (self.var_from.get() or "").strip()
        t = (self.var_to.get() or "").strip()
        if not f or not t:
            messagebox.showerror("Missing Date",
                                 "Please pick both Start and End dates.",
                                 parent=self)
            return
        try:
            df = _date.fromisoformat(f)
            dt = _date.fromisoformat(t)
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 "Dates must be valid YYYY-MM-DD values.",
                                 parent=self)
            return
        if df > dt:
            messagebox.showerror("Invalid Range",
                                 "Start Date must be on or before End Date.",
                                 parent=self)
            return
        self._refresh_data()

    def _update_toggle_style(self):
        active = self.var_view_type.get()
        for vt, btn in self._toggle_btns.items():
            if vt == active:
                btn.configure(bg=THEME["brown"], fg="white",
                              font=("Segoe UI", ui_scale.scale_font(9), "bold"))
            else:
                btn.configure(bg=THEME["beige"], fg=THEME["muted"],
                              font=("Segoe UI", ui_scale.scale_font(9)))

    # ──────────────────────────────────────────────────────────────────────────
    # KPI cards
    # ──────────────────────────────────────────────────────────────────────────

    def _refresh_kpi(self, total_sales: float, order_count: int):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        avg = total_sales / order_count if order_count else 0.0

        kpi_data = [
            ("Total Sales",       money(total_sales),   f"from {order_count} orders",   THEME["success"]),
            ("Total Orders",      str(order_count),     "completed orders",              THEME["brown"]),
            ("Average Order",     money(avg),           "per completed order",           THEME["accent"]),
        ]

        for frame, (title, value, subtitle, accent) in zip(self._kpi_frames, kpi_data):
            for w in frame.winfo_children():
                w.destroy()

            bar = tk.Frame(frame, bg=accent, height=4)
            bar.pack(fill="x")

            tk.Label(frame, text=title,
                     bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", f(9))).pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(frame, text=value,
                     bg=THEME["panel"], fg=accent,
                     font=("Segoe UI", f(18), "bold")).pack(anchor="w", padx=14)
            tk.Label(frame, text=subtitle,
                     bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", f(8))).pack(anchor="w", padx=14, pady=(2, 12))

    # ──────────────────────────────────────────────────────────────────────────
    # Data (unchanged logic)
    # ──────────────────────────────────────────────────────────────────────────

    def _get_sales_data(self):
        from datetime import date as _date
        view_type = self.var_view_type.get()
        rows = self.order_dao.list_orders(status="Completed")
        if not rows:
            return [], 0.0, 0

        # Custom range bounds (only used when view_type = "Custom")
        custom_from = custom_to = None
        if view_type == "Custom":
            try:
                custom_from = _date.fromisoformat(self.var_from.get().strip())
                custom_to   = _date.fromisoformat(self.var_to.get().strip())
            except Exception:
                # Range not set — return empty so the view shows empty state
                return [], 0.0, 0

        now = datetime.now()
        current_year_month = now.strftime("%Y-%m")

        sales_dict: dict[str, float] = {}
        total_sales = 0.0
        order_count = 0

        for row in rows:
            try:
                dt_str = row["start_dt"]
                total  = float(row["total"])
                dt     = datetime.fromisoformat(dt_str) if isinstance(dt_str, str) else dt_str

                if view_type == "Daily":
                    if dt.strftime("%Y-%m") != current_year_month:
                        total_sales += total
                        order_count += 1
                        continue
                    key = dt.strftime("%d")
                elif view_type == "Weekly":
                    key = dt.strftime("%Y-W%W")
                elif view_type == "Monthly":
                    key = dt.strftime("%Y-%m")
                elif view_type == "Yearly":
                    key = dt.strftime("%Y")
                else:  # Custom
                    d_only = dt.date()
                    if not (custom_from <= d_only <= custom_to):
                        continue
                    span_days = (custom_to - custom_from).days
                    if span_days <= 60:
                        key = dt.strftime("%Y-%m-%d")
                    elif span_days <= 365:
                        key = dt.strftime("%Y-W%W")
                    else:
                        key = dt.strftime("%Y-%m")

                sales_dict[key] = sales_dict.get(key, 0.0) + total
                total_sales    += total
                order_count    += 1
            except Exception:
                continue

        sorted_keys = sorted(sales_dict.keys())
        return [(k, sales_dict[k]) for k in sorted_keys], total_sales, order_count

    def _refresh_data(self):
        data, total_sales, order_count = self._get_sales_data()
        self._refresh_kpi(total_sales, order_count)

        vt = self.var_view_type.get()
        if vt == "Custom":
            f = (self.var_from.get() or "").strip()
            t = (self.var_to.get() or "").strip()
            if f and t:
                self._chart_title_lbl.configure(text=f"Sales — Custom: {f} → {t}")
            else:
                self._chart_title_lbl.configure(
                    text="Sales — Custom: pick a date range")
        else:
            self._chart_title_lbl.configure(text=f"Sales — {vt} View")

        self._draw_graph(data)
        self._refresh_payment_breakdown()

    # ──────────────────────────────────────────────────────────────────────────
    # Payment Breakdown
    # ──────────────────────────────────────────────────────────────────────────

    def _payment_period_clause(self) -> tuple[str, tuple]:
        """SQL clause + params restricting to the currently selected period.
        Targets the `datetime` column in `orders` (localtime)."""
        vt = self.var_view_type.get()
        now = datetime.now()
        if vt == "Daily":
            return ("strftime('%Y-%m', datetime, 'localtime') = ?",
                    (now.strftime("%Y-%m"),))
        if vt == "Weekly":
            return ("DATE(datetime, 'localtime') >= DATE('now', 'localtime', '-6 days')",
                    ())
        if vt == "Monthly":
            return ("strftime('%Y', datetime, 'localtime') = ?",
                    (now.strftime("%Y"),))
        if vt == "Yearly":
            return ("1=1", ())
        if vt == "Custom":
            from datetime import date as _date
            try:
                df = _date.fromisoformat(self.var_from.get().strip())
                dt = _date.fromisoformat(self.var_to.get().strip())
            except Exception:
                return ("1=0", ())  # no range chosen — return nothing
            return ("DATE(datetime, 'localtime') BETWEEN DATE(?) AND DATE(?)",
                    (df.isoformat(), dt.isoformat()))
        return ("1=1", ())

    def _fetch_payment_breakdown(self) -> list[dict]:
        clause, params = self._payment_period_clause()
        try:
            rows = self.db.fetchall(
                f"""
                SELECT COALESCE(NULLIF(payment_method, ''), 'Unknown') AS method,
                       COUNT(*) AS cnt,
                       COALESCE(SUM(total), 0) AS total
                FROM orders
                WHERE status = 'Completed' AND {clause}
                GROUP BY method
                ORDER BY total DESC;
                """,
                params,
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _refresh_payment_breakdown(self) -> None:
        body = getattr(self, "_pay_body", None)
        if body is None or not body.winfo_exists():
            return
        for w in body.winfo_children():
            w.destroy()

        f  = ui_scale.scale_font
        sp = ui_scale.s

        rows = self._fetch_payment_breakdown()
        total = sum(float(r.get("total") or 0) for r in rows)

        if not rows or total <= 0:
            tk.Label(
                body,
                text="No completed orders for the selected period.",
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", f(10), "italic"),
            ).pack(anchor="w", pady=8)
            return

        accents = [
            THEME["success"], THEME["primary"], THEME["accent"],
            THEME["brown"], THEME["warning"], THEME["danger"],
        ]
        grid = tk.Frame(body, bg=THEME["panel"])
        grid.pack(fill="x")
        # Up to four columns side-by-side; wraps to additional rows if more.
        per_row = min(4, max(1, len(rows)))
        for c in range(per_row):
            grid.columnconfigure(c, weight=1, uniform="pay")

        for i, r in enumerate(rows):
            method = str(r.get("method") or "—")
            amt    = float(r.get("total") or 0.0)
            cnt    = int(r.get("cnt") or 0)
            pct    = (amt / total * 100.0) if total else 0.0
            accent = accents[i % len(accents)]

            row_i, col_i = divmod(i, per_row)
            card = tk.Frame(
                grid, bg=THEME["panel"],
                highlightthickness=1, highlightbackground=THEME["border"],
            )
            card.grid(row=row_i, column=col_i, sticky="nsew",
                      padx=(0 if col_i == 0 else 8, 0),
                      pady=(0 if row_i == 0 else 8, 0))
            tk.Frame(card, bg=accent, height=3).pack(fill="x")
            tk.Label(card, text=method, bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", f(9), "bold"),
                     anchor="w").pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(card, text=money(amt), bg=THEME["panel"], fg=accent,
                     font=("Segoe UI", f(16), "bold"),
                     anchor="w").pack(anchor="w", padx=12, pady=(2, 0))
            tk.Label(
                card,
                text=f"{cnt} order{'s' if cnt != 1 else ''}  •  {pct:.1f}%",
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", f(8)),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(0, 10))

    # ──────────────────────────────────────────────────────────────────────────
    # Chart (unchanged matplotlib logic)
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_graph(self, data):
        # Destroy every previous chart widget before rendering new ones.
        # This guarantees at most one bar canvas and one pie canvas exist at any time.
        for widget in self.canvas_frame.winfo_children():
            widget.destroy()

        if not data:
            tk.Label(
                self.canvas_frame,
                text="No sales data available",
                bg="white", fg=THEME["muted"],
                font=("Segoe UI", 12),
            ).pack(expand=True)
            return

        import matplotlib
        from matplotlib.figure import Figure  # deferred — avoids freeze on first tab open
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: F811
        import numpy as _np

        labels = [item[0] for item in data]
        values = [item[1] for item in data]

        # Category breakdown for pie chart
        category_data: dict[str, float] = {}
        try:
            cat_rows = self.order_dao.db.fetchall(
                """SELECT COALESCE(c.name,'Uncategorized') AS cat,
                          SUM(oi.subtotal) AS rev
                   FROM order_items oi
                   JOIN products p ON p.id = oi.product_id
                   LEFT JOIN categories c ON c.id = p.category_id
                   JOIN orders o ON o.id = oi.order_id
                   WHERE o.status='Completed' AND oi.voided=0
                   GROUP BY cat ORDER BY rev DESC LIMIT 8;"""
            )
            category_data = {r["cat"]: float(r["rev"] or 0) for r in cat_rows}
        except Exception:
            pass

        has_pie = bool(category_data)

        charts_container = tk.Frame(self.canvas_frame, bg="white")
        charts_container.pack(fill="both", expand=True)

        # ── Bar chart figure ──────────────────────────────────────────────────
        matplotlib.rcParams.update({
            'figure.facecolor': '#FFFFFF',
            'axes.facecolor':   '#F9F9F9',
            'text.color':       '#333333',
            'axes.labelcolor':  '#333333',
            'xtick.color':      '#333333',
            'ytick.color':      '#333333',
        })
        fig_bar = Figure(figsize=(7, 4), tight_layout=True)
        fig_bar.patch.set_facecolor('#FFFFFF')
        ax = fig_bar.add_subplot(111)

        # ── Bar chart ─────────────────────────────────────────────────────────
        n_bars = len(labels)
        # Gradient: interpolate from #8c6e3b to #c4975a across bars
        c1 = _np.array([0x8c, 0x6e, 0x3b]) / 255
        c2 = _np.array([0xc4, 0x97, 0x5a]) / 255
        bar_colors = [tuple(c1 + (c2 - c1) * (i / max(n_bars - 1, 1))) for i in range(n_bars)]

        bars = ax.bar(labels, values, color=bar_colors, edgecolor="none", linewidth=0,
                      width=0.65)
        ax.set_facecolor("#F9F9F9")

        # Value labels on bars
        max_val = max(values) if values else 1
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    val + max_val * 0.01,
                    f"₱{val:,.0f}", ha="center", va="bottom",
                    fontsize=7, color="#5a3e28",
                )

        ax.set_xlabel("Period", fontsize=9, color="#333333")
        ax.set_ylabel("Sales (₱)", fontsize=9, color="#333333")
        ax.xaxis.label.set_color("#333333")
        ax.yaxis.label.set_color("#333333")
        ax.grid(axis="y", alpha=0.25, color="#ccc", linestyle="--")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_edgecolor("#CCCCCC")
        ax.tick_params(colors="#333333", labelsize=8)

        # Always rotate x-axis labels 45° — prevents overlap regardless of bar count
        _x_fontsize = 7 if n_bars > 12 else 8
        ax.tick_params(axis="x", rotation=45, labelsize=_x_fontsize)
        for _lbl in ax.get_xticklabels():
            _lbl.set_ha("right")

        # ── Hover annotation ──────────────────────────────────────────────────
        annot = ax.annotate("", xy=(0, 0), xytext=(10, 10),
                            textcoords="offset points",
                            bbox=dict(boxstyle="round,pad=0.3", fc="#fff8f0",
                                      ec="#8c6e3b", lw=1),
                            fontsize=9, color="#3d2b1f")
        annot.set_visible(False)

        def _on_hover(event):
            if event.inaxes != ax:
                annot.set_visible(False)
                try:
                    fig_bar.canvas.draw_idle()
                except Exception:
                    pass
                return
            for bar, lbl, val in zip(bars, labels, values):
                if bar.contains(event)[0]:
                    annot.xy = (bar.get_x() + bar.get_width() / 2,
                                bar.get_height())
                    annot.set_text(f"{lbl}\n₱{val:,.2f}")
                    annot.set_visible(True)
                    try:
                        fig_bar.canvas.draw_idle()
                    except Exception:
                        pass
                    return
            annot.set_visible(False)
            try:
                fig_bar.canvas.draw_idle()
            except Exception:
                pass

        bar_frame = tk.Frame(charts_container, bg="#FFFFFF")
        bar_frame.pack(fill="both", expand=True, side="left")

        canvas_bar = FigureCanvasTkAgg(fig_bar, master=bar_frame)
        widget_bar = canvas_bar.get_tk_widget()
        widget_bar.configure(bg="#FFFFFF")
        widget_bar.pack(fill="both", expand=True)
        charts_container.update_idletasks()
        canvas_bar.draw()

        if has_pie:
            # ── Pie chart figure (separate, side-by-side with bar chart) ─────
            matplotlib.rcParams.update({
                'figure.facecolor': '#FFFFFF',
                'axes.facecolor':   '#FFFFFF',
                'text.color':       '#333333',
                'axes.labelcolor':  '#333333',
                'xtick.color':      '#333333',
                'ytick.color':      '#333333',
            })
            fig_pie = Figure(figsize=(5, 6))
            fig_pie.patch.set_facecolor('#FFFFFF')
            ax_pie = fig_pie.add_subplot(111)
            ax_pie.set_facecolor('#FFFFFF')

            pie_labels = list(category_data.keys())
            pie_vals   = list(category_data.values())
            pie_colors = [
                "#8c6e3b", "#c4975a", "#e8b87a", "#a07855",
                "#d4a96a", "#6b4b2a", "#b8905c", "#9a7040",
            ][:len(pie_vals)]
            wedges, _, autotexts = ax_pie.pie(
                pie_vals,
                colors=pie_colors,
                autopct=lambda p: f"{p:.1f}%" if p > 5 else "",
                startangle=90,
                pctdistance=0.85,
                wedgeprops=dict(linewidth=1.5, edgecolor="white"),
            )
            for at in autotexts:
                at.set_fontsize(8)
                at.set_color("white")
                at.set_fontweight("bold")
            short_labels = [
                lbl[:15] + "…" if len(lbl) > 15 else lbl
                for lbl in pie_labels
            ]
            ax_pie.legend(
                wedges, short_labels,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.08),
                ncol=3,
                fontsize=7,
                frameon=False,
                labelcolor='#333333',
            )
            ax_pie.set_title("Revenue by Category", fontsize=11,
                             color="#3d2b1f", fontweight="bold", pad=12)
            ax_pie.set_aspect('equal')
            fig_pie.subplots_adjust(top=0.88, bottom=0.22, left=0.05, right=0.95)

            pie_frame = tk.Frame(charts_container, bg="#FFFFFF", width=420, height=520)
            pie_frame.pack(fill="both", expand=True, side="left")
            pie_frame.pack_propagate(False)

            canvas_pie = FigureCanvasTkAgg(fig_pie, master=pie_frame)
            widget_pie = canvas_pie.get_tk_widget()
            widget_pie.configure(bg="#FFFFFF")
            widget_pie.pack(fill="both", expand=True)
            pie_frame.update_idletasks()
            canvas_pie.draw()

        try:
            canvas_bar.mpl_connect("motion_notify_event", _on_hover)
        except Exception:
            pass
        self.canvas_figure = fig_bar

    # ──────────────────────────────────────────────────────────────────────────
    # Export (unchanged logic)
    # ──────────────────────────────────────────────────────────────────────────

    def _export_pdf(self):
        if not self.auth.has_permission(P_EXPORT):
            messagebox.showerror("Access Denied", "You do not have permission to export data.")
            return
        data, total_sales, order_count = self._get_sales_data()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"sales_{self.var_view_type.get()}.pdf",
        )
        if not file_path:
            return
        try:
            from matplotlib.backends.backend_pdf import PdfPages
            from matplotlib.figure import Figure
            import matplotlib.gridspec as gridspec

            vt  = self.var_view_type.get()
            avg = total_sales / order_count if order_count else 0.0
            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            with PdfPages(file_path) as pdf:
                fig = Figure(figsize=(10, 7))
                gs  = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[1, 3],
                                        hspace=0.5)

                # ── Header / summary panel ────────────────────────────────────
                ax_info = fig.add_subplot(gs[0])
                ax_info.axis("off")

                summary_lines = [
                    f"Aissas Kitchenette — Sales Report ({vt})",
                    f"Generated: {now}",
                    f"",
                    f"Total Sales:     \u20b1{total_sales:,.2f}",
                    f"Total Orders:    {order_count}",
                    f"Average Order:   \u20b1{avg:,.2f}",
                ]
                if data:
                    summary_lines.append(f"Date Range:      {data[0][0]}  to  {data[-1][0]}")

                ax_info.text(
                    0.02, 0.95, "\n".join(summary_lines),
                    transform=ax_info.transAxes,
                    fontsize=10, verticalalignment="top",
                    fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="#f9f0e8",
                              edgecolor="#c8a882", linewidth=1),
                )

                # ── Bar chart ─────────────────────────────────────────────────
                ax_chart = fig.add_subplot(gs[1])

                if data:
                    labels = [item[0] for item in data]
                    values = [item[1] for item in data]

                    bars = ax_chart.bar(labels, values, color="#6B4B3A",
                                        edgecolor="none")
                    for bar in bars:
                        h = bar.get_height()
                        if h > 0:
                            ax_chart.text(
                                bar.get_x() + bar.get_width() / 2, h,
                                f"\u20b1{h:,.0f}",
                                ha="center", va="bottom", fontsize=8,
                            )

                    ax_chart.set_xlabel("Period", fontsize=10)
                    ax_chart.set_ylabel("Sales (\u20b1)", fontsize=10)
                    ax_chart.set_title(f"Sales — {vt} View", fontsize=12, pad=10)
                    ax_chart.grid(axis="y", alpha=0.25)
                    ax_chart.spines["top"].set_visible(False)
                    ax_chart.spines["right"].set_visible(False)

                    if len(labels) > 10:
                        ax_chart.tick_params(axis="x", rotation=45)
                    fig.tight_layout(rect=[0, 0, 1, 1])
                else:
                    ax_chart.text(0.5, 0.5, "No sales data available",
                                  ha="center", va="center", fontsize=12,
                                  transform=ax_chart.transAxes)
                    ax_chart.axis("off")

                pdf.savefig(fig, bbox_inches="tight")

            messagebox.showinfo("PDF Exported", f"Saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("PDF Export Error", f"Failed to export PDF.\n\n{e}")

    def _export_excel(self):
        if not self.auth.has_permission(P_EXPORT):
            messagebox.showerror("Access Denied", "You do not have permission to export data.")
            return
        data, total_sales, order_count = self._get_sales_data()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"sales_{self.var_view_type.get()}.xlsx",
        )
        if not file_path:
            return
        try:
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sales Report"

            vt  = self.var_view_type.get()
            avg = total_sales / order_count if order_count else 0.0
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            date_range = (
                f"{data[0][0]}  to  {data[-1][0]}" if data else "N/A"
            )

            # ── Title block ───────────────────────────────────────────────────
            title_fill   = PatternFill("solid", fgColor="6B4B3A")
            title_font   = Font(bold=True, size=14, color="FFFFFF")
            subtitle_font = Font(size=10, color="6E6E6E")
            bold_font    = Font(bold=True, size=10)
            header_fill  = PatternFill("solid", fgColor="EADFD2")
            header_font  = Font(bold=True, size=10, color="1F1F1F")
            total_fill   = PatternFill("solid", fgColor="F0FAF4")
            border_side  = Side(style="thin", color="D5C7B8")
            thin_border  = Border(bottom=border_side)
            center_align = Alignment(horizontal="center", vertical="center")
            right_align  = Alignment(horizontal="right", vertical="center")

            ws.merge_cells("A1:C1")
            ws["A1"] = "Aissas Kitchenette — Sales Report"
            ws["A1"].font  = title_font
            ws["A1"].fill  = title_fill
            ws["A1"].alignment = center_align
            ws.row_dimensions[1].height = 28

            ws.merge_cells("A2:C2")
            ws["A2"] = f"View: {vt}  |  Generated: {now}  |  Date Range: {date_range}"
            ws["A2"].font      = subtitle_font
            ws["A2"].alignment = center_align
            ws.row_dimensions[2].height = 18

            # ── KPI summary row ───────────────────────────────────────────────
            ws.merge_cells("A3:C3")
            ws["A3"] = (
                f"Total Sales: \u20b1{total_sales:,.2f}     "
                f"Total Orders: {order_count}     "
                f"Average Order: \u20b1{avg:,.2f}"
            )
            ws["A3"].font      = bold_font
            ws["A3"].alignment = center_align
            ws["A3"].fill      = PatternFill("solid", fgColor="FFF3E0")
            ws.row_dimensions[3].height = 20

            # ── Column headers ────────────────────────────────────────────────
            headers = ["Period", "Sales (\u20b1)", "% of Total"]
            for col_idx, h in enumerate(headers, start=1):
                cell = ws.cell(row=5, column=col_idx, value=h)
                cell.font      = header_font
                cell.fill      = header_fill
                cell.alignment = center_align if col_idx > 1 else Alignment(horizontal="left")
                cell.border    = thin_border
            ws.row_dimensions[5].height = 18

            # ── Data rows ─────────────────────────────────────────────────────
            for row_idx, (label, value) in enumerate(data, start=6):
                # Store as decimal fraction (e.g. 0.255) so Excel's 0.00% format
                # renders it correctly as "25.50%" instead of "2550.00%"
                pct = (value / total_sales) if total_sales else 0
                row_fill = PatternFill("solid", fgColor="FFFFFF" if (row_idx % 2 == 0) else "FAF7F4")

                c_period = ws.cell(row=row_idx, column=1, value=label)
                c_period.fill = row_fill

                c_sales = ws.cell(row=row_idx, column=2, value=value)
                c_sales.number_format = '"\u20b1"#,##0.00'
                c_sales.alignment     = right_align
                c_sales.fill          = row_fill

                c_pct = ws.cell(row=row_idx, column=3, value=round(pct, 6))
                c_pct.number_format = "0.00%"
                c_pct.alignment     = right_align
                c_pct.fill          = row_fill

            # ── Totals row ────────────────────────────────────────────────────
            totals_row = len(data) + 6
            ws.cell(row=totals_row, column=1, value="TOTAL").font = Font(bold=True, size=10)
            ws.cell(row=totals_row, column=1).fill = total_fill

            c_total = ws.cell(row=totals_row, column=2, value=total_sales)
            c_total.number_format = '"\u20b1"#,##0.00'
            c_total.font          = Font(bold=True, size=10)
            c_total.alignment     = right_align
            c_total.fill          = total_fill

            c_total_pct = ws.cell(row=totals_row, column=3, value=1.0)
            c_total_pct.number_format = "0.00%"
            c_total_pct.font          = Font(bold=True, size=10)
            c_total_pct.alignment     = right_align
            c_total_pct.fill          = total_fill

            # ── Column widths ─────────────────────────────────────────────────
            ws.column_dimensions["A"].width = 22
            ws.column_dimensions["B"].width = 20
            ws.column_dimensions["C"].width = 14

            # ── Freeze header rows ────────────────────────────────────────────
            ws.freeze_panes = "A6"

            wb.save(file_path)
            messagebox.showinfo("Excel Exported", f"Report saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Excel Export Error", f"Failed to export Excel.\n\n{e}")