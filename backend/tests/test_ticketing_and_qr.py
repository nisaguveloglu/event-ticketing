from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
import zlib

import pytest
import segno
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.database import Base, SessionLocal, engine
from app.models.event import Event
from app.models.hall import Hall
from app.models.seat import Seat, SeatStatus
from app.models.seat_lock import SeatLock
from app.models.ticket import Ticket
from app.services.seat_lock_service import purchase_seat
from app.services.ticket_service import generate_ticket_code


def _seed_hall_seat_and_event(session, create_event: bool = True):
    hall = Hall(name="Main Hall")
    session.add(hall)
    session.flush()

    seat = Seat(hall_id=hall.id, row="A", number=1, status=SeatStatus.AVAILABLE)
    session.add(seat)
    session.flush()

    event = None
    if create_event:
        event = Event(
            hall_id=hall.id,
            name="Opening Night Concert",
            starts_at=datetime(2026, 11, 15, 17, 0, tzinfo=timezone.utc),
        )
        session.add(event)
        session.flush()

    session.commit()
    return hall, seat, event


def _load_seed_sql_statements() -> str:
    seed_path = Path(__file__).resolve().parents[2] / "database" / "seed" / "001_main_hall_event_seed.sql"
    raw_sql = seed_path.read_text(encoding="utf-8")
    return "\n".join(
        line for line in raw_sql.splitlines() if not line.strip().startswith("\\")
    )


def _decode_png_qr_modules(png_bytes: bytes) -> list[list[int]]:
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    width = height = bit_depth = color_type = None
    idat_chunks = []
    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset:offset + 4])[0]
        chunk_type = png_bytes[offset + 4:offset + 8]
        chunk_data = png_bytes[offset + 8:offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    assert width is not None and height is not None and width == height
    raw = zlib.decompress(b"".join(idat_chunks))
    assert bit_depth == 1 and color_type == 0
    stride = (width + 7) // 8
    rows = []
    pos = 0
    prev = bytearray(stride)
    for _ in range(height):
        filter_type = raw[pos]
        pos += 1
        scanline = bytearray(raw[pos:pos + stride])
        pos += stride
        if filter_type == 1:
            for i in range(1, stride):
                scanline[i] = (scanline[i] + scanline[i - 1]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                scanline[i] = (scanline[i] + prev[i]) & 0xFF
        prev = scanline
        bits = []
        for x in range(width):
            byte_val = scanline[x // 8]
            bit_val = (byte_val >> (7 - (x % 8))) & 1
            bits.append(bit_val)
        rows.append(bits)
    return rows


def test_isolated_database_guard():
    assert engine.url.database == "cinema_test"
    assert engine.url.database != "cinema"


def test_env_example_loads_cleanly_in_isolated_workdir(tmp_path):
    backend_dir = Path(__file__).resolve().parents[1]
    env_example = backend_dir / ".env.example"
    target_env = tmp_path / ".env"
    target_env.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")

    clean_env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"DATABASE_URL", "TEST_DATABASE_URL"}
    }
    clean_env["PYTHONPATH"] = str(backend_dir)

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.core.config import Settings; s = Settings(); assert bool(s.database_url)",
        ],
        cwd=str(tmp_path),
        env=clean_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_generate_ticket_code_format_and_sample():
    codes = {generate_ticket_code() for _ in range(2000)}
    assert len(codes) == 2000
    for code in codes:
        assert 16 <= len(code) <= 64


def test_successful_purchase_creates_ticket_and_preserves_legacy_contract(client, db_session):
    hall, seat, event = _seed_hall_seat_and_event(db_session, create_event=True)

    lock_res = client.post(f"/seats/{seat.id}/lock", json={"session_id": "buyer-1"})
    assert lock_res.status_code == 200
    assert lock_res.json() == {
        "message": "Seat locked successfully",
        "seat_id": seat.id,
        "status": "LOCKED",
    }

    purchase_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "buyer-1"})
    assert purchase_res.status_code == 200
    body = purchase_res.json()
    assert body["message"] == "Seat purchased successfully"
    assert body["seat_id"] == seat.id
    assert body["status"] == "SOLD"
    assert isinstance(body.get("ticket_code"), str) and len(body["ticket_code"]) >= 16

    db_session.expire_all()
    updated_seat = db_session.query(Seat).filter(Seat.id == seat.id).first()
    assert updated_seat.status == SeatStatus.SOLD
    remaining_lock = db_session.query(SeatLock).filter(SeatLock.seat_id == seat.id).first()
    assert remaining_lock is None

    tickets = db_session.query(Ticket).all()
    assert len(tickets) == 1
    assert tickets[0].ticket_code == body["ticket_code"]
    assert tickets[0].event_id == event.id
    assert tickets[0].seat_id == seat.id
    assert tickets[0].session_id == "buyer-1"
    assert tickets[0].event.hall_id == hall.id


