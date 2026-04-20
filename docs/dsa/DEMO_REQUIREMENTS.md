# DSA MVP — Demo Requirements
## ROMI Data Product Scenario

**Version:** 1.0  
**Date:** March 2026  
**Owner:** phData Product — Judy Albeige  
**Purpose:** Define the fake demo scenario, scripted data, and simulated source system content for the DSA MVP demo. This document is for demo build only — the ROMI data product is fictional and in-progress.

---

## 1. Demo Objective

Show a Product Owner and Data Analyst persona walking through the DSA workflow — from a scattered, messy real-world starting point to a clean, structured, versioned artifact — in a single demo session. The audience should feel the before/after contrast viscerally: *this is how it works today, and this is what it looks like with the DSA*.

The demo does not need to be complete end-to-end. It needs to demonstrate:
1. The agent interview replacing a blank PRD
2. Source context surfacing inline from connected systems (Atlan, Snowflake, Highspot) — no tab-switching
3. The artifact building live as the conversation progresses
4. One human gate executed deliberately

---

## 2. The Scenario

**Data product:** Return on Marketing Investment (ROMI)  
**Requesting team:** Marketing Operations  
**Assigned analyst:** Senior Data Analyst, ED&A team  
**Status at demo start:** The PO has emailed a brief asking for "a ROMI dashboard." Nothing else exists. No PRD. No requirements. No agreed source systems. The analyst has been assigned to figure it out.

This is the starting state the demo walks out of.

---

## 3. Where the Information Lives Today (The Before State)

The information needed to build the ROMI data product is real — but it is scattered across six systems in three different formats. The demo agent's job is to surface this without the analyst leaving the interface.

---

### 3.1 Highspot — Business Process Documentation (Unstructured)

**What it is:** Highspot contains Workday's internal sales and marketing business process documentation, pitch decks, and methodology guides. For ROMI, the relevant content is the Marketing Attribution Methodology doc and a QBR slide deck that defines how marketing ROI is currently calculated manually.

**Simulated content for demo:**

**Document 1: Marketing Attribution Methodology v2.1** *(unstructured — Word doc)*
> *"Marketing investment return is calculated quarterly by the Marketing Operations team using a combination of Allocadia budget exports, Salesforce opportunity reports, and Marketo lead data. The current process requires a 3–4 week consolidation effort each quarter. Attribution is assigned on a primary source basis — each closed-won opportunity is credited to one campaign. Influenced pipeline (any marketing touch within 90 days of opportunity creation) is tracked separately and used for executive reporting only.*
>
> *Known issues with the current process: (1) Allocadia and Salesforce campaign IDs are not consistently mapped, requiring manual reconciliation. (2) Agency and vendor spend is tracked in separate spreadsheets maintained by individual channel owners and is not systematically included in the total spend calculation. (3) The fiscal calendar in use is a Feb–Jan year-end, which does not match Salesforce's default calendar year — all Salesforce reports must be manually adjusted."*

**Document 2: Q3 FY2026 Marketing QBR Deck** *(unstructured — slide excerpt)*
> *Slide 7: "ROMI by Channel — Q3 FY2026"*
> - Paid Search: 2.4x return
> - Field Events: 1.1x return
> - Email Nurture: 3.8x return
> - LinkedIn Paid Social: 0.7x return (below target)
>
> *Footer note: "Numbers based on manual consolidation. Allocadia actuals as of Oct 15. Salesforce pipeline as of Oct 18. Figures are approximate — reconciliation in progress."*

**What the agent does with this:** When the PO says "we want to track ROMI by channel," the agent confirms it has found the Attribution Methodology doc in Highspot and surfaces the fiscal calendar mismatch and Allocadia/Salesforce mapping issue as known dependencies — without the analyst having to find the document themselves.

---

### 3.2 Atlan — Data Catalog (Semi-Structured)

**What it is:** Atlan is the data catalog. It contains metadata for existing Snowflake tables, column descriptions (where they exist), lineage, and data quality scores. For ROMI, two relevant tables exist in Atlan — one well-documented, one not.

**Simulated content for demo:**

