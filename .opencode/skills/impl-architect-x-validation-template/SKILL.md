---
name: impl-architect-x-validation-template
description: >
  Load this when writing the cross-validation report in Step 9 of the
  Implementation Planning Process. Contains the report template, writing
  rules, and detail level guidelines. Loaded by p-implementation-architect.
---

# Cross-Validation Report Template

Write to `docs/implementation/phase-N/phase-N-M/<plan-id>_x-validation.md`.
This is the plan's proof of correctness — a structured record of every
cross-check performed against architecture, vision, and codebase reality.

## Template

```markdown
# Cross-Validation Report — [Plan ID]
Date: [date]
Plan: docs/implementation/phase-N/phase-N-M/overview.md

## RC1 Contract Saturation
| Contract | Status | Detail |
|----------|--------|--------|
| [entity/event] | ✓ / ✗ (Significant) | [detail] |

## RC2 Vision Constraints
| Vision Principle | Status | Detail |
|------------------|--------|--------|

## RC3 Entity Collision
| Entity | Status | Detail |
|--------|--------|--------|

## RC4 Modification Safety
| Entity | Status | Detail |
|--------|--------|--------|

## RC5 Event Flow
| Event | Status | Detail |
|-------|--------|--------|

## RC6 Invariant Enforcement
| Invariant | Enforcement Layer | Detail |
|-----------|-------------------|--------|

## RC7 ADR Re-Check
| ADR | Status | Detail |
|-----|--------|--------|

## Computational Invariant Fixtures
[fixture triples for test architect — same input, same expected output, same tolerance]

## Gap Escalations
[detail from overview]
```

## Rules

- This is the ARCHITECT's validation record, not the coder's input
- Overview.md references this report, does not duplicate it
- The coder never loads this file

## Detail Levels Per Section

| Section | Detail Level | Guideline |
|---------|-------------|-----------|
| RC1–RC7 tables | Status + 1-sentence detail | Pass/fail + what was checked |
| Computational Invariant Fixtures | Concrete triples | Input → Expected → Tolerance |
| Gap Escalations | 2–3 sentences | What's missing, why it matters, who it's escalated to |

**Do NOT include:** step-level detail, file paths, implementation notes.
Those live in batch BRDs.