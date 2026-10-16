"""Endpoint accuracy against the real chubbstub data (read-only).

Every total is compared with an independent query on the header table, so a
join that duplicated invoices or inflated amounts would fail these tests.
No member names are written here; tests only compare values fetched at runtime.
"""
import csv
import io
from decimal import Decimal

import pytest
from sqlalchemy import text

START, END = "2026-01-01", "2026-03-31"


def header_totals(db, start, end):
    return db.execute(text("""
        SELECT count(*), COALESCE(sum(taxablesalesamt + nontaxablesalesamt), 0),
               count(DISTINCT (salespersondivisionno, salespersonno))
        FROM ar_invoicehistoryheader
        WHERE invoicedate >= :start AND invoicedate < CAST(:end AS date) + 1"""),
        {"start": start, "end": end}).one()


@pytest.fixture
def api(signed_in_client, db):
    return signed_in_client


# ---------- Listing ----------

def test_listing_total_matches_header_count(api, db):
    expected_count, _, _ = header_totals(db, START, END)
    body = api.get("/api/invoices", params={"start": START, "end": END, "page_size": 5}).json()
    assert body["total"] == expected_count
    assert len(body["items"]) == 5
    assert body["currency"] == "USD"


def test_listing_pages_do_not_overlap(api, db):
    params = {"start": START, "end": END, "page_size": 50, "sort": "amount", "order": "desc"}
    first = api.get("/api/invoices", params={**params, "page": 1}).json()["items"]
    second = api.get("/api/invoices", params={**params, "page": 2}).json()["items"]
    keys = {(r["invoice_no"], r["header_seq"]) for r in first + second}
    assert len(keys) == 100
    amounts = [Decimal(r["amount"]) for r in first + second]
    assert amounts == sorted(amounts, reverse=True)


def test_search_by_invoice_number(api, db):
    invoice_no = db.execute(text("SELECT invoiceno FROM ar_invoicehistoryheader LIMIT 1")).scalar_one().strip()
    items = api.get("/api/invoices", params={"q": invoice_no}).json()["items"]
    assert invoice_no in {r["invoice_no"] for r in items}


def test_search_with_no_matches_returns_empty_page(api, db):
    body = api.get("/api/invoices", params={"q": "zz-no-such-member-zz"}).json()
    assert body == {**body, "items": [], "total": 0}


def test_wildcard_characters_in_search_are_literal(api, db):
    assert api.get("/api/invoices", params={"q": "%"}).json()["total"] == 0


def test_facility_filter(api, db):
    code, expected = db.execute(text("""
        SELECT salespersonno, count(*) FROM ar_invoicehistoryheader
        GROUP BY salespersonno ORDER BY count(*) DESC LIMIT 1""")).one()
    body = api.get("/api/invoices", params={"facility": code.strip(), "page_size": 100}).json()
    assert body["total"] == expected
    assert {r["facility_code"] for r in body["items"]} == {code.strip()}


def test_unknown_facility_is_kept_and_labelled(api, db):
    code = db.execute(text("""
        SELECT h.salespersonno FROM ar_invoicehistoryheader h
        LEFT JOIN ar_salesperson s USING (salespersondivisionno, salespersonno)
        WHERE s.salespersonno IS NULL LIMIT 1""")).scalar_one_or_none()
    if code is None:
        pytest.skip("every invoice has a known facility")
    item = api.get("/api/invoices", params={"facility": code.strip(), "page_size": 1}).json()["items"][0]
    assert item["facility_known"] is False
    assert item["facility_name"] == f"Unknown facility ({code.strip()})"


# ---------- Detail ----------

def test_invoice_detail_lines_add_up_to_header_amount(api, db):
    invoice_no, seq, line_count = db.execute(text("""
        SELECT invoiceno, headerseqno, count(*) FROM ar_invoicehistorydetail
        GROUP BY 1, 2 HAVING count(*) > 3 LIMIT 1""")).one()
    body = api.get(f"/api/invoices/{invoice_no.strip()}/{seq.strip()}").json()
    assert len(body["lines"]) == line_count
    assert Decimal(body["lines_total"]) == Decimal(body["amount"])
    assert Decimal(body["amount"]) == Decimal(body["taxable_amount"]) + Decimal(body["non_taxable_amount"])
    assert "quantity" not in str(body.keys()) and "unit_price" not in str(body.keys())


