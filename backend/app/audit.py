"""Writes to app.auth_audit_log.

Metadata must never hold an SSN, a code or a full phone number. Callers pass
only outcome labels. A failed audit write is logged and does not block the user,
because the audit log must not become a way to lock everyone out.
"""
import json
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.app_database import app_connection
from app.errors import ServiceUnavailable

logger = logging.getLogger("bnd.audit")

EVENTS = (
    "lookup_attempt", "lookup_match", "lookup_multi_match", "otp_sent", "otp_verified",
    "otp_failed", "login", "logout", "admin_login",
)


def record(event: str, *, user_id: str | None = None, ip: str | None = None,
           user_agent: str | None = None, metadata: dict | None = None) -> None:
    if event not in EVENTS:
        raise ValueError(f"Unknown audit event: {event}")
    try:
        with app_connection() as conn:
            conn.execute(text("""
                INSERT INTO app.auth_audit_log (user_id, event, ip, user_agent, metadata)
                VALUES (CAST(:user_id AS uuid), :event, :ip, :user_agent, CAST(:metadata AS jsonb))"""),
                {"user_id": user_id, "event": event, "ip": ip,
                 "user_agent": (user_agent or "")[:255] or None,
                 "metadata": json.dumps(metadata or {})})
            conn.commit()
    except (SQLAlchemyError, ServiceUnavailable):
        logger.exception("Could not write audit event %s", event)
