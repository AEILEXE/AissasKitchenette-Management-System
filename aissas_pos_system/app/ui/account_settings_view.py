"""
app/ui/account_settings_view.py
Settings: Profile, Security (policy-enforced password change), Database Backup,
          User Management (create + deactivate), Role Permissions (admin only).
"""
from __future__ import annotations

import shutil
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

from app.config import THEME, DB_PATH
from app.db.database import Database
from app.db.dao import UserDAO, RolePermissionDAO
from app.services.auth_service import AuthService
from app.constants import (
    ROLES, ROLE_ADMIN,
    ALL_PERMISSION_KEYS, PERMISSION_LABELS,
)
from app.ui import ui_scale


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bind_mousewheel(canvas: tk.Canvas) -> None:
    """Bind scroll only while the mouse is inside the canvas."""
    def _scroll(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))


def _ask_password(parent: tk.Widget, title: str, prompt: str):
    """Modal dialog that asks for a password and returns the typed string (or None on cancel)."""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=THEME["bg"])
    dlg.geometry(f"{ui_scale.s(360)}x{ui_scale.s(170)}")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()

    tk.Label(
        dlg, text=prompt,
        bg=THEME["bg"], fg=THEME["text"],
        font=("Segoe UI", ui_scale.scale_font(10)),
    ).pack(anchor="w", padx=16, pady=(16, 6))

    var = tk.StringVar()
    ent = tk.Entry(
        dlg, textvariable=var, show="*", bd=0,
        bg=THEME["panel2"], fg=THEME["text"],
        font=("Segoe UI", ui_scale.scale_font(10)),
    )
    ent.pack(fill="x", padx=16, ipady=ui_scale.s(8))
    ent.focus_set()

    result = {"v": None}

    def _ok():
        result["v"] = var.get()
        dlg.destroy()

    btns = tk.Frame(dlg, bg=THEME["bg"])
    btns.pack(fill="x", padx=16, pady=14)
    tk.Button(
        btns, text="Cancel",
        bg=THEME["panel2"], fg=THEME["text"],
        bd=0, padx=12, pady=8, cursor="hand2",
        command=dlg.destroy,
    ).pack(side="right")
    tk.Button(
        btns, text="Confirm",
        bg=THEME["brown"], fg="white",
        bd=0, padx=12, pady=8, cursor="hand2",
        command=_ok,
    ).pack(side="right", padx=(0, 8))

    dlg.bind("<Return>", lambda _e: _ok())
    dlg.wait_window()
    return result["v"]


# ── Main dialog ───────────────────────────────────────────────────────────────

