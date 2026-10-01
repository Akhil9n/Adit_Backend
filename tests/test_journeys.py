def test_create_journey_calculates_distance_and_net_revenue(client, journey_payload):
    resp = client.post("/api/v1/journeys", json=journey_payload())
    assert resp.status_code == 201, resp.text
    j = resp.json()
    assert j["distance_km"] == 42
    assert j["net_revenue"] == 1250.00  # 1500 - 200 - 50
    assert j["total_expenses"] == 0
    assert j["profit"] == 1250.00
    assert j["amount_paid"] == 1250.00
    assert j["outstanding_amount"] == 0
    assert j["vehicle"]["registration_number"] == "MH-01-AB-1234"
    assert j["driver"]["name"] == "Ramesh"
    assert j["expenses"] == []


def test_journey_date_is_preserved_exactly(client, journey_payload):
    # A late-night IST trip must stay on its calendar date.
    resp = client.post(
        "/api/v1/journeys",
        json=journey_payload(
            journey_date="2026-10-01", start_time="2026-10-01T23:30:00+05:30", end_time="2026-10-02T00:45:00+05:30"
        ),
    )
    assert resp.status_code == 201, resp.text
    j = resp.json()
    assert j["journey_date"] == "2026-10-01"
    assert j["duration_minutes"] == 75
    # Instants are returned in UTC with an explicit offset.
    assert j["start_time"].replace("Z", "+00:00") == "2026-10-01T18:00:00+00:00"
    assert j["end_time"].replace("Z", "+00:00") == "2026-10-01T19:15:00+00:00"


def test_journey_updates_vehicle_odometer(client, journey_payload, vehicle):
    client.post("/api/v1/journeys", json=journey_payload(starting_odometer=10000, ending_odometer=10120))
    assert client.get(f"/api/v1/vehicles/{vehicle['id']}").json()["current_odometer"] == 10120


def test_manual_distance_override_is_retained(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload(distance_km=45.5, distance_overridden=True)).json()
    assert j["distance_km"] == 45.5

    # Changing odometers keeps the manual value while the override is on…
    j = client.patch(f"/api/v1/journeys/{j['id']}", json={"ending_odometer": 10060}).json()
    assert j["distance_km"] == 45.5
    # …and recalculates once it is switched off.
    j = client.patch(f"/api/v1/journeys/{j['id']}", json={"distance_overridden": False}).json()
    assert j["distance_km"] == 60


def test_distance_without_odometers(client, journey_payload):
    j = client.post(
        "/api/v1/journeys", json=journey_payload(starting_odometer=None, ending_odometer=None, distance_km=12)
    ).json()
    assert j["distance_km"] == 12


def test_net_revenue_override(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload(net_revenue=1230.55, net_revenue_overridden=True)).json()
    assert j["net_revenue"] == 1230.55
    assert j["gross_fare"] == 1500


def test_update_recalculates_net_revenue(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    j = client.patch(f"/api/v1/journeys/{j['id']}", json={"gross_fare": 2000}).json()
    assert j["net_revenue"] == 1750


def test_invalid_odometer_rejected(client, journey_payload):
    resp = client.post("/api/v1/journeys", json=journey_payload(starting_odometer=10050, ending_odometer=10000))
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"] == "Ending odometer cannot be lower than starting odometer"
    assert body["errors"][0]["field"] == "ending_odometer"


def test_invalid_odometer_rejected_on_update(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    resp = client.patch(f"/api/v1/journeys/{j['id']}", json={"ending_odometer": 9000})
    assert resp.status_code == 422


def test_negative_amounts_rejected(client, journey_payload):
    resp = client.post("/api/v1/journeys", json=journey_payload(gross_fare=-10))
    assert resp.status_code == 422
    assert resp.json()["errors"][0] == {"field": "gross_fare", "message": "Gross fare cannot be negative"}


def test_deductions_cannot_exceed_fare(client, journey_payload):
    resp = client.post("/api/v1/journeys", json=journey_payload(gross_fare=100, platform_commission=150))
    assert resp.status_code == 422


def test_required_fields(client, journey_payload):
    payload = journey_payload()
    for field in ("vehicle_id", "platform", "journey_date"):
        data = {k: v for k, v in payload.items() if k != field}
        resp = client.post("/api/v1/journeys", json=data)
        assert resp.status_code == 422, field
        assert resp.json()["errors"][0]["field"] == field


def test_partial_payment(client, journey_payload):
    resp = client.post("/api/v1/journeys", json=journey_payload(payment_status="partial"))
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "amount_paid"

    j = client.post("/api/v1/journeys", json=journey_payload(payment_status="partial", amount_paid=1000)).json()
    assert j["outstanding_amount"] == 250

    resp = client.post("/api/v1/journeys", json=journey_payload(payment_status="partial", amount_paid=5000))
    assert resp.status_code == 422


def test_pending_payment_is_outstanding(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload(payment_status="pending", amount_paid=500)).json()
    assert j["amount_paid"] == 0
    assert j["outstanding_amount"] == 1250


def test_end_time_before_start_rejected(client, journey_payload):
    resp = client.post(
        "/api/v1/journeys",
        json=journey_payload(start_time="2026-10-01T10:00:00+05:30", end_time="2026-10-01T09:00:00+05:30"),
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "end_time"


def test_list_filters(client, journey_payload):
    client.post("/api/v1/journeys", json=journey_payload(platform="uber", journey_date="2026-10-01"))
    client.post("/api/v1/journeys", json=journey_payload(platform="ola", journey_date="2026-10-02"))
    client.post(
        "/api/v1/journeys", json=journey_payload(platform="ola", journey_date="2026-09-15", payment_status="pending")
    )

    assert client.get("/api/v1/journeys").json()["total"] == 3
    assert client.get("/api/v1/journeys", params={"platform": "ola"}).json()["total"] == 2
    data = client.get("/api/v1/journeys", params={"from_date": "2026-10-01", "to_date": "2026-10-31"}).json()
    assert data["total"] == 2
    assert [j["journey_date"] for j in data["items"]] == ["2026-10-02", "2026-10-01"]
    assert client.get("/api/v1/journeys", params={"payment_status": "pending"}).json()["total"] == 1
    assert client.get("/api/v1/journeys", params={"search": "THANE"}).json()["total"] == 3


def test_soft_delete_and_restore(client, journey_payload, session_factory):
    from app.models import Expense, Journey

    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    exp = client.post(
        "/api/v1/expenses",
        json={"journey_id": j["id"], "category": "Toll", "amount": 120, "expense_date": "2026-10-01"},
    ).json()

    assert client.delete(f"/api/v1/journeys/{j['id']}").status_code == 204
    assert client.get(f"/api/v1/journeys/{j['id']}").status_code == 404
    assert client.get("/api/v1/journeys").json()["total"] == 0
    # The journey's expenses are hidden with it.
    assert client.get(f"/api/v1/expenses/{exp['id']}").status_code == 404

    # Rows remain in the database for audit/recovery.
    with session_factory() as s:
        assert s.get(Journey, __import__("uuid").UUID(j["id"])).deleted_at is not None
        assert s.get(Expense, __import__("uuid").UUID(exp["id"])).deleted_at is not None

    restored = client.post(f"/api/v1/journeys/{j['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["total_expenses"] == 120


def test_journey_not_found(client):
    resp = client.get("/api/v1/journeys/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Journey not found"}
