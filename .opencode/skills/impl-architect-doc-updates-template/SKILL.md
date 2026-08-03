---
name: impl-architect-doc-updates-template
description: >
  Load this when writing the architecture documentation updates file
  (batch-N-architecture.md) alongside a batch BRD in Step 9 of the
  Implementation Planning Process. Contains the template and writing rules.
  Loaded by p-implementation-architect.
---

# Architecture Documentation Updates Template

Write to `docs/implementation/phase-N/phase-N-M/batch-N-architecture.md`.

This file is loaded by `s-vision-and-architect-author` (or routed to it
by `p-technical-advisor`), never by the coder. It tells the architect
exactly which architecture documents need updating after this batch's
implementation changes. Omit this file if the batch does not change any
event flow, event catalogue entry, or architecture contract.

## Template

```markdown
# Architecture Documentation Updates — Phase N.M — Batch N: <theme>

## <file path relative to docs/>
### <section name>
- <specific change: add/update/remove entry X, change producer Y to Z>
- ...

## <file path relative to docs/>
...
```

## Rules

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
routed to s-vision-and-architect-author") so the batch's scope boundary is
explicit.