"""Admin login (ENV account) and the admin-only identity review queue."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import Connection, text

from app import audit
from app.auth import INVALID_CREDENTIALS, check_admin_credentials, login_limiter
from app.contact import normalize_email
from app.app_database import get_app_conn
from app.ratelimit import client_ip
from app.schemas import CurrentUser, LoginRequest, ReviewItem
from app.sessions import issue_admin_session, require_admin, require_same_origin, set_session_cookie

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_same_origin)])


@router.post("/login", response_model=CurrentUser)
def admin_login(credentials: LoginRequest, request: Request, response: Response) -> CurrentUser:
    email = normalize_email(credentials.email)
    wait_seconds = login_limiter.seconds_until_allowed(email)
    if wait_seconds:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(wait_seconds)},
        )
    if not check_admin_credentials(email, credentials.password):
        login_limiter.record_failure(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    login_limiter.reset(email)
    set_session_cookie(response, issue_admin_session(email))
    audit.record("admin_login", ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    return CurrentUser(role="admin", email=email, customerno=None)


@router.get("/review-queue", response_model=list[ReviewItem], dependencies=[Depends(require_admin)])
def review_queue(status_filter: Literal["pending", "resolved"] = "pending",
                 conn: Connection = Depends(get_app_conn)) -> list[ReviewItem]:
    """Lookups that matched more than one customer. Candidate numbers are listed, never auto-linked."""
    rows = conn.execute(text("""
        SELECT id, submitted_first_name, submitted_last_name, jsonb_array_length(candidate_customernos) AS candidate_count,
               status, created_at
        FROM app.identity_review_queue
        WHERE status = :status
        ORDER BY created_at DESC
        LIMIT 200"""), {"status": status_filter}).mappings().all()
    return [ReviewItem(id=str(r["id"]), submitted_first_name=r["submitted_first_name"],
                       submitted_last_name=r["submitted_last_name"], candidate_count=r["candidate_count"],
                       status=r["status"], created_at=r["created_at"]) for r in rows]
