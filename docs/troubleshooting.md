# Troubleshooting

## Connector won't connect

| Symptom | Likely cause | Fix |
|---|---|---|
| Add Custom Connector says "Discovery failed" or similar | URL wrong | Server URL is exactly `https://mcp.nubeam.io/mcp`. Trailing `/mcp`, no extra slash. |
| Browser opens, login page loads, but Authorize shows "Invite code not recognized" | Wrong code / extra whitespace | Re-paste the invite code carefully. If still failing, the maintainer may have rotated it — ask. |
| Browser opens then redirects back with `error=access_denied` | You closed the window or it timed out (codes expire in 2 min) | Re-add the connector and run the login again. |
| Browser doesn't open at all | Claude Desktop too old, or browser handler blocked | Update Claude Desktop. Try a different browser as default. |
| Settings shows the connector as "Connected" but tools fail with 401 in chat | Access token expired (24h TTL) | Click the connector → **Reconnect** to redo the login. |
| Settings shows connector errors mentioning IP | You are using the **root** invite code from outside the server | Use a per-friend invite code, not root. |
| `503 Service Unavailable` from healthcheck | Server down or DB unreachable | Wait a minute and retry. Ping the maintainer. |

## OAuth-specific

| Symptom | Fix |
|---|---|
| Login page won't load (`502`) | Server is restarting. Wait 10s, retry. |
| Token endpoint returns `invalid_grant` `PKCE failed` | Browser cancelled the auth flow midway. Restart from "Add Custom Connector". |
| Token endpoint returns `invalid_grant` `expired` | Auth code TTL is 120s — you took too long between paste and authorize. Try again. |

## Skill not appearing in chat

- Settings → Skills: confirm `secforms-db` is toggled **on**.
- Close + reopen the chat (skill list refreshes per chat).
- Mention `secforms`, `secforms-db`, or the database explicitly in your first message so Claude loads the skill.

## Skill loaded but Claude doesn't use the MCP

- Confirm connector is **Connected** in Settings → Connectors.
- Ask explicitly: *"Use the secforms-db MCP to run a query…"*
- If the question is purely about schema (no need to query), Claude may answer from the skill files alone — that's correct.

## Query returns `error: ... is not allowed`

The SQL guard rejected. Reasons:

| Fragment | Meaning |
|---|---|
| `Statement type 'InsertStmt'` etc | You sent a write. Rewrite as SELECT. |
| `Multi-statement SQL is not allowed` | One statement at a time. |
| `EXPLAIN ANALYZE is not allowed` | ANALYZE actually runs the query. Use plain `EXPLAIN` via the `explain` tool. |
| `SELECT ... FOR UPDATE` | Drop the FOR UPDATE clause. |
| `Function pg_terminate_backend() is not allowed` | Write-shaped function. Find an alternative. |
| `SQL parse error: ...` | Not valid Postgres SQL. Fix syntax. |

## Query times out at 15 seconds

DB has `statement_timeout = 15s` for the read-only role. Tighten:

- Add a date filter
- Narrow to one form_type
- Use smaller `LIMIT`
- Run `EXPLAIN` first to spot a missing index

## Rows truncated

`truncated: true` means you hit the `limit` cap (default 100, max 10000). Pass higher `limit`, paginate with `ORDER BY + LIMIT n OFFSET k`, or narrow filter.

## I want to write data

You can't. Read-only by design. If you need write access, that's a different MCP — talk to the maintainer.

## My invite code leaked

Tell the maintainer **immediately**. They rotate. Until then, traffic on your code is still read-only and rate-limited, but rotate anyway.
