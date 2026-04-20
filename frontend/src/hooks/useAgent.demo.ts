/**
 * useAgent — Manages the agent conversation flow across all 4 steps.
 *
 * The agent is proactive: it thinks ahead about what the user needs next,
 * guides them through each step without requiring them to know the process,
 * and surfaces relevant context from mock source systems inline.
 *
 * Each step has its own opening message and interview flow.
 * The agent transitions between steps automatically after gate approval.
 */

import { useEffect, useRef } from "react";
import { useAppState } from "../context/AppContext";
import { TIMING } from "../lib/constants";
import type { StepNumber, ConversationMessage } from "../lib/types";

// ─── Types ───

interface InterviewStep {
  field: string;
  agentMessage: string;
  suggestedReplies?: string[];
  artifactUpdate?: (userText: string) => any;
}

interface StepFlow {
  openingMessage: ConversationMessage;
  steps: InterviewStep[];
}

// ─── Step 1: Requirements Interview ───

const STEP1_OPENING: ConversationMessage = {
  data_product_id: "dp-romi-001",
  step: 1,
  message_role: "agent",
  message_text:
    `I've picked up Jennifer Moss's email requesting a ROMI dashboard for Marketing Ops. Let's turn that into a structured requirements document.\n\nI'll walk you through the key questions — your PRD will build automatically in the right panel as we go.\n\nFirst: what's the core business objective? What problem should this ROMI data product solve?`,
  timestamp: "",
  suggested_replies: [
    "Track marketing ROI by channel",
    "Replace the manual quarterly process",
    "Enable real-time spend optimization",
  ],
};

const STEP1_FLOW: InterviewStep[] = [
  {
    field: "business_objective",
    agentMessage:
      `Got it — I've captured that as the business objective.\n\nI found a relevant document in Highspot: the Marketing Attribution Methodology v2.1 confirms the current process takes 3–4 weeks per quarter using manual consolidation from Allocadia, Salesforce, and Marketo.\n\nNow — who are the primary consumers of this data product? Who will use this daily or weekly?`,
    suggestedReplies: ["Marketing Ops team", "VP Marketing + Channel Managers", "Finance and Marketing jointly"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: {
        business_objective: text,
        current_state_pain: "Manual quarterly ROMI process takes 3–4 weeks. Data scattered across Allocadia, Salesforce, and Marketo with no consistent mapping.",
      },
    }),
  },
  {
    field: "consumers",
    agentMessage: `I've added them as primary consumers.\n\nWhat key decisions should this data product enable? Think about what changes when people have reliable ROMI data at their fingertips.`,
    suggestedReplies: ["Reallocate budget across channels", "Kill underperforming campaigns faster", "Justify marketing spend to the CFO"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: { primary_consumers: [{ persona: text, role: "Primary Consumer", access_level: "Full" }] },
    }),
  },
  {
    field: "decisions_enabled",
    agentMessage: `Great — those decisions frame the scope perfectly.\n\nNow the critical question: what's the primary grain? At what level do you need to see ROMI — by campaign? By channel? By individual spend line item?\n\nThis drives every join and aggregation downstream, so it's worth getting right.`,
    suggestedReplies: ["Campaign level", "Channel + Campaign", "Individual spend line item"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: { decisions_enabled: text.includes(",") ? text.split(",").map((s: string) => s.trim()) : [text] },
    }),
  },
  {
    field: "grain",
    agentMessage: `I've captured the grain.\n\nOne flag from Highspot: Workday uses a Feb–Jan fiscal calendar, which doesn't match Salesforce's default calendar year. All time-based joins will need fiscal period mapping.\n\nWhat time range and refresh cadence do you need? How far back should the data go?`,
    suggestedReplies: ["24 months history, weekly refresh", "12 months, daily refresh", "Full history, monthly snapshot"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: {
        grain_statement: text.toLowerCase().includes("campaign") ? "One row per campaign per fiscal period" : `One row per ${text.toLowerCase()} per fiscal period`,
      },
    }),
  },
  {
    field: "time_range",
    agentMessage: `Time range captured.\n\nNow let's define the key metrics — the 3–5 most important calculations this product should support. What goes on the executive dashboard?`,
    suggestedReplies: ["ROMI ratio, spend, revenue, CPL", "ROI, pipeline influenced, cost per MQL", "Let me list them one by one"],
    artifactUpdate: (text: string) => {
      const parts = text.split(",").map((s: string) => s.trim());
      return {
        type: "UPDATE_PRD",
        updates: {
          time_range: { historical_coverage: parts[0] || text, refresh_cadence: parts[1] || "Weekly", snapshot_logic: "Fiscal period snapshots", fiscal_calendar: "Feb–Jan fiscal year" },
        },
      };
    },
  },
  {
    field: "key_metrics",
    agentMessage: `Metrics added.\n\nI checked Atlan for source system availability:\n• ✅ mktg.salesforce_opportunities — quality 87/100, daily refresh\n• ⚠️ finance.allocadia_budget — quality 41/100, stale 80+ days, no owner\n• ⚠️ Campaign codes don't match Salesforce IDs — needs normalization\n\nWhat are the primary source systems?`,
    suggestedReplies: ["Salesforce, Allocadia, Marketo", "Salesforce + Allocadia only for MVP", "Add LinkedIn Ads too"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: {
        key_metrics: text.split(",").map((s: string) => s.trim()).map((name: string) => ({
          name, definition: `${name} as defined by Marketing Ops`, formula: null, priority: "MVP" as const,
        })),
      },
    }),
  },
  {
    field: "source_systems",
    agentMessage: `Sources captured. The Allocadia quality issue is flagged.\n\nAlmost there — what does success look like? How will you know this data product is working?`,
    suggestedReplies: ["Numbers match the manual QBR within 5%", "ROMI available in hours, not weeks", "CFO trusts numbers for board reporting"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: {
        source_systems: text.split(",").map((s: string) => s.trim()).map((sys: string) => ({
          system: sys, data_domain: sys.toLowerCase().includes("salesforce") ? "Pipeline & Revenue" : sys.toLowerCase().includes("allocadia") ? "Budget & Spend" : "Leads & MQLs", access_confirmed: sys.toLowerCase().includes("salesforce") ? true : null,
        })),
      },
    }),
  },
  {
    field: "success_criteria",
    agentMessage: `Success criteria captured.\n\nLast question: any compliance, security, or governance constraints? Think PII, data masking, access controls.`,
    suggestedReplies: ["No PII in the product layer", "Standard data governance", "Finance data restricted to director+"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: { success_criteria: text },
    }),
  },
  {
    field: "constraints",
    agentMessage: `Constraints documented.\n\nThe PRD is at 87% completeness — I've captured business objective, consumers, grain, time range, metrics, sources, success criteria, and constraints.\n\nScroll down in the artifact panel to review and approve. You can also click any field to edit inline.`,
    suggestedReplies: ["Looks good, ready for review", "Let me review the artifact first", "I want to add more metrics"],
    artifactUpdate: (text: string) => ({
      type: "UPDATE_PRD",
      updates: {
        constraints: text,
        scope_in: ["ROMI by campaign", "Source system mapping", "Fiscal calendar alignment"],
        scope_out: ["Real-time streaming", "Predictive modeling", "Multi-touch attribution (Phase 2)"],
      },
    }),
  },
];

