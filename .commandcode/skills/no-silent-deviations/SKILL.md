---
name: no-silent-deviations
description: >
  Load this when an agent modifies application code and needs the
  canonical architectural boundary test — the six-bullet test that
  determines whether a fix crosses from implementation correction into
  architecture change. Agents that do not modify code should not load
  this skill.
---

# No Silent Deviations — Architectural Boundary Test

This is the canonical definition of the boundary between **implementation work**
and **architectural work**. Every agent in the Pheidipp ecosystem that touches
code must enforce this boundary. Do not redefine, paraphrase, or subset it —
load this skill.

---

## The Test

Before making any change that is not a direct, mechanical correction of a
stated requirement, ask: **would correcting this require any of the following?**

1. A new event or modified event payload contract
2. A new ownership boundary or responsibility not already specified
3. A schema redesign not specified in the plan or finding
4. An invariant change
5. A reinterpretation of an architecture contract
6. Any change to cross-subsystem dependencies

**If the answer to any of the above is YES → STOP.**

Do not implement the change. Do not "fix it anyway because it looks small."
Document the issue precisely and escalate to `p-implementation-architect`.

---

## Why This Exists

The architecture hierarchy (Vision → Architecture → Plans → Implementation)
exists to prevent undocumented drift. Silent deviations — changes that
cross an architectural boundary without an explicit decision — corrupt that
hierarchy whether they originate in:

- Batch Mode implementation (`p-coder`)
- Fix Mode corrections (`p-coder` from validator/devops reports)
- Diagnostic fixes (`p-diagnostics-fixer` chasing LSP errors)
- Validation-time classification (`p-implementation-validator` routing)

All four entry points share this exact test so the boundary is enforced
consistently, regardless of which agent encounters it first.

---

## What "No" Looks Like (Implementation Fix — You May Proceed)

- A completely missing function the plan explicitly names
- An incorrect implementation of a behaviour the plan already specifies
- Logic in the wrong layer when the plan already states the correct layer
- A wrong status code the plan already specifies correctly
- An unenforced invariant the plan already states clearly
- An event payload missing fields the plan already lists

---

## What "Yes" Looks Like (Architecture Change Required — You Must Stop)

- The plan does not specify which service owns a new piece of logic
- The fix would require a new event type or changed payload
- The fix would change an invariant's semantics (not just enforce it)
- The fix would move logic across an ownership boundary the plan doesn't define
- The fix would add a dependency between subsystems that didn't exist before
- A contract missing from the plan that the implementation needs

---

## Enforcement

- `p-coder`: Enforced in both Batch Mode and Fix Mode
- `p-implementation-validator`: Uses this test as the **Resolution Path**
  classification for every CRITICAL and MAJOR finding
- `p-diagnostics-fixer`: Enforced before any diagnostic fix that crosses
  a boundary

If you are writing a new agent that modifies application code, you must
load this skill and enforce this test.
