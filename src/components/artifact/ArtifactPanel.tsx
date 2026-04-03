import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import { getStepConfig } from "../../lib/constants";
import TabBar from "./TabBar";
import PRDView from "./PRDView";
import ConceptualERD from "./ConceptualERD";
import LogicalModel from "./LogicalModel";
import DetailedRequirements from "./DetailedRequirements";
import EmptyState from "../shared/EmptyState";
import GateApproval from "../gates/GateApproval";

function getTabsForStep(step: number, enableFlags: boolean): string[] {
  const config = getStepConfig(step as any);
  const tabs = [config.tab_name];
  if (step === 2) tabs.push("Relationships");
  if (step === 4) tabs.push("Completeness");
  if (enableFlags && step >= 3) tabs.push("Flags");
  return tabs;
}

export default function ArtifactPanel() {
  const { state, dispatch } = useAppState();
  const { theme } = useTheme();
  const currentStep = state.lifecycle.current_step;
  const tabs = getTabsForStep(currentStep, theme.features.enableFlagSystem);
  const activeTab = state.ui.activeArtifactTab;

  // Ensure active tab is valid for current step
  const resolvedTab = tabs.includes(activeTab) ? activeTab : tabs[0];

  const handleTabChange = (tab: string) => {
    dispatch({ type: "SET_ACTIVE_TAB", tab });
  };

  const renderContent = () => {
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
      className="flex flex-col"
      style={{ width: `${theme.layout.artifactPanelPercent}%` }}
    >
      <TabBar tabs={tabs} activeTab={resolvedTab} onTabChange={handleTabChange} />
      <div className="flex-1 flex flex-col overflow-y-auto">
        {renderContent()}
        {/* Gate approval at bottom of scroll — user must scroll to reach it */}
        <GateApproval />
      </div>
    </div>
  );
}
