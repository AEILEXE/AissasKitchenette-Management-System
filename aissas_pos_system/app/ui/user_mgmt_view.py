from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from app.config import THEME
from app.db.database import Database
from app.db.dao import UserDAO
from app.services.auth_service import AuthService
from app.constants import ROLES

_BG     = THEME["bg"]
_PANEL  = THEME["panel"]
_SB     = THEME["sidebar"]
_BROWN  = THEME["primary"]
_TERRA  = THEME["accent"]
_TEXT   = THEME["text"]
_MUTED  = THEME["muted"]
_BORDER = THEME["border"]
_BEIGE  = THEME["beige"]
_DANGER = THEME["danger"]
_GREEN  = THEME["success"]


class UserManagementView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=_BG)
        self.db       = db
        self.auth     = auth
        self.user_dao = UserDAO(db)
        self._build()
        self.refresh()

    # ─────────────────────────────────────────────────────────────────────
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Header bar ───────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=_SB)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Frame(hdr, bg=THEME["accent"], width=5).pack(side="left", fill="y")
        tk.Label(
            hdr, text="User Management",
            bg=_SB, fg="#FFFFFF",
            font=("Segoe UI", 14, "bold"),
            padx=16, pady=12,
        ).pack(side="left")
        tk.Label(
            hdr, text="Manage system accounts and roles",
            bg=_SB, fg="#C9B09A",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 16))

        # ── Main body (table left, form right) ───────────────────────────
        body = tk.Frame(self, bg=_BG)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=16)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=320)
        body.rowconfigure(0, weight=1)

        # ── Left: user table ─────────────────────────────────────────────
        tbl_card = tk.Frame(body, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
        tbl_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tbl_card.rowconfigure(1, weight=1)
        tbl_card.columnconfigure(0, weight=1)

        tbl_hdr = tk.Frame(tbl_card, bg=_PANEL)
        tbl_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        tk.Label(tbl_hdr, text="Accounts", bg=_PANEL, fg=_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        # Treeview
        cols = ("name", "username", "role", "status")
        self.tbl = ttk.Treeview(
            tbl_card, columns=cols, show="headings", height=18,
        )
        col_cfg = [
            ("name",     "Full Name",  160),
            ("username", "Username",   120),
            ("role",     "Role",        80),
            ("status",   "Status",      70),
        ]
        for cid, heading, w in col_cfg:
            self.tbl.heading(cid, text=heading)
            self.tbl.column(cid, width=w, minwidth=60, anchor="w")

        sb = ttk.Scrollbar(tbl_card, orient="vertical", command=self.tbl.yview)
        self.tbl.configure(yscrollcommand=sb.set)

        self.tbl.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        sb.grid(row=1, column=1, sticky="ns", pady=(0, 8))

        # Tag colours for active/inactive rows
        self.tbl.tag_configure("active",   background="#FDFAF6")
        self.tbl.tag_configure("inactive", background="#F9F0EE", foreground=_MUTED)

        # ── Right: create / edit form ─────────────────────────────────────
        form_card = tk.Frame(body, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        form_card.grid(row=0, column=1, sticky="nsew")
        form_card.columnconfigure(0, weight=1)

        tk.Label(form_card, text="Create New Account",
                 bg=_PANEL, fg=_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=20, pady=(18, 2))
        tk.Label(form_card, text="Fill in the details below",
                 bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 14))

        tk.Frame(form_card, bg=_BORDER, height=1).pack(fill="x")

        form_body = tk.Frame(form_card, bg=_PANEL)
        form_body.pack(fill="both", expand=True, padx=20, pady=16)
        form_body.columnconfigure(0, weight=1)

        def _field(parent, label_text, row, show=""):
            tk.Label(parent, text=label_text, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 8, "bold")).grid(
                row=row * 2, column=0, sticky="w", pady=(10, 2))
            var = tk.StringVar()
            ent = tk.Entry(parent, textvariable=var,
                           font=("Segoe UI", 10),
                           bg=_BEIGE, fg=_TEXT, bd=0,
                           insertbackground=_TEXT,
                           show=show)
            ent.grid(row=row * 2 + 1, column=0, sticky="ew", ipady=8,
                     padx=(0, 0))
            return var, ent

        self.var_fullname, self.ent_fullname = _field(form_body, "Full Name  (required)", 0)
        self.var_user,     self.ent_user     = _field(form_body, "Username",  1)
        self.var_pass,     self.ent_pass     = _field(form_body, "Password",  2, show="•")

        # Role selector
        tk.Label(form_body, text="Role", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 8, "bold")).grid(
            row=6, column=0, sticky="w", pady=(10, 2))

        self.var_role = tk.StringVar(value=ROLES[-1])
        role_frame = tk.Frame(form_body, bg=_PANEL)
        role_frame.grid(row=7, column=0, sticky="ew")
        role_frame.columnconfigure(tuple(range(len(ROLES))), weight=1)

        self._role_btns: dict[str, tk.Button] = {}
        for i, r in enumerate(ROLES):
            btn = tk.Button(
                role_frame, text=r.capitalize(),
                bg=_BEIGE, fg=_TEXT, bd=0,
                padx=8, pady=6, cursor="hand2",
                font=("Segoe UI", 9),
                command=lambda rv=r: self._select_role(rv),
            )
            btn.grid(row=0, column=i, sticky="ew", padx=(0, 4) if i < len(ROLES) - 1 else 0)
            self._role_btns[r] = btn
        self._select_role(ROLES[-1])

        # Policy hint
        tk.Label(
            form_body,
            text="Password: min 12 chars, upper + lower + number + special",
            bg=_PANEL, fg=_MUTED,
            font=("Segoe UI", 7),
            wraplength=260, justify="left",
        ).grid(row=8, column=0, sticky="w", pady=(10, 0))

        # Create button
        tk.Button(
            form_body,
            text="Create Account",
            command=self.create_user,
            bg=_BROWN, fg="white",
            activebackground=THEME["primary_dark"], activeforeground="white",
            bd=0, padx=16, pady=10, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=9, column=0, sticky="ew", pady=(16, 4))

        tk.Frame(form_card, bg=_BORDER, height=1).pack(fill="x")

        # Actions for selected user
        act_label = tk.Label(form_card, text="Selected Account Actions",
                             bg=_PANEL, fg=_TEXT,
                             font=("Segoe UI", 10, "bold"))
        act_label.pack(anchor="w", padx=20, pady=(14, 8))

        act_row = tk.Frame(form_card, bg=_PANEL)
        act_row.pack(fill="x", padx=20, pady=(0, 14))

        tk.Button(
            act_row, text="Activate",
            command=lambda: self._set_active(1),
            bg=_GREEN, fg="white",
            activebackground="#3A6347", activeforeground="white",
            bd=0, padx=12, pady=8, cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            act_row, text="Deactivate",
            command=lambda: self._set_active(0),
            bg=_DANGER, fg="white",
            activebackground="#8E3A35", activeforeground="white",
            bd=0, padx=12, pady=8, cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            act_row, text="Edit Name",
            command=self._edit_name,
            bg=THEME["warning"], fg="white",
            activebackground=THEME["accent_dark"], activeforeground="white",
            bd=0, padx=12, pady=8, cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

    def _select_role(self, role: str) -> None:
        self.var_role.set(role)
        for r, btn in self._role_btns.items():
            if r == role:
                btn.configure(bg=_BROWN, fg="white")
            else:
                btn.configure(bg=_BEIGE, fg=_TEXT)

    # ─────────────────────────────────────────────────────────────────────
    def refresh(self):
        self.tbl.delete(*self.tbl.get_children())
        for r in self.user_dao.list_users():
            uid      = r["user_id"]
            active   = bool(r["is_active"])
            tag      = "active" if active else "inactive"
            status   = "Active" if active else "Inactive"
            fullname = r["full_name"] or ""
            self.tbl.insert(
                "", tk.END, iid=str(uid), tags=(tag,),
                values=(fullname, r["username"], r["role"].capitalize(), status),
            )

    def create_user(self):
        fullname = self.var_fullname.get().strip()
        username = self.var_user.get().strip()
        password = self.var_pass.get()
        role     = self.var_role.get()

        if not fullname:
            messagebox.showerror("Validation", "Full Name is required.")
            self.ent_fullname.focus_set()
            return

        if not username:
            messagebox.showerror("Validation", "Username is required.")
            return

        ok, msg, _ = self.auth.create_user(
            username, password, role, full_name=fullname
        )
        if not ok:
            messagebox.showerror("Create Account", msg)
            return

        messagebox.showinfo("Create Account", msg)
        self.ent_fullname.delete(0, tk.END)
        self.ent_user.delete(0, tk.END)
        self.ent_pass.delete(0, tk.END)
        self.refresh()

    def _get_selected_uid(self) -> int | None:
        sel = self.tbl.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an account from the list first.")
            return None
        return int(sel[0])

    def _set_active(self, active: int) -> None:
        uid = self._get_selected_uid()
        if uid is None:
            return
        self.user_dao.set_active(uid, active)
        self.refresh()

    def _edit_name(self) -> None:
        uid = self._get_selected_uid()
        if uid is None:
            return
        user = self.user_dao.get_by_id(uid)
        if not user:
            return

        dlg = _EditNameDialog(self, current_name=user.full_name, username=user.username)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.user_dao.update_full_name(uid, dlg.result)
            self.refresh()


# ── Edit Name Dialog ──────────────────────────────────────────────────────────

class _EditNameDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, current_name: str, username: str):
        super().__init__(parent)
        self.title("Edit Display Name")
        self.configure(bg=_PANEL)
        self.resizable(False, False)
        self.grab_set()
        self.result: str | None = None

        tk.Frame(self, bg=_SB, height=44).pack(fill="x")
        hdr = tk.Frame(self, bg=_SB)

        # Rebuild with proper label
        for w in self.winfo_children():
            w.destroy()

        hdr = tk.Frame(self, bg=_SB)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"Edit Name — {username}",
                 bg=_SB, fg="#FFFFFF",
                 font=("Segoe UI", 11, "bold"),
                 padx=18, pady=10).pack(side="left")

        body = tk.Frame(self, bg=_PANEL)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(body, text="FULL NAME", bg=_PANEL, fg=_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")

        self.var = tk.StringVar(value=current_name)
        ent = tk.Entry(body, textvariable=self.var,
                       font=("Segoe UI", 12), bg=_BEIGE, fg=_TEXT, bd=0,
                       insertbackground=_TEXT)
        ent.pack(fill="x", ipady=10, pady=(4, 0))
        ent.focus_set()
        ent.select_range(0, "end")

        btn_row = tk.Frame(body, bg=_PANEL)
        btn_row.pack(fill="x", pady=(18, 0))

        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=_BEIGE, fg=_TEXT, bd=0, padx=14, pady=8,
                  cursor="hand2", font=("Segoe UI", 9)).pack(side="left")

        tk.Button(btn_row, text="Save", command=self._save,
                  bg=_BROWN, fg="white", bd=0, padx=14, pady=8,
                  cursor="hand2",
                  font=("Segoe UI", 9, "bold")).pack(side="right")

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        self.geometry(f"360x{self.winfo_height()}")
        self._center(parent)

    def _center(self, parent: tk.Widget) -> None:
        try:
            x = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _save(self) -> None:
        self.result = self.var.get().strip()
        self.destroy()
