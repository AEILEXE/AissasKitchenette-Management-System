from __future__ import annotations

import re
from typing import Optional

from app.constants import (
    DEFAULT_ROLE_PERMISSIONS,
    COMMON_WEAK_PASSWORDS,
    ERROR_INVALID_CREDENTIALS,
    ERROR_USER_DISABLED,
    ERROR_USER_NOT_FOUND,
    ROLES,
)
from app.db.dao import UserDAO, RolePermissionDAO
from app.db.database import Database
from app.models.user import User
from app.utils import verify_password, hash_password


def validate_password_strength(username: str, password: str) -> tuple[bool, str]:
    """
    Check password against policy.
    Returns (True, "") on pass, or (False, "reason") on fail.
    Policy:
      - Min 12 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character
      - Must NOT contain the username (case-insensitive)
      - Must NOT be a known common weak password
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long."

    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter (A-Z)."

    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter (a-z)."

    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one number (0-9)."

    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must include at least one special character (!@#$%^&*…)."

    if username and username.lower() in password.lower():
        return False, "Password must not contain your username."

    if password.lower() in COMMON_WEAK_PASSWORDS:
        return False, "That password is too common. Please choose a stronger one."

    return True, ""


class AuthService:
    def __init__(self, db: Database):
        self.user_dao  = UserDAO(db)
        self.rbac_dao  = RolePermissionDAO(db)
        self._current_user: Optional[User] = None
        self._last_error: str = ""

    def get_last_error(self) -> str:
        return self._last_error

    def get_current_user(self) -> Optional[User]:
        return self._current_user

    def login(self, username: str, password: str) -> bool:
        self._last_error = ""
        user = self.user_dao.get_by_username(username.strip())
        if not user:
            self._last_error = ERROR_USER_NOT_FOUND
            return False

        if not user.is_active:
            self._last_error = ERROR_USER_DISABLED
            return False

        if not verify_password(password, user.password_hash):
            self._last_error = ERROR_INVALID_CREDENTIALS
            return False

        user.role = (user.role or "").upper()
        self._current_user = user
        return True

    def logout(self) -> None:
        self._current_user = None
        self._last_error = ""

    def create_user(
        self, username: str, password: str, role: str,
        enforce_policy: bool = True,
    ) -> tuple[bool, str, int]:
        if not username.strip():
            return False, "Username cannot be empty", 0
        if role not in ROLES:
            return False, f"Invalid role: {role}", 0

        if enforce_policy:
            ok, reason = validate_password_strength(username.strip(), password)
            if not ok:
                return False, reason, 0
        else:
            if len(password) < 4:
                return False, "Password must be at least 4 characters", 0

        if self.user_dao.get_by_username(username.strip()):
            return False, "Username already exists", 0

        pw_hash = hash_password(password)
        uid = self.user_dao.create(username.strip(), pw_hash, role.upper())
        return True, f"User '{username}' created successfully", uid

    def has_permission(self, perm: str) -> bool:
        """
        Check if the current user has a given permission.
        Priority:
          1. DB role_permissions table (live, admin-togglable)
          2. Fall back to DEFAULT_ROLE_PERMISSIONS if no DB entry
        """
        if not self._current_user:
            return False
        role = (self._current_user.role or "").upper()
        try:
            return self.rbac_dao.has_permission(role, perm)
        except Exception:
            # DB unavailable — fall back to static defaults
            return perm in DEFAULT_ROLE_PERMISSIONS.get(role, set())

    def verify_password(self, username: str, password: str) -> tuple[bool, str]:
        """Verify if a given password matches a user's stored hash."""
        user = self.user_dao.get_by_username(username.strip())
        if not user:
            return False, "User not found"
        if not verify_password(password, user.password_hash):
            return False, "Incorrect password"
        return True, "Password verified"

    def change_password(
        self, user_id: int, username: str,
        new_password: str, enforce_policy: bool = True,
    ) -> tuple[bool, str]:
        """Change a user's password, optionally enforcing policy."""
        if enforce_policy:
            ok, reason = validate_password_strength(username, new_password)
            if not ok:
                return False, reason
        pw_hash = hash_password(new_password)
        try:
            self.user_dao.update_password(user_id, pw_hash)
            return True, "Password changed successfully."
        except Exception as e:
            return False, f"Failed to change password: {e}"
