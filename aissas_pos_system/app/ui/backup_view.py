"""
backup_view.py
Database Backup & Restore UI.
Only accessible to Admin (P_DATABASE permission).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.config import THEME
from app.db.database import Database
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService, BACKUP_DIR


class BackupView(tk.Frame):
    def __init__(self, parent, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db      = db
        self.auth    = auth
        self.backup  = BackupService(db.db_path)

        self._build()
        self._load_list()

    def _build(self):
        BG    = THEME["bg"]
        BROWN = THEME["primary"]

        # ── Page header bar ──────────────────────────────────────────────────
        hdr_bar = tk.Frame(self, bg=THEME["sidebar"])
        hdr_bar.pack(fill="x")
        tk.Frame(hdr_bar, bg=THEME["primary"], width=5).pack(side="left", fill="y")
        tk.Label(hdr_bar, text="Database Backup & Restore",
                 bg=THEME["sidebar"], fg="#FFFFFF",
                 font=("Segoe UI", 14, "bold"),
                 padx=16, pady=12).pack(side="left")

        # Backup folder info — small card showing where backups are stored
        info_card = tk.Frame(self, bg=THEME["panel"],
                              highlightthickness=1,
                              highlightbackground=THEME["border"])
        info_card.pack(fill="x", padx=20, pady=(12, 6))

        tk.Label(info_card, text="Backup Folder",
                 bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold")
                 ).pack(anchor="w", padx=14, pady=(8, 0))

        path_row = tk.Frame(info_card, bg=THEME["panel"])
        path_row.pack(fill="x", padx=14, pady=(2, 10))
        self._folder_path_lbl = tk.Label(
            path_row, text=str(BACKUP_DIR),
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", 9), anchor="w",
        )
        self._folder_path_lbl.pack(side="left", fill="x", expand=True)

        tk.Button(
            path_row, text="Open Folder",
            command=self._open_backup_folder,
            bg=THEME["panel"], fg=THEME["primary"], bd=1,
            relief="solid", padx=10, pady=4, cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side="right", padx=(8, 0))

        # Status bar
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, bg=BG,
                 fg=THEME["success"], font=("Segoe UI", 9, "italic"),
                 wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 0))

        # Action buttons
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=20, pady=(8, 12))

        tk.Button(
            btn_row, text="\U0001f4e6 Create Backup Now",
            command=self._create_backup,
            bg=THEME["primary"], fg="white", relief="flat",
            padx=14, pady=7, cursor="hand2", font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row, text="\U0001f4c2 Restore from File…",
            command=self._restore_from_file,
            bg=THEME["warning"], fg="white", relief="flat",
            padx=14, pady=7, cursor="hand2", font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_row, text="⟳ Refresh List",
            command=self._load_list,
            bg=THEME["panel"], fg=THEME["primary"], relief="flat",
            padx=14, pady=7, cursor="hand2", font=("Segoe UI", 9),
            highlightthickness=1, highlightbackground=THEME["border"],
        ).pack(side="left")

        # Backup list
        lf = tk.LabelFrame(self, text="  Backup History  ",
                           bg=BG, fg=BROWN, font=("Segoe UI", 9, "bold"),
                           bd=1, relief="groove", labelanchor="nw")
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        cols = [("created", "Created", 180), ("filename", "Filename", 320), ("size", "Size (KB)", 90)]
        self._tree = ttk.Treeview(lf, columns=[c[0] for c in cols], show="headings", height=18)
        for cid, heading, w in cols:
            self._tree.heading(cid, text=heading)
            self._tree.column(cid, width=w, minwidth=60)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True, padx=4, pady=4)

        restore_btn_row = tk.Frame(self, bg=BG)
        restore_btn_row.pack(fill="x", padx=20, pady=(0, 12))
        self._restore_btn = tk.Button(
            restore_btn_row, text="↩ Restore Selected Backup",
            command=self._restore_selected,
            bg=THEME["border"], fg=THEME["muted"], relief="flat",
            state="disabled",
            padx=14, pady=7, cursor="arrow", font=("Segoe UI", 9, "bold"),
        )
        self._restore_btn.pack(side="left")

        tk.Label(restore_btn_row,
                 text="⚠ Restoring will overwrite the live database. The current DB is saved automatically as a safety backup.",
                 bg=BG, fg=THEME["muted"], font=("Segoe UI", 8),
                 wraplength=500, justify="left").pack(side="left", padx=12)

        # Toggle restore button enabled state with selection
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select, add="+")

    def _on_tree_select(self, _event=None):
        try:
            has_sel = bool(self._tree.selection())
            if has_sel:
                self._restore_btn.configure(
                    state="normal",
                    bg=THEME["danger"], fg="white",
                    cursor="hand2",
                )
            else:
                self._restore_btn.configure(
                    state="disabled",
                    bg=THEME["border"], fg=THEME["muted"],
                    cursor="arrow",
                )
        except Exception:
            pass

    def _load_list(self):
        self._tree.delete(*self._tree.get_children())
        backups = self.backup.list_backups()
        for b in backups:
            self._tree.insert("", "end", iid=b["path"],
                              values=(b["created"], b["filename"], b["size_kb"]))
        if not backups:
            self._status_var.set(
                "  No backups yet. Use 'Create Backup Now' to save a copy."
            )
        else:
            self._status_var.set(f"  {len(backups)} backup(s) on disk.")
        # Selection is cleared after delete/insert — sync button state.
        self._on_tree_select()

    def _create_backup(self):
        try:
            ok, msg = self.backup.create_backup("manual")
        except Exception as exc:
            from app.utils import log_error
            log_error("Manual backup", exc)
            messagebox.showerror(
                "Backup Failed",
                "Could not create the backup. Please check disk space and try again.",
            )
            return
        if ok:
            self._status_var.set(f"✅ Backup created: {os.path.basename(msg)}")
            self._load_list()
        else:
            messagebox.showerror("Backup Failed", msg)

    def _open_backup_folder(self):
        """Open the backup folder in the OS file browser. Ensures the
        directory exists first — handles fresh installs / packaged EXE
        builds where no backup has been written yet."""
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            from app.utils import log_error
            log_error("Open backup folder mkdir", exc)
            messagebox.showinfo(
                "Backup Folder",
                f"Backups are saved at:\n{BACKUP_DIR}",
            )
            return

        path = str(BACKUP_DIR)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            from app.utils import log_error
            log_error("Open backup folder", exc)
            messagebox.showinfo(
                "Backup Folder",
                f"Backups are saved at:\n{path}",
            )

    def _restore_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a backup from the list first.")
            return
        path = sel[0]
        filename = self._tree.set(path, "filename")
        if not messagebox.askyesno(
            "Confirm Restore",
            f"Restore from:\n{filename}\n\nThe current live database will be overwritten.\n"
            "A safety backup will be created automatically.\n\nContinue?",
        ):
            return
        from app.ui.dialogs import PasswordConfirmDialog
        user = self.auth.get_current_user()
        dlg  = PasswordConfirmDialog(self, title="Confirm Restore",
                                     label="Enter your password to confirm restore.")
        self.wait_window(dlg)
        if not dlg.result:
            return
        ok2, _ = self.auth.verify_password(user.username, dlg.result)
        if not ok2:
            messagebox.showerror("Authentication Failed", "Incorrect password. Restore cancelled.")
            return

        ok, msg = self.backup.restore_backup(path)
        if ok:
            messagebox.showinfo("Restore Complete",
                                f"{msg}\n\nPlease RESTART the application for changes to take effect.")
        else:
            messagebox.showerror("Restore Failed", msg)

    def _restore_from_file(self):
        path = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("SQLite DB", "*.db"), ("All Files", "*.*")],
        )
        if not path:
            return
        user = self.auth.get_current_user()
        from app.ui.dialogs import PasswordConfirmDialog
        dlg  = PasswordConfirmDialog(self, title="Confirm Restore",
                                     label="Enter your password to confirm restore from file.")
        self.wait_window(dlg)
        if not dlg.result:
            return
        ok2, _ = self.auth.verify_password(user.username, dlg.result)
        if not ok2:
            messagebox.showerror("Authentication Failed", "Incorrect password.")
            return
        ok, msg = self.backup.restore_backup(path)
        if ok:
            messagebox.showinfo("Restore Complete",
                                f"{msg}\n\nPlease RESTART the application.")
        else:
            messagebox.showerror("Restore Failed", msg)
