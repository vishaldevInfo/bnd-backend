"""Writable connection for the app-owned "app" schema.

The Sage reporting connection (database.py) is read-only. This one is separate,
uses its own role (see create_app_writer_role.sql), and is only used for end-user
accounts, codes, audit rows and the review queue. If it is not configured, the
end-user features answer 503 and the admin area keeps working.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import URL, Connection, Engine, create_engine

from app.config import get_settings
from app.errors import ServiceUnavailable

NOT_CONFIGURED = "Customer accounts are not configured on this server."


@lru_cache
def get_engine() -> Engine | None:
    """Built on first use, so settings are read when they are needed, not at import.
    None when APP_DB_USER or APP_DB_PASSWORD is not set."""
    s = get_settings()
    if not (s.app_db_user and s.app_db_password):
        return None
    return create_engine(
        URL.create(
            "postgresql+psycopg",
            username=s.app_db_user,
            password=s.app_db_password.get_secret_value(),
            host=s.app_db_host or s.db_host,
            port=s.app_db_port or s.db_port,
            database=s.app_db_name or s.db_name,
        ),
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=15000", "connect_timeout": 5},
    )


@contextmanager
def app_connection() -> Iterator[Connection]:
    """One connection with its own transaction. Callers commit explicitly."""
    engine = get_engine()
    if engine is None:
        raise ServiceUnavailable(NOT_CONFIGURED)
    with engine.connect() as connection:
        yield connection


def get_app_conn() -> Iterator[Connection]:
    """FastAPI dependency wrapping app_connection()."""
    with app_connection() as connection:
        yield connection
