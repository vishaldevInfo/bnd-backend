"""Business rules verified during discovery. If a future data sync breaks one
of these, the invoice queries built on top of them must be revisited."""
from sqlalchemy import text


def scalar(db, sql: str):
    return db.execute(text(sql)).scalar_one()


def test_invoice_header_key_is_unique(db):
    duplicates = scalar(db, """
        SELECT count(*) FROM (
            SELECT 1 FROM ar_invoicehistoryheader
            GROUP BY invoiceno, headerseqno HAVING count(*) > 1
        ) d""")
    assert duplicates == 0


def test_invoice_detail_key_is_unique(db):
    duplicates = scalar(db, """
        SELECT count(*) FROM (
            SELECT 1 FROM ar_invoicehistorydetail
            GROUP BY invoiceno, headerseqno, detailseqno HAVING count(*) > 1
        ) d""")
    assert duplicates == 0


def test_every_detail_line_belongs_to_a_header(db):
    orphans = scalar(db, """
        SELECT count(*) FROM ar_invoicehistorydetail d
        WHERE NOT EXISTS (
            SELECT 1 FROM ar_invoicehistoryheader h
            WHERE h.invoiceno = d.invoiceno AND h.headerseqno = d.headerseqno
        )""")
    assert orphans == 0


def test_header_amount_equals_sum_of_detail_lines(db):
    # Invoice amount = taxablesalesamt + nontaxablesalesamt (the authoritative header total).
    mismatches = scalar(db, """
        SELECT count(*)
        FROM ar_invoicehistoryheader h
        JOIN (
            SELECT invoiceno, headerseqno, sum(extensionamt) AS line_total
            FROM ar_invoicehistorydetail GROUP BY invoiceno, headerseqno
        ) d USING (invoiceno, headerseqno)
        WHERE h.taxablesalesamt + h.nontaxablesalesamt <> d.line_total""")
    assert mismatches == 0


def test_salesperson_key_is_unique(db):
    duplicates = scalar(db, """
        SELECT count(*) FROM (
            SELECT 1 FROM ar_salesperson
            GROUP BY salespersondivisionno, salespersonno HAVING count(*) > 1
        ) d""")
    assert duplicates == 0


def test_header_to_detail_join_would_inflate_totals(db):
    # Documents why totals must come from the header table alone: joining details
    # repeats each header once per line.
    header_total = scalar(db, "SELECT sum(taxablesalesamt + nontaxablesalesamt) FROM ar_invoicehistoryheader")
    joined_total = scalar(db, """
        SELECT sum(h.taxablesalesamt + h.nontaxablesalesamt)
        FROM ar_invoicehistoryheader h
        JOIN ar_invoicehistorydetail d USING (invoiceno, headerseqno)""")
    assert joined_total > header_total
