-- Creates the writer role for end-user accounts and the "app" schema it owns.
-- Run once as the postgres superuser, passing the password from backend/.env so it is never typed or printed:
--
--   PW=$(grep '^APP_DB_PASSWORD=' .env | cut -d= -f2-)
--   psql -h localhost -U postgres -d chubbstub -v app_password="$PW" -f create_app_writer_role.sql
--
-- Then run the migrations with the writer role: cd backend && python -m app.migrate
--
-- The writer can write only the "app" schema. It has no write grant on the Sage tables
-- in public, and the read-only reporting role (create_readonly_role.sql) is unchanged.
\set ON_ERROR_STOP on

ALTER ROLE bnd_app WITH LOGIN PASSWORD :'app_password' CONNECTION LIMIT 20;

GRANT CONNECT ON DATABASE chubbstub TO bnd_app;
CREATE SCHEMA app AUTHORIZATION bnd_app;
REVOKE ALL ON SCHEMA public FROM bnd_app;
-- The identity lookup reads the source table (TODO: confirm with the client, then uncomment):
-- GRANT USAGE ON SCHEMA public TO bnd_app;
-- GRANT SELECT ON public.<identity_source_table> TO bnd_app;
