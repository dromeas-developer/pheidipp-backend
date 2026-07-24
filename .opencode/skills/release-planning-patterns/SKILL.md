---
name: release-planning-patterns
description: >
  Load this at Step 2 (Challenge) and Step 4 (Design Sub-Phases) of the
  Sub-Phase Detailing Process. Contains the Release Planning Anti-Patterns
  checklist and Sub-Phase Sizing Rules. Loaded by p-release-strategy-architect.
---

# Release Planning Patterns

## Anti-Patterns

Avoid these when designing sub-phases. A sub-phase exhibiting any of these
should be restructured before the document is written.

* **Infrastructure-only sub-phases** — setting up infrastructure delivers no
  athlete value on its own; pair it with the first capability that uses it
* **Data-only sub-phases** — schema changes without the service layer that
  consumes them are not independently testable
* **Refactor-only sub-phases** — refactoring without a capability change is
  not an exit-gate-verifiable deliverable; fold it into the sub-phase that
  motivates the refactor
* **Sub-phases that deliver no athlete or system value** — every sub-phase
  must produce something observable; internal reorganisation does not qualify
* **Sub-phases dependent on future sub-phases for validation** — if the exit
  gate cannot be verified until a later sub-phase completes, the boundary is
  in the wrong place
* **Sub-phases spanning unrelated architectural domains** — if two capabilities
  in a sub-phase touch different ownership boundaries with no shared contracts,
  they belong in separate sub-phases

## Sizing Rules

Correctly sized:
* the architect can produce a focused implementation plan without major scope decisions
* it can be implemented without context-switching across unrelated systems
* its exit gate is verifiable within the sub-phase itself

Too large:
* spans multiple unrelated architectural systems
* exit gate requires work from a later sub-phase
* the architect would need more than three implementation plans to cover it

Too small:
* delivers nothing testable on its own
* purely scaffolding for a later sub-phase
* could merge with an adjacent sub-phase without increasing risk

## Challenge Questions

Before finalizing sub-phase design, ask:

* Is this phase sequenced correctly relative to its architectural dependencies?
* Does it create blockers for subsequent phases?
* Is the scope too large? Should it be split?
* Is the scope too narrow? Should it merge with adjacent work?
* Are there capabilities that belong earlier or later?
* Does the phase deliver meaningful, testable value on its own?
* Are there missing capabilities that should be here but aren't?
* Are there ADRs that constrain or affect this phase's sequencing?
