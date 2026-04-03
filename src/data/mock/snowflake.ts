import type { SourceContext } from "../../lib/types";

export const SNOWFLAKE_SCHEMA_TABLES: SourceContext = {
  type: "snowflake",
  title: "MARKETING_DW.MKTG — Table List",
  summary: "5 tables found in the MKTG schema. salesforce_opportunities and marketo_leads are current. allocadia_budget is stale. No LinkedIn Campaign Stats table exists — connector not activated.",
  metadata: {
    schema: "MARKETING_DW.MKTG",
    table_count: "5",
  },
  flags: [
    "linkedin_campaign_stats does NOT exist — connector has not been activated. Flag as dependency if LinkedIn spend is in scope.",
  ],
};

export const SNOWFLAKE_ALLOCADIA_DESCRIBE: SourceContext = {
  type: "snowflake",
  title: "DESCRIBE TABLE finance.allocadia_budget",
  summary: "7 columns. No descriptions on any column. Column names are abbreviated (prd, cmpgn_cd, cost_typ) — meaning must be inferred. cmpgn_cd format does not match Salesforce campaign ID format.",
  metadata: {
    columns: "id, line_item_nm, budget_amt, actual_amt, prd, cmpgn_cd, cost_typ",
    row_count: "~3,200",
    last_refresh: "2026-01-08",
  },
  flags: [
    "No column descriptions — all columns undocumented",
    "cmpgn_cd appears to be a campaign code but format differs from Salesforce Campaign.Id — name normalization lookup required",
    "prd appears to be a period code but format unknown — needs mapping to fiscal calendar",
  ],
};

export const SNOWFLAKE_FISCAL_CALENDAR: SourceContext = {
  type: "snowflake",
  title: "FINANCE.FISCAL_CALENDAR",
  summary: "Company fiscal calendar table. Feb–Jan year-end. Maps calendar dates to fiscal year, fiscal quarter, and fiscal month. Required for all date-based joins — do NOT use calendar year directly.",
  metadata: {
    schema: "FINANCE",
    row_count: "~2,500 (7 years of daily records)",
    last_refresh: "2026-03-01",
  },
  flags: [],
};

export function getSnowflakeContext(topic: string): SourceContext[] {
  const results: SourceContext[] = [];

  if (topic.includes("source") || topic.includes("table") || topic.includes("schema") || topic.includes("snowflake")) {
    results.push(SNOWFLAKE_SCHEMA_TABLES);
  }
  if (topic.includes("allocadia") || topic.includes("budget") || topic.includes("spend")) {
    results.push(SNOWFLAKE_ALLOCADIA_DESCRIBE);
  }
  if (topic.includes("fiscal") || topic.includes("calendar") || topic.includes("date")) {
    results.push(SNOWFLAKE_FISCAL_CALENDAR);
  }

  return results;
}
