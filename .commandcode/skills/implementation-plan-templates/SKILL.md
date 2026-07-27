---
name: implementation-plan-templates
description: >
  Load this when persisting implementation plans in Step 9 — i.e. the
  Implementation Steps are drafted, batches are grouped, the cross-validation
  roast is complete, and you are ready to write the overview.md and per-batch
  BRD files. Not needed during retrieval, verification, or tentative drafting
  (Steps 1-8). Contains the exact templates for overview.md and batch BRD
  files, plus the Plan Sizing Rules and Anti-Patterns for final review.
  In Resolution Mode, also triggered when editing overview.md or a batch BRD
  and you need to confirm the template structure is preserved.
---

# Implementation Plan Templates

## Template 1: `overview.md`

Written to `docs/implementation/phase-N/phase-N-M/overview.md`.

```markdown
# Implementation Overview: [Sub-Phase ID] — [Sub-Phase Title]
## Plan ID: [Sub-Phase ID]-P[N]

## Sub-Phase Reference
Sub-Phase ID: [e.g. Phase-1.2]
Sub-Phase Title: [from the sub-phase document]

## Objective
One paragraph. What this plan delivers within the sub-phase, and how it
relates to other plans in the same sub-phase if there are multiple.

## Scope
Bulleted list of exactly what is in scope across all batches.
Specific enough that a reviewer understands the full plan boundary.

## Out Of Scope
Bulleted list of what is explicitly not in scope.
Include things a reader might reasonably assume are included but are not.

## Architecture Contracts
Entities, events, and computations this plan implements or depends on.
For each, state the relationship: IMPLEMENTS, CONSUMES, or DEPENDS ON.
If an ADR was written for this plan, reference it here as DECISION.
This is the full list for all batches — batch BRDs include only the
subset relevant to that batch.

- `01-entities/twin-state.md` — IMPLEMENTS
- `01-entities/athlete.md` — DEPENDS ON (must exist before this plan starts)
- `00-foundations/event-catalogue.md` → `twin_recalibrated` — PRODUCES
- `docs/adr/004-append-only-twinstate.md` — DECISION (read before implementing)

## Invariants
Specific invariants this plan must preserve across all batches.
Copy exact text from the architecture document. Do not paraphrase.

## Cross-Validation Summary
Produced by Step 5 (Roasting Mode). A structured record of every
cross-check performed against architecture, vision, and codebase
reality. This is the plan's proof of correctness — downstream agents
(coder, validator) can see exactly what was verified and what gaps
remain.

| Check | Result | Detail |
|-------|--------|--------|
| RC1 Contract Saturation | ✓ / ✗ | <detail> |
| RC2 Vision Constraints | ✓ / ✗ / N/A | <detail> |
| RC3 Entity Collision | ✓ / ✗ / N/A | <detail> |
| RC4 Modification Safety | ✓ / ✗ / N/A | <detail> |
| RC5 Event Flow | ✓ / ✗ / N/A | <detail> |
| RC6 Invariant Enforcement | ✓ / ✗ | <detail> |
| RC7 ADR Re-Check | ✓ / ✗ | <detail> |

If any check is ✗, state whether the gap was resolved (Minor) or
escalated (Significant — see Architecture Gap Resolution). A plan with
unresolved Significant gaps must not proceed to the coder.

## Event Contracts
All events this plan produces or consumes across all batches. For each:
- event name
- PRODUCES or CONSUMES
- payload fields required by this plan
- ordering assumptions (what must have fired before this event is valid)
- producing batch and consuming batch(s)

## Pseudocode
For non-trivial orchestration or decision logic that spans batches,
show the flow in pseudocode. Pseudocode describes behaviour and data
flow — not production code.

Good:
  activity_calibration_eligible received
    → read activity.aerobic_load, neuromuscular_load, structural_load
    → compute banister_update(current_fitness, load, time_constants)
    → append TwinState with updated inline snapshot fields
    → if confidence threshold crossed → fire twin_confidence_upgraded

Bad:
  def recalibrate(activity_id):
      activity = db.query(Activity).filter(...)

If the pseudocode is specific to one batch, place it in that batch's BRD
instead (see Template 2 — Relevant Pseudocode).

## Testing Requirements
Concrete, observable outcomes the coder must verify before this plan is
done. Not "unit tests pass" — specific assertions against real behaviour.
Each testing requirement maps to a capability from the sub-phase document.

## Notes

Four categories, each gated by a one-line test. Use only the categories
that actually have content for this plan — an empty category is omitted
entirely, not included with "none." A single plan rarely needs all four.
This section covers plan-level notes; batch-specific notes go in each
BRD's Relevant Notes section.

**Architecture Clarifications** — does this resolve a genuine ambiguity
in what an *existing* architecture document already specifies? This is
not new information; it's the specific reading that applies here, stated
so the coder does not have to re-derive it.

**Deferred Decisions** — is this capability explicitly out of scope for
this phase, with a defined placeholder or default standing in for it now?
Name the phase or condition under which it will be revisited. "Not yet
decided" is not this category — that is a sign the plan is not ready.

**Implementation Clarifications** — is this a specific value, method, or
pattern choice with no architecture ambiguity behind it — you are simply
telling the coder exactly what to do, where a reasonable engineer could
otherwise have picked a different but equally defensible option?

**Known Risks** — could this go wrong in a way the coder should watch
for, even after being told the correct approach? Device variability, data
quality assumptions, and edge cases with an explicit fallback behaviour
belong here.

## ADRs Written
List any ADRs produced for this plan. For each: ADR number, title, and
one-line constraint the coder must observe.

## Gap Escalations
Significant gaps from the Cross-Validation Summary that were escalated
rather than resolved. For each: which check, what is missing, escalation
target, and whether it blocks this plan or can proceed without it.
```

