---
name: coder-handoff-blocks
description: >
  Load this when writing the Coder Handoff Notes section of an
  implementation plan — i.e. after the Implementation Steps are already
  drafted and you are producing the final handoff package. Not needed
  during retrieval, verification, or tentative drafting (Steps 1-6 of the
  Implementation Planning Process). Contains the full spec for the four
  MANDATORY blocks: Coder Scope, Coder Batches, Batch Success Criteria,
  and Context Needed.
---

# Coder Handoff Notes — Mandatory Block Specifications

Everything the coder needs that is not captured in the rest of the plan:
- known risks in the implementation
- places where the architecture requires a specific interpretation
- things that are easy to get wrong
- rationale for step ordering beyond what the Coder Batches block already
  encodes mechanically — the block is for *what* order, this is for *why*
- if an ADR was written: state its path and what constraint it imposes that
  the coder must not violate during implementation

Four blocks are MANDATORY and must appear first, in this order, in every
Coder Handoff Notes section.

## Coder Scope

List every step number and its owner. The coder executes only the steps
listed under Execute and skips all others.

```
## Coder Scope
Execute:  Steps N, N, N  [OWNER: Coder] — includes migration generation
Skip:     Step N (DevOps — migration review and application),
          Step N (Test Architect — tests)
```

## Coder Batches

Every plan's Execute steps grouped into ordered, dependency-respecting
batches. This is not optional and not just for long plans — the coder is
always invoked once per batch, never once for an entire plan, so every
plan needs at least one batch. Construct batches so that:

- a plan with 6 or fewer Coder-owned steps still needs this block — it is
  valid, and often correct, for it to contain a single batch covering all
  of them ("Batch 1: Steps 1-6"). Do not fragment a small plan into
  multiple batches for its own sake; one honest batch is fine
- steps within a batch depend only on files that exist before the plan
  starts, or were created earlier in the same batch — never on a later batch
- a file touched by several steps stays inside one batch wherever
  possible, rather than being reopened across a batch boundary
- each batch is a coherent unit of work with its own one-line theme
- step count is not a proxy for batch size. A single step that touches an
  already-large method with several interacting concerns (an ordering
  constraint against other events, a conditional branch, a payload
  change) can cost more to implement correctly than four small additive
  steps combined. If one step in a batch is disproportionately complex
  relative to the rest of the plan, say so in the batch's theme rather
  than letting it look identical to a simple one

```
## Coder Batches
Batch 1: Steps N, N       — <theme>
Batch 2: Steps N, N, N    — <theme>
Batch 3: Steps N          — <theme, flagged if disproportionately complex>
```

## Batch Success Criteria

For each batch, the specific, checkable conditions that must hold true
when it is done. This is what makes validation possible per batch instead
of only once at the end of the whole plan — something a batch got subtly
wrong is caught immediately after that batch, not several batches later
when finding and unwinding it costs far more.

Rules:
- State conditions that can actually be checked against the code or a
  test run — "the `SportType` enum exists with values X, Y, Z", not
  "sport type handling works correctly"
- Every criterion for a batch must be satisfiable using only what that
  batch's own steps produce — never write a criterion that secretly
  depends on a later batch
- The next batch is entitled to assume every earlier batch's criteria
  already hold. Reference the batch number as a precondition; do not
  restate its criteria
- If a batch involves an ordering or contract claim that could plausibly
  be stated elsewhere in the plan too (event firing order is the most
  common case — see the Event Contracts table), state the criterion
  specifically enough to catch a disagreement — name the exact order, not
  "events fire correctly." Writing this criterion is also your check:
  before finalizing it, confirm it agrees with what the Event Contracts
  table, Non-Obvious Decisions, and Pseudocode each say about the same
  ordering. A plan that states the same fact two different ways in two
  sections is a defect the coder should never have to notice and resolve
  on your behalf

```
## Batch Success Criteria
Batch 1 complete when:
- <observable condition>
- <observable condition>
Batch 2 assumes Batch 1 is complete. Batch 2 complete when:
- <observable condition>
```

## Context Needed

For each Execute step, the specific existing files, architecture
sections, and invariants that step depends on. Nothing more. You already
know this: every step you write cites the specific pattern, contract, or
existing component it depends on in its own prose (a repository method, a
constraint name, "follow the X pattern exactly," a named invariant). This
block extracts that into a list the coder can act on directly, instead of
leaving it embedded in prose that only becomes actionable after a careful
re-read. Do not do new analysis to produce this — restate what the step
already establishes, in list form.

Rank what you list by how likely it is to actually be needed, in three
tiers:

- **Primary** — the smallest set of files, entities, or invariants that
  alone should resolve most of what this step needs. Usually one or two
  items. This is the only tier fetched upfront, in Pre-Flight Step 3.
- **Secondary** — supporting material needed only for edge cases or full
  correctness, not for the step's main path. Not fetched upfront — the
  coder requests these explicitly, and only if Primary genuinely did not
  answer the question.
- **Fallback** — the last resort, typically a broader lookup (e.g.
  `get_entity_context(EntityName)`) rather than a specific file, used
  only when Primary and Secondary both failed to resolve the step.

Most steps need only Primary. Only populate Secondary or Fallback when
you can genuinely foresee a case where Primary alone might not be enough
— do not populate them by default just because the tiers exist.

This is different from an "Optional" tier, which does not exist here and
should not be added. An optional tier invites the coder to explore more
than it needs, "to be thorough." Secondary and Fallback do the opposite —
they exist so that if Primary is not enough, the coder has one named
place to go instead of guessing or reaching into unrelated parts of the
codebase, and so that it has explicit permission to stop at Primary the
rest of the time rather than fetching everything "just in case."

Further rules:
- List only what THIS step needs — not what a neighbouring step needs,
  even if the two are related. If step 6 depends on the output of step 5
  rather than an existing file, say so ("output of Step 5"), not the file
  path — the coder will have just written it and does not need to re-fetch
  its own recent work.
- Existing files: exact paths, not "the repositories directory"
- Architecture/invariants: name the specific section or invariant ID, not
  the whole document
- If a step genuinely needs nothing beyond the plan's own Scope and
  Architecture Contracts sections (rare — most steps reference something
  specific), write "Primary: plan sections only"
- Add a `Forbidden:` line for a step only when you know, from your own
  retrieval earlier in this session, of a *specific* adjacent file or
  service the coder could plausibly but wrongly reach for — something
  that shares a name, a concept, or sits one directory over from what
  this step actually needs. Name it explicitly. This is not a tier the
  coder retrieves from — it is a named thing to avoid, independent of
  Primary/Secondary/Fallback
- Close the list with an explicit completeness statement covering all
  tiers together — "this is everything relevant to the steps above" —
  rather than leaving it open-ended. State it as a fact, not a
  reservation

```
## Context Needed
Step N:
  Primary:    <the 1-2 items that alone should answer this step>
  Secondary:  <supporting item(s), request only if Primary is insufficient>
  Fallback:   <last-resort lookup, e.g. get_entity_context(EntityName)>
  Forbidden:  <specific named file/service the coder might plausibly but
              wrongly reach for, if one exists>
Step N:
  Primary:    output of Step N (not yet on disk)
(This is everything relevant to the steps above. Primary items are
fetched together in Pre-Flight Step 3; Secondary and Fallback are
requested only on demand.)
```

These blocks also tell the coder a safe grouping for consolidating
same-file edits within a batch — see "Consolidate Same-File Edits" in the
coder's Execution Protocol.
