// CoverageMatrix — process × connection coverage grid (T060, US2 / FR-010).
//
// Renders one row per detected process and one column per workspace
// connection. Cells show whether the process is present; rows where
// `ready_to_combine` is true are visually highlighted (green pulse) to
// signal "cross-source data product is feasible."

import { useTheme } from "../../context/ThemeContext";
import type { CoverageMatrix as CoverageMatrixType } from "../../hooks/useWorkspaceDiscover";
import type { WorkspaceConnectionRef } from "../../context/AppContext";

interface Props {
  matrix: CoverageMatrixType;
  connections: WorkspaceConnectionRef[];
}

const READY_GLOW = "#16A34A"; // status-success per ADR-020 D4

export default function CoverageMatrix({ matrix, connections }: Props) {
  const { theme } = useTheme();
  if (!matrix.rows.length || !connections.length) {
    return (
      <div
        className="text-xs px-3 py-2 rounded"
        style={{
          color: theme.colors.textTertiary,
          backgroundColor: theme.colors.surfaceSubtle,
          border: `1px solid ${theme.colors.borderSubtle}`,
        }}
      >
        No coverage data yet — connect ≥1 source to populate this matrix.
      </div>
    );
  }
  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        border: `1px solid ${theme.colors.borderSubtle}`,
        backgroundColor: theme.colors.surfaceSubtle,
      }}
      data-testid="coverage-matrix"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: theme.colors.surfaceHover }}>
              <th
                className="text-left px-3 py-2 text-xs uppercase tracking-wide"
                style={{ color: theme.colors.textTertiary }}
              >
                Process
              </th>
              {connections.map((c) => (
                <th
                  key={c.connection_id}
                  className="text-left px-3 py-2 text-xs uppercase tracking-wide"
                  style={{ color: theme.colors.textTertiary }}
                  title={`${c.display_name} · ${c.scope}`}
                >
                  {c.display_name}
                </th>
              ))}
              <th
                className="text-left px-3 py-2 text-xs uppercase tracking-wide"
                style={{ color: theme.colors.textTertiary }}
              >
                Shared keys
              </th>
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row) => {
              const ready = row.ready_to_combine;
              return (
                <tr
                  key={row.process_name}
                  data-testid="coverage-row"
                  data-ready={ready ? "true" : "false"}
                  style={{
                    borderTop: `1px solid ${theme.colors.borderSubtle}`,
                    backgroundColor: ready ? `${READY_GLOW}10` : "transparent",
                  }}
                >
                  <td
                    className="px-3 py-2"
                    style={{ color: theme.colors.textPrimary }}
                  >
                    {row.process_name}
                  </td>
                  {connections.map((c) => {
                    const presence = row.per_connection[c.connection_id];
                    const present = !!presence?.present;
                    return (
                      <td
                        key={c.connection_id}
                        className="px-3 py-2"
                        style={{
                          color: present ? theme.colors.textPrimary : theme.colors.textTertiary,
                        }}
                      >
                        {present ? (
                          <span title={presence?.backing_tables.join(", ") ?? ""}>
                            ✓ {presence?.backing_tables.length ?? 0}
                          </span>
                        ) : (
                          <span aria-hidden>—</span>
                        )}
                      </td>
                    );
                  })}
                  <td
                    className="px-3 py-2 text-xs"
                    style={{
                      color: ready ? READY_GLOW : theme.colors.textTertiary,
                    }}
                  >
                    {row.shared_keys.length ? row.shared_keys.join(", ") : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
