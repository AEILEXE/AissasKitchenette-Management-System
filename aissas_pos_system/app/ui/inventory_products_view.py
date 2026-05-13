"""
app/ui/inventory_products_view.py
──────────────────────────────────
Part 3 — Inventory Products page redesign.
- Search bar + category filter dropdown
- Styled "Create Product" primary button
- Table with coloured status rows (green / red tint)
- Status column: "● Available" / "● Unavailable" with coloured text
- Edit via double-click (existing behaviour preserved)
- All logic/DAO calls unchanged
"""
from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.config import THEME, resolve_image_path, PRODUCT_IMAGES_DIR
from app.db.database import Database
from app.db.dao import ProductDAO, CategoryDAO
from app.services.auth_service import AuthService
from app.ui import ui_scale
from app.ui.dialogs import show_toast
from app.utils import money

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Row-tag colours
_AVAIL_BG   = "#f0faf4"   # very light green
_UNAVAIL_BG = "#fff5f5"   # very light red
_HOVER_BG   = "#eef3ff"   # blue-tint hover


def _safe_row(row, key, default=None):
    """sqlite3.Row has no .get(); guard column-may-be-missing access."""
    try:
        v = row[key]
        return default if v is None else v
    except Exception:
        return default


class InventoryProductsView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService,
                 on_change_cb=None):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.products = ProductDAO(db)
        self.categories = CategoryDAO(db)
        # Called after a successful save/delete so the cached POS view can
        # refresh categories + product cards (and invalidate image caches).
        # Signature: on_change_cb(changed_image_rel: str | None = None)
        self.on_change_cb = on_change_cb or (lambda *_a, **_k: None)

        self.var_search   = tk.StringVar()
        self.var_category = tk.StringVar(value="All")
        self.var_status   = tk.StringVar(value="All")
        self._hovered_iid: str | None = None
        self._iid_tags: dict[str, str] = {}   # iid → original tag name
        self._prod_sort: dict = {"col": None, "reverse": False}

        self._build()
        self.refresh()

    # ──────────────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build(self):
        sc = ui_scale.get_scale()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)   # table row expands

        # ── Header card ───────────────────────────────────────────────────────
        hdr_card = tk.Frame(
            self, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        hdr_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        hdr_card.columnconfigure(0, weight=1)

        # Title row
        title_row = tk.Frame(hdr_card, bg=THEME["panel"])
        title_row.pack(fill="x", padx=16, pady=(14, 12))
        title_row.columnconfigure(0, weight=1)

        tk.Label(
            title_row, text="Products",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", ui_scale.scale_font(20), "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            title_row, text="Manage your menu catalogue",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).grid(row=1, column=0, sticky="w")

        tk.Button(
            title_row,
            text="＋  Create Product",
            bg=THEME["brown"], fg="white",
            activebackground=THEME["brown_dark"], activeforeground="white",
            bd=0,
            padx=ui_scale.s(14), pady=ui_scale.s(8),
            cursor="hand2",
            font=("Segoe UI", ui_scale.scale_font(10), "bold"),
            command=self.create_product,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        # ── Toolbar (search + category filter) ────────────────────────────────
        toolbar = tk.Frame(self, bg=THEME["bg"])
        toolbar.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)

        # Search pill
        search_pill = tk.Frame(
            toolbar, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        search_pill.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        search_pill.columnconfigure(1, weight=1)

        tk.Label(
            search_pill, text="Search by Product ID or Name",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).grid(row=0, column=0, padx=(10, 4), pady=4)

        ent_search = tk.Entry(
            search_pill, textvariable=self.var_search,
            bd=0, bg=THEME["panel"], fg=THEME["text"],
            insertbackground="#3d2b1f", insertwidth=2,
            font=("Segoe UI", ui_scale.scale_font(10)),
        )
        ent_search.grid(row=0, column=1, sticky="ew", ipady=ui_scale.s(7), padx=(0, 10))
        ent_search.bind("<KeyRelease>", lambda _e: self.refresh())

        # Category dropdown
        cat_frame = tk.Frame(toolbar, bg=THEME["bg"])
        cat_frame.grid(row=0, column=1, sticky="e")

        tk.Label(
            cat_frame, text="Category:",
            bg=THEME["bg"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(side="left", padx=(0, 6))

        self.cat_combo = ttk.Combobox(
            cat_frame, textvariable=self.var_category,
            state="readonly",
            font=("Segoe UI", ui_scale.scale_font(9)),
            width=16,
        )
        self.cat_combo.pack(side="left")
        self.cat_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self._refresh_category_options()

        # Status filter
        tk.Label(
            cat_frame, text="Status:",
            bg=THEME["bg"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).pack(side="left", padx=(12, 6))

        status_combo = ttk.Combobox(
            cat_frame, textvariable=self.var_status,
            values=["All", "Available", "Unavailable"],
            state="readonly",
            font=("Segoe UI", ui_scale.scale_font(9)),
            width=12,
        )
        status_combo.pack(side="left")
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        # ── Table ─────────────────────────────────────────────────────────────
        self._build_table()

    def _build_table(self):
        sc = ui_scale.get_scale()

        # Style
        style = ttk.Style()
        style.configure(
            "Prod.Treeview",
            rowheight=ui_scale.s(32),
            font=("Segoe UI", ui_scale.scale_font(9)),
            background=THEME["panel"],
            fieldbackground=THEME["panel"],
            foreground=THEME["text"],
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Prod.Treeview.Heading",
            font=("Segoe UI", ui_scale.scale_font(9), "bold"),
            background=THEME["beige"],
            foreground=THEME["muted"],
            relief="flat",
            padding=(ui_scale.s(10), ui_scale.s(8)),
        )
        style.map(
            "Prod.Treeview",
            background=[("selected", THEME["select_bg"])],
            foreground=[("selected", THEME["select_fg"])],
        )
        style.map("Prod.Treeview.Heading", background=[("active", THEME["beige"])])

        # Container
        tbl_card = tk.Frame(
            self, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        tbl_card.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        tbl_card.rowconfigure(0, weight=1)
        tbl_card.columnconfigure(0, weight=1)

        cols = ("id", "name", "category", "price", "available", "action")
        self.tbl = ttk.Treeview(
            tbl_card, columns=cols, show="headings",
            style="Prod.Treeview",
        )
        self.tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_card, orient="vertical", command=self.tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self.tbl.configure(yscrollcommand=ysb.set)

        # Column headers
        col_cfg = [
            ("id",          "Product ID",   ui_scale.s(90),   "center", False),
            ("name",        "Name",         ui_scale.s(180),  "w",      True),
            ("category",    "Category",     ui_scale.s(120),  "w",      False),
            ("price",       "Price",        ui_scale.s(100),  "e",      False),
            ("available",   "Status",       ui_scale.s(90),   "center", False),
            ("action",      "",             ui_scale.s(60),   "center", False),
        ]
        for cid, heading, width, anchor, stretch in col_cfg:
            self.tbl.heading(cid, text=heading, anchor="center",
                             command=lambda c=cid: self._prod_sort_by(c))
            self.tbl.column(cid, width=width, minwidth=width // 2,
                            anchor=anchor, stretch=stretch)

        # Row colour tags
        self.tbl.tag_configure("avail",    background=_AVAIL_BG,   foreground=THEME["text"])
        self.tbl.tag_configure("unavail",  background=_UNAVAIL_BG, foreground=THEME["muted"])
        self.tbl.tag_configure("hover",    background=_HOVER_BG,   foreground=THEME["text"])

        # Status text colour override (overrides row foreground for whole row)
        # We'll use per-cell visual hints through the status text content instead.

        # Bindings
        self.tbl.bind("<Double-Button-1>", lambda _e: self.edit_selected())
        self.tbl.bind("<Return>",          lambda _e: self.edit_selected())
        self.tbl.bind("<Motion>",          self._on_hover)
        self.tbl.bind("<Leave>",           self._on_leave)

    # ──────────────────────────────────────────────────────────────────────────
    # Hover effect
    # ──────────────────────────────────────────────────────────────────────────

    def _on_hover(self, event):
        iid = self.tbl.identify_row(event.y)
        if iid == self._hovered_iid:
            return
        # Restore previous
        if self._hovered_iid:
            orig = self._iid_tags.get(self._hovered_iid, "avail")
            try:
                self.tbl.item(self._hovered_iid, tags=(orig,))
            except Exception:
                pass
        self._hovered_iid = iid
        if iid:
            try:
                self.tbl.item(iid, tags=("hover",))
            except Exception:
                pass

    def _on_leave(self, _event):
        if self._hovered_iid:
            orig = self._iid_tags.get(self._hovered_iid, "avail")
            try:
                self.tbl.item(self._hovered_iid, tags=(orig,))
            except Exception:
                pass
        self._hovered_iid = None

    def _prod_sort_by(self, col: str) -> None:
        if self._prod_sort["col"] == col:
            self._prod_sort["reverse"] = not self._prod_sort["reverse"]
        else:
            self._prod_sort["col"] = col
            self._prod_sort["reverse"] = False
        rev = self._prod_sort["reverse"]
        ind = " ▲" if not rev else " ▼"
        _labels = {"id": "Product ID", "name": "Name", "category": "Category",
                   "price": "Price", "available": "Status", "action": ""}
        for cid, hdr in _labels.items():
            self.tbl.heading(cid, text=(hdr + ind) if cid == col else hdr,
                             anchor="center", command=lambda c=cid: self._prod_sort_by(c))
        self.refresh()

    # ──────────────────────────────────────────────────────────────────────────
    # Data helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _refresh_category_options(self):
        cats = self.categories.list_categories()
        names = ["All"] + [c["name"] for c in cats]
        self.cat_combo["values"] = names
        if self.var_category.get() not in names:
            self.var_category.set("All")

    def refresh(self):
        self._hovered_iid = None
        self._iid_tags.clear()
        for iid in self.tbl.get_children():
            self.tbl.delete(iid)

        self._refresh_category_options()

        # Build category-name -> hierarchy-path map so the list can show
        # "Drinks > Hot Coffee" instead of just "Hot Coffee".
        try:
            _paths = self.categories.list_hierarchy_paths()
            self._cat_path_map: dict[str, str] = {p["name"]: p["path"] for p in _paths}
        except Exception:
            self._cat_path_map = {}

        q      = (self.var_search.get() or "").strip().lower()
        cat    = self.var_category.get()
        status = self.var_status.get()

        all_rows = self.products.list_all()
        filtered = []
        for r in all_rows:
            name     = str(r["name"])
            cat_name = str(r["category"])
            desc     = str(r["description"] or "")
            active   = int(r["active"] or 0)
            pid_str  = str(int(r["product_id"]))
            # Match by product name, category, description, or product ID (e.g. "12" or "#12")
            q_id = q.lstrip("#")
            if q and (q not in name.lower()
                      and q not in cat_name.lower()
                      and q not in desc.lower()
                      and q_id != pid_str):
                continue
            if cat != "All" and cat_name != cat:
                continue
            if status == "Available" and not active:
                continue
            if status == "Unavailable" and active:
                continue
            filtered.append(r)

        # Apply sort — use r[key] not r.get() since sqlite3.Row has no .get()
        sort_col = self._prod_sort["col"]
        if sort_col and sort_col != "action":
            _key = {
                "id":        lambda r: int(r["product_id"] or 0),
                "name":      lambda r: str(r["name"] or "").lower(),
                "category":  lambda r: str(r["category"] or "").lower(),
                "price":     lambda r: float(r["price"] or 0),
                "available": lambda r: int(r["active"] or 0),
            }
            filtered = sorted(filtered,
                               key=_key.get(sort_col, lambda r: 0),
                               reverse=self._prod_sort["reverse"])

        for r in filtered:
            pid    = int(r["product_id"])
            active = int(r["active"])
            tag          = "avail" if active else "unavail"
            status_text  = "● Available" if active else "● Unavailable"
            cat_name     = str(r["category"] or "")
            cat_display  = self._cat_path_map.get(cat_name, cat_name)
            self.tbl.insert(
                "", tk.END,
                iid=str(pid),
                values=(
                    f"#{pid}",
                    str(r["name"]), cat_display,
                    money(r["price"]),
                    status_text,
                    "Edit ›",
                ),
                tags=(tag,),
            )
            self._iid_tags[str(pid)] = tag

    def _selected_id(self) -> int | None:
        sel = self.tbl.selection()
        if not sel:
            return None
        return int(sel[0])

    def _on_product_saved(self, changed_image_rel: str | None = None):
        """Refresh the inventory list and notify any external listener
        (e.g. the cached POS view) so product cards and image caches
        update without an app restart."""
        self.refresh()
        try:
            self.on_change_cb(changed_image_rel)
        except Exception:
            pass

    def create_product(self):
        ProductEditor(self, self.db, product_id=None,
                      on_save=self._on_product_saved)

    def edit_selected(self):
        pid = self._selected_id()
        if pid is None:
            return
        ProductEditor(self, self.db, product_id=pid,
                      on_save=self._on_product_saved)


# ─────────────────────────────────────────────────────────────────────────────
# ProductEditor dialog — unchanged logic, cleaner layout
# ─────────────────────────────────────────────────────────────────────────────

class ProductEditor(tk.Toplevel):
    def __init__(self, parent: tk.Widget, db: Database, product_id: int | None, on_save=None):
        super().__init__(parent)
        self.db          = db
        self.product_id  = product_id
        self.on_save     = on_save
        self.products    = ProductDAO(db)
        self.categories  = CategoryDAO(db)

        self.title("Edit Product" if product_id else "Create Product")
        self.configure(bg=THEME["bg"])
        self.geometry(f"{ui_scale.s(700)}x{ui_scale.s(680)}")
        self.transient(parent)
        self.grab_set()

        self.var_name     = tk.StringVar()
        self.var_desc     = tk.StringVar()
        self.var_price    = tk.StringVar(value="0")
        self.var_stock    = tk.StringVar(value="0")
        self.var_low      = tk.StringVar(value="5")
        self.var_active   = tk.IntVar(value=1)
        self.var_image    = tk.StringVar()
        self.var_category = tk.StringVar()

        # Image preview reference (prevent garbage collection)
        self._img_ref = None
        self._preview_lbl: tk.Label | None = None

        # Path/Name lookup for hierarchical category dropdown
        self._path_to_name: dict[str, str] = {}
        self._name_to_path: dict[str, str] = {}

        self._build()
        self._load()

    def _build(self):
        f   = ui_scale.scale_font
        sp  = ui_scale.s

        # ── Title (top) ───────────────────────────────────────────────────────
        title_row = tk.Frame(self, bg=THEME["bg"])
        title_row.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(
            title_row, text=self.title(),
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", f(14), "bold"),
        ).pack(side="left")
        if self.product_id:
            tk.Label(
                title_row, text=f"Product ID: #{int(self.product_id)}",
                bg=THEME["bg"], fg=THEME["muted"],
                font=("Segoe UI", f(10), "bold"),
            ).pack(side="right")

        # ── Footer (bottom — packed BEFORE the scroll area so it's always visible) ──
        footer = tk.Frame(self, bg=THEME["bg"])
        footer.pack(side="bottom", fill="x", padx=18, pady=(6, 14))

        tk.Button(
            footer, text="Close",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=sp(12), pady=sp(8), cursor="hand2",
            font=("Segoe UI", f(9)),
            command=self.destroy,
        ).pack(side="right")

        label = "Update Product" if self.product_id else "Save Product"
        tk.Button(
            footer, text=label,
            bg=THEME["success"], fg="white",
            bd=0, padx=sp(12), pady=sp(8), cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._save,
        ).pack(side="right", padx=(0, 10))

        if self.product_id:
            tk.Button(
                footer, text="Delete",
                bg=THEME["danger"], fg="white",
                bd=0, padx=sp(12), pady=sp(8), cursor="hand2",
                font=("Segoe UI", f(9)),
                command=self._delete,
            ).pack(side="left")

        # ── Scrollable form area (fills remaining space) ──────────────────────
        scroll_wrap = tk.Frame(self, bg=THEME["panel"])
        scroll_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 4))
        scroll_wrap.rowconfigure(0, weight=1)
        scroll_wrap.columnconfigure(0, weight=1)

        form_canvas = tk.Canvas(scroll_wrap, bg=THEME["panel"], highlightthickness=0)
        form_canvas.grid(row=0, column=0, sticky="nsew")

        form_sb = ttk.Scrollbar(scroll_wrap, orient="vertical", command=form_canvas.yview)
        form_sb.grid(row=0, column=1, sticky="ns")
        form_canvas.configure(yscrollcommand=form_sb.set)

        # Inner frame — all form fields go here
        box = tk.Frame(form_canvas, bg=THEME["panel"])
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)
        _win_id = form_canvas.create_window((0, 0), window=box, anchor="nw")

        box.bind(
            "<Configure>",
            lambda _e: form_canvas.configure(scrollregion=form_canvas.bbox("all")),
            add="+",
        )
        form_canvas.bind(
            "<Configure>",
            lambda e: form_canvas.itemconfigure(_win_id, width=e.width),
            add="+",
        )

        # Mousewheel — bind only while hovering the canvas
        def _scroll(event):
            if not form_canvas.winfo_exists():
                return
            form_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

        form_canvas.bind("<Enter>", lambda _e: form_canvas.bind_all("<MouseWheel>", _scroll), add="+")
        form_canvas.bind("<Leave>", lambda _e: form_canvas.unbind_all("<MouseWheel>"), add="+")

        # ── Image row ─────────────────────────────────────────────────────────
        tk.Label(
            box, text="Product Image",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(9), "bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 2))
        req_txt = "(required — choose an image file)" if not self.product_id else "(optional — choose a new file to replace the current image)"
        tk.Label(
            box, text=req_txt,
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(8)),
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 4))

        row_img = tk.Frame(box, bg=THEME["panel"])
        row_img.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14)
        row_img.columnconfigure(1, weight=1)

        tk.Button(
            row_img, text="Choose File",
            command=self._choose_file,
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=sp(10), pady=sp(6), cursor="hand2",
            font=("Segoe UI", f(9)),
        ).grid(row=0, column=0)

        tk.Entry(
            row_img, textvariable=self.var_image,
            bd=0, bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", f(9)),
            insertbackground="#3d2b1f", insertwidth=2,
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0), ipady=sp(6))

        # Image preview — fixed 140px height, proportional resize, centered
        preview_frame = tk.Frame(
            box, bg=THEME["panel2"],
            highlightthickness=1, highlightbackground=THEME["border"],
            height=sp(140),
        )
        preview_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(8, 0))
        preview_frame.pack_propagate(False)
        preview_frame.grid_propagate(False)

        self._preview_lbl = tk.Label(
            preview_frame,
            text="No Image Selected",
            bg=THEME["panel2"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
            compound="center",
        )
        self._preview_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ── Product Name ──────────────────────────────────────────────────────
        tk.Label(
            box, text="Product Name",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
        ).grid(row=4, column=0, sticky="w", padx=14, pady=(12, 4))
        tk.Entry(
            box, textvariable=self.var_name,
            bd=0, bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", f(10)),
            insertbackground="#3d2b1f", insertwidth=2,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8), ipady=sp(8))

        # ── Category row ──────────────────────────────────────────────────────
        cat_row = tk.Frame(box, bg=THEME["panel"])
        cat_row.grid(row=6, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
        cat_row.columnconfigure(1, weight=1)

        tk.Label(
            cat_row, text="Category",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
        ).grid(row=0, column=0, sticky="w")

        self.cbo_cat = ttk.Combobox(
            cat_row, textvariable=self.var_category, state="readonly",
            font=("Segoe UI", f(9)),
        )
        self.cbo_cat.grid(row=0, column=1, sticky="ew", padx=(10, 10))

        tk.Button(
            cat_row, text="+ Add",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, padx=8, cursor="hand2",
            font=("Segoe UI", f(9)),
            command=self._add_category,
        ).grid(row=0, column=2)

        # ── Price ─────────────────────────────────────────────────────────────
        tk.Label(
            box, text="Price (\u20b1)",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
        ).grid(row=9, column=0, sticky="w", padx=14)
        tk.Entry(
            box, textvariable=self.var_price,
            bd=0, bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", f(10)),
            insertbackground="#3d2b1f", insertwidth=2,
        ).grid(row=9, column=1, sticky="ew", padx=14, pady=(0, 8), ipady=sp(8))

        # ── Available checkbox ────────────────────────────────────────────────
        tk.Checkbutton(
            box, text="Available  (uncheck to hide from POS)",
            variable=self.var_active,
            bg=THEME["panel"], fg=THEME["text"],
            activebackground=THEME["panel"],
            font=("Segoe UI", f(9)),
        ).grid(row=10, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 14))

    def _refresh_categories(self):
        # Hierarchy paths: "Beef", "Drinks > Hot Coffee", etc. Stored separately
        # from the displayed text so we can resolve back to a name on save.
        try:
            paths = self.categories.list_hierarchy_paths()
        except Exception:
            paths = [{"name": c["name"], "path": c["name"]}
                     for c in self.categories.list_categories()]
        self._path_to_name = {p["path"]: p["name"] for p in paths}
        self._name_to_path = {p["name"]: p["path"] for p in paths}
        labels = [p["path"] for p in paths]
        self.cbo_cat["values"] = labels
        cur_name = self.var_category.get()
        if cur_name and cur_name in self._name_to_path:
            self.var_category.set(self._name_to_path[cur_name])
        elif not self.var_category.get() and labels:
            self.var_category.set(labels[0])

    def _load(self):
        self._refresh_categories()
        if not self.product_id:
            return

        r = self.db.fetchone(
            """
            SELECT p.id AS product_id, p.name, p.description, p.image_path,
                   p.price, p.stock AS stock_qty, p.low_stock, p.active,
                   COALESCE(c.name,'') AS category
            FROM products p
            LEFT JOIN categories c ON p.category_id=c.id
            WHERE p.id=?;
            """,
            (int(self.product_id),),
        )
        if not r:
            return

        self.var_name.set(r["name"])
        img_path = r["image_path"] or ""
        self.var_image.set(img_path)
        self.var_price.set(str(r["price"]))
        self.var_stock.set(str(r["stock_qty"]))
        self.var_low.set(str(r["low_stock"]))
        self.var_active.set(int(r["active"]))
        self.var_category.set(r["category"] or "")

        # Show image preview for existing product
        if img_path:
            self.after(100, lambda: self._show_preview(img_path))

    def _show_preview(self, image_path: str) -> None:
        """Display a proportionally-resized thumbnail centred in the preview frame."""
        if self._preview_lbl is None:
            return
        if not image_path:
            self._preview_lbl.configure(image="", text="No Image Selected", compound="none")
            self._img_ref = None
            return
        if not HAS_PIL:
            self._preview_lbl.configure(image="", text="Install Pillow for preview", compound="none")
            self._img_ref = None
            return
        resolved = resolve_image_path(image_path)
        abs_path = str(resolved) if resolved else image_path
        if not resolved or not os.path.exists(abs_path):
            self._preview_lbl.configure(image="", text="Image file not found", compound="none")
            self._img_ref = None
            return
        try:
            from PIL import Image as PILImage, ImageTk
            img = PILImage.open(abs_path).convert("RGBA")
            # Proportional resize: fit within 260×120 keeping aspect ratio
            MAX_W, MAX_H = 260, 120
            img.thumbnail((MAX_W, MAX_H), PILImage.LANCZOS)
            # Composite onto a bg-coloured canvas to avoid alpha artefacts
            bg = PILImage.new("RGBA", img.size, (242, 238, 232, 255))
            bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            tk_img = ImageTk.PhotoImage(bg.convert("RGB"))
            self._img_ref = tk_img  # prevent GC
            self._preview_lbl.configure(image=tk_img, text="", compound="center")
        except Exception:
            self._preview_lbl.configure(image="", text="Could not load preview", compound="none")
            self._img_ref = None

    def _choose_file(self):
        path = filedialog.askopenfilename(
            title="Choose product image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif"), ("All files", "*.*")]
        )
        if not path:
            return

        # PRODUCT_IMAGES_DIR is always the correct writable location
        # (next to the EXE in packaged mode, project root in dev mode)
        img_dir = str(PRODUCT_IMAGES_DIR)
        os.makedirs(img_dir, exist_ok=True)

        _, ext = os.path.splitext(path)
        ext_lower = ext.lower()

        if ext_lower in (".jpg", ".jpeg"):
            if not HAS_PIL:
                messagebox.showerror("Pillow Required",
                    "JPG images require Pillow.\n\npip install Pillow")
                return
            try:
                from PIL import Image as PILImage
                img = PILImage.open(path)
                if img.mode == "RGBA":
                    bg = PILImage.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                filename  = os.path.splitext(os.path.basename(path))[0] + ".png"
                dest_path = os.path.join(img_dir, filename)
                img.save(dest_path, "PNG")
                rel_path = os.path.join("product_images", filename)
                self.var_image.set(rel_path)
                self._show_preview(rel_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to convert JPG:\n{e}")
            return

        filename  = os.path.basename(path)
        dest_path = os.path.join(img_dir, filename)
        try:
            if os.path.exists(dest_path):
                base, ext2 = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(img_dir, f"{base}_{counter}{ext2}")):
                    counter += 1
                filename  = f"{base}_{counter}{ext2}"
                dest_path = os.path.join(img_dir, filename)
            shutil.copy2(path, dest_path)
            rel_path = os.path.join("product_images", filename)
            self.var_image.set(rel_path)
            self._show_preview(rel_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy image:\n{e}")

    def _add_category(self):
        """Open the shared category dialog (supports Main + Subcategory with a
        parent picker) without leaving the Product form. On success, refresh
        the dropdown and auto-select the new entry."""
        dlg = _CategoryDialog(self, self.db)
        if not dlg.result:
            return
        new_name = (dlg.result.get("name") or "").strip()
        parent_id = dlg.result.get("parent_id")
        if not new_name:
            return
        try:
            self.categories.create(new_name, parent_id)
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                messagebox.showwarning(
                    "Duplicate Category",
                    f"A category named \"{new_name}\" already exists.",
                    parent=self,
                )
            else:
                messagebox.showerror(
                    "Error", f"Could not create category:\n{exc}", parent=self,
                )
            return
        # The dropdown shows hierarchy paths ("Drinks > Hot Coffee"). Refresh
        # so the new row is included, then select it by its full path.
        self._refresh_categories()
        new_path = self._name_to_path.get(new_name, new_name)
        self.var_category.set(new_path)

    def _save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("Name", "Product name is required.")
            return

        image_path = self.var_image.get().strip()

        # Image is required when creating a new product
        if not self.product_id and not image_path:
            messagebox.showerror(
                "Image Required",
                "A product image is required.\n\nPlease click 'Choose File' to select an image.",
            )
            return

        try:
            price = float(self.var_price.get().strip() or 0)
            stock = int(self.var_stock.get().strip() or 0)
            low   = int(self.var_low.get().strip() or 5)
        except Exception:
            messagebox.showerror("Invalid", "Price/stock/low must be numbers.")
            return

        # Combobox stores hierarchy path (e.g. "Drinks > Hot Coffee"). Resolve
        # it back to the leaf category name before looking up the FK.
        cat_label = self.var_category.get().strip()
        cat_name  = self._path_to_name.get(cat_label, cat_label) if cat_label else ""
        cat       = self.categories.get_by_name(cat_name) if cat_name else None
        cat_id    = int(cat["category_id"]) if cat else None

        was_update = bool(self.product_id)
        if self.product_id:
            self.products.update(
                self.product_id, cat_id, name, "", "", image_path,
                price, stock, low, int(self.var_active.get()),
            )
        else:
            self.products.create(
                cat_id, name, "", "", image_path,
                price, stock, low, int(self.var_active.get()),
            )

        if self.on_save:
            try:
                self.on_save(image_path or None)
            except TypeError:
                # Callers using the legacy zero-arg signature still work.
                self.on_save()
        parent_for_toast = self.master
        self.destroy()
        try:
            show_toast(parent_for_toast,
                       f"'{name}' {'updated' if was_update else 'added'} successfully.")
        except Exception:
            pass

    def _delete(self):
        if not self.product_id:
            return
        if not messagebox.askyesno("Delete", "Delete this product?"):
            return
        self.products.delete(self.product_id)
        if self.on_save:
            try:
                self.on_save(None)
            except TypeError:
                self.on_save()
        parent_for_toast = self.master
        self.destroy()
        try:
            show_toast(parent_for_toast, "Product deleted successfully.")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# simple_input helper (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def simple_input(parent: tk.Widget, title: str, label: str) -> str | None:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=THEME["bg"])
    dlg.geometry("360x160")
    dlg.transient(parent)
    dlg.grab_set()

    var = tk.StringVar()
    tk.Label(dlg, text=label, bg=THEME["bg"], fg=THEME["text"],
             font=("Segoe UI", ui_scale.scale_font(9))).pack(anchor="w", padx=14, pady=(14, 6))
    ent = tk.Entry(dlg, textvariable=var, bd=0, bg=THEME["panel2"], fg=THEME["text"],
                   font=("Segoe UI", ui_scale.scale_font(9)),
                   insertbackground="#3d2b1f", insertwidth=2)
    ent.pack(fill="x", padx=14, ipady=8)
    ent.focus_set()

    out = {"v": None}

    def ok():
        out["v"] = var.get().strip()
        dlg.destroy()

    btns = tk.Frame(dlg, bg=THEME["bg"])
    btns.pack(fill="x", padx=14, pady=14)
    tk.Button(btns, text="Cancel", bg=THEME["panel2"], fg=THEME["text"],
              bd=0, padx=12, pady=8, command=dlg.destroy).pack(side="right")
    tk.Button(btns, text="OK", bg=THEME["success"], fg="white",
              bd=0, padx=12, pady=8, command=ok).pack(side="right", padx=(0, 10))

    dlg.bind("<Return>", lambda _e: ok())
    dlg.wait_window()
    return out["v"]


# ─────────────────────────────────────────────────────────────────────────────
# Category Add/Edit dialog (supports main category + subcategory)
# ─────────────────────────────────────────────────────────────────────────────


class _CategoryDialog(tk.Toplevel):
    """Add/Edit category. Supports Main vs. Subcategory + parent dropdown."""

    def __init__(self, parent: tk.Widget, db: Database,
                 category: dict | None = None):
        super().__init__(parent)
        self.db = db
        self.cat = category
        self.result: dict | None = None
        self.title("Edit Category" if category else "Add Category")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cats = self.db.fetchall(
            "SELECT id, name FROM categories ORDER BY name;"
        )
        self._main_options = [(int(r["id"]), str(r["name"])) for r in cats]
        if category:
            cur_id = int(category.get("category_id", 0) or 0)
            self._main_options = [(i, n) for (i, n) in self._main_options if i != cur_id]

        # ── Header ────────────────────────────────────────────────────────────
        tk.Label(self,
                 text="Edit Category" if category else "New Category",
                 bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 13, "bold")
                 ).grid(row=0, column=0, columnspan=2,
                        sticky="w", padx=16, pady=(14, 4))
        tk.Label(self,
                 text="Categories can be top-level (Main) or nested under a parent (Subcategory).",
                 bg=THEME["bg"], fg=THEME["muted"],
                 font=("Segoe UI", 9)
                 ).grid(row=1, column=0, columnspan=2,
                        sticky="w", padx=16, pady=(0, 10))

        # ── Name ──────────────────────────────────────────────────────────────
        tk.Label(self, text="Name", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=2, column=0,
                                              sticky="w", padx=16, pady=4)
        self.var_name = tk.StringVar(value=str((category or {}).get("name", "")))
        tk.Entry(self, textvariable=self.var_name, width=32,
                 bg=THEME["beige"], fg=THEME["text"],
                 insertbackground="#3d2b1f", insertwidth=2,
                 font=("Segoe UI", 10)
                 ).grid(row=2, column=1, sticky="w", padx=16, pady=4)

        # ── Type segmented buttons ───────────────────────────────────────────
        tk.Label(self, text="Type", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=3, column=0, sticky="w",
                                              padx=16, pady=(8, 4))
        seg = tk.Frame(self, bg=THEME["bg"])
        seg.grid(row=3, column=1, sticky="w", padx=16, pady=(8, 4))
        initial_type = "SUB" if (category and category.get("parent_id")) else "MAIN"
        self.var_type = tk.StringVar(value=initial_type)
        self._type_btns: dict[str, tk.Button] = {}
        for v, lbl in (("MAIN", "Main Category"), ("SUB", "Subcategory")):
            b = tk.Button(seg, text=lbl, command=lambda vv=v: self._set_type(vv),
                          bd=0, padx=14, pady=8, cursor="hand2",
                          font=("Segoe UI", 10, "bold"), relief="flat")
            b.pack(side="left", padx=(0, 6))
            self._type_btns[v] = b

        # ── Parent dropdown (visible only for Sub) ───────────────────────────
        self._parent_lbl = tk.Label(self, text="Parent Category",
                                     bg=THEME["bg"], fg=THEME["text"],
                                     font=("Segoe UI", 10))
        self._parent_lbl.grid(row=4, column=0, sticky="w", padx=16, pady=4)
        self.var_parent = tk.StringVar()
        names = [n for (_i, n) in self._main_options]
        self._parent_cb = ttk.Combobox(self, textvariable=self.var_parent,
                                        values=names, state="readonly",
                                        width=30, font=("Segoe UI", 10))
        self._parent_cb.grid(row=4, column=1, sticky="w", padx=16, pady=4)
        if category and category.get("parent_id"):
            for (i, n) in self._main_options:
                if i == int(category["parent_id"]):
                    self.var_parent.set(n)
                    break
        elif names:
            self.var_parent.set(names[0])

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.grid(row=5, column=0, columnspan=2,
                     sticky="ew", padx=16, pady=(14, 14))
        btn_row.columnconfigure(0, weight=1)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=THEME["panel2"], fg=THEME["text"],
                  bd=0, padx=22, pady=10, cursor="hand2",
                  font=("Segoe UI", 10)
                  ).grid(row=0, column=1, padx=(0, 8))
        tk.Button(btn_row,
                  text=("Update" if category else "Save"),
                  command=self._save,
                  bg=THEME["success"], fg="white",
                  activebackground=THEME["primary_dark"], activeforeground="white",
                  bd=0, padx=22, pady=10, cursor="hand2",
                  font=("Segoe UI", 10, "bold")
                  ).grid(row=0, column=2)

        self._set_type(initial_type)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.wait_window()

    def _set_type(self, val: str):
        self.var_type.set(val)
        for v, b in self._type_btns.items():
            if v == val:
                b.configure(bg=THEME["primary"], fg="white",
                            activebackground=THEME["primary_dark"],
                            activeforeground="white")
            else:
                b.configure(bg=THEME["panel2"], fg=THEME["text"],
                            activebackground=THEME["border"],
                            activeforeground=THEME["text"])
        # Show/hide parent picker
        try:
            if val == "SUB":
                self._parent_lbl.grid()
                self._parent_cb.grid()
                if not self._main_options:
                    self._parent_cb.configure(state="disabled")
            else:
                self._parent_lbl.grid_remove()
                self._parent_cb.grid_remove()
        except Exception:
            pass

    def _save(self):
        name = (self.var_name.get() or "").strip()
        if not name:
            messagebox.showerror("Validation", "Category name is required.",
                                 parent=self)
            return
        parent_id: int | None = None
        if self.var_type.get() == "SUB":
            sel = (self.var_parent.get() or "").strip()
            for (i, n) in self._main_options:
                if n == sel:
                    parent_id = i
                    break
            if parent_id is None:
                messagebox.showerror(
                    "Validation",
                    "Pick a parent category, or switch the type to Main.",
                    parent=self,
                )
                return
        self.result = {"name": name, "parent_id": parent_id}
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# InventoryCategoriesView
# ─────────────────────────────────────────────────────────────────────────────

