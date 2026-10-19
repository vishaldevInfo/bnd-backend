"""Customer registration and sign-in. Both use a one-time code sent to the customer's email.

Registration: lookup (name + SSN) -> send-code (email + phone) -> verify (creates the account)
Sign-in:      login/request (email) -> login/verify (code)

The phone number is stored for contact only. It is not verified.
"""
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from app import audit, identity, otp
from app.app_database import get_app_conn
from app.config import get_settings
from app.contact import mask_email, normalize_email, normalize_phone
from app.database import get_db
from app.errors import ServiceUnavailable
from app.notify import DeliveryError
from app.ratelimit import client_ip, limiter
from app.schemas import (
    CodeSent,
    CurrentUser,
    LoginCodeSent,
    LoginRequestBody,
    LoginVerifyRequest,
    LookupRequest,
    LookupResult,
    ResendRequest,
    ResendResult,
    SendCodeRequest,
    VerifyRequest,
)
from app.sessions import issue_end_user_session, issue_flow_token, read_flow_token, require_same_origin, set_session_cookie

logger = logging.getLogger("bnd.auth")
router = APIRouter(prefix="/api/auth", tags=["customer auth"], dependencies=[Depends(require_same_origin)])

NO_MATCH = "We couldn't find a matching account. Please check your details or contact support."
ALREADY_REGISTERED = "An account already exists for these details. Please log in instead."
NEEDS_REVIEW = "We need to verify a few more details"
MATCHED = "OK, we found your account"
IN_USE = "These contact details are already in use. Please log in instead, or contact support."
CODE_ERROR = "That code is incorrect or has expired. Request a new code."


# ---------- Helpers ----------

def _take(key: str, max_events: int, window_seconds: int) -> None:
    """Count one attempt against a rate limit. Answers 429 with Retry-After when over the limit."""
    wait = limiter.take(key, max_events, window_seconds)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Please wait and try again.",
                            headers={"Retry-After": str(wait)})


def _take_code_send(email: str) -> None:
    """Limits code emails per address: one per cooldown, and a few per hour. Shared by sign-up and sign-in,
    so the limit cannot reveal whether an account exists."""
    s = get_settings()
    _take(f"code:cooldown:{email}", 1, s.otp_resend_cooldown_seconds)
    _take(f"code:hourly:{email}", s.otp_max_sends_per_hour, 60 * 60)


def _keyed(label: str, *parts: str) -> str:
    """Keyed HMAC, so rate-limit keys and stored hashes never hold raw SSN digits."""
    key = get_settings().session_secret.get_secret_value().encode()
    return hmac.new(key, f"{label}|{'|'.join(parts)}".encode(), hashlib.sha256).hexdigest()


def _send_code(email: str, code: str) -> None:
    try:
        otp.send_code(email, code)
    except DeliveryError as exc:
        logger.error("Code email failed: %s", exc)
        raise ServiceUnavailable("We couldn't send the code right now. Please try again in a few minutes.") from exc


def _ensure_not_registered(conn: Connection, customerno: str, email: str, phone: str) -> None:
    if conn.execute(text("SELECT 1 FROM app.users WHERE customerno = :customerno LIMIT 1"),
                    {"customerno": customerno}).scalar():
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_REGISTERED)
    if conn.execute(text("SELECT 1 FROM app.users WHERE email = :email OR phone = :phone LIMIT 1"),
                    {"email": email, "phone": phone}).scalar():
        raise HTTPException(status.HTTP_409_CONFLICT, IN_USE)


# ---------- Registration ----------

