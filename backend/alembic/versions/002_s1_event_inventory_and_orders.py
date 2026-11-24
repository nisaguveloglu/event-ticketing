from datetime import datetime, timedelta, timezone
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_s1_schema"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _row_order_for_label(label: str) -> int:
    clean = (label or "A").strip().upper()
    if len(clean) == 1 and "A" <= clean <= "Z":
        return ord(clean) - ord("A") + 1
    return 1


def upgrade() -> None:
    bind = op.get_bind()

    mismatched_tickets = bind.execute(
        sa.text(
            """
            SELECT t.id, t.ticket_code, t.event_id, t.seat_id
            FROM tickets t
            LEFT JOIN events e ON e.id = t.event_id
            LEFT JOIN seats s ON s.id = t.seat_id
            WHERE e.id IS NULL OR s.id IS NULL OR e.hall_id <> s.hall_id
            """
        )
    ).fetchall()

    if mismatched_tickets:
        raise RuntimeError(
            f"Migration aborted: ambiguous or mismatched event/seat relationship on tickets: {mismatched_tickets}"
        )

    bind.execute(
        sa.text(
            """
            ALTER TABLE halls ADD COLUMN IF NOT EXISTS stage_x INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE halls ADD COLUMN IF NOT EXISTS stage_y INTEGER NOT NULL DEFAULT 0;

            CREATE TABLE IF NOT EXISTS seat_segments (
                id SERIAL PRIMARY KEY,
                hall_id INTEGER NOT NULL REFERENCES halls(id),
                row_label VARCHAR(10) NOT NULL,
                orphan_exempt BOOLEAN NOT NULL DEFAULT FALSE
            );
            CREATE INDEX IF NOT EXISTS ix_seat_segments_id ON seat_segments (id);

            ALTER TABLE seats ADD COLUMN IF NOT EXISTS row_label VARCHAR(10) NOT NULL DEFAULT 'A';
            ALTER TABLE seats ADD COLUMN IF NOT EXISTS row_order INTEGER NOT NULL DEFAULT 1;
            ALTER TABLE seats ADD COLUMN IF NOT EXISTS segment_id INTEGER REFERENCES seat_segments(id);
            ALTER TABLE seats ADD COLUMN IF NOT EXISTS x INTEGER NOT NULL DEFAULT 1;
            ALTER TABLE seats ADD COLUMN IF NOT EXISTS y INTEGER NOT NULL DEFAULT 1;
            ALTER TABLE seats ADD COLUMN IF NOT EXISTS is_accessible BOOLEAN NOT NULL DEFAULT FALSE;

            ALTER TABLE events ADD COLUMN IF NOT EXISTS sales_open BOOLEAN NOT NULL DEFAULT TRUE;
            ALTER TABLE events ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

            CREATE TABLE IF NOT EXISTS ticket_categories (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id),
                name VARCHAR(100) NOT NULL,
                price_kurus INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_ticket_categories_id ON ticket_categories (id);

            CREATE TABLE IF NOT EXISTS guest_sessions (
                id SERIAL PRIMARY KEY,
                token_hash VARCHAR(64) NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_guest_sessions_id ON guest_sessions (id);
            CREATE UNIQUE INDEX IF NOT EXISTS ix_guest_sessions_token_hash ON guest_sessions (token_hash);

            CREATE TABLE IF NOT EXISTS reservations (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id),
                guest_session_id INTEGER NOT NULL REFERENCES guest_sessions(id),
                status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_reservations_id ON reservations (id);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_reservations_active_guest_session
                ON reservations (guest_session_id)
                WHERE status = 'ACTIVE';

            CREATE TABLE IF NOT EXISTS event_seats (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id),
                seat_id INTEGER NOT NULL REFERENCES seats(id),
                category_id INTEGER NOT NULL REFERENCES ticket_categories(id),
                price_kurus INTEGER NOT NULL,
                status seatstatus NOT NULL,
                current_reservation_id INTEGER REFERENCES reservations(id),
                CONSTRAINT uq_event_seats_event_seat UNIQUE (event_id, seat_id)
            );
            CREATE INDEX IF NOT EXISTS ix_event_seats_id ON event_seats (id);

            CREATE TABLE IF NOT EXISTS reservation_items (
                id SERIAL PRIMARY KEY,
                reservation_id INTEGER NOT NULL REFERENCES reservations(id),
                event_seat_id INTEGER NOT NULL REFERENCES event_seats(id),
                unit_price_kurus INTEGER NOT NULL,
                CONSTRAINT uq_reservation_items_res_event_seat UNIQUE (reservation_id, event_seat_id)
            );
            CREATE INDEX IF NOT EXISTS ix_reservation_items_id ON reservation_items (id);

            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                reservation_id INTEGER NOT NULL UNIQUE REFERENCES reservations(id),
                guest_session_id INTEGER NOT NULL REFERENCES guest_sessions(id),
                total_price_kurus INTEGER NOT NULL,
                currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS ix_orders_id ON orders (id);

            ALTER TABLE tickets ADD COLUMN IF NOT EXISTS order_id INTEGER REFERENCES orders(id);
            ALTER TABLE tickets ADD COLUMN IF NOT EXISTS unit_price_kurus INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE tickets ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'VALID';

            CREATE TABLE IF NOT EXISTS check_ins (
                id SERIAL PRIMARY KEY,
                ticket_id INTEGER NOT NULL UNIQUE REFERENCES tickets(id),
                checked_in_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                staff_label VARCHAR(100) NOT NULL DEFAULT 'staff'
            );
            CREATE INDEX IF NOT EXISTS ix_check_ins_id ON check_ins (id);

            CREATE TABLE IF NOT EXISTS email_deliveries (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                recipient VARCHAR(255) NOT NULL,
                purpose VARCHAR(50) NOT NULL DEFAULT 'ORDER_TICKETS',
                status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TIMESTAMPTZ,
                last_error TEXT,
                sent_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS ix_email_deliveries_id ON email_deliveries (id);

            CREATE TABLE IF NOT EXISTS idempotency_records (
                id SERIAL PRIMARY KEY,
                owner_key VARCHAR(100) NOT NULL,
                key VARCHAR(100) NOT NULL,
                request_hash VARCHAR(64) NOT NULL,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_idempotency_owner_key UNIQUE (owner_key, key)
            );
            CREATE INDEX IF NOT EXISTS ix_idempotency_records_id ON idempotency_records (id);
            """
        )
    )

    existing_seats = bind.execute(
        sa.text("SELECT id, hall_id, row, number, segment_id FROM seats ORDER BY id ASC")
    ).fetchall()

    for seat_row in existing_seats:
        seat_id, hall_id, r_label, s_number, seg_id = seat_row
        r_order = _row_order_for_label(r_label)
        is_acc = bool(r_label == "A" and s_number == 1)
        x_coord = s_number if s_number <= 5 else s_number + 1
        y_coord = r_order

        if seg_id is None:
            if is_acc:
                existing_seg = bind.execute(
                    sa.text(
                        """
                        SELECT id FROM seat_segments
                        WHERE hall_id = :hid AND row_label = :rl AND orphan_exempt = TRUE
                        ORDER BY id ASC LIMIT 1
                        """
                    ),
                    {"hid": hall_id, "rl": r_label},
                ).fetchone()
                if existing_seg:
                    seg_id = existing_seg[0]
                else:
                    seg_id = bind.execute(
                        sa.text(
                            """
                            INSERT INTO seat_segments (hall_id, row_label, orphan_exempt)
                            VALUES (:hid, :rl, TRUE) RETURNING id
                            """
                        ),
                        {"hid": hall_id, "rl": r_label},
                    ).scalar_one()
            else:
                non_exempt_segs = bind.execute(
                    sa.text(
                        """
                        SELECT id FROM seat_segments
                        WHERE hall_id = :hid AND row_label = :rl AND orphan_exempt = FALSE
                        ORDER BY id ASC
                        """
                    ),
                    {"hid": hall_id, "rl": r_label},
                ).fetchall()
                if len(non_exempt_segs) < 2:
                    while len(non_exempt_segs) < 2:
                        new_seg_id = bind.execute(
                            sa.text(
                                """
                                INSERT INTO seat_segments (hall_id, row_label, orphan_exempt)
                                VALUES (:hid, :rl, FALSE) RETURNING id
                                """
                            ),
                            {"hid": hall_id, "rl": r_label},
                        ).scalar_one()
                        non_exempt_segs.append((new_seg_id,))
                seg_id = non_exempt_segs[0][0] if s_number <= 5 else non_exempt_segs[1][0]

        bind.execute(
            sa.text(
                """
                UPDATE seats
                SET row_label = :rl,
                    row_order = :ro,
                    segment_id = :sid,
                    x = :x,
                    y = :y,
                    is_accessible = :acc
                WHERE id = :id
                """
            ),
            {
                "rl": r_label,
                "ro": r_order,
                "sid": seg_id,
                "x": x_coord,
                "y": y_coord,
                "acc": is_acc,
                "id": seat_id,
            },
        )

    events = bind.execute(
        sa.text(
            """
            SELECT e.id, e.hall_id, h.name AS hall_name
            FROM events e
            JOIN halls h ON h.id = e.hall_id
            ORDER BY e.id ASC
            """
        )
    ).fetchall()

    for ev_id, ev_hall_id, hall_name in events:
        if hall_name == "Studio Hall":
            std_cat = bind.execute(
                sa.text(
                    "SELECT id, price_kurus FROM ticket_categories WHERE event_id = :eid AND name = 'Standard' LIMIT 1"
                ),
                {"eid": ev_id},
            ).fetchone()
            if not std_cat:
                std_cat_id = bind.execute(
                    sa.text(
                        "INSERT INTO ticket_categories (event_id, name, price_kurus) VALUES (:eid, 'Standard', 25000) RETURNING id"
                    ),
                    {"eid": ev_id},
                ).scalar_one()
                std_price = 25000
            else:
                std_cat_id, std_price = std_cat[0], std_cat[1]
            prem_cat_id, prem_price = std_cat_id, std_price
        else:
            prem_cat = bind.execute(
                sa.text(
                    "SELECT id, price_kurus FROM ticket_categories WHERE event_id = :eid AND name = 'Premium' LIMIT 1"
                ),
                {"eid": ev_id},
            ).fetchone()
            if not prem_cat:
                prem_cat_id = bind.execute(
                    sa.text(
                        "INSERT INTO ticket_categories (event_id, name, price_kurus) VALUES (:eid, 'Premium', 50000) RETURNING id"
                    ),
                    {"eid": ev_id},
                ).scalar_one()
                prem_price = 50000
            else:
                prem_cat_id, prem_price = prem_cat[0], prem_cat[1]

            std_cat = bind.execute(
                sa.text(
                    "SELECT id, price_kurus FROM ticket_categories WHERE event_id = :eid AND name = 'Standard' LIMIT 1"
                ),
                {"eid": ev_id},
            ).fetchone()
            if not std_cat:
                std_cat_id = bind.execute(
                    sa.text(
                        "INSERT INTO ticket_categories (event_id, name, price_kurus) VALUES (:eid, 'Standard', 30000) RETURNING id"
                    ),
                    {"eid": ev_id},
                ).scalar_one()
                std_price = 30000
            else:
                std_cat_id, std_price = std_cat[0], std_cat[1]

        hall_seats = bind.execute(
            sa.text("SELECT id, row_order FROM seats WHERE hall_id = :hid ORDER BY id ASC"),
            {"hid": ev_hall_id},
        ).fetchall()

        for s_id, r_ord in hall_seats:
            exists_es = bind.execute(
                sa.text("SELECT id FROM event_seats WHERE event_id = :eid AND seat_id = :sid"),
                {"eid": ev_id, "sid": s_id},
            ).fetchone()
            if not exists_es:
                cat_id = prem_cat_id if (hall_name != "Studio Hall" and r_ord <= 2) else std_cat_id
                p_kurus = prem_price if (hall_name != "Studio Hall" and r_ord <= 2) else std_price
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO event_seats (event_id, seat_id, category_id, price_kurus, status)
                        VALUES (:eid, :sid, :cid, :pk, 'AVAILABLE'::seatstatus)
                        """
                    ),
                    {"eid": ev_id, "sid": s_id, "cid": cat_id, "pk": p_kurus},
                )

    legacy_tickets = bind.execute(
        sa.text(
            """
            SELECT id, ticket_code, event_id, seat_id, session_id, created_at, order_id, unit_price_kurus
            FROM tickets
            ORDER BY id ASC
            """
        )
    ).fetchall()

    for t_row in legacy_tickets:
        t_id, t_code, t_event_id, t_seat_id, t_sess, t_created, t_order_id, t_price = t_row
        es_row = bind.execute(
            sa.text(
                "SELECT id, price_kurus FROM event_seats WHERE event_id = :eid AND seat_id = :sid"
            ),
            {"eid": t_event_id, "sid": t_seat_id},
        ).fetchone()
        if not es_row:
            raise RuntimeError(
                f"Migration aborted: missing event_seat for ticket id={t_id}, event_id={t_event_id}, seat_id={t_seat_id}"
            )
        es_id, es_price = es_row[0], es_row[1]

        bind.execute(
            sa.text("UPDATE event_seats SET status = 'SOLD'::seatstatus WHERE id = :esid"),
            {"esid": es_id},
        )

        if t_order_id is None:
            token_hash = hashlib.sha256(f"legacy-ticket-{t_id}-{t_code}".encode("utf-8")).hexdigest()
            created_ts = t_created if t_created is not None else datetime.now(timezone.utc)
            expires_ts = created_ts + timedelta(minutes=5)

            gs_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO guest_sessions (token_hash, expires_at)
                    VALUES (:th, :exp)
                    RETURNING id
                    """
                ),
                {"th": token_hash, "exp": expires_ts},
            ).scalar_one()

            res_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO reservations (event_id, guest_session_id, status, created_at, expires_at)
                    VALUES (:eid, :gsid, 'PURCHASED', :cat, :exp)
                    RETURNING id
                    """
                ),
                {"eid": t_event_id, "gsid": gs_id, "cat": created_ts, "exp": expires_ts},
            ).scalar_one()

            bind.execute(
                sa.text(
                    """
                    INSERT INTO reservation_items (reservation_id, event_seat_id, unit_price_kurus)
                    VALUES (:rid, :esid, :pk)
                    """
                ),
                {"rid": res_id, "esid": es_id, "pk": es_price},
            )

            ord_id = bind.execute(
                sa.text(
                    """
                    INSERT INTO orders (reservation_id, guest_session_id, total_price_kurus, currency, created_at)
                    VALUES (:rid, :gsid, :tot, 'TRY', :cat)
                    RETURNING id
                    """
                ),
                {"rid": res_id, "gsid": gs_id, "tot": es_price, "cat": created_ts},
            ).scalar_one()

            bind.execute(
                sa.text(
                    """
                    UPDATE tickets
                    SET order_id = :oid,
                        unit_price_kurus = :pk,
                        status = COALESCE(status, 'VALID')
                    WHERE id = :tid
                    """
                ),
                {"oid": ord_id, "pk": es_price, "tid": t_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DROP TABLE IF EXISTS idempotency_records CASCADE;
            DROP TABLE IF EXISTS email_deliveries CASCADE;
            DROP TABLE IF EXISTS check_ins CASCADE;
            ALTER TABLE tickets DROP COLUMN IF EXISTS status;
            ALTER TABLE tickets DROP COLUMN IF EXISTS unit_price_kurus;
            ALTER TABLE tickets DROP COLUMN IF EXISTS order_id;
            DROP TABLE IF EXISTS orders CASCADE;
            DROP TABLE IF EXISTS reservation_items CASCADE;
            DROP TABLE IF EXISTS event_seats CASCADE;
            DROP TABLE IF EXISTS reservations CASCADE;
            DROP TABLE IF EXISTS guest_sessions CASCADE;
            DROP TABLE IF EXISTS ticket_categories CASCADE;
            ALTER TABLE events DROP COLUMN IF EXISTS version;
            ALTER TABLE events DROP COLUMN IF EXISTS sales_open;
            ALTER TABLE seats DROP COLUMN IF EXISTS is_accessible;
            ALTER TABLE seats DROP COLUMN IF EXISTS y;
            ALTER TABLE seats DROP COLUMN IF EXISTS x;
            ALTER TABLE seats DROP COLUMN IF EXISTS segment_id;
            ALTER TABLE seats DROP COLUMN IF EXISTS row_order;
            ALTER TABLE seats DROP COLUMN IF EXISTS row_label;
            DROP TABLE IF EXISTS seat_segments CASCADE;
            ALTER TABLE halls DROP COLUMN IF EXISTS stage_y;
            ALTER TABLE halls DROP COLUMN IF EXISTS stage_x;
            """
        )
    )
