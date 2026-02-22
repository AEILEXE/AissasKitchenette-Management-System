from __future__ import annotations

from typing import Optional

from app.constants import (
    ROLE_PERMS,
    ERROR_INVALID_CREDENTIALS,
    ERROR_USER_DISABLED,
    ERROR_USER_NOT_FOUND,
    ROLES,
)
from app.db.dao import UserDAO
from app.db.database import Database
from app.models.user import User
from app.utils import verify_password, hash_password


class AuthService:
    def __init__(self, db: Database):
        self.user_dao = UserDAO(db)
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

        # ✅ normalize role so permission mapping works even if DB has lowercase values
        user.role = (user.role or "").upper()
        self._current_user = user
        return True

    def logout(self) -> None:
        self._current_user = None
        self._last_error = ""

    def create_user(self, username: str, password: str, role: str) -> tuple[bool, str, int]:
        if not username.strip():
            return False, "Username cannot be empty", 0
        if len(password) < 4:
            return False, "Password must be at least 4 characters", 0
        if role not in ROLES:
            return False, f"Invalid role: {role}", 0

        # Check if username exists
        if self.user_dao.get_by_username(username.strip()):
            return False, "Username already exists", 0

        pw_hash = hash_password(password)
        uid = self.user_dao.create(username.strip(), pw_hash, role.upper())
        return True, f"User '{username}' created successfully", uid

    def has_permission(self, perm: str) -> bool:
        if not self._current_user:
            return False
        role = (self._current_user.role or "").upper()
        return perm in ROLE_PERMS.get(role, set())

    def verify_password(self, username: str, password: str) -> tuple[bool, str]:
        """Verify if a given password matches a user's password. Returns (success, message)."""
        user = self.user_dao.get_by_username(username.strip())
        if not user:
            return False, "User not found"
        
        if not verify_password(password, user.password_hash):
            return False, "Incorrect password"
        
        return True, "Password verified"

