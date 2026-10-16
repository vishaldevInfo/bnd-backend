"""Invoice report (one row per invoice) and its streamed CSV export.

Both endpoints use the same filters and the same query, so the CSV always
contains exactly the invoices counted in the on-screen report.
"""
import csv
import io
from collections.abc import Iterator
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Connection

from app import invoice_queries as q
from app.auth import require_user
from app.config import get_settings
from app.database import engine, get_db
from app.routes.invoices import MAX_PAGE_SIZE, date_range
from app.schemas import InvoiceReport

REPORT_SORT = ("invoice_date", "asc")
CSV_ROWS_PER_CHUNK = 1000

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_user)])


@router.get("/invoices", response_model=InvoiceReport)
def invoice_report(
    dates: tuple[date | None, date | None] = Depends(date_range),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    db: Connection = Depends(get_db),
) -> InvoiceReport:
    start, end = dates
    filters = q.InvoiceFilters(start=start, end=end)
    totals = q.invoice_totals(db, filters)
    rows = q.list_invoices(db, filters, *REPORT_SORT, limit=page_size, offset=(page - 1) * page_size)
    return InvoiceReport(start=start, end=end, invoice_count=totals["invoice_count"],
                         total_amount=totals["total_amount"], currency=get_settings().amount_currency_label,
                         rows=rows, page=page, page_size=page_size)


def csv_safe(value: str) -> str:
    """Stop spreadsheet apps from running text cells as formulas (CSV injection)."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def csv_lines(filters: q.InvoiceFilters, currency: str) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)  # handles quoting of commas, quotes and newlines

    def flush() -> str:
        chunk = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return chunk

    writer.writerow(["Invoice No", "Invoice Date", "Member No", "Member Name",
                     "Facility Code", "Facility", f"Amount ({currency})"])
    # The response streams after the endpoint returns, so the generator owns its connection.
    with engine.connect() as db:
        for count, row in enumerate(q.stream_invoices(db, filters, *REPORT_SORT), start=1):
            writer.writerow([
                csv_safe(row["invoice_no"]),
                row["invoice_date"].isoformat(),
                csv_safe(row["member_no"]),
                csv_safe(row["member_name"]),
                csv_safe(row["facility_code"]),
                csv_safe(row["facility_name"]),
                f"{row['amount']:.2f}",  # numbers stay numeric, e.g. -12.50
            ])
            if count % CSV_ROWS_PER_CHUNK == 0:
                yield flush()
    yield flush()


@router.get("/invoices/export", response_class=StreamingResponse,
            responses={200: {"content": {"text/csv": {}}, "description": "CSV file, one row per invoice."}})
def export_invoice_report(dates: tuple[date | None, date | None] = Depends(date_range)) -> StreamingResponse:
    start, end = dates
    filename = f"invoices_{start or 'all'}_to_{end or 'all'}.csv"
    return StreamingResponse(
        csv_lines(q.InvoiceFilters(start=start, end=end), get_settings().amount_currency_label),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
