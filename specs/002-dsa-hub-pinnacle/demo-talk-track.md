# Demo talk track — DSA Hub × Pinnacle Financial

8-minute showcase narrative. Stage directions are the bullets, **bold lines are what to say**.

---

## 0. Pre-demo (do this 10 min before)

- Ensure backend is up: `curl -s http://localhost:8080/health` returns `{"mode":"local",...}`. If not, kill stale `uvicorn` PIDs and restart with `uv run uvicorn platform_agent.api.app:app --host 0.0.0.0 --port 8080 --reload`. (We hit a stale process today — `--reload` can miss new top-level imports added since startup.)
- Ensure frontend is up: `cd frontend && pnpm dev`. Open `http://localhost:5173` in a fresh tab so the workspace UUID is clean.
- Open the **Connections** page first, **before** the audience joins. Pre-clicking saves the SSO browser handshake from happening live.
- Have `DSA_HUB_DEMO_MODE=1` ready as a single-command fallback if AWS or Snowflake misbehaves: `DSA_HUB_DEMO_MODE=1 pnpm dev`.
- Keep a second terminal on `tail -f /tmp/uvicorn.log` so backend errors surface fast.

**Known rough edges (all fixed today, mention only if asked):**
- Manual Snowflake add now defaults schema to `ANALYTICS` (was `PUBLIC` — silently scanned an empty schema and showed "Live · 0 tables").
- Workspace KPI strip now sums per-driver `row_count` (was looking for a key only the Iceberg driver emitted).
- Connection cards now show an amber alert if a Live connection scanned 0 tables, naming the scope so a schema typo can't masquerade as healthy.

---

## 1. Frame the problem (≈45 s, no clicks)

**"Most data platforms make you pick one source and live in it. Pinnacle's reality is the opposite: client AUM lives in the Snowflake analytical mirror, fee billing and trade ops live in operational Postgres, and the team that owns *Client 360* needs both — governed, joinable, with the same business keys. Today I'll take a fresh workspace and stand up a Client 360 data product across both warehouses, into a governed Iceberg table, in under 8 minutes."**

> If asked "why Iceberg?" — *open table format, Glue catalog, queryable from Snowflake/Athena/Spark/dbt without a copy. The semantic layer points at Iceberg, not at the source.*

---

## 2. Connections page — wire two sources (≈60 s)

Click the 🌐 **Connections** view in the sidebar.

- Show the empty workspace. Point at the KPI strip: `SOURCES CONNECTED 0`.
- Click the **Pinnacle PG** preset button. Card appears with status `Connecting…` → `Scanning…` → `Live`. Tables fill in to **34**.
- Click the **Pinnacle SF** preset button. Same lifecycle. Tables fill in.

**"Two clicks. Each preset reads server-side `.env` credentials — they never round-trip the browser. Notice the KPI strip rolling up: 2 sources, 34 + N tables, rows estimated. The connection ID is deterministic from `(driver, endpoint, scope)` — close this tab, reopen, the durable per-connection state reattaches."**

> If a card shows "Live · 0 tables" with the new amber alert, **don't panic** — say *"That alert is exactly the schema-mismatch guardrail we added; the scan succeeded but found nothing in the named schema. We'd remove and re-add with the right schema name."* Then click Remove → preset.

---

## 3. Discovery — schema-grounded business processes (≈90 s)

Click the 🧭 **Discovery** view.

- Page renders the KPI tiles, then the **8 detected business processes** (AP, billing, CRM, GL, HR, performance, planning, portfolio).
- Scroll to the **cross-source coverage matrix** — point at one row that has cells in both PG and SF.
- Scroll to the **Pilled PRDs** section — 6 schema-grounded chips appear (Client 360, Fee Attribution, Advisor Productivity, etc.).

**"Discovery ran against the live schemas. Every one of those processes was inferred from FK graphs and column-name heuristics, not a hand-curated list — point your hub at any database and the same shape comes back. The pills are pre-drafted PRDs that span both sources. Each one already knows which Postgres tables and which Snowflake tables it'll need."**

> If asked "what's in a pill?" — *title, target Iceberg table, estimated build minutes, the standards it'll apply (kimball, snake_case, Iceberg, MetricFlow), and a body that names every source table it joins.*

---

## 4. Click the pill — Build page lights up (≈90 s)

Click the **Client 360** pill.

- Pill spins ("Drafting PRD…"). On success, app navigates to the 🛠 **Build** view.
- The **7-agent DAG** renders: `schema → pipeline → model → quality → mapping → {semantic, delivery}`.
- Each node ticks through `pending → running → succeeded` over a few seconds. Watch the SSE event stream populate the activity log on the right.

**"That click triggered `/workflow/provision`. The DAG you're seeing is real — schema_agent introspects both connections, pipeline_agent runs the source pulls and writes Parquet, model_agent shapes the dimensional model, quality_agent runs the DQDL checks, mapping_agent links to the semantic graph, and the last two run in parallel — semantic_agent registers the new entity, delivery_agent promotes the Iceberg product. Each agent has its own retry; if one fails, only that node re-runs."**

> If a node goes red: click **Retry** on that node. If validation falls below the 80 % threshold, the run is flagged `needs_replan` instead of `final` — that's the gate that protects the Iceberg product.

