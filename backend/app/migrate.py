"""Applies the app-owned SQL migrations in backend/migrations, in filename order.

Run with the writer role's settings (APP_DB_USER / APP_DB_PASSWORD):

    cd backend && python -m app.migrate

Each file runs in one transaction and is recorded in app.schema_migrations, so
rerunning is safe. Migrations may only touch the "app" schema.
"""
import sys
from pathlib import Path

from sqlalchemy import text

from app.app_database import get_engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def pending_files(applied: set[str]) -> list[Path]:
    return [path for path in sorted(MIGRATIONS_DIR.glob("*.sql")) if path.name not in applied]


def main() -> int:
    engine = get_engine()
    if engine is None:
        print("APP_DB_USER and APP_DB_PASSWORD must be set to run migrations.", file=sys.stderr)
        return 1
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app.schema_migrations (
                name       text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now())"""))
        conn.commit()
        applied = {row[0] for row in conn.execute(text("SELECT name FROM app.schema_migrations"))}
        for path in pending_files(applied):
            conn.execute(text(path.read_text(encoding="utf-8")))
            conn.execute(text("INSERT INTO app.schema_migrations (name) VALUES (:name)"), {"name": path.name})
            conn.commit()
            print(f"applied {path.name}")
    print("up to date" if not pending_files(applied) else "done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
