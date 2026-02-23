from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from app.config import THEME
from app.db.database import Database
from app.db.dao import OrderDAO, DraftDAO
from app.services.auth_service import AuthService
from app.services.receipt_service import ReceiptService
from app.utils import money


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

        self._build()
        self.refresh()

    # FIX: Add placeholder helper methods
    def _clear_placeholder(self, widget: tk.Entry, placeholder: str):
        """Clear placeholder text when entry is focused."""
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
            widget.config(fg=THEME["text"])

    def _restore_placeholder(self, widget: tk.Entry, placeholder: str):
        """Restore placeholder text if entry is empty and loses focus."""
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(fg=THEME["muted"])

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        tk.Label(self, text="Transactions", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 22, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 8)
        )

        filters = tk.Frame(self, bg=THEME["bg"])
        filters.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        filters.columnconfigure(0, weight=1)

        ent = tk.Entry(filters, textvariable=self.var_search, bd=0, bg=THEME["panel2"], fg=THEME["text"])
        ent.grid(row=0, column=0, sticky="ew", ipady=8)
        # FIX: Add placeholder behavior for search entry
        ent.insert(0, "Search by ID")
        ent.config(fg=THEME["muted"])
        ent.bind("<FocusIn>", lambda e: self._clear_placeholder(ent, "Search by ID"))
        ent.bind("<FocusOut>", lambda e: self._restore_placeholder(ent, "Search by ID"))
        ent.bind("<KeyRelease>", lambda _e: self.refresh())

        status = ttk.Combobox(filters, textvariable=self.var_status, values=["All", "Pending", "Cancelled", "Completed"], state="readonly", width=16)
        status.grid(row=0, column=1, padx=10)
        status.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        pay = ttk.Combobox(filters, textvariable=self.var_payment, values=["All", "Cash", "Bank/E-Wallet"], state="readonly", width=18)
        pay.grid(row=0, column=2, padx=10)
        pay.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        # FIX: Add labels for date filters
        tk.Label(filters, text="From:", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 9)).grid(row=1, column=3, sticky="w", padx=(10, 0))
        ent_from = tk.Entry(filters, textvariable=self.var_from, bd=0, bg=THEME["panel2"], fg=THEME["text"], width=14)
        ent_from.grid(row=2, column=3, padx=10, ipady=8)
        # FIX: Add placeholder for date entry
        ent_from.insert(0, "YYYY-MM-DD")
        ent_from.config(fg=THEME["muted"])
        ent_from.bind("<FocusIn>", lambda e: self._clear_placeholder(ent_from, "YYYY-MM-DD"))
        ent_from.bind("<FocusOut>", lambda e: self._restore_placeholder(ent_from, "YYYY-MM-DD"))
        ent_from.bind("<KeyRelease>", lambda _e: self.refresh())

        # FIX: Add label for To date
        tk.Label(filters, text="To:", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 9)).grid(row=1, column=4, sticky="w", padx=(10, 0))
        ent_to = tk.Entry(filters, textvariable=self.var_to, bd=0, bg=THEME["panel2"], fg=THEME["text"], width=14)
        ent_to.grid(row=2, column=4, padx=10, ipady=8)
        # FIX: Add placeholder for date entry
        ent_to.insert(0, "YYYY-MM-DD")
        ent_to.config(fg=THEME["muted"])
        ent_to.bind("<FocusIn>", lambda e: self._clear_placeholder(ent_to, "YYYY-MM-DD"))
        ent_to.bind("<FocusOut>", lambda e: self._restore_placeholder(ent_to, "YYYY-MM-DD"))
        ent_to.bind("<KeyRelease>", lambda _e: self.refresh())

        wrap = tk.Frame(self, bg=THEME["bg"])
        wrap.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)

        cols = ("id", "payment", "paid", "change", "items", "status", "total", "start", "end", "details")
        self.tbl = ttk.Treeview(wrap, columns=cols, show="headings")
        self.tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self.tbl.configure(yscrollcommand=ysb.set)

        headers = [
            ("id", "ID"),
            ("payment", "PAYMENT"),
            ("paid", "AMOUNT PAID"),
            ("change", "CHANGE"),
            ("items", "ITEMS"),
            ("status", "STATUS"),
            ("total", "TOTAL"),
            ("start", "START"),
            ("end", "END"),
            ("details", "DETAILS"),
        ]
        for c, t in headers:
            self.tbl.heading(c, text=t)

        self.tbl.column("id", width=110, anchor="w")
        self.tbl.column("payment", width=110, anchor="w")
        self.tbl.column("paid", width=110, anchor="e")
        self.tbl.column("change", width=90, anchor="e")
        self.tbl.column("items", width=60, anchor="center")
        self.tbl.column("status", width=90, anchor="center")
        self.tbl.column("total", width=100, anchor="e")
        self.tbl.column("start", width=150, anchor="w")
        self.tbl.column("end", width=150, anchor="w")
        self.tbl.column("details", width=70, anchor="center")

        self.tbl.bind("<Double-Button-1>", lambda _e: self.open_selected())

    def refresh(self):
        for iid in self.tbl.get_children():
            self.tbl.delete(iid)

        # FIX: Ignore placeholder in search
        q = self.var_search.get().replace("Search by ID", "").strip()
        status = self.var_status.get()
        payment = self.var_payment.get()
        # FIX: Ignore placeholders in date filters
        date_from = self.var_from.get().replace("YYYY-MM-DD", "").strip()
        date_to = self.var_to.get().replace("YYYY-MM-DD", "").strip()

        rows = self.orders.list_orders(q, status, payment, date_from, date_to)
        for r in rows:
            oid = int(r["order_id"])
            self.tbl.insert(
                "",
                tk.END,
                iid=str(oid),
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


class TransactionDetailsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, db: Database, order_id: int, on_refresh=None):
        super().__init__(parent)
        self.db = db
        self.order_id = order_id
        self.on_refresh = on_refresh
        self.orders = OrderDAO(db)

        self.title("Transaction Details")
        self.configure(bg=THEME["bg"])
        self.geometry("560x520")
        self.transient(parent)
        self.grab_set()

        self._build()

    def _build(self):
        data = self.orders.get_order(self.order_id)
        if not data:
            messagebox.showerror("Not found", "Transaction not found.")
            self.destroy()
            return

        items = self.orders.get_order_items(self.order_id)

        top = tk.Frame(self, bg=THEME["bg"])
        top.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(top, text="Transaction Details", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 14, "bold")).pack(side="left")

        # status badge
        status = str(data["status"])
        badge_bg = THEME["success"] if status == "Completed" else (THEME["danger"] if status == "Cancelled" else "#f0ad4e")
        tk.Label(top, text=status, bg=badge_bg, fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=2).pack(side="right")

        body = tk.Frame(self, bg=THEME["panel2"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        def line(lbl, val):
            row = tk.Frame(body, bg=THEME["panel2"])
            row.pack(fill="x", padx=14, pady=6)
            tk.Label(row, text=lbl, bg=THEME["panel2"], fg=THEME["muted"], width=18, anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=THEME["panel2"], fg=THEME["text"], anchor="w").pack(side="left")

        line("Order Start:", str(data["start_dt"]))
        line("Order End:", str(data["end_dt"]))
        line("Customer Name:", str(data["customer_name"]))
        line("Payment Method:", str(data["payment_method"]))
        if str(data["reference_no"]).strip():
            line("Reference No.:", str(data["reference_no"]))

        # Items list
        box = tk.Frame(body, bg=THEME["panel"])
        box.pack(fill="x", padx=14, pady=10)

        tk.Label(box, text="Items", bg=THEME["panel"], fg=THEME["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 6))

        for it in items:
            name = it["name"] if it["name"] else f"#{it['product_id']}"
            txt = f"{it['qty']}x {name}"
            row = tk.Frame(box, bg=THEME["panel"])
            row.pack(fill="x", padx=10, pady=3)
            tk.Label(row, text=txt, bg=THEME["panel"], fg=THEME["text"]).pack(side="left")
            tk.Label(row, text=money(it["subtotal"]), bg=THEME["panel"], fg=THEME["text"]).pack(side="right")

        total_box = tk.Frame(body, bg=THEME["panel2"])
        total_box.pack(fill="x", padx=14, pady=(6, 12))
        tk.Label(total_box, text="Total:", bg=THEME["panel2"], fg=THEME["muted"]).pack(side="left")
        tk.Label(total_box, text=money(data["total"]), bg=THEME["panel2"], fg=THEME["text"], font=("Segoe UI", 10, "bold")).pack(side="right")

        paid_box = tk.Frame(body, bg=THEME["panel2"])
        paid_box.pack(fill="x", padx=14, pady=2)
        tk.Label(paid_box, text="Amount Paid:", bg=THEME["panel2"], fg=THEME["muted"]).pack(side="left")
        tk.Label(paid_box, text=money(data["amount_paid"]), bg=THEME["panel2"], fg=THEME["text"]).pack(side="right")

        chg_box = tk.Frame(body, bg=THEME["panel2"])
        chg_box.pack(fill="x", padx=14, pady=2)
        tk.Label(chg_box, text="Change:", bg=THEME["panel2"], fg=THEME["muted"]).pack(side="left")
        tk.Label(chg_box, text=money(data["change_due"]), bg=THEME["panel2"], fg=THEME["text"]).pack(side="right")

        # footer buttons
        footer = tk.Frame(self, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=(0, 14))

        if status == "Pending":
            tk.Button(
                footer, text="Resolve",
                bg="#f0ad4e", fg="white", bd=0, padx=12, pady=8, cursor="hand2",
                command=self._open_resolve
            ).pack(side="left")

        tk.Button(
            footer, text="Print Receipt",
            bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, cursor="hand2",
            command=self._print_receipt
        ).pack(side="right")

        tk.Button(
            footer, text="Close",
            bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, cursor="hand2",
            command=self.destroy
        ).pack(side="right", padx=(0, 10))

    def _open_resolve(self):
        ResolveDialog(self, self.db, self.order_id, on_done=self._resolved)

    def _resolved(self):
        if self.on_refresh:
            self.on_refresh()
        self.destroy()

    def _print_receipt(self):
        """Generate receipt and open it."""
        # FIX: Clean up receipt generation and auto-open
        try:
            data = self.orders.get_order(self.order_id)
            items = self.orders.get_order_items(self.order_id)
            if not data:
                messagebox.showerror("Receipt", "Order not found.")
                return
            # Convert sqlite3.Row to dict for ReceiptService
            order_dict = {k: data[k] for k in data.keys()}
            items_list = [{k: item[k] for k in item.keys()} for item in items]
            receipt_path = ReceiptService.generate_receipt(order_dict, items_list)
            # Auto-open receipt file
            if ReceiptService.open_file(receipt_path):
                messagebox.showinfo("Receipt", f"Receipt opened successfully.\n\nSaved to:\n{receipt_path}")
            else:
                messagebox.showwarning("Receipt", f"Receipt generated but could not open automatically.\n\nSaved to:\n{receipt_path}")
        except Exception as e:
            messagebox.showerror("Receipt Error", f"Failed to generate receipt.\n\n{e}")


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

    # FIX: Add placeholder helper methods
    def _clear_placeholder(self, widget: tk.Entry, placeholder: str):
        """Clear placeholder text when entry is focused."""
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
            widget.config(fg=THEME["text"])

    def _restore_placeholder(self, widget: tk.Entry, placeholder: str):
        """Restore placeholder text if entry is empty and loses focus."""
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

        # FIX: Add label for reference number
        tk.Label(box, text="Reference Number:", bg=THEME["panel2"], fg=THEME["text"], font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(14, 4))
        ent_ref = tk.Entry(box, textvariable=self.var_ref, bd=0, bg="white", fg=THEME["text"])
        ent_ref.pack(fill="x", padx=14, pady=(0, 14), ipady=8)
        # FIX: Add placeholder for reference entry
        ent_ref.insert(0, "Reference No.")
        ent_ref.config(fg=THEME["muted"])
        ent_ref.bind("<FocusIn>", lambda e: self._clear_placeholder(ent_ref, "Reference No."))
        ent_ref.bind("<FocusOut>", lambda e: self._restore_placeholder(ent_ref, "Reference No."))
        self.var_ref.set("")

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
        if not ref:
            messagebox.showerror("Reference", "Reference number is required.")
            return
        # FIX: Use existing amount_paid or order total
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