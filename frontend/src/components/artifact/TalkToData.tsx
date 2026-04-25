// "Talk to Data" tab — NL → SQL via /workflow/query.
//
// Takes a plain-English question, sends it to the backend which uses Bedrock
// Claude to translate to a SELECT against the user's connected source,
// executes via the driver, and renders the rows in a table.

import { useState } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { getOrMintSessionId } from "../../lib/session";
import { getIdToken, isAuthEnabled } from "../../lib/auth";

const BACKEND_URL =
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

interface QueryResponse {
  question: string;
  generated_sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  run_id: string;
  narrative: string;
  error: string | null;
}

// Fallback pills — used only before the discover endpoint has returned
// source-specific suggestions. Discovery overrides these via sourceContext.
const FALLBACK_QUESTIONS = [
  "How many rows are in each table?",
  "Show a sample of 10 rows from the largest table",
  "Which tables have foreign-key relationships to others?",
  "List the columns and types of the largest table",
];

export default function TalkToData() {
  const { state } = useAppState();
  const { theme } = useTheme();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const connection = state.connection;

  const run = async (q: string) => {
    if (!q.trim() || !connection) return;
    setLoading(true);
    setFetchError(null);
    setResult(null);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "X-DSA-Session-ID": getOrMintSessionId(),
      };
      if (isAuthEnabled()) {
        const t = getIdToken();
        if (t) headers.Authorization = `Bearer ${t}`;
      }
      const r = await fetch(`${BACKEND_URL}/workflow/query`, {
        method: "POST",
        headers,
        body: JSON.stringify({ question: q.trim(), connection }),
      });
      if (!r.ok) {
        const txt = await r.text().catch(() => "");
        setFetchError(`HTTP ${r.status}: ${txt || r.statusText}`);
        return;
      }
      const json: QueryResponse = await r.json();
      setResult(json);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  if (!connection) {
    return (
      <div className="px-6 py-8">
        <p className="text-sm" style={{ color: theme.colors.textSecondary }}>
          Connect a source database in the sidebar to enable querying.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-4 py-3 border-b" style={{ borderColor: theme.colors.borderSubtle }}>
        <p className="text-sm" style={{ color: theme.colors.textPrimary, fontWeight: theme.typography.mediumWeight }}>
          Talk to your data
        </p>
        <p className="text-xs mt-1" style={{ color: theme.colors.textSecondary }}>
          Ask a question in plain English. The agent translates it to SQL against <code>{connection.driver_type}</code> and returns rows.
        </p>
      </div>

      {/* Input */}
      <div className="px-4 py-3 flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !loading) run(question);
          }}
          placeholder="e.g. How many orders did each customer place last year?"
          className="flex-1 text-sm outline-none"
          style={{
            background: theme.colors.surfaceInput,
            color: theme.colors.textPrimary,
            border: `1px solid ${theme.colors.borderSubtle}`,
            borderRadius: `${theme.layout.borderRadius.input}px`,
            padding: "8px 12px",
          }}
          disabled={loading}
        />
        <button
          type="button"
          onClick={() => run(question)}
          disabled={loading || !question.trim()}
          className="text-sm px-4"
          style={{
            background: theme.colors.btnPrimaryBg,
            color: theme.colors.btnPrimaryText,
            borderRadius: `${theme.layout.borderRadius.button}px`,
            opacity: loading || !question.trim() ? 0.6 : 1,
          }}
        >
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      {/* Suggestions — grounded in the discovered schema once available. */}
      {!result && !loading && (
        <div className="px-4 pb-3 flex flex-wrap gap-2">
          {(state.sourceContext?.suggestedQuestions.length
            ? state.sourceContext.suggestedQuestions
            : FALLBACK_QUESTIONS
          ).map((q, i) => (
            <button
              key={i}
              type="button"
              onClick={() => {
                setQuestion(q);
                run(q);
              }}
              className="text-xs px-3 py-1.5"
              style={{
                background: theme.colors.surfaceInput,
                color: theme.colors.textPrimary,
                border: `1px solid ${theme.colors.borderSubtle}`,
                borderRadius: "20px",
              }}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Fetch-level error */}
      {fetchError && (
        <div
          className="mx-4 mb-3 px-3 py-2 text-xs rounded"
          style={{
            background: theme.colors.flagAmberSurface,
            color: theme.colors.flagAmber,
            border: `1px solid ${theme.colors.flagAmber}`,
          }}
        >
          ⚠️ {fetchError}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="px-4 pb-6">
          {/* Narrative */}
          {result.narrative && (
            <div className="mb-3">
              <p className="text-[11px] uppercase tracking-wider mb-1" style={{ color: theme.colors.textTertiary }}>
                Answer
              </p>
              <div
                className="text-sm whitespace-pre-wrap"
                style={{
                  background: theme.colors.surfaceSubtle,
                  border: `1px solid ${theme.colors.borderSubtle}`,
                  borderRadius: `${theme.layout.borderRadius.card}px`,
                  padding: "10px 12px",
                  color: theme.colors.textPrimary,
                }}
              >
                {result.narrative}
              </div>
            </div>
          )}

          {/* Generated SQL */}
          {result.generated_sql && <div className="mb-3">
            <p className="text-[11px] uppercase tracking-wider mb-1" style={{ color: theme.colors.textTertiary }}>
              Generated SQL
            </p>
            <pre
              className="text-xs overflow-x-auto whitespace-pre-wrap"
              style={{
                background: theme.colors.surfaceInput,
                border: `1px solid ${theme.colors.borderSubtle}`,
                borderRadius: `${theme.layout.borderRadius.input}px`,
                padding: "10px 12px",
                color: theme.colors.textPrimary,
                fontFamily: theme.typography.monoFamily,
              }}
            >
              {result.generated_sql}
            </pre>
          </div>}

          {/* Per-query error */}
          {result.error && (
            <div
              className="mb-3 px-3 py-2 text-xs rounded"
              style={{
                background: theme.colors.flagAmberSurface,
                color: theme.colors.flagAmber,
                border: `1px solid ${theme.colors.flagAmber}`,
              }}
            >
              Execution error: {result.error}
            </div>
          )}

          {/* Row count */}
          {!result.error && result.columns.length > 0 && (
            <p className="text-xs mb-2" style={{ color: theme.colors.textSecondary }}>
              {result.row_count} row{result.row_count === 1 ? "" : "s"}
              {result.truncated ? ` (truncated to first 250)` : ""}
            </p>
          )}

          {/* Results table */}
          {!result.error && result.columns.length > 0 && (
            <div
              className="overflow-x-auto"
              style={{
                border: `1px solid ${theme.colors.borderSubtle}`,
                borderRadius: `${theme.layout.borderRadius.card}px`,
              }}
            >
              <table className="w-full text-xs" style={{ borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: theme.colors.surfaceInput }}>
                    {result.columns.map((col) => (
                      <th
                        key={col}
                        className="text-left px-3 py-2 font-semibold"
                        style={{
                          color: theme.colors.textPrimary,
                          borderBottom: `1px solid ${theme.colors.borderSubtle}`,
                        }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td
                          key={j}
                          className="px-3 py-2"
                          style={{
                            color: theme.colors.textPrimary,
                            borderBottom: `1px solid ${theme.colors.borderSubtle}`,
                            fontFamily: theme.typography.monoFamily,
                          }}
                        >
                          {cell === null ? (
                            <span style={{ color: theme.colors.textTertiary }}>NULL</span>
                          ) : (
                            String(cell)
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Empty result */}
          {!result.error && result.rows.length === 0 && (
            <p className="text-xs" style={{ color: theme.colors.textTertiary }}>
              Query returned no rows.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
