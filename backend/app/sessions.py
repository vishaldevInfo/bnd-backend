"""Session cookies, role checks and short-lived signed flow tokens.

One cookie (bnd_session) holds either role:
- admin:    {"role": "admin", "email": ...}  (ENV login, see routes/admin.py)
- end_user: {"role": "end_user", "user_id": ...}

For end users the customer number and account status are read from the database
on every request, never trusted from the cookie. Disabling an account therefore
takes effect immediately.

Flow tokens carry the state between registration/login steps (for example the
matched customer number between lookup and contact). They are signed with a
different salt and carry a "kind", so one step's token cannot be used in another.
"""
from dataclasses import dataclass
from typing import Literal

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import text

from app.app_database import app_connection
from app.config import get_settings
from app.contact import normalize_email

SESSION_COOKIE = "bnd_session"
# v2: role-aware tokens. Sessions issued before the role claim existed are rejected.
SESSION_SALT = "bnd-session-v2"
FLOW_SALT = "bnd-flow-v1"
EXPIRED_MESSAGE = "Not signed in or session expired."


@dataclass(frozen=True)
class Session:
    role: Literal["admin", "end_user"]
    email: str | None = None  # admin
    user_id: str | None = None  # end_user


@dataclass(frozen=True)
class EndUser:
    user_id: str
    customerno: str
    email: str


@dataclass(frozen=True)
class InvoiceScope:
    """Which customer's invoices a request may see. None means every customer (admin)."""
    customerno: str | None


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret.get_secret_value(), salt=salt)


# ---------- Session tokens ----------

def issue_admin_session(email: str) -> str:
    return _serializer(SESSION_SALT).dumps({"role": "admin", "email": email})


def issue_end_user_session(user_id: str) -> str:
    return _serializer(SESSION_SALT).dumps({"role": "end_user", "user_id": user_id})


def read_session(token: str) -> Session | None:
    """Session for a valid, unexpired cookie, otherwise None."""
    max_age = int(get_settings().session_max_age_hours * 3600)
    try:
        data = _serializer(SESSION_SALT).loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("role") == "admin":
        # Only the configured admin account may hold an admin session.
        email = data.get("email")
        if email == normalize_email(get_settings().demo_email):
            return Session(role="admin", email=email)
        return None
    if data.get("role") == "end_user" and isinstance(data.get("user_id"), str):
        return Session(role="end_user", user_id=data["user_id"])
    return None


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(settings.session_max_age_hours * 3600),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True,
                           secure=get_settings().cookie_secure, samesite="lax")


def _expired_cookie_header() -> str:
    secure = "; Secure" if get_settings().cookie_secure else ""
    return f"{SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax{secure}"


# ---------- Flow tokens ----------

def issue_flow_token(kind: str, payload: dict) -> str:
    return _serializer(FLOW_SALT).dumps({**payload, "kind": kind})


def read_flow_token(token: str, kind: str, max_age_minutes: int) -> dict:
    """Payload of a flow token of this kind. Raises 401 when missing, forged, expired or of another kind."""
    try:
        data = _serializer(FLOW_SALT).loads(token, max_age=max_age_minutes * 60)
    except (SignatureExpired, BadSignature, TypeError):
        data = None
    if not isinstance(data, dict) or data.get("kind") != kind:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This step has expired. Please start again.")
    return data


# ---------- Request checks ----------

def require_same_origin(request: Request) -> None:
    """CSRF defence for state-changing requests. Browsers always send Origin on
    cross-site POSTs, so a foreign Origin is rejected. Requests without Origin
    (curl, tests) are allowed; the SameSite=Lax cookie covers the rest."""
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().allowed_origin_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request origin not allowed.")


def get_session(bnd_session: str | None = Cookie(default=None)) -> Session:
    """401 unless the request carries a valid session cookie."""
    session = read_session(bnd_session) if bnd_session else None
    if session is None:
        # Also delete an invalid or expired cookie, so the frontend stops treating
        # the browser as signed in (otherwise the login pages could loop).
        headers = {"Set-Cookie": _expired_cookie_header()} if bnd_session else None
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, EXPIRED_MESSAGE, headers=headers)
    return session


def optional_session(bnd_session: str | None = Cookie(default=None)) -> Session | None:
    return read_session(bnd_session) if bnd_session else None


def require_admin(session: Session = Depends(get_session)) -> Session:
    if session.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access only.")
    return session


def load_end_user(session: Session) -> EndUser:
    """The active account behind an end_user session, or 401 if it no longer exists or is disabled."""
    if session.role != "end_user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customer access only.")
    with app_connection() as conn:
        row = conn.execute(text("""
            SELECT id, customerno, email, status FROM app.users
            WHERE id = CAST(:user_id AS uuid)"""), {"user_id": session.user_id}).mappings().one_or_none()
    if row is None or row["status"] != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, EXPIRED_MESSAGE)
    return EndUser(user_id=str(row["id"]), customerno=row["customerno"], email=row["email"])


def require_end_user(session: Session = Depends(get_session)) -> EndUser:
    """The active customer behind the session. Admins get 403."""
    return load_end_user(session)


def invoice_scope(session: Session = Depends(get_session)) -> InvoiceScope:
    """Admins see every customer. End users see only their own customer number."""
    if session.role == "admin":
        return InvoiceScope(customerno=None)
    return InvoiceScope(customerno=load_end_user(session).customerno)
