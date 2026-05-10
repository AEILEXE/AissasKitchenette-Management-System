from __future__ import annotations

import calendar as _cal
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO, DraftDAO  # VoidDialog also uses void_completed_order / void_order_item
from app.services.auth_service import AuthService
from app.services.receipt_service import ReceiptService
from app.ui import ui_scale
from app.ui.dialogs import show_toast
from app.utils import money
from app.constants import P_VOID


# ── Pure-Tkinter date picker ──────────────────────────────────────────────────

class DatePickerDialog(tk.Toplevel):
    """
    Minimal pure-Tkinter month-calendar date picker.
    After wait_window() returns, check .result for the chosen 'YYYY-MM-DD'
    string, or None if the dialog was cancelled.
    """

    _DAY_HEADERS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

    def __init__(self, parent: tk.Widget, initial: str | None = None):
        super().__init__(parent)
        self.result: str | None = None

        today = datetime.today()
        try:
            d = datetime.fromisoformat(initial) if initial else today
        except Exception:
            d = today

        self._year  = d.year
        self._month = d.month

        self.title("Select Date")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._day_frame: tk.Frame | None  = None
        self._lbl_month: tk.Label | None  = None

        self._build()

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = max(self.winfo_reqwidth()  + 28, 300)
        h  = max(self.winfo_reqheight() + 28, 280)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self.wait_window()

    def _build(self):
        outer = tk.Frame(self, bg=THEME["bg"])
        outer.pack(fill="both", expand=True, padx=14, pady=10)

        # ── Navigation row ─────────────────────────────────────────────────
        nav = tk.Frame(outer, bg=THEME["bg"])
        nav.pack(fill="x", pady=(0, 6))

        tk.Button(
            nav, text=" < ", bd=0, cursor="hand2",
            bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 10), padx=8, pady=4,
            command=self._prev_month,
        ).pack(side="left")

        self._lbl_month = tk.Label(
            nav, bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", 11, "bold"), width=20, anchor="center",
        )
        self._lbl_month.pack(side="left", fill="x", expand=True)

        tk.Button(
            nav, text=" > ", bd=0, cursor="hand2",
            bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 10), padx=8, pady=4,
            command=self._next_month,
        ).pack(side="right")

        # ── Day-of-week headers ────────────────────────────────────────────
        hdr_row = tk.Frame(outer, bg=THEME["bg"])
        hdr_row.pack(fill="x")
        for col, txt in enumerate(self._DAY_HEADERS):
            tk.Label(
                hdr_row, text=txt,
                bg=THEME["bg"], fg=THEME["muted"],
                font=("Segoe UI", 8, "bold"), width=4, anchor="center",
            ).grid(row=0, column=col, padx=2, pady=(0, 4))

        # ── Day grid ──────────────────────────────────────────────────────
        self._day_frame = tk.Frame(outer, bg=THEME["bg"])
        self._day_frame.pack(fill="both")

        # ── Footer ────────────────────────────────────────────────────────
        foot = tk.Frame(outer, bg=THEME["bg"])
        foot.pack(fill="x", pady=(8, 0))

        tk.Button(
            foot, text="Today", bd=0, cursor="hand2",
            bg=THEME["panel2"], fg=THEME["text"],
            padx=10, pady=5,
            command=self._go_today,
        ).pack(side="left")

        tk.Button(
            foot, text="Cancel", bd=0, cursor="hand2",
            bg=THEME["panel2"], fg=THEME["text"],
            padx=10, pady=5,
            command=self.destroy,
        ).pack(side="right")

        self._render_days()
        self.bind("<Escape>", lambda _e: self.destroy(), add="+")

    def _render_days(self):
        if self._day_frame is None:
            return
        for w in self._day_frame.winfo_children():
            w.destroy()

        y, m = self._year, self._month
        self._lbl_month.config(text=f"{_cal.month_name[m]}  {y}")

        today                = datetime.today()
        _, num_days          = _cal.monthrange(y, m)
        first_wd             = _cal.weekday(y, m, 1)   # 0 = Monday

        col = first_wd
        row = 0
        for day in range(1, num_days + 1):
            is_today = (y == today.year and m == today.month and day == today.day)
            btn = tk.Button(
                self._day_frame,
                text=str(day),
                width=3, bd=0,
                padx=2, pady=5,
                cursor="hand2",
                font=("Segoe UI", 9, "bold" if is_today else "normal"),
                bg=THEME["brown"] if is_today else THEME["panel2"],
                fg="white"        if is_today else THEME["text"],
                activebackground=THEME["brown_dark"],
                activeforeground="white",
                command=lambda d=day: self._pick(d),
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _pick(self, day: int):
        self.result = f"{self._year:04d}-{self._month:02d}-{day:02d}"
        self.destroy()

    def _prev_month(self):
        self._month -= 1
        if self._month < 1:
            self._month = 12
            self._year -= 1
        self._render_days()

    def _next_month(self):
        self._month += 1
        if self._month > 12:
            self._month = 1
            self._year += 1
        self._render_days()

    def _go_today(self):
        today       = datetime.today()
        self._year  = today.year
        self._month = today.month
        self._render_days()


# ── TRANSACTIONS VIEW ─────────────────────────────────────────────────────────

class TransactionsView(tk.Frame):
    _POLL_INTERVAL_MS = 3000  # poll every 3 seconds

    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db   = db
        self.auth = auth
        self.orders = OrderDAO(db)
        self.drafts = DraftDAO(db)

        self.var_search  = tk.StringVar()
        self.var_status  = tk.StringVar(value="All")
        self.var_payment = tk.StringVar(value="All")
        self.var_from    = tk.StringVar()
        self.var_to      = tk.StringVar()

        self._search_after = None
        self._tx_sort: dict = {"col": None, "reverse": False}
        self._tx_rows_cache: list = []

        self._poll_after: int | None = None
        self._poll_version: int = -1

        # entry refs for placeholder restore
        self.ent_search: tk.Entry | None = None
        self.ent_from:   tk.Entry | None = None
        self.ent_to:     tk.Entry | None = None

        self._build()
        self.refresh()
        self._start_polling()
        self.bind("<Destroy>", lambda _e: self._cancel_poll())

    # ── polling ───────────────────────────────────────────────────────────────

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
        if not self.winfo_exists():
            return
        # Only refresh when this view is actually visible
        if self.winfo_ismapped():
            try:
                v = self.db.get_data_version()
                if v != self._poll_version:
                    self._poll_version = v
                    self.refresh()
            except Exception:
                pass
        self._poll_after = self.after(self._POLL_INTERVAL_MS, self._poll_tick)

    # ── placeholder helpers ───────────────────────────────────────────────────

    def _clear_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
            widget.config(fg=THEME["text"])

    def _restore_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(fg=THEME["muted"])

    def _apply_search_placeholder(self):
        if not self.ent_search:
            return
        self.ent_search.delete(0, tk.END)
        self.ent_search.insert(0, "Search transaction ID…")
        self.ent_search.config(fg=THEME["muted"])

    def _apply_date_placeholders(self):
        for ent in (self.ent_from, self.ent_to):
            if ent and ent.get().strip() == "":
                ent.insert(0, "YYYY-MM-DD")
                ent.config(fg=THEME["muted"])

    def _debounced_refresh(self):
        if self._search_after is not None:
            try:
                self.after_cancel(self._search_after)
            except Exception:
                pass
        self._search_after = self.after(160, self.refresh)

    def _clear_all(self):
        self.var_search.set("")
        self.var_status.set("All")
        self.var_payment.set("All")
        self.var_from.set("")
        self.var_to.set("")

        self._apply_search_placeholder()

        if self.ent_from:
            self.ent_from.delete(0, tk.END)
        if self.ent_to:
            self.ent_to.delete(0, tk.END)
        self._apply_date_placeholders()

        self.refresh()

    # ── calendar picker (pure Tkinter) ────────────────────────────────────────

    def _open_date_picker(self, target_entry: tk.Entry, which: str):
        """Open the pure-Tkinter DatePickerDialog and apply chosen date."""
        raw     = target_entry.get().strip()
        initial = raw if (raw and raw != "YYYY-MM-DD") else None

        dlg = DatePickerDialog(self, initial=initial)
        d   = dlg.result
        if d is None:
            return  # Cancelled

        if which == "from":
            self.var_from.set(d)
        else:
            self.var_to.set(d)

        target_entry.delete(0, tk.END)
        target_entry.insert(0, d)
        target_entry.config(fg=THEME["text"])
        self._debounced_refresh()

    def _clear_date(self, target_entry: tk.Entry, which: str):
        """Clear a date filter."""
        if which == "from":
            self.var_from.set("")
        else:
            self.var_to.set("")
        target_entry.delete(0, tk.END)
        target_entry.insert(0, "YYYY-MM-DD")
        target_entry.config(fg=THEME["muted"])
        self._debounced_refresh()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        style = ttk.Style()
        style.configure(
            "Tx.Treeview",
            font=("Segoe UI", 10),
            rowheight=30,
            background=THEME["panel"],
            fieldbackground=THEME["panel"],
            foreground="#222222",
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Tx.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=THEME["panel2"],
            foreground=THEME["text"],
            relief="flat",
            padding=(10, 12),
        )
        style.map("Tx.Treeview.Heading", background=[("active", THEME["panel2"])])
        style.map(
            "Tx.Treeview",
            background=[("selected", "#5C3D2E"), ("!selected", THEME["panel"])],
            foreground=[("selected", "#FFFFFF"), ("!selected", "#222222")],
        )

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Title
        tk.Label(
            self,
            text="Transactions",
            bg=THEME["bg"],
            fg=THEME["text"],
            font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 10))

        # ── Filter bar ────────────────────────────────────────────────────────
        bar = tk.Frame(
            self,
            bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["panel2"],
        )
        bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
        bar.columnconfigure(0, weight=1)

        row = tk.Frame(bar, bg=THEME["panel"])
        row.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=0)

        # Search pill
        search_box = tk.Frame(row, bg=THEME["panel2"])
        search_box.grid(row=0, column=0, sticky="ew")
        search_box.columnconfigure(1, weight=1)

        tk.Label(search_box, bg=THEME["panel2"], fg=THEME["muted"]).grid(
            row=0, column=0, padx=(10, 6)
        )

        self.ent_search = tk.Entry(
            search_box,
            textvariable=self.var_search,
            bd=0,
            bg=THEME["panel2"],
            fg=THEME["text"],
            insertbackground="#3d2b1f",
            insertwidth=2,
        )
        self.ent_search.grid(row=0, column=1, sticky="ew", ipady=8, padx=(0, 10))

        self._apply_search_placeholder()
        self.ent_search.bind(
            "<FocusIn>",
            lambda e: self._clear_placeholder(self.ent_search, "Search transaction ID…"),
        )
        self.ent_search.bind(
            "<FocusOut>",
            lambda e: self._restore_placeholder(self.ent_search, "Search transaction ID…"),
        )
        self.ent_search.bind("<KeyRelease>", lambda _e: self._debounced_refresh())

        # Filters group
        group = tk.Frame(row, bg=THEME["panel"])
        group.grid(row=0, column=1, sticky="e", padx=(12, 0))

        def mini_label(parent, text):
            return tk.Label(
                parent, text=text,
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", 9),
            )

        def pill_date(parent, textvariable, which: str, col: int):
            """Date pill with entry + calendar button."""
            pill = tk.Frame(parent, bg=THEME["panel2"])

            ent = tk.Entry(
                pill,
                textvariable=textvariable,
                bd=0,
                bg=THEME["panel2"],
                fg=THEME["text"],
                insertbackground="#3d2b1f",
                insertwidth=2,
                width=12,
            )
            ent.pack(side="left", fill="x", expand=True, padx=(10, 2), ipady=8)

            tk.Button(
                pill, text="...",
                bg=THEME["panel2"], fg=THEME["muted"],
                bd=0, padx=6, pady=6, cursor="hand2",
                command=lambda: self._open_date_picker(ent, which),
            ).pack(side="right", padx=(0, 4))

            ent.insert(0, "YYYY-MM-DD")
            ent.config(fg=THEME["muted"])
            ent.bind("<FocusIn>",  lambda e: self._clear_placeholder(ent, "YYYY-MM-DD"))
            ent.bind("<FocusOut>", lambda e: self._restore_placeholder(ent, "YYYY-MM-DD"))
            ent.bind("<KeyRelease>", lambda _e: self._debounced_refresh())
            ent.bind("<Return>",     lambda _e: self._debounced_refresh())

            return pill, ent

        mini_label(group, "Status").grid(row=0, column=0, sticky="w")
        cmb_status = ttk.Combobox(
            group,
            textvariable=self.var_status,
            values=["All", "Pending", "Cancelled", "Completed"],
            state="readonly",
            width=12,
        )
        cmb_status.grid(row=1, column=0, padx=(0, 10), sticky="w")
        cmb_status.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        mini_label(group, "Payment").grid(row=0, column=1, sticky="w")
        cmb_pay = ttk.Combobox(
            group,
            textvariable=self.var_payment,
            values=["All", "Cash", "Bank/E-Wallet"],
            state="readonly",
            width=14,
        )
        cmb_pay.grid(row=1, column=1, padx=(0, 10), sticky="w")
        cmb_pay.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        mini_label(group, "From").grid(row=0, column=2, sticky="w")
        from_pill, self.ent_from = pill_date(group, self.var_from, "from", col=2)
        from_pill.grid(row=1, column=2, padx=(0, 10), sticky="w")

        mini_label(group, "To").grid(row=0, column=3, sticky="w")
        to_pill, self.ent_to = pill_date(group, self.var_to, "to", col=3)
        to_pill.grid(row=1, column=3, padx=(0, 10), sticky="w")

        tk.Button(
            group,
            text="Clear",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=14, pady=8, cursor="hand2",
            command=self._clear_all,
        ).grid(row=1, column=4, sticky="w")

        # ── Table card ────────────────────────────────────────────────────────
        table_card = tk.Frame(
            self, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["panel2"],
        )
        table_card.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(0, weight=1)

        # FIX B: updated column order — ID | PAYMENT | CASHIER | CUSTOMER | PAID | CHANGE | ITEMS | STATUS | TOTAL | START | END | View
        cols = ("id", "payment", "cashier", "customer", "paid", "change", "items", "status", "total", "start", "end", "details")
        self.tbl = ttk.Treeview(table_card, columns=cols, show="headings", style="Tx.Treeview")
        self.tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(table_card, orient="vertical", command=self.tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self.tbl.configure(yscrollcommand=ysb.set)

        self._empty_lbl = tk.Label(
            table_card, text="No transactions yet",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", 13),
        )

        # (id, heading, width, anchor, stretch, minwidth)
        col_cfg = [
            ("id",      "ID",        50, "center", False,  40),
            ("payment", "PAYMENT",  140, "w",      False,  90),
            ("cashier", "CASHIER",  100, "w",      False,  70),
            ("customer","CUSTOMER", 160, "w",      True,   90),
            ("paid",    "PAID",     100, "e",      False,  70),
            ("change",  "CHANGE",   100, "e",      False,  70),
            ("items",   "ITEMS",     55, "center", False,  40),
            ("status",  "STATUS",    90, "center", False,  70),
            ("total",   "TOTAL",    100, "e",      False,  70),
            ("start",   "START",    140, "center", False, 100),
            ("end",     "END",      140, "center", False,  70),
            ("details", "",          55, "center", False,  40),
        ]

        for cid, hdr, width, anchor, stretch, minw in col_cfg:
            if cid != "details":
                self.tbl.heading(cid, text=hdr, anchor="center",
                                 command=lambda c=cid: self._tx_sort_by(c))
            else:
                self.tbl.heading(cid, text=hdr, anchor="center")
            self.tbl.column(cid, width=width, anchor=anchor, stretch=stretch, minwidth=minw)

        _row_font  = ("Segoe UI", 10)
        _dark_text = "#1A1A1A"   # near-black — high contrast on any light bg

        # ── Status row tags ───────────────────────────────────────────────────
        # Each tag uses an explicit dark foreground so date/time columns are
        # always readable regardless of the Windows native Treeview renderer.
        self.tbl.tag_configure("row_completed",
                               background="#F0FFF4", foreground=_dark_text,
                               font=_row_font)
        self.tbl.tag_configure("row_pending",
                               background="#FEF3C7", foreground="#92400E",
                               font=("Segoe UI", 10, "bold"))
        self.tbl.tag_configure("row_cancelled",
                               background="#FFE4E4", foreground="#991B1B",
                               font=_row_font)

        # ── Highlight tags ────────────────────────────────────────────────────
        self.tbl.tag_configure("top_sale",
                               background="#FEFCE8", foreground=_dark_text,
                               font=("Segoe UI", 10, "bold"))
        self.tbl.tag_configure("latest_sale",
                               background="#EFF6FF", foreground=_dark_text,
                               font=_row_font)
        self.tbl.tag_configure("top_and_latest",
                               background="#FEF9C3", foreground=_dark_text,
                               font=("Segoe UI", 10, "bold"))

        self.tbl.bind("<Double-Button-1>",  lambda _e: self.open_selected())
        self.tbl.bind("<Return>",           lambda _e: self.open_selected())
        self.tbl.bind("<ButtonRelease-1>",  self._on_tbl_click)

        # ── Bottom action bar ─────────────────────────────────────────────────
        action_bar = tk.Frame(
            table_card, bg=THEME["panel2"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        action_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        action_bar.columnconfigure(0, weight=1)

        self._count_var = tk.StringVar(value="")
        tk.Label(
            action_bar, textvariable=self._count_var,
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=7)

        tk.Button(
            action_bar, text="View Details  ▶",
            bg=THEME["brown"], fg="white",
            activebackground=THEME["brown_dark"], activeforeground="white",
            bd=0, padx=16, pady=6, cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            command=self._open_selected_from_btn,
        ).grid(row=0, column=1, sticky="e", padx=12, pady=6)

    # ── data ──────────────────────────────────────────────────────────────────

    # Badge-style display labels for the STATUS column (display only — DB values unchanged)
    _STATUS_BADGE: dict[str, str] = {
        "completed": "✔  Completed",
        "pending":   "⏳  Pending",
        "cancelled": "✗  Cancelled",
    }

    def refresh(self):
        q         = self.var_search.get().replace("Search transaction ID…", "").strip()
        status    = self.var_status.get()
        payment   = self.var_payment.get()
        date_from = self.var_from.get().replace("YYYY-MM-DD", "").strip()
        date_to   = self.var_to.get().replace("YYYY-MM-DD", "").strip()

        self._tx_rows_cache = list(self.orders.list_orders(q, status, payment, date_from, date_to))
        self._tx_apply_sort_and_display()

    def _tx_apply_sort_and_display(self) -> None:
        rows = list(self._tx_rows_cache)
        col  = self._tx_sort["col"]
        rev  = self._tx_sort["reverse"]
        if col:
            _key: dict = {
                "id":       lambda r: int(r.get("order_id") or 0),
                "payment":  lambda r: str(r.get("payment_method") or "").lower(),
                "cashier":  lambda r: str(r.get("cashier_username") or "").lower(),
                "customer": lambda r: str(r.get("customer_name") or "").lower(),
                "paid":     lambda r: float(r.get("amount_paid") or 0),
                "change":   lambda r: float(r.get("change_due") or 0),
                "items":    lambda r: int(r.get("items_count") or 0),
                "status":   lambda r: str(r.get("status") or "").lower(),
                "total":    lambda r: float(r.get("total") or 0),
                "start":    lambda r: str(r.get("start_dt") or ""),
                "end":      lambda r: str(r.get("end_dt") or ""),
            }
            rows = sorted(rows, key=_key.get(col, lambda r: 0), reverse=rev)
        self._tx_populate(rows)

    def _tx_sort_by(self, col: str) -> None:
        if self._tx_sort["col"] == col:
            self._tx_sort["reverse"] = not self._tx_sort["reverse"]
        else:
            self._tx_sort["col"] = col
            self._tx_sort["reverse"] = False
        rev = self._tx_sort["reverse"]
        ind = " ▲" if not rev else " ▼"
        _col_labels = {
            "id": "ID", "payment": "PAYMENT", "cashier": "CASHIER",
            "customer": "CUSTOMER", "paid": "PAID", "change": "CHANGE",
            "items": "ITEMS", "status": "STATUS", "total": "TOTAL",
            "start": "START", "end": "END",
        }
        for cid, lbl in _col_labels.items():
            self.tbl.heading(cid, text=(lbl + ind) if cid == col else lbl,
                             anchor="center", command=lambda c=cid: self._tx_sort_by(c))
        self._tx_apply_sort_and_display()

    def _tx_populate(self, rows: list) -> None:
        for iid in self.tbl.get_children():
            self.tbl.delete(iid)

        top_id     = None
        latest_id  = None
        best_total = None
        best_dt    = None

        for r in rows:
            oid = int(r["order_id"])
            try:
                total = float(r["total"] or 0.0)
            except Exception:
                total = 0.0
            dt_str = str(r["start_dt"] or "") or str(r["end_dt"] or "")
            dt = None
            try:
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                pass
            if best_total is None or total > best_total:
                best_total = total
                top_id = oid
            if dt is not None and (best_dt is None or dt > best_dt):
                best_dt = dt
                latest_id = oid

        for r in rows:
            oid = int(r["order_id"])
            status_str = str(r["status"] or "").lower()
            if status_str == "pending":
                status_tag = "row_pending"
            elif status_str == "cancelled":
                status_tag = "row_cancelled"
            else:
                status_tag = "row_completed"

            if status_tag in ("row_pending", "row_cancelled"):
                if top_id == oid and latest_id == oid:
                    tag = ("top_and_latest", status_tag)
                elif top_id == oid:
                    tag = ("top_sale", status_tag)
                elif latest_id == oid:
                    tag = ("latest_sale", status_tag)
                else:
                    tag = (status_tag,)
            else:
                if top_id == oid and latest_id == oid:
                    tag = (status_tag, "top_and_latest")
                elif top_id == oid:
                    tag = (status_tag, "top_sale")
                elif latest_id == oid:
                    tag = (status_tag, "latest_sale")
                else:
                    tag = (status_tag,)

            end_val      = str(r["end_dt"] or "")
            raw_status   = str(r["status"] or "")
            badge_status = self._STATUS_BADGE.get(raw_status.lower(), raw_status)

            self.tbl.insert(
                "", tk.END,
                iid=str(oid),
                tags=tag,
                values=(
                    oid,
                    str(r["payment_method"] or ""),
                    str(r["cashier_username"] or "Unknown"),
                    str(r["customer_name"] or ""),
                    money(r["amount_paid"]),
                    money(r["change_due"]),
                    int(r["items_count"]),
                    badge_status,
                    money(r["total"]),
                    str(r["start_dt"] or ""),
                    end_val,
                    "View ▶",
                ),
            )

        n = len(rows)
        if hasattr(self, "_count_var"):
            self._count_var.set(f"{n} transaction{'s' if n != 1 else ''} shown")
        if hasattr(self, "_empty_lbl"):
            if n == 0:
                self._empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                self._empty_lbl.place_forget()

    def _on_tbl_click(self, event: tk.Event) -> None:
        """Open transaction details when the View column cell is clicked."""
        region = self.tbl.identify_region(event.x, event.y)
        if region != "cell":
            return
        col_id = self.tbl.identify_column(event.x)
        cols = self.tbl["columns"]
        try:
            idx = int(col_id.lstrip("#")) - 1
            if cols[idx] == "details":
                self.open_selected()
        except (ValueError, IndexError):
            pass

    def open_selected(self):
        sel = self.tbl.selection()
        if not sel:
            return
        oid = int(sel[0])
        TransactionDetailsDialog(self, self.db, oid, auth=self.auth, on_refresh=self.refresh)

    def _open_selected_from_btn(self):
        """Called by the View Details button — shows a message if nothing is selected."""
        if not self.tbl.selection():
            messagebox.showinfo(
                "No Selection",
                "Select a transaction row first, then click View Details.",
            )
            return
        self.open_selected()

    def set_status_filter(self, status: str) -> None:
        """Pre-select a status filter and refresh — called from dashboard cards."""
        self.var_status.set(status)
        self.refresh()


# ── TRANSACTION DETAILS DIALOG ────────────────────────────────────────────────

class TransactionDetailsDialog(tk.Toplevel):
    MAX_COLLAPSED_ROWS = 5
    SCROLL_SPEED_UNITS = 3

    def __init__(self, parent: tk.Widget, db: Database, order_id: int,
                 auth: AuthService | None = None, on_refresh=None):
        super().__init__(parent)
        self.db         = db
        self.order_id   = order_id
        self.auth       = auth
        self.on_refresh = on_refresh
        self.orders     = OrderDAO(db)

        self.title("Transaction Details")
        self.configure(bg=THEME["bg"])
        self.geometry("640x600")
        self.minsize(580, 520)

        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())

        self._details_expanded = tk.BooleanVar(value=False)
        self._details_rows: list[tuple[str, str]] = []
        self._discount_amount: float = 0.0
        self._total_amount: float    = 0.0

        self._build()

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(760, sw - 120)
        h  = min(700, sh - 140)
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        data = self.orders.get_order(self.order_id)
        if not data:
            messagebox.showerror("Not found", "Transaction not found.")
            self.destroy()
            return

        items = self.orders.get_order_items(self.order_id)

        # ── Scrollable shell ──────────────────────────────────────────────────
        wrap = tk.Frame(self, bg=THEME["bg"])
        wrap.pack(fill="both", expand=True)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(wrap, bg=THEME["bg"], highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=sb.set)

        self.inner = tk.Frame(self.canvas, bg=THEME["bg"])
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
            add="+",
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(win, width=e.width),
            add="+",
        )

        def _mw(e):
            try:
                step = -1 if e.delta > 0 else 1
                self.canvas.yview_scroll(step * self.SCROLL_SPEED_UNITS, "units")
            except tk.TclError:
                pass

        for w in (self, wrap, self.canvas, self.inner):
            w.bind("<MouseWheel>", _mw, add="+")
            w.bind("<Button-4>",
                   lambda e: self.canvas.yview_scroll(-self.SCROLL_SPEED_UNITS, "units"), add="+")
            w.bind("<Button-5>",
                   lambda e: self.canvas.yview_scroll(self.SCROLL_SPEED_UNITS, "units"), add="+")

        # ── Title row ─────────────────────────────────────────────────────────
        top = tk.Frame(self.inner, bg=THEME["bg"])
        top.pack(fill="x", padx=18, pady=(16, 8))

        tk.Label(
            top, text="Transaction Details",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", f(15), "bold"),
        ).pack(side="left")

        status    = str(data["status"])
        badge_bg  = (
            THEME["success"] if status == "Completed" else
            THEME["danger"]  if status == "Cancelled" else
            "#d97706"
        )
        tk.Label(
            top, text=f"  {status}  ",
            bg=badge_bg, fg="white",
            font=("Segoe UI", f(9), "bold"),
            padx=sp(6), pady=sp(3),
        ).pack(side="right")

        # ── Info card ─────────────────────────────────────────────────────────
        info_card = tk.Frame(
            self.inner, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        info_card.pack(fill="x", padx=18, pady=(0, 10))

        card_hdr = tk.Frame(info_card, bg=THEME["beige"])
        card_hdr.pack(fill="x")
        tk.Label(
            card_hdr, text="Order Information",
            bg=THEME["beige"], fg=THEME["text"],
            font=("Segoe UI", f(9), "bold"),
            padx=14, pady=8,
        ).pack(side="left")
        tk.Label(
            card_hdr, text=f"#{self.order_id}",
            bg=THEME["beige"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
            padx=14,
        ).pack(side="right")

        def info_line(label: str, value: str, bold_val: bool = False):
            r = tk.Frame(info_card, bg=THEME["panel"])
            r.pack(fill="x", padx=14, pady=sp(5))
            tk.Label(
                r, text=label,
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", f(9)),
                width=18, anchor="w",
            ).pack(side="left")
            tk.Label(
                r, text=value,
                bg=THEME["panel"], fg=THEME["text"],
                font=("Segoe UI", f(9), "bold") if bold_val else ("Segoe UI", f(9)),
                anchor="w",
            ).pack(side="left")

        _ot = str(data["order_type"] if "order_type" in data.keys() else "DINE_IN").strip().upper()
        _tbl = str(data["table_number"] if "table_number" in data.keys() else "").strip()
        if not _tbl:
            _tbl = str(data["customer_name"] or "—").strip() or "—"
        _loc_label = "Order No." if _ot == "TAKE_OUT" else "Table No."

        info_line("Order Start:", str(data["start_dt"]))
        info_line("Order End:",   str(data["end_dt"] or ""))
        info_line("Cashier:",     str(data["cashier_username"]))
        info_line(f"{_loc_label}:", _tbl, bold_val=True)
        info_line("Payment:",     str(data["payment_method"]))

        ref = ""
        try:
            ref = str(data["reference_no"] or "").strip()
        except Exception:
            ref = ""
        # Always show reference number; show "—" when not yet generated
        info_line("Reference No.:", ref if ref else "—")

        tk.Frame(info_card, bg=THEME["border"], height=1).pack(fill="x", padx=14, pady=4)

        def money_line(label: str, value: str, accent: bool = False):
            r = tk.Frame(info_card, bg=THEME["panel"])
            r.pack(fill="x", padx=14, pady=sp(4))
            tk.Label(
                r, text=label,
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", f(9)), anchor="w",
            ).pack(side="left")
            tk.Label(
                r, text=value,
                bg=THEME["panel"],
                fg=THEME["success"] if accent else THEME["text"],
                font=("Segoe UI", f(9), "bold") if accent else ("Segoe UI", f(9)),
                anchor="e",
            ).pack(side="right")

        money_line("Amount Paid:", money(data["amount_paid"]))
        money_line("Change Due:",  money(data["change_due"]))

        tk.Frame(info_card, bg=THEME["bg"], height=sp(4)).pack()

        # ── Build item rows ───────────────────────────────────────────────────
        self._details_rows = []
        for it in items:
            name = it["name"] if it["name"] else f"#{it['product_id']}"
            qty  = it["qty"]
            self._details_rows.append((f"{qty}\u00d7 {name}", money(it["subtotal"])))

        try:
            self._discount_amount = float(data["discount"] or 0.0)
        except Exception:
            self._discount_amount = 0.0
        try:
            self._total_amount = float(data["total"] or 0.0)
        except Exception:
            self._total_amount = 0.0

        # ── Order Details collapsible card ────────────────────────────────────
        od_card = tk.Frame(
            self.inner, bg="#ffffff",
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        od_card.pack(fill="x", padx=18, pady=(0, 10))

        od_hdr = tk.Frame(od_card, bg=THEME["beige"])
        od_hdr.pack(fill="x")

        tk.Label(
            od_hdr, text="Order Details",
            bg=THEME["beige"], fg=THEME["text"],
            font=("Segoe UI", f(9), "bold"),
            padx=14, pady=8,
        ).pack(side="left")

        self.btn_toggle = tk.Button(
            od_hdr, text="\u25b8 Show",
            bg=THEME["beige"], fg=THEME["brown"],
            bd=0, padx=14, pady=8, cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._toggle_details,
        )
        self.btn_toggle.pack(side="right")

        self.details_body = tk.Frame(od_card, bg="#ffffff")
        self.details_body.pack(fill="x", padx=12, pady=10)
        self._render_details()

        # ── Footer buttons ────────────────────────────────────────────────────
        footer = tk.Frame(self.inner, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=(4, 16))

        can_void = self.auth.has_permission(P_VOID) if self.auth else False

        if status == "Pending":
            tk.Button(
                footer, text="Resolve",
                bg="#d97706", fg="white",
                activebackground="#b45309", activeforeground="white",
                bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
                font=("Segoe UI", f(9), "bold"),
                command=self._open_resolve,
            ).pack(side="left")

            if can_void:
                tk.Button(
                    footer, text="Void / Cancel",
                    bg=THEME["danger"], fg="white",
                    activebackground="#7f1d1d", activeforeground="white",
                    bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
                    font=("Segoe UI", f(9), "bold"),
                    command=self._open_void,
                ).pack(side="left", padx=(sp(8), 0))

        elif status == "Completed" and can_void:
            tk.Button(
                footer, text="Void Order",
                bg=THEME["danger"], fg="white",
                activebackground="#7f1d1d", activeforeground="white",
                bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
                font=("Segoe UI", f(9), "bold"),
                command=self._open_void_completed,
            ).pack(side="left")

        tk.Button(
            footer, text="Close",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
            font=("Segoe UI", f(9)),
            command=self.destroy,
        ).pack(side="right")

        tk.Button(
            footer, text="Print Receipt",
            bg=THEME["brown"], fg="white",
            activebackground=THEME["brown_dark"], activeforeground="white",
            bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._print_receipt,
        ).pack(side="right", padx=(0, sp(8)))

        self.bind("<Escape>", lambda _e: self.destroy(), add="+")

    def _toggle_details(self):
        self._details_expanded.set(not self._details_expanded.get())
        self._render_details()

    def _render_details(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        for w in self.details_body.winfo_children():
            w.destroy()

        expanded = self._details_expanded.get()
        self.btn_toggle.configure(text="\u25be Hide" if expanded else "\u25b8 Show")

        rows = self._details_rows if expanded else self._details_rows[:self.MAX_COLLAPSED_ROWS]
        for left_text, right_text in rows:
            r = tk.Frame(self.details_body, bg="#ffffff")
            r.pack(fill="x", pady=sp(4))
            tk.Label(
                r, text=left_text,
                bg="#ffffff", fg=THEME["text"],
                font=("Segoe UI", f(9)),
            ).pack(side="left")
            tk.Label(
                r, text=right_text,
                bg="#ffffff", fg=THEME["text"],
                font=("Segoe UI", f(9)),
            ).pack(side="right")

        if not expanded and len(self._details_rows) > self.MAX_COLLAPSED_ROWS:
            tk.Label(
                self.details_body,
                text=f"+ {len(self._details_rows) - self.MAX_COLLAPSED_ROWS} more items",
                bg="#ffffff", fg=THEME["muted"],
                font=("Segoe UI", f(8), "italic"),
            ).pack(anchor="w", pady=(sp(4), 0))

        if self._discount_amount > 0:
            drow = tk.Frame(self.details_body, bg="#ffffff")
            drow.pack(fill="x", pady=(sp(8), 0))
            tk.Label(
                drow, text="Discount",
                bg="#ffffff", fg=THEME["muted"],
                font=("Segoe UI", f(9)),
            ).pack(side="left")
            tk.Label(
                drow, text=f"\u2212{money(self._discount_amount)}",
                bg="#ffffff", fg=THEME["danger"],
                font=("Segoe UI", f(9), "bold"),
            ).pack(side="right")

        sep = tk.Frame(self.details_body, bg=THEME["border"], height=1)
        sep.pack(fill="x", pady=(sp(8), 0))

        tot = tk.Frame(self.details_body, bg=THEME["success"])
        tot.pack(fill="x", pady=(sp(2), 0))
        tk.Label(
            tot, text="TOTAL",
            bg=THEME["success"], fg="white",
            font=("Segoe UI", f(9), "bold"),
            padx=sp(12), pady=sp(9),
        ).pack(side="left")
        tk.Label(
            tot, text=money(self._total_amount),
            bg=THEME["success"], fg="white",
            font=("Segoe UI", f(13), "bold"),
            padx=sp(12), pady=sp(9),
        ).pack(side="right")

    def _open_resolve(self):
        ResolveDialog(self, self.db, self.order_id, on_done=self._resolved)

    def _resolved(self):
        if self.on_refresh:
            self.on_refresh()
        self.destroy()

    def _open_void(self):
        """Void/cancel a Pending order after permission + confirmation check."""
        if not (self.auth and self.auth.has_permission(P_VOID)):
            messagebox.showerror("Access Denied",
                                 "You do not have permission to void / cancel transactions.")
            return
        if not messagebox.askyesno(
            "Void / Cancel Transaction",
            f"Are you sure you want to VOID order #{self.order_id}?\n\n"
            "This will void/cancel the order. This cannot be undone.",
            icon="warning",
        ):
            return
        try:
            self.orders.cancel_order(self.order_id)
            messagebox.showinfo("Voided",
                                f"Order #{self.order_id} has been cancelled.")
            if self.on_refresh:
                self.on_refresh()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Void Failed", f"Could not void order:\n{exc}")

    def _open_void_completed(self):
        """Open the VoidDialog to void a Completed order (full or per-item)."""
        if not (self.auth and self.auth.has_permission(P_VOID)):
            messagebox.showerror("Access Denied",
                                 "You do not have permission to void transactions.")
            return
        VoidDialog(
            self, self.db, self.order_id, self.auth,
            on_done=self._void_done,
        )

    def _void_done(self):
        if self.on_refresh:
            self.on_refresh()
        self.destroy()

    def _print_receipt(self):
        try:
            data  = self.orders.get_order(self.order_id)
            items = self.orders.get_order_items(self.order_id)
            if not data:
                messagebox.showerror("Receipt", "Order not found.")
                return

            order_dict = {k: data[k]   for k in data.keys()}
            items_list = [{k: item[k]  for k in item.keys()} for item in items]

            _u = self.auth.get_current_user() if getattr(self, "auth", None) else None
            _by = (getattr(_u, "username", "") or "") if _u else ""
            receipt_path = ReceiptService.generate_receipt(
                order_dict, items_list, printed_by=_by
            )
            ok = ReceiptService.print_file(receipt_path)
            try:
                import os as _os
                u = self.auth.get_current_user() if getattr(self, "auth", None) else None
                self.db.log_print(
                    user_id=getattr(u, "user_id", None),
                    username=getattr(u, "username", "") or "",
                    print_type="RECEIPT",
                    reference_id=str(self.order_id),
                    detail=_os.path.basename(receipt_path),
                )
            except Exception:
                pass
            if not ok:
                if messagebox.askyesno(
                    "Receipt",
                    "Could not send the receipt directly to a printer.\n\n"
                    f"Receipt was saved to:\n{receipt_path}\n\n"
                    "Open the file for manual print preview?",
                ):
                    ReceiptService.open_file(receipt_path)
        except Exception as e:
            from app.utils import log_error
            log_error("Transactions print receipt", e)
            messagebox.showerror(
                "Receipt Error",
                "Could not generate the receipt. Please try again.",
            )


# ── RESOLVE DIALOG ────────────────────────────────────────────────────────────

class ResolveDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, db: Database, order_id: int, on_done=None):
        super().__init__(parent)
        self.db       = db
        self.order_id = order_id
        self.on_done  = on_done
        self.orders   = OrderDAO(db)

        self.title("Resolve Transaction")
        self.configure(bg=THEME["bg"])
        self.geometry("520x260")
        self.transient(parent)
        self.grab_set()

        self.var_ref = tk.StringVar()
        self._build()

    def _clear_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
            widget.config(fg=THEME["text"])

    def _restore_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(fg=THEME["muted"])

    def _build(self):
        tk.Label(
            self, text="Resolve Transaction",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=18, pady=(14, 6))

        tk.Label(
            self, text="Resolve by providing payment reference number.",
            bg=THEME["bg"], fg=THEME["muted"],
        ).pack(anchor="w", padx=18, pady=(0, 10))

        box = tk.Frame(self, bg=THEME["panel2"])
        box.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        tk.Label(
            box, text="Reference Number:",
            bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=14, pady=(14, 4))

        ent_ref = tk.Entry(box, textvariable=self.var_ref, bd=0, bg="white", fg=THEME["text"],
                           insertbackground="#3d2b1f", insertwidth=2)
        ent_ref.pack(fill="x", padx=14, pady=(0, 14), ipady=8)

        ent_ref.insert(0, "Reference No.")
        ent_ref.config(fg=THEME["muted"])
        ent_ref.bind("<FocusIn>",  lambda e: self._clear_placeholder(ent_ref, "Reference No."))
        ent_ref.bind("<FocusOut>", lambda e: self._restore_placeholder(ent_ref, "Reference No."))

        footer = tk.Frame(self, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=(0, 14))

        tk.Button(
            footer, text="Close",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=12, pady=8, cursor="hand2",
            command=self.destroy,
        ).pack(side="right")

        tk.Button(
            footer, text="Cancel transaction",
            bg=THEME["danger"], fg="white",
            bd=0, padx=12, pady=8, cursor="hand2",
            command=self._cancel,
        ).pack(side="right", padx=(0, 10))

        tk.Button(
            footer, text="Complete transaction",
            bg=THEME["success"], fg="white",
            bd=0, padx=12, pady=8, cursor="hand2",
            command=self._complete,
        ).pack(side="right", padx=(0, 10))

        self.bind("<Return>", lambda _e: self._complete(), add="+")
        self.bind("<Escape>", lambda _e: self.destroy(), add="+")

    def _complete(self):
        ref = self.var_ref.get().strip()
        if not ref or ref == "Reference No.":
            messagebox.showerror("Reference", "Reference number is required.")
            return

        from app.validators import validate_reference_no, REFERENCE_ERROR_MSG
        if not validate_reference_no(ref):
            messagebox.showerror("Invalid Reference", REFERENCE_ERROR_MSG)
            return

        if self.orders.reference_exists(ref, exclude_order_id=self.order_id):
            messagebox.showerror(
                "Duplicate Reference",
                f"Reference number '{ref}' is already used by another transaction.\n"
                "Please enter a different reference number.",
            )
            return

        data = self.orders.get_order(self.order_id)
        if not data:
            messagebox.showerror("Error", "Order not found.")
            return

        total = float(data["total"] or 0.0)
        try:
            self.orders.resolve_pending(self.order_id, ref, total)
        except Exception as exc:
            messagebox.showerror("Resolve Failed", f"Could not resolve order:\n{exc}")
            return

        # Show in-app receipt popup after resolve (no auto-opening browser/PDF)
        try:
            from app.ui.pos_view import ReceiptPreviewDialog
            fresh = self.orders.get_order(self.order_id)
            raw_order = self.db.fetchone(
                "SELECT * FROM orders WHERE id=?;", (int(self.order_id),)
            )
            items = self.orders.get_order_items(self.order_id)
            if fresh:
                order_dict = {k: fresh[k] for k in fresh.keys()}
                if raw_order:
                    for k in raw_order.keys():
                        if raw_order[k] is not None:
                            order_dict[k] = raw_order[k]
                items_list = [{k: item[k] for k in item.keys()} for item in items]
                ReceiptPreviewDialog(self.winfo_toplevel(), order_dict, items_list)
        except Exception:
            pass  # Receipt failure must not block the resolve flow

        if self.on_done:
            self.on_done()
        self.destroy()

    def _cancel(self):
        confirmed = messagebox.askyesno(
            "Cancel Transaction",
            f"Cancel order #{self.order_id}?\n\n"
            "This will void/cancel the order. This cannot be undone.",
            icon="warning",
        )
        if not confirmed:
            return
        try:
            self.orders.cancel_order(self.order_id)
        except Exception as e:
            messagebox.showerror(
                "Cancel Failed",
                f"Could not cancel order #{self.order_id}.\n\n{e}",
            )
            return
        if self.on_done:
            self.on_done()
        self.destroy()


# ── VOID DIALOG ───────────────────────────────────────────────────────────────

class VoidDialog(tk.Toplevel):
    """Allow voiding individual items or the entire completed order."""

    def __init__(
        self,
        parent: tk.Widget,
        db: Database,
        order_id: int,
        auth: AuthService | None,
        on_done=None,
    ):
        super().__init__(parent)
        self.db       = db
        self.order_id = order_id
        self.auth     = auth
        self.on_done  = on_done
        self.orders   = OrderDAO(db)

        self.title(f"Void Transaction — Order #{order_id}")
        self.configure(bg=THEME["bg"])
        self.geometry("560x500")
        self.resizable(False, True)
        self.transient(parent)
        self.grab_set()

        self._item_vars: dict[int, tk.BooleanVar] = {}
        self._items: list = []
        self._build()

    def _build(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        # Header
        hdr = tk.Frame(self, bg=THEME["danger"], padx=sp(16), pady=sp(10))
        hdr.pack(fill="x")
        tk.Label(
            hdr, text=f"Void Order #{self.order_id}",
            bg=THEME["danger"], fg="white",
            font=("Segoe UI", f(12), "bold"),
        ).pack(anchor="w")
        tk.Label(
            hdr, text="Select items to void, or void the entire order.",
            bg=THEME["danger"], fg="#fecaca",
            font=("Segoe UI", f(9)),
        ).pack(anchor="w")

        # Items list
        list_frame = tk.Frame(self, bg=THEME["panel"],
                              highlightthickness=1,
                              highlightbackground=THEME["border"])
        list_frame.pack(fill="both", expand=True, padx=sp(16), pady=(sp(12), sp(6)))

        canvas = tk.Canvas(list_frame, bg=THEME["panel"], bd=0, highlightthickness=0)
        sb     = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=THEME["panel"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

        # Column headers
        hrow = tk.Frame(inner, bg=THEME["beige"])
        hrow.pack(fill="x", padx=sp(4), pady=(sp(4), 0))
        tk.Label(hrow, text="", bg=THEME["beige"], width=3).pack(side="left")
        tk.Label(hrow, text="Item", bg=THEME["beige"], fg=THEME["muted"],
                 font=("Segoe UI", f(8), "bold")).pack(side="left", padx=(sp(4), 0))
        tk.Label(hrow, text="Price", bg=THEME["beige"], fg=THEME["muted"],
                 font=("Segoe UI", f(8), "bold")).pack(side="right", padx=sp(8))
        tk.Label(hrow, text="Qty", bg=THEME["beige"], fg=THEME["muted"],
                 font=("Segoe UI", f(8), "bold")).pack(side="right", padx=(0, sp(8)))

        try:
            raw_items = self.orders.get_order_items_with_void(self.order_id) or []
            self._items = [dict(row) for row in raw_items]
        except Exception:
            self._items = []

        for item in self._items:
            item_id  = int(item["item_id"])
            voided   = bool(item.get("voided", 0))
            name     = str(item.get("name") or f"Item #{item_id}")
            qty      = int(item.get("qty") or 0)
            price    = float(item.get("unit_price") or 0)
            subtotal = qty * price

            row_bg = "#fef2f2" if voided else THEME["panel"]
            row_cursor = "" if voided else "hand2"
            row = tk.Frame(inner, bg=row_bg, cursor=row_cursor)
            row.pack(fill="x", padx=sp(4), pady=sp(1))

            var = tk.BooleanVar(value=False)
            self._item_vars[item_id] = var

            cb = tk.Checkbutton(
                row, variable=var,
                bg=row_bg, activebackground=row_bg,
                state="disabled" if voided else "normal",
            )
            cb.pack(side="left", padx=(sp(4), 0))

            name_text = f"{name}" + ("  [Voided]" if voided else "")
            lbl_name = tk.Label(
                row, text=name_text,
                bg=row_bg,
                fg=THEME["muted"] if voided else THEME["text"],
                font=("Segoe UI", f(9), "overstrike" if voided else "normal"),
                cursor=row_cursor,
            )
            lbl_name.pack(side="left", padx=(sp(4), 0))

            lbl_price = tk.Label(
                row, text=money(subtotal),
                bg=row_bg,
                fg=THEME["muted"] if voided else THEME["text"],
                font=("Segoe UI", f(9)),
                cursor=row_cursor,
            )
            lbl_price.pack(side="right", padx=sp(8))

            lbl_qty = tk.Label(
                row, text=f"×{qty}",
                bg=row_bg,
                fg=THEME["muted"],
                font=("Segoe UI", f(9)),
                cursor=row_cursor,
            )
            lbl_qty.pack(side="right", padx=(0, sp(8)))

            if not voided:
                def _toggle(_e, v=var): v.set(not v.get())
                for w in (row, lbl_name, lbl_price, lbl_qty):
                    w.bind("<Button-1>", _toggle)

        # Reason
        reason_frame = tk.Frame(self, bg=THEME["bg"])
        reason_frame.pack(fill="x", padx=sp(16), pady=(sp(4), sp(8)))
        tk.Label(
            reason_frame,
            text="Reason  (manager will be asked to confirm):",
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", f(9)),
        ).pack(anchor="w")
        self.var_reason = tk.StringVar()
        tk.Entry(
            reason_frame, textvariable=self.var_reason,
            bg="white", fg=THEME["text"],
            bd=1, relief="solid",
            font=("Segoe UI", f(9)),
            insertbackground="#3d2b1f", insertwidth=2,
        ).pack(fill="x", ipady=sp(5), pady=(sp(4), 0))

        # Footer buttons
        footer = tk.Frame(self, bg=THEME["bg"])
        footer.pack(fill="x", padx=sp(16), pady=(0, sp(14)))

        tk.Button(
            footer, text="Void Entire Order",
            bg=THEME["danger"], fg="white",
            activebackground="#7f1d1d", activeforeground="white",
            bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._void_full,
        ).pack(side="left")

        tk.Button(
            footer, text="Void Selected Items",
            bg="#b45309", fg="white",
            activebackground="#92400e", activeforeground="white",
            bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._void_items,
        ).pack(side="left", padx=(sp(8), 0))

        tk.Button(
            footer, text="Close",
            bg=THEME["panel"], fg=THEME["text"],
            bd=1, padx=sp(14), pady=sp(9), cursor="hand2",
            font=("Segoe UI", f(9)),
            command=self.destroy,
        ).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy(), add="+")

    def _get_actor(self) -> tuple[int, str]:
        if self.auth:
            u = getattr(self.auth, "get_current_user", lambda: None)()
            if u:
                return int(u.user_id or 0), str(u.username or "")
        return 0, ""

    def _require_manager_approval(self, action_label: str) -> dict | None:
        """
        If current user already has approval rights, skip prompt.
        Otherwise open the manager approval dialog and return its result.
        Returns None when the action should be aborted.
        """
        try:
            from app.constants import (
                ROLE_ADMIN, ROLE_MANAGER, P_VOID_APPROVE,
            )
            u = self.auth.get_current_user() if self.auth else None
            role = (getattr(u, "role", "") or "").upper()
            if role in (ROLE_ADMIN, ROLE_MANAGER):
                return {
                    "approver_id":       int(getattr(u, "user_id", 0) or 0),
                    "approver_username": getattr(u, "username", "") or "",
                    "approver_role":     role,
                    "reason":             self.var_reason.get().strip(),
                }
            try:
                if self.auth and self.auth.rbac_dao.has_permission(role, P_VOID_APPROVE):
                    return {
                        "approver_id":       int(getattr(u, "user_id", 0) or 0),
                        "approver_username": getattr(u, "username", "") or "",
                        "approver_role":     role,
                        "reason":             self.var_reason.get().strip(),
                    }
            except Exception:
                pass
        except Exception:
            pass

        from app.ui.dialogs import ManagerApprovalDialog
        dlg = ManagerApprovalDialog(
            self, self.auth, action_label=action_label, require_reason=True,
        )
        self.wait_window(dlg)
        return dlg.result

    def _void_full(self):
        actor_id, actor_name = self._get_actor()
        if not actor_id:
            messagebox.showerror("Error", "Cannot verify current user.")
            return
        if not messagebox.askyesno(
            "Void Entire Order",
            f"Void ALL items in order #{self.order_id}?\n\n"
            "This will void/cancel the order. This cannot be undone.",
            icon="warning",
        ):
            return

        approval = self._require_manager_approval(
            f"voiding order #{self.order_id}"
        )
        if not approval:
            return
        # Apply approver's reason if cashier left it blank
        if not self.var_reason.get().strip() and approval.get("reason"):
            self.var_reason.set(approval["reason"])

        reason = self.var_reason.get().strip()
        try:
            self.orders.void_completed_order(
                self.order_id, actor_id, actor_name, reason
            )
            try:
                from app.db.dao import AuditLogDAO as _ALD
                _approver = approval.get("approver_username", "") or actor_name
                _ALD(self.db).log(
                    username=actor_name, action="VOID_ORDER",
                    detail=(f"order_id={self.order_id} "
                            f"approved_by={_approver} "
                            f"reason={reason or '-'}"),
                    user_id=actor_id,
                    new_value=str(approval.get("approver_id") or actor_id),
                )
            except Exception:
                pass
            if self.on_done:
                self.on_done()
            top = self.winfo_toplevel()
            self.destroy()
            show_toast(top, f"Order #{self.order_id} has been voided.")
        except Exception as exc:
            from app.utils import log_error
            log_error("Void full order", exc)
            messagebox.showerror(
                "Void Failed",
                "Could not void this order. Please try again.",
            )

    def _void_items(self):
        actor_id, actor_name = self._get_actor()
        if not actor_id:
            messagebox.showerror("Error", "Cannot verify current user.")
            return

        selected = [iid for iid, var in self._item_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Items Selected", "Please check at least one item to void.")
            return

        names = []
        for item in self._items:
            if int(item["item_id"]) in selected:
                names.append(str(item.get("name") or f"#{item['item_id']}"))

        if not messagebox.askyesno(
            "Void Selected Items",
            f"Void {len(selected)} item(s) from order #{self.order_id}?\n\n"
            + "\n".join(f"  • {n}" for n in names)
            + "\n\nThis cannot be undone.",
            icon="warning",
        ):
            return

        approval = self._require_manager_approval(
            f"voiding {len(selected)} item(s) on order #{self.order_id}"
        )
        if not approval:
            return
        if not self.var_reason.get().strip() and approval.get("reason"):
            self.var_reason.set(approval["reason"])

        reason = self.var_reason.get().strip()
        errors = []
        for item in self._items:
            iid = int(item["item_id"])
            if iid not in selected:
                continue
            try:
                raw_pid = item.get("product_id")
                self.orders.void_order_item(
                    order_id=self.order_id,
                    item_id=iid,
                    product_id=int(raw_pid) if raw_pid is not None else None,
                    qty=int(item.get("qty") or 0),
                    unit_price=float(item.get("unit_price") or 0),
                    voided_by_user_id=actor_id,
                    voided_by_username=actor_name,
                    reason=reason,
                )
                try:
                    from app.db.dao import AuditLogDAO as _ALD
                    _approver = approval.get("approver_username", "") or actor_name
                    _ALD(self.db).log(
                        username=actor_name, action="VOID_ITEM",
                        detail=(f"order_id={self.order_id} item_id={iid} "
                                f"approved_by={_approver} "
                                f"reason={reason or '-'}"),
                        user_id=actor_id,
                        new_value=str(approval.get("approver_id") or actor_id),
                    )
                except Exception:
                    pass
            except Exception as exc:
                from app.utils import log_error
                log_error("Void item", exc)
                errors.append(str(exc))

        top = self.winfo_toplevel()
        if errors:
            messagebox.showerror(
                "Partial Void",
                f"Some items could not be voided:\n\n" + "\n".join(errors),
            )
        if self.on_done:
            self.on_done()
        self.destroy()
        if not errors:
            show_toast(top, f"{len(selected)} item(s) voided successfully.")