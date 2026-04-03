# Data Product Requirements Document (PRD)
## Template v2.0 — DSA Standard

> **How to use this template:**
> Fields marked `[AGENT]` are auto-populated by the DSA Requirements Agent through interview.
> Fields marked `[HUMAN]` require human input or confirmation — the agent will ask, but cannot validate on your behalf.
> Fields marked `[GATE]` must be resolved before the indicated downstream step can begin.
>
> **Parallel artifact policy:** The Conceptual Model (Step 2) can begin once the five **[GATE → Conceptual]** fields are filled with sufficient confidence. Remaining PRD fields can continue to be refined in parallel. All fields must be resolved before the Logical Model gate (Step 3).

---

| Field | Value |
|-------|-------|
| **Document version** | `[AGENT]` |
| **Status** | Draft / In Review / Approved |
| **Data product ID** | `[AGENT — auto-assigned]` |
| **Created** | `[AGENT]` |
| **Last updated** | `[AGENT]` |
| **Product Owner** | `[HUMAN]` |
| **Data Product Manager** | `[HUMAN]` |
| **Data Architect** | `[HUMAN]` |
| **PRD Completeness** | `[AGENT — scored]` |
| **Conceptual Model unlock** | `[AGENT — ready / not ready]` |

---

## 1. Product Vision

### 1.1 Business Objective

> *What business question, decision, or outcome does this data product exist to support? Be specific — "improve analytics" is not an objective.*
> **[GATE → Conceptual]**

`[AGENT — populated from interview]`

---

### 1.2 Strategic Context

> *Why does this data product need to exist now? What changes when it does?*

`[AGENT — populated from interview]`

---

### 1.3 Natural Language Questions (NLQs) This Product Must Answer

> *List the 3–5 most important questions a user should be able to answer using this data product. These drive the conceptual model. If you can't write NLQs, the business objective is not clear enough yet.*
> **[GATE → Conceptual]** — minimum 3 NLQs required before conceptual modeling begins

| Priority | NLQ | Primary Consumer |
|----------|-----|-----------------|
| 1 | `[HUMAN — agent will suggest, you confirm]` | `[HUMAN]` |
| 2 | | |
| 3 | | |

---

## 2. Consumer Personas

> *Who uses this data product, and what do they need it to do for them?*
> **[GATE → Conceptual]** — at least primary persona required

### 2.1 Primary Consumers

| Persona | Role | What They Need to Do | Access Tier |
|---------|------|---------------------|-------------|
| `[AGENT]` | `[AGENT]` | `[AGENT]` | `[HUMAN — confirmed at gate]` |

### 2.2 Secondary Consumers

> *Who consumes this data indirectly — through reports, downstream systems, or partner access?*

`[AGENT]`

### 2.3 External / Partner Access (if applicable)

> *Are there external organizations, partners, or regulators who will receive outputs from this product? What can they receive?*

`[HUMAN — if applicable]`

---

## 3. Data Scope

### 3.1 Primary Grain

> *What does one row in the fact table represent? Complete this sentence: "One row = one ____ per ____."*
> **[GATE → Conceptual]** — grain must be stated before entity modeling begins. An approximate grain is acceptable to start; it will be refined in the logical model.

**Grain statement:** One row represents one `___` per `___`.

`[AGENT — proposed from NLQs, confirmed by human]`

---

### 3.2 Scope Boundaries

> *What is explicitly IN scope? What is explicitly OUT of scope? Both matter equally. If you haven't named what's out, you haven't defined the product.*

**In scope:**
- `[AGENT — derived from NLQs and objective]`

**Explicitly out of scope:**
- `[HUMAN — must be stated, not left implicit]`

---

### 3.3 Time Range and Refresh

| Dimension | Value |
|-----------|-------|
| Historical coverage | `[AGENT]` |
| Refresh cadence | `[AGENT]` |
| Snapshot logic | `[AGENT — e.g., end-of-month, event-based]` |
| SLA (data freshness) | `[HUMAN]` |

---

## 4. Source Systems

> *What systems contain the data needed for this product?*
> **[GATE → Conceptual]** — primary source systems must be identified (access confirmation not required yet)

| System | Data Domain | Access Status | Contract / Permission Status |
|--------|-------------|--------------|------------------------------|
| `[AGENT]` | `[AGENT]` | Confirmed / TBD / Blocked | `[HUMAN]` |

**Discovery required?** `[AGENT — yes/no + what needs to be discovered]`

---

## 5. Key Metrics and Definitions

> *What are the 3–7 most important metrics or measures this product must produce? Include plain-language definitions. Precise formulas come in the detailed data requirements; directional definitions are sufficient here.*

| Metric | Plain-language definition | Priority |
|--------|--------------------------|---------|
| `[AGENT]` | `[AGENT]` | MVP / Phase 2 |

---

## 6. Stakeholder Matrix

> *Who has accountability for this data product? Name individuals, not just roles.*

