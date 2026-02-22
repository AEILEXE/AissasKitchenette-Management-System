from __future__ import annotations
import csv
from pathlib import Path
from app.config import EXPORTS_DIR
from app.db.database import Database
from app.db.dao import ProductDAO, OrderDAO

class ExportService:
    def __init__(self, db: Database):
        self.db = db
        self.product_dao = ProductDAO(db)
        self.order_dao = OrderDAO(db)

    def export_inventory_csv(self, out_path: Path | None = None) -> Path:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = out_path or (EXPORTS_DIR / "inventory.csv")
        rows = self.product_dao.list_all()
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["product_id", "name", "category", "price", "stock_qty", "low_stock", "active"])
            for r in rows:
                w.writerow([r["product_id"], r["name"], r["category"], r["price"], r["stock_qty"], r["low_stock"], r["active"]])
        return out_path

    def export_best_sellers_today_csv(self, out_path: Path | None = None) -> Path:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = out_path or (EXPORTS_DIR / "best_sellers_today.csv")
        rows = self.order_dao.best_sellers_today(50)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["product_name", "qty_sold"])
            for r in rows:
                w.writerow([r["name"], r["total_qty"]])
        return out_path
