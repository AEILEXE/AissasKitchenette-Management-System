from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox

from app.db.database import Database
from app.services.auth_service import AuthService
from app.services.report_service import ReportService
from app.services.export_service import ExportService
from app.utils import money


class ReportsView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg="#f2f2f2")
        self.db = db
        self.auth = auth
        self.reports = ReportService(db)
        self.exporter = ExportService(db)

        self._build()
        self.refresh()

    def _build(self):
        tk.Label(self, text="Reports", font=("Segoe UI", 14, "bold"), bg="#f2f2f2").pack(anchor=tk.W, padx=10, pady=10)

        self.lbl_summary = tk.Label(self, text="", bg="#f2f2f2", font=("Segoe UI", 11))
        self.lbl_summary.pack(anchor=tk.W, padx=10)

        tk.Label(self, text="Best Sellers (Today)", bg="#f2f2f2", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, padx=10, pady=(10,0))

        self.tbl = ttk.Treeview(self, columns=("qty",), show="headings", height=15)
        self.tbl.heading("qty", text="Qty Sold")
        self.tbl.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        btns = tk.Frame(self, bg="#f2f2f2")
        btns.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(btns, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        tk.Button(btns, text="Export Inventory CSV", command=self.export_inventory).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text="Export Best Sellers CSV", command=self.export_best).pack(side=tk.LEFT, padx=5)

    def refresh(self):
        s = self.reports.today_summary()
        orders = int(s["order_count"]) if s else 0
        sales = float(s["total_sales"]) if s else 0.0
        self.lbl_summary.config(text=f"Orders Today: {orders}   |   Total Sales Today: {money(sales)}")

        self.tbl.delete(*self.tbl.get_children())
        rows = self.reports.today_best_sellers(20)
        for r in rows:
            self.tbl.insert("", tk.END, iid=r["name"], values=(r["total_qty"],), text=r["name"])
            # Treeview headings are only qty; show name in first column "text"
        # show name as item text:
        self.tbl.configure(show="tree headings")

    def export_inventory(self):
        path = self.exporter.export_inventory_csv()
        messagebox.showinfo("Export", f"Saved: {path}")

    def export_best(self):
        path = self.exporter.export_best_sellers_today_csv()
        messagebox.showinfo("Export", f"Saved: {path}")
