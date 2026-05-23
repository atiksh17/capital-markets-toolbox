# Install guide (friends — short)

Long version: [`INSTALL.md`](../INSTALL.md).

## You need

- Claude Desktop (Mac / Windows / Linux), latest version
- Your **invite code** from the maintainer (one random string)

The URL is the same for everyone: `https://mcp.nubeam.io/mcp`.

## Do this

1. **Add connector** — Claude Desktop → Settings → Connectors → Add Custom Connector
   - Name: `secforms-db`
   - Server URL: `https://mcp.nubeam.io/mcp`
   - Click Add. A login page opens. Paste your invite code → Authorize.
2. **Add skill** — Download `secforms-db-skill.zip` from this repo's Releases → Claude Desktop → Settings → Skills → Upload → toggle on.
3. **Verify** — New chat: *"Use secforms-db to run schema_summary"* → expect `35 tables, 34 foreign keys`.

## Ask Claude things like

- *"Find the top 10 Form 4 insider sales in the last 30 days"*
- *"What does the cik_role column mean?"*
- *"Help me find some founders who recently filed a Form 144"* (advisor mode)
- *"How is form_13f_hr different from form_13f_nt?"*

## Broken?

See [`troubleshooting.md`](troubleshooting.md). Common: wrong invite code, stale Claude Desktop version, browser blocking the OAuth redirect.
