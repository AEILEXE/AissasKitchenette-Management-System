from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

from app.config import THEME, resolve_image_path, PRODUCT_IMAGES_DIR
from app.db.database import Database
from app.db.dao import CategoryDAO, ProductDAO, DraftDAO, OrderDAO
from app.services.auth_service import AuthService
from app.services.pos_service import POSService
from app.services.receipt_service import ReceiptService
from app.ui.dialogs import DiscountDialog, DraftTitleDialog
from app.ui import ui_scale
from app.utils import money
from app.ml.recommender import Recommender


# Module-level image cache — persists for the entire app lifetime so images
# are never garbage-collected even when POSView instances are recreated.
_GLOBAL_IMG_CACHE: dict = {}


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


class POSView(tk.Frame):
    SCROLL_SPEED_UNITS = 3

    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth

        self.cat_dao = CategoryDAO(db)
        self.prod_dao = ProductDAO(db)
        self.draft_dao = DraftDAO(db)
        self.order_dao = OrderDAO(db)
        self.svc = POSService(db)

        self.cart: dict[int, tuple[str, float, int, str]] = {}
        self.var_order_type: tk.StringVar | None = None
        self.var_table_number: tk.StringVar | None = None
        self.var_payment: tk.StringVar | None = None
        self._lbl_table_no: tk.Label | None = None
        self._change_lbl: tk.Label | None = None
        self._product_stock: dict[int, int] = {}
        self.discount_mode: str = "NONE"
        self.discount_value: float = 0.0

        self._draft_id_by_index: list[int] = []
        self._cat_buttons: dict[str, tk.Button] = {}
        self._selected_category: str = "All"

        self._products_cache = []
        self._all_products_cache: list[Any] = []
        self._all_products_cache_cat: str = ""
        self._search_after: int | None = None
        self._product_card_widgets: list[tk.Frame] = []
        self._prod_resize_after: int | None = None
        self._prod_canvas_w: int = 0
        self._cart_resize_after: int | None = None
        self._last_wm_state: str = "normal"
        self._load_gen: int = 0

        self._img_cache = _GLOBAL_IMG_CACHE  # shared, never GC'd

        self._batch_products: list[Any] = []
        self._batch_idx: int = 0
        self._batch_after: int | None = None
        self._loading_lbl: tk.Label | None = None

        self._after_ids: set[int] = set()
        self._destroyed: bool = False
        self._building: bool = True
        self._suggest_after: int | None = None
        self._global_click_id: str | None = None

        self._search_entry: tk.Entry | None = None
        self._active_tooltip: tk.Toplevel | None = None

        self._discount_visible = False

        self.var_amount_paid: tk.StringVar | None = None
        self._amount_entry: tk.Entry | None = None
        self._lbl_subtotal_val: tk.Label | None = None
        self._lbl_discount_row: tk.Frame | None = None
        self._lbl_discount_name: tk.Label | None = None
        self._lbl_discount_val: tk.Label | None = None
        self._lbl_total_val: tk.Label | None = None
        self._cart_row_refs: dict[int, dict[str, tk.Label]] = {}

        # Category grid layout tracking
        self._cat_grid_frame: tk.Frame | None = None
        self._cat_grid_after: int | None = None
        self._cat_grid_width: int = 0

        try:
            self.recommender = Recommender(db)
        except Exception:
            self.recommender = None
        self._suggestions_frame: tk.Frame | None = None

        self._build()
        self._building = False
        self._preload_folder_images_async()   # warm cache before first card render
        self._after(50, self._refresh_categories)
        self._after(100, self._refresh_products)
        self._after(200, self._refresh_drafts_panel)  # defer — not needed immediately
        self._refresh_cart()
        self.after_idle(self._debounced_relayout)

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def destroy(self) -> None:
        self._destroyed = True
        self._building = False
        for aid in list(self._after_ids):
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()

        if self._global_click_id is not None:
            try:
                tl = self.winfo_toplevel()
                if tl and tl.winfo_exists():
                    tl.unbind("<Button-1>", self._global_click_id)
            except Exception:
                pass
            self._global_click_id = None

        for _attr in ("prod_canvas", "cart_canvas"):
            try:
                cv = getattr(self, _attr, None)
                if cv is not None:
                    cv.unbind_all("<MouseWheel>")
                    cv.unbind_all("<Button-4>")
                    cv.unbind_all("<Button-5>")
            except Exception:
                pass

        self._hide_tooltip()
        super().destroy()

    def _after(self, ms: int, fn: Callable[..., object], *a: object) -> int | None:
        if self._destroyed or self._building or not self.winfo_exists():
            return None
        def _cb():
            self._after_ids.discard(aid)
            if not self._destroyed and self.winfo_exists():
                fn(*a)
        aid = self.after(ms, _cb)
        self._after_ids.add(aid)
        return aid

    def _cancel_after(self, aid: int | None) -> None:
        if aid is not None:
            try:
                self.after_cancel(aid)
            except Exception:
                pass
            self._after_ids.discard(aid)

    # ── Tooltip ───────────────────────────────────────────────────────────────
    def _add_tooltip(self, widget: tk.Widget, text: str):
        def _show(_e=None):
            try:
                self._hide_tooltip()
                tip = tk.Toplevel(widget)
                tip.wm_overrideredirect(True)
                x = widget.winfo_pointerx() + 12
                y = widget.winfo_pointery() + 12
                tip.wm_geometry(f"+{x}+{y}")
                tk.Label(tip, text=text, bg="#ffffe0", fg="black", padx=8, pady=4,
                         font=("Segoe UI", 9), relief="solid", borderwidth=1).pack()
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

        widget.bind("<Enter>", _show, add="+")
        widget.bind("<Motion>", _move, add="+")
        widget.bind("<Leave>", lambda _e: self._hide_tooltip(), add="+")

    def _hide_tooltip(self):
        try:
            if self._active_tooltip and self._active_tooltip.winfo_exists():
                self._active_tooltip.destroy()
        except Exception:
            pass
        self._active_tooltip = None

    # ── Mousewheel routing ────────────────────────────────────────────────────
    def _bind_canvas_scroll(self, canvas: tk.Canvas) -> None:
        def _scroll(event):
            if not canvas.winfo_exists():
                return
            step = -1 if event.delta > 0 else 1
            canvas.yview_scroll(step * self.SCROLL_SPEED_UNITS, "units")

        def _linux_up(event):
            if not canvas.winfo_exists():
                return
            canvas.yview_scroll(-self.SCROLL_SPEED_UNITS, "units")

        def _linux_down(event):
            if not canvas.winfo_exists():
                return
            canvas.yview_scroll(self.SCROLL_SPEED_UNITS, "units")

        def _on_enter(_e):
            canvas.bind_all("<MouseWheel>", _scroll)
            canvas.bind_all("<Button-4>", _linux_up)
            canvas.bind_all("<Button-5>", _linux_down)

        def _on_leave(_e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _on_enter, add="+")
        canvas.bind("<Leave>", _on_leave, add="+")

    # ── Search placeholder ────────────────────────────────────────────────────
    def _clear_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == placeholder:
            widget.delete(0, tk.END)
            widget.config(fg=THEME["text"])

    def _restore_placeholder(self, widget: tk.Entry, placeholder: str):
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(fg=THEME["muted"])

    def _on_global_click(self, event):
        if isinstance(event.widget, tk.Entry):
            return
        if not self._search_entry or not self._search_entry.winfo_exists():
            return
        if event.widget is self._search_entry:
            return
        self.focus_set()
        self._restore_placeholder(self._search_entry, "Search Products")

    # ── Image helpers ─────────────────────────────────────────────────────────
    _IMG_SIZE = 70   # product card image size (px)

    def _load_default_image(self) -> object:
        key = "__default__"
        if key in self._img_cache:
            return self._img_cache[key]
        for rel in (
            os.path.join("product_images", "images.png"),
            os.path.join("product_images", "images.jpg"),
            os.path.join("assets", "product_images", "images.jpg"),
        ):
            path = resolve_image_path(rel)
            if path is None:
                continue
            try:
                from PIL import Image, ImageTk
                img = Image.open(path).convert("RGBA")
                _resample = getattr(Image, "Resampling", Image).LANCZOS
                img = img.resize((self._IMG_SIZE, self._IMG_SIZE), _resample)
                photo = ImageTk.PhotoImage(img)
                self._img_cache[key] = photo
                return photo
            except Exception:
                try:
                    img = tk.PhotoImage(file=str(path))
                    self._img_cache[key] = img
                    return img
                except Exception:
                    continue
        return None

    def _load_image(self, rel_path: str | None) -> object:
        if not rel_path:
            return self._load_default_image()
        # Normalise path separators so DB values with backslashes work
        rel_norm = rel_path.replace("\\", "/").strip()
        key = f"img::{rel_norm}"
        if key in self._img_cache:
            return self._img_cache[key]
        # Try the normalised relative path first, then the original
        path = resolve_image_path(rel_norm)
        if path is None:
            path = resolve_image_path(rel_path)
        if path is None:
            return self._load_default_image()
        try:
            from PIL import Image, ImageTk
            img = Image.open(path).convert("RGBA")
            _resample = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize((self._IMG_SIZE, self._IMG_SIZE), _resample)
            photo = ImageTk.PhotoImage(img)
            self._img_cache[key] = photo
            return photo
        except Exception:
            try:
                img = tk.PhotoImage(file=str(path))
                self._img_cache[key] = img
                return img
            except Exception:
                return self._load_default_image()

    def _preload_images_async(self) -> None:
        """Warm _img_cache for all product images in background so card renders never hit disk.

        PIL resize work runs in a daemon thread; ImageTk.PhotoImage creation is
        marshalled back to the main thread via after(0, ...) to satisfy Tkinter's
        requirement that PhotoImages are created on the main thread.
        """
        # Paths from the current DB product cache
        db_paths: list[str] = []
        for p in self._all_products_cache:
            rel = (_row_get(p, "image_path", None) or "").strip()
            if rel:
                db_paths.append(rel.replace("\\", "/"))

        # All files sitting in the product_images folder on disk
        folder_paths: list[str] = []
        try:
            if PRODUCT_IMAGES_DIR.exists():
                for f in PRODUCT_IMAGES_DIR.iterdir():
                    if f.is_file() and f.suffix.lower() in {
                        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                    }:
                        folder_paths.append(f"product_images/{f.name}")
        except Exception:
            pass

        # Deduplicate while keeping DB paths first (most likely to be displayed first)
        seen: set[str] = set()
        all_paths: list[str] = []
        for rp in db_paths + folder_paths:
            if rp not in seen:
                seen.add(rp)
                all_paths.append(rp)

        if not all_paths:
            return

        def _worker() -> None:
            for rel_path in all_paths:
                if self._destroyed:
                    return
                key = f"img::{rel_path}"
                if key in self._img_cache:
                    continue
                try:
                    from PIL import Image, ImageTk as _ITk  # noqa: F401
                    path = resolve_image_path(rel_path)
                    if path is None:
                        continue
                    img = Image.open(path).convert("RGBA")
                    _resample = getattr(Image, "Resampling", Image).LANCZOS
                    img_r = img.resize((self._IMG_SIZE, self._IMG_SIZE), _resample)

                    def _create(img_resized=img_r, k=key) -> None:
                        if self._destroyed or k in self._img_cache:
                            return
                        try:
                            from PIL import ImageTk as _ITk2
                            self._img_cache[k] = _ITk2.PhotoImage(img_resized)
                        except Exception:
                            pass

                    if not self._destroyed:
                        self.after(0, _create)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _preload_folder_images_async(self) -> None:
        """Scan product_images/ on disk and warm the cache without needing DB data.
        Called immediately at startup so images are ready before cards render."""
        def _worker() -> None:
            try:
                if not PRODUCT_IMAGES_DIR.exists():
                    return
                for f in PRODUCT_IMAGES_DIR.iterdir():
                    if self._destroyed:
                        return
                    if not f.is_file() or f.suffix.lower() not in {
                        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                    }:
                        continue
                    rel = f"product_images/{f.name}"
                    key = f"img::{rel}"
                    if key in self._img_cache:
                        continue
                    try:
                        from PIL import Image, ImageTk as _ITk
                        img = Image.open(f).convert("RGBA")
                        _resample = getattr(Image, "Resampling", Image).LANCZOS
                        img_r = img.resize((self._IMG_SIZE, self._IMG_SIZE), _resample)

                        def _create(img_resized=img_r, k=key) -> None:
                            if self._destroyed or k in self._img_cache:
                                return
                            try:
                                from PIL import ImageTk as _ITk2
                                self._img_cache[k] = _ITk2.PhotoImage(img_resized)
                            except Exception:
                                pass

                        if not self._destroyed:
                            self.after(0, _create)
                    except Exception:
                        pass
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    # ── UI Build ──────────────────────────────────────────────────────────────
    def _build(self):
        style = ttk.Style()
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
        body.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=5, minsize=380)   # Products
        body.columnconfigure(1, weight=2, minsize=220)   # Current Order
        body.columnconfigure(2, weight=3, minsize=260)   # Payment

        try:
            self._global_click_id = self.winfo_toplevel().bind("<Button-1>", self._on_global_click, add="+")
        except Exception:
            self._global_click_id = None

        # ══ LEFT / PRODUCT AREA ══════════════════════════════════════════════
        prod_area = tk.Frame(body, bg=THEME["panel"])
        prod_area.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        prod_area.rowconfigure(2, weight=1)
        prod_area.columnconfigure(0, weight=1)

        # ── ROW 0: Search bar (ABOVE categories) ──────────────────────────────
        search_outer = tk.Frame(prod_area, bg=THEME["panel"])
        search_outer.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        search_frame = tk.Frame(search_outer, bg=THEME["panel2"])
        search_frame.pack(fill="x")

        self.search_var = tk.StringVar()
        search = tk.Entry(
            search_frame, textvariable=self.search_var,
            bd=0, bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 10),
        )
        search.pack(fill="x", ipady=7, padx=(10, 10))
        self._search_entry = search

        search.insert(0, "Search Products")
        search.config(fg=THEME["muted"])
        search.bind("<FocusIn>",  lambda _e: self._clear_placeholder(search, "Search Products"), add="+")
        search.bind("<FocusOut>", lambda _e: self._restore_placeholder(search, "Search Products"), add="+")
        search.bind("<KeyRelease>", lambda _e: self._debounced_search(), add="+")

        # ── ROW 1: Wrapping category grid (BELOW search) ─────────────────────
        cat_outer = tk.Frame(prod_area, bg=THEME["panel"])
        cat_outer.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        cat_outer.columnconfigure(0, weight=1)

        self._cat_grid_frame = tk.Frame(cat_outer, bg=THEME["panel"])
        self._cat_grid_frame.grid(row=0, column=0, sticky="ew")

        self._cat_grid_frame.bind("<Configure>", self._on_cat_grid_configure, add="+")

        self.cat_canvas = None
        self.cat_inner = self._cat_grid_frame

        # ── ROW 2: Product grid canvas ────────────────────────────────────────
        prod_panel = tk.Frame(prod_area, bg=THEME["panel"])
        prod_panel.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        prod_panel.rowconfigure(0, weight=1)
        prod_panel.columnconfigure(0, weight=1)

        self.prod_canvas = tk.Canvas(prod_panel, bg="#e6ddbd", highlightthickness=0)
        self.prod_canvas.grid(row=0, column=0, sticky="nsew")

        prod_sb = ttk.Scrollbar(prod_panel, orient="vertical", command=self.prod_canvas.yview,
                                style="Thick.Vertical.TScrollbar")
        prod_sb.grid(row=0, column=1, sticky="ns")
        self.prod_canvas.configure(yscrollcommand=prod_sb.set)

        self.prod_inner = tk.Frame(self.prod_canvas, bg="#e6ddbd")
        self._prod_window_id = self.prod_canvas.create_window((0, 0), window=self.prod_inner, anchor="nw")
        self.prod_inner.bind(
            "<Configure>",
            lambda _e: self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all")),
            add="+",
        )
        self.prod_canvas.bind("<Configure>", self._on_prod_canvas_configure, add="+")
        self._bind_canvas_scroll(self.prod_canvas)

        # ══ COLUMN 1 — CURRENT ORDER + TOTALS ══════════════════════════════════
        col1 = tk.Frame(body, bg=THEME["panel"])
        col1.grid(row=0, column=1, sticky="nsew", padx=(0, 6))
        col1.rowconfigure(1, weight=1)   # cart list expands
        col1.columnconfigure(0, weight=1)

        # ── ORDER HEADER ──────────────────────────────────────────────────────
        order_bar = tk.Frame(col1, bg=THEME.get("brown_dark", "#8E0000"))
        order_bar.grid(row=0, column=0, sticky="ew")
        tk.Label(order_bar, text="Current Order",
                 bg=THEME.get("brown_dark", "#8E0000"), fg="white",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=14, pady=7)

        # ── CART CANVAS (expands) ─────────────────────────────────────────────
        self._cart_panel = tk.Frame(col1, bg=THEME["panel"])
        self._cart_panel.grid(row=1, column=0, sticky="nsew", padx=8, pady=(6, 0))
        self._cart_panel.rowconfigure(0, weight=1)
        self._cart_panel.columnconfigure(0, weight=1)

        self.cart_canvas = tk.Canvas(self._cart_panel, bg=THEME["panel2"],
                                     highlightthickness=0, height=120)
        self.cart_canvas.grid(row=0, column=0, sticky="nsew")

        cart_sb = ttk.Scrollbar(self._cart_panel, orient="vertical", command=self.cart_canvas.yview,
                                style="Thick.Vertical.TScrollbar")
        cart_sb.grid(row=0, column=1, sticky="ns")
        self.cart_canvas.configure(yscrollcommand=cart_sb.set)

        self.cart_tbl = tk.Frame(self.cart_canvas, bg=THEME["panel2"])
        self._cart_window_id = self.cart_canvas.create_window((0, 0), window=self.cart_tbl, anchor="nw")
        self.cart_tbl.bind("<Configure>", self._on_cart_tbl_configure, add="+")
        self.cart_canvas.bind(
            "<Configure>",
            lambda e: self.cart_canvas.itemconfigure(self._cart_window_id, width=e.width),
            add="+",
        )
        self._bind_canvas_scroll(self.cart_canvas)

        # ── ML SUGGESTIONS (row=2) ────────────────────────────────────────────
        self._suggestions_frame = tk.Frame(col1, bg=THEME["panel"])
        self._suggestions_frame.grid(row=2, column=0, sticky="ew")

        # ── TOTALS (row=3) ────────────────────────────────────────────────────
        self._footer_top = tk.Frame(col1, bg=THEME["panel"])
        self._footer_top.grid(row=3, column=0, sticky="ew", padx=8, pady=(6, 0))

        totals_box = tk.Frame(self._footer_top, bg=THEME["panel2"],
                              highlightthickness=1,
                              highlightbackground=THEME["border"])
        totals_box.pack(fill="x")

        _tv_pad = (12, 16)   # left, right padding for all value labels

        # Subtotal row
        sub_row = tk.Frame(totals_box, bg=THEME["panel2"])
        sub_row.pack(fill="x", padx=0, pady=(8, 2))
        tk.Label(sub_row, text="Subtotal", bg=THEME["panel2"], fg=THEME["muted"],
                 font=("Segoe UI", 9), anchor="w").pack(side="left", padx=_tv_pad)
        self._lbl_subtotal_val = tk.Label(sub_row, text="₱0.00",
                                          bg=THEME["panel2"], fg=THEME["muted"],
                                          font=("Segoe UI", 9))
        self._lbl_subtotal_val.pack(side="right", padx=_tv_pad)

        # Discount row (hidden until active)
        self._lbl_discount_row = tk.Frame(totals_box, bg=THEME["panel2"])
        self._lbl_discount_name = tk.Label(self._lbl_discount_row, text="Discount",
                                           bg=THEME["panel2"], fg=THEME["muted"],
                                           font=("Segoe UI", 9), anchor="w")
        self._lbl_discount_name.pack(side="left", padx=_tv_pad)
        self._lbl_discount_val = tk.Label(self._lbl_discount_row, text="",
                                          bg=THEME["panel2"], fg=THEME["danger"],
                                          font=("Segoe UI", 9, "bold"))
        self._lbl_discount_val.pack(side="right", padx=_tv_pad)

        # VAT row
        vat_row = tk.Frame(totals_box, bg=THEME["panel2"])
        vat_row.pack(fill="x", padx=0, pady=(2, 8))
        tk.Label(vat_row, text="VAT", bg=THEME["panel2"], fg=THEME["muted"],
                 font=("Segoe UI", 9), anchor="w").pack(side="left", padx=_tv_pad)
        tk.Label(vat_row, text="12% incl.", bg=THEME["panel2"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "italic")).pack(side="right", padx=_tv_pad)

        # Divider
        tk.Frame(totals_box, bg=THEME["border"], height=1).pack(fill="x")

        # TOTAL row — highlighted background
        _total_bg = THEME.get("brown_dark", "#8E0000")
        total_row = tk.Frame(totals_box, bg=_total_bg)
        total_row.pack(fill="x")
        tk.Label(total_row, text="TOTAL", bg=_total_bg, fg="white",
                 font=("Segoe UI", 11, "bold"), pady=9).pack(side="left", padx=_tv_pad)
        self._lbl_total_val = tk.Label(total_row, text="₱0.00",
                                       bg=_total_bg, fg="#00c853",
                                       font=("Segoe UI", 16, "bold"))
        self._lbl_total_val.pack(side="right", padx=_tv_pad)

        self.total_lbl = self._lbl_total_val
        self.discount_lbl = tk.Label(self._footer_top, text="",
                                     bg=THEME["panel"], fg=THEME["muted"],
                                     font=("Segoe UI", 10, "bold"))

        # ── DRAFTS PANEL (row=4) ──────────────────────────────────────────────
        self.drafts_section = tk.Frame(col1, bg=THEME["panel"])
        self.drafts_section.grid(row=4, column=0, sticky="ew")

        _dh = tk.Frame(self.drafts_section, bg=THEME["panel"])
        _dh.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(_dh, text="Draft Orders", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        tk.Frame(self.drafts_section, bg=THEME["border"], height=1).pack(fill="x", padx=10)

        self.draft_list = tk.Listbox(
            self.drafts_section, height=3, bd=0, highlightthickness=0,
            bg=THEME["panel2"], fg=THEME["text"],
            selectbackground=THEME["select_bg"],
            selectforeground=THEME["select_fg"],
            activestyle="none", font=("Segoe UI", 9),
        )
        self.draft_list.pack(fill="x", padx=10, pady=(4, 0))
        self.draft_list.bind("<Double-Button-1>", lambda _e: self._load_selected_draft(), add="+")
        self.draft_list.bind("<MouseWheel>", self._draft_mousewheel, add="+")

        draft_btns = tk.Frame(self.drafts_section, bg=THEME["panel"])
        draft_btns.pack(fill="x", padx=10, pady=(4, 6))

        tk.Button(draft_btns, text="Load Draft", command=self._load_selected_draft,
                  bg=THEME["brown"], fg="white", bd=0, padx=10, pady=5,
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  ).pack(side="left", fill="x", expand=True, padx=(0, 3))

        tk.Button(draft_btns, text="Delete", command=self._delete_selected_draft,
                  bg=THEME["danger"], fg="white", bd=0, padx=10, pady=5,
                  font=("Segoe UI", 9), cursor="hand2",
                  ).pack(side="left", fill="x", expand=True, padx=(0, 3))

        tk.Button(draft_btns, text="Delete All", command=self._delete_all_drafts,
                  bg=THEME["panel2"], fg=THEME["danger"], bd=0, padx=10, pady=5,
                  font=("Segoe UI", 9),
                  ).pack(side="left", fill="x", expand=True)

        # ══ COLUMN 2 — PAYMENT + KEYPAD ═════════════════════════════════════
        col2 = tk.Frame(body, bg=THEME["panel"])
        col2.grid(row=0, column=2, sticky="nsew")
        col2.columnconfigure(0, weight=1)

        _pad = 10

        # ── PAY NOW — packed bottom-first so it is always visible ─────────────
        self._btn_pay_now = tk.Button(col2, text="Pay Now",
                                      command=self._pay_now,
                                      bg=THEME.get("brown_dark", "#8E0000"), fg="white",
                                      activebackground=THEME.get("brown", "#6b4a3a"),
                                      activeforeground="white",
                                      bd=0, pady=14, cursor="hand2",
                                      font=("Segoe UI", 13, "bold"))
        self._btn_pay_now.pack(side="bottom", fill="x", padx=_pad, pady=(6, _pad))

        tk.Frame(col2, bg=THEME["border"], height=1).pack(side="bottom", fill="x", padx=_pad, pady=(4, 0))

        # ── DISCOUNT + SAVE DRAFT — above Pay Now ─────────────────────────────
        mid_btns = tk.Frame(col2, bg=THEME["panel"])
        mid_btns.pack(side="bottom", fill="x", padx=_pad, pady=(4, 2))
        mid_btns.columnconfigure(0, weight=1, uniform="mb")
        mid_btns.columnconfigure(1, weight=1, uniform="mb")

        tk.Button(mid_btns, text="Discount", command=self._add_discount,
                  bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=6, pady=8,
                  cursor="hand2", font=("Segoe UI", 9, "bold"),
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        tk.Button(mid_btns, text="Save Draft", command=self._save_draft,
                  bg=THEME["panel2"], fg=THEME["muted"], bd=0, padx=6, pady=8,
                  cursor="hand2", font=("Segoe UI", 9),
                  ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # ── ORDER TYPE ────────────────────────────────────────────────────────
        tk.Frame(col2, bg=THEME["border"], height=1).pack(fill="x")
        ot_hdr = tk.Frame(col2, bg=THEME.get("brown_dark", "#8E0000"))
        ot_hdr.pack(fill="x")
        tk.Label(ot_hdr, text="Order Type", bg=THEME.get("brown_dark", "#8E0000"), fg="white",
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=14, pady=6)

        self.var_order_type = tk.StringVar(value="DINE_IN")
        ot_btns = tk.Frame(col2, bg=THEME["panel"])
        ot_btns.pack(fill="x", padx=_pad, pady=(6, 4))
        ot_btns.columnconfigure(0, weight=1, uniform="ot")
        ot_btns.columnconfigure(1, weight=1, uniform="ot")

        def _ot_style(selected: str):
            for _var, _btn in (("DINE_IN", btn_dine), ("TAKE_OUT", btn_take)):
                if _var == selected:
                    _btn.configure(bg=THEME.get("brown_dark", "#8E0000"), fg="white")
                else:
                    _btn.configure(bg=THEME["panel2"], fg=THEME["text"])

        def _on_ot(val):
            self.var_order_type.set(val)
            _ot_style(val)
            lbl = "Table No." if val == "DINE_IN" else "Order No."
            if self._lbl_table_no:
                self._lbl_table_no.configure(text=lbl)

        btn_dine = tk.Button(ot_btns, text="Dine In",
                             bg=THEME.get("brown_dark", "#8E0000"), fg="white",
                             bd=0, pady=10, cursor="hand2",
                             font=("Segoe UI", 11, "bold"),
                             command=lambda: _on_ot("DINE_IN"))
        btn_dine.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        btn_take = tk.Button(ot_btns, text="Take Out",
                             bg=THEME["panel2"], fg=THEME["text"],
                             bd=0, pady=10, cursor="hand2",
                             font=("Segoe UI", 11, "bold"),
                             command=lambda: _on_ot("TAKE_OUT"))
        btn_take.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # ── TABLE / ORDER NO. ─────────────────────────────────────────────────
        tbl_outer = tk.Frame(col2, bg=THEME["panel"])
        tbl_outer.pack(fill="x", padx=_pad, pady=(2, 6))
        self._lbl_table_no = tk.Label(tbl_outer, text="Table No.",
                                      bg=THEME["panel"], fg=THEME["muted"],
                                      font=("Segoe UI", 8, "bold"))
        self._lbl_table_no.pack(anchor="w", pady=(0, 2))
        self.var_table_number = tk.StringVar()
        tk.Entry(tbl_outer, textvariable=self.var_table_number,
                 bg=THEME["panel2"], fg=THEME["text"], bd=0,
                 font=("Segoe UI", 11, "bold"), justify="center",
                 insertbackground=THEME["text"],
                 ).pack(fill="x", ipady=7)

        # ── PAYMENT METHOD ────────────────────────────────────────────────────
        tk.Frame(col2, bg=THEME["border"], height=1).pack(fill="x", padx=_pad)
        tk.Label(col2, text="Payment Method", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=_pad, pady=(6, 2))

        self.var_payment = tk.StringVar(value="Cash")
        pay_btns = tk.Frame(col2, bg=THEME["panel"])
        pay_btns.pack(fill="x", padx=_pad, pady=(0, 6))
        pay_btns.columnconfigure(0, weight=1, uniform="pb")
        pay_btns.columnconfigure(1, weight=1, uniform="pb")

        def _pay_style(selected: str):
            for _var, _btn in (("Cash", btn_cash), ("Bank/E-Wallet", btn_bank)):
                if _var == selected:
                    _btn.configure(bg=THEME.get("brown_dark", "#8E0000"), fg="white")
                else:
                    _btn.configure(bg=THEME["panel2"], fg=THEME["text"])

        def _on_pay(val):
            self.var_payment.set(val)
            _pay_style(val)
            _update_change_lbl()

        btn_cash = tk.Button(pay_btns, text="Cash",
                             bg=THEME.get("brown_dark", "#8E0000"), fg="white",
                             bd=0, pady=7, cursor="hand2",
                             font=("Segoe UI", 9, "bold"),
                             command=lambda: _on_pay("Cash"))
        btn_cash.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        btn_bank = tk.Button(pay_btns, text="Bank/E-Wallet",
                             bg=THEME["panel2"], fg=THEME["text"],
                             bd=0, pady=7, cursor="hand2",
                             font=("Segoe UI", 8, "bold"),
                             command=lambda: _on_pay("Bank/E-Wallet"))
        btn_bank.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # ── AMOUNT PAID ───────────────────────────────────────────────────────
        tk.Frame(col2, bg=THEME["border"], height=1).pack(fill="x", padx=_pad)
        tk.Label(col2, text="Amount Paid", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=_pad, pady=(6, 2))

        self.var_amount_paid = tk.StringVar(value="")
        self._amount_entry = tk.Entry(
            col2, textvariable=self.var_amount_paid,
            font=("Segoe UI", 13, "bold"),
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, justify="right",
            insertbackground=THEME["text"],
        )
        self._amount_entry.pack(fill="x", padx=_pad, ipady=7)
        self._amount_entry.bind("<Key>", self._on_amount_key)

        self._change_lbl = tk.Label(col2, text="", bg=THEME["panel"], fg=THEME["muted"],
                                    font=("Segoe UI", 8, "bold"), anchor="w")
        self._change_lbl.pack(fill="x", padx=_pad, pady=(2, 4))

        def _update_change_lbl(*_):
            if self.var_amount_paid is None or self._change_lbl is None:
                return
            try:
                paid = float(self.var_amount_paid.get().strip() or "0")
            except ValueError:
                self._change_lbl.configure(text="", fg=THEME["muted"], bg=THEME["panel"])
                return
            if self.var_payment and self.var_payment.get() == "Bank/E-Wallet":
                self._change_lbl.configure(text="", fg=THEME["muted"], bg=THEME["panel"])
                return
            _, _, _, total = self._calc_totals()
            diff = paid - total
            if diff < 0 and total > 0:
                self._change_lbl.configure(
                    text=f"  Short: {money(abs(diff))} more",
                    fg=THEME["danger"], bg="#FEF2F2")
            elif total > 0:
                self._change_lbl.configure(
                    text=f"  Change: {money(diff)}",
                    fg=THEME["success"], bg="#F0FDF4")
            else:
                self._change_lbl.configure(text="", fg=THEME["muted"], bg=THEME["panel"])

        self.var_amount_paid.trace_add("write", _update_change_lbl)
        self.var_payment.trace_add("write", _update_change_lbl)
        self._update_change_lbl_fn = _update_change_lbl

        # ── COMPACT KEYPAD (expands to fill remaining space) ─────────────────
        tk.Frame(col2, bg=THEME["border"], height=1).pack(fill="x", padx=_pad)
        _kp = tk.Frame(col2, bg=THEME["panel"])
        _kp.pack(fill="both", expand=True, padx=_pad, pady=(6, 6))
        _kp_rows = [
            ("7", "8", "9"),
            ("4", "5", "6"),
            ("1", "2", "3"),
            ("0", ".", "CLEAR"),
        ]
        for _ri in range(len(_kp_rows)):
            _kp.rowconfigure(_ri, weight=1)
        for _ri, _keys in enumerate(_kp_rows):
            for _ci, _key in enumerate(_keys):
                _kp.columnconfigure(_ci, weight=1, uniform="kp")
                is_special = _key in (".", "CLEAR")
                tk.Button(
                    _kp, text=_key,
                    command=lambda k=_key: self._keypad_press(k),
                    bg=THEME["panel2"] if is_special else THEME.get("brown", "#6b4a3a"),
                    fg=THEME["text"] if is_special else "white",
                    activebackground=THEME.get("beige", "#FFF3E0"),
                    activeforeground=THEME["text"],
                    bd=0, padx=6, pady=10, cursor="hand2",
                    font=("Segoe UI", 13, "bold"),
                ).grid(row=_ri, column=_ci, sticky="nsew", padx=2, pady=2)

    # ── Keypad ────────────────────────────────────────────────────────────────
    def _keypad_press(self, key: str) -> None:
        if self.var_amount_paid is None:
            return
        current = self.var_amount_paid.get().strip()
        if key == "CLEAR" or key == "C":
            self.var_amount_paid.set("")
            return
        if key == "←":
            self.var_amount_paid.set(current[:-1])
            return
        if key == ".":
            if "." in current:
                return
            self.var_amount_paid.set((current or "0") + ".")
            return
        if key.isdigit():
            if current == "0":
                self.var_amount_paid.set(key)
            else:
                self.var_amount_paid.set(current + key)

    def _on_amount_key(self, event: tk.Event) -> str:
        """Route keyboard input on the amount-paid entry through the keypad logic."""
        sym = event.keysym
        if sym in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self._keypad_press(sym)
        elif sym == "period":
            self._keypad_press(".")
        elif sym == "BackSpace":
            current = self.var_amount_paid.get() if self.var_amount_paid else ""
            if self.var_amount_paid:
                self.var_amount_paid.set(current[:-1])
        elif sym in ("Delete", "Escape"):
            self._keypad_press("CLEAR")
        # Block all default entry behaviour so the StringVar update is the only effect
        return "break"

    # ── Canvas resize ─────────────────────────────────────────────────────────
    def _on_prod_canvas_configure(self, e: object) -> None:
        ew: int = int(getattr(e, "width", 0))
        try:
            self.prod_canvas.itemconfigure(self._prod_window_id, width=ew)
        except Exception:
            pass

        old_w = self._prod_canvas_w
        self._prod_canvas_w = ew

        # Detect window state change (maximize / restore)
        try:
            new_state = self.winfo_toplevel().state()
        except Exception:
            new_state = self._last_wm_state
        state_changed = new_state != self._last_wm_state
        self._last_wm_state = new_state

        # If only the WM state changed but canvas width is identical, skip relayout
        if state_changed and ew == old_w:
            return

        if state_changed:
            # Maximize/restore: skip the 150 ms debounce — use 30 ms instead
            self._cancel_after(self._prod_resize_after)
            self._prod_resize_after = self._after(30, self._relayout_products)
        else:
            self._debounced_relayout()

    def _draft_mousewheel(self, e):
        try:
            step = -1 if e.delta > 0 else 1
            self.draft_list.yview_scroll(step * self.SCROLL_SPEED_UNITS, "units")
        except tk.TclError:
            pass

    # ── Category grid (wrapping, uniform buttons) ─────────────────────────────
    def _on_cat_grid_configure(self, event=None) -> None:
        if self._destroyed or self._building:
            return
        new_w = self._cat_grid_frame.winfo_width() if self._cat_grid_frame else 0
        if new_w < 10 or new_w == self._cat_grid_width:
            return
        self._cat_grid_width = new_w
        self._cancel_after(self._cat_grid_after)
        self._cat_grid_after = self._after(80, self._relayout_cat_grid)

    def _relayout_cat_grid(self) -> None:
        """Place all category buttons into a uniform grid that wraps based on frame width."""
        self._cat_grid_after = None
        if self._destroyed or not self.winfo_exists():
            return
        frame = self._cat_grid_frame
        if not frame or not frame.winfo_exists():
            return

        buttons = list(self._cat_buttons.values())
        if not buttons:
            return

        frame_w = frame.winfo_width()
        if frame_w < 10:
            return

        # Fixed button width (in chars) for uniformity — about 5–6 per row
        # Estimate pixel width per char ~7px at font size 8; +padx overhead ~20
        # Target 5–6 cols: try 6, reduce if buttons would overflow
        btn_char_w = 14  # fixed width in characters
        btn_px_est = btn_char_w * 7 + 24  # ~122px per button
        cols = max(4, min(8, frame_w // max(btn_px_est, 60)))

        # Clear old grid config
        for c in range(10):
            try:
                frame.columnconfigure(c, weight=0, uniform="")
            except Exception:
                pass

        # Re-grid all buttons with uniform width
        for i, btn in enumerate(buttons):
            btn.grid_forget()
            btn.grid(row=i // cols, column=i % cols, padx=2, pady=2, sticky="ew")

        # Uniform column weights so all columns are the same width
        for c in range(cols):
            frame.columnconfigure(c, weight=1, uniform="catcol")

    def _set_active_category_btn(self, name: str) -> None:
        self._selected_category = name
        for cat_name, btn in self._cat_buttons.items():
            if cat_name == name:
                btn.configure(bg=THEME["select_bg"], fg=THEME["select_fg"])
            else:
                btn.configure(bg=THEME.get("brown", "#6b4a3a"), fg="white")

    def _refresh_categories(self):
        if self._destroyed or not self.winfo_exists():
            return
        frame = self._cat_grid_frame
        if not frame or not frame.winfo_exists():
            return
        for w in frame.winfo_children():
            w.destroy()
        self._cat_buttons.clear()
        self._cat_grid_width = 0

        def add_btn(name: str):
            btn = tk.Button(
                frame,
                text=name,
                anchor="center",
                command=lambda n=name: self._on_category_click(n),
                bg=THEME.get("brown", "#6b4a3a"),
                fg="white",
                activebackground=THEME["select_bg"],
                activeforeground=THEME["select_fg"],
                bd=0,
                # Fixed width in characters for uniform sizing
                width=14,
                height=2,
                cursor="hand2",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                wraplength=100,
                justify="center",
            )
            self._cat_buttons[name] = btn

        add_btn("All")
        for r in self.cat_dao.list_categories():
            add_btn(str(r["name"]))

        self._set_active_category_btn(
            self._selected_category if self._selected_category in self._cat_buttons else "All"
        )
        self._cancel_after(self._cat_grid_after)
        self._cat_grid_after = self._after(60, self._relayout_cat_grid)

    def _on_category_click(self, name: str) -> None:
        self._set_active_category_btn(name)
        self._all_products_cache = []
        self._all_products_cache_cat = ""
        self._load_gen += 1  # discard any in-flight background load for old category
        self._refresh_products()

    # ── Products ──────────────────────────────────────────────────────────────
    _SEARCH_DEBOUNCE_MS = 150

    def _debounced_search(self) -> None:
        self._cancel_after(self._search_after)
        self._search_after = self._after(self._SEARCH_DEBOUNCE_MS, self._refresh_products)

    def _load_products_for_category(self) -> None:
        """Fetch products from DB in a background thread; continue on main thread."""
        cat_name = self._selected_category or "All"
        self._load_gen += 1
        gen = self._load_gen

        def _worker() -> None:
            err_msg: str | None = None
            rows = []
            thread_db = Database(self.db.db_path)
            try:
                thread_db.connect()
                t_cat_dao = CategoryDAO(thread_db)
                t_prod_dao = ProductDAO(thread_db)
                if cat_name == "All":
                    rows = t_prod_dao.list_all_active()
                else:
                    c = t_cat_dao.get_by_name(cat_name)
                    rows = (
                        t_prod_dao.list_by_category(int(c["category_id"])) if c else []
                    )
            except Exception as exc:
                err_msg = str(exc)
                rows = []
            finally:
                thread_db.disconnect()

            def _apply() -> None:
                if self._destroyed or gen != self._load_gen:
                    return
                self._all_products_cache = rows
                self._all_products_cache_cat = cat_name
                if err_msg:
                    messagebox.showerror("DB Error", err_msg)
                self._preload_images_async()
                search_text = ""
                try:
                    if self._search_entry and self._search_entry.winfo_exists():
                        search_text = self.search_var.get().strip()
                        if search_text in (
                            "Search…", "Search products…",
                            "Search products...", "Search Products",
                        ):
                            search_text = ""
                except Exception:
                    pass
                self._products_cache = self._filter_products(search_text)
                self._start_batch_load()

            if not self._destroyed:
                self.after(0, _apply)

        threading.Thread(target=_worker, daemon=True).start()

    def _filter_products(self, search_text: str = ""):
        q = (search_text or "").strip().lower()
        if not q or q in ["search", "search…", "search products…", "search products...", "search products"]:
            return list(self._all_products_cache)
        return [r for r in self._all_products_cache if q in str(r["name"]).lower()]

    def _calc_product_cols(self) -> int:
        """Return column count based on canvas width (canvas ≈ 50% of window width).
        Breakpoints mirror the window-width spec: 600/900/1200/1200+ px."""
        w = getattr(self, "_prod_canvas_w", 0)
        if w >= 600:
            return 5
        if w >= 450:
            return 4
        if w >= 300:
            return 3
        return 2

    def _debounced_relayout(self) -> None:
        if self._destroyed or self._building or not self.winfo_exists():
            return
        self._cancel_after(self._prod_resize_after)
        self._prod_resize_after = self._after(150, self._relayout_products)

    def _refresh_products(self):
        if self._destroyed or self._building or not self.winfo_exists():
            return
        self._search_after = None
        if not self._all_products_cache:
            # Show loading label immediately on main thread; worker fills cards when done
            try:
                for w in self.prod_inner.winfo_children():
                    w.destroy()
            except Exception:
                pass
            self._product_card_widgets = []
            self._loading_lbl = None
            tk.Label(
                self.prod_inner, text="Loading menu…",
                bg=self._CARD_BG, fg=THEME["muted"],
                font=("Segoe UI", 12),
            ).pack(pady=40)
            self._load_products_for_category()
            return
        search_text = self.search_var.get().strip()
        if search_text in ("Search…", "Search products…", "Search products...", "Search Products"):
            search_text = ""
        self._products_cache = self._filter_products(search_text)
        self._start_batch_load()

    # ── Batch card loading ────────────────────────────────────────────────────
    _BATCH_SIZE = 12

    def _start_batch_load(self) -> None:
        if self._destroyed or self._building or not self.winfo_exists():
            return
        self._cancel_after(self._batch_after)
        self._batch_after = None

        for w in self.prod_inner.winfo_children():
            w.destroy()
        self._product_card_widgets = []
        self._loading_lbl = None

        if not self._products_cache:
            tk.Label(self.prod_inner,
                     text="No items found. Clear search or seed products.",
                     bg=self._CARD_BG, fg=THEME["muted"],
                     font=("Segoe UI", 12, "bold")).pack(pady=40)
            return

        self._loading_lbl = tk.Label(self.prod_inner, text="Loading menu…",
                                     bg=self._CARD_BG, fg=THEME["muted"],
                                     font=("Segoe UI", 12))
        self._loading_lbl.pack(pady=40)

        self._batch_products = list(self._products_cache)
        self._batch_idx = 0
        self._last_batch_cols = 0
        self._batch_after = self._after(10, self._render_product_batch)

    def _render_product_batch(self) -> None:
        self._batch_after = None
        if self._destroyed or self._building or not self.winfo_exists():
            return

        if self._loading_lbl is not None:
            try:
                self._loading_lbl.destroy()
            except Exception:
                pass
            self._loading_lbl = None

        if not self.prod_inner.winfo_exists():
            return

        start = self._batch_idx
        end = min(start + self._BATCH_SIZE, len(self._batch_products))
        for i in range(start, end):
            card = self._product_card(self.prod_inner, self._batch_products[i])
            self._product_card_widgets.append(card)

        self._batch_idx = end

        # Incremental layout: only place newly added cards unless column count changed
        cols = max(2, min(5, self._calc_product_cols()))
        last_cols = getattr(self, "_last_batch_cols", 0)
        if cols != last_cols or start == 0:
            # Column count changed or first batch — full relayout needed
            self._last_batch_cols = cols
            self._do_product_grid_layout()
        else:
            # Fast path: just grid the new cards, existing ones stay in place
            for idx in range(start, end):
                self._product_card_widgets[idx].grid(
                    row=idx // cols, column=idx % cols,
                    sticky="nsew", padx=4, pady=4,
                )
            for r in range((end + cols - 1) // cols):
                self.prod_inner.rowconfigure(r, weight=0, uniform="prodrow", minsize=180)
            try:
                self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all"))
            except Exception:
                pass

        if self._batch_idx < len(self._batch_products):
            self._batch_after = self._after(10, self._render_product_batch)

    def _relayout_products(self, rebuild_cards: bool = False) -> None:
        if self._destroyed or self._building or not self.winfo_exists():
            return
        try:
            actual_w = self.prod_canvas.winfo_width()
            if actual_w > 1:
                self._prod_canvas_w = actual_w
                self.prod_canvas.itemconfigure(self._prod_window_id, width=actual_w)
        except Exception:
            pass
        # Skip full re-grid when nothing has changed — avoids the brief flicker
        # caused by Tkinter ungridding then re-placing every card widget.
        new_cols = max(2, min(5, self._calc_product_cols()))
        last_cols = getattr(self, "_last_relayout_cols", -1)
        last_count = getattr(self, "_last_relayout_count", -1)
        n_cards = len(self._product_card_widgets)
        if new_cols == last_cols and n_cards == last_count and not rebuild_cards:
            return
        self._do_product_grid_layout()

    def _do_product_grid_layout(self) -> None:
        if not self.winfo_exists():
            return
        try:
            if not self.prod_inner.winfo_exists() or not self.prod_canvas.winfo_exists():
                return
        except Exception:
            return
        if getattr(self, "_prod_canvas_w", 0) < 300:
            return
        cards = self._product_card_widgets
        cols = self._calc_product_cols()
        cols = max(2, min(5, cols))

        # Reset old row configs to prevent phantom blank rows when product count decreases
        prev_rows = getattr(self, "_last_relayout_rows", 0)
        for r in range(prev_rows):
            self.prod_inner.rowconfigure(r, weight=0, uniform="", minsize=0)

        # Reset old column configs
        for i in range(6):
            self.prod_inner.columnconfigure(i, weight=0, uniform="")
        for i in range(cols):
            self.prod_inner.columnconfigure(i, weight=1, uniform="prodcol")

        for idx, card in enumerate(cards):
            row = idx // cols
            col = idx % cols
            card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        # Enforce uniform row height so all cards align regardless of text length
        new_rows = (len(cards) + cols - 1) // cols
        for r in range(new_rows):
            self.prod_inner.rowconfigure(r, weight=0, uniform="prodrow", minsize=180)

        self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all"))

        # Track for skip-on-no-change optimisation in _relayout_products
        self._last_relayout_cols = cols
        self._last_relayout_count = len(cards)
        self._last_relayout_rows = new_rows

    # ── Product card — beige tile with left accent border ────────────────────
    _CARD_BG = "#e6ddbd"   # beige card background — prevents any black flash

    def _product_card(self, parent: tk.Widget, r) -> tk.Frame:
        pid   = int(r["product_id"])
        name  = str(r["name"])
        price = float(r["price"])
        desc  = str(_row_get(r, "description", "") or "").strip()

        card = tk.Frame(
            parent,
            bg=self._CARD_BG,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["border"],   # prevent default black active highlight
            cursor="hand2",
        )
        card.columnconfigure(1, weight=1)

        def _bind_click(w: tk.Widget):
            w.bind("<Button-1>",
                   lambda _e: self._add_to_cart(pid, name, price), add="+")

        _bind_click(card)

        # Left accent border (4 px terracotta stripe)
        accent_bar = tk.Frame(card, bg=THEME["accent"], width=4)
        accent_bar.grid(row=0, column=0, rowspan=6, sticky="nsew")
        _bind_click(accent_bar)

        # ── Image ─────────────────────────────────────────────────────────────
        img_size = self._IMG_SIZE
        img_frame = tk.Frame(card, bg=self._CARD_BG,
                             width=img_size, height=img_size, cursor="hand2")
        img_frame.grid(row=0, column=1, pady=(8, 3), padx=(8, 6))
        img_frame.grid_propagate(False)
        _bind_click(img_frame)

        img_rel = _row_get(r, "image_path", None) or ""
        photo = self._load_image(img_rel)
        if photo:
            lbl_img = tk.Label(img_frame, image=photo,
                               bg=self._CARD_BG, cursor="hand2")
            lbl_img.image = photo
            lbl_img.place(relx=0.5, rely=0.5, anchor="center")
            _bind_click(lbl_img)
        else:
            lbl_no = tk.Label(img_frame, text="🍽",
                              bg=self._CARD_BG, fg=THEME["muted"],
                              font=("Segoe UI", 24), cursor="hand2")
            lbl_no.place(relx=0.5, rely=0.5, anchor="center")
            _bind_click(lbl_no)

        # ── Product name ──────────────────────────────────────────────────────
        name_lbl = tk.Label(
            card, text=name,
            bg=self._CARD_BG, fg=THEME["text"],
            font=("Segoe UI", 9, "bold"),
            anchor="center", justify="center",
            wraplength=120, cursor="hand2",
        )
        name_lbl.grid(row=1, column=1, sticky="ew", padx=(4, 6), pady=(0, 1))
        _bind_click(name_lbl)
        if len(name) > 32:
            self._add_tooltip(name_lbl, name)

        # ── Description (one line, muted) ─────────────────────────────────────
        desc_show = desc if desc else "No description available"
        desc_lbl = tk.Label(
            card, text=desc_show,
            bg=self._CARD_BG, fg=THEME["muted"],
            font=("Segoe UI", 7),
            anchor="center", justify="center",
            wraplength=120, cursor="hand2",
        )
        desc_lbl.grid(row=2, column=1, sticky="ew", padx=(4, 6), pady=(0, 1))
        _bind_click(desc_lbl)

        def _on_card_resize(event, _n=name_lbl, _d=desc_lbl):
            wrap = max(30, event.width - 16)
            _n.configure(wraplength=wrap)
            _d.configure(wraplength=wrap)
        card.bind("<Configure>", _on_card_resize)

        # ── Price row ─────────────────────────────────────────────────────────
        price_row = tk.Frame(card, bg=self._CARD_BG, cursor="hand2")
        price_row.grid(row=3, column=1, sticky="ew", padx=(4, 6), pady=(0, 6))
        price_row.columnconfigure(0, weight=1)
        _bind_click(price_row)

        price_lbl = tk.Label(
            price_row, text=money(price),
            bg=self._CARD_BG, fg=THEME["accent"],
            font=("Segoe UI", 10, "bold"),
            anchor="center", cursor="hand2",
        )
        price_lbl.grid(row=0, column=0, sticky="ew")
        _bind_click(price_lbl)

        return card

    # ── Cart canvas dynamic sizing ────────────────────────────────────────────
    _CART_MAX_H = 300

    def _on_cart_tbl_configure(self, _event: object = None) -> None:
        try:
            if self.cart_canvas.winfo_exists():
                self.cart_canvas.configure(scrollregion=self.cart_canvas.bbox("all"))
        except Exception:
            pass
        if self._cart_resize_after is not None:
            try:
                self.after_cancel(self._cart_resize_after)
            except Exception:
                pass
        self._cart_resize_after = self._after(10, self._resize_cart_canvas)

    def _resize_cart_canvas(self):
        self._cart_resize_after = None
        try:
            if not self.cart_canvas.winfo_exists():
                return
            item_count = len(self.cart)
            content_h = self.cart_tbl.winfo_reqheight()
            if item_count == 0:
                new_h = 110  # compact empty height
            elif item_count <= 2:
                new_h = max(110, min(content_h, 200))
            elif item_count <= 4:
                new_h = max(130, min(content_h, 260))
            else:
                new_h = max(130, min(content_h, self._CART_MAX_H))
            self.cart_canvas.configure(height=new_h)
        except Exception:
            pass

    # ── Cart logic ────────────────────────────────────────────────────────────
    def _get_stock(self, pid: int) -> int:
        if pid in self._product_stock:
            return self._product_stock[pid]
        for r in self._all_products_cache:
            if int(r["product_id"]) == pid:
                val = int(_row_get(r, "stock_qty", 0))
                self._product_stock[pid] = val
                return val
        try:
            prod = self.prod_dao.get(pid)
            if prod is not None:
                self._product_stock[pid] = prod.stock_qty
                return prod.stock_qty
        except Exception:
            pass
        return 0

    def _get_live_stock(self, pid: int) -> int:
        """Always queries the DB for current stock — never uses stale cache."""
        try:
            r = self.db.fetchone(
                "SELECT stock FROM products WHERE id=? AND active=1;", (pid,)
            )
            if r:
                val = int(r["stock"])
                self._product_stock[pid] = val
                return val
        except Exception:
            pass
        return 0

    def _add_to_cart(self, pid: int, name: str, price: float):
        live_stock = self._get_live_stock(pid)
        current_qty = self.cart[pid][2] if pid in self.cart else 0
        if live_stock <= 0:
            messagebox.showwarning("Out of Stock", f"'{name}' is out of stock.")
            return
        if current_qty >= live_stock:
            messagebox.showwarning(
                "Stock Limit",
                f"Only {live_stock} unit(s) of '{name}' available.\n"
                f"You already have {current_qty} in the cart.",
            )
            return
        if pid in self.cart:
            n, p, qty, note = self.cart[pid]
            self.cart[pid] = (n, p, qty + 1, note)
            # Fast path: update existing row in-place — no widget rebuild
            refs = self._cart_row_refs.get(pid)
            if refs:
                try:
                    new_qty = qty + 1
                    refs["qty_lbl"].configure(text=str(new_qty))
                    refs["sub_lbl"].configure(text=money(new_qty * p))
                    _, _, _, total = self._calc_totals()
                    self.total_lbl.configure(text=money(total))
                    if self._lbl_total_val:
                        self._lbl_total_val.configure(text=money(total))
                    return
                except Exception:
                    pass
            self._refresh_cart()
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
        new_qty = qty + delta
        if new_qty <= 0:
            del self.cart[pid]
            self._refresh_cart()
            return
        if delta > 0:
            live_stock = self._get_live_stock(pid)
            if new_qty > live_stock:
                messagebox.showwarning(
                    "Stock Limit",
                    f"Only {live_stock} unit(s) of '{n}' available.",
                )
                return
        self.cart[pid] = (n, p, new_qty, note)
        # Fast path: update qty/subtotal labels in-place (avoids full widget rebuild)
        refs = self._cart_row_refs.get(pid)
        if refs:
            try:
                refs["qty_lbl"].configure(text=str(new_qty))
                refs["sub_lbl"].configure(text=money(new_qty * p))
                subtotal, discount, _, total = self._calc_totals()
                self.total_lbl.configure(text=money(total))
                if self._lbl_subtotal_val:
                    self._lbl_subtotal_val.configure(text=money(subtotal))
                if self._lbl_total_val:
                    self._lbl_total_val.configure(text=money(total))
                if discount > 0:
                    _mode_labels = {"PWD": "PWD 20%", "SENIOR": "Senior 20%", "SPECIAL": "Special"}
                    _disc_label = _mode_labels.get(self.discount_mode, "Discount")
                    if self._lbl_discount_name:
                        self._lbl_discount_name.configure(text=f"{_disc_label}:")
                    if self._lbl_discount_val:
                        self._lbl_discount_val.configure(text=f"−{money(discount)}")
                    if self._lbl_discount_row:
                        self._lbl_discount_row.pack(fill="x", pady=(0, 2))
                    self._set_discount_next_to_total(f"{_disc_label}: −{money(discount)}")
                else:
                    if self._lbl_discount_row:
                        self._lbl_discount_row.pack_forget()
                    self._set_discount_next_to_total(None)
                return
            except Exception:
                pass
        # Fallback: full rebuild (e.g. refs stale after theme rebuild)
        self._refresh_cart()

    def _calc_totals(self):
        subtotal = sum(qty * price for (_n, price, qty, _note) in self.cart.values())
        discount = 0.0
        mode = self.discount_mode
        if mode == "PWD" or mode == "SENIOR":
            discount = subtotal * 0.20
        elif mode == "SPECIAL":
            discount = max(0.0, min(float(self.discount_value), subtotal))
        elif mode == "amount":
            discount = max(0.0, min(float(self.discount_value), subtotal))
        elif mode == "percent":
            discount = max(0.0, min(100.0, float(self.discount_value))) / 100.0 * subtotal
        tax = 0.0
        total = max(0.0, subtotal - discount + tax)
        return subtotal, discount, tax, total

    def _set_discount_next_to_total(self, text: str | None):
        if text:
            self.discount_lbl.configure(text=text)
            if not self._discount_visible:
                self.discount_lbl.pack(anchor="e", padx=8, pady=(2, 0))
                self._discount_visible = True
        else:
            if self._discount_visible:
                self.discount_lbl.pack_forget()
                self._discount_visible = False

    def _refresh_cart(self):
        self._cart_row_refs = {}
        for w in self.cart_tbl.winfo_children():
            w.destroy()

        self.cart_tbl.columnconfigure(0, weight=1, minsize=130)
        self.cart_tbl.columnconfigure(1, weight=0, minsize=22)
        self.cart_tbl.columnconfigure(2, weight=0, minsize=26)
        self.cart_tbl.columnconfigure(3, weight=0, minsize=22)
        self.cart_tbl.columnconfigure(4, weight=0, minsize=64)
        self.cart_tbl.columnconfigure(5, weight=0, minsize=28)

        if not self.cart:
            self._set_discount_next_to_total(None)
            try:
                self.cart_canvas.yview_moveto(0)
                self.cart_canvas.configure(scrollregion=(0, 0, 0, 0))
            except Exception:
                pass
            tk.Label(self.cart_tbl, text="No items",
                     bg=THEME["panel2"], fg=THEME["muted"],
                     font=("Segoe UI", 9)).grid(row=0, column=0, columnspan=6, pady=4)
            self.total_lbl.configure(text="₱0.00")
            if self._lbl_subtotal_val:
                self._lbl_subtotal_val.configure(text="₱0.00")
            if self._lbl_discount_row:
                self._lbl_discount_row.pack_forget()
            if self._lbl_total_val:
                self._lbl_total_val.configure(text="₱0.00")
            self._cancel_after(self._suggest_after)
            self._suggest_after = self._after(30, self._refresh_suggestions)
            self._after(20, self._resize_cart_canvas)
            return

        tk.Label(self.cart_tbl, text="Item",
                 bg=THEME["panel2"], fg=THEME["muted"],
                 font=("Segoe UI", 9, "bold"),
                 ).grid(row=0, column=0, sticky="w", padx=(10, 2), pady=(4, 2))
        tk.Label(self.cart_tbl, text="Qty",
                 bg=THEME["panel2"], fg=THEME["muted"],
                 font=("Segoe UI", 9, "bold"), anchor="center",
                 ).grid(row=0, column=1, columnspan=3, sticky="ew", pady=(4, 2))
        tk.Label(self.cart_tbl, text="Subtotal",
                 bg=THEME["panel2"], fg=THEME["muted"],
                 font=("Segoe UI", 9, "bold"), anchor="e",
                 ).grid(row=0, column=4, sticky="ew", padx=(4, 4), pady=(4, 2))

        row_i = 1
        for pid, (name, price, qty, _note) in self.cart.items():
            name_txt = _truncate_text(name, max_len=22)
            tk.Label(self.cart_tbl, text=name_txt,
                     bg=THEME["panel2"], fg=THEME["text"], anchor="w",
                     font=("Segoe UI", 9),
                     ).grid(row=row_i, column=0, sticky="ew", padx=(10, 2), pady=2)
            tk.Button(self.cart_tbl, text="−",
                      command=lambda p=pid: self._change_qty(p, -1),
                      bg=THEME["panel"], fg=THEME["text"], bd=0, width=2, cursor="hand2",
                      ).grid(row=row_i, column=1, padx=2, pady=2)
            qty_lbl = tk.Label(self.cart_tbl, text=str(qty),
                               bg=THEME["panel2"], fg=THEME["text"], width=3, anchor="center")
            qty_lbl.grid(row=row_i, column=2, padx=2, pady=2)
            tk.Button(self.cart_tbl, text="+",
                      command=lambda p=pid: self._change_qty(p, 1),
                      bg=THEME["panel"], fg=THEME["text"], bd=0, width=2, cursor="hand2",
                      ).grid(row=row_i, column=3, padx=2, pady=2)
            sub_lbl = tk.Label(self.cart_tbl, text=money(qty * price),
                               bg=THEME["panel2"], fg=THEME["text"], anchor="e")
            sub_lbl.grid(row=row_i, column=4, sticky="e", padx=(4, 4), pady=2)
            tk.Button(self.cart_tbl, text="✕",
                      command=lambda p=pid: self._remove_from_cart(p),
                      bg=THEME["danger"], fg="white", bd=0, width=3, padx=2, pady=1,
                      cursor="hand2", font=("Segoe UI", 9, "bold"),
                      ).grid(row=row_i, column=5, padx=(4, 10), pady=2, sticky="e")
            self._cart_row_refs[pid] = {"qty_lbl": qty_lbl, "sub_lbl": sub_lbl}
            row_i += 1

        subtotal, discount, _tax, total = self._calc_totals()
        self.total_lbl.configure(text=money(total))
        if self._lbl_subtotal_val:
            self._lbl_subtotal_val.configure(text=money(subtotal))
        if self._lbl_total_val:
            self._lbl_total_val.configure(text=money(total))

        if discount > 0:
            _mode_labels = {"PWD": "PWD 20%", "SENIOR": "Senior 20%", "SPECIAL": "Special"}
            _disc_label = _mode_labels.get(self.discount_mode, "Discount")
            if self._lbl_discount_name:
                self._lbl_discount_name.configure(text=f"{_disc_label}:")
            if self._lbl_discount_val:
                self._lbl_discount_val.configure(text=f"−{money(discount)}")
            if self._lbl_discount_row:
                self._lbl_discount_row.pack(fill="x", pady=(0, 2))
            self._set_discount_next_to_total(f"{_disc_label}: −{money(discount)}")
        else:
            if self._lbl_discount_row:
                self._lbl_discount_row.pack_forget()
            self._set_discount_next_to_total(None)

        def _update_scroll():
            try:
                if self.cart_canvas.winfo_exists():
                    bbox = self.cart_canvas.bbox("all")
                    if bbox:
                        self.cart_canvas.configure(scrollregion=bbox)
            except Exception:
                pass
        self._after(0, _update_scroll)

        self._cancel_after(self._suggest_after)
        self._suggest_after = self._after(60, self._refresh_suggestions)

    # ── ML Suggestions ────────────────────────────────────────────────────────
    def _refresh_suggestions(self):
        self._suggest_after = None
        if not self.winfo_exists():
            return
        if self._suggestions_frame is None:
            return

        for w in self._suggestions_frame.winfo_children():
            w.destroy()

        if not self.cart:
            if self._suggestions_frame.winfo_ismapped():
                self._suggestions_frame.grid_remove()
            return

        cart_ids = list(self.cart.keys())
        try:
            suggested_ids = self.recommender.suggest(cart_ids, top_n=5)
        except Exception:
            suggested_ids = []

        if not suggested_ids:
            hdr2 = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
            hdr2.pack(fill="x", padx=14, pady=(4, 2))
            tk.Label(hdr2, text="Suggested Items", bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(self._suggestions_frame,
                     text="No suggestions yet — complete more sales",
                     bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=14, pady=(0, 4))
            if not self._suggestions_frame.winfo_ismapped():
                self._suggestions_frame.grid()
            return

        try:
            names = self.recommender.get_product_names(suggested_ids)
        except Exception:
            names = {pid: f"Item #{pid}" for pid in suggested_ids}

        hdr3 = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
        hdr3.pack(fill="x", padx=14, pady=(4, 2))
        tk.Label(hdr3, text="Suggested Items", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        valid_items: list[tuple[int, str, float]] = []
        for pid in suggested_ids:
            price: float = 0.0
            for cached_row in self._products_cache:
                if int(cached_row["product_id"]) == pid:
                    price = float(cached_row["price"])
                    break
            else:
                try:
                    prod = self.prod_dao.get(pid)
                    if prod:
                        price = prod.price
                except Exception:
                    pass
            if price == 0.0:
                try:
                    price = self.recommender.get_product_price(pid)
                except Exception:
                    price = 0.0
            valid_items.append((pid, names.get(pid, f"#{pid}"), price))

        rendered = len(valid_items)
        PER_ROW = 3
        for row_start in range(0, max(rendered, 1), PER_ROW):
            chunk = valid_items[row_start:row_start + PER_ROW]
            if not chunk:
                break
            is_last_chunk = (row_start + PER_ROW) >= rendered
            btn_row = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
            btn_row.pack(fill="x", padx=12, pady=(2, 6 if is_last_chunk else 3))
            for col_i in range(len(chunk)):
                btn_row.columnconfigure(col_i, weight=1, uniform="sg")
            for col_i, (pid, name, price) in enumerate(chunk):
                display = _truncate_text(name, max_len=14)
                def _add(p=pid, n=name, pr=price):
                    self._add_to_cart(p, n, pr)
                btn = tk.Button(btn_row, text=f"+ {display}", command=_add,
                                bg=THEME.get("beige", "#FFF3E0"), fg=THEME["brown"],
                                bd=1, relief="solid", padx=5, pady=6, cursor="hand2",
                                font=("Segoe UI", 9), wraplength=100, justify="center")
                btn.grid(row=0, column=col_i, sticky="ew",
                         padx=(0, 4) if col_i < len(chunk) - 1 else (0, 0))
                if len(name) > 14:
                    self._add_tooltip(btn, name)

        if rendered == 0:
            for w in self._suggestions_frame.winfo_children():
                w.destroy()
            hdr_empty = tk.Frame(self._suggestions_frame, bg=THEME["panel"])
            hdr_empty.pack(fill="x", padx=14, pady=(4, 2))
            tk.Label(hdr_empty, text="Suggested Items", bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(self._suggestions_frame,
                     text="No suggestions yet — complete more sales",
                     bg=THEME["panel"], fg=THEME["muted"],
                     font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=14, pady=(0, 4))

        if not self._suggestions_frame.winfo_ismapped():
            self._suggestions_frame.grid()

    # ── Discount ──────────────────────────────────────────────────────────────
    def _add_discount(self):
        dlg = DiscountDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        mode, value = dlg.result
        self.discount_mode = str(mode)
        self.discount_value = float(value)
        self._refresh_cart()

    # ── Drafts ────────────────────────────────────────────────────────────────
    def _refresh_drafts_panel(self):
        rows = self.draft_dao.list_drafts()
        if not rows:
            try:
                self.drafts_section.grid_remove()
            except Exception:
                pass
            self._draft_id_by_index.clear()
            try:
                self.draft_list.delete(0, tk.END)
            except Exception:
                pass
            return
        if not self.drafts_section.winfo_ismapped():
            self.drafts_section.grid()
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
        dlg = DraftTitleDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        title = dlg.result.strip()
        _subtotal, _discount, _tax, total = self._calc_totals()
        payload = {
            "cart": [{"product_id": pid, "name": n, "price": p, "qty": q, "note": note}
                     for pid, (n, p, q, note) in self.cart.items()],
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
            self.draft_dao.delete_all_drafts()
            self._refresh_drafts_panel()
            messagebox.showinfo("Draft orders", "All drafts deleted.")
        except Exception as e:
            messagebox.showerror("Draft orders", f"Failed to delete all drafts.\n\n{e}")

    # ── Checkout ──────────────────────────────────────────────────────────────
    def _checkout(self):
        """Legacy entry point — now delegates to inline _pay_now."""
        self._pay_now()

    def _pay_now(self):
        """Inline checkout — reads all fields from the POS panel directly."""
        if not self.cart:
            messagebox.showinfo("Checkout", "No items in order.")
            return

        if self.var_table_number is None or self.var_order_type is None or self.var_payment is None:
            messagebox.showerror("Checkout", "Payment panel not ready.")
            return

        table_number = self.var_table_number.get().strip()
        if not table_number:
            order_type = self.var_order_type.get()
            lbl = "Table No." if order_type == "DINE_IN" else "Order No."
            messagebox.showerror(lbl, f"{lbl} is required before checkout.")
            return

        order_type = self.var_order_type.get()

        _disc_labels = {"PWD": "PWD", "SENIOR": "SENIOR", "SPECIAL": "SPECIAL",
                        "amount": "AMOUNT", "percent": "PERCENT", "NONE": "NONE"}
        discount_type = _disc_labels.get(self.discount_mode, "NONE")

        paid_str = self.var_amount_paid.get().strip() if self.var_amount_paid else ""
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

        items = [{"product_id": pid, "qty": qty, "unit_price": price, "note": note}
                 for pid, (_name, price, qty, note) in self.cart.items()]

        # Pre-checkout stock validation: fail fast with a clear message before DB write
        stock_errors: list[str] = []
        for pid, (_name, _price, qty, _note) in self.cart.items():
            r = self.db.fetchone(
                "SELECT name, stock, active FROM products WHERE id=?;", (pid,)
            )
            if r is None or not r["active"]:
                stock_errors.append(f"• '{_name}' is no longer available.")
            elif qty > int(r["stock"]):
                avail = int(r["stock"])
                stock_errors.append(
                    f"• '{r['name']}': need {qty}, only {avail} in stock."
                )
        if stock_errors:
            messagebox.showerror(
                "Insufficient Stock",
                "Cannot complete order — stock issues:\n\n" + "\n".join(stock_errors),
            )
            return

        self._product_stock.clear()
        ref_no = f"TXN-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        try:
            order_id = self.svc.create_order(
                cashier_id=cashier_id,
                customer_name=table_number,
                payment_method=payment,
                status=status,
                reference_no=ref_no,
                items=items,
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                total=total,
                amount_paid=paid,
                cash_received=cash_received,
                change_due=change,
                order_type=order_type,
                table_number=table_number,
                discount_type=discount_type,
            )
            if status == "Pending":
                self._checkout_done(cleared=True, completed=False)
                self._show_ewallet_reference_dialog(order_id, total)
            else:
                # Clear cart first, then show in-app receipt preview
                self._checkout_done(cleared=True, completed=True)
                self._show_receipt_preview(order_id, order_type, table_number, discount_type,
                                           change=change, paid=paid)
        except Exception as e:
            err = str(e)
            if "Insufficient stock" in err:
                messagebox.showerror(
                    "Out of Stock",
                    f"{err}\n\n"
                    "Go to Inventory → Products and increase the stock for this item before selling.",
                )
            elif "no longer available" in err:
                messagebox.showerror(
                    "Product Unavailable",
                    f"{err}\n\nThe item may have been deactivated. Remove it from the cart.",
                )
            elif "Insufficient raw material" in err:
                messagebox.showerror(
                    "Insufficient Ingredients",
                    f"{err}\n\n"
                    "Go to Inventory → Raw Materials and restock the ingredient.",
                )
            else:
                messagebox.showerror("Checkout Error", f"Failed to save order.\n\n{err}")

    def _checkout_done(self, cleared: bool = True, completed: bool = False):
        if cleared:
            self.cart.clear()
            self._product_stock.clear()
            self.discount_mode = "NONE"
            self.discount_value = 0.0
            self._refresh_cart()
            self._refresh_drafts_panel()
            # Reset payment panel fields
            if self.var_amount_paid is not None:
                self.var_amount_paid.set("")
            if self.var_table_number is not None:
                self.var_table_number.set("")
            if self._change_lbl is not None:
                try:
                    self._change_lbl.configure(text="", bg=THEME["panel"], fg=THEME["muted"])
                except Exception:
                    pass
        self._all_products_cache = []
        self._all_products_cache_cat = ""
        self._after(80, self._refresh_products)
        if completed and self.recommender is not None:
            self.recommender.invalidate_cache()

    def _show_ewallet_reference_dialog(self, order_id: int, total: float) -> None:
        """After saving a Bank/E-Wallet Pending order, immediately ask for the
        reference number.  Shows the order total — no amount re-entry needed.
        Resolves to Completed on the spot; skipping leaves it as Pending."""
        from app.ui.dialogs import EWalletDialog
        dlg = EWalletDialog(self, order_id=order_id, total=total)
        self.wait_window(dlg)

        if dlg.result:
            ref = dlg.result
            try:
                self.order_dao.resolve_pending(order_id, ref, total)
                self._show_receipt_preview(order_id, "", "", "NONE")
            except Exception as e:
                messagebox.showwarning(
                    "Resolve Failed",
                    f"Order saved as Pending but could not be resolved:\n{e}\n\n"
                    "You can still resolve it from the Transactions page.",
                )
            return

        messagebox.showinfo(
            "Order Pending",
            f"Order #{order_id} saved as Pending.\n\n"
            "Go to Transactions to resolve it once the payment reference is confirmed.",
        )

    def _show_receipt_preview(self, order_id: int, order_type: str,
                               table_number: str, discount_type: str,
                               change: float = 0.0, paid: float = 0.0) -> None:
        """Build order_dict/items_list and launch the in-app receipt preview."""
        try:
            data = self.order_dao.get_order(order_id)
            items = self.order_dao.get_order_items(order_id)
            if not data:
                messagebox.showwarning("Receipt", "Order saved, but receipt data not found.")
                return

            order_dict = {k: data[k] for k in data.keys()}

            raw_order = self.db.fetchone(
                "SELECT * FROM orders WHERE id=?;", (int(order_id),)
            )
            raw_keys = set(raw_order.keys()) if raw_order else set()
            defaults = {
                "receipt_id": str(order_id),
                "order_type": order_type,
                "table_number": table_number,
                "discount_type": discount_type,
                "vat_amount": 0.0,
            }
            for key, default in defaults.items():
                if raw_order and key in raw_keys:
                    value = raw_order[key]
                else:
                    value = order_dict.get(key, default)
                if key == "vat_amount":
                    try:
                        order_dict[key] = float(value or 0.0)
                    except Exception:
                        order_dict[key] = 0.0
                else:
                    text_value = str(value).strip() if value is not None else ""
                    order_dict[key] = text_value or default

            items_list = [{k: item[k] for k in item.keys()} for item in items]
            ReceiptPreviewDialog(self, order_dict, items_list)
        except Exception as exc:
            messagebox.showwarning(
                "Receipt",
                f"Order completed, but receipt preview failed.\n\n{exc}",
            )


# ══════════════════════════════════════════════════════════════════════════════
# ReceiptPreviewDialog — in-app receipt shown after completed Cash checkout
# ══════════════════════════════════════════════════════════════════════════════
class ReceiptPreviewDialog(tk.Toplevel):
    """
    Shows a scrollable receipt preview inside the POS window.
    PDF is only generated if the user clicks 'Print / Save PDF'.
    """

    _BG   = str(THEME["bg"])
    _CARD = str(THEME["panel"])
    _TEXT = str(THEME["text"])
    _MUTED = str(THEME["muted"])
    _GREEN = str(THEME["success"])
    _RULE  = str(THEME["border"])

    def __init__(self, parent, order_data: dict, items: list):
        super().__init__(parent)
        self.order_data = order_data
        self.items = items

        self.title("Receipt")
        self.configure(bg=self._BG)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = min(400, sw - 80), min(640, sh - 80)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._build(w, h)
        self.bind("<Escape>", lambda _e: self.destroy())

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _rm(value) -> str:
        try:
            v = float(value)
        except Exception:
            v = 0.0
        return f"PHP {v:,.2f}"

    @staticmethod
    def _ot(value) -> str:
        kind = str(value or "DINE_IN").strip().upper().replace(" ", "_")
        return "Take Out" if kind == "TAKE_OUT" else "Dine In"

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self, w: int, h: int):
        o = self.order_data
        items = self.items

        # pull values
        order_id      = o.get("order_id", "—")
        receipt_id    = str(o.get("receipt_id", "—") or "—").strip() or "—"
        start_dt      = str(o.get("start_dt", "—"))[:19]
        order_type    = self._ot(o.get("order_type", "DINE_IN"))
        table_number  = str(o.get("table_number", "—") or "—").strip() or "—"
        cashier       = str(o.get("cashier_username", "Unknown") or "Unknown").strip()
        payment       = str(o.get("payment_method", "—"))
        status        = str(o.get("status", "—"))
        discount_type = str(o.get("discount_type", "NONE") or "NONE").strip().upper()
        subtotal_v    = float(o.get("subtotal") or 0.0)
        discount_v    = float(o.get("discount") or 0.0)
        total_v       = float(o.get("total")    or 0.0)
        paid_v        = float(o.get("amount_paid") or 0.0)
        change_v      = float(o.get("change_due")  or 0.0)
        loc_label     = "Order No." if order_type == "Take Out" else "Table No."

        disc_label_map = {"PWD": "PWD 20%", "SENIOR": "Senior 20%",
                          "SPECIAL": "Special Discount"}
        disc_label = disc_label_map.get(discount_type, "Discount")

        # ── outer frame: canvas + scrollbar ───────────────────────────────────
        outer = tk.Frame(self, bg=self._BG)
        outer.pack(fill="both", expand=True)

        cv = tk.Canvas(outer, bg=self._BG, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(cv, bg=self._BG)
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(_e=None):
            cv.configure(scrollregion=cv.bbox("all"))
        def _on_cv_resize(e):
            cv.itemconfigure(win_id, width=e.width)
        inner.bind("<Configure>", _on_configure)
        cv.bind("<Configure>", _on_cv_resize)

        def _scroll(e):
            step = -1 if e.delta > 0 else 1
            cv.yview_scroll(step * 3, "units")
        cv.bind_all("<MouseWheel>", _scroll)
        cv.bind_all("<Button-4>", lambda e: cv.yview_scroll(-3, "units"))
        cv.bind_all("<Button-5>", lambda e: cv.yview_scroll( 3, "units"))
        self.bind("<Destroy>", lambda _e: (cv.unbind_all("<MouseWheel>"),
                                           cv.unbind_all("<Button-4>"),
                                           cv.unbind_all("<Button-5>")))

        # ── padding / font helpers ─────────────────────────────────────────────
        PAD = 20
        def row(left: str, right: str, bold=False, large=False, color=None):
            f = tk.Frame(inner, bg=self._CARD)
            f.pack(fill="x", padx=PAD)
            fg = color or self._TEXT
            fs = 11 if large else 9
            fw = "bold" if bold else "normal"
            tk.Label(f, text=left, bg=self._CARD, fg=self._MUTED if not bold else fg,
                     font=("Segoe UI", fs), anchor="w").pack(side="left", pady=2)
            tk.Label(f, text=right, bg=self._CARD, fg=fg,
                     font=("Segoe UI", fs, fw), anchor="e").pack(side="right", pady=2, padx=(0, 4))

        def rule(thick=False):
            h_val = 2 if thick else 1
            tk.Frame(inner, bg=self._RULE, height=h_val).pack(fill="x", padx=PAD, pady=3)

        def spacer(px=6):
            tk.Frame(inner, bg=self._BG, height=px).pack(fill="x")

        def heading(text: str, size=10, color=None):
            tk.Label(inner, text=text, bg=self._BG, fg=color or self._TEXT,
                     font=("Segoe UI", size, "bold"), anchor="center",
                     ).pack(fill="x", padx=PAD, pady=(2, 0))

        def subheading(text: str, size=8):
            tk.Label(inner, text=text, bg=self._BG, fg=self._MUTED,
                     font=("Segoe UI", size), anchor="center",
                     ).pack(fill="x", padx=PAD)

        # ── HEADER ────────────────────────────────────────────────────────────
        spacer(10)
        heading("AISSA'S KITCHENETTE", size=13)
        subheading("1 Esperanza, Quezon City")
        subheading("0947 530 4889")
        spacer(6)
        tk.Label(inner, text="OFFICIAL RECEIPT", bg=self._BG, fg=self._GREEN,
                 font=("Segoe UI", 9, "bold"), anchor="center").pack(fill="x", padx=PAD)
        spacer(8)
        rule(thick=True)
        spacer(4)

        # ── ORDER DETAILS ─────────────────────────────────────────────────────
        details_bg = tk.Frame(inner, bg=self._CARD)
        details_bg.pack(fill="x", padx=PAD, pady=(0, 4))
        # temporarily redirect row() output to details_bg
        _orig_inner = inner

        def drow(left: str, right: str):
            f = tk.Frame(details_bg, bg=self._CARD)
            f.pack(fill="x", padx=8, pady=1)
            tk.Label(f, text=left, bg=self._CARD, fg=self._MUTED,
                     font=("Segoe UI", 8), anchor="w").pack(side="left")
            tk.Label(f, text=right, bg=self._CARD, fg=self._TEXT,
                     font=("Segoe UI", 8), anchor="e").pack(side="right")

        spacer_in = tk.Frame(details_bg, bg=self._CARD, height=6)
        spacer_in.pack()
        drow("Transaction #:", str(order_id))
        drow("Receipt ID:", receipt_id)
        drow("Date:", start_dt)
        drow("Order Type:", order_type)
        drow(f"{loc_label}:", table_number)
        drow("Cashier:", cashier)
        drow("Payment:", payment)
        drow("Status:", status)
        tk.Frame(details_bg, bg=self._CARD, height=6).pack()

        rule()
        spacer(4)

        # ── ITEMS ─────────────────────────────────────────────────────────────
        tk.Label(inner, text="Items", bg=self._BG, fg=self._MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=PAD+4, pady=(2, 4))

        items_bg = tk.Frame(inner, bg=self._CARD)
        items_bg.pack(fill="x", padx=PAD, pady=(0, 4))
        tk.Frame(items_bg, bg=self._CARD, height=4).pack()

        for item in items:
            qty    = item.get("qty", 0)
            name   = item.get("name") or f"#{item.get('product_id', '?')}"
            unit_p = float(item.get("unit_price", 0.0))
            sub    = float(item.get("subtotal",   0.0))

            irow = tk.Frame(items_bg, bg=self._CARD)
            irow.pack(fill="x", padx=8, pady=(2, 0))
            tk.Label(irow, text=name, bg=self._CARD, fg=self._TEXT,
                     font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left")
            tk.Label(irow, text=self._rm(sub), bg=self._CARD, fg=self._TEXT,
                     font=("Segoe UI", 8), anchor="e").pack(side="right")

            drow2 = tk.Frame(items_bg, bg=self._CARD)
            drow2.pack(fill="x", padx=8, pady=(0, 2))
            tk.Label(drow2, text=f"  {qty} x PHP {unit_p:,.2f}", bg=self._CARD,
                     fg=self._MUTED, font=("Segoe UI", 7)).pack(side="left")

        tk.Frame(items_bg, bg=self._CARD, height=4).pack()

        rule()
        spacer(4)

        # ── TOTALS ────────────────────────────────────────────────────────────
        totals_bg = tk.Frame(inner, bg=self._CARD)
        totals_bg.pack(fill="x", padx=PAD, pady=(0, 4))
        tk.Frame(totals_bg, bg=self._CARD, height=6).pack()

        def trow(left: str, right: str, bold=False, large=False, color=None):
            f = tk.Frame(totals_bg, bg=self._CARD)
            f.pack(fill="x", padx=8, pady=1)
            fg = color or (self._TEXT if bold else self._MUTED)
            fs = 11 if large else 9
            fw = "bold" if bold else "normal"
            tk.Label(f, text=left, bg=self._CARD, fg=fg,
                     font=("Segoe UI", fs, fw), anchor="w").pack(side="left")
            tk.Label(f, text=right, bg=self._CARD, fg=fg,
                     font=("Segoe UI", fs, fw), anchor="e").pack(side="right", padx=(0, 4))

        trow("Subtotal:", self._rm(subtotal_v))
        if discount_v > 0:
            trow(f"{disc_label}:", f"-{self._rm(discount_v)}", color=THEME["danger"])
        trow("VAT (12% incl.):", "—")

        tk.Frame(totals_bg, bg=self._RULE, height=1).pack(fill="x", padx=8, pady=4)

        trow("TOTAL:", self._rm(total_v), bold=True, large=True, color=self._GREEN)

        tk.Frame(totals_bg, bg=self._RULE, height=1).pack(fill="x", padx=8, pady=4)

        trow("Amount Paid:", self._rm(paid_v))
        if payment == "Cash":
            trow("Change:", self._rm(change_v))

        tk.Frame(totals_bg, bg=self._CARD, height=6).pack()

        rule(thick=True)
        spacer(8)

        # ── FOOTER ────────────────────────────────────────────────────────────
        tk.Label(inner, text="Thank you for your order!", bg=self._BG, fg=self._GREEN,
                 font=("Segoe UI", 9, "bold"), anchor="center").pack(fill="x", padx=PAD)
        spacer(14)

        # ── BUTTONS ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=self._BG)
        btn_frame.pack(fill="x", pady=(4, 10), padx=PAD)
        btn_frame.columnconfigure(0, weight=1, uniform="rb")
        btn_frame.columnconfigure(1, weight=1, uniform="rb")

        def _print_pdf():
            try:
                path = ReceiptService.generate_receipt(self.order_data, self.items)
                ok = ReceiptService.open_file(path)
                if not ok:
                    messagebox.showwarning(
                        "Receipt",
                        f"PDF saved but could not open automatically.\n\nSaved to:\n{path}",
                        parent=self,
                    )
            except Exception as exc:
                messagebox.showerror("Receipt Error",
                                     f"Failed to generate PDF.\n\n{exc}", parent=self)

        tk.Button(btn_frame, text="Print / Save PDF",
                  command=_print_pdf,
                  bg=THEME.get("brown", "#6b4a3a"), fg="white",
                  activebackground=THEME.get("brown_dark", "#8E0000"),
                  activeforeground="white",
                  bd=0, pady=10, cursor="hand2",
                  font=("Segoe UI", 9, "bold"),
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        tk.Button(btn_frame, text="Close",
                  command=self.destroy,
                  bg=THEME["panel2"], fg=THEME["text"],
                  activebackground=THEME["border"],
                  bd=0, pady=10, cursor="hand2",
                  font=("Segoe UI", 9),
                  ).grid(row=0, column=1, sticky="ew")


# ══════════════════════════════════════════════════════════════════════════════
# ConfirmOrderDialog — unchanged from original
# ══════════════════════════════════════════════════════════════════════════════
class ConfirmOrderDialog(tk.Toplevel):
    SCROLL_SPEED_UNITS = 3

    def __init__(self, parent: POSView, db: Database, auth: AuthService,
                 cart: dict[int, tuple[str, float, int, str]],
                 discount_mode: str, discount_value: float, on_done=None):
        super().__init__(parent)
        self.parent_view = parent
        self.db = db
        self.auth = auth
        self.svc = POSService(db)

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
        self.transient(parent)
        self.grab_set()

        self.var_order_type = tk.StringVar(value="DINE_IN")
        self.var_table_number = tk.StringVar()
        self.var_payment = tk.StringVar(value="Cash")
        _prefill = ""
        try:
            if parent.var_amount_paid and parent.var_amount_paid.get().strip():
                _prefill = parent.var_amount_paid.get().strip()
        except Exception:
            pass
        self.var_amount_paid = tk.StringVar(value=_prefill)
        self._details_expanded = tk.BooleanVar(value=False)
        self._details_rows: list[tuple[str, str]] = []
        self._build()

    def _calc_totals(self):
        subtotal = sum(qty * price for (_n, price, qty, _note) in self.cart.values())
        discount = 0.0
        mode = self.discount_mode
        if mode == "PWD" or mode == "SENIOR":
            discount = subtotal * 0.20
        elif mode == "SPECIAL":
            discount = max(0.0, min(float(self.discount_value), subtotal))
        elif mode == "amount":
            discount = max(0.0, min(float(self.discount_value), subtotal))
        elif mode == "percent":
            discount = max(0.0, min(100.0, float(self.discount_value))) / 100.0 * subtotal
        tax = 0.0
        total = max(0.0, subtotal - discount + tax)
        return subtotal, discount, tax, total

    def _build(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        subtotal, discount, tax, total = self._calc_totals()
        self._discount_amount = discount
        self._total_amount    = total

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(860, sw - 80)
        h  = min(560, sh - 80)
        x  = (sw - w) // 2
        y  = max(30, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(680, 460)
        self.resizable(True, True)

        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        hdr = tk.Frame(self, bg=THEME["brown_dark"])
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="Confirm Order", bg=THEME["brown_dark"], fg="white",
                 font=("Segoe UI", f(13), "bold"), anchor="w").pack(side="left", padx=18, pady=12)
        tk.Button(hdr, text="✕", bg=THEME["brown_dark"], fg="white",
                  activebackground=THEME["brown"], activeforeground="white",
                  bd=0, padx=14, pady=6, cursor="hand2",
                  font=("Segoe UI", f(11)), command=self.destroy).pack(side="right", padx=6)
        created_str = self.created_at.strftime("%b %d %Y  %I:%M %p")
        tk.Label(hdr, text=f"{self.created_by_user} ({self.created_by_role})  ·  {created_str}",
                 bg=THEME["brown_dark"], fg="#c9b8a8",
                 font=("Segoe UI", f(8))).pack(side="right", padx=(0, 4))

        body = tk.Frame(self, bg=THEME["bg"])
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=55, minsize=360)
        body.columnconfigure(1, weight=0)
        body.columnconfigure(2, weight=45, minsize=270)

        tk.Frame(body, bg=THEME["border"], width=1).grid(row=0, column=1, sticky="ns")

        left = tk.Frame(body, bg=THEME["bg"])
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        items_hdr = tk.Frame(left, bg=THEME["beige"])
        items_hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(items_hdr, text="Order Items", bg=THEME["beige"], fg=THEME["text"],
                 font=("Segoe UI", f(9), "bold"), padx=16, pady=9).pack(side="left")
        self.btn_toggle = tk.Button(items_hdr, text="▾ Hide",
                                    bg=THEME["beige"], fg=THEME["brown"],
                                    bd=0, padx=14, pady=9, cursor="hand2",
                                    font=("Segoe UI", f(9), "bold"),
                                    command=self._toggle_details)
        self.btn_toggle.pack(side="right")

        items_outer = tk.Frame(left, bg="#ffffff",
                               highlightthickness=1, highlightbackground=THEME["border"])
        items_outer.grid(row=1, column=0, sticky="nsew")
        items_outer.rowconfigure(0, weight=1)
        items_outer.columnconfigure(0, weight=1)

        items_canvas = tk.Canvas(items_outer, bg="#ffffff", highlightthickness=0)
        items_canvas.grid(row=0, column=0, sticky="nsew")
        items_sb = ttk.Scrollbar(items_outer, orient="vertical", command=items_canvas.yview,
                                 style="Thick.Vertical.TScrollbar")
        items_sb.grid(row=0, column=1, sticky="ns")
        items_canvas.configure(yscrollcommand=items_sb.set)

        self.details_body = tk.Frame(items_canvas, bg="#ffffff")
        items_win = items_canvas.create_window((0, 0), window=self.details_body, anchor="nw")
        self.details_body.bind("<Configure>",
                               lambda _e: items_canvas.configure(scrollregion=items_canvas.bbox("all")),
                               add="+")
        items_canvas.bind("<Configure>",
                          lambda e: items_canvas.itemconfigure(items_win, width=e.width),
                          add="+")

        def _items_scroll(e):
            items_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
            return "break"
        items_canvas.bind("<MouseWheel>", _items_scroll, add="+")
        items_canvas.bind("<Button-4>",
                          lambda _e: items_canvas.yview_scroll(-self.SCROLL_SPEED_UNITS, "units"), add="+")
        items_canvas.bind("<Button-5>",
                          lambda _e: items_canvas.yview_scroll(self.SCROLL_SPEED_UNITS, "units"), add="+")

        self._details_rows = []
        for _pid, (name, price, qty, _note) in self.cart.items():
            self._details_rows.append((f"{qty}× {name}", money(qty * price)))

        self._details_expanded.set(True)
        self._render_details()

        right = tk.Frame(body, bg=THEME["panel"])
        right.grid(row=0, column=2, sticky="nsew")
        right.columnconfigure(0, weight=1)

        pad = 18

        total_bar = tk.Frame(right, bg=THEME["success"])
        total_bar.pack(fill="x")
        tk.Label(total_bar, text="TOTAL", bg=THEME["success"], fg="white",
                 font=("Segoe UI", f(9), "bold"), padx=pad, pady=12).pack(side="left")
        tk.Label(total_bar, text=money(total), bg=THEME["success"], fg="white",
                 font=("Segoe UI", f(17), "bold"), padx=pad, pady=12).pack(side="right")

        if discount > 0:
            disc_bar = tk.Frame(right, bg="#FFF3E0")
            disc_bar.pack(fill="x")
            tk.Label(disc_bar, text="Discount applied:", bg="#FFF3E0", fg=THEME["brown"],
                     font=("Segoe UI", f(8)), padx=pad, pady=5).pack(side="left")
            tk.Label(disc_bar, text=f"−{money(discount)}", bg="#FFF3E0", fg=THEME["danger"],
                     font=("Segoe UI", f(9), "bold"), padx=pad, pady=5).pack(side="right")

        tk.Frame(right, bg=THEME["border"], height=1).pack(fill="x", pady=(10, 0))
        tk.Label(right, text="ORDER TYPE", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", f(8), "bold")).pack(anchor="w", padx=pad, pady=(8, 4))

        order_type_frame = tk.Frame(right, bg=THEME["panel"])
        order_type_frame.pack(fill="x", padx=pad, pady=(0, 6))
        order_type_frame.columnconfigure(0, weight=1, uniform="ot")
        order_type_frame.columnconfigure(1, weight=1, uniform="ot")

        def _make_ot_btn(label: str, value: str, col: int):
            def _select():
                self.var_order_type.set(value)
                _update_ot_buttons()
            btn = tk.Button(order_type_frame, text=label, command=_select,
                            bd=0, pady=sp(8), cursor="hand2",
                            font=("Segoe UI", f(10), "bold"))
            btn.grid(row=0, column=col, sticky="ew",
                     padx=(0, 4) if col == 0 else (4, 0))
            return btn

        btn_dine = _make_ot_btn("Dine In", "DINE_IN", 0)
        btn_take = _make_ot_btn("Take Out", "TAKE_OUT", 1)

        def _update_ot_buttons():
            if self.var_order_type.get() == "DINE_IN":
                btn_dine.configure(bg=THEME["success"], fg="white")
                btn_take.configure(bg=THEME["panel2"], fg=THEME["text"])
                table_lbl.configure(text="Table No.  (required)")
            else:
                btn_take.configure(bg=THEME["success"], fg="white")
                btn_dine.configure(bg=THEME["panel2"], fg=THEME["text"])
                table_lbl.configure(text="Order No.  (required)")

        tk.Label(right, text="TABLE / ORDER NO.", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", f(8), "bold")).pack(anchor="w", padx=pad, pady=(4, 2))
        table_lbl = tk.Label(right, text="Table No.  (required)",
                             bg=THEME["panel"], fg=THEME["muted"],
                             font=("Segoe UI", f(8)))
        table_lbl.pack(anchor="w", padx=pad, pady=(0, 3))

        ent_table = tk.Entry(right, textvariable=self.var_table_number,
                             bd=0, bg=THEME["panel2"], fg=THEME["text"],
                             insertbackground=THEME["text"], font=("Segoe UI", f(10)))
        ent_table.pack(fill="x", padx=pad, ipady=sp(8), pady=(0, 6))
        ent_table.focus_set()
        _update_ot_buttons()

        tk.Frame(right, bg=THEME["border"], height=1).pack(fill="x")
        tk.Label(right, text="Payment", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", f(8), "bold")).pack(anchor="w", padx=pad, pady=(8, 4))

        radio_frame = tk.Frame(right, bg=THEME["panel"])
        radio_frame.pack(fill="x", padx=pad, pady=(0, 4))
        for val, label in [("Cash", "Cash"), ("Bank/E-Wallet", "Bank Transfer / E-Wallet")]:
            tk.Radiobutton(radio_frame, text=label, value=val, variable=self.var_payment,
                           bg=THEME["panel"], fg=THEME["text"], activebackground=THEME["panel"],
                           font=("Segoe UI", f(10)), selectcolor=THEME["beige"]).pack(anchor="w", pady=sp(4))

        tk.Label(right, text="Amount Paid", bg=THEME["panel"], fg=THEME["muted"],
                 font=("Segoe UI", f(8))).pack(anchor="w", padx=pad, pady=(6, 3))

        amt_frame = tk.Frame(right, bg=THEME["panel2"])
        amt_frame.pack(fill="x", padx=pad, pady=(0, 3))
        amt_frame.columnconfigure(1, weight=1)
        tk.Label(amt_frame, text="₱", bg=THEME["panel2"], fg=THEME["muted"],
                 font=("Segoe UI", f(10))).grid(row=0, column=0, padx=(8, 2), sticky="ns")
        tk.Entry(amt_frame, textvariable=self.var_amount_paid,
                 bd=0, bg=THEME["panel2"], fg=THEME["text"],
                 insertbackground=THEME["text"],
                 font=("Segoe UI", f(10))).grid(row=0, column=1, sticky="ew", ipady=sp(8), padx=(0, 4))

        self._change_lbl = tk.Label(right, text="", bg=THEME["panel"], fg=THEME["muted"],
                                    font=("Segoe UI", f(9), "bold"), anchor="w")
        self._change_lbl.pack(fill="x", padx=pad, pady=(0, 6), ipady=4)

        def _update_change_lbl(*_):
            try:
                paid = float(self.var_amount_paid.get().strip() or "0")
            except ValueError:
                self._change_lbl.configure(text="", fg=THEME["muted"], bg=THEME["panel"])
                return
            if self.var_payment.get() == "Bank/E-Wallet":
                self._change_lbl.configure(text="", fg=THEME["muted"], bg=THEME["panel"])
                return
            diff = paid - self._total_amount
            if diff < 0:
                self._change_lbl.configure(
                    text=f"  Insufficient  —  need {money(abs(diff))} more",
                    fg=THEME["danger"], bg="#FEF2F2")
            else:
                self._change_lbl.configure(
                    text=f"  Change:  {money(diff)}",
                    fg=THEME["success"], bg="#F0FDF4")

        self.var_amount_paid.trace_add("write", _update_change_lbl)
        self.var_payment.trace_add("write", _update_change_lbl)

        tk.Frame(right, bg=THEME["panel"]).pack(fill="both", expand=True)
        tk.Frame(right, bg=THEME["border"], height=1).pack(fill="x")

        btn_row = tk.Frame(right, bg=THEME["panel"])
        btn_row.pack(fill="x", padx=pad, pady=10)
        btn_row.columnconfigure(0, weight=1, uniform="cbtn")
        btn_row.columnconfigure(1, weight=2, uniform="cbtn")

        tk.Button(btn_row, text="Cancel",
                  bg=THEME["panel2"], fg=THEME["danger"],
                  activebackground=THEME["danger"], activeforeground="white",
                  bd=0, pady=sp(10), cursor="hand2",
                  font=("Segoe UI", f(10)), command=self.destroy,
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_confirm = tk.Button(btn_row, text="Confirm Checkout",
                                     bg=THEME["success"], fg="white",
                                     activebackground=THEME["brown_dark"], activeforeground="white",
                                     bd=0, pady=sp(10), cursor="hand2",
                                     font=("Segoe UI", f(10), "bold"),
                                     command=self._confirm)
        self.btn_confirm.grid(row=0, column=1, sticky="ew")

        self.var_payment.trace_add("write", lambda *_: self._update_confirm_text())
        self._update_confirm_text()

        self.bind("<Return>", lambda _e: self._confirm(), add="+")
        self.bind("<Escape>", lambda _e: self.destroy(), add="+")

    def _section_label(self, parent: tk.Widget, text: str) -> None:
        row = tk.Frame(parent, bg=THEME["bg"])
        row.pack(fill="x", padx=18, pady=(10, 4))
        tk.Label(row, text=text.upper(), bg=THEME["bg"], fg=THEME["muted"],
                 font=("Segoe UI", ui_scale.scale_font(8), "bold")).pack(side="left")
        tk.Frame(row, bg=THEME["border"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=5)

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

        rows = self._details_rows if expanded else self._details_rows[:5]
        for i, (left_text, right_text) in enumerate(rows):
            row_bg = "#F8F9FA" if i % 2 == 0 else "#ffffff"
            r = tk.Frame(self.details_body, bg=row_bg)
            r.pack(fill="x")
            tk.Label(r, text=left_text, bg=row_bg, fg=THEME["text"],
                     font=("Segoe UI", f(9)), anchor="w").pack(side="left", padx=(12, 4), pady=sp(6))
            tk.Label(r, text=right_text, bg=row_bg, fg=THEME["text"],
                     font=("Segoe UI", f(9), "bold"), anchor="e").pack(side="right", padx=(4, 12), pady=sp(6))

        if not expanded and len(self._details_rows) > 5:
            tk.Label(self.details_body,
                     text=f"+ {len(self._details_rows) - 5} more items",
                     bg="#ffffff", fg=THEME["muted"],
                     font=("Segoe UI", f(8), "italic")).pack(anchor="w", pady=(sp(4), 0))

        if self._discount_amount > 0:
            subtotal_val = self._total_amount + self._discount_amount
            srow = tk.Frame(self.details_body, bg="#ffffff")
            srow.pack(fill="x", pady=(sp(6), 0))
            tk.Label(srow, text="Subtotal", bg="#ffffff", fg=THEME["muted"],
                     font=("Segoe UI", f(9))).pack(side="left", padx=(12, 4))
            tk.Label(srow, text=money(subtotal_val), bg="#ffffff", fg=THEME["muted"],
                     font=("Segoe UI", f(9))).pack(side="right", padx=(4, 12))

            drow = tk.Frame(self.details_body, bg="#ffffff")
            drow.pack(fill="x", pady=(sp(2), 0))
            tk.Label(drow, text="Discount", bg="#ffffff", fg=THEME["muted"],
                     font=("Segoe UI", f(9))).pack(side="left", padx=(12, 4))
            tk.Label(drow, text=f"−{money(self._discount_amount)}", bg="#ffffff", fg=THEME["danger"],
                     font=("Segoe UI", f(9), "bold")).pack(side="right", padx=(4, 12))

        tk.Frame(self.details_body, bg=THEME["border"], height=1).pack(fill="x", pady=(sp(8), 0))

        tot = tk.Frame(self.details_body, bg=THEME["success"])
        tot.pack(fill="x", pady=(sp(2), 0))
        tk.Label(tot, text="TOTAL", bg=THEME["success"], fg="white",
                 font=("Segoe UI", f(9), "bold"), padx=sp(12), pady=sp(9)).pack(side="left")
        tk.Label(tot, text=money(self._total_amount), bg=THEME["success"], fg="white",
                 font=("Segoe UI", f(14), "bold"), padx=sp(12), pady=sp(9)).pack(side="right")

    def _update_confirm_text(self):
        if self.var_payment.get() == "Bank/E-Wallet":
            self.btn_confirm.configure(text="Confirm as pending", bg="#d3a24a")
        else:
            self.btn_confirm.configure(text="Confirm Checkout", bg=THEME["success"])

    def _confirm(self):
        table_number = self.var_table_number.get().strip()
        if not table_number:
            messagebox.showerror("Table / Order No.", "Table or Order number is required.")
            return

        order_type = self.var_order_type.get()
        _disc_labels = {"PWD": "PWD", "SENIOR": "SENIOR", "SPECIAL": "SPECIAL",
                        "amount": "AMOUNT", "percent": "PERCENT", "NONE": "NONE"}
        discount_type = _disc_labels.get(self.discount_mode, "NONE")

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
        customer_name = table_number

        items = [{"product_id": pid, "qty": qty, "unit_price": price, "note": note}
                 for pid, (_name, price, qty, note) in self.cart.items()]
        try:
            order_id = self.svc.create_order(
                cashier_id=cashier_id,
                customer_name=customer_name,
                payment_method=payment,
                status=status,
                reference_no="",
                items=items,
                subtotal=subtotal,
                discount=discount,
                tax=tax,
                total=total,
                amount_paid=paid,
                cash_received=cash_received,
                change_due=change,
                order_type=order_type,
                table_number=table_number,
                discount_type=discount_type,
            )
            if status == "Pending":
                messagebox.showinfo("Saved", f"Order saved as Pending.\n\nTransaction ID: {order_id}")
            else:
                messagebox.showinfo("Completed",
                    f"Order completed.\n\nTransaction ID: {order_id}\nChange: {money(change)}")
            if self.on_done:
                self.on_done(True, status == "Completed")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Checkout Error", f"Failed to save order.\n\n{e}")