# Schema reference

Authoritative DDL: `schema.sql`. DBML: `schema.dbml`. Live introspection: `mcp__secforms-db__describe_table`.

Last snapshot: 2026-05-22T15:33:21Z — 35 public tables, 34 foreign keys, no public enums.

## Layout

```
LAYER 0  forms
LAYER 1  signals · signal_ciks · form_<27 tables>
LAYER 2  cik_list · companies · people
LAYER 3  company_filings · people_filings
```

---

## Layer 0 — Registry

### `forms` (catalog of every form type the pipeline ingests)

| Column | Type | Role |
|---|---|---|
| `form` | text | **PK**. Form type literal as SEC writes it: `4`, `D/A`, `13F-HR`, `SC 13D`, etc. |
| `purpose` | text | Plain-English description of what the form is for. |
| `why_filed` | text | Regulatory trigger that requires filing it. |
| `nubeam_relevance` | text | Why we care commercially — the sales/intelligence angle. |
| `signal_side` | text | `allocator` (capital deployers) or `seeker` (capital raisers). Filter dimension for any "who's investing / who's raising" question. |
| `filings_count` | bigint | Total signals ingested of this form. Default 0; refresh manually via `refresh_forms_counts()`. |
| `companies_count` | bigint | Distinct companies on this form. Default 0; refresh same way. |

27 rows today.

---

## Layer 1 — Signals

### `signals` (master event router, 1 row per filing)

| Column | Type | Role |
|---|---|---|
| `accession` | text | **PK**. Unique SEC filing accession. |
| `form_type` | text | **FK → `forms.form`** (RESTRICT). Routes to the matching `form_<type>` table. |
| `date_added` | timestamptz | When the pipeline ingested it. Use this for "recent" filters; the SEC filing date lives on each form_<type> row. |

Index: `(form_type, date_added)`.

### `signal_ciks` (junction: every CIK on every filing + role)

| Column | Type | Role |
|---|---|---|
| `accession` | text | **PK + FK → `signals.accession`** (CASCADE). |
| `cik` | text | **PK + FK → `cik_list.cik`** (CASCADE). |
| `cik_role` | text | **PK**. One of `filer_cik`, `issuer_cik`, `company_cik`, `person_cik`, `intermediary_cik`, `reg_cik`. See `identifiers.md`. |

Composite PK `(accession, cik, cik_role)`. Same CIK can appear under different roles on one filing.

### `form_<type>` tables (27 tables, 1:1 with `signals`)

Every form table follows the same shape:

- **PK + FK:** `accession text REFERENCES signals(accession) ON DELETE CASCADE`
- **Common columns (every form table):** `form_type text`, `filing_date date`, `filer_cik text`, `doc_url text`, `doc_name text`, `doc_mime text`, `index_url text`, `byte_size bigint`.
- **Per-form columns:** vary widely (3 cols on simple forms like `form_8_k`, up to 30 on `form_c` / `form_c_a`). See `form-tables.md` for the per-form details.

Full table list (live, 27): `form_3`, `form_4`, `form_4_a`, `form_5`, `form_8_k`, `form_10_q`, `form_13f_hr`, `form_13f_nt`, `form_40_app`, `form_144`, `form_144_a`, `form_424b5`, `form_425`, `form_c`, `form_c_a`, `form_d_a`, `form_def_14a`, `form_fwp`, `form_n_14`, `form_n_cen`, `form_n_port`, `form_n_px`, `form_s_1`, `form_s_1_a`, `form_s_3`, `form_sc_13d`, `form_sc_13g`.

---

## Layer 2 — Entities

### `cik_list` (master deduped CIK registry)

| Column | Type | Role |
|---|---|---|
| `cik` | text | **PK**. 10-digit zero-padded SEC CIK. |
| `date_added` | timestamptz | When this CIK first appeared on any filing. |
| `enriched` | boolean | Worker watches `enriched = false`. Flips to `true` after `companies` or `people` row is written. |

### `companies` (enriched company entities)

