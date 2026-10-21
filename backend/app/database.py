"""PostgreSQL connection for the existing chubbstub database.

The application only reads Sage data. Every session is opened with
default_transaction_read_only=on, so even a misconfigured privileged account
cannot modify the business tables through this app.
"""
from collections.abc import Iterator

from sqlalchemy import URL, Connection, create_engine, text

from app.config import get_settings


import logging
logger = logging.getLogger("uvicorn.error")

settings = get_settings()

engine = create_engine(
    URL.create(
        "postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    ),
    pool_pre_ping=True,
    connect_args={
        "options": "-c default_transaction_read_only=on -c statement_timeout=15000",  # Fix 2 liya to hata do
        "connect_timeout": 10,
        "sslmode": "require",
    },
)


def get_db() -> Iterator[Connection]:
    """FastAPI dependency: one connection per request, always returned to the pool."""
    with engine.connect() as connection:
        yield connection


def database_is_reachable() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False
    

# def database_is_reachable() -> bool:
#     try:
#         with engine.connect() as connection:
#             connection.execute(text("SELECT 1"))
#         return True
#     except Exception:
#         return False
