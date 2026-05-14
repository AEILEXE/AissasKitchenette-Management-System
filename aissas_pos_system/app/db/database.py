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
        - Enables WAL journal mode for faster concurrent reads/writes
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        # WAL mode: reads don't block writes; writes are ~2x faster on spinning disks
        self.conn.execute("PRAGMA journal_mode=WAL;")
        # NORMAL sync is safe with WAL and much faster than FULL
        self.conn.execute("PRAGMA synchronous=NORMAL;")

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
        self.conn = None

    def close(self) -> None:
        """Alias for disconnect() — used by import/export routines."""
        self.disconnect()

    def check_integrity(self) -> bool:
        """
        Run SQLite quick_check on the open database.
        Returns True if healthy, False if any corruption is detected.
        'quick_check' is significantly faster than full 'integrity_check'
        and catches the vast majority of real-world corruption cases.
        Must be called after connect() and before initialize_schema().
        """
        try:
            row = self.fetchone("PRAGMA quick_check;")
            return row is not None and row[0] == "ok"
        except Exception:
            return False

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
        return int(cur.lastrowid) if cur.lastrowid is not None else 0

    def execute_no_commit(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Execute SQL without committing. Returns lastrowid. Use with commit()."""
        assert self.conn is not None, "Database not connected"
        cur = self.conn.execute(sql, tuple(params))
        return int(cur.lastrowid) if cur.lastrowid is not None else 0

    def commit(self) -> None:
        """Explicitly commit the current transaction."""
        assert self.conn is not None, "Database not connected"
        self.conn.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        assert self.conn is not None, "Database not connected"
        self.conn.rollback()

    def get_data_version(self) -> int:
        """Return the current data_version counter from app_meta (0 if not set)."""
        try:
            r = self.fetchone("SELECT value FROM app_meta WHERE key='data_version';")
            return int(r["value"]) if r else 0
        except Exception:
            return 0

    def log_print(self, user_id: int | None, username: str,
                  print_type: str, reference_id: str = "", detail: str = "") -> None:
        """Record a print action (receipt/report) to the print_logs audit table."""
        try:
            self.execute(
                "INSERT INTO print_logs(user_id, username, print_type, reference_id, detail) "
                "VALUES(?,?,?,?,?);",
                (user_id, username, print_type, reference_id, detail),
            )
        except Exception:
            pass

    def increment_data_version(self) -> None:
        """Atomically increment data_version in app_meta. Never raises."""
        try:
            self.execute(
                "INSERT INTO app_meta(key, value) VALUES('data_version','1') "
                "ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT);"
            )
        except Exception:
            pass

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
        self.conn.commit()

        # Run migrations BEFORE indexes: columns added here (e.g. receipt_id)
        # must exist before indexes that reference them are created.
        self._migrate_if_needed()

        # Create all indexes (after migration so all referenced columns exist)
        for stmt in INDEX_STATEMENTS:
            self.conn.execute(stmt)
        self.conn.commit()

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
            self._add_column_if_missing("users", "full_name", "TEXT NOT NULL DEFAULT ''")

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

            # New fields from Modern Bistro upgrade
            self._add_column_if_missing("orders", "receipt_id", "TEXT")
            self._add_column_if_missing("orders", "order_type", "TEXT NOT NULL DEFAULT 'DINE_IN'")
            self._add_column_if_missing("orders", "table_number", "TEXT")
            self._add_column_if_missing("orders", "discount_type", "TEXT NOT NULL DEFAULT 'NONE'")
            self._add_column_if_missing("orders", "vat_amount", "REAL NOT NULL DEFAULT 0")

        # =====================================================================
        # ORDER_ITEMS TABLE MIGRATIONS
        # =====================================================================
        if self._table_exists("order_items"):
            self._add_column_if_missing("order_items", "unit_price", "REAL NOT NULL DEFAULT 0")
            self._add_column_if_missing("order_items", "note", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("order_items", "voided", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing("order_items", "subtotal", "REAL NOT NULL DEFAULT 0")

        # =====================================================================
        # ROLE_PERMISSIONS TABLE — seeded from constants if empty
        # =====================================================================
        if self._table_exists("role_permissions"):
            r = self.fetchone("SELECT COUNT(*) AS c FROM role_permissions;")
            if r and int(r["c"]) == 0:
                self._seed_default_role_permissions()

        # =====================================================================
        # ROLE_PERMISSIONS MIGRATION v2 — apply revised default permissions
        # • CASHIER loses can_view_inventory (inventory tab hidden for cashiers)
        # • INVENTORY role rows are seeded (INSERT OR IGNORE — safe to repeat)
        # Guarded by app_meta flag so it only runs once per database.
        # =====================================================================
        self._apply_permission_migration_v2()

        # =====================================================================
        # RAW_MATERIALS TABLE MIGRATIONS
        # =====================================================================
        if self._table_exists("raw_materials"):
            self._add_column_if_missing("raw_materials", "delivered_date", "TEXT DEFAULT NULL")
            self._add_column_if_missing("raw_materials", "expiration_date", "TEXT DEFAULT NULL")

        # =====================================================================
        # RAW_MATERIAL_LOGS — backfill columns added in later versions
        # (old_quantity, new_quantity, username) so logs carry full detail.
        # =====================================================================
        if self._table_exists("raw_material_logs"):
            self._add_column_if_missing(
                "raw_material_logs", "old_quantity", "REAL NOT NULL DEFAULT 0"
            )
            self._add_column_if_missing(
                "raw_material_logs", "new_quantity", "REAL NOT NULL DEFAULT 0"
            )
            self._add_column_if_missing(
                "raw_material_logs", "username", "TEXT NOT NULL DEFAULT ''"
            )

        # =====================================================================
        # RAW_MATERIAL_LOGS TABLE — create if missing (new table)
        # =====================================================================
        if not self._table_exists("raw_material_logs"):
            try:
                self.execute(
                    """
                    CREATE TABLE IF NOT EXISTS raw_material_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        material_id INTEGER NOT NULL,
                        action_type TEXT NOT NULL DEFAULT 'ADD',
                        quantity REAL NOT NULL DEFAULT 0,
                        reason TEXT NOT NULL DEFAULT '',
                        reference TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                        FOREIGN KEY(material_id) REFERENCES raw_materials(id) ON DELETE CASCADE
                    );
                    """
                )
                self.execute(
                    "CREATE INDEX IF NOT EXISTS idx_raw_material_logs_material_id "
                    "ON raw_material_logs(material_id);"
                )
            except Exception:
                pass

        # =====================================================================
        # APP_META TABLE — key-value store for app-level flags
        # =====================================================================
        if not self._table_exists("app_meta"):
            try:
                self.execute(
                    "CREATE TABLE IF NOT EXISTS app_meta "
                    "(key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '');"
                )
            except Exception:
                pass

        # =====================================================================
        # CATEGORIES TABLE — add parent_id for hierarchical categories
        # =====================================================================
        if self._table_exists("categories"):
            self._add_column_if_missing(
                "categories", "parent_id", "INTEGER DEFAULT NULL"
            )

        # =====================================================================
        # PRINT_LOGS TABLE — audit trail for receipt/report printing
        # =====================================================================
        if not self._table_exists("print_logs"):
            try:
                self.execute(
                    """
                    CREATE TABLE IF NOT EXISTS print_logs (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id      INTEGER,
                        username     TEXT NOT NULL DEFAULT '',
                        print_type   TEXT NOT NULL DEFAULT '',
                        reference_id TEXT NOT NULL DEFAULT '',
                        detail       TEXT NOT NULL DEFAULT '',
                        printed_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                    );
                    """
                )
                self.execute(
                    "CREATE INDEX IF NOT EXISTS idx_print_logs_printed_at "
                    "ON print_logs(printed_at);"
                )
            except Exception:
                pass

        # =====================================================================
        # UNIQUE INDEX — prevent duplicate e-wallet reference numbers
        # Partial index: only covers non-empty, digit-only reference_no values
        # so blank Cash references never conflict.
        # =====================================================================
        self._add_unique_reference_index()

        # =====================================================================
        # CATEGORY HIERARCHY — ensure 'Drinks' parent + reparent tea/coffee subs
        # Idempotent: tracked by app_meta key so it runs at most once per DB.
        # =====================================================================
        self._apply_drinks_category_migration()

        # =====================================================================
        # PRODUCT IMAGES — match empty/missing image_path to files on disk by
        # normalised name. One-shot, conservative: only updates when confident.
        # Tracked by app_meta key so it runs at most once per database.
        # =====================================================================
        self._apply_product_image_backfill()

        # =====================================================================
        # MENU CLEANUP — remove Sandwiches, Wraps & Quesadillas category.
        # Safe to re-run: exits early if the category is already gone.
        # =====================================================================
        try:
            from app.db.seed_menu import remove_sandwiches_category
            remove_sandwiches_category(self)
        except Exception:
            pass

    def _add_unique_reference_index(self) -> None:
        """
        Create a partial unique index on orders.reference_no.
        Only covers non-empty, digit-only values so blank Cash references
        never collide and TXN-* codes from old data are ignored.
        Safe to call multiple times (IF NOT EXISTS).
        """
        try:
            assert self.conn is not None
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_reference_no_unique "
                "ON orders(reference_no) "
                "WHERE reference_no <> '' AND reference_no GLOB '[0-9]*';"
            )
            self.conn.commit()
        except Exception:
            pass

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

    def _apply_drinks_category_migration(self) -> None:
        """
        Ensure a 'Drinks' main category exists and that the standard drink
        subcategories (Hot Coffee, Iced Coffee, Milk Tea, Hot Tea) are
        reparented under it. Safe & idempotent:
        • never deletes products or categories
        • only changes parent_id (top-level → child of Drinks)
        • won't reparent a category that already has a different parent
        • guarded by app_meta key 'drinks_cat_migration_v1' (still re-checks
          each run so missing children can be reparented if added later)
        """
        try:
            if not self._table_exists("categories"):
                return
            cols = self._table_columns("categories")
            if "parent_id" not in cols:
                return
            # Ensure 'Drinks' main category exists.
            row = self.fetchone(
                "SELECT id, parent_id FROM categories WHERE name='Drinks';"
            )
            if row is None:
                self.execute(
                    "INSERT INTO categories(name, parent_id) VALUES('Drinks', NULL);"
                )
                row = self.fetchone(
                    "SELECT id, parent_id FROM categories WHERE name='Drinks';"
                )
            if row is None:
                return
            drinks_id = int(row["id"])
            # Drinks itself must be top-level.
            if row["parent_id"] is not None:
                self.execute(
                    "UPDATE categories SET parent_id=NULL WHERE id=?;",
                    (drinks_id,),
                )
            # Reparent each standard drink subcategory if present and
            # not already under another parent.
            for sub_name in ("Hot Coffee", "Iced Coffee", "Milk Tea", "Hot Tea"):
                sub = self.fetchone(
                    "SELECT id, parent_id FROM categories WHERE name=?;",
                    (sub_name,),
                )
                if sub is None:
                    continue
                sub_id = int(sub["id"])
                if sub_id == drinks_id:
                    continue
                cur_parent = sub["parent_id"]
                if cur_parent is None or int(cur_parent) == drinks_id:
                    self.execute(
                        "UPDATE categories SET parent_id=? WHERE id=?;",
                        (drinks_id, sub_id),
                    )
        except Exception:
            pass

    def _apply_product_image_backfill(self) -> None:
        """
        One-shot fixer: when product_images/<file> exists on disk but a
        product's image_path is empty or points to a missing file, match
        by normalised product name and update image_path. Conservative —
        never overwrites a valid existing image_path; runs at most once
        per database (guarded by app_meta key 'product_image_backfill_v1').
        """
        try:
            if not self._table_exists("products"):
                return
            if not self._table_exists("app_meta"):
                return
            done = self.fetchone(
                "SELECT value FROM app_meta WHERE key='product_image_backfill_v1';"
            )
            if done:
                return

            from app.config import PRODUCT_IMAGES_DIR, resolve_image_path
            if not PRODUCT_IMAGES_DIR.exists():
                # Mark as done anyway so we don't probe every startup.
                self.execute(
                    "INSERT OR REPLACE INTO app_meta(key, value) "
                    "VALUES('product_image_backfill_v1','1');"
                )
                return

            def _norm(s: str) -> str:
                # lowercase + remove any non-alphanumeric so 'Spanish Latte'
                # matches 'SpanishLatte.png' or 'spanish_latte.png'.
                return "".join(ch for ch in s.lower() if ch.isalnum())

            valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
            files: list = []
            for f in PRODUCT_IMAGES_DIR.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in valid_exts:
                    continue
                stem = f.stem
                # Strip trailing _1, _2 etc. (alternate uploads)
                if "_" in stem:
                    parts = stem.rsplit("_", 1)
                    if parts[1].isdigit():
                        stem = parts[0]
                files.append((f.name, _norm(stem)))

            if not files:
                self.execute(
                    "INSERT OR REPLACE INTO app_meta(key, value) "
                    "VALUES('product_image_backfill_v1','1');"
                )
                return

            rows = self.fetchall(
                "SELECT id, name, image_path FROM products;"
            )
            updated = 0
            for r in rows:
                pid = int(r["id"])
                pname = str(r["name"] or "")
                img = str(r["image_path"] or "").strip()
                # Skip when product already has a valid image on disk.
                if img:
                    found = resolve_image_path(img)
                    if found is not None:
                        continue
                norm_name = _norm(pname)
                if not norm_name:
                    continue
                match = None
                for fname, fnorm in files:
                    if fnorm == norm_name:
                        match = fname
                        break
                if match is None:
                    continue
                rel = f"product_images/{match}"
                self.execute(
                    "UPDATE products SET image_path=? WHERE id=?;",
                    (rel, pid),
                )
                updated += 1

            self.execute(
                "INSERT OR REPLACE INTO app_meta(key, value) "
                "VALUES('product_image_backfill_v1','1');"
            )
        except Exception:
            pass

    def _apply_permission_migration_v2(self) -> None:
        """
        One-time migration: align role_permissions with revised defaults.
        • CASHIER: revoke can_view_inventory (cashiers no longer see Inventory).
        • INVENTORY role: seed all permission rows (INSERT OR IGNORE).
        Guarded by app_meta key 'perm_migration_v2' so it runs exactly once.
        """
        try:
            if not self._table_exists("role_permissions"):
                return
            if not self._table_exists("app_meta"):
                return
            done = self.fetchone(
                "SELECT value FROM app_meta WHERE key='perm_migration_v2';"
            )
            if done:
                return  # already applied

            from app.constants import DEFAULT_ROLE_PERMISSIONS, ALL_PERMISSION_KEYS, ROLE_INVENTORY

            # 1. Revoke can_view_inventory from CASHIER
            self.execute(
                "UPDATE role_permissions SET granted=0 "
                "WHERE role='CASHIER' AND permission='can_view_inventory';",
            )

            # 2. Seed the INVENTORY role (safe to repeat — INSERT OR IGNORE)
            inv_perms = DEFAULT_ROLE_PERMISSIONS.get(ROLE_INVENTORY, set())
            for perm in ALL_PERMISSION_KEYS:
                granted = 1 if perm in inv_perms else 0
                self.execute(
                    "INSERT OR IGNORE INTO role_permissions(role, permission, granted) VALUES(?,?,?);",
                    (ROLE_INVENTORY, perm, granted),
                )

            # 3. Mark migration as done
            self.execute(
                "INSERT OR REPLACE INTO app_meta(key, value) VALUES('perm_migration_v2','1');"
            )
        except Exception:
            pass