// ─── Step 2: Conceptual Model ───

const STEP2_OPENING: ConversationMessage = {
  data_product_id: "dp-romi-001",
  step: 2,
  message_role: "agent",
  message_text:
    `PRD approved — great work. Now let's build the conceptual data model.\n\nBased on your PRD, I'm thinking this is a dimensional model with a central fact table for campaign performance. I've already identified the key entities from your requirements.\n\nLet me propose the fact table first: should the central fact be "campaign performance by fiscal period" or something different?`,
  timestamp: "",
  suggested_replies: ["Campaign performance works", "Campaign spend + outcomes separately", "Start with the dimensions first"],
};

const STEP2_FLOW: InterviewStep[] = [
  {
    field: "fact_table",
    agentMessage: `I've created the fact table: fact_campaign_performance.\n\nNow for dimensions — based on your grain and metrics, I'm proposing these dimension tables:\n• dim_campaign — campaign attributes and metadata\n• dim_channel — marketing channel hierarchy\n• dim_date — fiscal calendar mapping (Feb–Jan)\n\nDoes this look right, or should we add more dimensions? Product line and geography are common additions.`,
    suggestedReplies: ["Add product line and geography", "Those three are enough for MVP", "Add a vendor dimension too"],
    artifactUpdate: () => ({
      type: "SET_CONCEPTUAL_MODEL",
      model: {
        entities: [
          { entity_id: "e1", entity_name: "fact_campaign_performance", role: "FACT" as const, description: "Campaign performance metrics by fiscal period", abstract_attributes: ["Spend metrics (planned, actual, variance)", "Pipeline and revenue metrics", "Key performance indicators (ROMI, CPL, CPA)"], cardinality_hint: "One row per campaign × channel × fiscal month" },
        ],
        relationships: [],
      },
    }),
  },
  {
    field: "dimensions",
    agentMessage: `Updated the model with all five dimensions. The entity cards are building in the right panel.\n\nNow I need to confirm the relationships. Here's what I'm proposing:\n• fact_campaign_performance → belongs to → dim_campaign\n• fact_campaign_performance → attributed to → dim_channel\n• fact_campaign_performance → occurs in → dim_date\n• fact_campaign_performance → targets → dim_product_line\n• fact_campaign_performance → covers → dim_geography\n\nDo these relationships capture the right business semantics?`,
    suggestedReplies: ["Yes, those are correct", "Campaign should link to channel differently", "Add a relationship to a lead/MQL entity"],
    artifactUpdate: () => ({
      type: "SET_CONCEPTUAL_MODEL",
      model: {
        entities: [
          { entity_id: "e1", entity_name: "fact_campaign_performance", role: "FACT" as const, description: "Campaign performance metrics by fiscal period", abstract_attributes: ["Spend metrics (planned, actual, variance)", "Pipeline and revenue metrics", "ROMI, CPL, CPA calculations"], cardinality_hint: "One row per campaign × channel × fiscal month" },
          { entity_id: "e2", entity_name: "dim_campaign", role: "DIM" as const, description: "Campaign master data from Salesforce", abstract_attributes: ["Campaign name and type", "Start/end dates and status", "Budget allocation tier"], cardinality_hint: null },
          { entity_id: "e3", entity_name: "dim_channel", role: "DIM" as const, description: "Marketing channel hierarchy", abstract_attributes: ["Channel name and category", "Channel group (paid, owned, earned)", "Cost center mapping"], cardinality_hint: null },
          { entity_id: "e4", entity_name: "dim_date", role: "REF" as const, description: "Fiscal calendar (Feb–Jan year-end)", abstract_attributes: ["Fiscal year, quarter, month", "Calendar-to-fiscal mapping", "Business day indicators"], cardinality_hint: null },
          { entity_id: "e5", entity_name: "dim_product_line", role: "DIM" as const, description: "Product line hierarchy", abstract_attributes: ["Product line name", "Business unit", "Revenue category"], cardinality_hint: null },
          { entity_id: "e6", entity_name: "dim_geography", role: "DIM" as const, description: "Geographic targeting regions", abstract_attributes: ["Region and sub-region", "Country and market", "Sales territory mapping"], cardinality_hint: null },
        ],
        relationships: [
          { from_entity: "fact_campaign_performance", verb: "belongs to", to_entity: "dim_campaign" },
          { from_entity: "fact_campaign_performance", verb: "attributed to", to_entity: "dim_channel" },
          { from_entity: "fact_campaign_performance", verb: "occurs in", to_entity: "dim_date" },
          { from_entity: "fact_campaign_performance", verb: "targets", to_entity: "dim_product_line" },
          { from_entity: "fact_campaign_performance", verb: "covers", to_entity: "dim_geography" },
        ],
      },
    }),
  },
  {
    field: "relationships_review",
    agentMessage: `The conceptual model is complete — 1 fact table and 5 dimensions with clear relationships.\n\nI've already thought ahead to Step 3: the Allocadia campaign code mismatch and the missing LinkedIn connector will become flags during logical modeling. Better to know that now.\n\nScroll down in the artifact panel to review and approve the conceptual model.`,
    suggestedReplies: ["Approve — move to logical model", "I want to add a comments section", "Let me check the relationships tab first"],
    artifactUpdate: () => null, // No artifact change, just gate activation
  },
];

