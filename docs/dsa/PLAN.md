# DSA MVP — Claude Code Build Plan

> **Read this file first. Then read every file in `docs/`. Then plan.**
> This is a standalone React application that demonstrates a gated, agent-driven data product delivery workflow. The demo scenario is a fictional ROMI (Return on Marketing Investment) data product.

---

## What You Are Building

A split-screen application where:
- **Left panel (42%)**: An AI agent interviews the user through a structured requirements workflow
- **Right panel (58%)**: A live artifact (PRD, data model, field mapping) builds in real-time as the conversation progresses
- **Bottom banner (64px)**: Human gate approval moments between steps
- **Left sidebar (264px)**: Sana-styled navigation with step indicators

The app has **4 steps** (plus an optional Step 0). Each step has its own agent persona, artifact type, and approval gate. The agent is powered by Claude API with step-scoped system prompts. State persists in Google Sheets (or local state for initial dev).

---

## Architecture Summary

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React 18 + TypeScript | Standalone SPA, no framework (Vite) |
| Styling | Tailwind CSS | Custom design tokens matching Sana UI |
| LLM | Claude API (`claude-sonnet-4-6`) | Step-scoped system prompts, no cross-step context |
| Persistent Layer | Google Sheets API (MVP) | 5 tables, one sheet per table |
| State Management | React Context + useReducer | Mirrors persistent layer schema |
| Mock Data | Local JSON files | Simulated Atlan/Snowflake/Highspot responses |

---

## Directory Structure

```
dsa-mvp/
├── PLAN.md                          ← YOU ARE HERE
├── docs/
│   ├── DESIGN_SPEC.md               ← Full UI spec (copy of DSA_MVP_UI_Design_Spec_v04.md)
│   ├── DEMO_REQUIREMENTS.md         ← Demo scenario and scripted moments
│   ├── ROMI_PRD.md                  ← Target PRD output for Step 1
│   ├── ROMI_DETAILED_REQUIREMENTS.md ← Target output for Step 4
│   └── PRD_TEMPLATE.md              ← Template the agent uses
├── src/
│   ├── main.tsx                     ← App entry point
│   ├── App.tsx                      ← Shell layout + routing
│   ├── components/
│   │   ├── shell/
│   │   │   ├── Sidebar.tsx          ← Sana-styled sidebar with step nav
│   │   │   ├── ContextBar.tsx       ← Top bar: product name + step + status
│   │   │   └── AppShell.tsx         ← Main layout orchestrator
│   │   ├── chat/
│   │   │   ├── ChatPanel.tsx        ← Agent conversation panel (42% width)
│   │   │   ├── MessageBubble.tsx    ← Agent and user message rendering
│   │   │   ├── SuggestedReplies.tsx ← Pill-style reply options (max 3)
│   │   │   ├── ChatInput.tsx        ← Sana-styled pill input
│   │   │   └── TypingIndicator.tsx  ← Three-dot animation
│   │   ├── artifact/
│   │   │   ├── ArtifactPanel.tsx    ← Right panel container (58% width)
│   │   │   ├── TabBar.tsx           ← Tab navigation with teal active indicator
│   │   │   ├── PRDView.tsx          ← Step 1 artifact: PRD building live
│   │   │   ├── ConceptualERD.tsx    ← Step 2 artifact: Entity cards + relationships
│   │   │   ├── LogicalModel.tsx     ← Step 3 artifact: Attribute tables + flags
│   │   │   ├── DetailedRequirements.tsx ← Step 4 artifact: Full field mapping table
│   │   │   ├── CompletenessBar.tsx  ← Animated progress indicator
│   │   │   ├── EntityCard.tsx       ← Reusable entity card (Step 2)
│   │   │   ├── FlagBadge.tsx        ← Quality flag indicator
│   │   │   └── FieldRow.tsx         ← Inline-editable artifact field
│   │   ├── gates/
│   │   │   ├── GateBanner.tsx       ← Full-width approval banner
│   │   │   └── GateConfirmation.tsx ← Post-approval animation
│   │   └── shared/
│   │       ├── EmptyState.tsx       ← Contextual empty state messages
│   │       ├── StatusPill.tsx       ← In Progress / Awaiting Approval / Complete
│   │       ├── Badge.tsx            ← Role badges, flag type badges
│   │       └── SettingsPanel.tsx    ← Runtime theme settings drawer (10 sections)
│   ├── hooks/
│   │   ├── useAgent.ts             ← Claude API integration + message management
│   │   ├── useLifecycleState.ts    ← Read/write lifecycle state (Sheets or local)
│   │   ├── useArtifact.ts          ← Artifact content state per step
│   │   ├── useAutoResume.ts        ← Session load → auto-resume logic
│   │   └── useFlags.ts             ← Quality flag management
│   ├── lib/
│   │   ├── claude.ts               ← Claude API client wrapper
│   │   ├── sheets.ts               ← Google Sheets API client (persistent layer)
│   │   ├── prompts.ts              ← System prompt loader per step
│   │   ├── scoring.ts              ← Completeness scoring logic
│   │   ├── theme-config.ts         ← Runtime theme: ThemeConfig type, 4 presets, URL param parser, deep merge
│   │   ├── types.ts                ← All TypeScript interfaces
│   │   └── constants.ts            ← Design tokens, step config, gate config
│   ├── styles/
│   │   └── tokens.css              ← CSS custom properties matching Sana design
│   ├── data/
│   │   ├── mock/
│   │   │   ├── highspot.ts         ← Simulated Highspot document search results
│   │   │   ├── atlan.ts            ← Simulated Atlan catalog metadata
│   │   │   ├── snowflake.ts        ← Simulated Snowflake schema/table info
│   │   │   └── allocadia.ts        ← Simulated Allocadia budget export
│   │   └── prompts/
│   │       ├── step1-requirements.md   ← System prompt for Requirements Agent
│   │       ├── step2-conceptual.md     ← System prompt for Conceptual Modeler
│   │       ├── step3-logical.md        ← System prompt for Logical Modeler
│   │       └── step4-detailed.md       ← System prompt for Requirements Finalizer
│   └── context/
│       ├── AppContext.tsx           ← Global state provider
│       └── ThemeContext.tsx         ← Runtime theme provider (reads URL params, applies CSS vars)
├── public/
│   └── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── vite.config.ts
└── .env.example                     ← ANTHROPIC_API_KEY, GOOGLE_SHEETS_ID
```

