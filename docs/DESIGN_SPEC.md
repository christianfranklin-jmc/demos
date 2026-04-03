# DSA MVP — UI Design Specification
## Requirements Gathering + Data Modeling Workflow

**Version:** 0.4 — All architectural decisions closed; no open questions  
**Date:** March 2026  
**Owner:** phData Product — Judy Albeige  
**For:** ML Architect / Demo Build  
**Reference Platform:** Workday Sana (sana.ai) — UI tokens verified from screenshots; demo is Sana-styled standalone, not Sana-embedded

---

## 1. Design Philosophy

### The North Star

Data product delivery has three compounding problems. The DSA UI is designed to eliminate all three simultaneously.

**The blank page problem.** Every requirements doc starts empty. Every analyst has stared at a template not knowing where to begin, every engineer has run the same scoping session three times because the output of the last one got lost. The agent replaces the blank page with a conversation — it speaks first, extracts context, and builds the artifact as a byproduct of dialogue.

**The context scatter problem.** The information needed to build a data product is never in one place. Business requirements live in Highspot or a slide deck. Source field documentation lives in Atlan. Schema definitions live in Snowflake. Naming conventions exist in someone's head or a Confluence page nobody can find. Today, analysts manually hunt across all of these systems before they can write a single requirement — and the hunt takes longer than the writing. The DSA agents surface this context inline: the Discovery Agent queries Atlan and Snowflake directly, surfaces reusable assets, flags missing metadata, and brings source field options into the conversation without the analyst ever leaving the interface.

**The handoff problem.** Data product delivery is not one person's job. Requirements move from business stakeholders to analysts to architects to engineers to QA — and at every handoff, context is lost, assumptions are made, and work gets redone. The artifact panel is the antidote: a single, versioned, live document that every persona in the workflow can see, validate, and approve against. The human gates are not bureaucracy — they are the structured handoff moments that ensure context survives the transition between roles.

This shapes every design decision:
- The agent speaks first. Always.
- The artifact is the shared source of truth. Always.
- Context from connected systems surfaces in the conversation — not in a separate tab. Always.
- The human controls progression between steps. Always.

### Design Principles (Ordered by Priority)

**1. Reduce context-gathering work, not just cognitive load.**  
The biggest time sink in requirements gathering is not thinking — it is finding. Finding the right Atlan asset, the right Snowflake schema, the right business process doc in Highspot. The UI must treat information retrieval as the agent's job, not the analyst's. Every field the agent auto-proposes from a connected source is time the analyst didn't spend hunting.

**2. Make handoffs explicit and lossless.**  
When a business analyst hands off to an analytics engineer, the artifact must contain everything the engineer needs to start — no verbal context, no re-explanation, no assumptions. The gate is the formal handoff moment. The artifact is the package. The design must make both feel deliberate and complete, not perfunctory.

**3. Make progress visible without making it anxious.**  
Completeness indicators, step navigation, and artifact state all communicate progress. But none of them should feel like a grading rubric or a deadline. Progress is informational, not evaluative.

**4. The artifact is the product of the conversation, not the goal.**  
Users should never feel like they're "filling out a form by talking." The conversation is the primary experience. The artifact appearing in the right panel is a pleasing side effect — proof that the conversation is working.

**5. Trust is earned through accuracy, not aesthetics.**  
Every time the agent captures something correctly, it earns trust. Every time it says "I've logged X as your primary grain — is that right?" it invites verification. The UI must make it easy to spot errors and correct them without friction.

**6. Human gates are power, not friction.**  
The approval gates are not checkboxes. They are the moment where the human asserts control over an AI-generated artifact and formally passes accountability to the next persona in the chain. The gate UI must feel deliberate and weighty — not like a dismissible dialog.

---

## 2. MVP Target Personas

### Who This Release Is Designed For

The MVP and demo are scoped to two personas. Every design decision — agent tone, question sequencing, artifact structure, gate placement — is made with these two people in mind. Not all personas. These two.

**Persona 1: The Product Owner**

The Product Owner owns the business outcome. They know what the data product needs to do, who it's for, and what "done" looks like — but they are not the ones who will build it. Their pain is translation loss: explaining the business need clearly enough that what gets built actually matches what they envisioned. They are most active in Step 1 (PRD interview) and at every approval gate.

| Attribute | Detail |
|-----------|--------|
| Primary role | Define requirements, approve artifacts, own business outcomes |
| Technical comfort | Low to moderate — comfortable with business terms, not SQL or schema |
| Biggest friction today | Re-explaining the same requirements to different team members; discovering at delivery that assumptions were wrong |
| What this product does for them | Structured capture of their intent in a single conversation; visible artifact they can review and correct; formal approval moment that puts their sign-off on record |
| Active in steps | Step 1 (PRD interview), Gate 1 (PRD approval), Gate 4 (final requirements approval) |

**Persona 2: The Data Analyst**

The Data Analyst owns the data logic. They translate approved requirements into field-level specifications and source mappings — which today means manually hunting across Atlan, Snowflake, Highspot, and wherever else documentation might live. Their pain is context scatter: by the time they've assembled enough information to start writing requirements, they've touched six tools and had three follow-up conversations. They are most active in Steps 2–4.

