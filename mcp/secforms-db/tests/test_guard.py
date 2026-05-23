from secforms_mcp.guard import validate


ACCEPT = [
    "SELECT 1",
    "SELECT * FROM signals LIMIT 10",
    "SELECT count(*) FROM companies WHERE enriched = true",
    "WITH c AS (SELECT * FROM companies) SELECT * FROM c LIMIT 5",
    "SELECT s.accession, f.form FROM signals s JOIN forms f ON s.form_type = f.form",
    "EXPLAIN SELECT * FROM signals",
    "EXPLAIN (FORMAT JSON) SELECT * FROM signals",
    "SELECT (SELECT count(*) FROM companies) AS n",
]

REJECT = [
    ("", "empty"),
    ("INSERT INTO companies (company_cik) VALUES ('x')", "insert"),
    ("UPDATE companies SET company_name='x' WHERE company_cik='1'", "update"),
    ("DELETE FROM companies WHERE company_cik='1'", "delete"),
    ("DROP TABLE companies", "drop"),
    ("CREATE TABLE x (id int)", "create"),
    ("ALTER TABLE companies ADD COLUMN x int", "alter"),
    ("TRUNCATE companies", "truncate"),
    ("GRANT SELECT ON companies TO public", "grant"),
    ("COPY companies TO STDOUT", "copy"),
    ("SELECT 1; DROP TABLE companies", "multi-statement"),
    ("SELECT 1; SELECT 2", "multi-statement"),
    ("SELECT * FROM companies FOR UPDATE", "for update"),
    ("SELECT * FROM companies FOR SHARE", "for share"),
    ("SELECT pg_terminate_backend(1)", "write function"),
    ("SELECT pg_cancel_backend(1)", "write function"),
    ("SELECT set_config('search_path','x',false)", "write function"),
    ("SELECT 1 INTO temptable FROM companies", "select into"),
    ("EXPLAIN ANALYZE SELECT * FROM signals", "explain analyze"),
    ("EXPLAIN UPDATE companies SET x=1", "explain non-select"),
    ("VACUUM companies", "vacuum"),
    ("REINDEX TABLE companies", "reindex"),
    ("CREATE INDEX ix ON companies (company_cik)", "create index"),
    ("ALTER ROLE secforms_ro RENAME TO bad", "alter role"),
    ("DROP ROLE secforms_ro", "drop role"),
    ("MERGE INTO companies USING x ON true WHEN MATCHED THEN DELETE", "merge"),
    ("not even sql at all", "parse error"),
]


def test_accept():
    for sql in ACCEPT:
        r = validate(sql)
        assert r.ok, f"expected accept, got reject for: {sql!r} -> {r.reason}"


def test_reject():
    for sql, label in REJECT:
        r = validate(sql)
        assert not r.ok, f"expected reject ({label}) but accepted: {sql!r}"
