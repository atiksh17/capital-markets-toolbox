# Query recipes

Ready-to-paste SELECTs against the live `secforms` Postgres. All examples use named placeholders for clarity — the MCP `query` tool uses `$1, $2, ...` positional placeholders.

Every recipe is **read-only** and safe under the `secforms_ro` role.

---

## 1. Recent filings of a specific form

```sql
SELECT s.accession, s.date_added, f4.issuer_name, f4.person_name, f4.total_sale_usd
FROM signals s
JOIN form_4 f4 ON f4.accession = s.accession
WHERE s.form_type = '4'
  AND s.date_added >= now() - interval '7 days'
ORDER BY s.date_added DESC
LIMIT 50;
```

Swap `'4'` and `form_4` for any of the 27 form codes / form tables.

## 2. All filings ever (last 3y) for one company

```sql
SELECT cf.accession, cf.form, cf.filing_date, cf.items
FROM company_filings cf
JOIN companies c ON c.company_cik = cf.company_cik
WHERE c.ticker = $1                   -- e.g. 'AAPL'
ORDER BY cf.filing_date DESC;
```

## 3. All filings ever (last 3y) for one person

```sql
SELECT pf.accession, pf.form, pf.filing_date
FROM people_filings pf
JOIN people p ON p.person_cik = pf.person_cik
WHERE p.canonical_name ILIKE $1       -- e.g. '%COOK TIMOTHY%'
ORDER BY pf.filing_date DESC;
```

## 4. Every CIK on a specific filing (with role + entity type)

```sql
WITH ciks AS (
  SELECT sc.cik, sc.cik_role
  FROM signal_ciks sc
  WHERE sc.accession = $1
)
SELECT ciks.cik, ciks.cik_role,
       CASE
         WHEN c.company_cik IS NOT NULL THEN 'company'
         WHEN p.person_cik  IS NOT NULL THEN 'person'
         ELSE 'unenriched'
       END AS kind,
       COALESCE(c.name, p.canonical_name) AS display_name
FROM ciks
LEFT JOIN companies c ON c.company_cik = ciks.cik
LEFT JOIN people    p ON p.person_cik  = ciks.cik;
```

## 5. Top insiders by Form 4 filing volume (window)

```sql
SELECT p.person_cik, p.canonical_name, COUNT(*) AS filings
FROM form_4 f4
JOIN people p ON p.person_cik = f4.person_cik
WHERE f4.filing_date >= now()::date - $1::int    -- e.g. 60
GROUP BY p.person_cik, p.canonical_name
ORDER BY filings DESC
LIMIT 50;
```

## 6. Allocator-side filings only (any form classified `allocator`)

```sql
SELECT s.accession, s.form_type, s.date_added
FROM signals s
JOIN forms f ON f.form = s.form_type
WHERE f.signal_side = 'allocator'
  AND s.date_added >= now() - interval '30 days'
ORDER BY s.date_added DESC
LIMIT 100;
```

## 7. Seeker-side filings only

```sql
SELECT s.accession, s.form_type, s.date_added
FROM signals s
JOIN forms f ON f.form = s.form_type
WHERE f.signal_side = 'seeker'
  AND s.date_added >= now() - interval '30 days'
ORDER BY s.date_added DESC
LIMIT 100;
```

## 8. Unenriched CIKs (enrichment backlog)

```sql
SELECT cl.cik, cl.date_added
FROM cik_list cl
WHERE cl.enriched = false
ORDER BY cl.date_added ASC
LIMIT 100;
```

## 9. Count of filings per form_type in last N days

```sql
SELECT s.form_type, count(*) AS n
FROM signals s
WHERE s.date_added >= now() - ($1 || ' days')::interval    -- e.g. '7'
GROUP BY s.form_type
ORDER BY n DESC;
```

## 10. 13F-HR holdings — top managers by total reported value (last quarter)

```sql
SELECT f13.company_cik, f13.company_name, f13.period_of_report,
       f13.table_entry_total, f13.table_value_total
FROM form_13f_hr f13
WHERE f13.period_of_report >= now()::date - 100
ORDER BY f13.table_value_total DESC NULLS LAST
LIMIT 50;
```

