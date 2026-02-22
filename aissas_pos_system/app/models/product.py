from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Product:
    product_id: int
    name: str
    category_id: int
    price: float
    stock_qty: int
    low_stock: int
    active: bool
