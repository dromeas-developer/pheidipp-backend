---
name: resolution-mode-procedure
description: >
  Load this when entering Resolution Mode — i.e. you receive a report
  from p-implementation-validator or p-devops routed to p-implementation-architect,
  and no sub-phase document is provided. Contains the full R0-R5
  procedure for classifying and resolving routed findings, plus the
  Resolution Report Format. Not needed in Plan Mode. Load exactly once
  at mode entry; do not reload during the session.
---

# Resolution Mode — R0–R5 Procedure

You are here because `p-implementation-validator` or `p-devops` routed
findings to you. Both agents already classify their findings and state,
in their own Routing Summary, exactly which findings are meant for you.
Only act on what is routed to `p-implementation-architect`. Everything else in the same
report is real, correctly reported, and not yours.

## R0 — Identify Your Scope

Read the report's `## Routing Summary` first — it already groups every
finding by owner. Your scope is every row where `Route = p-implementation-architect`.
This includes all Plan Gap findings, Architecture Change Required rows,
Layer 3 DEVIATION/CRITICAL rows, and DevOps RCs assigned to `p-implementation-architect`.

MINOR rows are never yours (always `p-coder`). Layer 3 `Acceptable` rows
need no action.

If the Routing Summary has no row for `p-implementation-architect`, or its row is empty,
STOP — you are not the correct recipient.

## R1 — Fetch The Implementation Plan

Every finding routed to you references the implementation plan it was
validated against. The plan path appears in the validator report's
header (`Plan: docs/implementation/<path-to-plan>.md`) or is inferable
from the devops report's plan id. Fetch it via `get_files` — once,
batched with any other files the findings explicitly name.

The plan is your primary reference for what was supposed to be built.
Findings routed to you are, by definition, claims that the plan itself
is insufficient, contradictory, or that something outside it needs
architectural acknowledgement — so you cannot resolve them without
reading the plan they were raised against.

## R2 — Classify Each Routed Finding

For every finding in your scope, determine which of these it is. This
classification drives the resolution path in R3.

**Plan Gap** — the plan is missing a contract, invariant, ownership
boundary, or event detail that the implementation needs. The validator
tags these as `PLAN GAP` (MAJOR, Architecture Change Required by
definition); devops tags them Category `Specification / Plan Gap`.
Resolution: update the plan.

**Plan Defect** — the plan contains an internal contradiction, an
unsatisfiable criterion, or a step that cannot be correctly implemented
as written. Resolution: fix the plan.

**Architecture Gap** — a contract the plan references is genuinely
missing from the architecture corpus, or an architecture document
contradicts what the plan requires. Resolution: Architecture Gap
Resolution procedure — minor gap → update the architecture doc and
re-index; significant gap → escalate to the Architecture Author.

**Unauthorized Scope (Layer 3 DEVIATION/CRITICAL)** — the coder added
something outside the plan. This is not a plan defect; it is a
judgement about whether the addition should be accepted. Resolution:
either accept it (update the plan to incorporate it formally) or reject
it (route back to `p-coder` to remove it). An accepted deviation that
introduces a new ownership boundary, event contract, or invariant
requires an ADR — see Step 8's ADR criteria, which apply here too.

**Misclassification — No Architecture Change Needed** — once you read
the plan and the code the finding describes, the fix turns out to be a
plain implementation correction that needs none of the six things in
the "No Silent Deviations" test (new event, new ownership boundary,
schema redesign, invariant change, contract reinterpretation,
cross-subsystem dependency change). The validator routes to you "when
unsure" by design — an unnecessary architect review costs less than
asking `p-coder` to make an architecture decision it is separately
instructed to refuse. But if you are confident the finding is
misclassified, do not do architecture work on it anyway: bounce it back
to `p-coder` with a one-line reason so the validator can recalibrate.
This is the symmetric case to `p-coder`'s own "if your read of the code
disagrees with the validator's classification, STOP and report" rule.

## R3 — Resolve Each Finding Per Its Classification

Process findings in the order that minimises rework: Plan Gaps and
Plan Defects first (they may change what the coder needs to do), then
Architecture Gaps (they may change what the plan can promise), then
Unauthorized Scope decisions (they depend on the plan being correct
first).

**Plan Gap / Plan Defect → update the implementation plan.** Edit the
affected file directly using the `edit` tool — `overview.md` for
architecture-level gaps (missing contracts, missing invariants, event
table errors) or the specific batch BRD for execution-level gaps
(missing Context Needed, broken Success Criteria). The update must
preserve the template structure exactly — load the
`implementation-plan-templates` skill to confirm. If the gap or defect
affects a batch BRD's Context Needed or Batch Success Criteria, load
the `coder-handoff-blocks` skill and update those blocks per its spec.
If the gap requires an ADR (see Step 8 criteria), write the ADR first,
then reference it in `overview.md`'s Architecture Contracts section with
the `DECISION` label.

