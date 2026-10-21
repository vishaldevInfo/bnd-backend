"""FastAPI entry point. Run with: uvicorn app.main:app --reload"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import auth
from app.database import database_is_reachable
from app.errors import ServiceUnavailable
from app.routes import admin, dashboard, end_user_auth, invoices, portal, reports

logger = logging.getLogger("bnd")

app = FastAPI(
    title="BND Invoice Reporting API",
    description="Read-only invoice reporting over the Sage 100 extract in PostgreSQL.",
    version="0.2.0",
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(end_user_auth.router)
app.include_router(dashboard.router)
app.include_router(invoices.router)
app.include_router(portal.router)
app.include_router(reports.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Every error response has the same shape: {"detail": "<readable message>"}.
    messages = [f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages) or "Invalid request."})


@app.exception_handler(ServiceUnavailable)
async def unavailable_handler(request: Request, exc: ServiceUnavailable) -> JSONResponse:
    # The message is written to be shown to users. Internal causes are logged, not returned.
    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Log the real error for developers; never send SQL or connection details to the client.
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=503, content={"detail": "The database is currently unavailable."})


@app.get("/api/health", tags=["health"])
def health() -> JSONResponse:
    if database_is_reachable():
        return JSONResponse({"status": "ok", "database": "ok"})
    return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})
