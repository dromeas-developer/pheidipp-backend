---
name: architecture-decision-templates
description: >
  Load this only when you have already determined (per Step 8 of the
  Implementation Planning Process) that an ADR is required, or when Step 4
  or Step 6 has surfaced a genuine architecture conflict that cannot be
  resolved within the plan. Most plans need neither. The decision criteria
  for whether an ADR or architecture escalation is warranted stay in the
  main prompt — this skill is the formatting template only, needed at the
  exact moment of writing the file, not for the judgment call that
  precedes it.
---

# Architecture Decision Templates

## ADR File Template

Write it to `docs/adr/NNN-<slug>.md` using the native write tool, where
`NNN` is the next available zero-padded number in the sequence. Follow
this structure exactly:

```markdown
---
id: ADR-NNN
status: accepted
tags: [tag1, tag2]
supersedes: ~
superseded-by: ~
---

# ADR NNN: Title

## Rules
Machine-readable directives only. Each rule: `**Name**: one-line imperative.`
Maximum 6 rules. Omit any rule already in stack-truth — reference it instead.

## Decision
One paragraph, 3–5 sentences. What was decided and the single clearest reason why.

## Rationale
3–6 bullets. One domain-specific reason per bullet why this option over others.
Do not repeat the Rules section. Do not explain general software principles.

## Alternatives Rejected
Table: | Option | Why Rejected |
One row per alternative. Rejection reason: one sentence, specific to this project.

## Tradeoffs
- **Pro**: ...
- **Con**: ...
Maximum 3 pros, 3 cons. Honest — do not minimise the cons.

## Compliance
One compliant code snippet. One non-compliant code snippet.
No explanatory prose. Omit if the rule is structural and not expressible in code.

## Cross-References
[ADR-NNN: Title](./NNN-slug.md) — one-line relationship description
```

After writing the ADR, call `refresh_architecture` to index it. Then
reference it in the implementation plan's **Architecture Contracts**
section with the `DECISION` label, and state the constraint it imposes in
**Coder Notes**.

---

## Architecture Delta Proposal Format

Use when a discovered conflict between architecture and implemented
reality cannot be resolved within the plan itself and must be escalated
to the Architecture Author.

```markdown
# Architecture Delta Proposal

## Sub-Phase: [Sub-Phase ID and title]

## Discovered Conflict
What the architecture specifies and what implemented reality shows.
Name the exact architecture document, the exact invariant or contract,
and the exact code evidence — cite the State Explorer's brief
(e.g. its registry of entities, services, repositories, event producers,
transaction boundaries) when it directly demonstrates the conflict; fall
back to specific file/line evidence from scoped retrieval when the
registry doesn't cover it.

## Why This Cannot Be Resolved In The Plan
Why the implementation plan cannot bridge this gap without redefining
architecture. If it can be resolved with a coder handoff note, it should be.

## Proposed Architecture Change
What the architecture document should say instead. This is a proposal —
the Vision & Architecture Author decides.

## Affected Documents
Every architecture, vision, or ADR document that would need updating.
```
