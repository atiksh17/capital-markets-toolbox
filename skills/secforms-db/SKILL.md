---
name: secforms-db
description: Expert knowledge of the secforms Postgres database — 35 tables covering SEC EDGAR filings, CIK entities (companies + people), 27 per-form payload tables, and the signals/junction layer that ties them together. Use whenever the user asks about any secforms table, column, join, filing form, CIK, accession, or how to query SEC filings data. Activates the query-advisor sub-mode when the user's request is vague ("help me find people who…", "what kind of companies can I look for"). Pairs with the mcp__secforms-db__* tools for live read-only queries.
---

# secforms-db

A Postgres database of SEC EDGAR filings, normalized into 27 per-form tables and indexed by CIK so any company or person on any tracked filing becomes a queryable, enriched entity. Used for capital-markets sales intelligence.

## The 4 layers

```
LAYER 0  forms                                  registry (27 form types, allocator/seeker tag)
LAYER 1  signals · signal_ciks · form_<27>      one row per filing + payload + every CIK
LAYER 2  cik_list · companies · people          deduped CIK registry + enriched profiles
LAYER 3  company_filings · people_filings       per-entity 3-yr filing history
```

## Key identifiers

- **`CIK`** — 10-digit zero-padded text (`"0000320193"`). Always text, never numeric.
- **`accession`** — SEC filing PK like `"0001-24-000001"`. Globally unique per filing.
- **`cik_role`** — one of `filer_cik | issuer_cik | company_cik | person_cik | intermediary_cik | reg_cik`. Lives on `signal_ciks`.
- **`signal_side`** — `allocator` (capital deployer) or `seeker` (capital raiser). Lives on `forms`.

## Decision tree — which reference file to read

| The user is asking… | Open |
|---|---|
| What does table/column X mean? | `reference/schema.md` |
| How are tables connected? Show me the diagram. | `reference/erd.md` |
| What does `form_<X>` capture? Why is it filed? | `reference/form-tables.md` |
| How do I write a query joining A → B? Give me an example. | `reference/query-recipes.md` |
| What's the exact DDL / column types? | `reference/schema.sql` (verbatim DDL) or `reference/schema.dbml` |
| What is a CIK / accession / cik_role? Person vs company? | `reference/identifiers.md` |
| **Their request is vague** — "help me find people who…", "what can you show me?", "I want to find companies that…" | `reference/query-advisor.md` (enter advisor mode: clarify → propose options → refine → confirm → run) |
| Their request is concrete and they want results | `reference/mcp-usage.md` → call `mcp__secforms-db__query` |

## Live-query tools (from the secforms-db MCP connector)

If the user has added the **secforms-db** Custom Connector in Claude Desktop (OAuth flow with invite code, server `https://mcp.nubeam.io/mcp`), these tools are callable:

```
mcp__secforms-db__query              — SELECT / WITH / EXPLAIN
mcp__secforms-db__count              — SELECT COUNT(*) shortcut
mcp__secforms-db__explain            — EXPLAIN (FORMAT JSON), no ANALYZE
mcp__secforms-db__list_tables        — base tables in a schema
mcp__secforms-db__describe_table     — columns + types + PK + FKs for one table
mcp__secforms-db__list_foreign_keys  — every FK edge
mcp__secforms-db__schema_summary     — schemas + table count + FK count
```

The MCP is **read-only by design**: no mutation tools exist, OAuth tokens are scoped `read:database`, and the underlying Postgres role can only SELECT. Don't attempt INSERT/UPDATE/DELETE/DDL — they will fail at the guard layer (and again at the role layer). See `reference/mcp-usage.md` for argument shapes + examples.

## Default behavior

- Always use placeholders (`$1, $2, …`) for user-supplied values when calling `query`. Never string-interpolate.
- Default `LIMIT 100` for `query` unless the user asks otherwise.
- For vague intents, **do not** dump a SQL query — enter advisor mode (`reference/query-advisor.md`) and propose options first.
- Before writing the final SELECT, run the **two-tier field picker** from `reference/query-advisor.md` §3.5 — Tier A = entity columns (companies / people / cik_list), Tier B = signal/form columns (per the form table involved). Use `AskUserQuestion` with `multiSelect: true` and offer a `Preset` bundle as the first option so the user can one-click or hand-pick. Skip Tier B if no per-filing detail is needed.
- For form-type → table-name lookups, the rule is: lowercase, replace ` ` and `-` with `_`, prefix `form_`. So `'13F-HR'` → `form_13f_hr`. Full map in `reference/query-recipes.md`.
- Treat `companies` and `people` as XOR: a CIK is in one or the other, never both. The XOR is app-enforced, not DB-enforced.
- `signals` / `signal_ciks` is the live filings stream. `company_filings` / `people_filings` is per-entity history from a *separate* SEC API path. They overlap but are not derived from each other.

## Connection

- **Friends** add the MCP via Claude Desktop → Settings → Connectors → Add Custom Connector with server URL `https://mcp.nubeam.io/mcp`. OAuth flow prompts for an invite code. Access token TTL: 24 hours, auto-renewed via Reconnect.
- **Maintainer** can also call the MCP directly with a static invite code as bearer (server-side only — root invite is IP-restricted to this server). DB lives at `127.0.0.1:54324`, container `sec-postgres`. To re-snapshot the schema after migrations, run `scripts/refresh-schema.sh`.