---

## Build Order (Follow This Sequence)

### Phase 1: Shell and Layout (Do This First)
1. Initialize Vite + React + TypeScript + Tailwind
2. Create `tokens.css` with all Sana design tokens from Section 3 of the design spec
3. Build `AppShell.tsx` — the 3-zone layout (sidebar | chat + artifact | gate banner)
4. Build `Sidebar.tsx` with step navigator and status indicators
5. Build `ContextBar.tsx` with product name + step + status pill
6. Verify the split-screen renders at correct proportions (sidebar 264px, chat 42%, artifact 58%)

### Phase 2: Chat Panel (Core Interaction)
1. Build `ChatPanel.tsx` with scroll behavior and message list
2. Build `MessageBubble.tsx` — agent (white bg, left-aligned) and user (gray bg, right-aligned)
3. Build `ChatInput.tsx` — Sana-style rounded pill with send button
4. Build `TypingIndicator.tsx` — three-dot animation
5. Build `SuggestedReplies.tsx` — staggered fade-in pills (max 3)
6. Wire up `useAgent.ts` hook with Claude API integration

### Phase 3: Artifact Panel (Live Document)
1. Build `ArtifactPanel.tsx` container with tab bar
2. Build `TabBar.tsx` with teal active indicator
3. Build `PRDView.tsx` — the Step 1 artifact with all 9 field sections
4. Build `CompletenessBar.tsx` with animated progress
5. Build `FieldRow.tsx` with inline edit affordance (pencil icon on hover)
6. Build `EmptyState.tsx` for each tab's empty state message
7. Implement the field population animation (teal highlight fade, 300ms)

### Phase 4: Agent Intelligence (Step 1 Focus)
1. Create the Step 1 system prompt (`step1-requirements.md`)
2. Implement the interview sequence (9 data points, one at a time)
3. Build completeness scoring logic in `scoring.ts`
4. Wire agent responses to artifact field population
5. Implement suggested reply pills for structured options (grain, time range, etc.)
6. Create mock source system responses (`highspot.ts`, `atlan.ts`, etc.)

