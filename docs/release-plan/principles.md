# Release Plan — Principles & Conventions
*How this plan is structured and how to read it*

## Purpose of This Document Set

This release plan defines what to build, in what order, with what scope boundary.
It does not define how to implement it — that is the architect's job.

Each sub-phase document is the primary input to the synthesizer agent. The synthesizer
reads the sub-phase document alongside the architecture index and stack truth to
produce an operational brief. The architect reads the brief and produces the
file-level implementation plan.

## Document Structure

```
release/
  release-index.md          ← entry point; one-liner per phase and sub-phase
  principles.md             ← this file
  phase-1/
    index.md                ← phase hypothesis, sub-phase list, done criteria, go/no-go
    1a-*.md                 ← one file per sub-phase
    ...
  phase-2/ ...
  ...
```

## Sub-Phase Document Format

Every sub-phase document contains exactly these sections:

**Objective** — one paragraph; what this sub-phase delivers and why now.

**Scope** — what IS built in this sub-phase. Models, services, tasks, endpoints.
Named precisely. Nothing vague.

**Non-Goals** — what is explicitly NOT built here and which sub-phase handles it.
Every deferral is named.

**Architecture References** — which architecture documents define the authoritative
spec for each element in scope. The synthesizer uses these to know which arch
sub-documents to load.

**Dependencies** — what must exist and be working before this sub-phase begins.
Expressed as prior sub-phase labels (e.g. "requires 1a, 1b").

**Models Introduced or Modified** — each model with its key fields and constraints.
For full field specs, the architecture reference is cited. New fields on existing
models are noted explicitly.

**Services & Tasks Introduced** — service class names, their responsibility in one
sentence, and whether they are sync, async, or worker tasks.

**Endpoints Introduced** — HTTP method, path, brief description. No request/response
schema detail — that belongs in the architect's plan.

**Key Constraints** — must-not-violate rules specific to this sub-phase. Derived from
the architecture invariants but stated in the context of what is being built.

**Done Criteria** — 2-4 specific, testable outcomes. These are the acceptance tests
for the sub-phase. If all pass, the sub-phase is complete and the next can begin.

## Phasing Philosophy

**Get the schema right first.** Core domain models are built in full in Phase 1,
even if some fields are not used until later phases. This avoids costly data
migrations as the system grows.

**One testable hypothesis per phase.** After each phase: does the system deliver
a meaningfully better experience than before? If not, the phase is too small.

**The coaching voice is the product.** Technical infrastructure phases are only
justified if they visibly improve coaching quality.

**Twin confidence is always honest.** Each phase states the twin's confidence level
at completion. Coaching language must match.

**No LLM in the analytical pipeline.** Ever. The twin computes; the LLM narrates.
This is an invariant across all phases.

## Phase Numbering

Six phases of increasing intelligence:

| Phase | Theme | Twin state at completion |
|---|---|---|
| 1 | Skeleton — the full coaching loop with no real data | Tier 3 bootstrap, LOW confidence |
| 2 | Real data — FIT ingestion, load computation, threshold detection | Layer 1 + 2 real data, MEDIUM/HIGH |
| 3 | Environmental context — wellness, weather, cycle modifiers | Layer 4 active |
| 4 | Coaching intelligence — execution analysis, objectives, session lifecycle | Coaching layer complete |
| 5 | Signal processing — cleaning pipeline, segmentation, race prediction | Layer 5 begins |
| 6 | Advanced twin — HMM, adaptation, three-dimensional load, personalised effort | All layers active |

## Go/No-Go Between Phases

Each phase index defines explicit go/no-go criteria. These are binary gates — not
aspirational targets. The next phase does not begin until all criteria pass.

The most important gate is between Phase 2 and Phase 3: the ingestion pipeline must
be reliable and every Activity must have a `fit_file_key`. Wellness data is meaningless
without a trustworthy training record to contextualise it.
