// EntityPanel — side-panel detail view for a selected entity (T110, US5).
//
// Renders attributes, metrics, and physical bindings for the entity loaded
// via useSemanticGraph.loadEntity.

import { useTheme } from "../../context/ThemeContext";
import type { EntityDetail } from "../../hooks/useSemanticGraph";

interface Props {
  detail: EntityDetail | null;
  loading: boolean;
  onClose: () => void;
}

export default function EntityPanel({ detail, loading, onClose }: Props) {
  const { theme } = useTheme();
  if (!detail && !loading) return null;
  return (
    <aside
      data-testid="entity-panel"
      className="flex flex-col gap-3 rounded-lg p-4 max-h-[420px] overflow-y-auto"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
        minWidth: 280,
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3
            className="font-semibold text-base"
            style={{ color: theme.colors.textPrimary }}
          >
            {detail?.entity.name ?? "Loading…"}
          </h3>
          {detail ? (
            <div
              className="text-[11px] uppercase tracking-wide"
              style={{ color: theme.colors.textTertiary }}
            >
              {detail.entity.domain.replace("_", " ")} · v{detail.entity.version}
            </div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-xs px-2 py-1 rounded"
          style={{
            color: theme.colors.textSecondary,
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          ✕
        </button>
      </div>

      {loading ? (
        <div
          className="text-xs"
          style={{ color: theme.colors.textTertiary }}
        >
          loading entity…
        </div>
      ) : detail ? (
        <>
          <Section title="Attributes" theme={theme}>
            {detail.entity.attributes.length === 0 ? (
              <Empty theme={theme}>no attributes</Empty>
            ) : (
              <ul className="text-xs space-y-1">
                {detail.entity.attributes.map((a) => (
                  <li
                    key={a.name}
                    className="flex items-center justify-between gap-2"
                    style={{ color: theme.colors.textPrimary }}
                  >
                    <span className="font-mono">{a.name}</span>
                    <span style={{ color: theme.colors.textTertiary }}>
                      {a.data_type}
                      {a.is_pii ? " · PII" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title={`Metrics (${detail.metrics.length})`} theme={theme}>
            {detail.metrics.length === 0 ? (
              <Empty theme={theme}>no metrics for this entity</Empty>
            ) : (
              <ul className="text-xs space-y-2">
                {detail.metrics.map((m) => (
                  <li
                    key={m.metric_id}
                    style={{ color: theme.colors.textPrimary }}
                  >
                    <div className="font-semibold">
                      {m.name}
                      {m.unit ? (
                        <span
                          className="ml-1 text-[10px]"
                          style={{ color: theme.colors.textTertiary }}
                        >
                          {m.unit}
                        </span>
                      ) : null}
                    </div>
                    <code
                      className="font-mono text-[10px] block px-2 py-1 rounded mt-1"
                      style={{
                        backgroundColor: theme.colors.surfaceInput,
                        color: theme.colors.textSecondary,
                      }}
                    >
                      {m.definition_sql}
                    </code>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section
            title={`Physical bindings (${detail.bindings.length})`}
            theme={theme}
          >
            {detail.bindings.length === 0 ? (
              <Empty theme={theme}>no bindings</Empty>
            ) : (
              <ul className="text-xs space-y-1">
                {detail.bindings.map((b) => (
                  <li
                    key={b.binding_id}
                    style={{ color: theme.colors.textPrimary }}
                  >
                    <code className="font-mono">{b.fully_qualified_name}</code>
                    {b.row_count_estimate != null ? (
                      <span
                        className="ml-2"
                        style={{ color: theme.colors.textTertiary }}
                      >
                        ~{b.row_count_estimate.toLocaleString()} rows
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </>
      ) : null}
    </aside>
  );
}

interface SectionProps {
  title: string;
  theme: { colors: Record<string, string> };
  children: React.ReactNode;
}

function Section({ title, theme, children }: SectionProps) {
  return (
    <div className="flex flex-col gap-1">
      <h4
        className="text-xs uppercase tracking-wide"
        style={{ color: theme.colors.textTertiary }}
      >
        {title}
      </h4>
      {children}
    </div>
  );
}

function Empty({
  theme,
  children,
}: {
  theme: { colors: Record<string, string> };
  children: React.ReactNode;
}) {
  return (
    <div
      className="text-xs"
      style={{ color: theme.colors.textTertiary }}
    >
      {children}
    </div>
  );
}
