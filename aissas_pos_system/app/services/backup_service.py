"""
backup_service.py
Handles database backup, restore, and scheduled daily backups.
"""
from __future__ import annotations

import shutil
import threading
import time
import datetime as _dt
from pathlib import Path
from typing import Callable, Optional

from app.config import DB_PATH, DATA_DIR


BACKUP_DIR = DATA_DIR / "backups"


def _ts() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


class BackupService:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else Path(DB_PATH)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

    # ── Manual backup ──────────────────────────────────────────────────────
    def create_backup(self, label: str = "manual") -> tuple[bool, str]:
        """Create a timestamped backup of the database. Returns (ok, path_or_error)."""
        try:
            dest = BACKUP_DIR / f"pos_{label}_{_ts()}.db"
            shutil.copy2(self.db_path, dest)
            self._prune_old_backups(keep=30)
            return True, str(dest)
        except Exception as e:
            return False, str(e)

    # ── Restore ────────────────────────────────────────────────────────────
    def restore_backup(self, backup_path: str) -> tuple[bool, str]:
        """Overwrite the live DB with a chosen backup. Returns (ok, message)."""
        try:
            src = Path(backup_path)
            if not src.exists():
                return False, "Backup file not found."
            safety = BACKUP_DIR / f"pos_pre_restore_{_ts()}.db"
            shutil.copy2(self.db_path, safety)
            shutil.copy2(src, self.db_path)
            return True, f"Restored from {src.name}. Previous DB saved as {safety.name}."
        except Exception as e:
            return False, str(e)

    # ── Backup list ────────────────────────────────────────────────────────
    def list_backups(self) -> list[dict]:
        """Return sorted list of backup metadata dicts (newest first)."""
        results = []
        for f in sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = f.stat()
            results.append({
                "filename": f.name,
                "path": str(f),
                "size_kb": round(stat.st_size / 1024, 1),
                "created": _dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        return results

    # ── Auto-prune ─────────────────────────────────────────────────────────
    def _prune_old_backups(self, keep: int = 30) -> None:
        backups = sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime)
        while len(backups) > keep:
            try:
                backups.pop(0).unlink(missing_ok=True)
            except Exception:
                break

    # ── Scheduled daily backup ─────────────────────────────────────────────
    def start_scheduler(self, on_backup: Optional[Callable[[bool, str], None]] = None) -> None:
        """Start background thread that creates a daily auto-backup at midnight-ish."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        self._stop_flag.clear()

        def _loop():
            last_date = None
            while not self._stop_flag.is_set():
                today = _dt.date.today()
                if last_date != today:
                    last_date = today
                    ok, msg = self.create_backup("auto")
                    if on_backup:
                        try:
                            on_backup(ok, msg)
                        except Exception:
                            pass
                self._stop_flag.wait(60)

        self._scheduler_thread = threading.Thread(target=_loop, daemon=True, name="BackupScheduler")
        self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        self._stop_flag.set()
