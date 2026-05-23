# MCP usage — `mcp__secforms-db__*` tools

The skill teaches schema. The MCP runs the actual queries. Once a user has added the **secforms-db** Custom Connector in Claude Desktop (server URL `https://mcp.nubeam.io/mcp`, OAuth via invite code), these tools are available:

| Tool | Purpose |
|---|---|
| `mcp__secforms-db__query` | Run a `SELECT` / `WITH SELECT` / `EXPLAIN SELECT`. **Primary tool.** |
| `mcp__secforms-db__count` | `SELECT COUNT(*)` shortcut for one table. |
| `mcp__secforms-db__explain` | `EXPLAIN (FORMAT JSON)`. No `ANALYZE`. |
| `mcp__secforms-db__list_tables` | Base tables in a schema. |
| `mcp__secforms-db__describe_table` | Columns + types + PK + FKs for one table. |
| `mcp__secforms-db__list_foreign_keys` | Every FK in the schema (join discovery). |
| `mcp__secforms-db__schema_summary` | Schemas + table count + FK count + per-table column count. |

There are **no mutation tools**. The MCP does not expose `insert` / `update` / `delete` / DDL. Don't ask for them — they aren't there.

## `query` — argument shape

```jsonc
{
  "sql": "SELECT s.accession, s.form_type FROM signals s WHERE s.form_type = $1 ORDER BY s.date_added DESC",
  "params": ["4"],
  "limit": 50
}
```

- `sql` (required) — exactly one statement. SELECT / WITH SELECT / EXPLAIN SELECT only.
- `params` (optional) — positional params for `$1, $2, ...` placeholders. **Always use placeholders for user input.** Don't string-interpolate.
- `limit` (optional) — row cap. Default 100, max 10000. Ignored if SQL already has its own `LIMIT`.

Response shape (success):

```json
{
  "rows": [ {...}, {...} ],
  "row_count": 50,
  "columns": ["accession", "form_type"],
  "truncated": true,
  "limit": 50
}
```

Response shape (rejection by SQL guard):

```json
{
  "error": "Statement type 'InsertStmt' is not allowed. Only SELECT / WITH SELECT / EXPLAIN SELECT are permitted.",
  "statement_kind": "InsertStmt"
}
```

If you see an `error` field, **don't retry blindly** — fix the SQL and call again.

## When to use which tool

| Question | Best tool |
|---|---|
| "Run this SELECT for me" | `query` |
| "How many rows in `signals`?" | `count` with `table="signals"` |
| "How many `signals` where form_type='4'?" | `count` with `table="signals"`, `where="form_type = $1"`, `params=["4"]` |
| "What's the query plan?" | `explain` |
| "What tables exist?" | `list_tables` |
| "What columns does X have?" | `describe_table` |
| "How does table A connect to table B?" | `list_foreign_keys` (filter the edges client-side) |
| "Give me a one-shot overview" | `schema_summary` |

## Examples

### Example 1 — recent Form 4 insider sales

```jsonc
{
  "name": "mcp__secforms-db__query",
  "arguments": {
    "sql": "SELECT s.accession, f.issuer_name, f.person_name, f.total_sale_usd, f.filing_date FROM signals s JOIN form_4 f ON f.accession = s.accession WHERE s.form_type = '4' AND f.filing_date >= now()::date - 7 ORDER BY f.total_sale_usd DESC NULLS LAST",
    "limit": 25
  }
}
```

### Example 2 — count unenriched CIKs

```jsonc
{
  "name": "mcp__secforms-db__count",
  "arguments": {
    "table": "cik_list",
    "where": "enriched = $1",
    "params": [false]
  }
}
```

### Example 3 — find FKs that touch `signals`

```jsonc
{
  "name": "mcp__secforms-db__list_foreign_keys",
  "arguments": {}
}
```

Filter the returned `edges` client-side for `from_table == 'signals'` or `to_table == 'signals'`.

### Example 4 — preview a plan before running a heavy query

```jsonc
{
  "name": "mcp__secforms-db__explain",
  "arguments": {
    "sql": "SELECT * FROM form_13f_hr WHERE period_of_report >= '2026-01-01'"
  }
}
```

## Limits, timeouts, errors you'll hit

| What | Behavior |
|---|---|
| Query > 15 seconds | Aborted by Postgres `statement_timeout`. Add a more selective WHERE or a smaller window. |
| Result > `limit` | Truncated at `limit`; `truncated: true` flag set. Pull the rest with offset/pagination or narrow filter. |
| `INSERT` / `UPDATE` / `DELETE` / `CREATE` / `DROP` / `TRUNCATE` | Rejected by SQL guard before hitting DB. Response has `error` field. |
| `EXPLAIN ANALYZE` | Rejected by SQL guard (it actually runs the query, which can have side effects on stats). Use `explain` (no ANALYZE) instead. |
| Multi-statement (`SELECT 1; SELECT 2`) | Rejected. Send one statement at a time. |
| Auth missing / wrong | HTTP 401 from the connector — surfaced as a connection error in Claude Desktop, not a tool response. |

## Don't

- Don't string-format user input into SQL — use `params`.
- Don't query `pg_*` system tables for write functions; the guard rejects `pg_terminate_backend`, `set_config`, etc.
- Don't expect tables outside `public` schema; the MCP only allows the schemas in its `ALLOWED_SCHEMAS` env var (defaults to `public`).
- Don't try to bypass the row limit by writing a huge UNION — narrow the filter instead.
