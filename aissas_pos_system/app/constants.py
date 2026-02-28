from __future__ import annotations

# APP ROLES (match DB values)
ROLE_ADMIN   = "ADMIN"
ROLE_MANAGER = "MANAGER"
ROLE_CLERK   = "CLERK"

ROLES = [ROLE_ADMIN, ROLE_MANAGER, ROLE_CLERK]

# ── New granular permission keys (stored in role_permissions table) ────────────
P_SELL          = "can_sell"
P_DISCOUNT      = "can_apply_discount"
P_VOID          = "can_void_transaction"
P_REPORTS       = "can_view_reports"
P_PROFIT        = "can_view_profit"
P_MANAGE_PRODS  = "can_manage_products"
P_EDIT_PRICE    = "can_edit_price"
P_MANAGE_USERS  = "can_manage_users"
P_SETTINGS      = "can_access_settings"
P_EXPORT        = "can_export_data"
P_DATABASE      = "can_manage_database"
P_ML            = "can_manage_ml"
P_INV_VIEW      = "can_view_inventory"   # broad inventory view

# Complete ordered list of all permission keys (used for UI + DB seeding)
ALL_PERMISSION_KEYS: list[str] = [
    P_SELL,
    P_DISCOUNT,
    P_VOID,
    P_REPORTS,
    P_PROFIT,
    P_MANAGE_PRODS,
    P_EDIT_PRICE,
    P_MANAGE_USERS,
    P_SETTINGS,
    P_EXPORT,
    P_DATABASE,
    P_ML,
    P_INV_VIEW,
]

# Human-readable labels for UI
PERMISSION_LABELS: dict[str, str] = {
    P_SELL:         "Sell (POS access)",
    P_DISCOUNT:     "Apply discounts",
    P_VOID:         "Void / cancel transactions",
    P_REPORTS:      "View reports",
    P_PROFIT:       "View profit / cost info",
    P_MANAGE_PRODS: "Manage products",
    P_EDIT_PRICE:   "Edit product prices",
    P_MANAGE_USERS: "Manage users",
    P_SETTINGS:     "Access settings",
    P_EXPORT:       "Export data",
    P_DATABASE:     "Manage database backup",
    P_ML:           "Manage ML / seeding",
    P_INV_VIEW:     "View inventory",
}

# Default permissions per role (used for initial DB seed + fallback)
DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_ADMIN: set(ALL_PERMISSION_KEYS),  # Admin gets everything
    ROLE_MANAGER: {
        P_SELL, P_DISCOUNT, P_VOID,
        P_REPORTS, P_MANAGE_PRODS, P_EDIT_PRICE,
        P_SETTINGS, P_EXPORT, P_INV_VIEW,
    },
    ROLE_CLERK: {
        P_SELL, P_DISCOUNT, P_INV_VIEW,
    },
}

# ── Backward-compatible aliases (old code used these) ─────────────────────────
P_POS        = P_SELL
P_INV_MANAGE = P_MANAGE_PRODS
P_USERS      = P_MANAGE_USERS

# Old ROLE_PERMISSIONS / ROLE_PERMS still work for any code still using them
ROLE_PERMISSIONS = DEFAULT_ROLE_PERMISSIONS
ROLE_PERMS = {k: set(v) for k, v in DEFAULT_ROLE_PERMISSIONS.items()}

# AUTH MESSAGES
ERROR_USER_NOT_FOUND      = "User not found"
ERROR_INVALID_CREDENTIALS = "Invalid username or password"
ERROR_ACCOUNT_DISABLED    = "User account is deactivated"
ERROR_USER_DISABLED       = "This account is disabled."

# ── Common weak passwords (blocked by password policy) ────────────────────────
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
