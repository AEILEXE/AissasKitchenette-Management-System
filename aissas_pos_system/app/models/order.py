from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Order:
    order_id: int
    datetime: str
    cashier_id: int
    subtotal: float
    discount: float
    tax: float
    total: float
    payment_method: str
    cash_received: float
    change_due: float
