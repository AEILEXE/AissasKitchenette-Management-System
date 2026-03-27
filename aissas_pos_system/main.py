from __future__ import annotations

import logging
import os
import sys
import tkinter as tk

# ── Packaged-EXE bootstrap ────────────────────────────────────────────────
# Must run BEFORE any app imports so config.py sees the right env.

def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

if _is_frozen():
    # Redirect matplotlib's config/cache to a writable directory
    # (avoids matplotlib trying to write into the read-only temp bundle)
    _writable = sys.executable  # full path to the .exe
    _mpl_dir = os.path.join(os.path.dirname(_writable), "mpl_config")
    os.makedirs(_mpl_dir, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", _mpl_dir)

    # Write a startup log next to the EXE so crashes are diagnosable.
    # console=False hides all stderr in packaged mode; the log captures it.
    _log_path = os.path.join(os.path.dirname(_writable), "app.log")
    logging.basicConfig(
        filename=_log_path,
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )
    # Also catch unhandled exceptions into the log
    def _log_excepthook(exc_type, exc_value, exc_tb):
        logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _log_excepthook

# ── Normal imports ────────────────────────────────────────────────────────
from app.config import APP_NAME, APP_VERSION, ASSETS_DIR, LOGO_PATH
from app.db.database import Database
from app.db.seed_menu import seed_menu_if_empty
from app.db.seed_users import seed_admin_user
from app.services.auth_service import AuthService
from app.ui.app_window import AppWindow


def _set_window_icon(root: tk.Tk) -> None:
    """
    Set the window/taskbar icon.
    - Prefers logo.ico (multi-size, best Windows support).
    - Falls back to iconphoto() via Pillow if only logo.jpg is present.
    - Silently skips if neither is found or Pillow is missing.
    """
    ico_path = ASSETS_DIR / "logo.ico"
    try:
        if ico_path.exists():
            root.iconbitmap(default=str(ico_path))
            return
    except Exception:
        pass

    try:
        if LOGO_PATH.exists():
            from PIL import Image, ImageTk
            img = Image.open(LOGO_PATH).convert("RGBA")
            img = img.resize((32, 32), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            root.iconphoto(True, photo)
            root._icon_ref = photo  # type: ignore[attr-defined]  # prevent GC
    except Exception:
        pass


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

    _set_window_icon(root)

    app_window = AppWindow(root, db, auth)

    root.bind_all("<Control-equal>", lambda _e: app_window._on_zoom(1))
    root.bind_all("<Control-plus>",  lambda _e: app_window._on_zoom(1))
    root.bind_all("<Control-minus>", lambda _e: app_window._on_zoom(-1))
    root.bind_all("<Control-0>",     lambda _e: app_window._on_zoom(0))

    try:
        root.mainloop()
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
