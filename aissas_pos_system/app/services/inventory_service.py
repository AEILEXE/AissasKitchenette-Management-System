from __future__ import annotations
from app.db.database import Database
from app.db.dao import ProductDAO

class InventoryService:
    def __init__(self, db: Database):
        self.db = db
        self.product_dao = ProductDAO(db)

    def restock(self, product_id: int, add_qty: int) -> None:
        p = self.product_dao.get(product_id)
        if not p:
            return
        self.product_dao.set_stock(product_id, p.stock_qty + max(0, add_qty))

    def adjust(self, product_id: int, new_qty: int) -> None:
        self.product_dao.set_stock(product_id, max(0, new_qty))
