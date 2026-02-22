from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from app.config import THEME
from app.db.database import Database
from app.db.dao import CategoryDAO, ProductDAO, DraftDAO, OrderDAO
from app.services.auth_service import AuthService
from app.ui.dialogs import DiscountDialog, TextPromptDialog
from app.utils import money


def _row_get(r, key: str, default=None):
    """Safe access for sqlite3.Row (no .get())."""
    try:
        v = r[key]
        return default if v is None else v
    except Exception:
        return default


def _truncate_text(text: str, max_len: int = 20, suffix: str = "…") -> str:
    """Truncate text with ellipsis if longer than max_len."""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + suffix


class POSView(tk.Frame):
    """
    POS View:
    - Categories are buttons (compact height)
    - Items responsive grid (2–3 per row; can fallback to 1)
    - Mousewheel scrolling for Categories + Items + Draft list
    - Add discount + Save draft beside Checkout
    - Save draft clears current order, Load restores
    - Checkout opens Confirm Order modal (Cash -> Completed, Bank/E-Wallet -> Pending)
    - Customer Name REQUIRED always; Contact removed
    """

    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth

        self.cat_dao = CategoryDAO(db)
        self.prod_dao = ProductDAO(db)
        self.draft_dao = DraftDAO(db)
        self.order_dao = OrderDAO(db)

        # cart: {product_id: (name, price, qty, note)}
        self.cart: dict[int, tuple[str, float, int, str]] = {}

        self.discount_mode: str = "amount"  # amount|percent
        self.discount_value: float = 0.0

        self._draft_id_by_index: list[int] = []

        # categories
        self._cat_buttons: dict[str, tk.Button] = {}
        self._selected_category: str = "All"

        # products responsive
        self._products_cache = []
        self._product_card_widgets: list[tk.Frame] = []
        self._prod_resize_after = None

        # image cache
        self._img_cache: dict[str, tk.PhotoImage] = {}

        self._build()
        self._refresh_categories()
        self._refresh_drafts_panel()
        self._refresh_products()
        self._refresh_cart()

    # ---------------- Mousewheel helpers ----------------
    def _on_mousewheel(self, event, canvas: tk.Canvas):
        try:
            # Check if canvas still exists before scrolling
            if not canvas.winfo_exists():
                return
            delta = -3 if event.delta > 0 else 3  # Increased from ±1 to ±3 for faster scrolling
            canvas.yview_scroll(delta, "units")
        except tk.TclError:
            # Widget was destroyed, silently ignore
            pass

    def _add_tooltip(self, widget: tk.Widget, text: str):
        """Simple tooltip on hover."""
        def on_enter(event):
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            label = tk.Label(tooltip, text=text, bg="#ffffe0", fg="black", padx=6, pady=3, font=("Segoe UI", 9))
            label.pack()
            
            def on_leave(e):
                tooltip.destroy()
            
            widget.tooltip = tooltip
            widget.bind("<Leave>", on_leave)
        
        widget.bind("<Enter>", on_enter)

    def _bind_mousewheel_to_canvas(self, bind_widget: tk.Widget, canvas: tk.Canvas):
        # Windows/macOS
        bind_widget.bind(
            "<Enter>",
            lambda _e: canvas.bind_all("<MouseWheel>", lambda e: self._on_mousewheel(e, canvas)),
        )
        bind_widget.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        # Linux - also protected against destroyed widgets
        def _linux_scroll_up(e):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(-3, "units")
            except tk.TclError:
                pass
        
        def _linux_scroll_down(e):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(3, "units")
            except tk.TclError:
                pass
        
        bind_widget.bind(
            "<Enter>",
            lambda _e: (
                canvas.bind_all("<Button-4>", _linux_scroll_up),
                canvas.bind_all("<Button-5>", _linux_scroll_down),
            ),
        )
        bind_widget.bind(
            "<Leave>",
            lambda _e: (canvas.unbind_all("<Button-4>"), canvas.unbind_all("<Button-5>")),
        )

    # ---------------- Placeholder helpers ----------------
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

    # ---------------- Image helpers ----------------
    def _load_default_image(self) -> tk.PhotoImage | None:
        key = "__default__"
        if key in self._img_cache:
            return self._img_cache[key]

        path = os.path.join(os.getcwd(), "product_images", "images.png")
        try:
            img = tk.PhotoImage(file=path)
            self._img_cache[key] = img
            return img
        except Exception:
            return None

    def _load_image(self, rel_path: str | None) -> tk.PhotoImage | None:
        if not rel_path:
            return self._load_default_image()

        key = f"img::{rel_path}"
        if key in self._img_cache:
            return self._img_cache[key]

        abs_path = os.path.join(os.getcwd(), rel_path)
        try:
            img = tk.PhotoImage(file=abs_path)
            self._img_cache[key] = img
            return img
        except Exception:
            return self._load_default_image()

    # ---------------- UI ----------------
    def _build(self):
        # Configure thicker scrollbar style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Thick.Vertical.TScrollbar', arrowcolor=THEME["text"], troughcolor=THEME["panel"], 
                        bordercolor=THEME["panel"], background=THEME["panel2"], darkcolor=THEME["panel2"], 
                        lightcolor=THEME["panel2"], width=14)  # width=14 makes scrollbar thicker
        
        # Header title
        header = tk.Frame(self, bg=THEME["bg"])
        header.pack(fill="x", padx=18, pady=(14, 8))
        tk.Label(
            header,
            text="POS",
            bg=THEME["bg"],
            fg=THEME["text"],
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left")

        body = tk.Frame(self, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        body.rowconfigure(0, weight=1)

        body.columnconfigure(0, weight=1, minsize=140)   # categories (reduced)
        body.columnconfigure(1, weight=8, minsize=800)   # items (expanded)
        body.columnconfigure(2, weight=2, minsize=320)   # right

        # ---------------- Left: Categories ----------------
        left = tk.Frame(body, bg=THEME["panel"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(
            left,
            text="Categories",
            bg=THEME["panel"],
            fg=THEME["text"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.cat_canvas = tk.Canvas(left, bg=THEME["panel"], highlightthickness=0)
        self.cat_canvas.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        cat_sb = ttk.Scrollbar(left, orient="vertical", command=self.cat_canvas.yview, style='Thick.Vertical.TScrollbar')
        cat_sb.pack(side="right", fill="y")
        self.cat_canvas.configure(yscrollcommand=cat_sb.set)

        self.cat_inner = tk.Frame(self.cat_canvas, bg=THEME["panel"])
        self._cat_window_id = self.cat_canvas.create_window((0, 0), window=self.cat_inner, anchor="nw")

        self.cat_inner.bind("<Configure>", lambda _e: self.cat_canvas.configure(scrollregion=self.cat_canvas.bbox("all")))

        def _cat_canvas_resize(e):
            self.cat_canvas.itemconfigure(self._cat_window_id, width=e.width)

        self.cat_canvas.bind("<Configure>", _cat_canvas_resize)

        self._bind_mousewheel_to_canvas(self.cat_canvas, self.cat_canvas)
        self._bind_mousewheel_to_canvas(self.cat_inner, self.cat_canvas)

        # ---------------- Middle: Products ----------------
        mid = tk.Frame(body, bg=THEME["panel"])
        mid.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        mid.rowconfigure(3, weight=1)

        tk.Label(
            mid,
            text="All Items",
            bg=THEME["panel"],
            fg=THEME["text"],
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.search_var = tk.StringVar()
        search = tk.Entry(mid, textvariable=self.search_var, bd=0, bg=THEME["panel2"], fg=THEME["text"])
        search.pack(fill="x", padx=14, pady=(0, 10), ipady=8)
        search.bind("<KeyRelease>", lambda _e: self._refresh_products())
        search.bind("<FocusIn>", lambda _e: self._clear_placeholder(search, "Search…"))
        search.bind("<FocusOut>", lambda _e: self._restore_placeholder(search, "Search…"))
        # Set initial placeholder
        search.insert(0, "Search…")
        search.config(fg=THEME["muted"])

        self.prod_canvas = tk.Canvas(mid, bg=THEME["panel"], highlightthickness=0)
        self.prod_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        prod_sb = ttk.Scrollbar(mid, orient="vertical", command=self.prod_canvas.yview, style='Thick.Vertical.TScrollbar')
        prod_sb.pack(side="right", fill="y")
        self.prod_canvas.configure(yscrollcommand=prod_sb.set)

        self.prod_inner = tk.Frame(self.prod_canvas, bg=THEME["panel"])
        self._prod_window_id = self.prod_canvas.create_window((0, 0), window=self.prod_inner, anchor="nw")

        self.prod_inner.bind("<Configure>", lambda _e: self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all")))

        def _prod_canvas_configure(e):
            self.prod_canvas.itemconfigure(self._prod_window_id, width=e.width)
            self._debounced_relayout()

        self.prod_canvas.bind("<Configure>", _prod_canvas_configure)

        self._bind_mousewheel_to_canvas(self.prod_canvas, self.prod_canvas)
        self._bind_mousewheel_to_canvas(self.prod_inner, self.prod_canvas)

        # ---------------- Right: Draft + Cart ----------------
        right = tk.Frame(body, bg=THEME["panel"])
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(5, weight=1)

        u = self.auth.get_current_user()
        uname = u.username if u else "—"
        role = u.role.upper() if u else "—"
        user_card = tk.Frame(right, bg=THEME["panel2"])
        user_card.pack(fill="x", padx=14, pady=(12, 10))
        tk.Label(
            user_card, text=role,
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=12, pady=(10, 0))
        tk.Label(
            user_card, text=uname,
            bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=12, pady=(0, 10))

        tk.Label(
            right, text="Draft orders",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w", padx=14, pady=(0, 6))

        self.draft_list = tk.Listbox(
            right,
            height=6,
            bd=0,
            highlightthickness=0,
            bg=THEME["panel2"],
            fg=THEME["text"],
            activestyle="none",
        )
        self.draft_list.pack(fill="x", padx=14)
        self.draft_list.bind("<Double-Button-1>", lambda _e: self._load_selected_draft())

        # Safe scroll handlers for draft list
        def _draft_mousewheel(e):
            try:
                if self.draft_list.winfo_exists():
                    self.draft_list.yview_scroll((-3 if e.delta > 0 else 3), "units")
            except tk.TclError:
                pass
        
        def _draft_scroll_up(_e):
            try:
                if self.draft_list.winfo_exists():
                    self.draft_list.yview_scroll(-3, "units")
            except tk.TclError:
                pass
        
        def _draft_scroll_down(_e):
            try:
                if self.draft_list.winfo_exists():
                    self.draft_list.yview_scroll(3, "units")
            except tk.TclError:
                pass

        self.draft_list.bind("<MouseWheel>", _draft_mousewheel)
        self.draft_list.bind("<Button-4>", _draft_scroll_up)
        self.draft_list.bind("<Button-5>", _draft_scroll_down)

        draft_btns = tk.Frame(right, bg=THEME["panel"])
        draft_btns.pack(fill="x", padx=14, pady=(6, 10))
        tk.Button(
            draft_btns,
            text="Load",
            command=self._load_selected_draft,
            bg=THEME["panel2"],
            fg=THEME["text"],
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side="left")
        tk.Button(
            draft_btns,
            text="Delete",
            command=self._delete_selected_draft,
            bg=THEME["danger"],
            fg="white",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side="left", padx=8)

        tk.Label(
            right, text="Current order",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=14, pady=(8, 6))

        self.cart_tbl = tk.Frame(right, bg=THEME["panel2"])
        self.cart_tbl.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # Two-row footer: Total on top row, buttons on bottom row
        footer_top = tk.Frame(right, bg=THEME["panel"])
        footer_top.pack(fill="x", padx=14, pady=(0, 6))
        
        self.total_lbl = tk.Label(
            footer_top, text="Total: ₱0.00",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", 12, "bold")
        )
        self.total_lbl.pack(side="left")

        footer_btns = tk.Frame(right, bg=THEME["panel"])
        footer_btns.pack(fill="x", padx=14, pady=(0, 14))

        tk.Button(
            footer_btns,
            text="Add discount",
            command=self._add_discount,
            bg=THEME["panel2"],
            fg=THEME["text"],
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=(0, 5))

        tk.Button(
            footer_btns,
            text="Save as draft",
            command=self._save_draft,
            bg=THEME.get("brown", "#6b4a3a"),
            fg="white",
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=5)

        tk.Button(
            footer_btns,
            text="Checkout",
            command=self._checkout,
            bg=THEME["success"],
            fg="white",
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=(5, 0))

    # ---------------- Categories ----------------
    def _set_active_category_btn(self, name: str) -> None:
        self._selected_category = name
        for cat_name, btn in self._cat_buttons.items():
            if cat_name == name:
                btn.configure(bg=THEME["select_bg"], fg=THEME["select_fg"])
            else:
                btn.configure(bg=THEME["panel2"], fg=THEME["text"])

    def _refresh_categories(self):
        for w in self.cat_inner.winfo_children():
            w.destroy()
        self._cat_buttons.clear()

        def add_btn(name: str):
            btn = tk.Button(
                self.cat_inner,
                text=name,
                anchor="w",
                command=lambda n=name: self._on_category_click(n),
                bg=THEME["panel2"],
                fg=THEME["text"],
                activebackground=THEME["select_bg"],
                activeforeground=THEME["select_fg"],
                bd=0,
                padx=8,
                pady=4,
                cursor="hand2",
                font=("Segoe UI", 10),
            )
            btn.pack(fill="x", pady=1)
            self._cat_buttons[name] = btn

        add_btn("All")
        for r in self.cat_dao.list_categories():
            add_btn(str(r["name"]))

        self._set_active_category_btn(self._selected_category if self._selected_category in self._cat_buttons else "All")

    def _on_category_click(self, name: str) -> None:
        self._set_active_category_btn(name)
        self._refresh_products()

    # ---------------- Products ----------------
    def _filter_products(self, search_text: str = ""):
        if not search_text:
            q = (self.search_var.get() or "").strip().lower()
        else:
            q = search_text.lower()
        cat_name = self._selected_category or "All"

        if cat_name == "All":
            rows = self.prod_dao.list_all_active()
        else:
            c = self.cat_dao.get_by_name(cat_name)
            rows = self.prod_dao.list_by_category(int(c["category_id"])) if c else []

        out = []
        for r in rows:
            name = str(r["name"]).lower()
            if q and q not in name:
                continue
            out.append(r)
        return out

    def _calc_product_cols(self) -> int:
        width = max(1, int(self.prod_canvas.winfo_width()))
        if width >= 960:
            return 3
        if width >= 640:
            return 2
        return 1

    def _debounced_relayout(self) -> None:
        if self._prod_resize_after is not None:
            try:
                self.after_cancel(self._prod_resize_after)
            except Exception:
                pass
        self._prod_resize_after = self.after(80, self._relayout_products)

    def _refresh_products(self):
        # Get search text, ignoring placeholder
        search_text = self.search_var.get().strip()
        if search_text == "Search…":
            search_text = ""
        self._products_cache = self._filter_products(search_text)
        self._relayout_products(rebuild_cards=True)

    def _relayout_products(self, rebuild_cards: bool = False) -> None:
        if rebuild_cards:
            for w in self.prod_inner.winfo_children():
                w.destroy()
            self._product_card_widgets = [self._product_card(self.prod_inner, r) for r in self._products_cache]

        cards = self._product_card_widgets
        cols = self._calc_product_cols()

        for i in range(cols):
            self.prod_inner.columnconfigure(i, weight=1)

        for w in cards:
            w.grid_forget()

        for idx, card in enumerate(cards):
            row = idx // cols
            col = idx % cols
            card.grid(row=row, column=col, sticky="ew", padx=10, pady=10)

        self.prod_inner.update_idletasks()
        self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all"))

    def _product_card(self, parent: tk.Widget, r) -> tk.Frame:
        pid = int(r["product_id"])
        name = str(r["name"])
        price = float(r["price"])
        stock = int(_row_get(r, "stock_qty", 0))

        is_available = stock > 0
        avail_txt = "Available" if is_available else "Not Available"
        avail_bg = THEME["success"] if is_available else THEME["danger"]

        card = tk.Frame(parent, bg=THEME["panel2"], bd=0, cursor="hand2" if is_available else "arrow")
        card.columnconfigure(1, weight=1)
        
        # Make card clickable if available
        if is_available:
            card.bind("<Button-1>", lambda _e: self._add_to_cart(pid, name, price))
            # Change cursor on hover
            card.bind("<Enter>", lambda _e: card.config(cursor="hand2"))
            card.bind("<Leave>", lambda _e: card.config(cursor="arrow"))

        img_frame = tk.Frame(card, bg=THEME["panel"], width=64, height=64, cursor="hand2" if is_available else "arrow")
        img_frame.grid(row=0, column=0, rowspan=3, padx=12, pady=12, sticky="n")
        img_frame.grid_propagate(False)
        
        # Make image frame clickable too
        if is_available:
            img_frame.bind("<Button-1>", lambda _e: self._add_to_cart(pid, name, price))

        img_rel = _row_get(r, "image_path", None)
        if not img_rel:
            img_rel = os.path.join("product_images", "images.png")

        photo = self._load_image(img_rel)
        if photo:
            lbl_img = tk.Label(img_frame, image=photo, bg=THEME["panel"], cursor="hand2" if is_available else "arrow")
            lbl_img.image = photo
            lbl_img.place(relx=0.5, rely=0.5, anchor="center")
            if is_available:
                lbl_img.bind("<Button-1>", lambda _e: self._add_to_cart(pid, name, price))
        else:
            txt_label = tk.Label(img_frame, text="IMG", bg=THEME["panel"], fg=THEME["muted"], font=("Segoe UI", 9, "bold"), cursor="hand2" if is_available else "arrow")
            txt_label.place(relx=0.5, rely=0.5, anchor="center")
            if is_available:
                txt_label.bind("<Button-1>", lambda _e: self._add_to_cart(pid, name, price))

        # Truncate product name for display
        display_name = _truncate_text(name, max_len=18)
        name_lbl = tk.Label(card, text=display_name, bg=THEME["panel2"], fg=THEME["text"], font=("Segoe UI", 10, "bold"), cursor="hand2" if is_available else "arrow")
        name_lbl.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(14, 0))
        if is_available:
            name_lbl.bind("<Button-1>", lambda _e: self._add_to_cart(pid, name, price))
        
        # Add tooltip with full name if truncated
        if len(name) > 18:
            self._add_tooltip(name_lbl, name)

        tk.Label(card, text=money(price), bg=THEME["panel2"], fg=THEME["success"], font=("Segoe UI", 10, "bold")).grid(
            row=1, column=1, sticky="w", padx=(0, 12), pady=(4, 0)
        )

        tk.Label(card, text=avail_txt, bg=avail_bg, fg="white", font=("Segoe UI", 8, "bold"), padx=8, pady=2).grid(
            row=0, column=2, sticky="e", padx=12, pady=(14, 0)
        )

        if is_available:
            tk.Button(
                card,
                text="Add",
                command=lambda: self._add_to_cart(pid, name, price),
                bg=THEME.get("brown", "#6b4a3a"),
                fg="white",
                bd=0,
                padx=10,
                pady=6,
                cursor="hand2",
            ).grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(8, 12))
        else:
            tk.Label(card, text="Out of stock", bg=THEME["panel2"], fg=THEME["muted"], font=("Segoe UI", 9)).grid(
                row=2, column=1, sticky="w", padx=(0, 12), pady=(8, 12)
            )
        return card

    # ---------------- Cart ----------------
    def _add_to_cart(self, pid: int, name: str, price: float):
        if pid in self.cart:
            n, p, qty, note = self.cart[pid]
            self.cart[pid] = (n, p, qty + 1, note)
        else:
            self.cart[pid] = (name, price, 1, "")
        self._refresh_cart()

    def _remove_from_cart(self, pid: int):
        if pid in self.cart:
            del self.cart[pid]
        self._refresh_cart()

    def _change_qty(self, pid: int, delta: int):
        if pid not in self.cart:
            return
        n, p, qty, note = self.cart[pid]
        qty = qty + delta
        if qty <= 0:
            del self.cart[pid]
        else:
            self.cart[pid] = (n, p, qty, note)
        self._refresh_cart()

    def _calc_totals(self):
        subtotal = sum(qty * price for (_n, price, qty, _note) in self.cart.values())

        discount = 0.0
        if self.discount_mode == "amount":
            discount = max(0.0, min(float(self.discount_value), subtotal))
        else:
            discount = max(0.0, min(100.0, float(self.discount_value))) / 100.0 * subtotal

        tax = 0.0
        total = max(0.0, subtotal - discount + tax)
        return subtotal, discount, tax, total

    def _refresh_cart(self):
        for w in self.cart_tbl.winfo_children():
            w.destroy()

        hdr = tk.Frame(self.cart_tbl, bg=THEME["panel2"])
        hdr.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(hdr, text="Item", bg=THEME["panel2"], fg=THEME["muted"], font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(hdr, text="Qty", bg=THEME["panel2"], fg=THEME["muted"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=10)
        tk.Label(hdr, text="Subtotal", bg=THEME["panel2"], fg=THEME["muted"], font=("Segoe UI", 9, "bold")).pack(side="right")

        if not self.cart:
            tk.Label(self.cart_tbl, text="No items", bg=THEME["panel2"], fg=THEME["muted"]).pack(pady=20)
            self.total_lbl.configure(text="Total: ₱0.00")
            return

        for pid, (name, price, qty, _note) in self.cart.items():
            row = tk.Frame(self.cart_tbl, bg=THEME["panel2"])
            row.pack(fill="x", padx=10, pady=4)

            tk.Label(row, text=name, bg=THEME["panel2"], fg=THEME["text"]).pack(side="left")

            qty_box = tk.Frame(row, bg=THEME["panel2"])
            qty_box.pack(side="left", padx=10)
            tk.Button(qty_box, text="-", command=lambda p=pid: self._change_qty(p, -1), bg=THEME["panel"], fg=THEME["text"], bd=0, width=2).pack(side="left")
            tk.Label(qty_box, text=str(qty), bg=THEME["panel2"], fg=THEME["text"], width=3).pack(side="left")
            tk.Button(qty_box, text="+", command=lambda p=pid: self._change_qty(p, 1), bg=THEME["panel"], fg=THEME["text"], bd=0, width=2).pack(side="left")

            tk.Label(row, text=money(qty * price), bg=THEME["panel2"], fg=THEME["text"]).pack(side="right")
            tk.Button(row, text="x", command=lambda p=pid: self._remove_from_cart(p), bg=THEME["danger"], fg="white", bd=0, width=2).pack(side="right", padx=(0, 10))

        _subtotal, _discount, _tax, total = self._calc_totals()
        self.total_lbl.configure(text=f"Total: {money(total)}")

    # ---------------- Discount ----------------
    def _add_discount(self):
        dlg = DiscountDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        mode, value = dlg.result
        self.discount_mode = str(mode)
        self.discount_value = float(value)
        self._refresh_cart()

    # ---------------- Drafts ----------------
    def _refresh_drafts_panel(self):
        self.draft_list.delete(0, tk.END)
        self._draft_id_by_index.clear()

        rows = self.draft_dao.list_drafts()
        if not rows:
            self.draft_list.insert(tk.END, "There are no draft orders")
            self._draft_id_by_index.append(-1)
            return

        for r in rows:
            did = int(r["draft_id"])
            title = str(r["title"])
            total = float(_row_get(r, "total", 0.0))
            self.draft_list.insert(tk.END, f"{title}  •  {money(total)}")
            self._draft_id_by_index.append(did)

    def _get_selected_draft_id(self):
        sel = self.draft_list.curselection()
        if not sel:
            return None
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._draft_id_by_index):
            return None
        did = self._draft_id_by_index[idx]
        return None if did == -1 else did

    def _save_draft(self):
        if not self.cart:
            messagebox.showinfo("Draft", "No items to save.")
            return

        prompt = TextPromptDialog(self, "Save order as draft", "Draft title (example: Table 3 / Takeout):")
        self.wait_window(prompt)
        if not prompt.result:
            return

        title = prompt.result.strip()
        _subtotal, _discount, _tax, total = self._calc_totals()

        payload = {
            "cart": [
                {"product_id": pid, "name": n, "price": p, "qty": q, "note": note}
                for pid, (n, p, q, note) in self.cart.items()
            ],
            "discount_mode": self.discount_mode,
            "discount_value": self.discount_value,
        }

        try:
            self.draft_dao.create_draft(title=title, payload=payload, total=total)
            messagebox.showinfo("Draft saved", f"Draft saved: {title}")
            self._refresh_drafts_panel()

            self.cart.clear()
            self.discount_mode = "amount"
            self.discount_value = 0.0
            self._refresh_cart()
        except Exception as e:
            messagebox.showerror("Draft Error", f"Failed to save draft.\n\n{e}")

    def _load_selected_draft(self):
        did = self._get_selected_draft_id()
        if did is None:
            return

        d = self.draft_dao.get_draft(did)
        if not d:
            return

        try:
            payload = json.loads(d["payload_json"])
        except Exception:
            payload = {}

        self.discount_mode = str(payload.get("discount_mode", "amount"))
        self.discount_value = float(payload.get("discount_value", 0.0))

        self.cart.clear()
        for it in payload.get("cart", []):
            pid = int(it.get("product_id", 0))
            name = str(it.get("name", ""))
            price = float(it.get("price", 0.0))
            qty = int(it.get("qty", 1))
            note = str(it.get("note", ""))
            if pid:
                self.cart[pid] = (name, price, qty, note)

        self._refresh_cart()
        messagebox.showinfo("Draft loaded", f"Loaded: {d['title']}")

    def _delete_selected_draft(self):
        did = self._get_selected_draft_id()
        if did is None:
            return
        if not messagebox.askyesno("Delete draft", "Delete selected draft?"):
            return
        self.draft_dao.delete_draft(did)
        self._refresh_drafts_panel()

    # ---------------- Checkout -> Confirm Order modal ----------------
    def _checkout(self):
        if not self.cart:
            messagebox.showinfo("Checkout", "No items in order.")
            return
        ConfirmOrderDialog(self, self.db, self.auth, self.cart, self.discount_mode, self.discount_value, on_done=self._checkout_done)

    def _checkout_done(self, cleared: bool = True):
        if cleared:
            self.cart.clear()
            self.discount_mode = "amount"
            self.discount_value = 0.0
            self._refresh_cart()
            self._refresh_drafts_panel()


class ConfirmOrderDialog(tk.Toplevel):
    def __init__(
        self,
        parent: POSView,
        db: Database,
        auth: AuthService,
        cart: dict[int, tuple[str, float, int, str]],
        discount_mode: str,
        discount_value: float,
        on_done=None,
    ):
        super().__init__(parent)
        self.parent_view = parent
        self.db = db
        self.auth = auth
        self.order_dao = OrderDAO(db)
        self.draft_dao = DraftDAO(db)

        self.cart = dict(cart)
        self.discount_mode = discount_mode
        self.discount_value = discount_value
        self.on_done = on_done

        self.title("Confirm Order")
        self.configure(bg=THEME["bg"])
        self.geometry("420x620")
        self.transient(parent)
        self.grab_set()

        self.var_customer = tk.StringVar()
        self.var_payment = tk.StringVar(value="Cash")
        self.var_amount_paid = tk.StringVar(value="0")

        self._build()

    def _calc_totals(self):
        subtotal = sum(qty * price for (_n, price, qty, _note) in self.cart.values())

        discount = 0.0
        if self.discount_mode == "amount":
            discount = max(0.0, min(float(self.discount_value), subtotal))
        else:
            discount = max(0.0, min(100.0, float(self.discount_value))) / 100.0 * subtotal

        tax = 0.0
        total = max(0.0, subtotal - discount + tax)
        return subtotal, discount, tax, total

    def _build(self):
        # ---- Scrollable container ----
        canvas = tk.Canvas(self, bg=THEME["bg"], highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=sb.set)

        inner = tk.Frame(canvas, bg=THEME["bg"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _conf(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _conf)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        # mousewheel
        def _mw(e):
            delta = -1 if e.delta > 0 else 1
            canvas.yview_scroll(delta, "units")
        canvas.bind_all("<MouseWheel>", _mw)
        canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))

        # ---- Header ----
        top = tk.Frame(inner, bg=THEME["bg"])
        top.pack(fill="x", padx=18, pady=(14, 10))
        tk.Label(top, text="Confirm Order", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Button(top, text="✕", bg=THEME["bg"], fg=THEME["muted"], bd=0, command=self.destroy).pack(side="right")

        tk.Label(inner, text=f"Order created: (now)", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(0, 10))

        # ---- Order Details box ----
        box = tk.Frame(inner, bg="#ffffff", highlightthickness=1, highlightbackground="#e6e6e6")
        box.pack(fill="x", padx=18, pady=(0, 12))

        tk.Label(box, text="Order Details", bg="#e9efff", fg="#2f4ea3", padx=12, pady=8, font=("Segoe UI", 10, "bold")).pack(fill="x")

        body = tk.Frame(box, bg="#ffffff")
        body.pack(fill="x", padx=12, pady=10)

        subtotal, discount, tax, total = self._calc_totals()

        for pid, (name, price, qty, _note) in self.cart.items():
            r = tk.Frame(body, bg="#ffffff")
            r.pack(fill="x", pady=4)
            tk.Label(r, text=f"{qty}x {name}", bg="#ffffff", fg=THEME["text"]).pack(side="left")
            tk.Label(r, text=money(qty * price), bg="#ffffff", fg=THEME["text"]).pack(side="right")

        tot = tk.Frame(body, bg="#dff6ef")
        tot.pack(fill="x", pady=(10, 0))
        tk.Label(tot, text="Total:", bg="#dff6ef", fg=THEME["text"], padx=10, pady=8).pack(side="left")
        tk.Label(tot, text=money(total), bg="#dff6ef", fg=THEME["text"], padx=10, pady=8, font=("Segoe UI", 10, "bold")).pack(side="right")

        # ---- Customer name REQUIRED ----
        tk.Label(inner, text="Customer Name (required)", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(8, 6))
        ent_name = tk.Entry(inner, textvariable=self.var_customer, bd=0, bg="#ffffff", fg=THEME["text"])
        ent_name.pack(fill="x", padx=18, ipady=10)
        ent_name.focus_set()

        # ---- Payment method ----
        tk.Label(inner, text="Payment Method", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(12, 6))

        pm = tk.Frame(inner, bg=THEME["bg"])
        pm.pack(fill="x", padx=18)

        rb1 = tk.Radiobutton(pm, text="Cash", value="Cash", variable=self.var_payment, bg=THEME["bg"])
        rb1.pack(anchor="w")
        rb2 = tk.Radiobutton(pm, text="Bank Transfer/E-Wallet", value="Bank/E-Wallet", variable=self.var_payment, bg=THEME["bg"])
        rb2.pack(anchor="w")

        tk.Label(inner, text="Amount Paid", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(10, 6))
        tk.Entry(inner, textvariable=self.var_amount_paid, bd=0, bg="#ffffff", fg=THEME["text"]).pack(fill="x", padx=18, ipady=10)

        # ---- Footer buttons ----
        footer = tk.Frame(inner, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=18)

        tk.Button(
            footer, text="Cancel",
            bg=THEME["danger"], fg="white", bd=0, padx=14, pady=10, cursor="hand2",
            command=self.destroy
        ).pack(side="left")

        # Dropdown arrow for "Save as draft"
        arrow = tk.Menubutton(
            footer, text="▾",
            bg="#d3a24a", fg="white", bd=0, padx=10, pady=10, cursor="hand2"
        )
        m = tk.Menu(arrow, tearoff=0)
        m.add_command(label="Save as draft", command=self._save_as_draft)
        arrow.configure(menu=m)
        arrow.pack(side="right")

        self.btn_confirm = tk.Button(
            footer, text="Confirm Checkout",
            bg=THEME["success"], fg="white", bd=0, padx=14, pady=10, cursor="hand2",
            command=self._confirm
        )
        self.btn_confirm.pack(side="right", padx=(0, 10))

        # change label based on payment
        self.var_payment.trace_add("write", lambda *_: self._update_confirm_text())
        self._update_confirm_text()

    def _update_confirm_text(self):
        if self.var_payment.get() == "Bank/E-Wallet":
            self.btn_confirm.configure(text="Confirm as pending", bg="#d3a24a")
        else:
            self.btn_confirm.configure(text="Confirm Checkout", bg=THEME["success"])

    def _save_as_draft(self):
        # ask title
        prompt = TextPromptDialog(self, "Save order as draft", "Draft title (example: Table 3 / Takeout):")
        self.wait_window(prompt)
        if not prompt.result:
            return

        title = prompt.result.strip()
        _subtotal, _discount, _tax, total = self._calc_totals()

        payload = {
            "cart": [
                {"product_id": pid, "name": n, "price": p, "qty": q, "note": note}
                for pid, (n, p, q, note) in self.cart.items()
            ],
            "discount_mode": self.discount_mode,
            "discount_value": self.discount_value,
        }
        try:
            self.draft_dao.create_draft(title=title, payload=payload, total=total)
            messagebox.showinfo("Draft saved", f"Draft saved: {title}")
            if self.on_done:
                self.on_done(True)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Draft Error", f"Failed to save draft.\n\n{e}")

    def _confirm(self):
        customer = self.var_customer.get().strip()
        if not customer:
            messagebox.showerror("Customer Name", "Customer name is required.")
            return

        try:
            paid = float(self.var_amount_paid.get().strip())
        except Exception:
            messagebox.showerror("Amount Paid", "Invalid amount paid.")
            return

        subtotal, discount, tax, total = self._calc_totals()

        payment = self.var_payment.get()
        status = "Pending" if payment == "Bank/E-Wallet" else "Completed"

        # Cash rules: must be >= total
        if payment == "Cash" and paid < total:
            messagebox.showerror("Cash", f"Amount paid must be at least {money(total)}.")
            return

        change = max(0.0, paid - total) if payment == "Cash" else 0.0
        cash_received = paid if payment == "Cash" else 0.0

        # cashier
        u = self.auth.get_current_user()
        cashier_id = u.user_id if u else 0

        try:
            order_id = self.order_dao.insert_order(
                cashier_id=cashier_id,
                customer_name=customer,
                payment_method=payment,
                status=status,
                reference_no="",
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                total=total,
                amount_paid=paid,
                cash_received=cash_received,
                change_due=change,
            )
            for pid, (_name, price, qty, note) in self.cart.items():
                self.order_dao.insert_item(order_id, pid, qty, price, note)

            if status == "Pending":
                messagebox.showinfo("Saved", f"Order saved as Pending.\n\nTransaction ID: {order_id}")
            else:
                messagebox.showinfo("Completed", f"Order completed.\n\nTransaction ID: {order_id}\nChange: {money(change)}")

            if self.on_done:
                self.on_done(True)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Checkout Error", f"Failed to save order.\n\n{e}")