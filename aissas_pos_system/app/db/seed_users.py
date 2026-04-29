from __future__ import annotations

from app.config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
from app.constants import ROLE_ADMIN
from app.db.database import Database
from app.utils import hash_password


def seed_admin_user(db: Database) -> None:
    username = DEFAULT_ADMIN_USERNAME.strip()
    pw_hash  = hash_password(DEFAULT_ADMIN_PASSWORD)

    row = db.fetchone(
        "SELECT id, role FROM users WHERE username = ? LIMIT 1;", (username,)
    )
    if row:
        current_role = (row["role"] or "").strip()
        if current_role != ROLE_ADMIN:
            db.execute("UPDATE users SET role = ? WHERE id = ?;",
                       (ROLE_ADMIN, int(row["id"])))
        return

    db.execute(
        "INSERT INTO users (username, password_hash, role, full_name, is_active) "
        "VALUES (?, ?, ?, ?, ?)",
        (username, pw_hash, ROLE_ADMIN, "Administrator", 1),
    )
