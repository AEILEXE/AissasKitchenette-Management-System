from __future__ import annotations
from dataclasses import dataclass

@dataclass
class OrderItem:
    order_item_id: int
    order_id: int
    product_id: int
    qty: int
    unit_price: float
    note: str
