import { useAppState } from "../../context/AppContext";
import { useTheme } from "../../context/ThemeContext";
import EntityCard from "./EntityCard";
import EmptyState from "../shared/EmptyState";

interface ConceptualERDProps {
  activeTab: string;
}

export default function ConceptualERD({ activeTab }: ConceptualERDProps) {
  const { state } = useAppState();
  const { theme } = useTheme();
  const model = state.artifacts.conceptual;

  if (!model || model.entities.length === 0) {
    return <EmptyState stepNumber={2} tabName="Conceptual Model" />;
  }

  if (activeTab === "Relationships") {
    return (
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <h3
          className="text-xs font-semibold uppercase tracking-wider mb-3"
          style={{ color: theme.colors.textSecondary }}
        >
          Entity Relationships
        </h3>
        <div className="flex flex-col gap-2">
          {model.relationships.map((rel, i) => (
            <div
              key={i}
              className="flex items-center gap-2 px-3 py-2 rounded text-sm"
              style={{
                backgroundColor: theme.colors.surfaceSubtle,
                color: theme.colors.textPrimary,
              }}
            >
              <span className="font-medium">{rel.from_entity}</span>
              <span style={{ color: theme.colors.textTertiary }}>&rarr;</span>
              <span style={{ color: theme.colors.textSecondary }}>{rel.verb}</span>
              <span style={{ color: theme.colors.textTertiary }}>&rarr;</span>
              <span className="font-medium">{rel.to_entity}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <div className="grid grid-cols-2 gap-3">
        {model.entities.map((entity) => (
          <EntityCard key={entity.entity_id} entity={entity} />
        ))}
      </div>
    </div>
  );
}
