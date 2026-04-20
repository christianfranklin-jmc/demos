import { useState } from "react";
import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { DATA_PRODUCTS, type DataProduct } from "../../data/mock/data-products";
import type { StepNumber, StepStatus } from "../../lib/types";
import ConnectionForm from "./ConnectionForm";

interface SidebarProps {
  onSettingsOpen: () => void;
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

export default function Sidebar({ onSettingsOpen }: SidebarProps) {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const [selectedProductId, setSelectedProductId] = useState(state.lifecycle.data_product_id);

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

        {/* Data products list */}
        {DATA_PRODUCTS.map((product) => (
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
