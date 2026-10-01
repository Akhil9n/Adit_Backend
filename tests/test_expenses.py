def _expense(client, **overrides):
    data = {"expense_date": "2026-10-01", "category": "Toll", "amount": 120}
    data.update(overrides)
    return client.post("/api/v1/expenses", json=data)


def test_create_general_expense(client, vehicle):
    resp = _expense(client, vehicle_id=vehicle["id"], category="insurance", amount=2500, payment_method="upi")
    assert resp.status_code == 201, resp.text
    e = resp.json()
    assert e["category"] == "Insurance"  # canonical spelling
    assert e["journey"] is None
    assert e["vehicle"]["id"] == vehicle["id"]


def test_journey_expense_inherits_vehicle_and_driver(client, journey_payload, driver):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    e = _expense(client, journey_id=j["id"]).json()
    assert e["vehicle_id"] == j["vehicle_id"]
    assert e["driver_id"] == driver["id"]
    assert e["journey"]["id"] == j["id"]


def test_expenses_reduce_journey_profit(client, journey_payload):
    j = client.post(
        "/api/v1/journeys", json=journey_payload(gross_fare=1250, platform_commission=0, other_deductions=0)
    ).json()
    for category, amount in (("Toll", 120), ("Driver", 200), ("Fuel", 300)):
        assert _expense(client, journey_id=j["id"], category=category, amount=amount).status_code == 201

    detail = client.get(f"/api/v1/journeys/{j['id']}").json()
    assert detail["net_revenue"] == 1250
    assert detail["total_expenses"] == 620
    assert detail["profit"] == 630
    assert sorted(e["category"] for e in detail["expenses"]) == ["Driver", "Fuel", "Toll"]

    listed = client.get("/api/v1/journeys").json()["items"][0]
    assert listed["total_expenses"] == 620
    assert listed["profit"] == 630


def test_deleted_expense_excluded_from_profit(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    e = _expense(client, journey_id=j["id"], amount=100).json()
    client.delete(f"/api/v1/expenses/{e['id']}")
    assert client.get(f"/api/v1/journeys/{j['id']}").json()["total_expenses"] == 0


def test_invalid_amounts(client, vehicle):
    for amount in (0, -5):
        resp = _expense(client, vehicle_id=vehicle["id"], amount=amount)
        assert resp.status_code == 422
        assert resp.json()["errors"][0] == {"field": "amount", "message": "Amount must be greater than zero"}

    resp = _expense(client, vehicle_id=vehicle["id"], amount=None)
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "amount"


def test_category_required_and_validated(client, vehicle):
    resp = client.post(
        "/api/v1/expenses", json={"expense_date": "2026-10-01", "amount": 10, "vehicle_id": vehicle["id"]}
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "category"

    resp = _expense(client, vehicle_id=vehicle["id"], category="Snacks")
    assert resp.status_code == 422
    assert "Unknown expense category" in resp.json()["detail"]


def test_vehicle_required_for_general_expense(client):
    resp = _expense(client)
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "vehicle_id"


def test_fuel_amount_from_quantity_and_price(client, vehicle):
    e = _expense(
        client,
        vehicle_id=vehicle["id"],
        category="Fuel",
        amount=None,
        fuel_type="cng",
        quantity=8.5,
        price_per_unit=76.5,
        fuel_station="HP Thane",
    ).json()
    assert e["amount"] == 650.25
    assert e["fuel_type"] == "cng"

    # Explicit amount overrides quantity x price.
    e = _expense(
        client, vehicle_id=vehicle["id"], category="Fuel", amount=600, quantity=8.5, price_per_unit=76.5
    ).json()
    assert e["amount"] == 600

    # Updating quantity recalculates when amount isn't sent.
    e = client.patch(f"/api/v1/expenses/{e['id']}", json={"quantity": 10}).json()
    assert e["amount"] == 765


def test_non_fuel_expense_drops_fuel_fields(client, vehicle):
    e = _expense(client, vehicle_id=vehicle["id"], category="Parking", quantity=3, fuel_type="cng").json()
    assert e["quantity"] is None and e["fuel_type"] is None


def test_vehicle_must_match_journey(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    other = client.post("/api/v1/vehicles", json={"registration_number": "MH-02-ZZ-9999"}).json()
    resp = _expense(client, journey_id=j["id"], vehicle_id=other["id"])
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "vehicle_id"


def test_detach_expense_from_journey(client, journey_payload):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    e = _expense(client, journey_id=j["id"]).json()
    e = client.patch(f"/api/v1/expenses/{e['id']}", json={"journey_id": None}).json()
    assert e["journey_id"] is None
    assert client.get(f"/api/v1/journeys/{j['id']}").json()["total_expenses"] == 0


def test_expense_filters(client, journey_payload, vehicle):
    j = client.post("/api/v1/journeys", json=journey_payload()).json()
    _expense(client, journey_id=j["id"], category="Toll", amount=100)
    _expense(client, vehicle_id=vehicle["id"], category="Fuel", amount=500, expense_date="2026-09-20")
    _expense(client, vehicle_id=vehicle["id"], category="Parking", amount=50, payment_method="cash")

    data = client.get("/api/v1/expenses").json()
    assert data["total"] == 3 and data["total_amount"] == 650
    assert client.get("/api/v1/expenses", params={"journey_id": j["id"]}).json()["total"] == 1
    assert client.get("/api/v1/expenses", params={"scope": "general"}).json()["total"] == 2
    assert client.get("/api/v1/expenses", params={"category": "fuel"}).json()["total"] == 1
    assert client.get("/api/v1/expenses", params={"payment_method": "cash"}).json()["total"] == 1
    assert client.get("/api/v1/expenses", params={"from_date": "2026-10-01"}).json()["total"] == 2


def test_custom_categories(client, vehicle):
    names = [c["name"] for c in client.get("/api/v1/expense-categories").json()]
    assert "Fuel" in names and "Fine/Penalty" in names

    created = client.post("/api/v1/expense-categories", json={"name": "FASTag Recharge"})
    assert created.status_code == 201
    assert client.post("/api/v1/expense-categories", json={"name": "fuel"}).status_code == 409
    assert _expense(client, vehicle_id=vehicle["id"], category="fastag recharge").status_code == 201
    # In use -> cannot delete
    assert client.delete(f"/api/v1/expense-categories/{created.json()['id']}").status_code == 409
