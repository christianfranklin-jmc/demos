import type { SourceContext } from "../../lib/types";

/**
 * Simulated Allocadia budget export data.
 * In the real world, this would be a spreadsheet maintained by channel owners.
 * The agent surfaces the name-mismatch problem when mapping spend to Salesforce.
 */

export const ALLOCADIA_BUDGET_EXPORT: SourceContext = {
  type: "allocadia",
  title: "Allocadia Budget Export — FY2026 Q1",
  summary:
    "Campaign-level budget vs. actual export from Allocadia. 8 line items across 5 campaigns. Campaign IDs not included — mapping to Salesforce requires manual lookup by campaign name. Known name mismatches between systems.",
  metadata: {
    export_date: "2026-03-20",
    fiscal_period: "FY2026 Q1",
    line_item_count: "8",
    total_planned: "$220,000",
    total_actual: "$183,850 (partial — Content Synd pending)",
  },
  flags: [
    "Campaign IDs not included in export — mapping to Salesforce campaigns requires manual name lookup",
    "'Spring Field Event — NYC' maps to SF Campaign 'NYC Spring Summit 2026' (name mismatch)",
    "LinkedIn campaign names abbreviated differently in each system",
    "Agency spend line (Ogilvy retainer) is CONFIDENTIAL — vendor name must not surface in Campaign Manager views",
    "Content Syndication — Gartner Q1 actual spend marked as [pending]",
  ],
};

/**
 * Raw budget line items for demo display in the artifact panel.
 */
export const ALLOCADIA_LINE_ITEMS = [
  {
    campaign_name: "Spring Field Event — NYC",
    type: "Field Event",
    channel: "FIELD_EVENT",
    planned: 45000,
    actual: 41200,
    cost_type: "EVENT",
  },
  {
    campaign_name: "Spring Field Event — NYC",
    type: "Field Event",
    channel: "FIELD_EVENT",
    planned: 12000,
    actual: 9800,
    cost_type: "AGENCY",
  },
  {
    campaign_name: "LinkedIn ABM — Enterprise Q1",
    type: "Paid Social",
    channel: "PAID_SOCIAL_LI",
    planned: 30000,
    actual: 28450,
    cost_type: "MEDIA",
  },
  {
    campaign_name: "LinkedIn ABM — Enterprise Q1",
    type: "Paid Social",
    channel: "PAID_SOCIAL_LI",
    planned: 5000,
    actual: 4200,
    cost_type: "CREATIVE",
  },
  {
    campaign_name: "Google Search — Brand Q1",
    type: "Paid Search",
    channel: "PAID_SEARCH",
    planned: 80000,
    actual: 79100,
    cost_type: "MEDIA",
  },
  {
    campaign_name: "Nurture Track — Mid-Market",
    type: "Email",
    channel: "EMAIL_NURTURE",
    planned: 8000,
    actual: 6300,
    cost_type: "CREATIVE",
  },
  {
    campaign_name: "Content Synd — Gartner Q1",
    type: "Content Synd",
    channel: "CONTENT_SYND",
    planned: 25000,
    actual: null, // pending
    cost_type: "MEDIA",
  },
  {
    campaign_name: "[Agency spend — Ogilvy retainer]",
    type: "—",
    channel: "—",
    planned: 15000,
    actual: 14800,
    cost_type: "AGENCY",
    confidential: true,
  },
];

/**
 * Campaign name normalization map — demonstrates the mismatch problem.
 */
export const CAMPAIGN_NAME_MISMATCHES = [
  {
    allocadia_name: "Spring Field Event — NYC",
    salesforce_name: "NYC Spring Summit 2026",
    resolution: "Lookup table required — manual mapping",
  },
  {
    allocadia_name: "LinkedIn ABM — Enterprise Q1",
    salesforce_name: "LI Enterprise ABM Campaign - Q1 FY26",
    resolution: "Abbreviated differently — fuzzy match or lookup",
  },
  {
    allocadia_name: "Nurture Track — Mid-Market",
    salesforce_name: "Mid-Market Email Nurture FY26",
    resolution: "Name structure differs — lookup table",
  },
];
