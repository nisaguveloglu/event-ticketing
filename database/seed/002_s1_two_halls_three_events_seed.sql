\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
    v_main_hall_id INTEGER;
    v_studio_hall_id INTEGER;
    v_row_label VARCHAR(10);
    v_row_order INTEGER;
    v_seat_num INTEGER;
    v_exempt_seg_id INTEGER;
    v_left_seg_id INTEGER;
    v_right_seg_id INTEGER;
    v_single_seg_id INTEGER;
    v_target_seg_id INTEGER;
    v_x INTEGER;
    v_is_acc BOOLEAN;
    v_ev1_id INTEGER;
    v_ev2_id INTEGER;
    v_ev3_id INTEGER;
    v_ev_id INTEGER;
    v_prem_cat_id INTEGER;
    v_std_cat_id INTEGER;
BEGIN
    SELECT id INTO v_main_hall_id FROM halls WHERE name = 'Main Hall' ORDER BY id ASC LIMIT 1;
    IF v_main_hall_id IS NULL THEN
        INSERT INTO halls (name, stage_x, stage_y)
        VALUES ('Main Hall', 6, 0)
        RETURNING id INTO v_main_hall_id;
    ELSE
        UPDATE halls SET stage_x = 6, stage_y = 0 WHERE id = v_main_hall_id;
    END IF;

    SELECT id INTO v_studio_hall_id FROM halls WHERE name = 'Studio Hall' ORDER BY id ASC LIMIT 1;
    IF v_studio_hall_id IS NULL THEN
        INSERT INTO halls (name, stage_x, stage_y)
        VALUES ('Studio Hall', 4, 0)
        RETURNING id INTO v_studio_hall_id;
    ELSE
        UPDATE halls SET stage_x = 4, stage_y = 0 WHERE id = v_studio_hall_id;
    END IF;

    FOR v_row_order IN 1..4 LOOP
        v_row_label := CHR(64 + v_row_order);

        IF v_row_label = 'A' THEN
            SELECT id INTO v_exempt_seg_id
            FROM seat_segments
            WHERE hall_id = v_main_hall_id AND row_label = 'A' AND orphan_exempt = TRUE
            ORDER BY id ASC LIMIT 1;

            IF v_exempt_seg_id IS NULL THEN
                INSERT INTO seat_segments (hall_id, row_label, orphan_exempt)
                VALUES (v_main_hall_id, 'A', TRUE)
                RETURNING id INTO v_exempt_seg_id;
            END IF;
        END IF;

        SELECT id INTO v_left_seg_id
        FROM seat_segments
        WHERE hall_id = v_main_hall_id AND row_label = v_row_label AND orphan_exempt = FALSE
        ORDER BY id ASC LIMIT 1;

        IF v_left_seg_id IS NULL THEN
            INSERT INTO seat_segments (hall_id, row_label, orphan_exempt)
            VALUES (v_main_hall_id, v_row_label, FALSE)
            RETURNING id INTO v_left_seg_id;
        END IF;

        SELECT id INTO v_right_seg_id
        FROM seat_segments
        WHERE hall_id = v_main_hall_id AND row_label = v_row_label AND orphan_exempt = FALSE AND id > v_left_seg_id
        ORDER BY id ASC LIMIT 1;

        IF v_right_seg_id IS NULL THEN
            INSERT INTO seat_segments (hall_id, row_label, orphan_exempt)
            VALUES (v_main_hall_id, v_row_label, FALSE)
            RETURNING id INTO v_right_seg_id;
        END IF;

        FOR v_seat_num IN 1..10 LOOP
            v_is_acc := (v_row_label = 'A' AND v_seat_num = 1);
            v_x := CASE WHEN v_seat_num <= 5 THEN v_seat_num ELSE v_seat_num + 1 END;
            v_target_seg_id := CASE
                WHEN v_is_acc THEN v_exempt_seg_id
                WHEN v_seat_num <= 5 THEN v_left_seg_id
                ELSE v_right_seg_id
            END;

            IF EXISTS (
                SELECT 1 FROM seats
                WHERE hall_id = v_main_hall_id AND (row_label = v_row_label OR row = v_row_label) AND number = v_seat_num
            ) THEN
                UPDATE seats
                SET row = v_row_label,
                    row_label = v_row_label,
                    row_order = v_row_order,
                    segment_id = v_target_seg_id,
                    x = v_x,
                    y = v_row_order,
                    is_accessible = v_is_acc
                WHERE hall_id = v_main_hall_id AND (row_label = v_row_label OR row = v_row_label) AND number = v_seat_num;
            ELSE
                INSERT INTO seats (hall_id, row, row_label, number, row_order, segment_id, x, y, is_accessible, status)
                VALUES (v_main_hall_id, v_row_label, v_row_label, v_seat_num, v_row_order, v_target_seg_id, v_x, v_row_order, v_is_acc, 'AVAILABLE'::seatstatus);
            END IF;
        END LOOP;
    END LOOP;

    FOR v_row_order IN 1..3 LOOP
        v_row_label := CHR(64 + v_row_order);

        IF v_row_label = 'A' THEN
            SELECT id INTO v_exempt_seg_id
            FROM seat_segments
            WHERE hall_id = v_studio_hall_id AND row_label = 'A' AND orphan_exempt = TRUE
            ORDER BY id ASC LIMIT 1;

            IF v_exempt_seg_id IS NULL THEN
                INSERT INTO seat_segments (hall_id, row_label, orphan_exempt)
                VALUES (v_studio_hall_id, 'A', TRUE)
                RETURNING id INTO v_exempt_seg_id;
            END IF;
        END IF;

        SELECT id INTO v_single_seg_id
        FROM seat_segments
        WHERE hall_id = v_studio_hall_id AND row_label = v_row_label AND orphan_exempt = FALSE
        ORDER BY id ASC LIMIT 1;

        IF v_single_seg_id IS NULL THEN
            INSERT INTO seat_segments (hall_id, row_label, orphan_exempt)
            VALUES (v_studio_hall_id, v_row_label, FALSE)
            RETURNING id INTO v_single_seg_id;
        END IF;

        FOR v_seat_num IN 1..8 LOOP
            v_is_acc := (v_row_label = 'A' AND v_seat_num = 1);
            v_target_seg_id := CASE WHEN v_is_acc THEN v_exempt_seg_id ELSE v_single_seg_id END;

            IF EXISTS (
                SELECT 1 FROM seats
                WHERE hall_id = v_studio_hall_id AND (row_label = v_row_label OR row = v_row_label) AND number = v_seat_num
            ) THEN
                UPDATE seats
                SET row = v_row_label,
                    row_label = v_row_label,
                    row_order = v_row_order,
                    segment_id = v_target_seg_id,
                    x = v_seat_num,
                    y = v_row_order,
                    is_accessible = v_is_acc
                WHERE hall_id = v_studio_hall_id AND (row_label = v_row_label OR row = v_row_label) AND number = v_seat_num;
            ELSE
                INSERT INTO seats (hall_id, row, row_label, number, row_order, segment_id, x, y, is_accessible, status)
                VALUES (v_studio_hall_id, v_row_label, v_row_label, v_seat_num, v_row_order, v_target_seg_id, v_seat_num, v_row_order, v_is_acc, 'AVAILABLE'::seatstatus);
            END IF;
        END LOOP;
    END LOOP;

    SELECT id INTO v_ev1_id FROM events WHERE hall_id = v_main_hall_id AND name = 'Opening Night Concert' ORDER BY id ASC LIMIT 1;
    IF v_ev1_id IS NULL THEN
        INSERT INTO events (hall_id, name, starts_at, sales_open, version)
        VALUES (
            v_main_hall_id,
            'Opening Night Concert',
            (((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Istanbul')::date + 7) + TIME '20:00:00') AT TIME ZONE 'Europe/Istanbul',
            TRUE,
            1
        )
        RETURNING id INTO v_ev1_id;
    END IF;

    SELECT id INTO v_ev2_id FROM events WHERE hall_id = v_main_hall_id AND name = 'Symphony Gala Night' ORDER BY id ASC LIMIT 1;
    IF v_ev2_id IS NULL THEN
        INSERT INTO events (hall_id, name, starts_at, sales_open, version)
        VALUES (
            v_main_hall_id,
            'Symphony Gala Night',
            (((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Istanbul')::date + 8) + TIME '20:00:00') AT TIME ZONE 'Europe/Istanbul',
            TRUE,
            1
        )
        RETURNING id INTO v_ev2_id;
    END IF;

    SELECT id INTO v_ev3_id FROM events WHERE hall_id = v_studio_hall_id AND name = 'Indie Acoustic Session' ORDER BY id ASC LIMIT 1;
    IF v_ev3_id IS NULL THEN
        INSERT INTO events (hall_id, name, starts_at, sales_open, version)
        VALUES (
            v_studio_hall_id,
            'Indie Acoustic Session',
            (((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Istanbul')::date + 9) + TIME '20:00:00') AT TIME ZONE 'Europe/Istanbul',
            TRUE,
            1
        )
        RETURNING id INTO v_ev3_id;
    END IF;

    FOREACH v_ev_id IN ARRAY ARRAY[v_ev1_id, v_ev2_id] LOOP
        SELECT id INTO v_prem_cat_id FROM ticket_categories WHERE event_id = v_ev_id AND name = 'Premium' LIMIT 1;
        IF v_prem_cat_id IS NULL THEN
            INSERT INTO ticket_categories (event_id, name, price_kurus)
            VALUES (v_ev_id, 'Premium', 50000)
            RETURNING id INTO v_prem_cat_id;
        END IF;

        SELECT id INTO v_std_cat_id FROM ticket_categories WHERE event_id = v_ev_id AND name = 'Standard' LIMIT 1;
        IF v_std_cat_id IS NULL THEN
            INSERT INTO ticket_categories (event_id, name, price_kurus)
            VALUES (v_ev_id, 'Standard', 30000)
            RETURNING id INTO v_std_cat_id;
        END IF;

        INSERT INTO event_seats (event_id, seat_id, category_id, price_kurus, status)
        SELECT
            v_ev_id,
            s.id,
            CASE WHEN s.row_order <= 2 THEN v_prem_cat_id ELSE v_std_cat_id END,
            CASE WHEN s.row_order <= 2 THEN 50000 ELSE 30000 END,
            'AVAILABLE'::seatstatus
        FROM seats s
        WHERE s.hall_id = v_main_hall_id
          AND NOT EXISTS (
              SELECT 1 FROM event_seats es
              WHERE es.event_id = v_ev_id AND es.seat_id = s.id
          );
    END LOOP;

    SELECT id INTO v_std_cat_id FROM ticket_categories WHERE event_id = v_ev3_id AND name = 'Standard' LIMIT 1;
    IF v_std_cat_id IS NULL THEN
        INSERT INTO ticket_categories (event_id, name, price_kurus)
        VALUES (v_ev3_id, 'Standard', 25000)
        RETURNING id INTO v_std_cat_id;
    END IF;

    INSERT INTO event_seats (event_id, seat_id, category_id, price_kurus, status)
    SELECT
        v_ev3_id,
        s.id,
        v_std_cat_id,
        25000,
        'AVAILABLE'::seatstatus
    FROM seats s
    WHERE s.hall_id = v_studio_hall_id
      AND NOT EXISTS (
          SELECT 1 FROM event_seats es
          WHERE es.event_id = v_ev3_id AND es.seat_id = s.id
      );
END
$$;

COMMIT;
