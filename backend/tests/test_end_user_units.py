"""Pure rules for end-user accounts: input normalisation, code hashing, flow tokens, rate limits."""
import pytest
from fastapi import HTTPException

from app import identity, otp
from app.contact import mask_email, normalize_email, normalize_phone
from app.ratelimit import SlidingWindowLimiter
from app.schemas import LookupRequest
from app.sessions import issue_flow_token, read_flow_token


@pytest.mark.parametrize("raw, expected", [
    ("(555) 010-0100", "+15550100100"),
    ("15550100100", "+15550100100"),
    ("555 010 0100", "+15550100100"),
    ("+44 20 7946 0958", "+442079460958"),
])
def test_phone_numbers_normalise_to_e164(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "+0123456789", "12345", "+1 555 01", ""])
def test_invalid_phone_numbers_are_refused(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_email_is_trimmed_and_lowercased():
    assert normalize_email("  Jo.Smith@Example.COM ") == "jo.smith@example.com"
    with pytest.raises(ValueError):
        normalize_email("not-an-email")


def test_masking_hides_most_of_the_email():
    assert mask_email("jo.smith@example.com") == "j***@example.com"


def test_lookup_normalises_ssn_and_names():
    request = LookupRequest(first_name="  Maria ", last_name="Gonzalez", ssn="123-45-6789")
    assert request.ssn == "123456789"
    assert request.first_name == "Maria"


@pytest.mark.parametrize("payload", [
    {"last_name": "Li", "ssn": "123456789"},  # fewer than 3 letters of last name
    {"last_name": "Gonzalez", "ssn": "12345678"},  # not 9 digits
    {"last_name": "R2D2", "ssn": "123456789"},  # digits in a name
    {"last_name": "Gonzalez; DROP", "ssn": "123456789"},  # punctuation outside allowed set
])
def test_lookup_rejects_bad_input(payload):
    with pytest.raises(ValueError):
        LookupRequest(first_name="Maria", **payload)


def test_ssn_last4_comes_from_nine_digits_only():
    assert identity.normalize_ssn_last4("123-45-6789") == "6789"
    assert identity.last_name_prefix("  Gonzalez ") == "gon"


@pytest.mark.parametrize("name", ["customer_identity; DROP TABLE x", "a b", "schema.table.extra", ""])
def test_identity_source_names_are_checked_before_use_in_sql(monkeypatch, name):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "identity_source_table", name)
    with pytest.raises(ValueError):
        identity._table_and_columns()


def test_customer_number_is_last_three_letters_and_ssn_last_four():
    assert identity.customerno_key("kum", "4798") == "KUM4798"
    assert identity.customerno_key(identity.last_name_prefix("Kumah"), identity.normalize_ssn_last4("123-45-4798")) == "KUM4798"


@pytest.mark.parametrize("bill_to, expected", [
    ("Kumah, Joana", "joana"),
    ("HATCHER  SAMANTHA", "samantha"),
    ("FRYE/CHERI/", None),  # unclear format: cannot break a tie
    (None, None),
])
def test_first_name_is_read_from_bill_to(bill_to, expected):
    assert identity.first_name_from_bill_to(bill_to) == expected


def test_code_hash_is_bound_to_its_challenge():
    stored = otp._hash("challenge-a", "123456")
    assert stored == otp._hash("challenge-a", "123456")
    assert stored != otp._hash("challenge-b", "123456")
    assert stored != otp._hash("challenge-a", "654321")


def test_flow_token_round_trips_for_its_own_kind():
    token = issue_flow_token("register", {"customerno": "T-1"})
    assert read_flow_token(token, "register", 15)["customerno"] == "T-1"


def test_flow_token_is_refused_at_another_step():
    token = issue_flow_token("register", {"customerno": "T-1"})
    with pytest.raises(HTTPException) as refused:
        read_flow_token(token, "login", 10)
    assert refused.value.status_code == 401


def test_tampered_or_expired_flow_token_is_refused():
    token = issue_flow_token("login", {"user_id": "u"})
    with pytest.raises(HTTPException):
        read_flow_token(token[:-2] + "xx", "login", 10)
    with pytest.raises(HTTPException):
        read_flow_token(token, "login", -1)  # treated as already expired


def test_sliding_window_blocks_after_limit_and_recovers():
    limiter = SlidingWindowLimiter()
    assert [limiter.take("k", 2, 60) for _ in range(2)] == [0, 0]
    wait = limiter.take("k", 2, 60)
    assert 0 < wait <= 61
    assert limiter.take("other", 2, 60) == 0  # keys are independent
    limiter.reset()
    assert limiter.take("k", 2, 60) == 0


def test_identity_lookup_finds_no_customer_for_an_unknown_key(db):
    assert identity.find_identity_candidates(db, "zzz", "0000", "Nobody") == []


def test_identity_source_missing_table_gives_a_clear_503_error(db, monkeypatch):
    """A configured table that does not exist must not look like a server crash."""
    from app.config import get_settings
    from app.errors import ServiceUnavailable

    monkeypatch.setattr(get_settings(), "identity_source_table", "no_such_identity_table")
    with pytest.raises(ServiceUnavailable) as unavailable:
        identity.find_identity_candidates(db, "gon", "6789", "Maria")
    assert "not configured" in unavailable.value.message
