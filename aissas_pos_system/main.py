from __future__ import annotations

import tkinter as tk

from app.config import APP_NAME, APP_VERSION
from app.db.database import Database
from app.db.seed_menu import seed_menu, seed_menu_if_empty
from app.db.seed_users import seed_admin_user
from app.services.auth_service import AuthService
from app.ui.app_window import AppWindow


def init_db(db: Database) -> None:
    db.connect()
    db.initialize_schema()
    seed_menu_if_empty(db)
    seed_admin_user(db)


def main() -> None:
    db = Database()
    init_db(db)

    auth = AuthService(db)

    root = tk.Tk()
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.minsize(1000, 650)

    AppWindow(root, db, auth)

    try:
        root.mainloop()
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