| Attribute | Detail |
|-----------|--------|
| Primary role | Translate business requirements into data logic; source field mapping; grain decisions |
| Technical comfort | High — fluent in data modeling concepts, SQL, and dimensional design |
| Biggest friction today | Manual discovery across disconnected systems (Atlan, Snowflake, Highspot); re-entering information already captured elsewhere; unclear handoff from PO |
| What this product does for them | Agent surfaces source context inline — no tab-switching; PRD artifact from Step 1 is already structured input, not a document to re-read; flags surface ambiguities before they become bugs |
| Active in steps | Steps 2, 3, 4 (conceptual model, logical model, detailed requirements), Gate 2 and Gate 3 |

---

### Phased Persona Rollout

The MVP covers Steps 1–4 (requirements through detailed data requirements). As the DSA expands, additional personas enter the workflow at new steps. The UI's information architecture, navigation model, and agent tone are designed to accommodate these personas without redesigning the shell.

| DSA Release | New capability | New persona entering |
|-------------|---------------|---------------------|
| MVP (now) | Requirements + Conceptual + Logical + Detailed Requirements | Product Owner, Data Analyst |
| v2 | Code Generation Agent | Analytics Engineer |
| v2 | QA Agent | QA Engineer |
| v3 | Metadata Agent, catalog publishing | Analytics Engineer, Data Product Owner |
| v3 | Enterprise Standards Agent visible in UI | Data Architect |

**Design implication:** The sidebar step navigator must visually distinguish which steps are active for the current user's persona. An Analytics Engineer logging in during v2 should see Steps 1–2 as read-only completed artifacts, Step 3 as their entry point, and Steps 4+ as their active work. The agent should greet them in the context of their role — not replay the PO's requirements interview.

---

## 3. UX Foundations

### Mental Model Alignment

Users arrive with one of two mental models:
- **"This is a form"** — they expect to fill in fields
- **"This is a chat"** — they expect to have a conversation

The DSA experience satisfies both models simultaneously. The chat is primary (left). The form-like artifact is secondary (right). Users who are "form-thinkers" can glance right to see their answers organized. Users who are "chat-thinkers" can stay in the conversation and let the artifact build itself.

Neither model is wrong. Design for both without breaking either.

### Cognitive Load Management

**Chunking:** The agent interview follows a natural funnel — business objective first, then consumers, then scope, then constraints. This mirrors how humans naturally think about requirements. Never jump to grain before establishing the business question.

**Progressive disclosure:** Step 4 (detailed field mapping) is deliberately the last step. Surfacing source-field-level detail in Step 1 would overwhelm any business stakeholder. The system reveals complexity only when the user is ready for it — after they've built context through Steps 1–3.

**Fitt's Law:** The two most important interactive elements — the chat input and the approval CTA — must be large, consistently positioned, and never compete for attention. The chat input anchors the bottom of the left panel. The gate CTA anchors the bottom of the entire main area. They never move.

**Miller's Law:** The agent never presents more than 3 suggested reply options at once. Entity cards are never more than 2 columns wide. Flag tabs show count but surface one flag at a time for resolution.

### Error States and Recovery

Every state in this system must have a defined error treatment. "Error" in this context means:
- Agent produced an incorrect capture ("That's not what I meant")
- A gate is attempted with missing required items
- A source field can't be mapped automatically
- The persistent layer is unreachable

**User-correctable errors (most common):** Show inline. Provide a "Correct this" affordance directly on the artifact field — not buried in conversation. The user should never have to scroll through chat history to fix a captured value.

**System errors:** Surface a specific, plain-language explanation. Never show raw error codes. Provide a clear recovery action. Do not lose conversation state.

**Ambiguity (not errors):** When the agent is uncertain, it signals uncertainty before capturing — "I'm interpreting this as X — is that right?" Guessing silently and capturing incorrectly destroys trust faster than anything else in the system.

### Empty States

Every panel, every tab, every table has a defined empty state. Empty states must:
1. Explain what will appear here (not just "No data")
2. Show where in the flow the content comes from
3. Not look broken

**Example:** An empty Flags tab in Step 3 shows: "No flags yet — I'll surface any source mapping gaps or grain ambiguities as we work through the logical model."

This is not decoration. Empty states set expectations. They prevent users from wondering if something is wrong.

### Micro-interactions and Feedback Loops

**Artifact field population:** When a new field populates from conversation, it should not just appear — it should briefly highlight (subtle background fade from the teal surface to white, 300ms). This tells the user: "that exchange produced something."

**Completeness bar:** Animates smoothly when score changes. Never jumps. The 300ms ease makes progress feel earned.

**Gate button:** On hover, the primary approval button subtly shifts — not a dramatic animation, just enough to confirm it's interactive and that clicking it matters.

**Agent "thinking" state:** 400ms delay + a typing indicator before the agent's first resume message. Signals that something is being computed, not just loading. Prevents the perception of a pre-scripted response.

**Suggested reply pills:** Animate in after the agent's message (50ms stagger, fade from 0 to 1). Do not appear simultaneously with the message text — they feel like afterthoughts, which they are.

### Accessibility

- All interactive elements meet 4.5:1 contrast ratio minimum on both white and subtle-gray backgrounds
- Keyboard navigation: Tab through chat input → suggested pills → artifact tabs → gate buttons
- Screen reader: All agent messages announced. Artifact updates announced with a summary ("PRD completeness updated to 72%") not field-by-field announcements
- Focus rings: Visible on all interactive elements. Use `outline: 2px solid #1A1A1A` — matches Sana's minimal aesthetic without hiding focus state
- Gate confirmation: Keyboard shortcut `Ctrl/Cmd + Enter` to confirm approval from the gate banner — never required, but discoverable

---

