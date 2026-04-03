/**
 * SettingsPanel — Runtime theme customization UI
 *
 * Opens as a slide-out drawer from the right edge. Allows users to:
 * 1. Pick a preset theme (Sana, phData, Dark, Minimal)
 * 2. Override individual parameters (brand name, colors, layout, features)
 * 3. Reset to defaults
 * 4. Copy current config as JSON or URL params
 *
 * Triggered by a gear icon in the sidebar or Ctrl+Shift+S.
 */

import { useState, type ChangeEvent } from "react";
import { useTheme } from "../../context/ThemeContext";
import { THEME_PRESETS, type ThemeConfig } from "../../lib/theme-config";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const { theme, updateTheme, loadPreset, resetTheme, presetNames, activePreset } = useTheme();
  const [activeSection, setActiveSection] = useState<string>("presets");
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  if (!isOpen) return null;

  const sections = [
    { id: "presets", label: "Presets" },
    { id: "brand", label: "Brand" },
    { id: "colors", label: "Colors" },
    { id: "layout", label: "Layout" },
    { id: "agent", label: "Agent" },
    { id: "sidebar", label: "Sidebar" },
    { id: "steps", label: "Steps & Gates" },
    { id: "scenario", label: "Demo Scenario" },
    { id: "features", label: "Features" },
    { id: "export", label: "Export / Import" },
  ];

  function handleColorChange(path: string, value: string) {
    const parts = path.split(".");
    const update: any = {};
    let current = update;
    for (let i = 0; i < parts.length - 1; i++) {
      current[parts[i]] = {};
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;
    updateTheme(update);
  }

  function handleTextChange(path: string, value: string) {
    handleColorChange(path, value); // same logic, different name for clarity
  }

  function handleNumberChange(path: string, value: number) {
    const parts = path.split(".");
    const update: any = {};
    let current = update;
    for (let i = 0; i < parts.length - 1; i++) {
      current[parts[i]] = {};
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;
    updateTheme(update);
  }

  function handleBoolChange(path: string, value: boolean) {
    const parts = path.split(".");
    const update: any = {};
    let current = update;
    for (let i = 0; i < parts.length - 1; i++) {
      current[parts[i]] = {};
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;
    updateTheme(update);
  }

  function copyAsJSON() {
    navigator.clipboard.writeText(JSON.stringify(theme, null, 2));
    setCopyFeedback("Copied JSON!");
    setTimeout(() => setCopyFeedback(null), 1500);
  }

  function copyAsURL() {
    const params = flattenToParams(theme);
    const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
    navigator.clipboard.writeText(url);
    setCopyFeedback("Copied URL!");
    setTimeout(() => setCopyFeedback(null), 1500);
  }

  function importJSON() {
    const input = prompt("Paste theme JSON:");
    if (!input) return;
    try {
      const parsed = JSON.parse(input);
      updateTheme(parsed);
    } catch {
      alert("Invalid JSON");
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ backgroundColor: "rgba(0,0,0,0.15)" }}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="fixed right-0 top-0 bottom-0 z-50 flex flex-col overflow-hidden shadow-xl"
        style={{
          width: "380px",
          backgroundColor: "var(--white)",
          borderLeft: "1px solid var(--border-subtle)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 border-b shrink-0"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Theme Settings
          </span>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-md text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            ✕
          </button>
        </div>

        {/* Section tabs */}
        <div
          className="flex flex-wrap gap-1 px-3 py-2 border-b shrink-0 overflow-x-auto"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          {sections.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              className="px-2 py-1 text-xs rounded-md shrink-0"
              style={{
                backgroundColor: activeSection === s.id ? "var(--surface-active-nav)" : "transparent",
                color: "var(--text-primary)",
                fontWeight: activeSection === s.id ? 500 : 400,
              }}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">

          {/* ── Presets ── */}
          {activeSection === "presets" && (
            <div className="space-y-3">
              <Label>Select a Preset</Label>
              <div className="grid grid-cols-2 gap-2">
                {presetNames.map((name) => (
                  <button
                    key={name}
                    onClick={() => loadPreset(name)}
                    className="px-3 py-2 text-sm rounded-lg border text-left"
                    style={{
                      borderColor: activePreset === name ? "var(--accent-teal)" : "var(--border-subtle)",
                      backgroundColor: activePreset === name ? "var(--accent-teal-surface)" : "var(--white)",
                      color: "var(--text-primary)",
                      fontWeight: activePreset === name ? 500 : 400,
                    }}
                  >
                    {name.charAt(0).toUpperCase() + name.slice(1)}
                  </button>
                ))}
              </div>
              <button
                onClick={resetTheme}
                className="text-xs underline"
                style={{ color: "var(--text-secondary)" }}
              >
                Reset to Sana default
              </button>
            </div>
          )}

          {/* ── Brand ── */}
          {activeSection === "brand" && (
            <div className="space-y-3">
              <TextInput label="Platform Name" value={theme.brand.platformName} onChange={(v) => handleTextChange("brand.platformName", v)} />
              <TextInput label="Product Name" value={theme.brand.productName} onChange={(v) => handleTextChange("brand.productName", v)} />
              <TextInput label="Company Name" value={theme.brand.companyName} onChange={(v) => handleTextChange("brand.companyName", v)} />
              <TextInput label="Logo URL (or blank for text)" value={theme.brand.logoUrl || ""} onChange={(v) => handleTextChange("brand.logoUrl", v || "")} />
            </div>
          )}

          {/* ── Colors ── */}
          {activeSection === "colors" && (
            <div className="space-y-3">
              <Label>Accent Color</Label>
              <ColorInput value={theme.colors.accent} onChange={(v) => handleColorChange("colors.accent", v)} />
              <ColorInput label="Accent Surface" value={theme.colors.accentSurface} onChange={(v) => handleColorChange("colors.accentSurface", v)} />

              <Label>Surfaces</Label>
              <ColorInput label="Background" value={theme.colors.white} onChange={(v) => handleColorChange("colors.white", v)} />
              <ColorInput label="Subtle" value={theme.colors.surfaceSubtle} onChange={(v) => handleColorChange("colors.surfaceSubtle", v)} />
              <ColorInput label="Input" value={theme.colors.surfaceInput} onChange={(v) => handleColorChange("colors.surfaceInput", v)} />

              <Label>Text</Label>
              <ColorInput label="Primary" value={theme.colors.textPrimary} onChange={(v) => handleColorChange("colors.textPrimary", v)} />
              <ColorInput label="Secondary" value={theme.colors.textSecondary} onChange={(v) => handleColorChange("colors.textSecondary", v)} />

              <Label>Buttons</Label>
              <ColorInput label="Primary BG" value={theme.colors.btnPrimaryBg} onChange={(v) => handleColorChange("colors.btnPrimaryBg", v)} />
              <ColorInput label="Primary Text" value={theme.colors.btnPrimaryText} onChange={(v) => handleColorChange("colors.btnPrimaryText", v)} />
            </div>
          )}

          {/* ── Layout ── */}
          {activeSection === "layout" && (
            <div className="space-y-3">
              <NumberInput label="Sidebar Width (px)" value={theme.layout.sidebarWidth} onChange={(v) => handleNumberChange("layout.sidebarWidth", v)} min={180} max={400} />
              <NumberInput label="Chat Panel (%)" value={theme.layout.chatPanelPercent} onChange={(v) => { handleNumberChange("layout.chatPanelPercent", v); handleNumberChange("layout.artifactPanelPercent", 100 - v); }} min={25} max={65} />
              <NumberInput label="Input Border Radius (px)" value={theme.layout.borderRadius.input} onChange={(v) => handleNumberChange("layout.borderRadius.input", v)} min={0} max={50} />
              <NumberInput label="Card Border Radius (px)" value={theme.layout.borderRadius.card} onChange={(v) => handleNumberChange("layout.borderRadius.card", v)} min={0} max={24} />
              <NumberInput label="Context Bar Height (px)" value={theme.layout.contextBarHeight} onChange={(v) => handleNumberChange("layout.contextBarHeight", v)} min={32} max={64} />
              <NumberInput label="Gate Banner Height (px)" value={theme.layout.gateBannerHeight} onChange={(v) => handleNumberChange("layout.gateBannerHeight", v)} min={48} max={96} />
            </div>
          )}

          {/* ── Agent ── */}
          {activeSection === "agent" && (
            <div className="space-y-3">
              <TextInput label="Avatar Label" value={theme.agent.avatarLabel} onChange={(v) => handleTextChange("agent.avatarLabel", v)} />
              <ColorInput label="Avatar BG" value={theme.agent.avatarBgColor} onChange={(v) => handleColorChange("agent.avatarBgColor", v)} />
              <TextInput label="Input Placeholder" value={theme.agent.inputPlaceholder} onChange={(v) => handleTextChange("agent.inputPlaceholder", v)} />
              <NumberInput label="Thinking Delay (ms)" value={theme.agent.thinkingDelayMs} onChange={(v) => handleNumberChange("agent.thinkingDelayMs", v)} min={0} max={2000} />
              <NumberInput label="Max Suggested Replies" value={theme.agent.maxSuggestedReplies} onChange={(v) => handleNumberChange("agent.maxSuggestedReplies", v)} min={1} max={5} />
              <TextInput label="Default Greeting" value={theme.agent.defaultGreeting} onChange={(v) => handleTextChange("agent.defaultGreeting", v)} multiline />
            </div>
          )}

          {/* ── Sidebar ── */}
          {activeSection === "sidebar" && (
            <div className="space-y-3">
              <TextInput label="Workflow Folder Label" value={theme.sidebar.workflowFolderLabel} onChange={(v) => handleTextChange("sidebar.workflowFolderLabel", v)} />
              <TextInput label="New Item Label" value={theme.sidebar.newItemLabel} onChange={(v) => handleTextChange("sidebar.newItemLabel", v)} />
              <Toggle label="Show Step Numbers" value={theme.sidebar.showStepNumbers} onChange={(v) => handleBoolChange("sidebar.showStepNumbers", v)} />
              <Toggle label="Show Status Dots" value={theme.sidebar.showStatusDots} onChange={(v) => handleBoolChange("sidebar.showStatusDots", v)} />
            </div>
          )}

          {/* ── Steps & Gates ── */}
          {activeSection === "steps" && (
            <div className="space-y-3">
              <TextInput label="Step 1 Label" value={theme.steps.step1Label} onChange={(v) => handleTextChange("steps.step1Label", v)} />
              <TextInput label="Step 2 Label" value={theme.steps.step2Label} onChange={(v) => handleTextChange("steps.step2Label", v)} />
              <TextInput label="Step 3 Label" value={theme.steps.step3Label} onChange={(v) => handleTextChange("steps.step3Label", v)} />
              <TextInput label="Step 4 Label" value={theme.steps.step4Label} onChange={(v) => handleTextChange("steps.step4Label", v)} />
              <hr style={{ borderColor: "var(--border-subtle)" }} />
              <TextInput label="Approve Button Text" value={theme.gates.approveButtonText} onChange={(v) => handleTextChange("gates.approveButtonText", v)} />
              <TextInput label="Request Changes Text" value={theme.gates.requestChangesText} onChange={(v) => handleTextChange("gates.requestChangesText", v)} />
            </div>
          )}

          {/* ── Demo Scenario ── */}
          {activeSection === "scenario" && (
            <div className="space-y-3">
              <TextInput label="Data Product Name" value={theme.scenario.dataProductName} onChange={(v) => handleTextChange("scenario.dataProductName", v)} />
              <TextInput label="Owner Name" value={theme.scenario.ownerName} onChange={(v) => handleTextChange("scenario.ownerName", v)} />
              <TextInput label="Owner Title" value={theme.scenario.ownerTitle} onChange={(v) => handleTextChange("scenario.ownerTitle", v)} />
              <TextInput label="Trigger Email" value={theme.scenario.triggerEmail || ""} onChange={(v) => handleTextChange("scenario.triggerEmail", v)} multiline />
            </div>
          )}

          {/* ── Features ── */}
          {activeSection === "features" && (
            <div className="space-y-3">
              <Toggle label="Show Step 0 (Stakeholder Alignment)" value={theme.features.showStep0} onChange={(v) => handleBoolChange("features.showStep0", v)} />
              <Toggle label="Inline Edit on Artifact Fields" value={theme.features.enableInlineEdit} onChange={(v) => handleBoolChange("features.enableInlineEdit", v)} />
              <Toggle label="Keyboard Shortcuts" value={theme.features.enableKeyboardShortcuts} onChange={(v) => handleBoolChange("features.enableKeyboardShortcuts", v)} />
              <Toggle label="Source Context Badges" value={theme.features.enableSourceContext} onChange={(v) => handleBoolChange("features.enableSourceContext", v)} />
              <Toggle label="Quality Flag System" value={theme.features.enableFlagSystem} onChange={(v) => handleBoolChange("features.enableFlagSystem", v)} />
              <Toggle label="Google Sheets Persistence" value={theme.features.enableGoogleSheets} onChange={(v) => handleBoolChange("features.enableGoogleSheets", v)} />
              <Toggle label="Completeness Bar" value={theme.features.showCompletenessBar} onChange={(v) => handleBoolChange("features.showCompletenessBar", v)} />
              <Toggle label="Field Highlight Animation" value={theme.features.showFieldHighlightAnimation} onChange={(v) => handleBoolChange("features.showFieldHighlightAnimation", v)} />
            </div>
          )}

          {/* ── Export / Import ── */}
          {activeSection === "export" && (
            <div className="space-y-3">
              <button onClick={copyAsJSON} className="w-full px-3 py-2 text-sm rounded-lg border" style={{ borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}>
                Copy Current Theme as JSON
              </button>
              <button onClick={copyAsURL} className="w-full px-3 py-2 text-sm rounded-lg border" style={{ borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}>
                Copy as Shareable URL
              </button>
              <button onClick={importJSON} className="w-full px-3 py-2 text-sm rounded-lg border" style={{ borderColor: "var(--border-subtle)", color: "var(--text-primary)" }}>
                Import Theme from JSON
              </button>
              {copyFeedback && (
                <p className="text-xs text-center" style={{ color: "var(--accent-teal)" }}>
                  {copyFeedback}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ─── Sub-components ───

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
      {children}
    </p>
  );
}

function TextInput({ label, value, onChange, multiline }: { label: string; value: string; onChange: (v: string) => void; multiline?: boolean }) {
  const Tag = multiline ? "textarea" : "input";
  return (
    <div>
      <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>{label}</label>
      <Tag
        value={value}
        onChange={(e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(e.target.value)}
        className="w-full px-2 py-1.5 text-sm rounded-md outline-none"
        style={{
          backgroundColor: "var(--surface-input)",
          color: "var(--text-primary)",
          border: "none",
          ...(multiline ? { minHeight: "64px", resize: "vertical" as const } : {}),
        }}
      />
    </div>
  );
}

function ColorInput({ label, value, onChange }: { label?: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-8 h-8 rounded border-0 cursor-pointer"
        style={{ backgroundColor: value }}
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 px-2 py-1 text-xs rounded-md font-mono"
        style={{ backgroundColor: "var(--surface-input)", color: "var(--text-primary)" }}
      />
      {label && <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</span>}
    </div>
  );
}

function NumberInput({ label, value, onChange, min, max }: { label: string; value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  return (
    <div>
      <label className="block text-xs mb-1" style={{ color: "var(--text-secondary)" }}>{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="range"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1"
        />
        <span className="text-xs font-mono w-10 text-right" style={{ color: "var(--text-primary)" }}>
          {value}
        </span>
      </div>
    </div>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm" style={{ color: "var(--text-primary)" }}>{label}</span>
      <button
        onClick={() => onChange(!value)}
        className="w-10 h-5 rounded-full relative transition-colors"
        style={{ backgroundColor: value ? "var(--accent-teal)" : "var(--surface-active-nav)" }}
      >
        <div
          className="w-4 h-4 rounded-full absolute top-0.5 transition-transform"
          style={{
            backgroundColor: "var(--white)",
            transform: value ? "translateX(21px)" : "translateX(2px)",
            boxShadow: "0 1px 2px rgba(0,0,0,0.15)",
          }}
        />
      </button>
    </div>
  );
}

// ─── Helper: Flatten theme to URL params ───

function flattenToParams(obj: any, prefix = ""): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const nested = flattenToParams(value, fullKey);
      for (const [k, v] of nested.entries()) {
        params.set(k, v);
      }
    } else if (value !== null && value !== undefined) {
      params.set(fullKey, String(value));
    }
  }
  return params;
}
