import secrets

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_seat import EventSeat
from app.models.order import Order
from app.models.reservation_item import ReservationItem
from app.models.seat import Seat, SeatStatus
from app.models.ticket import Ticket, TicketStatus
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


def _insert_ticket_with_retry(
    db: Session,
    event_id: int,
    seat_id: int,
    unit_price_kurus: int,
    session_id: str,
    order_id: int | None = None,
    max_retries: int = MAX_TICKET_CODE_RETRIES,
) -> Ticket:
    existing_ticket = (
        db.query(Ticket)
        .filter(
            Ticket.event_id == event_id,
            Ticket.seat_id == seat_id,
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
                    order_id=order_id,
                    ticket_code=candidate_code,
                    event_id=event_id,
                    seat_id=seat_id,
                    unit_price_kurus=unit_price_kurus,
                    status=TicketStatus.VALID.value,
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


def create_ticket_for_order_item(
    db: Session,
    order: Order,
    event_seat: EventSeat,
    unit_price_kurus: int | None = None,
    session_id: str = "guest",
    max_retries: int = MAX_TICKET_CODE_RETRIES,
) -> Ticket:
    seat = event_seat.seat or db.query(Seat).filter(Seat.id == event_seat.seat_id).first()
    event = event_seat.event or db.query(Event).filter(Event.id == event_seat.event_id).first()

    if seat is None or event is None or seat.hall_id != event.hall_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seat does not belong to the event's hall",
        )

    effective_price = (
        unit_price_kurus if unit_price_kurus is not None else event_seat.price_kurus
    )
    event_seat.status = SeatStatus.SOLD

    return _insert_ticket_with_retry(
        db=db,
        event_id=event_seat.event_id,
        seat_id=event_seat.seat_id,
        unit_price_kurus=effective_price,
        session_id=session_id,
        order_id=order.id,
        max_retries=max_retries,
    )


def create_tickets_for_order(
    db: Session,
    order: Order,
    reservation_items: list[ReservationItem],
    session_id: str = "guest",
    max_retries: int = MAX_TICKET_CODE_RETRIES,
) -> list[Ticket]:
    if not reservation_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order must contain at least one reservation item",
        )

    created_tickets: list[Ticket] = []
    for item in reservation_items:
        ev_seat = (
            item.event_seat
            or db.query(EventSeat).filter(EventSeat.id == item.event_seat_id).first()
        )
        if ev_seat is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="EventSeat not found for reservation item",
            )
        ticket = create_ticket_for_order_item(
            db=db,
            order=order,
            event_seat=ev_seat,
            unit_price_kurus=item.unit_price_kurus,
            session_id=session_id,
            max_retries=max_retries,
        )
        created_tickets.append(ticket)

    return created_tickets


def create_ticket_for_purchase(
    db: Session,
    seat: Seat,
    session_id: str,
    max_retries: int = MAX_TICKET_CODE_RETRIES,
) -> Ticket:
    event = resolve_event_for_seat(db=db, seat=seat)
    ev_seat = (
        db.query(EventSeat)
        .filter(
            EventSeat.event_id == event.id,
            EventSeat.seat_id == seat.id,
        )
        .first()
    )
    unit_price = ev_seat.price_kurus if ev_seat is not None else 0
    if ev_seat is not None:
        ev_seat.status = SeatStatus.SOLD

    return _insert_ticket_with_retry(
        db=db,
        event_id=event.id,
        seat_id=seat.id,
        unit_price_kurus=unit_price,
        session_id=session_id,
        order_id=None,
        max_retries=max_retries,
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

    ev_seat = (
        db.query(EventSeat)
        .filter(
            EventSeat.event_id == ticket.event_id,
            EventSeat.seat_id == ticket.seat_id,
        )
        .first()
    )
    category_name = ev_seat.category.name if (ev_seat and ev_seat.category) else None
    effective_seat_status = ev_seat.status if ev_seat is not None else seat.status
    row_lbl = seat.row_label or seat.row
    used_at = ticket.check_in.checked_in_at if ticket.check_in is not None else None

    return TicketResponse(
        id=ticket.id,
        order_id=ticket.order_id,
        ticket_code=ticket.ticket_code,
        event_id=event.id,
        event_name=event.name,
        event_starts_at=event.starts_at,
        hall_id=hall.id,
        hall_name=hall.name,
        seat_id=seat.id,
        seat_row=row_lbl,
        seat_number=seat.number,
        seat_label=f"{row_lbl}{seat.number}",
        category_name=category_name,
        unit_price_kurus=ticket.unit_price_kurus,
        status=ticket.status,
        used_at=used_at,
        seat_status=effective_seat_status,
        created_at=ticket.created_at,
    )
