# Instructions for Claude Code

> **Mode:** Plan first, then execute phase by phase.
> **Read PLAN.md first.** It contains the full architecture, build order, and design constraints.
> **Then read every file in docs/.** They are the authoritative specs.

---

## What This Project Is

A standalone React app (Vite + TypeScript + Tailwind) that demonstrates a gated, AI-agent-driven data product delivery workflow. The visual language matches Workday's Sana (sana.ai) exactly. The agent is powered by Claude API with step-scoped system prompts.

## What's Already Built

The project scaffold is in place:

- **`PLAN.md`** — Master build plan with architecture, directory structure, build order, design tokens, and constraints
- **`docs/`** — All 5 reference documents (design spec, demo requirements, ROMI PRD, ROMI detailed requirements, PRD template)
- **`src/lib/types.ts`** — All TypeScript interfaces matching the persistent layer schema
- **`src/lib/constants.ts`** — Step config, gate config, layout constants, timing constants, design token values
- **`src/lib/scoring.ts`** — PRD completeness scoring logic with interview progress tracking
- **`src/lib/claude.ts`** — Claude API client wrapper with step-scoped prompts
- **`src/lib/sheets.ts`** — Google Sheets persistence layer stub (runs in local mode when not configured)
- **`src/lib/prompts.ts`** — System prompt loader with resume context injection
- **`src/lib/theme-config.ts`** — Runtime theme configuration: ThemeConfig interface, 4 presets (Sana, phData, Dark, Minimal), deep merge, URL param parsing
- **`src/context/AppContext.tsx`** — Global state provider with full reducer (lifecycle, conversation, artifacts, flags, UI)
- **`src/context/ThemeContext.tsx`** — Theme provider: reads URL params + localStorage, applies CSS variables in real-time, exposes setTheme/updateTheme/loadPreset/resetTheme
- **`src/components/shared/SettingsPanel.tsx`** — Slide-out settings drawer with 10 sections (presets, brand, colors, layout, agent, sidebar, steps, scenario, features, export/import)
- **`src/data/mock/`** — Simulated responses from Atlan, Highspot, Snowflake, and Allocadia
- **`src/data/prompts/`** — System prompts for all 4 steps
- **`src/styles/tokens.css`** — CSS custom properties matching Sana design tokens
- **`src/App.tsx`** — Shell layout stub with correct proportions (sidebar 264px, chat 42%, artifact 58%, gate banner 64px)
- **`src/main.tsx`** — Entry point wired to AppProvider
- Config files: `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `.env.example`

## What Needs To Be Built (Follow PLAN.md Build Order)

### Phase 1: Polish the Shell
The `App.tsx` stub has the correct layout proportions. Break it into proper components:
- `src/components/shell/Sidebar.tsx` — With step navigator, status indicators, product list
- `src/components/shell/ContextBar.tsx` — Product name + step + status pill
- `src/components/shell/AppShell.tsx` — Layout orchestrator that composes everything

### Phase 2: Chat Panel
- `src/components/chat/ChatPanel.tsx` — Message list with scroll, header showing agent persona
- `src/components/chat/MessageBubble.tsx` — Agent (white bg, border, left) and user (gray bg, right) bubbles
- `src/components/chat/ChatInput.tsx` — Sana-style pill input with send button
- `src/components/chat/TypingIndicator.tsx` — Three-dot animation
- `src/components/chat/SuggestedReplies.tsx` — Staggered fade-in pills (max 3)
- `src/hooks/useAgent.ts` — Hook that manages sending messages, receiving responses, updating state

### Phase 3: Artifact Panel
- `src/components/artifact/ArtifactPanel.tsx` — Container with tab bar
- `src/components/artifact/TabBar.tsx` — Tabs with teal active underline
- `src/components/artifact/PRDView.tsx` — Step 1 artifact rendering all PRD fields live
- `src/components/artifact/CompletenessBar.tsx` — Animated progress bar
- `src/components/artifact/FieldRow.tsx` — Individual field with empty state, populated state, inline edit
- `src/components/shared/EmptyState.tsx` — Contextual empty state per tab

### Phase 4: Wire the Agent (Step 1 Focus)
- Connect `useAgent.ts` to the Claude API via `src/lib/claude.ts`
- Parse agent responses to extract PRD field updates
- Update `AppContext` with each field capture
- Trigger artifact panel field population animation (teal highlight, 300ms fade)
- Generate suggested reply pills from agent responses

### Phase 5: Human Gates
- `src/components/gates/GateBanner.tsx` — Full implementation with Request Changes and Approve flows
- `src/components/gates/GateConfirmation.tsx` — Checkmark animation on approve
- Wire to `AppContext.APPROVE_GATE` action
- Keyboard shortcut: Cmd+Enter to approve

### Phase 6: Steps 2-4 Artifacts
- `src/components/artifact/ConceptualERD.tsx` — Entity cards with role badges and color-coded borders
- `src/components/artifact/EntityCard.tsx` — Reusable card component
- `src/components/artifact/LogicalModel.tsx` — Attribute-level tables with flag column
- `src/components/artifact/DetailedRequirements.tsx` — Full field mapping table
- `src/components/artifact/FlagBadge.tsx` — Color-coded flag indicators

### Phase 7: Auto-Resume
- `src/hooks/useAutoResume.ts` — Read lifecycle state on load, navigate to correct step
- `src/hooks/useLifecycleState.ts` — Read/write lifecycle state (local or Sheets)
- Implement the resume message pattern per step (see PLAN.md)

## Key Constraints (Non-Negotiable)

1. **Match the Sana visual language exactly.** Pure white surfaces, Inter font, minimal chrome. See `tokens.css`.
2. **Teal (#3DDBB8) is used in exactly 3 places:** agent avatar badge, active tab underline, completeness bar/gate CTA. Nowhere else.
3. **Chat panel is always 42% width.** Never changes. Never collapses.
4. **Agent asks one question at a time.** Never batches.
5. **Every empty state explains what will appear and when.** Never just "No data."
6. **The persistent layer schema matches target Snowflake column names exactly.** See `types.ts`.

## Demo Scenario

The ROMI (Return on Marketing Investment) data product. Start from a VP's email asking for "a ROMI dashboard" — end with a structured PRD at 87% completeness. The agent surfaces source context from Atlan, Highspot, and Snowflake inline during the conversation. See `docs/DEMO_REQUIREMENTS.md` for the full scenario and `src/data/mock/` for the pre-scripted source system responses.

---

## Runtime Theme Customization System

The entire frontend is dynamically configurable at runtime. **No visual parameter is hardcoded in components.** Everything reads from `ThemeContext`.

### Architecture

```
ThemeConfig (src/lib/theme-config.ts)
  ↓ defines the shape + 4 presets (sana, phdata, dark, minimal)