## Template 2: Batch BRD (`batch-N-<theme>.md`)

Written to `docs/implementation/phase-N/phase-N-M/batch-N-<theme>.md`.
One file per batch from the Coder Batches grouping. Every BRD is
self-contained — a coder invoked with only this file can implement the
batch correctly. The coder never reads `overview.md` or any other batch's
BRD.

Load the `implementation-handoff-blocks` skill when producing BRDs and
architecture handoffs — it governs content rules for Context Needed
tiers, Batch Success Criteria, and architecture documentation handoff
conventions.

```markdown
# Batch BRD: [Sub-Phase ID] — Batch N — [Theme]
## Source: docs/implementation/phase-N/phase-N-M/overview.md

## Batch Objective
One to two sentences. What this batch delivers and how it fits in the
overall sub-phase sequence.

## Preconditions
If Batch 1: "No preconditions — this is the first batch."
Otherwise: "Batches 1 through N-1 are complete; their Batch Success
Criteria hold." Do not restate earlier batches' criteria.

## Scope
Bulleted list of exactly what this batch builds. Only this batch's files
and capabilities — nothing from earlier or later batches.

## Out Of Scope
What is explicitly not in this batch. Include things the coder might
reasonably assume are included but are not.

## Steps
Only the Coder-owned steps for this batch. Steps retain their original
numbering from the overview — do not renumber to 1, 2, 3. No DevOps or
Test Architect steps appear here.

Every step in a BRD must carry `[OWNER: Coder]`. The other owner tags
(`[OWNER: DevOps]`, `[OWNER: Test Architect]`) are drafting conventions
used during the architect's own planning process to separate Coder work
from migration-apply and test-generation work. They never appear in the
final BRD — if you see one in a BRD, you've leaked a non-Coder step in.

The migration generation/application split is deliberate: the coder
generates the revision file (it has full model context), DevOps reviews
it, augments it for hypertable/extension requirements if needed, and
applies it. The coder never calls `db-upgrade.sh` or `db-upgrade-test.sh`.

Steps reference architecture contracts by name. They do NOT specify
framework choices, library versions, or file structures.

Good step:
> 3. [OWNER: Coder] Implement `TwinRecalibrationService` to append a new
>    `TwinState` record on every `activity_calibration_eligible` event.

Bad step (no owner tag):
> 3. Write the twin recalibration code.

## Context Needed
Per-step: Primary, Secondary, Fallback, and Forbidden tiers for every
step in this batch. Follow the `implementation-handoff-blocks` skill exactly.
Close with the completeness statement.

## Batch Success Criteria
Specific, checkable conditions that hold when this batch is complete.
Follow the `implementation-handoff-blocks` skill exactly. Later batches assume
these hold — reference the batch number as a precondition in later
BRDs; do not restate criteria.

## Relevant Architecture Contracts
Only the Architecture Contracts entries from `overview.md` that this
batch's steps or Context Needed explicitly cite. Copied verbatim —
never paraphrased. Omit this section if nothing in this batch cites
any contract entry.

## Relevant Invariants
Only the Invariants entries from `overview.md` that this batch's steps
or Context Needed explicitly cite. Copied verbatim. Omit if none.

## Relevant Event Contracts
Only the Event Contracts table rows from `overview.md` that this
batch's steps produce or consume (the step's own prose states it).
Copied verbatim. Omit if none.

## Relevant Notes
Only Notes entries from `overview.md` (Implementation Clarifications,
Known Risks, etc.) that name a file, entity, or concept appearing in
this batch's Steps or Context Needed. Copied verbatim. Omit if none.

## Relevant Pseudocode
If `overview.md` has a Pseudocode section and it names a function,
method, class, or entity that also appears in this batch's Steps or
Context Needed: include the full section verbatim. Omit if none and
`overview.md`'s Pseudocode does not touch this batch.

## Files Expected To Change
- [NEW | EXISTING — modified | EXISTING — reference only] <path>
One line per file from this batch's Steps and Context Needed.
- `[NEW]` — a Step states this file is created
- `[EXISTING — modified]` — a Step states this file is edited
- `[EXISTING — reference only]` — appears only in Context Needed as
  reading material; no Step states it changes

## Coder Notes
Freeform section. Only populate if there is genuinely something to say
that is not already captured above: places where the architecture
requires a specific interpretation, things easy to get wrong, rationale
for step ordering, ADR constraints the coder must not violate. Do not
repeat information already in Architecture Contracts, Invariants, or
Steps. Omit the section entirely if empty — never include
"none" or a placeholder.
```

