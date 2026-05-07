from __future__ import annotations

# APP ROLES (match DB values)
ROLE_ADMIN     = "ADMIN"
ROLE_MANAGER   = "MANAGER"
ROLE_CASHIER   = "CASHIER"    # POS + Transactions only
ROLE_CLERK     = "CASHIER"    # backward-compat alias
ROLE_INVENTORY = "INVENTORY"  # Raw materials + inventory, no POS

ROLES = [ROLE_ADMIN, ROLE_MANAGER, ROLE_CASHIER, ROLE_INVENTORY]

# ── Granular permission keys (stored in role_permissions table) ────────────
P_SELL            = "can_sell"
P_DISCOUNT        = "can_apply_discount"
P_VOID            = "can_void_transaction"
P_VOID_APPROVE    = "can_approve_void"           # Manager/Admin only
P_REPORTS         = "can_view_reports"
P_REPORTS_FULL    = "can_view_full_reports"      # VAT, profit, raw material usage
P_PROFIT          = "can_view_profit"
P_MANAGE_PRODS    = "can_manage_products"
P_EDIT_PRICE      = "can_edit_price"
P_MANAGE_USERS    = "can_manage_users"
P_SETTINGS        = "can_access_settings"
P_EXPORT          = "can_export_data"
P_DATABASE        = "can_manage_database"        # backup / restore
P_ML              = "can_manage_ml"
P_INV_VIEW        = "can_view_inventory"
P_AUDIT_LOG       = "can_view_audit_log"
P_EDIT_COMPLETED  = "can_edit_completed_orders"

# Complete ordered list used for UI + DB seeding
ALL_PERMISSION_KEYS: list[str] = [
    P_SELL,
    P_DISCOUNT,
    P_VOID,
    P_VOID_APPROVE,
    P_REPORTS,
    P_REPORTS_FULL,
    P_PROFIT,
    P_MANAGE_PRODS,
    P_EDIT_PRICE,
    P_MANAGE_USERS,
    P_SETTINGS,
    P_EXPORT,
    P_DATABASE,
    P_INV_VIEW,
    P_EDIT_COMPLETED,
]

# Human-readable labels for UI
PERMISSION_LABELS: dict[str, str] = {
    P_SELL:           "Sell (POS access)",
    P_DISCOUNT:       "Apply discounts",
    P_VOID:           "Void / cancel transactions",
    P_VOID_APPROVE:   "Approve void (Manager PIN)",
    P_REPORTS:        "View basic reports",
    P_REPORTS_FULL:   "View full reports (VAT/profit/raw materials)",
    P_PROFIT:         "View profit / cost info",
    P_MANAGE_PRODS:   "Manage products",
    P_EDIT_PRICE:     "Edit product prices",
    P_MANAGE_USERS:   "Manage users",
    P_SETTINGS:       "Access settings",
    P_EXPORT:         "Export data (CSV / PDF)",
    P_DATABASE:       "Manage database (backup/restore)",
    P_INV_VIEW:       "View inventory",
    P_EDIT_COMPLETED: "Edit completed transactions",
}

# Default permissions per role (used for initial DB seed + fallback)
DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    # ADMIN — full access to every module
    ROLE_ADMIN: set(ALL_PERMISSION_KEYS),

    # MANAGER — everything except raw DB access and ML
    ROLE_MANAGER: {
        P_SELL, P_DISCOUNT, P_VOID, P_VOID_APPROVE,
        P_REPORTS, P_REPORTS_FULL, P_PROFIT,
        P_MANAGE_PRODS, P_EDIT_PRICE,
        P_SETTINGS, P_EXPORT, P_INV_VIEW,
        P_EDIT_COMPLETED,
    },

    # CASHIER — POS + Transactions only.
    # No inventory access (P_INV_VIEW removed) and no user management.
    ROLE_CASHIER: {
        P_SELL, P_DISCOUNT,
    },

    # INVENTORY STAFF — inventory + raw materials + basic reports.
    # No POS (P_SELL absent), no user management.
    ROLE_INVENTORY: {
        P_INV_VIEW, P_MANAGE_PRODS,
        P_REPORTS,
        P_EXPORT,
    },
}

# ── Permission groups — for organised UI display ──────────────────────────
PERMISSION_GROUPS: dict[str, list[str]] = {
    "POS":          [P_SELL, P_DISCOUNT, P_VOID, P_VOID_APPROVE],
    "Reports":      [P_REPORTS, P_REPORTS_FULL, P_PROFIT],
    "Inventory":    [P_INV_VIEW, P_MANAGE_PRODS, P_EDIT_PRICE],
    "Transactions": [P_EDIT_COMPLETED],
    "Settings":     [P_MANAGE_USERS, P_SETTINGS, P_EXPORT, P_DATABASE],
}

# ── Backward-compatible aliases ────────────────────────────────────────────
P_POS        = P_SELL
P_INV_MANAGE = P_MANAGE_PRODS
P_USERS      = P_MANAGE_USERS
ROLE_PERMISSIONS = DEFAULT_ROLE_PERMISSIONS
ROLE_PERMS   = {k: set(v) for k, v in DEFAULT_ROLE_PERMISSIONS.items()}
ROLE_STAFF   = ROLE_INVENTORY   # alias

# AUTH MESSAGES
ERROR_USER_NOT_FOUND      = "User not found"
ERROR_INVALID_CREDENTIALS = "Invalid username or password"
ERROR_ACCOUNT_DISABLED    = "User account is deactivated"
ERROR_USER_DISABLED       = "This account is disabled."

# ── Common weak passwords (blocked by password policy) ────────────────────
COMMON_WEAK_PASSWORDS: set[str] = {
    "password", "password1", "password12", "password123",
    "123456789012", "1234567890123", "qwerty123456",
    "admin123456", "admin1234", "admin123",
    "qwertyuiop", "abcdefghijkl",
    "passw0rd123", "letmein123456",
    "welcome123456", "monkey123456",
    "dragon123456", "master123456",
    "sunshine123456", "princess123456",
}