class AccountSettingsDialog(tk.Toplevel):
    """
    Full settings dialog:
      - Profile (read-only display)
      - Security  (password change with 12-char policy)
      - Database Management  (export / import .db)     [admin]
      - User Management  (list + create + deactivate)  [admin]
      - Role Permissions  (per-role toggle grid)        [admin]
    """

    def __init__(self, parent: tk.Widget, db: Database, auth: AuthService):
        super().__init__(parent)
        self.db       = db
        self.auth     = auth
        self.user_dao = UserDAO(db)
        self.rbac_dao = RolePermissionDAO(db)

        self.title("Settings")
        self.configure(bg=THEME["bg"])
        self.geometry(f"{ui_scale.s(860)}x{ui_scale.s(600)}")
        self.minsize(700, 500)
        if isinstance(parent, tk.Toplevel):
            self.transient(parent)
        self.grab_set()

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        sf = ui_scale.scale_font
        sp = ui_scale.s

        u        = self.auth.get_current_user()
        is_admin = bool(u and u.role.upper() == ROLE_ADMIN)
        self._user     = u
        self._is_admin = is_admin

        # ── Top header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=THEME["brown_dark"])
        hdr.pack(fill="x")

        tk.Label(
            hdr, text="Settings",
            bg=THEME["brown_dark"], fg="white",
            font=("Segoe UI", sf(14), "bold"),
        ).pack(side="left", padx=18, pady=12)

        tk.Button(
            hdr, text="\u2715  Close",
            bg=THEME["brown_dark"], fg="white",
            activebackground=THEME["brown"], activeforeground="white",
            bd=0, padx=12, pady=8, cursor="hand2",
            font=("Segoe UI", sf(9)),
            command=self.destroy,
        ).pack(side="right", padx=8, pady=6)

        tk.Label(
            hdr,
            text=f"{u.username}  \u00b7  {u.role}" if u else "",
            bg=THEME["brown_dark"], fg="#c9b8a8",
            font=("Segoe UI", sf(8)),
        ).pack(side="right", padx=(0, 4))

        # ── Sidebar + content body (3 columns: sidebar | divider | content) ──────
        body = tk.Frame(self, bg=THEME["bg"])
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, minsize=sp(175))   # sidebar — fixed width
        body.columnconfigure(1, minsize=1)          # divider
        body.columnconfigure(2, weight=1)           # content — expands

        # ── Left sidebar ──────────────────────────────────────────────────────
        sidebar = tk.Frame(body, bg=THEME["beige"], width=sp(175))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        tk.Label(
            sidebar, text="NAVIGATE",
            bg=THEME["beige"], fg=THEME["muted"],
            font=("Segoe UI", sf(7), "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 6))

        # Vertical divider between sidebar and content
        tk.Frame(body, bg=THEME["border"], width=1).grid(row=0, column=1, sticky="ns")

        # ── Right scrollable canvas ───────────────────────────────────────────
        right = tk.Frame(body, bg=THEME["bg"])
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self._right_canvas = tk.Canvas(right, bg=THEME["bg"], highlightthickness=0)
        self._right_canvas.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(right, orient="vertical", command=self._right_canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._right_canvas.configure(yscrollcommand=sb.set)
        _bind_mousewheel(self._right_canvas)

        # ── Sidebar nav buttons ───────────────────────────────────────────────
        self._nav_btns_settings: dict[str, tk.Button] = {}
        self._current_section: str = ""

        sections: list[tuple[str, str, bool]] = [
            ("profile",   "Profile",             False),
            ("security",  "Security",            False),
            ("database",  "Database",            True),
            ("users",     "User Management",     True),
            ("seed",      "Demo Seed",           True),
            ("roles",     "Role Permissions",    True),
        ]

        for key, label, admin_only in sections:
            if admin_only and not is_admin:
                continue
            btn = tk.Button(
                sidebar,
                text=f"  {label}",
                anchor="w",
                bg=THEME["beige"],
                fg=THEME["text"],
                activebackground=THEME["brown"],
                activeforeground="white",
                bd=0,
                padx=sp(6),
                pady=sp(9),
                cursor="hand2",
                font=("Segoe UI", sf(9)),
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(fill="x", padx=6, pady=1)
            self._nav_btns_settings[key] = btn

        # Default section
        self._show_section("profile")

    # ── Sidebar navigation ────────────────────────────────────────────────────

    def _show_section(self, key: str) -> None:
        """Clear the right canvas, rebuild the selected section, update highlights."""
        sf = ui_scale.scale_font
        self._current_section = key

        # Rebuild inner frame inside the canvas
        self._right_canvas.delete("all")
        inner = tk.Frame(self._right_canvas, bg=THEME["bg"])
        win = self._right_canvas.create_window((0, 0), window=inner, anchor="nw")

        # Immediately fill the canvas width — prevents narrow first render after section switch
        self._right_canvas.update_idletasks()
        cw = self._right_canvas.winfo_width()
        if cw > 1:
            self._right_canvas.itemconfigure(win, width=cw)

        inner.bind(
            "<Configure>",
            lambda _e: self._right_canvas.configure(
                scrollregion=self._right_canvas.bbox("all")
            ),
            add="+",
        )
        # Replace (not accumulate) — only current win tracks canvas resizes
        self._right_canvas.bind(
            "<Configure>",
            lambda e: self._right_canvas.itemconfigure(win, width=e.width),
        )

        # Dispatch to the right builder
        u = self._user
        builders = {
            "profile":  lambda: (self._section_header(inner, "Profile"),             self._build_profile(inner, u)),
            "security": lambda: (self._section_header(inner, "Security"),            self._build_security(inner)),
            "database": lambda: (self._section_header(inner, "Database Management"), self._build_db_section(inner)),
            "users":    lambda: (self._section_header(inner, "User Management"),     self._build_user_mgmt(inner)),
            "seed":     lambda: (self._section_header(inner, "Seed Demo Sales"),      self._build_seed_section(inner)),
            "roles":    lambda: (self._section_header(inner, "Role Permissions"),     self._build_role_mgmt(inner)),
        }
        if key in builders:
            builders[key]()

        tk.Frame(inner, bg=THEME["bg"], height=ui_scale.s(24)).pack()

        # Scroll to top
        try:
            self._right_canvas.yview_moveto(0)
        except Exception:
            pass

        # Update sidebar button highlights
        for k, btn in self._nav_btns_settings.items():
            if k == key:
                btn.configure(
                    bg=THEME["brown"], fg="white",
                    font=("Segoe UI", sf(9), "bold"),
                )
            else:
                btn.configure(
                    bg=THEME["beige"], fg=THEME["text"],
                    font=("Segoe UI", sf(9)),
                )

    # ── Section helpers ───────────────────────────────────────────────────────

    def _section_header(self, parent, text: str):
        row = tk.Frame(parent, bg=THEME["bg"])
        row.pack(fill="x", padx=12, pady=(18, 6))
        tk.Label(
            row, text=text.upper(),
            bg=THEME["bg"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(8), "bold"), anchor="w",
        ).pack(side="left")
        tk.Frame(row, bg=THEME["border"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=6,
        )

    def _card(self, parent, padx=12, pady=(0, 4)) -> tk.Frame:
        card = tk.Frame(
            parent, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        card.pack(fill="x", padx=padx, pady=pady)
        return card

    def _labeled_entry(self, parent, label: str, show: str = "") -> tk.Entry:
        tk.Label(
            parent, text=label,
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=16, pady=(6, 2))
        ent = tk.Entry(
            parent, bd=0,
            bg=THEME["panel2"], fg=THEME["text"],
            insertbackground=THEME["text"],
            show=show,
            font=("Segoe UI", ui_scale.scale_font(10)),
        )
        ent.pack(fill="x", padx=16, pady=(0, 4), ipady=ui_scale.s(8))
        return ent

    def _labeled_pwd_entry(self, parent, label: str) -> tk.Entry:
        """Password entry with an inline Show/Hide toggle. Returns the Entry widget."""
        tk.Label(
            parent, text=label,
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=16, pady=(6, 2))

        row = tk.Frame(parent, bg=THEME["panel2"])
        row.pack(fill="x", padx=16, pady=(0, 4))
        row.columnconfigure(0, weight=1)

        ent = tk.Entry(
            row, bd=0,
            bg=THEME["panel2"], fg=THEME["text"],
            insertbackground=THEME["text"],
            show="*",
            font=("Segoe UI", ui_scale.scale_font(10)),
        )
        ent.grid(row=0, column=0, sticky="ew", ipady=ui_scale.s(8), padx=(6, 0))

        _state = {"visible": False}

        def _toggle():
            _state["visible"] = not _state["visible"]
            ent.configure(show="" if _state["visible"] else "*")
            toggle_btn.configure(text="Hide" if _state["visible"] else "Show")

        toggle_btn = tk.Button(
            row, text="Show",
            bg=THEME["panel2"], fg=THEME["muted"],
            activebackground=THEME["panel2"], activeforeground=THEME["text"],
            bd=0, padx=8, pady=0, cursor="hand2", relief="flat",
            font=("Segoe UI", ui_scale.scale_font(8)),
            command=_toggle,
        )
        toggle_btn.grid(row=0, column=1, padx=(2, 4), sticky="ns")

        return ent

    # ── Profile ───────────────────────────────────────────────────────────────

    def _build_profile(self, parent, u):
        card = self._card(parent)

        # ── Avatar + name row ────────────────────────────────────────────────
        info_row = tk.Frame(card, bg=THEME["panel"])
        info_row.pack(fill="x", padx=20, pady=(20, 16))

        avatar = (u.username[0].upper() if u and u.username else "?")
        tk.Label(
            info_row, text=avatar,
            bg=THEME["brown"], fg="white",
            font=("Segoe UI", ui_scale.scale_font(22), "bold"),
            width=3, pady=ui_scale.s(8),
        ).pack(side="left", padx=(0, 20))

        user_info = tk.Frame(info_row, bg=THEME["panel"])
        user_info.pack(side="left", fill="x", expand=True)
        tk.Label(
            user_info, text=u.username if u else "\u2014",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(14), "bold"), anchor="w",
        ).pack(anchor="w")
        role_text  = u.role.upper() if u else "\u2014"
        role_color = THEME["brown"] if role_text == ROLE_ADMIN else THEME["accent"]
        tk.Label(
            user_info, text=f"  {role_text}  ",
            bg=role_color, fg="white",
            font=("Segoe UI", ui_scale.scale_font(8), "bold"),
            padx=4, pady=2,
        ).pack(anchor="w", pady=(6, 0))

        # ── Details grid ─────────────────────────────────────────────────────
        tk.Frame(card, bg=THEME["border"], height=1).pack(fill="x", padx=16)

        details = tk.Frame(card, bg=THEME["panel"])
        details.pack(fill="x", padx=20, pady=(14, 18))
        details.columnconfigure(0, weight=1)
        details.columnconfigure(1, weight=1)

        def _detail(lbl_text: str, val_text: str, row: int, col: int) -> None:
            cell = tk.Frame(details, bg=THEME["panel"])
            cell.grid(row=row, column=col, sticky="w", padx=(0, 16), pady=6)
            tk.Label(
                cell, text=lbl_text,
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", ui_scale.scale_font(8)),
            ).pack(anchor="w")
            tk.Label(
                cell, text=val_text,
                bg=THEME["panel"], fg=THEME["text"],
                font=("Segoe UI", ui_scale.scale_font(10), "bold"),
            ).pack(anchor="w")

        _detail("Username",  u.username if u else "\u2014",              0, 0)
        _detail("Role",      u.role if u else "\u2014",                  0, 1)
        _detail("User ID",   f"#{u.user_id}" if u else "\u2014",         1, 0)
        _detail("Status",    "Active" if u and u.is_active else "Inactive", 1, 1)

    # ── Security ──────────────────────────────────────────────────────────────

    def _build_security(self, parent):
        sec_card = self._card(parent)

        tk.Label(
            sec_card, text="Change Password",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))

        # Policy hint
        for hint in (
            "Min 12 characters \u2022 Uppercase + lowercase \u2022 Number \u2022 Special char (!@#$%^&*...)",
            "Must not contain your username or be a known weak password.",
        ):
            tk.Label(
                sec_card, text=hint,
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", ui_scale.scale_font(8)),
            ).pack(anchor="w", padx=16, pady=(0, 1))

        tk.Frame(sec_card, bg=THEME["border"], height=1).pack(
            fill="x", padx=16, pady=(6, 4),
        )

        self.old_pwd     = self._labeled_pwd_entry(sec_card, "Current Password")
        self.new_pwd     = self._labeled_pwd_entry(sec_card, "New Password")
        self.confirm_pwd = self._labeled_pwd_entry(sec_card, "Confirm New Password")

        pwd_footer = tk.Frame(sec_card, bg=THEME["panel"])
        pwd_footer.pack(fill="x", padx=16, pady=(8, 14))
        tk.Button(
            pwd_footer, text="Update Password",
            bg=THEME["success"], fg="white",
            bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8),
            cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(10), "bold"),
            command=self._change_password,
        ).pack(side="left")

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

        u = self.auth.get_current_user()
        if not u:
            messagebox.showerror("Error", "Not logged in.")
            return

        # Verify current password first
        ok, msg = self.auth.verify_password(u.username, old)
        if not ok:
            messagebox.showerror("Incorrect Password", msg or "Current password is incorrect.")
            return

        # Change via auth service — enforces 12-char policy
        ok, msg = self.auth.change_password(u.user_id, u.username, new, enforce_policy=True)
        if not ok:
            messagebox.showerror("Password Policy Violation", msg)
            return

        messagebox.showinfo("Success", "Password changed successfully.")
        for ent in (self.old_pwd, self.new_pwd, self.confirm_pwd):
            ent.delete(0, tk.END)

    # ── Database Management ───────────────────────────────────────────────────

    def _build_db_section(self, parent):
        db_card = self._card(parent)
        tk.Label(
            db_card, text="SQLite Database Backup",
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
        btn_grid = tk.Frame(db_card, bg=THEME["panel"])
        btn_grid.pack(fill="x", padx=16, pady=(0, 16))
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)
        tk.Button(
            btn_grid, text="Export Database (.db)",
            bg=THEME["accent"], fg="white",
            bd=0, pady=ui_scale.s(9), cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(9), "bold"),
            command=self._export_db,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6), ipady=2)
        tk.Button(
            btn_grid, text="Import Database (.db)",
            bg=THEME["danger"], fg="white",
            bd=0, pady=ui_scale.s(9), cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(9), "bold"),
            command=self._import_db,
        ).grid(row=0, column=1, sticky="ew", ipady=2)

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
            messagebox.showinfo(
                "Import Complete",
                "Database replaced successfully.\n\nPlease restart the application.",
            )
            self.destroy()
        except Exception as e:
            # Reconnect so the app keeps working if the copy failed
            try:
                self.db.connect()
            except Exception:
                pass
            messagebox.showerror("Import Failed", f"Could not import database:\n{e}")

    # ── User Management ───────────────────────────────────────────────────────

    def _build_user_mgmt(self, parent):
        u     = self.auth.get_current_user()
        users = self.user_dao.list_users()

        # -- Active users list --
        users_card = self._card(parent)
        tk.Label(
            users_card, text="Active Users",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))

        hdr = tk.Frame(users_card, bg=THEME["beige"])
        hdr.pack(fill="x", padx=16)
        for col_text, w in [("Username", 0), ("Role", 110), ("Status", 90), ("Action", 90)]:
            anchor = "w" if col_text == "Username" else "center"
            expand = col_text == "Username"
            tk.Label(
                hdr, text=col_text,
                bg=THEME["beige"], fg=THEME["muted"],
                font=("Segoe UI", ui_scale.scale_font(8), "bold"),
                anchor=anchor, width=w // 8 if w else 0,
            ).pack(
                side="left",
                fill="x" if expand else None,
                expand=expand, padx=10, pady=6,
            )

        for user_row in users:
            row_bg    = THEME["panel"]
            row_frame = tk.Frame(
                users_card, bg=row_bg,
                highlightthickness=1, highlightbackground=THEME["border"],
            )
            row_frame.pack(fill="x", padx=16, pady=2)
            tk.Label(
                row_frame, text=user_row["username"],
                bg=row_bg, fg=THEME["text"],
                font=("Segoe UI", ui_scale.scale_font(10), "bold"), anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=10, pady=8)
            tk.Label(
                row_frame, text=user_row["role"],
                bg=row_bg, fg=THEME["muted"],
                font=("Segoe UI", ui_scale.scale_font(9)), width=13, anchor="center",
            ).pack(side="left", padx=4)

            active    = user_row["is_active"]
            status_bg = "#e6f9ec" if active else "#fce8e8"
            status_fg = THEME["success"] if active else THEME["danger"]
            tk.Label(
                row_frame,
                text="\u25cf Active" if active else "\u25cf Inactive",
                bg=status_bg, fg=status_fg,
                font=("Segoe UI", ui_scale.scale_font(8), "bold"),
                padx=6, pady=2,
            ).pack(side="left", padx=8)

            if active and user_row["user_id"] != (u.user_id if u else None):
                tk.Button(
                    row_frame, text="Deactivate",
                    bg=THEME["danger"], fg="white",
                    bd=0, padx=ui_scale.s(8), pady=ui_scale.s(4), cursor="hand2",
                    font=("Segoe UI", ui_scale.scale_font(8)),
                    command=lambda uid=user_row["user_id"]: self._deactivate_user(uid),
                ).pack(side="right", padx=(4, 10), pady=6)
                tk.Button(
                    row_frame, text="Delete",
                    bg=THEME["panel2"], fg=THEME["danger"],
                    bd=1, relief="solid", padx=ui_scale.s(8), pady=ui_scale.s(4), cursor="hand2",
                    font=("Segoe UI", ui_scale.scale_font(8)),
                    command=lambda uid=user_row["user_id"], uname=user_row["username"]: self._delete_user(uid, uname),
                ).pack(side="right", padx=(4, 2), pady=6)

        # -- Create new user --
        create_card = self._card(parent, pady=(8, 4))
        tk.Label(
            create_card, text="Create New User",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(
            create_card,
            text="Password policy: 12+ chars, uppercase + lowercase + number + special char.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self.create_user_ent = self._labeled_entry(create_card, "Username")
        self.create_pass_ent = self._labeled_pwd_entry(create_card, "Password")
        self.create_conf_ent = self._labeled_pwd_entry(create_card, "Confirm Password")

        tk.Label(
            create_card, text="Role",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=16, pady=(6, 2))
        self.create_role_var = tk.StringVar(value=ROLES[0])
        role_combo = ttk.Combobox(
            create_card, textvariable=self.create_role_var,
            values=ROLES, state="readonly",
            font=("Segoe UI", ui_scale.scale_font(9)),
        )
        role_combo.pack(fill="x", padx=16, pady=(0, 8))

        create_footer = tk.Frame(create_card, bg=THEME["panel"])
        create_footer.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(
            create_footer, text="Create User",
            bg=THEME["success"], fg="white",
            bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8), cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(10), "bold"),
            command=self._create_user,
        ).pack(side="left")

    def _create_user(self):
        username = self.create_user_ent.get().strip()
        password = self.create_pass_ent.get()
        confirm  = self.create_conf_ent.get()
        role     = self.create_role_var.get()

        if not username or not password:
            messagebox.showerror("Required", "Username and password are required.")
            return
        if password != confirm:
            messagebox.showerror("Mismatch", "Passwords do not match.")
            return

        # auth.create_user enforces the 12-char policy by default
        ok, msg, _ = self.auth.create_user(username, password, role)
        if not ok:
            messagebox.showerror("Create User Failed", msg or "Failed to create user.")
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

    def _delete_user(self, user_id: int, username: str):
        """Delete user only if they have zero linked transactions."""
        if self.user_dao.has_transactions(user_id):
            messagebox.showerror(
                "Cannot Delete",
                "User cannot be deleted because transactions are linked to this account. "
                "Deactivate instead.",
            )
            return
        if not messagebox.askyesno(
            "Delete User",
            f"Permanently delete user '{username}'?\n\nThis cannot be undone.",
        ):
            return
        try:
            self.user_dao.delete(user_id)
            messagebox.showinfo("Deleted", f"User '{username}' deleted.")
            self.destroy()
            AccountSettingsDialog(self.master, self.db, self.auth)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete user.\n{e}")

    # ── Seed Demo Sales ───────────────────────────────────────────────────────

    def _build_seed_section(self, parent):
        import threading
        from app.services.seed_sales_service import SeedSalesService

        seed_card = self._card(parent)
        tk.Label(
            seed_card, text="Generate Demo Sales Data",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(
            seed_card,
            text="Creates realistic synthetic completed orders for testing and demos.\n"
                 "Existing real data is NOT deleted. Runs in the background.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)), justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # Progress label — hidden until a job is running
        progress_var = tk.StringVar(value="")
        progress_lbl = tk.Label(
            seed_card,
            textvariable=progress_var,
            bg=THEME["panel"], fg=THEME["brown"],
            font=("Segoe UI", ui_scale.scale_font(9), "italic"),
        )
        progress_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        btn_grid = tk.Frame(seed_card, bg=THEME["panel"])
        btn_grid.pack(fill="x", padx=16, pady=(0, 16))
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        seed_buttons: list[tk.Button] = []

        def _set_buttons_state(state: str):
            for b in seed_buttons:
                try:
                    b.configure(state=state)
                except Exception:
                    pass

        def _seed(num_orders: int, days_back: int, label: str):
            if not messagebox.askyesno(
                "Generate Demo Sales",
                f"Generate {label} of demo sales data?\n\nExisting real data will NOT be deleted.",
            ):
                return

            _set_buttons_state("disabled")
            progress_var.set(f"Generating {label}… please wait")

            def _worker():
                # SQLite connections cannot be shared across threads.
                # Open a dedicated connection for this worker thread.
                thread_db = Database()
                try:
                    thread_db.connect()
                    svc = SeedSalesService(thread_db)

                    def _progress(done, total):
                        pct = int(done / total * 100) if total else 0
                        try:
                            self.after(0, lambda: progress_var.set(
                                f"Generating {label}… {pct}%"
                            ))
                        except Exception:
                            pass

                    result = svc.run(
                        num_orders=num_orders,
                        days_back=days_back,
                        progress_cb=_progress,
                    )
                except Exception as exc:
                    result = {"orders_created": 0, "total_sales": 0.0, "error": str(exc)}
                finally:
                    try:
                        thread_db.disconnect()
                    except Exception:
                        pass

                # All UI updates must happen on the main thread
                def _done():
                    _set_buttons_state("normal")
                    if result.get("error"):
                        progress_var.set("")
                        messagebox.showerror("Seed Error", result["error"])
                    else:
                        progress_var.set(
                            f"✓ Done — {result['orders_created']} orders created"
                        )
                        messagebox.showinfo(
                            "Done",
                            f"Created {result['orders_created']} demo orders.\n"
                            f"Total simulated sales: ₱{result['total_sales']:,.2f}\n\n"
                            "Suggestions will refresh automatically in the POS.",
                        )

                try:
                    self.after(0, _done)
                except Exception:
                    pass

            t = threading.Thread(target=_worker, daemon=True)
            t.start()

        configs = [
            ("Generate 7 Days",     100,  7,  "7 days"),
            ("Generate 30 Days",    200, 30,  "30 days"),
            ("Generate 100 Orders", 100, 30, "100 orders"),
            ("Generate 500 Orders", 500, 60, "500 orders"),
        ]

        for i, (text, num, days, lbl) in enumerate(configs):
            btn = tk.Button(
                btn_grid,
                text=text,
                bg=THEME["accent"], fg="white",
                bd=0, pady=ui_scale.s(8),
                cursor="hand2",
                font=("Segoe UI", ui_scale.scale_font(9), "bold"),
                command=lambda n=num, d=days, l=lbl: _seed(n, d, l),
            )
            btn.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 6) if i % 2 == 0 else 0, pady=(0, 6))
            seed_buttons.append(btn)

    # ── Role Permissions (RBAC) ───────────────────────────────────────────────

    def _build_role_mgmt(self, parent):
        """
        Admin-only grid of permission toggles per role.
        Changes are written immediately to the role_permissions DB table.
        """
        # Ensure every role×permission row exists (idempotent)
        try:
            self.rbac_dao.ensure_seeded()
        except Exception:
            pass

        card = self._card(parent)

        tk.Label(
            card, text="Role Permissions",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(
            card,
            text="Toggle which permissions each role has.  "
                 "Changes take effect immediately.\n"
                 "Admin always has full access and cannot be modified here.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)), justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        def _toggle(role: str, perm: str, var: tk.BooleanVar):
            """Write permission change to DB; revert on failure."""
            try:
                self.rbac_dao.set_permission(role, perm, bool(var.get()))
            except Exception as exc:
                messagebox.showerror("Save Error", f"Could not save permission:\n{exc}")
                try:
                    var.set(self.rbac_dao.has_permission(role, perm))
                except Exception:
                    pass

        for role in ROLES:
            is_admin_role = (role.upper() == ROLE_ADMIN)

            # ── Role header bar ───────────────────────────────────────────────
            role_hdr = tk.Frame(card, bg=THEME["beige"])
            role_hdr.pack(fill="x", padx=16, pady=(10, 0))

            tk.Label(
                role_hdr, text=role,
                bg=THEME["beige"], fg=THEME["text"],
                font=("Segoe UI", ui_scale.scale_font(10), "bold"),
                padx=12, pady=6,
            ).pack(side="left")

            if is_admin_role:
                tk.Label(
                    role_hdr,
                    text="(Full access \u2014 cannot be modified)",
                    bg=THEME["beige"], fg=THEME["muted"],
                    font=("Segoe UI", ui_scale.scale_font(9)),
                    padx=6,
                ).pack(side="left")

            # ── Permission checkbox grid (3 columns) ──────────────────────────
            perm_frame = tk.Frame(card, bg=THEME["panel"])
            perm_frame.pack(fill="x", padx=20, pady=(4, 4))
            perm_frame.columnconfigure(0, weight=1, uniform="permcol")
            perm_frame.columnconfigure(1, weight=1, uniform="permcol")
            perm_frame.columnconfigure(2, weight=1, uniform="permcol")

            for idx, perm in enumerate(ALL_PERMISSION_KEYS):
                label = PERMISSION_LABELS.get(perm, perm)
                try:
                    val = self.rbac_dao.has_permission(role, perm)
                except Exception:
                    val = is_admin_role  # Admin fallback = True

                var = tk.BooleanVar(value=val)
                chk = tk.Checkbutton(
                    perm_frame,
                    text=label,
                    variable=var,
                    bg=THEME["panel"], fg=THEME["text"],
                    selectcolor=THEME["panel2"],
                    activebackground=THEME["panel"],
                    font=("Segoe UI", ui_scale.scale_font(9)),
                    state="disabled" if is_admin_role else "normal",
                    command=lambda r=role, p=perm, v=var: _toggle(r, p, v),
                )
                chk.grid(row=idx // 3, column=idx % 3, sticky="w", padx=8, pady=2)

            # Thin divider between roles
            tk.Frame(card, bg=THEME["border"], height=1).pack(
                fill="x", padx=16, pady=(8, 0),
            )

        tk.Frame(card, bg=THEME["panel"], height=ui_scale.s(10)).pack()