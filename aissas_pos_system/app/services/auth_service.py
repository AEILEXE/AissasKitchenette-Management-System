from __future__ import annotations

import re
import time
from typing import Optional

from app.constants import (
    DEFAULT_ROLE_PERMISSIONS,
    COMMON_WEAK_PASSWORDS,
    ERROR_INVALID_CREDENTIALS,
    ERROR_USER_DISABLED,
    ERROR_USER_NOT_FOUND,
    ROLES,
)
from app.db.dao import UserDAO, RolePermissionDAO, AuditLogDAO
from app.db.database import Database
from app.models.user import User
from app.utils import verify_password, hash_password


# ── Failed-login lockout policy ───────────────────────────────────────────────
# After this many bad attempts on a single username, lock for COOLDOWN_SECONDS.
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_COOLDOWN_SECONDS = 300  # 5 minutes


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
        self.audit_dao = AuditLogDAO(db)
        self._current_user: Optional[User] = None
        self._last_error: str = ""
        # In-memory lockout tracker: {username_lower: (failed_count, lock_until_ts)}
        self._fail_state: dict[str, tuple[int, float]] = {}

    def get_last_error(self) -> str:
        return self._last_error

    def get_current_user(self) -> Optional[User]:
        return self._current_user

    def _is_locked_out(self, username: str) -> tuple[bool, int]:
        """Return (locked, remaining_seconds). Cleans up expired locks."""
        key = (username or "").strip().lower()
        if not key:
            return False, 0
        entry = self._fail_state.get(key)
        if not entry:
            return False, 0
        _, lock_until = entry
        if lock_until <= 0:
            return False, 0
        now = time.time()
        if now >= lock_until:
            self._fail_state.pop(key, None)
            return False, 0
        return True, int(lock_until - now)

    def _record_failed_attempt(self, username: str) -> int:
        """Increment failed counter; return current count."""
        key = (username or "").strip().lower()
        if not key:
            return 0
        count, lock_until = self._fail_state.get(key, (0, 0.0))
        count += 1
        if count >= LOCKOUT_MAX_ATTEMPTS:
            lock_until = time.time() + LOCKOUT_COOLDOWN_SECONDS
        self._fail_state[key] = (count, lock_until)
        return count

    def _clear_failed_attempts(self, username: str) -> None:
        key = (username or "").strip().lower()
        self._fail_state.pop(key, None)

    def _safe_audit(self, action: str, detail: str = "",
                    user_id: int = 0, username: str = "") -> None:
        try:
            self.audit_dao.log(
                username=username, action=action, detail=detail,
                user_id=user_id,
            )
        except Exception:
            pass

    def login(self, username: str, password: str) -> bool:
        self._last_error = ""
        uname = (username or "").strip()

        locked, remaining = self._is_locked_out(uname)
        if locked:
            mins = max(1, (remaining + 59) // 60)
            self._last_error = (
                f"Too many failed attempts. Try again in about {mins} minute(s)."
            )
            self._safe_audit("LOGIN_LOCKED", detail=uname, username=uname)
            return False

        user = self.user_dao.get_by_username(uname)
        if not user:
            self._record_failed_attempt(uname)
            self._safe_audit("LOGIN_FAILED",
                              detail=f"unknown user: {uname}", username=uname)
            self._last_error = ERROR_USER_NOT_FOUND
            return False

        if not user.is_active:
            self._safe_audit("LOGIN_FAILED",
                              detail="user disabled",
                              user_id=user.user_id, username=user.username)
            self._last_error = ERROR_USER_DISABLED
            return False

        if not verify_password(password, user.password_hash):
            count = self._record_failed_attempt(uname)
            self._safe_audit("LOGIN_FAILED",
                              detail=f"bad password (attempt {count})",
                              user_id=user.user_id, username=user.username)
            self._last_error = ERROR_INVALID_CREDENTIALS
            return False

        self._clear_failed_attempts(uname)
        user.role = (user.role or "").upper()
        self._current_user = user
        self._safe_audit("LOGIN_SUCCESS",
                          detail=f"role={user.role}",
                          user_id=user.user_id, username=user.username)
        return True

    def logout(self) -> None:
        u = self._current_user
        if u is not None:
            self._safe_audit("LOGOUT", user_id=u.user_id, username=u.username)
        self._current_user = None
        self._last_error = ""

    def create_user(
        self, username: str, password: str, role: str,
        enforce_policy: bool = True,
        full_name: str = "",
    ) -> tuple[bool, str, int]:
        if not username.strip():
            return False, "Username cannot be empty", 0
        if not full_name.strip():
            return False, "Full Name is required", 0
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
        uid = self.user_dao.create(username.strip(), pw_hash, role.upper(),
                                   full_name.strip())
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