### 6.1 Decision Makers and Approvers

| Role | Named Individual | Organization | Gate Accountability |
|------|-----------------|--------------|---------------------|
| Business Owner / Sponsor | `[HUMAN]` | | PRD approval |
| Data Product Manager | `[HUMAN]` | | All gates |
| Data Architect | `[HUMAN]` | | Conceptual + Logical model gates |
| Legal / Compliance | `[HUMAN]` | | Governance sign-off |
| Data Engineering Lead | `[HUMAN]` | | Code Gen gate |

### 6.2 Delivery Team

| Role | Named Individual | Team |
|------|-----------------|------|
| `[HUMAN]` | | |

---

## 7. Governance and Privacy

> *This section establishes the governance framework — field-level rules, access tiers, and privacy controls go in the Detailed Data Requirements. This section defines the governing principles and any non-negotiable constraints that must shape the model before design begins.*

### 7.1 Data Classification

> *What is the overall sensitivity level of the data in this product? Who is the data about?*

`[HUMAN — confirmed with Legal/Compliance]`

### 7.2 Non-Negotiable Privacy Constraints

> *Are there regulatory, legal, or contractual constraints that must be enforced by design — not as an afterthought? List them here. These constrain the model.*

| Constraint | Regulatory basis | Design implication |
|------------|-----------------|-------------------|
| `[HUMAN]` | `[HUMAN]` | `[AGENT — will flag in modeling]` |

### 7.3 Obfuscation and De-identification Requirements

> *For each sensitive entity or attribute type, what technique is required?*
> *Detail belongs in Detailed Data Requirements. This section captures the approach, not the field list.*

| Entity / Attribute Type | Required Technique | Notes |
|------------------------|-------------------|-------|
| `[HUMAN]` | Pseudonymization / Tokenization / Bucketing / Suppression / Indexing / Masking | `[HUMAN]` |

### 7.4 Minimum Cohort Size (K-Anonymity)

> *If this product serves aggregated or research use cases, what is the minimum group size before a result is suppressed?*

`[HUMAN — confirm with Legal]`

### 7.5 Access Tiers

> *Define the access roles for this product. Field-level mapping comes in the Detailed Data Requirements.*

| Tier name | Who | What they can see |
|-----------|-----|------------------|
| `[HUMAN]` | | |

---

## 8. Success Criteria

### 8.1 Data Product Acceptance Criteria

> *Specific, testable conditions that must be true at release. These are about the data product — not business outcomes.*
> **Distinguish from business success metrics (Section 8.2).** Acceptance criteria tell engineers when the build is done. Business metrics tell the organization whether the product is delivering value.

| Criterion | Test method | Owner |
|-----------|-------------|-------|
| `[HUMAN — added at gate review]` | | |

### 8.2 Business Success Metrics

> *How will the organization know this data product is creating value? These may take months to measure. They are not acceptance criteria.*

| Metric | Target | Measurement timing |
|--------|--------|-------------------|
| `[HUMAN]` | | |

---

## 9. Open Questions and Assumptions

> *Do not bury open questions in comments. Surface them here where they can be tracked and closed. The agent will populate this section as it identifies gaps during the interview.*

### 9.1 Open Questions

| Question | Owner | Required for | Target date |
|----------|-------|--------------|-------------|
| `[AGENT — flags during interview]` | `[HUMAN]` | Conceptual / Logical / Code Gen | |

### 9.2 Assumptions

> *What are we assuming to be true in order to proceed? Assumptions that turn out to be wrong become risk.*

| Assumption | Risk if wrong | Owner to validate |
|-----------|---------------|------------------|
| `[AGENT + HUMAN]` | | |

---

## 10. Conceptual Model Readiness Check

> *Filled automatically by the Requirements Agent. The Conceptual Model step unlocks when all five criteria are met with sufficient confidence. "Sufficient" means the agent and Product Owner agree — not that every field is finalized.*

| Criterion | Status | Notes |
|-----------|--------|-------|
| Business objective is specific and agreed | `[AGENT]` | |
| At least 3 NLQs defined | `[AGENT]` | |
| Primary grain stated (even if approximate) | `[AGENT]` | |
| Primary consumer persona confirmed | `[AGENT]` | |
| Primary source systems identified | `[AGENT]` | |
| **Conceptual Model: UNLOCKED / LOCKED** | `[AGENT]` | |

> *Fields not yet complete continue to be refined in parallel with Conceptual Modeling. All fields must be complete before the Logical Model gate.*

---

## 11. Gate Approval Record

> *Populated by the Lifecycle Orchestrator on each approval.*

| Gate | Artifact version | Approved by | Persona | Approved at | Notes |
|------|-----------------|-------------|---------|-------------|-------|
| PRD → Conceptual Model | | | Data Product Owner | | |

---

*Generated by DSA Requirements Agent · phData*
*ODPS-compliant · Version controlled in persistent layer*
