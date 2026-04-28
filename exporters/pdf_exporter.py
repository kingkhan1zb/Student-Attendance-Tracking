"""
PDF report exporter using ReportLab — generates a clean, paginated attendance report.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models import AttendanceStatus, StudentRecord

# ── Palette ────────────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#1F3864")
LIGHT_NAVY = colors.HexColor("#2E5BA0")
OK_GREEN = colors.HexColor("#D9EAD3")
OK_TEXT = colors.HexColor("#274E13")
SHORTAGE_RED = colors.HexColor("#FCE4D6")
SHORTAGE_TEXT = colors.HexColor("#7F0000")
ALT_BLUE = colors.HexColor("#EBF2FF")
WHITE = colors.white
GREY_TEXT = colors.HexColor("#555555")
BORDER = colors.HexColor("#B8C9E1")


def _get_styles():
    """Return a set of custom paragraph styles."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=20,
            fontName="Helvetica-Bold",
            textColor=NAVY,
            spaceAfter=4,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=GREY_TEXT,
            spaceAfter=8,
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "SectionHeader",
            parent=base["Normal"],
            fontSize=12,
            fontName="Helvetica-Bold",
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "normal": ParagraphStyle(
            "BodyText",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=colors.black,
        ),
        "warning": ParagraphStyle(
            "WarningText",
            parent=base["Normal"],
            fontSize=8,
            fontName="Helvetica-Oblique",
            textColor=SHORTAGE_TEXT,
            leading=11,
        ),
        "kpi_label": ParagraphStyle(
            "KPILabel",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=GREY_TEXT,
            alignment=TA_CENTER,
        ),
        "kpi_value": ParagraphStyle(
            "KPIValue",
            parent=base["Normal"],
            fontSize=16,
            fontName="Helvetica-Bold",
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
    }


def _build_kpi_table(records: List[StudentRecord], threshold: float, styles: dict) -> Table:
    """Build a 4-column KPI summary row."""
    ok = sum(1 for r in records if r.status == AttendanceStatus.OK)
    shortage = len(records) - ok
    avg = sum(r.attendance_percentage for r in records) / len(records) if records else 0

    def kpi(label: str, value: str) -> List:
        return [
            Paragraph(label, styles["kpi_label"]),
            Paragraph(value, styles["kpi_value"]),
        ]

    data = [
        [
            Table([kpi("Total Students", str(len(records)))], colWidths=[4.5 * cm]),
            Table([kpi("✔ Meeting Threshold", str(ok))], colWidths=[4.5 * cm]),
            Table([kpi("✘ Below Threshold", str(shortage))], colWidths=[4.5 * cm]),
            Table([kpi("Average Attendance", f"{avg:.1f}%")], colWidths=[4.5 * cm]),
        ]
    ]

    t = Table(data, colWidths=[4.5 * cm] * 4)
    t.setStyle(
        TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("BACKGROUND", (0, 0), (0, 0), ALT_BLUE),
            ("BACKGROUND", (1, 0), (1, 0), OK_GREEN),
            ("BACKGROUND", (2, 0), (2, 0), SHORTAGE_RED),
            ("BACKGROUND", (3, 0), (3, 0), ALT_BLUE),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    return t


def _build_main_table(records: List[StudentRecord], styles: dict) -> Table:
    """Build the full attendance data table."""
    headers = [
        "Student Name", "Roll No.", "Total\nClasses",
        "Attended", "Attendance\n%", "Deficit\nClasses", "Status"
    ]

    col_widths = [5.0 * cm, 2.5 * cm, 2.2 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]

    data = [headers]
    for record in records:
        data.append([
            record.name,
            record.roll_number,
            str(record.total_classes),
            str(record.classes_attended),
            f"{record.attendance_percentage:.1f}%",
            str(record.deficit_classes) if record.deficit_classes > 0 else "—",
            record.status.value,
        ])

    style_cmds = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.8, NAVY),
    ]

    # Row colouring
    for row_i, record in enumerate(records, start=1):
        is_shortage = record.status == AttendanceStatus.SHORTAGE
        bg = SHORTAGE_RED if is_shortage else (ALT_BLUE if row_i % 2 == 0 else WHITE)
        style_cmds.append(("BACKGROUND", (0, row_i), (-1, row_i), bg))
        if is_shortage:
            style_cmds.append(("TEXTCOLOR", (6, row_i), (6, row_i), SHORTAGE_TEXT))
            style_cmds.append(("FONTNAME", (6, row_i), (6, row_i), "Helvetica-Bold"))
        else:
            style_cmds.append(("TEXTCOLOR", (6, row_i), (6, row_i), OK_TEXT))

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    return t


