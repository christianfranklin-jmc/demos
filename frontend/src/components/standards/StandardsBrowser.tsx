// StandardsBrowser — read-only Markdown reader (T132, US7).

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { getOrMintSessionId } from "../../lib/session";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

interface CategorySummary {
  key: string;
  label: string;
  preview: string;
}

interface CategoryContent {
  key: string;
  label: string;
  body: string;
}

export default function StandardsBrowser() {
  const { theme } = useTheme();
  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [content, setContent] = useState<CategoryContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sessionId = useMemo(() => getOrMintSessionId(), []);
  const headers = useMemo(
    () => ({ "X-DSA-Session-ID": sessionId }),
    [sessionId]
  );

  // Initial list fetch.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/standards`, { headers });
        if (!r.ok) throw new Error(`standards list failed: ${r.status}`);
        const body = (await r.json()) as { categories: CategorySummary[] };
        if (cancelled) return;
        setCategories(body.categories);
        if (body.categories.length && !active) {
          setActive(body.categories[0].key);
        }
      } catch (exc: unknown) {
        setError(exc instanceof Error ? exc.message : String(exc));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [headers]);

  // Detail fetch on selection change.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    setLoading(true);
    void (async () => {
      try {
        const r = await fetch(
          `${BACKEND_URL}/standards/${encodeURIComponent(active)}`,
          { headers }
        );
        if (!r.ok) throw new Error(`category fetch failed: ${r.status}`);
        const body = (await r.json()) as CategoryContent;
        if (cancelled) return;
        setContent(body);
        setError(null);
      } catch (exc: unknown) {
        setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [active, headers]);

  return (
    <div
      data-testid="standards-browser"
      className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4"
    >
      {/* Sidebar */}
      <nav
        className="rounded-lg p-2 flex flex-col gap-1"
        style={{
          backgroundColor: theme.colors.surfaceSubtle,
          border: `1px solid ${theme.colors.borderSubtle}`,
        }}
      >
        {categories.map((cat) => {
          const isActive = cat.key === active;
          return (
            <button
              key={cat.key}
              type="button"
              onClick={() => setActive(cat.key)}
              className="text-left px-3 py-2 rounded text-sm"
              style={{
                color: theme.colors.textPrimary,
                backgroundColor: isActive
                  ? theme.colors.surfaceActiveNav
                  : "transparent",
                fontWeight: isActive
                  ? theme.typography.mediumWeight
                  : theme.typography.bodyWeight,
              }}
            >
              <div>{cat.label}</div>
              <div
                className="text-[11px] mt-0.5 truncate"
                style={{ color: theme.colors.textTertiary }}
                title={cat.preview}
              >
                {cat.preview}
              </div>
            </button>
          );
        })}
      </nav>

      {/* Content pane */}
      <article
        className="rounded-lg p-6 overflow-y-auto"
        style={{
          backgroundColor: theme.colors.surfaceSubtle,
          border: `1px solid ${theme.colors.borderSubtle}`,
          color: theme.colors.textPrimary,
          maxHeight: "calc(100vh - 220px)",
        }}
      >
        {error ? (
          <div
            role="alert"
            className="text-xs px-3 py-2 rounded"
            style={{ color: "#DC2626", backgroundColor: "#DC262614" }}
          >
            {error}
          </div>
        ) : null}
        {loading ? (
          <div
            className="text-xs"
            style={{ color: theme.colors.textTertiary }}
          >
            loading…
          </div>
        ) : content ? (
          <pre
            className="whitespace-pre-wrap font-sans text-sm leading-relaxed"
            style={{ color: theme.colors.textPrimary }}
          >
            {content.body}
          </pre>
        ) : (
          <div
            className="text-xs"
            style={{ color: theme.colors.textTertiary }}
          >
            select a category
          </div>
        )}
      </article>
    </div>
  );
}