## 3. Design Language

### What the Actual Sana UI Looks Like

From verified screenshots (`sana.ai`, March 2026):

- **Background:** Pure white `#FFFFFF` — no tint, no gray wash, everywhere
- **Sidebar:** Same white, slightly distinguished by nav item fills only
- **Active nav item:** Light gray pill `#EBEBEB`
- **Typography:** Clean geometric sans-serif, consistent with Inter or close variant
- **Input field:** Rounded pill, light gray fill `#F4F4F4`, no border, medium-gray placeholder
- **Send button:** Filled dark circle, near-black bg, white arrow — highest contrast element on screen
- **Icons:** Thin line icons, medium gray `#6B6B6B`
- **No color accent in UI chrome.** The only non-neutral color is the Workday "W" brand mark.

### Corrected Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `white` | `#FFFFFF` | All surfaces — shell, sidebar, main |
| `surface-subtle` | `#FAFAFA` | Sidebar if distinguished at all |
| `surface-input` | `#F4F4F4` | Input fields, search |
| `surface-active-nav` | `#EBEBEB` | Active nav pill, hover state |
| `surface-hover` | `#F5F5F5` | Row hovers, secondary hover states |
| `text-primary` | `#1A1A1A` | All primary text |
| `text-secondary` | `#6B6B6B` | Labels, muted nav, placeholders |
| `text-tertiary` | `#9E9E9E` | Timestamps, hints, empty states |
| `border-subtle` | `#E8E8E8` | Panel dividers — used sparingly |
| `icon-default` | `#6B6B6B` | All line icons |
| `btn-primary-bg` | `#1A1A1A` | Primary CTA (send, approve) |
| `btn-primary-text` | `#FFFFFF` | Text on primary CTA |
| `accent-teal` | `#3DDBB8` | DSA agent badge, active tab underline, completeness bar, approval CTA only |
| `accent-teal-surface` | `#E8FBF6` | Teal-tinted field highlight on artifact population |
| `amber-flag` | `#D97706` | Flag badges, unresolved warnings |
| `amber-surface` | `#FEF3C7` | Flag field backgrounds |

> **Teal is reserved for three uses:** (1) DSA agent avatar badge, (2) active tab underline, (3) completeness progress bar and approval gate CTA. Nowhere else. This makes the teal feel purposeful — it signals "this is the DSA layer, and this action is important."

### Typography

| Role | Size | Weight | Color |
|------|------|--------|-------|
| App / product name | 14–15px | 600 | `#1A1A1A` |
| Nav item | 14px | 400 | `#1A1A1A` |
| Nav item (active) | 14px | 500 | `#1A1A1A` |
| Section label | 12px | 500 | `#6B6B6B` |
| Input placeholder | 14px | 400 | `#9E9E9E` |
| Agent message | 14px | 400 | `#1A1A1A`, line-height 1.6 |
| Artifact section label | 11px | 600 | `#6B6B6B` UPPERCASE |
| Artifact field label | 11px | 500 | `#6B6B6B` |
| Artifact field value | 13px | 400 | `#1A1A1A` |
| Empty state text | 13px | 400 | `#9E9E9E` italic |
| Source field (mono) | 11px | 400 | Monospace, `#6B6B6B` |
| Gate label | 11px | 700 | `#1A1A1A` UPPERCASE |
| Gate description | 13px | 400 | `#6B6B6B` |

**Weight discipline:** 400 and 500 only in UI chrome. 600 for emphasis in section labels and CTAs. Never 700+ except gate labels. Heavy weights look wrong in the Sana design context.

### Shape and Spacing

| Property | Value |
|----------|-------|
| Sidebar width | 264px |
| Context bar height | 44px |
| Gate banner height | 64px |
| Chat/artifact panel split | 42% / 58% |
| Nav item border radius | 8px |
| Input border radius | 24px (pill) |
| Card border radius | 10px |
| Entity card border radius | 10px |
| Badge border radius | 4px |
| Tag/chip border radius | 16px (pill) |
| Suggested reply pill | 20px |
| Internal card padding | 14px 16px |
| Section vertical gap | 20px |
| Field vertical gap | 8px |

---

## 4. Application Shell

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  SANA SIDEBAR (264px)       │       DSA MAIN AREA                   │
│  [W] Workday Sana           │ ┌─────────────────────────────────┐   │
│                             │ │  CONTEXT BAR (44px)             │   │
│  + New chat                 │ └─────────────────────────────────┘   │
│  ⚡ Workflows                │ ┌────────────────┬────────────────┐   │
│  🔍 Search                  │ │ AGENT CHAT     │ ARTIFACT PANEL │   │
│  📅 Meetings                │ │ (42%)          │ (58%)          │   │
│  ··· More                   │ │                │                │   │
│                             │ │                │                │   │
│  Folders                    │ │                │                │   │
│  ── DSA Workflows ──        │ │                │                │   │
│    ● ROMI Data Product      │ │                │                │   │
│    ✓ Headcount Analytics    │ ├────────────────┴────────────────┤   │
│    ! HC Plan vs. Actual     │ │  HUMAN GATE BANNER (64px)       │   │
│                             │ └─────────────────────────────────┘   │
│  Settings                   │                                        │
└─────────────────────────────┴────────────────────────────────────────┘
```

**DSA step navigator (within main area sidebar or context bar):**

```
  [Optional]
  ○  Stakeholder Alignment     ← Step 0 — no gate, no number
  ──────────────────────────
  ●  1 — Requirements          ← active step
  ○  2 — Conceptual Model      ← locked
  ○  3 — Logical Model         ← locked
  ○  4 — Detailed Requirements ← locked
