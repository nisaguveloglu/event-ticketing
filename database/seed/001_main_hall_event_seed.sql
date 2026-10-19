\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    v_total_halls INTEGER;
    v_main_hall_count INTEGER;
    v_hall_id INTEGER;
    v_total_events INTEGER;
    v_incompatible_events INTEGER;
    v_duplicate_seat_pairs INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total_halls FROM halls;
    SELECT COUNT(*) INTO v_main_hall_count FROM halls WHERE name = 'Main Hall';

    IF v_total_halls = 0 THEN
        INSERT INTO halls (name) VALUES ('Main Hall') RETURNING id INTO v_hall_id;
    ELSIF v_total_halls = 1 AND v_main_hall_count = 1 THEN
        SELECT id INTO STRICT v_hall_id FROM halls WHERE name = 'Main Hall';
    ELSE
        RAISE EXCEPTION 'Seed aborted: ambiguous or incompatible hall state in halls table (total=%, main_hall=%).', v_total_halls, v_main_hall_count;
    END IF;

    SELECT COUNT(*) INTO v_duplicate_seat_pairs
    FROM (
        SELECT row, number
        FROM seats
        WHERE hall_id = v_hall_id
        GROUP BY row, number
        HAVING COUNT(*) > 1
    ) dup;

    IF v_duplicate_seat_pairs > 0 THEN
        RAISE EXCEPTION 'Seed aborted: duplicate (row, number) seats detected in hall_id=%.', v_hall_id;
    END IF;

    SELECT COUNT(*) INTO v_total_events FROM events;
    SELECT COUNT(*) INTO v_incompatible_events
    FROM events
    WHERE hall_id <> v_hall_id
       OR name <> 'Opening Night Concert';

    IF v_total_events > 1 OR v_incompatible_events > 0 THEN
        RAISE EXCEPTION 'Seed aborted: ambiguous or incompatible event state in events table (total=%, incompatible=%).', v_total_events, v_incompatible_events;
    END IF;

    INSERT INTO seats (hall_id, row, number, status)
    SELECT v_hall_id, 'A', n, 'AVAILABLE'::seatstatus
    FROM generate_series(1, 6) AS n
    WHERE NOT EXISTS (
        SELECT 1
        FROM seats s
        WHERE s.hall_id = v_hall_id
          AND s.row = 'A'
          AND s.number = n
    );

    IF v_total_events = 0 THEN
        INSERT INTO events (hall_id, name, starts_at)
        VALUES (v_hall_id, 'Opening Night Concert', '2026-11-15 20:00:00+03'::timestamptz);
    END IF;
END
$$;

COMMIT;
