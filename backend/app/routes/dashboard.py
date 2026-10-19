"""Dashboard summary: KPIs, monthly series, top facilities and recent invoices."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Connection

from app import invoice_queries as q
from app.config import get_settings
from app.database import get_db
from app.routes.invoices import date_range
from app.sessions import require_admin
from app.schemas import DashboardSummary, PeriodTotals

TOP_FACILITY_COUNT = 8
RECENT_INVOICE_COUNT = 10

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin)])


def period_totals(db: Connection, start: date | None, end: date | None) -> PeriodTotals:
    totals = q.invoice_totals(db, q.InvoiceFilters(start=start, end=end))
    return PeriodTotals(
        start=start,
        end=end,
        invoice_count=totals["invoice_count"],
        total_amount=totals["total_amount"],
        average_amount=q.average_amount(totals["total_amount"], totals["invoice_count"]),
        active_facilities=totals["facility_count"],
    )


@router.get("/summary", response_model=DashboardSummary)
def summary(
    dates: tuple[date | None, date | None] = Depends(date_range),
    db: Connection = Depends(get_db),
) -> DashboardSummary:
    start, end = dates
    filters = q.InvoiceFilters(start=start, end=end)

    # A comparison only makes sense for a closed range: the previous period is
    # the same number of days ending the day before `start`.
    previous = None
    if start and end:
        previous_end = start - timedelta(days=1)
        previous = period_totals(db, previous_end - (end - start), previous_end)

    bounds = q.invoice_date_bounds(db)
    return DashboardSummary(
        currency=get_settings().amount_currency_label,
        first_invoice_date=bounds["first_invoice_date"],
        last_invoice_date=bounds["last_invoice_date"],
        current=period_totals(db, start, end),
        previous=previous,
        monthly=q.monthly_totals(db, filters),
        top_facilities=q.top_facilities(db, filters, TOP_FACILITY_COUNT),
        recent_invoices=q.list_invoices(db, filters, "invoice_date", "desc", RECENT_INVOICE_COUNT, 0),
    )
