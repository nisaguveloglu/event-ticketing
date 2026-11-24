from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal, engine
from app.models.check_in import CheckIn
from app.models.email_delivery import EmailDelivery, EmailDeliveryStatus
from app.models.event import Event
from app.models.event_seat import EventSeat
from app.models.guest_session import GuestSession
from app.models.hall import Hall
from app.models.order import Order
from app.models.reservation import Reservation, ReservationStatus
from app.models.reservation_item import ReservationItem
from app.models.seat import Seat, SeatStatus
from app.models.seat_segment import SeatSegment
from app.models.ticket import Ticket, TicketStatus
from app.services.checkin_service import (
    CheckInConflictError,
    verify_and_check_in_ticket,
)
from app.services.email_service import (
    EmailDeliveryError,
    enqueue_order_email_in_transaction,
    list_order_email_deliveries,
    process_pending_email_deliveries,
    request_order_email_delivery,
)
from app.services.pdf_service import (
    decode_qr_from_png_bytes,
    extract_and_decode_qrs_from_pdf_bytes,
    generate_order_tickets_pdf,
)
from app.services.qr_service import generate_ticket_qr_png
from app.services.seed_service import run_s1_demo_seed
from app.services.ticket_service import (
    create_ticket_for_order_item,
    create_tickets_for_order,
)


def _create_order_for_event_seats(
    session,
    event: Event,
    event_seats: list[EventSeat],
    token_hash_seed: str = "test-guest-token",
    recipient_email: str | None = None,
) -> tuple[Order, list[Ticket]]:
    now_utc = datetime.now(timezone.utc)
    gs = GuestSession(
        token_hash=f"{token_hash_seed}-{now_utc.timestamp()}".ljust(64, "0")[:64],
        expires_at=now_utc + timedelta(hours=24),
    )
    session.add(gs)
    session.flush()

    res = Reservation(
        event_id=event.id,
        guest_session_id=gs.id,
        status=ReservationStatus.PURCHASED.value,
        created_at=now_utc,
        expires_at=now_utc + timedelta(seconds=300),
    )
    session.add(res)
    session.flush()

    items: list[ReservationItem] = []
    total_kurus = 0
    for es in event_seats:
        ri = ReservationItem(
            reservation_id=res.id,
            event_seat_id=es.id,
            unit_price_kurus=es.price_kurus,
        )
        session.add(ri)
        items.append(ri)
        total_kurus += es.price_kurus
    session.flush()

    order = Order(
        reservation_id=res.id,
        guest_session_id=gs.id,
        total_price_kurus=total_kurus,
        currency="TRY",
        created_at=now_utc,
    )
    session.add(order)
    session.flush()

    tickets = create_tickets_for_order(
        db=session,
        order=order,
        reservation_items=items,
        session_id=f"g:{gs.id}",
    )

    if recipient_email:
        enqueue_order_email_in_transaction(
            db=session,
            order_id=order.id,
            recipient=recipient_email,
            now_utc=now_utc,
        )

    session.commit()
    return order, tickets