def test_missing_invoice_returns_404(api, db):
    response = api.get("/api/invoices/9999999/000000")
    assert response.status_code == 404
    assert response.json() == {"detail": "Invoice not found."}


# ---------- Dashboard ----------

def test_dashboard_totals_match_header_table(api, db):
    count, total, facilities = header_totals(db, START, END)
    body = api.get("/api/dashboard/summary", params={"start": START, "end": END}).json()
    current = body["current"]
    assert current["invoice_count"] == count
    assert Decimal(current["total_amount"]) == total
    assert current["active_facilities"] == facilities
    assert Decimal(current["average_amount"]) == (total / count).quantize(Decimal("0.01"))


def test_dashboard_chart_totals_follow_the_same_rules(api, db):
    body = api.get("/api/dashboard/summary", params={"start": START, "end": END}).json()
    current = body["current"]
    assert sum(m["invoice_count"] for m in body["monthly"]) == current["invoice_count"]
    assert sum(Decimal(m["total_amount"]) for m in body["monthly"]) == Decimal(current["total_amount"])
    assert [m["month"] for m in body["monthly"]] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    top = [Decimal(f["total_amount"]) for f in body["top_facilities"]]
    assert top == sorted(top, reverse=True) and sum(top) <= Decimal(current["total_amount"])


def test_dashboard_previous_period_is_same_length(api, db):
    body = api.get("/api/dashboard/summary", params={"start": "2026-02-01", "end": "2026-02-28"}).json()
    previous = body["previous"]
    assert (previous["start"], previous["end"]) == ("2026-01-04", "2026-01-31")
    count, total, _ = header_totals(db, "2026-01-04", "2026-01-31")
    assert previous["invoice_count"] == count and Decimal(previous["total_amount"]) == total


def test_dashboard_without_range_has_no_comparison(api, db):
    body = api.get("/api/dashboard/summary").json()
    assert body["previous"] is None
    total = db.execute(text("SELECT count(*) FROM ar_invoicehistoryheader")).scalar_one()
    assert body["current"]["invoice_count"] == total
    assert len(body["recent_invoices"]) == 10


def test_dashboard_for_empty_period(api, db):
    body = api.get("/api/dashboard/summary", params={"start": "1990-01-01", "end": "1990-12-31"}).json()
    current = body["current"]
    assert (current["invoice_count"], Decimal(current["total_amount"])) == (0, 0)
    assert current["average_amount"] is None
    assert body["monthly"] == [] and body["top_facilities"] == [] and body["recent_invoices"] == []


# ---------- Report and CSV export ----------

def test_report_count_and_total_match_header_table(api, db):
    count, total, _ = header_totals(db, START, END)
    body = api.get("/api/reports/invoices", params={"start": START, "end": END}).json()
    assert body["invoice_count"] == count
    assert Decimal(body["total_amount"]) == total


def test_csv_export_matches_the_report(api, db):
    count, total, _ = header_totals(db, "2026-03-01", "2026-03-07")
    response = api.get("/api/reports/invoices/export", params={"start": "2026-03-01", "end": "2026-03-07"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="invoices_2026-03-01_to_2026-03-07.csv"' in response.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(response.text)))
    header, data = rows[0], rows[1:]
    assert header[-1] == "Amount (USD)"
    assert len(data) == count
    assert len({row[0] for row in data}) == count  # one row per invoice, no duplicates
    assert sum(Decimal(row[-1]) for row in data) == total


def test_empty_csv_export_has_only_the_header(api, db):
    response = api.get("/api/reports/invoices/export", params={"start": "1990-01-01", "end": "1990-01-31"})
    rows = list(csv.reader(io.StringIO(response.text)))
    assert len(rows) == 1


@pytest.mark.parametrize("sort", ["invoice_date", "invoice_no", "member_name", "facility", "amount"])
def test_every_sort_returns_a_stable_page(api, db, sort):
    # Covers both query paths (page-then-join, and join-then-sort for facility).
    params = {"start": START, "end": END, "sort": sort, "order": "asc", "page_size": 25}
    first = api.get("/api/invoices", params=params).json()["items"]
    again = api.get("/api/invoices", params=params).json()["items"]
    assert len(first) == 25 and first == again
