---
name: impl-architect-batch-brd-template
description: >
  Load this when writing a batch BRD (batch-N-<theme>.md) in Step 9 of the
  Implementation Planning Process. Contains the BRD template, step writing
  rules, batch anti-patterns, and sizing rules. For inline context tier
  conventions and Batch Success Criteria rules, load
  impl-architect-handoff-blocks alongside this skill.
  Loaded by p-implementation-architect.
---

# Batch BRD Template

Write to `docs/implementation/phase-N/phase-N-M/batch-N-<theme>.md`.
One file per batch from the Coder Batches grouping. Every BRD is
self-contained — a coder invoked with only this file can implement the
batch correctly. The coder never reads `overview.md` or any other batch's
BRD.

Load the `impl-architect-handoff-blocks` skill when producing BRDs and
architecture handoffs — it governs content rules for inline context
tiers, Batch Success Criteria, and architecture documentation handoff
conventions.

## Template

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

Every step must carry `[OWNER: Coder]`. The other owner tags
(`[OWNER: DevOps]`, `[OWNER: Test Architect]`) are drafting conventions
used during the architect's own planning process. They never appear in
the final BRD.

Steps reference architecture contracts by name. They do NOT specify
framework choices, library versions, or file structures.

**Context is inline with each step.** The coder reads one step and has
everything needed to implement it — no jumping to a separate section.

Step format:
N. [OWNER: Coder] <step description>
   Primary: <1-2 items that alone should answer this step>
   Secondary: <supporting items, request only if Primary is insufficient>
   Fallback: <last-resort lookup, e.g. get_entity_context(EntityName)>
   Forbidden: <specific named thing to avoid, if one exists>

Close the steps section with:
> (This is everything relevant to the steps above. Primary items are
> fetched together in Pre-Flight Step 3; Secondary and Fallback are
> requested only on demand.)

## Batch Success Criteria
Specific, checkable conditions that hold when this batch is complete.
Later batches assume these hold — reference the batch number as a
precondition in later BRDs; do not restate criteria.

## Relevant Invariants
Only the Invariants entries from the architecture docs that this batch's
steps must preserve. Copy exact text from the architecture document.
Do not paraphrase. Omit if none.

## Relevant Notes
Only notes that name a file, entity, or concept appearing in this batch's
Steps. Sources: architecture docs, the cross-validation report, or the
architect's own analysis. Include Implementation Clarifications, Known
Risks, and Deferred Decisions that apply to this batch. Copied verbatim.
Omit if none.

## Relevant Pseudocode
If the architecture docs or the architect's analysis contain pseudocode
that names a function, method, class, or entity appearing in this batch's
Steps: include it verbatim. Omit if none.

## Files Expected To Change
- [NEW | EXISTING — modified | EXISTING — reference only] <path>
One line per file from this batch's Steps.
- `[NEW]` — a Step states this file is created
- `[EXISTING — modified]` — a Step states this file is edited
- `[EXISTING — reference only]` — appears only in inline context as
  reading material; no Step states it changes

## Coder Notes
Freeform section. Only populate if there is genuinely something to say
that is not already captured above. Omit the section entirely if empty —
never include "none" or a placeholder.
```

## Step Writing Rules

### Detail Level

| Aspect | Detail Level | Guideline |
|--------|-------------|-----------|
| What to build | Specific | Named service/agent/function, not "the feature" |
| Where to build | Exact path | `app/services/foo.py`, not "the services layer" |
| Which pattern to follow | Named reference | "Follow the `FirstMessageAgent` pattern exactly" |
| What to preserve | Named invariant | "Preserve the single-commit boundary from ADR-014" |
| What NOT to do | Explicit | "Do NOT hold an AsyncSession" |

### Do NOT Specify

- exact ORM column declarations or SQLAlchemy syntax
- exact class or method signatures
- exact imports or package exports
- exact endpoint boilerplate or HTTP status codes
- exact migration contents or alembic commands
- exact implementation constants

### Boundary Test

If a coder could mechanically generate code from the step without reading
existing code patterns, the step is too detailed. The step tells the coder
*what* to build and *why*, not *how* to write it.

### Step Writing Examples

- Too low-level: "Add `recorded_at: Mapped[datetime]` column to `EventLog`."
- Correct: "Extend event log model to capture timestamp and source attribution."
- Too low-level: "Create `EventLogRepository` with methods `get_by_source_id`, `get_by_date_range`."
- Correct: "Introduce persistence abstraction for event log data supporting lookup by source and range retrieval."

### Context Tiers and Batch Success Criteria

These rules live in `impl-architect-handoff-blocks` — load it alongside
this template. It owns the full spec for Primary/Secondary/Fallback/Forbidden
tiers and observable/negative/ordering Batch Success Criteria rules.
Do not duplicate them here.

### Migration Split

The coder generates the revision file (it has full model context), DevOps
reviews it, augments it for hypertable/extension requirements if needed,
and applies it. The coder never calls `db-upgrade.sh` or `db-upgrade-test.sh`.

## Batch Anti-Patterns

Check these at the BRD level:

- **Leaves implementation decisions to the coder** — if a decision must
  be made, make it in the step; the coder is an executor, not a designer
- **Contains architectural redesign** — batch steps execute architecture;
  they do not redefine it
- **Introduces new invariants** — invariants belong in architecture
  documents, not batch steps
- **Redefines event contracts** — event schema changes belong in the
  architecture event catalogue and require an ADR, not a batch step

## Batch Sizing Rules

- Correctly sized: one coder can implement it in a focused session
  without context-switching, no significant scope decisions left to
  the coder
- Too large: would take a coder multiple sessions with different mental
  contexts
- Too small: delivers no independently testable capability, purely
  scaffolding for a later batch, could merge with an adjacent batch
  without increasing risk

## Companion Files

Test scenarios for this batch go in `batch-N-<theme>-tests.md` — loaded
by the test architect, never the coder. Architecture documentation updates
go in `batch-N-architecture.md` — loaded by `s-vision-and-architect-author`,
never the coder.