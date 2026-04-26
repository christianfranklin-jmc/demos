import { useState } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { DATA_PRODUCTS, type DataProduct } from "../../data/mock/data-products";
import type { StepNumber, StepStatus } from "../../lib/types";
import ConnectionForm from "./ConnectionForm";

type ShellView =
  | "workflow"
  | "connections"
  | "discovery"
  | "build"
  | "semantic";

interface SidebarProps {
  onSettingsOpen: () => void;
  view?: ShellView;
  onViewChange?: (view: ShellView) => void;
}

interface SidebarNavItemProps {
  icon: string;
  label: string;
  badge?: string;
  isActive: boolean;
  onClick: () => void;
  theme: any;
}

function SidebarNavItem({
  icon,
  label,
  badge,
  isActive,
  onClick,
  theme,
}: SidebarNavItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 px-2 py-1.5 text-sm w-full text-left"
      style={{
        backgroundColor: isActive ? theme.colors.surfaceActiveNav : "transparent",
        borderRadius: `${theme.layout.borderRadius.nav}px`,
        color: theme.colors.textPrimary,
        fontWeight: isActive
          ? theme.typography.mediumWeight
          : theme.typography.bodyWeight,
      }}
    >
      <span aria-hidden>{icon}</span>
      <span className="flex-1 truncate">{label}</span>
      {badge ? (
        <span
          className="text-[10px] px-1.5 py-0.5 rounded-full"
          style={{
            backgroundColor: theme.colors.accent,
            color: theme.colors.btnPrimaryText ?? theme.colors.white,
          }}
        >
          {badge}
        </span>
      ) : null}
    </button>
  );
}

function StepIndicator({ status, isActive, theme }: { status: StepStatus; isActive: boolean; theme: any }) {
  if (status === "approved") {
    return (
      <span className="w-4 h-4 flex items-center justify-center text-xs" style={{ color: theme.colors.textTertiary }}>
        ✓
      </span>
    );
  }
  if (status === "awaiting_approval") {
    return (
      <span className="w-4 h-4 flex items-center justify-center text-xs font-semibold" style={{ color: theme.colors.flagAmber }}>
        !
      </span>
    );
  }
  return (
    <span
      className="w-2 h-2 rounded-full"
      style={{
        backgroundColor: isActive ? theme.colors.accent : theme.colors.borderSubtle,
      }}
    />
  );
}

// Short page-level descriptions shown in the sidebar for the current step.
// Kept tight (~2 sentences each) so the connection form stays visible below.
const STEP_DESCRIPTIONS: Record<number, { title: string; body: string }> = {
  0: {
    title: "Stakeholders",
    body: "Capture who needs the data product and why. The trigger email and target consumers are recorded here before requirements work begins.",
  },
  1: {
    title: "Requirements",
    body: "Connect a source, then describe what you want to understand. The agent scans the live schema and drafts a PRD grounded in the real tables and discovered business processes.",
  },
  2: {
    title: "Conceptual Model",
    body: "Entities and relationships derived from the live foreign-key graph. Review the proposed shape, then approve to move on.",
  },
  3: {
    title: "Logical Model",
    body: "Typed tables with sample values pulled live from each column. Verify the data types and samples before approving.",
  },
  4: {
    title: "Detailed Requirements",
    body: "A compilable dbt project plus a semantic layer, packaged as a downloadable zip you can run against the source.",
  },
};

function ProductStatusDot({ product, theme }: { product: DataProduct; theme: any }) {
  const color =
    product.overallStatus === "complete"
      ? theme.colors.textTertiary
      : product.overallStatus === "awaiting"
      ? theme.colors.flagAmber
      : product.overallStatus === "active"
      ? theme.colors.accent
      : theme.colors.borderSubtle;

  return (
    <span
      className="w-2 h-2 rounded-full shrink-0"
      style={{ backgroundColor: color }}
    />
  );
}

