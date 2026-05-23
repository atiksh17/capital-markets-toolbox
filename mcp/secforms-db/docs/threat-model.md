# Threat model

Goal: friends can read everything in `secforms.public`. They cannot write, exfiltrate at unreasonable scale, or affect other databases.

## What the system protects against

| Attack | Defense |
|---|---|
| LLM accidentally writes (INSERT / UPDATE / DELETE) | (1) JWT scope is `read:database`, (2) no mutation tools defined on the MCP, (3) SQL guard rejects non-SELECT, (4) Postgres role lacks INSERT/UPDATE/DELETE grant, (5) `default_transaction_read_only = on`. |
| LLM tries a stealthy write (`SELECT INTO`, `pg_terminate_backend`, `set_config`, multi-statement) | SQL guard catches each. Even if it didn't, the role rejects. |
| Friend's JWT replayed from another machine | JWT bound to identity via `invite_name` claim. IP allowlist enforced per identity for sensitive accounts (root). Logs attribute every request to the named identity. JWTs expire in 24h. |
| Stolen invite code | Maintainer revokes by removing the entry from `TOKENS_JSON` + restart. Existing JWTs the attacker may have issued remain valid until 24h TTL or `JWT_SECRET` is rotated (nuking all sessions). |
| `JWT_SECRET` leakage | All issued JWTs become forgeable. Rotate `JWT_SECRET` immediately and force all friends to Reconnect. |
| Code-injection via auth flow | Auth codes are 32-byte URL-safe random, single-use, 120s TTL. PKCE S256 mandatory — even if redirect_uri is intercepted, attacker can't redeem the code without the verifier. |
| Token leakage via repo / logs | `.gitignore` blocks `.env*` and `TOKENS.local.md`. Logs hash bearer tokens (`sha256[:12]`); JWTs are not logged. |
| Long-running query exhausts DB | `statement_timeout = 15s`, `lock_timeout = 5s`, `idle_in_transaction_session_timeout = 30s`. Connection cap 10. Default LIMIT 100 / max 10000 on row output. |
| Reaching other databases on the host | Connection string in env hard-pins `secforms`. Role has no access to other DBs (Coolify network isolation keeps it on `supabase-slim_sec-internal`). |
| SQL injection from user-supplied params | The MCP passes `params` as positional parameters to asyncpg — never string-formatted into SQL. The guard validates the SQL string separately. |
| DoS via many concurrent connections | Asyncpg pool capped at 5 client-side; role `CONNECTION LIMIT = 10`. |
| Information leak via logs | Logs hash tokens. SQL is logged as a hash by default; `LOG_FULL_SQL=true` only for short debug windows. |
| Bypassing the MCP and hitting Postgres directly | Postgres is on `127.0.0.1:54324` (loopback) on the host. The role is read-only even if reached. |
| Future migrations create writeable tables for `secforms_ro` | `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT` — new tables only get SELECT. |

## What the system does NOT protect against

- A friend deliberately running an expensive aggregation. The 15s timeout + LIMIT caps the damage but won't stop a determined low-yield query loop. Watch logs.
- A friend exfiltrating data row by row over time. There's no rate limit per token (yet). Tolerable for friends-only use; add per-token quotas if user count grows.
- Anthropic-side prompt injection that tricks the LLM into running benign-but-leaky SELECTs. The DB role only sees what the LLM sends; can't inspect intent. Mitigation: skill nudges the LLM to use LIMIT 100 by default and to confirm before running.
- Theft of the maintainer's `sec_admin` superuser password. That's outside this MCP's blast radius — it would compromise the DB regardless.

## Key invariants

1. The MCP role `secforms_ro` has **only** SELECT and USAGE grants in `public`. Verify:
   ```sql
   SELECT * FROM information_schema.role_table_grants WHERE grantee = 'secforms_ro';
   ```
2. The MCP container's `PG_DSN` uses **only** the `secforms_ro` role, never the superuser.
3. `TOKENS_JSON` (or legacy `BEARER_TOKENS`) is non-empty in production. `JWT_SECRET` is non-empty for OAuth to work.
4. The Dockerfile bundles no secrets — env vars injected at runtime.
5. `.env.local`, `.env.prod`, `TOKENS.local.md` are git-ignored.
6. JWTs are validated for issuer + audience + signature on every request.
7. PKCE S256 is required; plain method is rejected.

## Incident playbook

- **Token leak** → rotate immediately (see `for-maintainers-deploy.md`).
- **Unexpected mutation appears in `secforms`** → not from the MCP. Check who else has DB credentials.
- **Suspicious traffic** → grep logs for the offending `token_id`; identify the friend; revoke.
- **MCP service down** → `coolify logs secforms-mcp`; restart from Coolify UI; if PG is down, fix that first.
