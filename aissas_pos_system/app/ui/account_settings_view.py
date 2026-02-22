from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from app.config import THEME
from app.db.database import Database
from app.db.dao import UserDAO
from app.services.auth_service import AuthService
from app.constants import ROLES


class AccountSettingsDialog(tk.Toplevel):
    """Account settings for current user (change password) + admin-only user management."""
    
    def __init__(self, parent: tk.Widget, db: Database, auth: AuthService):
        super().__init__(parent)
        self.db = db
        self.auth = auth
        self.user_dao = UserDAO(db)
        
        self.title("Account Settings")
        self.configure(bg=THEME["bg"])
        self.geometry("600x500")
        if isinstance(parent, tk.Toplevel):
            self.transient(parent)
        self.grab_set()
        
        self._build()
    
    def _build(self):
        tk.Label(self, text="Account Settings", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 16, "bold")).pack(
            anchor="w", padx=18, pady=(14, 8)
        )
        
        # Tabs: Account + Admin Only
        tab_frame = tk.Frame(self, bg=THEME["bg"])
        tab_frame.pack(fill="x", padx=18, pady=(0, 12))
        
        self.tab_account_btn = tk.Button(
            tab_frame, text="My Account", command=self._show_account_tab,
            bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, cursor="hand2"
        )
        self.tab_account_btn.pack(side="left", padx=(0, 6))
        
        u = self.auth.get_current_user()
        is_admin = u and u.role.upper() == "ADMIN"
        
        if is_admin:
            self.tab_admin_btn = tk.Button(
                tab_frame, text="User Management (Admin)", command=self._show_admin_tab,
                bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, cursor="hand2"
            )
            self.tab_admin_btn.pack(side="left")
        else:
            self.tab_admin_btn = None
        
        # Content frame
        self.content = tk.Frame(self, bg=THEME["bg"])
        self.content.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        
        self._show_account_tab()
    
    def _clear_content(self):
        """Clear content frame."""
        for w in self.content.winfo_children():
            w.destroy()
    
    def _show_account_tab(self):
        """Show account tab with change password option."""
        self._clear_content()
        self.tab_account_btn.config(bg=THEME["primary_light"], fg=THEME["text_on_primary"])
        if self.tab_admin_btn:
            self.tab_admin_btn.config(bg=THEME["panel2"], fg=THEME["text"])
        
        u = self.auth.get_current_user()
        
        box = tk.Frame(self.content, bg=THEME["panel2"])
        box.pack(fill="x", pady=(0, 12))
        
        # Current user info
        tk.Label(box, text="Current User", bg=THEME["panel2"], fg=THEME["muted"], font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=14, pady=(12, 6)
        )
        
        tk.Label(box, text=f"Username: {u.username if u else '—'}", bg=THEME["panel2"], fg=THEME["text"]).pack(
            anchor="w", padx=14, pady=2
        )
        tk.Label(box, text=f"Role: {u.role.upper() if u else '—'}", bg=THEME["panel2"], fg=THEME["text"]).pack(
            anchor="w", padx=14, pady=(2, 12)
        )
        
        # Change password section
        pwd_box = tk.Frame(self.content, bg=THEME["panel2"])
        pwd_box.pack(fill="x")
        
        tk.Label(pwd_box, text="Change Password", bg=THEME["panel2"], fg=THEME["muted"], font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=14, pady=(12, 8)
        )
        
        tk.Label(pwd_box, text="Current Password:", bg=THEME["panel2"], fg=THEME["text"]).pack(
            anchor="w", padx=14, pady=(0, 2)
        )
        self.old_pwd = tk.Entry(pwd_box, bd=0, bg="white", fg=THEME["text"], show="*")
        self.old_pwd.pack(fill="x", padx=14, pady=(0, 8), ipady=8)
        
        tk.Label(pwd_box, text="New Password:", bg=THEME["panel2"], fg=THEME["text"]).pack(
            anchor="w", padx=14, pady=(0, 2)
        )
        self.new_pwd = tk.Entry(pwd_box, bd=0, bg="white", fg=THEME["text"], show="*")
        self.new_pwd.pack(fill="x", padx=14, pady=(0, 8), ipady=8)
        
        tk.Label(pwd_box, text="Confirm Password:", bg=THEME["panel2"], fg=THEME["text"]).pack(
            anchor="w", padx=14, pady=(0, 2)
        )
        self.confirm_pwd = tk.Entry(pwd_box, bd=0, bg="white", fg=THEME["text"], show="*")
        self.confirm_pwd.pack(fill="x", padx=14, pady=(0, 12), ipady=8)
        
        btn_frame = tk.Frame(pwd_box, bg=THEME["panel2"])
        btn_frame.pack(fill="x", padx=14, pady=(0, 12))
        
        tk.Button(
            btn_frame, text="Change Password", command=self._change_password,
            bg=THEME["success"], fg="white", bd=0, padx=12, pady=8, cursor="hand2"
        ).pack(side="left")
    
    def _show_admin_tab(self):
        """Show admin user management tab (only for admins)."""
        u = self.auth.get_current_user()
        if not u or u.role.upper() != "ADMIN":
            messagebox.showerror("Access Denied", "Only admins can access user management.")
            return
        
        self._clear_content()
        if self.tab_admin_btn:
            self.tab_admin_btn.config(bg=THEME["primary_light"], fg=THEME["text_on_primary"])
        self.tab_account_btn.config(bg=THEME["panel2"], fg=THEME["text"])
        
        # User list
        tk.Label(self.content, text="Users", bg=THEME["bg"], fg=THEME["muted"], font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 6)
        )
        
        list_box = tk.Frame(self.content, bg=THEME["panel2"])
        list_box.pack(fill="both", expand=True, pady=(0, 10))
        
        users = self.user_dao.list_users()
        
        for user_row in users:
            user_frame = tk.Frame(list_box, bg=THEME["panel"])
            user_frame.pack(fill="x", padx=8, pady=4)
            
            tk.Label(user_frame, text=user_row["username"], bg=THEME["panel"], fg=THEME["text"],
                     font=("Segoe UI", 10, "bold"), width=20, anchor="w").pack(side="left", padx=8, pady=6)
            
            tk.Label(user_frame, text=user_row["role"], bg=THEME["panel"], fg=THEME["muted"], width=12, anchor="w").pack(side="left", padx=4)
            
            active_text = "Active" if user_row["is_active"] else "Inactive"
            active_color = THEME["success"] if user_row["is_active"] else THEME["danger"]
            tk.Label(user_frame, text=active_text, bg=THEME["panel"], fg=active_color, width=12, anchor="w").pack(side="left", padx=4)
            
            if user_row["is_active"] and user_row["user_id"] != (u.user_id if u else None):
                tk.Button(user_frame, text="Deactivate", bg=THEME["danger"], fg="white", bd=0,
                         padx=8, pady=4, cursor="hand2",
                         command=lambda uid=user_row["user_id"]: self._deactivate_user(uid)).pack(side="right", padx=(4, 8), pady=6)
        
        # Create user section
        create_box = tk.Frame(self.content, bg=THEME["panel2"])
        create_box.pack(fill="x", pady=(0, 10))
        
        tk.Label(create_box, text="Create New User", bg=THEME["panel2"], fg=THEME["muted"], font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=14, pady=(12, 8)
        )
        
        tk.Label(create_box, text="Username:", bg=THEME["panel2"], fg=THEME["text"]).pack(anchor="w", padx=14, pady=(0, 2))
        self.create_user_ent = tk.Entry(create_box, bd=0, bg="white", fg=THEME["text"])
        self.create_user_ent.pack(fill="x", padx=14, pady=(0, 8), ipady=8)
        
        tk.Label(create_box, text="Password:", bg=THEME["panel2"], fg=THEME["text"]).pack(anchor="w", padx=14, pady=(0, 2))
        self.create_pass_ent = tk.Entry(create_box, bd=0, bg="white", fg=THEME["text"], show="*")
        self.create_pass_ent.pack(fill="x", padx=14, pady=(0, 8), ipady=8)
        
        tk.Label(create_box, text="Role:", bg=THEME["panel2"], fg=THEME["text"]).pack(anchor="w", padx=14, pady=(0, 2))
        self.create_role_var = tk.StringVar(value=ROLES[0])
        role_combo = tk.OptionMenu(create_box, self.create_role_var, *ROLES)
        role_combo.pack(fill="x", padx=14, pady=(0, 12))
        
        btn_frame = tk.Frame(create_box, bg=THEME["panel2"])
        btn_frame.pack(fill="x", padx=14, pady=(0, 12))
        
        tk.Button(btn_frame, text="Create User", bg=THEME["success"], fg="white", bd=0, padx=12, pady=8,
                 cursor="hand2", command=self._create_user).pack(side="left")
    
    def _change_password(self):
        """Change current user password."""
        old = self.old_pwd.get()
        new = self.new_pwd.get()
        confirm = self.confirm_pwd.get()
        
        if not old or not new or not confirm:
            messagebox.showerror("Required", "All fields are required.")
            return
        
        if new != confirm:
            messagebox.showerror("Mismatch", "New passwords don't match.")
            return
        
        if len(new) < 4:
            messagebox.showerror("Too Short", "Password must be at least 4 characters.")
            return
        
        u = self.auth.get_current_user()
        if not u:
            messagebox.showerror("Error", "Not logged in.")
            return
        
        # Verify old password
        ok, msg = self.auth.verify_password(u.username, old)
        if not ok:
            messagebox.showerror("Incorrect", msg or "Old password is incorrect.")
            return
        
        # Update password
        try:
            self.user_dao.update_password(u.user_id, new)
            messagebox.showinfo("Success", "Password changed successfully.")
            self.old_pwd.delete(0, tk.END)
            self.new_pwd.delete(0, tk.END)
            self.confirm_pwd.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to change password:\n{e}")
    
    def _create_user(self):
        """Create new user (admin only)."""
        username = self.create_user_ent.get().strip()
        password = self.create_pass_ent.get()
        role = self.create_role_var.get()
        
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
        self.create_user_ent.delete(0, tk.END)
        self.create_pass_ent.delete(0, tk.END)
        self._show_admin_tab()  # Refresh list
    
    def _deactivate_user(self, user_id: int):
        """Deactivate a user."""
        if messagebox.askyesno("Confirm", "Deactivate this user?"):
            try:
                self.user_dao.set_active(user_id, 0)
                messagebox.showinfo("Success", "User deactivated.")
                self._show_admin_tab()  # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"Failed to deactivate user.\n{e}")
