import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { calculatePRDCompleteness } from "../../lib/scoring";
import CompletenessBar from "./CompletenessBar";
import FieldRow from "./FieldRow";
import EmptyState from "../shared/EmptyState";
import type { PRDArtifact } from "../../lib/types";

/** Check if all displayable PRD fields are empty */
function isPRDEmpty(prd: PRDArtifact): boolean {
  return (
    !prd.business_objective &&
    !prd.current_state_pain &&
    (!prd.decisions_enabled || prd.decisions_enabled.length === 0) &&
    (!prd.primary_consumers || prd.primary_consumers.length === 0) &&
    !prd.secondary_consumers &&
    !prd.grain_statement &&
    !prd.time_range &&
    (!prd.key_metrics || prd.key_metrics.length === 0) &&
    (!prd.source_systems || prd.source_systems.length === 0) &&
    !prd.success_criteria &&
    (!prd.acceptance_criteria || prd.acceptance_criteria.length === 0) &&
    !prd.constraints &&
    (!prd.scope_in || prd.scope_in.length === 0) &&
    (!prd.scope_out || prd.scope_out.length === 0)
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const { theme } = useTheme();
  return (
    <div style={{ marginBottom: "20px" }}>
      <h3
        className="text-xs font-semibold uppercase tracking-wider mb-2"
        style={{ color: theme.colors.textSecondary }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function PRDView() {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const prd = state.artifacts.prd;
  const score = calculatePRDCompleteness(prd);

  if (isPRDEmpty(prd)) {
    return <EmptyState stepNumber={1} tabName="PRD Draft" />;
  }

  const updateField = (field: keyof PRDArtifact, value: string) => {
    dispatch({ type: "UPDATE_PRD", updates: { [field]: value } });
  };

  // Format complex types for display
  const consumersDisplay = prd.primary_consumers
    ? prd.primary_consumers.map((c) => `${c.persona} (${c.role})`).join(", ")
    : null;

  const metricsDisplay = prd.key_metrics
    ? prd.key_metrics.map((m) => m.name).join(", ")
    : null;

  const sourcesDisplay = prd.source_systems
    ? prd.source_systems.map((s) => `${s.system} (${s.data_domain})`).join(", ")
    : null;

  const timeRangeDisplay = prd.time_range
    ? `${prd.time_range.historical_coverage}, ${prd.time_range.refresh_cadence}`
    : null;

  const acceptanceDisplay = prd.acceptance_criteria
    ? prd.acceptance_criteria.map((a) => a.criterion).join("; ")
    : null;

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Metadata row */}
      <div
        className="flex items-center gap-4 px-4 py-3 border-b text-xs"
        style={{
          borderColor: theme.colors.borderSubtle,
          color: theme.colors.textSecondary,
        }}
      >
        <span>{theme.scenario.dataProductName}</span>
        <span>&middot;</span>
        <span>v0.3</span>
        <span>&middot;</span>
        <span>Owner: {theme.scenario.ownerName}</span>
      </div>

      <CompletenessBar score={score} />

      <div className="px-4 py-4">
        <Section title="Business Objective">
          <FieldRow
            label="Objective"
            value={prd.business_objective}
            onUpdate={(v) => updateField("business_objective", v)}
            highlightKey={prd.business_objective ?? undefined}
          />
          <FieldRow
            label="Current State / Pain"
            value={prd.current_state_pain}
            onUpdate={(v) => updateField("current_state_pain", v)}
            highlightKey={prd.current_state_pain ?? undefined}
          />
          <FieldRow
            label="Decisions Enabled"
            value={prd.decisions_enabled}
            highlightKey={prd.decisions_enabled?.join(",") ?? undefined}
          />
        </Section>

        <Section title="Consumers">
          <FieldRow
            label="Primary Consumers"
            value={consumersDisplay}
            highlightKey={consumersDisplay ?? undefined}
          />
          <FieldRow
            label="Secondary Consumers"
            value={prd.secondary_consumers}
            onUpdate={(v) => updateField("secondary_consumers", v)}
            highlightKey={prd.secondary_consumers ?? undefined}
          />
        </Section>

        <Section title="Data Scope">
          <FieldRow
            label="Primary Grain"
            value={prd.grain_statement}
            onUpdate={(v) => updateField("grain_statement", v)}
            highlightKey={prd.grain_statement ?? undefined}
          />
          <FieldRow
            label="Time Range"
            value={timeRangeDisplay}
            highlightKey={timeRangeDisplay ?? undefined}
          />
        </Section>

        <Section title="Key Metrics">
          <FieldRow
            label="Metrics"
            value={metricsDisplay}
            highlightKey={metricsDisplay ?? undefined}
          />
        </Section>

        <Section title="Source Systems">
          <FieldRow
            label="Sources"
            value={sourcesDisplay}
            highlightKey={sourcesDisplay ?? undefined}
          />
        </Section>

        <Section title="Success Criteria">
          <FieldRow
            label="Definition of Done"
            value={prd.success_criteria}
            onUpdate={(v) => updateField("success_criteria", v)}
            highlightKey={prd.success_criteria ?? undefined}
          />
          <FieldRow
            label="Acceptance Criteria"
            value={acceptanceDisplay}
            highlightKey={acceptanceDisplay ?? undefined}
          />
        </Section>

        <Section title="Constraints & Scope">
          <FieldRow
            label="Constraints"
            value={prd.constraints}
            onUpdate={(v) => updateField("constraints", v)}
            highlightKey={prd.constraints ?? undefined}
          />
          <FieldRow
            label="In Scope"
            value={prd.scope_in}
            highlightKey={prd.scope_in?.join(",") ?? undefined}
          />
          <FieldRow
            label="Out of Scope"
            value={prd.scope_out}
            highlightKey={prd.scope_out?.join(",") ?? undefined}
          />
        </Section>
      </div>
    </div>
  );
}
