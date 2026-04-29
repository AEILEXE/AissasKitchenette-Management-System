"""
inventory_raw_materials_view.py
Raw Materials Inventory + Product Recipe (product_materials) management.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional

from app.config import THEME
from app.db.database import Database
from app.services.auth_service import AuthService


def _safe(row, key, default=None):
    try:
        v = row[key]
        return default if v is None else v
    except Exception:
        return default


class _MaterialDialog(tk.Toplevel):
    """Modal dialog for adding or editing a raw material."""

    def __init__(self, parent, db: Database = None, material: Optional[dict] = None):
        super().__init__(parent)
        self.db = db
        self.material = material
        self.result: Optional[dict] = None

        self.title("Edit Material" if material else "Add Raw Material")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.grab_set()

        pad = 14
        for row_i, (lbl_txt, attr, default) in enumerate([
            ("Name:", "var_name", _safe(material, "name", "")),
            ("Unit:", "var_unit", _safe(material, "unit", "pcs")),
            ("Quantity:", "var_qty", str(_safe(material, "quantity", 0))),
            ("Low Stock Alert:", "var_low", str(_safe(material, "low_stock", 5))),
        ]):
            tk.Label(self, text=lbl_txt, bg=THEME["bg"], fg=THEME["text"],
                     font=("Segoe UI", 10)).grid(row=row_i, column=0, sticky="w",
                                                  padx=pad, pady=(pad if row_i == 0 else 4, 4))
            sv = tk.StringVar(value=default)
            setattr(self, attr, sv)
            tk.Entry(self, textvariable=sv, width=28,
                     font=("Segoe UI", 10)).grid(row=row_i, column=1, padx=pad,
                                                  pady=(pad if row_i == 0 else 4, 4))

        tk.Label(self, text="Type:", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=4, column=0, sticky="w", padx=pad, pady=4)
        self.var_type = tk.StringVar(value=_safe(material, "material_type", "DRY"))
        frm_type = tk.Frame(self, bg=THEME["bg"])
        frm_type.grid(row=4, column=1, sticky="w", padx=pad, pady=4)
        for val, lbl in (("DRY", "Dry"), ("WET", "Wet")):
            tk.Radiobutton(frm_type, text=lbl, variable=self.var_type, value=val,
                           bg=THEME["bg"], fg=THEME["text"], selectcolor=THEME["bg"],
                           font=("Segoe UI", 10)).pack(side="left", padx=6)

        self.var_active = tk.BooleanVar(value=bool(_safe(material, "active", 1)))
        tk.Checkbutton(self, text="Active", variable=self.var_active,
                       bg=THEME["bg"], fg=THEME["text"], selectcolor=THEME["bg"],
                       font=("Segoe UI", 10)).grid(row=5, column=1, sticky="w", padx=pad, pady=4)

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.grid(row=6, column=0, columnspan=2, pady=(8, pad))
        tk.Button(btn_row, text="Save", command=self._save,
                  bg=THEME["primary"], fg="white", padx=16, pady=6,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=THEME["border"], fg=THEME["text"], padx=16, pady=6,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10)).pack(side="left", padx=6)

        self.transient(parent)
        self.wait_window()

    def _save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("Validation", "Name is required.", parent=self)
            return
        try:
            qty = float(self.var_qty.get())
            low = float(self.var_low.get())
        except ValueError:
            messagebox.showerror("Validation", "Quantity and Low Stock must be numbers.", parent=self)
            return
        self.result = {
            "name": name,
            "material_type": self.var_type.get(),
            "unit": self.var_unit.get().strip() or "pcs",
            "quantity": qty,
            "low_stock": low,
            "active": 1 if self.var_active.get() else 0,
        }
        self.destroy()


class _LinkMaterialDialog(tk.Toplevel):
    """Add or edit a product_materials link."""

    def __init__(self, parent, db: Database, product_id: int, product_name: str,
                 existing_link: Optional[dict] = None):
        super().__init__(parent)
        self.db = db
        self.product_id = product_id
        self.existing_link = existing_link
        self.result: Optional[dict] = None

        self.title(f"{'Edit' if existing_link else 'Link'} Material → {product_name}")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.grab_set()

        pad = 14
        if not existing_link:
            tk.Label(self, text="Material:", bg=THEME["bg"], fg=THEME["text"],
                     font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=pad, pady=(pad, 4))
            rows = db.fetchall("SELECT id, name, unit FROM raw_materials WHERE active=1 ORDER BY name;", ())
            self._mats = {f"{r['name']} ({r['unit']})": r['id'] for r in rows}
            self.var_mat = tk.StringVar()
            cb = ttk.Combobox(self, textvariable=self.var_mat,
                              values=list(self._mats.keys()), state="readonly", width=28)
            cb.grid(row=0, column=1, padx=pad, pady=(pad, 4))
            if self._mats:
                cb.current(0)
        else:
            tk.Label(self,
                     text=f"Material: {existing_link.get('mat_name','')} ({existing_link.get('unit','')})",
                     bg=THEME["bg"], fg=THEME["text"],
                     font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=2,
                                                  sticky="w", padx=pad, pady=(pad, 4))

        tk.Label(self, text="Qty Per Order:", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", padx=pad, pady=4)
        self.var_qty = tk.StringVar(value=str(_safe(existing_link, "quantity_used", 1)))
        tk.Entry(self, textvariable=self.var_qty, width=14,
                 font=("Segoe UI", 10)).grid(row=1, column=1, sticky="w", padx=pad, pady=4)

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.grid(row=2, column=0, columnspan=2, pady=(8, pad))
        tk.Button(btn_row, text="Save", command=self._save,
                  bg=THEME["primary"], fg="white", padx=16, pady=6,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=THEME["border"], fg=THEME["text"], padx=16, pady=6,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10)).pack(side="left", padx=6)

        self.transient(parent)
        self.wait_window()

    def _save(self):
        try:
            qty = float(self.var_qty.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation", "Qty must be a positive number.", parent=self)
            return
        if self.existing_link:
            mat_id = self.existing_link["material_id"]
        else:
            sel = self.var_mat.get()
            if not sel or sel not in self._mats:
                messagebox.showerror("Validation", "Select a material.", parent=self)
                return
            mat_id = self._mats[sel]
        self.result = {"material_id": mat_id, "quantity_used": qty}
        self.destroy()


class InventoryRawMaterialsView(tk.Frame):
    LOW_STOCK_BG = "#fff3cd"
    LOW_STOCK_FG = "#856404"

    def __init__(self, parent, db: Database, auth: AuthService):
        super().__init__(parent, bg=THEME["bg"])
        self.db = db
        self.auth = auth
        self._filter = "ALL"
        self._status_filter = "Active"
        self._sel_product_id: Optional[int] = None
        self._sel_product_name: str = ""

        self._build_ui()
        self.refresh_materials()

    def _build_ui(self):
        top = tk.Frame(self, bg=THEME["bg"])
        top.pack(fill="x", padx=16, pady=(14, 0))

        tk.Label(top, text="Raw Materials", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 16, "bold")).pack(side="left")

        filter_frame = tk.Frame(top, bg=THEME["bg"])
        filter_frame.pack(side="left", padx=20)
        self._filter_btns: dict[str, tk.Button] = {}
        for key, lbl in (("ALL", "All Types"), ("DRY", "Dry"), ("WET", "Wet")):
            btn = tk.Button(filter_frame, text=lbl,
                            command=lambda k=key: self._set_filter(k),
                            bg=THEME["primary"] if key == self._filter else THEME["border"],
                            fg="white" if key == self._filter else THEME["text"],
                            padx=14, pady=5, relief="flat", cursor="hand2",
                            font=("Segoe UI", 9))
            btn.pack(side="left", padx=3)
            self._filter_btns[key] = btn

        status_row = tk.Frame(self, bg=THEME["bg"])
        status_row.pack(fill="x", padx=16, pady=(6, 0))
        tk.Label(status_row, text="Show:", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._status_btns: dict[str, tk.Button] = {}
        for key in ("Active", "Inactive", "All"):
            btn = tk.Button(status_row, text=key,
                            command=lambda k=key: self._set_status_filter(k),
                            bg=THEME["primary"] if key == self._status_filter else THEME["border"],
                            fg="white" if key == self._status_filter else THEME["text"],
                            padx=12, pady=4, relief="flat", cursor="hand2",
                            font=("Segoe UI", 9))
            btn.pack(side="left", padx=3)
            self._status_btns[key] = btn

        btn_row = tk.Frame(self, bg=THEME["bg"])
        btn_row.pack(fill="x", padx=16, pady=(8, 4))
        for txt, cmd in [
            ("Add Material",  self._add_material),
            ("Edit Selected", self._edit_material),
            ("Adjust Stock",  self._adjust_stock),
            ("Refresh",       self.refresh_materials),
        ]:
            tk.Button(btn_row, text=txt, command=cmd,
                      bg=THEME["primary"], fg="white", padx=12, pady=5,
                      relief="flat", cursor="hand2",
                      font=("Segoe UI", 9)).pack(side="left", padx=3)

        self._toggle_btn = tk.Button(btn_row, text="Deactivate",
                                     command=self._toggle_active_material,
                                     bg=THEME["primary"], fg="white", padx=12, pady=5,
                                     relief="flat", cursor="hand2",
                                     font=("Segoe UI", 9))
        self._toggle_btn.pack(side="left", padx=3)

        tree_frame = tk.Frame(self, bg=THEME["bg"])
        tree_frame.pack(fill="both", expand=True, padx=16, pady=(0, 2))

        cols = ("name", "type", "unit", "quantity", "low_stock", "status")
        hdrs = ("Name", "Type", "Unit", "Quantity", "Low Stock Alert", "Status")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
        for col, hdr, w in zip(cols, hdrs, (180, 70, 70, 100, 120, 80)):
            self.tree.heading(col, text=hdr)
            self.tree.column(col, width=w, minwidth=50)
        sb_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")
        self.tree.tag_configure("low", background=self.LOW_STOCK_BG, foreground=self.LOW_STOCK_FG)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        legend = tk.Frame(self, bg=THEME["bg"])
        legend.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(legend, text=" ⚠ Low stock ", bg=self.LOW_STOCK_BG,
                 fg=self.LOW_STOCK_FG, font=("Segoe UI", 9), padx=4).pack(side="left")

        tk.Frame(self, bg="#cccccc", height=1).pack(fill="x", padx=16, pady=6)

        tk.Label(self, text="Product Recipe / Materials Used",
                 bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(0, 4))

        prod_row = tk.Frame(self, bg=THEME["bg"])
        prod_row.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(prod_row, text="Product:", bg=THEME["bg"], fg=THEME["text"],
                 font=("Segoe UI", 10)).pack(side="left")

        prods = self.db.fetchall(
            "SELECT id, name FROM products WHERE active=1 ORDER BY name;", ()
        )
        self._product_map = {r["name"]: r["id"] for r in prods}
        self.var_product = tk.StringVar()
        self._prod_cb = ttk.Combobox(prod_row, textvariable=self.var_product,
                                     values=list(self._product_map.keys()),
                                     state="readonly", width=30)
        self._prod_cb.pack(side="left", padx=8)
        self._prod_cb.bind("<<ComboboxSelected>>", self._on_product_selected)

        rec_btns = tk.Frame(self, bg=THEME["bg"])
        rec_btns.pack(fill="x", padx=16, pady=(0, 4))
        for txt, cmd in [
            ("Link Material", self._link_material),
            ("Edit Link",     self._edit_link),
            ("Remove Link",   self._remove_link),
        ]:
            tk.Button(rec_btns, text=txt, command=cmd,
                      bg=THEME["primary"], fg="white", padx=12, pady=5,
                      relief="flat", cursor="hand2",
                      font=("Segoe UI", 9)).pack(side="left", padx=3)

        rec_frame = tk.Frame(self, bg=THEME["bg"])
        rec_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        rec_cols = ("mat_name", "mat_type", "unit", "qty_used")
        rec_hdrs = ("Material", "Type", "Unit", "Qty Per Order")
        self.rec_tree = ttk.Treeview(rec_frame, columns=rec_cols, show="headings", height=7)
        for col, hdr, w in zip(rec_cols, rec_hdrs, (200, 80, 80, 120)):
            self.rec_tree.heading(col, text=hdr)
            self.rec_tree.column(col, width=w, minwidth=50)
        rec_sb = ttk.Scrollbar(rec_frame, orient="vertical", command=self.rec_tree.yview)
        self.rec_tree.configure(yscrollcommand=rec_sb.set)
        self.rec_tree.pack(side="left", fill="both", expand=True)
        rec_sb.pack(side="right", fill="y")

    # ── Filter ────────────────────────────────────────────────────────────────

    def _set_filter(self, key: str):
        self._filter = key
        for k, btn in self._filter_btns.items():
            btn.configure(
                bg=THEME["primary"] if k == key else THEME["border"],
                fg="white" if k == key else THEME["text"],
            )
        self.refresh_materials()

    def _set_status_filter(self, key: str):
        self._status_filter = key
        for k, btn in self._status_btns.items():
            btn.configure(
                bg=THEME["primary"] if k == key else THEME["border"],
                fg="white" if k == key else THEME["text"],
            )
        self.refresh_materials()

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self._toggle_btn.configure(text="Deactivate")
            return
        try:
            mid = int(sel[0])
            mat = self._get_material(mid)
            if mat is None:
                self._toggle_btn.configure(text="Deactivate")
                return
            cur_active = int(_safe(mat, "active", 1))
            self._toggle_btn.configure(text="Deactivate" if cur_active else "Activate")
        except Exception:
            self._toggle_btn.configure(text="Deactivate")

    # ── Materials CRUD ────────────────────────────────────────────────────────

    def refresh_materials(self):
        self.tree.delete(*self.tree.get_children())

        where_parts = []
        params: list = []

        if self._filter != "ALL":
            where_parts.append("material_type=?")
            params.append(self._filter)

        if self._status_filter == "Active":
            where_parts.append("active=1")
        elif self._status_filter == "Inactive":
            where_parts.append("active=0")

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        rows = self.db.fetchall(
            f"SELECT * FROM raw_materials {where_sql} ORDER BY material_type, name;",
            tuple(params)
        )
        for r in rows:
            qty  = float(_safe(r, "quantity", 0))
            low  = float(_safe(r, "low_stock", 0))
            status = "Active" if _safe(r, "active", 1) else "Inactive"
            tag  = ("low",) if qty <= low else ()
            self.tree.insert("", "end", iid=str(r["id"]), tags=tag, values=(
                _safe(r, "name", ""), _safe(r, "material_type", ""),
                _safe(r, "unit", ""), qty, low, status,
            ))
        self._toggle_btn.configure(text="Deactivate")

    def _selected_material_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a material first.")
            return None
        return int(sel[0])

    def _get_material(self, mid: int) -> Optional[dict]:
        row = self.db.fetchone("SELECT * FROM raw_materials WHERE id=?;", (mid,))
        return dict(row) if row else None

    def _add_material(self):
        dlg = _MaterialDialog(self, self.db)
        if dlg.result:
            r = dlg.result
            try:
                self.db.execute(
                    """INSERT INTO raw_materials(name, material_type, unit, quantity, low_stock, active)
                       VALUES(?,?,?,?,?,?);""",
                    (r["name"], r["material_type"], r["unit"],
                     r["quantity"], r["low_stock"], r["active"])
                )
                self.refresh_materials()
            except Exception as e:
                messagebox.showerror("Error", f"Could not add material:\n{e}")

    def _edit_material(self):
        mid = self._selected_material_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        dlg = _MaterialDialog(self, self.db, material=mat)
        if dlg.result:
            r = dlg.result
            try:
                self.db.execute(
                    """UPDATE raw_materials SET name=?, material_type=?, unit=?,
                       quantity=?, low_stock=?, active=? WHERE id=?;""",
                    (r["name"], r["material_type"], r["unit"],
                     r["quantity"], r["low_stock"], r["active"], mid)
                )
                self.refresh_materials()
            except Exception as e:
                messagebox.showerror("Error", f"Could not update material:\n{e}")

    def _adjust_stock(self):
        mid = self._selected_material_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        cur  = float(_safe(mat, "quantity", 0))
        unit = _safe(mat, "unit", "")
        val  = simpledialog.askfloat(
            "Adjust Stock",
            f"Current: {cur} {unit}\nEnter new quantity:",
            initialvalue=cur, minvalue=0, parent=self
        )
        if val is None:
            return
        try:
            self.db.execute("UPDATE raw_materials SET quantity=? WHERE id=?;", (float(val), mid))
            self.refresh_materials()
        except Exception as e:
            messagebox.showerror("Error", f"Could not adjust stock:\n{e}")

    def _toggle_active_material(self):
        mid = self._selected_material_id()
        if mid is None:
            return
        mat = self._get_material(mid)
        if not mat:
            return
        cur_active = int(_safe(mat, "active", 1))
        action = "Deactivate" if cur_active else "Activate"
        name = _safe(mat, "name", "")
        if not messagebox.askyesno(action, f"{action} '{name}'?"):
            return
        try:
            new_val = 0 if cur_active else 1
            self.db.execute("UPDATE raw_materials SET active=? WHERE id=?;",
                            (new_val, mid))
            self.refresh_materials()
        except Exception as e:
            messagebox.showerror("Error", f"Could not update material:\n{e}")

    # ── Product Recipe ─────────────────────────────────────────────────────────

    def _on_product_selected(self, _event=None):
        pname = self.var_product.get()
        self._sel_product_id = self._product_map.get(pname)
        self._sel_product_name = pname
        self._refresh_recipe()

    def _refresh_recipe(self):
        self.rec_tree.delete(*self.rec_tree.get_children())
        if not self._sel_product_id:
            return
        rows = self.db.fetchall(
            """SELECT pm.id, pm.material_id, rm.name AS mat_name,
                      rm.material_type, rm.unit, pm.quantity_used
               FROM product_materials pm
               JOIN raw_materials rm ON rm.id = pm.material_id
               WHERE pm.product_id=? ORDER BY rm.name;""",
            (self._sel_product_id,)
        )
        for r in rows:
            self.rec_tree.insert("", "end", iid=str(r["id"]), values=(
                r["mat_name"], r["material_type"], r["unit"], r["quantity_used"]
            ))

    def _selected_link_row(self) -> Optional[dict]:
        sel = self.rec_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a linked material row.")
            return None
        link_id = int(sel[0])
        row = self.db.fetchone(
            """SELECT pm.*, rm.name AS mat_name, rm.unit
               FROM product_materials pm
               JOIN raw_materials rm ON rm.id = pm.material_id
               WHERE pm.id=?;""",
            (link_id,)
        )
        return dict(row) if row else None

    def _link_material(self):
        if not self._sel_product_id:
            messagebox.showwarning("Product", "Select a product first.")
            return
        dlg = _LinkMaterialDialog(self, self.db,
                                  self._sel_product_id, self._sel_product_name)
        if dlg.result:
            try:
                self.db.execute(
                    """INSERT INTO product_materials(product_id, material_id, quantity_used)
                       VALUES(?,?,?)
                       ON CONFLICT(product_id, material_id)
                       DO UPDATE SET quantity_used=excluded.quantity_used;""",
                    (self._sel_product_id, dlg.result["material_id"], dlg.result["quantity_used"])
                )
                self._refresh_recipe()
            except Exception as e:
                messagebox.showerror("Error", f"Could not link material:\n{e}")

    def _edit_link(self):
        link = self._selected_link_row()
        if not link:
            return
        dlg = _LinkMaterialDialog(self, self.db,
                                  self._sel_product_id, self._sel_product_name,
                                  existing_link=link)
        if dlg.result:
            try:
                self.db.execute(
                    "UPDATE product_materials SET quantity_used=? WHERE id=?;",
                    (dlg.result["quantity_used"], link["id"])
                )
                self._refresh_recipe()
            except Exception as e:
                messagebox.showerror("Error", f"Could not update link:\n{e}")

    def _remove_link(self):
        link = self._selected_link_row()
        if not link:
            return
        if not messagebox.askyesno("Remove", f"Remove '{link['mat_name']}' from recipe?"):
            return
        try:
            self.db.execute("DELETE FROM product_materials WHERE id=?;", (link["id"],))
            self._refresh_recipe()
        except Exception as e:
            messagebox.showerror("Error", f"Could not remove link:\n{e}")