export default function Sidebar({
  onSettingsOpen,
  view = "workflow",
  onViewChange,
}: SidebarProps) {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const [selectedProductId, setSelectedProductId] = useState(state.lifecycle.data_product_id);
  const liveConnections = state.workspaceConnections.filter(
    (c) => c.status === "live"
  ).length;

  const stepLabels: Record<number, string> = {
    0: theme.steps.step0Label,
    1: theme.steps.step1Label,
    2: theme.steps.step2Label,
    3: theme.steps.step3Label,
    4: theme.steps.step4Label,
  };

  const steps = theme.features.showStep0 ? [0, 1, 2, 3, 4] : [1, 2, 3, 4];

  const handleStepClick = (step: StepNumber) => {
    const status = state.lifecycle.step_statuses[step];
    if (status === "not_started") return;
    dispatch({ type: "SET_STEP", step });
  };

  const handleProductClick = (product: DataProduct) => {
    setSelectedProductId(product.id);
    // Only the ROMI product is fully wired; others show selection state
    if (product.id === "dp-romi-001") return; // already loaded
  };

  const isActiveProduct = (id: string) => id === selectedProductId;

  return (
    <aside
      className="flex flex-col border-r shrink-0 h-full"
      style={{
        width: `${theme.layout.sidebarWidth}px`,
        minWidth: `${theme.layout.sidebarWidth}px`,
        borderColor: theme.colors.borderSubtle,
        backgroundColor: theme.colors.surfaceSubtle,
      }}
    >
      {/* Platform header */}
      <div className="px-4 py-3 flex items-center gap-2">
        {theme.brand.logoUrl ? (
          <img src={theme.brand.logoUrl} alt={theme.brand.logoAltText} className="h-5" />
        ) : null}
        <span className="text-sm font-semibold" style={{ color: theme.colors.textPrimary }}>
          {theme.brand.platformName}
        </span>
      </div>

      {/* 002-dsa-hub-pinnacle US1+US2 — top-level view toggle */}
      {onViewChange ? (
        <div className="px-3 pb-2 flex flex-col gap-0.5">
          <SidebarNavItem
            icon="📐"
            label="Workflow"
            isActive={view === "workflow"}
            onClick={() => onViewChange("workflow")}
            theme={theme}
          />
          <SidebarNavItem
            icon="🌐"
            label="Connections"
            badge={liveConnections > 0 ? String(liveConnections) : undefined}
            isActive={view === "connections"}
            onClick={() => onViewChange("connections")}
            theme={theme}
          />
          <SidebarNavItem
            icon="🧭"
            label="Discovery"
            isActive={view === "discovery"}
            onClick={() => onViewChange("discovery")}
            theme={theme}
          />
          <SidebarNavItem
            icon="🛠"
            label="Build"
            isActive={view === "build"}
            onClick={() => onViewChange("build")}
            theme={theme}
          />
          <SidebarNavItem
            icon="🕸"
            label="Semantic"
            isActive={view === "semantic"}
            onClick={() => onViewChange("semantic")}
            theme={theme}
          />
        </div>
      ) : null}

      {/* Extra nav items */}
      {theme.sidebar.navItems.map((item: any, i: number) => (
        <div
          key={i}
          className="flex items-center gap-2 px-4 py-1.5 text-sm"
          style={{ color: theme.colors.textPrimary }}
        >
          <span>{item.icon}</span>
          <span>{item.label}</span>
        </div>
      ))}

      {/* Workflow folder */}
      <nav className="flex-1 px-3 py-2 overflow-y-auto">
        <p
          className="text-xs font-medium uppercase tracking-wide mb-2 px-2"
          style={{ color: theme.colors.textSecondary }}
        >
          {theme.sidebar.workflowFolderLabel}
        </p>

        {/* Active data product only — the unused mock cohort (Customer Churn,
            Revenue Attribution, Customer Lifetime Value, Sales Pipeline Health)
            is replaced by a per-step description card below. */}
        {DATA_PRODUCTS.filter((p) => p.id === "dp-romi-001").map((product) => (
          <div key={product.id}>
            <button
              onClick={() => handleProductClick(product)}
              className="flex items-center gap-2 px-2 py-1.5 text-sm w-full text-left mb-0.5"
              style={{
                backgroundColor: isActiveProduct(product.id) ? theme.colors.surfaceActiveNav : "transparent",
                borderRadius: `${theme.layout.borderRadius.nav}px`,
                color: theme.colors.textPrimary,
                fontWeight: isActiveProduct(product.id) ? theme.typography.mediumWeight : theme.typography.bodyWeight,
              }}
            >
              <ProductStatusDot product={product} theme={theme} />
              <span className="truncate">{product.name}</span>
            </button>

            {/* Step navigator — only for selected product */}
            {isActiveProduct(product.id) && product.id === "dp-romi-001" && (
              <div className="ml-2 mb-2">
                {steps.map((step) => {
                  const stepNum = step as StepNumber;
                  const status = state.lifecycle.step_statuses[stepNum];
                  const isActive = state.lifecycle.current_step === stepNum;
                  const isLocked = status === "not_started";

                  return (
                    <div key={step}>
                      {step === 1 && theme.features.showStep0 && (
                        <div
                          className="my-1 mx-2 border-t"
                          style={{ borderColor: theme.colors.borderSubtle }}
                        />
                      )}
                      <button
                        onClick={() => handleStepClick(stepNum)}
                        disabled={isLocked}
                        className="flex items-center gap-2 px-2 py-1 text-xs w-full text-left"
                        style={{
                          backgroundColor: isActive ? theme.colors.surfaceHover : "transparent",
                          borderRadius: `${theme.layout.borderRadius.nav}px`,
                          color: theme.colors.textPrimary,
                          fontWeight: isActive ? theme.typography.mediumWeight : theme.typography.bodyWeight,
                          opacity: isLocked ? 0.4 : 1,
                          cursor: isLocked ? "default" : "pointer",
                        }}
                      >
                        {theme.sidebar.showStatusDots && (
                          <span className="w-4 h-4 flex items-center justify-center shrink-0">
                            <StepIndicator status={status} isActive={isActive} theme={theme} />
                          </span>
                        )}
                        <span>
                          {theme.sidebar.showStepNumbers && step > 0 ? `${step} — ` : ""}
                          {stepLabels[step] || `Step ${step}`}
                        </span>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Show step summary for non-ROMI products */}
            {isActiveProduct(product.id) && product.id !== "dp-romi-001" && (
              <div className="ml-6 mb-2">
                <p className="text-xs italic px-2 py-1" style={{ color: theme.colors.textTertiary }}>
                  Step {product.currentStep} — {stepLabels[product.currentStep]}
                  {product.overallStatus === "complete" && " (Complete)"}
                  {product.overallStatus === "awaiting" && " (Awaiting Approval)"}
                </p>
              </div>
            )}
          </div>
        ))}

        {/* Per-step description — replaces the unused mock data products
            (Customer Churn / Revenue Attribution / etc.) with a brief,
            context-aware blurb about what the current step does. */}
        {(() => {
          const desc = STEP_DESCRIPTIONS[state.lifecycle.current_step];
          if (!desc) return null;
          return (
            <div
              className="mt-3 mx-1 px-3 py-2.5 rounded text-xs leading-snug"
              style={{
                background: theme.colors.surfaceInput,
                border: `1px solid ${theme.colors.borderSubtle}`,
              }}
            >
              <p
                className="text-[10px] uppercase tracking-wider mb-1"
                style={{ color: theme.colors.textTertiary }}
              >
                About this step
              </p>
              <p
                className="font-semibold mb-1"
                style={{ color: theme.colors.textPrimary }}
              >
                {desc.title}
              </p>
              <p style={{ color: theme.colors.textSecondary }}>{desc.body}</p>
            </div>
          );
        })()}
      </nav>

      {/* 001-dsa-agent-integration: source-database connection form. */}
      <div className="px-3 py-2 border-t" style={{ borderColor: theme.colors.borderSubtle }}>
        <ConnectionForm />
      </div>

      {/* Settings trigger */}
      <div className="px-3 py-2 border-t" style={{ borderColor: theme.colors.borderSubtle }}>
        <button
          onClick={onSettingsOpen}
          className="flex items-center gap-2 px-2 py-1.5 text-sm w-full rounded-lg"
          style={{ color: theme.colors.textSecondary }}
        >
          <span style={{ fontSize: "16px" }}>&#9881;</span>
          Settings
        </button>
      </div>
    </aside>
  );
}
