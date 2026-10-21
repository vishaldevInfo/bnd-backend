"""Customer registration and sign-in through the API.

Needs the writable app schema (APP_DB_* set) and TEST_APP_DB_RESET=1, see conftest.py.
The identity source is a fixture table in the app schema, and emailed codes are
captured instead of sent.
"""
import re

import pytest
from sqlalchemy import text

from app import notify
from app.app_database import app_connection
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.ratelimit import limiter
from app.sessions import SESSION_COOKIE

EMAIL = "maria@example.com"
PHONE = "+1 555 010 0100"
SSN = "111-22-3333"  # lookup key LAW3333
CUSTOMER = "LAW3333"

# Same shape as ar_invoicehistoryheader: customer number and billtoname ("Last, First").
ROWS = [
    ("LAW3333", "Lawson, Maria"),  # single match
    ("CAR6666", "Carter, Ana"),  # two customer numbers that differ only in case...
    ("car6666", "Carter, Ana"),  # ...and the first name cannot tell them apart
    ("ORT7777", "Ortiz, Ben"),  # first name tells these two apart
    ("ort7777", "Ortiz, Carla"),
]


@pytest.fixture
def sent(monkeypatch):
    """Every emailed code, as (address, code)."""
    emails = []
    monkeypatch.setattr(notify, "send_code", lambda to, code, minutes: emails.append((to, code)))
    return emails


@pytest.fixture
def identity_rows(app_db, monkeypatch):
    app_db.execute(text("DROP TABLE IF EXISTS app.identity_fixture"))  # never reuse an older layout
    app_db.execute(text("CREATE TABLE app.identity_fixture (customerno varchar(20), billtoname varchar(50))"))
    for customerno, bill_to in ROWS:
        app_db.execute(text("INSERT INTO app.identity_fixture VALUES (:c, :b)"), {"c": customerno, "b": bill_to})
    app_db.commit()
    monkeypatch.setattr(get_settings(), "identity_source_table", "app.identity_fixture")

    # Lookups read the identity source through the read-only connection, so point it at the fixture.
    def fixture_connection():
        with app_connection() as conn:
            yield conn

    app.dependency_overrides[get_db] = fixture_connection
    yield
    app.dependency_overrides.pop(get_db, None)


def last_code(sent):
    return sent[-1][1]


def lookup(client, first="Maria", last="Lawson", ssn=SSN):
    return client.post("/api/auth/register/lookup", json={"first_name": first, "last_name": last, "ssn": ssn})


def send_code(client, token, email=EMAIL, phone=PHONE):
    return client.post("/api/auth/register/send-code", json={
        "registration_token": token, "email": email, "phone": phone})


def start_registration(client, first="Maria", last="Lawson", ssn=SSN):
    """Lookup and send the code. Returns the verification token."""
    found = lookup(client, first, last, ssn).json()
    assert found["status"] == "matched", found
    response = send_code(client, found["registration_token"])
    assert response.status_code == 200, response.text
    return response.json()["verification_token"]


def verify(client, token, code):
    return client.post("/api/auth/register/verify", json={"verification_token": token, "code": code})


def register(client, sent):
    return verify(client, start_registration(client), last_code(sent))


# ---------- Registration ----------

def test_single_match_registers_and_signs_in(client, identity_rows, sent, app_db):
    response = register(client, sent)
    assert response.status_code == 200, response.text
    assert response.json() == {"role": "end_user", "email": EMAIL, "customerno": CUSTOMER}
    assert SESSION_COOKIE in client.cookies
    row = app_db.execute(text("SELECT customerno, email, phone FROM app.users")).mappings().one()
    assert dict(row) == {"customerno": CUSTOMER, "email": EMAIL, "phone": "+15550100100"}


def test_emailed_code_is_six_digits(client, identity_rows, sent):
    start_registration(client)
    assert re.fullmatch(r"[0-9]{6}", last_code(sent))


def test_phone_is_stored_but_gets_no_code(client, identity_rows, sent):
    register(client, sent)
    assert [address for address, _ in sent] == [EMAIL]  # one email, nothing sent to the phone


