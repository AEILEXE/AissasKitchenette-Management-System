"""
backup_view.py
Database Backup & Restore UI.
Only accessible to Admin (P_DATABASE permission).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.config import THEME
from app.db.database import Database
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService


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

        # Status bar
        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, bg=BG,
                 fg=THEME["success"], font=("Segoe UI", 9, "italic"),
                 wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(8, 0))

        # Action buttons
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=20, pady=(4, 12))

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
        tk.Button(
            restore_btn_row, text="↩ Restore Selected Backup",
            command=self._restore_selected,
            bg=THEME["danger"], fg="white", relief="flat",
            padx=14, pady=7, cursor="hand2", font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        tk.Label(restore_btn_row,
                 text="⚠ Restoring will overwrite the live database. The current DB is saved automatically as a safety backup.",
                 bg=BG, fg=THEME["muted"], font=("Segoe UI", 8),
                 wraplength=500, justify="left").pack(side="left", padx=12)

    def _load_list(self):
        self._tree.delete(*self._tree.get_children())
        backups = self.backup.list_backups()
        for b in backups:
            self._tree.insert("", "end", iid=b["path"],
                              values=(b["created"], b["filename"], b["size_kb"]))
        self._status_var.set(f"  {len(backups)} backup(s) found in history.")

    def _create_backup(self):
        ok, msg = self.backup.create_backup("manual")
        if ok:
            self._status_var.set(f"✅ Backup created: {msg}")
            self._load_list()
        else:
            messagebox.showerror("Backup Failed", msg)

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
