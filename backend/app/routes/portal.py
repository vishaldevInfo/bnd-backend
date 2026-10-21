"""Customer dashboard summary. Every number is limited to the signed-in customer's own invoices.

The invoice list itself is GET /api/invoices, which already applies the same scope.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Connection

from app import invoice_queries as q
from app.config import get_settings
from app.database import get_db
from app.routes.invoices import date_range
from app.schemas import PeriodTotals, PortalSummary
from app.sessions import EndUser, require_end_user

router = APIRouter(prefix="/api/portal", tags=["portal"])


def _period(db: Connection, customerno: str, start: date | None, end: date | None) -> PeriodTotals:
    totals = q.invoice_totals(db, q.InvoiceFilters(start=start, end=end, customerno=customerno))
    return PeriodTotals(
        start=start,
        end=end,
        invoice_count=totals["invoice_count"],
        total_amount=totals["total_amount"],
        average_amount=q.average_amount(totals["total_amount"], totals["invoice_count"]),
        active_facilities=totals["facility_count"],
    )


@router.get("/summary", response_model=PortalSummary)
def summary(
    dates: tuple[date | None, date | None] = Depends(date_range),
    customer: EndUser = Depends(require_end_user),
    db: Connection = Depends(get_db),
) -> PortalSummary:
    start, end = dates
    previous = None
    if start and end:
        # Same-length period immediately before `start`, for the change badges.
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - (end - start)
        previous = _period(db, customer.customerno, previous_start, previous_end)

    bounds = q.invoice_date_bounds(db, customer.customerno)
    return PortalSummary(
        currency=get_settings().amount_currency_label,
        first_invoice_date=bounds["first_invoice_date"],
        last_invoice_date=bounds["last_invoice_date"],
        current=_period(db, customer.customerno, start, end),
        previous=previous,
        monthly=q.monthly_totals(db, q.InvoiceFilters(start=start, end=end, customerno=customer.customerno)),
    )
