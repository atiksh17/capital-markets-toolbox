# Plan: Claude skill `secforms-db` (SEC filings database expert)

> **Historical design doc.** Snapshots the plan as it was written before the build. Actual production state diverges:
> - Production URL: `https://mcp.nubeam.io/mcp` (not a placeholder)
> - Auth: OAuth 2.1 (PKCE) for friends + static-bearer fallback for server scripts (the doc below predates the OAuth pivot)
> - Schema snapshot: 27 form tables (not 28 as guessed mid-plan)
> - Per-friend tokens + IP-restricted root token
> - Field-picker step (§3.5 in `skills/secforms-db/reference/query-advisor.md`)
>
> For the live operating runbook see [`docs/for-maintainers-deploy.md`](docs/for-maintainers-deploy.md).

## Context

User wants a Claude skill that knows the SEC-filings Postgres database (project `secforms` in `sec-postgres` container, port 54324) so deeply that any future question about it — "what does column X mean", "how do I join form_4 to companies", "which tables hold person CIKs", "what's the difference between filer_cik and issuer_cik" — gets answered accurately without re-introspecting the DB every time.

This is **phase 1** of a two-phase ask: skill first, then a read-only MCP later. Both will live under `/root/.claude/capital-markets-toolbox/`.

Scope per user (locked):
- ✅ Schema reference (tables, columns, types, FKs, enums)
- ✅ Business meaning per table / column
- ✅ Common query patterns & joins
- ❌ Operational rules (enrichment, RLS, n8n jobs, triggers) — explicitly out of scope for the skill

Install target: **drafts only in `capital-markets-toolbox/`**. Don't copy to `~/.claude/skills/` yet.

## What already exists (reuse, don't rewrite)

The repo `/root/supabase-pro/` already has high-quality docs that the skill should consume verbatim or by reference:

| Existing file | Reuse as |
|---|---|
| `/root/supabase-pro/DATABASE_SCHEMA.md` (322 lines) | Source of canonical schema reference → copy into `reference/schema.md` |
| `/root/supabase-pro/SCHEMA_GRAPH.md` (397 lines) | ERD + relationship matrix → copy into `reference/erd.md` |
| `/root/supabase-pro/preview.sql` (25 KB) | Canonical DDL → copy as `reference/schema.sql` (verbatim, no edits) |
| `/root/supabase-pro/preview.dbml` (23 KB) | DBML for visual tools → copy as `reference/schema.dbml` |
| `/root/supabase-pro/DATABASE.md`, `DATABASE_PLAN.md` | Business overview → distill into `reference/overview.md` |
| `/root/supabase-pro/entities/companies/company_schema.json` | Companies column meaning |
| `/root/supabase-pro/entities/people/people_schema.json` | People column meaning |
| `/root/supabase-pro/forms.json` (114 KB) | Per-form purpose / why_filed / nubeam_relevance → distill into `reference/form-tables.md` |
| `/root/supabase-pro/forms+sql.json` (131 KB) | Per-form column meaning |
| `/root/supabase/init/00_constants.md` | SCRAPE_LIST + form_type → table_name map |

The skill **must not duplicate** these — it copies the immutable ones (DDL, ERD) and distills the narrative ones (business overview, form purpose). One source of truth per fact.

## Live DB snapshot (from introspection, 2026-05-22)

Connection: `postgresql://sec_admin:<pw>@127.0.0.1:54324/secforms` (container `sec-postgres`).

- **35 public tables**, organized in 4 layers:
  1. Registry: `forms`
  2. Filings: `signals` (master), 28 `form_*` payload tables (1:1 FK to signals)
  3. Junction: `signal_ciks`, `cik_list`
  4. Entities: `companies`, `people`, `company_filings`, `people_filings`
- **34 foreign keys** — every `form_*.accession → signals.accession`; `companies.company_cik`, `people.person_cik`, `signal_ciks.cik` → `cik_list.cik`; `signals.form_type → forms.form`
- **No enums** in `public` (verified)
- All form tables follow same shape: PK `accession`, FK to `signals`, plus 3–30 form-specific columns

Note doc/live mismatch: `DATABASE_SCHEMA.md` says 27 forms, live DB has **28** form tables. Skill must reflect live DB, not stale doc count.

## Skill layout

