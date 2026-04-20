// T045: PostgreSQL / Redshift / Snowflake connection form for the Sidebar.
//
// Renders a compact driver picker plus the fields each driver needs.
// Dispatches CONNECTION_SET on submit; shows a status pill that reflects
// AppContext.connection.
//
// Credentials live only in the form's local state + AppContext.connection
// for the duration of the session (FR-014). No localStorage, no cookies.

import { useState } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import type { DriverType, SourceConnection } from "../../lib/types";

type Status = "disconnected" | "connected";

export default function ConnectionForm() {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();

  const [driver, setDriver] = useState<DriverType>("postgresql");
  const [host, setHost] = useState("");
  const [port, setPort] = useState<number>(5432);
  const [database, setDatabase] = useState("");
  const [schema, setSchema] = useState("");
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [account, setAccount] = useState("");
  const [role, setRole] = useState("");
  const [warehouse, setWarehouse] = useState("");

  const status: Status = state.connection ? "connected" : "disconnected";

  const handleConnect = () => {
    const conn: SourceConnection =
      driver === "snowflake"
        ? {
            driver_type: "snowflake",
            account,
            database,
            schema: schema || undefined,
            user,
            role: role || undefined,
            warehouse: warehouse || undefined,
            credential: { kind: "sso_externalbrowser" },
          }
        : {
            driver_type: driver,
            host,
            port,
            database,
            schema: schema || undefined,
            user,
            credential: { kind: "password", password },
          };
    dispatch({ type: "CONNECTION_SET", connection: conn });
  };

  const handleDisconnect = () => {
    dispatch({ type: "CONNECTION_CLEAR" });
  };

  const labelStyle = { color: theme.colors.textSecondary, fontSize: "11px" };
  const inputStyle = {
    background: theme.colors.surfaceInput,
    color: theme.colors.textPrimary,
    border: `1px solid ${theme.colors.borderSubtle}`,
    borderRadius: `${theme.layout.borderRadius.input}px`,
    padding: "6px 8px",
    fontSize: "12px",
    width: "100%",
  };

  return (
    <div
      className="flex flex-col gap-2 p-3 rounded"
      style={{
        background: theme.colors.surfaceSubtle,
        borderRadius: `${theme.layout.borderRadius.card}px`,
      }}
    >
      <div className="flex items-center justify-between">
        <span style={{ color: theme.colors.textPrimary, fontWeight: theme.typography.mediumWeight, fontSize: "13px" }}>
          Source connection
        </span>
        <span
          className="text-[10px] uppercase rounded px-1.5 py-0.5"
          style={{
            background: status === "connected" ? theme.colors.accentSurface : theme.colors.surfaceInput,
            color: status === "connected" ? theme.colors.accent : theme.colors.textTertiary,
          }}
        >
          {status}
        </span>
      </div>

      <label style={labelStyle}>Driver</label>
      <select
        value={driver}
        onChange={(e) => setDriver(e.target.value as DriverType)}
        style={inputStyle}
        disabled={status === "connected"}
      >
        <option value="postgresql">PostgreSQL</option>
        <option value="redshift">Redshift</option>
        <option value="snowflake">Snowflake (SSO)</option>
      </select>

      {driver !== "snowflake" && (
        <>
          <label style={labelStyle}>Host</label>
          <input style={inputStyle} value={host} onChange={(e) => setHost(e.target.value)} disabled={status === "connected"} />
          <label style={labelStyle}>Port</label>
          <input
            type="number"
            style={inputStyle}
            value={port}
            onChange={(e) => setPort(Number(e.target.value))}
            disabled={status === "connected"}
          />
        </>
      )}

      {driver === "snowflake" && (
        <>
          <label style={labelStyle}>Account</label>
          <input style={inputStyle} value={account} onChange={(e) => setAccount(e.target.value)} disabled={status === "connected"} />
          <label style={labelStyle}>Role</label>
          <input style={inputStyle} value={role} onChange={(e) => setRole(e.target.value)} disabled={status === "connected"} />
          <label style={labelStyle}>Warehouse</label>
          <input style={inputStyle} value={warehouse} onChange={(e) => setWarehouse(e.target.value)} disabled={status === "connected"} />
        </>
      )}

      <label style={labelStyle}>Database</label>
      <input style={inputStyle} value={database} onChange={(e) => setDatabase(e.target.value)} disabled={status === "connected"} />
      <label style={labelStyle}>Schema</label>
      <input style={inputStyle} value={schema} onChange={(e) => setSchema(e.target.value)} disabled={status === "connected"} />
      <label style={labelStyle}>User</label>
      <input style={inputStyle} value={user} onChange={(e) => setUser(e.target.value)} disabled={status === "connected"} />

      {driver !== "snowflake" && (
        <>
          <label style={labelStyle}>Password</label>
          <input
            type="password"
            style={inputStyle}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={status === "connected"}
          />
        </>
      )}

      {status === "connected" ? (
        <button
          type="button"
          onClick={handleDisconnect}
          className="mt-1 px-3 py-1.5 text-xs rounded"
          style={{
            background: theme.colors.surfaceInput,
            color: theme.colors.textPrimary,
            border: `1px solid ${theme.colors.borderSubtle}`,
          }}
        >
          Disconnect
        </button>
      ) : (
        <button
          type="button"
          onClick={handleConnect}
          className="mt-1 px-3 py-1.5 text-xs rounded"
          style={{
            background: theme.colors.btnPrimaryBg,
            color: theme.colors.btnPrimaryText,
          }}
        >
          Connect
        </button>
      )}
    </div>
  );
}
