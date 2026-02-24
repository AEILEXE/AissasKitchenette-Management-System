from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime
from typing import Any

from app.utils import money


class ReceiptService:
    @staticmethod
    def generate_receipt(order_data: dict[str, Any], items: list[dict[str, Any]]) -> str:
        lines: list[str] = []

        lines.append("=" * 50)
        lines.append("AISSA'S KITCHENETTE")
        lines.append("=" * 50)
        lines.append("")

        order_id = order_data.get("order_id", "—")
        lines.append(f"Order ID: {order_id}")

        start_dt = order_data.get("start_dt", "—")
        end_dt = order_data.get("end_dt", "—")
        lines.append(f"Start: {start_dt}")
        if end_dt and str(end_dt) != "None":
            lines.append(f"End: {end_dt}")

        customer = order_data.get("customer_name", "—")
        lines.append(f"Customer: {customer}")

        payment = order_data.get("payment_method", "—")
        lines.append(f"Payment: {payment}")

        status = order_data.get("status", "—")
        lines.append(f"Status: {status}")

        reference = order_data.get("reference_no", "")
        if payment == "Bank/E-Wallet":
            ref_display = reference if reference and str(reference).strip() else "(not set)"
            lines.append(f"Reference: {ref_display}")

        lines.append("")
        lines.append("-" * 50)
        lines.append("ITEMS")
        lines.append("-" * 50)

        for item in items:
            qty = item.get("qty", 0)
            name = item.get("name") or f"#{item.get('product_id', '?')}"
            subtotal = item.get("subtotal", 0.0)
            lines.append(f"{qty}x {name}")
            lines.append(f"   {money(subtotal)}")

        lines.append("-" * 50)

        subtotal_v = float(order_data.get("subtotal") or 0.0)
        discount_v = float(order_data.get("discount") or 0.0)
        tax_v = float(order_data.get("tax") or 0.0)
        total_v = float(order_data.get("total") or 0.0)
        paid_v = float(order_data.get("amount_paid") or 0.0)
        change_v = float(order_data.get("change_due") or 0.0)

        if discount_v > 0:
            lines.append(f"Subtotal:          {money(subtotal_v)}")
            lines.append(f"Discount:         -{money(discount_v)}")
        if tax_v > 0:
            lines.append(f"Tax:               {money(tax_v)}")

        lines.append(f"Total:            {money(total_v)}")
        lines.append(f"Amount Paid:      {money(paid_v)}")
        if payment == "Cash":
            lines.append(f"Change:           {money(change_v)}")

        lines.append("=" * 50)
        lines.append(f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # SAFEST: NamedTemporaryFile with delete=False (no bad fd)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            prefix="receipt_",
            delete=False
        ) as f:
            f.write("\n".join(lines))
            return f.name

    @staticmethod
    def open_file(file_path: str) -> bool:
        try:
            if os.name == "nt":
                os.startfile(file_path)
                return True
            elif os.name == "posix":
                if os.uname().sysname == "Darwin":
                    subprocess.run(["open", file_path], check=True)
                else:
                    subprocess.run(["xdg-open", file_path], check=True)
                return True
            return False
        except Exception:
            return False