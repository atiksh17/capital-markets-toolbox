# Coolify deployment notes

This server runs Coolify + Traefik (`coolify-proxy`). Deploy `secforms-mcp` alongside.

Current production deploy actually uses **plain `docker compose -f docker-compose.prod.yml up -d`** with Traefik labels on the container — bypasses the Coolify UI but uses the same Traefik instance for TLS. Both approaches valid.

## Prerequisites

- DNS A record: `mcp.nubeam.io → 167.86.113.172` (already set)
- Postgres role `secforms_ro` exists (`setup/apply.sh`)
- One invite code per friend + one root code (`openssl rand -base64 32`)
- JWT secret (`openssl rand -base64 48`)

## Path A — via docker compose with Traefik labels (current production)

```bash
cd mcp/secforms-db
# fill in .env.prod (see env vars below)
docker compose -f docker-compose.prod.yml up -d --build
```

Container labels register routes on coolify-proxy Traefik. Let's Encrypt issues the cert on first HTTPS hit.

## Path B — via Coolify UI

1. New Resource → Public Repository → paste GitHub URL → branch `main`
2. Build Pack: Dockerfile → path `mcp/secforms-db/Dockerfile` → build context `mcp/secforms-db`
3. Domains → `https://mcp.nubeam.io` → enable HTTPS
4. Network → attach to `supabase-slim_sec-internal` (where `sec-postgres` lives)
5. Environment Variables (see below)
6. Healthcheck: Coolify reads Dockerfile `HEALTHCHECK` (`GET /healthz`)
7. Resources: 256 MB RAM, 0.5 CPU
8. Deploy

## Environment variables (both paths)

```
PG_DSN=postgresql://secforms_ro:<urlencoded-pw>@sec-postgres:5432/secforms?sslmode=disable
TOKENS_JSON=[{"name":"root","token":"...","ip_allow":["127.0.0.0/8","::1/128","10.0.0.0/8","fd9b:3329:2bf7::/64","167.86.113.172/32"]},{"name":"<friend1>","token":"..."},{"name":"<friend2>","token":"..."}]
ALLOWED_SCHEMAS=public
DEFAULT_LIMIT=100
MAX_LIMIT=10000
LOG_LEVEL=info
PUBLIC_BASE_URL=https://mcp.nubeam.io
JWT_SECRET=<openssl rand -base64 48>
JWT_ISSUER=https://mcp.nubeam.io
JWT_AUDIENCE=https://mcp.nubeam.io/mcp
ACCESS_TOKEN_TTL_SECONDS=86400
AUTH_CODE_TTL_SECONDS=120
```

## Verify

```bash
curl https://mcp.nubeam.io/healthz
# → {"status":"ok"}

curl https://mcp.nubeam.io/.well-known/oauth-protected-resource | jq
curl https://mcp.nubeam.io/.well-known/oauth-authorization-server | jq

# direct static-bearer smoke test (server-side)
curl -X POST https://mcp.nubeam.io/mcp \
  -H "Authorization: Bearer <invite-code>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
```

Friends connect via Claude Desktop (OAuth flow), not curl.

## Reading logs

```bash
docker logs -f secforms-mcp
```

One JSON line per request:

```json
{"ts":"...", "level":"INFO", "msg":{"request_id":"<uuid>","token_id":"<sha256[:12]>","name":"atiksh","client_ip":"73.x.x.x","method":"POST","path":"/mcp","status":200}}
```

`name` is the friend's identity (from JWT `invite_name` claim or static token lookup). `client_ip` is from `X-Forwarded-For`. Use for attribution.

Set `LOG_FULL_SQL=true` only for short debug windows.
