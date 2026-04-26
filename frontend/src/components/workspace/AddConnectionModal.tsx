// AddConnectionModal — driver-specific Add Connection form (T041, US1).
//
// Renders a driver picker plus the per-driver fields each backend driver
// needs. Submission goes through the useWorkspace hook; the modal
// surfaces backend errors (400 validation / 409 duplicate) inline.

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import type {
  AddConnectionInput,
  DriverType,
} from "../../hooks/useWorkspace";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (
    input: AddConnectionInput
  ) => Promise<{ ok: true } | { ok: false; message: string }>;
}

interface FormState {
  driver_type: DriverType;
  display_name: string;
  // PostgreSQL / Redshift
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  sslmode: string;
  // Snowflake
  account: string;
  sfRole: string;
  sfWarehouse: string;
  sfDatabase: string;
  sfSchema: string;
  sfUser: string;
  sfPassword: string;
  // Iceberg / Glue
  glueDatabase: string;
  warehouseS3Uri: string;
  region: string;
}

const DRIVERS: { value: DriverType; label: string }[] = [
  { value: "postgresql", label: "PostgreSQL / RDS" },
  { value: "redshift", label: "Redshift" },
  { value: "snowflake", label: "Snowflake" },
  { value: "databricks", label: "Databricks" },
  { value: "iceberg", label: "Iceberg / Glue" },
];

const INITIAL: FormState = {
  driver_type: "postgresql",
  display_name: "",
  host: "",
  port: 5432,
  database: "",
  user: "postgres",
  password: "",
  sslmode: "require",
  account: "",
  sfRole: "",
  sfWarehouse: "",
  sfDatabase: "",
  sfSchema: "PUBLIC",
  sfUser: "",
  sfPassword: "",
  glueDatabase: "",
  warehouseS3Uri: "",
  region: "us-east-1",
};

