from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox

from app.db.database import Database
from app.db.dao import UserDAO
from app.services.auth_service import AuthService
from app.constants import ROLES


class UserManagementView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg="#f2f2f2")
        self.db = db
        self.auth = auth
        self.user_dao = UserDAO(db)

        self._build()
        self.refresh()

    def _build(self):
        tk.Label(self, text="User Management", font=("Segoe UI", 14, "bold"), bg="#f2f2f2").pack(anchor=tk.W, padx=10, pady=10)

        self.tbl = ttk.Treeview(self, columns=("role", "active"), show="headings", height=16)
        self.tbl.heading("role", text="Role")
        self.tbl.heading("active", text="Active")
        self.tbl.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        form = tk.Frame(self, bg="#f2f2f2")
        form.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(form, text="Username:", bg="#f2f2f2").pack(side=tk.LEFT)
        self.ent_user = tk.Entry(form, width=18)
        self.ent_user.pack(side=tk.LEFT, padx=5)

        tk.Label(form, text="Password:", bg="#f2f2f2").pack(side=tk.LEFT)
        self.ent_pass = tk.Entry(form, width=18, show="*")
        self.ent_pass.pack(side=tk.LEFT, padx=5)

        tk.Label(form, text="Role:", bg="#f2f2f2").pack(side=tk.LEFT)
        self.var_role = tk.StringVar(value=ROLES[2])
        tk.OptionMenu(form, self.var_role, *ROLES).pack(side=tk.LEFT, padx=5)

        tk.Button(form, text="Create", command=self.create_user).pack(side=tk.LEFT, padx=5)
        tk.Button(form, text="Deactivate", command=self.deactivate_user).pack(side=tk.RIGHT)

    def refresh(self):
        self.tbl.delete(*self.tbl.get_children())
        for r in self.user_dao.list_users():
            uid = r["user_id"]
            self.tbl.insert("", tk.END, iid=str(uid), values=(r["role"], r["is_active"]), text=r["username"])
        self.tbl.configure(show="tree headings")

    def create_user(self):
        u = self.ent_user.get().strip()
        p = self.ent_pass.get()
        role = self.var_role.get()

        ok, msg, _ = self.auth.create_user(u, p, role)
        if not ok:
            messagebox.showerror("Create user", msg)
            return
        messagebox.showinfo("Create user", msg)
        self.ent_user.delete(0, tk.END)
        self.ent_pass.delete(0, tk.END)
        self.refresh()

    def deactivate_user(self):
        sel = self.tbl.selection()
        if not sel:
            return
        uid = int(sel[0])
        self.user_dao.set_active(uid, 0)
        self.refresh()