```

Step 0 is visually separated from the numbered steps by a divider. It carries an "Optional" label so users who don't need it immediately understand they can skip it.

### Sidebar — DSA Integration

The standard Sana sidebar is not modified. One folder is added: **DSA Workflows**. Each data product appears as a named folder item with a status indicator dot:

| Indicator | Meaning |
|-----------|---------|
| `●` teal | In progress — active step |
| `!` amber | Awaiting approval — gate open |
| `✓` gray | Complete — all steps approved |

Clicking a product name triggers auto-resume (Section 5).

### Context Bar

Replaces the standard "All ▾" filter row:

```
[Product name]  ·  Step [N] — [Step name]          [Status pill]
```

Example: `ROMI Data Product  ·  Step 2 — Conceptual Model          ● In Progress`

Single line, 14px, medium weight. Status pill right-aligned. This is the only place step position is displayed.

---

## 5. State-Aware Auto-Resume

This is not a feature. It is the core product contract. The system must always know where a user left off and return them there without any action on their part.

### Session Load Sequence

```
1. User clicks data product in sidebar
2. UI reads lifecycle_state from persistent layer [< 200ms target]
3. Context bar populates with product name + current step
4. Sidebar step indicators update to reflect approved/active/locked states
5. Artifact panel renders current artifact state (may be partial)
6. Agent conversation history loads in chat panel
7. 400ms pause — agent "thinking" indicator
8. Agent fires resume message with immediate next question
```

Steps 5 and 6 happen simultaneously. The artifact panel and conversation history are both visible before the agent speaks. The user sees context before they see new content.

### Resume Message Pattern

```
"Welcome back, [first name]. [One sentence: state of current artifact.]
[Immediate next question — no "let's continue", no preamble.]"
```

The agent never says "Where were we?" or "Let me review what we've covered." It already knows. The resume message demonstrates that.

### Resume Behavior Matrix

| Step | Status | Auto-navigation | Artifact panel state | Agent opens with |
|------|--------|-----------------|----------------------|-----------------|
| 0 | in_progress | Step 0 | Stakeholder map at current state | "Welcome back — [N] stakeholders identified, [N] responses received. Want to continue prepping or move into the requirements interview?" |
| 0 | complete | Step 1 (auto) | PRD pre-populated from Step 0 | "I've pulled in your stakeholder input — PRD is at [N]% already. Let me pick up from here." |
| 1 | in_progress | Step 1 | PRD at current completeness | Last unanswered question |
| 1 | awaiting_approval | Step 1, gate active | Completed PRD | "Ready for review — approve when ready." |
| 2 | in_progress | **Step 2 (auto)** | Conceptual ERD at current state | Next entity validation question |
| 2 | awaiting_approval | Step 2, gate active | Full conceptual ERD | "Model is ready — analytics engineer review needed." |
| 3 | in_progress | **Step 3 (auto)** | Logical model + resolved flags | Next unresolved flag |
| 3 | awaiting_approval | Step 3, gate active | Full logical model + flag count | "Ready for review — [N] flags documented." |
| 4 | in_progress | **Step 4 (auto)** | Field table + completeness bar | "[N] of [total] fields mapped — next gap:" |
| 4 | awaiting_approval | Step 4, final gate | Complete requirements table | "At [N]% completeness — review and approve." |

### New Product State

No data product selected → sidebar shows empty DSA Workflows folder + "Start new data product" affordance. Agent opens with:

> *"Let's build your next data product. What business question do you need this data to answer?"*

Artifact panel shows the PRD template in full empty/awaiting state — all fields visible but unpopulated. This sets expectations for what will be built before a single exchange happens.

---

## 6. Agent Chat Panel

### Positioning and Anchoring

The chat panel is 42% of the main area width. It is fixed — it never collapses, never expands, never becomes full-screen. Its constancy is the anchor that makes the split-screen model work. If the chat panel changes size, the user loses their spatial reference for both panels.

### Visual Treatment — Native Sana

**Agent message bubble:**
- White background, very subtle `1px solid #E8E8E8` border, 10px radius
- Agent avatar: small 24px rounded badge — `DSA` label on `#EBEBEB` background, `#1A1A1A` text
- Font: 14px, 400, `#1A1A1A`, line-height 1.6
- Max width: 88% of panel

**User message bubble:**
- `#F4F4F4` background, no border, 10px radius
- Right-aligned
- Font: 14px, 400, `#1A1A1A`

**Suggested reply pills:**
- Appear 150ms after agent message settles (staggered fade-in, 50ms between pills)
- `#F4F4F4` background, no border, 20px radius, 14px text, `#1A1A1A`
- On hover: `#EBEBEB`
- On tap: disappears + text appears in input field + auto-sends
- Maximum 3 pills per message

**Panel header (inside chat pane):**
```
Requirements Agent  ·  Step 1 of 4
```
12px, `#9E9E9E`, left-aligned, fixed at top of scroll area. Does not scroll with messages.

**Input field:**
- Matches Sana native exactly: rounded pill, `#F4F4F4` fill, lightning bolt prefix icon
- Placeholder: `"Reply to the agent…"`
- On focus: no dramatic change — perhaps `#EEEEEE` fill. No border. Consistent with Sana.
- Send button: filled dark circle with arrow, activates on Enter or click