export default function AddConnectionModal({ open, onClose, onSubmit }: Props) {
  const { theme } = useTheme();
  const [state, setState] = useState<FormState>(INITIAL);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form whenever the modal opens.
  useEffect(() => {
    if (open) {
      setState(INITIAL);
      setError(null);
    }
  }, [open]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setState((s) => ({ ...s, [key]: value }));

  const buildInput = useMemo<() => AddConnectionInput | null>(
    () => () => {
      const display = state.display_name.trim();
      if (!display) return null;
      switch (state.driver_type) {
        case "postgresql":
        case "redshift": {
          if (!state.host || !state.database) return null;
          return {
            driver_type: state.driver_type,
            display_name: display,
            endpoint: `${state.host}:${state.port}`,
            scope: `${state.database}.public`,
            credentials: {
              host: state.host,
              port: state.port,
              database: state.database,
              user: state.user,
              password: state.password,
              sslmode: state.sslmode,
            },
          };
        }
        case "snowflake":
          if (!state.account || !state.sfDatabase) return null;
          return {
            driver_type: "snowflake",
            display_name: display,
            endpoint: state.account,
            scope: `${state.sfDatabase}.${state.sfSchema}`,
            credentials: {
              account: state.account,
              user: state.sfUser,
              password: state.sfPassword,
              role: state.sfRole,
              warehouse: state.sfWarehouse,
              database: state.sfDatabase,
              schema: state.sfSchema,
              authenticator: state.sfPassword ? "snowflake" : "externalbrowser",
            },
          };
        case "iceberg":
          if (!state.glueDatabase || !state.warehouseS3Uri) return null;
          return {
            driver_type: "iceberg",
            display_name: display,
            endpoint: `glue://${state.region}/${state.glueDatabase}`,
            scope: state.glueDatabase,
            credentials: {
              glue_database: state.glueDatabase,
              warehouse_s3_uri: state.warehouseS3Uri,
              region: state.region,
            },
          };
        case "databricks":
          // Databricks driver is registered conditionally; pass a thin payload.
          return {
            driver_type: "databricks",
            display_name: display,
            endpoint: state.host,
            scope: state.database,
            credentials: { host: state.host, database: state.database, token: state.password },
          };
        default:
          return null;
      }
    },
    [state]
  );

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const input = buildInput();
    if (!input) {
      setError("Fill the required fields for this driver.");
      return;
    }
    setSubmitting(true);
    setError(null);
    const result = await onSubmit(input);
    setSubmitting(false);
    if (result.ok) {
      onClose();
    } else {
      setError(result.message);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Add connection"
      data-testid="add-connection-modal"
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.55)" }}
    >
      <form
        onSubmit={handleSubmit}
        className="w-[480px] max-h-[90vh] overflow-y-auto rounded-lg p-6 flex flex-col gap-4"
        style={{
          backgroundColor: theme.colors.surfaceSubtle,
          border: `1px solid ${theme.colors.borderSubtle}`,
        }}
      >
        <h2
          className="text-lg font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          Add connection
        </h2>

        <Field label="Driver">
          <select
            value={state.driver_type}
            onChange={(e) => update("driver_type", e.target.value as DriverType)}
            className="w-full px-2 py-1.5 rounded"
            style={{
              backgroundColor: theme.colors.white,
              color: theme.colors.textPrimary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
          >
            {DRIVERS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Display name">
          <Input
            value={state.display_name}
            onChange={(v) => update("display_name", v)}
            placeholder="e.g., Pinnacle PG"
          />
        </Field>

        {state.driver_type === "postgresql" || state.driver_type === "redshift" ? (
          <SqlFields state={state} update={update} />
        ) : null}

        {state.driver_type === "snowflake" ? (
          <SnowflakeFields state={state} update={update} />
        ) : null}

        {state.driver_type === "iceberg" ? (
          <IcebergFields state={state} update={update} />
        ) : null}

        {state.driver_type === "databricks" ? (
          <DatabricksFields state={state} update={update} />
        ) : null}

        {error ? (
          <div
            className="text-xs px-3 py-2 rounded"
            // Status hex inlined per ADR-020 D4 (status-error token).
            style={{
              color: "#DC2626",
              backgroundColor: "#DC262614",
            }}
            role="alert"
          >
            {error}
          </div>
        ) : null}

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded"
            style={{
              color: theme.colors.textSecondary,
              border: `1px solid ${theme.colors.borderSubtle}`,
            }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-3 py-1.5 rounded font-semibold"
            style={{
              color: theme.colors.white,
              backgroundColor: theme.colors.accent,
              opacity: submitting ? 0.6 : 1,
            }}
          >
            {submitting ? "Adding…" : "Add connection"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ───── small primitives, kept private so the modal stays self-contained ─────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  const { theme } = useTheme();
  return (
    <label className="flex flex-col gap-1 text-xs"
           style={{ color: theme.colors.textSecondary }}>
      {label}
      {children}
    </label>
  );
}

function Input({
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  value: string | number;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  const { theme } = useTheme();
  return (
    <input
      type={type}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-2 py-1.5 rounded"
      style={{
        backgroundColor: theme.colors.white,
        color: theme.colors.textPrimary,
        border: `1px solid ${theme.colors.borderSubtle}`,
      }}
    />
  );
}

interface SubProps {
  state: FormState;
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
}

function SqlFields({ state, update }: SubProps) {
  return (
    <>
      <Field label="Host">
        <Input value={state.host} onChange={(v) => update("host", v)} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Port">
          <Input
            type="number"
            value={state.port}
            onChange={(v) => update("port", Number(v) || 5432)}
          />
        </Field>
        <Field label="Database">
          <Input value={state.database} onChange={(v) => update("database", v)} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="User">
          <Input value={state.user} onChange={(v) => update("user", v)} />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            value={state.password}
            onChange={(v) => update("password", v)}
          />
        </Field>
      </div>
    </>
  );
}

function SnowflakeFields({ state, update }: SubProps) {
  return (
    <>
      <Field label="Account">
        <Input
          value={state.account}
          onChange={(v) => update("account", v)}
          placeholder="e.g., lga76011"
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Database">
          <Input value={state.sfDatabase} onChange={(v) => update("sfDatabase", v)} />
        </Field>
        <Field label="Schema">
          <Input value={state.sfSchema} onChange={(v) => update("sfSchema", v)} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Warehouse">
          <Input value={state.sfWarehouse} onChange={(v) => update("sfWarehouse", v)} />
        </Field>
        <Field label="Role">
          <Input value={state.sfRole} onChange={(v) => update("sfRole", v)} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="User (optional for SSO)">
          <Input value={state.sfUser} onChange={(v) => update("sfUser", v)} />
        </Field>
        <Field label="Password (blank → externalbrowser SSO)">
          <Input
            type="password"
            value={state.sfPassword}
            onChange={(v) => update("sfPassword", v)}
          />
        </Field>
      </div>
    </>
  );
}

function IcebergFields({ state, update }: SubProps) {
  return (
    <>
      <Field label="Glue database">
        <Input
          value={state.glueDatabase}
          onChange={(v) => update("glueDatabase", v)}
          placeholder="e.g., dsa_hub_pinnacle_360"
        />
      </Field>
      <Field label="S3 warehouse URI">
        <Input
          value={state.warehouseS3Uri}
          onChange={(v) => update("warehouseS3Uri", v)}
          placeholder="s3://my-bucket/iceberg-warehouse"
        />
      </Field>
      <Field label="Region">
        <Input value={state.region} onChange={(v) => update("region", v)} />
      </Field>
    </>
  );
}

function DatabricksFields({ state, update }: SubProps) {
  return (
    <>
      <Field label="Workspace host">
        <Input
          value={state.host}
          onChange={(v) => update("host", v)}
          placeholder="adb-…azuredatabricks.net"
        />
      </Field>
      <Field label="Catalog">
        <Input value={state.database} onChange={(v) => update("database", v)} />
      </Field>
      <Field label="Personal access token">
        <Input
          type="password"
          value={state.password}
          onChange={(v) => update("password", v)}
        />
      </Field>
    </>
  );
}
