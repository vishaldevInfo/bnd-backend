"""Invoice listing, invoice detail and the facility list for filters."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import Connection

from app import invoice_queries as q
from app.auth import require_user
from app.config import get_settings
from app.database import get_db
from app.schemas import Facility, InvoiceDetail, InvoicePage

MAX_PAGE_SIZE = 100
SortKey = Literal["invoice_date", "invoice_no", "member_name", "facility", "amount"]

router = APIRouter(prefix="/api", tags=["invoices"], dependencies=[Depends(require_user)])


def date_range(
    start: date | None = Query(None, description="First invoice date to include (YYYY-MM-DD)."),
    end: date | None = Query(None, description="Last invoice date to include (YYYY-MM-DD)."),
) -> tuple[date | None, date | None]:
    """Shared by every endpoint that filters by invoice date."""
    if start and end and start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Start date must be on or before end date.")
    return start, end


@router.get("/invoices", response_model=InvoicePage)
def list_invoices(
    dates: tuple[date | None, date | None] = Depends(date_range),
    search: str | None = Query(None, alias="q", max_length=100,
                               description="Matches invoice number, member number or member name."),
    facility: str | None = Query(None, max_length=20, description="Facility code."),
    sort: SortKey = "invoice_date",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: Connection = Depends(get_db),
) -> InvoicePage:
    filters = q.InvoiceFilters(start=dates[0], end=dates[1],
                               search=(search or "").strip() or None,
                               facility=(facility or "").strip() or None)
    total = q.invoice_totals(db, filters)["invoice_count"]
    rows = q.list_invoices(db, filters, sort, order, limit=page_size, offset=(page - 1) * page_size)
    return InvoicePage(items=rows, total=total, page=page, page_size=page_size,
                       currency=get_settings().amount_currency_label)


@router.get("/invoices/{invoice_no}/{header_seq}", response_model=InvoiceDetail)
def get_invoice(
    invoice_no: str = Path(max_length=20),
    header_seq: str = Path(max_length=10),
    db: Connection = Depends(get_db),
) -> InvoiceDetail:
    header = q.get_invoice_header(db, invoice_no, header_seq)
    if header is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found.")
    lines = q.get_invoice_lines(db, invoice_no, header_seq)
    return InvoiceDetail(**header, lines=lines, lines_total=sum((line["amount"] for line in lines), start=0),
                         currency=get_settings().amount_currency_label)


@router.get("/facilities", response_model=list[Facility])
def list_facilities(db: Connection = Depends(get_db)) -> list[Facility]:
    return q.list_facilities(db)
