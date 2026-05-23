# Identifiers used in secforms

## CIK — SEC Central Index Key

- **Format:** zero-padded 10-digit string. Example: `"0000320193"` (Apple Inc).
- **Type in DB:** `text` everywhere. Never numeric. Don't strip leading zeros.
- **Authority:** issued by SEC EDGAR. One CIK per legal entity (a person or a company), forever.
- **Where it lives in this DB:**
  - `cik_list.cik` — master deduped registry
  - `companies.company_cik` — 1:1 FK to `cik_list.cik`, only for enriched company CIKs
  - `people.person_cik` — 1:1 FK to `cik_list.cik`, only for enriched person CIKs
  - `signal_ciks.cik` — every CIK appearing on every filing
  - `<form_X>.<role>_cik` — form-specific CIK columns (see below)

A given CIK is either in `companies` or `people` — never both. The split is decided at enrichment time by the worker. (`cik_list` is the union.)

## accession — SEC filing accession number

- **Format:** dashed string like `"0001-24-000001"` or `"0000320193-24-000001"`.
- **Type in DB:** `text`. Globally unique per filing.
- **Where it lives:**
  - `signals.accession` — PK, one row per filing
  - `<form_X>.accession` — PK and FK to `signals.accession` (1:1)
  - `signal_ciks.accession` — part of composite PK
  - `company_filings.accession` / `people_filings.accession` — per-entity filing history

## CIK roles (`signal_ciks.cik_role`)

`signal_ciks` is the bridge between filings and entities. For every CIK on every filing, one row is written with a `cik_role`:

| Value              | Meaning |
|--------------------|---------|
| `filer_cik`        | the CIK that actually submitted the form to EDGAR |
| `issuer_cik`       | the public company whose securities the form is about (Form 4, Form 144, SC 13D/G, ...) |
| `company_cik`      | the company entity disclosed on the form (Form C, Form D, Form 13F, Form N-PORT, ...) |
| `person_cik`       | the individual reporting (Form 3, Form 4, Form 5) |
| `intermediary_cik` | a regulated intermediary (e.g. Reg CF funding portal on Form C) |
| `reg_cik`          | the registrant (used on Form N-PORT for the fund registrant) |

The same CIK can appear in multiple roles on the same filing. The composite PK is `(accession, cik, cik_role)` — so duplicates per role are impossible, but the same CIK can show up twice on one filing under different roles.

## `company_cik` vs `person_cik` (in form tables)

Form tables that capture both a company and a person (e.g. `form_4` — insider trading) have **both** columns:

- `company_cik` = the issuer the insider is reporting on
- `person_cik` = the insider doing the reporting

Don't conflate them with the columns of the same name in `companies` / `people`. The form-table columns are *references at filing time*; the entity-table columns are the *enriched profiles*. Join with FK semantics:

```sql
SELECT f4.*, c.name AS issuer_name, p.canonical_name AS insider_name
FROM form_4 f4
LEFT JOIN companies c ON c.company_cik = f4.company_cik
LEFT JOIN people    p ON p.person_cik  = f4.person_cik;
```

`LEFT JOIN` because the CIK may not be enriched yet (`cik_list.enriched = false`).

## Other identifiers worth knowing

- **CUSIP** — appears in `form_sc_13d.cusip` and `form_sc_13g.cusip` (plus `cusips` jsonb for multi-class). 9-character security identifier; SEC-side.
- **ticker** — `companies.ticker`. Stock exchange ticker symbol. May be NULL for non-listed entities.
- **SIC** — Standard Industrial Classification, `companies.sic` (text code) + `companies.sic_description`. Useful for sector filters.
- **CRD** — `form_c.intermediary_crd` / `form_c_a.intermediary_crd`. FINRA Central Registration Depository ID for the Reg CF funding portal.
