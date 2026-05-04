from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from pathlib import Path

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
    Set the window/taskbar icon using logo dark.png.
    iconphoto(True, ...) propagates the icon to all child windows/dialogs.
    Falls back to logo.ico then logo.png if dark variant is unavailable.
    """
    # Primary: logo dark.png via Pillow (applies to main window AND all dialogs)
    logo_dark = ASSETS_DIR / "logo dark.png"
    for candidate in (logo_dark, LOGO_PATH):
        if not candidate.exists():
            continue
        try:
            from PIL import Image, ImageTk
            img = Image.open(candidate).convert("RGBA")
            _resample = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize((32, 32), _resample)
            photo = ImageTk.PhotoImage(img)
            root.iconphoto(True, photo)   # True = default for all future windows
            root._icon_ref = photo  # type: ignore[attr-defined]  # prevent GC
            return
        except Exception:
            continue

    # Final fallback: .ico file (no Pillow needed, Windows only, no dialog propagation)
    ico_path = ASSETS_DIR / "logo.ico"
    try:
        if ico_path.exists():
            root.iconbitmap(default=str(ico_path))
    except Exception:
        pass


def _handle_corrupt_db(db_path: Path) -> bool:
    """
    Show an error dialog when the database fails its integrity check.
    Returns True if the user chose to back up and reset, False to quit.
    A temporary hidden Tk root is used so the dialog works before the
    main window is created.
    """
    import tkinter.messagebox as mb
    from datetime import datetime

    tmp = tk.Tk()
    tmp.withdraw()
    try:
        reset = mb.askyesno(
            title="Database Integrity Error",
            message=(
                "The database file failed its integrity check and may be corrupted.\n\n"
                "YES — Back up the corrupt file and start with a fresh database.\n"
                "NO  — Quit (keep the file for manual recovery).\n\n"
                f"Database location:\n{db_path}"
            ),
            icon="error",
            parent=tmp,
        )
        if not reset:
            return False

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(f"pos_corrupt_{ts}.db")
        try:
            db_path.rename(backup)
        except OSError as exc:
            mb.showerror(
                "Backup Failed",
                f"Could not rename the corrupt database:\n{exc}\n\nQuitting.",
                parent=tmp,
            )
            return False

        mb.showinfo(
            "Database Reset",
            f"Corrupt database backed up as:\n  {backup.name}\n\n"
            "A fresh database will now be created and the app will continue.",
            parent=tmp,
        )
        return True
    finally:
        tmp.destroy()


def init_db(db: Database) -> bool:
    """
    Connect, integrity-check, migrate schema, and seed the database.
    Returns False if the DB is corrupt and the user chose to quit rather
    than reset — the caller should exit cleanly in that case.
    """
    db.connect()

    if not db.check_integrity():
        db.disconnect()
        if not _handle_corrupt_db(db.db_path):
            return False
        # User chose to reset: reconnect against the now-absent file so
        # SQLite creates a clean database on the next connect() call.
        db.connect()

    db.initialize_schema()
    seed_menu_if_empty(db)
    seed_admin_user(db)
    return True


def main() -> None:
    db = Database()
    if not init_db(db):
        return

    auth = AuthService(db)

    root = tk.Tk()
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.minsize(1024, 650)
    root.configure(bg="#e6ddbd")   # permanent beige root bg — any exposed gap matches canvas
    # Start maximized before any UI is built so the first layout pass
    # commits at full size — no resize snap, no partial-width flash.
    try:
        root.state("zoomed")
    except Exception:
        try:
            root.attributes("-zoomed", True)
        except Exception:
            pass

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
