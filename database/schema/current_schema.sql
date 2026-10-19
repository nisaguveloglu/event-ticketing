DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'seatstatus') THEN
        CREATE TYPE seatstatus AS ENUM ('AVAILABLE', 'LOCKED', 'SOLD');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS halls (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_halls_id ON halls (id);

CREATE TABLE IF NOT EXISTS seats (
    id SERIAL PRIMARY KEY,
    hall_id INTEGER NOT NULL REFERENCES halls(id),
    row VARCHAR(10) NOT NULL,
    number INTEGER NOT NULL,
    status seatstatus NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_seats_id ON seats (id);

CREATE TABLE IF NOT EXISTS seat_locks (
    id SERIAL PRIMARY KEY,
    seat_id INTEGER NOT NULL UNIQUE REFERENCES seats(id),
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_seat_locks_id ON seat_locks (id);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    hall_id INTEGER NOT NULL REFERENCES halls(id),
    name VARCHAR(200) NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_events_id ON events (id);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    ticket_code VARCHAR(64) NOT NULL,
    event_id INTEGER NOT NULL REFERENCES events(id),
    seat_id INTEGER NOT NULL REFERENCES seats(id),
    session_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tickets_event_seat UNIQUE (event_id, seat_id)
);

CREATE INDEX IF NOT EXISTS ix_tickets_id ON tickets (id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tickets_ticket_code ON tickets (ticket_code);
