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

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import os

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO
from app.services.auth_service import AuthService
from app.ui import ui_scale
from app.utils import money


class InventorySalesView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db         = db
        self.auth       = auth
        self.order_dao  = OrderDAO(db)

        self.var_view_type  = tk.StringVar(value="Daily")
        self.canvas_figure  = None

        self._build()
        self._refresh_data()

    # ──────────────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)   # chart row expands

        # ── Page header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["bg"])
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
        for vt in ["Daily", "Monthly", "Yearly"]:
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

        # ── KPI cards row ─────────────────────────────────────────────────────
        self.kpi_row = tk.Frame(self, bg=THEME["bg"])
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
            self, bg=THEME["panel"],
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
        self.canvas_frame = tk.Frame(chart_card, bg="white")
        self.canvas_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))

        # ── Export bar ────────────────────────────────────────────────────────
        export_bar = tk.Frame(
            self, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        export_bar.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 16))

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
        view_type = self.var_view_type.get()
        rows = self.order_dao.list_orders(status="Completed")
        if not rows:
            return [], 0.0, 0

        sales_dict: dict[str, float] = {}
        total_sales = 0.0
        order_count = 0

        for row in rows:
            try:
                dt_str = row["start_dt"]
                total  = float(row["total"])
                dt     = datetime.fromisoformat(dt_str) if isinstance(dt_str, str) else dt_str

                if view_type == "Daily":
                    key = dt.strftime("%Y-%m-%d")
                elif view_type == "Monthly":
                    key = dt.strftime("%Y-%m")
                else:
                    key = dt.strftime("%Y")

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

        # Update chart title
        vt = self.var_view_type.get()
        self._chart_title_lbl.configure(text=f"Sales — {vt} View")

        self._draw_graph(data)

    # ──────────────────────────────────────────────────────────────────────────
    # Chart (unchanged matplotlib logic)
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_graph(self, data):
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

        fig = Figure(figsize=(10, 5), dpi=80)
        ax  = fig.add_subplot(111)

        labels = [item[0] for item in data]
        values = [item[1] for item in data]

        bars = ax.bar(labels, values, color=THEME["brown"], edgecolor="none", linewidth=0)
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2, height,
                f"₱{height:.0f}", ha="center", va="bottom", fontsize=9,
            )

        ax.set_xlabel("Period", fontsize=10)
        ax.set_ylabel("Sales (₱)", fontsize=10)
        ax.grid(axis="y", alpha=0.2)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        if len(labels) > 10:
            ax.tick_params(axis="x", rotation=45)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas_figure = fig

    # ──────────────────────────────────────────────────────────────────────────
    # Export (unchanged logic)
    # ──────────────────────────────────────────────────────────────────────────

    def _export_pdf(self):
        if not self.canvas_figure:
            messagebox.showwarning("PDF Export", "No chart to export yet.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"sales_{self.var_view_type.get()}.pdf",
        )
        if not file_path:
            return
        try:
            self.canvas_figure.savefig(file_path, dpi=150, bbox_inches="tight")
            messagebox.showinfo("PDF Exported", f"Saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("PDF Export Error", f"Failed to export PDF.\n\n{e}")

    def _export_excel(self):
        data, total_sales, order_count = self._get_sales_data()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"sales_{self.var_view_type.get()}.xlsx",
        )
        if not file_path:
            return
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sales"

            ws["A1"] = f"Sales Report — {self.var_view_type.get()} View"
            ws["A1"].font = Font(bold=True, size=14)
            ws.merge_cells("A1:B1")

            ws["A3"] = "Period"
            ws["B3"] = "Sales (₱)"
            for cell in [ws["A3"], ws["B3"]]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

            for row_idx, (label, value) in enumerate(data, start=4):
                ws[f"A{row_idx}"] = label
                ws[f"B{row_idx}"] = value
                ws[f"B{row_idx}"].number_format = "₱#,##0.00"

            footer_row = len(data) + 5
            ws[f"A{footer_row}"] = "Summary"
            ws[f"A{footer_row}"].font = Font(bold=True)
            ws[f"A{footer_row+1}"] = "Total Orders:"
            ws[f"B{footer_row+1}"] = order_count
            ws[f"A{footer_row+2}"] = "Total Sales:"
            ws[f"B{footer_row+2}"] = total_sales
            ws[f"B{footer_row+2}"].number_format = "₱#,##0.00"
            ws[f"B{footer_row+2}"].font = Font(bold=True)

            ws.column_dimensions["A"].width = 20
            ws.column_dimensions["B"].width = 18

            wb.save(file_path)
            messagebox.showinfo("Excel Exported", f"Saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Excel Export Error", f"Failed to export Excel.\n\n{e}")
