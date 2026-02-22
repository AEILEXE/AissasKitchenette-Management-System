from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, Menu
from typing import Any, Callable, Optional, Type

from app.config import APP_NAME, THEME
from app.db.database import Database
from app.services.auth_service import AuthService
from app.constants import P_POS, P_INV_VIEW, P_INV_MANAGE  # keep perms

from app.ui.login_view import LoginView
from app.ui.pos_view import POSView
from app.ui.transactions_view import TransactionsView
from app.ui.inventory_shell_view import InventoryShellView
from app.ui.account_settings_view import AccountSettingsDialog


class AppWindow:
    def __init__(self, root: tk.Tk, db: Database, auth_service: AuthService):
        self.root = root
        self.db = db
        self.auth_service = auth_service
        self._current_view: Optional[tk.Widget] = None

        self.root.configure(bg=THEME["bg"])

        self.root_frame = tk.Frame(root, bg=THEME["bg"])
        self.root_frame.pack(fill=tk.BOTH, expand=True)

        self.nav = tk.Frame(self.root_frame, bg=THEME["primary"], height=52)

        self.content = tk.Frame(self.root_frame, bg=THEME["bg"])
        self.content.pack(fill=tk.BOTH, expand=True)

        self._nav_btns: dict[str, tk.Button] = {}
        self._active_nav_key: str | None = None

        self.nav_title: tk.Label | None = None
        self.user_label: tk.Label | None = None
        self.settings_btn: tk.Button | None = None
        self.settings_menu: Menu | None = None

        self.show_login()

    # ---------- helpers ----------
    def _set_user_label(self) -> None:
        if not self.user_label:
            return
        u = self.auth_service.get_current_user()
        self.user_label.config(text=f"{u.username} ({u.role})" if u else "")

    def _clear_content(self) -> None:
        if self._current_view is not None:
            self._current_view.destroy()
        self._current_view = None

    def _set_view(self, cls: Type[tk.Frame], *args: Any) -> None:
        self._clear_content()
        view = cls(self.content, *args)
        view.pack(fill=tk.BOTH, expand=True)
        self._current_view = view

    def _clear_nav(self) -> None:
        for w in self.nav.winfo_children():
            w.destroy()
        self._nav_btns.clear()
        self._active_nav_key = None
        self.nav_title = None
        self.user_label = None
        self.settings_btn = None
        self.settings_menu = None

    def _btn(
        self,
        key: str,
        text: str,
        cmd: Callable[[], None],
        side: str = tk.LEFT,
        color: Optional[str] = None,
    ) -> tk.Button:
        bg = color if color is not None else THEME["primary"]
        btn = tk.Button(
            self.nav,
            text=text,
            command=cmd,
            bg=bg,
            fg=THEME["text_on_primary"],
            activebackground=THEME["primary_light"],
            activeforeground=THEME["text_on_primary"],
            padx=16,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )
        btn.pack(side=side, padx=6, pady=6)
        self._nav_btns[key] = btn
        return btn

    def _set_active_nav(self, key: str) -> None:
        self._active_nav_key = key
        for k, btn in self._nav_btns.items():
            if k in ("logout",):
                continue
            btn.configure(bg=THEME["primary_dark"] if k == key else THEME["primary"])

        # Settings button highlight too
        if self.settings_btn:
            self.settings_btn.configure(bg=THEME["primary_dark"] if key == "settings" else THEME["primary"])

    def _show_shell(self, visible: bool) -> None:
        if visible:
            if not self.nav.winfo_ismapped():
                self.nav.pack(fill=tk.X, before=self.content)
        else:
            if self.nav.winfo_ismapped():
                self.nav.pack_forget()

    def _build_nav(self) -> None:
        self._clear_nav()

        self.nav_title = tk.Label(
            self.nav,
            text=APP_NAME,
            bg=THEME["primary"],
            fg=THEME["text_on_primary"],
            font=("Segoe UI", 12, "bold"),
        )
        self.nav_title.pack(side=tk.LEFT, padx=(14, 10), pady=8)

        # Tabs
        if self.auth_service.has_permission(P_POS):
            self._btn("pos", "POS", self.show_pos)

        self._btn("tx", "Transactions", self.show_transactions)

        if self.auth_service.has_permission(P_INV_VIEW) or self.auth_service.has_permission(P_INV_MANAGE):
            self._btn("inv", "Inventory", self.show_inventory)

        # Settings dropdown
        self.settings_btn = tk.Button(
            self.nav,
            text="Settings ▾",
            bg=THEME["primary"],
            fg=THEME["text_on_primary"],
            activebackground=THEME["primary_light"],
            activeforeground=THEME["text_on_primary"],
            padx=16,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            command=self._open_settings_menu,
        )
        self.settings_btn.pack(side=tk.LEFT, padx=6, pady=6)

        self.settings_menu = Menu(self.root, tearoff=0)
        self.settings_menu.add_command(label="Account", command=self.show_account_settings)
        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="Logout", command=self.logout)

        # Right area
        self.user_label = tk.Label(
            self.nav,
            text="",
            bg=THEME["primary"],
            fg=THEME["text_on_primary"],
            font=("Segoe UI", 10, "bold"),
        )
        self.user_label.pack(side=tk.RIGHT, padx=(10, 14), pady=8)

        self._set_user_label()

    def _open_settings_menu(self):
        if not self.settings_menu or not self.settings_btn:
            return
        self._set_active_nav("settings")
        x = self.settings_btn.winfo_rootx()
        y = self.settings_btn.winfo_rooty() + self.settings_btn.winfo_height()
        self.settings_menu.tk_popup(x, y)

    def show_account_settings(self) -> None:
        """Open account settings dialog."""
        AccountSettingsDialog(self.root, self.db, self.auth_service)

    # ---------- Navigation ----------
    def show_login(self) -> None:
        self.auth_service.logout()
        self._show_shell(False)
        self._set_view(LoginView, self.auth_service, self.on_login_success)

    def on_login_success(self) -> None:
        self._show_shell(True)
        self._build_nav()
        self.show_pos()

    def show_pos(self) -> None:
        if not self.auth_service.has_permission(P_POS):
            messagebox.showerror("Access denied", "No permission for POS")
            self.show_login()
            return
        self._set_active_nav("pos")
        self._set_view(POSView, self.db, self.auth_service)

    def show_transactions(self) -> None:
        self._set_active_nav("tx")
        self._set_view(TransactionsView, self.db, self.auth_service)

    def show_inventory(self) -> None:
        if not (self.auth_service.has_permission(P_INV_VIEW) or self.auth_service.has_permission(P_INV_MANAGE)):
            messagebox.showerror("Access denied", "No permission for Inventory")
            return
        self._set_active_nav("inv")
        self._set_view(InventoryShellView, self.db, self.auth_service, self.show_transactions, self.show_pos)

    def logout(self) -> None:
        self.show_login()