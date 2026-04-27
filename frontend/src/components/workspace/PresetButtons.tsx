// PresetButtons — one-click demo connection presets.
//
// Reads GET /workspace/connection-presets to learn which presets are
// wired up via the server-side .env, then POSTs to
// /workspace/connection-presets/{name} to add the connection. The
// credentials never leave the server bundle.

import { useEffect, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { getOrMintSessionId } from "../../lib/session";

const BACKEND_URL: string =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (import.meta as any).env?.VITE_BACKEND_URL ?? "http://localhost:8080";

interface PresetSummary {
  name: string;
  label: string;
  driver_type: string;
  available: boolean;
  missing_env: string[];
}

interface Props {
  onAdded: () => void;
}

export default function PresetButtons({ onAdded }: Props) {
  const { theme } = useTheme();
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const sessionId = getOrMintSessionId();
    fetch(`${BACKEND_URL}/workspace/connection-presets`, {
      headers: { "X-DSA-Session-ID": sessionId },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body: { presets: PresetSummary[] }) => setPresets(body.presets))
      .catch(() => setPresets([]));
  }, []);

  if (presets.length === 0) return null;

  async function activate(name: string) {
    setBusy(name);
    setErr(null);
    try {
      const sessionId = getOrMintSessionId();
      const r = await fetch(
        `${BACKEND_URL}/workspace/connection-presets/${name}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-DSA-Session-ID": sessionId,
          },
        }
      );
      if (r.status !== 201) {
        type Detail = { code?: string; message?: string } | string;
        let detail: Detail = "";
        try {
          const body = (await r.json()) as { detail?: Detail };
          detail = body.detail ?? "";
        } catch {
          // empty
        }
        const message =
          typeof detail === "string"
            ? detail || `HTTP ${r.status}`
            : detail.message ?? `HTTP ${r.status}`;
        setErr(message);
        return;
      }
      onAdded();
    } catch (exc) {
      setErr(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div
      className="flex flex-col gap-2 px-3 py-2 rounded text-xs"
      style={{
        backgroundColor: theme.colors.surfaceSubtle,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span style={{ color: theme.colors.textSecondary }}>
          Demo presets:
        </span>
        {presets.map((p) => (
          <button
            key={p.name}
            type="button"
            disabled={!p.available || busy !== null}
            onClick={() => void activate(p.name)}
            title={
              p.available
                ? `Add ${p.label} from server-side credentials`
                : `Unavailable — set ${p.missing_env.join(", ")} in .env`
            }
            className="px-2 py-1 rounded font-semibold disabled:opacity-50"
            style={{
              color: theme.colors.white,
              backgroundColor: theme.colors.accent,
            }}
          >
            {busy === p.name ? "Adding…" : `Use ${p.label}`}
          </button>
        ))}
      </div>
      {err ? (
        <span style={{ color: "#DC2626" }}>{err}</span>
      ) : null}
    </div>
  );
}