def test_websocket_broadcast_on_purchase_preserves_format(client, db_session):
    _, seat, _ = _seed_hall_seat_and_event(db_session, create_event=True)

    with client.websocket_connect("/ws/seats") as ws:
        lock_res = client.post(f"/seats/{seat.id}/lock", json={"session_id": "ws-user"})
        assert lock_res.status_code == 200
        ws_lock_msg = ws.receive_json()
        assert ws_lock_msg == {"seat_id": seat.id, "status": "LOCKED"}

        purchase_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "ws-user"})
        assert purchase_res.status_code == 200
        ws_purchase_msg = ws.receive_json()
        assert ws_purchase_msg == {"seat_id": seat.id, "status": "SOLD"}

    seats_res = client.get("/seats/")
    assert seats_res.status_code == 200
    assert seats_res.json() == [
        {
            "id": seat.id,
            "hall_id": seat.hall_id,
            "row": "A",
            "number": 1,
            "status": "SOLD",
        }
    ]


def test_purchase_rejected_without_lock_or_with_foreign_lock(client, db_session):
    _, seat, _ = _seed_hall_seat_and_event(db_session, create_event=True)

    no_lock_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "user-a"})
    assert no_lock_res.status_code == 409
    assert db_session.query(Ticket).count() == 0

    client.post(f"/seats/{seat.id}/lock", json={"session_id": "owner-session"})

    foreign_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "intruder-session"})
    assert foreign_res.status_code == 409

    db_session.expire_all()
    assert db_session.query(Ticket).count() == 0
    assert db_session.query(Seat).filter(Seat.id == seat.id).first().status == SeatStatus.LOCKED
    assert db_session.query(SeatLock).filter(SeatLock.seat_id == seat.id).first().session_id == "owner-session"


def test_double_purchase_rejected(client, db_session):
    _, seat, _ = _seed_hall_seat_and_event(db_session, create_event=True)

    client.post(f"/seats/{seat.id}/lock", json={"session_id": "user-1"})
    first_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "user-1"})
    assert first_res.status_code == 200

    second_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "user-1"})
    assert second_res.status_code == 409
    assert second_res.json()["detail"] == "Seat is already sold"
    assert db_session.query(Ticket).count() == 1


