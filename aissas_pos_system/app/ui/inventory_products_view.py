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

from app.config import THEME
from app.db.database import Database
from app.db.dao import ProductDAO, CategoryDAO
from app.services.auth_service import AuthService
from app.ui import ui_scale
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


class InventoryProductsView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.products = ProductDAO(db)
        self.categories = CategoryDAO(db)

        self.var_search   = tk.StringVar()
        self.var_category = tk.StringVar(value="All")
        self._hovered_iid: str | None = None
        self._iid_tags: dict[str, str] = {}   # iid → original tag name

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
            bg="#3b5bfd", fg="white",
            activebackground="#2f4de0", activeforeground="white",
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
            search_pill, text="Search",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", ui_scale.scale_font(9)),
        ).grid(row=0, column=0, padx=(10, 4), pady=4)

        ent_search = tk.Entry(
            search_pill, textvariable=self.var_search,
            bd=0, bg=THEME["panel"], fg=THEME["text"],
            insertbackground=THEME["text"],
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

        cols = ("name", "category", "description", "price", "available", "action")
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
            ("name",        "Name",         ui_scale.s(180),  "w",      True),
            ("category",    "Category",     ui_scale.s(130),  "w",      False),
            ("description", "Description",  ui_scale.s(280),  "w",      True),
            ("price",       "Price",        ui_scale.s(95),   "e",      False),
            ("available",   "Status",       ui_scale.s(120),  "center", False),
            ("action",      "",             ui_scale.s(70),   "center", False),
        ]
        for cid, heading, width, anchor, stretch in col_cfg:
            self.tbl.heading(cid, text=heading)
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

        q   = (self.var_search.get() or "").strip().lower()
        cat = self.var_category.get()

        rows = self.products.list_all()
        for r in rows:
            name = str(r["name"])
            cat_name = str(r["category"])
            desc = str(r["description"] or "")

            # Filter by search text
            if q and q not in name.lower() and q not in cat_name.lower() and q not in desc.lower():
                continue
            # Filter by category
            if cat != "All" and cat_name != cat:
                continue

            pid    = int(r["product_id"])
            active = int(r["active"])

            tag          = "avail" if active else "unavail"
            status_text  = "● Available" if active else "● Unavailable"

            self.tbl.insert(
                "", tk.END,
                iid=str(pid),
                values=(
                    name, cat_name, desc,
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

    def create_product(self):
        ProductEditor(self, self.db, product_id=None, on_save=self.refresh)

    def edit_selected(self):
        pid = self._selected_id()
        if pid is None:
            return
        ProductEditor(self, self.db, product_id=pid, on_save=self.refresh)


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

        self._build()
        self._load()

    def _build(self):
        f   = ui_scale.scale_font
        sp  = ui_scale.s

        # ── Title (top) ───────────────────────────────────────────────────────
        tk.Label(
            self, text=self.title(),
            bg=THEME["bg"], fg=THEME["text"],
            font=("Segoe UI", f(14), "bold"),
        ).pack(anchor="w", padx=18, pady=(14, 6))

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
        tk.Label(
            box, text="(optional — auto-filled when you choose a file)",
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
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8), ipady=sp(8))

        # ── Description ───────────────────────────────────────────────────────
        tk.Label(
            box, text="Description",
            bg=THEME["panel"], fg=THEME["muted"],
            font=("Segoe UI", f(9)),
        ).grid(row=6, column=0, sticky="w", padx=14)
        self._desc_text = tk.Text(
            box, height=4, bd=0,
            bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", f(9)),
        )
        self._desc_text.grid(row=7, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 10))

        # ── Category row ──────────────────────────────────────────────────────
        cat_row = tk.Frame(box, bg=THEME["panel"])
        cat_row.grid(row=8, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
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
            cat_row, text="+",
            bg=THEME["panel2"], fg=THEME["text"],
            bd=0, width=3, cursor="hand2",
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
        cats  = self.categories.list_categories()
        names = [c["name"] for c in cats]
        self.cbo_cat["values"] = names
        if not self.var_category.get() and names:
            self.var_category.set(names[0])

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

        self._desc_text.delete("1.0", "end")
        self._desc_text.insert("1.0", r["description"] or "")

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
        abs_path = image_path if os.path.isabs(image_path) else os.path.join(os.getcwd(), image_path)
        if not os.path.exists(abs_path):
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

        img_dir = os.path.join(os.getcwd(), "product_images")
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
        name = simple_input(self, "New Category", "Category name:")
        if not name:
            return
        try:
            self.categories.create(name.strip())
        except Exception:
            pass
        self._refresh_categories()
        self.var_category.set(name.strip())

    def _save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("Name", "Product name is required.")
            return

        desc       = self._desc_text.get("1.0", "end").strip()
        image_path = self.var_image.get().strip()

        try:
            price = float(self.var_price.get().strip() or 0)
            stock = int(self.var_stock.get().strip() or 0)
            low   = int(self.var_low.get().strip() or 5)
        except Exception:
            messagebox.showerror("Invalid", "Price/stock/low must be numbers.")
            return

        cat_name = self.var_category.get().strip()
        cat      = self.categories.get_by_name(cat_name) if cat_name else None
        cat_id   = int(cat["category_id"]) if cat else None

        if self.product_id:
            self.products.update(
                self.product_id, cat_id, name, desc, "", image_path,
                price, stock, low, int(self.var_active.get()),
            )
        else:
            self.products.create(
                cat_id, name, desc, "", image_path,
                price, stock, low, int(self.var_active.get()),
            )

        if self.on_save:
            self.on_save()
        self.destroy()

    def _delete(self):
        if not self.product_id:
            return
        if not messagebox.askyesno("Delete", "Delete this product?"):
            return
        self.products.delete(self.product_id)
        if self.on_save:
            self.on_save()
        self.destroy()


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
                   font=("Segoe UI", ui_scale.scale_font(9)))
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
