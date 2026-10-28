"""Fixed-size reproduction of the established Paramshiv payment receipt.

The layout deliberately uses ReportLab canvas coordinates rather than a generic
invoice/table template: every dynamic value sits in its historic field.
"""

from io import BytesIO
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


# The flattened receipt photograph is approximately 1.41:1. This is the
# finished landscape counterfoil size, not A4. Printing at 100% retains it.
PAGE_SIZE = (225 * mm, 160 * mm)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
PAPER = colors.HexColor("#f7f1dc")
INK = colors.HexColor("#202020")
BLUE = colors.HexColor("#15487d")
RED = colors.HexColor("#b22d33")
ASSET_ROOT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "brand"
PARAMSHIV_LOGO = ASSET_ROOT / "paramshiv-logo.png"
_UNICODE_FONT = None


def _unicode_font():
    """Use a configured Unicode font for ₹ / Hindi when the host provides one.

    Deployments should set PARAMSHIV_RECEIPT_UNICODE_FONT to the licensed,
    approved Devanagari TTF used by Paramshiv. macOS' Arial Unicode is used for
    development preview only; ReportLab cannot shape Indic text with Helvetica.
    """
    global _UNICODE_FONT
    if _UNICODE_FONT is not None:
        return _UNICODE_FONT
    candidates = [os.environ.get("PARAMSHIV_RECEIPT_UNICODE_FONT", ""), "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont("ParamshivUnicode", candidate))
            _UNICODE_FONT = "ParamshivUnicode"
            return _UNICODE_FONT
        except Exception:
            continue
    _UNICODE_FONT = "Helvetica"
    return _UNICODE_FONT


def _draw_rupee_mark(pdf, x, y, size):
    """Vector ₹ fallback keeps the original lower-left amount mark legible."""
    pdf.saveState()
    pdf.setLineWidth(size * .11)
    pdf.line(x, y + size * .84, x + size * .75, y + size * .84)
    pdf.line(x, y + size * .64, x + size * .75, y + size * .64)
    pdf.line(x + size * .12, y + size * .47, x + size * .7, y + size * .08)
    pdf.line(x + size * .36, y + size * .66, x + size * .36, y)
    pdf.restoreState()


def _fit_text(pdf, text, x, y, max_width, *, font="Helvetica", size=8.5, min_size=6.2):
    """Draw a non-wrapping field without spilling into adjacent historic text."""
    text = str(text or "-").replace("\n", " ").strip() or "-"
    fitted = size
    while fitted > min_size and pdf.stringWidth(text, font, fitted) > max_width:
        fitted -= 0.2
    if pdf.stringWidth(text, font, fitted) > max_width:
        suffix = "…"
        while text and pdf.stringWidth(text + suffix, font, fitted) > max_width:
            text = text[:-1]
        text += suffix
    pdf.setFont(font, fitted)
    pdf.drawString(x, y, text)


def _dotted_line(pdf, x1, x2, y):
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.55)
    pdf.setDash(1.25, 1.65)
    pdf.line(x1, y, x2, y)
    pdf.restoreState()


def _image(pdf, path, x, y, width, height):
    if not path.exists():
        return False
    image = ImageReader(str(path))
    iw, ih = image.getSize()
    scale = min(width / iw, height / ih)
    dw, dh = iw * scale, ih * scale
    pdf.drawImage(image, x + (width - dw) / 2, y + (height - dh) / 2, dw, dh, mask="auto", preserveAspectRatio=True)
    return True


def _rupees(value):
    return "{:,.2f}".format(value)


