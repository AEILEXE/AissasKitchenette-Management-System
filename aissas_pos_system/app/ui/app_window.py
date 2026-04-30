from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, Menu
from typing import Any, Callable, Optional, Type

from app.config import APP_NAME, THEME, LOGO_PATH
from app.db.database import Database
from app.services.auth_service import AuthService
from app.constants import P_POS, P_INV_VIEW, P_INV_MANAGE, P_REPORTS, P_DATABASE
from app.ui import ui_scale
from app.ui import ui_styles

try:
    from PIL import Image, ImageTk  # type: ignore
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

from app.ui.login_view import LoginView
from app.ui.pos_view import POSView
from app.ui.transactions_view import TransactionsView
from app.ui.inventory_shell_view import InventoryShellView
from app.ui.dashboard_view import DashboardView
from app.ui.reports_view import ReportsView
from app.ui.backup_view import BackupView
from app.ui.account_settings_view import AccountSettingsDialog

# ── Nav colours (warm café palette) ─────────────────────────────────────────
_SB        = THEME["sidebar"]         # #5C3D2E  warm coffee brown
_SB_ACTIVE = THEME["sidebar_active"]  # #D4956A  terra cotta
_SB_HOVER  = THEME["sidebar_hover"]   # #7A5244  deeper warm brown
_SB_TEXT   = "#FFFFFF"
_TOPBAR_H  = 48


def _format_display_name(user) -> str:
    """Return 'Full Name (Role)' or fall back to formatted username."""
    full_name = getattr(user, "full_name", "").strip() if user else ""
    username  = getattr(user, "username", "").strip() if user else ""
    role      = (getattr(user, "role", "") or "").capitalize()

    if full_name:
        return f"{full_name}  ({role})"

    if not username:
        return "User"
    parts = [p for p in re.split(r"[\s._-]+", username) if p]
    display = " ".join(p[:1].upper() + p[1:].lower() for p in parts) if parts else username.title()
    return f"{display}  ({role})"


