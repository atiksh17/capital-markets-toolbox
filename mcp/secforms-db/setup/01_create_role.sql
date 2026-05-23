-- Idempotent creation of the secforms_ro role.
-- Run as a superuser (sec_admin) against the `secforms` database.
-- Usage: PGPASSWORD=... psql -h 127.0.0.1 -p 54324 -U sec_admin -d secforms -v ro_password="'<password>'" -f 01_create_role.sql

\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'secforms_ro') THEN
    EXECUTE format('CREATE ROLE secforms_ro LOGIN PASSWORD %L CONNECTION LIMIT 10', :'ro_password');
  ELSE
    EXECUTE format('ALTER ROLE secforms_ro WITH LOGIN PASSWORD %L CONNECTION LIMIT 10', :'ro_password');
  END IF;
END $$;

-- Required when public tables have RLS enabled (Supabase default).
-- Without this the role gets the SELECT grant but RLS default-deny returns 0 rows
-- for every query (no SELECT policy whitelists the role).
-- Safe for a read-only analytics role: BYPASSRLS does not grant any write privilege —
-- writes are still rejected by `default_transaction_read_only = on` + missing INSERT/UPDATE/DELETE grants.
ALTER ROLE secforms_ro BYPASSRLS;

REVOKE ALL ON DATABASE secforms FROM secforms_ro;
GRANT CONNECT ON DATABASE secforms TO secforms_ro;

GRANT USAGE ON SCHEMA public TO secforms_ro;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO secforms_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO secforms_ro;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO secforms_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO secforms_ro;

ALTER ROLE secforms_ro SET default_transaction_read_only = on;
ALTER ROLE secforms_ro SET statement_timeout = '15s';
ALTER ROLE secforms_ro SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE secforms_ro SET lock_timeout = '5s';
ALTER ROLE secforms_ro SET search_path = public;

COMMIT;
