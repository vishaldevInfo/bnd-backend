"""Health endpoint and database safety checks."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_health_reports_database_ok(client, db):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_unavailable_database(client, monkeypatch):
    monkeypatch.setattr("app.main.database_is_reachable", lambda: False)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"


def test_connections_are_read_only(db):
    # WHERE false: even if read-only mode were broken, no row could change.
    with pytest.raises(DBAPIError, match="read-only transaction"):
        db.execute(text("UPDATE ar_salesperson SET salespersonname = salespersonname WHERE false"))


def test_app_does_not_connect_as_superuser(db):
    # The app must use the read-only role (create_readonly_role.sql), never postgres.
    is_superuser = db.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar_one()
    assert is_superuser is False
