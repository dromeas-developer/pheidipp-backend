---
name: impl-architect-overview-template
description: >
  Load this when writing the implementation overview (overview.md) in Step 9
  of the Implementation Planning Process. Contains the overview template,
  writing rules, detail level guidelines, plan anti-patterns, and sizing rules.
  Loaded by p-implementation-architect.
---

# Implementation Overview Template

Write to `docs/implementation/phase-N/phase-N-M/overview.md`.

## Template

```markdown
# Implementation Overview: [Sub-Phase ID] — [Sub-Phase Title]
## Plan ID: [Sub-Phase ID]-P[N]

## Sub-Phase Reference
Sub-Phase ID: [e.g. Phase-1.2]
Sub-Phase Title: [from the sub-phase document]

## Objective
One to two sentences max. What this plan delivers.

## Scope
- Bullet 1
- Bullet 2

## Out Of Scope
- Bullet 1
- Bullet 2

## Batch Routing
| Batch | Focus | Depends On |
|-------|-------|------------|
| 1 | [theme] | — |
| 2 | [theme] | Batch 1 |

## ADRs Written
- **ADR-NNN: [Title]** — one-line constraint

## Gap Escalations
- [Check]: [what is missing] — [blocks/does not block]
```

## Rules

- Overview is a THIN INDEX, not a restatement of batch content
- Maximum 25 lines

## Detail Levels Per Section

| Section | Detail Level | Guideline |
|---------|-------------|-----------|
| Objective | 1–2 sentences | What, not how |
| Scope | Bullet list | Named capabilities, not implementation steps |
| Out of Scope | Bullet list | Explicit exclusions, not rationale |
| Batch Routing | Table | Batch number, theme, dependency |
| ADRs Written | One-liner each | ADR number + constraint |
| Gap Escalations | One-liner each | What's missing + blocks/doesn't block |

**Do NOT include:** invariants, event contracts, pseudocode, testing
requirements, architecture contracts, notes. Those live in batch BRDs
or the cross-validation report.

## Plan Anti-Patterns

Check these at the overview level. If a plan exhibits any of these, revise
it before handing off to the coder.

- **Spans multiple ownership domains** — if a plan requires two different
  services to be modified by the same implementation step, split it
- **Testing depends on a later plan** — every plan must be independently
  verifiable at completion
- **Contains architectural redesign** — implementation plans execute
  architecture; they do not redefine it
- **Introduces new invariants** — invariants belong in architecture
  documents, not implementation plans
- **Redefines event contracts** — event schema changes belong in the
  architecture event catalogue and require an ADR, not a plan step

Implementation plans execute architecture. They do not redefine it.

## Plan Sizing Rules

- Correctly sized: one coder can implement it in a focused session,
  testing requirements are independently verifiable, no significant
  scope decisions left to the coder
- Too large: spans multiple unrelated ownership boundaries, testing
  depends on a later plan, would take multiple sessions with different
  mental contexts
- Too small: delivers no independently testable capability, purely
  scaffolding for a later plan, could merge with an adjacent plan
  without increasing risk