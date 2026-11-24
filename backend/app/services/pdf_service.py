import io
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import numpy as np
from PIL import Image, ImageOps
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.models.event_seat import EventSeat
from app.models.order import Order
from app.models.ticket import Ticket
from app.services.qr_service import generate_ticket_qr_png

DISPLAY_TZ = ZoneInfo("Europe/Istanbul")
_REGISTERED_FONT_NAME: str | None = None


def _ensure_unicode_font() -> str:
    global _REGISTERED_FONT_NAME
    if _REGISTERED_FONT_NAME is not None:
        return _REGISTERED_FONT_NAME

    candidate_paths = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\tahoma.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]

    for font_path in candidate_paths:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("TicketUnicodeFont", str(font_path)))
            _REGISTERED_FONT_NAME = "TicketUnicodeFont"
            return _REGISTERED_FONT_NAME

    _REGISTERED_FONT_NAME = "Helvetica"
    return _REGISTERED_FONT_NAME


def _format_kurus_try(amount_kurus: int, currency: str = "TRY") -> str:
    lira = amount_kurus / 100.0
    return f"{lira:.2f} {currency}"


def generate_order_tickets_pdf(db: Session, order_id: int) -> bytes:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise ValueError(f"Order {order_id} not found")

    tickets = (
        db.query(Ticket)
        .filter(Ticket.order_id == order.id)
        .order_by(Ticket.id.asc())
        .all()
    )
    if not tickets:
        raise ValueError(f"No tickets found for order {order_id}")

    font_name = _ensure_unicode_font()
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    cards_per_page = 1
    card_height = 320
    top_margin = page_height - 80

    for idx, ticket in enumerate(tickets):
        if idx > 0 and idx % cards_per_page == 0:
            pdf.showPage()

        slot_in_page = idx % cards_per_page
        card_top = top_margin - slot_in_page * (card_height + 40)
        card_bottom = card_top - card_height

        event = ticket.event
        hall = event.hall
        seat = ticket.seat
        ev_seat = (
            db.query(EventSeat)
            .filter(
                EventSeat.event_id == ticket.event_id,
                EventSeat.seat_id == ticket.seat_id,
            )
            .first()
        )
        category_name = ev_seat.category.name if (ev_seat and ev_seat.category) else "Standard"
        row_lbl = seat.row_label or seat.row
        seat_label = f"{row_lbl}{seat.number}"
        local_starts_at = event.starts_at.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M")

        pdf.setLineWidth(1.2)
        pdf.roundRect(40, card_bottom, page_width - 80, card_height, 10, stroke=1, fill=0)

        pdf.setFont(font_name, 16)
        pdf.drawString(60, card_top - 35, f"Etkinlik Bileti — {event.name}")

        pdf.setFont(font_name, 11)
        pdf.drawString(60, card_top - 65, f"Salon: {hall.name}")
        pdf.drawString(60, card_top - 90, f"Tarih / Saat: {local_starts_at} (Europe/Istanbul)")
        pdf.drawString(60, card_top - 115, f"Koltuk: Sıra {row_lbl} - No {seat.number} ({seat_label})")
        pdf.drawString(60, card_top - 140, f"Kategori: {category_name}")
        pdf.drawString(
            60,
            card_top - 165,
            f"Ücret: {_format_kurus_try(ticket.unit_price_kurus, order.currency)} (Simulated purchase)",
        )
        pdf.drawString(60, card_top - 190, f"Durum: {ticket.status}")
        pdf.drawString(60, card_top - 215, f"Sipariş No: #{order.id}")
        pdf.drawString(60, card_top - 245, f"Bilet Kodu: {ticket.ticket_code}")

        qr_png_bytes = generate_ticket_qr_png(ticket.ticket_code, scale=10, border=4)
        qr_image = ImageReader(io.BytesIO(qr_png_bytes))
        qr_size = 170
        pdf.drawImage(
            qr_image,
            page_width - 60 - qr_size,
            card_top - 45 - qr_size,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask="auto",
        )

    pdf.save()
    return buffer.getvalue()


def _decode_pil_qr_image(pil_img: Image.Image) -> str:
    gray = ImageOps.expand(pil_img.convert("L"), border=24, fill=255)
    base_arr = np.array(gray, dtype=np.uint8)

    detectors = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        detectors.append(cv2.QRCodeDetectorAruco())

    for scale_factor in (1, 2, 3):
        if scale_factor == 1:
            candidate = base_arr
        else:
            candidate = cv2.resize(
                base_arr,
                (0, 0),
                fx=scale_factor,
                fy=scale_factor,
                interpolation=cv2.INTER_NEAREST,
            )
        for det in detectors:
            decoded_text, _, _ = det.detectAndDecode(candidate)
            if decoded_text:
                return decoded_text

    return ""


def decode_qr_from_png_bytes(png_bytes: bytes) -> str:
    pil_img = Image.open(io.BytesIO(png_bytes))
    decoded_text = _decode_pil_qr_image(pil_img)
    if not decoded_text:
        raise ValueError("QR code could not be decoded from PNG image")
    return decoded_text


def extract_and_decode_qrs_from_pdf_bytes(pdf_bytes: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    decoded_codes: list[str] = []

    for page in reader.pages:
        for image_file in page.images:
            pil_img = Image.open(io.BytesIO(image_file.data))
            decoded_text = _decode_pil_qr_image(pil_img)
            if decoded_text:
                decoded_codes.append(decoded_text)

    return decoded_codes