**Asset 1: `mktg.salesforce_opportunities` — well-documented**
```
Table: mktg.salesforce_opportunities
Owner: Marketing Data Team
Last updated: 2026-03-15
Data quality score: 87/100
Description: Salesforce opportunity data synced daily via Fivetran. Contains all opportunities 
             created after 2022-01-01. Primary source of truth for pipeline and revenue metrics.

Columns (selected):
  opportunity_id        VARCHAR(18)   PK   Salesforce opportunity ID (18-char)
  opportunity_name      VARCHAR(255)       Human-readable name — not reliable for parsing
  account_id            VARCHAR(18)   FK   Links to mktg.salesforce_accounts
  primary_campaign_id   VARCHAR(18)        Campaign credited as primary source. NULL for ~23% 
                                           of opps — these are sales-originated with no campaign.
  amount                DECIMAL(18,2)      Contract value in USD. Does not include expansion.
  stage_name            VARCHAR(50)        Current stage. Closed Won / Closed Lost / [open stages]
  close_date            DATE               Opportunity close date — USE fiscal_calendar join for 
                                           fiscal period mapping. DO NOT use calendar year.
  created_date          DATE               Date opportunity was created in Salesforce

Data quality flags:
  ⚠ primary_campaign_id: 23% NULL rate — known gap for sales-sourced pipeline
  ⚠ amount: 4 records with $0 value — likely test records, filter with amount > 0
```

**Asset 2: `finance.allocadia_budget` — poorly documented**
```
Table: finance.allocadia_budget
Owner: Unknown (last owner left company)
Last updated: 2026-01-08 (stale — 80+ days)
Data quality score: 41/100
Description: [No description provided]

Columns (selected):
  id                    VARCHAR(36)        [No description]
  line_item_nm          VARCHAR(200)       [No description]  
  budget_amt            DECIMAL(18,2)      [No description]
  actual_amt            DECIMAL(18,2)      [No description]
  prd                   VARCHAR(20)        [No description — likely period code]
  cmpgn_cd              VARCHAR(50)        [No description — likely campaign code]
  cost_typ              VARCHAR(10)        [No description — likely cost type]

Data quality flags:
  ⚠ No column descriptions — ownership gap
  ⚠ Last refresh 80+ days ago — may not reflect current actuals
  ⚠ cmpgn_cd format does not match Salesforce primary_campaign_id format — join key TBD
  ✗ No lineage documented — source pipeline unknown
```

**Asset 3: `mktg.marketo_leads` — exists but not confirmed in scope**
```
Table: mktg.marketo_leads
Owner: Marketing Ops (Automated)
Last updated: 2026-03-29 (current)
Data quality score: 79/100
Description: Marketo lead records synced nightly. Contains all leads from 2021 onward.

Columns (selected):
  lead_id               INT                Marketo internal ID
  lead_source_campaign  VARCHAR(100)       Campaign name string — NOT a campaign ID. 
                                           Requires fuzzy match to join to Salesforce campaigns.
  mql_score             INT                Current lead score. MQL threshold = 85.
  mql_date              DATE               Date lead reached MQL score. NULL if not yet MQL.
  email                 VARCHAR(255)  🔒   PII — masked in all downstream views. Do not surface.
  created_date          DATE
```

**What the agent does with this:** When the analyst asks about lead data, the agent surfaces the Marketo leads table from Atlan and immediately flags two issues: (1) the `lead_source_campaign` field is a name string, not an ID — joining to Salesforce campaigns requires a fuzzy match or a lookup table, and (2) the email field is PII and must never be surfaced in the product layer. These are real issues the analyst would normally discover hours into the work. The agent surfaces them in 30 seconds.

---

### 3.3 Snowflake — Live Schema (Structured)

**What it is:** The Snowflake schema browser. For the demo, the agent queries available tables and surfaces schema metadata inline when the analyst asks about source availability.

**Simulated content for demo:**

**Schema: `MARKETING_DW`**
```sql
-- Tables available (simulated query result)
MARKETING_DW.MKTG.SALESFORCE_OPPORTUNITIES     -- 1.2M rows, daily refresh
MARKETING_DW.MKTG.SALESFORCE_CAMPAIGNS         -- 18K rows, daily refresh  
MARKETING_DW.MKTG.SALESFORCE_CAMPAIGN_MEMBERS  -- 4.8M rows, daily refresh
MARKETING_DW.MKTG.MARKETO_LEADS                -- 890K rows, nightly refresh
MARKETING_DW.FINANCE.ALLOCADIA_BUDGET          -- 24K rows, last refresh 80 days ago ⚠
MARKETING_DW.FINANCE.FISCAL_CALENDAR           -- Reference table, static
MARKETING_DW.MKTG.GOOGLE_ADS_PERFORMANCE       -- 340K rows, daily refresh
MARKETING_DW.MKTG.LINKEDIN_CAMPAIGN_STATS      -- ⚠ TABLE NOT FOUND — connector not yet active
```

