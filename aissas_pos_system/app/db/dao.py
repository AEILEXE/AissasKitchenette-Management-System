from __future__ import annotations

import json
from typing import Optional, Any

from app.db.database import Database
from app.models.user import User
from app.models.product import Product


# =============================================================================
# USER DATA ACCESS OBJECT
# =============================================================================

class UserDAO:
    """
    Database access for users table.
    Columns: id, username, password_hash, role, is_active, created_at
    """

    def __init__(self, db: Database):
        self.db = db

    def get_by_username(self, username: str) -> Optional[User]:
        """Fetch user by username."""
        r = self.db.fetchone(
            "SELECT id AS user_id, username, password_hash, role, is_active FROM users WHERE username=?;",
            (username,),
        )
        if not r:
            return None
        return User(
            int(r["user_id"]),
            r["username"],
            r["password_hash"],
            r["role"],
            bool(r["is_active"]),
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Fetch user by ID."""
        r = self.db.fetchone(
            "SELECT id AS user_id, username, password_hash, role, is_active FROM users WHERE id=?;",
            (user_id,),
        )
        if not r:
            return None
        return User(
            int(r["user_id"]),
            r["username"],
            r["password_hash"],
            r["role"],
            bool(r["is_active"]),
        )

    def create(self, username: str, password_hash: str, role: str) -> int:
        """Create new user."""
        return self.db.execute_id(
            "INSERT INTO users(username, password_hash, role, is_active) VALUES(?,?,?,1);",
            (username, password_hash, role),
        )

    def update_password(self, user_id: int, password_hash: str) -> None:
        """Update user password hash."""
        self.db.execute(
            "UPDATE users SET password_hash=? WHERE id=?;",
            (password_hash, user_id),
        )

    def list_users(self):
        """List all users."""
        return self.db.fetchall(
            "SELECT id AS user_id, username, role, is_active FROM users ORDER BY id;"
        )

    def set_active(self, user_id: int, active: int) -> None:
        """Activate/deactivate user."""
        self.db.execute(
            "UPDATE users SET is_active=? WHERE id=?;",
            (active, user_id),
        )


# =============================================================================
# CATEGORY DATA ACCESS OBJECT
# =============================================================================

class CategoryDAO:
    """Database access for categories table."""

    def __init__(self, db: Database):
        self.db = db

    def list_categories(self):
        """List all categories."""
        return self.db.fetchall("SELECT id AS category_id, name FROM categories ORDER BY name;")

    def get_by_name(self, name: str):
        """Get category by name."""
        return self.db.fetchone(
            "SELECT id AS category_id, name FROM categories WHERE name=?;",
            (name,),
        )

    def create(self, name: str) -> int:
        """Create new category."""
        return self.db.execute_id(
            "INSERT INTO categories(name) VALUES(?);",
            (name,),
        )


# =============================================================================
# PRODUCT DATA ACCESS OBJECT
# =============================================================================

class ProductDAO:
    """
    Database access for products table.
    Columns: id, category_id, name, description, tags, price, stock, active, low_stock, image_path, created_at
    """

    def __init__(self, db: Database):
        self.db = db

    def list_by_category(self, category_id: int):
        """List all active products in a category."""
        return self.db.fetchall(
            """
            SELECT id AS product_id,
                   name,
                   description,
                   tags,
                   image_path,
                   price,
                   stock AS stock_qty,
                   low_stock,
                   active
            FROM products
            WHERE category_id=? AND active=1
            ORDER BY name;
            """,
            (category_id,),
        )

    def list_all_active(self):
        """List all active products with category name."""
        return self.db.fetchall(
            """
            SELECT p.id AS product_id,
                   p.name,
                   COALESCE(c.name, '') AS category,
                   p.description,
                   p.tags,
                   p.image_path,
                   p.price,
                   p.stock AS stock_qty,
                   p.low_stock,
                   p.active
            FROM products p
            LEFT JOIN categories c ON p.category_id=c.id
            WHERE p.active=1
            ORDER BY c.name, p.name;
            """
        )

    def list_all(self):
        """List all products (active and inactive)."""
        return self.db.fetchall(
            """
            SELECT p.id AS product_id,
                   p.name,
                   COALESCE(c.name, '') AS category,
                   p.description,
                   p.tags,
                   p.image_path,
                   p.price,
                   p.stock AS stock_qty,
                   p.low_stock,
                   p.active
            FROM products p
            LEFT JOIN categories c ON p.category_id=c.id
            ORDER BY c.name, p.name;
            """
        )

    def get(self, product_id: int) -> Optional[Product]:
        """Get product by ID."""
        r = self.db.fetchone(
            """
            SELECT id AS product_id,
                   name,
                   category_id,
                   price,
                   stock AS stock_qty,
                   low_stock,
                   active
            FROM products
            WHERE id=?;
            """,
            (product_id,),
        )
        if not r:
            return None
        return Product(
            int(r["product_id"]),
            r["name"],
            int(r["category_id"]) if r["category_id"] is not None else 0,
            float(r["price"]),
            int(r["stock_qty"]),
            int(r["low_stock"]),
            bool(r["active"]),
        )

    def count_active(self) -> int:
        """Count total active products."""
        r = self.db.fetchone("SELECT COUNT(*) AS c FROM products WHERE active=1;")
        return int(r["c"]) if r else 0

    def set_stock(self, product_id: int, new_qty: int) -> None:
        """Update product stock quantity."""
        self.db.execute(
            "UPDATE products SET stock=? WHERE id=?;",
            (int(new_qty), int(product_id)),
        )

    def set_active(self, product_id: int, active: int) -> None:
        """Activate/deactivate product."""
        self.db.execute(
            "UPDATE products SET active=? WHERE id=?;",
            (int(active), int(product_id)),
        )

    def create(self, category_id: int | None, name: str, description: str, tags: str, image_path: str, price: float, stock: int, low_stock: int, active: int) -> int:
        """Create new product (tags optional, image_path optional)."""
        return self.db.execute_id(
            """
            INSERT INTO products(category_id, name, description, tags, image_path, price, stock, low_stock, active)
            VALUES(?,?,?,?,?,?,?,?,?);
            """,
            (int(category_id) if category_id else None, str(name), str(description), str(tags), str(image_path), float(price), int(stock), int(low_stock), int(active)),
        )

    def update(self, product_id: int, category_id: int | None, name: str, description: str, tags: str, image_path: str, price: float, stock: int, low_stock: int, active: int) -> None:
        """Update existing product (tags and image_path optional)."""
        self.db.execute(
            """
            UPDATE products
            SET category_id=?, name=?, description=?, tags=?, image_path=?, price=?, stock=?, low_stock=?, active=?
            WHERE id=?;
            """,
            (int(category_id) if category_id else None, str(name), str(description), str(tags), str(image_path), float(price), int(stock), int(low_stock), int(active), int(product_id)),
        )

    def delete(self, product_id: int) -> None:
        """Delete product."""
        self.db.execute("DELETE FROM products WHERE id=?;", (int(product_id),))


# =============================================================================
# DRAFT DATA ACCESS OBJECT
# =============================================================================

class DraftDAO:
    """
    Database access for drafts table (pending transactions).
    Columns: id, title, payload_json, total, created_at
    """

    def __init__(self, db: Database):
        self.db = db

    def create_draft(self, title: str, payload: dict[str, Any], total: float = 0.0) -> int:
        """Create new draft."""
        payload_json = json.dumps(payload, ensure_ascii=False)
        return self.db.execute_id(
            "INSERT INTO drafts(title, payload_json, total) VALUES(?,?,?);",
            (title, payload_json, float(total)),
        )

    def list_drafts(self):
        """List all drafts, newest first."""
        return self.db.fetchall(
            "SELECT id AS draft_id, title, created_at, total FROM drafts ORDER BY datetime(created_at) DESC;"
        )

    def get_draft(self, draft_id: int):
        """Get draft by ID."""
        return self.db.fetchone(
            "SELECT id AS draft_id, title, payload_json, created_at, total FROM drafts WHERE id=?;",
            (int(draft_id),),
        )

    def delete_draft(self, draft_id: int) -> None:
        """Delete draft."""
        self.db.execute("DELETE FROM drafts WHERE id=?;", (int(draft_id),))

    def count_drafts(self) -> int:
        """Count total drafts."""
        r = self.db.fetchone("SELECT COUNT(*) AS c FROM drafts;")
        return int(r["c"]) if r else 0


# =============================================================================
# ORDER DATA ACCESS OBJECT
# =============================================================================

class OrderDAO:
    """
    Database access for orders table (transactions).
    Columns: id, datetime, end_datetime, cashier_id, customer_name, payment_method,
             status, reference_no, subtotal, discount, tax, total, amount_paid,
             cash_received, change_due, created_at
    """

    def __init__(self, db: Database):
        self.db = db

    def insert_order(
        self,
        cashier_id: int,
        customer_name: str,
        payment_method: str,
        status: str,
        reference_no: str,
        subtotal: float,
        discount: float,
        tax: float,
        total: float,
        amount_paid: float,
        cash_received: float,
        change_due: float,
    ) -> int:
        """
        Create new order.
        datetime and end_datetime use schema defaults (NOW).
        Exactly 12 columns, 12 parameters.
        """
        return self.db.execute_id(
            """
            INSERT INTO orders(
                cashier_id, customer_name, payment_method, status, reference_no,
                subtotal, discount, tax, total,
                amount_paid, cash_received, change_due
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?);
            """,
            (
                int(cashier_id),
                str(customer_name),
                str(payment_method),
                str(status),
                str(reference_no),
                float(subtotal),
                float(discount),
                float(tax),
                float(total),
                float(amount_paid),
                float(cash_received),
                float(change_due),
            ),
        )

    def insert_item(
        self,
        order_id: int,
        product_id: int,
        qty: int,
        unit_price: float,
        note: str,
    ) -> None:
        """Add item to order."""
        subtotal = float(qty) * float(unit_price)
        self.db.execute(
            """
            INSERT INTO order_items(order_id, product_id, qty, unit_price, note, subtotal)
            VALUES(?,?,?,?,?,?);
            """,
            (int(order_id), int(product_id), int(qty), float(unit_price), str(note), subtotal),
        )

    def list_orders(
        self,
        order_id_like: str = "",
        status: str = "All",
        payment: str = "All",
        date_from: str = "",
        date_to: str = "",
    ):
        """List orders with optional filters."""
        where = []
        params: list[Any] = []

        if order_id_like.strip():
            where.append("CAST(o.id AS TEXT) LIKE ?")
            params.append(f"%{order_id_like.strip()}%")

        if status != "All":
            where.append("o.status = ?")
            params.append(status)

        if payment != "All":
            where.append("o.payment_method = ?")
            params.append(payment)

        if date_from:
            where.append("DATE(o.datetime) >= DATE(?)")
            params.append(date_from)

        if date_to:
            where.append("DATE(o.datetime) <= DATE(?)")
            params.append(date_to)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        return self.db.fetchall(
            f"""
            SELECT o.id AS order_id,
                   o.payment_method,
                   o.amount_paid,
                   o.change_due,
                   (SELECT COALESCE(SUM(qty), 0) FROM order_items oi WHERE oi.order_id=o.id) AS items_count,
                   o.status,
                   o.total,
                   o.datetime AS start_dt,
                   o.end_datetime AS end_dt
            FROM orders o
            {where_sql}
            ORDER BY datetime(o.datetime) DESC;
            """,
            tuple(params),
        )

    def get_order(self, order_id: int):
        """Get order details."""
        return self.db.fetchone(
            """
            SELECT id AS order_id,
                   datetime AS start_dt,
                   end_datetime AS end_dt,
                   customer_name,
                   payment_method,
                   status,
                   reference_no,
                   subtotal,
                   discount,
                   tax,
                   total,
                   amount_paid,
                   change_due
            FROM orders
            WHERE id=?;
            """,
            (int(order_id),),
        )

    def get_order_items(self, order_id: int):
        """Get items in order."""
        return self.db.fetchall(
            """
            SELECT oi.product_id,
                   p.name,
                   oi.qty,
                   oi.unit_price,
                   oi.subtotal
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id=p.id
            WHERE oi.order_id=?
            ORDER BY oi.id;
            """,
            (int(order_id),),
        )

    def resolve_pending(self, order_id: int, reference_no: str, amount_paid: float) -> None:
        """Transition order from Pending to Completed."""
        self.db.execute(
            """
            UPDATE orders
            SET reference_no=?,
                amount_paid=?,
                cash_received=?,
                status='Completed',
                end_datetime=datetime('now','localtime')
            WHERE id=? AND status='Pending';
            """,
            (reference_no.strip(), float(amount_paid), float(amount_paid), int(order_id)),
        )

    def cancel_order(self, order_id: int) -> None:
        """Cancel order."""
        self.db.execute(
            """
            UPDATE orders
            SET status='Cancelled',
                end_datetime=datetime('now','localtime')
            WHERE id=?;
            """,
            (int(order_id),),
        )

    def count_by_status(self, status: str) -> int:
        """Count orders by status."""
        r = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM orders WHERE status=?;",
            (status,),
        )
        return int(r["c"]) if r else 0

    def summary_today(self):
        """Get order count and total sales for today."""
        return self.db.fetchone(
            """
            SELECT COUNT(*) AS order_count,
                   COALESCE(SUM(total), 0) AS total_sales
            FROM orders
            WHERE DATE(datetime) = DATE('now', 'localtime') AND status='Completed';
            """
        )

    def summary_month(self):
        """Get order count and total sales for the current calendar month."""
        return self.db.fetchone(
            """
            SELECT COUNT(*) AS order_count,
                   COALESCE(SUM(total), 0) AS total_sales
            FROM orders
            WHERE strftime('%Y-%m', datetime) = strftime('%Y-%m', 'now', 'localtime')
              AND status='Completed';
            """
        )

    def list_recent(self, limit: int = 10):
        """Get the N most recent orders (any status) for the dashboard."""
        return self.db.fetchall(
            """
            SELECT id AS order_id,
                   datetime AS start_dt,
                   payment_method,
                   total,
                   status
            FROM orders
            ORDER BY datetime(datetime) DESC
            LIMIT ?;
            """,
            (int(limit),),
        )

    def best_sellers_today(self, limit: int = 10):
        """Get best-selling products today."""
        return self.db.fetchall(
            """
            SELECT p.name,
                   SUM(oi.qty) AS total_qty,
                   SUM(oi.subtotal) AS total_sales
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE DATE(o.datetime) = DATE('now', 'localtime') AND o.status='Completed'
            GROUP BY p.id, p.name
            ORDER BY total_qty DESC
            LIMIT ?;
            """,
            (limit,),
        )

    def order_items_for_ml(self, last_n_orders: int = 300):
        """
        Get order_id + product_id rows from the last N COMPLETED orders.
        Used by the offline ML recommender to build pair-frequency counts.
        """
        return self.db.fetchall(
            """
            SELECT oi.order_id, oi.product_id
            FROM order_items oi
            JOIN (
                SELECT id
                FROM orders
                WHERE status = 'Completed'
                ORDER BY datetime DESC
                LIMIT ?
            ) recent ON recent.id = oi.order_id
            ORDER BY oi.order_id ASC;
            """,
            (int(last_n_orders),),
        )
