"""Demo login, session cookie, rate limiting and endpoint protection."""
from app.auth import SESSION_COOKIE, create_session_token, hash_password, verify_password
from app.config import get_settings
from tests.conftest import TEST_EMAIL, TEST_PASSWORD

LOGIN = "/api/auth/login"


def login(client, email=TEST_EMAIL, password=TEST_PASSWORD, **kwargs):
    return client.post(LOGIN, json={"email": email, "password": password}, **kwargs)


def test_password_hash_is_bcrypt_and_round_trips():
    stored = hash_password("s3cret-value")
    assert stored.startswith("$2b$")
    assert verify_password("s3cret-value", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret-value", "garbage")
    assert not verify_password("x" * 100, stored)


def test_login_sets_secure_session_cookie(client):
    response = login(client)
    assert response.status_code == 200
    assert response.json() == {"email": TEST_EMAIL}
    cookie_header = response.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE}=" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header


def test_email_is_case_insensitive(client):
    response = login(client, email="  TESTER@Example.COM ")
    assert response.status_code == 200
    assert response.json() == {"email": TEST_EMAIL}


def test_wrong_password_and_unknown_email_get_the_same_error(client):
    wrong_password = login(client, password="nope")
    unknown_email = login(client, email="someone@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Invalid email or password."}
    assert SESSION_COOKIE not in client.cookies


def test_repeated_failures_are_rate_limited(client):
    for _ in range(get_settings().login_max_failures):
        assert login(client, password="wrong").status_code == 401
    blocked = login(client)  # even the correct password is refused while blocked
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


def test_rate_limit_is_per_email(client):
    for _ in range(get_settings().login_max_failures):
        login(client, email="attacker@example.com", password="wrong")
    assert login(client).status_code == 200


def test_successful_login_clears_failure_count(client):
    for _ in range(get_settings().login_max_failures - 1):
        login(client, password="wrong")
    assert login(client).status_code == 200
    assert login(client, password="wrong").status_code == 401  # counting restarted


def test_me_requires_a_session(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_the_signed_in_user(signed_in_client):
    response = signed_in_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == {"email": TEST_EMAIL}


def test_tampered_cookie_is_rejected(client):
    token = create_session_token(TEST_EMAIL)
    client.cookies.set(SESSION_COOKIE, token[:-2] + "xx")
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["set-cookie"].startswith(f"{SESSION_COOKIE}=; Max-Age=0")


def test_expired_session_is_rejected(client, monkeypatch):
    client.cookies.set(SESSION_COOKIE, create_session_token(TEST_EMAIL))
    monkeypatch.setattr(get_settings(), "session_max_age_hours", -1)
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_the_cookie(signed_in_client):
    response = signed_in_client.post("/api/auth/logout")
    assert response.status_code == 204
    assert SESSION_COOKIE not in signed_in_client.cookies
    assert signed_in_client.get("/api/auth/me").status_code == 401


def test_cross_origin_login_is_rejected(client):
    assert login(client, headers={"Origin": "https://evil.example"}).status_code == 403


def test_same_origin_login_is_allowed(client):
    assert login(client, headers={"Origin": "http://localhost:3010"}).status_code == 200


def test_health_stays_public(client):
    assert client.get("/api/health").status_code in (200, 503)
