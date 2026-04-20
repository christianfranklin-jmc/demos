import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { getStepConfig } from "../../lib/constants";
import TabBar from "./TabBar";
import PRDView from "./PRDView";
import ConceptualERD from "./ConceptualERD";
import LogicalModel from "./LogicalModel";
import DetailedRequirements from "./DetailedRequirements";
import StandardsView from "./StandardsView";
import FlagsList from "./FlagsList";
import GraphView from "./GraphView";
import DemoBadge from "../shared/DemoBadge";
import EmptyState from "../shared/EmptyState";
import GateApproval from "../gates/GateApproval";

function getTabsForStep(
  step: number,
  enableFlags: boolean,
  enableStandards: boolean,
  enableVisual: boolean
): string[] {
  const config = getStepConfig(step as any);
  const tabs = [config.tab_name];
  if (step === 2) tabs.push("Relationships");
  if (step === 4) tabs.push("Completeness");
  if (enableVisual) tabs.push("Visual");
  if (enableFlags) tabs.push("Flags");
  if (enableStandards) tabs.push("Standards");
  return tabs;
}

export default function ArtifactPanel() {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const currentStep = state.lifecycle.current_step;
  const tabs = getTabsForStep(
    currentStep,
    theme.features.enableFlagSystem,
    theme.features.enableStandardsView,
    theme.features.enableVisualGraph
  );
  const activeTab = state.ui.activeArtifactTab;
  const resolvedTab = tabs.includes(activeTab) ? activeTab : tabs[0];

  const handleTabChange = (tab: string) => {
    dispatch({ type: "SET_ACTIVE_TAB", tab });
  };

  const renderContent = () => {
    // Cross-step tabs
    if (resolvedTab === "Standards") {
      return <StandardsView stepNumber={currentStep} />;
    }
    if (resolvedTab === "Flags") {
      return <FlagsList />;
    }
    if (resolvedTab === "Visual") {
      return <GraphView stepNumber={currentStep} />;
    }

    // Step-specific tabs
    switch (currentStep) {
      case 1:
        if (resolvedTab === "PRD Draft") return <PRDView />;
        break;
      case 2:
        return <ConceptualERD activeTab={resolvedTab} />;
      case 3:
        return <LogicalModel activeTab={resolvedTab} />;
      case 4:
        return <DetailedRequirements activeTab={resolvedTab} />;
    }
    return <EmptyState stepNumber={currentStep} tabName={resolvedTab} />;
  };

  return (
    <div
      className="flex flex-col relative"
      style={{ width: `${theme.layout.artifactPanelPercent}%` }}
    >
      <TabBar tabs={tabs} activeTab={resolvedTab} onTabChange={handleTabChange} />
      <div className="flex-1 flex flex-col overflow-y-auto relative">
        {/* FR-018: visible demo-mode indicator on every artifact panel. */}
        <DemoBadge corner="top-right" />
        {renderContent()}
        <GateApproval />
      </div>
    </div>
  );
}
