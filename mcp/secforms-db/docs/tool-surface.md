# Tool surface

The MCP exposes exactly these 7 tools. Mutation tools do not exist.

| Tool | Signature |
|---|---|
| `query` | `(sql: str, params?: list, limit?: int) -> {rows, row_count, columns, truncated, limit}` |
| `count` | `(table: str, where?: str, params?: list) -> {count}` |
| `explain` | `(sql: str, params?: list) -> {plan}` |
| `list_tables` | `(schema: str = "public") -> {schema, tables}` |
| `describe_table` | `(name: str, schema: str = "public") -> {schema, name, columns, primary_key, foreign_keys}` |
| `list_foreign_keys` | `() -> {edges}` |
| `schema_summary` | `() -> {schemas, table_count, foreign_key_count, tables}` |

Full client-facing usage examples live in [`skills/secforms-db/reference/mcp-usage.md`](../../../skills/secforms-db/reference/mcp-usage.md).

## SQL guard rejections

| Pattern | Result |
|---|---|
| `INSERT / UPDATE / DELETE / MERGE` | rejected — "Disallowed statement node …" |
| `CREATE / ALTER / DROP / TRUNCATE` | rejected |
| `GRANT / REVOKE / COPY / VACUUM / REINDEX` | rejected |
| `SELECT 1; SELECT 2` (multi) | rejected — "Multi-statement SQL is not allowed" |
| `SELECT ... FOR UPDATE / FOR SHARE` | rejected |
| `SELECT 1 INTO temp FROM ...` | rejected — "SELECT INTO is not allowed" |
| `EXPLAIN ANALYZE SELECT ...` | rejected — ANALYZE executes the query |
| `EXPLAIN UPDATE ...` | rejected — non-SELECT EXPLAIN |
| `SELECT pg_terminate_backend(...)` | rejected — write function |
| `SELECT set_config(...)` | rejected — write function |
| Garbage text | rejected — "SQL parse error" |

## Postgres role rejections (defense in depth)

Even if the guard somehow accepted a write, the `secforms_ro` role rejects:

- `cannot execute INSERT in a read-only transaction`
- `permission denied for table ...` (if grant somehow lost)
- `permission denied for schema ...`

## Limits

| Knob | Default | Source |
|---|---|---|
| `DEFAULT_LIMIT` | 100 | env var, applied to `query` if SQL has no LIMIT |
| `MAX_LIMIT` | 10000 | env var, hard cap |
| `statement_timeout` | 15s | Postgres role setting |
| `lock_timeout` | 5s | Postgres role setting |
| `idle_in_transaction_session_timeout` | 30s | Postgres role setting |
| asyncpg pool min/max | 1 / 5 | code, in `db.py` |
| Role `CONNECTION LIMIT` | 10 | Postgres role |

## Schemas

`ALLOWED_SCHEMAS` (env var, default `public`) defines what the tools will reach. Tables outside the allowlist are invisible to `list_tables`, `describe_table`, and `count` (which validate the schema arg). `query` can technically reference any schema in its SQL, but the role's `search_path = public` makes unqualified refs default to public; cross-schema queries require explicit `other_schema.table` qualification AND that the role has USAGE on that schema (it doesn't, except for public).