def test_composite_unique_constraint_event_seat_at_db_level(db_session):
    _, seat, event = _seed_hall_seat_and_event(db_session, create_event=True)

    t1 = Ticket(ticket_code="CODE_UNIQUE_1", event_id=event.id, seat_id=seat.id, session_id="s1")
    db_session.add(t1)
    db_session.commit()

    t2 = Ticket(ticket_code="CODE_UNIQUE_2", event_id=event.id, seat_id=seat.id, session_id="s2")
    db_session.add(t2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_ticket_code_collision_retries_and_succeeds(client, db_session, monkeypatch):
    hall, seat1, event = _seed_hall_seat_and_event(db_session, create_event=True)
    seat2 = Seat(hall_id=hall.id, row="A", number=2, status=SeatStatus.AVAILABLE)
    db_session.add(seat2)
    db_session.commit()

    existing = Ticket(
        ticket_code="COLLIDING_CODE_XYZ",
        event_id=event.id,
        seat_id=seat1.id,
        session_id="init",
    )
    seat1.status = SeatStatus.SOLD
    db_session.add(existing)
    db_session.commit()

    client.post(f"/seats/{seat2.id}/lock", json={"session_id": "buyer-2"})

    generated_sequence = iter(["COLLIDING_CODE_XYZ", "FRESH_UNIQUE_CODE_999"])
    monkeypatch.setattr(
        "app.services.ticket_service.generate_ticket_code",
        lambda: next(generated_sequence),
    )

    res = client.post(f"/seats/{seat2.id}/purchase", json={"session_id": "buyer-2"})
    assert res.status_code == 200
    assert res.json()["ticket_code"] == "FRESH_UNIQUE_CODE_999"
    assert db_session.query(Ticket).count() == 2


def test_rollback_when_ticket_creation_fails_preserves_lock_and_status(client, db_session, monkeypatch):
    hall, seat1, event = _seed_hall_seat_and_event(db_session, create_event=True)
    seat2 = Seat(hall_id=hall.id, row="A", number=2, status=SeatStatus.AVAILABLE)
    db_session.add(seat2)
    db_session.commit()

    existing = Ticket(
        ticket_code="ALWAYS_COLLIDES",
        event_id=event.id,
        seat_id=seat1.id,
        session_id="init",
    )
    seat1.status = SeatStatus.SOLD
    db_session.add(existing)
    db_session.commit()

    client.post(f"/seats/{seat2.id}/lock", json={"session_id": "buyer-rollback"})

    monkeypatch.setattr(
        "app.services.ticket_service.generate_ticket_code",
        lambda: "ALWAYS_COLLIDES",
    )

    res = client.post(f"/seats/{seat2.id}/purchase", json={"session_id": "buyer-rollback"})
    assert res.status_code == 500

    db_session.expire_all()
    refreshed_seat2 = db_session.query(Seat).filter(Seat.id == seat2.id).first()
    assert refreshed_seat2.status == SeatStatus.LOCKED
    lock_still_there = db_session.query(SeatLock).filter(SeatLock.seat_id == seat2.id).first()
    assert lock_still_there is not None
    assert lock_still_there.session_id == "buyer-rollback"
    assert db_session.query(Ticket).filter(Ticket.seat_id == seat2.id).count() == 0


def test_unrelated_integrity_error_is_not_retried_or_masked_and_rolls_back(db_session, monkeypatch):
    _, seat, _ = _seed_hall_seat_and_event(db_session, create_event=True)
    seat.status = SeatStatus.LOCKED
    db_session.add(SeatLock(seat_id=seat.id, session_id="buyer-notnull"))
    db_session.commit()

    call_count = 0

    def _produce_none_code():
        nonlocal call_count
        call_count += 1
        return None

    monkeypatch.setattr(
        "app.services.ticket_service.generate_ticket_code",
        _produce_none_code,
    )

    with pytest.raises(IntegrityError) as exc_info:
        purchase_seat(db=db_session, seat_id=seat.id, session_id="buyer-notnull")

    assert call_count == 1
    assert getattr(exc_info.value.orig, "pgcode", None) == "23502"

    db_session.expire_all()
    refreshed_seat = db_session.query(Seat).filter(Seat.id == seat.id).first()
    assert refreshed_seat.status == SeatStatus.LOCKED
    remaining_lock = db_session.query(SeatLock).filter(SeatLock.seat_id == seat.id).first()
    assert remaining_lock is not None
    assert remaining_lock.session_id == "buyer-notnull"
    assert db_session.query(Ticket).count() == 0


def test_missing_or_multiple_events_returns_explicit_error_and_rolls_back(client, db_session):
    hall, seat, _ = _seed_hall_seat_and_event(db_session, create_event=False)
    client.post(f"/seats/{seat.id}/lock", json={"session_id": "buyer-event-check"})

    no_event_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "buyer-event-check"})
    assert no_event_res.status_code == 409
    assert "No active event" in no_event_res.json()["detail"]

    db_session.expire_all()
    assert db_session.query(Seat).filter(Seat.id == seat.id).first().status == SeatStatus.LOCKED
    assert db_session.query(SeatLock).filter(SeatLock.seat_id == seat.id).first() is not None

    e1 = Event(hall_id=hall.id, name="Event 1", starts_at=datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc))
    e2 = Event(hall_id=hall.id, name="Event 2", starts_at=datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc))
    db_session.add_all([e1, e2])
    db_session.commit()

    multi_event_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "buyer-event-check"})
    assert multi_event_res.status_code == 409
    assert "Multiple events" in multi_event_res.json()["detail"]

    db_session.expire_all()
    assert db_session.query(Seat).filter(Seat.id == seat.id).first().status == SeatStatus.LOCKED
    assert db_session.query(SeatLock).filter(SeatLock.seat_id == seat.id).first() is not None
    assert db_session.query(Ticket).count() == 0