// ─── Step 3: Logical Model ───

const STEP3_OPENING: ConversationMessage = {
  data_product_id: "dp-romi-001",
  step: 3,
  message_role: "agent",
  message_text:
    `Conceptual model approved. Now let's expand it into the logical model with actual field definitions, data types, and source mappings.\n\nI'll start with the fact table since it's the most complex. I've already mapped several fields from Salesforce and Allocadia based on what Atlan tells me about the source schemas.\n\nLet me show you what I've got for the keys and identifiers — are these the right source fields?`,
  timestamp: "",
  suggested_replies: ["Show me what you've mapped", "Start with the spend metrics instead", "What flags have you found so far?"],
};

const STEP3_FLOW: InterviewStep[] = [
  {
    field: "fact_fields",
    agentMessage: `I've mapped the initial fields for fact_campaign_performance.\n\nTwo flags I need your input on:\n\n⚠️ Grain Ambiguity — Allocadia's 'prd' column appears to be a period code, but the format doesn't match our fiscal calendar. We need to confirm the mapping logic.\n\n⚠️ Missing Source — LinkedIn Campaign Stats table doesn't exist in Snowflake yet. The connector hasn't been activated.\n\nShould I flag LinkedIn as a Phase 2 dependency, or is it a blocker?`,
    suggestedReplies: ["Phase 2 — not a blocker", "It's a blocker, we need it for MVP", "Defer and flag for follow-up"],
    artifactUpdate: () => ({
      type: "SET_LOGICAL_MODEL",
      model: {
        entities: [
          {
            entity_name: "fact_campaign_performance", role: "FACT" as const,
            attributes: [
              { target_field: "campaign_key", data_type: "INT", source_field: null, transformation_rule: "Hash of campaign_id + channel_code + fiscal_month_key", flag: null },
              { target_field: "campaign_id", data_type: "VARCHAR(50)", source_field: "Campaign.Id", transformation_rule: "Direct map from Salesforce", flag: null },
              { target_field: "channel_code", data_type: "VARCHAR(20)", source_field: null, transformation_rule: "FK lookup via campaign_channel mapping", flag: null },
              { target_field: "fiscal_month_key", data_type: "INT", source_field: null, transformation_rule: "FK to dim_date on fiscal_month_start_date", flag: null },
              { target_field: "planned_spend", data_type: "DECIMAL(18,2)", source_field: "allocadia_budget.budget_amt", transformation_rule: "Sum of line items by campaign period", flag: "grain_ambiguity" as const },
              { target_field: "actual_spend", data_type: "DECIMAL(18,2)", source_field: "allocadia_budget.actual_amt", transformation_rule: "Sum of actual amounts by campaign period", flag: "grain_ambiguity" as const },
              { target_field: "leads_generated", data_type: "INT", source_field: "marketo_leads.lead_id", transformation_rule: "COUNT where lead_source_campaign matches", flag: "naming_conflict" as const },
              { target_field: "opportunities_created", data_type: "INT", source_field: "salesforce_opportunities.opportunity_id", transformation_rule: "COUNT where primary_campaign matches", flag: null },
              { target_field: "attributed_revenue", data_type: "DECIMAL(18,2)", source_field: "salesforce_opportunities.amount", transformation_rule: "SUM where stage = Closed Won", flag: null },
              { target_field: "linkedin_spend", data_type: "DECIMAL(18,2)", source_field: null, transformation_rule: "Pending connector activation", flag: "missing_source" as const },
            ],
          },
        ],
        flags: [
          { flag_id: "f1", data_product_id: "dp-romi-001", step: 3, flag_type: "grain_ambiguity" as const, description: "Allocadia 'prd' column format doesn't match fiscal calendar. Period mapping logic TBD.", status: "open" as const, resolution: null, resolved_by: null, resolved_at: null, created_at: new Date().toISOString() },
          { flag_id: "f2", data_product_id: "dp-romi-001", step: 3, flag_type: "missing_source" as const, description: "LinkedIn Campaign Stats table does not exist in Snowflake. Connector not activated.", status: "open" as const, resolution: null, resolved_by: null, resolved_at: null, created_at: new Date().toISOString() },
          { flag_id: "f3", data_product_id: "dp-romi-001", step: 3, flag_type: "naming_conflict" as const, description: "Marketo lead_source_campaign is a name string, not a campaign ID. Requires fuzzy match or lookup table.", status: "open" as const, resolution: null, resolved_by: null, resolved_at: null, created_at: new Date().toISOString() },
        ],
      },
    }),
  },
  {
    field: "flag_resolution",
    agentMessage: `Good call. I've deferred LinkedIn to Phase 2 and resolved that flag.\n\nFor the Allocadia period mapping — I'm proposing we create a lookup table that maps Allocadia's 'prd' codes to our fiscal calendar. The Analytics Engineer can build this during implementation.\n\nThe Marketo naming conflict still needs resolution. Should we build a name-to-ID lookup table, or is there a better approach?`,
    suggestedReplies: ["Build a lookup table", "Use fuzzy matching", "Ask Marketing Ops for the mapping file"],
    artifactUpdate: () => ({
      type: "SET_LOGICAL_MODEL",
      model: {
        entities: [
          {
            entity_name: "fact_campaign_performance", role: "FACT" as const,
            attributes: [
              { target_field: "campaign_key", data_type: "INT", source_field: null, transformation_rule: "Hash of campaign_id + channel_code + fiscal_month_key", flag: null },
              { target_field: "campaign_id", data_type: "VARCHAR(50)", source_field: "Campaign.Id", transformation_rule: "Direct map from Salesforce", flag: null },
              { target_field: "channel_code", data_type: "VARCHAR(20)", source_field: null, transformation_rule: "FK lookup via campaign_channel mapping", flag: null },
              { target_field: "fiscal_month_key", data_type: "INT", source_field: null, transformation_rule: "FK to dim_date on fiscal_month_start_date", flag: null },
              { target_field: "planned_spend", data_type: "DECIMAL(18,2)", source_field: "allocadia_budget.budget_amt", transformation_rule: "Sum of line items by campaign period", flag: null },
              { target_field: "actual_spend", data_type: "DECIMAL(18,2)", source_field: "allocadia_budget.actual_amt", transformation_rule: "Sum of actual amounts by campaign period", flag: null },
              { target_field: "leads_generated", data_type: "INT", source_field: "marketo_leads.lead_id", transformation_rule: "COUNT where lead_source_campaign matches", flag: "naming_conflict" as const },
              { target_field: "opportunities_created", data_type: "INT", source_field: "salesforce_opportunities.opportunity_id", transformation_rule: "COUNT where primary_campaign matches", flag: null },
              { target_field: "attributed_revenue", data_type: "DECIMAL(18,2)", source_field: "salesforce_opportunities.amount", transformation_rule: "SUM where stage = Closed Won", flag: null },
              { target_field: "linkedin_spend", data_type: "DECIMAL(18,2)", source_field: null, transformation_rule: "Phase 2 — connector pending", flag: null },
            ],
          },
        ],
        flags: [
          { flag_id: "f1", data_product_id: "dp-romi-001", step: 3, flag_type: "grain_ambiguity" as const, description: "Allocadia 'prd' column format doesn't match fiscal calendar.", status: "resolved" as const, resolution: "Lookup table mapping prd codes to fiscal periods", resolved_by: "Analyst", resolved_at: new Date().toISOString(), created_at: new Date().toISOString() },
          { flag_id: "f2", data_product_id: "dp-romi-001", step: 3, flag_type: "missing_source" as const, description: "LinkedIn Campaign Stats table does not exist in Snowflake.", status: "deferred" as const, resolution: "Deferred to Phase 2", resolved_by: "Analyst", resolved_at: new Date().toISOString(), created_at: new Date().toISOString() },
          { flag_id: "f3", data_product_id: "dp-romi-001", step: 3, flag_type: "naming_conflict" as const, description: "Marketo lead_source_campaign is a name string, not a campaign ID.", status: "open" as const, resolution: null, resolved_by: null, resolved_at: null, created_at: new Date().toISOString() },
        ],
      },
    }),
  },
  {
    field: "remaining_flags",
    agentMessage: `Marketo naming conflict resolved — lookup table approach documented.\n\nAll flags are now resolved or deferred. The logical model covers 10 fields on the fact table with clear source mappings, transformation rules, and data types.\n\nI'm already thinking about Step 4: we'll need detailed field-level specs for each dimension table too, plus the calculated metric formulas.\n\nScroll down in the artifact panel to approve the logical model.`,
    suggestedReplies: ["Approve and continue", "Add dimension table attributes first", "Review the flags tab"],
    artifactUpdate: () => ({
      type: "SET_LOGICAL_MODEL",
      model: {
        entities: [
          {
            entity_name: "fact_campaign_performance", role: "FACT" as const,
            attributes: [
              { target_field: "campaign_key", data_type: "INT", source_field: null, transformation_rule: "Hash surrogate key", flag: null },
              { target_field: "campaign_id", data_type: "VARCHAR(50)", source_field: "Campaign.Id", transformation_rule: "Direct map", flag: null },
              { target_field: "channel_code", data_type: "VARCHAR(20)", source_field: null, transformation_rule: "FK lookup", flag: null },
              { target_field: "fiscal_month_key", data_type: "INT", source_field: null, transformation_rule: "FK to dim_date", flag: null },
              { target_field: "planned_spend", data_type: "DECIMAL(18,2)", source_field: "allocadia_budget.budget_amt", transformation_rule: "Sum by campaign period", flag: null },
              { target_field: "actual_spend", data_type: "DECIMAL(18,2)", source_field: "allocadia_budget.actual_amt", transformation_rule: "Sum by campaign period", flag: null },
              { target_field: "leads_generated", data_type: "INT", source_field: "marketo_leads.lead_id", transformation_rule: "COUNT with lookup table join", flag: null },
              { target_field: "opportunities_created", data_type: "INT", source_field: "salesforce_opportunities.opportunity_id", transformation_rule: "COUNT by primary_campaign", flag: null },
              { target_field: "attributed_revenue", data_type: "DECIMAL(18,2)", source_field: "salesforce_opportunities.amount", transformation_rule: "SUM Closed Won", flag: null },
              { target_field: "linkedin_spend", data_type: "DECIMAL(18,2)", source_field: null, transformation_rule: "Phase 2", flag: null },
            ],
          },
        ],
        flags: [
          { flag_id: "f1", data_product_id: "dp-romi-001", step: 3, flag_type: "grain_ambiguity" as const, description: "Allocadia period format mismatch", status: "resolved" as const, resolution: "Lookup table", resolved_by: "Analyst", resolved_at: new Date().toISOString(), created_at: new Date().toISOString() },
          { flag_id: "f2", data_product_id: "dp-romi-001", step: 3, flag_type: "missing_source" as const, description: "LinkedIn connector not activated", status: "deferred" as const, resolution: "Phase 2", resolved_by: "Analyst", resolved_at: new Date().toISOString(), created_at: new Date().toISOString() },
          { flag_id: "f3", data_product_id: "dp-romi-001", step: 3, flag_type: "naming_conflict" as const, description: "Marketo campaign name vs ID mismatch", status: "resolved" as const, resolution: "Lookup table joining name strings to Salesforce campaign IDs", resolved_by: "Analyst", resolved_at: new Date().toISOString(), created_at: new Date().toISOString() },
        ],
      },
    }),
  },
];

