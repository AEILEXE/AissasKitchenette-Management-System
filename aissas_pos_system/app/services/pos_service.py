from __future__ import annotations

import json
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

    def create_order(
        self,
        cashier_id: int,
        customer_name: str,
        payment_method: str,
        status: str,
        reference_no: str,
        items: list[dict[str, Any]],
        subtotal: float,
        discount: float,
        tax: float,
        total: float,
        amount_paid: float,
        cash_received: float,
        change_due: float,
    ) -> int:
        """
        Create a completed or pending order and persist all items.
        All INSERTs are wrapped in a single transaction — one commit regardless
        of how many items are in the cart (was N+1 commits before).
        """
        try:
            order_id = self.db.execute_no_commit(
                """
                INSERT INTO orders(
                    cashier_id, customer_name, payment_method, status, reference_no,
                    subtotal, discount, tax, total,
                    amount_paid, cash_received, change_due
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?);
                """,
                (
                    int(cashier_id), str(customer_name), str(payment_method),
                    str(status), str(reference_no),
                    float(subtotal), float(discount), float(tax), float(total),
                    float(amount_paid), float(cash_received), float(change_due),
                ),
            )
            for it in items:
                qty        = int(it["qty"])
                unit_price = float(it["unit_price"])
                product_id = int(it["product_id"])

                # Verify stock inside the transaction before committing.
                # Raises ValueError (→ rollback) when requested qty exceeds available stock.
                row = self.db.fetchone(
                    "SELECT name, stock FROM products WHERE id=? AND active=1;",
                    (product_id,),
                )
                if row is None:
                    raise ValueError(f"Product (id={product_id}) is no longer available.")
                available = int(row["stock"])
                if qty > available:
                    raise ValueError(
                        f"Insufficient stock for '{row['name']}': "
                        f"requested {qty}, only {available} available."
                    )

                self.db.execute_no_commit(
                    """
                    INSERT INTO order_items(order_id, product_id, qty, unit_price, note, subtotal)
                    VALUES(?,?,?,?,?,?);
                    """,
                    (order_id, product_id, qty, unit_price,
                     str(it.get("note", "")), qty * unit_price),
                )

                # Deduct stock in the same transaction.
                # Both Completed and Pending orders deduct stock immediately
                # (pending = item is being prepared, so stock is reserved).
                # MAX(0,...) is a last-resort safety net; the check above already
                # guarantees qty <= available at this point.
                self.db.execute_no_commit(
                    "UPDATE products SET stock = MAX(0, stock - ?) WHERE id=?;",
                    (qty, product_id),
                )

            # Single commit: order + all items + all stock updates are atomic.
            # If anything above threw, the except block rolls everything back.
            self.db.commit()
            return order_id
        except Exception:
            self.db.rollback()
            raise
