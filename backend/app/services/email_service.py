from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import os
import re
import smtplib
from typing import Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.email_delivery import EmailDelivery, EmailDeliveryStatus
from app.models.order import Order
from app.models.ticket import Ticket
from app.services.pdf_service import generate_order_tickets_pdf

MAX_EMAIL_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = {1: 10, 2: 30}
RESEND_COOLDOWN_SECONDS = 60
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailDeliveryError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_envelope(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }


def normalize_and_validate_email(raw_email: str) -> str:
    cleaned = (raw_email or "").strip().lower()
    if not cleaned or len(cleaned) > 255 or not _EMAIL_REGEX.match(cleaned):
        raise EmailDeliveryError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Invalid recipient email address.",
        )
    return cleaned


def enqueue_order_email_in_transaction(
    db: Session,
    order_id: int,
    recipient: str,
    purpose: str = "ORDER_TICKETS",
    now_utc: datetime | None = None,
) -> EmailDelivery:
    normalized_recipient = normalize_and_validate_email(recipient)
    current_time = now_utc or datetime.now(timezone.utc)
    delivery = EmailDelivery(
        order_id=order_id,
        recipient=normalized_recipient,
        purpose=purpose,
        status=EmailDeliveryStatus.PENDING.value,
        attempts=0,
        next_attempt_at=current_time,
        created_at=current_time,
    )
    db.add(delivery)
    db.flush()
    return delivery


def request_order_email_delivery(
    db: Session,
    order_id: int,
    recipient: str,
    purpose: str = "ORDER_TICKETS",
    now_utc: datetime | None = None,
) -> EmailDelivery:
    normalized_recipient = normalize_and_validate_email(recipient)
    current_time = now_utc or datetime.now(timezone.utc)

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise EmailDeliveryError(
            status_code=404,
            code="NOT_FOUND",
            message="Order not found.",
        )

    cooldown_cutoff = current_time - timedelta(seconds=RESEND_COOLDOWN_SECONDS)
    recent_delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.order_id == order_id,
            EmailDelivery.recipient == normalized_recipient,
            EmailDelivery.created_at >= cooldown_cutoff,
        )
        .order_by(EmailDelivery.id.desc())
        .first()
    )
    if recent_delivery is not None:
        raise EmailDeliveryError(
            status_code=429,
            code="RATE_LIMITED",
            message="Please wait 60 seconds before requesting another email for this order.",
        )

    delivery = EmailDelivery(
        order_id=order_id,
        recipient=normalized_recipient,
        purpose=purpose,
        status=EmailDeliveryStatus.PENDING.value,
        attempts=0,
        next_attempt_at=current_time,
        created_at=current_time,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def list_order_email_deliveries(db: Session, order_id: int) -> list[EmailDelivery]:
    return (
        db.query(EmailDelivery)
        .filter(EmailDelivery.order_id == order_id)
        .order_by(EmailDelivery.id.asc())
        .all()
    )


def _default_smtp_sender(
    recipient: str,
    subject: str,
    body_text: str,
    pdf_bytes: bytes,
    order_id: int,
) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "127.0.0.1")
    smtp_port = int(os.environ.get("SMTP_PORT", "1025"))
    smtp_user = os.environ.get("SMTP_USERNAME", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", "noreply@event-ticketing.local")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = recipient
    msg.set_content(body_text)
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"order-{order_id}-tickets.pdf",
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        if smtp_user and smtp_pass:
            server.starttls()
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def process_pending_email_deliveries(
    db: Session,
    send_fn: Callable[[str, str, str, bytes, int], None] | None = None,
    now_utc: datetime | None = None,
    batch_size: int = 10,
) -> list[EmailDelivery]:
    current_time = now_utc or datetime.now(timezone.utc)
    sender = send_fn or _default_smtp_sender

    due_deliveries = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.status == EmailDeliveryStatus.PENDING.value,
            or_(
                EmailDelivery.next_attempt_at.is_(None),
                EmailDelivery.next_attempt_at <= current_time,
            ),
        )
        .order_by(EmailDelivery.id.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
        .all()
    )

    processed: list[EmailDelivery] = []
    for delivery in due_deliveries:
        delivery.attempts += 1
        try:
            tickets = (
                db.query(Ticket)
                .filter(Ticket.order_id == delivery.order_id)
                .order_by(Ticket.id.asc())
                .all()
            )
            ticket_codes_str = ", ".join(t.ticket_code for t in tickets)
            pdf_bytes = generate_order_tickets_pdf(db=db, order_id=delivery.order_id)
            subject = f"Event Ticketing - Sipariş #{delivery.order_id} Biletleriniz"
            body = (
                f"Sipariş #{delivery.order_id} için biletleriniz ekteki PDF dosyasındadır.\n"
                f"Bilet Kodları: {ticket_codes_str}\n"
            )
            sender(
                delivery.recipient,
                subject,
                body,
                pdf_bytes,
                delivery.order_id,
            )
            delivery.status = EmailDeliveryStatus.SENT.value
            delivery.sent_at = current_time
            delivery.last_error = None
            delivery.next_attempt_at = None
        except Exception as exc:
            delivery.last_error = str(exc)
            if delivery.attempts >= MAX_EMAIL_ATTEMPTS:
                delivery.status = EmailDeliveryStatus.FAILED.value
                delivery.next_attempt_at = None
            else:
                backoff = RETRY_BACKOFF_SECONDS.get(delivery.attempts, 30)
                delivery.status = EmailDeliveryStatus.PENDING.value
                delivery.next_attempt_at = current_time + timedelta(seconds=backoff)

        processed.append(delivery)

    db.commit()
    return processed