```
/root/.claude/capital-markets-toolbox/skills/secforms-db/
├── SKILL.md                        # trigger doc (<5 KB, progressive disclosure)
├── reference/
│   ├── overview.md                 # business purpose + 4 layers (distilled)
│   ├── erd.md                      # entity-relationship diagram (mermaid)
│   ├── identifiers.md              # CIK, accession, cik_role conventions
│   ├── schema.md                   # all 35 tables: purpose + every column
│   ├── schema.sql                  # canonical DDL (verbatim from preview.sql)
│   ├── schema.dbml                 # DBML mirror (for dbdiagram.io)
│   ├── form-tables.md              # per-form table: form_*, what it captures, key columns
│   └── query-recipes.md            # common joins + ready-to-run SELECTs
└── scripts/
    └── refresh-schema.sh           # regenerate schema.sql + table inventory from live DB
```

### `SKILL.md` (the trigger surface)

YAML frontmatter:
```yaml
---
name: secforms-db
description: Expert knowledge of the secforms Postgres database — 35 tables covering SEC EDGAR filings, CIK entities (companies + people), 28 per-form payload tables, and the signals/junction layer that ties them together. Use when answering any question about table purpose, column meaning, joins, or how to query SEC filings data.
---
```

Body (≤5 KB) — orientation only, not exhaustive content:
1. **What this DB is** (3 sentences, lifted from `overview.md`)
2. **The 4 layers** (registry → signals → junction → entities) with one-line each
3. **Key identifiers** (CIK = 10-digit padded; accession = filing PK)
4. **Decision tree: which reference file to read for which question**
   - "What does table/column X mean?" → `reference/schema.md`
   - "How are tables connected?" → `reference/erd.md`
   - "What does form_X capture?" → `reference/form-tables.md`
   - "How do I write a query joining A → B?" → `reference/query-recipes.md`
   - "Exact DDL for table X?" → `reference/schema.sql`
   - "What's a CIK / accession / cik_role?" → `reference/identifiers.md`
   - **"User intent is vague — they want to find people/companies/filings but haven't specified what exactly"** → `reference/query-advisor.md` (enter advisor mode: clarify → propose options → refine → confirm → run)
   - "User has clear intent and just wants the query run" → `reference/mcp-usage.md` → `mcp__secforms-db__query`
5. **Connection** (read-only): how to connect to live DB if user wants to verify (host/port/db, point at `scripts/refresh-schema.sh` for re-introspection)

### Per-reference file content (concise)

- **`overview.md`** (~150 lines): business purpose, 4-layer model, data flow at high level (1 paragraph: "filings are ingested upstream by an automated pipeline" — no n8n/automation depth, per scope).
- **`erd.md`** (~400 lines): copy of `SCHEMA_GRAPH.md` (ASCII + mermaid + matrix). Update form count from 27 → 28.
- **`identifiers.md`** (~80 lines): CIK format, accession format, the six `cik_role` values, company_cik vs person_cik distinction (XOR at app layer).
- **`schema.md`** (~400 lines): for each of 35 tables — purpose (1 line), column list with type + meaning, PK, FK targets. Pull narrative meaning from `DATABASE_SCHEMA.md` + entity schemas + forms.json. Tables grouped by layer.
- **`schema.sql`**: verbatim copy of `/root/supabase-pro/preview.sql`. Authoritative DDL.
- **`schema.dbml`**: verbatim copy of `/root/supabase-pro/preview.dbml`.
- **`form-tables.md`** (~600 lines): for each of 28 `form_*` tables — form code, purpose (from forms.json), why filed, signal side (allocator / seeker), key columns beyond the standard accession/CIK set. One section per form. Distilled from `forms+sql.json` + `forms.json`.
- **`query-recipes.md`** (~200 lines): 10–15 ready-to-paste SELECTs for the most common questions:
  - all filings for a company (CIK → company_filings)
  - all filings for a person (CIK → people_filings)
  - join signals → form_4 → companies for insider trades by company
  - find unenriched CIKs (`cik_list.enriched = false`)
  - count filings per form_type in last N days
  - allocator-side filings only (join forms.signal_side)
  - signals + signal_ciks expansion (all CIKs on a filing with their roles)
  - per-table row counts (health check)
  - top filers by form
  - 13F holdings join pattern

### `reference/query-advisor.md` (new — vague-request → final-SQL workflow)

Sub-mode of the skill. Activated when the user describes intent loosely ("find people who…", "help me look for companies that…", "what kind of insider activity can you show me?"). The skill must **not** immediately run a query — it enters advisor mode.

**Advisor protocol** (codified in this file so the LLM follows the same loop every time):

1. **Clarify intent** (≤3 short questions):
   - Subject: companies, people, filings, or holdings?
   - Filter dimensions: time window, geography, form type, role (insider vs. allocator), size, ticker, etc.?
   - Output: count, list, ranked list, joined detail?
