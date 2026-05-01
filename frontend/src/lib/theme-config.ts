/**
 * DSA MVP — Runtime Theme Configuration
 *
 * This module allows the entire frontend to be re-skinned on demand.
 * Users can change branding, colors, layout, typography, agent persona,
 * demo scenario content, and sidebar labels — all at runtime via a
 * settings panel or URL parameters.
 *
 * HOW IT WORKS:
 * 1. ThemeConfig defines every tunable parameter.
 * 2. ThemeContext provides the active config to all components.
 * 3. Components read from ThemeContext instead of hardcoded values.
 * 4. The Settings Panel (or URL params) writes to ThemeContext.
 * 5. CSS custom properties update in real-time via useThemeApplicator().
 *
 * IMPORTANT FOR COMPONENT AUTHORS:
 * Never hardcode colors, brand names, layout values, or agent text.
 * Always read from useTheme(). The tokens.css file provides defaults
 * but the runtime config overrides them.
 */

// ─── Theme Configuration Shape ───

export interface ThemeConfig {
  // — Brand Identity —
  brand: {
    platformName: string;       // e.g. "Workday Sana", "Acme Analytics"
    productName: string;        // e.g. "DSA", "Data Product Studio"
    logoUrl: string | null;     // URL or base64 — null = text-only
    logoAltText: string;
    companyName: string;        // e.g. "Workday", "Acme Corp"
  };

  // — Color Palette —
  colors: {
    // Surfaces
    white: string;
    surfaceSubtle: string;
    surfaceInput: string;
    surfaceActiveNav: string;
    surfaceHover: string;

    // Text
    textPrimary: string;
    textSecondary: string;
    textTertiary: string;

    // Borders
    borderSubtle: string;

    // Primary actions
    btnPrimaryBg: string;
    btnPrimaryText: string;
    btnPrimaryHover: string;

    // Accent — the signature color (teal in Sana theme)
    accent: string;
    accentSurface: string;

    // Semantic
    flagAmber: string;
    flagAmberSurface: string;
    flagRed: string;
    flagBlue: string;
    flagGray: string;
    flagPurple: string;
    flagPurpleSurface: string;

    // Entity card borders (Step 2)
    entityFact: string;
    entityDim: string;
    entityRef: string;
    entityPrimary: string;
  };

  // — Typography —
  typography: {
    fontFamily: string;         // e.g. "'Inter', sans-serif"
    monoFamily: string;         // e.g. "'JetBrains Mono', monospace"
    baseFontSize: number;       // px, default 14
    headingWeight: number;      // 600 or 700
    bodyWeight: number;         // 400
    mediumWeight: number;       // 500
  };

  // — Layout —
  layout: {
    sidebarWidth: number;       // px, default 264
    contextBarHeight: number;   // px, default 44
    gateBannerHeight: number;   // px, default 64
    chatPanelPercent: number;   // 0-100, default 42
    artifactPanelPercent: number; // 0-100, default 58
    borderRadius: {
      nav: number;              // px, default 8
      input: number;            // px, default 24
      card: number;             // px, default 10
      badge: number;            // px, default 4
      pill: number;             // px, default 16
      button: number;           // px, default 8
    };
  };

  // — Agent Configuration —
  agent: {
    avatarLabel: string;        // e.g. "DSA", "AI", "Bot"
    avatarBgColor: string;      // defaults to surfaceActiveNav
    avatarTextColor: string;    // defaults to textPrimary
    defaultGreeting: string;    // opening message when no scenario loaded
    inputPlaceholder: string;   // e.g. "Reply to the agent…"
    thinkingDelayMs: number;    // ms before typing indicator, default 400
    maxSuggestedReplies: number; // default 3
  };

  // — Sidebar Configuration —
  sidebar: {
    workflowFolderLabel: string;  // e.g. "DSA Workflows", "My Projects"
    showStepNumbers: boolean;     // show "1 —" prefix on steps
    showStatusDots: boolean;      // show teal/amber/gray indicators
    newItemLabel: string;         // e.g. "+ New chat", "+ New project"
    navItems: SidebarNavItem[];   // additional nav items above the workflow folder
  };

  // — Step Labels (allows renaming steps without code changes) —
  steps: {
    step0Label: string;
    step1Label: string;
    step2Label: string;
    step3Label: string;
    step4Label: string;
  };

  // — Gate Labels —
  gates: {
    gate1Label: string;
    gate2Label: string;
    gate3Label: string;
    gate4Label: string;
    approveButtonText: string;    // e.g. "Approve →"
    requestChangesText: string;   // e.g. "Request Changes"
    gateIconType: "shield" | "check" | "lock" | "none";
  };

  // — Demo Scenario (swappable) —
  scenario: {
    dataProductName: string;    // e.g. "New Data Product"
    dataProductId: string;      // e.g. "dp-romi-001"
    ownerName: string;          // e.g. "Jennifer Moss"
    ownerTitle: string;         // e.g. "VP Marketing Operations"
    triggerEmail: string | null; // The "starting email" — null to skip
  };