def test_service_layer_concurrent_purchase_requests_serialized(db_session):
    _, seat, _ = _seed_hall_seat_and_event(db_session, create_event=True)
    seat.status = SeatStatus.LOCKED
    db_session.add(SeatLock(seat_id=seat.id, session_id="concurrent-owner"))
    db_session.commit()
    target_seat_id = seat.id

    barrier = threading.Barrier(2)

    def worker():
        local_db = SessionLocal()
        try:
            barrier.wait(timeout=5)
            result = purchase_seat(db=local_db, seat_id=target_seat_id, session_id="concurrent-owner")
            return ("OK", result["ticket_code"])
        except Exception as exc:
            status_code = getattr(exc, "status_code", 500)
            detail = getattr(exc, "detail", str(exc))
            return ("ERR", status_code, detail)
        finally:
            local_db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker), pool.submit(worker)]
        outcomes = [f.result() for f in futures]

    successes = [o for o in outcomes if o[0] == "OK"]
    errors = [o for o in outcomes if o[0] == "ERR"]

    assert len(successes) == 1
    assert len(errors) == 1
    assert errors[0][1] == 409

    db_session.expire_all()
    assert db_session.query(Ticket).count() == 1
    assert db_session.query(Seat).filter(Seat.id == target_seat_id).first().status == SeatStatus.SOLD
    assert db_session.query(SeatLock).filter(SeatLock.seat_id == target_seat_id).count() == 0


def test_get_ticket_and_qr_endpoints_and_404(client, db_session):
    hall, seat, event = _seed_hall_seat_and_event(db_session, create_event=True)
    client.post(f"/seats/{seat.id}/lock", json={"session_id": "qr-buyer"})
    purchase_res = client.post(f"/seats/{seat.id}/purchase", json={"session_id": "qr-buyer"})
    ticket_code = purchase_res.json()["ticket_code"]

    ticket_res = client.get(f"/tickets/{ticket_code}")
    assert ticket_res.status_code == 200
    t_json = ticket_res.json()
    assert t_json["ticket_code"] == ticket_code
    assert t_json["event_id"] == event.id
    assert t_json["event_name"] == "Opening Night Concert"
    assert t_json["hall_id"] == hall.id
    assert t_json["hall_name"] == "Main Hall"
    assert t_json["seat_id"] == seat.id
    assert t_json["seat_row"] == "A"
    assert t_json["seat_number"] == 1
    assert t_json["seat_status"] == "SOLD"
    assert "session_id" not in t_json

    qr_res = client.get(f"/tickets/{ticket_code}/qr")
    assert qr_res.status_code == 200
    assert qr_res.headers["content-type"] == "image/png"
    png_bytes = qr_res.content
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    decoded_bitmap = _decode_png_qr_modules(png_bytes)
    expected_qr = segno.make_qr(ticket_code)
    scale = 6
    border = 4
    matrix_size = expected_qr.symbol_size(scale=1, border=0)[0]
    assert len(decoded_bitmap) == (matrix_size + 2 * border) * scale
    for r_idx, row in enumerate(expected_qr.matrix):
        for c_idx, module_is_dark in enumerate(row):
            px_y = (r_idx + border) * scale + scale // 2
            px_x = (c_idx + border) * scale + scale // 2
            pixel_bit = decoded_bitmap[px_y][px_x]
            expected_bit = 0 if module_is_dark else 1
            assert pixel_bit == expected_bit

    assert client.get("/tickets/NON_EXISTENT_TICKET_CODE").status_code == 404
    assert client.get("/tickets/NON_EXISTENT_TICKET_CODE/qr").status_code == 404


def test_seed_sql_idempotency_and_preserves_locked_and_sold_records(db_session):
    statements = _load_seed_sql_statements()

    with engine.begin() as conn:
        conn.execute(text(statements))

    db_session.expire_all()
    assert db_session.query(Hall).count() == 1
    assert db_session.query(Seat).count() == 6
    assert db_session.query(Event).count() == 1

    seats_before = db_session.query(Seat).order_by(Seat.number.asc()).all()
    seat_ids_before = [s.id for s in seats_before]
    event_obj = db_session.query(Event).first()

    locked_seat = seats_before[0]
    sold_seat = seats_before[1]
    locked_seat.status = SeatStatus.LOCKED
    sold_seat.status = SeatStatus.SOLD
    db_session.add(SeatLock(seat_id=locked_seat.id, session_id="seed-lock-owner"))
    db_session.add(
        Ticket(
            ticket_code="SEED_PRESERVED_TICKET_1",
            event_id=event_obj.id,
            seat_id=sold_seat.id,
            session_id="seed-ticket-owner",
        )
    )
    db_session.commit()

    with engine.begin() as conn:
        conn.execute(text(statements))

    db_session.expire_all()
    assert db_session.query(Hall).count() == 1
    assert db_session.query(Seat).count() == 6
    assert db_session.query(Event).count() == 1
    assert [s.id for s in db_session.query(Seat).order_by(Seat.number.asc()).all()] == seat_ids_before
    assert db_session.query(Seat).filter(Seat.id == locked_seat.id).first().status == SeatStatus.LOCKED
    assert db_session.query(Seat).filter(Seat.id == sold_seat.id).first().status == SeatStatus.SOLD
    assert db_session.query(SeatLock).filter(SeatLock.seat_id == locked_seat.id).count() == 1
    assert db_session.query(Ticket).filter(Ticket.ticket_code == "SEED_PRESERVED_TICKET_1").count() == 1


