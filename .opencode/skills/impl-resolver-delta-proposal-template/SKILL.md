---
name: impl-resolver-delta-proposal-template
description: >
  Load this when a discovered conflict between architecture and implemented
  reality cannot be resolved within the plan itself and must be escalated
  to the Architecture Author. Contains the Architecture Delta Proposal
  format. Loaded by p-implementation-resolver and p-implementation-architect.
---

# Architecture Delta Proposal Template

Use when a discovered conflict between architecture and implemented
reality cannot be resolved within the plan itself and must be escalated
to the Architecture Author.

## Template

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