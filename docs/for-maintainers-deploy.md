# Maintainer runbook

Server already runs Coolify + Traefik (`coolify-proxy` exposes 80/443). `sec-postgres` hosts the `secforms` Postgres on `127.0.0.1:54324` (host) / `sec-postgres:5432` (Docker network `supabase-slim_sec-internal`).

Live: `https://mcp.nubeam.io/mcp` (Let's Encrypt via Traefik).

## One-time setup (already done)

1. **Read-only DB role**: see `mcp/secforms-db/setup/apply.sh`. Creates `secforms_ro` with SELECT-only grants + per-role guardrails (`statement_timeout = 15s`, `default_transaction_read_only = on`, ...). Run once as `sec_admin`.

2. **Generate invite codes**: one per friend, plus one root code.
   ```bash
   openssl rand -base64 32
   ```

3. **JWT signing secret**: 48-byte random for HS256.
   ```bash
   openssl rand -base64 48
   ```

4. **Env file** `mcp/secforms-db/.env.prod` (gitignored):
   ```
   PG_DSN=postgresql://secforms_ro:<urlencoded-pw>@sec-postgres:5432/secforms?sslmode=disable
   TOKENS_JSON=[{"name":"root","token":"...","ip_allow":["127.0.0.0/8","::1/128","10.0.0.0/8","fd9b:3329:2bf7::/64","167.86.113.172/32","2a02:c207:2329:2320::/64"]},{"name":"atiksh","token":"..."},{"name":"harsh","token":"..."},{"name":"harpreet","token":"..."},{"name":"remo","token":"..."}]
   ALLOWED_SCHEMAS=public
   DEFAULT_LIMIT=100
   MAX_LIMIT=10000
   LOG_LEVEL=info
   PUBLIC_BASE_URL=https://mcp.nubeam.io
   JWT_SECRET=<base64 48 bytes>
   JWT_ISSUER=https://mcp.nubeam.io
   JWT_AUDIENCE=https://mcp.nubeam.io/mcp
   ACCESS_TOKEN_TTL_SECONDS=86400
   AUTH_CODE_TTL_SECONDS=120
   ```

5. **Deploy** via docker compose (uses existing coolify-proxy Traefik for TLS + routing):
   ```bash
   cd mcp/secforms-db
   docker compose -f docker-compose.prod.yml up -d --build
   ```

   Container labels register routes on Traefik. Let's Encrypt issues the cert on first HTTPS hit if DNS resolves.

6. **DNS**: `mcp.nubeam.io` A record → `167.86.113.172` (already set).

## Verify

```bash
curl https://mcp.nubeam.io/healthz                                                                                                     # {"status":"ok"}
curl https://mcp.nubeam.io/.well-known/oauth-protected-resource | jq                                                                   # discovery
curl https://mcp.nubeam.io/.well-known/oauth-authorization-server | jq                                                                 # discovery
```

Walk the full PKCE flow (script in `mcp/secforms-db/scripts/oauth-smoke.sh` if you want repeatable verification).

## Routine ops

### Add a friend

1. Generate invite code: `openssl rand -base64 32`
2. Edit `.env.prod` → `TOKENS_JSON` → append `{"name":"<name>","token":"<code>"}`
3. Restart: `docker compose -f docker-compose.prod.yml up -d`
4. Send the friend their invite code + the URL `https://mcp.nubeam.io/mcp` + link to `INSTALL.md`

### Revoke a friend (or rotate one)

1. Edit `.env.prod` → `TOKENS_JSON` → remove the entry (or replace `"token"` with a new value)
2. Restart
3. Existing JWTs they hold remain valid until 24h TTL expires. To force-revoke immediately: rotate `JWT_SECRET` too — invalidates **all** tokens. Friends re-add the connector.

### Rotate JWT secret (nukes all sessions)

1. Generate new 48-byte secret
2. Update `JWT_SECRET` in `.env.prod`
3. Restart
4. Tell friends to **Reconnect** their connector in Claude Desktop (which redoes the OAuth flow)

### Read logs

```bash
docker logs -f secforms-mcp
```

One JSON line per request:

```json
{"ts":"...", "level":"INFO", "msg":{"request_id":"<uuid>","token_id":"<sha256[:12]>","name":"atiksh","client_ip":"73.x.x.x","method":"POST","path":"/mcp","status":200}}
```

`name` is the friend's identity from the OAuth/static token. `client_ip` is the originator (from `X-Forwarded-For`). Use for attribution and abuse detection.

### Re-snapshot the schema after a migration

```bash
cd skills/secforms-db
./scripts/refresh-schema.sh
git add reference/schema.sql reference/schema.md
git commit -m "refresh: schema snapshot"
git tag v0.X.Y
git push --tags
```

Cuts a new release with the regenerated skill zip.

### Restart the service

Coolify UI → Restart, or:

```bash
docker restart secforms-mcp
```

~3 seconds. In-flight OAuth codes lost (TTL 120s anyway); friends re-login as needed.

### Update the service

```bash
cd /root/.claude/capital-markets-toolbox/mcp/secforms-db
docker compose -f docker-compose.prod.yml up -d --build
```

Rebuilds the image, recreates the container, picks up new env.

## Never commit

- `.env.prod`, `.env.local`
- `TOKENS.local.md`
- `JWT_SECRET`
- Postgres superuser password

Audit before release: `git diff origin/main -- '*.env*' '*.json'`.

## Path to a managed OAuth provider (v2 — not now)

Currently the MCP IS the auth server (token-based "login" page). Friends-only scale, fine. If you grow to many users or want SSO:

- Put Authentik / Ory Hydra / Auth0 in front
- Replace `/oauth/*` endpoints with a thin reverse-proxy passthrough
- Keep JWT validation in the MCP (just swap to RS256 + JWKS from the provider)

Not v1 — over-engineered for the current set.
