import type { SourceContext } from "../../lib/types";

/**
 * Simulated Atlan catalog search results.
 * These fire when the agent reaches source system discovery in the conversation.
 */

export const ATLAN_SALESFORCE_OPPORTUNITIES: SourceContext = {
  type: "atlan",
  title: "mktg.salesforce_opportunities",
  summary:
    "Salesforce opportunity data synced daily via Fivetran. Contains all opportunities created after 2022-01-01. Primary source of truth for pipeline and revenue metrics.",
  quality_score: 87,
  metadata: {
    owner: "Marketing Data Team",
    last_updated: "2026-03-15",
    row_count: "~142,000",
    refresh: "Daily via Fivetran",
  },
  flags: [
    "primary_campaign_id: 23% NULL rate — known gap for sales-sourced pipeline",
    "amount: 4 records with $0 value — likely test records, filter with amount > 0",
  ],
};

export const ATLAN_ALLOCADIA_BUDGET: SourceContext = {
  type: "atlan",
  title: "finance.allocadia_budget",
  summary:
    "Allocadia budget data. No description provided. Last owner left company. Table has not been refreshed in 80+ days.",
  quality_score: 41,
  metadata: {
    owner: "Unknown (last owner left company)",
    last_updated: "2026-01-08",
    row_count: "~3,200",
    refresh: "Unknown — pipeline not documented",
  },
  flags: [
    "No column descriptions — ownership gap",
    "Last refresh 80+ days ago — may not reflect current actuals",
    "cmpgn_cd format does not match Salesforce primary_campaign_id format — join key TBD",
    "No lineage documented — source pipeline unknown",
  ],
};

export const ATLAN_MARKETO_LEADS: SourceContext = {
  type: "atlan",
  title: "mktg.marketo_leads",
  summary:
    "Marketo lead records synced nightly. Contains all leads from 2021 onward. MQL threshold = 85.",
  quality_score: 79,
  metadata: {
    owner: "Marketing Ops (Automated)",
    last_updated: "2026-03-29",
    row_count: "~89,000",
    refresh: "Nightly sync",
  },
  flags: [
    "lead_source_campaign is a name string, NOT a campaign ID — requires fuzzy match to join to Salesforce campaigns",
    "email field is PII — masked in all downstream views",
  ],
};

/**
 * Returns relevant Atlan context based on the current conversation topic.
 */
export function getAtlanContext(topic: string): SourceContext[] {
  const results: SourceContext[] = [];

  if (topic.includes("opportunity") || topic.includes("revenue") || topic.includes("pipeline")) {
    results.push(ATLAN_SALESFORCE_OPPORTUNITIES);
  }
  if (topic.includes("budget") || topic.includes("spend") || topic.includes("allocadia")) {
    results.push(ATLAN_ALLOCADIA_BUDGET);
  }
  if (topic.includes("lead") || topic.includes("mql") || topic.includes("marketo")) {
    results.push(ATLAN_MARKETO_LEADS);
  }

  return results;
}
