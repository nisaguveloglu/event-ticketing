from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.check_in import CheckIn
from app.models.ticket import Ticket, TicketStatus
from app.schemas.checkin import CheckInResponse


class CheckInConflictError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        checked_in_at: datetime | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.checked_in_at = checked_in_at

    def to_envelope(self) -> dict:
        payload = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.checked_in_at is not None:
            payload["error"]["checked_in_at"] = self.checked_in_at.isoformat()
        return payload


def verify_and_check_in_ticket(
    db: Session,
    event_id: int,
    ticket_code: str,
    staff_label: str = "staff",
) -> CheckInResponse:
    try:
        ticket = (
            db.query(Ticket)
            .filter(Ticket.ticket_code == ticket_code)
            .with_for_update()
            .first()
        )

        if ticket is None:
            db.rollback()
            raise CheckInConflictError(
                status_code=404,
                code="TICKET_NOT_FOUND",
                message="Ticket not found.",
            )

        if ticket.event_id != event_id:
            db.rollback()
            raise CheckInConflictError(
                status_code=409,
                code="WRONG_EVENT",
                message="Ticket belongs to a different event.",
            )

        existing_check_in = (
            db.query(CheckIn)
            .filter(CheckIn.ticket_id == ticket.id)
            .first()
        )

        if ticket.status == TicketStatus.USED.value or existing_check_in is not None:
            first_time = existing_check_in.checked_in_at if existing_check_in else None
            db.rollback()
            raise CheckInConflictError(
                status_code=409,
                code="TICKET_ALREADY_USED",
                message="Ticket has already been used.",
                checked_in_at=first_time,
            )

        now_utc = datetime.now(timezone.utc)
        ticket.status = TicketStatus.USED.value
        check_in_record = CheckIn(
            ticket_id=ticket.id,
            checked_in_at=now_utc,
            staff_label=staff_label,
        )
        db.add(check_in_record)
        db.commit()

        return CheckInResponse(
            result="ACCEPTED",
            ticket_code=ticket.ticket_code,
            event_id=ticket.event_id,
            seat_id=ticket.seat_id,
            checked_in_at=check_in_record.checked_in_at,
        )
    except CheckInConflictError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        existing_ticket = (
            db.query(Ticket).filter(Ticket.ticket_code == ticket_code).first()
        )
        existing_ci = (
            db.query(CheckIn).filter(CheckIn.ticket_id == existing_ticket.id).first()
            if existing_ticket
            else None
        )
        raise CheckInConflictError(
            status_code=409,
            code="TICKET_ALREADY_USED",
            message="Ticket has already been used.",
            checked_in_at=existing_ci.checked_in_at if existing_ci else None,
        ) from exc
    except SQLAlchemyError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
