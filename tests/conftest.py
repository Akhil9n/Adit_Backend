"""Test setup.

Runs against SQLite by default so the suite works anywhere. Set TEST_DATABASE_URL to a
PostgreSQL URL (e.g. postgresql+psycopg://postgres@localhost:5432/cabops_test) to run the
same tests against Postgres.
"""

import os
import time
import uuid
from collections.abc import Callable, Iterator

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app import models  # noqa: F401
from app.config import Settings, get_settings
from app.constants import SYSTEM_EXPENSE_CATEGORIES
from app.db.database import Base, get_db
from app.main import create_app
from app.models import ExpenseCategory

JWT_SECRET = "test-secret-with-at-least-32-characters!!"


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"
    eng = create_engine(url)
    if eng.dialect.name == "sqlite":

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - sqlite only
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session_factory(engine) -> Iterator[sessionmaker[Session]]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as s:
        s.add_all([ExpenseCategory(name=n, is_system=True) for n in SYSTEM_EXPENSE_CATEGORIES])
        s.commit()
    yield factory
    with engine.begin() as conn:
        for table in ("expenses", "journeys", "drivers", "vehicles", "expense_categories"):
            conn.execute(text(f"DELETE FROM {table}"))


@pytest.fixture
def app(session_factory):
    application = create_app()

    def _db() -> Iterator[Session]:
        with session_factory() as s:
            yield s

    application.dependency_overrides[get_db] = _db
    application.dependency_overrides[get_settings] = lambda: Settings(
        database_url="", supabase_jwt_secret=JWT_SECRET, environment="test"
    )
    return application


def make_token(user_id: uuid.UUID, *, expires_in: int = 3600, secret: str = JWT_SECRET) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "aud": "authenticated", "role": "authenticated", "iat": now, "exp": now + expires_in},
        secret,
        algorithm="HS256",
    )


@pytest.fixture
def make_client(app) -> Callable[[uuid.UUID | None], TestClient]:
    def _make(user_id: uuid.UUID | None = None) -> TestClient:
        client = TestClient(app)
        client.user_id = user_id or uuid.uuid4()  # type: ignore[attr-defined]
        client.headers["Authorization"] = f"Bearer {make_token(client.user_id)}"  # type: ignore[attr-defined]
        return client

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def vehicle(client) -> dict:
    resp = client.post(
        "/api/v1/vehicles",
        json={
            "registration_number": "mh-01-ab-1234",
            "make": "Maruti",
            "model": "Dzire",
            "fuel_type": "cng",
            "current_odometer": 10000,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def driver(client) -> dict:
    resp = client.post("/api/v1/drivers", json={"name": "Ramesh", "payment_model": "daily_allowance"})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def journey_payload(vehicle, driver) -> Callable[..., dict]:
    def _payload(**overrides) -> dict:
        data = {
            "vehicle_id": vehicle["id"],
            "driver_id": driver["id"],
            "journey_date": "2026-10-01",
            "platform": "uber",
            "trip_type": "local",
            "pickup_location": "Mumbai",
            "drop_location": "Thane",
            "starting_odometer": 10000,
            "ending_odometer": 10042,
            "gross_fare": 1500,
            "platform_commission": 200,
            "other_deductions": 50,
            "payment_status": "paid",
        }
        data.update(overrides)
        return data

    return _payload
