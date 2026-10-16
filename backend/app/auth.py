"""Demo login: bcrypt password check, login rate limiting, signed session
cookie, and the auth routes.

There is one demo account, configured in backend/.env (see create_demo_user.py).
The session is a signed, HTTP-only cookie holding only the email and its issue
time; the signature stops tampering and itsdangerous enforces expiry.
"""
import hmac
import threading
import time

import bcrypt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings
from app.schemas import CurrentUser, LoginRequest

SESSION_COOKIE = "bnd_session"
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


def normalize_email(email: str) -> str:
    return email.strip().casefold()


# ---------- Login rate limiting ----------

class LoginRateLimiter:
    """Counts failed logins per email in a sliding window, in memory.

    Keyed by email rather than IP because requests arrive through the Next.js
    proxy. In-memory state is enough for this single-process demo; it resets
    when the backend restarts.
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


# ---------- Session tokens ----------

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret.get_secret_value(), salt="bnd-session")


def create_session_token(email: str) -> str:
    return _serializer().dumps({"email": email})


def read_session_token(token: str) -> str | None:
    """Return the email for a valid, unexpired token, otherwise None."""
    max_age = int(get_settings().session_max_age_hours * 3600)
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    email = data.get("email") if isinstance(data, dict) else None
    # Only the configured demo user may hold a session.
    return email if email == normalize_email(get_settings().demo_email) else None


# ---------- FastAPI dependencies ----------

def require_user(bnd_session: str | None = Cookie(default=None)) -> CurrentUser:
    """Protects business endpoints: 401 unless the request carries a valid session cookie."""
    email = read_session_token(bnd_session) if bnd_session else None
    if email is None:
        # Also delete an invalid or expired cookie, so the frontend stops treating
        # the browser as signed in (otherwise /login and / could redirect in a loop).
        headers = {"Set-Cookie": _expired_cookie_header()} if bnd_session else None
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in or session expired.", headers=headers)
    return CurrentUser(email=email)


def _expired_cookie_header() -> str:
    secure = "; Secure" if get_settings().cookie_secure else ""
    return f"{SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax{secure}"


def require_same_origin(request: Request) -> None:
    """CSRF defence for state-changing requests. Browsers always send Origin on
    cross-site POSTs, so a foreign Origin is rejected. Requests without Origin
    (curl, tests) are allowed; the SameSite=Lax cookie covers the rest."""
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().allowed_origin_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request origin not allowed.")


# ---------- Routes ----------

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=CurrentUser, dependencies=[Depends(require_same_origin)])
def login(credentials: LoginRequest, response: Response) -> CurrentUser:
    settings = get_settings()
    email = normalize_email(credentials.email)

    wait_seconds = login_limiter.seconds_until_allowed(email)
    if wait_seconds:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(wait_seconds)},
        )

    # Always run the bcrypt check so a wrong email takes as long as a wrong password.
    password_ok = verify_password(credentials.password, settings.demo_password_hash.get_secret_value())
    email_ok = hmac.compare_digest(email.encode(), normalize_email(settings.demo_email).encode())
    if not (password_ok and email_ok):
        login_limiter.record_failure(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    login_limiter.reset(email)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(email),
        max_age=int(settings.session_max_age_hours * 3600),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return CurrentUser(email=email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_same_origin)])
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True,
                           secure=get_settings().cookie_secure, samesite="lax")


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(require_user)) -> CurrentUser:
    return user