**Architecture Gap → Architecture Gap Resolution.** Classify as Minor or
Significant. A Minor gap lets you update the architecture document, call
`refresh_architecture`, and continue. A Significant gap stops planning
and escalates to the Architecture Author; in Resolution Mode this means
the finding cannot be fully resolved this session and the report must
say so.

**Unauthorized Scope → accept or reject.** Read the code the deviation
added (scoped to what the finding names — do not retrieve broadly).
Decide:
* **Accept** — the addition is architecturally sound and should become
  part of the plan. Update the plan to incorporate it formally. If it
  introduces a new ownership boundary, event contract, or invariant,
  write an ADR first. Then the coder's next session implements against
  the updated plan; no removal is needed.
* **Reject** — the addition should not have been made. Route back to
  `p-coder` with a one-line instruction to remove it. Do not remove it
  yourself — you do not write production code.

**Misclassification → bounce back.** Do not resolve the finding. Note
in the report that it was misclassified, state the one-line reason, and
route it to `p-coder`. This is not a failure of the validator — the
validator's "when unsure, route to architect" default is correct by
design; this is the expected outcome for the uncertain subset of
routed findings, and the validator recalibrates from it.

## R4 — Self-Check Before Producing Output

Before writing the Resolution Report, verify:

* every finding routed to `p-implementation-architect` in the Routing Summary has been
  classified and resolved per R3 — none skipped, none silently dropped
* no finding routed to `p-coder`, `p-test-architect`, `p-devops`, or
  `Unassigned` was touched, even if you could see how to resolve it
* every plan update preserves the template structure exactly (load
  `implementation-plan-templates` to confirm if unsure)
* every architecture document update was followed by
  `refresh_architecture` if the architecture index is stale
* every ADR written was followed by `refresh_architecture` and
  referenced in the plan's Architecture Contracts section
* no finding was resolved by silently crossing the Architecture
  Authority line — if a resolution would require changing ownership
  boundaries, event contracts, invariants, or vision intent, it is an
  Architecture Delta Proposal, not a plan edit, and it goes to the
  Architecture Author instead

## R5 — Produce The Resolution Report

Write the report to `reports/<plan-id>_architect_resolution.md` using
the `write` tool. Follow the Resolution Report Format below exactly.

---

## Resolution Report Format

```markdown
# Architect Resolution Report — <Plan ID>
Date: <date>
Source report: reports/<plan-id>_validation.md | reports/<plan-id>_devops.md
Plan: docs/implementation/<path-to-plan>.md

## Result: RESOLVED | PARTIALLY RESOLVED | BOUNCED | ESCALATED

* RESOLVED — every routed finding addressed; plan and/or architecture
  updated; no escalation needed
* PARTIALLY RESOLVED — some findings addressed; at least one escalated
  to the Architecture Author (Significant Architecture Gap) or bounced
  to p-coder (misclassification)
* BOUNCED — every routed finding was misclassification; nothing
  required architecture work; all bounced to p-coder
* ESCALATED — every routed finding required Architecture Author
  involvement; none could be resolved this session

---

## Findings Resolved

| Finding | Source | Classification | Resolution | Artifact |
|---------|--------|----------------|------------|----------|
| Layer 2: PLAN GAP — ip_address anonymisation invariant | validator | Plan Gap | Added invariant to overview.md's Invariants section; updated batch BRD's Context Needed | overview.md, batch-1 BRD updated |
| Layer 3: event_log.py — new EventLog model | validator | Unauthorized Scope — Accepted | ADR-007 written; plan updated to incorporate EventLog formally | ADR-007, plan updated |
| RC2 — Specification / Plan Gap | devops | Plan Defect | Step 4 criterion was unsatisfiable; rewritten to match what the code actually requires | plan updated |

---

## Findings Bounced Back

| Finding | Source | Reason | Route To |
|---------|--------|--------|----------|
| Layer 1 Step 8 — returns 404 where plan states 403 | validator | Misclassification — fix is relocating code to the correct layer, which the plan already names; no architecture change needed | p-coder |

---

## Findings Escalated

| Finding | Source | Reason | Escalated To |
|---------|--------|--------|--------------|
| Layer 2: missing ownership boundary for X | validator | Significant Architecture Gap — architecture corpus has no contract for X; cannot be safely inferred | Architecture Author |

---

## Artifacts Produced

* Updated files: docs/implementation/phase-N/phase-N-M/overview.md (list every section changed)
* Updated BRDs: docs/implementation/phase-N/phase-N-M/batch-N-<theme>.md (list each, or omit if none)
* ADRs written: docs/adr/NNN-<slug>.md (list each, or omit if none)
* Architecture docs updated: <path> (list each, or omit if none)
* Architecture index refreshed: yes / no

---

## Next Step

* RESOLVED → p-coder re-implements against the updated plan (if plan
  changed), or p-devops re-runs (if architecture-only change)
* PARTIALLY RESOLVED → p-coder acts on bounced findings; Architecture
  Author acts on escalated findings; remaining findings are done
* BOUNCED → p-coder acts on the bounced findings; no architecture work
  was needed
* ESCALATED → Architecture Author acts; no further work this session
```

Confirm the report was saved, then STOP.
