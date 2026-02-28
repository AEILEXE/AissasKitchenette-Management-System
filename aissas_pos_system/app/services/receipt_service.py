from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from app.utils import money

# Receipt output folder (created automatically)
_RECEIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "receipts"
_RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)


class ReceiptService:
    """Generates 80mm-style thermal receipt PDFs using reportlab."""

    @staticmethod
    def generate_receipt(order_data: dict[str, Any], items: list[dict[str, Any]]) -> str:
        """
        Build a PDF receipt and return its file path.
        Falls back to a plain-text file if reportlab is unavailable.
        """
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.units import mm
            from reportlab.lib.pagesizes import A4
        except ImportError:
            return ReceiptService._generate_text_receipt(order_data, items)

        order_id   = order_data.get("order_id", "—")
        start_dt   = str(order_data.get("start_dt", "—"))
        end_dt     = str(order_data.get("end_dt", ""))
        customer   = str(order_data.get("customer_name", "—"))
        payment    = str(order_data.get("payment_method", "—"))
        status     = str(order_data.get("status", "—"))
        reference  = str(order_data.get("reference_no", "") or "").strip()

        subtotal_v = float(order_data.get("subtotal") or 0.0)
        discount_v = float(order_data.get("discount") or 0.0)
        tax_v      = float(order_data.get("tax") or 0.0)
        total_v    = float(order_data.get("total") or 0.0)
        paid_v     = float(order_data.get("amount_paid") or 0.0)
        change_v   = float(order_data.get("change_due") or 0.0)

        # ── File path ─────────────────────────────────────────────────────────
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename   = f"receipt_{order_id}_{timestamp}.pdf"
        file_path  = str(_RECEIPTS_DIR / filename)

        # ── Page geometry (80 mm paper width, dynamic height) ─────────────────
        PAGE_W     = 80 * mm
        MARGIN     = 6 * mm
        COL_W      = PAGE_W - 2 * MARGIN

        # Estimate page height
        base_lines = 22 + len(items) * 2
        PAGE_H     = max(100 * mm, base_lines * 5.5 * mm + 20 * mm)

        c = rl_canvas.Canvas(file_path, pagesize=(PAGE_W, PAGE_H))

        # Cursor starts from the TOP of the page
        y = PAGE_H - 8 * mm

        def line_h(pts=10):
            return pts * 1.3

        def draw_text(text, x_offset=0, font="Helvetica", size=8,
                      align="left", bold=False):
            nonlocal y
            fname = "Helvetica-Bold" if bold else font
            c.setFont(fname, size)
            x = MARGIN + x_offset
            if align == "center":
                x = PAGE_W / 2
                c.drawCentredString(x, y, text)
            elif align == "right":
                x = PAGE_W - MARGIN
                c.drawRightString(x, y, text)
            else:
                c.drawString(x, y, text)
            y -= line_h(size)

        def draw_hr(thickness=0.5):
            nonlocal y
            c.setLineWidth(thickness)
            c.line(MARGIN, y, PAGE_W - MARGIN, y)
            y -= 4

        def draw_row(left: str, right: str, size=8, bold_right=False):
            nonlocal y
            c.setFont("Helvetica", size)
            c.drawString(MARGIN, y, left)
            c.setFont("Helvetica-Bold" if bold_right else "Helvetica", size)
            c.drawRightString(PAGE_W - MARGIN, y, right)
            y -= line_h(size)

        # ── Header ────────────────────────────────────────────────────────────
        y -= 2 * mm
        draw_text("AISSA'S KITCHENETTE", size=11, align="center", bold=True)
        draw_text("Official Receipt", size=8, align="center")
        y -= 2 * mm
        draw_hr(1.0)

        # ── Order info ────────────────────────────────────────────────────────
        draw_row("Order #:", str(order_id))
        draw_row("Date:", start_dt[:19] if len(start_dt) > 19 else start_dt)
        if end_dt and end_dt not in ("None", "—", ""):
            draw_row("Completed:", end_dt[:19] if len(end_dt) > 19 else end_dt)
        draw_row("Customer:", customer)
        draw_row("Payment:", payment)
        if payment == "Bank/E-Wallet" and reference:
            draw_row("Reference:", reference)
        draw_row("Status:", status)

        y -= 2 * mm
        draw_hr()

        # ── Items ─────────────────────────────────────────────────────────────
        draw_text("ITEMS", size=8, bold=True)
        y -= 1 * mm

        for item in items:
            qty      = item.get("qty", 0)
            name     = item.get("name") or f"#{item.get('product_id', '?')}"
            unit_p   = float(item.get("unit_price", 0.0))
            subtotal = float(item.get("subtotal", 0.0))

            # Product name line (wrap if needed)
            c.setFont("Helvetica", 8)
            c.drawString(MARGIN, y, name[:38])
            y -= line_h(8)

            # Qty × price  =  subtotal
            detail = f"  {qty} x {money(unit_p)}"
            draw_row(detail, money(subtotal), size=7)

        y -= 1 * mm
        draw_hr()

        # ── Totals ────────────────────────────────────────────────────────────
        if discount_v > 0:
            draw_row("Subtotal:", money(subtotal_v))
            draw_row("Discount:", f"-{money(discount_v)}")
        if tax_v > 0:
            draw_row("Tax:", money(tax_v))

        y -= 1 * mm
        # Green total strip (simulate with bold text)
        draw_row("TOTAL:", money(total_v), size=10, bold_right=True)

        y -= 1 * mm
        draw_hr()

        draw_row("Amount Paid:", money(paid_v))
        if payment == "Cash":
            draw_row("Change:", money(change_v))

        y -= 2 * mm
        draw_hr(1.0)

        # ── Footer ────────────────────────────────────────────────────────────
        draw_text(f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                  size=7, align="center")
        draw_text("Thank you for your order!", size=8, align="center", bold=True)
        y -= 2 * mm

        c.save()
        return file_path

    # Fallback: plain-text receipt (used if reportlab is missing)
    @staticmethod
    def _generate_text_receipt(order_data: dict[str, Any], items: list[dict[str, Any]]) -> str:
        import tempfile
        lines: list[str] = []

        lines.append("=" * 50)
        lines.append("AISSA'S KITCHENETTE")
        lines.append("=" * 50)
        lines.append("")

        order_id = order_data.get("order_id", "—")
        lines.append(f"Order ID: {order_id}")
        lines.append(f"Date:     {order_data.get('start_dt', '—')}")
        lines.append(f"Customer: {order_data.get('customer_name', '—')}")
        lines.append(f"Payment:  {order_data.get('payment_method', '—')}")
        lines.append(f"Status:   {order_data.get('status', '—')}")
        lines.append("")
        lines.append("-" * 50)
        lines.append("ITEMS")
        lines.append("-" * 50)

        for item in items:
            qty  = item.get("qty", 0)
            name = item.get("name") or f"#{item.get('product_id', '?')}"
            sub  = item.get("subtotal", 0.0)
            lines.append(f"{qty}x {name}")
            lines.append(f"   {money(sub)}")

        lines.append("-" * 50)

        discount_v = float(order_data.get("discount") or 0.0)
        subtotal_v = float(order_data.get("subtotal") or 0.0)
        total_v    = float(order_data.get("total") or 0.0)
        paid_v     = float(order_data.get("amount_paid") or 0.0)
        change_v   = float(order_data.get("change_due") or 0.0)

        if discount_v > 0:
            lines.append(f"Subtotal:   {money(subtotal_v)}")
            lines.append(f"Discount:  -{money(discount_v)}")
        lines.append(f"Total:      {money(total_v)}")
        lines.append(f"Paid:       {money(paid_v)}")
        if order_data.get("payment_method") == "Cash":
            lines.append(f"Change:     {money(change_v)}")

        lines.append("=" * 50)
        lines.append(f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8",
            suffix=".txt", prefix="receipt_", delete=False,
        ) as f:
            f.write("\n".join(lines))
            return f.name

    @staticmethod
    def open_file(file_path: str) -> bool:
        try:
            if os.name == "nt":
                os.startfile(file_path)  # type: ignore[attr-defined]
                return True
            elif os.name == "posix":
                try:
                    import platform
                    if platform.system() == "Darwin":
                        subprocess.run(["open", file_path], check=True)
                    else:
                        subprocess.run(["xdg-open", file_path], check=True)
                    return True
                except Exception:
                    return False
            return False
        except Exception:
            return False
