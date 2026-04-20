import type { PRDArtifact } from "./types";
import { PRD_COMPLETENESS_WEIGHTS } from "./constants";

/**
 * Calculate PRD completeness score (0-100) based on weighted fields.
 * Matches the scoring spec from the design doc Section 9, Step 1.
 */
export function calculatePRDCompleteness(prd: PRDArtifact): number {
  let score = 0;

  // Business objective captured: 20%
  if (prd.business_objective && prd.business_objective.trim().length > 0) {
    score += PRD_COMPLETENESS_WEIGHTS.business_objective;
  }

  // Consumers confirmed: 10%
  if (prd.primary_consumers && prd.primary_consumers.length > 0) {
    score += PRD_COMPLETENESS_WEIGHTS.consumers;
  }

  // Grain confirmed: 20%
  if (prd.grain_statement && prd.grain_statement.trim().length > 0) {
    score += PRD_COMPLETENESS_WEIGHTS.grain;
  }

  // Time range confirmed: 10%
  if (prd.time_range && prd.time_range.historical_coverage) {
    score += PRD_COMPLETENESS_WEIGHTS.time_range;
  }

  // Key metrics (≥ 3): 20%
  if (prd.key_metrics && prd.key_metrics.length >= 3) {
    score += PRD_COMPLETENESS_WEIGHTS.key_metrics;
  } else if (prd.key_metrics && prd.key_metrics.length > 0) {
    // Partial credit: proportional to 3
    score += Math.round(
      (prd.key_metrics.length / 3) * PRD_COMPLETENESS_WEIGHTS.key_metrics
    );
  }

  // Success criteria captured: 15%
  if (prd.success_criteria && prd.success_criteria.trim().length > 0) {
    score += PRD_COMPLETENESS_WEIGHTS.success_criteria;
  }

  // Constraints answered: 5%
  if (prd.constraints && prd.constraints.trim().length > 0) {
    score += PRD_COMPLETENESS_WEIGHTS.constraints;
  }

  return Math.min(score, 100);
}

/**
 * Determine which interview topics are complete vs pending.
 */
export function getInterviewProgress(prd: PRDArtifact): {
  completed: string[];
  pending: string[];
  next: string | null;
} {
  const checks: [string, boolean][] = [
    ["business_objective", Boolean(prd.business_objective?.trim())],
    ["consumers", Boolean(prd.primary_consumers?.length)],
    ["decisions_enabled", Boolean(prd.decisions_enabled?.length)],
    ["grain", Boolean(prd.grain_statement?.trim())],
    ["time_range", Boolean(prd.time_range?.historical_coverage)],
    ["key_metrics", Boolean(prd.key_metrics && prd.key_metrics.length >= 3)],
    ["source_systems", Boolean(prd.source_systems?.length)],
    ["success_criteria", Boolean(prd.success_criteria?.trim())],
    ["constraints", Boolean(prd.constraints?.trim())],
  ];

  const completed = checks.filter(([, done]) => done).map(([name]) => name);
  const pending = checks.filter(([, done]) => !done).map(([name]) => name);
  const next = pending.length > 0 ? pending[0] : null;

  return { completed, pending, next };
}

/**
 * Generate a human-readable completeness summary for the agent.
 */
export function getCompletenessSummary(prd: PRDArtifact): string {
  const score = calculatePRDCompleteness(prd);
  const { completed, pending } = getInterviewProgress(prd);

  const parts: string[] = [];
  parts.push(`PRD is at ${score}% completeness.`);

  if (completed.length > 0) {
    parts.push(
      `Captured: ${completed.map(humanize).join(", ")}.`
    );
  }

  if (pending.length > 0) {
    parts.push(
      `Still needed: ${pending.map(humanize).join(", ")}.`
    );
  }

  return parts.join(" ");
}

function humanize(field: string): string {
  const map: Record<string, string> = {
    business_objective: "business objective",
    consumers: "consumer personas",
    decisions_enabled: "decisions enabled",
    grain: "primary grain",
    time_range: "time range & refresh",
    key_metrics: "key metrics",
    source_systems: "source systems",
    success_criteria: "success criteria",
    constraints: "constraints & governance",
  };
  return map[field] || field;
}

/**
 * Create an empty PRD artifact with all fields null.
 */
export function createEmptyPRD(): PRDArtifact {
  return {
    business_objective: null,
    current_state_pain: null,
    decisions_enabled: null,
    primary_consumers: null,
    secondary_consumers: null,
    grain_statement: null,
    time_range: null,
    key_metrics: null,
    source_systems: null,
    success_criteria: null,
    acceptance_criteria: null,
    constraints: null,
    scope_in: null,
    scope_out: null,
    completeness_score: 0,
  };
}
