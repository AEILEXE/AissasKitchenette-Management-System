"""
app/ui/account_settings_view.py
─────────────────────────────────
Part 7 — Settings page redesign (card-style, professional admin panel).
Part 8 — Developer Tools section with Seed Sales tool.

Sections:
  Profile         — avatar + current user info
  Security        — change password
  User Management — admin-only: view/deactivate users, create new user
  Developer Tools — visible when DEBUG=True OR role=ADMIN
                    contains the Seed Sales generator
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app.config import THEME, DEBUG
from app.db.database import Database
from app.db.dao import UserDAO
from app.services.auth_service import AuthService
from app.constants import ROLES
from app.ui import ui_scale


# ─────────────────────────────────────────────────────────────────────────────
# Main dialog
# ─────────────────────────────────────────────────────────────────────────────

class AccountSettingsDialog(tk.Toplevel):
    """Settings dialog: Profile, Security, User Management, Developer Tools."""

    def __init__(self, parent: tk.Widget, db: Database, auth: AuthService):
        super().__init__(parent)
        self.db       = db
        self.auth     = auth
        self.user_dao = UserDAO(db)

        self.title("Settings")
        self.configure(bg=THEME["bg"])
        self.geometry(f"{ui_scale.s(680)}x{ui_scale.s(620)}")
        self.minsize(580, 500)
        if isinstance(parent, tk.Toplevel):
            self.transient(parent)
        self.grab_set()

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        u        = self.auth.get_current_user()
        is_admin = u and u.role.upper() == "ADMIN"
        show_dev = DEBUG or is_admin

        # Scrollable canvas shell
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
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        # ── Page title row ────────────────────────────────────────────────────
        title_row = tk.Frame(inner, bg=THEME["bg"])
        title_row.pack(fill="x", padx=24, pady=(18, 2))

        tk.Label(
            title_row, text="Settings",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(20), "bold"),
        ).pack(side="left")

        tk.Button(
            title_row, text="✕  Close",
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

        # ── Profile section ───────────────────────────────────────────────────
        self._section_header(inner, "Profile")
        profile_card = self._card(inner)

        info_row = tk.Frame(profile_card, bg=THEME["panel"])
        info_row.pack(fill="x", padx=16, pady=(14, 14))

        # Avatar circle (first letter of username)
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
            user_info,
            text=u.username if u else "—",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(13), "bold"),
            anchor="w",
        ).pack(anchor="w")

        role_text = u.role.upper() if u else "—"
        role_color = THEME["brown"] if role_text == "ADMIN" else THEME["accent"]
        tk.Label(
            user_info, text=f"  {role_text}  ",
            bg=role_color, fg="white",
            font=("Segoe UI", ui_scale.scale_font(8), "bold"),
            padx=4, pady=2,
        ).pack(anchor="w", pady=(4, 0))

        # ── Security section ──────────────────────────────────────────────────
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
            activebackground=THEME["brown_dark"], activeforeground="white",
            bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8),
            cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(10), "bold"),
            command=self._change_password,
        ).pack(side="left")

        # ── User Management (admin only) ──────────────────────────────────────
        if is_admin:
            self._section_header(inner, "User Management")
            self._build_user_mgmt(inner)

        # ── Developer Tools ───────────────────────────────────────────────────
        if show_dev:
            self._section_header(inner, "Developer Tools")
            self._build_dev_tools(inner)

        # Bottom spacer
        tk.Frame(inner, bg=THEME["bg"], height=ui_scale.s(24)).pack()

    # ── Section builder helpers ────────────────────────────────────────────────

    def _section_header(self, parent: tk.Widget, text: str) -> None:
        row = tk.Frame(parent, bg=THEME["bg"])
        row.pack(fill="x", padx=24, pady=(18, 6))

        tk.Label(
            row, text=text.upper(),
            bg=THEME["bg"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(8), "bold"),
            anchor="w",
        ).pack(side="left")

        sep = tk.Frame(row, bg=THEME["border"], height=1)
        sep.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

    def _card(self, parent: tk.Widget, padx: int = 24, pady=(0, 4)) -> tk.Frame:
        card = tk.Frame(
            parent, bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        card.pack(fill="x", padx=padx, pady=pady)
        return card

    def _labeled_entry(
        self, parent: tk.Widget, label: str, show: str = ""
    ) -> tk.Entry:
        tk.Label(
            parent, text=label,
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=16, pady=(6, 2))

        ent = tk.Entry(
            parent,
            bd=0, bg=THEME["panel2"], fg=THEME["text"],
            insertbackground=THEME["text"],
            show=show,
            font=("Segoe UI", ui_scale.scale_font(10)),
        )
        ent.pack(fill="x", padx=16, pady=(0, 4), ipady=ui_scale.s(8))
        return ent

    # ── User Management ────────────────────────────────────────────────────────

    def _build_user_mgmt(self, parent: tk.Widget) -> None:
        u     = self.auth.get_current_user()
        users = self.user_dao.list_users()

        users_card = self._card(parent)

        tk.Label(
            users_card, text="Active Users",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))

        # Table header
        hdr = tk.Frame(users_card, bg=THEME["beige"])
        hdr.pack(fill="x", padx=16)
        hdr.columnconfigure(0, weight=1)
        for col_text, w in [
            ("Username", 0), ("Role", 110), ("Status", 90), ("Action", 90),
        ]:
            anchor = "w" if col_text == "Username" else "center"
            expand = col_text == "Username"
            tk.Label(
                hdr, text=col_text,
                bg=THEME["beige"], fg=THEME["muted"],
                font=("Segoe UI", ui_scale.scale_font(8), "bold"),
                anchor=anchor,
                width=w // 8 if w else 0,
            ).pack(
                side="left",
                fill="x" if expand else None,
                expand=expand,
                padx=10, pady=6,
            )

        # User rows
        for user_row in users:
            row_bg = THEME["panel"]
            row_frame = tk.Frame(
                users_card, bg=row_bg,
                highlightthickness=1,
                highlightbackground=THEME["border"],
            )
            row_frame.pack(fill="x", padx=16, pady=2)

            tk.Label(
                row_frame, text=user_row["username"],
                bg=row_bg, fg=THEME["text"],
                font=("Segoe UI", ui_scale.scale_font(10), "bold"),
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=10, pady=8)

            tk.Label(
                row_frame, text=user_row["role"],
                bg=row_bg, fg=THEME["muted"],
                font=("Segoe UI", ui_scale.scale_font(9)),
                width=13, anchor="center",
            ).pack(side="left", padx=4)

            active     = user_row["is_active"]
            status_bg  = "#e6f9ec" if active else "#fce8e8"
            status_fg  = THEME["success"] if active else THEME["danger"]
            tk.Label(
                row_frame,
                text="● Active" if active else "● Inactive",
                bg=status_bg, fg=status_fg,
                font=("Segoe UI", ui_scale.scale_font(8), "bold"),
                padx=6, pady=2,
            ).pack(side="left", padx=8)

            if active and user_row["user_id"] != (u.user_id if u else None):
                tk.Button(
                    row_frame, text="Deactivate",
                    bg=THEME["danger"], fg="white",
                    bd=0, padx=ui_scale.s(8), pady=ui_scale.s(4),
                    cursor="hand2",
                    font=("Segoe UI", ui_scale.scale_font(8)),
                    command=lambda uid=user_row["user_id"]: self._deactivate_user(uid),
                ).pack(side="right", padx=(4, 10), pady=6)

        # Create user sub-card
        create_card = self._card(parent, pady=(8, 4))

        tk.Label(
            create_card, text="Create New User",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        self.create_user_ent = self._labeled_entry(create_card, "Username")
        self.create_pass_ent = self._labeled_entry(create_card, "Password", show="*")

        tk.Label(
            create_card, text="Role",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(anchor="w", padx=16, pady=(6, 2))

        self.create_role_var = tk.StringVar(value=ROLES[0])
        role_combo = ttk.Combobox(
            create_card,
            textvariable=self.create_role_var,
            values=ROLES,
            state="readonly",
            font=("Segoe UI", ui_scale.scale_font(9)),
        )
        role_combo.pack(fill="x", padx=16, pady=(0, 8))

        create_footer = tk.Frame(create_card, bg=THEME["panel"])
        create_footer.pack(fill="x", padx=16, pady=(0, 14))

        tk.Button(
            create_footer, text="Create User",
            bg=THEME["success"], fg="white",
            bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8),
            cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(10), "bold"),
            command=self._create_user,
        ).pack(side="left")

    # ── Developer Tools ────────────────────────────────────────────────────────

    def _build_dev_tools(self, parent: tk.Widget) -> None:
        dev_card = self._card(parent)

        # Dark header strip
        dev_hdr = tk.Frame(dev_card, bg="#1e1b4b")
        dev_hdr.pack(fill="x")
        tk.Label(
            dev_hdr,
            text="⚙  Developer / Debug Features",
            bg="#1e1b4b", fg="#a5b4fc",
            font=("Segoe UI", ui_scale.scale_font(10), "bold"),
        ).pack(anchor="w", padx=14, pady=10)

        tk.Label(
            dev_card,
            text="These tools are only visible in DEBUG mode or for ADMIN users.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9), "italic"),
        ).pack(anchor="w", padx=16, pady=(10, 6))

        # ── Seed Sales row ────────────────────────────────────────────────────
        seed_row = tk.Frame(dev_card, bg=THEME["panel"])
        seed_row.pack(fill="x", padx=16, pady=(4, 14))

        seed_info = tk.Frame(seed_row, bg=THEME["panel"])
        seed_info.pack(side="left", fill="x", expand=True)

        tk.Label(
            seed_info, text="Seed Sales Data",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(11), "bold"),
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            seed_info,
            text="Generate synthetic orders to train the ML pair-frequency recommender.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        tk.Button(
            seed_row, text="Open Seed Tool →",
            bg="#4f46e5", fg="white",
            activebackground="#3730a3", activeforeground="white",
            bd=0, padx=ui_scale.s(14), pady=ui_scale.s(8),
            cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(9), "bold"),
            command=lambda: SeedSalesDialog(self, self.db),
        ).pack(side="right", padx=(12, 0))

    # ── Actions ────────────────────────────────────────────────────────────────

    def _change_password(self):
        old     = self.old_pwd.get()
        new     = self.new_pwd.get()
        confirm = self.confirm_pwd.get()

        if not old or not new or not confirm:
            messagebox.showerror("Required", "All password fields are required.")
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
        # Refresh the dialog
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


# ─────────────────────────────────────────────────────────────────────────────
# Seed Sales dialog (Part 8)
# ─────────────────────────────────────────────────────────────────────────────

class SeedSalesDialog(tk.Toplevel):
    """DEV-only: Configure and run synthetic sales data generation for ML testing."""

    def __init__(self, parent: tk.Widget, db: Database):
        super().__init__(parent)
        self.db = db

        self.title("Seed Sales Data")
        self.configure(bg=THEME["bg"])
        self.geometry(f"{ui_scale.s(460)}x{ui_scale.s(510)}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.var_num_orders  = tk.IntVar(value=200)
        self.var_items_min   = tk.IntVar(value=2)
        self.var_items_max   = tk.IntVar(value=5)
        self.var_days_back   = tk.IntVar(value=30)
        self.var_weighted    = tk.BooleanVar(value=True)
        self.var_reduce_stock = tk.BooleanVar(value=False)

        self._build()

    def _build(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        # ── Dark header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg="#1e1b4b")
        hdr.pack(fill="x")

        tk.Label(
            hdr, text="⚙  Seed Sales Data",
            bg="#1e1b4b", fg="#a5b4fc",
            font=("Segoe UI", f(14), "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))

        tk.Label(
            hdr,
            text="Generate synthetic orders to train the ML recommender.",
            bg="#1e1b4b", fg="#6b7280",
            font=("Segoe UI", f(9)),
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # ── Body ─────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=14)

        def field_row(label_text: str, widget_factory):
            r = tk.Frame(body, bg=THEME["bg"])
            r.pack(fill="x", pady=(0, sp(10)))
            tk.Label(
                r, text=label_text,
                bg=THEME["bg"], fg=THEME["muted"],
                font=("Segoe UI", f(9)),
                anchor="w", width=26,
            ).pack(side="left")
            widget_factory(r)

        def spinbox(parent, var, from_, to_):
            sb = tk.Spinbox(
                parent, from_=from_, to=to_,
                textvariable=var, width=8,
                bd=1, font=("Segoe UI", f(9)),
            )
            sb.pack(side="left")

        field_row("Number of Orders:",
                  lambda p: spinbox(p, self.var_num_orders, 1, 5000))
        field_row("Min Items per Order:",
                  lambda p: spinbox(p, self.var_items_min, 1, 10))
        field_row("Max Items per Order:",
                  lambda p: spinbox(p, self.var_items_max, 1, 10))
        field_row("Date Range (last N days):",
                  lambda p: spinbox(p, self.var_days_back, 1, 365))

        tk.Checkbutton(
            body,
            text="Weighted Combos  (coffee+pastry, rice+drink, etc.)  — Recommended",
            variable=self.var_weighted,
            bg=THEME["bg"], fg=THEME["text"],
            activebackground=THEME["bg"],
            font=("Segoe UI", f(9)),
        ).pack(anchor="w", pady=(sp(4), sp(6)))

        tk.Checkbutton(
            body,
            text="Reduce Stock After Seeding",
            variable=self.var_reduce_stock,
            bg=THEME["bg"], fg=THEME["text"],
            activebackground=THEME["bg"],
            font=("Segoe UI", f(9)),
        ).pack(anchor="w", pady=(0, sp(12)))

        # Warning
        warn_card = tk.Frame(
            body, bg="#fef3c7",
            highlightthickness=1, highlightbackground="#fcd34d",
        )
        warn_card.pack(fill="x", pady=(0, sp(10)))
        tk.Label(
            warn_card,
            text="⚠  This writes synthetic records to the production database.\n"
                 "    TestCustomer### orders can be identified and filtered out.",
            bg="#fef3c7", fg="#92400e",
            font=("Segoe UI", f(9)),
            justify="left", anchor="w",
        ).pack(anchor="w", padx=10, pady=8)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=THEME["bg"])
        footer.pack(fill="x", padx=20, pady=(0, sp(16)))

        tk.Button(
            footer, text="Cancel",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=sp(14), pady=sp(8), cursor="hand2",
            font=("Segoe UI", f(9)),
            command=self.destroy,
        ).pack(side="right")

        tk.Button(
            footer, text="Generate Orders",
            bg="#4f46e5", fg="white",
            activebackground="#3730a3", activeforeground="white",
            bd=0, padx=sp(14), pady=sp(8), cursor="hand2",
            font=("Segoe UI", f(10), "bold"),
            command=self._run,
        ).pack(side="right", padx=(0, sp(8)))

    # ── Run ───────────────────────────────────────────────────────────────────

    def _run(self):
        num          = self.var_num_orders.get()
        items_min    = self.var_items_min.get()
        items_max    = self.var_items_max.get()
        days         = self.var_days_back.get()
        weighted     = self.var_weighted.get()
        reduce_stock = self.var_reduce_stock.get()

        if items_min > items_max:
            messagebox.showerror("Invalid", "Min items cannot exceed max items.")
            return

        confirm_msg = (
            f"Generate {num} synthetic orders?\n\n"
            f"  Items per order : {items_min} – {items_max}\n"
            f"  Date range      : last {days} days\n"
            f"  Weighted combos : {'Yes' if weighted else 'No'}\n"
            f"  Reduce stock    : {'Yes' if reduce_stock else 'No'}\n\n"
            "This will write records to the live database."
        )
        if not messagebox.askyesno("Confirm Seed", confirm_msg):
            return

        try:
            from app.services.seed_sales_service import SeedSalesService
            svc    = SeedSalesService(self.db)
            result = svc.run(
                num_orders=num,
                items_min=items_min,
                items_max=items_max,
                days_back=days,
                weighted_combos=weighted,
                reduce_stock=reduce_stock,
            )

            if result.get("error"):
                messagebox.showerror("Seed Error", result["error"])
                return

            from app.utils import money

            # Invalidate ML cache (best-effort)
            try:
                from app.ml.recommender import Recommender
                Recommender(self.db).invalidate_cache()
            except Exception:
                pass

            messagebox.showinfo(
                "Seed Complete",
                f"Done!\n\n"
                f"  Orders created  : {result['orders_created']}\n"
                f"  Total generated : {money(result['total_sales'])}\n\n"
                "ML recommender cache has been invalidated.",
            )
            self.destroy()

        except Exception as exc:
            messagebox.showerror("Error", f"Seeding failed:\n{exc}")