**Typing indicator:**
- Three dots animation, matches Sana's native style
- Appears for 400ms on session resume before agent fires first message
- Appears for 600–1200ms during agent "thinking" (based on response complexity)

---

## 7. Artifact Panel

### The Artifact Panel's Job

The artifact panel is not a preview. It is not a sidebar. It is the authoritative output of the conversation — the thing that gets written to the persistent layer and handed to the next agent. It should feel like a live document, not a chatbot output window.

### Panel Structure

```
┌─────────────────────────────────────────────┐
│  [Tab 1]  [Tab 2]  [Tab 3]                  │  ← Tab bar (fixed, 40px)
├─────────────────────────────────────────────┤
│                                             │
│  [Scrollable artifact content]              │
│                                             │
└─────────────────────────────────────────────┘
```

**Tab bar:** `#FAFAFA` background, `1px solid #E8E8E8` bottom border.  
**Active tab:** White background, `2px solid #3DDBB8` bottom border — the one teal use in the artifact panel.  
**Inactive tab:** `#6B6B6B` text, no border.

### Field Population Animation

When a new field populates from a conversation exchange:
1. Field value area transitions from empty-state italic to normal text (cross-fade, 200ms)
2. Field briefly highlights with `#E8FBF6` background (teal-tinted, 300ms fade out)
3. Completeness bar animates to new value (300ms ease)

This animation must be subtle. It confirms something happened — it does not celebrate it.

### Inline Correction Affordance

Every populated field in the artifact panel has an edit affordance. On hover over any populated field:
- A small pencil icon appears at the right edge of the field
- On click: field enters inline edit mode (simple text input, same font, auto-save on blur)
- On save: agent is notified ("Judy updated [field] to [new value]") — this goes into conversation history as a system note, not as a chat bubble

Users should never have to re-explain a correction through the chat. They can fix it directly in the artifact. The agent acknowledges and continues.

### Empty State Design (Per Tab)

Every empty state answers: **What appears here? When?**

| Tab | Empty state message |
|-----|-------------------|
| PRD Draft | "Your PRD will build here as we talk. I'll ask you the key questions — nothing to fill in." |
| Conceptual ERD | "Entity cards appear here once we've confirmed your business requirements." |
| Logical Model | "The logical model expands here after the conceptual model is approved." |
| Detailed Requirements | "Field-level mapping appears here as we work through the logical model." |
| Flags | "No flags yet — I'll surface mapping gaps or grain ambiguities here as we go." |

---

## 8. Human Gate Design

### The Gate as a Moment

The gate is not a button. It is a checkpoint — a deliberate pause in an otherwise flowing experience. Its design must communicate: "This is a decision, not a dismiss."

### Gate Banner Anatomy

```
┌──────────────────────────────────────────────────────────────────────┐
│  [gate icon]   Human Gate · [Gate name]                              │
│                [Approver description] · [Artifact version]           │
│                                     [Request Changes]  [Approve →]  │
└──────────────────────────────────────────────────────────────────────┘
```

**Banner background:** `#FAFAFA` — not white, not colored. Slightly differentiated.  
**Top border:** `1px solid #E8E8E8`  
**Gate icon:** Small shield or checkmark icon, `#1A1A1A`  
**Gate name:** 11px, 700 weight, UPPERCASE, `#1A1A1A`  
**Approver description:** 13px, 400, `#6B6B6B`  
**Request Changes:** Secondary button — white background, `1px solid #E8E8E8`, `#1A1A1A` text  
**Approve →:** Primary button — `#1A1A1A` background, `#FFFFFF` text, 8px radius

**Hover states:**
- Request Changes: `#F5F5F5` background
- Approve: `#333333` background (slightly lighter than rest — tactile feedback)

### Gate Behavior

**Request Changes flow:**
1. User clicks "Request Changes"
2. A small inline text input appears below the banner: "What needs to change?" (14px, `#F4F4F4` pill)
3. User types a note and hits Enter
4. Banner collapses
5. Agent receives the note and fires a follow-up question targeting the gap
6. Artifact field in question highlights briefly in amber to show the gap

**Approve flow:**
1. User clicks Approve
2. A brief confirmation state: button shows a checkmark for 800ms
3. Banner animates out (fade + slide down, 300ms)
4. Sidebar: current step indicator becomes `✓`, next step unlocks
5. Context bar updates to new step
6. If resuming next step mid-session: artifact panel loads next step's state, agent fires first question
7. If next step is new: artifact panel shows empty state for next step, agent fires immediately

**Keyboard shortcut:** `Cmd/Ctrl + Enter` to approve — shown as a subtle hint on the button (`⌘↵`) for power users.

### Gate Variants by Step

| Step | Gate Name | Approver Persona | Hard block on open flags? |
|------|-----------|-----------------|--------------------------|
| 1 | PRD Review | Data Product Owner | No — soft warn if completeness < 80% |
| 2 | Conceptual Model Review | Analytics Engineer + Architect | No — soft warn only |
| 3 | Logical Model Review | Analytics Engineer | Soft block — "Resolve Flags First" CTA replaces Approve when flags > 0 |
| 4 | Final Requirements Review | PO + Analytics Engineer | No hard block — deferred fields are valid |

---

## 9. Step Specifications

### Step 0 — Stakeholder Alignment (Optional Pre-Step)

**When it applies:** Not every data product starts with the right person in the room. Sometimes the analyst or DPM knows the product is needed but hasn't yet identified who holds the business knowledge, what questions to ask, or how to structure the conversation. Step 0 addresses this — it is the preparation layer before the requirements interview begins.

