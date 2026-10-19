"""Admin credential check, admin login rate limiting and the session routes shared by both roles.

The admin account is the ENV-configured one (DEMO_EMAIL / DEMO_PASSWORD_HASH):
create the hash with `python -m app.create_demo_user`. Its login form lives at
/admin and posts to /api/admin/login (routes/admin.py).
"""
import hmac
import threading
import time

import bcrypt
from fastapi import APIRouter, Depends, Request, Response, status

from app import audit
from app.config import get_settings
from app.contact import normalize_email
from app.ratelimit import client_ip
from app.sessions import (
    Session,
    clear_session_cookie,
    get_session,
    load_end_user,
    optional_session,
    require_same_origin,
)
from app.schemas import CurrentUser

BCRYPT_ROUNDS = 12
BCRYPT_MAX_BYTES = 72  # bcrypt ignores/refuses input beyond 72 bytes
INVALID_CREDENTIALS = "Invalid email or password."


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    if len(password.encode()) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time bcrypt comparison. Malformed hashes and oversized input never match."""
    if len(password.encode()) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except ValueError:
        return False


# ---------- Admin login rate limiting ----------

class LoginRateLimiter:
    """Counts failed admin logins per email in a sliding window, in memory.

    Keyed by email rather than IP because requests arrive through the Next.js
    proxy. State resets when the backend restarts.
    """

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        window = get_settings().login_window_minutes * 60
        recent = [t for t in self._failures.get(key, []) if now - t < window]
        self._failures[key] = recent
        return recent

    def seconds_until_allowed(self, key: str) -> int:
        """0 if another attempt is allowed, otherwise seconds to wait."""
        settings = get_settings()
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)
            if len(recent) < settings.login_max_failures:
                return 0
            return int(recent[0] + settings.login_window_minutes * 60 - now) + 1

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._recent(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)


login_limiter = LoginRateLimiter()


def check_admin_credentials(email: str, password: str) -> bool:
    """Runs bcrypt even for a wrong email, so both failure modes take the same time."""
    settings = get_settings()
    password_ok = verify_password(password, settings.demo_password_hash.get_secret_value())
    email_ok = hmac.compare_digest(email.encode(), normalize_email(settings.demo_email).encode())
    return password_ok and email_ok


# ---------- Routes shared by both roles ----------

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUser)
def me(session: Session = Depends(get_session)) -> CurrentUser:
    if session.role == "admin":
        return CurrentUser(role="admin", email=session.email, customerno=None)
    user = load_end_user(session)
    return CurrentUser(role="end_user", email=user.email, customerno=user.customerno)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_same_origin)])
def logout(request: Request, response: Response, session: Session | None = Depends(optional_session)) -> None:
    if session is not None and session.role == "end_user":
        audit.record("logout", user_id=session.user_id, ip=client_ip(request),
                     user_agent=request.headers.get("user-agent"))
    clear_session_cookie(response)