The BRD is the coder's sole input for this batch. Every contract,
invariant, event row, and note the coder needs for this batch must be
present in this file — copied verbatim from `overview.md`, never
paraphrased. The coder never reads `overview.md` or any other batch's
BRD.

Test scenarios for this batch go in a companion file
`batch-N-<theme>-tests.md` — see Template 3. The coder never loads it;
it is for the test architect only.

Architecture documentation updates for this batch go in a companion file
`batch-N-architecture.md` — see Template 4. The coder never loads it;
it is for `p-vision-and-architect-author` only.

---

## Template 3: `batch-N-<theme>-tests.md`

Written alongside each BRD at
`docs/implementation/phase-N/phase-N-M/batch-N-<theme>-tests.md`.

This file is loaded by the test architect, never by the coder. Each
scenario gives the test architect a concrete input/output pair to
generate assertions from. Omit this file entirely if the batch has no
behavioural changes worth a dedicated test scenario (purely structural
changes like adding a field or renaming a column do not need scenarios —
the test architect derives those from contracts).

```markdown
# Test Scenarios — Phase N.M — Batch N: <theme>

## Step <number> — <step description>

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | <scenario name> | <concrete input> | <concrete expected output> | type-system / database / application-logic | none / external-only / db-session |
| 2 | <scenario name> | <concrete input> | <concrete expected output> | type-system / database / application-logic | none / external-only / db-session |

...
```

Rules:
- One table per step that has behavioural changes. Multiple steps can
  share a table if they form a single workflow — label the step as
  "Steps N–M" in the header.
- Input/Expected must be concrete enough to turn into assertions. "Returns
  a valid X" is not concrete; "Returns `X(id=1, status='active')`" is.
