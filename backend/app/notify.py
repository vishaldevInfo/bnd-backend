"""Sends one-time codes by email.

EMAIL_PROVIDER=console writes the code to the server log instead of sending it.
That is for development only, and config refuses it when COOKIE_SECURE=true.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings
from app.contact import mask_email

logger = logging.getLogger("bnd.notify")
TIMEOUT_SECONDS = 10


class DeliveryError(Exception):
    """The email could not be sent."""


def send_code(to: str, code: str, minutes: int) -> None:
    settings = get_settings()
    if settings.email_provider == "console":
        logger.warning("DEV email code for %s: %s", mask_email(to), code)
        return

    if not settings.smtp_host:
        raise DeliveryError("SMTP_HOST is not set.")
    message = EmailMessage()
    message["From"], message["To"] = settings.email_from, to
    message["Subject"] = "Your BND verification code"
    message.set_content(
        f"Your verification code is {code}. It expires in {minutes} minutes.\n"
        "If you did not ask for this code, you can ignore this email."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise DeliveryError("SMTP delivery failed.") from exc
