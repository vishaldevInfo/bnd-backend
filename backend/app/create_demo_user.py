"""Create or replace the demo login in backend/.env.

Usage (from the backend folder, virtualenv active):
    python -m app.create_demo_user --email demo@example.com

You are prompted for the password (not echoed); only its bcrypt hash is stored.
A random SESSION_SECRET is added if one is not already set.
"""
import argparse
import getpass
import re
import secrets
import sys
from pathlib import Path

from app.auth import BCRYPT_MAX_BYTES, hash_password, normalize_email

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
MIN_PASSWORD_LENGTH = 10
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def set_env_value(text: str, key: str, value: str) -> str:
    """Replace KEY=... if present, otherwise append it."""
    line = f"{key}={value}"
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda _: line, text)
    return text.rstrip("\n") + f"\n{line}\n"


def remove_env_value(text: str, key: str) -> str:
    return re.sub(rf"^{key}=.*\n?", "", text, flags=re.MULTILINE)


def read_password() -> str:
    if not sys.stdin.isatty():  # allows: echo "password" | python -m app.create_demo_user ...
        return sys.stdin.readline().rstrip("\n")
    password = getpass.getpass("Demo password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    email = normalize_email(args.email)
    if not EMAIL_PATTERN.match(email):
        sys.exit("That does not look like an email address.")

    password = read_password()
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password.encode()) > BCRYPT_MAX_BYTES:
        sys.exit(f"Password must be at most {BCRYPT_MAX_BYTES} bytes.")

    text = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    text = remove_env_value(text, "DEMO_USERNAME")  # replaced by DEMO_EMAIL
    text = set_env_value(text, "DEMO_EMAIL", email)
    # Single quotes stop .env parsers from treating the '$' in bcrypt hashes as variables.
    text = set_env_value(text, "DEMO_PASSWORD_HASH", f"'{hash_password(password)}'")
    if not re.search(r"^SESSION_SECRET=.{32,}$", text, re.MULTILINE):
        text = set_env_value(text, "SESSION_SECRET", secrets.token_urlsafe(48))

    ENV_FILE.write_text(text)
    ENV_FILE.chmod(0o600)
    print(f"Demo user {email} saved to {ENV_FILE}. Restart the backend to apply.")


if __name__ == "__main__":
    main()
