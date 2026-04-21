// Live-mode step openers.
//
// Injected by useAgent when the user enters a step with no messages yet.
// Gives the user a starting prompt + clickable suggestions — same affordance
// DSA's pre-scripted demo engine provides, but scoped to the live backend's
// capabilities and the Northwinds / Pinnacle demo schemas.
//
// Demo mode is unaffected: useAgent.demo.ts owns the ROMI-scenario openers
// when AppContext.demoMode.enabled is true.

import type { StepNumber } from "../lib/types";

export interface StepOpener {
  greeting: string;
  /** Initial prompts shown at step entry (before any user message). */
  suggestions: string[];
  /** Continuation prompts attached to every live agent response. */
  followups: string[];
}

export const STEP_OPENERS: Record<StepNumber, StepOpener | null> = {
  0: null, // Step 0 (stakeholders) is out of scope for the live backend

  1: {
    greeting:
      "Welcome to Step 1 — Requirements. Connect a source database in the sidebar, then tell me what you want to understand. I'll scan the real schema and draft a PRD grounded in the tables I find.",
    suggestions: [
      "Help me understand our order data",
      "Analyze customer segments and purchasing patterns",
      "Track product sales by territory and region",
      "Measure employee performance across orders",
    ],
    followups: [
      "Also track returns and refunds",
      "Include seasonal and monthly trends",
      "Add supplier performance metrics",
      "Focus on high-value customers",
      "Add data quality requirements (completeness, freshness)",
      "Add PII and governance constraints",
    ],
  },

  2: {
    greeting:
      "Step 2 — Conceptual Model. I'll derive entities and relationships from the real foreign-key graph. For Northwinds you should see orders, customers, products, order_details, plus the employees self-reference.",
    suggestions: [
      "Propose entities and relationships",
      "Focus on the orders fact and its dimensions",
      "Include the employee reports-to hierarchy",
      "Show only sales-related entities (orders, customers, products)",
    ],
    followups: [
      "Add a Date conformed dimension",
      "Include Shipper and Territory as lookup dimensions",
      "Flag any entities with no incoming relationships",
      "Show the cardinalities inline on each edge",
    ],
  },

  3: {
    greeting:
      "Step 3 — Logical Model. I'll build typed tables with real data types from information_schema and pull a handful of sample values live from each column.",
    suggestions: [
      "Build fct_orders with customer, product, and date dimensions",
      "Include shipping and territory dimensions",
      "Focus on revenue measures (unit_price * quantity)",
      "Sample values for each attribute",
    ],
    followups: [
      "Add a fct_order_lines grain (one row per line item)",
      "Flag nullable columns that need imputation",
      "Show suggested surrogate keys",
      "Add a late-arriving dimension strategy",
    ],
  },

  4: {
    greeting:
      "Step 4 — Detailed Requirements. I'll generate a compilable dbt project and a semantic layer. Clicking one of these will stream a zip back to your browser.",
    suggestions: [
      "Generate the dbt project",
      "Include a revenue metric in the semantic layer",
      "Target PostgreSQL with dbt-utils surrogate keys",
      "Add quality tests to the marts",
    ],
    followups: [
      "Re-generate with mart models included",
      "Add not_null and unique tests to every PK",
      "Include an incremental materialization strategy",
      "Add a semantic metric for average order value",
    ],
  },
};