  // — Feature Flags —
  features: {
    showStep0: boolean;           // show optional Stakeholder Alignment step
    enableInlineEdit: boolean;    // allow editing artifact fields directly
    enableKeyboardShortcuts: boolean;
    enableSourceContext: boolean;  // show source system badges in chat
    enableFlagSystem: boolean;    // show quality flags in Steps 3-4
    enableGoogleSheets: boolean;  // persist to Sheets (vs local-only)
    showCompletenessBar: boolean;
    showFieldHighlightAnimation: boolean;
    enableStandardsView: boolean;     // show Standards tab on all steps
    enableStandardsValidation: boolean; // validate edits against standards
    enableVisualGraph: boolean;       // show Visual graph tab on all steps
  };
}

export interface SidebarNavItem {
  icon: string;   // emoji or icon name
  label: string;
  href?: string;
}

// ─── Default Theme: Sana (Workday) ───

export const SANA_THEME: ThemeConfig = {
  brand: {
    platformName: "Workday Sana",
    productName: "DSA",
    logoUrl: null,
    logoAltText: "Workday Sana",
    companyName: "Workday",
  },
  colors: {
    white: "#FFFFFF",
    surfaceSubtle: "#FAFAFA",
    surfaceInput: "#F4F4F4",
    surfaceActiveNav: "#EBEBEB",
    surfaceHover: "#F5F5F5",
    textPrimary: "#1A1A1A",
    textSecondary: "#6B6B6B",
    textTertiary: "#9E9E9E",
    borderSubtle: "#E8E8E8",
    btnPrimaryBg: "#1A1A1A",
    btnPrimaryText: "#FFFFFF",
    btnPrimaryHover: "#333333",
    accent: "#3DDBB8",
    accentSurface: "#E8FBF6",
    flagAmber: "#D97706",
    flagAmberSurface: "#FEF3C7",
    flagRed: "#EF4444",
    flagBlue: "#3B82F6",
    flagGray: "#9CA3AF",
    flagPurple: "#8B5CF6",
    flagPurpleSurface: "#EDE9FE",
    entityFact: "#BFDBFE",
    entityDim: "#99F6E4",
    entityRef: "#FDE68A",
    entityPrimary: "#3DDBB8",
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    monoFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    baseFontSize: 14,
    headingWeight: 600,
    bodyWeight: 400,
    mediumWeight: 500,
  },
  layout: {
    sidebarWidth: 264,
    contextBarHeight: 44,
    gateBannerHeight: 64,
    chatPanelPercent: 42,
    artifactPanelPercent: 58,
    borderRadius: { nav: 8, input: 24, card: 10, badge: 4, pill: 16, button: 8 },
  },
  agent: {
    avatarLabel: "DSA",
    avatarBgColor: "#EBEBEB",
    avatarTextColor: "#1A1A1A",
    defaultGreeting: "Let's build your next data product. What business question do you need this data to answer?",
    inputPlaceholder: "Reply to the agent…",
    thinkingDelayMs: 400,
    maxSuggestedReplies: 3,
  },
  sidebar: {
    workflowFolderLabel: "DSA Workflows",
    showStepNumbers: true,
    showStatusDots: true,
    newItemLabel: "+ New chat",
    navItems: [],
  },
  steps: {
    step0Label: "Stakeholder Alignment",
    step1Label: "Requirements",
    step2Label: "Conceptual Model",
    step3Label: "Logical Model",
    step4Label: "Detailed Requirements",
  },
  gates: {
    gate1Label: "PRD Review",
    gate2Label: "Conceptual Model Review",
    gate3Label: "Logical Model Review",
    gate4Label: "Final Requirements Review",
    approveButtonText: "Approve →",
    requestChangesText: "Request Changes",
    gateIconType: "shield",
  },
  scenario: {
    dataProductName: "New Data Product",
    dataProductId: "dp-romi-001",
    ownerName: "Jennifer Moss",
    ownerTitle: "VP Marketing Operations",
    triggerEmail: `FROM: Jennifer Moss <j.moss@company.com>\nTO: analytics-team@company.com\nDATE: March 24, 2026 — 9:14 AM\nSUBJECT: ROMI Dashboard — can we get this built?\n\nHi team,\n\nComing out of the board meeting last week, there's a strong ask for better visibility into marketing ROI. Right now we're doing this manually every quarter and it takes weeks.\n\nCan we get a data product built that shows ROMI by channel and campaign? Finance wants to be able to reproduce the numbers we show the board, and the campaign managers want to see their own performance without having to ask us every time.\n\nLet me know what you need from me.\n\n— Jen`,
  },
  features: {
    showStep0: false,
    enableInlineEdit: true,
    enableKeyboardShortcuts: true,
    enableSourceContext: true,
    enableFlagSystem: true,
    enableGoogleSheets: false,
    showCompletenessBar: true,
    showFieldHighlightAnimation: true,
    enableStandardsView: true,
    enableStandardsValidation: true,
    enableVisualGraph: true,
  },
};

