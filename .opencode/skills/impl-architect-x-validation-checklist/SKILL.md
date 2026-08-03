---
name: impl-architect-x-validation-checklist
description: >
  Load this at Step 5 of the Implementation Planning Process when
  cross-validating the tentative plan against architecture, vision,
  and codebase reality (Roasting Mode). Contains the full RC1-RC7
  check definitions, computational invariant fixture gate, input
  validation enforcement layer table, Test Scenario Grill procedure,
  and Enforcement/Mock Boundary classification tables. Loaded by
  p-implementation-architect only. Not needed in Resolution Mode.
---

# Cross-Validation Checklist — Roasting Mode

Execute these checks in order against the tentative plan and already-retrieved
context (Steps 1-4). Record one of:
- ✓ SATISFIED — plan handles this correctly
- ✗ GAP — plan is missing something; note what and escalate or resolve
- — N/A — not applicable to this plan

---

## RC1 — Contract Saturation

Every architecture entity, event, and invariant the Doc Explorer returned
for this sub-phase's domain must appear in the plan's Architecture Contracts
section or be explicitly excluded from scope. If a returned contract is
absent from the plan and not excluded, flag as GAP.

### Computational Invariant Fixture Gate

A computational invariant — any invariant whose enforcement is a formula,
decay, threshold, ratio, or numeric transformation rather than a structural
constraint (append-only, ownership boundary, layer separation) — must ship
with a concrete numeric fixture in the plan: a specific input, the expected
output, and a tolerance.

Qualitative description alone is a GAP, same severity as a missing event
contract. The fixture must be precise enough that a test assertion can be
written directly from it — a concrete numeric triple (input, expected
output, tolerance), not a prose approximation of the behaviour.

This gate lives in the architect's own RC1 reasoning, not in
`s-contract-verifier`'s output — the contract verifier returns invariant
type and enforcement mechanism, not fixtures. The architect is the one
who knows whether an invariant is computational (and thus needs a fixture)
versus structural, because that judgment requires reading the invariant's
prose, not just its metadata.

For entities the plan touches, delegate contract retrieval to
`s-contract-verifier` for structured comparison:

```
Tool: task
Input:
{
  "subagent_type": "s-contract-verifier",
  "description": "Verify entity contract for sub-phase planning",
  "prompt": "Entity: <entity_name>\n\nAspects: events, invariants"
}
```

A single `get_related_contracts(entity)` call for the primary entity may
be warranted if Doc Explorer's results feel narrow — but prefer reasoning
over already-gathered context first.

---

## RC2 — Vision Constraint Completeness

Every constraint (behavioural rule, UX requirement, coaching principle) from
the vision context that touches this sub-phase's capabilities must map to
a specific plan step, invariant, or testing requirement. Flag any vision
constraint with no enforcement path.

Example: "The twin must never show confidence below 0.3" is a constraint —
if the plan implements confidence display but has no step or invariant
enforcing the floor, that is a GAP.

---

## RC3 — Entity Collision

Cross-reference every entity the plan states it will CREATE against the
State Explorer registry. Flag any collision — an entity the plan marks as
new that already exists in the codebase with the same name or semantic role.
Also flag the inverse: an entity the plan states it will MODIFY that the
registry shows does not exist.

---

## RC4 — Modification Safety

For every entity the plan modifies, verify no downstream consumer (service,
event producer, API route) is broken by the planned change. Use
`get_change_impact` results from Step 3. Flag any consumer the plan does
not account for.

If Step 3 did not call `get_change_impact` for a modified entity, call
it now — this is the one sanctioned retrieval during roasting.

---

## RC5 — Event Flow Consistency

For every event in the plan's Event Contracts table, trace the full
produce → consume chain across all batches:
- (a) every consumer is in the same batch as the producer or a later batch
- (b) all payload fields the consumer states it needs are set by the producer
- (c) ordering assumptions are consistent — if event A must fire before
  event B according to the plan, verify no step fires B before A

Flag any broken chain.

---

## RC6 — Invariant Enforcement

For every invariant in the plan, the enforcement mechanism must be stated
or clearly inferable:
- database constraint (UNIQUE, CHECK, NOT NULL)
- application check (service-layer validation before commit)
- API validation (Pydantic validator on the request schema)
- architectural convention ("append-only by construction — no UPDATE path exists")

Flag any invariant whose enforcement mechanism is unspecified or unclear.

### Input Validation Enforcement Layer

For every input the plan's capabilities accept, the plan should state which
layer rejects invalid input. This classification determines what the test
architect must test and what it can safely skip:

| Enforcement Layer | What rejects invalid input | Test needed? |
|---|---|---|
| **Type system** (Pydantic validator, `Literal`, type hint, `Enum`, `@field_validator`) | Schema boundary, before service logic | No — unless it is a custom `@field_validator` (your logic, test it). One schema-level integration test confirms the schema exists. |
| **Database constraint** (NOT NULL, UNIQUE, CHECK, FK) | PostgreSQL, on commit | Integration only — one test per constraint confirms it fires, not one per invalid value. |
| **Application logic** (service-layer validation, business rule, conditional branch) | Your code, in the service | Yes — every branch, every boundary value, every error condition. |