def test_no_match_gives_the_generic_message(client, identity_rows):
    response = lookup(client, last="Nobody").json()
    assert response["status"] == "no_match"
    assert response["message"] == ("We couldn't find a matching account. "
                                   "Please check your details or contact support.")
    assert response["registration_token"] is None


def test_several_matches_go_to_review_and_are_never_linked(client, identity_rows, app_db, sent):
    response = lookup(client, first="Ana", last="Carter", ssn="000-00-6666").json()
    assert response == {"status": "needs_review", "message": "We need to verify a few more details",
                        "registration_token": None}
    queued = app_db.execute(text("SELECT count(*), max(candidate_customernos::text) FROM app.identity_review_queue")
                            ).one()
    assert queued[0] == 1 and "CAR6666" in queued[1] and "car6666" in queued[1]
    assert app_db.execute(text("SELECT count(*) FROM app.users")).scalar() == 0


def test_first_name_breaks_a_tie(client, identity_rows):
    response = lookup(client, first="Ben", last="Ortiz", ssn="111-11-7777").json()
    assert response["status"] == "matched"


def test_already_registered_customer_is_pointed_to_login(client, identity_rows, sent):
    register(client, sent)
    client.post("/api/auth/logout")
    again = lookup(client).json()
    assert again["status"] == "already_registered"
    assert again["message"] == "An account already exists for these details. Please log in instead."


def test_lookup_is_rate_limited_per_name_and_ssn(client, identity_rows):
    for _ in range(get_settings().lookup_max_attempts):
        assert lookup(client, last="Nobody").status_code == 200
    blocked = lookup(client, last="Nobody")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert lookup(client, first="Ben", last="Ortiz", ssn="111-11-7777").status_code == 200


def test_code_expires_after_the_ttl(client, identity_rows, sent, app_db):
    token = start_registration(client)
    app_db.execute(text("UPDATE app.otp_codes SET expires_at = now() - interval '1 second'"))
    app_db.commit()
    assert verify(client, token, last_code(sent)).status_code == 400
    assert app_db.execute(text("SELECT count(*) FROM app.users")).scalar() == 0


def test_code_is_locked_after_five_wrong_guesses(client, identity_rows, sent, app_db):
    token = start_registration(client)
    right = last_code(sent)
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(get_settings().otp_max_attempts):
        assert verify(client, token, wrong).status_code == 400
    assert verify(client, token, right).status_code == 400  # even the right code no longer works
    assert app_db.execute(text("SELECT attempts FROM app.otp_codes")).scalar() == get_settings().otp_max_attempts


def test_resend_is_blocked_during_the_cooldown(client, identity_rows, sent):
    token = start_registration(client)
    response = client.post("/api/auth/register/resend-code", json={"verification_token": token})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_resend_voids_the_old_code(client, identity_rows, sent, monkeypatch):
    token = start_registration(client)
    monkeypatch.setattr(get_settings(), "otp_resend_cooldown_seconds", 0)
    assert client.post("/api/auth/register/resend-code", json={"verification_token": token}).status_code == 200
    old_code, new_code = sent[0][1], sent[1][1]
    if old_code != new_code:
        assert verify(client, token, old_code).status_code == 400
    assert verify(client, token, new_code).status_code == 200