def build_receipt_pdf(receipt) -> bytes:
    """Render a receipt strictly from its immutable issuance snapshot."""
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=PAGE_SIZE, pageCompression=1)
    pdf.setTitle(f"Paramshiv Receipt {receipt.serial_number}")
    pdf.setAuthor("Paramshiv Urban Real Estate")
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    pdf.setFillColor(INK)
    snap = receipt.snapshot

    # Header: genuine Paramshiv artwork is retained; the surrounding typeset
    # wording is aligned to the original counterfoil instead of CRM branding.
    if not _image(pdf, PARAMSHIV_LOGO, 8 * mm, 132 * mm, 72 * mm, 20 * mm):
        pdf.setFont("Helvetica-Bold", 13)
        pdf.setFillColor(BLUE)
        pdf.drawString(10 * mm, 141 * mm, "PARAMSHIV")
        pdf.setFillColor(INK)
    pdf.setFillColor(BLUE)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawCentredString(PAGE_WIDTH / 2 + 15 * mm, 146 * mm, "PARAMSHIV URBAN REAL ESTATE")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 6.9)
    pdf.drawCentredString(PAGE_WIDTH / 2 + 15 * mm, 141.5 * mm, "Office No.: 1111, 11th Floor, Uttaria Mall, Ek Murti Chowk, Greater Noida West (U.P.)")
    pdf.drawCentredString(PAGE_WIDTH / 2 + 15 * mm, 138.2 * mm, "Email : paramshiv01@gmail.com  |  Mobile : +91 - 730312111")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(PAGE_WIDTH / 2, 131.1 * mm, "RECEIPT")
    pdf.setLineWidth(.6)
    pdf.line(PAGE_WIDTH / 2 - 10 * mm, 130 * mm, PAGE_WIDTH / 2 + 10 * mm, 130 * mm)

    # Original first three rows.
    pdf.setFont("Helvetica", 8.4)
    pdf.drawString(7 * mm, 120.5 * mm, "Sr. No.")
    _dotted_line(pdf, 21 * mm, 48 * mm, 121 * mm)
    _fit_text(pdf, receipt.serial_number, 25 * mm, 120.5 * mm, 20 * mm, font="Helvetica-Bold", size=9)
    pdf.drawString(169 * mm, 120.5 * mm, "Date")
    _dotted_line(pdf, 180 * mm, 217 * mm, 121 * mm)
    _fit_text(pdf, receipt.receipt_date.strftime("%d-%m-%Y"), 185 * mm, 120.5 * mm, 30 * mm, size=8.5)

    pdf.drawString(7 * mm, 112.5 * mm, "Received with thanks from Mr./Mrs./Ms.")
    _dotted_line(pdf, 61 * mm, 216 * mm, 113 * mm)
    _fit_text(pdf, snap.get("customer_name"), 64 * mm, 112.5 * mm, 149 * mm, size=9)

    pdf.drawString(7 * mm, 104.5 * mm, "Total Amount")
    _dotted_line(pdf, 29 * mm, 73 * mm, 105 * mm)
    _fit_text(pdf, _rupees(receipt.total_amount), 31 * mm, 104.5 * mm, 39 * mm, size=8.4)
    pdf.drawString(76 * mm, 104.5 * mm, "Receive Amount")
    _dotted_line(pdf, 103 * mm, 143 * mm, 105 * mm)
    _fit_text(pdf, _rupees(receipt.amount_received), 105 * mm, 104.5 * mm, 35 * mm, size=8.4)
    pdf.drawString(146 * mm, 104.5 * mm, "Balance Amount")
    _dotted_line(pdf, 174 * mm, 217 * mm, 105 * mm)
    _fit_text(pdf, _rupees(receipt.balance_amount), 176 * mm, 104.5 * mm, 38 * mm, size=8.4)

    pdf.drawString(7 * mm, 96.5 * mm, "Due Date")
    _dotted_line(pdf, 22 * mm, 72 * mm, 97 * mm)
    _fit_text(pdf, snap.get("due_date") or "-", 25 * mm, 96.5 * mm, 43 * mm, size=8)
    pdf.drawString(75 * mm, 96.5 * mm, "R/o Address")
    _dotted_line(pdf, 96 * mm, 216 * mm, 97 * mm)
    _fit_text(pdf, snap.get("residential_address"), 99 * mm, 96.5 * mm, 114 * mm, size=8)
    _dotted_line(pdf, 7 * mm, 216 * mm, 87.5 * mm)

    # Historic middle fields and payment reference row.
    pdf.drawString(7 * mm, 79.5 * mm, "Mob.")
    _dotted_line(pdf, 16 * mm, 69 * mm, 80 * mm)
    _fit_text(pdf, snap.get("mobile"), 19 * mm, 79.5 * mm, 46 * mm, size=8.2)
    pdf.drawString(72 * mm, 79.5 * mm, "Plot No.")
    _dotted_line(pdf, 88 * mm, 144 * mm, 80 * mm)
    _fit_text(pdf, snap.get("plot_number"), 91 * mm, 79.5 * mm, 48 * mm, size=8.2)
    pdf.drawString(147 * mm, 79.5 * mm, "Plot Size.")
    _dotted_line(pdf, 165 * mm, 217 * mm, 80 * mm)
    _fit_text(pdf, snap.get("plot_size"), 168 * mm, 79.5 * mm, 45 * mm, size=8.2)

    mode = {"CASH": "Cash", "CHEQUE": "Cheque", "DRAFT": "Draft", "TRANSFER": "Transfer", "UPI": "UPI"}.get(receipt.payment_method, receipt.payment_method)
    pdf.drawString(7 * mm, 69.5 * mm, f"By {mode} / Cheque / Draft No.")
    _dotted_line(pdf, 53 * mm, 112 * mm, 70 * mm)
    _fit_text(pdf, receipt.reference_number or "-", 55 * mm, 69.5 * mm, 53 * mm, size=8.2)
    pdf.drawString(115 * mm, 69.5 * mm, "Drawn on")
    _dotted_line(pdf, 134 * mm, 217 * mm, 70 * mm)
    _fit_text(pdf, receipt.drawn_on or "-", 137 * mm, 69.5 * mm, 76 * mm, size=8.2)

    # Lower-left amount box, original instruction locations, and signatory.
    pdf.setStrokeColor(INK)
    pdf.rect(7 * mm, 42 * mm, 57 * mm, 13 * mm, fill=0, stroke=1)
    pdf.setFillColor(INK)
    _draw_rupee_mark(pdf, 9.2 * mm, 45.3 * mm, 7 * mm)
    _fit_text(pdf, _rupees(receipt.amount_received), 19 * mm, 46.5 * mm, 42 * mm, font="Helvetica-Bold", size=10, min_size=7)
    pdf.setFont("Helvetica", 6.7)
    pdf.drawString(7 * mm, 37.3 * mm, "*Please bring this receipt at the time of registry")
    # ReportLab's standard fonts cannot shape Devanagari. The HTML print version
    # supplies browser shaping; this PDF preserves the exact Hindi wording for
    # Unicode-capable configured reportlab fonts.
    pdf.setFont(_unicode_font(), 6.1)
    pdf.drawString(7 * mm, 32.7 * mm, "प्लाट बुकिंग की तारीख से 15 दिन के अन्दर बुकिंग का पैसा वापिस किया जायेगा")
    pdf.drawString(7 * mm, 28.5 * mm, "अन्यथा हमारी कोई जिम्मेदारी नहीं होगी !")
    pdf.setFillColor(BLUE)
    pdf.setFont("Helvetica-Bold", 7.2)
    pdf.drawRightString(216 * mm, 54.5 * mm, "PARAMSHIV URBAN REAL ESTATE")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawRightString(216 * mm, 34.5 * mm, "Authorised Signatory")

    pdf.showPage()
    pdf.save()
    return output.getvalue()
