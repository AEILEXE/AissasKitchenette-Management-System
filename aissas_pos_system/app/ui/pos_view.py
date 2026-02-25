from __future__ import annotations

import json
import os
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from app.config import THEME, DEBUG
from app.db.database import Database
from app.db.dao import CategoryDAO, ProductDAO, DraftDAO, OrderDAO
from app.services.auth_service import AuthService
from app.ui.dialogs import DiscountDialog
from app.utils import money
from app.ml.recommender import Recommender


def _row_get(r, key: str, default=None):
    try:
        v = r[key]
        return default if v is None else v
    except Exception:
        return default


def _truncate_text(text: str, max_len: int = 20, suffix: str = "…") -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + suffix


class SimpleDraftTitleDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Widget,
        title: str = "Save order as draft",
        prompt: str = "Draft title (example: Table 3 / Takeout):",
    ):
        super().__init__(parent)
        self.configure(bg=THEME["bg"])
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: str | None = None
        self.var = tk.StringVar()

        wrap = tk.Frame(self, bg=THEME["bg"])
        wrap.pack(fill="both", expand=True, padx=18, pady=16)

        tk.Label(wrap, text=prompt, bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ent = tk.Entry(wrap, textvariable=self.var, bd=0, bg=THEME["panel2"], fg=THEME["text"])
        ent.pack(fill="x", pady=(8, 14), ipady=10)
        ent.focus_set()

        btns = tk.Frame(wrap, bg=THEME["bg"])
        btns.pack(fill="x")

        tk.Button(
            btns,
            text="Confirm",
            bg=THEME.get("brown", "#6b4a3a"),
            fg="white",
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2",
            command=self._ok,
        ).pack(side="left")

        tk.Button(
            btns,
            text="Close",
            bg=THEME["panel2"],
            fg=THEME["text"],
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2",
            command=self.destroy,
        ).pack(side="right")

        self.bind("<Return>", lambda _e: self._ok(), add="+")
        self.bind("<Escape>", lambda _e: self.destroy(), add="+")

    def _ok(self):
        val = self.var.get().strip()
        if not val:
            messagebox.showerror("Draft title", "Please enter a draft title.")
            return
        self.result = val
        self.destroy()


class POSView(tk.Frame):
    SCROLL_SPEED_UNITS = 10

    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth

        self.cat_dao = CategoryDAO(db)
        self.prod_dao = ProductDAO(db)
        self.draft_dao = DraftDAO(db)
        self.order_dao = OrderDAO(db)

        self.cart: dict[int, tuple[str, float, int, str]] = {}
        self.discount_mode: str = "amount"
        self.discount_value: float = 0.0

        self._draft_id_by_index: list[int] = []
        self._cat_buttons: dict[str, tk.Button] = {}
        self._selected_category: str = "All"

        self._products_cache = []
        self._product_card_widgets: list[tk.Frame] = []
        self._prod_resize_after = None

        self._img_cache: dict[str, tk.PhotoImage] = {}

        self._scroll_targets: list[tuple[tk.Widget, tk.Canvas]] = []
        self._scroll_enabled: dict[tk.Canvas, bool] = {}

        # Windows mousewheel
        self.bind_all("<MouseWheel>", self._route_mousewheel, add="+")

        # Linux mousewheel (Button-4 = scroll up, Button-5 = scroll down)
        self.bind_all(
            "<Button-4>",
            lambda e: self._route_mousewheel(
                type("_E", (object,), {"x_root": e.x_root, "y_root": e.y_root, "delta": 120})()
            ),
            add="+",
        )
        self.bind_all(
            "<Button-5>",
            lambda e: self._route_mousewheel(
                type("_E", (object,), {"x_root": e.x_root, "y_root": e.y_root, "delta": -120})()
            ),
            add="+",
        )

        self._search_entry: tk.Entry | None = None
        self._active_tooltip: tk.Toplevel | None = None

        self._discount_visible = False

        # ML suggestions
        self.recommender = Recommender(db)
        self._suggestions_frame: tk.Frame | None = None

        self._build()
        self.search_var.set("")
        self.after(50, self._refresh_categories)
        self._refresh_drafts_panel()
        self.after(100, self._refresh_products)
        self._refresh_cart()

    # ---------------- Tooltip ----------------
    def _add_tooltip(self, widget: tk.Widget, text: str):
        def _show(_e=None):
            try:
                self._hide_tooltip()
                tip = tk.Toplevel(widget)
                tip.wm_overrideredirect(True)
                x = widget.winfo_pointerx() + 12
                y = widget.winfo_pointery() + 12
                tip.wm_geometry(f"+{x}+{y}")
                tk.Label(
                    tip,
                    text=text,
                    bg="#ffffe0",
                    fg="black",
                    padx=8,
                    pady=4,
                    font=("Segoe UI", 9),
                    relief="solid",
                    borderwidth=1,
                ).pack()
                self._active_tooltip = tip
            except Exception:
                pass

        def _move(_e=None):
            try:
                if self._active_tooltip and self._active_tooltip.winfo_exists():
                    x = widget.winfo_pointerx() + 12
                    y = widget.winfo_pointery() + 12
                    self._active_tooltip.wm_geometry(f"+{x}+{y}")
            except Exception:
                pass

        def _hide(_e=None):
            self._hide_tooltip()

        widget.bind("<Enter>", _show, add="+")
        widget.bind("<Motion>", _move, add="+")
        widget.bind("<Leave>", _hide, add="+")

    def _hide_tooltip(self):
        try:
            if self._active_tooltip and self._active_tooltip.winfo_exists():
                self._active_tooltip.destroy()
        except Exception:
            pass
        self._active_tooltip = None

    # ---------------- Mousewheel routing ----------------
    def _register_scroll_panel(self, panel_root: tk.Widget, canvas: tk.Canvas):
        self._scroll_targets.append((panel_root, canvas))
        self._scroll_enabled[canvas] = True

    def _set_scroll_enabled(self, canvas: tk.Canvas, enabled: bool):
        self._scroll_enabled[canvas] = bool(enabled)

    def _is_descendant(self, widget: tk.Widget | None, ancestor: tk.Widget) -> bool:
        w = widget
        while w is not None:
            if w is ancestor:
                return True
            try:
                w = w.master  # type: ignore[attr-defined]
            except Exception:
                return False
        return False

    def _route_mousewheel(self, event):
        """Route mousewheel to the correct scrollable panel based on hover position."""
        try:
            hovered = self.winfo_toplevel().winfo_containing(event.x_root, event.y_root)
            if hovered is None:
                return
            for panel_root, canvas in self._scroll_targets:
                if self._is_descendant(hovered, panel_root):
                    if not canvas.winfo_exists():
                        return
                    if not self._scroll_enabled.get(canvas, True):
                        return
                    step = -1 if event.delta > 0 else 1
                    canvas.yview_scroll(step * self.SCROLL_SPEED_UNITS, "units")
                    return
        except tk.TclError:
            return

    # ---------------- Search caret fix ----------------
    def _clear_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
            widget.config(fg=THEME["text"])

    def _restore_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(fg=THEME["muted"])

    def _on_global_click(self, event):
        if not self._search_entry or not self._search_entry.winfo_exists():
            return
        if event.widget is self._search_entry:
            return
        self.focus_set()
        self._restore_placeholder(self._search_entry, "Search…")

    # ---------------- Image helpers ----------------
    def _load_default_image(self) -> object:
        key = "__default__"
        if key in self._img_cache:
            return self._img_cache[key]

        path = os.path.join(os.getcwd(), "product_images", "images.png")
        try:
            from PIL import Image, ImageTk

            img = Image.open(path)
            img = img.resize((64, 64), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._img_cache[key] = photo
            return photo
        except Exception:
            try:
                img = tk.PhotoImage(file=path)
                self._img_cache[key] = img
                return img
            except Exception:
                return None

    def _load_image(self, rel_path: str | None) -> object:
        if not rel_path:
            return self._load_default_image()

        key = f"img::{rel_path}"
        if key in self._img_cache:
            return self._img_cache[key]

        abs_path = os.path.join(os.getcwd(), rel_path)
        try:
            from PIL import Image, ImageTk

            img = Image.open(abs_path)
            img = img.resize((64, 64), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._img_cache[key] = photo
            return photo
        except Exception:
            try:
                img = tk.PhotoImage(file=abs_path)
                self._img_cache[key] = img
                return img
            except Exception:
                return self._load_default_image()

    # ---------------- UI ----------------
    def _build(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Thick.Vertical.TScrollbar",
            troughcolor=THEME["panel"],
            bordercolor=THEME["panel"],
            background=THEME["panel2"],
            darkcolor=THEME["panel2"],
            lightcolor=THEME["panel2"],
            arrowcolor=THEME["text"],
            gripcount=0,
            width=18,
        )

        body = tk.Frame(self, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(10, 18))
        body.rowconfigure(0, weight=1)

        body.columnconfigure(0, weight=1, minsize=90)
        body.columnconfigure(1, weight=8, minsize=800)
        body.columnconfigure(2, weight=2, minsize=320)

        self.winfo_toplevel().bind("<Button-1>", self._on_global_click, add="+")

        # ---------------- Left: Categories ----------------
        left = tk.Frame(body, bg=THEME["panel"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(left, text="Categories", bg=THEME["panel"], fg=THEME["text"], font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=8, pady=(8, 4)
        )

        cat_panel = tk.Frame(left, bg=THEME["panel"])
        cat_panel.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        cat_panel.rowconfigure(0, weight=1)
        cat_panel.columnconfigure(0, weight=1)

        self.cat_canvas = tk.Canvas(cat_panel, bg=THEME["panel"], highlightthickness=0)
        self.cat_canvas.grid(row=0, column=0, sticky="nsew")

        cat_sb = ttk.Scrollbar(cat_panel, orient="vertical", command=self.cat_canvas.yview, style="Thick.Vertical.TScrollbar")
        cat_sb.grid(row=0, column=1, sticky="ns")
        self.cat_canvas.configure(yscrollcommand=cat_sb.set)

        self.cat_inner = tk.Frame(self.cat_canvas, bg=THEME["panel"])
        self._cat_window_id = self.cat_canvas.create_window((0, 0), window=self.cat_inner, anchor="nw")
        self.cat_inner.bind("<Configure>", lambda _e: self.cat_canvas.configure(scrollregion=self.cat_canvas.bbox("all")), add="+")
        self.cat_canvas.bind("<Configure>", lambda e: self.cat_canvas.itemconfigure(self._cat_window_id, width=e.width), add="+")
        self._register_scroll_panel(cat_panel, self.cat_canvas)

        # ---------------- Middle: Products ----------------
        mid = tk.Frame(body, bg=THEME["panel"])
        mid.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        mid.rowconfigure(2, weight=1)

        tk.Label(mid, text="All Items", bg=THEME["panel"], fg=THEME["text"], font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=14, pady=(12, 6)
        )

        self.search_var = tk.StringVar()
        search = tk.Entry(mid, textvariable=self.search_var, bd=0, bg=THEME["panel2"], fg=THEME["text"])
        search.pack(fill="x", padx=14, pady=(0, 10), ipady=8)
        self._search_entry = search

        search.insert(0, "Search…")
        search.config(fg=THEME["muted"])
        search.bind("<FocusIn>", lambda _e: self._clear_placeholder(search, "Search…"), add="+")
        search.bind("<FocusOut>", lambda _e: self._restore_placeholder(search, "Search…"), add="+")
        search.bind("<KeyRelease>", lambda _e: self._refresh_products(), add="+")

        prod_panel = tk.Frame(mid, bg=THEME["panel"])
        prod_panel.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        prod_panel.rowconfigure(0, weight=1)
        prod_panel.columnconfigure(0, weight=1)

        self.prod_canvas = tk.Canvas(prod_panel, bg=THEME["panel"], highlightthickness=0)
        self.prod_canvas.grid(row=0, column=0, sticky="nsew")

        prod_sb = ttk.Scrollbar(prod_panel, orient="vertical", command=self.prod_canvas.yview, style="Thick.Vertical.TScrollbar")
        prod_sb.grid(row=0, column=1, sticky="ns")
        self.prod_canvas.configure(yscrollcommand=prod_sb.set)

        self.prod_inner = tk.Frame(self.prod_canvas, bg=THEME["panel"])
        self._prod_window_id = self.prod_canvas.create_window((0, 0), window=self.prod_inner, anchor="nw")
        self.prod_inner.bind("<Configure>", lambda _e: self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all")), add="+")
        self.prod_canvas.bind("<Configure>", self._on_prod_canvas_configure, add="+")
        self._register_scroll_panel(prod_panel, self.prod_canvas)

        # ---------------- Right: Cart + Drafts ----------------
        right = tk.Frame(body, bg=THEME["panel"])
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(99, weight=1)

        tk.Label(right, text="Current order", bg=THEME["panel"], fg=THEME["text"], font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=14, pady=(8, 6)
        )

        cart_panel = tk.Frame(right, bg=THEME["panel"])
        cart_panel.pack(fill="both", expand=True, padx=14, pady=(0, 4))
        cart_panel.rowconfigure(0, weight=1)
        cart_panel.columnconfigure(0, weight=1)

        self.cart_canvas = tk.Canvas(cart_panel, bg=THEME["panel2"], highlightthickness=0, height=200)
        self.cart_canvas.grid(row=0, column=0, sticky="nsew")

        cart_sb = ttk.Scrollbar(cart_panel, orient="vertical", command=self.cart_canvas.yview, style="Thick.Vertical.TScrollbar")
        cart_sb.grid(row=0, column=1, sticky="ns")
        self.cart_canvas.configure(yscrollcommand=cart_sb.set)

        self.cart_tbl = tk.Frame(self.cart_canvas, bg=THEME["panel2"])
        self._cart_window_id = self.cart_canvas.create_window((0, 0), window=self.cart_tbl, anchor="nw")
        self.cart_tbl.bind("<Configure>", lambda _e: self.cart_canvas.configure(scrollregion=self.cart_canvas.bbox("all")), add="+")
        self.cart_canvas.bind("<Configure>", lambda e: self.cart_canvas.itemconfigure(self._cart_window_id, width=e.width), add="+")
        self._register_scroll_panel(cart_panel, self.cart_canvas)

        # ---------------- Suggestions Panel (ML) ----------------
        # Created here but NOT packed — _refresh_suggestions() packs/unpacks it
        # dynamically between cart_panel and _footer_top.
        self._suggestions_frame = tk.Frame(right, bg=THEME["panel"])

        # ---------------- Totals row ----------------
        self._footer_top = tk.Frame(right, bg=THEME["panel"])
        self._footer_top.pack(fill="x", padx=14, pady=(0, 6))
        self._footer_top.columnconfigure(0, weight=1)
        self._footer_top.columnconfigure(1, weight=0)
        footer_top = self._footer_top  # local alias

        self.total_lbl = tk.Label(footer_top, text="Total: ₱0.00", bg=THEME["panel"], fg=THEME["text"], font=("Segoe UI", 12, "bold"))
        self.total_lbl.grid(row=0, column=0, sticky="w")

        self.discount_lbl = tk.Label(footer_top, text="", bg=THEME["panel"], fg=THEME["muted"], font=("Segoe UI", 10, "bold"))

        # ---------------- Action buttons ----------------
        footer_btns = tk.Frame(right, bg=THEME["panel"])
        footer_btns.pack(fill="x", padx=14, pady=(0, 10))

        # Brown background makes "Add Discount" visible against the light panel
        tk.Button(
            footer_btns,
            text="Add Discount",
            command=self._add_discount,
            bg=THEME["brown"],
            fg="white",
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2",
        ).pack(side="left", padx=(0, 5))

        tk.Button(
            footer_btns,
            text="Save as Draft",
            command=self._save_draft,
            bg=THEME.get("brown_dark", "#3E2A22"),
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

        # ---------------- Drafts panel ----------------
        self.drafts_section = tk.Frame(right, bg=THEME["panel"])

        tk.Label(self.drafts_section, text="Draft orders", bg=THEME["panel"], fg=THEME["text"], font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=(6, 6))
        self.draft_list = tk.Listbox(self.drafts_section, height=6, bd=0, highlightthickness=0, bg=THEME["panel2"], fg=THEME["text"], activestyle="none")
        self.draft_list.pack(fill="x", padx=14)
        self.draft_list.bind("<Double-Button-1>", lambda _e: self._load_selected_draft(), add="+")
        self.draft_list.bind("<MouseWheel>", self._draft_mousewheel, add="+")

        draft_btns = tk.Frame(self.drafts_section, bg=THEME["panel"])
        draft_btns.pack(fill="x", padx=14, pady=(8, 12))
        draft_btns.columnconfigure(0, weight=1, uniform="dbtn")
        draft_btns.columnconfigure(1, weight=1, uniform="dbtn")
        draft_btns.columnconfigure(2, weight=1, uniform="dbtn")

        tk.Button(draft_btns, text="Load", command=self._load_selected_draft, bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=6, pady=6, font=("Segoe UI", 9, "bold"), cursor="hand2").grid(row=0, column=0, sticky="ew", padx=(0, 6))
        tk.Button(draft_btns, text="Delete", command=self._delete_selected_draft, bg=THEME["danger"], fg="white", bd=0, padx=6, pady=6, font=("Segoe UI", 9, "bold"), cursor="hand2").grid(row=0, column=1, sticky="ew", padx=6)
        tk.Button(draft_btns, text="Delete all", command=self._delete_all_drafts, bg=THEME["danger"], fg="white", bd=0, padx=6, pady=6, font=("Segoe UI", 9, "bold"), cursor="hand2").grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _on_prod_canvas_configure(self, e):
        try:
            self.prod_canvas.itemconfigure(self._prod_window_id, width=e.width)
        except Exception:
            pass
        self._debounced_relayout()

    def _draft_mousewheel(self, e):
        try:
            step = -1 if e.delta > 0 else 1
            self.draft_list.yview_scroll(step * self.SCROLL_SPEED_UNITS, "units")
        except tk.TclError:
            pass

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
        q = (search_text or "").strip().lower()
        if not q or q in ["search", "search…"]:
            q = ""
        cat_name = self._selected_category or "All"
        try:
            if cat_name == "All":
                rows = self.prod_dao.list_all_active()
            else:
                c = self.cat_dao.get_by_name(cat_name)
                rows = self.prod_dao.list_by_category(int(c["category_id"])) if c else []
        except Exception as e:
            print("Product query failed:", e)
            messagebox.showerror("DB Error", str(e))
            return []
        out = []
        for r in rows:
            name = str(r["name"]).lower()
            if q and q not in name:
                continue
            out.append(r)
        return out

    def _calc_product_cols(self) -> int:
        width = max(1, int(self.prod_canvas.winfo_width()))
        return 3 if width >= 860 else 2

    def _debounced_relayout(self) -> None:
        if self._prod_resize_after is not None:
            try:
                self.after_cancel(self._prod_resize_after)
            except Exception:
                pass
        self._prod_resize_after = self.after(80, self._relayout_products)

    def _refresh_products(self):
        search_text = self.search_var.get().strip()
        if search_text == "Search…":
            search_text = ""
        self._products_cache = self._filter_products(search_text)
        self._relayout_products(rebuild_cards=True)

    def _relayout_products(self, rebuild_cards: bool = False) -> None:
        if rebuild_cards:
            for w in self.prod_inner.winfo_children():
                w.destroy()
            if not self._products_cache:
                tk.Label(self.prod_inner, text="No items found. Clear search or seed products.", bg=THEME["panel"], fg=THEME["muted"], font=("Segoe UI", 12, "bold")).pack(pady=40)
                self._product_card_widgets = []
            else:
                self._product_card_widgets = [self._product_card(self.prod_inner, r) for r in self._products_cache]

        cards = self._product_card_widgets
        cols = self._calc_product_cols()
        cols = 2 if cols < 2 else (3 if cols > 3 else cols)

        for i in range(3):
            self.prod_inner.columnconfigure(i, weight=0)
        for i in range(cols):
            self.prod_inner.columnconfigure(i, weight=1, uniform="prodcol")

        for w in cards:
            w.grid_forget()

        for idx, card in enumerate(cards):
            row = idx // cols
            col = idx % cols
            card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        for r in range((len(cards) + cols - 1) // cols):
            self.prod_inner.rowconfigure(r, weight=1)

        self.prod_inner.update_idletasks()
        self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all"))

    # ✅ Entire card clickable — _bind_click() applied to frame + all child labels
    def _product_card(self, parent: tk.Widget, r) -> tk.Frame:
        pid = int(r["product_id"])
        name = str(r["name"])
        price = float(r["price"])
        stock = int(_row_get(r, "stock_qty", 0))
        is_available = stock > 0

        card = tk.Frame(parent, bg=THEME["panel2"], bd=0, cursor="hand2" if is_available else "arrow")
        card.columnconfigure(1, weight=1)
        card.rowconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        card.rowconfigure(2, weight=1)

        def _bind_click(w: tk.Widget):
            if is_available:
                w.bind("<Button-1>", lambda _e: self._add_to_cart(pid, name, price), add="+")

        _bind_click(card)

        img_frame = tk.Frame(card, bg=THEME["panel"], width=80, height=80,
                             cursor="hand2" if is_available else "arrow")
        img_frame.grid(row=0, column=0, rowspan=3, padx=10, pady=10)
        img_frame.grid_propagate(False)
        _bind_click(img_frame)

        img_rel = _row_get(r, "image_path", None) or os.path.join("product_images", "images.png")
        photo = self._load_image(img_rel)
        if photo:
            lbl_img = tk.Label(img_frame, image=photo, bg=THEME["panel"],
                               cursor="hand2" if is_available else "arrow")
            lbl_img.image = photo
            lbl_img.place(relx=0.5, rely=0.5, anchor="center")
            _bind_click(lbl_img)
        else:
            lbl_no = tk.Label(img_frame, text="IMG", bg=THEME["panel"], fg=THEME["muted"],
                              font=("Segoe UI", 9, "bold"),
                              cursor="hand2" if is_available else "arrow")
            lbl_no.place(relx=0.5, rely=0.5, anchor="center")
            _bind_click(lbl_no)

        if is_available:
            badge = tk.Label(img_frame, text="Available", bg=THEME["success"], fg="white",
                             font=("Segoe UI", 8, "bold"), padx=8, pady=1)
            badge.place(relx=0.5, rely=1.0, anchor="s", y=-6)
            _bind_click(badge)
        else:
            badge = tk.Label(img_frame, text="Not Available", bg=THEME["danger"], fg="white",
                             font=("Segoe UI", 8, "bold"), padx=6, pady=1)
            badge.place(relx=0.5, rely=1.0, anchor="s", y=-6)

        display_name = _truncate_text(name, max_len=20)
        name_lbl = tk.Label(card, text=display_name, bg=THEME["panel2"], fg=THEME["text"],
                            font=("Segoe UI", 10, "bold"), anchor="w", justify="left",
                            cursor="hand2" if is_available else "arrow")
        name_lbl.grid(row=0, column=1, sticky="ew", padx=(10, 12), pady=(12, 0))
        _bind_click(name_lbl)
        if display_name.endswith("…"):
            self._add_tooltip(name_lbl, name)

        price_lbl = tk.Label(card, text=money(price), bg=THEME["panel2"], fg=THEME["success"],
                             font=("Segoe UI", 10, "bold"), anchor="w",
                             cursor="hand2" if is_available else "arrow")
        price_lbl.grid(row=1, column=1, sticky="w", padx=(10, 12), pady=(4, 0))
        _bind_click(price_lbl)

        if is_available:
            tk.Button(
                card, text="Add",
                command=lambda: self._add_to_cart(pid, name, price),
                bg=THEME.get("brown", "#6b4a3a"), fg="white",
                bd=0, padx=12, pady=6, cursor="hand2",
            ).grid(row=2, column=1, sticky="w", padx=(10, 12), pady=(8, 12))
        else:
            tk.Label(card, text="Out of stock", bg=THEME["panel2"], fg=THEME["muted"],
                     font=("Segoe UI", 9)).grid(row=2, column=1, sticky="w", padx=(10, 12), pady=(8, 12))

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

    def _set_discount_next_to_total(self, text: str | None):
        if text:
            self.discount_lbl.configure(text=text)
            if not self._discount_visible:
                self.discount_lbl.grid(row=0, column=1, sticky="e")
                self._discount_visible = True
        else:
            if self._discount_visible:
                self.discount_lbl.grid_forget()
                self._discount_visible = False

    def _refresh_cart(self):
        for w in self.cart_tbl.winfo_children():
            w.destroy()

        # Column layout:
        #  0: item name  (expands)
        #  1: − button   (fixed)
        #  2: qty label  (fixed)
        #  3: + button   (fixed)
        #  4: subtotal   (fixed, right-aligned)
        #  5: × remove   (fixed)
        self.cart_tbl.columnconfigure(0, weight=1, minsize=100)
        self.cart_tbl.columnconfigure(1, weight=0, minsize=24)
        self.cart_tbl.columnconfigure(2, weight=0, minsize=28)
        self.cart_tbl.columnconfigure(3, weight=0, minsize=24)
        self.cart_tbl.columnconfigure(4, weight=0, minsize=62)
        self.cart_tbl.columnconfigure(5, weight=0, minsize=32)

        # Header row
        tk.Label(
            self.cart_tbl, text="Item",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(14, 6), pady=(10, 6))

        tk.Label(
            self.cart_tbl, text="Qty",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9, "bold"), anchor="center",
        ).grid(row=0, column=1, columnspan=3, sticky="ew", pady=(10, 6))

        tk.Label(
            self.cart_tbl, text="Subtotal",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9, "bold"), anchor="e",
        ).grid(row=0, column=4, sticky="ew", padx=(4, 4), pady=(10, 6))

        if not self.cart:
            self._set_scroll_enabled(self.cart_canvas, False)
            self._set_discount_next_to_total(None)
            try:
                self.cart_canvas.yview_moveto(0)
                self.cart_canvas.configure(scrollregion=(0, 0, 0, 0))
            except Exception:
                pass
            tk.Label(
                self.cart_tbl, text="No items",
                bg=THEME["panel2"], fg=THEME["muted"],
            ).grid(row=1, column=0, columnspan=6, pady=20)
            self.total_lbl.configure(text="Total: ₱0.00")
            self.after(30, self._refresh_suggestions)
            return

        row_i = 1
        for pid, (name, price, qty, _note) in self.cart.items():
            name_txt = _truncate_text(name, max_len=18)

            tk.Label(
                self.cart_tbl, text=name_txt,
                bg=THEME["panel2"], fg=THEME["text"], anchor="w",
            ).grid(row=row_i, column=0, sticky="ew", padx=(14, 4), pady=4)

            tk.Button(
                self.cart_tbl, text="−",
                command=lambda p=pid: self._change_qty(p, -1),
                bg=THEME["panel"], fg=THEME["text"],
                bd=0, width=2, cursor="hand2",
            ).grid(row=row_i, column=1, padx=2, pady=4)

            tk.Label(
                self.cart_tbl, text=str(qty),
                bg=THEME["panel2"], fg=THEME["text"],
                width=3, anchor="center",
            ).grid(row=row_i, column=2, padx=2, pady=4)

            tk.Button(
                self.cart_tbl, text="+",
                command=lambda p=pid: self._change_qty(p, 1),
                bg=THEME["panel"], fg=THEME["text"],
                bd=0, width=2, cursor="hand2",
            ).grid(row=row_i, column=3, padx=2, pady=4)

            tk.Label(
                self.cart_tbl, text=money(qty * price),
                bg=THEME["panel2"], fg=THEME["text"], anchor="e",
            ).grid(row=row_i, column=4, sticky="e", padx=(4, 4), pady=4)

            tk.Button(
                self.cart_tbl,
                text="✕",
                command=lambda p=pid: self._remove_from_cart(p),
                bg=THEME["danger"],
                fg="white",
                bd=0,
                width=3,
                padx=2,
                pady=2,
                cursor="hand2",
                font=("Segoe UI", 9, "bold"),
            ).grid(row=row_i, column=5, padx=(4, 10), pady=4, sticky="e")

            row_i += 1

        _subtotal, discount, _tax, total = self._calc_totals()
        self.total_lbl.configure(text=f"Total: {money(total)}")

        if discount > 0:
            self._set_discount_next_to_total(f"Discount: -{money(discount)}")
        else:
            self._set_discount_next_to_total(None)

        self.cart_tbl.update_idletasks()
        bbox = self.cart_canvas.bbox("all")
        if bbox:
            self.cart_canvas.configure(scrollregion=bbox)

        try:
            content_h = (bbox[3] - bbox[1]) if bbox else 0
            canvas_h = self.cart_canvas.winfo_height()
            self._set_scroll_enabled(self.cart_canvas, content_h > canvas_h + 2)
        except Exception:
            self._set_scroll_enabled(self.cart_canvas, True)

        # Refresh ML suggestions after every cart change
        self.after(60, self._refresh_suggestions)

    # ---------------- ML Suggestions ----------------
    def _refresh_suggestions(self):
        """
        Rebuild the 'Suggested Items' panel based on the current cart.

        States:
          1. Cart empty                   → hide panel entirely
          2. Cart has items, no ML data   → show muted "No suggestions yet" message
          3. Cart has items, suggestions  → show up to 3 clickable buttons
                                            (out-of-stock items are skipped)

        Panel is packed dynamically BEFORE _footer_top so it appears between
        the cart and the totals/buttons row.
        """
        if self._suggestions_frame is None:
            return

        # Clear stale content first
        for w in self._suggestions_frame.winfo_children():
            w.destroy()

        # ── State 1: cart empty → hide ──────────────────────────────────────
        if not self.cart:
            if self._suggestions_frame.winfo_ismapped():
                self._suggestions_frame.pack_forget()
            return

        # ── Fetch suggestions ────────────────────────────────────────────────
        cart_ids = list(self.cart.keys())

        if DEBUG:
            print(f"[POS] _refresh_suggestions — cart_ids: {cart_ids}")

        try:
            suggested_ids = self.recommender.suggest(cart_ids, top_n=3)
        except Exception as exc:
            if DEBUG:
                print(f"[POS] recommender.suggest() raised: {exc}")
            suggested_ids = []

        if DEBUG:
            print(f"[POS] suggested_ids returned to UI: {suggested_ids}")

        # ── State 2: no data yet → show muted placeholder ───────────────────
        if not suggested_ids:
            hdr2 = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
            hdr2.pack(fill="x", padx=14, pady=(8, 2))
            tk.Label(
                hdr2,
                text="💡 Suggested Items",
                bg=THEME["panel"],
                fg=THEME["muted"],
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")

            tk.Label(
                self._suggestions_frame,
                text="No suggestions yet — complete more sales",
                bg=THEME["panel"],
                fg=THEME["muted"],
                font=("Segoe UI", 8, "italic"),
            ).pack(anchor="w", padx=14, pady=(0, 8))

            if not self._suggestions_frame.winfo_ismapped():
                self._suggestions_frame.pack(fill="x", pady=(2, 0), before=self._footer_top)
            return

        # ── State 3: render suggestion buttons ──────────────────────────────

        # Resolve display names in one pass (uses internal name cache)
        try:
            names = self.recommender.get_product_names(suggested_ids)
        except Exception:
            names = {pid: f"Item #{pid}" for pid in suggested_ids}

        # Header
        hdr3 = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
        hdr3.pack(fill="x", padx=14, pady=(8, 2))
        tk.Label(
            hdr3,
            text="💡 Suggested Items",
            bg=THEME["panel"],
            fg=THEME["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        btn_row = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
        btn_row.pack(fill="x", padx=14, pady=(0, 8))

        rendered = 0
        for pid in suggested_ids:
            # ── Resolve stock and price ──────────────────────────────────────
            stock_qty: int = 0
            price: float = 0.0
            found_in_cache = False

            # Fast path: check the already-loaded active product cache
            for cached_row in self._products_cache:
                if int(cached_row["product_id"]) == pid:
                    stock_qty = int(_row_get(cached_row, "stock_qty", 0))
                    price = float(cached_row["price"])
                    found_in_cache = True
                    break

            # Fallback: ask the DAO directly (handles products not in current filter)
            if not found_in_cache:
                try:
                    prod = self.prod_dao.get(pid)
                    if prod:
                        stock_qty = prod.stock_qty
                        price = prod.price
                except Exception:
                    pass

            # ── Skip out-of-stock suggestions ───────────────────────────────
            if stock_qty <= 0:
                if DEBUG:
                    print(f"[POS] Skipping suggestion #{pid} — out of stock (qty={stock_qty})")
                continue

            # ── Last-resort price fallback via recommender helper ────────────
            if price == 0.0:
                try:
                    price = self.recommender.get_product_price(pid)
                except Exception:
                    price = 0.0

            name = names.get(pid, f"#{pid}")
            display = _truncate_text(name, max_len=14)

            def _add(p=pid, n=name, pr=price):
                self._add_to_cart(p, n, pr)

            btn = tk.Button(
                btn_row,
                text=f"+ {display}",
                command=_add,
                bg=THEME.get("beige", "#EADFD2"),
                fg=THEME["brown"],
                bd=1,
                relief="solid",
                padx=6,
                pady=4,
                cursor="hand2",
                font=("Segoe UI", 8),
                wraplength=80,
                justify="center",
            )
            btn.pack(side="left", padx=(0, 6))

            if len(name) > 14:
                self._add_tooltip(btn, name)

            rendered += 1

        if DEBUG:
            print(f"[POS] Rendered {rendered} suggestion button(s).")

        # If every suggested item was out-of-stock, show the "no data" message
        if rendered == 0:
            for w in self._suggestions_frame.winfo_children():
                w.destroy()

            hdr_empty = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
            hdr_empty.pack(fill="x", padx=14, pady=(8, 2))
            tk.Label(
                hdr_empty,
                text="💡 Suggested Items",
                bg=THEME["panel"],
                fg=THEME["muted"],
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")

            tk.Label(
                self._suggestions_frame,
                text="No suggestions yet — complete more sales",
                bg=THEME["panel"],
                fg=THEME["muted"],
                font=("Segoe UI", 8, "italic"),
            ).pack(anchor="w", padx=14, pady=(0, 8))

        # Ensure panel is visible just above the totals row
        if not self._suggestions_frame.winfo_ismapped():
            self._suggestions_frame.pack(fill="x", pady=(2, 0), before=self._footer_top)

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
        rows = self.draft_dao.list_drafts()
        if not rows:
            try:
                self.drafts_section.pack_forget()
            except Exception:
                pass
            self._draft_id_by_index.clear()
            try:
                self.draft_list.delete(0, tk.END)
            except Exception:
                pass
            return

        if not self.drafts_section.winfo_ismapped():
            self.drafts_section.pack(fill="x", pady=(0, 6))

        self.draft_list.delete(0, tk.END)
        self._draft_id_by_index.clear()

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

        dlg = SimpleDraftTitleDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        title = dlg.result.strip()

        _subtotal, _discount, _tax, total = self._calc_totals()

        payload = {
            "cart": [{"product_id": pid, "name": n, "price": p, "qty": q, "note": note} for pid, (n, p, q, note) in self.cart.items()],
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

        try:
            self.draft_dao.delete_draft(did)
        except Exception:
            pass

        self._refresh_cart()
        self._refresh_drafts_panel()
        messagebox.showinfo("Draft loaded", f"Loaded: {d['title']}")

    def _delete_selected_draft(self):
        did = self._get_selected_draft_id()
        if did is None:
            return
        if not messagebox.askyesno("Delete draft", "Delete selected draft?"):
            return
        self.draft_dao.delete_draft(did)
        self._refresh_drafts_panel()

    def _delete_all_drafts(self):
        rows = self.draft_dao.list_drafts()
        if not rows:
            messagebox.showinfo("Draft orders", "There are no drafts to delete.")
            return
        if not messagebox.askyesno("Delete all drafts", "Delete ALL draft orders?"):
            return
        try:
            for r in rows:
                self.draft_dao.delete_draft(int(r["draft_id"]))
            self._refresh_drafts_panel()
            messagebox.showinfo("Draft orders", "All drafts deleted.")
        except Exception as e:
            messagebox.showerror("Draft orders", f"Failed to delete all drafts.\n\n{e}")

    # ---------------- Checkout ----------------
    def _checkout(self):
        if not self.cart:
            messagebox.showinfo("Checkout", "No items in order.")
            return
        ConfirmOrderDialog(self, self.db, self.auth, self.cart, self.discount_mode, self.discount_value, on_done=self._checkout_done)

    # ✅ FIX: cache is only invalidated when the order was actually Completed.
    #         Pending orders do NOT update the ML pair-frequency data.
    def _checkout_done(self, cleared: bool = True, completed: bool = False):
        if cleared:
            self.cart.clear()
            self.discount_mode = "amount"
            self.discount_value = 0.0
            self._refresh_cart()
            self._refresh_drafts_panel()

            if completed:
                # Only invalidate when a real sale was recorded
                self.recommender.invalidate_cache()


class ConfirmOrderDialog(tk.Toplevel):
    SCROLL_SPEED_UNITS = 10

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

        self.created_at = datetime.now()
        u = self.auth.get_current_user()
        self.created_by_role = (u.role.upper() if u else "—")
        self.created_by_user = (u.username if u else "—")

        self.title("Confirm Order")
        self.configure(bg=THEME["bg"])
        self.geometry("420x620")
        self.transient(parent)
        self.grab_set()

        self.var_customer = tk.StringVar()
        self.var_payment = tk.StringVar(value="Cash")
        self.var_amount_paid = tk.StringVar(value="")

        self._details_expanded = tk.BooleanVar(value=False)
        self._details_rows: list[tuple[str, str]] = []
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
        wrap = tk.Frame(self, bg=THEME["bg"])
        wrap.pack(fill="both", expand=True)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        canvas = tk.Canvas(wrap, bg=THEME["bg"], highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview, style="Thick.Vertical.TScrollbar")
        sb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=sb.set)

        inner = tk.Frame(canvas, bg=THEME["bg"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")), add="+")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width), add="+")

        def _mw(e):
            step = -1 if e.delta > 0 else 1
            canvas.yview_scroll(step * self.SCROLL_SPEED_UNITS, "units")
            return "break"

        self.bind("<MouseWheel>", _mw, add="+")
        self.bind("<Button-4>", lambda _e: (canvas.yview_scroll(-self.SCROLL_SPEED_UNITS, "units"), "break"), add="+")
        self.bind("<Button-5>", lambda _e: (canvas.yview_scroll(self.SCROLL_SPEED_UNITS, "units"), "break"), add="+")

        top = tk.Frame(inner, bg=THEME["bg"])
        top.pack(fill="x", padx=18, pady=(14, 10))
        tk.Label(top, text="Confirm Order", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Button(top, text="✕", bg=THEME["bg"], fg=THEME["muted"], bd=0, command=self.destroy).pack(side="right")

        created_str = self.created_at.strftime("%Y-%m-%d %I:%M %p")
        tk.Label(
            inner,
            text=f"Order created: {created_str}  •  By: {self.created_by_user} ({self.created_by_role})",
            bg=THEME["bg"],
            fg=THEME["muted"],
        ).pack(anchor="w", padx=18, pady=(0, 10))

        box = tk.Frame(inner, bg="#ffffff", highlightthickness=1, highlightbackground="#e6e6e6")
        box.pack(fill="x", padx=18, pady=(0, 12))

        head = tk.Frame(box, bg="#e9efff")
        head.pack(fill="x")
        tk.Label(head, text="Order Details", bg="#e9efff", fg="#2f4ea3", padx=12, pady=8, font=("Segoe UI", 10, "bold")).pack(side="left")

        self.btn_toggle = tk.Button(
            head,
            text="▸ Show",
            bg="#e9efff",
            fg="#2f4ea3",
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
            command=self._toggle_details,
        )
        self.btn_toggle.pack(side="right")

        self.details_body = tk.Frame(box, bg="#ffffff")
        self.details_body.pack(fill="x", padx=12, pady=10)

        self._details_rows = []
        subtotal, discount, tax, total = self._calc_totals()
        for _pid, (name, price, qty, _note) in self.cart.items():
            self._details_rows.append((f"{qty}x {name}", money(qty * price)))

        self._discount_amount = discount
        self._total_amount = total

        self._render_details()

        tk.Label(inner, text="Customer Name (required)", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(8, 6))
        ent_name = tk.Entry(inner, textvariable=self.var_customer, bd=0, bg="#ffffff", fg=THEME["text"])
        ent_name.pack(fill="x", padx=18, ipady=10)
        ent_name.focus_set()

        tk.Label(inner, text="Payment Method", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(12, 6))
        pm = tk.Frame(inner, bg=THEME["bg"])
        pm.pack(fill="x", padx=18)
        tk.Radiobutton(pm, text="Cash", value="Cash", variable=self.var_payment, bg=THEME["bg"]).pack(anchor="w")
        tk.Radiobutton(pm, text="Bank Transfer/E-Wallet", value="Bank/E-Wallet", variable=self.var_payment, bg=THEME["bg"]).pack(anchor="w")

        tk.Label(inner, text="Amount Paid", bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(10, 6))
        ent_paid = tk.Entry(inner, textvariable=self.var_amount_paid, bd=0, bg="#ffffff", fg=THEME["text"])
        ent_paid.pack(fill="x", padx=18, ipady=10)

        footer = tk.Frame(inner, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=18)

        tk.Button(
            footer,
            text="Cancel",
            bg=THEME["danger"],
            fg="white",
            bd=0,
            padx=14,
            pady=10,
            cursor="hand2",
            command=self.destroy,
        ).pack(side="left")

        self.btn_confirm = tk.Button(
            footer,
            text="Confirm Checkout",
            bg=THEME["success"],
            fg="white",
            bd=0,
            padx=14,
            pady=10,
            cursor="hand2",
            command=self._confirm,
        )
        self.btn_confirm.pack(side="right")

        self.var_payment.trace_add("write", lambda *_: self._update_confirm_text())
        self._update_confirm_text()

    def _toggle_details(self):
        self._details_expanded.set(not self._details_expanded.get())
        self._render_details()

    def _render_details(self):
        for w in self.details_body.winfo_children():
            w.destroy()

        expanded = self._details_expanded.get()
        self.btn_toggle.configure(text="▾ Hide" if expanded else "▸ Show")

        rows = self._details_rows if expanded else self._details_rows[:5]
        for left_text, right_text in rows:
            r = tk.Frame(self.details_body, bg="#ffffff")
            r.pack(fill="x", pady=4)
            tk.Label(r, text=left_text, bg="#ffffff", fg=THEME["text"]).pack(side="left")
            tk.Label(r, text=right_text, bg="#ffffff", fg=THEME["text"]).pack(side="right")

        if not expanded and len(self._details_rows) > 5:
            tk.Label(self.details_body, text=f"+ {len(self._details_rows) - 5} more items", bg="#ffffff", fg=THEME["muted"]).pack(anchor="w", pady=(6, 0))

        if self._discount_amount > 0:
            drow = tk.Frame(self.details_body, bg="#ffffff")
            drow.pack(fill="x", pady=(10, 0))
            tk.Label(drow, text="Discount", bg="#ffffff", fg=THEME["muted"]).pack(side="left")
            tk.Label(drow, text=f"-{money(self._discount_amount)}", bg="#ffffff", fg=THEME["muted"]).pack(side="right")

        tot = tk.Frame(self.details_body, bg="#dff6ef")
        tot.pack(fill="x", pady=(10, 0))
        tk.Label(tot, text="Total:", bg="#dff6ef", fg=THEME["text"], padx=10, pady=8).pack(side="left")
        tk.Label(tot, text=money(self._total_amount), bg="#dff6ef", fg=THEME["text"], padx=10, pady=8, font=("Segoe UI", 10, "bold")).pack(side="right")

    def _update_confirm_text(self):
        if self.var_payment.get() == "Bank/E-Wallet":
            self.btn_confirm.configure(text="Confirm as pending", bg="#d3a24a")
        else:
            self.btn_confirm.configure(text="Confirm Checkout", bg=THEME["success"])

    def _confirm(self):
        customer = self.var_customer.get().strip()
        if not customer:
            messagebox.showerror("Customer Name", "Customer name is required.")
            return

        paid_str = self.var_amount_paid.get().strip()
        if paid_str == "":
            paid_str = "0"
        try:
            paid = float(paid_str)
        except Exception:
            messagebox.showerror("Amount Paid", "Invalid amount paid.")
            return

        subtotal, discount, tax, total = self._calc_totals()
        payment = self.var_payment.get()
        status = "Pending" if payment == "Bank/E-Wallet" else "Completed"

        if payment == "Cash" and paid < total:
            messagebox.showerror("Cash", f"Amount paid must be at least {money(total)}.")
            return

        change = max(0.0, paid - total) if payment == "Cash" else 0.0
        cash_received = paid if payment == "Cash" else 0.0

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

            # ✅ FIX: pass completed=True only when status is "Completed"
            #         so the ML cache is only invalidated for real sales,
            #         not for Pending (bank/e-wallet) orders.
            if self.on_done:
                self.on_done(True, status == "Completed")

            self.destroy()
        except Exception as e:
            messagebox.showerror("Checkout Error", f"Failed to save order.\n\n{e}")
