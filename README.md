<<<<<<< HEAD
# bnd-frontend
=======
# BND Invoice Reporting

Read-only invoice reporting over the Sage 100 extract stored in the existing
PostgreSQL database `chubbstub`. No Docker: everything runs directly on your machine.

| Part     | Stack                                          | Local URL                  |
|----------|------------------------------------------------|----------------------------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, Recharts | http://localhost:3010      |
| Backend  | FastAPI, SQLAlchemy Core, psycopg 3, Pydantic  | http://localhost:8010/docs |
| Database | Existing PostgreSQL 16 database `chubbstub`    | localhost:5432             |

The browser only talks to Next.js. Next.js forwards every `/api/*` request to
FastAPI (`frontend/next.config.ts`), so the session cookie stays same-origin and
CORS is not needed.

The app **only reads** the three existing tables `ar_salesperson`,
`ar_invoicehistoryheader` and `ar_invoicehistorydetail`. It never creates, changes
or deletes database objects or data.

## Quick start

Prerequisites: Python 3.12+, Node.js 20+ (24 for the frontend tests), npm, and
PostgreSQL running with the existing `chubbstub` database
(Linux: `sudo systemctl start postgresql` · macOS/Homebrew: `brew services start postgresql@16` ·
Windows: start the "postgresql" service in Services).

1. **Backend environment**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   cp .env.example .env               # Windows: copy .env.example .env
   ```
   Edit `backend/.env`: keep `DB_USER=bnd_readonly` and set `DB_PASSWORD` to a new
   random value, for example the output of
   `python -c "import secrets; print(secrets.token_urlsafe(24))"`.

2. **Read-only database role** (once, as the PostgreSQL administrator, see
   [Database permissions](#database-permissions)).

3. **Demo login**
   ```bash
   python -m app.create_demo_user --email demo@example.com   # prompts for a password
   ```

4. **Start the backend** (keep this terminal open)
   ```bash
   uvicorn app.main:app --reload --port 8010
   ```
   Check http://localhost:8010/api/health → `{"status":"ok","database":"ok"}`.

5. **Start the frontend** (second terminal)
   ```bash
   cd frontend
   npm install
   cp .env.example .env.local         # Windows: copy .env.example .env.local
   npm run dev
   ```
   Open http://localhost:3010 and sign in with the demo email and password.

## Environment configuration

### `backend/.env` (never committed)

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_NAME` | no | `localhost` / `5432` / `chubbstub` | Database location |
| `DB_USER` | yes | | Use `bnd_readonly` |
| `DB_PASSWORD` | yes | | Password of `DB_USER` |
| `AMOUNT_CURRENCY_LABEL` | no | `USD` | Currency shown with amounts (the data has no currency column) |
| `DEMO_EMAIL` | yes | | Demo login email (written by `create_demo_user`) |
| `DEMO_PASSWORD_HASH` | yes | | bcrypt hash, single-quoted (written by `create_demo_user`) |
| `SESSION_SECRET` | yes | | 32+ random characters that sign session cookies (written by `create_demo_user`) |
| `SESSION_MAX_AGE_HOURS` | no | `8` | Session lifetime |
| `COOKIE_SECURE` | no | `false` | Set `true` when the app is served over HTTPS |
| `ALLOWED_ORIGINS` | no | `http://localhost:3010` | Comma-separated browser origins allowed to sign in (CSRF check) |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_MINUTES` | no | `5` / `15` | Failed sign-ins per email before a temporary block |

The backend refuses to start if a required value is missing and names the missing
setting without printing any values.

### `frontend/.env.local` (never committed)

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8010` | Where Next.js forwards `/api/*` (server-side only) |

## Database permissions

The application connects as `bnd_readonly`, never as `postgres`. The role is created by
[`backend/create_readonly_role.sql`](backend/create_readonly_role.sql), which only adds:

- `LOGIN`, at most 20 connections, and `default_transaction_read_only = on`
- `CONNECT` on database `chubbstub` and `USAGE` on schema `public`
- `SELECT` on the three `ar_*` tables

Run it once, passing the password from `backend/.env` so it is never typed or shown
(psql asks for the administrator password):

```bash
cd backend
PW=$(grep '^DB_PASSWORD=' .env | cut -d= -f2-)
psql -h localhost -U postgres -d chubbstub -v ro_password="$PW" -f create_readonly_role.sql
```

Windows PowerShell:

```powershell
cd backend
$PW = (Select-String -Path .env -Pattern '^DB_PASSWORD=').Line.Split('=', 2)[1]
psql -h localhost -U postgres -d chubbstub -v ro_password="$PW" -f create_readonly_role.sql
```

If the role already exists and only the password changed:
`psql -h localhost -U postgres -d chubbstub -c "ALTER ROLE bnd_readonly PASSWORD '$PW'"`.

Each app session is also opened read-only, so even a misconfigured privileged account
could not write through the app. `backend/tests/test_foundation.py` fails if the app
connects as a superuser or if a write is not rejected.

## Running the tests

| Command (folder) | What it checks | Needs |
|---|---|---|
| `pytest` (`backend/`) | Data rules, API accuracy against the live data, auth, validation, CSV | Database role; DB tests skip with a reason if unreachable |
| `npm test` (`frontend/`) | Amount/date/percent formatting | Node 24 |
| `npm run test:smoke` (`frontend/`) | Real browser journey: login, invoices, detail, dashboard, report, sign out | Both servers running, Chrome, `SMOKE_EMAIL` + `SMOKE_PASSWORD` |
| `npx tsc --noEmit`, `npm run lint`, `npm run build` (`frontend/`) | Types, lint, production build | |

