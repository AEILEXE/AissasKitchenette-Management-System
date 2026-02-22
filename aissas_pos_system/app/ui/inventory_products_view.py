from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.config import THEME
from app.db.database import Database
from app.db.dao import ProductDAO, CategoryDAO
from app.services.auth_service import AuthService
from app.utils import money

# Try to import Pillow for JPG handling
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class InventoryProductsView(tk.Frame):
    def __init__(self, parent: tk.Frame, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self.products = ProductDAO(db)
        self.categories = CategoryDAO(db)

        self.var_search = tk.StringVar()

        self._build()
        self.refresh()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = tk.Frame(self, bg=THEME["bg"])
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        top.columnconfigure(1, weight=1)
        tk.Label(top, text="Products", bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w")

        tk.Button(
            top, text="Create Product",
            bg="#3b5bfd", fg="white", bd=0, padx=12, pady=8, cursor="hand2",
            command=self.create_product
        ).grid(row=0, column=2, sticky="e")

        search = tk.Entry(self, textvariable=self.var_search, bd=0, bg=THEME["panel2"], fg=THEME["text"])
        search.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10), ipady=8)
        search.bind("<KeyRelease>", lambda _e: self.refresh())

        wrap = tk.Frame(self, bg=THEME["bg"])
        wrap.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)

        # Removed "tags" column from table
        cols = ("name", "category", "description", "price", "available", "action")
        self.tbl = ttk.Treeview(wrap, columns=cols, show="headings")
        self.tbl.grid(row=0, column=0, sticky="nsew")

        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tbl.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        self.tbl.configure(yscrollcommand=ysb.set)

        for c, t in [
            ("name", "NAME"),
            ("category", "CATEGORY"),
            ("description", "DESCRIPTION"),
            ("price", "PRICE"),
            ("available", "AVAILABLE"),
            ("action", "ACTION"),
        ]:
            self.tbl.heading(c, text=t)

        self.tbl.column("name", width=160, anchor="w")
        self.tbl.column("category", width=120, anchor="w")
        self.tbl.column("description", width=260, anchor="w")
        self.tbl.column("price", width=90, anchor="e")
        self.tbl.column("available", width=100, anchor="center")
        self.tbl.column("action", width=70, anchor="center")

        self.tbl.bind("<Double-Button-1>", lambda _e: self.edit_selected())

    def refresh(self):
        for iid in self.tbl.get_children():
            self.tbl.delete(iid)

        q = (self.var_search.get() or "").strip().lower()
        rows = self.products.list_all()
        for r in rows:
            name = str(r["name"])
            cat = str(r["category"])
            desc = str(r["description"] or "")
            if q and (q not in name.lower() and q not in cat.lower() and q not in desc.lower()):
                continue

            pid = int(r["product_id"])
            active = int(r["active"])
            available_text = "Available" if active == 1 else "Not Available"

            self.tbl.insert(
                "",
                tk.END,
                iid=str(pid),
                values=(name, cat, desc, money(r["price"]), available_text, "Edit"),
            )

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


