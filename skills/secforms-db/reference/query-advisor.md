# Query advisor — vague intent → final SQL

This file defines the **advisor sub-mode** of the skill. Enter it whenever the user's request is *not* already a concrete query.

## When to enter advisor mode

Symptoms in the user's prompt:

- No subject named ("find me some good leads", "what's interesting?")
- Subject named but no filter ("show me companies")
- A verb that implies discovery, not retrieval ("help me look for", "I want to find", "suggest", "what can I get")
- A goal stated instead of a query ("I want to reach out to recently liquid founders")

When in doubt, ask one clarifying question instead of guessing. The user wants iteration, not a wall of SQL.

## The 5-step protocol

### 1. Clarify intent (≤3 short questions)

Pick at most three from:

- **Subject** — companies, people, filings, or holdings?
- **Filter dimensions** — time window, geography, form type, role (insider vs allocator), size, ticker?
- **Output shape** — count, ranked list, detail rows, joinable export?

Ask only the ones the prompt left ambiguous. Don't ask for things the prompt already provided.

### 2. Propose 2–4 candidate queries (no SQL yet)

Numbered menu. Each option must say:

- **What it returns** (1 line, plain English)
- **Tables it touches** (and why those, given your schema knowledge)
- **Approximate shape** (columns + row count expectation)
- **Caveats** (e.g. "only enriched CIKs", "30d window — adjustable")

End with: *"Which one — or want to mix filters?"*

### 3. User picks or refines

If user picks → step 4. If user refines ("narrow to last 30 days", "add ticker", "exclude funds") → re-do step 2 with the refinement applied. Repeat until they pick or you've iterated 3 times — at that point summarize what you've gathered and propose a single best query.

### 3.5. Field picker (two-tier checkbox menu)

Before writing SQL, lock in **which columns** to project. Two tiers, in this order:

**Tier A — entity fields.** Columns from the entity table the answer hangs on (`companies` if subject is a company / fund / issuer; `people` if subject is a person / insider; `cik_list` only for unenriched / queue questions).

**Tier B — signal/form fields.** Columns from the per-form table that hangs off the accession (e.g. `form_4` for insider trades, `form_13f_hr` for fund holdings, `form_144` for pre-sale notices). Skip Tier B if the user picked a count / aggregate / list-of-entities answer with no per-filing detail.

Render each tier as a **multi-select** using `AskUserQuestion` (multiSelect: true). For each tier, offer one **preset bundle** as a single option *plus* individual columns so the user can either one-click a preset or hand-pick.

#### Preset bundles (use these by default — extend if user asks)

**Entity = `companies`:**
| Preset | Columns |
|---|---|
| `Minimal` | `company_cik`, `name`, `ticker` |
| `Outreach` (Recommended) | `company_cik`, `name`, `ticker`, `website`, `investor_website`, `address`, `sic_description`, `state_of_incorp` |
| `Full` | all 15 columns |

**Entity = `people`:**
| Preset | Columns |
|---|---|
| `Minimal` | `person_cik`, `canonical_name` |
| `Outreach` (Recommended) | `person_cik`, `canonical_name`, `address`, `entity_type`, `former_names` |
| `Full` | all 6 columns |

**Entity = `cik_list`** (queue/registry questions only): `Minimal` = `cik`, `date_added`, `enriched`.

**Signal/form (per form table):**

