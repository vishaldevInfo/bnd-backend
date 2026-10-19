"""Normalisation of the email and phone number a customer types, and masking for display."""
import re

from app.config import get_settings

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_CHARS = re.compile(r"\+?[0-9 ()\-.]{7,25}")
E164 = re.compile(r"\+[1-9][0-9]{7,14}")


def normalize_email(raw: str) -> str:
    """Trim and lowercase. Raises ValueError for anything that is not an email address."""
    email = raw.strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def normalize_phone(raw: str) -> str:
    """Return the number in E.164 form ("+" then country code and number).

    A number typed without "+" gets PHONE_DEFAULT_COUNTRY_CODE added when it is a national number.
    """
    text = raw.strip()
    if not PHONE_CHARS.fullmatch(text):
        raise ValueError("Enter a valid phone number.")
    digits = re.sub(r"\D", "", text)
    country = get_settings().phone_default_country_code
    if text.startswith("+"):
        candidate = "+" + digits
    elif digits.startswith(country) and len(digits) == len(country) + 10:
        candidate = "+" + digits
    elif len(digits) == 10:
        candidate = f"+{country}{digits}"
    else:
        raise ValueError("Enter a valid phone number with its country code, e.g. +1 555 123 4567.")
    if not E164.fullmatch(candidate):
        raise ValueError("Enter a valid phone number.")
    return candidate


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"
