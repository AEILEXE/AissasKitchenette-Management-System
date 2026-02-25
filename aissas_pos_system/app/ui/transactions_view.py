from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime  # IMPORTANT for latest sale detection

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO, DraftDAO
from app.services.auth_service import AuthService
from app.services.receipt_service import ReceiptService
from app.ui import ui_scale
from app.utils import money

# --- Offline calendar picker (tkcalendar) ---
_TKCAL_ERROR = None
try:
    import tkcalendar as _tkcal  # pip install tkcalendar
    Calendar = _tkcal.Calendar
except Exception as e:
    Calendar = None
    _TKCAL_ERROR = e


# =========================================================
# ===================== TRANSACTIONS VIEW =================
# =========================================================

class TransactionsView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.orders = OrderDAO(db)
        self.drafts = DraftDAO(db)

        self.var_search = tk.StringVar()
        self.var_status = tk.StringVar(value="All")
        self.var_payment = tk.StringVar(value="All")
        self.var_from = tk.StringVar()
        self.var_to = tk.StringVar()

        self._search_after = None

        # entry refs for placeholder restore
        self.ent_search: tk.Entry | None = None
        self.ent_from: tk.Entry | None = None
        self.ent_to: tk.Entry | None = None

        self._build()
        self.refresh()

    # ---------------- placeholder helpers ----------------
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
        if self.ent_from:
            if self.ent_from.get().strip() == "":
                self.ent_from.insert(0, "YYYY-MM-DD")
                self.ent_from.config(fg=THEME["muted"])
        if self.ent_to:
            if self.ent_to.get().strip() == "":
                self.ent_to.insert(0, "YYYY-MM-DD")
                self.ent_to.config(fg=THEME["muted"])

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

    # ---------------- calendar picker ----------------
    def _open_date_picker(self, target_entry: tk.Entry, which: str):
        """
        Offline calendar popup. Sets var_from/var_to to YYYY-MM-DD.
        which: "from" or "to"
        """
        if Calendar is None:
            messagebox.showerror(
                "Calendar Picker",
                "tkcalendar failed to import.\n\n"
                f"Error: {_TKCAL_ERROR}\n\n"
                "Fix this:\n"
                "1) Make sure you're running the same venv where you installed tkcalendar.\n"
                "2) Check your project for a file/folder named 'tkcalendar' and rename it.\n"
            )
            return

        # current value if valid
        current = None
        raw = target_entry.get().strip()
        if raw and raw != "YYYY-MM-DD":
            try:
                current = datetime.fromisoformat(raw).date()
            except Exception:
                current = None

        top = tk.Toplevel(self)
        top.title("Select date")
        top.configure(bg=THEME["bg"])
        top.transient(self.winfo_toplevel())
        top.grab_set()

        # center-ish
        top.update_idletasks()
        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        w, h = 320, 330
        x = (sw - w) // 2
        y = (sh - h) // 2
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.resizable(False, False)

        cal_wrap = tk.Frame(top, bg=THEME["bg"])
        cal_wrap.pack(fill="both", expand=True, padx=12, pady=12)

        cal = Calendar(
            cal_wrap,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
        )
        cal.pack(fill="both", expand=True)

        if current is not None:
            try:
                cal.selection_set(current)
            except Exception:
                pass

        btns = tk.Frame(top, bg=THEME["bg"])
        btns.pack(fill="x", padx=12, pady=(0, 12))

        def apply():
            d = cal.get_date()  # yyyy-mm-dd
            if which == "from":
                self.var_from.set(d)
            else:
                self.var_to.set(d)

            target_entry.delete(0, tk.END)
            target_entry.insert(0, d)
            target_entry.config(fg=THEME["text"])
            top.destroy()
            self._debounced_refresh()

        def clear():
            if which == "from":
                self.var_from.set("")
            else:
                self.var_to.set("")
            target_entry.delete(0, tk.END)
            target_entry.insert(0, "YYYY-MM-DD")
            target_entry.config(fg=THEME["muted"])
            top.destroy()
            self._debounced_refresh()

        tk.Button(
            btns, text="Clear date",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=12, pady=8, cursor="hand2",
            command=clear
        ).pack(side="left")

        tk.Button(
            btns, text="Cancel",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=12, pady=8, cursor="hand2",
            command=top.destroy
        ).pack(side="right")

        tk.Button(
            btns, text="Apply",
            bg=THEME["success"], fg="white",
            bd=0, padx=14, pady=8, cursor="hand2",
            command=apply
        ).pack(side="right", padx=(0, 10))

        cal.bind("<Double-Button-1>", lambda _e: apply(), add="+")

    # ---------------- UI ----------------
    def _build(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Clean Treeview
        style.configure(
            "Tx.Treeview",
            font=("Segoe UI", 10),
            rowheight=30,
            background=THEME["panel"],
            fieldbackground=THEME["panel"],
            foreground=THEME["text"],
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Tx.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=THEME["panel2"],
            foreground=THEME["text"],
            relief="flat",
            padding=(10, 10),
        )
        style.map("Tx.Treeview.Heading", background=[("active", THEME["panel2"])])

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

        # ================= FILTER BAR (redesigned + calendar) =================
        bar = tk.Frame(
            self,
            bg=THEME["panel"],
            highlightthickness=1,
            highlightbackground=THEME["panel2"]
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

        tk.Label(search_box, bg=THEME["panel2"], fg=THEME["muted"]).grid(row=0, column=0, padx=(10, 6))

        self.ent_search = tk.Entry(
            search_box,
            textvariable=self.var_search,
            bd=0,
            bg=THEME["panel2"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
        )
        self.ent_search.grid(row=0, column=1, sticky="ew", ipady=8, padx=(0, 10))

        self._apply_search_placeholder()
        self.ent_search.bind("<FocusIn>", lambda e: self._clear_placeholder(self.ent_search, "Search transaction ID…"))
        self.ent_search.bind("<FocusOut>", lambda e: self._restore_placeholder(self.ent_search, "Search transaction ID…"))
        self.ent_search.bind("<KeyRelease>", lambda _e: self._debounced_refresh())

        # Filters
        group = tk.Frame(row, bg=THEME["panel"])
        group.grid(row=0, column=1, sticky="e", padx=(12, 0))

        def mini_label(parent, text):
            return tk.Label(parent, text=text, bg=THEME["panel"], fg=THEME["muted"], font=("Segoe UI", 9))

        def pill_date(parent, textvariable, which: str, width=12):
            pill = tk.Frame(parent, bg=THEME["panel2"])

            ent = tk.Entry(
                pill,
                textvariable=textvariable,
                bd=0,
                bg=THEME["panel2"],
                fg=THEME["text"],
                insertbackground=THEME["text"],
                width=width
            )
            ent.pack(side="left", fill="x", expand=True, padx=(10, 6), ipady=8)

            btn = tk.Button(
                pill,
                text="📅",
                bg=THEME["panel2"],
                fg=THEME["muted"],
                bd=0,
                padx=8,
                pady=6,
                cursor="hand2",
                command=lambda: self._open_date_picker(ent, which),
            )
            btn.pack(side="right", padx=(0, 6), pady=0)

            ent.insert(0, "YYYY-MM-DD")
            ent.config(fg=THEME["muted"])
            ent.bind("<FocusIn>", lambda e: self._clear_placeholder(ent, "YYYY-MM-DD"))
            ent.bind("<FocusOut>", lambda e: self._restore_placeholder(ent, "YYYY-MM-DD"))
            ent.bind("<KeyRelease>", lambda _e: self._debounced_refresh())
            ent.bind("<Return>", lambda _e: self._debounced_refresh())

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
        from_pill, self.ent_from = pill_date(group, self.var_from, "from", width=12)
        from_pill.grid(row=1, column=2, padx=(0, 10), sticky="w")

        mini_label(group, "To").grid(row=0, column=3, sticky="w")
        to_pill, self.ent_to = pill_date(group, self.var_to, "to", width=12)
        to_pill.grid(row=1, column=3, padx=(0, 10), sticky="w")

        tk.Button(
            group,
            text="Clear",
            bg=THEME["panel2"],
            fg=THEME["text"],
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._clear_all,
        ).grid(row=1, column=4, sticky="w")

        # ================= TABLE CARD =================
        table_card = tk.Frame(self, bg=THEME["panel"], highlightthickness=1, highlightbackground=THEME["panel2"])
        table_card.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(0, weight=1)

        cols = ("id", "payment", "paid", "change", "items", "status", "total", "start", "end", "details")
        self.tbl = ttk.Treeview(table_card, columns=cols, show="headings", style="Tx.Treeview")
        self.tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(table_card, orient="vertical", command=self.tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self.tbl.configure(yscrollcommand=ysb.set)

        headers = [
            ("id", "ID"),
            ("payment", "PAYMENT"),
            ("paid", "PAID"),
            ("change", "CHANGE"),
            ("items", "ITEMS"),
            ("status", "STATUS"),
            ("total", "TOTAL"),
            ("start", "START"),
            ("end", "END"),
            ("details", ""),
        ]
        for c, t in headers:
            self.tbl.heading(c, text=t)

        self.tbl.column("id", width=80, anchor="w")
        self.tbl.column("payment", width=140, anchor="w")
        self.tbl.column("paid", width=110, anchor="e")
        self.tbl.column("change", width=100, anchor="e")
        self.tbl.column("items", width=70, anchor="center")
        self.tbl.column("status", width=120, anchor="center")
        self.tbl.column("total", width=120, anchor="e")
        self.tbl.column("start", width=180, anchor="w")
        self.tbl.column("end", width=180, anchor="w")
        self.tbl.column("details", width=60, anchor="center")

        self.tbl.tag_configure("top_sale", background="#dff6ef")
        self.tbl.tag_configure("latest_sale", background="#e9efff")
        self.tbl.tag_configure("top_and_latest", background="#d7f0ff")

        self.tbl.bind("<Double-Button-1>", lambda _e: self.open_selected())
        self.tbl.bind("<Return>", lambda _e: self.open_selected())

    # ---------------- data ----------------
    def refresh(self):
        for iid in self.tbl.get_children():
            self.tbl.delete(iid)

        q = self.var_search.get().replace("Search transaction ID…", "").strip()
        status = self.var_status.get()
        payment = self.var_payment.get()
        date_from = self.var_from.get().replace("YYYY-MM-DD", "").strip()
        date_to = self.var_to.get().replace("YYYY-MM-DD", "").strip()

        rows = self.orders.list_orders(q, status, payment, date_from, date_to)

        top_id = None
        latest_id = None
        best_total = None
        best_dt = None

        for r in rows:
            oid = int(r["order_id"])

            try:
                total = float(r["total"] or 0.0)
            except Exception:
                total = 0.0

            dt_str = ""
            try:
                dt_str = str(r["start_dt"] or "")
            except Exception:
                dt_str = ""
            if not dt_str:
                try:
                    dt_str = str(r["end_dt"] or "")
                except Exception:
                    dt_str = ""

            dt = None
            try:
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                dt = None

            if best_total is None or total > best_total:
                best_total = total
                top_id = oid

            if dt is not None:
                if best_dt is None or dt > best_dt:
                    best_dt = dt
                    latest_id = oid

        for r in rows:
            oid = int(r["order_id"])

            tag = ()
            if top_id == oid and latest_id == oid:
                tag = ("top_and_latest",)
            elif top_id == oid:
                tag = ("top_sale",)
            elif latest_id == oid:
                tag = ("latest_sale",)

            self.tbl.insert(
                "",
                tk.END,
                iid=str(oid),
                tags=tag,
                values=(
                    oid,
                    r["payment_method"],
                    money(r["amount_paid"]),
                    money(r["change_due"]),
                    int(r["items_count"]),
                    r["status"],
                    money(r["total"]),
                    r["start_dt"],
                    r["end_dt"],
                    "View",
                ),
            )

    def open_selected(self):
        sel = self.tbl.selection()
        if not sel:
            return
        oid = int(sel[0])
        TransactionDetailsDialog(self, self.db, oid, on_refresh=self.refresh)


# =========================================================
# ================ TRANSACTION DETAILS DIALOG ==============
# (keep your current version here)
# =========================================================

class TransactionDetailsDialog(tk.Toplevel):
    MAX_COLLAPSED_ROWS = 5
    SCROLL_SPEED_UNITS = 10

    def __init__(self, parent: tk.Widget, db: Database, order_id: int, on_refresh=None):
        super().__init__(parent)
        self.db = db
        self.order_id = order_id
        self.on_refresh = on_refresh
        self.orders = OrderDAO(db)

        self.title("Transaction Details")
        self.configure(bg=THEME["bg"])
        self.geometry("640x600")
        self.minsize(580, 520)

        self.transient(parent)
        self.grab_set()

        self._details_expanded = tk.BooleanVar(value=False)
        self._details_rows: list[tuple[str, str]] = []
        self._discount_amount: float = 0.0
        self._total_amount: float = 0.0

        self._build()

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(760, sw - 120)
        h = min(700, sh - 140)
        x = (sw - w) // 2
        y = (sh - h) // 2
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

        # Pill-style status badge
        status = str(data["status"])
        badge_bg = (
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

        # Card title strip
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
            row = tk.Frame(info_card, bg=THEME["panel"])
            row.pack(fill="x", padx=14, pady=sp(5))
            tk.Label(
                row, text=label,
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", f(9)),
                width=18, anchor="w",
            ).pack(side="left")
            tk.Label(
                row, text=value,
                bg=THEME["panel"], fg=THEME["text"],
                font=("Segoe UI", f(9), "bold") if bold_val else ("Segoe UI", f(9)),
                anchor="w",
            ).pack(side="left")

        info_line("Order Start:", str(data["start_dt"]))
        info_line("Order End:",   str(data["end_dt"]))
        info_line("Customer:",    str(data["customer_name"]), bold_val=True)
        info_line("Payment:",     str(data["payment_method"]))

        ref = ""
        try:
            ref = str(data["reference_no"] or "").strip()
        except Exception:
            ref = ""
        if ref:
            info_line("Reference No.:", ref)

        tk.Frame(info_card, bg=THEME["border"], height=1).pack(fill="x", padx=14, pady=4)

        # Amount Paid / Change
        def money_line(label: str, value: str, accent: bool = False):
            row = tk.Frame(info_card, bg=THEME["panel"])
            row.pack(fill="x", padx=14, pady=sp(4))
            tk.Label(
                row, text=label,
                bg=THEME["panel"], fg=THEME["muted"],
                font=("Segoe UI", f(9)), anchor="w",
            ).pack(side="left")
            tk.Label(
                row, text=value,
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
            self._details_rows.append((f"{qty}× {name}", money(it["subtotal"])))

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
            od_hdr, text="▸ Show",
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

        if status == "Pending":
            tk.Button(
                footer, text="Resolve",
                bg="#d97706", fg="white",
                activebackground="#b45309", activeforeground="white",
                bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
                font=("Segoe UI", f(9), "bold"),
                command=self._open_resolve,
            ).pack(side="left")

        tk.Button(
            footer, text="Close",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
            font=("Segoe UI", f(9)),
            command=self.destroy,
        ).pack(side="right")

        tk.Button(
            footer, text="🖨  Print Receipt",
            bg=THEME["brown"], fg="white",
            activebackground=THEME["brown_dark"], activeforeground="white",
            bd=0, padx=sp(14), pady=sp(9), cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._print_receipt,
        ).pack(side="right", padx=(0, sp(8)))

    def _toggle_details(self):
        self._details_expanded.set(not self._details_expanded.get())
        self._render_details()

    def _render_details(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        for w in self.details_body.winfo_children():
            w.destroy()

        expanded = self._details_expanded.get()
        self.btn_toggle.configure(text="▾ Hide" if expanded else "▸ Show")

        rows = self._details_rows if expanded else self._details_rows[: self.MAX_COLLAPSED_ROWS]
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
                drow, text=f"−{money(self._discount_amount)}",
                bg="#ffffff", fg=THEME["danger"],
                font=("Segoe UI", f(9), "bold"),
            ).pack(side="right")

        # Emphasized total row
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

    def _print_receipt(self):
        try:
            data = self.orders.get_order(self.order_id)
            items = self.orders.get_order_items(self.order_id)
            if not data:
                messagebox.showerror("Receipt", "Order not found.")
                return

            order_dict = {k: data[k] for k in data.keys()}
            items_list = [{k: item[k] for k in item.keys()} for item in items]

            receipt_path = ReceiptService.generate_receipt(order_dict, items_list)
            ok = ReceiptService.open_file(receipt_path)
            if not ok:
                messagebox.showwarning("Receipt", f"Receipt generated but could not open automatically.\n\nSaved to:\n{receipt_path}")

        except Exception as e:
            messagebox.showerror("Receipt Error", f"Failed to generate receipt.\n\n{e}")


# =========================================================
# ======================= RESOLVE DIALOG ==================
# =========================================================

class ResolveDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, db: Database, order_id: int, on_done=None):
        super().__init__(parent)
        self.db = db
        self.order_id = order_id
        self.on_done = on_done
        self.orders = OrderDAO(db)

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
        tk.Label(self, text="Resolve Transaction", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=18, pady=(14, 6)
        )
        tk.Label(self, text="Resolve by providing payment reference number.", bg=THEME["bg"], fg=THEME["muted"]).pack(
            anchor="w", padx=18, pady=(0, 10)
        )

        box = tk.Frame(self, bg=THEME["panel2"])
        box.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        tk.Label(box, text="Reference Number:", bg=THEME["panel2"], fg=THEME["text"], font=("Segoe UI", 10)).pack(
            anchor="w", padx=14, pady=(14, 4)
        )
        ent_ref = tk.Entry(box, textvariable=self.var_ref, bd=0, bg="white", fg=THEME["text"])
        ent_ref.pack(fill="x", padx=14, pady=(0, 14), ipady=8)

        ent_ref.insert(0, "Reference No.")
        ent_ref.config(fg=THEME["muted"])
        ent_ref.bind("<FocusIn>", lambda e: self._clear_placeholder(ent_ref, "Reference No."))
        ent_ref.bind("<FocusOut>", lambda e: self._restore_placeholder(ent_ref, "Reference No."))

        footer = tk.Frame(self, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=(0, 14))

        tk.Button(
            footer, text="Close",
            bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, cursor="hand2",
            command=self.destroy
        ).pack(side="right")

        tk.Button(
            footer, text="Cancel transaction",
            bg=THEME["danger"], fg="white", bd=0, padx=12, pady=8, cursor="hand2",
            command=self._cancel
        ).pack(side="right", padx=(0, 10))

        tk.Button(
            footer, text="Complete transaction",
            bg=THEME["success"], fg="white", bd=0, padx=12, pady=8, cursor="hand2",
            command=self._complete
        ).pack(side="right", padx=(0, 10))

    def _complete(self):
        ref = self.var_ref.get().strip()
        if not ref or ref == "Reference No.":
            messagebox.showerror("Reference", "Reference number is required.")
            return

        data = self.orders.get_order(self.order_id)
        if not data:
            messagebox.showerror("Error", "Order not found.")
            return

        paid = float(data["amount_paid"]) if data["amount_paid"] else float(data["total"])
        self.orders.resolve_pending(self.order_id, ref, paid)

        if self.on_done:
            self.on_done()
        self.destroy()

    def _cancel(self):
        if not messagebox.askyesno("Cancel", "Cancel this transaction?"):
            return
        self.orders.cancel_order(self.order_id)
        if self.on_done:
            self.on_done()
        self.destroy()