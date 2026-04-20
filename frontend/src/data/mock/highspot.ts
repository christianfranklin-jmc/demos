import type { SourceContext } from "../../lib/types";

export const HIGHSPOT_ATTRIBUTION_METHODOLOGY: SourceContext = {
  type: "highspot",
  title: "Marketing Attribution Methodology v2.1",
  summary:
    "Marketing investment return is calculated quarterly by Marketing Ops using Allocadia budget exports, Salesforce opportunity reports, and Marketo lead data. Current process takes 3–4 weeks per quarter. Attribution is primary-source-based — each closed-won opportunity credited to one campaign. Influenced pipeline (any touch within 90 days) tracked separately for executive reporting.",
  metadata: {
    document_type: "Business Process Doc (Word)",
    last_updated: "2025-11-14",
    owner: "Marketing Operations",
  },
  flags: [
    "Allocadia and Salesforce campaign IDs are not consistently mapped — requires manual reconciliation",
    "Agency/vendor spend tracked in separate spreadsheets by channel owners — not systematically included in total spend",
    "Fiscal calendar is Feb–Jan year-end — does NOT match Salesforce default calendar year. All Salesforce reports must be manually adjusted.",
  ],
};

export const HIGHSPOT_QBR_DECK: SourceContext = {
  type: "highspot",
  title: "Q3 FY2026 Marketing QBR Deck — Slide 7",
  summary:
    "ROMI by Channel: Paid Search 2.4x, Field Events 1.1x, Email Nurture 3.8x, LinkedIn Paid Social 0.7x (below target). Numbers based on manual consolidation — Allocadia actuals as of Oct 15, Salesforce pipeline as of Oct 18. Figures are approximate.",
  metadata: {
    document_type: "Slide Deck (PowerPoint)",
    last_updated: "2025-10-22",
    owner: "VP Marketing Operations",
  },
  flags: [
    "Numbers based on manual consolidation — reconciliation was still in progress at time of presentation",
  ],
};

export function getHighspotContext(topic: string): SourceContext[] {
  const results: SourceContext[] = [];

  if (
    topic.includes("romi") ||
    topic.includes("attribution") ||
    topic.includes("marketing roi") ||
    topic.includes("business objective")
  ) {
    results.push(HIGHSPOT_ATTRIBUTION_METHODOLOGY);
  }
  if (topic.includes("qbr") || topic.includes("channel") || topic.includes("benchmark")) {
    results.push(HIGHSPOT_QBR_DECK);
  }

  return results;
}
