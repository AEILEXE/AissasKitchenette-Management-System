from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

from app.config import DB_PATH, DATA_DIR
from app.db.schema import ALL_SCHEMAS, INDEX_STATEMENTS


class Database:
    """
    Manages SQLite database connections and schema initialization.
    Handles safe migrations for backward compatibility.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else Path(DB_PATH)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """
        Establish database connection.
        - Creates data directory if missing
        - Enables foreign key constraints
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
        self.conn = None

    def close(self) -> None:
        """Alias for disconnect() — used by import/export routines."""
        self.disconnect()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        """Execute SQL statement with parameters (with commit)."""
        assert self.conn is not None, "Database not connected"
        self.conn.execute(sql, tuple(params))
        self.conn.commit()

    def execute_id(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Execute INSERT and return last row ID."""
        assert self.conn is not None, "Database not connected"
        cur = self.conn.execute(sql, tuple(params))
        self.conn.commit()
        return int(cur.lastrowid)

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        """Fetch single row."""
        assert self.conn is not None, "Database not connected"
        cur = self.conn.execute(sql, tuple(params))
        return cur.fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        """Fetch all rows."""
        assert self.conn is not None, "Database not connected"
        cur = self.conn.execute(sql, tuple(params))
        return cur.fetchall()

    def initialize_schema(self) -> None:
        """
        Create all tables and indexes if missing.
        - Runs ALL_SCHEMAS from schema.py
        - Creates indexes
        - Runs safe migrations for backward compatibility
        """
        assert self.conn is not None, "Database not connected"

        # Create all tables
        for stmt in ALL_SCHEMAS:
            self.conn.execute(stmt)

        # Create all indexes
        for stmt in INDEX_STATEMENTS:
            self.conn.execute(stmt)

        self.conn.commit()

        # Run safe migrations for existing databases
        self._migrate_if_needed()

    def _table_columns(self, table: str) -> set[str]:
        """Get set of column names for a table using PRAGMA."""
        rows = self.fetchall(f"PRAGMA table_info({table});")
        return {r["name"] for r in rows}

    def _table_exists(self, table: str) -> bool:
        """Check if table exists."""
        r = self.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table,),
        )
        return r is not None

    def _add_column_if_missing(self, table: str, col: str, coldef: str) -> None:
        """
        Safely add column to table if it doesn't exist.
        Uses PRAGMA table_info to check before ALTERing.
        """
        cols = self._table_columns(table)
        if col not in cols:
            try:
                self.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef};")
            except sqlite3.OperationalError:
                # Column may already exist, silently ignore
                pass

    def _migrate_if_needed(self) -> None:
        """
        Add missing columns to existing tables.
        Safe: only adds if column doesn't exist.
        Idempotent: can run multiple times.
        """
        # =====================================================================
        # USERS TABLE MIGRATIONS
        # =====================================================================
        if self._table_exists("users"):
            # No new columns needed for users - schema is stable
            pass

        # =====================================================================
        # PRODUCTS TABLE MIGRATIONS
        # =====================================================================
        if self._table_exists("products"):
            self._add_column_if_missing("products", "description", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("products", "tags", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("products", "image_path", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("products", "active", "INTEGER NOT NULL DEFAULT 1")
            self._add_column_if_missing("products", "low_stock", "INTEGER NOT NULL DEFAULT 5")
            self._add_column_if_missing(
                "products",
                "created_at",
                "TEXT NOT NULL DEFAULT (datetime('now','localtime'))",
            )

        # =====================================================================
        # DRAFTS TABLE MIGRATIONS
        # =====================================================================
        if self._table_exists("drafts"):
            self._add_column_if_missing(
                "drafts",
                "created_at",
                "TEXT NOT NULL DEFAULT (datetime('now','localtime'))",
            )
            self._add_column_if_missing("drafts", "total", "REAL NOT NULL DEFAULT 0")

        # =====================================================================
        # ORDERS TABLE MIGRATIONS - COMPREHENSIVE
        # =====================================================================
        if self._table_exists("orders"):
            # Timestamps
            self._add_column_if_missing(
                "orders",
                "datetime",
                "TEXT NOT NULL DEFAULT (datetime('now','localtime'))",
            )
            self._add_column_if_missing(
                "orders",
                "end_datetime",
                "TEXT NOT NULL DEFAULT (datetime('now','localtime'))",
            )

            # Cashier and customer
            self._add_column_if_missing("orders", "cashier_id", "INTEGER DEFAULT NULL")
            self._add_column_if_missing("orders", "customer_name", "TEXT NOT NULL DEFAULT ''")

            # Payment
            self._add_column_if_missing("orders", "payment_method", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("orders", "status", "TEXT NOT NULL DEFAULT 'Completed'")
            self._add_column_if_missing("orders", "reference_no", "TEXT NOT NULL DEFAULT ''")

            # Amounts
            self._add_column_if_missing("orders", "subtotal", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("orders", "discount", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("orders", "tax", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("orders", "total", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("orders", "amount_paid", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("orders", "cash_received", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("orders", "change_due", "REAL NOT NULL DEFAULT 0")

            # Metadata
            self._add_column_if_missing(
                "orders",
                "created_at",
                "TEXT NOT NULL DEFAULT (datetime('now','localtime'))",
            )

        # =====================================================================
        # ORDER_ITEMS TABLE MIGRATIONS
        # =====================================================================
        if self._table_exists("order_items"):
            self._add_column_if_missing("order_items", "unit_price", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("order_items", "note", "TEXT NOT NULL DEFAULT ''")

        # =====================================================================
        # ROLE_PERMISSIONS TABLE — seeded from constants if empty
        # =====================================================================
        if self._table_exists("role_permissions"):
            r = self.fetchone("SELECT COUNT(*) AS c FROM role_permissions;")
            if r and int(r["c"]) == 0:
                self._seed_default_role_permissions()

    def _seed_default_role_permissions(self) -> None:
        """Populate role_permissions with hardcoded defaults (runs once on fresh DB)."""
        try:
            from app.constants import DEFAULT_ROLE_PERMISSIONS, ALL_PERMISSION_KEYS
            for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
                for perm in ALL_PERMISSION_KEYS:
                    granted = 1 if perm in perms else 0
                    try:
                        self.execute(
                            "INSERT OR IGNORE INTO role_permissions(role, permission, granted) VALUES(?,?,?);",
                            (role, perm, granted),
                        )
                    except Exception:
                        pass
        except Exception:
            pass