---

## 5. Validation card — the threshold gate (≈30 s)

The **Validation Card** auto-runs the PRD's three business questions against the new product.

- Watch each question turn green with a row count + sample answer.
- Footer flips to: `Validated 3 / 3 (100 %) → product registered as final.`

**"This is Q5 — the validation threshold. The product doesn't get exposed to downstream consumers as `final` until at least 80 % of the PRD's named questions resolve. Below that, it lands as `provisional` and the user is asked to replan."**

---

## 6. Cross-source TTYD — the payoff (≈90 s)

Switch the **lens selector** in the context bar to "All Pinnacle sources".

Open the artifact panel's **Talk to Data** tab. Type:

> *"Show me Q1 advisor productivity with AUM growth and meeting count, ranked."*

- Response renders **source chips**: one per source pull (PG and SF), one for the DuckDB scratchpad join, one for the new Iceberg product.
- Each chip shows row counts; a truncated chip would be amber. Highlight the row counts.

**"The query plan ran two read-only pulls — 250 rows max from each — into an in-process DuckDB scratchpad, joined them on the shared `advisor_id` business key, and answered. The hub never copies bulk data; it's a federated read with a hard 5,000-row join cap so a runaway query can't blow up the session. And because the Client 360 product we just built is now an Iceberg table, the next person who asks the same question hits that, not the federation."**

> If TTYD errors with `read_only_violation` — *"that's the safety net working — the planner attempted a write and the gateway rejected it."*

---

## 7. Semantic Graph — show the governance layer (≈30 s, optional if time)

Click the 🕸 **Semantic** view.

- React Flow graph renders entities + joins for the selected connection.
- Hover an entity, show its physical bindings + metric registrations.

**"Every product, every metric, every join lives in the semantic graph for the connection it belongs to. The Standards page" — click 📚 — "is the read-only catalog of naming conventions, metric definitions, PII policy, dbt templates, domains, and Iceberg standards that the build agents enforced. The pill footer at Discovery cites which of these were applied."**

---

## 8. Land the close (≈30 s, no clicks)

**"What you saw: a fresh workspace, two presets, one pill click, an end-to-end provision into Iceberg, validation, and a federated cross-source query — all in under 8 minutes. The pieces that made it fast: deterministic connection identity, agent-per-step retries, the validation threshold gate, the semantic-graph layer that lets the next product reuse what this one built. Where we go next: swap the deterministic v1 agents for Strands LLM agents along the swap-paths we already reserved, and run the same demo on a customer's actual two warehouses."**

---

## Q&A cheat sheet

| Question | One-line answer |
|---|---|
| "How is connection state persisted?" | Per-connection `ConnectionStore` — SQLite locally under `~/.dsa-hub/connections/<id>/`, DynamoDB in deployed mode. |
| "What if I close the tab?" | Workspace is per-tab and ephemeral. Connection durable state survives and reattaches when the same `(driver, endpoint, scope)` is re-added. |
| "Where do credentials live?" | Process-local in-memory cache keyed by `(session_uuid, connection_id)`. Never hit disk, never round-trip the browser, dropped on Remove. |
| "What's the Iceberg write path?" | `pyiceberg.create_table()` against the Glue catalog DB, Parquet files written to the configured S3 warehouse URI. Demo runs against a Glue DB Terraform pre-provisions. |
| "Can it do schema drift?" | EventBridge rule fires on schema change → schema_agent re-runs → re-enrichment + downstream re-validation. Shown in deployed mode only. |
| "Why DuckDB and not Athena for federation?" | TTYD is a session-bound interactive path, not a workload — DuckDB in-process gives sub-second joins on the row caps without round-tripping AWS. The Iceberg product *is* the persisted answer. |
| "What's deferred for the LLM swap?" | pill-agent, redundancy-agent, semantic-agent, delivery-agent, NL→SQL planner. All have ADR-reserved swap paths (ADR-018 / 019 / 021 D2). v1 ships deterministic; eval cases land with the swap. |
| "How accurate is process detection?" | Heuristic + named-pill catalog for Pinnacle. Generic schemas fall back to FK-graph clustering. We've validated against the Pinnacle 8-process layout end-to-end. |
| "What's the test coverage?" | 144 pytest + 18 vitest, mypy strict + ruff clean across all new modules. |

---

## If something goes wrong live

| Symptom | Quickest recovery |
|---|---|
| Standards tab shows `404` | Backend wasn't restarted after a code change. `kill <uvicorn pid>` + restart, or fall back to demo mode. |
| Snowflake card stuck `Connecting…` | SSO browser tab is waiting for click in the background — bring it forward. |
| Snowflake card `Live · 0 tables` | Schema name mismatch. Click Remove, re-add with `Schema = ANALYTICS`. The amber alert on the card now names the scope, so this is a 5-second recovery. |
| Build DAG red | Click the failed node → Retry. If it persists, fall back: `DSA_HUB_DEMO_MODE=1` reproduces the full narrative offline. |
| TTYD returns no rows | Lens still set to a single source. Set it to "All Pinnacle sources" in the context bar. |
| Browser tab feels stuck on Discovery | Hit the **Re-discover** button top-right; the discovery payload is cacheable but the refresh path is idempotent. |