```bash
SMOKE_EMAIL=demo@example.com SMOKE_PASSWORD='your-demo-password' npm run test:smoke
```

The backend accuracy tests compare every API total with an independent query on the
header table, so a join that duplicated invoices or inflated amounts would fail.
All tests are read-only.

## API

All endpoints except health and login require the session cookie. Interactive docs:
http://localhost:8010/docs. Errors always have the shape `{"detail": "message"}`.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | App and database status |
| `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` | Session |
| `GET /api/dashboard/summary?start&end` | KPIs, previous-period comparison, monthly series, top 8 facilities, 10 recent invoices |
| `GET /api/invoices?q&start&end&facility&sort&order&page&page_size` | Invoice list (`page_size` ≤ 100; `sort`: `invoice_date`, `invoice_no`, `member_name`, `facility`, `amount`) |
| `GET /api/invoices/{invoice_no}/{header_seq}` | Invoice header, facility and line items |
| `GET /api/facilities` | Facilities for the filter |
| `GET /api/reports/invoices?start&end&page&page_size` | One row per invoice, with count and total |
| `GET /api/reports/invoices/export?start&end` | Streamed CSV of the same report |

## Project structure

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app, routers, error handlers |
| `backend/app/config.py` | Settings from `.env`, validated at startup |
| `backend/app/database.py` | Read-only connection pool |
| `backend/app/auth.py` | Password check, rate limit, session cookie, auth routes |
| `backend/app/invoice_queries.py` | **All invoice SQL and the financial rules** |
| `backend/app/routes/` | Dashboard, invoices and report endpoints |
| `backend/app/schemas.py` | Request/response models |
| `backend/app/create_demo_user.py` | Writes the demo login to `.env` |
| `frontend/src/app/login/` | Sign-in page |
| `frontend/src/app/(app)/` | Signed-in pages; each `page.tsx` wraps a client `*-view.tsx` |
| `frontend/src/components/app-shell.tsx` | Sidebar (collapsible, mobile drawer), top-bar search, sign out |
| `frontend/src/components/ui.tsx` | Cards, skeletons, empty/error states, date filter, pagination |
| `frontend/src/components/invoice-table.tsx` | Invoice table used by dashboard, invoices and report |
| `frontend/src/components/charts.tsx` | Monthly amount and top facilities charts |
| `frontend/src/lib/` | API helpers and types, formatting, URL filter state |
| `frontend/src/proxy.ts` | Sends visitors without a session to `/login` |

Filters live in the URL (`/invoices?q=…&start=…`), so a filtered view survives a
reload and can be bookmarked. The sidebar's collapsed state is remembered per browser.

## Verified data rules

Discovered from the data (the tables have no keys or constraints) and enforced by
`backend/tests/test_data_rules.py`:

- An invoice is identified by `(invoiceno, headerseqno)`; a line by `(invoiceno, headerseqno, detailseqno)`.
- **Invoice amount = `taxablesalesamt + nontaxablesalesamt`.** It equals the sum of the
  lines' `extensionamt` for every invoice. Tax, freight and discount are 0 in this data.
- Counts and totals are computed from the header table only; joining detail lines would
  repeat each invoice once per line.
- Line `quantity*` and `unitprice` are 0 on almost every line, so only the line amount is shown.
- `ar_salesperson` holds facilities, joined on `(salespersondivisionno, salespersonno)`.
  152 invoices use 4 codes missing from that table; they are kept and shown as
  "Unknown facility (CODE)".
- "Active facilities" = facilities with at least one invoice in the period.
- The dashboard comparison uses the same number of days immediately before the chosen start date.
- Negative invoices (credits/adjustments) are included in all totals and shown in red.

## Known limitations

- **No indexes** on the source tables (not added without approval). Most requests take
  0.3–1.5 s; the all-time dashboard takes about 1.5–3 s. An index on
  `ar_invoicehistoryheader (invoicedate)` and `ar_invoicehistorydetail (invoiceno, headerseqno)`
  would help if approved.
- Login rate limiting is in memory: it resets when the backend restarts and assumes a single backend process.
- Signing out deletes the browser cookie; a copied cookie stays valid until it expires (8 hours by default).
- One demo account only; no roles or user management (out of MVP scope).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Backend exits with `Field required` for `db_user` / `db_password` | Create `backend/.env` from `.env.example`. |
| Backend exits with `Field required` for `demo_email` / `demo_password_hash` / `session_secret` | Run `python -m app.create_demo_user --email …`. |
| `/api/health` shows `"database": "unavailable"` | PostgreSQL is stopped, or the role/password is wrong. The PostgreSQL log (`/var/log/postgresql/` on Linux) says which, e.g. `Role "bnd_readonly" does not exist`. |
| Backend tests are skipped | Same as above: the database is not reachable with the `.env` credentials. |
| Login says "Invalid email or password." | Wrong credentials. Forgot the password? Run `create_demo_user` again and restart the backend. |
| Login says "Too many failed sign-in attempts" | Wait 15 minutes or restart the backend. |
| Login says "Request origin not allowed." | Add the frontend URL you use to `ALLOWED_ORIGINS` in `backend/.env`. |
| `address already in use` on 8010 or 3010 | Another process uses the port. Stop it, or start uvicorn with another `--port` and set `BACKEND_URL` in `frontend/.env.local` to match. |
| Frontend shows "Cannot reach the server" | The backend is not running, or `BACKEND_URL` points to the wrong port. |
| Backend stops responding after code edits | The `--reload` worker crashed. Press Ctrl+C and start uvicorn again. |
>>>>>>> ffb3495 (setup project)
