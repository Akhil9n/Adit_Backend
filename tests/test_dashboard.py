import pytest


@pytest.fixture
def sample_data(client, journey_payload, vehicle):
    def journey(**kw):
        resp = client.post("/api/v1/journeys", json=journey_payload(**kw))
        assert resp.status_code == 201, resp.text
        return resp.json()

    def expense(**kw):
        data = {"expense_date": "2026-10-01", "category": "Toll", "amount": 100, "vehicle_id": vehicle["id"]}
        data.update(kw)
        resp = client.post("/api/v1/expenses", json=data)
        assert resp.status_code == 201, resp.text
        return resp.json()

    # Oct 1: Uber 1000 net (40 km), Oct 2: Ola 600 net (20 km) pending, Oct 2: Direct 2400 net (100 km)
    j1 = journey(
        journey_date="2026-10-01",
        platform="uber",
        gross_fare=1200,
        platform_commission=200,
        other_deductions=0,
        starting_odometer=1000,
        ending_odometer=1040,
    )
    journey(
        journey_date="2026-10-02",
        platform="ola",
        gross_fare=700,
        platform_commission=100,
        other_deductions=0,
        starting_odometer=1040,
        ending_odometer=1060,
        payment_status="pending",
    )
    journey(
        journey_date="2026-10-02",
        platform="direct",
        gross_fare=2400,
        platform_commission=0,
        other_deductions=0,
        starting_odometer=1060,
        ending_odometer=1160,
    )
    # Outside the range
    journey(
        journey_date="2026-09-30",
        platform="uber",
        gross_fare=999,
        platform_commission=0,
        other_deductions=0,
        starting_odometer=None,
        ending_odometer=None,
        distance_km=10,
        payment_status="pending",
    )
    # Deleted journey must not count
    deleted = journey(
        journey_date="2026-10-01", platform="uber", gross_fare=5000, platform_commission=0, other_deductions=0
    )
    client.delete(f"/api/v1/journeys/{deleted['id']}")

    expense(journey_id=j1["id"], category="Toll", amount=120, vehicle_id=None)
    expense(category="Fuel", amount=500, expense_date="2026-10-02")
    expense(category="Fuel", amount=300, expense_date="2026-10-03")
    expense(category="Insurance", amount=80, expense_date="2026-09-29")  # outside range
    return j1


def test_dashboard_totals(client, sample_data):
    d = client.get("/api/v1/dashboard", params={"from_date": "2026-10-01", "to_date": "2026-10-03"}).json()
    assert d["total_revenue"] == 4000
    assert d["total_expenses"] == 920
    assert d["net_profit"] == 3080
    assert d["total_journeys"] == 3
    assert d["total_distance_km"] == 160
    assert d["average_revenue_per_km"] == 25
    assert d["average_profit_per_journey"] == pytest.approx(1026.67)
    # All-time unpaid: Ola 600 + out-of-range 999
    assert d["outstanding_amount"] == 1599
    assert d["outstanding_journeys"] == 2

    platforms = {p["platform"]: p["amount"] for p in d["revenue_by_platform"]}
    assert platforms == {"direct": 2400, "uber": 1000, "ola": 600}
    assert d["revenue_by_platform"][0]["platform"] == "direct"  # sorted by amount

    categories = {c["category"]: c["amount"] for c in d["expenses_by_category"]}
    assert categories == {"Fuel": 800, "Toll": 120}

    assert d["daily_financials"] == [
        {"date": "2026-10-01", "revenue": 1000, "expenses": 120, "profit": 880},
        {"date": "2026-10-02", "revenue": 3000, "expenses": 500, "profit": 2500},
        {"date": "2026-10-03", "revenue": 0, "expenses": 300, "profit": -300},
    ]


def test_dashboard_empty_range(client):
    d = client.get("/api/v1/dashboard", params={"from_date": "2026-01-01", "to_date": "2026-01-02"}).json()
    assert d["total_revenue"] == 0
    assert d["average_revenue_per_km"] == 0
    assert d["average_profit_per_journey"] == 0
    assert len(d["daily_financials"]) == 2


def test_dashboard_vehicle_filter(client, sample_data):
    other = client.post("/api/v1/vehicles", json={"registration_number": "MH-02-XY-0001"}).json()
    d = client.get(
        "/api/v1/dashboard", params={"from_date": "2026-10-01", "to_date": "2026-10-03", "vehicle_id": other["id"]}
    ).json()
    assert d["total_revenue"] == 0 and d["total_expenses"] == 0


def test_dashboard_invalid_range(client):
    resp = client.get("/api/v1/dashboard", params={"from_date": "2026-10-05", "to_date": "2026-10-01"})
    assert resp.status_code == 422


def test_reports(client, sample_data, driver):
    params = {"from_date": "2026-10-01", "to_date": "2026-10-03"}

    rev = client.get("/api/v1/reports/revenue", params=params).json()
    assert rev["total_revenue"] == 4000
    assert rev["total_gross_fare"] == 4300
    assert rev["total_commission"] == 300
    assert len(rev["by_journey"]) == 3
    assert [d["amount"] for d in rev["by_day"]] == [1000, 3000, 0]

    exp = client.get("/api/v1/reports/expenses", params=params).json()
    assert exp["total_expenses"] == 920
    assert exp["journey_expenses"] == 120
    assert exp["general_expenses"] == 800
    assert exp["by_vehicle"][0]["amount"] == 920

    prof = client.get("/api/v1/reports/profitability", params=params).json()
    assert prof["profit"] == 3080
    assert prof["revenue_per_km"] == 25
    assert prof["profit_per_km"] == 19.25
    uber = next(p for p in prof["by_platform"] if p["platform"] == "uber")
    assert uber["journey_expenses"] == 120 and uber["profit"] == 880

    drivers = client.get("/api/v1/reports/drivers", params=params).json()["rows"]
    ramesh = next(r for r in drivers if r["driver_id"] == driver["id"])
    assert ramesh["journeys"] == 3
    assert ramesh["revenue"] == 4000
    assert ramesh["driver_expenses"] == 120  # toll inherited the journey's driver


def test_csv_export(client, sample_data):
    params = {"from_date": "2026-10-01", "to_date": "2026-10-03"}
    for kind in ("revenue", "expenses", "profitability", "drivers"):
        resp = client.get(f"/api/v1/reports/{kind}/csv", params=params)
        assert resp.status_code == 200, kind
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
    lines = client.get("/api/v1/reports/revenue/csv", params=params).text.lstrip("﻿").strip().splitlines()
    assert lines[0].startswith("Date,Platform")
    assert len(lines) == 4
    assert client.get("/api/v1/reports/unknown/csv").status_code == 422