def _build_warnings_table(flagged: List[StudentRecord], styles: dict) -> Table:
    """Build the AI warnings table for flagged students."""
    headers = ["Student Name", "Roll No.", "Att. %", "Warning Message"]
    col_widths = [3.5 * cm, 2.5 * cm, 2.0 * cm, 11.4 * cm]

    data = [headers]
    for record in flagged:
        warning_para = Paragraph(record.ai_warning or "—", styles["warning"])
        data.append([
            record.name,
            record.roll_number,
            f"{record.attendance_percentage:.1f}%",
            warning_para,
        ])

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), SHORTAGE_TEXT),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 1), (2, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (2, -1), 8),
        ("ALIGN", (1, 1), (2, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BOX", (0, 0), (-1, -1), 0.8, SHORTAGE_TEXT),
    ]
    for row_i in range(1, len(flagged) + 1):
        bg = SHORTAGE_RED if row_i % 2 == 1 else WHITE
        style_cmds.append(("BACKGROUND", (0, row_i), (-1, row_i), bg))

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    return t


def _on_page(canvas, doc, threshold: float) -> None:
    """Draw header/footer on every page."""
    canvas.saveState()
    w, h = doc.pagesize

    # Footer line
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 1.5 * cm, w - doc.rightMargin, 1.5 * cm)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY_TEXT)
    canvas.drawString(doc.leftMargin, 1.1 * cm, f"Threshold: {threshold}%")
    canvas.drawCentredString(w / 2, 1.1 * cm, "Student Attendance Management System")
    canvas.drawRightString(
        w - doc.rightMargin, 1.1 * cm, f"Page {doc.page}"
    )
    canvas.restoreState()


def export_pdf(records: List[StudentRecord], threshold: float = 75.0) -> bytes:
    """
    Generate a professional PDF attendance report.

    Args:
        records: List of StudentRecord objects.
        threshold: Attendance threshold for this report.

    Returns:
        Raw bytes of the generated PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = _get_styles()
    story = []

    # ── Title block ────────────────────────────────────────────────────────────
    story.append(Paragraph("Student Attendance Report", styles["title"]))
    now = datetime.now().strftime("%B %d, %Y  •  %I:%M %p")
    story.append(Paragraph(f"Generated on {now}", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=10))

    # ── KPI Summary ────────────────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", styles["section"]))
    story.append(_build_kpi_table(records, threshold, styles))
    story.append(Spacer(1, 0.5 * cm))

    # ── Full attendance table ──────────────────────────────────────────────────
    story.append(Paragraph("Attendance Details", styles["section"]))
    story.append(_build_main_table(records, styles))
    story.append(Spacer(1, 0.5 * cm))

    # ── Warnings section ───────────────────────────────────────────────────────
    flagged = [r for r in records if r.status == AttendanceStatus.SHORTAGE and r.ai_warning]
    if flagged:
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8))
        story.append(Paragraph("⚠ AI-Generated Warning Messages", styles["section"]))
        story.append(_build_warnings_table(flagged, styles))

    doc.build(
        story,
        onFirstPage=lambda c, d: _on_page(c, d, threshold),
        onLaterPages=lambda c, d: _on_page(c, d, threshold),
    )
    return buf.getvalue()
