# Per-form table reference

Source of truth for what each `form_<type>` table captures and why it matters. Common columns on every form table (omitted in the per-form lists below): `accession (PK+FK)`, `form_type`, `filing_date`, `filer_cik`, `doc_url`, `doc_name`, `doc_mime`, `index_url`, `byte_size`.

Live row counts: query `forms.filings_count` (after `refresh_forms_counts()`) or `SELECT count(*) FROM form_<type>`.

---


## ALLOCATOR forms (9)

### `form_13f_hr` — SEC form `13F-HR` (allocator)

**Purpose.** Quarterly long-equity holdings report from institutional investment managers with $100M+ in 13(f)-eligible AUM, covering stocks, options, convertibles, and ADRs.

**Why filed.** Mandated under Section 13(f) of the Exchange Act within 45 days of each calendar quarter end.

**Why we care.** Cleanest available map of institutional allocators and their portfolio composition — primary source for sizing funds, identifying active deployers, and tracking sector concentration.

**Form-specific columns** (in addition to the common 9): `company_cik, company_name, report_type, period_of_report, table_entry_total, table_value_total`.

---

### `form_13f_nt` — SEC form `13F-NT` (allocator)

**Purpose.** Notice form filed by a 13F manager when all of its reportable holdings are included on another manager's 13F-HR (typical for sub-advisor or affiliate structures).

**Why filed.** Avoids duplicate reporting; required under Section 13(f) when the manager has no holdings to report directly.

**Why we care.** Low direct signal but reveals organizational structure — parent/sub-advisor relationships and which entity in a complex actually holds the positions.

**Form-specific columns** (in addition to the common 9): `company_cik, company_name, report_type, period_of_report, table_entry_total (jsonb), table_value_total (jsonb)`.

---

### `form_40_app` — SEC form `40-APP` (allocator)

**Purpose.** Application for an SEC exemptive order under the Investment Company Act, requesting relief for novel fund structures (multi-class arrangements, ETF approvals, joint transactions, co-investments).

**Why filed.** Filed by fund sponsors seeking permission for arrangements not explicitly permitted under the 1940 Act.

**Why we care.** Surfaces sophisticated multi-vehicle allocators — BDCs, interval funds, complex sponsors — building custom structures, indicating institutional-grade operations.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_n_14` — SEC form `N-14` (allocator)

**Purpose.** Registration statement covering the reorganization or merger of one registered investment company into another, including terms, shareholder votes, and combined-entity disclosures.

**Why filed.** Required when a fund-to-fund merger or reorganization is presented to shareholders for approval.

**Why we care.** Post-merger AUM concentration — larger combined deployment capacity and sponsor consolidation, signaling expanded allocation power.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title (jsonb)`.

---

### `form_n_cen` — SEC form `N-CEN` (allocator)

**Purpose.** Annual structural census for registered investment companies, covering advisors, sub-advisors, custodians, share classes, fees, and operational arrangements.

**Why filed.** Required annually under Rule 30a-1 of the Investment Company Act.

**Why we care.** Org chart of fund complexes — service provider relationships, sponsor consolidation, and fee structures across the industry.

**Form-specific columns** (in addition to the common 9): `holdings (jsonb), holdings_count, total_holding_value_usd`.

---

### `form_n_port` — SEC form `N-PORT` (allocator)

**Purpose.** Monthly portfolio holdings report from registered investment companies, including full position-level data with liquidity classifications (only the third-month report is made public).

**Why filed.** Required under Rule 30b1-9 of the Investment Company Act.

**Why we care.** Deepest portfolio visibility into mutual funds, ETFs, and closed-end funds — position-level data for sizing allocator concentration and sector exposure.

**Form-specific columns** (in addition to the common 9): `series_name, reg_name, reg_cik, company_name, company_cik, rep_pd_end, rep_pd_date, total_assets, total_liabilities, net_assets, holdings (jsonb), holdings_count, total_holding_value_usd`.

---

### `form_n_px` — SEC form `N-PX` (allocator)

**Purpose.** Annual report of how a registered fund voted the proxy ballots of every portfolio company it held during the period.

