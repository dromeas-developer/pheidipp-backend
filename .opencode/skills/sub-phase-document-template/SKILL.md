---
name: sub-phase-document-template
description: >
  Load this at Step 5 of the Sub-Phase Detailing Process when producing
  sub-phase documents. Contains the exact template structure that every
  sub-phase document must follow. Loaded by p-release-strategy-architect.
---

# Sub-Phase Document Template

Every sub-phase document must follow this structure exactly.

```markdown
# [Phase Label] — [Sub-Phase Title]
## Sub-Phase ID: Phase-X.N

## Objective
One paragraph. What this sub-phase delivers and why it matters at this point
in the delivery sequence. Written for the architect agent — technical, direct.

## Challenge Notes
What was considered and rejected or deferred when designing this sub-phase.
If the high-level phase was restructured, explain what changed and why.
If the phase survived challenge unchanged, state that and give the rationale.

## Capabilities Delivered
Bulleted list of specific, testable capabilities this sub-phase makes available.
Not feature areas — concrete observable outcomes.

## Architectural Contracts Required
Architecture documents the architect must read before planning implementation.
Listed by exact document path.

- `00-foundations/principles.md`
- `01-entities/twin-state.md`
- `02-computations/load-computation.md`

## Vision References Required
Vision documents relevant to this sub-phase. Exact document paths.

- `twin/load-fatigue.md`
- `coach/post-workout.md`

## Upstream Dependencies
What must already exist and be working before this sub-phase begins.
Reference specific sub-phase IDs.

## Downstream Enablement
What becomes possible after this sub-phase completes.
Reference specific sub-phase IDs that depend on this work.

## Invariants To Preserve
Specific architectural invariants this sub-phase must not violate.
Copy the invariant text from the source document. Do not paraphrase.

## Exit Gate
The concrete, verifiable condition that marks this sub-phase complete.
Must be testable. Not "implementation done" — a specific observable outcome.

## Risks
What could go wrong and what the fallback is.
```

## Section Notes

- **Objective**: Written for the architect agent — technical, direct. One paragraph.
- **Challenge Notes**: Document the reasoning behind sequencing decisions. If the phase survived challenge unchanged, state that and give the rationale.
- **Capabilities Delivered**: Concrete observable outcomes, not feature areas. Each bullet should be testable.
- **Architectural Contracts Required**: Exact document paths from `docs/architecture/`. Do not say "see the twin documentation" — give the document path.
- **Vision References Required**: Exact document paths from `docs/vision/`.
- **Upstream Dependencies**: Reference specific sub-phase IDs (e.g., `Phase-1.2`).
- **Downstream Enablement**: Reference specific sub-phase IDs that depend on this work.
- **Invariants To Preserve**: Copy the invariant text from the source document. Do not paraphrase.
- **Exit Gate**: Must be testable. Not "implementation done" — a specific observable outcome.
- **Risks**: What could go wrong and what the fallback is.
