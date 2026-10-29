"""Branded customer quote PDF (retail price only — never net cost or markup)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TEAL = colors.HexColor("#115e59")
STONE = colors.HexColor("#57534e")
LIGHT = colors.HexColor("#f5f5f4")
VALID_DAYS = 7


def _peso(v: Decimal) -> str:
    return f"PHP {v:,.2f}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle("brand", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20, textColor=TEAL, alignment=0, spaceAfter=2),
        "tag": ParagraphStyle("tag", parent=base["Normal"], fontSize=9, textColor=STONE),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=TEAL, spaceBefore=10, spaceAfter=4),
        "title": ParagraphStyle("title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, spaceAfter=2),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=13),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8, leading=11, textColor=STONE),
        "right": ParagraphStyle("right", parent=base["Normal"], fontSize=9, alignment=TA_RIGHT, textColor=STONE, leading=12),
    }


def _p(text: Optional[str], style) -> Paragraph:
    return Paragraph(escape(text or "").replace("\n", "<br/>"), style)


def build_quote_pdf(
    *, brand: dict, agent: dict, agent_email: Optional[str], pkg: dict, destination: Optional[dict],
    unit_retail: Decimal, pax: int, customer_name: Optional[str], travel_date: Optional[str],
    quote_no: str,
) -> bytes:
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=f"Quote {quote_no}")
    now = datetime.now(timezone.utc)
    total = (unit_retail * pax).quantize(Decimal("0.01"))

    header_left = [_p(brand.get("name") or "Biyahe'Ta Bai Travel", s["brand"]), _p(brand.get("tagline"), s["tag"])]
    header_right = [Paragraph(
        f"<b>TRAVEL QUOTE</b><br/>No. {escape(quote_no)}<br/>Date: {now:%d %b %Y}<br/>"
        f"Valid until: {(now + timedelta(days=VALID_DAYS)):%d %b %Y}", s["right"])]
    story = [Table([[header_left, header_right]], colWidths=[110 * mm, 64 * mm],
                   style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, TEAL),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 8)])]
    story.append(Spacer(1, 8))

    agent_lines = "<br/>".join(escape(x) for x in [agent.get("phone"), agent_email] if x)
    prepared = [[
        Paragraph(f"<b>Prepared for</b><br/>{escape(customer_name or 'Valued guest')}", s["body"]),
        Paragraph(
            f"<b>Your travel agent</b><br/>{escape(agent.get('agency_name') or agent.get('display_name') or '')}"
            f"<br/>{escape(agent.get('display_name') or '')}<br/>{agent_lines}", s["body"]),
    ]]
    story.append(Table(prepared, colWidths=[87 * mm, 87 * mm], style=[
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(Spacer(1, 10))
    story.append(_p(pkg["title"], s["title"]))
    where = ", ".join(x for x in [(destination or {}).get("name"), (destination or {}).get("country")] if x)
    story.append(_p(f"{where} · {pkg.get('duration_days')} days / {pkg.get('duration_nights')} nights", s["small"]))
    if pkg.get("summary"):
        story.append(Spacer(1, 4))
        story.append(_p(pkg["summary"], s["body"]))

    story.append(_p("Price summary", s["h"]))
    rows = [
        ["Travel date", travel_date or "To be confirmed"],
        ["Number of travellers", f"{pax} pax"],
        ["Price per person", _peso(unit_retail)],
        ["Total package price", _peso(total)],
    ]
    t = Table(rows, colWidths=[110 * mm, 64 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e7e5e4")),
        ("BACKGROUND", (0, -1), (-1, -1), TEAL), ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)

    def bullet_list(title, items):
        if not items:
            return
        story.append(_p(title, s["h"]))
        for it in items:
            story.append(Paragraph(f"• {escape(it)}", s["body"]))

    sort = lambda xs: [x.get("text") for x in sorted(xs or [], key=lambda x: x.get("sort_order", 0))]
    bullet_list("Inclusions", sort(pkg.get("inclusions")))
    bullet_list("Exclusions", sort(pkg.get("exclusions")))
    if pkg.get("highlights"):
        story.append(_p("Highlights", s["h"]))
        story.append(_p(pkg["highlights"], s["body"]))

    story.append(Spacer(1, 14))
    contact = " · ".join(x for x in [brand.get("support_email"), brand.get("support_phone")] if x)
    story.append(_p(
        f"Prices are per person in Philippine pesos and subject to availability at the time of booking. "
        f"This quote is valid for {VALID_DAYS} days. {brand.get('name') or ''}" + (f" · {contact}" if contact else ""), s["small"]))

    doc.build(story)
    return buf.getvalue()