| Column | Type | Role |
|---|---|---|
| `company_cik` | text | **PK + FK → `cik_list.cik`** (CASCADE). |
| `name` | text | Legal entity name. |
| `ticker` | text | Stock exchange ticker (NULL if not listed). |
| `exchanges` | jsonb | Array of exchange codes. |
| `former_names` | jsonb | Array of past legal names. |
| `sic` | text | Standard Industrial Classification code. |
| `sic_description` | text | Human label for the SIC. |
| `state_of_incorp` | text | 2-letter state code. |
| `address` | text | Business address (semi-structured string from SEC). |
| `website` | text | Company URL. |
| `investor_website` | text | IR URL. |
| `fiscal_year_end` | text | `MM-DD` form. |
| `entity_type` | text | SEC entity type label. **Never `'individual'`** — that's a stale signal; person/company split happens in the worker, not from this column. |
| `filer_category` | text | SEC filer category. |
| `date_added` | timestamptz | When the company was enriched. |

### `people` (enriched person entities)

| Column | Type | Role |
|---|---|---|
| `person_cik` | text | **PK + FK → `cik_list.cik`** (CASCADE). |
| `canonical_name` | text | Normalized name (e.g. `"COOK TIMOTHY D"`). |
| `former_names` | jsonb | Array of prior names. |
| `address` | text | Last-known address. |
| `entity_type` | text | SEC entity type label. |
| `date_added` | timestamptz | When enriched. |

XOR with `companies`: a CIK is in one or the other, never both. Not DB-enforced.

---

## Layer 3 — Filings (per-entity history)

### `company_filings`

| Column | Type | Role |
|---|---|---|
| `company_cik` | text | **PK + FK → `companies.company_cik`** (CASCADE). |
| `accession` | text | **PK**. SEC accession (same identifier shape as `signals.accession` but inserted by a different pipeline; overlaps but is not derived from signals). |
| `form` | text | Form type as SEC writes it. |
| `filing_date` | date | SEC receipt date. |
| `items` | text | 8-K item codes when applicable, NULL otherwise. |
| `date_added` | timestamptz | When the row was written. |

Composite PK `(company_cik, accession)`. Indexes: `(filing_date)`, `(form)`.

### `people_filings`

| Column | Type | Role |
|---|---|---|
| `person_cik` | text | **PK + FK → `people.person_cik`** (CASCADE). |
| `accession` | text | **PK**. |
| `form` | text | Form type. |
| `filing_date` | date | |
| `date_added` | timestamptz | |

Composite PK `(person_cik, accession)`. Indexes: `(filing_date)`, `(form)`.

**Filter rules** (app-enforced at insert, not DB constraints):

- `form ∈ <the 27 in forms.form>`
- `filing_date >= CURRENT_DATE - INTERVAL '3 years'`

Old rows are not auto-purged.

---

## Foreign-key map

| From | To | Cardinality | On Delete |
|---|---|---|---|
| `signals.form_type` | `forms.form` | N:1 | RESTRICT |
| `form_<X>.accession` (×27) | `signals.accession` | 1:1 | CASCADE |
| `signal_ciks.accession` | `signals.accession` | N:1 | CASCADE |
| `signal_ciks.cik` | `cik_list.cik` | N:1 | CASCADE |
| `companies.company_cik` | `cik_list.cik` | 1:1 | CASCADE |
| `people.person_cik` | `cik_list.cik` | 1:1 | CASCADE |
| `company_filings.company_cik` | `companies.company_cik` | N:1 | CASCADE |
| `people_filings.person_cik` | `people.person_cik` | N:1 | CASCADE |

34 FKs total (27 form_*→signals + 7 above).

## When to use `signals + signal_ciks` vs `company_filings` / `people_filings`

| Question | Use |
|---|---|
| "What is currently happening across all filings of form X?" | `signals` + `signal_ciks` (live stream layer) |
| "Show me everything Apple ever filed in the last 3 years" | `company_filings` (per-entity history) |
| "Who appeared on filing accession N?" | `signal_ciks` joined to `companies` + `people` |
| "Was form 4 X by insider Y? what shares?" | `form_4` payload (signal layer) |
| "How many filings does fund Z make per quarter?" | `company_filings` (per-entity) |