| Form table | `Minimal` | `Detail` (Recommended) |
|---|---|---|
| `form_4` / `form_4_a` / `form_5` | `accession`, `filing_date`, `issuer_name`, `person_name`, `total_sale_usd` | + `issuer_trading_symbol`, `is_officer`, `is_director`, `is_ten_pct`, `officer_title`, `transactions`, `sale_count`, `doc_url` |
| `form_3` | `accession`, `filing_date`, `issuer_name`, `person_name`, `officer_title` | + `is_officer`, `is_director`, `is_ten_pct`, `transactions`, `doc_url` |
| `form_144` / `form_144_a` | `accession`, `filing_date`, `issuer_name`, `seller_name`, `total_shares`, `agg_market_value`, `approx_sale_date` | + `security_class_title`, `broker_name`, `relationships`, `shares_outstanding`, `exchange_name`, `doc_url` |
| `form_13f_hr` | `accession`, `filing_date`, `company_name`, `period_of_report`, `table_value_total` | + `table_entry_total`, `report_type`, `doc_url` |
| `form_13f_nt` | `accession`, `filing_date`, `company_name`, `period_of_report` | + `report_type`, `doc_url` |
| `form_sc_13d` | `accession`, `filing_date`, `issuer_name`, `filer_name`, `person_name`, `pct_of_class`, `shares_owned` | + `securities_class_title`, `date_of_event`, `max_pct_of_class`, `sum_shares_owned`, `cusip`, `doc_url` |
| `form_sc_13g` | `accession`, `filing_date`, `issuer_name`, `securities_class_title`, `submission_type` | + `date_of_event`, `cusip`, `reporting_persons`, `doc_url` |
| `form_c` / `form_c_a` | `accession`, `filing_date`, `company_name`, `target_offering_amount`, `maximum_offering_amount`, `intermediary_name` | + `entity_type`, `jurisdiction_of_inc`, `issuer_website`, `security_offered_type`, `price`, `deadline`, `total_revenue_most_recent_fy`, `current_employees`, `doc_url` |
| `form_d_a` | `accession`, `filing_date`, `company_name`, `total_offering_amount`, `total_amount_sold` | + `entity_type`, `industry_group_type`, `investment_fund_type`, `revenue_range`, `aggregate_net_asset_value_range`, `date_of_first_sale`, `minimum_investment_accepted`, `has_non_accredited_investors`, `doc_url` |
| `form_n_port` | `accession`, `filing_date`, `series_name`, `company_name`, `rep_pd_end`, `net_assets`, `total_holding_value_usd`, `holdings_count` | + `reg_name`, `reg_cik`, `total_assets`, `total_liabilities`, `holdings`, `doc_url` |
| `form_n_cen` / `form_n_px` | `accession`, `filing_date`, `holdings_count`, `total_holding_value_usd` | + `holdings`, `doc_url` |
| `form_s_1` / `form_s_1_a` / `form_s_3` / `form_424b5` / `form_425` / `form_fwp` / `form_def_14a` / `form_n_14` / `form_40_app` / `form_10_q` | `accession`, `filing_date`, `document_title` | + `body_text_head`, `filer_cik`, `doc_url`, `byte_size` |
| `form_8_k` | `accession`, `filing_date`, `items`, `item_count` | + `body_text_head`, `doc_url` |

If the requested entity has **no per-form table involved** (e.g. "just list enriched companies in CA"), skip Tier B entirely.

#### Picker call shape

Use `AskUserQuestion` with `multiSelect: true`. Two questions max — one per tier. Each option = one column. Add the preset bundle as the **first** option labeled `Preset: <name>` so single-click picks the bundle.

Example:

```
AskUserQuestion(
  questions=[
    {
      "question": "Which company fields do you want?",
      "header": "Company cols",
      "multiSelect": true,
      "options": [
        {"label": "Preset: Outreach (Recommended)", "description": "name, ticker, website, investor_website, address, sic_description, state_of_incorp"},
        {"label": "company_cik", "description": "always projected (PK)"},
        {"label": "name", "description": "legal entity name"},
        {"label": "ticker", "description": "stock symbol (NULL if not listed)"},
        ...
      ]
    },
    {
      "question": "Which Form 4 (insider trade) fields per filing?",
      "header": "Form 4 cols",
      "multiSelect": true,
      "options": [
        {"label": "Preset: Detail (Recommended)", "description": "filing_date, issuer_name, person_name, total_sale_usd, transactions, sale_count, is_officer, is_director, ...]"},
        {"label": "filing_date", "description": "SEC receipt date"},
        {"label": "total_sale_usd", "description": "rolled-up sale amount in USD"},
        ...
      ]
    }
  ]
)
```

If `AskUserQuestion` isn't available (e.g. running in a non-Claude-Desktop client), fall back to a markdown checkbox menu the user can edit:

```
Tier A — companies fields (check what you want):
[x] company_cik   (required)
[x] name
[ ] ticker
[ ] website
...

Tier B — form_4 fields:
[x] filing_date
[x] total_sale_usd
[ ] transactions (jsonb — verbose)
...
```

Then continue to step 4 with the user's picks merged into the SELECT projection.

### 4. Show the SQL

Present the final SQL **with a 1-line annotation per clause** so the user can verify it matches intent. End with: *"Run as-is, or tweak?"*

Don't run it yet.

### 5. Run via `mcp__secforms-db__query` when confirmed

