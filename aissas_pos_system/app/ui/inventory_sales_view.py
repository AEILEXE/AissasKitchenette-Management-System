from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
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
from app.utils import money


class InventorySalesView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.order_dao = OrderDAO(db)

        self.var_view_type = tk.StringVar(value="Daily")
        self.canvas_figure = None

        self._build()
        self._refresh_data()

    def _build(self):
        # Header
        header = tk.Frame(self, bg=THEME["bg"])
        header.pack(fill="x", padx=18, pady=(14, 10))
        header.columnconfigure(1, weight=1)

        tk.Label(header, text="Sales", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w")

        # View selector
        selector_frame = tk.Frame(header, bg=THEME["bg"])
        selector_frame.grid(row=0, column=1, sticky="e")

        tk.Label(selector_frame, text="View by:", bg=THEME["bg"], fg=THEME["text"]).pack(side="left", padx=(0, 8))
        
        for view_type in ["Daily", "Monthly", "Yearly"]:
            tk.Radiobutton(
                selector_frame,
                text=view_type,
                variable=self.var_view_type,
                value=view_type,
                bg=THEME["bg"],
                fg=THEME["text"],
                command=self._refresh_data,
            ).pack(side="left", padx=6)

        # Stats box
        self.stats_frame = tk.Frame(self, bg="#ffffff", highlightthickness=1, highlightbackground="#e6e6e6")
        self.stats_frame.pack(fill="x", padx=18, pady=(0, 12))

        tk.Label(self.stats_frame, text="Sales Summary", bg="#ffffff", fg=THEME["muted"]).pack(anchor="w", padx=14, pady=(14, 6))
        
        self.stats_labels_frame = tk.Frame(self.stats_frame, bg="#ffffff")
        self.stats_labels_frame.pack(anchor="w", padx=14, pady=(0, 14))

        # Graph frame
        graph_frame = tk.Frame(self, bg=THEME["bg"])
        graph_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        self.canvas_frame = tk.Frame(graph_frame, bg="white")
        self.canvas_frame.pack(fill="both", expand=True)

        # Export buttons
        export_frame = tk.Frame(self, bg=THEME["bg"])
        export_frame.pack(fill="x", padx=18, pady=(0, 18))

        tk.Button(
            export_frame,
            text="Save as PDF",
            command=self._export_pdf,
            bg=THEME["panel2"],
            fg=THEME["text"],
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            export_frame,
            text="Save as Excel",
            command=self._export_excel,
            bg=THEME["panel2"],
            fg=THEME["text"],
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side="left")

    def _get_sales_data(self):
        """
        Get sales data based on view type.
        Returns: list of tuples (label, value)
        """
        view_type = self.var_view_type.get()
        
        # Get all completed orders
        rows = self.order_dao.list_orders(status="Completed")
        if not rows:
            return [], 0, 0

        sales_dict = {}
        total_sales = 0.0
        order_count = 0

        for row in rows:
            try:
                dt_str = row["start_dt"]
                total = float(row["total"])
                
                # Parse datetime
                dt = datetime.fromisoformat(dt_str) if isinstance(dt_str, str) else dt_str
                
                if view_type == "Daily":
                    key = dt.strftime("%Y-%m-%d")
                elif view_type == "Monthly":
                    key = dt.strftime("%Y-%m")
                else:  # Yearly
                    key = dt.strftime("%Y")

                sales_dict[key] = sales_dict.get(key, 0.0) + total
                total_sales += total
                order_count += 1
            except Exception:
                continue

        # Sort keys
        sorted_keys = sorted(sales_dict.keys())
        data = [(key, sales_dict[key]) for key in sorted_keys]
        
        return data, total_sales, order_count

    def _refresh_data(self):
        """Refresh graph and statistics."""
        data, total_sales, order_count = self._get_sales_data()

        # Update stats
        for widget in self.stats_labels_frame.winfo_children():
            widget.destroy()

        tk.Label(self.stats_labels_frame, text=f"Total Completed Orders: {order_count}", bg="#ffffff", fg=THEME["text"]).pack(anchor="w", pady=2)
        tk.Label(self.stats_labels_frame, text=f"Total Sales: {money(total_sales)}", bg="#ffffff", fg=THEME["text"], font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=2)

        # Draw graph
        self._draw_graph(data)

    def _draw_graph(self, data):
        """Draw matplotlib graph."""
        # Clear previous canvas
        for widget in self.canvas_frame.winfo_children():
            widget.destroy()

        if not data:
            tk.Label(
                self.canvas_frame,
                text="No sales data available",
                bg="white",
                fg=THEME["muted"],
                font=("Segoe UI", 12),
            ).pack(expand=True)
            return

        # Create figure
        fig = Figure(figsize=(10, 5), dpi=80)
        ax = fig.add_subplot(111)

        labels = [item[0] for item in data]
        values = [item[1] for item in data]

        # Create bar chart
        bars = ax.bar(labels, values, color="#3b5bfd", edgecolor="black", linewidth=0.5)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                f"₱{height:.0f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        ax.set_xlabel("Period", fontsize=10)
        ax.set_ylabel("Sales (₱)", fontsize=10)
        ax.set_title(f"Sales - {self.var_view_type.get()} View", fontsize=12, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
        
        # Rotate x labels if needed
        if len(labels) > 10:
            ax.tick_params(axis="x", rotation=45)

        fig.tight_layout()

        # Embed in Tkinter
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # Store reference
        self.canvas_figure = fig

    def _export_pdf(self):
        """Export graph as PDF."""
        if not self.canvas_figure:
            messagebox.showwarning("PDF Export", "No graph to export yet.")
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
        """Export sales data as Excel."""
        data, total_sales, order_count = self._get_sales_data()

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"sales_{self.var_view_type.get()}.xlsx",
        )

        if not file_path:
            return

        try:
            # Create workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sales"

            # Header
            ws["A1"] = f"Sales Report - {self.var_view_type.get()} View"
            ws["A1"].font = Font(bold=True, size=14)
            ws.merge_cells("A1:B1")

            ws["A3"] = "Period"
            ws["B3"] = "Sales (₱)"
            ws["A3"].font = Font(bold=True)
            ws["B3"].font = Font(bold=True)
            ws["A3"].fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
            ws["B3"].fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

            # Data rows
            for row_idx, (label, value) in enumerate(data, start=4):
                ws[f"A{row_idx}"] = label
                ws[f"B{row_idx}"] = value
                ws[f"B{row_idx}"].number_format = "₱#,##0.00"

            # Footer
            footer_row = len(data) + 5
            ws[f"A{footer_row}"] = "Summary"
            ws[f"A{footer_row}"].font = Font(bold=True)

            ws[f"A{footer_row + 1}"] = "Total Orders:"
            ws[f"B{footer_row + 1}"] = order_count

            ws[f"A{footer_row + 2}"] = "Total Sales:"
            ws[f"B{footer_row + 2}"] = total_sales
            ws[f"B{footer_row + 2}"].number_format = "₱#,##0.00"
            ws[f"B{footer_row + 2}"].font = Font(bold=True)

            # Adjust column widths
            ws.column_dimensions["A"].width = 20
            ws.column_dimensions["B"].width = 18

            wb.save(file_path)
            messagebox.showinfo("Excel Exported", f"Saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Excel Export Error", f"Failed to export Excel.\n\n{e}")
