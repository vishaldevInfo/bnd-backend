-- Creates the read-only role the application connects with.
-- Run as the postgres superuser, passing the password from backend/.env so it is never typed or printed:
--
--   PW=$(grep '^DB_PASSWORD=' .env | cut -d= -f2-)
--   psql -h localhost -U postgres -d chubbstub -v ro_password="$PW" -f create_readonly_role.sql
--
-- It only adds a role and SELECT grants; no table is created, altered or dropped.
\set ON_ERROR_STOP on

CREATE ROLE bnd_readonly LOGIN PASSWORD :'ro_password' CONNECTION LIMIT 20;
-- Second safety net next to the app's own read-only sessions.
ALTER ROLE bnd_readonly SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE chubbstub TO bnd_readonly;
GRANT USAGE ON SCHEMA public TO bnd_readonly;
GRANT SELECT ON public.ar_salesperson,
                public.ar_invoicehistoryheader,
                public.ar_invoicehistorydetail TO bnd_readonly;
