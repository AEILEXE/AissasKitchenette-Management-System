from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.db.database import Database
from app.db.dao import CategoryDAO, ProductDAO, OrderDAO, DraftDAO


class POSService:
    def __init__(self, db: Database):
        self.db = db
        self.categories = CategoryDAO(db)
        self.products = ProductDAO(db)
        self.orders = OrderDAO(db)
        self.drafts = DraftDAO(db)

    def list_categories(self):
        return self.categories.list_categories()

    def list_products_by_category(self, category_id: int):
        return self.products.list_by_category(category_id)

    def list_all_products(self):
        return self.products.list_all_active()

    # ---- Drafts ----
    def list_drafts(self):
        return self.drafts.list_drafts()

    def load_draft_items(self, draft_id: int):
        draft = self.drafts.get_draft(draft_id)
        if not draft:
            return []
        payload = json.loads(draft['payload_json'])
        return payload.get('items', [])

    def delete_draft(self, draft_id: int) -> None:
        self.drafts.delete_draft(draft_id)

    def save_draft(
        self,
        title: str,
        cashier_id: int,
        items: list[dict[str, Any]],
        subtotal: float,
        discount: float,
        tax: float,
        total: float,
    ) -> int:
        payload = {
            'cashier_id': cashier_id,
            'subtotal': subtotal,
            'discount': discount,
            'tax': tax,
            'items': items
        }
        return self.drafts.create_draft(title, payload, total)

    # ---- Orders ----
    def create_order(
        self,
        cashier_id: int,
        items: list[dict[str, Any]],
        subtotal: float,
        discount: float,
        tax: float,
        total: float,
        payment_method: str,
        cash_received: float,
        change_due: float,
    ) -> int:
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = self.orders.insert_order(
            dt, cashier_id, subtotal, discount, tax, total, payment_method, cash_received, change_due
        )
        for it in items:
            self.orders.insert_item(
                order_id,
                int(it["product_id"]),
                int(it["qty"]),
                float(it["unit_price"]),
                str(it.get("note", "")),
            )
        return order_id
