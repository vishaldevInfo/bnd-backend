"""Request and response models shared by the API routes."""
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

NAME_PATTERN = re.compile(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*")
CODE_PATTERN = r"^[0-9]{6}$"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class CurrentUser(BaseModel):
    role: Literal["admin", "end_user"]
    email: str | None
    customerno: str | None = Field(default=None, description="Set for end users only.")


# ---------- Customer registration and sign-in ----------

class LookupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=3, max_length=100)
    ssn: str = Field(min_length=9, max_length=20, description="With or without hyphens.")

    @field_validator("first_name", "last_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not NAME_PATTERN.fullmatch(value):
            raise ValueError("use letters, spaces, hyphens or apostrophes only")
        return value

    @field_validator("last_name")
    @classmethod
    def _last_name_prefix(cls, value: str) -> str:
        if len(value) < 3:
            raise ValueError("enter at least the first 3 letters of your last name")
        return value

    @field_validator("ssn")
    @classmethod
    def _ssn(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) != 9:
            raise ValueError("enter a 9-digit Social Security number")
        return digits


class LookupResult(BaseModel):
    status: Literal["matched", "already_registered", "needs_review", "no_match"]
    message: str
    registration_token: str | None = None


class SendCodeRequest(BaseModel):
    registration_token: str = Field(min_length=1, max_length=4096)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(min_length=7, max_length=25, description="Stored for contact; not verified.")


class CodeSent(BaseModel):
    verification_token: str
    email_masked: str
    expires_in_seconds: int
    resend_after_seconds: int


class VerifyRequest(BaseModel):
    verification_token: str = Field(min_length=1, max_length=4096)
    code: str = Field(pattern=CODE_PATTERN)


class ResendRequest(BaseModel):
    verification_token: str = Field(min_length=1, max_length=4096)


class ResendResult(BaseModel):
    message: str
    resend_after_seconds: int


class LoginRequestBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class LoginCodeSent(BaseModel):
    login_token: str
    email_masked: str
    expires_in_seconds: int


class LoginVerifyRequest(BaseModel):
    login_token: str = Field(min_length=1, max_length=4096)
    code: str = Field(pattern=CODE_PATTERN)


class ReviewItem(BaseModel):
    id: str
    submitted_first_name: str
    submitted_last_name: str
    candidate_count: int
    status: Literal["pending", "resolved"]
    created_at: datetime


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