Step 0 is optional and skippable. If the Product Owner is present and ready to answer requirements questions directly, skip straight to Step 1. Step 0 exists for the cases where you need to do the work first.

---

#### What Step 0 Does

**1. Stakeholder identification**

The agent asks a small number of scoping questions about the data product's purpose and organizational context, then proposes a stakeholder list — the personas and functions who should have input into the requirements. It does not assume the person in the session knows who all the right stakeholders are.

Example agent output:
> *"For a ROMI data product, I'd suggest getting input from at least three stakeholders: the VP or Director of Marketing Operations (who owns the business outcome), a Finance Business Partner (who will use the data for board reporting), and a Campaign Manager (who needs day-to-day visibility into their own performance). Do you have named contacts for these roles, or should I help you figure out who to approach?"*

The artifact panel on the right shows a **Stakeholder Map** — a simple table of proposed personas, their accountability, and their input status (not contacted / contacted / response received).

**2. Question set generation**

Once stakeholders are identified, the agent generates a tailored interview question set for each persona. Questions are scoped to what that person can actually answer — a Finance BP should not be asked about data grain; a Campaign Manager should not be asked about board reporting requirements.

The question set is exportable — it can be copied as plain text, sent as a formatted email, or shared as a link. The analyst does not need to be on a call to use it.

Example output for Finance BP:
> - *What financial metrics do you need to be able to reproduce from this data product for board presentations?*
> - *How do you currently validate the ROMI figure before it goes to the board?*
> - *Are there any fields or calculations that Finance considers sensitive and should be restricted to Finance-only access?*
> - *What is your acceptable tolerance for data freshness — do you need daily, weekly, or is monthly sufficient for your reporting cycle?*

**3. Async response capture**

When stakeholders can't attend a live session, Step 0 supports an async path. The analyst sends the question set out (via email, Slack, or shared doc — the DSA doesn't dictate the channel), collects responses, and brings them back into the DSA session one of three ways:

| Async input method | How the agent handles it |
|-------------------|--------------------------|
| Analyst pastes stakeholder's written responses into the chat | Agent reads the responses, extracts relevant data points, and pre-populates the corresponding PRD fields in the artifact panel |
| Analyst uploads a response doc (email thread, notes doc) | Agent parses the document and surfaces any extractable requirements, flagging ambiguities for clarification |
| Analyst summarizes verbally what they heard | Agent captures the summary through follow-up questions, same as live interview mode |

In all three cases, the artifact panel updates in real time. Async responses become PRD field values — they don't remain as raw text.

**4. Readiness signal**

Step 0 ends when the agent and the analyst agree that enough stakeholder input exists to begin the live requirements interview. This is a soft signal — no gate, no approval. The agent simply says:

> *"You've got input from Marketing Ops and Finance. Campaign Manager hasn't responded yet — you could proceed without them and revisit their constraints in Step 1, or wait for their response. What would you like to do?"*

The decision belongs to the analyst. The agent doesn't block.

---

#### What Step 0 Does Not Do

- It does not replace the requirements interview. Stakeholder prep is not requirements capture. Step 1 still happens.
- It does not send messages or emails on the analyst's behalf. The question set is generated for export — the analyst controls how and whether it gets sent.
- It does not gate Step 1. If the analyst wants to skip it, they skip it.
- It does not require all stakeholders to respond before proceeding.

---

#### Step 0 in the Sidebar

Step 0 appears in the sidebar as an optional pre-step above Step 1, visually distinguished:

```
  [Optional]
  ○  Step 0 — Stakeholder Alignment
  ─────────────────────────────────
  ●  Step 1 — Requirements Interview   ← active
  ○  Step 2 — Conceptual Model
  ○  Step 3 — Logical Model
  ○  Step 4 — Detailed Requirements
```

It carries no step number in the main workflow numbering — it is preparatory scaffolding, not a lifecycle stage. It does not appear in the approval audit trail unless the analyst explicitly saves a stakeholder map artifact.

---

#### Artifact Panel in Step 0

**Tabs:** Stakeholder Map | Question Sets | Async Responses

**Stakeholder Map tab:**

| Persona | Named Contact | Organization | Status | Input Needed For |
|---------|--------------|--------------|--------|-----------------|
| Marketing Ops | Jennifer Moss | Marketing | Response received | Business objective, metrics, scope |
| Finance BP | TBD | Finance | Not contacted | Governance, board reporting requirements |
| Campaign Manager | TBD | Marketing | Not contacted | Access tier, day-to-day use cases |

**Question Sets tab:** One expandable section per stakeholder, showing the generated question list. Export button (copy as plain text or formatted email) per section.

**Async Responses tab:** Paste area for incoming responses. Agent reads and extracts on input. Fields populated in the Stakeholder Map and pre-staged for Step 1.

---

#### Step 0 and the PRD

Any information captured in Step 0 — stakeholder identities, extracted requirements from async responses — flows automatically into the Step 1 PRD draft. The analyst doesn't re-enter it. When Step 1 begins, the PRD is already partially populated from Step 0 work. The agent acknowledges this:

> *"I've pulled in what you gathered from Jennifer and the Finance team — the PRD is already at 31% completeness. Let me pick up the remaining questions from here."*

---

### Step 1 — Requirements Interview

**Agent's job:** Extract 9 data points through natural conversation. Never ask more than one at a time. Confirm each capture before proceeding. Offer structured options where appropriate.

