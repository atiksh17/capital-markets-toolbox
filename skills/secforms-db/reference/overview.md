# secforms — business overview

## What this database is

`secforms` is a Postgres database that captures SEC EDGAR filings as **signals** for capital-markets sales intelligence. Every filing is normalized into one of 27 form-specific tables and indexed by the CIKs (SEC Central Index Keys) it mentions — so any company or person who shows up on any tracked filing becomes a queryable, enriched entity.

The downstream use case: surface the right person/company at the right moment (e.g. a Form 4 insider sale, a Form 144 pre-sale notice, an S-1 IPO filing) for targeted outreach.

## Two sides of the capital markets

Every form is tagged `signal_side`:

- **`allocator`** — capital deployers. Funds, RIAs, institutional investors. Their filings tell you who is buying / holding (13F-HR, N-PORT, N-CEN, SC 13D, SC 13G, ...).
- **`seeker`** — capital raisers. Issuers, founders, insiders. Their filings tell you who is selling / raising (S-1, 424B5, Form D/A, Form C, Form 4, Form 144, ...).

`forms.signal_side` is the column to filter on whenever a question is "show me allocators who …" or "find seekers that …".

## The four layers

```
LAYER 0 · REGISTRY     forms                       (27 form types, allocator/seeker tag)
                         ↑ FK
LAYER 1 · SIGNALS      signals                     (1 row per filing)
                         ↓ 1:1 CASCADE
                       form_<type>                 (27 per-form payload tables)
                         ↓ N:M via
                       signal_ciks                 (every CIK on every filing + role)
                         ↑ FK
LAYER 2 · ENTITIES     cik_list                    (deduped CIK registry, enrichment flag)
                         ↓ 1:1 XOR (app-enforced)
                       companies   |   people      (enriched profiles)
                         ↓ 1:N CASCADE
LAYER 3 · FILINGS      company_filings | people_filings   (per-entity 3-yr filing history)
```

Read top-down for "where did this data come from" and bottom-up for "what does this entity do".

## How rows arrive

Upstream automation (out of scope for this skill) listens to SEC EDGAR feeds and pushes new filings into the database. Three things happen on every filing:

1. A row in `signals` is created with the `accession` and `form_type`.
2. A row in the matching `form_<type>` table holds the form-specific payload.
3. Every CIK on the filing lands in `signal_ciks` with its role (`filer_cik`, `issuer_cik`, `company_cik`, `person_cik`, `intermediary_cik`, `reg_cik`).

Separately, an enrichment worker watches `cik_list.enriched = false`. When it finds a new CIK it calls the SEC enrichment API, decides "company or person", and writes the enriched profile into `companies` or `people` plus a rolling 3-year filing history into `company_filings` / `people_filings`.

Once enriched, every future filing automatically links back to the entity via `signal_ciks`.

## Things that are true but not obvious

- **`accession`** is the unique key for everything in the signals layer. It looks like `0001-24-000001`. If you have one, you can pull the full payload for the filing.
- **`cik`** is a 10-digit zero-padded string (`"0000320193"`, not `"320193"`). Always treat it as `text`, never as a number.
- **A CIK is either a company OR a person.** Never both. There is no DB constraint enforcing this — the enrichment worker decides at write time. If you need "is X a company or person", check whether the CIK appears in `companies.company_cik` or `people.person_cik`.
- **`company_filings` and `people_filings` are *not* derived from `signals`.** They come from a separate per-entity SEC API lookup at enrichment time. They overlap by accession but represent different ingest paths.
- **3-year rolling window** on `company_filings` / `people_filings` is *app-enforced*, not a DB constraint. Old rows are not auto-deleted.
- **Filing types tracked are the 27 in `forms`.** Anything else SEC publishes isn't in this DB.