def test_t02_fresh_and_upgrade_migration_preserves_legacy_tickets():
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS test_m2_mig CASCADE"))
        conn.execute(text("CREATE SCHEMA test_m2_mig"))

    try:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL search_path TO test_m2_mig, public"))
            conn.execute(
                text(
                    "CREATE TABLE test_m2_mig.alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            alembic_cfg.attributes["connection"] = conn
            command.upgrade(alembic_cfg, "001_baseline")

            conn.execute(
                text(
                    """
                    INSERT INTO halls (id, name) VALUES (1, 'Main Hall');
                    INSERT INTO seats (id, hall_id, row, number, status)
                    VALUES (5, 1, 'A', 2, 'SOLD'::seatstatus),
                           (6, 1, 'A', 5, 'AVAILABLE'::seatstatus);
                    INSERT INTO events (id, hall_id, name, starts_at)
                    VALUES (1, 1, 'Opening Night Concert', '2026-11-15 17:00:00+00');
                    INSERT INTO tickets (id, ticket_code, event_id, seat_id, session_id, created_at)
                    VALUES (1, 'PBVG1sWVG7YgwHdKgBM94w', 1, 5, 'member3-demo', '2026-10-19 11:51:28+00');
                    """
                )
            )

            command.upgrade(alembic_cfg, "002_s1_schema")

            upgraded_ticket = conn.execute(
                text(
                    """
                    SELECT t.ticket_code, t.order_id, t.unit_price_kurus, t.status, es.status
                    FROM tickets t
                    JOIN event_seats es ON es.event_id = t.event_id AND es.seat_id = t.seat_id
                    WHERE t.id = 1
                    """
                )
            ).fetchone()

            assert upgraded_ticket is not None
            assert upgraded_ticket[0] == "PBVG1sWVG7YgwHdKgBM94w"
            assert upgraded_ticket[1] is not None
            assert upgraded_ticket[2] == 50000
            assert upgraded_ticket[3] == "VALID"
            assert upgraded_ticket[4] == "SOLD"

            other_es = conn.execute(
                text("SELECT status FROM event_seats WHERE event_id = 1 AND seat_id = 6")
            ).scalar_one()
            assert other_es == "AVAILABLE"
    finally:
        alembic_cfg.attributes.pop("connection", None)
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS test_m2_mig CASCADE"))


def test_t03_same_hall_two_events_independent_seat_occupancy(db_session):
    run_s1_demo_seed(engine)
    db_session.expire_all()

    main_hall = db_session.query(Hall).filter(Hall.name == "Main Hall").first()
    studio_hall = db_session.query(Hall).filter(Hall.name == "Studio Hall").first()
    assert main_hall is not None and studio_hall is not None

    main_seats = db_session.query(Seat).filter(Seat.hall_id == main_hall.id).all()
    studio_seats = db_session.query(Seat).filter(Seat.hall_id == studio_hall.id).all()
    assert len(main_seats) == 40
    assert len(studio_seats) == 24

    seat_a1 = (
        db_session.query(Seat)
        .filter(Seat.hall_id == main_hall.id, Seat.row_label == "A", Seat.number == 1)
        .first()
    )
    assert seat_a1 is not None
    assert seat_a1.is_accessible is True
    seg_a1 = db_session.query(SeatSegment).filter(SeatSegment.id == seat_a1.segment_id).first()
    assert seg_a1 is not None and seg_a1.orphan_exempt is True

    main_events = (
        db_session.query(Event)
        .filter(Event.hall_id == main_hall.id)
        .order_by(Event.id.asc())
        .all()
    )
    assert len(main_events) == 2
    ev1, ev2 = main_events[0], main_events[1]

    es_ev1_a1 = (
        db_session.query(EventSeat)
        .filter(EventSeat.event_id == ev1.id, EventSeat.seat_id == seat_a1.id)
        .first()
    )
    es_ev2_a1 = (
        db_session.query(EventSeat)
        .filter(EventSeat.event_id == ev2.id, EventSeat.seat_id == seat_a1.id)
        .first()
    )
    assert es_ev1_a1.status == SeatStatus.AVAILABLE
    assert es_ev2_a1.status == SeatStatus.AVAILABLE
    assert es_ev1_a1.price_kurus == 50000
    assert es_ev2_a1.price_kurus == 50000

    _, tickets_ev1 = _create_order_for_event_seats(
        db_session,
        ev1,
        [es_ev1_a1],
        token_hash_seed="t03-ev1",
    )
    assert len(tickets_ev1) == 1

    db_session.expire_all()
    assert (
        db_session.query(EventSeat)
        .filter(EventSeat.id == es_ev1_a1.id)
        .first()
        .status
        == SeatStatus.SOLD
    )
    assert (
        db_session.query(EventSeat)
        .filter(EventSeat.id == es_ev2_a1.id)
        .first()
        .status
        == SeatStatus.AVAILABLE
    )

    _, tickets_ev2 = _create_order_for_event_seats(
        db_session,
        ev2,
        [es_ev2_a1],
        token_hash_seed="t03-ev2",
    )
    assert len(tickets_ev2) == 1
    assert tickets_ev1[0].ticket_code != tickets_ev2[0].ticket_code


def test_t14_order_ticket_code_collision_retries_and_unmasked_error(db_session, monkeypatch):
    run_s1_demo_seed(engine)
    db_session.expire_all()

    ev = db_session.query(Event).order_by(Event.id.asc()).first()
    ev_seats = (
        db_session.query(EventSeat)
        .filter(EventSeat.event_id == ev.id)
        .order_by(EventSeat.id.asc())
        .limit(3)
        .all()
    )

    _, first_tickets = _create_order_for_event_seats(
        db_session,
        ev,
        [ev_seats[0]],
        token_hash_seed="t14-first",
    )
    existing_code = first_tickets[0].ticket_code

    seq = iter([existing_code, "RETRY_SUCCEEDED_CODE_S1"])
    monkeypatch.setattr(
        "app.services.ticket_service.generate_ticket_code",
        lambda: next(seq),
    )

    _, second_tickets = _create_order_for_event_seats(
        db_session,
        ev,
        [ev_seats[1]],
        token_hash_seed="t14-second",
    )
    assert second_tickets[0].ticket_code == "RETRY_SUCCEEDED_CODE_S1"

    call_count = 0

    def _none_code():
        nonlocal call_count
        call_count += 1
        return None

    monkeypatch.setattr("app.services.ticket_service.generate_ticket_code", _none_code)

    order_obj = db_session.query(Order).first()
    with pytest.raises(IntegrityError) as exc_info:
        create_ticket_for_order_item(
            db=db_session,
            order=order_obj,
            event_seat=ev_seats[2],
        )
    db_session.rollback()
    assert call_count == 1
    assert getattr(exc_info.value.orig, "pgcode", None) == "23502"


def test_t23_qr_decoded_independently_from_png_and_multi_ticket_pdf(db_session):
    run_s1_demo_seed(engine)
    db_session.expire_all()

    ev = db_session.query(Event).order_by(Event.id.asc()).first()
    ev.name = "Açılış Gecesi Gösterisi — Şişli & Çağlayan"
    db_session.commit()

    ev_seats = (
        db_session.query(EventSeat)
        .filter(EventSeat.event_id == ev.id)
        .order_by(EventSeat.id.asc())
        .limit(3)
        .all()
    )

    order, tickets = _create_order_for_event_seats(
        db_session,
        ev,
        ev_seats,
        token_hash_seed="t23-multi",
    )
    assert len(tickets) == 3
    expected_codes = [t.ticket_code for t in tickets]

    for code in expected_codes:
        png_bytes = generate_ticket_qr_png(code)
        decoded_from_png = decode_qr_from_png_bytes(png_bytes)
        assert decoded_from_png == code

    pdf_bytes = generate_order_tickets_pdf(db=db_session, order_id=order.id)
    assert pdf_bytes.startswith(b"%PDF-")

    decoded_from_pdf = extract_and_decode_qrs_from_pdf_bytes(pdf_bytes)
    assert decoded_from_pdf == expected_codes


def test_t24_check_in_distinguishes_valid_used_fake_and_wrong_event(db_session):
    run_s1_demo_seed(engine)
    db_session.expire_all()

    events = db_session.query(Event).order_by(Event.id.asc()).all()
    ev1, ev2 = events[0], events[1]
    es1 = (
        db_session.query(EventSeat)
        .filter(EventSeat.event_id == ev1.id)
        .order_by(EventSeat.id.asc())
        .first()
    )

    _, tickets = _create_order_for_event_seats(
        db_session,
        ev1,
        [es1],
        token_hash_seed="t24-checkin",
    )
    ticket = tickets[0]

    with pytest.raises(CheckInConflictError) as fake_exc:
        verify_and_check_in_ticket(
            db=db_session,
            event_id=ev1.id,
            ticket_code="FAKE_UNKNOWN_CODE_999",
        )
    assert fake_exc.value.status_code == 404
    assert fake_exc.value.code == "TICKET_NOT_FOUND"

    with pytest.raises(CheckInConflictError) as wrong_ev_exc:
        verify_and_check_in_ticket(
            db=db_session,
            event_id=ev2.id,
            ticket_code=ticket.ticket_code,
        )
    assert wrong_ev_exc.value.status_code == 409
    assert wrong_ev_exc.value.code == "WRONG_EVENT"

    db_session.expire_all()
    assert db_session.query(Ticket).filter(Ticket.id == ticket.id).first().status == TicketStatus.VALID.value

    accepted_res = verify_and_check_in_ticket(
        db=db_session,
        event_id=ev1.id,
        ticket_code=ticket.ticket_code,
        staff_label="gate-staff-1",
    )
    assert accepted_res.result == "ACCEPTED"
    assert accepted_res.ticket_code == ticket.ticket_code

    db_session.expire_all()
    assert db_session.query(Ticket).filter(Ticket.id == ticket.id).first().status == TicketStatus.USED.value
    assert db_session.query(CheckIn).filter(CheckIn.ticket_id == ticket.id).count() == 1

    with pytest.raises(CheckInConflictError) as used_exc:
        verify_and_check_in_ticket(
            db=db_session,
            event_id=ev1.id,
            ticket_code=ticket.ticket_code,
        )
    assert used_exc.value.status_code == 409
    assert used_exc.value.code == "TICKET_ALREADY_USED"
    assert used_exc.value.checked_in_at == accepted_res.checked_in_at


def test_t25_concurrent_check_in_accepts_exactly_one(db_session):
    run_s1_demo_seed(engine)
    db_session.expire_all()

    ev = db_session.query(Event).order_by(Event.id.asc()).first()
    es = (
        db_session.query(EventSeat)
        .filter(EventSeat.event_id == ev.id)
        .order_by(EventSeat.id.asc())
        .first()
    )

    _, tickets = _create_order_for_event_seats(
        db_session,
        ev,
        [es],
        token_hash_seed="t25-concurrent-ci",
    )
    target_code = tickets[0].ticket_code
    target_ticket_id = tickets[0].id
    target_event_id = ev.id

    barrier = threading.Barrier(2)

    def _scanner_worker(scanner_name: str):
        local_db = SessionLocal()
        try:
            barrier.wait(timeout=5)
            res = verify_and_check_in_ticket(
                db=local_db,
                event_id=target_event_id,
                ticket_code=target_code,
                staff_label=scanner_name,
            )
            return ("ACCEPTED", res.checked_in_at)
        except CheckInConflictError as exc:
            return ("REJECTED", exc.status_code, exc.code)
        finally:
            local_db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_scanner_worker, "scanner-1"),
            pool.submit(_scanner_worker, "scanner-2"),
        ]
        results = [f.result() for f in futures]

    accepted = [r for r in results if r[0] == "ACCEPTED"]
    rejected = [r for r in results if r[0] == "REJECTED"]

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert rejected[0][1] == 409
    assert rejected[0][2] == "TICKET_ALREADY_USED"

    db_session.expire_all()
    assert db_session.query(CheckIn).filter(CheckIn.ticket_id == target_ticket_id).count() == 1
    assert (
        db_session.query(Ticket).filter(Ticket.id == target_ticket_id).first().status
        == TicketStatus.USED.value
    )


