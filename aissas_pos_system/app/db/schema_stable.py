from __future__ import annotations

# =============================================================================
# COMPLETE DATABASE SCHEMA
# =============================================================================
# This file defines ALL_SCHEMAS and INDEX_STATEMENTS for the POS system.
# All columns are defined here to ensure DAO queries match exactly.
# =============================================================================

ALL_SCHEMAS: list[str] = [
    # =========================================================================
    # USERS TABLE - Cashiers, Managers, Admins
    # =========================================================================
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'ADMIN',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

    # =========================================================================
    # CATEGORIES TABLE - Product Categories
    # =========================================================================
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    """,

    # =========================================================================
    # PRODUCTS TABLE - Menu Items
    # =========================================================================
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '',
        price REAL NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        low_stock INTEGER NOT NULL DEFAULT 5,
        image_path TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
    );
    """,

    # =========================================================================
    # DRAFTS TABLE - Saved Pending Transactions
    # =========================================================================
    """
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        total REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

    # =========================================================================
    # ORDERS TABLE - Completed/Pending/Cancelled Orders
    # =========================================================================
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datetime TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        end_datetime TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        cashier_id INTEGER,
        customer_name TEXT NOT NULL DEFAULT '',
        payment_method TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Completed',
        reference_no TEXT NOT NULL DEFAULT '',
        subtotal REAL NOT NULL DEFAULT 0,
        discount REAL NOT NULL DEFAULT 0,
        tax REAL NOT NULL DEFAULT 0,
        total REAL NOT NULL DEFAULT 0,
        amount_paid REAL NOT NULL DEFAULT 0,
        cash_received REAL NOT NULL DEFAULT 0,
        change_due REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

    # =========================================================================
    # ORDER_ITEMS TABLE - Individual Items in Orders
    # =========================================================================
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        qty INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '',
        subtotal REAL NOT NULL DEFAULT 0,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
    );
    """,
]

# =============================================================================
# INDEXES - For Query Performance
# =============================================================================
INDEX_STATEMENTS: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);",
    "CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);",
    "CREATE INDEX IF NOT EXISTS idx_drafts_created_at ON drafts(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_orders_datetime ON orders(datetime);",
    "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);",
]

# =============================================================================
# BACKWARD COMPATIBILITY ALIASES
# =============================================================================
SCHEMAS = ALL_SCHEMAS
TABLE_SCHEMAS = ALL_SCHEMAS
