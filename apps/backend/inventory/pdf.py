"""Branded, print-ready inventory reports for authorized NIPRIX exports."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

NAVY = colors.HexColor("#222344")
LAVENDER = colors.HexColor("#CBB3E8")
SOFT_LAVENDER = colors.HexColor("#F8F5FC")
PEACH = colors.HexColor("#E8B8A5")
MINT = colors.HexColor("#A9E5D0")
INK = colors.HexColor("#303048")
MUTED = colors.HexColor("#6E6C82")
GRID = colors.HexColor("#DED9E8")

ASSET_ROOT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "brand"
NIPRIX_LOGO = ASSET_ROOT / "niprix-logo.png"
NIPRIX_MARK = ASSET_ROOT / "niprix-mark.png"
PARAMSHIV_LOGO = ASSET_ROOT / "paramshiv-logo.png"


def _text(value: object) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _currency(value: object) -> str:
    if value in (None, ""):
        return "-"
    try:
        amount = Decimal(str(value))
    except Exception:
        return _text(value)
    return "INR {:,.0f}".format(amount)


def _date(value: object) -> str:
    if not value:
        return "-"
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return _text(value)


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    # The data is application-owned but escaping keeps this renderer safe if a
    # project name happens to contain ReportLab markup characters.
    from xml.sax.saxutils import escape

    return Paragraph(escape(_text(value)), style)


def _draw_contained_image(pdf: canvas.Canvas, path: Path, x: float, y: float, width: float, height: float, *, mask: str | None = "auto") -> bool:
    """Draw an image without distortion; return False if a local asset is absent."""
    if not path.exists():
        return False
    image = ImageReader(str(path))
    image_width, image_height = image.getSize()
    scale = min(width / image_width, height / image_height)
    draw_width, draw_height = image_width * scale, image_height * scale
    pdf.drawImage(
        image,
        x + (width - draw_width) / 2,
        y + (height - draw_height) / 2,
        draw_width,
        draw_height,
        preserveAspectRatio=True,
        mask=mask,
    )
    return True


def _draw_watermark(pdf: canvas.Canvas, *, opacity: float = 0.04) -> None:
    """Place a subtle logo mark behind every report page."""
    pdf.saveState()
    try:
        pdf.setFillAlpha(opacity)
        pdf.setStrokeAlpha(opacity)
    except AttributeError:
        # Older ReportLab builds do not expose transparency. The pale fill
        # remains intentionally non-intrusive on those installations.
        pass
    mark_size = 102 * mm
    mark_x = (PAGE_WIDTH - mark_size) / 2
    mark_y = (PAGE_HEIGHT - mark_size) / 2 - 7 * mm
    if not _draw_contained_image(pdf, NIPRIX_MARK, mark_x, mark_y, mark_size, mark_size):
        pdf.setFillColor(SOFT_LAVENDER)
        pdf.setFont("Helvetica-Bold", 54)
        pdf.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT / 2, "NIPRIX")
    pdf.restoreState()


def _page_chrome(pdf: canvas.Canvas, document: SimpleDocTemplate) -> None:
    _draw_watermark(pdf)

    pdf.saveState()
    header_height = 23 * mm
    header_bottom = PAGE_HEIGHT - header_height
    pdf.setFillColor(colors.white)
    pdf.rect(0, header_bottom, PAGE_WIDTH, header_height, fill=1, stroke=0)
    pdf.setFillColor(LAVENDER)
    pdf.rect(0, header_bottom, PAGE_WIDTH, 1.4 * mm, fill=1, stroke=0)

    if not _draw_contained_image(pdf, NIPRIX_LOGO, 16 * mm, header_bottom + 3.2 * mm, 40 * mm, 15 * mm):
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(18 * mm, header_bottom + 9 * mm, "NIPRIX")

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(PAGE_WIDTH / 2, header_bottom + 12.8 * mm, "PROPERTY INVENTORY REPORT")
    company_name = getattr(document, "company_name", "")
    if company_name:
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7.4)
        pdf.drawCentredString(PAGE_WIDTH / 2, header_bottom + 8.4 * mm, company_name)

    if not _draw_contained_image(pdf, PARAMSHIV_LOGO, PAGE_WIDTH - 63 * mm, header_bottom + 4 * mm, 45 * mm, 13 * mm):
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawRightString(PAGE_WIDTH - 18 * mm, header_bottom + 9 * mm, "Paramshiv")
    pdf.restoreState()


class PageNumberCanvas(canvas.Canvas):
    """Defers pages so the footer can include a final page count."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):  # noqa: N802 - ReportLab callback name
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_footer(self, page_count: int) -> None:
        self.saveState()
        # This second, low-opacity pass happens after flowables have painted
        # their opaque table cells, keeping the NIPRIX watermark visible on
        # every dense data page as well as in open report space.
        _draw_watermark(self, opacity=0.025)
        footer_y = 11.5 * mm
        pdf_margin = 18 * mm
        self.setStrokeColor(GRID)
        self.setLineWidth(0.45)
        self.line(pdf_margin, footer_y + 4 * mm, PAGE_WIDTH - pdf_margin, footer_y + 4 * mm)
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 7.3)
        self.drawString(pdf_margin, footer_y, "NIPRIX CRM - Authorized inventory export")
        page_label = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(PAGE_WIDTH - pdf_margin, footer_y, page_label)
        self.restoreState()


