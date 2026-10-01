import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings

PROD = {
    "environment": "production",
    "database_url": "postgresql://u:p@host:6543/postgres",
    "supabase_url": "https://example.supabase.co",
    "cors_origins": "https://cab.example.com",
}


def test_production_settings_accept_valid_config():
    s = Settings(_env_file=None, **PROD)
    assert s.is_production and not s.is_development
    assert s.cors_origin_list == ["https://cab.example.com"]


@pytest.mark.parametrize(
    "override",
    [
        {"database_url": ""},
        {"supabase_url": "http://example.supabase.co"},
        {"cors_origins": "http://localhost:3000"},
        {"cors_origins": ""},
    ],
)
def test_production_settings_reject_unsafe_config(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**PROD, **override})


def test_security_headers(client):
    resp = client.get("/api/v1/vehicles")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["cache-control"] == "no-store"


def test_unhandled_errors_return_json_without_details(app, client, monkeypatch):
    from app.services import vehicle

    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(vehicle, "list_vehicles", boom)
    resp = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/vehicles", headers={"Authorization": client.headers["Authorization"]}
    )
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Something went wrong. Please try again."}
    assert "secret" not in resp.text