@router.post("/register/lookup", response_model=LookupResult)
def lookup(body: LookupRequest, request: Request, db: Connection = Depends(get_db),
           conn: Connection = Depends(get_app_conn)) -> LookupResult:
    s = get_settings()
    ip = client_ip(request)
    last3 = identity.last_name_prefix(body.last_name)
    ssn4 = body.ssn[-4:]

    # Both limits count every attempt. The per-combination one stops SSN guessing even when
    # the attacker changes IP address.
    _take(f"lookup:ip:{ip}", s.lookup_ip_max_attempts, s.lookup_window_minutes * 60)
    _take(f"lookup:id:{_keyed('lookup', last3, ssn4)}", s.lookup_max_attempts, s.lookup_window_minutes * 60)
    audit.record("lookup_attempt", ip=ip, user_agent=request.headers.get("user-agent"))

    candidates = identity.find_identity_candidates(db, last3, ssn4, body.first_name)
    if not candidates:
        return LookupResult(status="no_match", message=NO_MATCH)

    if len(candidates) > 1:
        # Never link an ambiguous match automatically. An admin resolves it from the review queue.
        conn.execute(text("""
            INSERT INTO app.identity_review_queue
                (submitted_first_name, submitted_last_name, ssn_last4_hash, candidate_customernos)
            VALUES (:first_name, :last_name, :ssn_hash, CAST(:candidates AS jsonb))"""),
            {"first_name": body.first_name, "last_name": body.last_name,
             "ssn_hash": _keyed("ssn4", ssn4), "candidates": json.dumps(candidates)})
        conn.commit()
        audit.record("lookup_multi_match", ip=ip, metadata={"candidate_count": len(candidates)})
        return LookupResult(status="needs_review", message=NEEDS_REVIEW)

    customerno = candidates[0]
    linked = conn.execute(text("SELECT 1 FROM app.users WHERE customerno = :customerno LIMIT 1"),
                          {"customerno": customerno}).scalar()
    audit.record("lookup_match", ip=ip, metadata={"already_registered": bool(linked)})
    if linked:
        return LookupResult(status="already_registered", message=ALREADY_REGISTERED)

    token = issue_flow_token("register", {
        "customerno": customerno,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "ssn_last4_hash": _keyed("ssn4", ssn4),
    })
    return LookupResult(status="matched", message=MATCHED, registration_token=token)


@router.post("/register/send-code", response_model=CodeSent)
def send_code(body: SendCodeRequest, request: Request, conn: Connection = Depends(get_app_conn)) -> CodeSent:
    s = get_settings()
    flow = read_flow_token(body.registration_token, "register", s.registration_token_minutes)
    try:
        email = normalize_email(body.email)
        phone = normalize_phone(body.phone)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    _ensure_not_registered(conn, flow["customerno"], email, phone)
    _take(f"otp:ip:{client_ip(request)}", s.lookup_ip_max_attempts, s.lookup_window_minutes * 60)
    _take_code_send(email)

    challenge_id = otp.new_challenge_id()
    code = otp.issue_code(conn, challenge_id=challenge_id, user_id=None, purpose="register", email=email)
    print(code)
    _send_code(email, code)
    audit.record("otp_sent", metadata={"purpose": "register"})

    token = issue_flow_token("register_verify", {
        "customerno": flow["customerno"],
        "first_name": flow["first_name"],
        "last_name": flow["last_name"],
        "ssn_last4_hash": flow["ssn_last4_hash"],
        "email": email,
        "phone": phone,
        "challenge_id": challenge_id,
    })
    return CodeSent(verification_token=token, email_masked=mask_email(email),
                    expires_in_seconds=s.otp_ttl_minutes * 60, resend_after_seconds=s.otp_resend_cooldown_seconds)


@router.post("/register/resend-code", response_model=ResendResult)
def resend_code(body: ResendRequest, conn: Connection = Depends(get_app_conn)) -> ResendResult:
    s = get_settings()
    flow = read_flow_token(body.verification_token, "register_verify", s.registration_token_minutes)
    _ensure_not_registered(conn, flow["customerno"], flow["email"], flow["phone"])
    _take_code_send(flow["email"])

    code = otp.issue_code(conn, challenge_id=flow["challenge_id"], user_id=None, purpose="register",
                          email=flow["email"])
    _send_code(flow["email"], code)
    audit.record("otp_sent", metadata={"purpose": "register", "resend": True})
    return ResendResult(message="We sent a new code.", resend_after_seconds=s.otp_resend_cooldown_seconds)


