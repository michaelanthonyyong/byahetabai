"""Agent-branded customer documents: quotes and payment receipts.

Only retail figures ever appear — never net cost or markup.
"""
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
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TEAL = colors.HexColor("#115e59")
STONE = colors.HexColor("#57534e")
LIGHT = colors.HexColor("#f5f5f4")
RULE = colors.HexColor("#e7e5e4")
VALID_DAYS = 7

METHOD_LABELS = {"cash": "Cash", "gcash": "GCash", "bank_transfer": "Bank transfer", "card": "Card", "other": "Other"}


def peso(v: Decimal) -> str:
    return f"PHP {v:,.2f}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle("brand", parent=base["Title"], fontName="Helvetica-Bold", fontSize=18, textColor=TEAL, alignment=0, spaceAfter=2, leading=22),
        "tag": ParagraphStyle("tag", parent=base["Normal"], fontSize=8.5, textColor=STONE, leading=11),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=TEAL, spaceBefore=10, spaceAfter=4),
        "title": ParagraphStyle("title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, spaceAfter=2),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=13),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8, leading=11, textColor=STONE),
        "right": ParagraphStyle("right", parent=base["Normal"], fontSize=9, alignment=TA_RIGHT, textColor=STONE, leading=12),
    }


def _p(text: Optional[str], style) -> Paragraph:
    return Paragraph(escape(text or "").replace("\n", "<br/>"), style)


def _logo(data: Optional[bytes]):
    if not data:
        return None
    try:
        reader = ImageReader(BytesIO(data))
        w, h = reader.getSize()
        max_w, max_h = 40 * mm, 18 * mm
        scale = min(max_w / w, max_h / h)
        return Image(BytesIO(data), width=w * scale, height=h * scale, hAlign="LEFT")
    except Exception:
        return None


def _header(s, brand: dict, right_html: str) -> Table:
    left = []
    logo = _logo(brand.get("logo"))
    if logo:
        left += [logo, Spacer(1, 3)]
    left.append(_p(brand.get("name"), s["brand"]))
    if brand.get("lines"):
        left.append(Paragraph("<br/>".join(escape(x) for x in brand["lines"]), s["tag"]))
    return Table([[left, [Paragraph(right_html, s["right"])]]], colWidths=[110 * mm, 64 * mm],
                 style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, TEAL),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (0, 0), 0)])


def _kv_table(rows: list[list[str]], highlight_last: bool = True) -> Table:
    t = Table(rows, colWidths=[110 * mm, 64 * mm])
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 10), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    if highlight_last:
        style += [("BACKGROUND", (0, -1), (-1, -1), TEAL), ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                  ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, -1), (-1, -1), 11)]
    t.setStyle(TableStyle(style))
    return t


def _doc(buf: BytesIO, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                             topMargin=16 * mm, bottomMargin=16 * mm, title=title)


