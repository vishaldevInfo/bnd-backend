"""Invoice SQL shared by the invoice, dashboard and report endpoints.

Financial rules (verified during discovery, enforced by tests/test_data_rules.py):
- One invoice = one row of ar_invoicehistoryheader, keyed by (invoiceno, headerseqno).
- Invoice amount = taxablesalesamt + nontaxablesalesamt on the header.
- Counts and totals are computed from the header table only. Detail lines are read
  only for a single invoice, so a header-to-detail join can never inflate a total.
- Facility = ar_salesperson, joined on (salespersondivisionno, salespersonno). That key
  is unique, so the LEFT JOIN cannot duplicate invoices; invoices whose facility code is
  missing from ar_salesperson are kept and labelled "Unknown facility (CODE)".
"""
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Connection, RowMapping, text

AMOUNT = "(h.taxablesalesamt + h.nontaxablesalesamt)"

FACILITY_JOIN = """
    LEFT JOIN ar_salesperson s
           ON s.salespersondivisionno = h.salespersondivisionno
          AND s.salespersonno = h.salespersonno"""

FACILITY_NAME = (
    "COALESCE(NULLIF(TRIM(s.salespersonname), ''), "
    "'Unknown facility (' || TRIM(h.salespersonno) || ')')"
)

INVOICE_COLUMNS = f"""
    TRIM(h.invoiceno)       AS invoice_no,
    TRIM(h.headerseqno)     AS header_seq,
    h.invoicedate::date     AS invoice_date,
    TRIM(h.customerno)      AS member_no,
    TRIM(h.billtoname)      AS member_name,
    TRIM(h.salespersonno)   AS facility_code,
    {FACILITY_NAME}         AS facility_name,
    (s.salespersonno IS NOT NULL) AS facility_known,
    {AMOUNT}                AS amount"""

# Public sort keys mapped to fixed SQL. Only these keys are accepted, so user
# input never reaches the ORDER BY clause.
SORT_COLUMNS = {
    "invoice_date": "h.invoicedate",
    "invoice_no": "h.invoiceno",
    "member_name": "h.billtoname",
    "facility": "facility_name",
    "amount": AMOUNT,
}


