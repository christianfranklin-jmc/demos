// Standards — read-only enterprise-standards browser (T131, US7 / FR-037).

import { useTheme } from "../context/ThemeContext";
import StandardsBrowser from "../components/standards/StandardsBrowser";

export default function Standards() {
  const { theme } = useTheme();
  return (
    <div className="flex flex-col gap-4 p-6">
      <header>
        <h1
          className="text-2xl font-semibold"
          style={{ color: theme.colors.textPrimary }}
        >
          Standards
        </h1>
        <p
          className="text-sm mt-1"
          style={{ color: theme.colors.textSecondary }}
        >
          Read-only catalog of naming, metric, PII, dbt, domain, and Iceberg
          standards. PRD generation in Step 1 consults this content to
          populate every PRD's "Standards applied" footer (FR-038, SC-011).
        </p>
      </header>
      <StandardsBrowser />
    </div>
  );
}