class ProductEditor(tk.Toplevel):
    def __init__(self, parent: tk.Widget, db: Database, product_id: int | None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.product_id = product_id
        self.on_save = on_save
        self.products = ProductDAO(db)
        self.categories = CategoryDAO(db)

        self.title("Edit Product" if product_id else "Create Product")
        self.configure(bg=THEME["bg"])
        self.geometry("700x540")
        self.transient(parent)
        self.grab_set()

        # fields
        self.var_name = tk.StringVar()
        self.var_desc = tk.StringVar()
        self.var_price = tk.StringVar(value="0")
        self.var_stock = tk.StringVar(value="0")
        self.var_low = tk.StringVar(value="5")
        self.var_active = tk.IntVar(value=1)
        self.var_image = tk.StringVar()

        self.var_category = tk.StringVar()

        self._build()
        self._load()

    def _build(self):
        tk.Label(self, text=self.title(), bg=THEME["bg"], fg=THEME["text"], font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=18, pady=(14, 10))

        box = tk.Frame(self, bg="#ffffff")
        box.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)

        # image path - with clear description
        tk.Label(box, text="Product Image Path", bg="#ffffff", fg=THEME["muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 2))
        tk.Label(box, text="(auto-filled after choosing image; optional)", bg="#ffffff", fg=THEME["muted"], font=("Segoe UI", 8)).grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 4))
        
        row_img = tk.Frame(box, bg="#ffffff")
        row_img.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14)
        row_img.columnconfigure(1, weight=1)

        tk.Button(row_img, text="Choose File", command=self._choose_file, bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=10, pady=6).grid(row=0, column=0)
        tk.Entry(row_img, textvariable=self.var_image, bd=0, bg=THEME["panel2"], fg=THEME["text"]).grid(row=0, column=1, sticky="ew", padx=(10, 0), ipady=6)

        # name
        tk.Label(box, text="Product Name", bg="#ffffff", fg=THEME["muted"]).grid(row=3, column=0, sticky="w", padx=14, pady=(12, 4))
        tk.Entry(box, textvariable=self.var_name, bd=0, bg=THEME["panel2"], fg=THEME["text"]).grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8), ipady=8)

        # description
        tk.Label(box, text="Description", bg="#ffffff", fg=THEME["muted"]).grid(row=5, column=0, sticky="w", padx=14)
        txt = tk.Text(box, height=5, bd=0, bg=THEME["panel2"], fg=THEME["text"])
        txt.grid(row=6, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 10))
        self._desc_text = txt

        # category row
        cat_row = tk.Frame(box, bg="#ffffff")
        cat_row.grid(row=7, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
        cat_row.columnconfigure(1, weight=1)

        tk.Label(cat_row, text="Category", bg="#ffffff", fg=THEME["muted"]).grid(row=0, column=0, sticky="w")
        self.cbo_cat = ttk.Combobox(cat_row, textvariable=self.var_category, state="readonly")
        self.cbo_cat.grid(row=0, column=1, sticky="ew", padx=(10, 10))

        tk.Button(cat_row, text="+", bg=THEME["panel2"], fg=THEME["text"], bd=0, width=3, command=self._add_category).grid(row=0, column=2)

        # price
        tk.Label(box, text="Price (₱)", bg="#ffffff", fg=THEME["muted"]).grid(row=8, column=0, sticky="w", padx=14)
        tk.Entry(box, textvariable=self.var_price, bd=0, bg=THEME["panel2"], fg=THEME["text"]).grid(row=8, column=1, sticky="ew", padx=14, pady=(0, 8), ipady=8)

        # available
        tk.Checkbutton(box, text="Available (uncheck to hide from POS)", variable=self.var_active, bg="#ffffff", fg=THEME["text"]).grid(row=9, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 14))

        footer = tk.Frame(self, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=(0, 14))

        tk.Button(footer, text="Close", bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, command=self.destroy).pack(side="right")
        tk.Button(footer, text="Save Product" if not self.product_id else "Update Product",
                  bg=THEME["success"], fg="white", bd=0, padx=12, pady=8, cursor="hand2",
                  command=self._save).pack(side="right", padx=(0, 10))

        if self.product_id:
            tk.Button(footer, text="Delete", bg=THEME["danger"], fg="white", bd=0, padx=12, pady=8, cursor="hand2",
                      command=self._delete).pack(side="left")

    def _refresh_categories(self):
        cats = self.categories.list_categories()
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
        self.var_image.set(r["image_path"] or "")
        self.var_price.set(str(r["price"]))
        self.var_stock.set(str(r["stock_qty"]))
        self.var_low.set(str(r["low_stock"]))
        self.var_active.set(int(r["active"]))
        self.var_category.set(r["category"] or "")

        self._desc_text.delete("1.0", "end")
        self._desc_text.insert("1.0", r["description"] or "")

    def _choose_file(self):
        path = filedialog.askopenfilename(
            title="Choose product image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif"), ("All files", "*.*")]
        )
        if not path:
            return
        
        # Ensure product_images directory exists
        img_dir = os.path.join(os.getcwd(), "product_images")
        os.makedirs(img_dir, exist_ok=True)
        
        # Get file extension
        _, ext = os.path.splitext(path)
        ext_lower = ext.lower()
        
        # Handle JPG conversion
        if ext_lower in [".jpg", ".jpeg"]:
            if not HAS_PIL:
                messagebox.showerror("Pillow Required", "JPG images require Pillow library.\nPlease install it: pip install Pillow")
                return
            try:
                # Open JPG and convert to PNG
                img = Image.open(path)
                # Convert RGBA if necessary
                if img.mode == "RGBA":
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                
                # Save as PNG in product_images folder
                filename = os.path.splitext(os.path.basename(path))[0] + ".png"
                dest_path = os.path.join(img_dir, filename)
                img.save(dest_path, "PNG")
                
                rel_path = os.path.join("product_images", filename)
                self.var_image.set(rel_path)
                messagebox.showinfo("Success", f"Image converted to PNG and saved.")
                return
            except Exception as e:
                messagebox.showerror("Error", f"Failed to convert JPG: {str(e)}")
                return
        
        # For other formats (PNG, GIF, etc.), copy directly
        filename = os.path.basename(path)
        dest_path = os.path.join(img_dir, filename)
        try:
            # If file already exists, rename it
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(img_dir, f"{base}_{counter}{ext}")):
                    counter += 1
                filename = f"{base}_{counter}{ext}"
                dest_path = os.path.join(img_dir, filename)
            
            shutil.copy2(path, dest_path)
            rel_path = os.path.join("product_images", filename)
            self.var_image.set(rel_path)
            messagebox.showinfo("Success", "Image saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy image: {str(e)}")

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

        desc = self._desc_text.get("1.0", "end").strip()
        image_path = self.var_image.get().strip()

        try:
            price = float(self.var_price.get().strip() or 0)
            stock = int(self.var_stock.get().strip() or 0)
            low = int(self.var_low.get().strip() or 5)
        except Exception:
            messagebox.showerror("Invalid", "Price/stock/low must be numbers.")
            return

        cat_name = self.var_category.get().strip()
        cat = self.categories.get_by_name(cat_name) if cat_name else None
        cat_id = int(cat["category_id"]) if cat else None

        if self.product_id:
            self.products.update(
                self.product_id, cat_id, name, desc, "", image_path,
                price, stock, low, int(self.var_active.get())
            )
        else:
            self.products.create(
                cat_id, name, desc, "", image_path,
                price, stock, low, int(self.var_active.get())
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


def simple_input(parent: tk.Widget, title: str, label: str) -> str | None:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=THEME["bg"])
    dlg.geometry("360x160")
    dlg.transient(parent)
    dlg.grab_set()

    var = tk.StringVar()

    tk.Label(dlg, text=label, bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=14, pady=(14, 6))
    ent = tk.Entry(dlg, textvariable=var, bd=0, bg=THEME["panel2"], fg=THEME["text"])
    ent.pack(fill="x", padx=14, ipady=8)
    ent.focus_set()

    out = {"v": None}

    def ok():
        out["v"] = var.get().strip()
        dlg.destroy()

    def cancel():
        dlg.destroy()

    btns = tk.Frame(dlg, bg=THEME["bg"])
    btns.pack(fill="x", padx=14, pady=14)
    tk.Button(btns, text="Cancel", bg=THEME["panel2"], fg=THEME["text"], bd=0, padx=12, pady=8, command=cancel).pack(side="right")
    tk.Button(btns, text="OK", bg=THEME["success"], fg="white", bd=0, padx=12, pady=8, command=ok).pack(side="right", padx=(0, 10))

    dlg.wait_window()
    return out["v"]