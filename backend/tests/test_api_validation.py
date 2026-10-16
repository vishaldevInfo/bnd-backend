"""Request validation, protection and error handling. No database needed."""
import pytest
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.invoice_queries import InvoiceFilters, escape_like
from app.main import app
from app.routes.reports import csv_safe

@pytest.fixture
def no_db():
    """Validation must fail before any query runs, so a stub connection is enough."""
    app.dependency_overrides[get_db] = lambda: None
    yield
    app.dependency_overrides.pop(get_db, None)


PROTECTED = [
    "/api/dashboard/summary",
    "/api/invoices",
    "/api/invoices/0000126/000000",
    "/api/facilities",
    "/api/reports/invoices",
    "/api/reports/invoices/export",
]


@pytest.mark.parametrize("path", PROTECTED)
def test_business_endpoints_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/api/invoices", "/api/dashboard/summary",
                                  "/api/reports/invoices", "/api/reports/invoices/export"])
def test_start_after_end_is_rejected(signed_in_client, no_db, path):
    response = signed_in_client.get(path, params={"start": "2026-02-01", "end": "2026-01-01"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Start date must be on or before end date."}


@pytest.mark.parametrize("params", [{"page_size": 101}, {"page_size": 0}, {"page": 0},
                                    {"sort": "drop table"}, {"order": "sideways"}, {"start": "not-a-date"}])
def test_invalid_list_parameters_are_rejected(signed_in_client, no_db, params):
    response = signed_in_client.get("/api/invoices", params=params)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_database_errors_return_503_without_details(signed_in_client):
    def broken_db():
        raise OperationalError("SELECT secret", {}, Exception("password=hunter2"))
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken_db
    try:
        response = signed_in_client.get("/api/facilities")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 503
    assert response.json() == {"detail": "The database is currently unavailable."}
    assert "secret" not in response.text and "hunter2" not in response.text


def test_like_wildcards_are_escaped():
    assert escape_like("50%_off\\") == "50\\%\\_off\\\\"


def test_end_date_includes_the_whole_day():
    where, params = InvoiceFilters(end=__import__("datetime").date(2026, 1, 31)).where_sql()
    assert "h.invoicedate < :end_exclusive" in where
    assert str(params["end_exclusive"]) == "2026-02-01"


@pytest.mark.parametrize("value, expected", [
    ("=HYPERLINK(1)", "'=HYPERLINK(1)"), ("+1", "'+1"), ("-1", "'-1"), ("@x", "'@x"),
    ("Smith, John", "Smith, John"), ("", ""),
])
def test_csv_text_cells_cannot_become_formulas(value, expected):
    assert csv_safe(value) == expected
