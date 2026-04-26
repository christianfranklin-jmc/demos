// 002-dsa-hub-pinnacle US2 — discovery components.
//
// Smoke renders for ProcessCard, CoverageMatrix, and PillRow against
// fixtures that match the wire shapes from /workspace/discover and
// /workflow/pills.

import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ThemeProvider } from "../context/ThemeContext";
import ProcessCard from "../components/discovery/ProcessCard";
import CoverageMatrix from "../components/discovery/CoverageMatrix";
import PillRow from "../components/discovery/PillRow";
import type {
  BusinessProcess,
  CoverageMatrix as CoverageMatrixType,
} from "../hooks/useWorkspaceDiscover";
import type { PillSuggestion } from "../hooks/usePills";
import type { WorkspaceConnectionRef } from "../context/AppContext";

function wrap(node: React.ReactNode) {
  return <ThemeProvider>{node}</ThemeProvider>;
}

const PG: WorkspaceConnectionRef = {
  connection_id: "pg-1",
  driver_type: "postgresql",
  display_name: "Pinnacle PG",
  scope: "pinnacle.public",
  status: "live",
};
const SF: WorkspaceConnectionRef = {
  connection_id: "sf-1",
  driver_type: "snowflake",
  display_name: "Pinnacle SF",
  scope: "PINNACLE_FINANCIAL_DEMO_ASINGH.ANALYTICS",
  status: "live",
};

describe("ProcessCard", () => {
  it("renders the process name + driver icon + row count", () => {
    const proc: BusinessProcess = {
      process_id: "p1",
      connection_id: "pg-1",
      name: "Accounts Payable",
      domain: "accounting",
      volume_signal: { row_count: 336, dollar_total: null, currency: null },
      last_activity_ts: null,
      sparkline: [1, 2, 3, 2, 1, 4, 5, 3, 2, 1, 0, 0],
      backing_tables: ["pinnacle.ap.ap_invoice", "pinnacle.ap.ap_payment"],
    };
    render(wrap(<ProcessCard process={proc} connections={[PG, SF]} />));
    expect(screen.getByText("Accounts Payable")).toBeTruthy();
    expect(screen.getByText(/336 rows/)).toBeTruthy();
    expect(screen.getByText(/2 table\(s\)/)).toBeTruthy();
  });
});

describe("CoverageMatrix", () => {
  it("highlights ready_to_combine rows", () => {
    const matrix: CoverageMatrixType = {
      matrix_id: "m1",
      rows: [
        {
          process_name: "CRM",
          per_connection: {
            "pg-1": { present: true, backing_tables: ["pinnacle.crm.client"] },
            "sf-1": { present: true, backing_tables: ["...DIM_CLIENT"] },
          },
          shared_keys: ["client_id"],
          ready_to_combine: true,
        },
        {
          process_name: "HR & Cost Management",
          per_connection: {
            "pg-1": { present: true, backing_tables: ["pinnacle.hr.employee"] },
            "sf-1": { present: false, backing_tables: [] },
          },
          shared_keys: [],
          ready_to_combine: false,
        },
      ],
    };
    render(wrap(<CoverageMatrix matrix={matrix} connections={[PG, SF]} />));
    const rows = screen.getAllByTestId("coverage-row");
    expect(rows).toHaveLength(2);
    expect(rows[0].getAttribute("data-ready")).toBe("true");
    expect(rows[1].getAttribute("data-ready")).toBe("false");
    expect(screen.getByText("client_id")).toBeTruthy();
  });

  it("renders empty state when matrix is empty", () => {
    render(
      wrap(
        <CoverageMatrix
          matrix={{ matrix_id: "m0", rows: [] }}
          connections={[]}
        />
      )
    );
    expect(screen.getByText(/No coverage data yet/)).toBeTruthy();
  });
});

describe("PillRow", () => {
  it("renders pill chips and fires onSelect on click", () => {
    const pills: PillSuggestion[] = [
      {
        pill_id: "pill-1",
        title: "Client 360",
        subtitle: "combines: Postgres + Snowflake",
        icon: "users-round",
        target_iceberg_table: "iceberg.pinnacle_360.fct_client_360",
        source_connection_ids: ["pg-1", "sf-1"],
        estimated_build_minutes: 4,
        generated_at: new Date().toISOString(),
        flags: { demo: false },
      },
    ];
    let clicked: string | null = null;
    render(
      wrap(<PillRow pills={pills} onSelect={(p) => (clicked = p.pill_id)} />)
    );
    expect(screen.getByText("Client 360")).toBeTruthy();
    expect(screen.getByText(/iceberg\.pinnacle_360\.fct_client_360/)).toBeTruthy();
    const chip = screen.getByTestId("pill-chip");
    fireEvent.click(chip);
    expect(clicked).toBe("pill-1");
  });

  it("renders empty state when no pills", () => {
    render(wrap(<PillRow pills={[]} onSelect={() => {}} />));
    expect(screen.getByTestId("pills-empty")).toBeTruthy();
  });
});