ThemeContext (src/context/ThemeContext.tsx)
  ↓ provides active config to all components
  ↓ applies config to CSS custom properties in real-time
  ↓ reads overrides from URL params (?theme=phdata) and localStorage
SettingsPanel (src/components/shared/SettingsPanel.tsx)
  ↓ slide-out drawer for live editing
  ↓ 10 sections: presets, brand, colors, layout, agent, sidebar, steps, scenario, features, export
Components
  ↓ read from useTheme() — never hardcode colors, labels, or layout values
```

### What's Configurable (Everything)

| Category | Parameters | Example |
|----------|-----------|---------|
| **Brand** | Platform name, product name, company, logo URL | "Workday Sana" → "Acme Analytics" |
| **Colors** | All 20+ color tokens (accent, surfaces, text, buttons, flags, entities) | Teal accent → Indigo accent |
| **Typography** | Font family, mono family, base size, weights | Inter → Helvetica, 14px → 16px |
| **Layout** | Sidebar width, chat/artifact split ratio, all border radii, bar heights | 42/58 split → 50/50 split |
| **Agent** | Avatar label, avatar colors, placeholder text, thinking delay, max suggested replies | "DSA" → "AI", 400ms → 800ms |
| **Sidebar** | Folder label, nav items, step numbers toggle, status dots toggle | "DSA Workflows" → "My Projects" |
| **Steps** | All step labels, all gate labels, approve/reject button text | "Requirements" → "Discovery" |
| **Scenario** | Data product name, owner, trigger email | ROMI → Customer Churn |
| **Features** | 8 feature flags (Step 0, inline edit, shortcuts, source context, flags, Sheets, completeness bar, animations) | Toggle any on/off |

### 3 Ways To Configure

1. **Settings Panel** — Click ⚙️ in sidebar or press `Ctrl+Shift+S`. Live editing with instant preview.
2. **URL Parameters** — `?theme=phdata` loads the phData preset. `?brand.platformName=Acme&colors.accent=%236366F1` overrides individual fields. Shareable URLs.
3. **JSON Import/Export** — Copy current config as JSON. Paste to restore. Useful for saving per-demo configurations.

### Rules For Component Authors

1. **Never hardcode a color.** Read from `useTheme()` — e.g. `theme.colors.accent`, not `"#3DDBB8"`.
2. **Never hardcode a label.** Read from `theme.brand.platformName`, `theme.steps.step1Label`, `theme.gates.approveButtonText`, etc.
3. **Never hardcode a layout value.** Read from `theme.layout.sidebarWidth`, `theme.layout.chatPanelPercent`, etc.
4. **Use CSS variables as fallbacks.** The `tokens.css` file provides defaults. `ThemeContext` overrides them at runtime via `document.documentElement.style.setProperty()`.
5. **Check feature flags.** Before rendering optional features, check `theme.features.*` — e.g. `theme.features.enableFlagSystem` before showing the Flags tab.
6. **Agent behavior is also themed.** `theme.agent.avatarLabel`, `theme.agent.inputPlaceholder`, `theme.agent.thinkingDelayMs` — the agent's visual presence is configurable.