def escape_like(value: str) -> str:
    """Make %, _ and \\ match literally inside an ILIKE pattern."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class InvoiceFilters:
    start: date | None = None
    end: date | None = None  # inclusive
    search: str | None = None
    facility: str | None = None

    def where_sql(self) -> tuple[str, dict]:
        """WHERE clause and bind parameters. Uses header columns only."""
        clauses, params = ["TRUE"], {}
        if self.start:
            clauses.append("h.invoicedate >= :start")
            params["start"] = self.start
        if self.end:
            # invoicedate is a timestamp; "< next day" keeps the whole end date.
            clauses.append("h.invoicedate < :end_exclusive")
            params["end_exclusive"] = self.end + timedelta(days=1)
        if self.search:
            clauses.append(
                "(h.invoiceno ILIKE :search OR h.customerno ILIKE :search OR h.billtoname ILIKE :search)"
            )
            params["search"] = f"%{escape_like(self.search)}%"
        if self.facility:
            clauses.append("h.salespersonno = :facility")
            params["facility"] = self.facility
        return " AND ".join(clauses), params


def _invoice_select(filters: InvoiceFilters, sort: str, order: str) -> tuple[str, dict]:
    where, params = filters.where_sql()
    direction = "DESC" if order == "desc" else "ASC"
    sql = f"""
        SELECT {INVOICE_COLUMNS}
        FROM ar_invoicehistoryheader h
        {FACILITY_JOIN}
        WHERE {where}
        ORDER BY {SORT_COLUMNS[sort]} {direction}, h.invoiceno {direction}, h.headerseqno"""
    return sql, params


# Header columns needed by INVOICE_COLUMNS and the sort keys.
_LISTED_HEADER_COLUMNS = """h.invoiceno, h.headerseqno, h.invoicedate, h.customerno, h.billtoname,
    h.salespersondivisionno, h.salespersonno, h.taxablesalesamt, h.nontaxablesalesamt"""


def list_invoices(db: Connection, filters: InvoiceFilters, sort: str, order: str,
                  limit: int, offset: int) -> list[RowMapping]:
    page = {"limit": limit, "offset": offset}
    if sort == "facility":
        # Sorting by facility name needs the join before the sort.
        sql, params = _invoice_select(filters, sort, order)
        return list(db.execute(text(sql + " LIMIT :limit OFFSET :offset"), {**params, **page}).mappings())

    # Pick the page from the header table first, then join facility names onto
    # just those rows. Same result as joining first, but much less work.
    where, params = filters.where_sql()
    direction = "DESC" if order == "desc" else "ASC"
    order_by = f"{SORT_COLUMNS[sort]} {direction}, h.invoiceno {direction}, h.headerseqno"
    sql = f"""
        SELECT {INVOICE_COLUMNS}
        FROM (
            SELECT {_LISTED_HEADER_COLUMNS}
            FROM ar_invoicehistoryheader h
            WHERE {where}
            ORDER BY {order_by}
            LIMIT :limit OFFSET :offset
        ) h
        {FACILITY_JOIN}
        ORDER BY {order_by}"""
    return list(db.execute(text(sql), {**params, **page}).mappings())


def stream_invoices(db: Connection, filters: InvoiceFilters, sort: str, order: str) -> Iterator[RowMapping]:
    """All matching invoices via a server-side cursor, so exports never load everything into memory."""
    sql, params = _invoice_select(filters, sort, order)
    result = db.execution_options(yield_per=2000).execute(text(sql), params)
    yield from result.mappings()


def invoice_totals(db: Connection, filters: InvoiceFilters) -> dict:
    """Invoice count, total amount and number of distinct facilities, from headers only."""
    where, params = filters.where_sql()
    # Grouping by facility first and then summing the groups gives the same numbers
    # as count(*)/sum()/count(DISTINCT ...) but runs ~10x faster on the full history.
    row = db.execute(text(f"""
        SELECT COALESCE(sum(g.invoice_count), 0)::bigint AS invoice_count,
               COALESCE(sum(g.total_amount), 0)          AS total_amount,
               count(*)                                  AS facility_count
        FROM (
            SELECT count(*) AS invoice_count, sum({AMOUNT}) AS total_amount
            FROM ar_invoicehistoryheader h
            WHERE {where}
            GROUP BY h.salespersondivisionno, h.salespersonno
        ) g"""), params).mappings().one()
    return dict(row)


def average_amount(total: Decimal, count: int) -> Decimal | None:
    """Average invoice amount; None when there are no invoices (not zero)."""
    return (total / count).quantize(Decimal("0.01")) if count else None


def monthly_totals(db: Connection, filters: InvoiceFilters) -> list[dict]:
    """Invoice count and amount per calendar month, with empty months filled as zero."""
    where, params = filters.where_sql()
    rows = db.execute(text(f"""
        SELECT date_trunc('month', h.invoicedate)::date AS month,
               count(*)                                 AS invoice_count,
               sum({AMOUNT})                            AS total_amount
        FROM ar_invoicehistoryheader h
        WHERE {where}
        GROUP BY 1
        ORDER BY 1"""), params).mappings().all()
    if not rows:
        return []

    by_month = {row["month"]: row for row in rows}
    series, month, last = [], rows[0]["month"], rows[-1]["month"]
    while month <= last:
        row = by_month.get(month)
        series.append({
            "month": month,
            "invoice_count": row["invoice_count"] if row else 0,
            "total_amount": row["total_amount"] if row else Decimal("0.00"),
        })
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)  # first day of next month
    return series


def top_facilities(db: Connection, filters: InvoiceFilters, limit: int) -> list[RowMapping]:
    """Facilities with the highest invoice amount. Aggregates headers first, then
    joins facility names, so each invoice is counted exactly once."""
    where, params = filters.where_sql()
    return list(db.execute(text(f"""
        SELECT TRIM(t.salespersonno) AS facility_code,
               {FACILITY_NAME.replace("h.salespersonno", "t.salespersonno")} AS facility_name,
               (s.salespersonno IS NOT NULL) AS facility_known,
               t.invoice_count,
               t.total_amount
        FROM (
            SELECT h.salespersondivisionno, h.salespersonno,
                   count(*) AS invoice_count, sum({AMOUNT}) AS total_amount
            FROM ar_invoicehistoryheader h
            WHERE {where}
            GROUP BY 1, 2
            ORDER BY total_amount DESC
            LIMIT :limit
        ) t
        LEFT JOIN ar_salesperson s
               ON s.salespersondivisionno = t.salespersondivisionno
              AND s.salespersonno = t.salespersonno
        ORDER BY t.total_amount DESC"""), {**params, "limit": limit}).mappings())


def invoice_date_bounds(db: Connection) -> RowMapping:
    """Earliest and latest invoice date in the whole data set."""
    return db.execute(text("""
        SELECT min(invoicedate)::date AS first_invoice_date,
               max(invoicedate)::date AS last_invoice_date
        FROM ar_invoicehistoryheader""")).mappings().one()


def get_invoice_header(db: Connection, invoice_no: str, header_seq: str) -> RowMapping | None:
    return db.execute(text(f"""
        SELECT {INVOICE_COLUMNS},
               h.invoiceduedate::date               AS due_date,
               NULLIF(TRIM(h.termscode), '')        AS terms_code,
               NULLIF(TRIM(h.comment), '')          AS comment,
               h.taxablesalesamt                    AS taxable_amount,
               h.nontaxablesalesamt                 AS non_taxable_amount
        FROM ar_invoicehistoryheader h
        {FACILITY_JOIN}
        WHERE h.invoiceno = :invoice_no AND h.headerseqno = :header_seq"""),
        {"invoice_no": invoice_no, "header_seq": header_seq}).mappings().one_or_none()


def get_invoice_lines(db: Connection, invoice_no: str, header_seq: str) -> list[RowMapping]:
    # Quantity and unit price are 0 on almost every line in this data, so only
    # extensionamt (the line amount) is returned.
    return list(db.execute(text("""
        SELECT TRIM(d.detailseqno)                      AS line_no,
               TRIM(d.itemcode)                         AS item_code,
               NULLIF(TRIM(d.itemcodedesc), '')         AS description,
               NULLIF(TRIM(d.udf_carrier_code), '')     AS carrier_code,
               d.extensionamt                           AS amount
        FROM ar_invoicehistorydetail d
        WHERE d.invoiceno = :invoice_no AND d.headerseqno = :header_seq
        ORDER BY d.detailseqno"""), {"invoice_no": invoice_no, "header_seq": header_seq}).mappings())


def list_facilities(db: Connection) -> list[RowMapping]:
    """Facilities that appear on at least one invoice, including codes missing
    from ar_salesperson, for the facility filter."""
    return list(db.execute(text(f"""
        SELECT TRIM(f.salespersonno) AS facility_code,
               {FACILITY_NAME.replace("h.salespersonno", "f.salespersonno")} AS facility_name,
               (s.salespersonno IS NOT NULL) AS facility_known
        FROM (SELECT DISTINCT salespersondivisionno, salespersonno FROM ar_invoicehistoryheader) f
        LEFT JOIN ar_salesperson s
               ON s.salespersondivisionno = f.salespersondivisionno
              AND s.salespersonno = f.salespersonno
        ORDER BY 2""")).mappings())
