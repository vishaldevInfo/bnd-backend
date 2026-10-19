"""Step 1 of registration: find the Sage customer number that matches a name and SSN.

Matching rule (client requirement), as implemented here:
- The Sage customer number has the form <first 3 letters of last name><4 digits>,
  for example KUM4798 for Kumah. The lookup key is therefore last-name prefix + SSN last 4,
  and it must equal the customer number (case-insensitive).
- The first name breaks ties when more than one customer number matches. It is read from
  billtoname, which is written "Last, First" (or "LAST FIRST").

ASSUMPTION TO CONFIRM WITH THE CLIENT: the four digits in the customer number are the last
4 digits of the SSN. If they are not, this lookup is wrong and must not be used.

The source is only read, through the read-only Sage connection.
"""
import re

from sqlalchemy import Connection, text
from sqlalchemy.exc import ProgrammingError

from app.config import get_settings
from app.errors import ServiceUnavailable

IDENTIFIER = re.compile(r"(?:[a-z_][a-z0-9_]{0,62}\.)?[a-z_][a-z0-9_]{0,62}")  # table or schema.table
MAX_CANDIDATE_ROWS = 50


class IdentitySourceError(ServiceUnavailable):
    """The configured identity table or columns do not exist in the database."""

    def __init__(self) -> None:
        super().__init__("Account lookup is not configured on this server. Please contact support.")


def last_name_prefix(last_name: str) -> str:
    return last_name.strip().lower()[:3]


def normalize_ssn_last4(ssn: str) -> str:
    digits = re.sub(r"\D", "", ssn)
    if len(digits) != 9:
        raise ValueError("Enter a 9-digit Social Security number.")
    return digits[-4:]


def customerno_key(last3: str, ssn_last4: str) -> str:
    """The customer number this name and SSN would have, e.g. KUM + 4798 = KUM4798."""
    return f"{last3.upper()}{ssn_last4}"


def first_name_from_bill_to(bill_to: str | None) -> str | None:
    """First name from billtoname: "Kumah, Joana" -> "joana"; "HATCHER SAMANTHA" -> "samantha".
    None when the format is unclear (for example "FRYE/CHERI/"), so it cannot break a tie."""
    if not bill_to:
        return None
    if "," in bill_to:
        _, _, rest = bill_to.partition(",")
        words = rest.split()
    else:
        words = bill_to.split()[1:]
    if not words or not re.fullmatch(r"[^\W\d_][^\W\d_'\-]*", words[0]):
        return None
    return words[0].lower()


def _table_and_columns() -> tuple[str, str, str]:
    s = get_settings()
    table, customerno, name = s.identity_source_table, s.identity_customerno_column, s.identity_name_column
    for identifier in (table, customerno, name):
        # Names are placed into SQL, so only plain identifiers are accepted.
        if not IDENTIFIER.fullmatch(identifier):
            raise ValueError(f"Invalid identity table or column name in configuration: {identifier!r}")
    return table, customerno, name


def find_identity_candidates(conn: Connection, last3: str, ssn_last4: str, first_name: str) -> list[str]:
    """Distinct customer numbers matching the lookup.

    - 0 results: no match
    - 1 result: match
    - 2+ results: the first name narrows them. Whatever remains is returned, and the caller
      treats more than one as "needs review" (never auto-linked).
    """
    table, customerno, name = _table_and_columns()
    sql = f"""
        SELECT DISTINCT TRIM(src.{customerno}) AS customerno, src.{name} AS bill_to
        FROM {table} src
        WHERE UPPER(TRIM(src.{customerno})) = :key
        LIMIT {MAX_CANDIDATE_ROWS}"""
    try:
        rows = conn.execute(text(sql), {"key": customerno_key(last3, ssn_last4)}).mappings().all()
    except ProgrammingError as exc:
        raise IdentitySourceError() from exc

    by_customer: dict[str, set[str | None]] = {}
    for row in rows:
        by_customer.setdefault(row["customerno"], set()).add(first_name_from_bill_to(row["bill_to"]))
    if len(by_customer) <= 1:
        return sorted(by_customer)
    wanted = first_name.strip().lower()
    return sorted(c for c, firsts in by_customer.items() if wanted in firsts)