class AppWindow:
    def __init__(self, root: tk.Tk, db: Database, auth_service: AuthService):
        self.root = root
        self.db = db
        self.auth_service = auth_service
        self._current_view: Optional[tk.Widget] = None

        self.root.configure(bg=THEME["bg"])
        ui_styles.apply_global_styles()

        self.root_frame = tk.Frame(root, bg=THEME["bg"])
        self.root_frame.pack(fill=tk.BOTH, expand=True)

        # Topbar — warm coffee brown
        self.nav = tk.Frame(self.root_frame, bg=_SB, height=_TOPBAR_H)
        self.nav.pack_propagate(False)

        self.content = tk.Frame(self.root_frame, bg=THEME["bg"])
        self.content.pack(fill=tk.BOTH, expand=True)

        self._nav_btns: dict[str, tk.Button] = {}
        self._active_nav_key: str | None = None
        self._nav_logo_ref = None

        self.nav_title: tk.Button | None = None
        self.user_label: tk.Label | None = None
        self.settings_btn: tk.Button | None = None
        self.settings_menu: Menu | None = None

        self.show_login()

    # ── helpers ──────────────────────────────────────────────────────────

    def _set_user_label(self) -> None:
        if not self.user_label:
            return
        u = self.auth_service.get_current_user()
        if not u:
            self.user_label.config(text="")
            return
        self.user_label.config(text=_format_display_name(u))

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
        bg = color if color is not None else _SB
        btn = tk.Button(
            self.nav,
            text=text,
            command=cmd,
            bg=bg,
            fg=_SB_TEXT,
            activebackground=_SB_HOVER,
            activeforeground=_SB_TEXT,
            padx=16,
            pady=0,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            height=2,
        )
        btn.pack(side=side, padx=2, pady=0)
        self._nav_btns[key] = btn
        return btn

    def _set_active_nav(self, key: str) -> None:
        self._active_nav_key = key
        for k, btn in self._nav_btns.items():
            active = (k == key)
            btn.configure(
                bg=_SB_ACTIVE if active else _SB,
                relief=tk.FLAT,
            )
        if self.settings_btn:
            self.settings_btn.configure(
                bg=_SB_ACTIVE if key == "settings" else _SB,
            )

    def _show_shell(self, visible: bool) -> None:
        if visible:
            if not self.nav.winfo_ismapped():
                self.nav.pack(fill=tk.X, before=self.content)
        else:
            if self.nav.winfo_ismapped():
                self.nav.pack_forget()

    def _load_nav_logo(self, height: int = 34) -> "tk.PhotoImage | None":
        try:
            if _HAS_PIL and LOGO_PATH.exists():
                img = Image.open(LOGO_PATH).convert("RGBA")
                ratio = height / img.height
                new_w = max(1, int(img.width * ratio))
                img = img.resize((new_w, height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception:
            pass
        return None

    def _build_nav(self) -> None:
        self._clear_nav()

        # Left warm accent stripe
        tk.Frame(self.nav, bg=THEME["accent"], width=4).pack(side=tk.LEFT, fill=tk.Y)

        # Logo / brand
        logo_img = self._load_nav_logo(32)
        if logo_img:
            self._nav_logo_ref = logo_img
            self.nav_title = tk.Button(
                self.nav,
                image=logo_img,
                text="",
                bg=_SB,
                activebackground=_SB_HOVER,
                bd=0,
                cursor="hand2",
                command=self._logo_click,
                padx=10,
            )
        else:
            self.nav_title = tk.Button(
                self.nav,
                text="Aissa's Kitchenette",
                bg=_SB,
                fg="#FFFFFF",
                activebackground=_SB_HOVER,
                activeforeground="#FAF7F2",
                bd=0,
                cursor="hand2",
                font=("Segoe UI", 11, "bold"),
                command=self._logo_click,
                padx=14,
                pady=0,
                height=2,
            )
        self.nav_title.pack(side=tk.LEFT, padx=(4, 8))

        # Thin vertical divider after logo
        tk.Frame(self.nav, bg="#7A6050", width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)

        # Nav tabs
        if self.auth_service.has_permission(P_POS):
            self._btn("pos", "  POS  ", self.show_pos)

        self._btn("tx", "  Transactions  ", self.show_transactions)
        self._btn("dash", "  Dashboard  ", self.show_dashboard)

        if self.auth_service.has_permission(P_INV_VIEW) or self.auth_service.has_permission(P_INV_MANAGE):
            self._btn("inv", "  Inventory  ", self.show_inventory)

        if self.auth_service.has_permission(P_REPORTS):
            self._btn("reports", "  Reports  ", self.show_reports)

        # ── Right side ────────────────────────────────────────────────────────
        # Settings dropdown (right-aligned)
        self.settings_btn = tk.Button(
            self.nav,
            text="Settings  ▾",
            bg=_SB,
            fg=_SB_TEXT,
            activebackground=_SB_HOVER,
            activeforeground=_SB_TEXT,
            padx=16,
            pady=0,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            height=2,
            command=self._open_settings_menu,
        )
        self.settings_btn.pack(side=tk.RIGHT, padx=2)

        # User label
        self.user_label = tk.Label(
            self.nav,
            text="",
            bg=_SB,
            fg="#F5DFB8",
            font=("Segoe UI", 9),
            padx=14,
        )
        self.user_label.pack(side=tk.RIGHT)

        # Divider before user label
        tk.Frame(self.nav, bg="#7A6050", width=1).pack(side=tk.RIGHT, fill=tk.Y, pady=8)

        self.settings_menu = Menu(
            self.root,
            tearoff=0,
            bg=THEME["panel"],
            fg=THEME["text"],
            activebackground=THEME["primary"],
            activeforeground="white",
            font=("Segoe UI", 10),
            bd=0,
            relief="flat",
        )
        self.settings_menu.add_command(
            label="  Account Settings  ",
            command=self.show_account_settings,
        )
        if self.auth_service.has_permission(P_DATABASE):
            self.settings_menu.add_command(
                label="  Backup & Restore  ",
                command=self.show_backup_settings,
            )
        self.settings_menu.add_separator()
        self.settings_menu.add_command(
            label="  Logout  ",
            command=self.logout,
        )

        self._set_user_label()

    def _logo_click(self) -> None:
        if self.auth_service.has_permission(P_POS):
            self.show_pos()
        elif (self.auth_service.has_permission(P_INV_VIEW) or
              self.auth_service.has_permission(P_INV_MANAGE)):
            self.show_inventory()
        else:
            self.show_transactions()

    def _open_settings_menu(self):
        if not self.settings_menu or not self.settings_btn:
            return
        self._set_active_nav("settings")
        x = self.settings_btn.winfo_rootx()
        y = self.settings_btn.winfo_rooty() + self.settings_btn.winfo_height()
        self.settings_menu.tk_popup(x, y)

    def show_account_settings(self) -> None:
        AccountSettingsDialog(self.root, self.db, self.auth_service,
                              on_data_import=self._refresh_current_view,
                              initial_section="profile")

    def show_backup_settings(self) -> None:
        if not self.auth_service.has_permission(P_DATABASE):
            messagebox.showerror("Access Denied", "No permission to manage database backup.")
            return
        AccountSettingsDialog(self.root, self.db, self.auth_service,
                              on_data_import=self._refresh_current_view,
                              initial_section="backup")

    # ── Navigation ────────────────────────────────────────────────────────────

    def show_login(self) -> None:
        self.auth_service.logout()
        self._show_shell(False)
        self._set_view(LoginView, self.auth_service, self.on_login_success)

    def on_login_success(self) -> None:
        self._show_shell(True)
        self._build_nav()
        self._show_welcome()
        # Navigate to the most appropriate first view for each role.
        # Roles without POS access land on Inventory (if they have it) or Transactions.
        if self.auth_service.has_permission(P_POS):
            self.show_pos()
        elif (self.auth_service.has_permission(P_INV_VIEW) or
              self.auth_service.has_permission(P_INV_MANAGE)):
            self.show_inventory()
        else:
            self.show_transactions()

    def _show_welcome(self) -> None:
        u = self.auth_service.get_current_user()
        if not u:
            return
        full_name = getattr(u, "full_name", "").strip()
        display = full_name if full_name else u.username.upper()
        try:
            _WelcomeToast(self.root, display)
        except Exception:
            pass

    def show_pos(self) -> None:
        if not self.auth_service.has_permission(P_POS):
            messagebox.showerror("Access denied", "No permission for POS")
            self.show_login()
            return
        if self._active_nav_key == "pos" and self._current_view is not None:
            return  # Already on POS — preserve cart state
        self._set_active_nav("pos")
        self._set_view(POSView, self.db, self.auth_service)

    def show_transactions(self) -> None:
        if self._active_nav_key == "tx" and self._current_view is not None:
            return
        self._set_active_nav("tx")
        self._set_view(TransactionsView, self.db, self.auth_service)

    def show_dashboard(self) -> None:
        if self._active_nav_key == "dash" and self._current_view is not None:
            return
        self._set_active_nav("dash")
        self._clear_content()
        view = DashboardView(
            self.content,
            self.db,
            self.auth_service,
            go_transactions_cb=self.show_transactions,
            go_pos_cb=self.show_pos,
        )
        view.pack(fill=tk.BOTH, expand=True)
        self._current_view = view

    def show_inventory(self) -> None:
        if not (self.auth_service.has_permission(P_INV_VIEW) or
                self.auth_service.has_permission(P_INV_MANAGE)):
            messagebox.showerror("Access denied", "No permission for Inventory")
            return
        if self._active_nav_key == "inv" and self._current_view is not None:
            return
        self._set_active_nav("inv")
        self._set_view(InventoryShellView, self.db, self.auth_service,
                       self.show_transactions, self.show_pos, self._force_show_reports)

    def show_reports(self) -> None:
        if not self.auth_service.has_permission(P_REPORTS):
            messagebox.showerror("Access denied", "No permission to view reports.")
            return
        if self._active_nav_key == "reports" and self._current_view is not None:
            # Already on reports — refresh data so latest checkout/resolve shows
            if hasattr(self._current_view, "refresh"):
                self._current_view.refresh()
            return
        self._set_active_nav("reports")
        self._set_view(ReportsView, self.db, self.auth_service)

    def _force_show_reports(self) -> None:
        """Navigate to Reports, bypassing the same-tab guard (e.g. from Inventory)."""
        if not self.auth_service.has_permission(P_REPORTS):
            messagebox.showerror("Access denied", "No permission to view reports.")
            return
        self._active_nav_key = None
        self.show_reports()

    def show_backup(self) -> None:
        if not self.auth_service.has_permission(P_DATABASE):
            messagebox.showerror("Access denied", "No permission to manage database backup.")
            return
        self._set_active_nav("backup")
        self._set_view(BackupView, self.db, self.auth_service)

    def logout(self) -> None:
        self.show_login()

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def _on_zoom(self, direction: int) -> None:
        if direction == 1:
            ui_scale.zoom_in()
        elif direction == -1:
            ui_scale.zoom_out()
        else:
            ui_scale.zoom_reset()

        if self.nav.winfo_ismapped():
            self._build_nav()
            if self._active_nav_key:
                self._set_active_nav(self._active_nav_key)

        self._refresh_current_view()

        pct = int(round(ui_scale.get_scale() * 100))
        try:
            self.root.title(f"{APP_NAME}  ·  {pct}%")
        except Exception:
            pass

    def _refresh_current_view(self) -> None:
        key = self._active_nav_key
        # Force re-render by clearing the active key first, then navigate
        self._active_nav_key = None
        if key == "pos":
            self.show_pos()
        elif key == "tx":
            self.show_transactions()
        elif key == "dash":
            self.show_dashboard()
        elif key == "inv":
            self.show_inventory()
        elif key == "reports":
            self.show_reports()


# ── Welcome toast overlay ─────────────────────────────────────────────────────

class _WelcomeToast(tk.Toplevel):
    """
    Brief fullscreen-centered overlay that says WELCOME, [NAME]!
    Fades out automatically after 2 seconds.
    """
    _DURATION_MS = 2200
    _BG          = "#5C3D2E"
    _FG_HEAD     = "#F5DFB8"
    _FG_SUB      = "#D4956A"

    def __init__(self, parent: tk.Widget, display_name: str):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.93)
        except Exception:
            pass
        self.configure(bg=self._BG)

        # Size and center on parent
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w, h = 420, 180
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        tk.Frame(self, bg=THEME["accent"], height=4).pack(fill="x")

        body = tk.Frame(self, bg=self._BG)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="WELCOME,",
            bg=self._BG, fg=self._FG_SUB,
            font=("Segoe UI", 13, "italic"),
        ).pack(pady=(30, 0))

        tk.Label(
            body,
            text=display_name.upper() + "!",
            bg=self._BG, fg=self._FG_HEAD,
            font=("Segoe UI", 22, "bold"),
        ).pack()

        tk.Frame(self, bg=THEME["accent"], height=4).pack(fill="x")

        self.after(self._DURATION_MS, self._close)
        self.bind("<Button-1>", lambda _e: self._close())

    def _close(self) -> None:
        try:
            self.destroy()
        except Exception:
            pass