class InventoryCategoriesView(tk.Frame):
    """
    Category management panel inside the Inventory shell.
    Shows all categories with their product counts and allows safe deletion
    (only when no products are linked) and creation of new categories.
    """

    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService,
                 refresh_pos_cats_cb=None):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.categories = CategoryDAO(db)
        self._refresh_pos_cats = refresh_pos_cats_cb or (lambda: None)
        self._del_btn: tk.Button | None = None
        self._build()
        self.refresh()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # ── Header card ───────────────────────────────────────────────────
        hdr_card = tk.Frame(
            self, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        hdr_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        hdr_card.columnconfigure(0, weight=1)

        title_row = tk.Frame(hdr_card, bg=THEME["panel"])
        title_row.pack(fill="x", padx=16, pady=(14, 12))
        title_row.columnconfigure(0, weight=1)

        tk.Label(
            title_row, text="Categories",
            bg=THEME["panel"], fg=THEME["text"],
            font=("Segoe UI", f(20), "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            title_row,
            text="Manage main categories and subcategories. "
                 "Subcategories appear under their parent in POS.",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
        ).grid(row=1, column=0, sticky="w")

        tk.Button(
            title_row,
            text="＋  Add Category",
            bg=THEME["brown"], fg="white",
            activebackground=THEME["brown_dark"], activeforeground="white",
            bd=0,
            padx=sp(14), pady=sp(8),
            cursor="hand2",
            font=("Segoe UI", f(10), "bold"),
            command=self._create_category,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        # ── Action bar (Edit + Delete — always visible and enabled) ──────────
        action_bar = tk.Frame(self, bg=THEME["bg"])
        action_bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))

        self._edit_btn = tk.Button(
            action_bar,
            text="Edit",
            bg=THEME["primary"], fg="white",
            activebackground=THEME["primary_dark"], activeforeground="white",
            bd=0, padx=sp(14), pady=sp(7),
            cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._edit_selected,
        )
        self._edit_btn.pack(side="left", padx=(0, 6))

        self._del_btn = tk.Button(
            action_bar,
            text="Delete",
            bg=THEME["danger"], fg="white",
            activebackground="#c0392b", activeforeground="white",
            bd=0, padx=sp(14), pady=sp(7),
            cursor="hand2",
            font=("Segoe UI", f(9), "bold"),
            command=self._delete_selected,
        )
        self._del_btn.pack(side="left")

        # Refresh button
        tk.Button(
            action_bar,
            text="↻ Refresh",
            bg=THEME["panel2"], fg=THEME["text"],
            activebackground=THEME["border"],
            bd=0, padx=sp(12), pady=sp(7),
            cursor="hand2",
            font=("Segoe UI", f(9)),
            command=self.refresh,
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            action_bar,
            text="Select a row then Edit or Delete. Double-click to edit.",
            bg=THEME["bg"], fg=THEME["muted"],
            font=("Segoe UI", f(8), "italic"),
        ).pack(side="left", padx=(14, 0))

        # ── Table ─────────────────────────────────────────────────────────
        self._build_table()

    def _build_table(self):
        f  = ui_scale.scale_font
        sp = ui_scale.s

        style = ttk.Style()
        style.configure(
            "Cat.Treeview",
            rowheight=sp(34),
            font=("Segoe UI", f(10)),
            background=THEME["panel"],
            fieldbackground=THEME["panel"],
            foreground=THEME["text"],
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Cat.Treeview.Heading",
            font=("Segoe UI", f(9), "bold"),
            background=THEME["beige"],
            foreground=THEME["muted"],
            relief="flat",
            padding=(sp(10), sp(8)),
        )
        style.map(
            "Cat.Treeview",
            background=[("selected", THEME["select_bg"])],
            foreground=[("selected", THEME["select_fg"])],
        )
        style.map("Cat.Treeview.Heading", background=[("active", THEME["beige"])])

        tbl_card = tk.Frame(
            self, bg=THEME["panel"],
            highlightthickness=1, highlightbackground=THEME["border"],
        )
        tbl_card.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        tbl_card.rowconfigure(0, weight=1)
        tbl_card.columnconfigure(0, weight=1)

        cols = ("id", "name", "type", "parent", "products")
        self.tbl = ttk.Treeview(
            tbl_card, columns=cols, show="headings",
            style="Cat.Treeview",
        )
        self.tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(tbl_card, orient="vertical", command=self.tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self.tbl.configure(yscrollcommand=ysb.set)

        col_cfg = [
            ("id",       "ID",            sp(70),  "center", False),
            ("name",     "Category Name", sp(280), "w",      True),
            ("type",     "Type",          sp(110), "center", False),
            ("parent",   "Parent",        sp(160), "w",      False),
            ("products", "Products",      sp(100), "center", False),
        ]
        for cid, heading, width, anchor, stretch in col_cfg:
            self.tbl.heading(cid, text=heading,
                             anchor="w" if cid in ("name", "parent") else "center")
            self.tbl.column(cid, width=width, minwidth=sp(60),
                            anchor=anchor, stretch=stretch)

        # Visual cue: subcategories highlighted in muted text colour
        self.tbl.tag_configure("main", foreground=THEME["text"])
        self.tbl.tag_configure("sub",  foreground=THEME["brown"])

        self.tbl.bind("<<TreeviewSelect>>", self._on_select)
        self.tbl.bind("<Double-Button-1>", lambda _e: self._edit_selected())
        self.tbl.bind("<Delete>", lambda _e: self._delete_selected())

    # ── Data ─────────────────────────────────────────────────────────────────

    def refresh(self):
        for iid in self.tbl.get_children():
            self.tbl.delete(iid)

        rows = self.categories.list_with_counts()
        # Build hierarchy: render mains first, then their subs indented.
        mains = [r for r in rows if not _safe_row(r, "parent_id")]
        subs_by_parent: dict[int, list] = {}
        for r in rows:
            pid = _safe_row(r, "parent_id")
            if pid:
                subs_by_parent.setdefault(int(pid), []).append(r)

        def insert_main(r):
            cid   = int(r["category_id"])
            name  = str(r["name"])
            count = int(r["product_count"])
            self.tbl.insert("", tk.END, iid=str(cid),
                            tags=("main",),
                            values=(f"#{cid}", name, "Main", "—", count))

        def insert_sub(parent_name, r):
            cid   = int(r["category_id"])
            name  = str(r["name"])
            count = int(r["product_count"])
            self.tbl.insert("", tk.END, iid=str(cid),
                            tags=("sub",),
                            values=(f"#{cid}", f"    └ {name}",
                                    "Subcategory", parent_name, count))

        if mains or subs_by_parent:
            for m in mains:
                insert_main(m)
                for s in subs_by_parent.get(int(m["category_id"]), []):
                    insert_sub(str(m["name"]), s)
            # Orphans (parent_id pointing nowhere) — surface so they aren't lost
            seen = {int(m["category_id"]) for m in mains}
            for pid, srows in subs_by_parent.items():
                if pid not in seen:
                    for s in srows:
                        insert_sub("(missing parent)", s)
        else:
            # Schema without parent_id — fall back to flat
            for r in rows:
                cid   = int(r["category_id"])
                name  = str(r["name"])
                count = int(r["product_count"])
                self.tbl.insert("", tk.END, iid=str(cid),
                                tags=("main",),
                                values=(f"#{cid}", name, "Main", "—", count))

        # Reset button highlights (no selection after refresh)
        self._on_select()

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_select(self, _event=None):
        """Highlight active selection in action buttons; buttons stay always enabled."""
        sel = self.tbl.selection()
        if sel:
            if getattr(self, "_edit_btn", None):
                self._edit_btn.configure(
                    bg=THEME["primary"],
                    relief="flat",
                )
            if self._del_btn:
                self._del_btn.configure(
                    bg=THEME["danger"],
                    relief="flat",
                )
        else:
            if getattr(self, "_edit_btn", None):
                self._edit_btn.configure(
                    bg=THEME["primary_light"],
                    relief="flat",
                )
            if self._del_btn:
                self._del_btn.configure(
                    bg="#C7766F",
                    relief="flat",
                )

    def _create_category(self):
        dlg = _CategoryDialog(self, self.db)
        if not dlg.result:
            return
        try:
            self.categories.create(dlg.result["name"], dlg.result.get("parent_id"))
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                messagebox.showwarning(
                    "Duplicate",
                    f"A category named '{dlg.result['name']}' already exists.",
                    parent=self,
                )
            else:
                messagebox.showerror("Error", f"Could not create category:\n{exc}",
                                     parent=self)
            return
        self.refresh()
        self._refresh_pos_cats()
        try:
            show_toast(self, f"Category '{dlg.result['name']}' added.")
        except Exception:
            pass

    def _edit_selected(self):
        sel = self.tbl.selection()
        if not sel:
            try:
                show_toast(self, "Select a category row first.", kind="warning")
            except Exception:
                messagebox.showinfo("No Selection", "Select a category to edit.", parent=self)
            return
        cat_id = int(sel[0])
        cur = self.db.fetchone(
            "SELECT id, name, parent_id FROM categories WHERE id=?;",
            (cat_id,),
        )
        if not cur:
            return
        dlg = _CategoryDialog(self, self.db, category={
            "category_id": cat_id,
            "name": cur["name"],
            "parent_id": _safe_row(cur, "parent_id"),
        })
        if not dlg.result:
            return
        # Self-parent guard
        if (dlg.result.get("parent_id") is not None
                and int(dlg.result["parent_id"]) == cat_id):
            messagebox.showerror("Invalid Parent",
                                 "A category cannot be its own parent.",
                                 parent=self)
            return
        try:
            self.categories.update(cat_id, dlg.result["name"],
                                    dlg.result.get("parent_id"))
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                messagebox.showwarning(
                    "Duplicate",
                    f"A category named '{dlg.result['name']}' already exists.",
                    parent=self,
                )
            else:
                messagebox.showerror("Error", f"Could not update:\n{exc}",
                                     parent=self)
            return
        self.refresh()
        self._refresh_pos_cats()
        try:
            show_toast(self, f"Category '{dlg.result['name']}' updated.")
        except Exception:
            pass

    def _delete_selected(self):
        sel = self.tbl.selection()
        if not sel:
            try:
                show_toast(self, "Select a category row first.", kind="warning")
            except Exception:
                messagebox.showinfo("No Selection", "Select a category to delete.", parent=self)
            return

        cat_id   = int(sel[0])
        item     = self.tbl.item(str(cat_id))
        cat_name = str(item["values"][1]).strip().lstrip("└ ").strip()
        count    = int(item["values"][4])

        if count > 0:
            messagebox.showerror(
                "Cannot Delete",
                f"Cannot delete category while products are assigned to it.\n\n"
                f"'{cat_name}' still has {count} product(s).\n\n"
                "Reassign or delete those products first, then retry.",
                parent=self,
            )
            return

        # Block delete if subcategories exist
        try:
            sub_count = self.db.fetchone(
                "SELECT COUNT(*) AS c FROM categories WHERE parent_id=?;",
                (cat_id,),
            )
            if sub_count and int(sub_count["c"]) > 0:
                messagebox.showerror(
                    "Cannot Delete",
                    f"'{cat_name}' has {int(sub_count['c'])} subcategory/ies.\n\n"
                    "Delete or reassign the subcategories first.",
                    parent=self,
                )
                return
        except Exception:
            pass

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete category '{cat_name}'?\n\nThis cannot be undone.",
            icon="warning", parent=self,
        ):
            return

        self.categories.delete(cat_id)
        self.refresh()
        self._refresh_pos_cats()
        try:
            show_toast(self, f"Category '{cat_name}' deleted.")
        except Exception:
            pass