### Phase 5: Human Gates
1. Build `GateBanner.tsx` with the approval UI
2. Implement "Request Changes" flow (inline text input → agent follow-up)
3. Implement "Approve" flow (checkmark animation → step transition)
4. Wire gate to lifecycle state (step completion, next step unlock)
5. Add keyboard shortcut (Cmd+Enter to approve)

### Phase 6: Steps 2-4 (Extend Pattern)
1. Build Step 2 artifact: `ConceptualERD.tsx` with `EntityCard.tsx`
2. Build Step 3 artifact: `LogicalModel.tsx` with flag system
3. Build Step 4 artifact: `DetailedRequirements.tsx` with field mapping table
4. Create system prompts for Steps 2-4
5. Implement flag taxonomy (amber, red, blue, gray) in `FlagBadge.tsx`

### Phase 7: State Persistence and Auto-Resume
1. Build `useLifecycleState.ts` — local state first, then Google Sheets
2. Build `useAutoResume.ts` — session load → correct step + resume message
3. Implement the resume message pattern per step (see design spec Section 5)
4. Wire conversation history persistence

### Phase 8: Runtime Theme System (Already Scaffolded)
The theming system is already built (`theme-config.ts`, `ThemeContext.tsx`, `SettingsPanel.tsx`). As you build each component:
1. **Read all visual values from `useTheme()`.** Never hardcode colors, labels, layout sizes, or feature flags.
2. **Check feature flags** before rendering optional features (e.g., `theme.features.enableFlagSystem`, `theme.features.showStep0`).
3. **Read step/gate labels from `theme.steps.*` and `theme.gates.*`** instead of from constants.
4. **Read agent config from `theme.agent.*`** for avatar label, placeholder text, thinking delay.
5. **Read scenario data from `theme.scenario.*`** for product name, owner, trigger email.
6. Verify all 4 presets (Sana, phData, Dark, Minimal) render correctly when switched.
7. Verify URL param loading works: `?theme=phdata`, `?brand.platformName=Test`, etc.
8. Verify localStorage persistence: theme survives page refresh.

---

## Runtime Theme System (Already Built)

Every visual parameter in the app is runtime-configurable. The system has 3 layers:

| Layer | File | What It Does |
|-------|------|-------------|
| Config + Presets | `src/lib/theme-config.ts` | Defines `ThemeConfig` interface (100+ fields), 4 presets, deep merge, URL param parser |
| Context + CSS | `src/context/ThemeContext.tsx` | Provides `useTheme()` hook, applies theme to CSS custom properties on every change, reads from URL/localStorage on mount |
| Settings UI | `src/components/shared/SettingsPanel.tsx` | Slide-out drawer (⚙️ in sidebar or Ctrl+Shift+S) with 10 config sections |

**4 Built-in Presets:** Sana (default), phData (navy/blue), Dark (dark mode), Minimal (indigo, no chrome)

**3 Config Methods:** Settings panel, URL params (`?theme=phdata`), JSON import/export

**Rule for all components:** Use `const { theme } = useTheme()` and read `theme.colors.*`, `theme.layout.*`, `theme.agent.*`, etc. Never use raw CSS variable values or hardcoded strings.

---

## Critical Design Tokens (From Sana Screenshots)

```css
/* Surfaces */
--white: #FFFFFF;
--surface-subtle: #FAFAFA;
--surface-input: #F4F4F4;
--surface-active-nav: #EBEBEB;
--surface-hover: #F5F5F5;

/* Text */
--text-primary: #1A1A1A;
--text-secondary: #6B6B6B;
--text-tertiary: #9E9E9E;

/* Borders */
--border-subtle: #E8E8E8;

/* Actions */
--btn-primary-bg: #1A1A1A;
--btn-primary-text: #FFFFFF;

/* DSA Accent — ONLY for agent badge, active tab, completeness bar, gate CTA */
--accent-teal: #3DDBB8;
--accent-teal-surface: #E8FBF6;

/* Flags */
--amber-flag: #D97706;
--amber-surface: #FEF3C7;
```

**Teal is reserved for 3 uses only:** agent avatar badge, active tab underline, completeness bar / gate CTA. Nowhere else.

---

## Step Configuration Reference

