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
from app.ui.dialogs import DiscountDialog, DraftTitleDialog, show_toast
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
        self._selected_category: str = ""    # "" = no selection (main level shows all active)
        self._selected_category_id: int | None = None
        self._cat_level: str = "main"        # "main" or "sub"
        self._cat_parent_id: int | None = None
        self._cat_parent_name: str = ""

        self._products_cache = []
        self._all_products_cache: list[Any] = []
        self._all_products_cache_cat: str = ""
        self._search_after: int | None = None
        self._product_card_widgets: list[tk.Frame] = []
        self._card_pool: list[tk.Frame] = []     # never destroyed — only hidden/shown
        self._loading_lbl: tk.Label | None = None  # unified overlay tracker
        self._prod_resize_after: int | None = None
        self._prod_canvas_w: int = 0
        self._layout_scheduled: bool = False
        self._cart_resize_after: int | None = None
        self._last_wm_state: str = "normal"
        self._load_gen: int = 0

        self._img_cache = _GLOBAL_IMG_CACHE  # shared, never GC'd

        self._batch_products: list[Any] = []
        self._batch_idx: int = 0
        self._batch_after: int | None = None

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
        self._keypad_target: tk.StringVar | None = None   # active field the keypad writes to
        self._lbl_subtotal_val: tk.Label | None = None
        self._lbl_discount_row: tk.Frame | None = None
        self._lbl_discount_name: tk.Label | None = None
        self._lbl_discount_val: tk.Label | None = None
        self._lbl_total_val: tk.Label | None = None
        self._cart_row_refs: dict[int, dict[str, tk.Label]] = {}

        # Cart widget pool — widgets are never destroyed, only shown/hidden in-place
        self._cart_row_pool: list[dict] = []
        self._cart_hdr_name: tk.Label | None = None
        self._cart_hdr_qty: tk.Label | None = None
        self._cart_hdr_sub: tk.Label | None = None
        self._cart_empty_lbl: tk.Label | None = None

        # Category grid layout tracking
        self._cat_grid_frame: tk.Frame | None = None
        self._cat_grid_after: int | None = None
        self._cat_grid_width: int = 0
        self._cat_click_after: int | None = None

        try:
            self.recommender = Recommender(db)
        except Exception:
            self.recommender = None
        self._suggestions_frame: tk.Frame | None = None

        self._build()
        self._building = False
        self._preload_folder_images_async()   # warm cache before first card render
        self._refresh_categories()            # sync: buttons exist before frame is shown
        self._after(0, self._refresh_products)   # start DB fetch immediately, not 100ms later
        self._after(200, self._refresh_drafts_panel)  # defer — not needed immediately
        self._refresh_cart()

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
        body.columnconfigure(0, weight=5, minsize=200)   # Products   — 50% of extra space
        body.columnconfigure(1, weight=3, minsize=180)   # Order      — 30% of extra space
        body.columnconfigure(2, weight=2, minsize=160)   # Payment    — 20% of extra space

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
            insertbackground="#3d2b1f", insertwidth=2,
        )
        search.pack(fill="x", ipady=7, padx=(10, 10))
        self._search_entry = search

        search.insert(0, "Search Products")
        search.config(fg=THEME["muted"])
        search.bind("<FocusIn>",  lambda _e: self._clear_placeholder(search, "Search Products"), add="+")
        search.bind("<FocusOut>", lambda _e: self._restore_placeholder(search, "Search Products"), add="+")
        search.bind("<KeyRelease>", lambda _e: self._debounced_search(), add="+")

        # ── ROW 1: Category tile grid (BELOW search) ─────────────────────────
        # No header strip — the Back tile lives inline with the category tiles
        # on sub-level so the area always feels like a continuous card grid.
        cat_outer = tk.Frame(prod_area, bg=THEME["panel"])
        cat_outer.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 0))
        cat_outer.columnconfigure(0, weight=1)

        # Hidden placeholder header (kept for backwards-compat with helpers
        # that grid_remove() on it). No visible content.
        self._cat_header = tk.Frame(cat_outer, bg=THEME["panel"])
        self._cat_back_btn = None  # back is rendered inline as a tile now
        self._cat_breadcrumb_lbl = tk.Label(self._cat_header, text="",
                                            bg=THEME["panel"])

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
        # scroll region is updated via after_idle in _update_prod_scroll_region after each layout pass
        self.prod_canvas.bind("<Configure>", self._on_prod_canvas_configure, add="+")
        self.prod_canvas.bind("<Map>", self._on_prod_canvas_map, add="+")
        self.prod_inner.bind("<Map>", self._on_prod_canvas_map, add="+")
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
        self._init_cart_pool()

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

        # ── DRAFTS PANEL — removed from cashier UI ────────────────────────────
        # Save/Load/Delete-Draft cashier-facing UX has been removed; the
        # drafts table and DraftDAO remain so other code paths still compile.
        # An empty placeholder frame is kept so existing references to
        # `self.drafts_section` (e.g. in _refresh_drafts_panel) stay valid.
        self.drafts_section = tk.Frame(col1, bg=THEME["panel"])
        # Not gridded — section stays hidden permanently in cashier flow.
        self.draft_list = None  # type: ignore[assignment]

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

        # ── DISCOUNT — above Pay Now (Save Draft removed from cashier flow) ──
        mid_btns = tk.Frame(col2, bg=THEME["panel"])
        mid_btns.pack(side="bottom", fill="x", padx=_pad, pady=(4, 2))
        mid_btns.columnconfigure(0, weight=1)

        tk.Button(mid_btns, text="Discount", command=self._add_discount,
                  bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=6, pady=8,
                  cursor="hand2", font=("Segoe UI", 9, "bold"),
                  ).grid(row=0, column=0, sticky="ew")

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
            if val == "TAKE_OUT":
                if self._lbl_table_no:
                    self._lbl_table_no.configure(text="Order No.  (auto)")
                # Always auto-generate fresh order number for take-out — cashier
                # never types this manually
                if self.var_table_number is not None:
                    self.var_table_number.set(self._generate_order_number())
                # Lock the entry — order number is auto-assigned
                try:
                    _tbl_entry.configure(state="readonly", readonlybackground=THEME["panel2"])
                except Exception:
                    pass
            else:
                if self._lbl_table_no:
                    self._lbl_table_no.configure(text="Table No.")
                if self.var_table_number is not None:
                    self.var_table_number.set("")
                try:
                    _tbl_entry.configure(state="normal")
                except Exception:
                    pass

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
        _tbl_entry = tk.Entry(tbl_outer, textvariable=self.var_table_number,
                 bg=THEME["panel2"], fg=THEME["text"], bd=0,
                 font=("Segoe UI", 11, "bold"), justify="center",
                 insertbackground="#3d2b1f", insertwidth=2,
                 )
        _tbl_entry.pack(fill="x", ipady=7)
        _tbl_entry.bind("<FocusIn>",  lambda _e: setattr(self, "_keypad_target", self.var_table_number), add="+")

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
            insertbackground="#3d2b1f", insertwidth=2,
        )
        self._amount_entry.pack(fill="x", padx=_pad, ipady=7)
        self._amount_entry.bind("<Key>", self._on_amount_key)
        self._amount_entry.bind("<FocusIn>",  lambda _e: setattr(self, "_keypad_target", self.var_amount_paid), add="+")

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
                _btn = tk.Button(
                    _kp, text=_key,
                    command=lambda k=_key: self._keypad_press(k),
                    bg=THEME["panel2"] if is_special else THEME.get("brown", "#6b4a3a"),
                    fg=THEME["text"] if is_special else "white",
                    activebackground=THEME.get("beige", "#FFF3E0"),
                    activeforeground=THEME["text"],
                    bd=0, padx=6, pady=10, cursor="hand2",
                    font=("Segoe UI", 13, "bold"),
                )
                _btn.grid(row=_ri, column=_ci, sticky="nsew", padx=2, pady=2)
                # Prevent keypad buttons from stealing focus from the active
                # entry — without this, clicking a button fires FocusOut on
                # the entry, clears _keypad_target, and the keypad always
                # falls back to var_amount_paid regardless of which field
                # the user clicked last.
                _btn.configure(takefocus=0)

    # ── Keypad ────────────────────────────────────────────────────────────────
    def _keypad_press(self, key: str) -> None:
        # Write to whichever field is currently focused; fall back to amount paid
        target = self._keypad_target or self.var_amount_paid
        if target is None:
            return
        current = target.get().strip()
        if key == "CLEAR" or key == "C":
            target.set("")
            return
        if key == "←":
            target.set(current[:-1])
            return
        if key == ".":
            if "." in current:
                return
            target.set((current or "0") + ".")
            return
        if key.isdigit():
            if current == "0":
                target.set(key)
            else:
                target.set(current + key)

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
        # Set backgrounds FIRST — prevents any flash on resize/maximize
        try:
            self.prod_canvas.configure(bg=self._CARD_BG)
            self.prod_inner.configure(bg=self._CARD_BG)
        except Exception:
            pass

        ew: int = int(getattr(e, "width", 0))
        if ew <= 0:
            return

        old_w = self._prod_canvas_w
        self._prod_canvas_w = ew

        # Sync inner window width whenever canvas width changes
        if ew != old_w:
            try:
                self.prod_canvas.itemconfigure(self._prod_window_id, width=ew)
            except Exception:
                pass

        # Layout commit gate: coalesce all Configure events in a burst into
        # a single after_idle pass — no artificial delay, no intermediate repaints.
        if not self._layout_scheduled:
            self._layout_scheduled = True
            self.after_idle(self._commit_layout)

    def _on_prod_canvas_map(self, _event: object = None) -> None:
        """Fire when the canvas becomes visible — pre-paint beige before any items are drawn."""
        try:
            self.prod_canvas.configure(bg=self._CARD_BG)
            self.prod_inner.configure(bg=self._CARD_BG)
        except Exception:
            pass

    def _draft_mousewheel(self, e):
        # Cashier draft UI was removed — kept as a stub to avoid breaking any
        # legacy lambda still bound somewhere.
        return None

    # ── Category grid (wrapping, uniform buttons) ─────────────────────────────
    def _on_cat_grid_configure(self, event=None) -> None:
        if self._destroyed or self._building:
            return
        # Use event dimensions when available — winfo_width() can return 1 during
        # minimize/restore transitions, which causes a spurious re-layout at width=1
        # followed by a second layout at the real width, producing double-rendered rows.
        new_w = int(getattr(event, "width", 0)) or (
            self._cat_grid_frame.winfo_width() if self._cat_grid_frame else 0
        )
        if new_w < 10 or new_w == self._cat_grid_width:
            return
        self._cat_grid_width = new_w
        self._cancel_after(self._cat_grid_after)
        is_initial = not getattr(self, "_cat_last_cols", None)
        self._cat_grid_after = self._after(0 if is_initial else 80, self._relayout_cat_grid)

    def _relayout_cat_grid(self) -> None:
        """Place all category tiles into a uniform grid that wraps based on frame width."""
        self._cat_grid_after = None
        if self._destroyed or not self.winfo_exists():
            return
        frame = self._cat_grid_frame
        if not frame or not frame.winfo_exists():
            return

        tiles = list(self._cat_buttons.values())
        if not tiles:
            return

        frame_w = frame.winfo_width()
        if frame_w < 10:
            return

        # Tile-style layout: ~118px wide tiles → 4-7 cols based on width
        tile_px_est = 130
        cols = max(3, min(8, frame_w // tile_px_est))

        if cols == getattr(self, "_cat_last_cols", -1):
            return
        self._cat_last_cols = cols

        for c in range(10):
            try:
                frame.columnconfigure(c, weight=0, uniform="")
            except Exception:
                pass

        for i, tile in enumerate(tiles):
            tile.grid_forget()
            tile.grid(row=i // cols, column=i % cols, padx=4, pady=4, sticky="nsew")

        for c in range(cols):
            frame.columnconfigure(c, weight=1, uniform="catcol")

    def _set_active_category_btn(self, name: str) -> None:
        self._selected_category = name
        for cat_name, tile in self._cat_buttons.items():
            try:
                _apply = getattr(tile, "_apply_state", None)
                if callable(_apply):
                    _apply(active=(cat_name == name))
            except Exception:
                pass

    def _update_breadcrumb(self) -> None:
        """Header strip is removed in the tile layout — Back is an inline tile.
        Kept as a no-op so existing callers stay safe."""
        return None

    def refresh_after_inventory_change(self, changed_image_rel: str | None = None) -> None:
        """Public hook called from inventory after a product/category save or delete.

        Clears the cached product list and (optionally) invalidates a single
        image cache entry, then refreshes categories + visible POS cards. Safe
        to call from the Tk main thread — schedules work via `after` so we
        never touch widgets from a background thread.
        """
        if self._destroyed or not self.winfo_exists():
            return
        try:
            if changed_image_rel:
                norm = changed_image_rel.replace("\\", "/").strip()
                key = f"img::{norm}"
                if key in self._img_cache:
                    self._img_cache.pop(key, None)
        except Exception:
            pass
        # Force a fresh DB fetch on next render.
        self._all_products_cache = []
        self._all_products_cache_cat = ""

        def _do() -> None:
            if self._destroyed or not self.winfo_exists():
                return
            try:
                self._refresh_categories()
            except Exception:
                pass
            try:
                self._refresh_products()
            except Exception:
                pass

        self._after(0, _do)

    # Category tile dimensions (px). Square-ish to mirror product cards.
    _CAT_TILE_W = 118
    _CAT_TILE_H = 50

    def _build_cat_tile(self, parent: tk.Widget, label: str, *,
                         icon: str = "", is_back: bool = False,
                         on_click=None) -> tk.Frame:
        """Build a compact text-only tile (no reserved image / icon area).
        The label is centred vertically and horizontally; a thin accent bar at
        the top keeps the brand styling and serves as a selection cue."""
        bg = THEME.get("panel2", "#E8DDD0") if is_back else THEME.get("panel", "#FFFFFF")
        accent = THEME.get("muted", "#7B6B57") if is_back else THEME.get("accent", "#D4956A")

        tile = tk.Frame(
            parent, bg=bg,
            width=self._CAT_TILE_W, height=self._CAT_TILE_H,
            highlightthickness=1, highlightbackground=THEME["border"],
            cursor="hand2",
        )
        tile.grid_propagate(False)
        tile.columnconfigure(0, weight=1)
        tile.rowconfigure(1, weight=1)

        # Top accent bar (visible selection cue) — kept thin for compactness
        accent_bar = tk.Frame(tile, bg=accent, height=3)
        accent_bar.grid(row=0, column=0, sticky="ew")

        body = tk.Frame(tile, bg=bg)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        # Inline the back arrow into the label so the back tile matches the
        # same compact text-only style as every other category card.
        display_label = label
        if is_back and icon == "←":
            display_label = f"←  {label}"

        text_lbl = tk.Label(
            body, text=display_label, bg=bg,
            fg=THEME.get("text", "#3d2b1f"),
            font=("Segoe UI", 10, "bold"),
            wraplength=self._CAT_TILE_W - 14,
            justify="center",
            anchor="center",
        )
        text_lbl.grid(row=0, column=0, sticky="nsew", padx=6, pady=(2, 4))

        # Hidden placeholder so existing code paths that reference an icon
        # label (e.g. _apply_state) keep working without conditionals.
        ico_lbl = tk.Label(body, text="", bg=bg)

        widgets = (tile, accent_bar, body, ico_lbl, text_lbl)
        for w in widgets:
            w.configure(cursor="hand2")
            if on_click is not None:
                w.bind("<Button-1>", lambda _e, cb=on_click: cb(), add="+")

        # State styling helper attached to the tile so _set_active_category_btn
        # can recolour without rebuilding.
        _ACTIVE_BG = THEME.get("select_bg", "#5C3D2E")
        _ACTIVE_FG = THEME.get("select_fg", "#FFFFFF")
        _HOVER_BORDER = THEME.get("accent", "#D4956A")
        _NORMAL_BORDER = THEME["border"]

        def _apply_state(active: bool = False):
            if is_back:
                # Back tile keeps neutral colour but shows accent border
                return
            try:
                if active:
                    for w in (tile, body, accent_bar):
                        w.configure(bg=_ACTIVE_BG)
                    text_lbl.configure(bg=_ACTIVE_BG, fg=_ACTIVE_FG)
                    ico_lbl.configure(bg=_ACTIVE_BG, fg=_ACTIVE_FG)
                    tile.configure(highlightbackground=_HOVER_BORDER,
                                    highlightcolor=_HOVER_BORDER)
                else:
                    for w in (tile, body):
                        w.configure(bg=bg)
                    accent_bar.configure(bg=accent)
                    text_lbl.configure(bg=bg, fg=THEME.get("text", "#3d2b1f"))
                    ico_lbl.configure(bg=bg, fg=THEME.get("brown", "#6b4a3a"))
                    tile.configure(highlightbackground=_NORMAL_BORDER,
                                    highlightcolor=_NORMAL_BORDER)
            except Exception:
                pass

        def _on_enter(_e=None):
            try:
                if not is_back and tile.winfo_exists():
                    tile.configure(highlightbackground=_HOVER_BORDER,
                                    highlightcolor=_HOVER_BORDER)
            except Exception:
                pass

        def _on_leave(_e=None):
            try:
                if tile.winfo_exists():
                    tile.configure(highlightbackground=_NORMAL_BORDER,
                                    highlightcolor=_NORMAL_BORDER)
            except Exception:
                pass

        for w in widgets:
            w.bind("<Enter>", _on_enter, add="+")
            w.bind("<Leave>", _on_leave, add="+")

        tile._apply_state = _apply_state  # type: ignore[attr-defined]
        return tile

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
        # Force re-layout pass next time even if column count is same
        self._cat_last_cols = -1

        if self._cat_level == "sub":
            # Inline Back tile is always the first card on sub-level
            back_tile = self._build_cat_tile(
                frame,
                label=f"Back to Categories",
                icon="←",
                is_back=True,
                on_click=self._on_back_click,
            )
            self._cat_buttons["__back__"] = back_tile

            subs = []
            if self._cat_parent_id is not None:
                subs = self.cat_dao.list_subcategories(self._cat_parent_id)
            for r in subs:
                nm = str(r["name"])
                tile = self._build_cat_tile(
                    frame, label=nm, icon="",
                    on_click=lambda n=nm: self._on_category_click(n),
                )
                self._cat_buttons[nm] = tile

            # If no subcategories, surface a single neutral tile so the row
            # still looks like a card grid (no thin/clipped strip).
            if not subs:
                parent_label = self._cat_parent_name or "Items"
                hint_tile = self._build_cat_tile(
                    frame,
                    label=f"All {parent_label}",
                    icon="",
                    is_back=True,
                    on_click=lambda: None,
                )
                self._cat_buttons["__all_parent__"] = hint_tile
        else:
            for r in self.cat_dao.list_main_categories():
                nm = str(r["name"])
                tile = self._build_cat_tile(
                    frame, label=nm, icon="",
                    on_click=lambda n=nm: self._on_category_click(n),
                )
                self._cat_buttons[nm] = tile

        if self._selected_category in self._cat_buttons:
            self._set_active_category_btn(self._selected_category)
        else:
            self._set_active_category_btn("")
        self._update_breadcrumb()
        self._cancel_after(self._cat_grid_after)
        self._cat_grid_after = self._after(0, self._relayout_cat_grid)

    def _on_category_click(self, name: str) -> None:
        if self._cat_level == "main":
            # Always drill down when a main category is clicked. Sub-level shows
            # ← Back plus this category's subcategories (or just ← Back if no subs).
            try:
                cat = self.cat_dao.get_by_name(name)
                if cat:
                    self._cat_level = "sub"
                    self._cat_parent_id = int(cat["category_id"])
                    self._cat_parent_name = name
                    self._selected_category = name
                    self._selected_category_id = int(cat["category_id"])
                    self._all_products_cache = []
                    self._all_products_cache_cat = ""
                    self._refresh_categories()
                    self._cancel_after(self._cat_click_after)
                    self._cat_click_after = self._after(100, lambda: self._do_category_load(name))
                    return
            except Exception:
                pass
        # Sub-level click on a subcategory — show only that sub's products
        self._set_active_category_btn(name)
        self._selected_category_id = None
        try:
            c = self.cat_dao.get_by_name(name)
            if c:
                self._selected_category_id = int(c["category_id"])
        except Exception:
            self._selected_category_id = None
        self._update_breadcrumb()
        self._cancel_after(self._cat_click_after)
        self._cat_click_after = self._after(100, lambda: self._do_category_load(name))

    def _on_back_click(self) -> None:
        """Return from subcategory view to main category view (no selection)."""
        self._cat_level = "main"
        self._cat_parent_id = None
        self._cat_parent_name = ""
        self._selected_category = ""
        self._selected_category_id = None
        self._all_products_cache = []
        self._all_products_cache_cat = ""
        self._refresh_categories()
        self._cancel_after(self._cat_click_after)
        self._cat_click_after = self._after(100, lambda: self._do_category_load(""))

    # ── Auto order number ─────────────────────────────────────────────────────
    def _generate_order_number(self) -> str:
        """Generate a take-out order number: T0507-001 (date + daily sequence)."""
        try:
            from datetime import date
            today = date.today().strftime("%m%d")
            r = self.db.fetchone(
                "SELECT COUNT(*) AS c FROM orders "
                "WHERE order_type='TAKE_OUT' "
                "AND DATE(datetime,'localtime')=DATE('now','localtime');"
            )
            n = (int(r["c"]) if r and r["c"] is not None else 0) + 1
            return f"T{today}-{n:03d}"
        except Exception:
            import time
            return f"T-{int(time.time()) % 100000:05d}"

    def _do_category_load(self, name: str) -> None:
        self._cat_click_after = None
        # Cancel any in-flight batch render from the previous category.
        self._cancel_after(self._batch_after)
        self._batch_after = None
        self._all_products_cache = []
        self._all_products_cache_cat = ""
        self._load_gen += 1
        self._refresh_products()

    # ── Products ──────────────────────────────────────────────────────────────
    _SEARCH_DEBOUNCE_MS = 150

    def _debounced_search(self) -> None:
        self._cancel_after(self._search_after)
        self._search_after = self._after(self._SEARCH_DEBOUNCE_MS, self._refresh_products)

    def _load_products_for_category(self) -> None:
        """Fetch products from DB in a background thread; continue on main thread."""
        cat_name       = self._selected_category or ""
        cat_level      = self._cat_level
        parent_id      = self._cat_parent_id
        parent_nm      = self._cat_parent_name or ""
        selected_cat_id = self._selected_category_id
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
                if selected_cat_id is None:
                    # No category selected — show all active products.
                    rows = t_prod_dao.list_all_active()
                elif cat_level == "main":
                    # Main-level: use the selected category ID only, plus its
                    # explicitly linked subcategories if any.
                    c_id = int(selected_cat_id)
                    subs = t_cat_dao.list_subcategories(c_id)
                    if subs:
                        all_ids = [c_id] + [int(s["category_id"]) for s in subs]
                        rows = t_prod_dao.list_by_categories(all_ids)
                    else:
                        rows = t_prod_dao.list_by_category(c_id)
                else:
                    # Sub-level: if the displayed selection is still the parent,
                    # include only the parent and its direct children.
                    if cat_name == parent_nm and parent_id is not None:
                        subs = t_cat_dao.list_subcategories(int(parent_id))
                        if subs:
                            ids = [int(parent_id)] + [int(s["category_id"]) for s in subs]
                            rows = t_prod_dao.list_by_categories(ids)
                        else:
                            rows = t_prod_dao.list_by_category(int(parent_id))
                    elif selected_cat_id is not None:
                        rows = t_prod_dao.list_by_category(int(selected_cat_id))
                    else:
                        rows = []
            except Exception as exc:
                err_msg = str(exc)
                rows = []
            finally:
                thread_db.disconnect()

            # POS displays image-driven cards. Products without an image_path
            # are kept in inventory management but suppressed here so the grid
            # never renders empty / placeholder tiles.
            try:
                rows = [r for r in rows
                        if str(_row_get(r, "image_path", "") or "").strip()]
            except Exception:
                pass

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
        if not self._layout_scheduled:
            self._layout_scheduled = True
            self.after_idle(self._commit_layout)

    def _commit_layout(self) -> None:
        """Single layout commit fired once per idle cycle after a resize burst."""
        self._layout_scheduled = False
        if self._destroyed or self._building or not self.winfo_exists():
            return
        # Read the settled canvas width before doing any layout work
        try:
            actual_w = self.prod_canvas.winfo_width()
            if actual_w > 1:
                self._prod_canvas_w = actual_w
                self.prod_canvas.itemconfigure(self._prod_window_id, width=actual_w)
        except Exception:
            pass
        self._relayout_products()
        # Commit scroll region once, after layout is settled
        try:
            if self.prod_canvas.winfo_exists():
                self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all"))
        except Exception:
            pass

    def _refresh_products(self):
        if self._destroyed or self._building or not self.winfo_exists():
            return
        self._search_after = None
        if not self._all_products_cache:
            # Cancel any in-flight batch BEFORE resetting the widget list.
            # Without this, a stale batch fires with _batch_idx>0 but an empty
            # _product_card_widgets list, causing the IndexError in the fast path.
            self._cancel_after(self._batch_after)
            self._batch_after = None
            # Hide pool cards (never destroy) and show loading overlay
            for card in self._card_pool:
                try:
                    card.grid_remove()
                except Exception:
                    pass
            self._product_card_widgets = []
            if self._loading_lbl is not None:
                try:
                    self._loading_lbl.destroy()
                except Exception:
                    pass
            self._loading_lbl = tk.Label(
                self.prod_inner, text="Loading menu…",
                bg=self._CARD_BG, fg=THEME["muted"],
                font=("Segoe UI", 12),
            )
            self._loading_lbl.pack(pady=40)
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

        # Set canvas backgrounds FIRST to prevent any flash
        try:
            self.prod_canvas.configure(bg=self._CARD_BG)
            self.prod_inner.configure(bg=self._CARD_BG)
        except Exception:
            pass

        # Destroy the overlay label (loading/empty) if present
        if self._loading_lbl is not None:
            try:
                self._loading_lbl.destroy()
            except Exception:
                pass
            self._loading_lbl = None

        # Hide ALL pool cards (never destroy — just remove from grid)
        for card in self._card_pool:
            try:
                card.grid_remove()
            except Exception:
                pass
        self._product_card_widgets = []

        if not self._products_cache:
            if self._selected_category:
                msg = f"No products in '{self._selected_category}'."
            else:
                msg = "No items found. Clear search or seed products."
            self._loading_lbl = tk.Label(
                self.prod_inner,
                text=msg,
                bg=self._CARD_BG, fg=THEME["muted"],
                font=("Segoe UI", 12, "bold"),
            )
            self._loading_lbl.pack(pady=40)
            return

        self._batch_products = list(self._products_cache)
        self._batch_idx = 0
        self._last_batch_cols = 0
        self._batch_gen = self._load_gen  # snapshot — batch aborts if generation changes
        self._batch_after = self._after(10, self._render_product_batch)

    def _render_product_batch(self) -> None:
        self._batch_after = None
        if self._destroyed or self._building or not self.winfo_exists():
            return
        # Abort stale batch: a new category was clicked after this batch was queued.
        if getattr(self, "_batch_gen", -1) != self._load_gen:
            return
        if not self.prod_inner.winfo_exists():
            return

        start = self._batch_idx
        end = min(start + self._BATCH_SIZE, len(self._batch_products))

        for i in range(start, end):
            product_data = self._batch_products[i]
            if i < len(self._card_pool):
                # Reuse existing card — update its content in place
                card = self._card_pool[i]
                self._pool_update_card(card, product_data)
            else:
                # Create new card and permanently add it to the pool
                card = self._product_card(self.prod_inner, product_data)
                self._card_pool.append(card)
            self._product_card_widgets.append(card)

        self._batch_idx = end

        # Incremental layout: only full relayout if column count changed
        cols = max(2, min(5, self._calc_product_cols()))
        last_cols = getattr(self, "_last_batch_cols", 0)
        if cols != last_cols or start == 0:
            self._last_batch_cols = cols
            self._do_product_grid_layout()
        else:
            # Fast path: just grid the new cards, existing ones stay in place.
            # Bounds-guard against any edge case where the list is shorter than expected.
            n_widgets = len(self._product_card_widgets)
            for idx in range(start, end):
                if idx >= n_widgets:
                    break
                self._product_card_widgets[idx].grid(
                    row=idx // cols, column=idx % cols,
                    sticky="nsew", padx=4, pady=4,
                )
            for r in range((end + cols - 1) // cols):
                self.prod_inner.rowconfigure(r, weight=0, minsize=0)

        if self._batch_idx < len(self._batch_products):
            self._batch_after = self._after(10, self._render_product_batch)
        else:
            # All batches done — update scroll region once (after geometry settles)
            self.after_idle(self._update_prod_scroll_region)

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

        # Configure rows — let cards determine their own height naturally
        new_rows = (len(cards) + cols - 1) // cols
        for r in range(new_rows):
            self.prod_inner.rowconfigure(r, weight=0, minsize=0)

        # Defer wraplength updates so card grid positions are committed first.
        # Applying wraplength inline triggers per-label text reflow which cascades
        # height changes up through every card frame — visible as cards "settling"
        # during resize.  after_idle fires in the same idle cycle (before next paint)
        # but AFTER Tkinter has processed all queued geometry from the grid calls above.
        #
        # Cache the computed wrap value — only recompute when canvas width changes
        # by more than 10 px or the column count changes, to avoid per-pixel thrashing.
        last_wrap_w    = getattr(self, "_last_wrap_canvas_w", -1)
        last_wrap_cols = getattr(self, "_last_wrap_cols", -1)
        if abs(self._prod_canvas_w - last_wrap_w) > 10 or cols != last_wrap_cols:
            self._last_wrap_canvas_w = self._prod_canvas_w
            self._last_wrap_cols     = cols
            card_w = max(80, (self._prod_canvas_w - (cols + 1) * 8) // cols)
            self._cached_wrap = max(60, card_w - 28)
        wrap = getattr(self, "_cached_wrap", 120)
        snapshot = list(cards)

        def _apply_wrap(w=wrap, cc=snapshot):
            for card in cc:
                refs = getattr(card, "_pool_refs", None)
                if refs:
                    try:
                        refs["name_lbl"].configure(wraplength=w)
                    except Exception:
                        pass
            self._update_prod_scroll_region()

        self.after_idle(_apply_wrap)

        # Track for skip-on-no-change optimisation in _relayout_products
        self._last_relayout_cols = cols
        self._last_relayout_count = len(cards)
        self._last_relayout_rows = new_rows

    def _update_prod_scroll_region(self) -> None:
        """Update product canvas scroll region — called via after_idle so geometry is settled."""
        try:
            if self.prod_canvas.winfo_exists():
                self.prod_canvas.configure(scrollregion=self.prod_canvas.bbox("all"))
        except Exception:
            pass

    # ── Product card — beige tile with left accent border ────────────────────
    _CARD_BG = "#e6ddbd"   # beige card background — prevents any black flash

    def _product_card(self, parent: tk.Widget, r) -> tk.Frame:
        pid     = int(r["product_id"])
        name    = str(r["name"])
        price   = float(r["price"])
        desc    = str(_row_get(r, "description", "") or "").strip()
        img_rel = _row_get(r, "image_path", None) or ""
        active  = int(_row_get(r, "active", 1) or 1)
        # Menu products are not inventory-tracked — only the active flag
        # (Show / Hide in POS) decides availability. Raw-material stock is
        # tracked separately.
        unavail = (active == 0)

        card = tk.Frame(
            parent,
            bg=self._CARD_BG,
            highlightthickness=1,
            highlightbackground=THEME["border"],
            highlightcolor=THEME["border"],
            cursor="hand2" if not unavail else "arrow",
        )
        card.columnconfigure(1, weight=1)

        clickables: list[tk.Widget] = []

        def _bind_click(w: tk.Widget):
            clickables.append(w)
            if not unavail:
                w.bind("<Button-1>",
                       lambda _e, p=pid, n=name, pr=price: self._add_to_cart(p, n, pr),
                       add="+")

        _bind_click(card)

        # Left accent border — slightly thicker for clearer visual rhythm
        accent_color = THEME.get("muted", "#7B6B57") if unavail else THEME["accent"]
        accent_bar = tk.Frame(card, bg=accent_color, width=5)
        accent_bar.grid(row=0, column=0, rowspan=6, sticky="nsew")
        _bind_click(accent_bar)

        # ── Image (unified Label — shows image OR fallback emoji) ─────────────
        img_size = self._IMG_SIZE
        img_frame = tk.Frame(card, bg=self._CARD_BG,
                             width=img_size, height=img_size,
                             cursor="hand2" if not unavail else "arrow")
        img_frame.grid(row=0, column=1, pady=(10, 4), padx=(10, 8))
        img_frame.grid_propagate(False)
        _bind_click(img_frame)

        img_lbl = tk.Label(img_frame, bg=self._CARD_BG,
                            cursor="hand2" if not unavail else "arrow")
        img_lbl.place(relx=0.5, rely=0.5, anchor="center")
        clickables.append(img_lbl)
        if not unavail:
            img_lbl.bind("<Button-1>",
                         lambda _e, p=pid, n=name, pr=price: self._add_to_cart(p, n, pr),
                         add="+")

        photo = self._load_image(img_rel)
        if photo:
            img_lbl.configure(image=photo, text="")
            img_lbl.image = photo
        else:
            # No image — leave the image area blank (no fallback emoji/icon).
            img_lbl.configure(text="", image="", bg=self._CARD_BG)

        # ── Product name ──────────────────────────────────────────────────────
        name_color = THEME.get("muted", "#7B6B57") if unavail else THEME["text"]
        name_lbl = tk.Label(
            card, text=name,
            bg=self._CARD_BG, fg=name_color,
            font=("Segoe UI", 10, "bold"),
            anchor="center", justify="center",
            wraplength=124,
            cursor="hand2" if not unavail else "arrow",
        )
        name_lbl.grid(row=1, column=1, sticky="ew", padx=(6, 8), pady=(0, 2))
        _bind_click(name_lbl)
        if len(name) > 32:
            self._add_tooltip(name_lbl, name)

        # ── Price ─────────────────────────────────────────────────────────────
        price_row = tk.Frame(card, bg=self._CARD_BG,
                              cursor="hand2" if not unavail else "arrow")
        price_row.grid(row=2, column=1, sticky="ew", padx=(6, 8), pady=(0, 4))
        price_row.columnconfigure(0, weight=1)
        _bind_click(price_row)

        price_color = THEME.get("muted", "#7B6B57") if unavail else THEME["accent"]
        price_lbl = tk.Label(
            price_row, text=money(price),
            bg=self._CARD_BG, fg=price_color,
            font=("Segoe UI", 11, "bold"),
            anchor="center",
            cursor="hand2" if not unavail else "arrow",
        )
        price_lbl.grid(row=0, column=0, sticky="ew")
        _bind_click(price_lbl)

        # ── Availability badge (only when hidden from POS / inactive) ─────────
        badge_lbl = tk.Label(
            card,
            text="Unavailable",
            bg=THEME.get("danger", "#991B1B"), fg="white",
            font=("Segoe UI", 8, "bold"),
            padx=8, pady=2,
        )
        if unavail:
            badge_lbl.grid(row=3, column=1, sticky="ew", padx=(6, 8), pady=(0, 8))
        else:
            badge_lbl.grid_remove()

        # ── Hover feedback (border colour) ────────────────────────────────────
        # Closure reads the LIVE unavail state from card._pool_refs so a
        # pooled card whose product changed from available → unavailable
        # (or vice versa) still hovers correctly.
        _BORDER       = THEME["border"]
        _BORDER_HOVER = THEME.get("accent", "#D4956A")
        def _on_enter(_e=None):
            try:
                if not card.winfo_exists():
                    return
                refs_now = getattr(card, "_pool_refs", {})
                color = _BORDER if refs_now.get("unavail") else _BORDER_HOVER
                card.configure(highlightbackground=color,
                               highlightcolor=color)
            except Exception:
                pass
        def _on_leave(_e=None):
            try:
                if card.winfo_exists():
                    card.configure(highlightbackground=_BORDER,
                                   highlightcolor=_BORDER)
            except Exception:
                pass
        for w in (card, *clickables):
            try:
                w.bind("<Enter>", _on_enter, add="+")
                w.bind("<Leave>", _on_leave, add="+")
            except Exception:
                pass

        # Store refs so this card can be updated in-place without recreation
        card._pool_refs = {   # type: ignore[attr-defined]
            "image_rel": img_rel,
            "img_lbl":   img_lbl,
            "name_lbl":  name_lbl,
            "price_lbl": price_lbl,
            "badge_lbl": badge_lbl,
            "accent":    accent_bar,
            "clickables": clickables,
            "unavail":   unavail,
        }

        return card

    def _pool_update_card(self, card: tk.Frame, r) -> None:
        """Update an existing pooled card with new product data — no widget destruction."""
        refs  = card._pool_refs   # type: ignore[attr-defined]
        pid   = int(r["product_id"])
        name  = str(r["name"])
        price = float(r["price"])
        desc  = str(_row_get(r, "description", "") or "").strip()
        img_rel = _row_get(r, "image_path", None) or ""
        active  = int(_row_get(r, "active", 1) or 1)
        unavail = (active == 0)

        # Rebind click targets — only when product is available
        for w in refs["clickables"]:
            try:
                w.unbind("<Button-1>")
                if not unavail:
                    w.bind("<Button-1>",
                           lambda _e, p=pid, n=name, pr=price: self._add_to_cart(p, n, pr))
            except Exception:
                pass

        # Update text labels (color reflects availability)
        name_color  = THEME.get("muted", "#7B6B57") if unavail else THEME["text"]
        price_color = THEME.get("muted", "#7B6B57") if unavail else THEME["accent"]
        refs["name_lbl"].configure(text=name, fg=name_color)
        refs["price_lbl"].configure(text=money(price), fg=price_color)
        try:
            accent_color = THEME.get("muted", "#7B6B57") if unavail else THEME["accent"]
            refs["accent"].configure(bg=accent_color)
        except Exception:
            pass

        # Update cursor on hand-grabable widgets
        cur = "hand2" if not unavail else "arrow"
        try:
            card.configure(cursor=cur)
            for w in refs["clickables"]:
                try:
                    w.configure(cursor=cur)
                except Exception:
                    pass
        except Exception:
            pass

        # Show/hide availability badge
        try:
            badge = refs["badge_lbl"]
            badge.configure(text="Unavailable")
            if unavail:
                badge.grid(row=3, column=1, sticky="ew", padx=(6, 8), pady=(0, 8))
            else:
                badge.grid_remove()
        except Exception:
            pass

        # Update image only when changed
        if img_rel != refs["image_rel"]:
            photo = self._load_image(img_rel)
            if photo:
                refs["img_lbl"].configure(image=photo, text="")
                refs["img_lbl"].image = photo
            else:
                refs["img_lbl"].configure(image="", text="")
            refs["image_rel"] = img_rel

        refs["unavail"] = unavail

        # Reset border to base — clears any stale hover highlight that was
        # active on the previous product when the card was reused.
        try:
            _b = THEME["border"]
            card.configure(highlightbackground=_b, highlightcolor=_b)
        except Exception:
            pass

        # Update tooltip on name label
        refs["name_lbl"].unbind("<Enter>")
        refs["name_lbl"].unbind("<Leave>")
        refs["name_lbl"].unbind("<Motion>")
        if len(name) > 32:
            self._add_tooltip(refs["name_lbl"], name)

    # ── Cart widget pool ──────────────────────────────────────────────────────

    def _init_cart_pool(self) -> None:
        """Build persistent cart header/empty label once after cart_tbl is created."""
        self.cart_tbl.columnconfigure(0, weight=1, minsize=130)
        self.cart_tbl.columnconfigure(1, weight=0, minsize=22)
        self.cart_tbl.columnconfigure(2, weight=0, minsize=26)
        self.cart_tbl.columnconfigure(3, weight=0, minsize=22)
        self.cart_tbl.columnconfigure(4, weight=0, minsize=64)
        self.cart_tbl.columnconfigure(5, weight=0, minsize=28)

        self._cart_empty_lbl = tk.Label(
            self.cart_tbl, text="No items",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9),
        )
        self._cart_hdr_name = tk.Label(
            self.cart_tbl, text="Item",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9, "bold"),
        )
        self._cart_hdr_qty = tk.Label(
            self.cart_tbl, text="Qty",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9, "bold"), anchor="center",
        )
        self._cart_hdr_sub = tk.Label(
            self.cart_tbl, text="Subtotal",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", 9, "bold"), anchor="e",
        )

    def _get_cart_row(self, pool_idx: int) -> "dict[str, tk.Widget]":
        """Return (or create) a persistent cart row at zero-based pool index."""
        if pool_idx < len(self._cart_row_pool):
            return self._cart_row_pool[pool_idx]
        row: dict[str, tk.Widget] = {
            "name_lbl":   tk.Label(self.cart_tbl, bg=THEME["panel2"], fg=THEME["text"],
                                   anchor="w", font=("Segoe UI", 9)),
            "minus_btn":  tk.Button(self.cart_tbl, text="−",
                                    bg=THEME["panel"], fg=THEME["text"],
                                    bd=0, width=2, cursor="hand2"),
            "qty_lbl":    tk.Label(self.cart_tbl, bg=THEME["panel2"], fg=THEME["text"],
                                   width=3, anchor="center"),
            "plus_btn":   tk.Button(self.cart_tbl, text="+",
                                    bg=THEME["panel"], fg=THEME["text"],
                                    bd=0, width=2, cursor="hand2"),
            "sub_lbl":    tk.Label(self.cart_tbl, bg=THEME["panel2"], fg=THEME["text"],
                                   anchor="e"),
            "remove_btn": tk.Button(self.cart_tbl, text="✕",
                                    bg=THEME["danger"], fg="white",
                                    bd=0, width=3, padx=2, pady=1,
                                    cursor="hand2", font=("Segoe UI", 9, "bold")),
        }
        self._cart_row_pool.append(row)
        return row

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
        # Menu products are not inventory-tracked — qty is only bounded by the
        # raw-material check performed at checkout. No per-card stock limit.
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
        """Refresh cart display using a persistent widget pool — no widget destruction."""
        self._cart_row_refs = {}

        if not self.cart:
            # Hide header and all pool rows; show "No items"
            if self._cart_hdr_name:
                self._cart_hdr_name.grid_remove()
            if self._cart_hdr_qty:
                self._cart_hdr_qty.grid_remove()
            if self._cart_hdr_sub:
                self._cart_hdr_sub.grid_remove()
            for pr in self._cart_row_pool:
                for w in pr.values():
                    w.grid_remove()
            if self._cart_empty_lbl:
                self._cart_empty_lbl.grid(row=0, column=0, columnspan=6, pady=4)

            self._set_discount_next_to_total(None)
            try:
                self.cart_canvas.yview_moveto(0)
                self.cart_canvas.configure(scrollregion=(0, 0, 0, 0))
            except Exception:
                pass
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

        # Items present — hide empty label, show persistent header
        if self._cart_empty_lbl:
            self._cart_empty_lbl.grid_remove()
        if self._cart_hdr_name:
            self._cart_hdr_name.grid(row=0, column=0, sticky="w", padx=(10, 2), pady=(4, 2))
        if self._cart_hdr_qty:
            self._cart_hdr_qty.grid(row=0, column=1, columnspan=3, sticky="ew", pady=(4, 2))
        if self._cart_hdr_sub:
            self._cart_hdr_sub.grid(row=0, column=4, sticky="ew", padx=(4, 4), pady=(4, 2))

        # Update pool rows in-place (no widget creation/destruction)
        row_i = 1
        for pid, (name, price, qty, _note) in self.cart.items():
            pr = self._get_cart_row(row_i - 1)
            name_txt = _truncate_text(name, max_len=22)
            pr["name_lbl"].configure(text=name_txt)
            pr["name_lbl"].grid(row=row_i, column=0, sticky="ew", padx=(10, 2), pady=2)
            pr["minus_btn"].configure(command=lambda p=pid: self._change_qty(p, -1))
            pr["minus_btn"].grid(row=row_i, column=1, padx=2, pady=2)
            pr["qty_lbl"].configure(text=str(qty))
            pr["qty_lbl"].grid(row=row_i, column=2, padx=2, pady=2)
            pr["plus_btn"].configure(command=lambda p=pid: self._change_qty(p, 1))
            pr["plus_btn"].grid(row=row_i, column=3, padx=2, pady=2)
            pr["sub_lbl"].configure(text=money(qty * price))
            pr["sub_lbl"].grid(row=row_i, column=4, sticky="e", padx=(4, 4), pady=2)
            pr["remove_btn"].configure(command=lambda p=pid: self._remove_from_cart(p))
            pr["remove_btn"].grid(row=row_i, column=5, padx=(4, 10), pady=2, sticky="e")
            self._cart_row_refs[pid] = {"qty_lbl": pr["qty_lbl"], "sub_lbl": pr["sub_lbl"]}
            row_i += 1

        # Hide unused pool rows (pool grows, never shrinks)
        for i in range(row_i - 1, len(self._cart_row_pool)):
            for w in self._cart_row_pool[i].values():
                w.grid_remove()

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

        if not self.cart:
            if self._suggestions_frame.winfo_ismapped():
                self._suggestions_frame.grid_remove()
            self._last_suggest_ids: list = []
            return

        cart_ids = list(self.cart.keys())
        try:
            suggested_ids = self.recommender.suggest(cart_ids, top_n=5)
        except Exception:
            suggested_ids = []

        # Skip full rebuild when suggestions are identical to the last render
        last = getattr(self, "_last_suggest_ids", None)
        if last is not None and last == suggested_ids:
            if not self._suggestions_frame.winfo_ismapped():
                self._suggestions_frame.grid()
            return
        self._last_suggest_ids = suggested_ids

        # Clear previous suggestion widgets before rebuilding
        for w in self._suggestions_frame.winfo_children():
            w.destroy()

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

        if not self._suggestions_frame.winfo_ismapped():
            self._suggestions_frame.grid()

    # ── Discount ──────────────────────────────────────────────────────────────
    # Manager approval is required when discount magnitude exceeds either
    # threshold below. PWD/Senior 20% legal-rate discounts are exempt because
    # they are statutory and routinely applied by cashiers.
    _LARGE_DISCOUNT_AMOUNT     = 200.0   # peso threshold
    _LARGE_DISCOUNT_PERCENT_PCT = 20.0   # % subtotal threshold for SPECIAL/ % types

    def _calc_subtotal(self) -> float:
        try:
            return float(sum(p * q for (_n, p, q, _r) in self.cart.values()))
        except Exception:
            return 0.0

    def _discount_needs_approval(self, mode: str, value: float) -> bool:
        """Return True when the chosen discount is 'large' and needs approval."""
        m = (mode or "").upper()
        # Statutory 20% PWD/Senior — no approval needed
        if m in ("NONE", "PWD", "SENIOR"):
            return False
        try:
            v = float(value or 0.0)
        except Exception:
            v = 0.0
        if v <= 0:
            return False
        sub = self._calc_subtotal()
        # SPECIAL/AMOUNT: peso threshold
        if v >= self._LARGE_DISCOUNT_AMOUNT:
            return True
        # As % of subtotal
        if sub > 0 and (v / sub) * 100.0 >= self._LARGE_DISCOUNT_PERCENT_PCT:
            return True
        return False

    def _request_manager_approval(self, action_label: str,
                                  require_reason: bool = True) -> dict | None:
        """Skip prompt for ADMIN/MANAGER current user; otherwise prompt."""
        try:
            from app.constants import ROLE_ADMIN, ROLE_MANAGER, P_VOID_APPROVE
            u = self.auth.get_current_user() if self.auth else None
            role = (getattr(u, "role", "") or "").upper()
            if role in (ROLE_ADMIN, ROLE_MANAGER):
                return {
                    "approver_id": int(getattr(u, "user_id", 0) or 0),
                    "approver_username": getattr(u, "username", "") or "",
                    "approver_role": role, "reason": "",
                }
            try:
                if (self.auth
                        and self.auth.rbac_dao.has_permission(role, P_VOID_APPROVE)):
                    return {
                        "approver_id": int(getattr(u, "user_id", 0) or 0),
                        "approver_username": getattr(u, "username", "") or "",
                        "approver_role": role, "reason": "",
                    }
            except Exception:
                pass
        except Exception:
            pass

        from app.ui.dialogs import ManagerApprovalDialog
        dlg = ManagerApprovalDialog(
            self, self.auth,
            action_label=action_label, require_reason=require_reason,
        )
        self.wait_window(dlg)
        return dlg.result

    def _add_discount(self):
        dlg = DiscountDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        mode, value = dlg.result

        # Large-discount approval gate
        if self._discount_needs_approval(mode, value):
            approval = self._request_manager_approval(
                f"applying a discount of ₱{value:,.2f}",
                require_reason=True,
            )
            if not approval:
                show_toast(self,
                            "Discount cancelled — manager approval required.",
                            kind="warning")
                return
            try:
                from app.db.dao import AuditLogDAO
                u = self.auth.get_current_user() if self.auth else None
                AuditLogDAO(self.db).log(
                    username=getattr(u, "username", "") or "",
                    action="DISCOUNT_APPROVED",
                    detail=(f"mode={mode} value={value} "
                            f"approved_by={approval.get('approver_username','')} "
                            f"reason={approval.get('reason','-')}"),
                    user_id=int(getattr(u, "user_id", 0) or 0),
                    new_value=str(approval.get("approver_id") or 0),
                )
            except Exception:
                pass

        self.discount_mode = str(mode)
        self.discount_value = float(value)
        self._refresh_cart()

    # ── Drafts (cashier UI removed; methods kept as safe no-ops) ─────────────
    def _refresh_drafts_panel(self):
        # Cashier draft UI was removed — make sure the section is hidden and
        # any internal index is cleared. DraftDAO still exists for future use.
        try:
            self.drafts_section.grid_remove()
        except Exception:
            pass
        self._draft_id_by_index.clear()

    def _get_selected_draft_id(self):
        # Cashier draft UI was removed; nothing is ever selected.
        return None

    def _save_draft(self):
        # Cashier draft UI was removed — kept as a no-op stub.
        return None

    def _load_selected_draft(self):
        # Cashier draft UI was removed — kept as a no-op stub.
        return None

    def _delete_selected_draft(self):
        # Cashier draft UI was removed — kept as a no-op stub.
        return None

    def _delete_all_drafts(self):
        # Cashier draft UI was removed — kept as a no-op stub.
        return None

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
        order_type = self.var_order_type.get()

        # Take-out order numbers are auto-generated; ensure one exists if missing
        if order_type == "TAKE_OUT" and not table_number:
            table_number = self._generate_order_number()
            if self.var_table_number is not None:
                self.var_table_number.set(table_number)

        if not table_number:
            messagebox.showerror("Table No.", "Table number is required before checkout.")
            return

        if order_type == "DINE_IN":
            try:
                _tbl_int = int(table_number)
                if not table_number.lstrip("-").isdigit() or _tbl_int < 1 or _tbl_int > 20:
                    raise ValueError
            except (ValueError, TypeError):
                messagebox.showerror("Table Number", "Table number must be from 1 to 20 only.")
                return
        # TAKE_OUT: no manual range — order number is auto-generated and accepted as-is

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

        # Pre-checkout: verify all products still exist and are active
        unavail_errors: list[str] = []
        for pid, (_name, _price, qty, _note) in self.cart.items():
            r = self.db.fetchone(
                "SELECT name, active FROM products WHERE id=?;", (pid,)
            )
            if r is None or not r["active"]:
                unavail_errors.append(f"• '{_name}' is no longer available.")
        if unavail_errors:
            messagebox.showerror(
                "Product Unavailable",
                "Cannot complete order:\n\n" + "\n".join(unavail_errors),
            )
            return

        self._product_stock.clear()
        try:
            order_id = self.svc.create_order(
                cashier_id=cashier_id,
                customer_name=table_number,
                payment_method=payment,
                status=status,
                reference_no="",  # set by resolve_pending for Bank/E-Wallet; blank for Cash
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
            if "no longer available" in err:
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
        dlg = EWalletDialog(self, order_id=order_id, total=total, db=self.db)
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
            ReceiptPreviewDialog(self, order_dict, items_list,
                                  db=self.db, auth=self.auth)
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
    Cashier flow exposes a single 'Print' action — no Save PDF option.
    """

    _BG   = str(THEME["bg"])
    _CARD = str(THEME["panel"])
    _TEXT = str(THEME["text"])
    _MUTED = str(THEME["muted"])
    _GREEN = str(THEME["success"])
    _RULE  = str(THEME["border"])

    def __init__(self, parent, order_data: dict, items: list,
                 db: Database | None = None, auth: AuthService | None = None):
        super().__init__(parent)
        self.order_data = order_data
        self.items = items
        self.db = db
        self.auth = auth
        self._closed = False

        self.title("Receipt")
        self.configure(bg=self._BG)
        self.transient(parent)
        # No grab_set — receipt is a safe info window; clicking elsewhere closes it
        self.wm_attributes("-topmost", True)
        self.resizable(False, False)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = min(400, sw - 80), min(640, sh - 80)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._build(w, h)
        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        # Arm click-outside after 300 ms so the click that opened the dialog
        # is not treated as an outside click.
        self.after(300, self._arm_outside_click)

    # ── close / click-outside ─────────────────────────────────────────────────

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.destroy()
        except Exception:
            pass

    def _arm_outside_click(self) -> None:
        try:
            if self._closed or not self.winfo_exists():
                return
        except Exception:
            return
        self.bind_all("<ButtonPress-1>", self._on_global_click, add="+")

    def _on_global_click(self, event: tk.Event) -> None:
        if self._closed:
            return
        try:
            if not self.winfo_exists():
                return
            me = str(self)
            target = str(event.widget)
            # Click is inside this dialog or any of its children — ignore
            if target == me or target.startswith(me + "."):
                return
            self._close()
        except Exception:
            pass

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

        def _print_receipt():
            """Generate the receipt and send it straight to the default printer.
            Cashier flow has no 'Save PDF' option — only Print."""
            try:
                _u = self.auth.get_current_user() if self.auth else None
                _by = (getattr(_u, "username", "") or "") if _u else ""
                path = ReceiptService.generate_receipt(
                    self.order_data, self.items, printed_by=_by
                )
                ok = ReceiptService.print_file(path)
                # Audit print regardless of dispatch success — the file exists.
                try:
                    u = self.auth.get_current_user() if self.auth else None
                    if self.db is not None:
                        self.db.log_print(
                            user_id=getattr(u, "user_id", None),
                            username=getattr(u, "username", "") or "",
                            print_type="RECEIPT",
                            reference_id=str(self.order_data.get("order_id", "")),
                            detail=os.path.basename(path),
                        )
                except Exception:
                    pass
                if not ok:
                    if messagebox.askyesno(
                        "Print",
                        "Could not send the receipt directly to a printer.\n\n"
                        f"Receipt was saved to:\n{path}\n\n"
                        "Open the file for manual print preview?",
                        parent=self,
                    ):
                        ReceiptService.open_file(path)
            except Exception as exc:
                from app.utils import log_error
                log_error("Receipt print", exc)
                messagebox.showerror(
                    "Print Error",
                    "Could not print the receipt. Please try again.",
                    parent=self,
                )

        tk.Button(btn_frame, text="Print",
                  command=_print_receipt,
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