**Why filed.** Required annually under Section 30(b)(1) of the Investment Company Act.

**Why we care.** Governance and voting behavior — useful for tracking ESG alignment, activist support patterns, and how funds engage with portfolio companies.

**Form-specific columns** (in addition to the common 9): `holdings (jsonb), holdings_count, total_holding_value_usd`.

---

### `form_sc_13d` — SEC form `SC 13D` (allocator)

**Purpose.** Beneficial ownership report for any party crossing the 5% threshold of a public company's voting stock with active or control-seeking intent.

**Why filed.** Section 13(d) requires filing within 10 days of crossing 5%; amendments required on any material change.

**Why we care.** Identifies activist capital, concentrated bets, and change-of-control plays — highest-conviction allocator signal in the dataset.

**Form-specific columns** (in addition to the common 9): `submission_type, securities_class_title, date_of_event (jsonb), reporting_persons (jsonb), issuer_cik, issuer_name, company_name, company_cik, cusips (jsonb), cusip, filer_name, person_name, person_cik, pct_of_class, shares_owned, max_pct_of_class, sum_shares_owned`.

---

### `form_sc_13g` — SEC form `SC 13G` (allocator)

**Purpose.** Short-form beneficial ownership report for 5%+ stakes held passively, without intent to influence control.

**Why filed.** Available to qualified institutional investors, passive investors, and exempt investors under Rule 13d-1(b)/(c).

**Why we care.** Surfaces large passive accumulators — index complexes, pensions, long-only funds — providing a clean view of institutional float ownership.

**Form-specific columns** (in addition to the common 9): `submission_type, securities_class_title, date_of_event (jsonb), issuer_cik, issuer_name, company_name, company_cik, cusips (jsonb), cusip, reporting_persons (jsonb)`.

---


## SEEKER forms (18)

### `form_10_q` — SEC form `10-Q` (seeker)

**Purpose.** Quarterly report containing unaudited financial statements (income, balance sheet, cash flow), MD&A, internal controls disclosure, and risk updates.

**Why filed.** Exchange Act Section 13 requires filing within 40–45 days of each of the first three fiscal quarter ends.

**Why we care.** Fundamental data source — revenue trajectory, burn, runway, segment performance, and cash position for prospect qualification and timing.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_144` — SEC form `144` (seeker)

**Purpose.** Pre-sale notice filed by a Section 16 affiliate (officer, director, 10%+ holder) declaring intent to sell restricted or control securities under Rule 144.

**Why filed.** Required before an affiliate can sell more than 5,000 shares or $50K aggregate value of restricted stock in any 3-month window.

**Why we care.** Leading indicator of insider liquidity events — surfaces executives and founders about to receive a cash event, ideal timing for wealth/investment product outreach.

**Form-specific columns** (in addition to the common 9): `issuer_name, company_name, issuer_cik, company_cik, seller_name, person_name, relationships (jsonb), security_class_title, broker_name, total_shares, agg_market_value, approx_sale_date, shares_outstanding, exchange_name, nature_of_acquisition, date_of_acquisition, acquired_from, amount_acquired, is_gift`.

---

### `form_144_a` — SEC form `144/A` (seeker)

**Purpose.** Amendment to a Form 144 proposed-sale notice, updating the share count, price range, or broker details of a previously disclosed insider sale plan.

**Why filed.** Filed when the original Form 144 needs correction or when sale parameters change before execution.

**Why we care.** Refinement on a previously flagged insider liquidity event — useful for confirming whether a planned sale is actually proceeding.

**Columns.** same as form_144.

---

### `form_3` — SEC form `3` (seeker)

**Purpose.** Initial beneficial ownership statement filed the first time an individual becomes subject to Section 16 — newly named officer, director, or 10%+ holder, or all insiders at the moment of IPO.

**Why filed.** Required within 10 days of becoming an insider; establishes the baseline holdings against which future Form 4s report changes.

**Why we care.** Identifies newly appointed executives and directors — pre-event signal for upcoming Form 4 activity and option grants tied to the appointment.

**Form-specific columns** (in addition to the common 9): `period_of_report, not_subject_to_section16 (jsonb), issuer_cik, issuer_name, issuer_trading_symbol, company_cik, company_name, reporting_owners (jsonb), person_cik, person_name, is_officer, is_director, is_ten_pct, officer_title, transactions (jsonb), sale_count, total_sale_usd`.

---

### `form_4` — SEC form `4` (seeker)

**Purpose.** Statement of changes in beneficial ownership by Section 16 insiders, disclosing each individual transaction (purchase, sale, option exercise, grant, gift) with date, price, and share count.

**Why filed.** Section 16(a) requires filing within 2 business days of any transaction in the issuer's equity securities.

**Why we care.** Highest-volume insider signal — option exercises and open-market sales surface newly liquid founders, executives, and 10%+ holders becoming HNW investors themselves.

**Form-specific columns** (in addition to the common 9): `period_of_report, not_subject_to_section16, issuer_cik, issuer_name, issuer_trading_symbol, company_cik, company_name, reporting_owners (jsonb), person_cik, person_name, is_officer, is_director, is_ten_pct, officer_title (jsonb), transactions (jsonb), sale_count, total_sale_usd`.

---

### `form_424b5` — SEC form `424B5` (seeker)

**Purpose.** Prospectus supplement disclosing the pricing and final terms of an actual securities offering executed off an existing S-3 shelf registration.

**Why filed.** Required by Rule 424 upon execution of a follow-on, secondary, or ATM offering tied to a prior shelf.

**Why we care.** Live capital raise confirmation — proves that an issuer has actually priced and sold securities off its shelf. Direct deal signal.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_425` — SEC form `425` (seeker)