## 11. Insider sales at companies that *also* filed S-1 or 424B5 in same window

Surfaces insiders at companies currently raising.

```sql
WITH raising AS (
  SELECT DISTINCT filer_cik AS company_cik
  FROM form_s_1
  WHERE filing_date >= now()::date - 60
  UNION
  SELECT DISTINCT filer_cik
  FROM form_424b5
  WHERE filing_date >= now()::date - 60
)
SELECT f4.company_cik, c.name AS company_name,
       p.canonical_name AS insider_name,
       f4.filing_date, f4.total_sale_usd
FROM form_4 f4
JOIN raising r ON r.company_cik = f4.company_cik
LEFT JOIN companies c ON c.company_cik = f4.company_cik
LEFT JOIN people    p ON p.person_cik  = f4.person_cik
WHERE f4.filing_date >= now()::date - 60
ORDER BY f4.filing_date DESC
LIMIT 100;
```

## 12. New insiders (Form 3, last 60 days)

```sql
SELECT f3.filing_date, f3.issuer_name, f3.person_name, p.address
FROM form_3 f3
LEFT JOIN people p ON p.person_cik = f3.person_cik
WHERE f3.filing_date >= now()::date - 60
ORDER BY f3.filing_date DESC
LIMIT 100;
```

## 13. Activist signals (SC 13D filings, last 30 days, ≥10% stake)

```sql
SELECT f13d.filing_date, f13d.issuer_name, f13d.filer_name,
       f13d.pct_of_class, f13d.shares_owned
FROM form_sc_13d f13d
WHERE f13d.filing_date >= now()::date - 30
  AND f13d.pct_of_class >= 10
ORDER BY f13d.pct_of_class DESC
LIMIT 50;
```

## 14. Reg CF (Form C) issuers with their funding portal + raise target

```sql
SELECT c.filing_date, c.company_name, c.intermediary_name,
       c.target_offering_amount, c.maximum_offering_amount, c.issuer_website
FROM form_c c
WHERE c.filing_date >= now()::date - 90
ORDER BY c.filing_date DESC
LIMIT 100;
```

## 15. Per-table row counts (health snapshot — uses MCP `count` tool or this query)

```sql
SELECT table_name,
       (xpath('/row/c/text()',
              query_to_xml(format('SELECT count(*) AS c FROM %I', table_name),
                           false, true, '')))[1]::text::bigint AS rows
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY rows DESC NULLS LAST;
```

Prefer `mcp__secforms-db__count` for a single table.

---

## Pattern: company name → entity → recent activity

```sql
WITH entity AS (
  SELECT company_cik FROM companies WHERE name ILIKE $1 LIMIT 1
)
SELECT cf.filing_date, cf.form, cf.accession
FROM company_filings cf
JOIN entity e USING (company_cik)
ORDER BY cf.filing_date DESC
LIMIT 50;
```

## Pattern: walk signal → form_X dynamically (when you know form_type but not the table)

`signals.form_type` matches the SEC code (e.g. `'4'`). Map to a table name with:

```
form_type    table_name
'3'          form_3
'4'          form_4
'4/A'        form_4_a
'5'          form_5
'8-K'        form_8_k
'10-Q'       form_10_q
'13F-HR'     form_13f_hr
'13F-NT'     form_13f_nt
'40-APP'     form_40_app
'144'        form_144
'144/A'      form_144_a
'424B5'      form_424b5
'425'        form_425
'C'          form_c
'C/A'        form_c_a
'D/A'        form_d_a
'DEF 14A'    form_def_14a
'FWP'        form_fwp
'N-14'       form_n_14
'N-CEN'      form_n_cen
'N-PORT'     form_n_port
'N-PX'       form_n_px
'S-1'        form_s_1
'S-1/A'      form_s_1_a
'S-3'        form_s_3
'SC 13D'     form_sc_13d
'SC 13G'     form_sc_13g
```

Rule: lowercase, replace ` ` and `-` with `_`, drop the prefix `form_` if it appears, and prefix `form_`. The skill always answers "which table" by checking this mapping.
