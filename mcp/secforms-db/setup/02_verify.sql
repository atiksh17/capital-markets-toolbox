-- Verification: run as secforms_ro (not superuser).
-- Usage: PGPASSWORD=<ro_password> psql -h 127.0.0.1 -p 54324 -U secforms_ro -d secforms -f 02_verify.sql
-- All blocks below should print expected results. The mutations should FAIL.

\set ON_ERROR_STOP off

\echo
\echo == Positive checks (should succeed) ==

SELECT 1 AS select_one;
SELECT count(*) AS table_count FROM information_schema.tables WHERE table_schema = 'public';
SELECT current_user, current_setting('default_transaction_read_only') AS read_only,
       current_setting('statement_timeout') AS stmt_timeout,
       current_setting('search_path') AS search_path;

\echo
\echo == Negative checks (should each FAIL with 'permission denied' or 'read-only transaction') ==

\echo --- INSERT (expect failure) ---
INSERT INTO companies (company_cik) VALUES ('0000000000');

\echo --- UPDATE (expect failure) ---
UPDATE companies SET company_name = 'x' WHERE company_cik = '0000000000';

\echo --- DELETE (expect failure) ---
DELETE FROM companies WHERE company_cik = '0000000000';

\echo --- CREATE TABLE (expect failure) ---
CREATE TABLE _ro_should_fail (id int);

\echo --- TRUNCATE (expect failure) ---
TRUNCATE companies;

\echo --- DROP (expect failure) ---
DROP TABLE companies;

\echo
\echo == If you saw 'ERROR' on every negative check above, role isolation is working. ==