def build_inventory_pdf(records: Iterable[Sequence[object]], *, company_name: str = "") -> bytes:
    """Build a complete, branded inventory PDF from an already scoped queryset."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=PAGE_SIZE,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=31 * mm,
        bottomMargin=20 * mm,
        title="NIPRIX Property Inventory Report",
        author="NIPRIX CRM",
    )
    document.company_name = company_name.strip()

    styles = getSampleStyleSheet()
    report_title = ParagraphStyle(
        "InventoryTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=NAVY,
        spaceAfter=1.5 * mm,
    )
    metadata = ParagraphStyle(
        "InventoryMetadata",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=11,
        textColor=MUTED,
    )
    column_header = ParagraphStyle(
        "InventoryColumnHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.8,
        leading=8.3,
        textColor=NAVY,
        alignment=TA_LEFT,
    )
    cell = ParagraphStyle(
        "InventoryCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=8.7,
        textColor=INK,
        alignment=TA_LEFT,
    )
    centered_cell = ParagraphStyle("InventoryCenteredCell", parent=cell, alignment=TA_CENTER)

    row_list = list(records)
    generated_at = timezone.localtime(timezone.now()).strftime("%d %b %Y, %I:%M %p")
    summary = f"Generated {generated_at} | {len(row_list)} authorized inventory record{'s' if len(row_list) != 1 else ''}"
    if document.company_name:
        summary = f"{summary} | {document.company_name}"

    story = [
        Paragraph("Property Inventory", report_title),
        Paragraph(summary, metadata),
        Spacer(1, 4.5 * mm),
    ]

    if not row_list:
        empty_state = Table(
            [[Paragraph("No active inventory records are available in this workspace.", ParagraphStyle("InventoryEmpty", parent=metadata, fontSize=10, leading=14, textColor=NAVY, alignment=TA_CENTER))]],
            colWidths=[PAGE_WIDTH - 36 * mm],
            rowHeights=[27 * mm],
        )
        empty_state.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SOFT_LAVENDER),
                    ("BOX", (0, 0), (-1, -1), 0.7, LAVENDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(empty_state)
    else:
        headers = ("Project", "Unit", "Type", "Size", "Floor", "Basic price", "Status", "Landing", "Booked")
        data = [[_paragraph(header, column_header) for header in headers]]
        for project, unit, property_type, size, floor, basic_price, status, landing, booking_date in row_list:
            data.append(
                [
                    _paragraph(project, cell),
                    _paragraph(unit, cell),
                    _paragraph(property_type, cell),
                    _paragraph(f"{_text(size)} sq ft" if size not in (None, "") else "-", centered_cell),
                    _paragraph(floor, cell),
                    _paragraph(_currency(basic_price), centered_cell),
                    _paragraph(status.replace("_", " ").title() if status else "-", centered_cell),
                    _paragraph(_currency(landing), centered_cell),
                    _paragraph(_date(booking_date), centered_cell),
                ]
            )

        # LongTable continuation fragments can start at the physical page top
        # in ReportLab, covering the repeated dual-brand chrome. Paging modest
        # chunks explicitly keeps each page within the document frame.

        table = Table(
            data,
            colWidths=[
                42 * mm, 22 * mm, 26 * mm, 18 * mm, 16 * mm,
                28 * mm, 20 * mm, 29 * mm, 22 * mm,
            ],
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), LAVENDER),
                    ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
                    ("GRID", (0, 0), (-1, -1), 0.3, GRID),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT_LAVENDER]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, 0), 3.4 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 3.1 * mm),
                    ("TOPPADDING", (0, 1), (-1, -1), 2.6 * mm),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 2.6 * mm),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2.1 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2.1 * mm),
                ]
            )
        )
        story.append(table)


    document.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome, canvasmaker=PageNumberCanvas)
    return output.getvalue()
