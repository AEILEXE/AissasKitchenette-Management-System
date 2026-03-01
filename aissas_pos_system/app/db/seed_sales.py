"""
Seed realistic historical sales data for ML training, reports, and dashboard KPIs.

Usage (run from the aissas_pos_system/ directory):
    python -m app.db.seed_sales

Optional CLI args:
    --days        <int>   Days of history to create  (default: 90)
    --min-orders  <int>   Min completed orders/day   (default: 15)
    --max-orders  <int>   Max completed orders/day   (default: 60)
    --cashier-id  <int>   User-ID used as cashier    (default: 1)

Why this script matters:
  - ML "Suggested Items": needs >= 10 completed orders for pair-frequency mode.
    After seeding 90 days the recommender switches from the low-data fallback
    to full pair-frequency scoring.
  - Top Sellers widget: populated from order_items JOIN orders WHERE Completed.
  - Monthly / daily sales reports: now have data across date ranges.
  - Dashboard KPI cards: Sales Today / Sales Month show real figures.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running as `python -m app.db.seed_sales` from the aissas_pos_system dir
# or as a plain script from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import DB_PATH
from app.db.database import Database
from app.db.dao import OrderDAO, ProductDAO

# ── Defaults (override via CLI) ───────────────────────────────────────────────
_DAYS       = 90
_MIN_ORDERS = 15
_MAX_ORDERS = 60
_CASHIER_ID = 1   # must match an existing user.id (admin = 1 by default)

# Weighted list: Cash is more common than Bank/E-Wallet
_PAYMENTS = ["Cash"] * 7 + ["Bank/E-Wallet"]

_CUSTOMERS = [
    "Walk-in", "Dine-in", "Takeout",
    "Table 1", "Table 2", "Table 3", "Table 4",
    "Online Order",
]


def _ref_no() -> str:
    return f"REF{random.randint(100_000, 999_999)}"


def seed_sales(
    days: int       = _DAYS,
    min_orders: int = _MIN_ORDERS,
    max_orders: int = _MAX_ORDERS,
    cashier_id: int = _CASHIER_ID,
) -> None:
    db = Database(str(DB_PATH))
    db.connect()

    prod_dao  = ProductDAO(db)
    order_dao = OrderDAO(db)

    products = prod_dao.list_all_active()
    if not products:
        print("[seed_sales] ERROR: No active products found.")
        print("             Run the menu seeder first:")
        print("             python -m app.db.seed_menu")
        db.disconnect()
        return

    prod_list: list[tuple[int, str, float]] = [
        (int(r["product_id"]), str(r["name"]), float(r["price"]))
        for r in products
    ]

    now          = datetime.now()
    total_orders = 0

    print(f"[seed_sales] Seeding {days} days of history "
          f"({min_orders}–{max_orders} orders/day) …")

    for day_offset in range(days, 0, -1):
        date     = now - timedelta(days=day_offset)
        n_orders = random.randint(min_orders, max_orders)

        for _ in range(n_orders):
            # Random timestamp during business hours (7 AM – 10 PM)
            hour     = random.randint(7, 21)
            minute   = random.randint(0, 59)
            second   = random.randint(0, 59)
            order_dt = date.replace(hour=hour, minute=minute,
                                    second=second, microsecond=0)
            end_dt   = order_dt + timedelta(minutes=random.randint(2, 20))
            dt_str   = order_dt.strftime("%Y-%m-%d %H:%M:%S")
            end_str  = end_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Build cart: 1–6 distinct products, qty 1–4 each
            n_items  = random.randint(1, min(6, len(prod_list)))
            selected = random.sample(prod_list, n_items)

            subtotal = 0.0
            cart: list[tuple[int, int, float]] = []
            for pid, _name, price in selected:
                qty      = random.randint(1, 4)
                subtotal += price * qty
                cart.append((pid, qty, price))

            payment   = random.choice(_PAYMENTS)
            customer  = random.choice(_CUSTOMERS)
            reference = _ref_no() if payment == "Bank/E-Wallet" else ""

            # Round cash payments up to the nearest sensible denomination
            if payment == "Cash":
                bump        = random.choice([0, 5, 10, 20, 50])
                amount_paid = (subtotal // 10 + 1) * 10 + bump
            else:
                amount_paid = subtotal

            change_due = max(0.0, amount_paid - subtotal)

            # OrderDAO.insert_order() always uses datetime('now','localtime').
            # For historical data we must supply an explicit timestamp, so we
            # call db.execute_id() directly with the datetime column included.
            order_id = db.execute_id(
                """
                INSERT INTO orders(
                    datetime, end_datetime,
                    cashier_id, customer_name, payment_method, status,
                    reference_no, subtotal, discount, tax, total,
                    amount_paid, cash_received, change_due
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?);
                """,
                (
                    dt_str, end_str,
                    cashier_id, customer, payment, "Completed",
                    reference, subtotal, 0.0, 0.0, subtotal,
                    amount_paid, amount_paid, change_due,
                ),
            )

            # Items use the DAO (no timestamp needed)
            for pid, qty, unit_price in cart:
                order_dao.insert_item(order_id, pid, qty, unit_price, note="")

            total_orders += 1

        # Progress indicator every 15 days and on the last 3 days
        if day_offset % 15 == 0 or day_offset <= 3:
            print(f"  … day -{day_offset:3d}  |  {n_orders} orders this day"
                  f"  |  {total_orders} total so far")

    db.disconnect()

    print(f"\n[seed_sales] Done!  {total_orders} completed orders inserted "
          f"over {days} days.")
    print()
    print("  What improves now:")
    print("  ✓ ML Suggested Items  — pair-frequency mode kicks in after 10+ orders")
    print("  ✓ Top Sellers widget  — dashboard & inventory sales now have real data")
    print("  ✓ Reports (monthly / daily) — full date range populated")
    print("  ✓ Dashboard KPI cards — Sales Today / Month show real figures")
    print()
    print("  To run again:")
    print("    cd aissas_pos_system")
    print("    python -m app.db.seed_sales")
    print()
    print("  To run with custom settings:")
    print("    python -m app.db.seed_sales --days 60 --min-orders 20 --max-orders 80")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Seed realistic historical sales data for ML and reporting."
    )
    ap.add_argument("--days",        type=int, default=_DAYS,
                    help=f"Days of history to seed (default: {_DAYS})")
    ap.add_argument("--min-orders",  type=int, default=_MIN_ORDERS,
                    help=f"Min orders per day (default: {_MIN_ORDERS})")
    ap.add_argument("--max-orders",  type=int, default=_MAX_ORDERS,
                    help=f"Max orders per day (default: {_MAX_ORDERS})")
    ap.add_argument("--cashier-id",  type=int, default=_CASHIER_ID,
                    help=f"User ID to use as cashier (default: {_CASHIER_ID})")
    args = ap.parse_args()

    seed_sales(
        days       = args.days,
        min_orders = args.min_orders,
        max_orders = args.max_orders,
        cashier_id = args.cashier_id,
    )
