from __future__ import annotations

ALL_SCHEMAS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'ADMIN',
        full_name TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    """,

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

    """
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        total REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datetime TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        end_datetime TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        cashier_id INTEGER,
        receipt_id TEXT,
        order_type TEXT NOT NULL DEFAULT 'DINE_IN',
        table_number TEXT,
        customer_name TEXT NOT NULL DEFAULT '',
        payment_method TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Completed',
        reference_no TEXT NOT NULL DEFAULT '',
        subtotal REAL NOT NULL DEFAULT 0,
        discount REAL NOT NULL DEFAULT 0,
        discount_type TEXT NOT NULL DEFAULT 'NONE',
        tax REAL NOT NULL DEFAULT 0,
        vat_amount REAL NOT NULL DEFAULT 0,
        total REAL NOT NULL DEFAULT 0,
        amount_paid REAL NOT NULL DEFAULT 0,
        cash_received REAL NOT NULL DEFAULT 0,
        change_due REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        qty INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '',
        voided INTEGER NOT NULL DEFAULT 0,
        subtotal REAL NOT NULL DEFAULT 0,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS void_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_order_id INTEGER NOT NULL,
        void_type TEXT NOT NULL DEFAULT '',
        order_item_id INTEGER,
        voided_by_user_id INTEGER,
        voided_by_username TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        void_receipt_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(original_order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY(order_item_id) REFERENCES order_items(id) ON DELETE SET NULL,
        FOREIGN KEY(voided_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS raw_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        material_type TEXT NOT NULL DEFAULT 'DRY',
        unit TEXT NOT NULL DEFAULT 'pcs',
        quantity REAL NOT NULL DEFAULT 0,
        low_stock REAL NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        delivered_date TEXT DEFAULT NULL,
        expiration_date TEXT DEFAULT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

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
    """,

    """
    CREATE TABLE IF NOT EXISTS product_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        quantity_used REAL NOT NULL DEFAULT 0,
        UNIQUE(product_id, material_id),
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY(material_id) REFERENCES raw_materials(id) ON DELETE CASCADE
    );
    """,

    # ── RBAC: per-role permission toggles ─────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        permission TEXT NOT NULL,
        granted INTEGER NOT NULL DEFAULT 1,
        UNIQUE(role, permission)
    );
    """,

    # ── Audit log for sensitive actions ───────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        old_value TEXT NOT NULL DEFAULT '',
        new_value TEXT NOT NULL DEFAULT '',
        timestamp TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
    """,

    # ── App-level key-value meta (used for recommender dirty flag, etc.) ──────
    """
    CREATE TABLE IF NOT EXISTS app_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT ''
    );
    """,
]

INDEX_STATEMENTS: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);",
    "CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);",
    "CREATE INDEX IF NOT EXISTS idx_products_active ON products(active);",
    "CREATE INDEX IF NOT EXISTS idx_drafts_created_at ON drafts(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_orders_datetime ON orders(datetime);",
    "CREATE INDEX IF NOT EXISTS idx_orders_receipt_id ON orders(receipt_id);",
    "CREATE INDEX IF NOT EXISTS idx_orders_order_type ON orders(order_type);",
    "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);",
    "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);",
    "CREATE INDEX IF NOT EXISTS idx_order_items_voided ON order_items(voided);",
    "CREATE INDEX IF NOT EXISTS idx_void_records_original_order_id ON void_records(original_order_id);",
    "CREATE INDEX IF NOT EXISTS idx_void_records_order_item_id ON void_records(order_item_id);",
    "CREATE INDEX IF NOT EXISTS idx_void_records_void_receipt_id ON void_records(void_receipt_id);",
    "CREATE INDEX IF NOT EXISTS idx_raw_materials_material_type ON raw_materials(material_type);",
    "CREATE INDEX IF NOT EXISTS idx_raw_materials_active ON raw_materials(active);",
    "CREATE INDEX IF NOT EXISTS idx_raw_material_logs_material_id ON raw_material_logs(material_id);",
    "CREATE INDEX IF NOT EXISTS idx_product_materials_product_id ON product_materials(product_id);",
    "CREATE INDEX IF NOT EXISTS idx_product_materials_material_id ON product_materials(material_id);",
    "CREATE INDEX IF NOT EXISTS idx_role_perms ON role_permissions(role, permission);",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_ts ON audit_logs(timestamp);",
]

SCHEMAS = ALL_SCHEMAS
TABLE_SCHEMAS = ALL_SCHEMAS