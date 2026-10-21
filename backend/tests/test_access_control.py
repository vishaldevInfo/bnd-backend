"""Who may see what: admin sees everything, an end user only their own customer's invoices.

Needs the Sage database (for real invoice numbers) and the writable app schema
(TEST_APP_DB_RESET=1, see conftest.py).
"""
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.sessions import SESSION_COOKIE, issue_end_user_session


def two_customers(db):
    rows = db.execute(text("""
        SELECT DISTINCT ON (TRIM(customerno)) TRIM(customerno) AS customerno,
               TRIM(invoiceno) AS invoice_no, TRIM(headerseqno) AS seq
        FROM ar_invoicehistoryheader ORDER BY TRIM(customerno), invoiceno LIMIT 2""")).mappings().all()
    if len(rows) < 2:
        pytest.skip("need invoices for two customers")
    return rows[0], rows[1]


def end_user_client(client, app_db, customerno: str, suffix: str):
    user_id = app_db.execute(text("""
        INSERT INTO app.users (customerno, first_name, last_name, ssn_last4_hash, email, phone, email_verified_at)
        VALUES (:customerno, 'Test', 'User', 'hash', :email, :phone, now())
        RETURNING id"""), {"customerno": customerno, "email": f"{suffix}@example.com",
                           "phone": f"+1555{abs(hash(suffix)) % 10_000_000:07d}"}).scalar_one()
    app_db.commit()
    client.cookies.set(SESSION_COOKIE, issue_end_user_session(str(user_id)))
    return client


def test_end_user_cannot_open_another_customers_invoice(client, db, app_db):
    mine, theirs = two_customers(db)
    end_user_client(client, app_db, mine["customerno"], "owner")

    own = client.get(f"/api/invoices/{mine['invoice_no']}/{mine['seq']}")
    assert own.status_code == 200
    assert own.json()["member_no"] == mine["customerno"]

    other = client.get(f"/api/invoices/{theirs['invoice_no']}/{theirs['seq']}")
    assert other.status_code == 404  # same answer as an invoice that does not exist


def test_end_user_list_and_totals_contain_only_their_customer(client, db, app_db):
    mine, _ = two_customers(db)
    end_user_client(client, app_db, mine["customerno"], "lister")
    expected = db.execute(text("""
        SELECT count(*) FROM ar_invoicehistoryheader WHERE TRIM(customerno) = :c"""),
        {"c": mine["customerno"]}).scalar()

    body = client.get("/api/invoices", params={"page_size": 100}).json()
    assert body["total"] == expected
    assert {item["member_no"] for item in body["items"]} == {mine["customerno"]}


def test_end_user_cannot_widen_the_scope_with_query_parameters(client, db, app_db):
    mine, theirs = two_customers(db)
    end_user_client(client, app_db, mine["customerno"], "tricks")
    body = client.get("/api/invoices", params={"q": theirs["customerno"], "page_size": 100}).json()
    assert all(item["member_no"] == mine["customerno"] for item in body["items"])
    assert client.get("/api/invoices", params={"customerno": theirs["customerno"]}).json()["total"] == \
        client.get("/api/invoices").json()["total"]


def test_end_user_is_refused_admin_pages_and_apis(client, db, app_db):
    mine, _ = two_customers(db)
    end_user_client(client, app_db, mine["customerno"], "admin-probe")
    for path in ["/api/dashboard/summary", "/api/reports/invoices", "/api/reports/invoices/export",
                 "/api/facilities", "/api/admin/review-queue"]:
        assert client.get(path).status_code == 403, path


def test_admin_still_sees_every_customer(signed_in_client, db):
    total = db.execute(text("SELECT count(*) FROM ar_invoicehistoryheader")).scalar()
    assert signed_in_client.get("/api/invoices", params={"page_size": 1}).json()["total"] == total
    assert signed_in_client.get("/api/dashboard/summary").status_code == 200


def test_anonymous_requests_are_refused(client):
    for path in ["/api/invoices", "/api/dashboard/summary", "/api/admin/review-queue"]:
        assert client.get(path).status_code == 401, path


def test_disabled_end_user_loses_access_immediately(client, db, app_db):
    mine, _ = two_customers(db)
    end_user_client(client, app_db, mine["customerno"], "disabled")
    assert client.get("/api/invoices").status_code == 200
    app_db.execute(text("UPDATE app.users SET status = 'disabled'"))
    app_db.commit()
    assert client.get("/api/invoices").status_code == 401


def test_session_token_for_a_deleted_user_is_refused(client, db, app_db):
    mine, _ = two_customers(db)
    client.cookies.set(SESSION_COOKIE, issue_end_user_session("00000000-0000-4000-8000-000000000000"))
    assert client.get("/api/invoices").status_code == 401


def test_customer_dashboard_totals_cover_only_their_own_invoices(client, db, app_db):
    mine, _ = two_customers(db)
    end_user_client(client, app_db, mine["customerno"], "dash")
    expected = db.execute(text("""
        SELECT count(*), coalesce(sum(taxablesalesamt + nontaxablesalesamt), 0)
        FROM ar_invoicehistoryheader WHERE TRIM(customerno) = :c"""), {"c": mine["customerno"]}).one()

    body = client.get("/api/portal/summary").json()
    assert body["current"]["invoice_count"] == expected[0]
    assert float(body["current"]["total_amount"]) == pytest.approx(float(expected[1]), abs=0.01)
    assert sum(m["invoice_count"] for m in body["monthly"]) == expected[0]


def test_customer_dashboard_is_refused_to_admins_and_anonymous(client, signed_in_client):
    assert signed_in_client.get("/api/portal/summary").status_code == 403
    client.cookies.clear()
    assert client.get("/api/portal/summary").status_code == 401
