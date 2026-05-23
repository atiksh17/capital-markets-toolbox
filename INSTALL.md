# Install guide — Claude Desktop

Two artifacts. ~3 minutes once you have your invite code.

## What you need from the maintainer

| Item | Looks like |
|---|---|
| Invite code | a single random string (~44 chars, base64) |

That's it. URL is public: `https://mcp.nubeam.io/mcp`. Ask via Signal / password-manager share, not chat or email.

## Step 1 — Add the connector

1. Open Claude Desktop (Mac, Windows, or Linux). Update to the latest version.
2. Click your name / avatar (bottom-left) → **Settings**.
3. Go to **Connectors**.
4. Click **Add Custom Connector** (or **+**).
5. Fill in:
   - **Name:** `secforms-db`
   - **Server URL:** `https://mcp.nubeam.io/mcp`
6. Click **Add** (or **Save**).

Claude Desktop discovers the OAuth endpoints automatically and opens a browser window for you to log in.

7. On the login page (titled *"Connect to secforms-db"*), paste your **invite code** into the *Invite code* field → click **Authorize**.
8. The browser redirects back to Claude Desktop. The connector switches to `Connected`. Expand it — you should see 7 tools: `query`, `count`, `explain`, `list_tables`, `describe_table`, `list_foreign_keys`, `schema_summary`.

That's it. The invite code stays on the server; Claude Desktop now holds a 24-hour access token (auto-renewed on the next login).

If something fails: [`docs/troubleshooting.md`](docs/troubleshooting.md).

## Step 2 — Add the skill

1. Open this repo's [Releases page](../../releases).
2. Download `secforms-db-skill.zip` from the latest release.
3. Back in Claude Desktop → **Settings → Skills**.
4. Click **Upload Skill** (or drag the zip onto the window).
5. Toggle `secforms-db` **On**.

The skill is now active for any new chat that mentions the database.

## Step 3 — Verify

Open a fresh chat. Send:

> Using the **secforms-db** skill, run a `schema_summary` and tell me how many tables and foreign keys are in the database.

Claude should:

1. Acknowledge the skill is active.
2. Call `mcp__secforms-db__schema_summary`.
3. Reply: `35 tables, 34 foreign keys`.

Then try a real question:

> Using **secforms-db**, find the 10 most recent Form 4 insider sale filings, ordered by total sale value.

Claude writes a SELECT joining `form_4` to `signals`, runs it through the connector, shows rows.

## What you can ask Claude

| Pattern | Example |
|---|---|
| Direct query | *"Pull top 25 13F-HR filings by table_value_total last quarter"* |
| Schema question | *"What does `signal_ciks.cik_role` mean?"* |
| Vague intent (triggers advisor) | *"Help me find some people I should look at"* |
| Concrete intent | *"Get insider sales over $1M at AAPL in the last 30 days"* |

## Updating

When the maintainer cuts a new release:

- Re-download the latest skill zip and re-upload (Skills UI replaces the existing one).
- No action needed on the connector — improvements ship server-side and the access token auto-refreshes.

## Removing

- Skill: **Settings → Skills** → toggle off or delete.
- Connector: **Settings → Connectors → secforms-db** → **Remove**.

If you suspect your invite code leaked, tell the maintainer immediately so they can revoke + reissue.
