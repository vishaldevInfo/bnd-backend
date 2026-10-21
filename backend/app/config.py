"""Application settings, loaded from environment variables or backend/.env.

Startup fails with a clear list of missing settings if anything required is absent.
Secret values are never printed.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Sage reporting database (read-only role). Parts, so passwords need no URL-encoding.
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "chubbstub"
    db_user: str
    db_password: SecretStr

    # Writer role for the app-owned "app" schema (customer accounts only). Unset = customer
    # accounts are off and answer 503; the admin area still works.
    app_db_user: str | None = None
    app_db_password: SecretStr | None = None
    app_db_host: str | None = None  # default: same as DB_HOST
    app_db_port: int | None = None  # default: same as DB_PORT
    app_db_name: str | None = None  # default: same as DB_NAME

    # The source data has no currency column; this label is a business configuration.
    amount_currency_label: str = "USD"

    # Admin login. Create the hash with: python -m app.create_demo_user --email ...
    demo_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    demo_password_hash: SecretStr
    session_secret: SecretStr = Field(min_length=32)
    session_max_age_hours: float = 8
    cookie_secure: bool = False  # true when served over HTTPS
    allowed_origins: str = "https://bnd-frontend-1.onrender.com/,http://localhost:3010"  # browser origins allowed to POST (CSRF check)
    login_max_failures: int = 5  # failed admin sign-ins per email...
    login_window_minutes: int = 15  # ...within this window

    # Read the client IP from X-Forwarded-For (last hop). Enable only behind the Next.js
    # proxy, which sets that header. Otherwise anyone can spoof it.
    trust_proxy_headers: bool = False

    # Customer lookup: customer number must equal <last 3 letters><SSN last 4>. See identity.py.
    # TODO(client): confirm that the 4 digits are the SSN's last 4 digits.
    identity_source_table: str = "ar_invoicehistoryheader"
    identity_customerno_column: str = "customerno"
    identity_name_column: str = "billtoname"

    # Rate limits (per process, in memory)
    lookup_max_attempts: int = 5  # per name + SSN combination
    lookup_ip_max_attempts: int = 20  # per client IP
    lookup_window_minutes: int = 15
    verify_ip_max_attempts: int = 20  # code checks per client IP
    verify_window_minutes: int = 15

    # One-time email codes
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5  # wrong guesses before a code is dead
    otp_resend_cooldown_seconds: int = 60
    otp_max_sends_per_hour: int = 5  # codes to one email address
    registration_token_minutes: int = 15  # lifetime of the signed step tokens

    # TEST MODE ONLY: no email is sent and every code is "123456". Refused on HTTPS.
    otp_test_mode: bool = False

    # Email delivery. "console" writes the code to the server log (development only).
    email_provider: Literal["console", "smtp"] = "console"
    email_from: str = "no-reply@example.com"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True

    # Country code added to phone numbers typed without "+" (stored in E.164 form).
    phone_default_country_code: str = "1"

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Console delivery writes live codes to the server log, so refuse it on HTTPS (production).
    # Checked here rather than in a validator, because pydantic would echo every setting.
    if settings.cookie_secure and settings.email_provider == "console":
        raise SystemExit("Startup refused: EMAIL_PROVIDER must not be 'console' when COOKIE_SECURE=true.")
    if settings.cookie_secure and settings.otp_test_mode:
        raise SystemExit("Startup refused: OTP_TEST_MODE must not be enabled when COOKIE_SECURE=true.")
    return settings
