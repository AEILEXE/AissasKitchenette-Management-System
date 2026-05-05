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
        order_type: str = "DINE_IN",
        table_number: str = "",
        discount_type: str = "NONE",
    ) -> int:
        """
        Create a completed or pending order and persist all items.
        All INSERTs are wrapped in a single transaction — one commit regardless
        of how many items are in the cart (was N+1 commits before).
        """
        try:
            order_type_value = str(order_type or "DINE_IN").strip().upper()
            if order_type_value not in ("DINE_IN", "TAKE_OUT"):
                order_type_value = "DINE_IN"

            table_number_value = str(table_number or "").strip()

            discount_type_value = str(discount_type or "NONE").strip().upper()
            if discount_type_value not in ("NONE", "PWD", "SENIOR", "SPECIAL"):
                discount_type_value = "SPECIAL" if float(discount or 0.0) > 0 else "NONE"

            vat_amount = float(total) * 12.0 / 112.0 if float(total) > 0 else 0.0
            receipt_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

            order_id = self.db.execute_no_commit(
                """
                INSERT INTO orders(
                    cashier_id, receipt_id, order_type, table_number, customer_name,
                    payment_method, status, reference_no,
                    subtotal, discount, discount_type, tax, vat_amount, total,
                    amount_paid, cash_received, change_due
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
                """,
                (
                    int(cashier_id),
                    "",
                    order_type_value,
                    table_number_value,
                    str(customer_name),
                    str(payment_method),
                    str(status),
                    str(reference_no),
                    float(subtotal),
                    float(discount),
                    discount_type_value,
                    float(tax),
                    float(vat_amount),
                    float(total),
                    float(amount_paid),
                    float(cash_received),
                    float(change_due),
                ),
            )
            receipt_id = f"RCP-{receipt_stamp}-{order_id}"
            # Only set receipt_id — do NOT overwrite the caller-supplied reference_no.
            # Bank/E-Wallet orders are created with reference_no='' and have it set
            # later by resolve_pending once the user provides the transaction ref.
            self.db.execute_no_commit(
                "UPDATE orders SET receipt_id=? WHERE id=?;",
                (receipt_id, int(order_id)),
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

                # Deduct product stock in the same transaction.
                # Both Completed and Pending orders deduct stock immediately
                # (pending = item is being prepared, so stock is reserved).
                # MAX(0,...) is a last-resort safety net; the check above already
                # guarantees qty <= available at this point.
                self.db.execute_no_commit(
                    "UPDATE products SET stock = MAX(0, stock - ?) WHERE id=?;",
                    (qty, product_id),
                )

            # Single commit: order + all items + all product stock updates are atomic.
            # If anything above threw, the except block rolls everything back.
            self.db.commit()
            self.db.increment_data_version()
            return order_id
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _generate_void_receipt_id(order_id: int) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"VOID-{stamp}-{int(order_id)}"

    def _validate_void_actor(self, user_id: int, username: str) -> tuple[int, str]:
        actor_id = int(user_id or 0)
        actor_username = str(username or "").strip()
        if actor_id <= 0 or not actor_username:
            raise ValueError("Unable to verify the user performing this void.")
        return actor_id, actor_username

    def _restore_stock(self, product_id: int | None, qty: int) -> None:
        if product_id is None:
            raise ValueError("Cannot restore stock for a voided item with no linked product.")

        product = self.db.fetchone(
            "SELECT id FROM products WHERE id=?;",
            (int(product_id),),
        )
        if product is None:
            raise ValueError(
                f"Cannot restore stock because product #{int(product_id)} no longer exists."
            )

        self.db.execute_no_commit(
            "UPDATE products SET stock = stock + ? WHERE id=?;",
            (int(qty), int(product_id)),
        )

    def _insert_void_record(
        self,
        order_id: int,
        void_type: str,
        order_item_id: int | None,
        voided_by_user_id: int,
        voided_by_username: str,
        reason: str,
        void_receipt_id: str,
    ) -> None:
        self.db.execute_no_commit(
            """
            INSERT INTO void_records(
                original_order_id, void_type, order_item_id,
                voided_by_user_id, voided_by_username, reason, void_receipt_id
            ) VALUES(?,?,?,?,?,?,?);
            """,
            (
                int(order_id),
                str(void_type),
                int(order_item_id) if order_item_id is not None else None,
                int(voided_by_user_id),
                str(voided_by_username),
                str(reason or ""),
                str(void_receipt_id),
            ),
        )

    def void_order_item(
        self,
        order_id: int,
        order_item_id: int,
        voided_by_user_id: int,
        voided_by_username: str,
        reason: str = "",
    ) -> str:
        actor_id, actor_username = self._validate_void_actor(voided_by_user_id, voided_by_username)
        order_id = int(order_id)
        order_item_id = int(order_item_id)
        void_receipt_id = self._generate_void_receipt_id(order_id)

        try:
            order = self.db.fetchone(
                "SELECT id, status FROM orders WHERE id=?;",
                (order_id,),
            )
            if order is None:
                raise ValueError(f"Order #{order_id} was not found.")

            status = str(order["status"] or "")
            if status == "Cancelled":
                raise ValueError(f"Order #{order_id} is already cancelled.")
            if status != "Completed":
                raise ValueError("Only completed transactions can void a selected item.")

            item = self.db.fetchone(
                """
                SELECT id AS order_item_id, order_id, product_id, qty, voided
                FROM order_items
                WHERE id=? AND order_id=?;
                """,
                (order_item_id, order_id),
            )
            if item is None:
                raise ValueError("The selected item was not found for this transaction.")
            if int(item["voided"] or 0) == 1:
                raise ValueError("The selected item has already been voided.")

            self._restore_stock(item["product_id"], int(item["qty"]))

            self.db.execute_no_commit(
                "UPDATE order_items SET voided=1 WHERE id=? AND voided=0;",
                (order_item_id,),
            )
            self._insert_void_record(
                order_id,
                "ITEM",
                order_item_id,
                actor_id,
                actor_username,
                reason,
                void_receipt_id,
            )

            remaining = self.db.fetchone(
                "SELECT COUNT(*) AS c FROM order_items WHERE order_id=? AND voided=0;",
                (order_id,),
            )
            if remaining and int(remaining["c"]) == 0:
                self.db.execute_no_commit(
                    "UPDATE orders SET status='Cancelled' WHERE id=? AND status!='Cancelled';",
                    (order_id,),
                )

            self.db.commit()
            self.db.increment_data_version()
            return void_receipt_id
        except Exception:
            self.db.rollback()
            raise

    def void_order_transaction(
        self,
        order_id: int,
        voided_by_user_id: int,
        voided_by_username: str,
        reason: str = "",
    ) -> str:
        actor_id, actor_username = self._validate_void_actor(voided_by_user_id, voided_by_username)
        order_id = int(order_id)
        void_receipt_id = self._generate_void_receipt_id(order_id)

        try:
            order = self.db.fetchone(
                "SELECT id, status FROM orders WHERE id=?;",
                (order_id,),
            )
            if order is None:
                raise ValueError(f"Order #{order_id} was not found.")

            status = str(order["status"] or "")
            if status == "Cancelled":
                raise ValueError(f"Order #{order_id} is already cancelled.")
            if status not in ("Completed", "Pending"):
                raise ValueError(f"Order #{order_id} cannot be voided from status '{status}'.")

            items = self.db.fetchall(
                """
                SELECT id AS order_item_id, product_id, qty
                FROM order_items
                WHERE order_id=? AND voided=0
                ORDER BY id;
                """,
                (order_id,),
            )
            if not items:
                raise ValueError("There are no active items left to void in this transaction.")

            for item in items:
                self._restore_stock(item["product_id"], int(item["qty"]))

            self.db.execute_no_commit(
                "UPDATE order_items SET voided=1 WHERE order_id=? AND voided=0;",
                (order_id,),
            )

            if status == "Pending":
                self.db.execute_no_commit(
                    """
                    UPDATE orders
                    SET status='Cancelled',
                        end_datetime=datetime('now','localtime')
                    WHERE id=? AND status!='Cancelled';
                    """,
                    (order_id,),
                )
            else:
                self.db.execute_no_commit(
                    "UPDATE orders SET status='Cancelled' WHERE id=? AND status!='Cancelled';",
                    (order_id,),
                )

            self._insert_void_record(
                order_id,
                "TRANSACTION",
                None,
                actor_id,
                actor_username,
                reason,
                void_receipt_id,
            )

            self.db.commit()
            self.db.increment_data_version()
            return void_receipt_id
        except Exception:
            self.db.rollback()
            raise