def test_seed_sql_rejects_ambiguous_or_incompatible_state_without_persisting_changes(db_session):
    statements = _load_seed_sql_statements()

    h1 = Hall(name="Main Hall")
    h2 = Hall(name="Second Hall")
    db_session.add_all([h1, h2])
    db_session.commit()

    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            conn.execute(text(statements))

    db_session.expire_all()
    assert db_session.query(Hall).count() == 2
    assert db_session.query(Seat).count() == 0
    assert db_session.query(Event).count() == 0

    db_session.query(Hall).filter(Hall.id == h2.id).delete()
    bad_event = Event(
        hall_id=h1.id,
        name="Incompatible Event Name",
        starts_at=datetime(2026, 12, 1, 18, 0, tzinfo=timezone.utc),
    )
    db_session.add(bad_event)
    db_session.commit()

    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            conn.execute(text(statements))

    db_session.expire_all()
    assert db_session.query(Hall).count() == 1
    assert db_session.query(Seat).count() == 0
    assert db_session.query(Event).count() == 1
    assert db_session.query(Event).first().name == "Incompatible Event Name"


def test_orm_and_sql_schema_alignment_in_isolated_schemas():
    root_dir = Path(__file__).resolve().parents[2]
    current_schema_sql = (root_dir / "database" / "schema" / "current_schema.sql").read_text(encoding="utf-8")

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS test_orm_schema CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS test_sql_schema CASCADE"))
        conn.execute(text("CREATE SCHEMA test_orm_schema"))
        conn.execute(text("CREATE SCHEMA test_sql_schema"))

    try:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL search_path TO test_orm_schema, public"))
            translated_conn = conn.execution_options(
                schema_translate_map={None: "test_orm_schema"}
            )
            Base.metadata.create_all(bind=translated_conn)

        with engine.begin() as conn:
            conn.execute(text("SET LOCAL search_path TO test_sql_schema, public"))
            conn.execute(text(current_schema_sql))

        col_query = text(
            """
            SELECT table_name, column_name, data_type, udt_name, is_nullable,
                   CASE
                       WHEN column_default LIKE 'nextval(%' THEN 'SERIAL_SEQ'
                       ELSE COALESCE(column_default, 'NONE')
                   END AS norm_default
            FROM information_schema.columns
            WHERE table_schema = :schema_name
            ORDER BY table_name, ordinal_position
            """
        )

        idx_query = text(
            """
            SELECT tablename, indexname,
                   regexp_replace(indexdef, ' test_(orm|sql)_schema\\.', ' ', 'g') AS norm_indexdef
            FROM pg_indexes
            WHERE schemaname = :schema_name
            ORDER BY tablename, indexname
            """
        )

        with engine.connect() as conn:
            orm_cols = conn.execute(col_query, {"schema_name": "test_orm_schema"}).fetchall()
            sql_cols = conn.execute(col_query, {"schema_name": "test_sql_schema"}).fetchall()
            orm_idxs = conn.execute(idx_query, {"schema_name": "test_orm_schema"}).fetchall()
            sql_idxs = conn.execute(idx_query, {"schema_name": "test_sql_schema"}).fetchall()

        assert orm_cols == sql_cols
        assert orm_idxs == sql_idxs

        seats_status_col = [
            c for c in sql_cols if c[0] == "seats" and c[1] == "status"
        ][0]
        assert seats_status_col[5] == "NONE"

        ticket_code_indexes = [
            i[1] for i in sql_idxs if i[0] == "tickets" and "ticket_code" in i[2]
        ]
        assert ticket_code_indexes == ["ix_tickets_ticket_code"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS test_orm_schema CASCADE"))
            conn.execute(text("DROP SCHEMA IF EXISTS test_sql_schema CASCADE"))
