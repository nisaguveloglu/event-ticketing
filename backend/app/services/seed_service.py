from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_s1_demo_seed(target_engine: Engine) -> None:
    seed_path = (
        Path(__file__).resolve().parents[3]
        / "database"
        / "seed"
        / "002_s1_two_halls_three_events_seed.sql"
    )
    raw_sql = seed_path.read_text(encoding="utf-8")
    statements = "\n".join(
        line for line in raw_sql.splitlines() if not line.strip().startswith("\\")
    )
    with target_engine.begin() as conn:
        conn.execute(text(statements))


def reset_and_seed_database(target_engine: Engine, confirm_db_name: str) -> None:
    actual_db = target_engine.url.database or ""
    if actual_db != confirm_db_name:
        raise ValueError(
            f"Database name mismatch: expected '{confirm_db_name}', got '{actual_db}'"
        )
    with target_engine.begin() as conn:
        conn.execute(
            text(
                """
                TRUNCATE TABLE
                    idempotency_records,
                    email_deliveries,
                    check_ins,
                    tickets,
                    orders,
                    reservation_items,
                    event_seats,
                    reservations,
                    guest_sessions,
                    ticket_categories,
                    seat_locks,
                    events,
                    seats,
                    seat_segments,
                    halls
                RESTART IDENTITY CASCADE
                """
            )
        )
    run_s1_demo_seed(target_engine)
