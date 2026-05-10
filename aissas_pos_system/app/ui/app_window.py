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

# Cache nav logo so it isn't re-loaded from disk on every login
_nav_logo_cache: dict = {}

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
    # ── Inactivity lock policy ────────────────────────────────────────────
    INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000   # 15 minutes (configurable)

    def __init__(self, root: tk.Tk, db: Database, auth_service: AuthService):
        self.root = root
        self.db = db
        self.auth_service = auth_service
        self._current_view: Optional[tk.Widget] = None
        self._view_cache: dict[str, tk.Widget] = {}
        self._resize_pending: bool = False
        self._wm_state: str = "normal"
        # Single inactivity-lock state — one timer, no duplicates.
        self._idle_after: Optional[str] = None
        self._lock_overlay: Optional[tk.Toplevel] = None
        self._idle_armed: bool = False
        # Activity bindings are attached at most ONCE per AppWindow lifetime
        # to prevent handler accumulation across logout/login cycles.
        self._activity_bindings_attached: bool = False

        self.root.configure(bg=THEME["bg"])
        ui_styles.apply_global_styles()

        self.root_frame = tk.Frame(root, bg=THEME["bg"])
        self.root_frame.pack(fill=tk.BOTH, expand=True)

        # Topbar — warm coffee brown
        self.nav = tk.Frame(self.root_frame, bg=_SB, height=_TOPBAR_H)
        self.nav.pack_propagate(False)

        self.content = tk.Frame(self.root_frame, bg=THEME["bg"])
        self.content.pack(fill=tk.BOTH, expand=True)

        # Bind root Configure so background stays warm on maximize/restore
        self.root.bind("<Configure>", self._on_root_configure, add="+")

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

    _CANVAS_BG = "#e6ddbd"   # beige — matches POS canvas; used to mask all view transitions

    def _clear_content(self) -> None:
        # Paint containers beige so any momentary gap shows the warm background.
        # Do NOT call update_idletasks() here — that forces a mid-transition render that
        # makes the beige visually flash between screens.
        try:
            self.root.configure(bg=self._CANVAS_BG)
            self.root_frame.configure(bg=self._CANVAS_BG)
            self.content.configure(bg=self._CANVAS_BG)
        except Exception:
            pass
        v = self._current_view
        if v is not None:
            try:
                if not v.winfo_exists():
                    pass  # already destroyed
                elif v in self._view_cache.values():
                    v.pack_forget()   # cached view: hide, preserve state
                else:
                    v.destroy()       # transient view (login, loading): destroy
            except Exception:
                pass
        self._current_view = None

    def _set_view(self, cls: Type[tk.Frame], *args: Any) -> None:
        self._clear_content()
        view = cls(self.content, *args)
        view.pack(fill=tk.BOTH, expand=True)
        self._current_view = view

    def _evict_all_cached_views(self) -> None:
        """Destroy every cached view and clear the cache — called on logout."""
        for v in list(self._view_cache.values()):
            try:
                if v.winfo_exists():
                    v.destroy()
            except Exception:
                pass
        self._view_cache.clear()
        self._current_view = None  # prevent _clear_content from double-destroying

    def _show_cached_view(
        self,
        key: str,
        factory,
        refresh_fn=None,
    ) -> tk.Widget:
        """Show a cached view (lazy-create on first visit). Hides the current view first.

        Cached views are never destroyed on navigation — only pack_forgotten and
        re-packed. This eliminates the destroy/recreate overhead and preserves state
        (e.g. POS cart). refresh_fn(view) is called when re-showing an existing view.
        """
        self._clear_content()
        cached = self._view_cache.get(key)
        if cached is not None and cached.winfo_exists():
            cached.pack(fill=tk.BOTH, expand=True)
            self._current_view = cached
            if refresh_fn is not None:
                try:
                    refresh_fn(cached)
                except Exception:
                    pass
            return cached
        view = factory()
        view.pack(fill=tk.BOTH, expand=True)
        self._view_cache[key] = view
        self._current_view = view
        return view

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
        global _nav_logo_cache
        cache_key = height
        if cache_key in _nav_logo_cache:
            return _nav_logo_cache[cache_key]
        try:
            if _HAS_PIL and LOGO_PATH.exists():
                img = Image.open(LOGO_PATH).convert("RGBA")
                ratio = height / img.height
                new_w = max(1, int(img.width * ratio))
                img = img.resize((new_w, height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                _nav_logo_cache[cache_key] = photo
                return photo
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

        # Nav tabs — Dashboard is the primary landing tab
        self._btn("dash", "  Dashboard  ", self.show_dashboard)

        if self.auth_service.has_permission(P_POS):
            self._btn("pos", "  POS  ", self.show_pos)

        self._btn("tx", "  Transactions  ", self.show_transactions)

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
                label="  Database Backup  ",
                command=self.show_backup,
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

    # ── Navigation ────────────────────────────────────────────────────────────

    def show_login(self) -> None:
        self._disarm_inactivity_lock()
        self.auth_service.logout()
        self._show_shell(False)
        self._evict_all_cached_views()
        self._set_view(LoginView, self.auth_service, self.on_login_success)

    def _on_root_configure(self, event: tk.Event) -> None:
        """Batch background colour updates — single commit per resize burst.
        Skips intermediate Configure events fired during minimize/maximize
        animation so the background is only repainted once the window settles."""
        if event.widget is not self.root:
            return
        try:
            new_state = self.root.state()
        except Exception:
            new_state = self._wm_state
        if new_state != self._wm_state:
            self._wm_state = new_state
            self._resize_pending = False
        if not self._resize_pending:
            self._resize_pending = True
            self.root.after_idle(self._commit_root_layout)

    def _commit_root_layout(self) -> None:
        # Skip repaint while window is iconified — nothing is visible anyway.
        try:
            if self.root.state() == "iconic":
                self._resize_pending = False
                return
        except Exception:
            pass
        try:
            self.root.configure(bg=self._CANVAS_BG)
            self.root_frame.configure(bg=self._CANVAS_BG)
            self.content.configure(bg=self._CANVAS_BG)
        except Exception:
            pass
        finally:
            self._resize_pending = False

    def on_login_success(self) -> None:
        # Maximise the window BEFORE building the nav and navigating so the
        # layout commits at full size in one pass — eliminates the visible
        # "compact → wide" snap that happens when geometry settles after login.
        try:
            self.root.state("zoomed")
        except Exception:
            try:
                self.root.attributes("-zoomed", True)
            except Exception:
                pass
        self._show_loading_screen()
        self._show_shell(True)
        self._build_nav()
        self._show_welcome()
        self.root.after(30, self._finish_login_navigation)
        # Arm inactivity lock now that a user is logged in.
        self._arm_inactivity_lock()

    def _show_loading_screen(self) -> None:
        """Brief loading indicator shown while the main view is being built."""
        self._clear_content()
        frame = tk.Frame(self.content, bg=self._CANVAS_BG)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            frame, text="Loading…",
            bg=self._CANVAS_BG, fg=THEME["muted"],
            font=("Segoe UI", 14),
        ).place(relx=0.5, rely=0.5, anchor="center")
        self._current_view = frame
        self.root.update_idletasks()   # paint the loading frame before continuing

    def _finish_login_navigation(self) -> None:
        """Navigate to the appropriate first view after login.
        Dashboard is the default landing screen for any logged-in user;
        if Dashboard is unavailable for some reason, fall back to POS,
        then Inventory, then Transactions based on permissions."""
        try:
            self.show_dashboard()
            return
        except Exception:
            pass
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
        self._show_cached_view(
            "pos",
            lambda: POSView(self.content, self.db, self.auth_service),
        )

    def show_transactions(self) -> None:
        if self._active_nav_key == "tx" and self._current_view is not None:
            return
        self._set_active_nav("tx")
        self._show_cached_view(
            "tx",
            lambda: TransactionsView(self.content, self.db, self.auth_service),
            refresh_fn=lambda v: v.refresh() if hasattr(v, "refresh") else None,
        )

    def show_transactions_filtered(self, status: str = "All") -> None:
        """Navigate to Transactions and pre-apply a status filter."""
        self._active_nav_key = None   # bypass same-tab guard
        self.show_transactions()
        v = self._view_cache.get("tx")
        if v and v.winfo_exists() and hasattr(v, "set_status_filter"):
            v.set_status_filter(status)

    def show_dashboard(self) -> None:
        if self._active_nav_key == "dash" and self._current_view is not None:
            return
        self._set_active_nav("dash")
        self._show_cached_view(
            "dash",
            lambda: DashboardView(
                self.content, self.db, self.auth_service,
                go_transactions_cb=self.show_transactions,
                go_pos_cb=self.show_pos,
                go_inventory_cb=self.show_inventory,
                go_pending_cb=lambda: self.show_transactions_filtered("Pending"),
                go_completed_cb=lambda: self.show_transactions_filtered("Completed"),
                go_reports_cb=self.show_reports,
            ),
            refresh_fn=lambda v: v._refresh() if hasattr(v, "_refresh") else None,
        )

    def _refresh_pos_categories(self) -> None:
        """Refresh the category buttons on the cached POS view, if it exists."""
        v = self._view_cache.get("pos")
        if v and v.winfo_exists() and hasattr(v, "_refresh_categories"):
            try:
                v._refresh_categories()
            except Exception:
                pass

    def _refresh_pos_after_inventory(self, changed_image_rel: str | None = None) -> None:
        """Full POS refresh after an inventory product/category change.

        Refreshes both category buttons and the visible product cards on the
        cached POS view (if any). Image cache is invalidated for the changed
        product so a swapped image renders without an app restart.
        """
        v = self._view_cache.get("pos")
        if v and v.winfo_exists() and hasattr(v, "refresh_after_inventory_change"):
            try:
                v.refresh_after_inventory_change(changed_image_rel)
            except Exception:
                pass

    def show_inventory(self) -> None:
        if not (self.auth_service.has_permission(P_INV_VIEW) or
                self.auth_service.has_permission(P_INV_MANAGE)):
            messagebox.showerror("Access denied", "No permission for Inventory")
            return
        if self._active_nav_key == "inv" and self._current_view is not None:
            return
        self._set_active_nav("inv")
        self._show_cached_view(
            "inv",
            lambda: InventoryShellView(
                self.content, self.db, self.auth_service,
                self.show_transactions, self.show_pos, self._force_show_reports,
                refresh_pos_cats_cb=self._refresh_pos_categories,
                refresh_pos_full_cb=self._refresh_pos_after_inventory,
            ),
        )

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
        self._show_cached_view(
            "reports",
            lambda: ReportsView(self.content, self.db, self.auth_service),
            refresh_fn=lambda v: v.refresh() if hasattr(v, "refresh") else None,
        )

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
        self._show_cached_view(
            "backup",
            lambda: BackupView(self.content, self.db, self.auth_service),
        )

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

    # ── Inactivity lock ──────────────────────────────────────────────────────

    def _arm_inactivity_lock(self) -> None:
        """Start tracking activity and (re)start the idle timer.
        Idempotent — repeated calls don't add duplicate bindings or timers.
        Activity bindings are attached at most ONCE per AppWindow lifetime
        so logout/login cycles do not accumulate Tk event handlers."""
        if not self._activity_bindings_attached:
            for ev in ("<Any-KeyPress>", "<Any-ButtonPress>", "<Motion>"):
                try:
                    self.root.bind_all(ev, self._on_user_activity, add="+")
                except Exception:
                    pass
            self._activity_bindings_attached = True
        # Always (re)start a single timer
        self._idle_armed = True
        self._reset_idle_timer()

    def _disarm_inactivity_lock(self) -> None:
        """Stop tracking and cancel any pending lock timer.
        Bindings stay attached (single-shot install) — the handler returns
        early when no user is logged in, so no work is done."""
        if self._idle_after is not None:
            try:
                self.root.after_cancel(self._idle_after)
            except Exception:
                pass
            self._idle_after = None
        self._idle_armed = False

    def _on_user_activity(self, _event=None) -> None:
        # While locked, activity should not silently restart the timer.
        if self._lock_overlay is not None:
            return
        # Skip cheaply when no one is logged in or tracker is disarmed.
        if not self._idle_armed:
            return
        if self.auth_service.get_current_user() is None:
            return
        self._reset_idle_timer()

    def _reset_idle_timer(self) -> None:
        if self._idle_after is not None:
            try:
                self.root.after_cancel(self._idle_after)
            except Exception:
                pass
            self._idle_after = None
        if self.auth_service.get_current_user() is None:
            return  # not logged in — don't arm
        self._idle_after = self.root.after(
            self.INACTIVITY_TIMEOUT_MS, self._on_inactivity_lock
        )

    def _on_inactivity_lock(self) -> None:
        self._idle_after = None
        if self.auth_service.get_current_user() is None:
            return
        # Prevent overlay stacking — even if an existing overlay was
        # destroyed externally, never instantiate a second concurrent one.
        existing = self._lock_overlay
        if existing is not None:
            try:
                if existing.winfo_exists():
                    try:
                        existing.lift()
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            self._lock_overlay = None
        try:
            self._lock_overlay = _InactivityLockOverlay(
                self.root, self.auth_service,
                on_unlock=self._on_unlock,
                on_logout=self._on_lock_logout,
            )
        except Exception as exc:
            from app.utils import log_error
            log_error("Inactivity lock overlay", exc)
            # Fall back to logout if overlay can't render
            self._on_lock_logout()

    def _on_unlock(self) -> None:
        self._lock_overlay = None
        # Resume idle tracking with a fresh timer
        self._reset_idle_timer()

    def _on_lock_logout(self) -> None:
        self._lock_overlay = None
        self._disarm_inactivity_lock()
        self.show_login()

    def _refresh_current_view(self) -> None:
        key = self._active_nav_key
        # Evict the cached view for this key so it's fully rebuilt (e.g. after zoom)
        if key in self._view_cache:
            try:
                old = self._view_cache.pop(key)
                if old.winfo_exists():
                    old.destroy()
            except Exception:
                pass
        if self._current_view is not None:
            try:
                if self._current_view.winfo_exists():
                    self._current_view.destroy()
            except Exception:
                pass
        self._current_view = None
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


# ── Inactivity Lock Overlay ───────────────────────────────────────────────────

class _InactivityLockOverlay(tk.Toplevel):
    """
    Modal screen-locking overlay shown after the inactivity timeout.

    The current user must re-enter their password to unlock — preserves the
    POS cart, transaction view state, etc. Logout button drops to login.
    Any underlying view is left intact (not destroyed), so the cart never
    gets cleared.
    """

    _BG    = "#1a1410"
    _PANEL = "#FFFFFF"

    def __init__(self, parent: tk.Tk, auth: AuthService,
                 on_unlock, on_logout):
        super().__init__(parent)
        self.auth = auth
        self.on_unlock = on_unlock
        self.on_logout = on_logout
        self._parent_ref = parent
        self._resize_after: Optional[str] = None
        self._resize_bind_id: Optional[str] = None

        self.overrideredirect(True)
        self.configure(bg=self._BG)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.97)
        except Exception:
            pass

        # Cover the whole parent window.
        self._sync_geometry()

        self.grab_set()
        self.transient(parent)

        # Follow parent resize/maximize/minimize so the overlay never
        # exposes edges of the underlying view.
        try:
            self._resize_bind_id = parent.bind(
                "<Configure>", self._on_parent_configure, add="+"
            )
        except Exception:
            self._resize_bind_id = None

        # Card container, centered
        card = tk.Frame(self, bg=self._PANEL, highlightthickness=2,
                         highlightbackground=THEME.get("accent", "#D4956A"))
        card.place(relx=0.5, rely=0.5, anchor="center", width=420, height=300)

        tk.Label(
            card, text="🔒  Session Locked",
            bg=self._PANEL, fg=THEME["text"],
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(28, 4))

        u = self.auth.get_current_user()
        uname = getattr(u, "username", "") if u else ""
        tk.Label(
            card,
            text=("Inactivity timeout. Enter your password to continue." +
                  (f"\nLogged in as: {uname}" if uname else "")),
            bg=self._PANEL, fg=THEME.get("muted", "#7B6B57"),
            font=("Segoe UI", 9),
            justify="center",
        ).pack(pady=(0, 18))

        # Password input
        self._pw_var = tk.StringVar()
        entry = tk.Entry(
            card, textvariable=self._pw_var,
            font=("Segoe UI", 12), bg="#F4EFEA",
            bd=0, show="*",
            insertbackground="#3d2b1f", insertwidth=2,
            justify="center",
        )
        entry.pack(fill="x", padx=40, ipady=10)
        entry.focus_set()
        # Block clipboard leakage from the inactivity-unlock password field.
        entry.bind("<<Copy>>",  lambda _e: "break")
        entry.bind("<<Cut>>",   lambda _e: "break")
        entry.bind("<Button-3>", lambda _e: "break")

        self._err_lbl = tk.Label(
            card, text="", bg=self._PANEL,
            fg=THEME.get("danger", "#991B1B"),
            font=("Segoe UI", 9, "italic"),
        )
        self._err_lbl.pack(pady=(8, 0))

        btns = tk.Frame(card, bg=self._PANEL)
        btns.pack(fill="x", padx=40, pady=(18, 24))

        tk.Button(
            btns, text="Logout", command=self._do_logout,
            bg="#FFFFFF", fg=THEME["text"], bd=1,
            relief="solid", padx=14, pady=8, cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side="left")

        tk.Button(
            btns, text="Unlock", command=self._do_unlock,
            bg=THEME.get("accent", "#D4956A"), fg="white", bd=0,
            padx=18, pady=9, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        self.bind("<Return>", lambda _e: self._do_unlock())
        # Block Escape so the overlay can't be casually dismissed
        self.bind("<Escape>", lambda _e: "break")
        self.protocol("WM_DELETE_WINDOW", lambda: None)

    def _do_unlock(self) -> None:
        u = self.auth.get_current_user()
        if u is None:
            # Auth lost mid-lock — drop to login safely.
            try:
                self._cleanup()
                self.destroy()
            finally:
                self.on_logout()
            return
        pw = self._pw_var.get() or ""
        if not pw:
            self._err_lbl.configure(text="Enter your password.")
            return
        try:
            ok, _ = self.auth.verify_password(u.username, pw)
        except Exception:
            ok = False
        if not ok:
            self._err_lbl.configure(text="Incorrect password.")
            self._pw_var.set("")
            return
        try:
            self._cleanup()
            self.destroy()
        finally:
            self.on_unlock()

    def _do_logout(self) -> None:
        try:
            self._cleanup()
            self.destroy()
        finally:
            self.on_logout()

    # ── Geometry sync ─────────────────────────────────────────────────────
    def _sync_geometry(self) -> None:
        try:
            parent = self._parent_ref
            if not parent or not parent.winfo_exists():
                return
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = max(1, parent.winfo_width())
            ph = max(1, parent.winfo_height())
            if pw <= 1 or ph <= 1:
                return
            self.geometry(f"{pw}x{ph}+{px}+{py}")
        except Exception:
            pass

    def _on_parent_configure(self, _event=None) -> None:
        # Debounce — Tk fires <Configure> rapidly during drag/resize.
        if self._resize_after is not None:
            try:
                self.after_cancel(self._resize_after)
            except Exception:
                pass
        try:
            self._resize_after = self.after(50, self._sync_geometry)
        except Exception:
            self._resize_after = None

    def _cleanup(self) -> None:
        if self._resize_after is not None:
            try:
                self.after_cancel(self._resize_after)
            except Exception:
                pass
            self._resize_after = None
        try:
            if self._resize_bind_id and self._parent_ref \
                    and self._parent_ref.winfo_exists():
                self._parent_ref.unbind("<Configure>", self._resize_bind_id)
        except Exception:
            pass
        self._resize_bind_id = None