**Key discovery the agent makes from Snowflake:**
- LinkedIn Campaign Stats table does not exist — the connector is not active. This surfaces immediately as a dependency flag. The analyst did not know this.
- Allocadia budget table is 80 days stale — matches the Atlan quality flag.
- Fiscal calendar table exists and is ready — resolves the fiscal year mapping concern from the Highspot doc.

---

### 3.4 Allocadia — Budget Planning Tool (Structured, External)

**What it is:** Allocadia is the marketing budget planning system. It is not in Snowflake yet for this scenario — it needs to be connected. The demo shows the agent flagging this as a dependency.

**Simulated content for demo (what a manual Allocadia export looks like):**

```
ALLOCADIA BUDGET EXPORT — Q1 FY2027 (Feb–Apr 2026)
Exported by: Sarah Chen, Marketing Ops
Export date: 2026-03-01

Campaign Name                     | Type          | Channel          | Planned ($) | Actual ($) | Cost Type
----------------------------------|---------------|------------------|-------------|------------|----------
Spring Field Event — NYC          | Field Event   | FIELD_EVENT      | 45,000      | 41,200     | EVENT
Spring Field Event — NYC          | Field Event   | FIELD_EVENT      | 12,000      | 9,800      | AGENCY
LinkedIn ABM — Enterprise Q1      | Paid Social   | PAID_SOCIAL_LI   | 30,000      | 28,450     | MEDIA
LinkedIn ABM — Enterprise Q1      | Paid Social   | PAID_SOCIAL_LI   | 5,000       | 4,200      | CREATIVE
Google Search — Brand Q1          | Paid Search   | PAID_SEARCH      | 80,000      | 79,100     | MEDIA
Nurture Track — Mid-Market        | Email         | EMAIL_NURTURE    | 8,000       | 6,300      | CREATIVE
Content Synd — Gartner Q1         | Content Synd  | CONTENT_SYND     | 25,000      | [pending]  | MEDIA
[Agency spend — Ogilvy retainer]  | —             | —                | 15,000      | 14,800     | AGENCY ← CONFIDENTIAL

NOTE: Campaign IDs not included in this export. Mapping to Salesforce 
campaigns requires manual lookup by campaign name. Known mismatches:
  - "Spring Field Event — NYC" → SF Campaign: "NYC Spring Summit 2026" (name mismatch)
  - LinkedIn campaign names abbreviated differently in each system
```

**What the agent does with this:** The Allocadia data confirms the name-mismatch problem flagged in the Highspot doc. The agent surfaces this as a named transformation dependency — a campaign name normalization lookup table is required before spend can be joined to Salesforce revenue. This is a genuine modeling decision that would normally require a separate conversation with the Marketing Ops team.

---

### 3.5 Salesforce — CRM (Structured, Via Existing Snowflake Sync)

**What it is:** Already in Snowflake via the `mktg.salesforce_*` tables. Well-documented in Atlan. No additional connection needed.

**Key demo data point — the fiscal calendar mismatch in action:**

```sql
-- What an analyst would discover manually when they try to run a ROMI calc:
SELECT 
    YEAR(close_date) as calendar_year,   -- Returns 2025 for a Jan 2026 deal
    amount
FROM mktg.salesforce_opportunities
WHERE stage_name = 'Closed Won'
-- BUG: Jan 2026 deals land in FY2025 using calendar year
-- Correct approach requires joining to FINANCE.FISCAL_CALENDAR
-- This is the trap the agent warns about before they build
```

---

### 3.6 Email Thread — The Real Starting Point (Unstructured)

**What it is:** The demo opens with the actual trigger artifact that started this whole thing — a brief email from the VP of Marketing Operations to the analyst. This is what "requirements" look like in the real world before the DSA.

**Simulated email:**

