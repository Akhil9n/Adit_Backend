import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_token


@pytest.fixture
def other(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def owned(client, journey_payload, vehicle, driver):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    e = client.post(
        "/api/v1/expenses",
        json={"journey_id": j["id"], "category": "Toll", "amount": 100, "expense_date": "2026-10-01"},
    ).json()
    return {"vehicles": vehicle["id"], "drivers": driver["id"], "journeys": j["id"], "expenses": e["id"]}


def test_lists_are_scoped_to_user(other, owned):
    assert other.get("/api/v1/vehicles").json() == []
    assert other.get("/api/v1/drivers").json() == []
    assert other.get("/api/v1/journeys").json()["total"] == 0
    assert other.get("/api/v1/expenses").json()["total"] == 0


@pytest.mark.parametrize("resource", ["vehicles", "drivers", "journeys", "expenses"])
def test_cannot_read_modify_or_delete_other_users_records(other, owned, client, resource):
    url = f"/api/v1/{resource}/{owned[resource]}"
    assert other.get(url).status_code == 404
    assert other.patch(url, json={"notes": "hacked"}).status_code == 404
    assert other.delete(url).status_code == 404
    # The owner still sees it untouched.
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.json()["notes"] is None


def test_cannot_reference_other_users_records(other, owned):
    own_vehicle = other.post("/api/v1/vehicles", json={"registration_number": "KA-01-0001"}).json()

    resp = other.post(
        "/api/v1/journeys", json={"vehicle_id": owned["vehicles"], "journey_date": "2026-10-01", "platform": "uber"}
    )
    assert resp.status_code == 422 and resp.json()["errors"][0]["field"] == "vehicle_id"

    resp = other.post(
        "/api/v1/journeys",
        json={
            "vehicle_id": own_vehicle["id"],
            "driver_id": owned["drivers"],
            "journey_date": "2026-10-01",
            "platform": "uber",
        },
    )
    assert resp.status_code == 422 and resp.json()["errors"][0]["field"] == "driver_id"

    resp = other.post(
        "/api/v1/expenses",
        json={"journey_id": owned["journeys"], "category": "Toll", "amount": 5, "expense_date": "2026-10-01"},
    )
    assert resp.status_code == 422 and resp.json()["errors"][0]["field"] == "journey_id"


def test_user_id_in_body_is_ignored(other, client, owned):
    resp = other.post("/api/v1/vehicles", json={"registration_number": "KA-02-0002", "user_id": str(client.user_id)})
    assert resp.status_code == 201
    assert len(client.get("/api/v1/vehicles").json()) == 1  # victim unaffected


def test_dashboard_isolated(other, owned):
    d = other.get("/api/v1/dashboard", params={"from_date": "2026-10-01", "to_date": "2026-10-31"}).json()
    assert d["total_revenue"] == 0 and d["total_expenses"] == 0 and d["total_journeys"] == 0
    assert d["outstanding_amount"] == 0


def test_custom_categories_are_private(client, other, vehicle):
    client.post("/api/v1/expense-categories", json={"name": "Secret"})
    assert "Secret" not in [c["name"] for c in other.get("/api/v1/expense-categories").json()]


# --- authentication ----------------------------------------------------------------------


def test_requires_token(app):
    resp = TestClient(app).get("/api/v1/journeys")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}


def test_rejects_bad_signature(app):
    token = make_token(uuid.uuid4(), secret="another-secret-with-32-characters-xx")
    resp = TestClient(app).get("/api/v1/journeys", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_rejects_expired_token(app):
    token = make_token(uuid.uuid4(), expires_in=-60)
    resp = TestClient(app).get("/api/v1/journeys", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_rejects_garbage(app):
    resp = TestClient(app).get("/api/v1/journeys", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
