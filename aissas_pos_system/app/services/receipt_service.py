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


def _receipt_money(value: Any) -> str:
    """
    Money formatter for PDF receipts.
    Uses 'PHP' prefix instead of '₱' to avoid black-square rendering
    when Helvetica (the default reportlab font) is used — Helvetica
    does not contain the Philippine Peso sign (U+20B1).
    """
    try:
        v = float(value)
    except Exception:
        v = 0.0
    return f"PHP {v:,.2f}"


def _try_register_unicode_font():
    """
    Attempt to register a Unicode-capable TTF font for reportlab.
    Returns (font_name_regular, font_name_bold) or (None, None) on failure.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Search common locations for DejaVuSans
        base = Path(__file__).resolve().parent.parent.parent
        candidates_reg = [
            base / "assets" / "fonts" / "DejaVuSans.ttf",
            Path(r"C:\Windows\Fonts\DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        ]
        candidates_bold = [
            base / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
            Path(r"C:\Windows\Fonts\DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        ]

        reg_path  = next((p for p in candidates_reg  if p.exists()), None)
        bold_path = next((p for p in candidates_bold if p.exists()), None)

        if reg_path:
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(reg_path)))
            if bold_path:
                pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold_path)))
                return "DejaVuSans", "DejaVuSans-Bold"
            return "DejaVuSans", "DejaVuSans"
    except Exception:
        pass
    return None, None


class ReceiptService:
    """Generates 80mm-style thermal receipt PDFs using reportlab."""

    @staticmethod
    def generate_receipt(order_data: dict[str, Any], items: list[dict[str, Any]]) -> str:
        """
        Build a PDF receipt and return its file path.
        Raises RuntimeError if reportlab is not installed.
        """
        try:
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.units import mm
        except ImportError:
            raise RuntimeError(
                "reportlab is not installed.\n\n"
                "Run:  pip install reportlab\n\n"
                "Then restart the application."
            )

        # Try Unicode font first (supports ₱), else use Helvetica + PHP prefix
        reg_font, bold_font = _try_register_unicode_font()
        if reg_font:
            FONT_REG  = reg_font
            FONT_BOLD = bold_font
            fmt_money = money          # ₱ renders correctly with DejaVuSans
        else:
            FONT_REG  = "Helvetica"
            FONT_BOLD = "Helvetica-Bold"
            fmt_money = _receipt_money  # PHP prefix avoids black squares

        order_id  = order_data.get("order_id", "—")
        start_dt  = str(order_data.get("start_dt", "—"))
        end_dt    = str(order_data.get("end_dt", ""))
        customer  = str(order_data.get("customer_name", "—"))
        cashier   = str(order_data.get("cashier_username", "") or "Unknown").strip() or "Unknown"
        payment   = str(order_data.get("payment_method", "—"))
        status    = str(order_data.get("status", "—"))
        reference = str(order_data.get("reference_no", "") or "").strip()

        subtotal_v = float(order_data.get("subtotal") or 0.0)
        discount_v = float(order_data.get("discount") or 0.0)
        tax_v      = float(order_data.get("tax")      or 0.0)
        total_v    = float(order_data.get("total")    or 0.0)
        paid_v     = float(order_data.get("amount_paid") or 0.0)
        change_v   = float(order_data.get("change_due")  or 0.0)

        # ── File path ─────────────────────────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"receipt_{order_id}_{timestamp}.pdf"
        file_path = str(_RECEIPTS_DIR / filename)

        # ── Page geometry (80 mm paper width, dynamic height) ─────────────────
        PAGE_W = 80 * mm
        MARGIN = 6 * mm

        # Height: base overhead + per-item lines + extra for 5 dividers with 6 mm gap.
        # Adding ~40 mm buffer so long product names and discounts never get clipped.
        base_lines = 32 + len(items) * 4
        PAGE_H     = max(180 * mm, base_lines * 6.5 * mm + 60 * mm)

        c = rl_canvas.Canvas(file_path, pagesize=(PAGE_W, PAGE_H))
        y = PAGE_H - 10 * mm   # cursor starts near top

        NL  = 5.2 * mm   # normal line height
        SNL = 4.4 * mm   # small line height

        def move(mm_val: float = 1.5):
            nonlocal y
            y -= mm_val * mm

        def draw_text(text: str, font=FONT_REG, size: int = 8,
                      align: str = "left", x_off: float = 0):
            nonlocal y
            c.setFont(font, size)
            lh = NL if size >= 8 else SNL
            if align == "center":
                c.drawCentredString(PAGE_W / 2, y, str(text))
            elif align == "right":
                c.drawRightString(PAGE_W - MARGIN, y, str(text))
            else:
                # Clip to printable width
                avail = int((PAGE_W - 2 * MARGIN - x_off * mm) / (size * 0.52))
                t = str(text)
                if len(t) > avail:
                    t = t[:avail - 1] + "…"
                c.drawString(MARGIN + x_off * mm, y, t)
            y -= lh

        def draw_hr(thickness: float = 0.4, gap_after: float = 1.5):
            nonlocal y
            c.setLineWidth(thickness)
            c.line(MARGIN, y, PAGE_W - MARGIN, y)
            y -= gap_after * mm

        def draw_row(left: str, right: str, size: int = 8,
                     bold_right: bool = False, bold_left: bool = False):
            nonlocal y
            lh = NL if size >= 8 else SNL
            c.setFont(FONT_BOLD if bold_left  else FONT_REG, size)
            avail_l = int((PAGE_W - 2 * MARGIN) * 0.55 / (size * 0.52))
            left = left[:avail_l - 1] + "…" if len(left) > avail_l else left
            c.drawString(MARGIN, y, left)
            c.setFont(FONT_BOLD if bold_right else FONT_REG, size)
            c.drawRightString(PAGE_W - MARGIN, y, str(right))
            y -= lh

        # ── Header ────────────────────────────────────────────────────────────
        move(0.5)
        draw_text("AISSA'S KITCHENETTE", font=FONT_BOLD, size=11, align="center")
        draw_text("Official Receipt",     size=8,         align="center")
        move(3)
        # gap_after=6 keeps the next text baseline 6 mm below the line;
        # 8-pt ascenders are ~2 mm, giving 4 mm clearance — clearly separated.
        draw_hr(1.0, 6.0)

        # ── Order metadata ────────────────────────────────────────────────────
        draw_row("Order #:", str(order_id))
        draw_row("Date:", start_dt[:19] if len(start_dt) > 19 else start_dt)
        if end_dt and end_dt not in ("None", "—", ""):
            draw_row("Completed:", end_dt[:19] if len(end_dt) > 19 else end_dt)
        draw_row("Customer:", customer)
        draw_row("Cashier:", cashier)
        draw_row("Payment:", payment)
        if payment == "Bank/E-Wallet" and reference:
            draw_row("Reference:", reference)
        draw_row("Status:", status)

        move(3)
        draw_hr(0.4, 6.0)

        # ── Items ─────────────────────────────────────────────────────────────
        draw_text("ITEMS", font=FONT_BOLD, size=8)
        move(1)

        for item in items:
            qty    = item.get("qty", 0)
            name   = item.get("name") or f"#{item.get('product_id', '?')}"
            unit_p = float(item.get("unit_price", 0.0))
            sub    = float(item.get("subtotal",   0.0))

            draw_text(name, size=8)
            draw_row(f"  {qty} x {fmt_money(unit_p)}", fmt_money(sub), size=7)
            move(0.5)   # small breath between items

        move(2)
        draw_hr(0.4, 6.0)

        # ── Totals ────────────────────────────────────────────────────────────
        if discount_v > 0:
            draw_row("Subtotal:", fmt_money(subtotal_v))
            draw_row("Discount:", f"-{fmt_money(discount_v)}")
        if tax_v > 0:
            draw_row("Tax:", fmt_money(tax_v))

        move(1)
        draw_row("TOTAL:", fmt_money(total_v), size=10,
                 bold_right=True, bold_left=True)
        move(3)
        draw_hr(0.4, 6.0)

        draw_row("Amount Paid:", fmt_money(paid_v))
        if payment == "Cash":
            draw_row("Change:", fmt_money(change_v))

        move(4)
        draw_hr(1.0, 6.0)

        # ── Footer ────────────────────────────────────────────────────────────
        draw_text(f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                  size=7, align="center")
        draw_text("Thank you for your order!", font=FONT_BOLD, size=8, align="center")
        move(4)

        c.save()
        return file_path

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