// ─── Preset: phData Brand ───

export const PHDATA_THEME: ThemeConfig = {
  ...SANA_THEME,
  brand: {
    platformName: "phData",
    productName: "Data Product Studio",
    logoUrl: null,
    logoAltText: "phData",
    companyName: "phData",
  },
  colors: {
    ...SANA_THEME.colors,
    accent: "#2E75B6",
    accentSurface: "#D5E8F0",
    btnPrimaryBg: "#1B2A4A",
    btnPrimaryHover: "#2E3F5E",
    entityPrimary: "#2E75B6",
    entityDim: "#B4DED3",
  },
  agent: {
    ...SANA_THEME.agent,
    avatarLabel: "DPS",
    avatarBgColor: "#D5E8F0",
    avatarTextColor: "#1B2A4A",
  },
  sidebar: {
    ...SANA_THEME.sidebar,
    workflowFolderLabel: "Data Products",
    newItemLabel: "+ New Data Product",
    navItems: [
      { icon: "📊", label: "Dashboard" },
      { icon: "🔍", label: "Catalog" },
      { icon: "⚙️", label: "Settings" },
    ],
  },
};

// ─── Preset: Dark Mode ───

export const DARK_THEME: ThemeConfig = {
  ...SANA_THEME,
  colors: {
    ...SANA_THEME.colors,
    white: "#1A1A2E",
    surfaceSubtle: "#16213E",
    surfaceInput: "#0F3460",
    surfaceActiveNav: "#1A1A40",
    surfaceHover: "#1F2A48",
    textPrimary: "#E8E8E8",
    textSecondary: "#9E9EAE",
    textTertiary: "#6B6B7B",
    borderSubtle: "#2A2A3E",
    btnPrimaryBg: "#3DDBB8",
    btnPrimaryText: "#1A1A2E",
    btnPrimaryHover: "#5DE8CB",
  },
};

// ─── Preset: Minimal / Neutral ───

export const MINIMAL_THEME: ThemeConfig = {
  ...SANA_THEME,
  brand: {
    platformName: "Data Studio",
    productName: "Agent",
    logoUrl: null,
    logoAltText: "Data Studio",
    companyName: "",
  },
  colors: {
    ...SANA_THEME.colors,
    accent: "#6366F1",           // Indigo
    accentSurface: "#EEF2FF",
    entityPrimary: "#6366F1",
  },
  agent: {
    ...SANA_THEME.agent,
    avatarLabel: "AI",
  },
  sidebar: {
    ...SANA_THEME.sidebar,
    workflowFolderLabel: "Projects",
    newItemLabel: "+ New Project",
    navItems: [],
  },
};

// ─── Preset Registry ───

export const THEME_PRESETS: Record<string, ThemeConfig> = {
  sana: SANA_THEME,
  phdata: PHDATA_THEME,
  dark: DARK_THEME,
  minimal: MINIMAL_THEME,
};

/**
 * Deep merge a partial config onto a base theme.
 * Allows users to override only the fields they care about.
 */
export function mergeTheme(
  base: ThemeConfig,
  overrides: DeepPartial<ThemeConfig>
): ThemeConfig {
  return deepMerge(base, overrides) as ThemeConfig;
}

type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

function deepMerge(target: any, source: any): any {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    if (
      source[key] &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key])
    ) {
      result[key] = deepMerge(target[key] || {}, source[key]);
    } else if (source[key] !== undefined) {
      result[key] = source[key];
    }
  }
  return result;
}

/**
 * Parse URL search params into theme overrides.
 * Usage: ?theme=phdata or ?brand.platformName=MyApp&colors.accent=%23FF6600
 */
export function parseThemeFromUrl(): DeepPartial<ThemeConfig> | null {
  const params = new URLSearchParams(window.location.search);
  if (params.size === 0) return null;

  // Check for preset shorthand: ?theme=phdata
  const preset = params.get("theme");
  if (preset && THEME_PRESETS[preset]) {
    // Merge any additional params on top of the preset
    const overrides = parseNestedParams(params, ["theme"]);
    return Object.keys(overrides).length > 0
      ? mergeTheme(THEME_PRESETS[preset], overrides)
      : THEME_PRESETS[preset];
  }

  // Otherwise parse individual dot-notation params
  return parseNestedParams(params);
}

function parseNestedParams(
  params: URLSearchParams,
  skipKeys: string[] = []
): DeepPartial<ThemeConfig> {
  const result: any = {};
  for (const [key, value] of params.entries()) {
    if (skipKeys.includes(key)) continue;
    const parts = key.split(".");
    let current = result;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) current[parts[i]] = {};
      current = current[parts[i]];
    }
    // Auto-detect numbers and booleans
    if (value === "true") current[parts[parts.length - 1]] = true;
    else if (value === "false") current[parts[parts.length - 1]] = false;
    else if (!isNaN(Number(value))) current[parts[parts.length - 1]] = Number(value);
    else current[parts[parts.length - 1]] = value;
  }
  return result;
}
