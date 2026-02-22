"""Receipt generation service for printing orders."""

from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime
from typing import Any

from app.utils import money


class ReceiptService:
    """Generate and open receipts."""

    @staticmethod
    def generate_receipt(order_data: dict[str, Any], items: list[dict[str, Any]]) -> str:
        """
        Generate a receipt as plain text.
        Returns path to generated file.
        """
        lines: list[str] = []
        
        # Header
        lines.append("=" * 50)
        lines.append("AISSA'S KITCHENETTE")
        lines.append("=" * 50)
        lines.append("")
        
        # Order info
        order_id = order_data.get("order_id", "—")
        lines.append(f"Order ID: {order_id}")
        
        start_dt = order_data.get("start_dt", "—")
        end_dt = order_data.get("end_dt", "—")
        lines.append(f"Start: {start_dt}")
        if end_dt and end_dt != "None":
            lines.append(f"End: {end_dt}")
        
        customer = order_data.get("customer_name", "—")
        lines.append(f"Customer: {customer}")
        
        payment = order_data.get("payment_method", "—")
        lines.append(f"Payment: {payment}")
        
        status = order_data.get("status", "—")
        lines.append(f"Status: {status}")
        
        reference = order_data.get("reference_no", "")
        if payment == "Bank/E-Wallet":
            ref_display = reference if reference and reference.strip() else "(not set)"
            lines.append(f"Reference: {ref_display}")
        
        lines.append("")
        lines.append("-" * 50)
        lines.append("ITEMS")
        lines.append("-" * 50)
        
        # Items
        for item in items:
            qty = item.get("qty", 0)
            name = item.get("name", f"#{item.get('product_id', '?')}")
            subtotal = item.get("subtotal", 0.0)
            lines.append(f"{qty}x {name}")
            lines.append(f"   {money(subtotal)}")
        
        lines.append("-" * 50)
        
        # Totals
        subtotal = order_data.get("subtotal", 0.0)
        discount = order_data.get("discount", 0.0)
        tax = order_data.get("tax", 0.0)
        total = order_data.get("total", 0.0)
        amount_paid = order_data.get("amount_paid", 0.0)
        change_due = order_data.get("change_due", 0.0)
        
        if discount > 0:
            lines.append(f"Subtotal:          {money(subtotal)}")
            lines.append(f"Discount:         -{money(discount)}")
        if tax > 0:
            lines.append(f"Tax:               {money(tax)}")
        
        lines.append(f"Total:            {money(total)}")
        lines.append(f"Amount Paid:      {money(amount_paid)}")
        
        if payment == "Cash":
            lines.append(f"Change:           {money(change_due)}")
        
        lines.append("=" * 50)
        lines.append(f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="receipt_", text=True)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write("\n".join(lines))
        except Exception:
            os.close(fd)
            raise
        
        return path

    @staticmethod
    def open_file(file_path: str) -> bool:
        """
        Open file with platform-specific command.
        Returns True if opened successfully, False otherwise.
        """
        try:
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
                return True
            elif os.name == 'posix':  # macOS / Linux
                if os.uname().sysname == 'Darwin':  # macOS
                    subprocess.run(["open", file_path], check=True)
                else:  # Linux
                    subprocess.run(["xdg-open", file_path], check=True)
                return True
            else:
                return False
        except Exception:
            return False