| Step | Agent Persona | Artifact Type | Tab Name | Gate Name | Approver |
|------|--------------|---------------|----------|-----------|----------|
| 0 | Stakeholder Prep | Stakeholder Map | Stakeholder Map | (no gate) | — |
| 1 | Requirements Interviewer | PRD | PRD Draft | PRD Review | Product Owner |
| 2 | Conceptual Modeler | Entity-Relationship | Conceptual Model | Conceptual Model Review | Analytics Engineer |
| 3 | Logical Modeler | Logical Model + Flags | Logical Model | Logical Model Review | Analytics Engineer |
| 4 | Requirements Finalizer | Detailed Field Mapping | Detailed Requirements | Final Requirements Review | Product Owner |

---

## Agent Behavior Rules

1. **Agent speaks first. Always.** On session start, on resume, on step transition.
2. **One question at a time.** Never batch multiple questions.
3. **Confirm before proceeding.** "I've captured X as your primary grain — is that right?"
4. **Offer structured options where appropriate.** Use suggested reply pills for grain, time range, etc.
5. **Signal readiness explicitly.** "The PRD is at 87% — ready for review when you are."
6. **Surface source context inline.** When the conversation reaches a topic where mock data exists, the agent mentions it proactively.
7. **Never say "Where were we?" on resume.** The agent already knows. The resume message proves it.

---

## ROMI Demo Scenario Summary

**Starting state:** VP Marketing emailed asking for "a ROMI dashboard." Nothing else exists.

**Key demo moments:**
1. Agent opens by referencing the email, begins structured interview → PRD builds live
2. Agent surfaces Highspot doc showing fiscal calendar mismatch (Feb-Jan year-end)
3. Agent finds Allocadia table in Atlan with 80-day-stale data + campaign code format mismatch
4. Agent flags LinkedIn connector as missing in Snowflake → creates dependency flag
5. PRD reaches 87% → gate banner appears → PO approves → Step 2 unlocks

**Mock source data is pre-scripted** — see `src/data/mock/` files. The agent "discovers" this data at specific conversation points, not via live API calls.

---

## Files To Read (In This Order)

1. `docs/DESIGN_SPEC.md` — Full UI spec. The authoritative source for every visual and interaction decision.
2. `docs/DEMO_REQUIREMENTS.md` — The demo scenario, scripted moments, and mock data definitions.
3. `docs/ROMI_PRD.md` — What the Step 1 artifact should look like when complete.
4. `docs/ROMI_DETAILED_REQUIREMENTS.md` — What the Step 4 artifact should look like when complete.
5. `docs/PRD_TEMPLATE.md` — The template structure the agent follows.
6. `src/data/prompts/step1-requirements.md` — The Step 1 system prompt (start here for agent behavior).
7. `src/lib/types.ts` — All TypeScript interfaces (the data contract).
8. `src/lib/constants.ts` — Design tokens and step configuration.

---

## Environment Setup

```bash
# Initialize
npm create vite@latest . -- --template react-ts
npm install tailwindcss @tailwindcss/vite
npm install @anthropic-ai/sdk

# Dev
cp .env.example .env  # Add your ANTHROPIC_API_KEY
npm run dev
```

**Note:** The Claude API call must go through a backend proxy or edge function to avoid exposing the API key in the browser. For the demo, a simple Vite proxy or a `/api/chat` endpoint is sufficient.

---

## Non-Negotiable Constraints

1. **No hardcoded visual values in components.** Every color, label, layout size, and feature flag must be read from `useTheme()`. The only exception is `tokens.css` which provides CSS variable defaults — but `ThemeContext` overrides them at runtime.
2. **No color except the active theme palette.** The app defaults to Sana but must look correct in all 4 presets.
3. **Chat panel width is theme-controlled.** Defaults to 42% but adjustable via `theme.layout.chatPanelPercent`.
4. **Artifact panel is the source of truth.** What's in the artifact is what gets persisted. The chat is conversation; the artifact is the product.
5. **Gates are deliberate moments.** Not dismissible dialogs. The gate banner must feel weighty.
6. **Agent never asks more than one question at a time.** Ever.
7. **Empty states must explain what will appear and when.** "No data" is not an empty state.
8. **The persistent layer schema must match the target Snowflake schema exactly.** Column names, types, everything.
9. **Feature flags control optional features.** Check `theme.features.*` before rendering Step 0, flags tab, inline edit, source badges, completeness bar, or field animations.
10. **Theme changes are instant and non-destructive.** Switching presets or adjusting colors must not reset conversation state, artifact progress, or lifecycle position.
