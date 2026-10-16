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
from sqlalchemy import Connection  # noqa: E402

from app.database import database_is_reachable, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    from app.auth import login_limiter
    login_limiter.reset()  # each test starts with no recorded failed logins
    return TestClient(app)


@pytest.fixture
def db() -> Connection:
    """Read-only connection to the real chubbstub database. Skips if it is not reachable."""
    if not database_is_reachable():
        pytest.skip("chubbstub database is not reachable")
    with engine.connect() as connection:
        yield connection


@pytest.fixture
def signed_in_client(client) -> TestClient:
    response = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return client
