import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  SANA_THEME,
  THEME_PRESETS,
  mergeTheme,
  parseThemeFromUrl,
  type ThemeConfig,
} from "../lib/theme-config";

// ─── Context Shape ───

interface ThemeContextType {
  theme: ThemeConfig;
  setTheme: (config: ThemeConfig) => void;
  updateTheme: (overrides: Partial<ThemeConfig> | any) => void;
  loadPreset: (presetName: string) => void;
  resetTheme: () => void;
  presetNames: string[];
  activePreset: string | null;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

// ─── Provider ───

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeConfig>(SANA_THEME);
  const [activePreset, setActivePreset] = useState<string | null>("sana");

  // On mount: check URL params for theme overrides
  useEffect(() => {
    const urlOverrides = parseThemeFromUrl();
    if (urlOverrides) {
      setThemeState(mergeTheme(SANA_THEME, urlOverrides));
      // Check if it matches a preset exactly
      const presetName = new URLSearchParams(window.location.search).get("theme");
      setActivePreset(presetName && THEME_PRESETS[presetName] ? presetName : "custom");
    }

    // Also check localStorage for saved theme
    const savedTheme = localStorage.getItem("dsa-theme");
    if (savedTheme && !urlOverrides) {
      try {
        const parsed = JSON.parse(savedTheme);
        setThemeState(mergeTheme(SANA_THEME, parsed));
        setActivePreset(localStorage.getItem("dsa-theme-preset") || "custom");
      } catch {
        // Invalid JSON — ignore
      }
    }
  }, []);

  // Apply theme to CSS custom properties whenever it changes
  useEffect(() => {
    applyThemeToCSSVariables(theme);
  }, [theme]);

  // Persist to localStorage on change
  useEffect(() => {
    localStorage.setItem("dsa-theme", JSON.stringify(theme));
    if (activePreset) localStorage.setItem("dsa-theme-preset", activePreset);
  }, [theme, activePreset]);

  const setTheme = useCallback((config: ThemeConfig) => {
    setThemeState(config);
    setActivePreset("custom");
  }, []);

  const updateTheme = useCallback(
    (overrides: any) => {
      setThemeState((prev) => mergeTheme(prev, overrides));
      setActivePreset("custom");
    },
    []
  );

  const loadPreset = useCallback((presetName: string) => {
    const preset = THEME_PRESETS[presetName];
    if (preset) {
      setThemeState(preset);
      setActivePreset(presetName);
    }
  }, []);

  const resetTheme = useCallback(() => {
    setThemeState(SANA_THEME);
    setActivePreset("sana");
    localStorage.removeItem("dsa-theme");
    localStorage.removeItem("dsa-theme-preset");
  }, []);

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        updateTheme,
        loadPreset,
        resetTheme,
        presetNames: Object.keys(THEME_PRESETS),
        activePreset,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

// ─── Hook ───

export function useTheme(): ThemeContextType {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

// ─── CSS Variable Applicator ───

function applyThemeToCSSVariables(theme: ThemeConfig) {
  const root = document.documentElement;

  // Colors
  root.style.setProperty("--white", theme.colors.white);
  root.style.setProperty("--surface-subtle", theme.colors.surfaceSubtle);
  root.style.setProperty("--surface-input", theme.colors.surfaceInput);
  root.style.setProperty("--surface-active-nav", theme.colors.surfaceActiveNav);
  root.style.setProperty("--surface-hover", theme.colors.surfaceHover);
  root.style.setProperty("--text-primary", theme.colors.textPrimary);
  root.style.setProperty("--text-secondary", theme.colors.textSecondary);
  root.style.setProperty("--text-tertiary", theme.colors.textTertiary);
  root.style.setProperty("--border-subtle", theme.colors.borderSubtle);
  root.style.setProperty("--btn-primary-bg", theme.colors.btnPrimaryBg);
  root.style.setProperty("--btn-primary-text", theme.colors.btnPrimaryText);
  root.style.setProperty("--btn-primary-hover", theme.colors.btnPrimaryHover);
  root.style.setProperty("--accent-teal", theme.colors.accent);
  root.style.setProperty("--accent-teal-surface", theme.colors.accentSurface);
  root.style.setProperty("--amber-flag", theme.colors.flagAmber);
  root.style.setProperty("--amber-surface", theme.colors.flagAmberSurface);
  root.style.setProperty("--red-flag", theme.colors.flagRed);
  root.style.setProperty("--blue-flag", theme.colors.flagBlue);
  root.style.setProperty("--gray-flag", theme.colors.flagGray);
  root.style.setProperty("--entity-fact", theme.colors.entityFact);
  root.style.setProperty("--entity-dim", theme.colors.entityDim);
  root.style.setProperty("--entity-ref", theme.colors.entityRef);
  root.style.setProperty("--entity-primary", theme.colors.entityPrimary);

  // Layout
  root.style.setProperty("--sidebar-width", `${theme.layout.sidebarWidth}px`);
  root.style.setProperty("--context-bar-height", `${theme.layout.contextBarHeight}px`);
  root.style.setProperty("--gate-banner-height", `${theme.layout.gateBannerHeight}px`);
  root.style.setProperty("--chat-ratio", `${theme.layout.chatPanelPercent}%`);
  root.style.setProperty("--artifact-ratio", `${theme.layout.artifactPanelPercent}%`);
  root.style.setProperty("--radius-nav", `${theme.layout.borderRadius.nav}px`);
  root.style.setProperty("--radius-input", `${theme.layout.borderRadius.input}px`);
  root.style.setProperty("--radius-card", `${theme.layout.borderRadius.card}px`);
  root.style.setProperty("--radius-badge", `${theme.layout.borderRadius.badge}px`);
  root.style.setProperty("--radius-pill", `${theme.layout.borderRadius.pill}px`);
  root.style.setProperty("--radius-btn", `${theme.layout.borderRadius.button}px`);

  // Typography
  root.style.setProperty("--font-sans", theme.typography.fontFamily);
  root.style.setProperty("--font-mono", theme.typography.monoFamily);

  // Body font
  document.body.style.fontFamily = theme.typography.fontFamily;
  document.body.style.fontSize = `${theme.typography.baseFontSize}px`;
  document.body.style.color = theme.colors.textPrimary;
  document.body.style.backgroundColor = theme.colors.white;
}
