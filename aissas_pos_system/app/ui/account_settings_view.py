"""
app/ui/account_settings_view.py
Settings dialog: Profile, Security, Database Backup, User Management.
"""
from __future__ import annotations

import shutil
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

from app.config import THEME, DB_PATH
from app.db.database import Database
from app.db.dao import UserDAO
from app.services.auth_service import AuthService
from app.constants import ROLES
from app.ui import ui_scale


def _bind_mousewheel(canvas: tk.Canvas) -> None:
    """Bind mousewheel only while the mouse is inside the canvas."""
    def _scroll(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))


class AccountSettingsDialog(tk.Toplevel):
    """Settings dialog: Profile, Security, Database Management, User Management."""

    def __init__(self, parent: tk.Widget, db: Database, auth: AuthService):
        super().__init__(parent)
        self.db       = db
        self.auth     = auth
        self.user_dao = UserDAO(db)

        self.title("Settings")
        self.configure(bg=THEME["bg"])
        self.geometry(f"{ui_scale.s(680)}x{ui_scale.s(640)}")
        self.minsize(580, 500)
        if isinstance(parent, tk.Toplevel):
            self.transient(parent)
        self.grab_set()

        self._build()

    def _build(self):
        u        = self.auth.get_current_user()
        is_admin = u and u.role.upper() == "ADMIN"

        outer = tk.Frame(self, bg=THEME["bg"])
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=THEME["bg"], highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=sb.set)

        inner = tk.Frame(canvas, bg=THEME["bg"])
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
            add="+",
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win, width=e.width),
            add="+",
        )
        _bind_mousewheel(canvas)

        title_row = tk.Frame(inner, bg=THEME["bg"])
        title_row.pack(fill="x", padx=24, pady=(18, 2))

        tk.Label(
            title_row, text="Settings",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(20), "bold"),
        ).pack(side="left")

        tk.Button(
            title_row, text="X  Close",
            bg=THEME["panel2"], fg=THEME["muted"],
            bd=0, padx=ui_scale.s(10), pady=ui_scale.s(6),
            cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(9)),
            command=self.destroy,
        ).pack(side="right")

        tk.Label(
            inner, text="Manage your account and system preferences.",
            bg=THEME["bg"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=24, pady=(0, 16))

        # Profile
        self._section_header(inner, "Profile")
        profile_card = self._card(inner)
        info_row = tk.Frame(profile_card, bg=THEME["panel"])
        info_row.pack(fill="x", padx=16, pady=(14, 14))

        avatar_letter = (u.username[0].upper() if u and u.username else "?")
        tk.Label(
            info_row, text=avatar_letter,
            bg=THEME["brown"], fg="white",
            font=("Segoe UI", ui_scale.scale_font(20), "bold"),
            width=3, pady=ui_scale.s(6),
        ).pack(side="left", padx=(0, 16))

        user_info = tk.Frame(info_row, bg=THEME["panel"])
        user_info.pack(side="left", fill="x", expand=True)
        tk.Label(
            user_info, text=u.username if u else "\u2014",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(13), "bold"), anchor="w",
        ).pack(anchor="w")

        role_text  = u.role.upper() if u else "\u2014"
        role_color = THEME["brown"] if role_text == "ADMIN" else THEME["accent"]
        tk.Label(
            user_info, text=f"  {role_text}  ",
            bg=role_color, fg="white",
            font=("Segoe UI", ui_scale.scale_font(8), "bold"), padx=4, pady=2,
        ).pack(anchor="w", pady=(4, 0))

        # Security
        self._section_header(inner, "Security")
        sec_card = self._card(inner)
        tk.Label(
            sec_card, text="Change Password",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(
            sec_card,
            text="Update your login credentials. Must be at least 4 characters.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=16, pady=(0, 10))
        self.old_pwd     = self._labeled_entry(sec_card, "Current Password", show="*")
        self.new_pwd     = self._labeled_entry(sec_card, "New Password", show="*")
        self.confirm_pwd = self._labeled_entry(sec_card, "Confirm New Password", show="*")
        pwd_footer = tk.Frame(sec_card, bg=THEME["panel"])
        pwd_footer.pack(fill="x", padx=16, pady=(8, 14))
        tk.Button(
            pwd_footer, text="Update Password",
            bg=THEME["success"], fg="white",
            bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8), cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(10), "bold"),
            command=self._change_password,
        ).pack(side="left")

        if is_admin:
            self._section_header(inner, "Database Management")
            self._build_db_section(inner)
            self._section_header(inner, "User Management")
            self._build_user_mgmt(inner)

        tk.Frame(inner, bg=THEME["bg"], height=ui_scale.s(24)).pack()

    def _section_header(self, parent, text):
        row = tk.Frame(parent, bg=THEME["bg"])
        row.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(row, text=text.upper(), bg=THEME["bg"], fg=THEME["muted"],
                 font=("Segoe UI", ui_scale.scale_font(8), "bold"), anchor="w",
                 ).pack(side="left")
        tk.Frame(row, bg=THEME["border"], height=1
                 ).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

    def _card(self, parent, padx=24, pady=(0, 4)):
        card = tk.Frame(parent, bg=THEME["panel"],
                        highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="x", padx=padx, pady=pady)
        return card

    def _labeled_entry(self, parent, label, show=""):
        tk.Label(parent, text=label, bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", ui_scale.scale_font(9))).pack(anchor="w", padx=16, pady=(6, 2))
        ent = tk.Entry(parent, bd=0, bg=THEME["panel2"], fg=THEME["text"],
                       insertbackground=THEME["text"], show=show,
                       font=("Segoe UI", ui_scale.scale_font(10)))
        ent.pack(fill="x", padx=16, pady=(0, 4), ipady=ui_scale.s(8))
        return ent

    def _build_db_section(self, parent):
        db_card = self._card(parent)
        tk.Label(db_card, text="SQLite Database Backup",
                 bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", ui_scale.scale_font(11), "bold"),
                 ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(
            db_card,
            text="Export a full .db backup or restore from a previous backup file.\n"
                 "Admin password confirmation is required before importing.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)), justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))
        btn_row = tk.Frame(db_card, bg=THEME["panel"])
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        tk.Button(btn_row, text="Export Database (.db)",
                  bg=THEME["accent"], fg="white",
                  bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8), cursor="hand2",
                  font=("Segoe UI", ui_scale.scale_font(9), "bold"),
                  command=self._export_db).pack(side="left", padx=(0, 10))
        tk.Button(btn_row, text="Import Database (.db)",
                  bg=THEME["danger"], fg="white",
                  bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8), cursor="hand2",
                  font=("Segoe UI", ui_scale.scale_font(9), "bold"),
                  command=self._import_db).pack(side="left")

    def _export_db(self):
        dest = filedialog.asksaveasfilename(
            title="Export Database",
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            initialfile="pos_backup.db",
        )
        if not dest:
            return
        try:
            shutil.copy2(str(DB_PATH), dest)
            messagebox.showinfo("Export Complete", f"Database exported to:\n{dest}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not export database:\n{e}")

    def _import_db(self):
        u = self.auth.get_current_user()
        if not u:
            messagebox.showerror("Error", "Not logged in.")
            return

        pwd = _ask_password(self, "Confirm Import", "Enter admin password to confirm import:")
        if pwd is None:
            return

        ok, msg = self.auth.verify_password(u.username, pwd)
        if not ok:
            messagebox.showerror("Authentication Failed", "Incorrect password. Import cancelled.")
            return

        src = filedialog.askopenfilename(
            title="Select Database Backup",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
        )
        if not src:
            return

        confirm = messagebox.askyesno(
            "Confirm Replace",
            "WARNING: This will REPLACE the current database.\n\n"
            "All current data will be overwritten. This cannot be undone.\n\nProceed?",
            icon="warning",
        )
        if not confirm:
            return

        try:
            self.db.close()
            shutil.copy2(src, str(DB_PATH))
            messagebox.showinfo("Import Complete",
                                "Database replaced successfully.\n\nPlease restart the application.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Import Failed", f"Could not import database:\n{e}")

    def _build_user_mgmt(self, parent):
        u     = self.auth.get_current_user()
        users = self.user_dao.list_users()
        users_card = self._card(parent)
        tk.Label(users_card, text="Active Users", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", ui_scale.scale_font(11), "bold"),
                 ).pack(anchor="w", padx=16, pady=(14, 6))

        hdr = tk.Frame(users_card, bg=THEME["beige"])
        hdr.pack(fill="x", padx=16)
        for col_text, w in [("Username", 0), ("Role", 110), ("Status", 90), ("Action", 90)]:
            anchor = "w" if col_text == "Username" else "center"
            expand = col_text == "Username"
            tk.Label(hdr, text=col_text, bg=THEME["beige"], fg=THEME["muted"],
                     font=("Segoe UI", ui_scale.scale_font(8), "bold"),
                     anchor=anchor, width=w // 8 if w else 0,
                     ).pack(side="left", fill="x" if expand else None,
                            expand=expand, padx=10, pady=6)

        for user_row in users:
            row_bg    = THEME["panel"]
            row_frame = tk.Frame(users_card, bg=row_bg,
                                 highlightthickness=1, highlightbackground=THEME["border"])
            row_frame.pack(fill="x", padx=16, pady=2)
            tk.Label(row_frame, text=user_row["username"], bg=row_bg, fg=THEME["text"],
                     font=("Segoe UI", ui_scale.scale_font(10), "bold"), anchor="w",
                     ).pack(side="left", fill="x", expand=True, padx=10, pady=8)
            tk.Label(row_frame, text=user_row["role"], bg=row_bg, fg=THEME["muted"],
                     font=("Segoe UI", ui_scale.scale_font(9)), width=13, anchor="center",
                     ).pack(side="left", padx=4)
            active    = user_row["is_active"]
            status_bg = "#e6f9ec" if active else "#fce8e8"
            status_fg = THEME["success"] if active else THEME["danger"]
            tk.Label(row_frame,
                     text="\u25cf Active" if active else "\u25cf Inactive",
                     bg=status_bg, fg=status_fg,
                     font=("Segoe UI", ui_scale.scale_font(8), "bold"),
                     padx=6, pady=2).pack(side="left", padx=8)
            if active and user_row["user_id"] != (u.user_id if u else None):
                tk.Button(
                    row_frame, text="Deactivate",
                    bg=THEME["danger"], fg="white",
                    bd=0, padx=ui_scale.s(8), pady=ui_scale.s(4), cursor="hand2",
                    font=("Segoe UI", ui_scale.scale_font(8)),
                    command=lambda uid=user_row["user_id"]: self._deactivate_user(uid),
                ).pack(side="right", padx=(4, 10), pady=6)

        create_card = self._card(parent, pady=(8, 4))
        tk.Label(create_card, text="Create New User", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", ui_scale.scale_font(11), "bold"),
                 ).pack(anchor="w", padx=16, pady=(14, 4))
        self.create_user_ent = self._labeled_entry(create_card, "Username")
        self.create_pass_ent = self._labeled_entry(create_card, "Password", show="*")
        tk.Label(create_card, text="Role", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", ui_scale.scale_font(9)),
                 ).pack(anchor="w", padx=16, pady=(6, 2))
        self.create_role_var = tk.StringVar(value=ROLES[0])
        role_combo = ttk.Combobox(create_card, textvariable=self.create_role_var,
                                  values=ROLES, state="readonly",
                                  font=("Segoe UI", ui_scale.scale_font(9)))
        role_combo.pack(fill="x", padx=16, pady=(0, 8))
        create_footer = tk.Frame(create_card, bg=THEME["panel"])
        create_footer.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(create_footer, text="Create User",
                  bg=THEME["success"], fg="white",
                  bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8), cursor="hand2",
                  font=("Segoe UI", ui_scale.scale_font(10), "bold"),
                  command=self._create_user).pack(side="left")

    def _change_password(self):
        old     = self.old_pwd.get()
        new     = self.new_pwd.get()
        confirm = self.confirm_pwd.get()
        if not old or not new or not confirm:
            messagebox.showerror("Required", "All password fields are required.")
            return
        if new != confirm:
            messagebox.showerror("Mismatch", "New passwords do not match.")
            return
        if len(new) < 4:
            messagebox.showerror("Too Short", "Password must be at least 4 characters.")
            return
        u = self.auth.get_current_user()
        if not u:
            messagebox.showerror("Error", "Not logged in.")
            return
        ok, msg = self.auth.verify_password(u.username, old)
        if not ok:
            messagebox.showerror("Incorrect", msg or "Current password is incorrect.")
            return
        try:
            self.user_dao.update_password(u.user_id, new)
            messagebox.showinfo("Success", "Password changed successfully.")
            self.old_pwd.delete(0, tk.END)
            self.new_pwd.delete(0, tk.END)
            self.confirm_pwd.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to change password:\n{e}")

    def _create_user(self):
        username = self.create_user_ent.get().strip()
        password = self.create_pass_ent.get()
        role     = self.create_role_var.get()
        if not username or not password:
            messagebox.showerror("Required", "Username and password are required.")
            return
        if len(password) < 4:
            messagebox.showerror("Too Short", "Password must be at least 4 characters.")
            return
        ok, msg, _ = self.auth.create_user(username, password, role)
        if not ok:
            messagebox.showerror("Create User", msg or "Failed to create user.")
            return
        messagebox.showinfo("Success", f"User '{username}' created successfully.")
        self.destroy()
        AccountSettingsDialog(self.master, self.db, self.auth)

    def _deactivate_user(self, user_id: int):
        if not messagebox.askyesno("Confirm", "Deactivate this user?"):
            return
        try:
            self.user_dao.set_active(user_id, 0)
            messagebox.showinfo("Success", "User deactivated.")
            self.destroy()
            AccountSettingsDialog(self.master, self.db, self.auth)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to deactivate user.\n{e}")


