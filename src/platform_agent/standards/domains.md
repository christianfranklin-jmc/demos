# Approved Data Domains (Pinnacle)

Pinnacle entities are tagged with one of these domains for filtering
on the Semantic page (US5) and for grouping in business-process
detection (US2).

| Domain | Pinnacle processes | Example entities |
|--------|--------------------|-------------------|
| `wealth_mgmt` | Portfolio Management & Trading, Performance & Asset Reporting | account, holding, strategy, aum_snapshot |
| `accounting` | Accounts Payable, Client Fee Billing & Revenue, General Ledger | ap_invoice, fee_invoice, journal_entry, gl_account |
| `crm` | CRM | client, advisor, meeting, opportunity, engagement_metric |
| `hr` | HR & Cost Management | employee, department, cost_center |
| `planning` | Financial Planning & Budgeting | budget_line, forecast_line, fiscal_period |

`unspecified` is used for non-Pinnacle datasets where the schema-name
heuristic does not match a Pinnacle process. The semantic graph
viewer's domain filter still works against `unspecified`.