```
FROM: Jennifer Moss <j.moss@company.com>
TO: analytics-team@company.com
DATE: March 24, 2026 — 9:14 AM
SUBJECT: ROMI Dashboard — can we get this built?

Hi team,

Coming out of the board meeting last week, there's a strong ask for 
better visibility into marketing ROI. Right now we're doing this 
manually every quarter and it takes weeks.

Can we get a data product built that shows ROMI by channel and campaign? 
Finance wants to be able to reproduce the numbers we show the board, 
and the campaign managers want to see their own performance without 
having to ask us every time.

Let me know what you need from me.

— Jen
```

**What the demo shows:** The agent opens with this email as the context. The PO (Jen, or played by the demo presenter) starts the requirements interview from here. By the end of the demo, that 3-sentence email has become a structured PRD with source mappings, metric definitions, governance rules, and a conceptual data model — and the agent surfaced 4 data quality issues, 2 access dependencies, and 1 fiscal calendar trap without the analyst opening a single other tab.

---

## 4. Demo Script — Key Moments

### Moment 1: The Interview Replaces the Blank Page (Step 1, ~3 min)
Agent opens: *"I found the email from Jennifer Moss from March 24th. Looks like the ask is ROMI visibility by channel and campaign — let me ask you a few questions to turn that into a structured product spec."*

The audience sees the PRD building in the right panel as the conversation progresses. No form. No template. Just answers becoming a document.

---

### Moment 2: The Source Discovery Surprise (Step 2–3 transition, ~2 min)
Analyst says they want to include LinkedIn spend data.

Agent: *"I checked the Snowflake schema — the LinkedIn Campaign Stats table doesn't exist yet. The connector hasn't been activated. I've flagged this as a dependency. Do you want to mark LinkedIn as Phase 2, or should we block the model on this?"*

The audience sees a flag appear in the artifact panel. The analyst didn't have to run a query.

---

### Moment 3: The Atlan Quality Flag (Step 3, ~1 min)
Agent proposes mapping spend to the Allocadia budget table.

Agent: *"I found the Allocadia budget table in Atlan — but I want to flag something. The table hasn't been refreshed in 80 days, and the campaign code field doesn't match Salesforce's campaign ID format. This join will need a name normalization lookup table. I've documented this as a transformation dependency."*

Audience sees the flag appear. The analyst nods. This is exactly the kind of thing they would have discovered three hours into building the model.

---

### Moment 4: The Gate (End of Step 1, ~1 min)
The PRD reaches 87% completeness. The gate banner appears.

Agent: *"The PRD is ready for review. Two open dependencies are documented — Workday Financials access and the LinkedIn connector. Everything else is resolved."*

The PO reviews the artifact panel, clicks Approve. The sidebar shows Step 1 complete. Step 2 unlocks. The audience sees a governance-gated workflow in action.

---

## 5. Simulated Source System Access Model

For the demo, the architect should simulate the following agent-to-source-system interactions. These do not need to be live API calls — they should be realistic mock responses that fire when the agent reaches the relevant point in the conversation.

| Source system | What the agent "calls" | What it returns | When it fires |
|---|---|---|---|
| Highspot | Search for docs matching "ROMI" or "marketing attribution" | Attribution methodology doc summary + fiscal calendar warning | When PO describes the business objective |
| Atlan | Search catalog for tables matching `campaign`, `opportunity`, `budget` | Table metadata cards for 3 matching tables, including quality scores | When analyst asks about source data |
| Snowflake | `SHOW TABLES IN SCHEMA MARKETING_DW.MKTG` | Table list with row counts and refresh dates | When agent proposes source mapping |
| Snowflake | `DESCRIBE TABLE finance.allocadia_budget` | Column list with no descriptions — triggers metadata gap flag | When agent maps Allocadia fields |
| Atlan | Fetch lineage for `finance.allocadia_budget` | No lineage found — triggers ownership flag | Same as above |

---

## 6. What the Demo Is Not

- It is not a live demo against real Workday data
- It is not a production-ready deployment
- It is not connected to real Atlan, real Snowflake, or real Highspot instances
- The ROMI data product is fictional — no real campaigns, no real spend figures

All data is simulated. All source system responses are pre-scripted mock responses that fire at the right moment in the conversation flow. The demo should feel real because the *problems* are real — the data quality issues, the join key mismatches, the fiscal calendar trap, the scattered documentation — these are things every data analyst recognizes immediately.

---

*Demo Requirements v1.0*  
*Owner: Judy Albeige, phData*
