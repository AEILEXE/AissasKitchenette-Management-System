from __future__ import annotations

# =========================
# APP ROLES (match DB values)
# =========================
ROLE_ADMIN = "ADMIN"
ROLE_MANAGER = "MANAGER"
ROLE_CLERK = "CLERK"

ROLES = [ROLE_ADMIN, ROLE_MANAGER, ROLE_CLERK]

# =========================
# PERMISSION KEYS
# =========================
P_POS = "pos.access"
P_INV_VIEW = "inventory.view"
P_INV_MANAGE = "inventory.manage"
P_REPORTS = "reports.view"
P_USERS = "users.manage"

# =========================
# ROLE -> PERMISSIONS
# =========================
ROLE_PERMISSIONS = {
    ROLE_ADMIN: [P_POS, P_INV_VIEW, P_INV_MANAGE, P_REPORTS, P_USERS],
    ROLE_MANAGER: [P_POS, P_INV_VIEW, P_INV_MANAGE, P_REPORTS],
    ROLE_CLERK: [P_POS, P_INV_VIEW],
}

# Backward compatible alias (if other code uses ROLE_PERMS)
ROLE_PERMS = {k: set(v) for k, v in ROLE_PERMISSIONS.items()}

# =========================
# AUTH MESSAGES
# =========================
ERROR_USER_NOT_FOUND = "User not found"
ERROR_INVALID_CREDENTIALS = "Invalid username or password"
ERROR_ACCOUNT_DISABLED = "User account is deactivated"
ERROR_USER_DISABLED = "This account is disabled."
