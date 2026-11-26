DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'seatstatus') THEN
        CREATE TYPE seatstatus AS ENUM ('AVAILABLE', 'LOCKED', 'SOLD');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS guest_sessions (
    id SERIAL PRIMARY KEY,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_guest_sessions_id ON guest_sessions (id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_guest_sessions_token_hash ON guest_sessions (token_hash);

CREATE TABLE IF NOT EXISTS halls (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    stage_x INTEGER NOT NULL DEFAULT 0,
    stage_y INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_halls_id ON halls (id);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    hall_id INTEGER NOT NULL REFERENCES halls(id),
    name VARCHAR(200) NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    sales_open BOOLEAN NOT NULL DEFAULT true,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS ix_events_id ON events (id);

CREATE TABLE IF NOT EXISTS seat_segments (
    id SERIAL PRIMARY KEY,
    hall_id INTEGER NOT NULL REFERENCES halls(id),
    row_label VARCHAR(10) NOT NULL,
    orphan_exempt BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS ix_seat_segments_id ON seat_segments (id);

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

CREATE TABLE IF NOT EXISTS seats (
    id SERIAL PRIMARY KEY,
    hall_id INTEGER NOT NULL REFERENCES halls(id),
    row VARCHAR(10) NOT NULL,
    row_label VARCHAR(10) NOT NULL DEFAULT 'A',
    number INTEGER NOT NULL,
    row_order INTEGER NOT NULL DEFAULT 1,
    segment_id INTEGER REFERENCES seat_segments(id),
    x INTEGER NOT NULL DEFAULT 1,
    y INTEGER NOT NULL DEFAULT 1,
    is_accessible BOOLEAN NOT NULL DEFAULT false,
    status seatstatus NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_seats_id ON seats (id);

CREATE TABLE IF NOT EXISTS ticket_categories (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    name VARCHAR(100) NOT NULL,
    price_kurus INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ticket_categories_id ON ticket_categories (id);

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

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    reservation_id INTEGER NOT NULL UNIQUE REFERENCES reservations(id),
    guest_session_id INTEGER NOT NULL REFERENCES guest_sessions(id),
    total_price_kurus INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_orders_id ON orders (id);

CREATE TABLE IF NOT EXISTS seat_locks (
    id SERIAL PRIMARY KEY,
    seat_id INTEGER NOT NULL UNIQUE REFERENCES seats(id),
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_seat_locks_id ON seat_locks (id);

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

CREATE TABLE IF NOT EXISTS reservation_items (
    id SERIAL PRIMARY KEY,
    reservation_id INTEGER NOT NULL REFERENCES reservations(id),
    event_seat_id INTEGER NOT NULL REFERENCES event_seats(id),
    unit_price_kurus INTEGER NOT NULL,
    CONSTRAINT uq_reservation_items_res_event_seat UNIQUE (reservation_id, event_seat_id)
);

CREATE INDEX IF NOT EXISTS ix_reservation_items_id ON reservation_items (id);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    ticket_code VARCHAR(64) NOT NULL,
    event_id INTEGER NOT NULL REFERENCES events(id),
    seat_id INTEGER NOT NULL REFERENCES seats(id),
    unit_price_kurus INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'VALID',
    session_id VARCHAR(100) NOT NULL DEFAULT 'guest',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tickets_event_seat UNIQUE (event_id, seat_id)
);

CREATE INDEX IF NOT EXISTS ix_tickets_id ON tickets (id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tickets_ticket_code ON tickets (ticket_code);

CREATE TABLE IF NOT EXISTS check_ins (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL UNIQUE REFERENCES tickets(id),
    checked_in_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    staff_label VARCHAR(100) NOT NULL DEFAULT 'staff'
);

CREATE INDEX IF NOT EXISTS ix_check_ins_id ON check_ins (id);