def _ask_password(parent: tk.Widget, title: str, prompt: str):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=THEME["bg"])
    dlg.geometry(f"{ui_scale.s(360)}x{ui_scale.s(170)}")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()
    tk.Label(dlg, text=prompt, bg=THEME["bg"], fg=THEME["text"],
             font=("Segoe UI", ui_scale.scale_font(10))).pack(anchor="w", padx=16, pady=(16, 6))
    var = tk.StringVar()
    ent = tk.Entry(dlg, textvariable=var, show="*", bd=0,
                   bg=THEME["panel2"], fg=THEME["text"],
                   font=("Segoe UI", ui_scale.scale_font(10)))
    ent.pack(fill="x", padx=16, ipady=ui_scale.s(8))
    ent.focus_set()
    result = {"v": None}

    def _ok():
        result["v"] = var.get()
        dlg.destroy()

    btns = tk.Frame(dlg, bg=THEME["bg"])
    btns.pack(fill="x", padx=16, pady=14)
    tk.Button(btns, text="Cancel", bg=THEME["panel2"], fg=THEME["text"],
              bd=0, padx=12, pady=8, cursor="hand2",
              command=dlg.destroy).pack(side="right")
    tk.Button(btns, text="Confirm", bg=THEME["danger"], fg="white",
              bd=0, padx=12, pady=8, cursor="hand2",
              command=_ok).pack(side="right", padx=(0, 8))
    dlg.bind("<Return>", lambda _e: _ok())
    dlg.wait_window()
    return result["v"]
