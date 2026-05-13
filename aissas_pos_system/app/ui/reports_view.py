"""
reports_view.py — Reports & Analytics View
"""
from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, timedelta

from app.config import THEME
from app.db.database import Database
from app.services.auth_service import AuthService
from app.ui.transactions_view import DatePickerDialog


def _bind_date_picker(entry: tk.Entry, var: tk.StringVar) -> None:
    """Attach a calendar popup to a date Entry widget."""
    def _open(e=None):
        parent = entry.winfo_toplevel()
        dlg = DatePickerDialog(parent, initial=var.get() or None)
        if dlg.result:
            var.set(dlg.result)
    entry.bind("<Button-1>", _open)
    entry.configure(cursor="hand2")

_SB     = THEME["sidebar"]
_RED    = THEME["primary"]
_SLATE  = THEME["accent"]
_GREEN  = THEME["success"]
_BG     = THEME["bg"]
_PANEL  = THEME["panel"]
_TEXT   = THEME["text"]
_MUTED  = THEME["muted"]
_BORDER = THEME["border"]


def _money(v):
    try:
        return f"₱{float(v):,.2f}"
    except Exception:
        return "₱0.00"


class ReportsView(tk.Frame):
    _POLL_INTERVAL_MS = 5000  # check for new data every 5 s

    def __init__(self, parent, db: Database, auth: AuthService):
        super().__init__(parent, bg=_BG)
        self.db   = db
        self.auth = auth
        self._active_tab: str = "reports"
        self._tab_btns: dict[str, tk.Button] = {}
        self._content: tk.Frame | None = None
        self._tab_frames: dict[str, tk.Frame] = {}   # cached tab content
        self._poll_after: int | None = None
        self._poll_version: int = -1
        self._build()
        self._start_polling()
        self.bind("<Destroy>", lambda _e: self._cancel_poll())

    # ── Top navigation ────────────────────────────────────────────────────────
    def _build(self):
        hdr_bar = tk.Frame(self, bg=_SB)
        hdr_bar.pack(fill="x")
        tk.Frame(hdr_bar, bg=_RED, width=5).pack(side="left", fill="y")
        tk.Label(hdr_bar, text="Reports & Analytics",
                 bg=_SB, fg="#792D2D",
                 font=("Segoe UI", 14, "bold"),
                 padx=14, pady=12).pack(side="left")

        # A single "Back to Reports" button is shown on the right of the header
        # whenever a specific report is open. It returns to the cards picker.
        # The previous duplicate sub-navigation tabs (Home / Total Sales /
        # Discounts / Inventory / Void History / Analytics) have been removed
        # because the card picker on the home view already provides navigation.
        self._back_btn = tk.Button(
            hdr_bar, text="←  Back to Reports",
            command=lambda: self._show_tab("home"),
            bg=THEME["primary_dark"], fg="#FFFFFF",
            activebackground=THEME["primary"], activeforeground="#FFFFFF",
            bd=0, padx=14, pady=6, cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        # Not packed by default — only visible when a report is open.

        self._content = tk.Frame(self, bg=_BG)
        self._content.pack(fill="both", expand=True)

        # Land on the type-picker home view, not a mixed Overview
        self._active_tab = "home"
        self._show_tab("home")

    def _update_tab_style(self):
        # Only the Back button is visible — toggle it based on whether the
        # active tab is the home picker or a specific report.
        back = getattr(self, "_back_btn", None)
        if back is None:
            return
        try:
            if self._active_tab == "home":
                back.pack_forget()
            else:
                if not back.winfo_ismapped():
                    back.pack(side="right", padx=(8, 14), pady=10)
        except Exception:
            pass

    def refresh(self):
        # Force-rebuild only the active tab so stale data is never shown
        old = self._tab_frames.pop(self._active_tab, None)
        if old and old.winfo_exists():
            old.destroy()
        self._show_tab(self._active_tab)

    def _log_report_print(self, report_type: str, path: str) -> None:
        """Audit a report export/print to print_logs. Never raises."""
        try:
            import os as _os
            u = self.auth.get_current_user() if getattr(self, "auth", None) else None
            self.db.log_print(
                user_id=getattr(u, "user_id", None),
                username=getattr(u, "username", "") or "",
                print_type=f"REPORT_{report_type}",
                reference_id="",
                detail=_os.path.basename(path or ""),
            )
        except Exception:
            pass

    # ── Polling (cross-device auto-refresh) ──────────────────────────────────

    def _start_polling(self) -> None:
        self._cancel_poll()
        self._poll_after = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    def _cancel_poll(self) -> None:
        if self._poll_after is not None:
            try:
                self.after_cancel(self._poll_after)
            except Exception:
                pass
            self._poll_after = None

    def _poll_tick(self) -> None:
        self._poll_after = None
        try:
            if not self.winfo_exists():
                return
            if self.winfo_ismapped():
                v = self.db.get_data_version()
                if v != self._poll_version:
                    self._poll_version = v
                    self.refresh()  # synchronous; re-arm below after it returns
        except Exception:
            pass
        self._poll_after = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    # Sub-tab → required permission. Defense-in-depth: ReportsView itself is
    # already gated by P_REPORTS at the nav level, but a hostile call into
    # _show_tab (e.g. from a future refactor or a stale callback) must not be
    # able to open Analytics / Void History / Breakdowns / etc for a session
    # whose role lost permission since the view was first opened.
    _TAB_PERMISSIONS: dict[str, str] = {
        "sales":         "can_view_reports",
        "top_sellers":   "can_view_reports",
        "discounts":     "can_view_reports",
        "raw_materials": "can_view_reports",
        "void_history":  "can_view_reports",
        "breakdowns":    "can_view_reports",
        # "home" intentionally omitted — the picker itself is reachable for
        # anyone who already passed the outer P_REPORTS gate.
    }

    def _show_tab(self, key: str):
        # ── Permission re-check (defense-in-depth) ───────────────────────────
        required = self._TAB_PERMISSIONS.get(key)
        if required and not self.auth.has_permission(required):
            try:
                messagebox.showerror(
                    "Access Denied",
                    "You do not have permission to open this report.",
                )
            except Exception:
                pass
            # Fall back to the home picker so the user is not left on a stale
            # tab. If the user can't even reach home, route them out cleanly.
            if key != "home" and self.auth.has_permission("can_view_reports"):
                key = "home"
            else:
                return

        self._active_tab = key
        self._update_tab_style()
        if not self._content:
            return

        # Hide every cached tab frame
        for frame in self._tab_frames.values():
            if frame.winfo_exists():
                frame.pack_forget()

        # Return cached frame if it exists
        cached = self._tab_frames.get(key)
        if cached and cached.winfo_exists():
            cached.pack(fill="both", expand=True)
            return

        # Build fresh tab content inside a wrapper frame
        tab_frame = tk.Frame(self._content, bg=_BG)
        tab_frame.pack(fill="both", expand=True)
        self._tab_frames[key] = tab_frame

        if key == "sales":
            self._build_sales_tab(tab_frame)
        elif key == "top_sellers":
            self._build_top_sellers_tab(tab_frame)
        elif key == "discounts":
            self._build_discounts_tab(tab_frame)
        elif key == "raw_materials":
            self._build_raw_materials_tab(tab_frame)
        elif key == "void_history":
            self._build_void_history_tab(tab_frame)
        elif key == "breakdowns":
            self._build_breakdowns_tab(tab_frame)
        elif key == "home":
            self._build_home_picker(tab_frame)
        else:
            self._build_reports_tab(tab_frame)

    # ── Home picker (type-first landing) ──────────────────────────────────────
    def _build_home_picker(self, parent: tk.Frame) -> None:
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Choose a Report",
                 bg=_BG, fg=_TEXT,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=28, pady=(20, 4))
        tk.Label(outer, text="Pick the report type you want to view. "
                             "Each report opens on its own — no mixed dashboards.",
                 bg=_BG, fg=_MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=28, pady=(0, 18))

        grid = tk.Frame(outer, bg=_BG)
        grid.pack(fill="both", expand=True, padx=22, pady=(0, 22))
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="rpt")

        cards = [
            ("sales",        "Total Sales",  "Daily, weekly, monthly and yearly revenue charts.", _RED),
            ("discounts",    "Discounts",    "PWD, Senior, and special discounts breakdown.",     _SLATE),
            ("raw_materials","Inventory",    "Raw materials movement and stock activity.",        _SB),
            ("void_history", "Void History", "Voided / cancelled transactions with calendar.",    THEME["danger"]),
            ("top_sellers",  "Analytics",    "Top selling products with quantity sold chart.",    _GREEN),
            ("breakdowns",   "Breakdowns",   "Payment methods, Dine-In vs Take-Out, and order status charts.", THEME["brown"]),
        ]
        for i, (key, title, sub, accent) in enumerate(cards):
            r, c = divmod(i, 3)
            card = tk.Frame(grid, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER, cursor="hand2")
            card.grid(row=r, column=c, sticky="nsew", padx=8, pady=8)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=title, bg=_PANEL, fg=_TEXT,
                     font=("Segoe UI", 14, "bold"), anchor="w"
                     ).pack(anchor="w", padx=18, pady=(14, 4))
            tk.Label(card, text=sub, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9), anchor="w", justify="left",
                     wraplength=260).pack(anchor="w", padx=18, pady=(0, 14))
            tk.Label(card, text="Open  →", bg=_PANEL, fg=accent,
                     font=("Segoe UI", 9, "bold"),
                     ).pack(anchor="e", padx=18, pady=(0, 12))

            for w in (card, *card.winfo_children()):
                w.bind("<Button-1>", lambda _e, k=key: self._show_tab(k))
            for w in card.winfo_children():
                for ch in w.winfo_children():
                    ch.bind("<Button-1>", lambda _e, k=key: self._show_tab(k))

    # ── Void History tab ──────────────────────────────────────────────────────
    def _build_void_history_tab(self, parent: tk.Frame) -> None:
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(2, weight=1)
        outer.columnconfigure(0, weight=1)

        _FILTER_BG = "#f5f0e8"
        _LABEL_FG  = "#3d2b1f"
        _SEL_BG    = "#8c6e3b"
        _SEL_FG    = "white"
        _UNSEL_BG  = _FILTER_BG
        _UNSEL_FG  = _LABEL_FG

        # Filter bar with calendar + period quick-buttons
        bar = tk.Frame(outer, bg=_FILTER_BG,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))

        tk.Label(bar, text="Period:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)

        period_var = tk.StringVar(value="month")
        _period_btns: dict[str, tk.Button] = {}

        def _set_period(val: str) -> None:
            period_var.set(val)
            for v, b in _period_btns.items():
                b.configure(
                    bg=_SEL_BG if v == val else _UNSEL_BG,
                    fg=_SEL_FG if v == val else _UNSEL_FG,
                )

        for lbl, val in [("Today", "today"), ("This Week", "week"),
                          ("This Month", "month"), ("This Year", "year"),
                          ("All Time", "all")]:
            is_def = (val == "month")
            btn = tk.Button(
                bar, text=lbl,
                command=lambda v=val: _set_period(v),
                bg=_SEL_BG if is_def else _UNSEL_BG,
                fg=_SEL_FG if is_def else _UNSEL_FG,
                activebackground=_SEL_BG, activeforeground=_SEL_FG,
                relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            btn.pack(side="left", padx=2, pady=8)
            _period_btns[val] = btn

        # Custom date range using DatePickerDialog
        tk.Label(bar, text="From:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=12,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT, insertwidth=2)
        from_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(from_ent, from_var)

        tk.Label(bar, text="To:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=12,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT, insertwidth=2)
        to_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(to_ent, to_var)

        # Summary KPI row
        kpi_frame = tk.Frame(outer, bg=_BG)
        kpi_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 0))
        for i in range(3):
            kpi_frame.columnconfigure(i, weight=1, uniform="vkpi")

        kpi_vars = [tk.StringVar(value="—") for _ in range(3)]
        kpi_labels = ["Voided Transactions", "Total Voided Amount", "Items Voided"]
        kpi_accents = [THEME["danger"], _RED, THEME["primary_dark"]]
        for i, (lbl, var, accent) in enumerate(zip(kpi_labels, kpi_vars, kpi_accents)):
            outer_c = tk.Frame(kpi_frame, bg=_BG)
            outer_c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            card = tk.Frame(outer_c, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
            card.pack(fill="both", expand=True)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=lbl, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 8), anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, textvariable=var, bg=_PANEL, fg=accent,
                     font=("Segoe UI", 18, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

        # Table
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("VH.Treeview", rowheight=28, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT,
                    borderwidth=0, relief="flat")
        s.configure("VH.Treeview.Heading", font=("Segoe UI", 9, "bold"),
            background=_SB, foreground="#2B2B2B",
            relief="flat", padding=(8, 7))
        s.map("VH.Treeview",
              background=[("selected", _RED), ("!selected", _PANEL)],
              foreground=[("selected", "#FFFFFF"), ("!selected", _TEXT)])

        cols = ("dt", "trx", "type", "voided_by", "amount", "reason")
        tbl = ttk.Treeview(tbl_frame, columns=cols, show="headings", style="VH.Treeview")
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        col_cfg = [
            ("dt",        "Date & Time",   140, "center", False),
            ("trx",       "Transaction #",  90, "center", False),
            ("type",      "Void Type",     110, "center", False),
            ("voided_by", "Voided By",     130, "w",      False),
            ("amount",    "Amount",        110, "e",      False),
            ("reason",    "Reason",        260, "w",      True),
        ]
        for cid, hdr, w, anc, stretch in col_cfg:
            tbl.heading(cid, text=hdr, anchor="center")
            tbl.column(cid, width=w, minwidth=60, anchor=anc, stretch=stretch)

        tbl.tag_configure("odd",  background=_PANEL)
        tbl.tag_configure("even", background="#FAFAF8")

        empty_lbl = tk.Label(
            tbl_frame, text="No voided transactions for the selected period.",
            bg=_PANEL, fg=_MUTED, font=("Segoe UI", 11, "italic"),
        )

        # Footer
        foot = tk.Frame(outer, bg=_BG)
        foot.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        def _date_clause() -> str:
            p = period_var.get()
            df = from_var.get().strip()
            dt = to_var.get().strip()
            if df and dt:
                return f"DATE(vr.created_at,'localtime') BETWEEN DATE('{df}') AND DATE('{dt}')"
            if p == "today":
                return "DATE(vr.created_at,'localtime') = DATE('now','localtime')"
            if p == "week":
                return "DATE(vr.created_at,'localtime') >= DATE('now','localtime','-6 days')"
            if p == "year":
                return "strftime('%Y',vr.created_at,'localtime') = strftime('%Y','now','localtime')"
            if p == "all":
                return "1=1"
            return "strftime('%Y-%m',vr.created_at,'localtime') = strftime('%Y-%m','now','localtime')"

        def load(*_args):
            dc = _date_clause()
            try:
                # For ITEM_VOID we use (oi.qty * oi.unit_price) because the
                # void process zeroes out oi.subtotal — so subtotal alone
                # would always show ₱0.00. The qty / unit_price columns are
                # left intact and represent the original line amount.
                #
                # For FULL_ORDER we sum (qty * unit_price) across every line
                # of the original order so the report reflects the original
                # gross value of the voided receipt regardless of any prior
                # item-level voids that mutated subtotal / orders.total.
                rows = self.db.fetchall(
                    f"""
                    SELECT vr.created_at,
                           vr.original_order_id AS order_id,
                           vr.void_type,
                           vr.voided_by_username,
                           vr.reason,
                           (SELECT COALESCE(SUM(qty * unit_price), 0)
                              FROM order_items
                             WHERE order_id = vr.original_order_id) AS order_original_amount,
                           COALESCE(oi.qty * oi.unit_price, 0)       AS item_original_amount
                    FROM void_records vr
                    LEFT JOIN order_items oi ON oi.id = vr.order_item_id
                    WHERE {dc}
                    ORDER BY datetime(vr.created_at) DESC
                    LIMIT 500;
                    """
                )
            except Exception:
                rows = []

            for iid in tbl.get_children():
                tbl.delete(iid)

            if not rows:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
                for v in kpi_vars:
                    v.set("—")
                count_lbl.configure(text="No voided records found")
                return

            empty_lbl.place_forget()

            tot_count    = 0
            tot_amount   = 0.0
            tot_items    = 0
            for i, r in enumerate(rows):
                tag = "odd" if i % 2 else "even"
                vt = str(r["void_type"] or "").upper()
                if vt == "FULL_ORDER":
                    type_label = "Full Order"
                    amount = float(r["order_original_amount"] or 0.0)
                else:
                    type_label = "Item Void"
                    amount = float(r["item_original_amount"] or 0.0)
                    tot_items += 1
                tot_count  += 1
                tot_amount += amount
                tbl.insert("", tk.END, tags=(tag,), values=(
                    str(r["created_at"])[:16],
                    f"#{r['order_id']}",
                    type_label,
                    str(r["voided_by_username"] or "—"),
                    _money(amount),
                    str(r["reason"] or "—"),
                ))

            kpi_vars[0].set(str(tot_count))
            kpi_vars[1].set(_money(tot_amount))
            kpi_vars[2].set(str(tot_items))
            count_lbl.configure(text=f"{tot_count} voided record{'s' if tot_count != 1 else ''}")

        period_var.trace_add("write", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>", load)
        load()

    # ── Breakdowns tab (ported from dashboard, with date filters) ─────────────
    def _build_breakdowns_tab(self, parent: tk.Frame) -> None:
        """Payment Methods, Dine-In vs Take-Out, and Order Status charts.
        Honours the same Today / Week / Month / Year / Custom date filters as
        the other report tabs and renders matplotlib charts using the brown
        aesthetic palette.
        """
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(2, weight=1)
        outer.columnconfigure(0, weight=1)

        _FILTER_BG = "#f5f0e8"
        _LABEL_FG  = "#3d2b1f"
        _SEL_BG    = "#8c6e3b"
        _SEL_FG    = "white"
        _UNSEL_BG  = _FILTER_BG
        _UNSEL_FG  = _LABEL_FG

        # ── Filter bar (Today / Week / Month / Year + custom date range) ──
        bar = tk.Frame(outer, bg=_FILTER_BG,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))

        tk.Label(bar, text="Period:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)

        period_var = tk.StringVar(value="month")
        _period_btns: dict[str, tk.Button] = {}

        def _set_period(val: str) -> None:
            period_var.set(val)
            for v, b in _period_btns.items():
                b.configure(
                    bg=_SEL_BG if v == val else _UNSEL_BG,
                    fg=_SEL_FG if v == val else _UNSEL_FG,
                )

        for lbl, val in [("Today", "today"), ("This Week", "week"),
                          ("This Month", "month"), ("This Year", "year"),
                          ("All Time", "all")]:
            is_def = (val == "month")
            btn = tk.Button(
                bar, text=lbl, command=lambda v=val: _set_period(v),
                bg=_SEL_BG if is_def else _UNSEL_BG,
                fg=_SEL_FG if is_def else _UNSEL_FG,
                activebackground=_SEL_BG, activeforeground=_SEL_FG,
                relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            btn.pack(side="left", padx=2, pady=8)
            _period_btns[val] = btn

        tk.Label(bar, text="From:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=12,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT, insertwidth=2)
        from_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(from_ent, from_var)

        tk.Label(bar, text="To:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=12,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT, insertwidth=2)
        to_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(to_ent, to_var)

        # ── KPI cards ─────────────────────────────────────────────────────
        kpi_frame = tk.Frame(outer, bg=_BG)
        kpi_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 0))
        for i in range(3):
            kpi_frame.columnconfigure(i, weight=1, uniform="bkdkpi")

        kpi_vars = [tk.StringVar(value="—") for _ in range(3)]
        kpi_labels = ["Completed Orders", "Total Sales", "Payment Methods"]
        kpi_accents = [_SB, _GREEN, THEME["brown"]]
        for i, (lbl, var, accent) in enumerate(zip(kpi_labels, kpi_vars, kpi_accents)):
            pad_left = 0 if i == 0 else 10
            cell = tk.Frame(kpi_frame, bg=_BG)
            cell.grid(row=0, column=i, sticky="nsew", padx=(pad_left, 0))
            card = tk.Frame(cell, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
            card.pack(fill="both", expand=True)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=lbl, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9), anchor="w"
                     ).pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, textvariable=var, bg=_PANEL, fg=accent,
                     font=("Segoe UI", 18, "bold"), anchor="w"
                     ).pack(anchor="w", padx=14, pady=(0, 12))

        # ── Chart grid (3 cards side-by-side, wraps to two rows on narrow widths) ──
        grid_card = tk.Frame(outer, bg=_BG)
        grid_card.grid(row=2, column=0, sticky="nsew", padx=24, pady=12)
        grid_card.rowconfigure(0, weight=1)
        for c in range(3):
            grid_card.columnconfigure(c, weight=1, uniform="bkdcol")

        # Brown palette used across all three charts
        _BROWN_PALETTE = [
            "#6b4a3a", "#8c6e3b", "#a07855", "#b8905c",
            "#c4975a", "#d4a96a", "#e8b87a", "#f0c890",
        ]

        def _make_card(col: int, title: str) -> tuple[tk.Frame, tk.Frame]:
            card = tk.Frame(grid_card, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
            card.grid(row=0, column=col, sticky="nsew",
                      padx=(0 if col == 0 else 8, 0))
            tk.Label(card, text=title, bg=_PANEL, fg=_TEXT,
                     font=("Segoe UI", 11, "bold"), anchor="w"
                     ).pack(anchor="w", padx=14, pady=(12, 4))
            host = tk.Frame(card, bg=_PANEL)
            host.pack(fill="both", expand=True, padx=8, pady=(0, 10))
            return card, host

        _, pay_host    = _make_card(0, "Payment Methods")
        _, otype_host  = _make_card(1, "Dine-In vs Take-Out")
        _, status_host = _make_card(2, "Order Status")

        empty_lbl = tk.Label(outer, text="", bg=_BG, fg=_MUTED,
                              font=("Segoe UI", 9, "italic"))

        # ── Period clause (matches other report tabs) ─────────────────────
        def _date_clause() -> str:
            p = period_var.get()
            df = (from_var.get() or "").strip()
            dt2 = (to_var.get() or "").strip()
            if df and dt2:
                return (f"DATE(datetime,'localtime') BETWEEN "
                        f"DATE('{df}') AND DATE('{dt2}')")
            if p == "today":
                return "DATE(datetime,'localtime') = DATE('now','localtime')"
            if p == "week":
                return "DATE(datetime,'localtime') >= DATE('now','localtime','-6 days')"
            if p == "year":
                return "strftime('%Y',datetime,'localtime') = strftime('%Y','now','localtime')"
            if p == "all":
                return "1=1"
            return "strftime('%Y-%m',datetime,'localtime') = strftime('%Y-%m','now','localtime')"

        # ── Render helpers ────────────────────────────────────────────────
        def _clear(host: tk.Frame) -> None:
            for w in host.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

        def _show_empty(host: tk.Frame, msg: str) -> None:
            _clear(host)
            tk.Label(host, text=msg, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 10, "italic")
                     ).pack(expand=True, fill="both")

        def _draw_bar(host: tk.Frame, labels: list[str], values: list[float],
                      value_fmt) -> None:
            _clear(host)
            if not labels or not any(v > 0 for v in values):
                _show_empty(host, "No data for the selected period.")
                return
            try:
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            except Exception:
                _show_empty(host, "matplotlib not available.")
                return
            fig = Figure(figsize=(5.8, 4.4), dpi=100, constrained_layout=True)
            fig.patch.set_facecolor("#FAFAF8")
            ax = fig.add_subplot(111)
            ax.set_facecolor("#FAFAF8")
            colors = [_BROWN_PALETTE[i % len(_BROWN_PALETTE)]
                      for i in range(len(labels))]
            bars = ax.bar(labels, values, color=colors,
                          edgecolor="none", width=0.62)
            mx = max(values) if values else 1.0
            for b, v in zip(bars, values):
                if v > 0:
                    ax.text(b.get_x() + b.get_width() / 2,
                            v + mx * 0.02,
                            value_fmt(v),
                            ha="center", va="bottom",
                            fontsize=10, color="#3d2b1f",
                            fontweight="bold")
            ax.grid(axis="y", alpha=0.25, color="#cabba0", linestyle="--")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#cabba0")
            ax.spines["bottom"].set_color("#cabba0")
            ax.tick_params(axis="x", colors="#3d2b1f", labelsize=10, rotation=0)
            ax.tick_params(axis="y", colors="#7b6b57", labelsize=9)
            # Headroom above tallest bar so value labels never clip
            ax.set_ylim(0, mx * 1.18 if mx > 0 else 1.0)
            canvas = FigureCanvasTkAgg(fig, master=host)
            canvas.draw_idle()
            canvas.get_tk_widget().pack(fill="both", expand=True)

        def _draw_donut(host: tk.Frame, labels: list[str], values: list[float]) -> None:
            _clear(host)
            if not labels or not any(v > 0 for v in values):
                _show_empty(host, "No data for the selected period.")
                return
            try:
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            except Exception:
                _show_empty(host, "matplotlib not available.")
                return
            fig = Figure(figsize=(5.8, 4.4), dpi=100, constrained_layout=True)
            fig.patch.set_facecolor("#FAFAF8")
            ax = fig.add_subplot(111)
            ax.set_facecolor("#FAFAF8")
            colors = [_BROWN_PALETTE[i % len(_BROWN_PALETTE)]
                      for i in range(len(labels))]
            wedges, _texts, autotexts = ax.pie(
                values, colors=colors,
                autopct=lambda p: f"{p:.1f}%" if p >= 4 else "",
                startangle=90, pctdistance=0.78,
                wedgeprops=dict(linewidth=2, edgecolor="white", width=0.42),
            )
            for at in autotexts:
                at.set_fontsize(10)
                at.set_color("white")
                at.set_fontweight("bold")
            ax.legend(
                wedges,
                [f"{lbl}  ({int(v)})" for lbl, v in zip(labels, values)],
                loc="lower center",
                bbox_to_anchor=(0.5, -0.05),
                ncol=min(3, len(labels)),
                frameon=False, fontsize=10,
            )
            ax.set_aspect("equal")
            canvas = FigureCanvasTkAgg(fig, master=host)
            canvas.draw_idle()
            canvas.get_tk_widget().pack(fill="both", expand=True)

        def _money_short(v: float) -> str:
            v = float(v or 0)
            if v >= 1000:
                return f"₱{v/1000:.1f}k"
            return f"₱{v:.0f}"

        # ── Loader ────────────────────────────────────────────────────────
        def load(*_args):
            dc = _date_clause()
            # Payment methods
            try:
                pay_rows = self.db.fetchall(
                    f"""
                    SELECT COALESCE(NULLIF(payment_method,''), 'Unknown') AS method,
                           COUNT(*)                  AS cnt,
                           COALESCE(SUM(total), 0)   AS total
                    FROM orders
                    WHERE status='Completed' AND {dc}
                    GROUP BY method
                    ORDER BY total DESC;
                    """
                )
                pay_rows = [dict(r) for r in pay_rows]
            except Exception:
                pay_rows = []

            # Dine-In vs Take-Out
            try:
                ot_rows = self.db.fetchall(
                    f"""
                    SELECT COALESCE(NULLIF(order_type,''), 'DINE_IN') AS otype,
                           COUNT(*) AS cnt
                    FROM orders
                    WHERE status='Completed' AND {dc}
                    GROUP BY otype;
                    """
                )
                ot_rows = [dict(r) for r in ot_rows]
            except Exception:
                ot_rows = []

            # Order status (does not filter on Completed because we want all)
            try:
                st_rows = self.db.fetchall(
                    f"""
                    SELECT status, COUNT(*) AS cnt
                    FROM orders
                    WHERE {dc}
                    GROUP BY status;
                    """
                )
                st_rows = [dict(r) for r in st_rows]
            except Exception:
                st_rows = []

            # KPIs
            total_orders = sum(int(r.get("cnt") or 0) for r in pay_rows)
            total_sales  = sum(float(r.get("total") or 0) for r in pay_rows)
            kpi_vars[0].set(str(total_orders))
            kpi_vars[1].set(_money(total_sales))
            kpi_vars[2].set(str(len(pay_rows)))

            # Payment Methods — bar chart with ₱ values
            pm_labels = [str(r.get("method") or "—")[:12] for r in pay_rows]
            pm_values = [float(r.get("total") or 0)        for r in pay_rows]
            _draw_bar(pay_host, pm_labels, pm_values, _money_short)

            # Dine-In vs Take-Out — donut by order count
            ot_map = {(r.get("otype") or "DINE_IN"): int(r.get("cnt") or 0)
                      for r in ot_rows}
            ot_labels = ["Dine-In", "Take-Out"]
            ot_values = [ot_map.get("DINE_IN", 0), ot_map.get("TAKE_OUT", 0)]
            _draw_donut(otype_host, ot_labels, ot_values)

            # Order Status — donut by order count
            preferred = ["Completed", "Pending", "Cancelled"]
            st_map = {str(r.get("status") or ""): int(r.get("cnt") or 0)
                      for r in st_rows}
            st_labels = [k for k in preferred if st_map.get(k, 0) > 0]
            st_values = [st_map[k] for k in st_labels]
            # Include any other status not in preferred list
            for k, v in st_map.items():
                if k and k not in preferred and v > 0:
                    st_labels.append(k)
                    st_values.append(v)
            _draw_donut(status_host, st_labels, st_values)

        period_var.trace_add("write", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>", load)
        load()

    def _build_sales_tab(self, parent: tk.Frame):
        from app.ui.inventory_sales_view import InventorySalesView
        InventorySalesView(parent, self.db, self.auth).pack(fill="both", expand=True)

    # ── Overview tab ──────────────────────────────────────────────────────────

    def _build_reports_tab(self, parent: tk.Frame):
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=_BG, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vsb.set)

        body = tk.Frame(canvas, bg=_BG)
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")

        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))

        def _scroll(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _scroll))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        # KPI cards
        kpi_row = tk.Frame(body, bg=_BG)
        kpi_row.pack(fill="x", padx=24, pady=(16, 8))
        kpi_row.rowconfigure(0, weight=1)

        kpi_data = self._fetch_kpis()
        kpi_cards = [
            ("Today's Sales", _money(kpi_data["today_sales"]), _RED),
            ("This Month",    _money(kpi_data["month_sales"]), _SLATE),
            ("Total Orders",  str(kpi_data["total_orders"]),   _SB),
            ("Avg. Order",    _money(kpi_data["avg_order"]),   _GREEN),
        ]
        for i, (label, val, accent) in enumerate(kpi_cards):
            kpi_row.columnconfigure(i, weight=1, uniform="kpi")
            outer_cell = tk.Frame(kpi_row, bg=_BG)
            outer_cell.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            card = tk.Frame(outer_cell, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
            card.pack(fill="both", expand=True)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=label, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9), anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, text=val, bg=_PANEL, fg=accent,
                     font=("Segoe UI", 18, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

        def _section_hdr(text: str):
            row = tk.Frame(body, bg=_BG)
            row.pack(fill="x", padx=24, pady=(14, 4))
            tk.Label(row, text=text.upper(), bg=_BG, fg=_MUTED,
                     font=("Segoe UI", 8, "bold")).pack(side="left")
            tk.Frame(row, bg=_BORDER, height=1).pack(
                side="left", fill="x", expand=True, padx=(8, 0), pady=6)

        def _alert_card(parent, name, qty, threshold, unit="pcs"):
            row = tk.Frame(parent, bg=_PANEL,
                           highlightthickness=1, highlightbackground=_BORDER)
            row.pack(fill="x", padx=16, pady=2)
            row.columnconfigure(1, weight=1)

            status_color = THEME["danger"] if qty <= 0 else THEME["warning"]
            tag = "OUT" if qty <= 0 else "LOW"
            tk.Label(row, text=f"  {tag}  ", bg=status_color, fg="white",
                     font=("Segoe UI", 7, "bold"),
                     padx=4, pady=3).grid(row=0, column=0, padx=(10, 8), pady=8, sticky="w")
            tk.Label(row, text=name, bg=_PANEL, fg=_TEXT,
                     font=("Segoe UI", 10, "bold"), anchor="w").grid(
                     row=0, column=1, sticky="ew", pady=8)
            tk.Label(row, text=f"{qty} {unit}  (min {threshold})",
                     bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 9)).grid(row=0, column=2, padx=(0, 14), pady=8)

        # Raw Materials Alerts
        _section_hdr("Inventory Alerts — Raw Materials")
        mat_card = tk.Frame(body, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
        mat_card.pack(fill="x", padx=24, pady=(0, 4))
        tk.Frame(mat_card, bg=THEME["warning"], height=3).pack(fill="x")

        low_mats = self._fetch_low_stock_materials()
        if low_mats:
            for m in low_mats:
                unit = m.get("unit", "pcs") or "pcs"
                _alert_card(mat_card, m["name"], m["quantity"], m["low_stock"], unit)
        else:
            tk.Label(mat_card, text="All raw materials have sufficient stock.",
                     bg=_PANEL, fg=_GREEN,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=12)

        # Top Products (summary, all-time)
        _section_hdr("Top Selling Products — All Time")
        top_card = tk.Frame(body, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
        top_card.pack(fill="x", padx=24, pady=(0, 4))
        tk.Frame(top_card, bg=_SLATE, height=3).pack(fill="x")

        top_prods = self._fetch_top_products_alltime()
        if top_prods:
            hdr_row = tk.Frame(top_card, bg=_SB)
            hdr_row.pack(fill="x", padx=16, pady=(6, 0))
            for txt, w in [("Product", 0), ("Units Sold", 100), ("Revenue", 120)]:
                expand = w == 0
                tk.Label(hdr_row, text=txt, bg=_SB, fg="#FFFFFF",
                         font=("Segoe UI", 8, "bold"),
                         anchor="w" if expand else "e",
                         width=0 if expand else w // 8).pack(
                    side="left", fill="x" if expand else None,
                    expand=expand, padx=8, pady=6)
            for p in top_prods:
                r = tk.Frame(top_card, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
                r.pack(fill="x", padx=16, pady=2)
                r.columnconfigure(0, weight=1)
                tk.Label(r, text=p["name"], bg=_PANEL, fg=_TEXT,
                         font=("Segoe UI", 9, "bold"), anchor="w").grid(
                    row=0, column=0, sticky="ew", padx=10, pady=6)
                tk.Label(r, text=str(p["units"]), bg=_PANEL, fg=_MUTED,
                         font=("Segoe UI", 9), width=12, anchor="e").grid(
                    row=0, column=1, padx=4)
                tk.Label(r, text=_money(p["revenue"]), bg=_PANEL, fg=_GREEN,
                         font=("Segoe UI", 9, "bold"), width=14, anchor="e").grid(
                    row=0, column=2, padx=(4, 10))
        else:
            tk.Label(top_card, text="No completed orders yet.",
                     bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=12)

        tk.Frame(body, bg=_BG, height=20).pack()

    # ── Top Sellers tab ───────────────────────────────────────────────────────

    def _build_top_sellers_tab(self, parent: tk.Frame):
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(2, weight=1)   # table row expands; chart sits above
        outer.columnconfigure(0, weight=1)

        _FILTER_BG = "#f5f0e8"
        _LABEL_FG  = "#3d2b1f"

        # Filter bar
        bar = tk.Frame(outer, bg=_FILTER_BG,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))

        tk.Label(bar, text="Period:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)

        period_var = tk.StringVar(value="month")

        _SEL_BG   = "#8c6e3b"
        _SEL_FG   = "white"
        _UNSEL_BG = _FILTER_BG   # "#f5f0e8"
        _UNSEL_FG = _LABEL_FG    # "#3d2b1f"

        _period_btns: dict[str, tk.Button] = {}

        def _set_period(val: str) -> None:
            period_var.set(val)
            for v, b in _period_btns.items():
                b.configure(
                    bg=_SEL_BG if v == val else _UNSEL_BG,
                    fg=_SEL_FG if v == val else _UNSEL_FG,
                )

        periods = [("Today", "today"), ("This Week", "week"),
                   ("This Month", "month"), ("This Year", "year")]
        for lbl, val in periods:
            is_default = val == "month"
            btn = tk.Button(
                bar, text=lbl,
                command=lambda v=val: _set_period(v),
                bg=_SEL_BG   if is_default else _UNSEL_BG,
                fg=_SEL_FG   if is_default else _UNSEL_FG,
                activebackground=_SEL_BG, activeforeground=_SEL_FG,
                relief="flat", bd=0,
                padx=12, pady=5,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            btn.pack(side="left", padx=2, pady=8)
            _period_btns[val] = btn

        # Custom date range
        tk.Label(bar, text="From:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=11,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT, insertwidth=2)
        from_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(from_ent, from_var)

        tk.Label(bar, text="To:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=11,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT, insertwidth=2)
        to_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(to_ent, to_var)

        # ── Quantity Sold chart card (row 1) ───────────────────────────────────
        chart_card = tk.Frame(outer, bg=_PANEL,
                              highlightthickness=1, highlightbackground=_BORDER)
        chart_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 0))
        tk.Frame(chart_card, bg=_GREEN, height=4).pack(fill="x")
        tk.Label(chart_card, text="Quantity Sold — Top Products",
                 bg=_PANEL, fg=_TEXT,
                 font=("Segoe UI", 10, "bold"), anchor="w",
                 ).pack(anchor="w", padx=14, pady=(8, 0))
        chart_host = tk.Frame(chart_card, bg=_PANEL, height=240)
        chart_host.pack(fill="x", padx=10, pady=(4, 10))
        chart_host.pack_propagate(False)
        self._ts_chart_host = chart_host
        self._ts_chart_canvas = None

        # Table
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("TS.Treeview",
                    rowheight=28, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT,
                    borderwidth=0, relief="flat")
        s.configure("TS.Treeview.Heading",
                    font=("Segoe UI", 9, "bold"),
                    background=_SB, foreground="#2B2B2B", relief="flat",
                    padding=(8, 7))
        s.map("TS.Treeview",
              background=[("selected", _RED), ("!selected", _PANEL)],
              foreground=[("selected", "#702C2C"), ("!selected", _TEXT)])

        ts_cols = ("rank", "name", "category", "qty", "revenue")
        tbl = ttk.Treeview(tbl_frame, columns=ts_cols, show="headings",
                           style="TS.Treeview")
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        col_cfg = [
            ("rank",     "#",         50,  "center", False),
            ("name",     "Product",  200,  "w",      True),
            ("category", "Category", 120,  "w",      False),
            ("qty",      "Qty Sold",  90,  "center", False),
            ("revenue",  "Revenue",  100,  "e",      False),
        ]
        _ts_col_labels = {cid: hdr for cid, hdr, *_ in col_cfg}
        for cid, hdr, w, anc, stretch in col_cfg:
            tbl.column(cid, width=w, minwidth=50, anchor=anc, stretch=stretch)

        rank_tags = ["rank1", "rank2", "rank3"]
        tbl.tag_configure("rank1", background="#FFF5F5", foreground="#7f1d1d",
                          font=("Segoe UI", 9, "bold"))
        tbl.tag_configure("rank2", background="#FAFAFA", font=("Segoe UI", 9, "bold"))
        tbl.tag_configure("rank3", background="#FAFAFA", font=("Segoe UI", 9, "bold"))
        tbl.tag_configure("odd",  background=_PANEL)
        tbl.tag_configure("even", background="#FAFAF8")

        # Footer bar
        foot = tk.Frame(outer, bg=_BG)
        foot.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        rows_cache: list[dict] = []
        _ts_sort: dict = {"col": None, "reverse": False}

        def _draw_qty_chart(rows: list[dict]) -> None:
            """Render a horizontal bar chart of top products by qty sold."""
            host = self._ts_chart_host
            if host is None or not host.winfo_exists():
                return
            for w in host.winfo_children():
                w.destroy()
            self._ts_chart_canvas = None
            top = rows[:10]
            if not top:
                tk.Label(host, text="No sales data to chart for this period.",
                         bg=_PANEL, fg=_MUTED,
                         font=("Segoe UI", 10, "italic")
                         ).pack(expand=True)
                return
            try:
                from matplotlib.figure import Figure
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                names = [str(r["name"])[:18] for r in top][::-1]
                qtys  = [int(r["total_qty"] or 0) for r in top][::-1]
                fig = Figure(figsize=(7, 2.4), dpi=92, facecolor=_PANEL)
                ax = fig.add_subplot(111)
                ax.set_facecolor(_PANEL)
                bars = ax.barh(names, qtys, color="#2e7d32", edgecolor="#1b5e20")
                ax.set_xlabel("Qty Sold", fontsize=8, color=_TEXT)
                for spine in ("top", "right"):
                    ax.spines[spine].set_visible(False)
                ax.tick_params(labelsize=8, colors=_TEXT)
                for bar, v in zip(bars, qtys):
                    ax.text(bar.get_width() + max(qtys) * 0.01,
                            bar.get_y() + bar.get_height() / 2,
                            str(v), va="center", fontsize=8, color=_TEXT)
                fig.tight_layout(pad=0.6)
                canvas_widget = FigureCanvasTkAgg(fig, master=host)
                canvas_widget.draw()
                canvas_widget.get_tk_widget().pack(fill="both", expand=True)
                self._ts_chart_canvas = canvas_widget
            except Exception:
                # Fallback: pure-Tkinter bar list when matplotlib unavailable
                max_q = max((int(r["total_qty"] or 0) for r in top), default=1) or 1
                for r in top:
                    fr = tk.Frame(host, bg=_PANEL)
                    fr.pack(fill="x", padx=10, pady=2)
                    tk.Label(fr, text=str(r["name"])[:24], bg=_PANEL, fg=_TEXT,
                             font=("Segoe UI", 8), width=22, anchor="w"
                             ).pack(side="left")
                    bar_outer = tk.Frame(fr, bg="#E8E2D9", height=14)
                    bar_outer.pack(side="left", fill="x", expand=True, padx=6)
                    bar_outer.pack_propagate(False)
                    pct = max(2, int((int(r["total_qty"] or 0) / max_q) * 100))
                    bar = tk.Frame(bar_outer, bg=_GREEN)
                    bar.place(x=0, y=0, relwidth=pct / 100, relheight=1)
                    tk.Label(fr, text=str(int(r["total_qty"] or 0)),
                             bg=_PANEL, fg=_TEXT,
                             font=("Segoe UI", 8, "bold"), width=6, anchor="e"
                             ).pack(side="left")

        def _ts_display(rows: list[dict]) -> None:
            for iid in tbl.get_children():
                tbl.delete(iid)
            if not rows:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                empty_lbl.place_forget()
            for i, r in enumerate(rows, 1):
                tag = rank_tags[i - 1] if i <= 3 else ("odd" if i % 2 else "even")
                tbl.insert("", tk.END, tags=(tag,), values=(
                    f"#{i}", r["name"], r["category"],
                    int(r["total_qty"] or 0), _money(r["total_revenue"]),
                ))
            n = len(rows)
            count_lbl.configure(text=f"{n} product{'s' if n != 1 else ''} shown")

        def _ts_sort_by(col: str) -> None:
            if _ts_sort["col"] == col:
                _ts_sort["reverse"] = not _ts_sort["reverse"]
            else:
                _ts_sort["col"] = col
                _ts_sort["reverse"] = False
            rev = _ts_sort["reverse"]
            ind = "▲" if not rev else "▼"
            for cid, hdr in _ts_col_labels.items():
                tbl.heading(cid, text=(hdr + " " + ind) if cid == col else hdr,
                            anchor="center",
                            command=lambda c=cid: _ts_sort_by(c))
            key_map = {
                "rank": lambda r: float(r.get("total_qty") or 0),
                "name": lambda r: str(r.get("name") or "").lower(),
                "category": lambda r: str(r.get("category") or "").lower(),
                "qty": lambda r: float(r.get("total_qty") or 0),
                "revenue": lambda r: float(r.get("total_revenue") or 0),
            }
            kf = key_map.get(col, lambda r: 0)
            sorted_rows = sorted(rows_cache, key=kf, reverse=rev)
            _ts_display(sorted_rows)

        for cid, hdr, *_ in col_cfg:
            tbl.heading(cid, text=hdr, anchor="center",
                        command=lambda c=cid: _ts_sort_by(c))

        def export():
            if not rows_cache:
                messagebox.showinfo("Export", "No data to export.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="top_sellers.csv",
                title="Save CSV",
            )
            if not path:
                return
            try:
                from datetime import datetime as _datetime
                now_str = _datetime.now().strftime("%Y-%m-%d %H:%M")
                p = period_var.get()
                df_v = from_var.get().strip()
                dt_v = to_var.get().strip()
                period_label = df_v and dt_v and f"{df_v} to {dt_v}" or {
                    "today": "Today", "week": "This Week",
                    "month": "This Month", "year": "This Year"}.get(p, p)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Aissa's Kitchenette"])
                    w.writerow(["Top Sellers Report"])
                    w.writerow([f"Period: {period_label}"])
                    w.writerow([f"Generated: {now_str}"])
                    w.writerow([])
                    w.writerow(["Rank", "Product", "Category", "Qty Sold", "Revenue"])
                    for i, r in enumerate(rows_cache, 1):
                        w.writerow([i, r["name"], r["category"],
                                    r["total_qty"], _money(r["total_revenue"])])
                self._log_report_print("TOP_SELLERS", path)
                messagebox.showinfo("Export", f"Saved to:\n{path}")
            except Exception as e:
                from app.utils import log_error
                log_error("Reports export top sellers", e)
                messagebox.showerror(
                    "Export Error",
                    "Could not save the export file. Please try again.",
                )

        tk.Button(foot, text="Export CSV",
                  bg=THEME["success"], fg="white",
                  activebackground="#16a34a", activeforeground="white",
                  bd=0, padx=12, pady=5, cursor="hand2",
                  font=("Segoe UI", 8, "bold"),
                  command=export).pack(side="right")

        empty_lbl = tk.Label(tbl_frame, text="No sales data for the selected period.",
                              bg=_PANEL, fg=_MUTED,
                              font=("Segoe UI", 11, "italic"))

        def load(*args):
            nonlocal rows_cache
            p = period_var.get()
            df = from_var.get().strip()
            dt = to_var.get().strip()

            if df and dt:
                date_clause = f"DATE(o.datetime) BETWEEN DATE('{df}') AND DATE('{dt}')"
            elif p == "today":
                date_clause = "DATE(o.datetime) = DATE('now','localtime')"
            elif p == "week":
                date_clause = "DATE(o.datetime) >= DATE('now','localtime','-6 days')"
            elif p == "year":
                date_clause = "strftime('%Y',o.datetime) = strftime('%Y','now','localtime')"
            else:
                date_clause = "strftime('%Y-%m',o.datetime) = strftime('%Y-%m','now','localtime')"

            try:
                raw = self.db.fetchall(
                    f"""
                    SELECT p.name,
                           COALESCE(c.name, 'Uncategorized') AS category,
                           SUM(oi.qty)      AS total_qty,
                           SUM(oi.subtotal) AS total_revenue
                    FROM order_items oi
                    JOIN products p  ON p.id = oi.product_id
                    LEFT JOIN categories c ON c.id = p.category_id
                    JOIN orders o    ON o.id = oi.order_id
                    WHERE o.status = 'Completed'
                      AND oi.voided = 0
                      AND {date_clause}
                    GROUP BY p.id, p.name, c.name
                    ORDER BY total_qty DESC
                    LIMIT 50;
                    """
                )
                rows_cache = [dict(r) for r in raw]
            except Exception:
                rows_cache = []

            # Reset sort state on fresh load
            _ts_sort["col"] = None
            _ts_sort["reverse"] = False
            for cid, hdr in _ts_col_labels.items():
                tbl.heading(cid, text=hdr, anchor="center",
                            command=lambda c=cid: _ts_sort_by(c))
            _ts_display(rows_cache)
            _draw_qty_chart(rows_cache)

        period_var.trace_add("write", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>",   load)
        load()

    # ── Discounts Report tab ──────────────────────────────────────────────────

    def _build_discounts_tab(self, parent: tk.Frame):
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(2, weight=1)
        outer.columnconfigure(0, weight=1)

        _FILTER_BG = "#f5f0e8"
        _LABEL_FG  = "#3d2b1f"
        _SEL_BG    = "#8c6e3b"
        _SEL_FG    = "white"
        _UNSEL_BG  = _FILTER_BG
        _UNSEL_FG  = _LABEL_FG

        # ── Filter bar ────────────────────────────────────────────────────────
        bar = tk.Frame(outer, bg=_FILTER_BG,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))

        tk.Label(bar, text="Period:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)

        period_var = tk.StringVar(value="month")
        _period_btns: dict[str, tk.Button] = {}

        def _set_period(val: str) -> None:
            period_var.set(val)
            for v, b in _period_btns.items():
                b.configure(
                    bg=_SEL_BG if v == val else _UNSEL_BG,
                    fg=_SEL_FG if v == val else _UNSEL_FG,
                )

        for lbl, val in [("Today", "today"), ("This Week", "week"),
                          ("This Month", "month"), ("This Year", "year")]:
            is_def = (val == "month")
            btn = tk.Button(bar, text=lbl,
                            command=lambda v=val: _set_period(v),
                            bg=_SEL_BG if is_def else _UNSEL_BG,
                            fg=_SEL_FG if is_def else _UNSEL_FG,
                            activebackground=_SEL_BG, activeforeground=_SEL_FG,
                            relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                            font=("Segoe UI", 9, "bold"))
            btn.pack(side="left", padx=2, pady=8)
            _period_btns[val] = btn

        # Custom date range
        tk.Label(bar, text="From:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=11,
                            bd=0, bg="#FFFFFF", fg=_TEXT,
                            insertbackground=_TEXT, insertwidth=2)
        from_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(from_ent, from_var)

        tk.Label(bar, text="To:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=11,
                          bd=0, bg="#FFFFFF", fg=_TEXT,
                          insertbackground=_TEXT, insertwidth=2)
        to_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(to_ent, to_var)

        # ── Summary KPI row ───────────────────────────────────────────────────
        kpi_frame = tk.Frame(outer, bg=_BG)
        kpi_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 0))
        for i in range(3):
            kpi_frame.columnconfigure(i, weight=1, uniform="dkpi")

        kpi_vars = [tk.StringVar(value="—") for _ in range(3)]
        kpi_labels = ["Discounted Orders", "Total Discount Amount", "Net Discounted Sales"]
        kpi_accents = [_RED, _RED, _GREEN]
        for i, (lbl, var, accent) in enumerate(zip(kpi_labels, kpi_vars, kpi_accents)):
            pad_left = 0 if i == 0 else 10
            outer_c = tk.Frame(kpi_frame, bg=_BG)
            outer_c.grid(row=0, column=i, sticky="nsew", padx=(pad_left, 0))
            card = tk.Frame(outer_c, bg=_PANEL,
                            highlightthickness=1, highlightbackground=_BORDER)
            card.pack(fill="both", expand=True)
            tk.Frame(card, bg=accent, height=4).pack(fill="x")
            tk.Label(card, text=lbl, bg=_PANEL, fg=_MUTED,
                     font=("Segoe UI", 8), anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
            tk.Label(card, textvariable=var, bg=_PANEL, fg=accent,
                     font=("Segoe UI", 18, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

        # ── Breakdown table ───────────────────────────────────────────────────
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=2, column=0, sticky="nsew", padx=24, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("DC.Treeview",
                    rowheight=28, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT,
                    borderwidth=0, relief="flat")
        s.configure("DC.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=_SB, foreground="#2B2B2B", relief="flat", padding=(8, 7))
        s.map("DC.Treeview",
              background=[("selected", _RED), ("!selected", _PANEL)],
              foreground=[("selected", "#FFFFFF"), ("!selected", _TEXT)])

        dc_cols = ("dt", "trx", "type", "discount", "net")
        tbl = ttk.Treeview(tbl_frame, columns=dc_cols, show="headings",
                           style="DC.Treeview")
        tbl.grid(row=0, column=0, sticky="nsew")
        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        for cid, hdr, w, anc, stretch in [
            ("dt",       "Date & Time",     150, "center", False),
            ("trx",      "Transaction #",   110, "center", False),
            ("type",     "Discount Type",   170, "w",      True),
            ("discount", "Discount Amount", 140, "e",      False),
            ("net",      "Net Sales",       140, "e",      False),
        ]:
            tbl.heading(cid, text=hdr, anchor="center")
            tbl.column(cid, width=w, minwidth=60, anchor=anc, stretch=stretch)

        tbl.tag_configure("odd",  background=_PANEL)
        tbl.tag_configure("even", background="#FAFAF8")

        empty_lbl = tk.Label(tbl_frame, text="No discounted orders for the selected period.",
                              bg=_PANEL, fg=_MUTED, font=("Segoe UI", 11, "italic"))

        # Footer
        foot = tk.Frame(outer, bg=_BG)
        foot.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        def _export():
            rows_cache_ref = getattr(_export, "_rows", [])
            if not rows_cache_ref:
                messagebox.showinfo("Export", "No data to export.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="discounts_report.csv",
                title="Save CSV",
            )
            if not path:
                return
            try:
                from datetime import datetime as _dt
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Aissa's Kitchenette", "Discounts Report",
                                f"Generated: {_dt.now().strftime('%Y-%m-%d %H:%M')}"])
                    w.writerow([])
                    w.writerow(["Date & Time", "Transaction #",
                                "Discount Type", "Discount Amount", "Net Sales"])
                    for r in rows_cache_ref:
                        w.writerow([
                            str(r.get("dt") or "")[:16],
                            f"#{r.get('order_id', '')}",
                            r.get("type_label", r.get("discount_type", "")),
                            _money(r.get("discount_amount") or 0),
                            _money(r.get("net_total") or 0),
                        ])
                self._log_report_print("DISCOUNTS", path)
                messagebox.showinfo("Export", f"Saved to:\n{path}")
            except Exception as e:
                from app.utils import log_error
                log_error("Reports export discounts", e)
                messagebox.showerror(
                    "Export Error",
                    "Could not save the export file. Please try again.",
                )

        tk.Button(foot, text="Export CSV",
                  bg=THEME["success"], fg="white",
                  activebackground="#16a34a", activeforeground="white",
                  bd=0, padx=12, pady=5, cursor="hand2",
                  font=("Segoe UI", 8, "bold"),
                  command=_export).pack(side="right")

        _type_labels = {
            "PWD":     "PWD (20%)",
            "SENIOR":  "Senior (20%)",
            "SPECIAL": "Special Discount",
            "NONE":    "No Discount Type",
        }

        def load(*_args):
            from app.db.dao import OrderDAO
            p  = period_var.get()
            df = from_var.get().strip()
            dt_to = to_var.get().strip()
            try:
                raw = OrderDAO(self.db).list_discounted_orders(
                    period=p,
                    date_from=df or None,
                    date_to=dt_to or None,
                )
                rows = []
                for r in raw:
                    row = dict(r)
                    row["type_label"] = _type_labels.get(
                        str(row.get("discount_type") or ""),
                        str(row.get("discount_type") or "—"),
                    )
                    rows.append(row)
            except Exception:
                rows = []

            _export._rows = rows

            for iid in tbl.get_children():
                tbl.delete(iid)

            if not rows:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
                for v in kpi_vars:
                    v.set("—")
                count_lbl.configure(text="No discounted orders found")
                return

            empty_lbl.place_forget()

            total_count    = len(rows)
            total_discount = sum(float(r.get("discount_amount") or 0) for r in rows)
            total_net      = sum(float(r.get("net_total") or 0) for r in rows)

            kpi_vars[0].set(str(total_count))
            kpi_vars[1].set(_money(total_discount))
            kpi_vars[2].set(_money(total_net))

            for i, r in enumerate(rows):
                tag = "odd" if i % 2 else "even"
                tbl.insert("", tk.END, tags=(tag,), values=(
                    str(r.get("dt") or "")[:16],
                    f"#{r.get('order_id', '')}",
                    r["type_label"],
                    _money(r.get("discount_amount") or 0),
                    _money(r.get("net_total") or 0),
                ))

            count_lbl.configure(
                text=f"{total_count} discounted order"
                     f"{'s' if total_count != 1 else ''}"
            )

        period_var.trace_add("write", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>", load)
        load()

    # ── Raw Materials Movement Report tab ─────────────────────────────────────

    def _build_raw_materials_tab(self, parent: tk.Frame):
        outer = tk.Frame(parent, bg=_BG)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        _FILTER_BG  = "#f5f0e8"   # warm beige for filter bar
        _LABEL_FG   = "#3d2b1f"   # dark brown — high contrast on beige

        # Filter bar
        bar = tk.Frame(outer, bg=_FILTER_BG,
                       highlightthickness=1, highlightbackground=_BORDER)
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 0))

        # Date period
        tk.Label(bar, text="Period:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 6), pady=8)
        period_var = tk.StringVar(value="month")

        _SEL_BG   = "#8c6e3b"
        _SEL_FG   = "white"
        _UNSEL_BG = _FILTER_BG   # "#f5f0e8"
        _UNSEL_FG = _LABEL_FG    # "#3d2b1f"

        _period_btns: dict[str, tk.Button] = {}

        def _set_period(val: str) -> None:
            period_var.set(val)
            for v, b in _period_btns.items():
                b.configure(
                    bg=_SEL_BG if v == val else _UNSEL_BG,
                    fg=_SEL_FG if v == val else _UNSEL_FG,
                )

        for lbl, val in [("Today", "today"), ("This Week", "week"),
                          ("This Month", "month"), ("This Year", "year")]:
            is_default = val == "month"
            btn = tk.Button(
                bar, text=lbl,
                command=lambda v=val: _set_period(v),
                bg=_SEL_BG   if is_default else _UNSEL_BG,
                fg=_SEL_FG   if is_default else _UNSEL_FG,
                activebackground=_SEL_BG, activeforeground=_SEL_FG,
                relief="flat", bd=0,
                padx=12, pady=5,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            )
            btn.pack(side="left", padx=2, pady=8)
            _period_btns[val] = btn

        # Custom from/to
        tk.Label(bar, text="From:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 4), pady=8)
        from_var = tk.StringVar()
        from_ent = tk.Entry(bar, textvariable=from_var, width=11,
                            bd=0, bg=THEME["panel2"], fg=_TEXT,
                            insertbackground=_TEXT, insertwidth=2)
        from_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(from_ent, from_var)
        tk.Label(bar, text="To:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=8)
        to_var = tk.StringVar()
        to_ent = tk.Entry(bar, textvariable=to_var, width=11,
                          bd=0, bg=THEME["panel2"], fg=_TEXT,
                          insertbackground=_TEXT, insertwidth=2)
        to_ent.pack(side="left", ipady=5, pady=8)
        _bind_date_picker(to_ent, to_var)

        # Type and Action filters — same bar, separated by a divider
        tk.Frame(bar, bg=_BORDER, width=1, height=30).pack(side="left", padx=10, pady=4)

        tk.Label(bar, text="Type:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 4), pady=8)
        type_var = tk.StringVar(value="All")
        type_cb = ttk.Combobox(bar, textvariable=type_var,
                               values=["All", "DRY", "WET"],
                               state="readonly", width=7)
        type_cb.pack(side="left", padx=(0, 10), pady=8)

        tk.Label(bar, text="Action:", bg=_FILTER_BG, fg=_LABEL_FG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4), pady=8)
        action_var = tk.StringVar(value="All")
        action_cb = ttk.Combobox(bar, textvariable=action_var,
                                 values=["All", "ADD", "DEDUCT", "Initial"],
                                 state="readonly", width=9)
        action_cb.pack(side="left", padx=(0, 10), pady=8)

        # Table
        tbl_frame = tk.Frame(outer, bg=_PANEL,
                             highlightthickness=1, highlightbackground=_BORDER)
        tbl_frame.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        s = ttk.Style()
        s.configure("RM.Treeview",
                    rowheight=28, font=("Segoe UI", 9),
                    background=_PANEL, fieldbackground=_PANEL, foreground=_TEXT,
                    borderwidth=0, relief="flat")
        s.configure("RM.Treeview.Heading",
                    font=("Segoe UI", 9, "bold"),
                    background=_SB, foreground="#703131", relief="flat",
                    padding=(8, 7))
        s.map("RM.Treeview",
              background=[("selected", _RED), ("!selected", _PANEL)],
              foreground=[("selected", "#752B2B"), ("!selected", _TEXT)])

        rm_cols = ("dt", "material", "mat_type", "action", "qty_change", "notes")
        tbl = ttk.Treeview(tbl_frame, columns=rm_cols, show="headings",
                           style="RM.Treeview")
        tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        tbl.configure(yscrollcommand=ysb.set)

        xsb = ttk.Scrollbar(tbl_frame, orient="horizontal", command=tbl.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        tbl.configure(xscrollcommand=xsb.set)

        rm_col_cfg = [
            ("dt",         "Date & Time",     140, "center", False),
            ("material",   "Material Name",   180, "w",      True),
            ("mat_type",   "Type",             70, "center", False),
            ("action",     "Action",           90, "center", False),
            ("qty_change", "Qty Change",      100, "center", False),
            ("notes",      "Notes/Reason",    180, "w",      True),
        ]
        _rm_col_labels = {cid: hdr for cid, hdr, *_ in rm_col_cfg}
        for cid, hdr, w, anc, stretch in rm_col_cfg:
            tbl.column(cid, width=w, minwidth=60, anchor=anc, stretch=stretch)

        tbl.tag_configure("add",    foreground="#16a34a")
        tbl.tag_configure("deduct", foreground=THEME["danger"])
        tbl.tag_configure("odd",    background=_PANEL)
        tbl.tag_configure("even",   background="#FAFAF8")

        # Footer
        foot = tk.Frame(outer, bg=_BG)
        foot.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        count_lbl = tk.Label(foot, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        count_lbl.pack(side="left")

        rows_cache: list[dict] = []
        _rm_sort: dict = {"col": None, "reverse": False}

        def _rm_display(rows: list[dict]) -> None:
            for iid in tbl.get_children():
                tbl.delete(iid)
            if not rows:
                empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                empty_lbl.place_forget()
            for i, r in enumerate(rows):
                act = r["action_type"] or ""
                sign = "+" if act in ("ADD", "Initial") else "-"
                qty_disp = f"{sign}{r['quantity']}"
                color_tag = "add" if sign == "+" else "deduct"
                row_tag   = "odd" if i % 2 else "even"
                tbl.insert("", tk.END, tags=(color_tag, row_tag), values=(
                    str(r["created_at"])[:16],
                    r["name"], r["material_type"], act, qty_disp,
                    r["reason"] or "",
                ))
            n = len(rows)
            count_lbl.configure(text=f"{n} record{'s' if n != 1 else ''} shown")

        def _rm_sort_by(col: str) -> None:
            if _rm_sort["col"] == col:
                _rm_sort["reverse"] = not _rm_sort["reverse"]
            else:
                _rm_sort["col"] = col
                _rm_sort["reverse"] = False
            rev = _rm_sort["reverse"]
            ind = "▲" if not rev else "▼"
            for cid, hdr in _rm_col_labels.items():
                tbl.heading(cid, text=(hdr + " " + ind) if cid == col else hdr,
                            anchor="center",
                            command=lambda c=cid: _rm_sort_by(c))
            key_map = {
                "dt":         lambda r: str(r.get("created_at") or ""),
                "material":   lambda r: str(r.get("name") or "").lower(),
                "mat_type":   lambda r: str(r.get("material_type") or "").lower(),
                "action":     lambda r: str(r.get("action_type") or "").lower(),
                "qty_change": lambda r: float(r.get("quantity") or 0),
                "notes":      lambda r: str(r.get("reason") or "").lower(),
            }
            kf = key_map.get(col, lambda r: "")
            sorted_rows = sorted(rows_cache, key=kf, reverse=rev)
            _rm_display(sorted_rows)

        for cid, hdr, *_ in rm_col_cfg:
            tbl.heading(cid, text=hdr, anchor="center",
                        command=lambda c=cid: _rm_sort_by(c))

        def export():
            if not rows_cache:
                messagebox.showinfo("Export", "No data to export.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="raw_materials_movement.csv",
                title="Save CSV",
            )
            if not path:
                return
            try:
                from datetime import datetime as _datetime
                now_str = _datetime.now().strftime("%Y-%m-%d %H:%M")
                p = period_var.get()
                df_v = from_var.get().strip()
                dt_v = to_var.get().strip()
                period_label = df_v and dt_v and f"{df_v} to {dt_v}" or {
                    "today": "Today", "week": "This Week",
                    "month": "This Month", "year": "This Year"}.get(p, p)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["Aissa's Kitchenette"])
                    w.writerow(["Raw Materials Movement Report"])
                    w.writerow([f"Period: {period_label}"])
                    w.writerow([f"Generated: {now_str}"])
                    w.writerow([])
                    w.writerow(["Date & Time", "Material", "Type",
                                "Action", "Qty Change", "Notes"])
                    for r in rows_cache:
                        act = r["action_type"]
                        sign = "+" if act in ("ADD", "Initial") else "-"
                        w.writerow([
                            str(r["created_at"])[:16],
                            r["name"], r["material_type"],
                            act, f"{sign}{r['quantity']}",
                            r["reason"] or "",
                        ])
                self._log_report_print("RAW_MATERIALS", path)
                messagebox.showinfo("Export", f"Saved to:\n{path}")
            except Exception as e:
                from app.utils import log_error
                log_error("Reports export raw materials", e)
                messagebox.showerror(
                    "Export Error",
                    "Could not save the export file. Please try again.",
                )

        tk.Button(foot, text="Export CSV",
                  bg=THEME["success"], fg="white",
                  activebackground="#16a34a", activeforeground="white",
                  bd=0, padx=12, pady=5, cursor="hand2",
                  font=("Segoe UI", 8, "bold"),
                  command=export).pack(side="right")

        empty_lbl = tk.Label(tbl_frame, text="No raw material movements for the selected period.",
                              bg=_PANEL, fg=_MUTED,
                              font=("Segoe UI", 11, "italic"))

        def load(*args):
            nonlocal rows_cache
            p = period_var.get()
            df = from_var.get().strip()
            dt = to_var.get().strip()

            if df and dt:
                date_clause = f"DATE(rml.created_at) BETWEEN DATE('{df}') AND DATE('{dt}')"
            elif p == "today":
                date_clause = "DATE(rml.created_at) = DATE('now','localtime')"
            elif p == "week":
                date_clause = "DATE(rml.created_at) >= DATE('now','localtime','-6 days')"
            elif p == "year":
                date_clause = "strftime('%Y',rml.created_at) = strftime('%Y','now','localtime')"
            else:
                date_clause = "strftime('%Y-%m',rml.created_at) = strftime('%Y-%m','now','localtime')"

            type_filter   = type_var.get()
            action_filter = action_var.get()

            extra = ""
            if type_filter != "All":
                extra += f" AND rm.material_type = '{type_filter}'"
            if action_filter != "All":
                extra += f" AND rml.action_type = '{action_filter}'"

            try:
                raw = self.db.fetchall(
                    f"""
                    SELECT rml.created_at,
                           rm.name,
                           rm.material_type,
                           rml.action_type,
                           rml.quantity,
                           rml.reason
                    FROM raw_material_logs rml
                    JOIN raw_materials rm ON rm.id = rml.material_id
                    WHERE {date_clause}{extra}
                    ORDER BY rml.created_at DESC
                    LIMIT 500;
                    """
                )
                rows_cache = [dict(r) for r in raw]
            except Exception:
                rows_cache = []

            # Reset sort state on fresh load
            _rm_sort["col"] = None
            _rm_sort["reverse"] = False
            for cid, hdr in _rm_col_labels.items():
                tbl.heading(cid, text=hdr, anchor="center",
                            command=lambda c=cid: _rm_sort_by(c))
            _rm_display(rows_cache)

        period_var.trace_add("write", load)
        type_cb.bind("<<ComboboxSelected>>",   load)
        action_cb.bind("<<ComboboxSelected>>", load)
        from_ent.bind("<Return>", load)
        to_ent.bind("<Return>",   load)
        load()

    # ── Data fetchers ──────────────────────────────────────────────────────────

    def _fetch_kpis(self) -> dict:
        result = {"today_sales": 0, "month_sales": 0, "total_orders": 0, "avg_order": 0}
        try:
            row = self.db.fetchone(
                "SELECT COALESCE(SUM(total),0) AS s FROM orders "
                "WHERE DATE(datetime)=DATE('now','localtime') AND status='Completed';"
            )
            if row:
                result["today_sales"] = float(row["s"] or 0)
        except Exception:
            pass
        try:
            row = self.db.fetchone(
                "SELECT COALESCE(SUM(total),0) AS s FROM orders "
                "WHERE strftime('%Y-%m',datetime)=strftime('%Y-%m','now','localtime') "
                "AND status='Completed';"
            )
            if row:
                result["month_sales"] = float(row["s"] or 0)
        except Exception:
            pass
        try:
            row = self.db.fetchone(
                "SELECT COUNT(*) AS c, COALESCE(AVG(total),0) AS a FROM orders WHERE status='Completed';"
            )
            if row:
                result["total_orders"] = int(row["c"] or 0)
                result["avg_order"] = float(row["a"] or 0)
        except Exception:
            pass
        return result

    def _fetch_low_stock_products(self) -> list:
        """Only returns products that have stock tracking enabled (low_stock > 0)."""
        try:
            rows = self.db.fetchall(
                "SELECT name, stock, low_stock FROM products "
                "WHERE active=1 AND low_stock > 0 AND stock <= low_stock "
                "ORDER BY stock ASC LIMIT 20;"
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _fetch_low_stock_materials(self) -> list:
        try:
            rows = self.db.fetchall(
                "SELECT name, quantity, low_stock, unit FROM raw_materials "
                "WHERE active=1 AND quantity <= low_stock "
                "ORDER BY quantity ASC LIMIT 20;"
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _fetch_top_products_alltime(self) -> list:
        """Top sellers across all time — used by Overview tab."""
        try:
            rows = self.db.fetchall(
                """
                SELECT p.name,
                       SUM(oi.qty)      AS units,
                       SUM(oi.subtotal) AS revenue
                FROM order_items oi
                JOIN products p ON p.id = oi.product_id
                JOIN orders o   ON o.id = oi.order_id
                WHERE o.status = 'Completed' AND oi.voided = 0
                GROUP BY p.id, p.name
                ORDER BY units DESC LIMIT 10;
                """
            )
            return [dict(r) for r in rows]
        except Exception:
            return []
