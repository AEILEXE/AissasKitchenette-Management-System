from __future__ import annotations

from app.config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
from app.constants import ROLE_ADMIN
from app.db.database import Database
from app.utils import hash_password


def seed_admin_user(db: Database) -> None:
    username = DEFAULT_ADMIN_USERNAME.strip()
    pw_hash = hash_password(DEFAULT_ADMIN_PASSWORD)

    # Does admin exist?
    row = db.fetchone("SELECT id, role FROM users WHERE username = ? LIMIT 1;", (username,))
    if row:
        # If role is wrong (e.g., 'admin' instead of 'ADMIN'), fix it
        current_role = (row["role"] or "").strip()
        if current_role != ROLE_ADMIN:
            db.execute("UPDATE users SET role = ? WHERE id = ?;", (ROLE_ADMIN, int(row["id"])))
        return

    # Create admin if missing
    db.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active)
        VALUES (?, ?, ?, ?)
        """,
        (username, pw_hash, ROLE_ADMIN, 1),
    )
