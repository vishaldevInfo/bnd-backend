"""Request and response models shared by the API routes."""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class CurrentUser(BaseModel):
    email: str


# ---------- Invoices ----------
# Amounts are Decimal (serialised as strings like "34.82") so no precision is lost
# between PostgreSQL and the browser. The currency label comes from configuration
# because the source data has no currency column.

class InvoiceRow(BaseModel):
    invoice_no: str
    header_seq: str
    invoice_date: date
    member_no: str
    member_name: str
    facility_code: str
    facility_name: str
    facility_known: bool
    amount: Decimal


class InvoicePage(BaseModel):
    items: list[InvoiceRow]
    total: int = Field(description="Number of invoices matching the filters (all pages).")
    page: int
    page_size: int
    currency: str


class InvoiceLine(BaseModel):
    line_no: str
    item_code: str
    description: str | None
    carrier_code: str | None
    amount: Decimal


class InvoiceDetail(InvoiceRow):
    due_date: date | None
    terms_code: str | None
    comment: str | None
    taxable_amount: Decimal
    non_taxable_amount: Decimal
    lines: list[InvoiceLine]
    lines_total: Decimal = Field(description="Sum of line amounts; equals `amount` in verified data.")
    currency: str


class Facility(BaseModel):
    facility_code: str
    facility_name: str
    facility_known: bool


# ---------- Dashboard ----------

class PeriodTotals(BaseModel):
    start: date | None
    end: date | None
    invoice_count: int
    total_amount: Decimal
    average_amount: Decimal | None = Field(description="Null when the period has no invoices.")
    active_facilities: int = Field(description="Distinct facilities with at least one invoice in the period.")


class MonthlyTotal(BaseModel):
    month: date
    invoice_count: int
    total_amount: Decimal


class FacilityTotal(BaseModel):
    facility_code: str
    facility_name: str
    facility_known: bool
    invoice_count: int
    total_amount: Decimal


class DashboardSummary(BaseModel):
    currency: str
    first_invoice_date: date | None
    last_invoice_date: date | None
    current: PeriodTotals
    previous: PeriodTotals | None = Field(
        description="Same-length period immediately before `start`; only when both start and end are given.")
    monthly: list[MonthlyTotal]
    top_facilities: list[FacilityTotal]
    recent_invoices: list[InvoiceRow]


# ---------- Reports ----------

class InvoiceReport(BaseModel):
    start: date | None
    end: date | None
    invoice_count: int
    total_amount: Decimal
    currency: str
    rows: list[InvoiceRow]
    page: int
    page_size: int
