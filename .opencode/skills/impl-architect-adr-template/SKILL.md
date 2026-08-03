---
name: impl-architect-adr-template
description: >
  Load this when determining whether an ADR is required (Step 8 of the
  Implementation Planning Process) and when writing the ADR file. Contains
  the ADR decision criteria (when to create / when not to create), the
  ADR file template, and post-write procedure. Most plans need neither an
  ADR nor a delta proposal. Loaded by p-implementation-architect.
---

# ADR Template

## Decision Criteria

### When to Create an ADR

An ADR may be created when:
- The architecture defines the behaviour but multiple valid implementation
  approaches remain possible
- The decision affects implementation strategy: orchestration flow, persistence
  strategy, caching strategy, processing order, retry behaviour, reprocessing
  orchestration, or similar concerns
- The decision has meaningful alternatives that were considered and rejected
- The decision introduces implementation constraints that future coders must
  understand and preserve

### When NOT to Create an ADR

Do not create an ADR when the decision would alter or introduce:
- Ownership boundaries or architectural responsibilities
- Entity contracts or event contracts
- Event semantics or event payload definitions
- Invariants or cross-subsystem dependencies
- Domain behaviour or vision intent
- Release-plan scope

These are architecture decisions — they belong to the Architecture Author, not
the Implementation Architect.

Also do not create an ADR when:
- The decision is already documented in the architecture corpus or an existing ADR
- The implementation follows an established platform pattern with no meaningful
  alternative
- The decision is purely repository structure, file naming, or module layout
- The decision is a routine coding detail that future engineers are unlikely to
  revisit

### If Architecture Decision Required

If such a decision is required to proceed with implementation planning:
- Stop planning
- Document the issue precisely — what decision is needed, why it cannot be
  deferred, what the implementation is blocked on
- Escalate to the Architecture Author

## Template

Write to `docs/adr/NNN-<slug>.md` using the native write tool, where
`NNN` is the next available zero-padded number in the sequence.

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

## Examples of Valid Implementation ADRs

- **Snapshot storage strategy** — how TwinState snapshots are stored and retrieved
- **Event replay strategy** — how the system replays events after algorithm upgrades
- **Idempotency implementation approach** — how duplicate ingestion is detected
- **Cache invalidation approach** — when and how caches are invalidated
- **Batch vs streaming execution strategy** — choosing between batch processing and streaming for a specific computation
- **Reprocessing orchestration strategy** — how the system handles reprocessing of historical data