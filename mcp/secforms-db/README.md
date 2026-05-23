# secforms-mcp

Read-only Model Context Protocol server for the **secforms** Postgres database (SEC EDGAR filings). Speaks **Streamable HTTP** with **OAuth 2.1 (PKCE)** + static-bearer fallback for server-side scripts.

Live at `https://mcp.nubeam.io/mcp`.

## What it does

Exposes 7 tools that let an LLM understand and query the database without ever writing to it:

- `query(sql, params=[], limit=100)` — `SELECT` / `WITH SELECT` / `EXPLAIN SELECT`
- `count(table, where?, params?)` — `SELECT COUNT(*)` shortcut
- `explain(sql, params?)` — `EXPLAIN (FORMAT JSON)` (no `ANALYZE`)
- `list_tables(schema='public')` — base tables
- `describe_table(name, schema?)` — columns, types, PK, FKs
- `list_foreign_keys()` — every FK edge (join discovery)
- `schema_summary()` — schemas + table count + FK count + column counts

## Auth model

Two paths, both end in a Bearer header on each MCP call:

| Path | Used by | How |
|---|---|---|
| **OAuth 2.1 PKCE** | Claude Desktop friends | Add Custom Connector → browser → login page → paste invite code → JWT (24h TTL) auto-issued. |
| **Static bearer** | Server-side scripts / cron / curl | Send `Authorization: Bearer <invite-code>` directly. Root code is IP-restricted to this server. |

Both paths converge on the same identity model: each friend has a labeled entry in `TOKENS_JSON` (name + optional ip_allow). Logs attribute every request to the friend's name.

## OAuth endpoints

| Endpoint | Purpose |
|---|---|
| `GET /.well-known/oauth-protected-resource` | RFC 9728 — points discoverers at the auth server |
| `GET /.well-known/oauth-authorization-server` | RFC 8414 — auth endpoints + supported flows |
| `POST /oauth/register` | RFC 7591 — Dynamic Client Registration (returns synthetic `client_id`) |
| `GET /oauth/authorize` | Renders the invite-code login form |
| `POST /oauth/authorize` | Validates invite, redirects with auth code |
| `POST /oauth/token` | Exchanges auth code + PKCE verifier for a 24h JWT |

Issued JWT is HS256, signed with `JWT_SECRET`. Validated on every MCP call.

## Safety — four independent layers

1. **OAuth scope** — JWTs are scoped `read:database`. No write scopes defined.
2. **No mutation tools** on the MCP. `insert`/`update`/`delete`/DDL don't exist.
3. **SQL guard** (`pglast`) — every SQL string parsed and rejected unless it is exactly one `SELECT` / `WITH SELECT` / `EXPLAIN SELECT`. Multi-statements, `FOR UPDATE`, `SELECT INTO`, write functions, `EXPLAIN ANALYZE` — all rejected.
4. **Postgres role** — `secforms_ro` has only `SELECT` + `USAGE` grants and `default_transaction_read_only = on`. Any write that slipped through still gets `cannot execute X in a read-only transaction`.

Additional guardrails: `statement_timeout = 15s`, `idle_in_transaction_session_timeout = 30s`, `lock_timeout = 5s`, role `CONNECTION LIMIT = 10`.

## Run locally

```bash
cd mcp/secforms-db
cp .env.example .env.local                                                                                                              # fill in PG_DSN, JWT_SECRET, TOKENS_JSON
docker compose up --build
```

Server: `http://127.0.0.1:8088/mcp`.

Smoke test:
```bash
curl http://127.0.0.1:8088/healthz
curl http://127.0.0.1:8088/.well-known/oauth-protected-resource
curl -H "Authorization: Bearer <invite-code>" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
     http://127.0.0.1:8088/mcp
```

## Deploy

See [`coolify/deploy-notes.md`](coolify/deploy-notes.md) and [`docs/operating.md`](docs/operating.md).

## Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

`test_guard.py` covers ~30 SQL patterns (accept + reject). `test_auth.py` covers bearer enforcement.
