# bnd-frontend

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

### Prerequisites

- Python 3.12+
- Node.js 20+ (Node.js 24 is required for frontend tests)
- npm
- GNU Make
- PostgreSQL running with the existing `chubbstub` database

Start PostgreSQL if needed:

- Linux: `sudo systemctl start postgresql`
- macOS/Homebrew: `brew services start postgresql@16`
- Windows: start the PostgreSQL service from Services

### 1. Install backend and frontend dependencies

From the repository root (`bnd-platform/`), run:

```bash
make install-all
```

This creates the root `venv/` virtual environment, installs Python dependencies from
`backend/requirements.txt`, and installs frontend dependencies with `npm install`.

You do not need to activate the virtual environment manually; the Makefile calls the
Python executable inside `venv/` directly.

### 2. Configure the backend environment

Create the backend environment file:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`. Keep `DB_USER=bnd_readonly` and set `DB_PASSWORD` to a new random
value. You can generate one with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Configure the remaining required values as described in
[Environment configuration](#environment-configuration). Do not commit `.env` files.

### 3. Create the read-only database role

Run the database-role setup once as the PostgreSQL administrator. See
[Database permissions](#database-permissions) for the commands. The app should connect
as `bnd_readonly`, not as `postgres`.

### 4. Configure the frontend environment

Create the frontend environment file:

```bash
cp frontend/.env.example frontend/.env.local
```

The default `BACKEND_URL` should be `http://localhost:8010`. See
[Environment configuration](#environment-configuration).

### 5. Create the admin login

From the repository root, run:

```bash
cd backend
../venv/bin/python -m app.create_demo_user --email demo@example.com
cd ..
```

The command prompts you to choose a password and writes the admin login settings to
`backend/.env`. Use the email and password you chose on the admin sign-in page.

### 6. Start the backend and frontend

Open two terminals at the repository root.

**Terminal 1 — FastAPI backend:**

```bash
make dev
```

The backend runs at `http://localhost:8010`. Check
`http://localhost:8010/api/health`; a healthy response is
`{"status":"ok","database":"ok"}`.

**Terminal 2 — Next.js frontend:**

```bash
make frontend-dev
```

- Admins sign in at `http://localhost:3010/admin` with the email and password from step 5.
- Customers sign in at `http://localhost:3010/login`. New customers register there (see
  [Customer accounts](#customer-accounts)).

### Makefile commands

| Command | Purpose |
|---|---|
| `make setup` | Create the Python virtual environment and install backend dependencies |
| `make frontend-install` | Install frontend dependencies |
| `make install-all` | Set up the backend and frontend dependencies |
| `make dev` | Start the FastAPI development server on port `8010` |
| `make frontend-dev` | Start the Next.js development server |
| `make clean` | Remove the root `venv/` and `frontend/node_modules/` |

Run `make install-all` again after pulling changes that update Python or npm dependencies.
Use `make dev` and `make frontend-dev` in separate terminals whenever you work on the app.

## Environment configuration

### `backend/.env` (never committed)

| Variable | Required | Default | Meaning |

|---|---|---|---|

| `DB_HOST` / `DB_PORT` / `DB_NAME` | no | `localhost` / `5432` / `chubbstub` | Database location |

| `DB_USER` | yes | | Use `bnd_readonly` |

| `DB_PASSWORD` | yes | | Password of `DB_USER` |

| `AMOUNT_CURRENCY_LABEL` | no | `USD` | Currency shown with amounts (the data has no currency column) |

| `DEMO_EMAIL` | yes | | Admin login email (written by `create_demo_user`) |

| `DEMO_PASSWORD_HASH` | yes | | Admin password as a bcrypt hash, single-quoted (written by `create_demo_user`) |

| `SESSION_SECRET` | yes | | 32+ random characters that sign session cookies (written by `create_demo_user`) |

| `SESSION_MAX_AGE_HOURS` | no | `8` | Session lifetime |

| `COOKIE_SECURE` | no | `false` | Set `true` when the app is served over HTTPS |

| `ALLOWED_ORIGINS` | no | `http://localhost:3010` | Comma-separated browser origins allowed to sign in (CSRF check) |

| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_MINUTES` | no | `5` / `15` | Failed admin sign-ins per email before a temporary block |

Customer account settings (`APP_DB_*`, identity source, providers, rate limits and so on) are
listed in [Customer accounts](#customer-accounts).

The backend refuses to start if a required value is missing and names the missing

setting without printing any values.

### `frontend/.env.local` (never committed)

| Variable | Default | Meaning |

|---|---|---|

| `BACKEND_URL` | `http://localhost:8010` | Where Next.js forwards `/api/*` (server-side only) |

## Database permissions

The application connects as `bnd_readonly`, never as `postgres`. The role is created by

[`backend/create_readonly_role.sql`]\(backend/create_readonly_role.sql), which only adds:

- `LOGIN`, at most 20 connections, and `default_transaction_read_only = on`

- `CONNECT` on database `chubbstub` and `USAGE` on schema `public`

- `SELECT` on the three `ar\_*` tables

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

All endpoints except health and the sign-in and registration steps require the session cookie.
Admin endpoints return 403 to customers. Invoice endpoints show a customer only their own customer's invoices. Interactive docs:

http://localhost:8010/docs. Errors always have the shape `{"detail": "message"}`.

| Endpoint | Purpose |

|---|---|

| `GET /api/health` | App and database status |

| `POST /api/admin/login` | Admin sign-in (ENV account) |

| `POST /api/auth/logout` · `GET /api/auth/me` | Session (both roles); `me` returns `role` and `customerno` |

| `POST /api/auth/register/lookup` · `send-codes` · `resend-code` · `verify` | Customer registration (see [Customer accounts](#customer-accounts)) |

| `POST /api/auth/login/request` · `POST /api/auth/login/verify` | Customer login by email or phone code |

| `GET /api/admin/review-queue?status_filter` | Admin only: lookups that matched several customers |

| `GET /api/dashboard/summary?start&end` | KPIs, previous-period comparison, monthly series, top 8 facilities, 10 recent invoices |

| `GET /api/invoices?q&start&end&facility&sort&order&page&page_size` | Invoice list (`page_size` ≤ 100; `sort`: `invoice_date`, `invoice_no`, `member_name`, `facility`, `amount`) |

| `GET /api/invoices/{invoice_no}/{header_seq}` | Invoice header, facility and line items (a customer gets 404 for another customer's invoice) |

| `GET /api/facilities` | Facilities for the filter (admin only) |

| `GET /api/reports/invoices?start&end&page&page_size` | One row per invoice, with count and total |

| `GET /api/reports/invoices/export?start&end` | Streamed CSV of the same report |

## Project structure

| Path | Purpose |

|---|---|

| `backend/app/main.py` | FastAPI app, routers, error handlers |

| `backend/app/config.py` | Settings from `.env`, validated at startup |

| `backend/app/database.py` | Read-only connection pool |

| `backend/app/auth.py` | Admin password check, admin rate limit, `/api/auth` session routes |

| `backend/app/sessions.py` | Role-aware session cookie, role checks, invoice scope, signed step tokens |

| `backend/app/identity.py` | Step 1 lookup (name and SSN) against the configured identity source |

| `backend/app/otp.py` · `notify.py` · `contact.py` | One-time codes, delivery providers, email and phone normalisation |

| `backend/app/routes/end_user_auth.py` · `admin.py` | Customer registration and login; admin login and review queue |

| `backend/app/app_database.py` · `audit.py` · `migrate.py` | Writable app-schema connection, audit log, migrations |

| `backend/migrations/` | SQL for the app-owned `app` schema |

| `backend/app/invoice_queries.py` | ****All invoice SQL and the financial rules**** |

| `backend/app/routes/` | Dashboard, invoices and report endpoints |

| `backend/app/schemas.py` | Request/response models |

| `backend/app/create_demo_user.py` | Writes the demo login to `.env` |

| `frontend/src/app/login/` | Customer registration and sign-in |

| `frontend/src/app/admin/` | Admin sign-in at `/admin` |

| `frontend/src/app/admin/(panel)/` | Admin pages at `/admin/dashboard`, `/invoices`, `/reports`, `/review-queue`; each `page.tsx` wraps a client `*-view.tsx` |

| `frontend/src/app/portal/` | Customer home: their own invoices |

| `frontend/src/components/app-shell.tsx` | Sidebar (collapsible, mobile drawer), top-bar search, sign out |

| `frontend/src/components/ui.tsx` | Cards, skeletons, empty/error states, date filter, pagination |

| `frontend/src/components/invoice-table.tsx` | Invoice table used by dashboard, invoices and report |

| `frontend/src/components/charts.tsx` | Monthly amount and top facilities charts |

| `frontend/src/lib/` | API helpers and types, formatting, URL filter state |

| `frontend/src/proxy.ts` | Sends visitors without a session to `/admin` (admin pages) or `/login` (customer pages) |

Filters live in the URL (`/admin/invoices?q=…&start=…`), so a filtered view survives a

reload and can be bookmarked. The sidebar's collapsed state is remembered per browser.

## Customer accounts

Customers register and sign in at `/login`. Admins keep the ENV login at `/admin` and see every
customer. A customer sees only their own customer's invoices, and the backend enforces this on every
request.

Each sign-up or sign-in is verified with a 6-digit code sent to the customer's **email**. The phone
number is saved on the account for contact but is not verified, and no SMS is sent.

### Registration

1. **Find my account.** The customer enters first name, last name and SSN. The lookup key is the first
   3 letters of the last name plus the last 4 SSN digits, and it must equal the Sage customer number
   (for example `KUM4798`). The first name breaks ties when several customers match, and it is read
   from `billtoname` (`Last, First`).

   | Result | Shown to the customer |
   |---|---|
   | One match | "OK, we found your account", then step 2 |
   | No match | "We couldn't find a matching account. Please check your details or contact support." |
   | Several matches after the first-name tie-break | "We need to verify a few more details". Nothing is linked. The lookup goes to the admin review queue. |
   | Customer already has an account | "An account already exists for these details. Please log in instead." |

2. **Contact details.** The customer enters an email and a mobile number. A code is emailed to the address.
3. **Code.** The code must match. The account is then created, linked to the matched customer number,
   and the customer is signed in.

### Sign-in

The customer enters their email. A code is emailed, and it is checked the same way. The response is
the same whether or not the account exists, so the form cannot be used to find out who is registered.

### Open item: identity source (confirm with the client)

The lookup reads `ar_invoicehistoryheader`. Each `customerno` is 3 letters of the last name followed
by 4 digits (`KUM4798` for Kumah). The rule assumes those 4 digits are the last 4 digits of the SSN.
**This is not confirmed.** If it is not true, the lookup must not be used.

Confirm with the client:
- that the 4 digits in `customerno` are the SSN's last 4 digits;
- whether this is a privacy problem, because customer numbers appear in invoice pages, URLs and CSV
  exports, so an SSN fragment would be exposed there;
- the first-name source, since `billtoname` is not always in `Last, First` form.

The lookup is in `backend/app/identity.py`. Table and column names are checked against a strict pattern
before use, because they are placed into SQL.

**Security note:** last 3 letters plus 4 digits identify a customer loosely. The emailed code proves that
the person controls the email address they typed, not that they are the customer. Anyone who knows the
name and SSN last 4 can register and link to that account.

### Setup

1. Create the writer role once, as the Postgres superuser (see
   [`backend/create_app_writer_role.sql`](backend/create_app_writer_role.sql)). The role can write only
   the `app` schema, not the Sage tables in `public`.
2. Set `APP_DB_USER` and `APP_DB_PASSWORD` in `backend/.env`.
3. Apply the migrations: `cd backend && ../venv/bin/python -m app.migrate`.

Without `APP_DB_*`, the admin area still works. Customer features answer 503.

### Customer account settings (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `APP_DB_USER` / `APP_DB_PASSWORD` | unset | Writer role for the `app` schema. Required for customer accounts |
| `APP_DB_HOST` / `APP_DB_PORT` / `APP_DB_NAME` | same as `DB_*` | Only if the app schema is elsewhere |
| `IDENTITY_SOURCE_TABLE` | `ar_invoicehistoryheader` | **Confirm the SSN assumption first** (see above) |
| `IDENTITY_CUSTOMERNO_COLUMN` / `IDENTITY_NAME_COLUMN` | `customerno` / `billtoname` | Column names in that table |
| `EMAIL_PROVIDER` | `console` | `console` (development) or `smtp` |
| `EMAIL_FROM` | `no-reply@example.com` | Sender address |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_STARTTLS` | unset / `587` / unset / unset / `true` | For `smtp` |
| `PHONE_DEFAULT_COUNTRY_CODE` | `1` | Added to national numbers typed without `+` |
| `TRUST_PROXY_HEADERS` | `false` | Read the client IP from `X-Forwarded-For` (last hop). Set only behind the Next.js proxy |
| `LOOKUP_MAX_ATTEMPTS` / `LOOKUP_IP_MAX_ATTEMPTS` / `LOOKUP_WINDOW_MINUTES` | `5` / `20` / `15` | Lookups per name and SSN combination, and per client IP |
| `VERIFY_IP_MAX_ATTEMPTS` / `VERIFY_WINDOW_MINUTES` | `20` / `15` | Code checks per client IP |
| `OTP_TTL_MINUTES` / `OTP_MAX_ATTEMPTS` | `10` / `5` | Code lifetime, and wrong guesses before the code is dead |
| `OTP_RESEND_COOLDOWN_SECONDS` | `60` | Wait between codes to the same address |
| `OTP_MAX_SENDS_PER_HOUR` | `5` | Codes to one email address per hour |
| `REGISTRATION_TOKEN_MINUTES` | `15` | Lifetime of the signed step tokens |

**Development.** With `EMAIL_PROVIDER=console`, codes are written to the backend log instead of sent.
`COOKIE_SECURE=true` is refused with `console`, so live codes never reach a production log.

**Codes and tokens.** Codes are 6 digits. They are stored only as keyed HMACs, bound to their
attempt, and used up once accepted. Between steps, the customer's details travel in short-lived signed
tokens, so the browser cannot change them. The tokens are readable (signed, not encrypted), so they
hold only the customer's own details.

**Stored data.** The full SSN is never stored. `app.users.ssn_last4_hash` is a keyed HMAC of the last 4
digits. The audit log stores outcome labels only, never SSNs or codes.

**Review queue.** Lookups that match more than one customer are listed at `/admin/review-queue`. Resolving
them is manual, and nothing is linked automatically.

### Tests for customer accounts

The pure rules run anywhere. The flow and access tests need the writable app schema, so point `APP_DB_*`
at a **test** database and set `TEST_APP_DB_RESET=1`. The tests truncate the app tables. Without the flag
they are skipped, so they cannot wipe real data.

```bash
cd backend
APP_DB_USER=... APP_DB_PASSWORD=... TEST_APP_DB_RESET=1 ../venv/bin/python -m pytest
```

The access tests also need the Sage database, because they check real invoice numbers.

## Verified data rules

Discovered from the data (the tables have no keys or constraints) and enforced by

`backend/tests/test_data_rules.py`:

- An invoice is identified by `(invoiceno, headerseqno)`; a line by `(invoiceno, headerseqno, detailseqno)`.

- ****Invoice amount = `taxablesalesamt + nontaxablesalesamt`.**** It equals the sum of the

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

- ****No indexes**** on the source tables (not added without approval). Most requests take

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