- Default `LIMIT 100` unless the user asked for more.
- Show first 10 rows in a markdown table + a row count summary line.
- Offer follow-ups: "filter further?", "export full result?", "join in more detail?"

## Decision rules (by subject)

| Subject (user phrasing) | Start from | Common joins |
|---|---|---|
| "person" / "insider" / "founder" / "executive" | `people` | `signal_ciks` → `signals` → form table |
| "company" / "issuer" / "fund" | `companies` | same pattern |
| "filing" / "what just happened" | `signals` + `forms` (`signal_side`) | form table for detail |
| "who holds what" / "holdings" / "portfolio" | `form_13f_hr` or `form_n_port` | `signal_ciks` → `cik_list` → `companies` |
| "insider trading" / "Form 4" | `form_4` | `signals` → `people` (insider), `companies` (issuer) |
| "raising capital" / "fundraise" / "IPO" | `form_s_1`, `form_424b5`, `form_c`, `form_d_a` | `signal_ciks` → `companies` |
| "activist" / "5% stake" | `form_sc_13d` (active) or `form_sc_13g` (passive) | → `companies` (issuer), `people` or `companies` (filer) |
| "recent liquidity event" | `form_144` | → `people` (seller), `companies` (issuer) |

## Heuristics for the proposal menu

- **Always include one broad + one narrow option.** Broad = looser filters, more rows. Narrow = tighter, fewer rows. Lets the user choose tradeoff explicitly.
- **If the prompt maps cleanly to a recipe in `query-recipes.md`, lead with that recipe** as option 1 and cite its number.
- **Vague time terms** ("recent", "lately", "this quarter") → don't guess. Offer 7d / 30d / 90d as a picker.
- **If a needed filter column isn't mentioned, surface it as a question rather than defaulting.** Example: user wants "insiders at small companies" → ask "small by what — market cap (not in DB), employee count (only on Form C/C_A), or SIC sector?"

## Example dialogue (use this as the template)

> **User**: "Help me find some people I should look at."
>
> **Advisor**: "Three quick questions — (1) people in a specific role (corporate insiders, fund managers, signatories)? (2) Time window for their recent activity? (3) Any company or sector filter?"
>
> *(user: "insiders, last 60 days, no sector filter")*
>
> **Advisor**: "Three options:
>
> 1. **Top insiders by Form 4 filing volume (last 60d)** — joins `form_4` → `people`; returns name + cik + filing_count; ~50–500 rows. Broad signal.
> 2. **Insiders at companies that also filed S-1 or 424B5 in last 60d** — narrower (~10–80 rows). Surfaces insiders at actively-raising issuers. (Recipe 11.)
> 3. **New insiders only (Form 3, last 60d)** — people becoming insiders for the first time; ~100–300 rows. Fresh names, not repeats.
>
> Which one — or mix?"
>
> *(user: "go with #2 but also include their address")*
>
> **Advisor**: "OK — adding `p.address` to the projection. Here's the SQL:"
>
> ```sql
> -- CTE: companies that raised in last 60d (S-1 or 424B5)
> WITH raising AS (...)
> -- main: insiders at those companies in same window, plus address from people
> SELECT f4.company_cik, c.name AS company_name,
>        p.canonical_name, p.address,
>        f4.filing_date, f4.total_sale_usd
> FROM form_4 f4
> JOIN raising r ON r.company_cik = f4.company_cik
> LEFT JOIN companies c ON c.company_cik = f4.company_cik
> LEFT JOIN people    p ON p.person_cik  = f4.person_cik
> WHERE f4.filing_date >= now()::date - 60
> ORDER BY f4.filing_date DESC
> LIMIT 100;
> ```
>
> "Run as-is, or tweak the window / limit / columns?"
>
> *(user: "run it")*
>
> **Advisor**: *(calls `mcp__secforms-db__query`, shows first 10 rows + row count)*
> "Returned 73 rows. Want me to filter to officers only (`f4.is_officer = true`)?"

## What advisor mode is NOT

- Not always-on. If the user types a fully-formed query intent (`"show me Form 4 filings in last 7 days where total_sale_usd > 1M"`), skip the menu and run it directly.
- Not a SQL-writing exercise. Step 2 is plain English; SQL only appears at step 4.
- Not a place to load every table into the menu. Pick 2–4 options per round, max.
- Not a substitute for `query-recipes.md`. If a recipe fits, cite it.