**Interview sequence:**
1. Primary business question
2. Primary consumers and current data access method
3. Decisions this product should enable
4. Primary grain (offer pills)
5. Time range / history needed
6. Key metrics (3–5)
7. Known source systems
8. Definition of done
9. Compliance, access, or security constraints

**Completeness scoring:**

| Dimension | Weight |
|-----------|--------|
| Business objective captured | 20% |
| Consumers confirmed | 10% |
| Grain confirmed | 20% |
| Time range confirmed | 10% |
| Key metrics (≥ 3) | 20% |
| Success criteria captured | 15% |
| Constraints answered | 5% |

Gate unlocks at ≥ 80% AND agent explicit readiness signal.

---

### Step 2 — Conceptual Data Model

**Agent's job:** Propose entities and relationships from the approved PRD. Validate domain-specific naming. Surface missing dimensions. One topic per exchange.

**Artifact — entity card:**
- Icon (letter-based, color-coded by entity type)
- Entity name + role badge (FACT / DIM / REF)
- 2–3 abstract attribute descriptions (no data types)
- Cardinality hint where inferable

**Entity type color coding (border only — background stays white):**
- Fact: `2px solid #BFDBFE` (blue-tinted)
- Dimension: `2px solid #99F6E4` (teal-tinted)
- Reference: `2px solid #FDE68A` (amber-tinted)
- Primary/core: `2px solid #3DDBB8` (full DSA teal)

**Relationship display:**
Plain-language rows below the entity grid. No arrows rendered in MVP — arrows introduce layout complexity. Use text: `[Entity A] → [verb] → [Entity B]`.

---

### Step 3 — Logical Data Model

**Agent's job:** Expand each entity to attribute level. Map source fields. Surface and resolve gaps one at a time.

**Flag taxonomy:**

| Flag Type | Color | Trigger |
|-----------|-------|---------|
| Grain ambiguity | Amber | Source granularity doesn't match target |
| Access dependency | Amber | Field may need elevated permissions |
| Missing source | Red | No source found for required field |
| Derived field | Blue | Field calculated, not stored |
| Naming conflict | Gray | Name conflicts with standards library |

**Logical model table columns:**
Target Field | Data Type | Source Field | Transformation Rule | Flag

---

### Step 4 — Detailed Data Requirements

**Agent's job:** Build field-level source-to-target mapping. Score completeness. Confirm readiness before triggering gate.

**Detailed requirements table columns:**
Target Field | Source System | Source Field | Transformation | Business Rule | Required | Governance | Phase

**Governance column values:**
- `Public` — accessible to all authorized users
- `Restricted` — role-based access, noted in governance spec
- `Masked` — field visible but value obscured for certain roles
- `Excluded` — field present in model but not surfaced in product layer

**Phase column values:**
- `MVP` — in scope for this delivery
- `Phase 2` — explicitly deferred
- `Out of scope` — excluded by user decision

---

## 10. Persistent Layer Schema

All UI state is driven from the persistent layer. The UI is a stateless view.

| Table | Key Fields |
|-------|-----------|
| `lifecycle_state` | `data_product_id`, `data_product_name`, `current_step`, `step_status`, `last_agent_question`, `open_flag_count`, `approved_steps[]`, `last_updated_by`, `last_updated_at` |
| `artifact_log` | `artifact_id`, `data_product_id`, `step`, `artifact_type`, `content_json`, `version`, `created_at` |
| `approval_audit` | `data_product_id`, `step`, `artifact_id`, `action`, `approved_by`, `persona`, `approved_at`, `notes` |
| `agent_conversation_log` | `data_product_id`, `step`, `message_role`, `message_text`, `timestamp` |
| `quality_flags` | `data_product_id`, `step`, `flag_type`, `description`, `resolution`, `resolved_by`, `resolved_at` |

> **Workday MVP:** Google Sheets, one tab per table. Schema mirrors target Snowflake structure for zero-friction migration.

---

## 11. Build Architecture — Decisions and Rationale

All architectural questions are closed. No open items remain. The architect should treat everything in this section as decided — not as a starting point for discussion.

---

### Decision 1: Standalone React app, not Sana-embedded

**Decision:** Build as a standalone React application. Do not attempt to embed inside sana.ai.

**Rationale:** Sana's UI has been confirmed as chat-only — no structured widget panels, no split-screen capability, nothing beyond a conversational bubble. Embedding the DSA experience inside Sana would mean removing the artifact panel entirely, which is the core of the interaction model. A standalone app that faithfully reproduces Sana's visual language is both technically unconstrained and visually indistinguishable to the demo audience.

**What "Sana-like" means for the build:** Match the verified design tokens from Section 3 exactly — pure white surfaces, Inter/geometric sans-serif, rounded pill input, `#EBEBEB` active nav states, minimal chrome, no color except the DSA teal accent. The demo audience will read it as Sana-native without needing it to run at sana.ai.

**What does not need to happen:** No call to Farhad. No Sana API access. No widget capability investigation. The platform question is closed.

---

### Decision 2: Claude API for all agent conversations

**Decision:** Power all agent conversations via Claude API (`claude-sonnet-4-6`) with step-scoped system prompts. Do not use Sana's hosted LLM.

**Rationale:** The demo is not running on Sana infrastructure, so there is no reason to use their LLM. Claude API gives the architect full control over step-scoped system prompts — the agent in Step 1 behaves as a requirements interviewer, Step 3 as a logical modeler, and so on. Sana's LLM would add a platform dependency with no corresponding benefit.