Flag any input whose enforcement layer is unspecified. An input with no
stated enforcement layer is a GAP — the test architect cannot know
whether to write a test for it or skip it as framework-enforced.

---

## RC7 — ADR Re-Check

Re-apply Step 8 ADR criteria against all GAP findings from RC1–RC6. If any
GAP requires an architecture decision (new ownership boundary, event
contract change, invariant introduction), an ADR is now required that was
not previously identified. Flag which GAP triggers this and proceed to
Step 8 to write the ADR before finalizing the plan.

---

## Resolution

For each GAP found:

- **Minor gap** — missing clarification, missing example, missing
  enforcement mechanism where intent is clear from surrounding context
  → resolve inline: update the plan's Architecture Contracts, Invariants,
  or Implementation Steps to close the gap. Do not retrieve new
  architecture documents; the context is already in hand.
- **Significant gap** — missing ownership boundary, missing event contract,
  missing invariant where intent cannot be safely inferred → escalate to
  Architecture Gap Resolution (Step 10). Do not finalize the plan until
  all significant gaps are resolved or escalated.

---

## Output

After completing all 7 checks, produce a concise **Cross-Validation
Summary** table:

| Check | Result | Detail |
|-------|--------|--------|
| RC1 Contract Saturation | ✓ | All returned contracts accounted for or excluded |
| RC2 Vision Constraints | ✓ | N constraints mapped to Steps/Invariants/Test Reqs |
| RC3 Entity Collision | ✗ | `CalibrationCache` exists; plan says CREATE |
| RC4 Modification Safety | ✓ | N modified entities; no downstream consumers broken |
| RC5 Event Flow | ✓ | N events; all produce→consume chains consistent |
| RC6 Invariant Enforcement | ✗ | Invariant I-2 "append-only" has no enforcement mechanism stated |
| RC7 ADR Re-Check | ✗ | RC3 GAP requires ADR for `CalibrationCache` boundary |

If all checks pass with no GAPs → proceed to Step 6.
If GAPs exist → resolve Minor gaps inline before proceeding. Escalate
Significant gaps per Architecture Gap Resolution (Step 10).

---

## Test Scenario Grill

Before leaving Step 5, for every step with behavioural changes (not purely
structural like adding a field or renaming a column), draft at least one
concrete test scenario: a specific input and expected output.

### Grill Each Scenario

Ask for each scenario:
- Does the expected output actually match what the contract promises?
- If the input is on a boundary or edge case, does the contract say what
  should happen?
- Would a coder who passes this scenario have built what the plan
  intended — or would they have built something that technically passes
  the test but misses the intent?

Scenarios that expose contract gaps → Minor gap, resolve inline. Scenarios
that expose missing contracts → Significant gap, escalate.

### Computational Invariant Fixtures

Scenarios for computational invariants must use the fixtures pinned in
RC1 — same input, same expected output, same tolerance. Do not re-derive
approximations in the scenario; the RC1 fixture is the authoritative
expected value. If RC1 did not pin a fixture for a computational invariant
this scenario depends on, go back and fix RC1 first.

### Classify Enforcement and Mock Boundary

Classify each scenario's enforcement layer and its mocking boundary before
writing it into the `-tests.md` file:

| Field | Values | Purpose |
|---|---|---|
| **Enforcement** | `type-system` / `database` / `application-logic` | Tells the test architect whether to write a test for this scenario at all. `type-system` scenarios are skipped (framework-enforced). `database` scenarios get one integration test per constraint. `application-logic` scenarios get full branch coverage. |
| **Mock Boundary** | `none` / `external-only` / `db-session` | Tells the test architect what to mock. `none` — pure function, mock nothing. `external-only` — mock only out-of-process dependencies (HTTP, S3, LLM proxy), let all internal code run real. `db-session` — unit test, mock the DB session but let the service logic run real. |

### Mock Boundary Principle

**Mock at the external boundary, not the internal boundary.** Mock things
that leave the process (HTTP calls to external services, S3/MinIO, LLM
proxy). Do not mock things inside the process (services calling
repositories, models being persisted). The test should exercise the maximum
amount of production code; mocks exist to isolate the test from *external*
dependencies, not from *internal* ones.

### Draft Status

Draft scenarios are not written to disk yet — they're notes for Step 9
where they become the `-tests.md` companion file.

### Documentation Content Restriction

**Test scenarios must validate implementation behaviour, never documentation
content.** Do not draft scenarios that check whether a doc file exists,
whether a doc contains specific text, or whether documentation matches
expectations. Tests verify code behaviour against architecture contracts —
not prose against prose. If a scenario would only pass or fail based on
reading a markdown file, it is not a valid test scenario.
