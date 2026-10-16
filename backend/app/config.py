"""Application settings, loaded from environment variables or backend/.env.

Startup fails with a clear list of missing settings if anything required is absent.
Secret values are never printed.
"""
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Existing Sage reporting database. Kept as separate parts so passwords with
    # special characters never need URL-encoding.
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "chubbstub"
    db_user: str
    db_password: SecretStr

    # The source data has no currency column; this label is a business configuration.
    amount_currency_label: str = "USD"

    # Demo login. Create these values with: python -m app.create_demo_user --email ...
    demo_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    demo_password_hash: SecretStr
    session_secret: SecretStr = Field(min_length=32)
    session_max_age_hours: float = 8
    # True when served over HTTPS. Must stay False for plain http://localhost.
    cookie_secure: bool = False
    # Browser origins allowed to POST to the API (CSRF defence, comma-separated).
    allowed_origins: str = "http://localhost:3010"
    # Failed logins allowed per email within the window before answering 429.
    login_max_failures: int = 5
    login_window_minutes: int = 15

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
