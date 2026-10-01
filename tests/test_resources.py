def test_vehicle_crud(client):
    v = client.post("/api/v1/vehicles", json={"registration_number": " mh-12-ab-0001 ", "year": 2022}).json()
    assert v["registration_number"] == "MH-12-AB-0001"
    assert v["status"] == "active"

    dup = client.post("/api/v1/vehicles", json={"registration_number": "MH-12-AB-0001"})
    assert dup.status_code == 409

    v = client.patch(f"/api/v1/vehicles/{v['id']}", json={"status": "sold", "notes": "  "}).json()
    assert v["status"] == "sold" and v["notes"] is None

    assert client.patch(f"/api/v1/vehicles/{v['id']}", json={"registration_number": None}).status_code == 422
    assert client.post("/api/v1/vehicles", json={"registration_number": ""}).status_code == 422
    assert client.post("/api/v1/vehicles", json={"registration_number": "X", "year": 1800}).status_code == 422

    assert client.delete(f"/api/v1/vehicles/{v['id']}").status_code == 204
    assert client.get(f"/api/v1/vehicles/{v['id']}").status_code == 404


def test_vehicle_in_use_cannot_be_deleted(client, journey_payload, vehicle):
    client.post("/api/v1/journeys", json=journey_payload())
    resp = client.delete(f"/api/v1/vehicles/{vehicle['id']}")
    assert resp.status_code == 409
    assert "inactive" in resp.json()["detail"]


def test_driver_crud(client):
    d = client.post(
        "/api/v1/drivers",
        json={"name": "Suresh", "phone": "98200 00000", "joining_date": "2026-01-15", "payment_model": "fixed_salary"},
    ).json()
    assert d["status"] == "active"
    assert client.post("/api/v1/drivers", json={"name": "X", "payment_model": "bitcoin"}).status_code == 422
    d = client.patch(f"/api/v1/drivers/{d['id']}", json={"status": "inactive"}).json()
    assert d["status"] == "inactive"
    assert [x["name"] for x in client.get("/api/v1/drivers", params={"status": "active"}).json()] == []
    assert client.delete(f"/api/v1/drivers/{d['id']}").status_code == 204
