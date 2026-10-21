import os


# Test-only login, set before the app reads its settings. Environment variables
# take precedence over backend/.env, so tests never depend on the real demo password.
from app.auth import hash_password

TEST_EMAIL = "tester@example.com"
TEST_PASSWORD = "correct horse battery staple"
os.environ["DEMO_EMAIL"] = TEST_EMAIL
os.environ.pop("DEMO_USERNAME", None)
os.environ["DEMO_PASSWORD_HASH"] = hash_password(TEST_PASSWORD)
os.environ["SESSION_SECRET"] = "test-secret-" + "x" * 32
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3010"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Connection, text  # noqa: E402

from app.app_database import get_engine as get_app_engine  # noqa: E402
from app.auth import login_limiter  # noqa: E402
from app.database import database_is_reachable, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.ratelimit import limiter  # noqa: E402

APP_TABLES = "app.users, app.otp_codes, app.auth_audit_log, app.identity_review_queue"


@pytest.fixture
def client() -> TestClient:
    login_limiter.reset()  # each test starts with no recorded failed logins
    limiter.reset()
    return TestClient(app)


@pytest.fixture
def app_db() -> Connection:
    """Writable connection to the app schema. Tests that use it wipe the app tables first,
    so it only runs when TEST_APP_DB_RESET=1 is set, to keep it away from real data."""
    app_engine = get_app_engine()
    if app_engine is None:
        pytest.skip("APP_DB_USER / APP_DB_PASSWORD are not set")
    if os.environ.get("TEST_APP_DB_RESET") != "1":
        pytest.skip("set TEST_APP_DB_RESET=1 to run tests that reset the app schema (use a test database)")
    from app.config import get_settings

    database = get_settings().app_db_name or get_settings().db_name
    if "test" not in database.lower():
        # Refuse to truncate anything that is not clearly a test database.
        pytest.skip(f"app database {database!r} does not look like a test database (name must contain 'test')")
    try:
        connection = app_engine.connect()
    except Exception:
        pytest.skip("app database is not reachable")
    connection.execute(text(f"TRUNCATE {APP_TABLES} CASCADE"))
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def db() -> Connection:
    """Read-only connection to the real chubbstub database. Skips if it is not reachable."""
    if not database_is_reachable():
        pytest.skip("chubbstub database is not reachable")
    with engine.connect() as connection:
        yield connection


@pytest.fixture
def signed_in_client(client) -> TestClient:
    response = client.post("/api/admin/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return client