def test_t27_email_delivery_failure_retries_without_breaking_sale_or_duplicating_tickets(db_session):
    run_s1_demo_seed(engine)
    db_session.expire_all()

    ev = db_session.query(Event).order_by(Event.id.asc()).first()
    ev_seats = (
        db_session.query(EventSeat)
        .filter(EventSeat.event_id == ev.id)
        .order_by(EventSeat.id.asc())
        .limit(2)
        .all()
    )

    order, tickets = _create_order_for_event_seats(
        db_session,
        ev,
        ev_seats,
        token_hash_seed="t27-email",
        recipient_email="Buyer@Example.com",
    )
    assert len(tickets) == 2

    deliveries = list_order_email_deliveries(db_session, order.id)
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.recipient == "buyer@example.com"
    assert delivery.status == EmailDeliveryStatus.PENDING.value

    base_time = delivery.created_at

    def _failing_sender(recipient, subject, body, pdf_bytes, ord_id):
        raise ConnectionError("Simulated SMTP outage")

    process_pending_email_deliveries(
        db=db_session,
        send_fn=_failing_sender,
        now_utc=base_time,
    )
    db_session.refresh(delivery)
    assert delivery.attempts == 1
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert delivery.next_attempt_at == base_time + timedelta(seconds=10)
    assert "Simulated SMTP outage" in (delivery.last_error or "")

    process_pending_email_deliveries(
        db=db_session,
        send_fn=_failing_sender,
        now_utc=base_time + timedelta(seconds=10),
    )
    db_session.refresh(delivery)
    assert delivery.attempts == 2
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert delivery.next_attempt_at == base_time + timedelta(seconds=40)

    process_pending_email_deliveries(
        db=db_session,
        send_fn=_failing_sender,
        now_utc=base_time + timedelta(seconds=40),
    )
    db_session.refresh(delivery)
    assert delivery.attempts == 3
    assert delivery.status == EmailDeliveryStatus.FAILED.value
    assert delivery.next_attempt_at is None

    db_session.expire_all()
    assert db_session.query(Ticket).filter(Ticket.order_id == order.id).count() == 2
    for es in ev_seats:
        assert (
            db_session.query(EventSeat).filter(EventSeat.id == es.id).first().status
            == SeatStatus.SOLD
        )

    with pytest.raises(EmailDeliveryError) as rate_exc:
        request_order_email_delivery(
            db=db_session,
            order_id=order.id,
            recipient="buyer@example.com",
            now_utc=base_time + timedelta(seconds=30),
        )
    assert rate_exc.value.status_code == 429
    assert rate_exc.value.code == "RATE_LIMITED"

    retry_delivery = request_order_email_delivery(
        db=db_session,
        order_id=order.id,
        recipient="buyer@example.com",
        now_utc=base_time + timedelta(seconds=65),
    )
    assert retry_delivery.id != delivery.id
    assert retry_delivery.status == EmailDeliveryStatus.PENDING.value

    sent_attachments: list[bytes] = []

    def _success_sender(recipient, subject, body, pdf_bytes, ord_id):
        sent_attachments.append(pdf_bytes)

    process_pending_email_deliveries(
        db=db_session,
        send_fn=_success_sender,
        now_utc=base_time + timedelta(seconds=66),
    )
    db_session.refresh(retry_delivery)
    assert retry_delivery.status == EmailDeliveryStatus.SENT.value
    assert retry_delivery.attempts == 1
    assert retry_delivery.sent_at is not None
    assert len(sent_attachments) == 1
    assert extract_and_decode_qrs_from_pdf_bytes(sent_attachments[0]) == [
        t.ticket_code for t in tickets
    ]
    assert db_session.query(Ticket).filter(Ticket.order_id == order.id).count() == 2