**Purpose.** Filing of communications relating to a business combination or merger transaction subject to a registration statement.

**Why filed.** Required under Rule 425 for any written soliciting materials issued in connection with a registered M&A or SPAC transaction.

**Why we care.** Strategic capital transaction in motion — surfaces SPAC combinations, mergers, and large strategic deals, often months before closing.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_4_a` — SEC form `4/A` (seeker)

**Purpose.** Amendment correcting a previously filed Form 4 — typically fixes transaction dates, share counts, prices, or transaction codes.

**Why filed.** Filed when errors are discovered in the original Form 4 or when previously omitted transactions surface.

**Why we care.** Data-hygiene filing; occasionally reveals previously undisclosed transactions or restates the size of an insider's position.

**Columns.** same shape as form_4 (officer_title is text, not jsonb).

---

### `form_5` — SEC form `5` (seeker)

**Purpose.** Annual statement of beneficial ownership changes catching transactions that were eligible for deferred reporting on Form 4 — gifts, small transactions, and late filings.

**Why filed.** Required within 45 days of fiscal year end if an insider had any transactions exempt from Form 4 reporting during the year.

**Why we care.** Low-signal housekeeping filing; occasionally surfaces late-disclosed material activity that escaped Form 4 reporting throughout the year.

**Columns.** same shape as form_4 (total_sale_usd is bigint).

---

### `form_8_k` — SEC form `8-K` (seeker)

**Purpose.** Current report disclosing material events between periodic filings — acquisitions, departures, definitive agreements, financing, earnings releases, Reg FD disclosures, and other item-coded events.

**Why filed.** Required within 4 business days of the triggering event under Exchange Act Section 13.

**Why we care.** Real-time capital and operational events — PIPE deals, acquisitions, exec changes, and financing closures all hit here first.

**Form-specific columns** (in addition to the common 9): `items (jsonb), item_count, body_text_head`.

---

### `form_c` — SEC form `C` (seeker)

**Purpose.** Regulation Crowdfunding offering statement disclosing the issuer, offering terms, financials, and use of proceeds for raises up to $5M per 12-month period.

**Why filed.** Required before soliciting non-accredited investors through a registered funding portal under Reg CF.

**Why we care.** Surfaces early-stage companies actively fundraising — founder details, team composition, traction metrics, and round mechanics available for sourcing.

**Form-specific columns** (in addition to the common 9): `submission_type, company_name, company_cik, entity_type, jurisdiction_of_inc, date_incorporation, issuer_website, intermediary_name, intermediary_cik, intermediary_crd, progress_update (jsonb), security_offered_type, price, offering_amount, target_offering_amount (jsonb), maximum_offering_amount, deadline, current_employees, total_asset_most_recent_fy, total_revenue_most_recent_fy (jsonb), net_income_most_recent_fy`.

---

### `form_c_a` — SEC form `C/A` (seeker)

**Purpose.** Amendment to a previously filed Form C disclosing material changes in a Regulation Crowdfunding offering.

**Why filed.** Required when offering terms, pricing, oversubscription, or material company information changes during an active Reg CF raise.

**Why we care.** Signals progress on an active early-stage raise — extensions, increased targets, or oversubscription often precede a priced round.

**Columns.** same as form_c (intermediary_crd is jsonb, price is jsonb).

---

### `form_d_a` — SEC form `D/A` (seeker)

**Purpose.** Amendment to a Form D Regulation D private placement notice, updating amount sold, investor count, issuer details, or extending the offering period.

**Why filed.** Required when material facts change during a Reg D offering or annually if the offering remains open.

**Why we care.** Signals an active private raise still in motion — continued capital intake, round extensions, or new tranches on an ongoing deal.

**Form-specific columns** (in addition to the common 9): `entity_name, entity_type, jurisdiction_of_inc, year_of_inc, company_name, submission_type, is_amendment, company_cik, industry_group_type, investment_fund_type, revenue_range, aggregate_net_asset_value_range, date_of_first_sale, total_offering_amount, total_amount_sold, total_remaining, minimum_investment_accepted, total_number_already_invested, has_non_accredited_investors`.

---

### `form_def_14a` — SEC form `DEF 14A` (seeker)

**Purpose.** Definitive proxy statement issued ahead of annual or special meetings, covering director nominations, executive compensation (CD&A), say-on-pay, shareholder proposals, and auditor ratification.

**Why filed.** Required under Section 14(a) before soliciting proxy votes from shareholders.

**Why we care.** Governance snapshot — executive compensation packages, board composition, equity awards, and contested proxies. Core source for executive recruiting and activist tracking.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_fwp` — SEC form `FWP` (seeker)