**Step-scoped system prompts (one per step):**

| Step | Agent persona | Core instruction |
|------|--------------|-----------------|
| 1 | Requirements interviewer | Extract 9 data points through sequential interview. Confirm each capture before proceeding. Signal readiness when completeness ≥ 80%. Output PRD JSON to persistent layer. |
| 2 | Conceptual modeler | Receive approved PRD JSON. Propose entity set and relationships. Validate domain-specific naming with the user one topic at a time. Output entity/relationship schema JSON. |
| 3 | Logical modeler | Receive approved conceptual model JSON. Expand each entity to attribute level. Map source fields. Surface gaps as discrete named flags, one at a time. Output logical model JSON + flag log. |
| 4 | Requirements finalizer | Receive approved logical model JSON. Build source-to-target field mapping. Score completeness. Confirm readiness before signaling gate. Output ODPS-compliant requirements artifact JSON. |

Each step's system prompt is scoped to that step only — no cross-step context leakage. The persistent layer (Google Sheets) carries state between steps, not the prompt chain.

---

### Decision 3: Google Sheets via direct API, not Sana connector

**Decision:** Read and write lifecycle state directly via the Google Sheets API from the React app. Do not route through Sana's connector.

**Rationale:** The demo is standalone — Sana's Google Sheets connector is irrelevant. The React app calls the Sheets API directly on every agent exchange that produces a state change. Mid-conversation writes are standard Sheets API calls; no middleware layer required.

**Write triggers (when the app writes to Sheets):**
- Every confirmed field capture in Step 1 → updates `artifact_log` and `lifecycle_state.last_agent_question`
- Every gate approval → writes to `approval_audit`, updates `lifecycle_state.current_step` and `step_status`
- Every flag surfaced or resolved in Steps 3–4 → writes to `quality_flags`
- Every agent message → appends to `agent_conversation_log`

**Schema reminder:** Five sheets, one per table. Schema mirrors target Snowflake structure — column names and types must match exactly to enable zero-friction migration when the Snowflake connector ships.

---

### Decision 4: Single sign-off per gate for MVP

**Decision:** One approver per gate. Single click, single recorded persona. Dual approval (PO + AE both required) deferred to v2.

**Rationale:** Single sign-off is sufficient to demonstrate the governance model to Workday stakeholders. Requiring two separate people to be present and approve in a demo environment adds ceremony that could stall a live review. The data model is built to support dual personas from day one — `approval_audit` records both `approved_by` and `persona` fields — so enforcing dual approval in v2 requires no schema changes, only a UI and orchestration update.

**Gate approver personas by step:**

| Gate | MVP approver persona | v2 (post-MVP) |
|------|---------------------|---------------|
| PRD → Conceptual Model | Data Product Owner | PO + Business Analyst |
| Conceptual → Logical | Analytics Engineer | Analytics Engineer + Data Architect |
| Logical → Detailed Requirements | Analytics Engineer | Analytics Engineer |
| Detailed Requirements → Code Gen | Data Product Owner | PO + Analytics Engineer |

---

### Decision 5: Standalone demo is the right stakeholder experience

**Decision:** The demo runs in a browser window as a standalone app. It does not need to be embedded in sana.ai to land with Workday stakeholders.

**Rationale:** The demo's job is to show the interaction model — how the agent interviews, how the artifact builds live, how the gate works. That story is identical whether the app runs at sana.ai or at localhost:3000 with a polished Sana-matched UI. What the audience will remember is watching a data product go from a blank PRD to a complete conceptual model in a single conversation — not what URL was in the browser bar.

**If stakeholders ask why it's not in Sana:** Don't frame this as a Sana limitation — frame it as a scope distinction. The accurate answer is:

> *"Sana is Workday's conversational assistant platform — and it's the right front door for a significant portion of the DSA experience. But the DSA is a purpose-built delivery system that goes well beyond what any general-purpose chat platform can provide today. It includes a gated workflow engine that controls progression between lifecycle steps with recorded approvals, a structured artifact panel that builds live in parallel with the conversation, a multi-agent harness where discrete agents own discrete lifecycle stages, and direct integrations into systems like Atlan, Snowflake, and Highspot to surface source context inline. These capabilities don't exist in Sana — and they shouldn't. Sana is the front door. The DSA is the infrastructure behind it. What you're seeing today is the DSA's purpose-built surface. The Sana integration is a future layer, not a prerequisite."*

This positions the standalone demo as a deliberate architectural choice, not a workaround. It also reinforces the DSA's core value proposition: this is not a chatbot. It is a delivery system.

---

## 12. Architect Handoff Summary

Everything the architect needs to start building, with no decisions deferred:

| Item | Decision |
|------|----------|
| Build target | Standalone React app |
| Visual language | Sana design tokens (Section 3) — match exactly |
| Agent LLM | Claude API — `claude-sonnet-4-6` |
| Prompt architecture | Step-scoped system prompts — one per step, no cross-step leakage |
| Persistent layer | Google Sheets — direct API from React app |
| Write strategy | Mid-conversation writes on every state change |
| Gate model | Single sign-off, one approver per gate |
| Sana integration | None required for demo — visual match only |
| State on session load | Read `lifecycle_state` from Sheets on launch, auto-resume to current step |
| Schema | Five tables — match target Snowflake column names exactly |

---

*End of spec v0.4 — fully resolved*  
*Owner: Judy Albeige, phData*
