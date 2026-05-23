# capital-markets-toolbox

A **Claude skill** + a **read-only OAuth-authenticated MCP connector** for the `secforms` Postgres database (27 SEC EDGAR form types, enriched companies + people, signals layer).

Two things friends install in **Claude Desktop**:

1. **secforms-db MCP** — a hosted Custom Connector. Add once by URL. Logs in via your invite code.
2. **secforms-db skill** — a zip uploaded to Claude's Skills UI. Teaches Claude the database so it picks the right SQL and joins.

Together: ask Claude *"find me insiders at companies raising capital in the last 60 days, then pull their addresses"* and get back rows.

## Live URL

```
https://mcp.nubeam.io/mcp
```

## Install in 3 steps (~3 minutes)

> You need only one thing from the maintainer: your **invite code** (a single random string).

### 1 · Add the MCP connector

Claude Desktop → **Settings → Connectors → Add Custom Connector**

| Field | Value |
|---|---|
| Name | `secforms-db` |
| Server URL | `https://mcp.nubeam.io/mcp` |

Click **Add**. Claude Desktop will open a browser window asking you to log in to the MCP. Paste your **invite code** → click **Authorize** → done. Claude Desktop receives the access token automatically.

You should see `Connected` and 7 tools: `query`, `count`, `explain`, `list_tables`, `describe_table`, `list_foreign_keys`, `schema_summary`.

### 2 · Add the skill

Download `secforms-db-skill.zip` from the latest [Release](../../releases).

Claude Desktop → **Settings → Skills → Upload Skill** → toggle `secforms-db` **on**.

### 3 · Try it

New chat → *"Using secforms-db, show me 5 most recent Form 4 insider sale filings."*

Claude uses the skill to pick the right tables + columns, runs SQL via the connector, returns rows.

If something doesn't work: [`docs/troubleshooting.md`](docs/troubleshooting.md).

## What's inside

```
capital-markets-toolbox/
├── skills/secforms-db/      Skill (uploaded to Claude Desktop)
├── mcp/secforms-db/         MCP service (deployed by maintainer)
├── connector/               Brand assets + manifest
├── docs/                    User + maintainer guides
├── .github/workflows/       CI + release pipeline
└── PLAN.md                  Full design rationale
```

## Things you can ask Claude

- "What does column `cik_role` mean? What values can it take?"
- "How do I join Form 4 to the issuing company?"
- "Show me top fund managers by 13F-HR holdings value last quarter."
- "Help me find people I should look at." *(triggers advisor mode — Claude clarifies, proposes 2–4 options, refines with you, runs the chosen one)*
- "What columns are on `form_13f_hr`?"
- "Why is there both `company_cik` and `person_cik` if they're both CIKs?"

## Safety

Read-only by design. **Four** independent layers:

1. **OAuth scope** — issued tokens are scoped `read:database`. No write scopes exist.
2. **No mutation tools** in the MCP surface. `insert`/`update`/`delete`/DDL don't exist as tools.
3. **SQL guard** — every SQL string parsed and rejected if not `SELECT` / `WITH SELECT` / `EXPLAIN SELECT`.
4. **Postgres role** — `secforms_ro` has only `SELECT` grants and `default_transaction_read_only = on`.

Per-friend identity flows from invite code → JWT → request log. Each friend's traffic is attributable. Maintainer can revoke any invite code without affecting others. See [`mcp/secforms-db/docs/threat-model.md`](mcp/secforms-db/docs/threat-model.md).

## For the maintainer

See [`docs/for-maintainers-deploy.md`](docs/for-maintainers-deploy.md).

## License

MIT. See [`LICENSE`](LICENSE).
