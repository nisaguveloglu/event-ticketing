import secrets

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.seat import Seat
from app.models.ticket import Ticket
from app.schemas.ticket import TicketResponse

MAX_TICKET_CODE_RETRIES = 5
UNIQUE_VIOLATION_SQLSTATE = "23505"
EVENT_SEAT_UNIQUE_CONSTRAINT = "uq_tickets_event_seat"
TICKET_CODE_UNIQUE_CONSTRAINTS = frozenset(
    {
        "ix_tickets_ticket_code",
        "uq_tickets_ticket_code",
        "tickets_ticket_code_key",
    }
)


def generate_ticket_code() -> str:
    return secrets.token_urlsafe(16)


def resolve_event_for_seat(db: Session, seat: Seat) -> Event:
    events = (
        db.query(Event)
        .filter(Event.hall_id == seat.hall_id)
        .order_by(Event.id.asc())
        .limit(2)
        .all()
    )

    if len(events) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active event found for this seat's hall",
        )

    if len(events) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple events found for this hall; explicit event selection required",
        )

    event = events[0]
    if event.hall_id != seat.hall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seat does not belong to the event's hall",
        )

    return event


def _extract_pg_sqlstate_and_constraint(exc: IntegrityError) -> tuple[str, str]:
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None) or ""
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None) or ""
    return sqlstate, constraint_name


def _is_duplicate_event_seat_error(exc: IntegrityError) -> bool:
    sqlstate, constraint_name = _extract_pg_sqlstate_and_constraint(exc)
    return (
        sqlstate == UNIQUE_VIOLATION_SQLSTATE
        and constraint_name == EVENT_SEAT_UNIQUE_CONSTRAINT
    )


def _is_ticket_code_collision_error(exc: IntegrityError) -> bool:
    sqlstate, constraint_name = _extract_pg_sqlstate_and_constraint(exc)
    return (
        sqlstate == UNIQUE_VIOLATION_SQLSTATE
        and constraint_name in TICKET_CODE_UNIQUE_CONSTRAINTS
    )


def create_ticket_for_purchase(
    db: Session,
    seat: Seat,
    session_id: str,
    max_retries: int = MAX_TICKET_CODE_RETRIES,
) -> Ticket:
    event = resolve_event_for_seat(db=db, seat=seat)

    existing_ticket = (
        db.query(Ticket)
        .filter(
            Ticket.event_id == event.id,
            Ticket.seat_id == seat.id,
        )
        .first()
    )
    if existing_ticket is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket already exists for this event and seat",
        )

    for _ in range(max_retries):
        candidate_code = generate_ticket_code()
        try:
            with db.begin_nested():
                ticket = Ticket(
                    ticket_code=candidate_code,
                    event_id=event.id,
                    seat_id=seat.id,
                    session_id=session_id,
                )
                db.add(ticket)
                db.flush()
            return ticket
        except IntegrityError as exc:
            if _is_duplicate_event_seat_error(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ticket already exists for this event and seat",
                ) from exc
            if _is_ticket_code_collision_error(exc):
                continue
            raise

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not generate a unique ticket code",
    )


def get_ticket_by_code(db: Session, ticket_code: str) -> TicketResponse:
    ticket = (
        db.query(Ticket)
        .filter(Ticket.ticket_code == ticket_code)
        .first()
    )

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    event = ticket.event
    seat = ticket.seat
    hall = event.hall

    return TicketResponse(
        id=ticket.id,
        ticket_code=ticket.ticket_code,
        event_id=event.id,
        event_name=event.name,
        event_starts_at=event.starts_at,
        hall_id=hall.id,
        hall_name=hall.name,
        seat_id=seat.id,
        seat_row=seat.row,
        seat_number=seat.number,
        seat_status=seat.status,
        created_at=ticket.created_at,
    )
