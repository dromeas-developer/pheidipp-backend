---
name: coder-contract-gap-check
description: >
  Load when an architecture contract referenced in a BRD step or routed
  finding is unclear, contradicted by the code, or absent from context.
  Defines when to delegate to s-contract-verifier and the fallback path.
  Loaded on demand by p-coder-batch-mode and p-coder-fix-mode.
---

If the plan (Batch Mode) or the routed finding (Fix Mode) references an
architecture contract that is unclear or contradicted by what you see in
the code, delegate to `s-contract-verifier` for that specific entity:

```
Tool: task
Input:
{
  "subagent_type": "s-contract-verifier",
  "description": "Resolve entity or event contract",
  "prompt": "Entity: <entity_name>"
}
```

The contract verifier returns schema, events (with payload fields and
producer/consumer), invariants (with type and enforcement), APIs, and
storage rules — everything needed to resolve the contract question.

Use this delegation only when:
* implementation is blocked on an unclear contract
* code and plan (or code and the routed finding) appear inconsistent
  with each other
* a referenced contract is absent from the plan's or report's detail
* a file named in scope feels like it might implement multiple entities —
  call `get_arch_for_code(file_path)` to confirm which architecture
  entities live in this file and whether modifying it crosses entity
  boundaries the plan didn't warn about

Never use it for general orientation or exploration — the plan/report and
injected context cover that.

**Fallback:** call `get_entity_context(entity_name)` directly only after
an actual `task` call to `s-contract-verifier` for that entity has
failed, timed out, or returned `Confidence: LOW` with a flag you cannot
resolve from the brief alone. "It seemed faster to just fetch it myself"
is never a valid reason. If the brief is sufficient, use it — do not
fetch the entity a second time yourself.