// ─── Step 4: Detailed Requirements ───

const STEP4_OPENING: ConversationMessage = {
  data_product_id: "dp-romi-001",
  step: 4,
  message_role: "agent",
  message_text:
    `Logical model approved. Now for the final step — detailed field-level requirements.\n\nI've pre-populated the fact table fields from the logical model and I'm adding business rules, governance levels, and phase assignments. I've also drafted the dimension table specs based on what Atlan shows me about the source schemas.\n\nLet's start with governance: should spend data be restricted or public?`,
  timestamp: "",
  suggested_replies: ["Spend restricted to Finance + Marketing Ops", "All data public within the org", "Spend restricted, pipeline public"],
};

const STEP4_FLOW: InterviewStep[] = [
  {
    field: "governance",
    agentMessage: `Governance levels set. Spend fields are Restricted, pipeline metrics are Public, and individual deal amounts over $500K will be Masked for non-Finance roles.\n\nI've built out the detailed field mapping table with ${6} fact table fields and ${3} dimension tables. The completeness bar shows our progress.\n\nDo you want to review the calculated metrics next? I'm proposing ROMI ratio, cost per lead, and cost per acquisition.`,
    suggestedReplies: ["Yes, show me the metrics", "Add cost per MQL too", "Skip metrics, review the full table"],
    artifactUpdate: () => ({
      type: "SET_DETAILED_REQUIREMENTS",
      model: {
        fact_table: {
          table_name: "fact_campaign_performance",
          grain: "campaign × channel × fiscal_month",
          fields: [
            { target_field: "campaign_key", data_type: "INT", source_system: "Generated", source_field: "—", transformation: "Hash surrogate", business_rule: "Unique per grain combination", required: true, governance: "Public" as const, phase: "MVP" as const },
            { target_field: "campaign_id", data_type: "VARCHAR(50)", source_system: "Salesforce", source_field: "Campaign.Id", transformation: "Direct map", business_rule: "Must exist in dim_campaign", required: true, governance: "Public" as const, phase: "MVP" as const },
            { target_field: "planned_spend", data_type: "DECIMAL(18,2)", source_system: "Allocadia", source_field: "budget_amt", transformation: "Sum by campaign period", business_rule: "NULL if no Allocadia record (not zero)", required: true, governance: "Restricted" as const, phase: "MVP" as const },
            { target_field: "actual_spend", data_type: "DECIMAL(18,2)", source_system: "Allocadia", source_field: "actual_amt", transformation: "Sum by campaign period", business_rule: "NULL-safe aggregation", required: true, governance: "Restricted" as const, phase: "MVP" as const },
            { target_field: "attributed_revenue", data_type: "DECIMAL(18,2)", source_system: "Salesforce", source_field: "Opportunity.Amount", transformation: "SUM Closed Won by campaign", business_rule: "Primary attribution only", required: true, governance: "Masked" as const, phase: "MVP" as const },
            { target_field: "leads_generated", data_type: "INT", source_system: "Marketo", source_field: "Lead.lead_id", transformation: "COUNT with lookup join", business_rule: "MQLs only (score >= 85)", required: true, governance: "Public" as const, phase: "MVP" as const },
          ],
        },
        dimension_tables: [
          {
            table_name: "dim_campaign",
            fields: [
              { target_field: "campaign_id", data_type: "VARCHAR(50)", source_system: "Salesforce", source_field: "Campaign.Id", transformation: "Direct map", business_rule: "Natural key", required: true, governance: "Public" as const, phase: "MVP" as const },
              { target_field: "campaign_name", data_type: "VARCHAR(255)", source_system: "Salesforce", source_field: "Campaign.Name", transformation: "Direct map", business_rule: "", required: true, governance: "Public" as const, phase: "MVP" as const },
              { target_field: "campaign_type", data_type: "VARCHAR(50)", source_system: "Salesforce", source_field: "Campaign.Type", transformation: "Direct map", business_rule: "Standard picklist values", required: false, governance: "Public" as const, phase: "MVP" as const },
            ],
          },
          {
            table_name: "dim_channel",
            fields: [
              { target_field: "channel_code", data_type: "VARCHAR(20)", source_system: "Manual", source_field: "—", transformation: "Reference table", business_rule: "Maintained by Marketing Ops", required: true, governance: "Public" as const, phase: "MVP" as const },
              { target_field: "channel_name", data_type: "VARCHAR(100)", source_system: "Manual", source_field: "—", transformation: "Reference table", business_rule: "", required: true, governance: "Public" as const, phase: "MVP" as const },
              { target_field: "channel_group", data_type: "VARCHAR(50)", source_system: "Manual", source_field: "—", transformation: "Reference table", business_rule: "Paid / Owned / Earned", required: true, governance: "Public" as const, phase: "MVP" as const },
            ],
          },
          {
            table_name: "dim_date",
            fields: [
              { target_field: "date_key", data_type: "INT", source_system: "Finance", source_field: "fiscal_calendar.date_key", transformation: "Direct map", business_rule: "YYYYMMDD format", required: true, governance: "Public" as const, phase: "MVP" as const },
              { target_field: "fiscal_year", data_type: "INT", source_system: "Finance", source_field: "fiscal_calendar.fiscal_year", transformation: "Direct map", business_rule: "Feb–Jan fiscal year", required: true, governance: "Public" as const, phase: "MVP" as const },
              { target_field: "fiscal_month", data_type: "INT", source_system: "Finance", source_field: "fiscal_calendar.fiscal_month", transformation: "Direct map", business_rule: "1-12, Feb=1", required: true, governance: "Public" as const, phase: "MVP" as const },
            ],
          },
        ],
        calculated_metrics: [],
        completeness_score: 62,
      },
    }),
  },
  {
    field: "metrics_review",
    agentMessage: `I've added 3 calculated metrics:\n\n• ROMI Ratio = attributed_revenue / total_actual_spend\n• Cost Per Lead = total_actual_spend / leads_generated\n• Cost Per Acquisition = total_actual_spend / deals_closed_won\n\nAll are Restricted governance (since they derive from spend data) and scoped to MVP.\n\nThe requirements are at 79% completeness. The remaining gap is Phase 2 items like LinkedIn spend and multi-touch attribution.\n\nScroll down to approve the final requirements package.`,
    suggestedReplies: ["Approve — this is complete for MVP", "Add cost per MQL metric", "Change CPL governance to Public"],
    artifactUpdate: () => ({
      type: "SET_DETAILED_REQUIREMENTS",
      model: {
        fact_table: {
          table_name: "fact_campaign_performance",
          grain: "campaign × channel × fiscal_month",
          fields: [
            { target_field: "campaign_key", data_type: "INT", source_system: "Generated", source_field: "—", transformation: "Hash surrogate", business_rule: "Unique per grain combination", required: true, governance: "Public" as const, phase: "MVP" as const },
            { target_field: "campaign_id", data_type: "VARCHAR(50)", source_system: "Salesforce", source_field: "Campaign.Id", transformation: "Direct map", business_rule: "Must exist in dim_campaign", required: true, governance: "Public" as const, phase: "MVP" as const },
            { target_field: "planned_spend", data_type: "DECIMAL(18,2)", source_system: "Allocadia", source_field: "budget_amt", transformation: "Sum by period", business_rule: "NULL if no record", required: true, governance: "Restricted" as const, phase: "MVP" as const },
            { target_field: "actual_spend", data_type: "DECIMAL(18,2)", source_system: "Allocadia", source_field: "actual_amt", transformation: "Sum by period", business_rule: "NULL-safe", required: true, governance: "Restricted" as const, phase: "MVP" as const },
            { target_field: "attributed_revenue", data_type: "DECIMAL(18,2)", source_system: "Salesforce", source_field: "Amount", transformation: "SUM Closed Won", business_rule: "Primary attribution", required: true, governance: "Masked" as const, phase: "MVP" as const },
            { target_field: "leads_generated", data_type: "INT", source_system: "Marketo", source_field: "lead_id", transformation: "COUNT with lookup", business_rule: "MQL score >= 85", required: true, governance: "Public" as const, phase: "MVP" as const },
          ],
        },
        dimension_tables: [
          { table_name: "dim_campaign", fields: [
            { target_field: "campaign_id", data_type: "VARCHAR(50)", source_system: "Salesforce", source_field: "Campaign.Id", transformation: "Direct", business_rule: "Natural key", required: true, governance: "Public" as const, phase: "MVP" as const },
            { target_field: "campaign_name", data_type: "VARCHAR(255)", source_system: "Salesforce", source_field: "Campaign.Name", transformation: "Direct", business_rule: "", required: true, governance: "Public" as const, phase: "MVP" as const },
          ]},
          { table_name: "dim_channel", fields: [
            { target_field: "channel_code", data_type: "VARCHAR(20)", source_system: "Manual", source_field: "—", transformation: "Ref table", business_rule: "Maintained by Mktg Ops", required: true, governance: "Public" as const, phase: "MVP" as const },
            { target_field: "channel_name", data_type: "VARCHAR(100)", source_system: "Manual", source_field: "—", transformation: "Ref table", business_rule: "", required: true, governance: "Public" as const, phase: "MVP" as const },
          ]},
          { table_name: "dim_date", fields: [
            { target_field: "date_key", data_type: "INT", source_system: "Finance", source_field: "date_key", transformation: "Direct", business_rule: "YYYYMMDD", required: true, governance: "Public" as const, phase: "MVP" as const },
            { target_field: "fiscal_year", data_type: "INT", source_system: "Finance", source_field: "fiscal_year", transformation: "Direct", business_rule: "Feb-Jan", required: true, governance: "Public" as const, phase: "MVP" as const },
          ]},
        ],
        calculated_metrics: [
          { field: "romi_ratio", formula: "attributed_revenue / total_actual_spend", business_rule: "NULL if denominator is zero or NULL", governance: "Restricted" as const, phase: "MVP" as const },
          { field: "cost_per_lead", formula: "total_actual_spend / leads_generated", business_rule: "NULL if no leads", governance: "Restricted" as const, phase: "MVP" as const },
          { field: "cost_per_acquisition", formula: "total_actual_spend / deals_closed_won", business_rule: "NULL if no closed deals", governance: "Restricted" as const, phase: "MVP" as const },
        ],
        completeness_score: 79,
      },
    }),
  },
];