- **Enforcement column** — which layer rejects invalid input for this
  scenario. `type-system` scenarios are skipped by the test architect
  (framework-enforced, not your logic). `database` scenarios get one
  integration test per constraint. `application-logic` scenarios get
  full branch coverage. See the architect's RC6 table for the full
  classification.
- **Mock Boundary column** — what the test architect should mock for this
  scenario. `none` — pure function, mock nothing. `external-only` — mock
  only out-of-process dependencies (HTTP, S3, LLM proxy), let all
  internal code run real. `db-session` — unit test, mock the DB session
  but let the service logic run real. The principle: mock at the
  external boundary, not the internal boundary.
- Include edge cases: missing data, boundary values, error conditions.
  A coder who passes every scenario has built what the plan intended.
- Scenarios are derived from the step's own prose, the Architecture
  Contracts, and the Invariants — they do not introduce new requirements.
  If you discover a requirement while writing scenarios that the step
  doesn't state, the step is incomplete — fix the step first.
- Scenarios for computational invariants must use the exact fixtures
  pinned in RC1 — same input, same expected output, same tolerance.
- Omit this file for batches with no behavioural changes. The test
  architect handles those from contracts alone.

---

## Template 4: `batch-N-architecture.md`

Written alongside each BRD at
`docs/implementation/phase-N/phase-N-M/batch-N-architecture.md`.

This file is loaded by `p-vision-and-architect-author` (or routed to it
by `p-technical-advisor`), never by the coder. It tells the architect
exactly which architecture documents need updating after this batch's
implementation changes. Omit this file if the batch does not change any
event flow, event catalogue entry, or architecture contract.

```markdown
# Architecture Documentation Updates — Phase N.M — Batch N: <theme>

## <file path relative to docs/>
### <section name>
- <specific change: add/update/remove entry X, change producer Y to Z>
- ...

## <file path relative to docs/>
...
```

Rules:
- One `##` heading per file to update (e.g. `docs/architecture/04-platform/event-topology.md`).
  Multiple files get multiple `##` headings.
- Under each file, one `###` heading per section to modify. Be specific: name the
  exact section header as it appears in the file.
- Each bullet is a concrete instruction: "Add consumer: `generate_plan` procrastinate
  task" not "Update the event flow."
- Include a reference to the coder's BRD so the architect can read it for context:
  "See `batch-3-event-flow-plan-router.md` for the implemented flow."
- Omit this file if the batch has no architecture documentation impact. Purely
  structural changes (file relocation, import rewiring, naming) do not need
  architecture doc updates — this is for behavioural changes that alter event
  flows, catalogue entries, or contracts.

The coder BRD should reference this file in its `## Relevant Notes` section
(e.g. "Architecture documentation updates are in `batch-3-architecture.md` —
routed to p-vision-and-architect-author") so the batch's scope boundary is
explicit.

---

## Implementation Plan Anti-Patterns

Avoid these in every plan. If a plan exhibits any of these, revise it
before handing off to the coder.

* **Plans that span multiple ownership domains** — if a plan requires two
  different services to be modified by the same implementation step, split it
* **Plans whose testing requirements depend on a later plan** — every plan
  must be independently verifiable at completion
* **Plans that contain architectural redesign** — implementation plans execute
  architecture; they do not redefine it
* **Plans that leave implementation decisions to the coder** — if a decision
  must be made, make it in the plan; the coder is an executor, not a designer
* **Plans that introduce new invariants** — invariants belong in architecture
  documents, not implementation plans
* **Plans that redefine event contracts** — event schema changes belong in the
  architecture event catalogue and require an ADR, not a plan step

Implementation plans execute architecture. They do not redefine it.

---

## Plan Sizing Rules

Correctly sized:
* one coder can implement it in a focused session without context-switching
* its testing requirements are independently verifiable
* it does not require the coder to make significant scope decisions

Too large:
* spans multiple unrelated ownership boundaries
* testing requirements depend on work from a later plan
* would take a coder multiple sessions with different mental contexts

Too small:
* delivers no independently testable capability
* purely scaffolding for a later plan
* could merge with an adjacent plan without increasing risk
