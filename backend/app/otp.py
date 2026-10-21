"""One-time email codes.

A challenge is one verification attempt. It has one live code at a time: asking for a
new code voids the old one. Codes are stored as HMACs keyed with the server secret, and
the challenge id is part of the MAC, so a code works only for its own challenge.
"""
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, text

from app import notify
from app.config import get_settings

logger = logging.getLogger("bnd.otp")
TEST_CODE = "123456"


def new_challenge_id() -> str:
    return str(uuid.uuid4())


def _hash(challenge_id: str, code: str) -> str:
    key = get_settings().session_secret.get_secret_value().encode()
    return hmac.new(key, f"{challenge_id}|{code}".encode(), hashlib.sha256).hexdigest()


def issue_code(conn: Connection, *, challenge_id: str, user_id: str | None, purpose: str, email: str) -> str:
    """Create a new code for the challenge, void the previous one, save it and return the code."""
    code = TEST_CODE if get_settings().otp_test_mode else f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(UTC) + timedelta(minutes=get_settings().otp_ttl_minutes)
    conn.execute(text("""
        UPDATE app.otp_codes SET consumed_at = now()
        WHERE challenge_id = CAST(:challenge_id AS uuid) AND consumed_at IS NULL"""),
        {"challenge_id": challenge_id})
    conn.execute(text("""
        INSERT INTO app.otp_codes (user_id, challenge_id, email, purpose, code_hash, expires_at)
        VALUES (CAST(:user_id AS uuid), CAST(:challenge_id AS uuid), :email, :purpose, :code_hash, :expires_at)"""),
        {"user_id": user_id, "challenge_id": challenge_id, "email": email, "purpose": purpose,
         "code_hash": _hash(challenge_id, code), "expires_at": expires_at})
    conn.commit()
    return code


def send_code(email: str, code: str) -> None:
    """Email the code. Raises notify.DeliveryError if the mail is not sent."""
    if get_settings().otp_test_mode:
        logger.warning("TEST MODE: no email sent. Use code %s", TEST_CODE)
        return
    notify.send_code(email, code, get_settings().otp_ttl_minutes)


def verify_code(conn: Connection, challenge_id: str, code: str) -> bool:
    """True when `code` is the live code for this challenge.

    A wrong guess is counted, and after OTP_MAX_ATTEMPTS the code is dead. A correct
    code is used up, so it cannot be used twice. The transaction is committed either way.
    """
    row = conn.execute(text("""
        SELECT id, code_hash, attempts FROM app.otp_codes
        WHERE challenge_id = CAST(:challenge_id AS uuid) AND consumed_at IS NULL AND expires_at > now()
        ORDER BY created_at DESC LIMIT 1 FOR UPDATE"""),
        {"challenge_id": challenge_id}).mappings().one_or_none()

    if row is None or row["attempts"] >= get_settings().otp_max_attempts:
        conn.commit()
        return False
    if not hmac.compare_digest(_hash(challenge_id, code), row["code_hash"]):
        conn.execute(text("UPDATE app.otp_codes SET attempts = attempts + 1 WHERE id = :id"), {"id": row["id"]})
        conn.commit()
        return False
    conn.execute(text("UPDATE app.otp_codes SET consumed_at = now() WHERE id = :id"), {"id": row["id"]})
    conn.commit()
    return True