**Purpose.** Free Writing Prospectus — supplemental marketing or communication material distributed during a registered offering, including term sheets, roadshow decks, and press releases.

**Why filed.** Filed when an issuer or underwriter distributes offering materials outside the formal statutory prospectus.

**Why we care.** Indicates an active roadshow with a deal in market right now — early warning for an imminent priced offering.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_s_1` — SEC form `S-1` (seeker)

**Purpose.** Initial registration statement for an IPO, providing full company disclosure: audited financials, MD&A, risk factors, capitalization, use of proceeds, and management bios.

**Why filed.** Required under the Securities Act before the SEC declares the registration effective and the company can sell shares to the public.

**Why we care.** Identifies pre-IPO companies preparing institutional rounds and the pipeline of soon-to-be-liquid founders, executives, and early employees.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_s_1_a` — SEC form `S-1/A` (seeker)

**Purpose.** Amendment to an S-1 IPO registration, typically responding to SEC staff comments, updating financials, or refining offering terms.

**Why filed.** Filed as the SEC review progresses or when material new information must be added before effectiveness.

**Why we care.** Late-stage IPO indicator — pricing ranges, share counts, and underwriter syndicate appear here, signaling imminent listing.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---

### `form_s_3` — SEC form `S-3` (seeker)

**Purpose.** Short-form shelf registration for seasoned issuers, enabling future securities offerings (follow-ons, secondaries, ATM programs, convertibles) to be launched on a rapid timeline.

**Why filed.** Available to issuers with 12+ months of reporting history and at least $75M public float; filed to pre-position for future capital needs.

**Why we care.** Indicates a public company is positioned for follow-on capital — track for actual draws via 424B prospectus supplements that follow.

**Form-specific columns** (in addition to the common 9): `body_text_head, document_title`.

---