@router.post("/register/verify", response_model=CurrentUser)
def verify_registration(body: VerifyRequest, request: Request, response: Response,
                        conn: Connection = Depends(get_app_conn)) -> CurrentUser:
    s = get_settings()
    flow = read_flow_token(body.verification_token, "register_verify", s.registration_token_minutes)
    ip = client_ip(request)
    _take(f"verify:ip:{ip}", s.verify_ip_max_attempts, s.verify_window_minutes * 60)
    _ensure_not_registered(conn, flow["customerno"], flow["email"], flow["phone"])

    if not otp.verify_code(conn, flow["challenge_id"], body.code):
        audit.record("otp_failed", ip=ip, metadata={"purpose": "register"})
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CODE_ERROR)

    try:
        user_id = conn.execute(text("""
            INSERT INTO app.users (customerno, first_name, last_name, ssn_last4_hash, email, phone,
                                   email_verified_at, last_login_at)
            VALUES (:customerno, :first_name, :last_name, :ssn_last4_hash, :email, :phone, now(), now())
            RETURNING id"""), {
            "customerno": flow["customerno"], "first_name": flow["first_name"], "last_name": flow["last_name"],
            "ssn_last4_hash": flow["ssn_last4_hash"], "email": flow["email"], "phone": flow["phone"],
        }).scalar_one()
        conn.commit()
    except IntegrityError as exc:
        # Someone registered this customer or these contact details first.
        conn.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_REGISTERED) from exc

    audit.record("otp_verified", user_id=str(user_id), ip=ip, metadata={"purpose": "register"})
    audit.record("login", user_id=str(user_id), ip=ip, metadata={"method": "registration"})
    set_session_cookie(response, issue_end_user_session(str(user_id)))
    return CurrentUser(role="end_user", email=flow["email"], customerno=flow["customerno"])


# ---------- Sign-in ----------

@router.post("/login/request", response_model=LoginCodeSent)
def request_login_code(body: LoginRequestBody, request: Request,
                       conn: Connection = Depends(get_app_conn)) -> LoginCodeSent:
    s = get_settings()
    _take(f"login:ip:{client_ip(request)}", s.lookup_ip_max_attempts, s.lookup_window_minutes * 60)
    try:
        email = normalize_email(body.email)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # The same limits apply whether or not the account exists, and the response is the same,
    # so this endpoint cannot be used to find out who is registered.
    _take_code_send(email)
    user = conn.execute(text("SELECT id FROM app.users WHERE email = :email AND status = 'active'"),
                        {"email": email}).mappings().one_or_none()
    challenge_id = otp.new_challenge_id()
    user_id = str(user["id"]) if user else None
    if user_id:
        code = otp.issue_code(conn, challenge_id=challenge_id, user_id=user_id, purpose="login", email=email)
        _send_code(email, code)
        audit.record("otp_sent", user_id=user_id, metadata={"purpose": "login"})

    token = issue_flow_token("login", {"user_id": user_id, "email": email, "challenge_id": challenge_id})
    return LoginCodeSent(login_token=token, email_masked=mask_email(email),
                         expires_in_seconds=s.otp_ttl_minutes * 60)


@router.post("/login/verify", response_model=CurrentUser)
def verify_login(body: LoginVerifyRequest, request: Request, response: Response,
                 conn: Connection = Depends(get_app_conn)) -> CurrentUser:
    s = get_settings()
    flow = read_flow_token(body.login_token, "login", s.otp_ttl_minutes)
    ip = client_ip(request)
    _take(f"verify:ip:{ip}", s.verify_ip_max_attempts, s.verify_window_minutes * 60)
    user_id = flow["user_id"]

    # No account means no code was issued, so the check fails the same way as a wrong code.
    if user_id is None or not otp.verify_code(conn, flow["challenge_id"], body.code):
        audit.record("otp_failed", user_id=user_id, ip=ip, metadata={"purpose": "login"})
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CODE_ERROR)

    user = conn.execute(text("SELECT customerno, email, status FROM app.users WHERE id = CAST(:id AS uuid)"),
                        {"id": user_id}).mappings().one_or_none()
    if user is None or user["status"] != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CODE_ERROR)
    conn.execute(text("UPDATE app.users SET last_login_at = :now, updated_at = :now WHERE id = CAST(:id AS uuid)"),
                 {"now": datetime.now(UTC), "id": user_id})
    conn.commit()

    audit.record("otp_verified", user_id=user_id, ip=ip, metadata={"purpose": "login"})
    audit.record("login", user_id=user_id, ip=ip, user_agent=request.headers.get("user-agent"),
                 metadata={"method": "email_code"})
    set_session_cookie(response, issue_end_user_session(user_id))
    return CurrentUser(role="end_user", email=user["email"], customerno=user["customerno"])