// ─── Flow registry ───

function getStepFlow(step: StepNumber): StepFlow | null {
  switch (step) {
    case 1: return { openingMessage: STEP1_OPENING, steps: STEP1_FLOW };
    case 2: return { openingMessage: STEP2_OPENING, steps: STEP2_FLOW };
    case 3: return { openingMessage: STEP3_OPENING, steps: STEP3_FLOW };
    case 4: return { openingMessage: STEP4_OPENING, steps: STEP4_FLOW };
    default: return null;
  }
}

// ─── Hook ───

/**
 * Pre-scripted conversation engine from DSA. Preserved here for demo mode
 * (T059-T063 will wire this in via AppContext.demoMode.enabled). The live
 * step dispatcher lives in useAgent.ts.
 */
export function useAgentDemo() {
  const { state, dispatch } = useAppState();
  const interviewIndexRef = useRef(0);
  const hasInitializedRef = useRef(false);
  const processingRef = useRef(false);
  const lastStepRef = useRef<StepNumber | null>(null);

  const currentStep = state.lifecycle.current_step;
  const messages = state.conversation.filter((m) => m.step === currentStep);

  // Reset interview index when step changes
  useEffect(() => {
    if (lastStepRef.current !== null && lastStepRef.current !== currentStep) {
      interviewIndexRef.current = 0;
      hasInitializedRef.current = false;
      processingRef.current = false;
    }
    lastStepRef.current = currentStep;
  }, [currentStep]);

  // Send opening message for current step
  useEffect(() => {
    if (!state.demoMode.enabled) return; // live mode owns message dispatch
    const flow = getStepFlow(currentStep);
    if (!flow) return;
    if (hasInitializedRef.current) return;

    // Check if there are already messages for this step
    const stepMessages = state.conversation.filter((m) => m.step === currentStep);
    if (stepMessages.length > 0) return;

    hasInitializedRef.current = true;
    dispatch({ type: "SET_AGENT_THINKING", thinking: true });

    const timer = setTimeout(() => {
      dispatch({ type: "SET_AGENT_THINKING", thinking: false });
      dispatch({
        type: "ADD_MESSAGE",
        message: { ...flow.openingMessage, timestamp: new Date().toISOString() },
      });
    }, TIMING.TYPING_INDICATOR_DELAY);

    return () => {
      clearTimeout(timer);
      hasInitializedRef.current = false;
      dispatch({ type: "SET_AGENT_THINKING", thinking: false });
    };
  }, [currentStep, state.conversation, dispatch]);

  // Respond to user messages
  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const lastMessageRef = useRef<string | null>(null);

  useEffect(() => {
    if (!state.demoMode.enabled) return; // live mode owns message dispatch
    const flow = getStepFlow(currentStep);
    if (!flow) return;
    if (!lastMessage) return;
    if (lastMessage.message_role !== "user") return;
    if (lastMessage.timestamp === lastMessageRef.current) return;
    if (processingRef.current) return;

    lastMessageRef.current = lastMessage.timestamp;
    processingRef.current = true;

    const index = interviewIndexRef.current;
    const step = flow.steps[index];

    if (!step) {
      processingRef.current = false;
      dispatch({ type: "SET_GATE_ACTIVE", active: true });
      return;
    }

    // Update artifact
    if (step.artifactUpdate) {
      const action = step.artifactUpdate(lastMessage.message_text);
      if (action) dispatch(action);
    }

    // Show typing then respond
    dispatch({ type: "SET_AGENT_THINKING", thinking: true });
    const delay = TIMING.TYPING_INDICATOR_THINKING + Math.random() * 400;

    const timer = setTimeout(() => {
      dispatch({ type: "SET_AGENT_THINKING", thinking: false });
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          data_product_id: state.lifecycle.data_product_id,
          step: currentStep as StepNumber,
          message_role: "agent",
          message_text: step.agentMessage,
          timestamp: new Date().toISOString(),
          suggested_replies: step.suggestedReplies,
        },
      });

      interviewIndexRef.current = index + 1;
      processingRef.current = false;

      // Activate gate after last step
      if (index + 1 >= flow.steps.length) {
        setTimeout(() => {
          dispatch({ type: "SET_GATE_ACTIVE", active: true });
        }, 500);
      }
    }, delay);

    return () => {
      clearTimeout(timer);
      processingRef.current = false;
      dispatch({ type: "SET_AGENT_THINKING", thinking: false });
    };
  }, [lastMessage, currentStep, dispatch, state.lifecycle.data_product_id]);
}
