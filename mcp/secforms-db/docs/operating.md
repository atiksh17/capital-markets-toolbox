# Operating the secforms-mcp service

## Reading logs

```
coolify logs secforms-mcp        # via Coolify UI is easier
# or:
docker logs -f $(docker ps -qf name=secforms-mcp)
```

One JSON line per HTTP request:

```json
{"ts":"2026-05-22 15:18:29,726","level":"INFO","msg":{"request_id":"<uuid>","token_id":"<sha256[:12]>","method":"POST","path":"/mcp","status":200}}
```

To find traffic by friend, grep for their token_id (precompute it once: `echo -n "<token>" | sha256sum | cut -c1-12`).

## Rotating an invite code

1. Generate new code: `openssl rand -base64 32`
2. Edit `.env.prod` → `TOKENS_JSON` → replace the friend's token value (keep `name` the same)
3. Restart the service
4. Send the new code to the friend; they click their connector → **Reconnect** → re-enter the new code on the login page

Old JWTs they hold remain valid until 24h TTL expires. To force-cut earlier: rotate `JWT_SECRET` (see below) — nukes all sessions.

## Rotating JWT_SECRET (invalidates all sessions)

1. Generate new 48-byte secret: `openssl rand -base64 48`
2. Update `JWT_SECRET` in `.env.prod`
3. Restart
4. Tell all friends to Reconnect their connector

## Restarting the service

Coolify → Service → Restart. Or:

```bash
docker restart $(docker ps -qf name=secforms-mcp)
```

Restart takes ~3 seconds. No active sessions are preserved (MCP sessions are per-request anyway for stateless tool calls).

## Adding a friend

1. Generate invite code: `openssl rand -base64 32`
2. Edit `.env.prod` → `TOKENS_JSON` → append `{"name":"<friend>","token":"<code>"}`
3. Restart
4. Send the friend their invite code + the URL `https://mcp.nubeam.io/mcp` + a link to `INSTALL.md`

Each friend gets their own code so revocation is granular.

## Upgrading the service

1. Push commits to `main`
2. Tag `vX.Y.Z` and push the tag — release.yml builds + pushes `ghcr.io/<owner>/secforms-mcp:X.Y.Z`
3. Coolify (if configured with webhook) auto-pulls + redeploys

If you only changed the skill, no service redeploy needed — re-cut a release and friends re-upload the new skill zip.

## Backing up env

The only state in this service is the env vars (token list, DSN). Back them up periodically:

```bash
coolify env export secforms-mcp > /root/backups/secforms-mcp-env-$(date +%F).txt
chmod 600 /root/backups/secforms-mcp-env-*.txt
```

(Or copy from the Coolify UI to a password manager.)

## Path to a managed OAuth provider (v2)

The MCP currently is the auth server (token-based login page). Works for friends-only. If audience widens:

- Front the service with Authentik / Ory Hydra / Auth0
- Strip the local `/oauth/*` endpoints, replace with a reverse-proxy passthrough
- Switch JWT validation to RS256 + JWKS fetch from the provider
- Add per-user scopes (`read:database`, `read:schema_only`) and per-user quotas

Over-engineered for current scale.

## Path to per-user row limits or column-level redaction

Roll forward when needed:

- Tag each token with a tier (`free`, `power`) and read tier from a side store (Redis)
- Adjust `DEFAULT_LIMIT` / `MAX_LIMIT` per tier in middleware
- For column-level redaction, wrap `query` to drop columns from the response based on tier

Don't build until a friend asks.