2. **Propose 2–4 candidate queries** as a numbered menu. Each option states:
   - One-line **what it returns** (in plain English)
   - The **tables it touches** (and why those, given schema knowledge)
   - Approximate **result shape** (columns + row count expectation)
   - **Caveats** (e.g. "only enriched companies — `companies.enriched=true`")
   - Do **not** show SQL yet
3. **User picks or refines.** If user picks → go to step 4. If user refines ("narrow to last 30 days", "add ticker") → loop step 2 with the refinement applied.
4. **Show the SQL** for the chosen option, with a 1-line annotation per clause. Ask: *"Run as-is, or tweak?"*
5. **Run via `mcp__secforms-db__query`** when user confirms. Show result preview (first 10 rows + total count). Offer follow-ups ("filter further?", "export?", "join more detail?").

**Decision rules built into the advisor:**

- Subject = "person" → start from `people` (enriched); add `signal_ciks` + `signals` + `form_X` only if user wants per-filing detail
- Subject = "company" → start from `companies`; same join pattern
- Subject = "what just happened" → start from `signals` + `forms` (allocator/seeker side)
- Subject = "who holds what" → 13F path: `form_13f_hr` → `signal_ciks` → `cik_list` → `companies`
- Subject = "insider trading" → Form 4 path: `form_4` → `signals` → `signal_ciks` → `people`
- Vague time terms ("recent", "lately") → propose 7d / 30d / 90d as picker options, don't guess

**Heuristics for proposing options:**

- Always include one "broad" option (looser filter, more rows) and one "narrow" option (tighter, fewer rows) so user has a tradeoff
- If the request maps cleanly to a recipe in `query-recipes.md`, cite the recipe id and offer it as option 1
- If filters require a column the user didn't mention, surface it as a question rather than guessing a default

**Example dialog** (included in the file as a worked example so the LLM has a pattern to mimic):

> **User**: "Help me find people I should look at."
>
> **Advisor**: "Three quick questions — (1) people in a specific role (corporate insiders, fund managers, signatories)? (2) Time window for their recent activity? (3) Any company or sector filter?"
>
> *(user answers: insiders, last 60 days, no sector filter)*
>
> **Advisor**: "Here are 3 options:
> 1. **Top insiders by Form 4 filing volume (last 60d)** — joins `form_4` → `signal_ciks` → `people`; returns name + cik + filing_count; ~50–500 rows
> 2. **Insiders at companies that also filed S-1/424B5 (capital-raise signal) in last 60d** — narrower, ~10–80 rows; surfaces insiders at companies actively raising
> 3. **New insiders (Form 3 filed in last 60d)** — people just becoming insiders; ~100–300 rows
>
> Which one — or want to mix filters?"