def test_send_is_rate_limited_per_email(client, identity_rows, sent, monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_resend_cooldown_seconds", 0)
    found = lookup(client).json()
    for _ in range(get_settings().otp_max_sends_per_hour):
        assert send_code(client, found["registration_token"]).status_code == 200
    assert send_code(client, found["registration_token"]).status_code == 429


def test_steps_cannot_be_used_out_of_order(client, identity_rows):
    found = lookup(client).json()
    assert verify(client, found["registration_token"], "123456").status_code == 401  # lookup token at verify


def test_forged_step_token_is_refused(client, identity_rows):
    response = send_code(client, "eyJraW5kIjoicmVnaXN0ZXIifQ.forged")
    assert response.status_code == 401


def test_invalid_phone_is_refused_before_anything_is_sent(client, identity_rows, sent):
    found = lookup(client).json()
    response = send_code(client, found["registration_token"], phone="abc")
    assert response.status_code == 422
    assert sent == []


# ---------- Sign-in ----------

def test_sign_in_with_email_code(client, identity_rows, sent):
    register(client, sent)
    client.post("/api/auth/logout")
    client.cookies.clear()
    limiter.reset()  # a sign-in a while after registration, not seconds later
    requested = client.post("/api/auth/login/request", json={"email": EMAIL})
    assert requested.status_code == 200
    verified = client.post("/api/auth/login/verify", json={
        "login_token": requested.json()["login_token"], "code": last_code(sent)})
    assert verified.status_code == 200, verified.text
    assert verified.json()["customerno"] == CUSTOMER


def test_sign_in_is_refused_for_a_phone_number(client, identity_rows):
    response = client.post("/api/auth/login/request", json={"email": PHONE})
    assert response.status_code == 422


def test_sign_in_answers_the_same_for_unknown_accounts(client, identity_rows, sent):
    response = client.post("/api/auth/login/request", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert "nobody" not in response.json()["email_masked"]
    assert sent == []  # nothing is sent for an unknown account
    verified = client.post("/api/auth/login/verify", json={
        "login_token": response.json()["login_token"], "code": "123456"})
    assert verified.status_code == 400
    assert verified.json()["detail"] == "That code is incorrect or has expired. Request a new code."


def test_sign_in_code_is_single_use(client, identity_rows, sent):
    register(client, sent)
    client.post("/api/auth/logout")
    client.cookies.clear()
    limiter.reset()  # a sign-in a while after registration, not seconds later
    requested = client.post("/api/auth/login/request", json={"email": EMAIL}).json()
    code = last_code(sent)
    assert client.post("/api/auth/login/verify", json={"login_token": requested["login_token"], "code": code}).status_code == 200
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.post("/api/auth/login/verify", json={"login_token": requested["login_token"], "code": code}).status_code == 400


def test_sign_in_requests_are_rate_limited(client, identity_rows, sent):
    register(client, sent)
    client.post("/api/auth/logout")
    limiter.reset()
    assert client.post("/api/auth/login/request", json={"email": EMAIL}).status_code == 200
    assert client.post("/api/auth/login/request", json={"email": EMAIL}).status_code == 429


# ---------- What is stored ----------

def test_stored_data_never_holds_the_ssn_or_a_plain_code(client, identity_rows, sent, app_db):
    register(client, sent)
    stored = app_db.execute(text("""
        SELECT coalesce(string_agg(x, ' '), '') FROM (
            SELECT ssn_last4_hash AS x FROM app.users
            UNION ALL SELECT code_hash FROM app.otp_codes
            UNION ALL SELECT metadata::text FROM app.auth_audit_log) t""")).scalar()
    assert "111223333" not in stored and "111-22-3333" not in stored
    assert last_code(sent) not in stored.split()


def test_admin_sees_the_review_queue_and_customers_do_not(client, identity_rows, sent):
    lookup(client, first="Ana", last="Carter", ssn="000-00-6666")  # anonymous: queues one review
    client.post("/api/admin/login", json={"email": "tester@example.com", "password": "correct horse battery staple"})
    queue = client.get("/api/admin/review-queue").json()
    assert [(item["submitted_first_name"], item["candidate_count"], item["status"]) for item in queue] == \
        [("Ana", 2, "pending")]
    assert "ssn" not in str(queue).lower() and "hash" not in str(queue).lower()

    client.cookies.clear()
    register(client, sent)
    assert client.get("/api/admin/review-queue").status_code == 403  # a customer session cannot see it


def test_test_mode_sends_nothing_and_accepts_123456(client, identity_rows, sent, monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_test_mode", True)
    found = lookup(client).json()
    token = send_code(client, found["registration_token"]).json()["verification_token"]
    assert sent == []  # no email goes out in test mode
    assert verify(client, token, "123456").status_code == 200
