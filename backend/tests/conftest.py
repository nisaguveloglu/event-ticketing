import os
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
if not TEST_DB_URL:
    raise RuntimeError("TEST_DATABASE_URL environment variable must be set before running tests.")

parsed_url = urlparse(TEST_DB_URL)
target_db_name = (parsed_url.path or "").lstrip("/")

if not target_db_name or target_db_name == "cinema" or not target_db_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests against non-isolated database '{target_db_name}'. "
        "TEST_DATABASE_URL must target an isolated *_test database (e.g. cinema_test or event_ticketing_test)."
    )

os.environ["DATABASE_URL"] = TEST_DB_URL

from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app

if settings.database_url != TEST_DB_URL:
    raise RuntimeError("Application settings.database_url did not bind to TEST_DATABASE_URL.")

if engine.url.database != target_db_name or engine.url.database == "cinema":
    raise RuntimeError(f"SQLAlchemy engine bound to unexpected database: {engine.url.database}")


def _ensure_test_db_migrated() -> None:
    if engine.url.database != target_db_name or engine.url.database == "cinema":
        raise RuntimeError("Safety check failed: refusing to migrate non-test database.")
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")


_ensure_test_db_migrated()


@pytest.fixture(autouse=True)
def reset_test_database():
    if engine.url.database != target_db_name or engine.url.database == "cinema":
        raise RuntimeError("Safety check failed: refusing to touch non-test database.")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
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
    yield


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
