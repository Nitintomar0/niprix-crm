from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle


NAVY = colors.HexColor("#0B1F3A")
BLUE = colors.HexColor("#0869D8")
MUTED = colors.HexColor("#60708A")
GRID = colors.HexColor("#DCE4EE")


class PageNumberCanvas(canvas.Canvas):
    """Adds a final page count after ReportLab has laid out every table page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.setFont("Helvetica", 8)
            self.setFillColor(MUTED)
            self.drawRightString(landscape(A4)[0] - 18 * mm, 12 * mm, f"Page {self._pageNumber} of {page_count}")
            super().showPage()
        super().save()


def _page_chrome(pdf, document):
    width, height = landscape(A4)
    pdf.saveState()
    pdf.setFillColor(NAVY)
    pdf.rect(0, height - 16 * mm, width, 16 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(document.leftMargin, height - 10 * mm, "NIPRIX")
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - document.rightMargin, height - 10 * mm, "Inventory Report")
    pdf.restoreState()


def _text(value) -> str:
    return escape(str(value).strip()) if value not in (None, "") else "—"


def _currency(value) -> str:
    return "—" if value is None else f"INR {value:,.2f}"


def _date(value) -> str:
    return value.strftime("%d %b %Y") if value else "—"


def build_inventory_pdf(records) -> bytes:
    """Create a complete A4-landscape inventory report from a tenant-scoped queryset."""

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=24 * mm,
        bottomMargin=18 * mm,
        title="NIPRIX Inventory Report",
        author="NIPRIX CRM",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InventoryTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=NAVY,
        spaceAfter=3 * mm,
    )
    metadata_style = ParagraphStyle(
        "InventoryMetadata",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=MUTED,
    )
    cell_style = ParagraphStyle(
        "InventoryCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.4,
        textColor=NAVY,
    )
    number_style = ParagraphStyle(
        "InventoryNumber",
        parent=cell_style,
        alignment=TA_RIGHT,
    )
    header_style = ParagraphStyle(
        "InventoryHeader",
        parent=cell_style,
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8,
        textColor=colors.white,
    )
    generated_at = timezone.localtime(timezone.now()).strftime("%d %b %Y, %H:%M %Z")
    story = [
        Paragraph("Inventory Report", title_style),
        Paragraph(f"Generated {generated_at} · Complete authorized inventory", metadata_style),
        Spacer(1, 5 * mm),
    ]

    headers = [
        "Project",
        "Unit / Flat No.",
        "Property Type",
        "Size (sq. ft.)",
        "Floor",
        "Basic Price",
        "Status",
        "Landing / Cost Price",
        "Booking Date",
    ]
    data = [[Paragraph(escape(header), header_style) for header in headers]]
    record_count = 0
    for project, unit_number, property_type, size_sqft, floor, basic_price, status, landing, booking_date in records.iterator(chunk_size=500):
        record_count += 1
        data.append([
            Paragraph(_text(project), cell_style),
            Paragraph(_text(unit_number), cell_style),
            Paragraph(_text(property_type), cell_style),
            Paragraph(_text(size_sqft), number_style),
            Paragraph(_text(floor), cell_style),
            Paragraph(_currency(basic_price), number_style),
            Paragraph(_text(status.replace("_", " ").title()), cell_style),
            Paragraph(_currency(landing), number_style),
            Paragraph(_date(booking_date), cell_style),
        ])

    if not record_count:
        empty_style = ParagraphStyle(
            "InventoryEmpty",
            parent=styles["Normal"],
            alignment=1,
            fontName="Helvetica",
            fontSize=11,
            textColor=MUTED,
        )
        story.append(Spacer(1, 30 * mm))
        story.append(Paragraph("No inventory records are available for this company.", empty_style))
    else:
        table = LongTable(
            data,
            colWidths=[31 * mm, 21 * mm, 23 * mm, 16 * mm, 15 * mm, 25 * mm, 20 * mm, 28 * mm, 20 * mm],
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.35, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFD")]),
            ("LINEABOVE", (0, 1), (-1, 1), 0.8, BLUE),
        ]))
        story.append(table)

    document.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome, canvasmaker=PageNumberCanvas)
    return buffer.getvalue()
