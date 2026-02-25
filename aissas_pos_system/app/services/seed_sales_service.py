"""
app/services/seed_sales_service.py
────────────────────────────────────
DEV-ONLY: Generates synthetic completed orders to populate the orders table
so the ML pair-frequency recommender has data to learn from.

Only accessible from Settings → Developer Tools (visible when DEBUG=True or role=ADMIN).
Does NOT touch existing schema or change any DAO behavior.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Callable

from app.db.database import Database
from app.db.dao import ProductDAO, OrderDAO

_COMBO_GROUPS: list[tuple[list[str], list[str]]] = [
    # Coffee + pastry / bread
    (
        ["coffee", "espresso", "latte", "cappuccino", "americano", "brew", "mocha", "frappe"],
        ["croissant", "pandesal", "muffin", "cake", "bread", "ensaymada", "cookie", "donut", "pastry"],
    ),
    # Rice meal + drink
    (
        ["rice", "meal", "lunch", "pork", "chicken", "beef", "adobo", "sinigang",
         "tinola", "lechon", "sisig", "liempo", "tocino", "longganisa", "menudo"],
        ["juice", "iced tea", "soda", "water", "coke", "softdrink", "shake", "lemon", "buko"],
    ),
    # Milk tea + toppings
    (
        ["milk tea", "taro", "matcha", "brown sugar", "wintermelon", "oolong",
         "jasmine", "hokkaido", "okinawa", "thai tea"],
        ["pudding", "jelly", "tapioca", "sinkers", "nata", "grass jelly", "pearls"],
    ),
    # Snack combo
    (
        ["fries", "nachos", "chips", "popcorn", "onion rings", "nuggets", "hotdog"],
        ["ketchup", "cheese sauce", "dip", "gravy", "ranch"],
    ),
]


class SeedSalesService:
    """DEV-only service that generates synthetic completed orders."""

    def __init__(self, db: Database):
        self.db = db
        self.products = ProductDAO(db)
        self.orders = OrderDAO(db)

    def run(
        self,
        num_orders: int = 200,
        items_min: int = 2,
        items_max: int = 5,
        days_back: int = 30,
        weighted_combos: bool = True,
        reduce_stock: bool = False,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        Generate synthetic completed orders.

        Returns a dict:
            {
                "orders_created": int,
                "total_sales": float,
                "error": str | None,
            }
        """
        all_products = self.db.fetchall(
            "SELECT id AS product_id, name, price, stock, active FROM products WHERE active=1;"
        )

        if not all_products:
            return {"orders_created": 0, "total_sales": 0.0,
                    "error": "No active products found in the database."}

        if reduce_stock:
            all_products = [p for p in all_products if int(p["stock"] or 0) > 0]
            if not all_products:
                return {"orders_created": 0, "total_sales": 0.0,
                        "error": "No active products with stock > 0."}

        orders_created = 0
        total_sales = 0.0
        now = datetime.now()

        for i in range(num_orders):
            try:
                n_items = random.randint(
                    items_min,
                    min(items_max, len(all_products)),
                )
                selected = self._pick_products(all_products, n_items, weighted_combos)
                if not selected:
                    continue

                subtotal = 0.0
                order_items: list[tuple[int, int, float]] = []
                for prod in selected:
                    qty = random.randint(1, 3)
                    price = float(prod["price"])
                    order_items.append((int(prod["product_id"]), qty, price))
                    subtotal += qty * price

                delta = random.uniform(0, days_back)
                order_dt = now - timedelta(days=delta)
                order_dt_str = order_dt.strftime("%Y-%m-%d %H:%M:%S")

                customer_name = f"TestCustomer{random.randint(1, 999):03d}"
                total = round(subtotal, 2)

                order_id = self._insert_order_at(
                    customer_name=customer_name,
                    payment_method="Cash",
                    status="Completed",
                    subtotal=subtotal,
                    total=total,
                    amount_paid=total,
                    order_dt_str=order_dt_str,
                )

                for pid, qty, price in order_items:
                    self.orders.insert_item(order_id, pid, qty, price, "")

                if reduce_stock:
                    self._reduce_stock(order_items)

                total_sales += total
                orders_created += 1

                if progress_cb and i % 20 == 0:
                    progress_cb(i, num_orders)

            except Exception as exc:
                print(f"[SeedSales] Error at order {i}: {exc}")

        return {
            "orders_created": orders_created,
            "total_sales": round(total_sales, 2),
            "error": None,
        }

    def _pick_products(self, products: list, n: int, weighted: bool) -> list:
        """Pick n products, optionally using combo-keyword weighting."""
        if not weighted or len(products) < 2:
            return random.sample(products, min(n, len(products)))

        names_lower = {
            int(p["product_id"]): str(p["name"]).lower()
            for p in products
        }
        result: list = []

        shuffled_groups = list(_COMBO_GROUPS)
        random.shuffle(shuffled_groups)

        for grp_a_kws, grp_b_kws in shuffled_groups:
            grp_a = [
                p for p in products
                if any(kw in names_lower[int(p["product_id"])] for kw in grp_a_kws)
            ]
            grp_b = [
                p for p in products
                if any(kw in names_lower[int(p["product_id"])] for kw in grp_b_kws)
            ]
            if grp_a and grp_b:
                result.append(random.choice(grp_a))
                result.append(random.choice(grp_b))
                break

        if not result:
            result = random.sample(products, min(2, len(products)))

        used_ids = {int(p["product_id"]) for p in result}
        remaining = [p for p in products if int(p["product_id"]) not in used_ids]
        extra = max(0, n - len(result))
        if remaining and extra > 0:
            result += random.sample(remaining, min(extra, len(remaining)))

        return result[:n]

    def _insert_order_at(
        self,
        customer_name: str,
        payment_method: str,
        status: str,
        subtotal: float,
        total: float,
        amount_paid: float,
        order_dt_str: str,
    ) -> int:
        """Insert an order row with a specific datetime (bypasses DAO defaults)."""
        return self.db.execute_id(
            """
            INSERT INTO orders(
                datetime, end_datetime,
                cashier_id, customer_name, payment_method, status, reference_no,
                subtotal, discount, tax, total,
                amount_paid, cash_received, change_due
            ) VALUES(?,?,1,?,?,?,?,?,?,?,?,?,?,?);
            """,
            (
                order_dt_str,
                order_dt_str,
                customer_name,
                payment_method,
                status,
                "",          # reference_no
                subtotal,
                0.0,         # discount
                0.0,         # tax
                total,
                amount_paid,
                amount_paid,  # cash_received
                0.0,          # change_due
            ),
        )

    def _reduce_stock(self, order_items: list[tuple[int, int, float]]) -> None:
        """Optionally reduce stock for seeded items."""
        for pid, qty, _price in order_items:
            try:
                r = self.db.fetchone(
                    "SELECT stock FROM products WHERE id=?;", (pid,)
                )
                if r:
                    new_qty = max(0, int(r["stock"]) - qty)
                    self.products.set_stock(pid, new_qty)
            except Exception:
                pass