The advisor sub-mode is **opt-in by user signal**, not always-on: triggered when SKILL.md decision tree detects vague intent (user didn't specify a table, a filter, or a concrete SELECT shape). If the user gives a fully-formed query intent, the skill goes straight to `query-recipes.md` + `mcp__secforms-db__query`.

### `scripts/refresh-schema.sh`

Bash script (read-only) that re-runs introspection and rewrites `schema.sql` + a table inventory table inside `schema.md`. Uses the `sec-postgres` container credentials. Marks the run timestamp in the top of `schema.md`. Lets the skill stay current after future migrations.

## Build steps (when plan is approved)

1. `mkdir -p /root/.claude/capital-markets-toolbox/skills/secforms-db/{reference,scripts}`
2. Copy `preview.sql` → `reference/schema.sql`; copy `preview.dbml` → `reference/schema.dbml` (verbatim, no edits)
3. Write `reference/erd.md` from `SCHEMA_GRAPH.md` (fix 27→28 form count)
4. Write `reference/identifiers.md` (distilled, ~80 lines)
5. Write `reference/overview.md` (distilled from DATABASE.md + DATABASE_PLAN.md, no automation depth)
6. Write `reference/schema.md` by walking the 35 tables, pulling per-column meaning from DATABASE_SCHEMA.md / entity JSON schemas / forms+sql.json
7. Write `reference/form-tables.md` by walking the 28 form tables, pulling purpose from forms.json and column meaning from forms+sql.json
8. Write `reference/query-recipes.md` (hand-write 10–15 recipes against live schema; verify each runs against `sec-postgres` container)
9. Write `reference/query-advisor.md` (clarify→propose→refine→confirm→run protocol; decision rules per subject; 2–3 worked example dialogs)
10. Write `SKILL.md` (trigger doc with decision tree — including the vague-intent branch into advisor)
11. Write `scripts/refresh-schema.sh` and test it once

## Verification

End-to-end check after build:

1. **Self-coherence**: every table in `schema.sql` appears in `schema.md`. Every FK shown in `erd.md` matches `schema.sql`. Form count is 28 everywhere.
2. **Round-trip queries**: each SELECT in `query-recipes.md` runs successfully against `sec-postgres` (port 54324). Use the supabase-pg MCP to verify.
3. **Answerability test**: from a fresh Claude session, ask 5 questions of varying depth — must answer from skill files alone, no live DB hits required:
   - "What does `signal_ciks.cik_role` represent and what values can it take?"
   - "What's the join from a company name to its insider trades?"
   - "What columns does `form_13f_hr` have?"
   - "How is `companies` different from `cik_list`?"
   - "Why is there both `company_cik` and `person_cik` if both are CIKs?"
4. **Advisor-flow test**: in a fresh session, send a deliberately vague prompt: *"help me find some people I should look at."* — the skill must enter advisor mode (clarify questions, then propose 2–4 candidate queries with table sources + caveats, then refine on user feedback, then show final SQL, then run it via the MCP only after confirmation). It must **not** dump a SQL query as the first response.
4. **Skill installability**: `SKILL.md` frontmatter passes Claude skills validator (`name` kebab-case, `description` ≤1024 chars, ≤5 KB body).
5. **Refresh script**: run `scripts/refresh-schema.sh`; confirm `schema.sql` is regenerated identically (idempotent on unchanged DB).

## Out of scope of the skill (covered by the MCP — see Part 2 below)

- Live query execution from inside Claude (the MCP does this)
- RLS policies, triggers, RPCs (`ingest_signal`, `enrich_company_v2`, `enrich_person_v2`)
- n8n / automation pipeline depth
- Write operations of any kind

---

# Part 2: MCP `secforms-ro` (read-only Postgres MCP for the skill)

## Context

The skill teaches Claude *what* the DB contains. The MCP gives Claude the *ability to query it live*. User requirement: arbitrary SQL allowed, **but only SELECT / read shape** — LLM generates queries to filter rows, project columns, join, aggregate. No INSERT/UPDATE/DELETE/DDL.

Safety must be defense-in-depth: skill instruction alone is not enough (LLM can be wrong). DB-level role permissions are authoritative.

## Decision: build a small custom remote MCP server (not reuse stdio `postgres-mcp`)

The distribution model (Part 4) requires friends to connect to **a remote MCP server over HTTP**, not a local stdio binary. Stdio MCPs don't work for Claude Desktop's Custom Connector flow — connectors expect a URL.

So the MCP becomes a small Python service exposing the **Streamable HTTP MCP transport**, hosted on this same server, with these properties:

- ✅ Only read-shaped tools in the tool surface (mutation tools hidden, not just role-rejected)
- ✅ Bearer-token auth at the HTTP layer (friends each get a token)
- ✅ SQL parser guard (reject anything but SELECT/WITH/EXPLAIN before sending to Postgres)
- ✅ Postgres connection uses the `secforms_ro` role (defense-in-depth — even if guards fail, DB rejects writes)
- ✅ Deployed via Coolify on this server, TLS terminated by existing `coolify-proxy` (Traefik)
- ✅ Public URL e.g. `https://secforms-mcp.<your-domain>/mcp`

The previously-suggested `postgres-mcp` binary is retained as a **local dev fallback only** (registered in `~/.claude.json` for the maintainer's local testing).

## Architecture

```
                 ┌──────────────────────────────────────────────────────────┐
                 │                       This server                         │
                 │                                                           │
┌──────────────┐ │  ┌──────────────┐   ┌─────────────────┐   ┌────────────┐ │
│ Friend's     │ │  │ Traefik /    │   │ secforms-mcp    │   │ sec-       │ │
│ Claude       │─┼─▶│ coolify-proxy│──▶│ (Python, FastMCP│──▶│ postgres   │ │
│ Desktop      │ │  │ TLS + routing│   │ Streamable HTTP)│   │ container  │ │
│ (Custom      │ │  │              │   │ bearer auth     │   │ role:      │ │
│  Connector   │ │  └──────────────┘   │ SQL guard       │   │ secforms_ro│ │
│  URL+token)  │ │                     └─────────────────┘   └────────────┘ │
└──────────────┘ │                                                           │
                 └──────────────────────────────────────────────────────────┘
```

## DB-side setup (one-time, idempotent SQL)

Create a dedicated read-only role:

```sql
-- Role with login + read-only profile
CREATE ROLE secforms_ro LOGIN PASSWORD '<generated-strong-password>'
  CONNECTION LIMIT 10;

-- Strip default privileges granted to PUBLIC
REVOKE ALL ON DATABASE secforms FROM secforms_ro;
GRANT CONNECT ON DATABASE secforms TO secforms_ro;

-- Schema usage
GRANT USAGE ON SCHEMA public TO secforms_ro;

-- SELECT on all existing tables in public
GRANT SELECT ON ALL TABLES IN SCHEMA public TO secforms_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO secforms_ro;

-- SELECT on tables created in the future (so migrations don't break the MCP)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO secforms_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO secforms_ro;

-- Per-role guardrails
ALTER ROLE secforms_ro SET default_transaction_read_only = on;
ALTER ROLE secforms_ro SET statement_timeout = '15s';
ALTER ROLE secforms_ro SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE secforms_ro SET lock_timeout = '5s';
ALTER ROLE secforms_ro SET search_path = public;
```

Verification queries (must pass before MCP registration):
- `SELECT 1` as `secforms_ro` → succeeds
- `INSERT INTO companies (company_cik) VALUES ('test')` as `secforms_ro` → `permission denied` ✓
- `CREATE TABLE x (id int)` as `secforms_ro` → `permission denied` ✓
- `SELECT * FROM signals LIMIT 5` → returns rows ✓

Setup script will live at `/root/.claude/capital-markets-toolbox/mcp/secforms-ro/setup/01_create_role.sql`.

## Local dev registration (maintainer only — not for distribution)

For local development on this server, the maintainer can also register the local `postgres-mcp` binary in `~/.claude.json` for direct stdio access while iterating. This is **not** what friends use:

```json
"secforms-ro-local": {
  "type": "stdio",
  "command": "postgres-mcp",
  "args": [
    "--connection-string",
    "postgresql://secforms_ro:<urlencoded-password>@127.0.0.1:54324/secforms"
  ],
  "env": {}
}
```

Friends use the public HTTPS URL (Part 3), not stdio.

## Tool surface exposed by the remote MCP

Custom, narrow surface — only what the skill needs. Mutation tools are not even defined.

| Tool | Use case |
|---|---|
| `query(sql, params=[], limit=100)` | Run SELECT/WITH/EXPLAIN. Validated by SQL guard before hitting DB. Returns rows + column types. |
| `list_tables(schema='public')` | All tables in the schema. |
| `describe_table(name, schema='public')` | Columns, types, nullability, defaults, PK, FK targets. |
| `list_foreign_keys()` | Full FK graph in one call (skill uses this for join discovery). |
| `count(table, where=None, params=[])` | `SELECT COUNT(*)` shortcut. |
| `explain(sql, params=[])` | `EXPLAIN ANALYZE` for query plan inspection. |
| `schema_summary()` | One-shot dump: tables + column counts + FK count. For "what's in this DB?" questions. |

No `insert`, `update`, `delete`, `alter`, `drop`, `truncate`, `grant`, `revoke`, `create`, `vacuum`, `copy`. Not in the tool list at all.

## SQL guard (in the MCP service)

Every `query()` / `explain()` SQL string is parsed before execution:

- Parse with `pglast` (Postgres-native parser). Reject if parse fails.
- Walk AST: only allow `SELECT`, `WITH ... SELECT`, `EXPLAIN ... SELECT`.
- Reject any statement containing `INTO`, `FOR UPDATE`, `FOR SHARE`, set-returning DDL functions, or multi-statement `;`-separated queries.
- Reject if any `pg_*` write function appears in the call graph (e.g. `pg_terminate_backend`).
- Enforce `LIMIT` cap (default 100, max 10000).

If guard rejects → return a structured error so the LLM can fix the query, not retry blindly.

## Skill integration

Update `SKILL.md` decision tree to add a "live query" branch:

```
"I need to actually run a query, not just read the docs"
  → use mcp__secforms-db__query (the remote MCP exposed as connector "secforms-db")
  → write only SELECT / WITH / EXPLAIN
  → start with LIMIT 100 unless user asks otherwise
  → use `list_foreign_keys` first if unsure how two tables join
  → no mutation tools exist on this MCP — don't try
```

Tool-name namespacing: when Claude Desktop adds the custom connector with name `secforms-db`, tools surface as `mcp__secforms-db__query`, `mcp__secforms-db__list_tables`, etc. The skill must reference these exact ids.

Add `reference/mcp-usage.md` to the skill: how to call each tool (parameter shape, limit semantics, error responses from the SQL guard), with 5–6 ready examples that the LLM can pattern-match against.

The skill's existing `query-recipes.md` recipes become directly runnable via this MCP — verification of the skill is now executable through the MCP itself.

## Repo layout for the MCP (drafts; final shape ships in the GitHub repo — see Part 4)

```
/root/.claude/capital-markets-toolbox/mcp/secforms-db/
├── README.md                       # what this MCP is, why read-only
├── pyproject.toml                  # uv/pip project, deps: mcp[cli], fastmcp, psycopg[binary], pglast, pydantic
├── src/secforms_mcp/
│   ├── __init__.py
│   ├── server.py                   # FastMCP app, tool definitions, auth middleware
│   ├── db.py                       # asyncpg/psycopg pool, statement_timeout enforcement
│   ├── guard.py                    # pglast-based SELECT-only validator
│   ├── tools/
│   │   ├── query.py                # query / count / explain
│   │   └── schema.py               # list_tables / describe_table / list_foreign_keys / schema_summary
│   └── config.py                   # env-driven config (PG_DSN, BEARER_TOKENS, ALLOWED_SCHEMAS)
├── tests/
│   ├── test_guard.py               # ~30 cases: SELECT/CTE/EXPLAIN accepted; INSERT/UPDATE/DROP/COPY/multi-stmt rejected
│   ├── test_tools.py               # tool integration tests against a temp Postgres
│   └── test_auth.py                # bearer token enforcement
├── Dockerfile                      # python:3.12-slim + uv install + runs uvicorn
├── docker-compose.yml              # for local dev (links to existing sec-postgres network)
├── coolify/
│   └── deploy-notes.md             # how to deploy via Coolify (build pack, env vars, domain, healthcheck)
├── setup/                          # DB-side setup (unchanged from earlier in Part 2)
│   ├── 01_create_role.sql
│   ├── 02_verify.sql
│   └── apply.sh                    # runs 01 + 02 against sec-postgres
└── docs/
    ├── tool-surface.md             # what tools exist, parameter shapes, examples
    ├── threat-model.md             # what's allowed / blocked / why
    └── operating.md                # rotating tokens, reading logs, restarting service
```

All MCP source lives under `capital-markets-toolbox/` per user instruction. Public GitHub repo is structured the same way (Part 4).

## Part 2 build steps (DB role + MCP service code)

1. `mkdir -p /root/.claude/capital-markets-toolbox/mcp/secforms-db/{src/secforms_mcp/tools,tests,setup,coolify,docs}`
2. Write `setup/01_create_role.sql`, `setup/02_verify.sql`, `setup/apply.sh`
3. Run `apply.sh` → creates `secforms_ro` role; verify all positive + negative checks pass
4. Write `pyproject.toml` (deps pinned)
5. Write `src/secforms_mcp/guard.py` + `tests/test_guard.py` first (TDD — guard is the critical safety boundary)
6. Write `src/secforms_mcp/db.py` (asyncpg pool, statement_timeout)
7. Write `src/secforms_mcp/tools/{query,schema}.py`
8. Write `src/secforms_mcp/server.py` (FastMCP app, bearer auth middleware, mount Streamable HTTP at `/mcp`, health at `/healthz`)
9. Write `Dockerfile` + `docker-compose.yml` for local run
10. Run locally: `docker compose up` → smoke-test via `mcp inspect http://localhost:8000/mcp -H "Authorization: Bearer dev"`
11. Run all guard tests + tool tests → green

## Verification (Part 2)

1. **Role isolation**: as `secforms_ro` → `SELECT` ok; `INSERT`/`UPDATE`/`DELETE`/`CREATE`/`DROP`/`TRUNCATE` all `permission denied`
2. **Guard rejects**: writes (`INSERT INTO ...`), DDL (`CREATE TABLE`), multi-statement (`SELECT 1; DROP TABLE x`), `COPY`, `pg_terminate_backend(...)` — all rejected before reaching DB, with a structured error
3. **Guard accepts**: SELECT, SELECT with CTE, EXPLAIN ANALYZE SELECT, nested subqueries
4. **Timeouts**: `SELECT pg_sleep(30)` aborts at 15s (`statement_timeout`)
5. **Auth**: request without bearer → 401; bad bearer → 401; good bearer → 200
6. **Tool surface**: `mcp inspect` lists exactly the documented tools; no mutation/DDL tools present

---

# Part 3: Public hosting (this server, via Coolify)

## Context

Server already runs Coolify + Traefik (`coolify-proxy` container exposes 80/443 to the internet). New service piggybacks on this stack — no new infra to provision.

## Deployment

- **Service name in Coolify**: `secforms-mcp`
- **Source**: GitHub repo (Part 4), build pack = Dockerfile
- **Network**: attach to the same Docker network as `sec-postgres` so the MCP can reach `sec-postgres:5432` internally (not via published port 54324)
- **Environment variables** (set in Coolify, never committed):
  - `PG_DSN=postgresql://secforms_ro:<pw>@sec-postgres:5432/secforms?sslmode=disable` (internal network, no need for SSL)
  - `BEARER_TOKENS=<comma-separated tokens, one per friend>` (or single token for v1)
  - `ALLOWED_SCHEMAS=public`
  - `DEFAULT_LIMIT=100`
  - `MAX_LIMIT=10000`
  - `LOG_LEVEL=info`
- **Domain**: user picks a subdomain like `secforms-mcp.<your-domain>`. Coolify provisions Let's Encrypt cert via Traefik automatically. Public URL: `https://secforms-mcp.<your-domain>/mcp`
- **Healthcheck**: `GET /healthz` returns 200 if DB connection pool is alive
- **Resource limits**: 256 MB RAM, 0.5 CPU is plenty (read-only, low traffic)

## Auth model (v1)

- Single shared bearer token, or per-friend tokens in a comma-separated env var
- Tokens are opaque random 32-byte strings (base64)
- Token rotation = update env var in Coolify → restart service. Friends update their connector config.
- No OAuth in v1 (over-engineered for friends-only use). Document path to OAuth in `docs/operating.md` for v2.

## Observability

- Structured JSON logs to stdout (Coolify captures): request id, friend token id (hashed), SQL hash (not full SQL), rows returned, duration, guard verdict
- Don't log full SQL by default (could leak intent if logs are shared); flag `LOG_FULL_SQL=true` for debug

## Verification (Part 3)

1. `curl https://secforms-mcp.<your-domain>/healthz` → 200
2. `mcp inspect https://secforms-mcp.<your-domain>/mcp -H "Authorization: Bearer <token>"` → tool list matches Part 2's surface
3. From a different machine, run a sample `query` call → returns rows
4. Without auth header → 401
5. Pull Coolify logs → see structured request log per call, no full SQL leakage

---

# Part 4: Distribution (GitHub repo + Claude Desktop install for friends)

## Context

Friends need a one-page install path. Goal: under 5 minutes, no terminal, no JSON editing.

Two artifacts:
1. **MCP** → Custom Connector URL (paste into Claude Desktop)
2. **Skill** → uploadable zip (drag into Claude Desktop Skills UI)

## GitHub repo: `capital-markets-toolbox`

Public repo. Layout:

```
capital-markets-toolbox/
├── README.md                       # landing page: what this is, screenshots, install in 3 steps
├── INSTALL.md                      # detailed install walkthrough with screenshots
├── LICENSE                         # MIT (or chosen)
├── .github/
│   └── workflows/
│       ├── release.yml             # on tag push: build skill.zip, attach to GitHub Release
│       └── ci.yml                  # run MCP tests (guard, tools, auth)
├── skills/
│   └── secforms-db/                # the skill (from Part 1)
│       ├── SKILL.md
│       ├── reference/...
│       └── scripts/...
├── mcp/
│   └── secforms-db/                # the MCP service (from Part 2)
│       ├── README.md
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/...
│       ├── tests/...
│       └── setup/...
├── connector/
│   ├── manifest.json               # optional Anthropic-format connector manifest (forward-compatible)
│   └── icon.png                    # 256x256 brand icon shown in Claude Desktop
└── docs/
    ├── for-friends-install.md      # one-page user install (linked from README)
    ├── for-maintainers-deploy.md   # how the maintainer deploys + rotates tokens
    └── troubleshooting.md          # common errors and fixes
```

No secrets in repo. `.env.example` shows env var names with placeholders. `.gitignore` excludes `.env`, `*.pem`, `*.key`.

## What friends do (the 3-step install)

Documented in `README.md` and `INSTALL.md` with screenshots:

**Step 1 — Add the MCP as a Custom Connector**
1. Open Claude Desktop → **Settings → Connectors → Add Custom Connector**
2. Name: `secforms-db`
3. URL: `https://secforms-mcp.<your-domain>/mcp`
4. Auth: **Bearer Token** → paste the token the maintainer shared
5. Click **Add**. Connector should show "Connected" and list ~7 tools.

**Step 2 — Add the skill**
1. Download `secforms-db-skill.zip` from the GitHub Releases page (latest)
2. In Claude Desktop → **Settings → Skills → Upload Skill** (or drag the zip onto the window)
3. Skill `secforms-db` appears in the list. Toggle on.

**Step 3 — Test it**
1. Start a new chat in Claude Desktop
2. Ask: *"Using the secforms-db skill, show me 5 most recent Form 4 filings."*
3. Claude reads the skill, picks `mcp__secforms-db__query`, runs SELECT, returns rows.

If steps fail → `docs/troubleshooting.md` covers: bad token (401), wrong URL, skill not visible, connector won't connect, "permission denied" (means tried a write — expected).

## Release process (automated)

On `git tag v0.1.0 && git push --tags`:

1. `.github/workflows/release.yml` runs:
   - Bundles `skills/secforms-db/` into `secforms-db-skill.zip`
   - Builds and pushes Docker image `ghcr.io/<user>/secforms-mcp:v0.1.0` (Coolify can pull from GHCR)
   - Creates a GitHub Release with the zip attached + auto-generated changelog
2. Coolify auto-deploys the new image (via webhook from GHCR)
3. Friends pull the new zip from Releases when notified

## What the user (maintainer) does once, before sharing

1. Push repo to GitHub (public)
2. Pick a subdomain, point DNS A record to this server
3. In Coolify: create service from GitHub repo, set env vars (PG_DSN, BEARER_TOKENS, etc.), set domain, deploy
4. Generate first bearer token: `openssl rand -base64 32`; add to `BEARER_TOKENS` env var
5. Tag v0.1.0; let GitHub Actions build the skill zip
6. Send each friend: (a) public URL, (b) their bearer token, (c) link to README

## Verification (Part 4)

1. **Repo is clean**: clone repo to a fresh dir → no secrets, no `.env`, no DB dump files
2. **Skill zip installs**: download `secforms-db-skill.zip` from a Release, upload to Claude Desktop on a second machine, skill appears in Skills list
3. **Connector flow works on a second machine**: paste URL + bearer token, connector shows "Connected", `query` tool is callable
4. **End-to-end test from a friend's machine**: ask Claude in Desktop "List 5 recent Form 4 filings via secforms-db" → returns rows
5. **README screenshots match current Claude Desktop UI** (re-shoot if UI changed since recording)
6. **CI green**: tests for guard, tools, auth pass on every push
7. **No write path**: attempt `INSERT` via the connector from a friend's machine → guard rejects with structured error; even if guard bypassed, DB role rejects

---

# Combined execution order (Parts 1–4)

1. **Part 2 setup steps 1–3** — create `secforms_ro` role, verify role isolation
2. **Part 2 build steps 4–11** — build the MCP service locally (guard first, then tools, then server), get local smoke test green
3. **Part 3** — deploy to Coolify behind public domain with TLS; verify remote tool calls work end-to-end
4. **Part 1** — build the skill (all reference files), with `SKILL.md` decision tree referencing the now-locked tool names `mcp__secforms-db__query` etc.
5. **Part 4** — push to GitHub, tag v0.1.0, verify release artifacts, do dry-run install on a second machine
6. **Hand off** — send URL + token + README link to first friend, observe install, fix friction

## Critical files (full list, all under `/root/.claude/capital-markets-toolbox/` then mirrored to public GitHub repo)

**Skill (Part 1):**
- `skills/secforms-db/SKILL.md`
- `skills/secforms-db/reference/{overview,erd,identifiers,schema,form-tables,query-recipes,query-advisor,mcp-usage}.md`
- `skills/secforms-db/reference/{schema.sql,schema.dbml}`
- `skills/secforms-db/scripts/refresh-schema.sh`

**MCP service (Part 2):**
- `mcp/secforms-db/{README.md,Dockerfile,docker-compose.yml,pyproject.toml}`
- `mcp/secforms-db/src/secforms_mcp/{__init__.py,server.py,db.py,guard.py,config.py}`
- `mcp/secforms-db/src/secforms_mcp/tools/{query.py,schema.py}`
- `mcp/secforms-db/tests/{test_guard.py,test_tools.py,test_auth.py}`
- `mcp/secforms-db/setup/{01_create_role.sql,02_verify.sql,apply.sh}`
- `mcp/secforms-db/coolify/deploy-notes.md`
- `mcp/secforms-db/docs/{tool-surface.md,threat-model.md,operating.md}`

**Distribution (Part 4):**
- `README.md` (repo landing, 3-step install with screenshots)
- `INSTALL.md` (long walkthrough)
- `LICENSE`
- `.gitignore`, `.env.example`
- `.github/workflows/{release.yml,ci.yml}`
- `connector/{manifest.json,icon.png}`
- `docs/{for-friends-install.md,for-maintainers-deploy.md,troubleshooting.md}`

**Touched on this server (not in repo):**
- `~/.claude.json` — optional dev-only `secforms-ro-local` stdio entry for maintainer testing (backed up before edit)
- Coolify service config — env vars and domain set via Coolify UI, not files