def build_quote_pdf(
    *, brand: dict, pkg: dict, destination: Optional[dict],
    unit_retail: Decimal, pax: int, customer_name: Optional[str], travel_date: Optional[str],
    quote_no: str,
) -> bytes:
    s = _styles()
    buf = BytesIO()
    now = datetime.now(timezone.utc)
    total = (unit_retail * pax).quantize(Decimal("0.01"))
    story = [_header(s, brand,
                     f"<b>TRAVEL QUOTE</b><br/>No. {escape(quote_no)}<br/>Date: {now:%d %b %Y}<br/>"
                     f"Valid until: {(now + timedelta(days=VALID_DAYS)):%d %b %Y}"),
             Spacer(1, 8)]
    story.append(Table([[Paragraph(f"<b>Prepared for</b><br/>{escape(customer_name or 'Valued guest')}", s["body"])]],
                       colWidths=[174 * mm], style=[("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                                                    ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
                                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(Spacer(1, 10))
    story.append(_p(pkg["title"], s["title"]))
    where = ", ".join(x for x in [(destination or {}).get("name"), (destination or {}).get("country")] if x)
    story.append(_p(f"{where} · {pkg.get('duration_days')} days / {pkg.get('duration_nights')} nights", s["small"]))
    if pkg.get("summary"):
        story += [Spacer(1, 4), _p(pkg["summary"], s["body"])]

    story.append(_p("Price summary", s["h"]))
    story.append(_kv_table([
        ["Travel date", travel_date or "To be confirmed"],
        ["Number of travellers", f"{pax} pax"],
        ["Price per person", peso(unit_retail)],
        ["Total package price", peso(total)],
    ]))

    sort = lambda xs: [x.get("text") for x in sorted(xs or [], key=lambda x: x.get("sort_order", 0))]
    for title, items in (("Inclusions", sort(pkg.get("inclusions"))), ("Exclusions", sort(pkg.get("exclusions")))):
        if items:
            story.append(_p(title, s["h"]))
            story += [Paragraph(f"• {escape(it)}", s["body"]) for it in items]
    if pkg.get("highlights"):
        story += [_p("Highlights", s["h"]), _p(pkg["highlights"], s["body"])]

    story += [Spacer(1, 14), _p(
        f"Prices are per person in Philippine pesos and subject to availability at the time of booking. "
        f"This quote is valid for {VALID_DAYS} days.", s["small"])]
    _doc(buf, f"Quote {quote_no}").build(story)
    return buf.getvalue()


def build_receipt_pdf(
    *, brand: dict, receipt_no: str, booking: dict, pkg_title: str, customer_name: str,
    payment: dict, history: list[dict], total_due: Decimal, paid_to_date: Decimal,
) -> bytes:
    s = _styles()
    buf = BytesIO()
    balance = max(total_due - paid_to_date, Decimal("0.00"))
    paid_on = datetime.fromisoformat(payment["paid_on"]).strftime("%d %b %Y")
    story = [_header(s, brand, f"<b>OFFICIAL RECEIPT</b><br/>No. {escape(receipt_no)}<br/>Date paid: {paid_on}"),
             Spacer(1, 8)]

    travel = booking.get("travel_start_date")
    travel_label = datetime.fromisoformat(travel).strftime("%d %b %Y") if travel else "To be confirmed"
    info = [[
        Paragraph(f"<b>Received from</b><br/>{escape(customer_name)}", s["body"]),
        Paragraph(f"<b>Booking</b><br/>{escape(booking['reference_code'])}<br/>{escape(pkg_title)}"
                  f"<br/>{booking.get('pax')} pax · travel {travel_label}", s["body"]),
    ]]
    story.append(Table(info, colWidths=[87 * mm, 87 * mm], style=[
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(_p("This payment", s["h"]))
    rows = [["Payment method", METHOD_LABELS.get(payment["method"], payment["method"])]]
    if payment.get("reference"):
        rows.append(["Reference", payment["reference"]])
    rows.append(["Amount received", peso(payment["amount"])])
    story.append(_kv_table(rows))

    story.append(_p("Payment history", s["h"]))
    hist = [["Date", "Method", "Amount"]] + [
        [datetime.fromisoformat(h["paid_on"]).strftime("%d %b %Y"), METHOD_LABELS.get(h["method"], h["method"]), peso(h["amount"])]
        for h in history
    ]
    ht = Table(hist, colWidths=[60 * mm, 60 * mm, 54 * mm])
    ht.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), STONE), ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(ht)

    story.append(_p("Account summary", s["h"]))
    story.append(_kv_table([
        ["Total package price", peso(total_due)],
        ["Total paid to date", peso(paid_to_date)],
        ["Balance due" if balance > 0 else "Fully paid", peso(balance)],
    ]))
    story += [Spacer(1, 14), _p("Thank you for your payment. Please keep this receipt for your records.", s["small"])]
    _doc(buf, f"Receipt {receipt_no}").build(story)
    return buf.getvalue()
