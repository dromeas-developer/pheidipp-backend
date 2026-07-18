# Test Manifest Schema

The authoritative schema for the test manifest, split across `index.yaml`
(cross-phase) and one `phase-N-Mx.yaml` file per sub-phase. Consumed by
`p-test-architect` (writes) and `p-devops` (reads). Both agents reference
this file instead of carrying the schema inline.

---

## Manifest Structure

```
tests/test-manifest/
  index.yaml          # selection groups, cross-phase coverage, history summary
  phase-1-1.yaml      # all features and tests for Phase 1.1
  phase-1-2a.yaml     # all features and tests for Phase 1.2a
  phase-1-2b.yaml     # etc — one file per sub-phase
```

**Agents load only what they need:**
- DevOps: reads `index.yaml` (for selection scope) + the current sub-phase file
- Test Architect: reads `index.yaml` + the current sub-phase file; reads other
  sub-phase files only when cross-phase impact analysis requires it
- Implementation Architect: reads `index.yaml` only (for coverage gaps)

**One file per sub-phase.** When a new sub-phase begins, the Test Architect
creates a new `phase-N-Mx.yaml` file. It never modifies a prior sub-phase
file except to update `validation` fields when DevOps reports results for
previously deferred tests.

---

## Index Schema

```yaml
# tests/test-manifest/index.yaml
# Lean cross-phase registry. Only two things live here:
#   1. Resolved selection groups (paths only)
#   2. Cross-phase coverage summary
#   3. Cross-phase execution group dependencies
# History, features, execution groups, and per-sub-phase coverage
# live in the individual sub-phase files.
version: "1.0"
last_reviewed_at: "<ISO 8601>"

# Resolved selection groups — paths only, no feature metadata.
# Rebuilt by Test Architect when any sub-phase file changes promotion state.
selection:
  smoke:
    - "<test file path>"
  feature:
    - "<test file path>"     # current sub-phase only
  regression:
    - "<test file path>"     # all promoted tests across all sub-phases
  release:
    - "<test file path>"     # all status=promoted tests

# Cross-phase coverage summary — updated when features are promoted.
coverage:
  routes:
    covered: ["<route>"]
    partial: ["<route>"]
    missing: ["<route>"]
  events:
    covered: ["<event>"]
    partial: ["<event>"]
    missing: ["<event>"]
  invariants:
    covered: ["<invariant>"]
    partial: ["<invariant>"]
    missing: ["<invariant>"]

# Cross-phase execution group dependencies.
# Intra-phase ordering lives in the sub-phase files.
cross_phase_dependencies:
  <group-id>:
    depends_on_cross_phase:
      - "<group-id>"
```

---

## Sub-Phase File Schema

```yaml
# tests/test-manifest/phase-N-Mx.yaml
version: "1.0"
plan_id: "<plan-id>"
generated_at: "<ISO 8601>"
last_reviewed_at: "<ISO 8601>"

features:
  <feature-id>:
    status: pending           # pending | generated | executable | passing | promoted | deprecated
    # "pending" means Step 3 has identified and tagged this capability but
    # no Test Mode session has generated its test yet. This is the state
    # every capability starts in — it lets a later single-mode session
    # (e.g. "integration" run in a separate session from "unit") find
    # exactly what it still owes without re-deriving the inventory.
    test_type: unit           # unit | integration | api | behaviour — set by Step 3
    file_scope:               # exact paths from the plan's Scope section — set by Step 3
      - "<file path>"
    plan: "<plan file path>"
    owned_by_plan:
      - "<plan-id>"
    description: "<one line>"
    protects:
      - "<invariant description>"
    impacts:
      - "<feature-id>"       # may reference features in other sub-phase files
    execution_prerequisites:
      migrations: true
      seed_data: false
      external_services: []
    validation:
      implemented: false     # set by Test Architect when this feature's test is generated
      executable: false      # set by DevOps after execution
      passed: false          # set by DevOps after execution
    tests:
      unit:
        - path: "tests/unit/test_x.py"
          owner: "<plan-id>"
      integration:
        - path: "tests/integration/test_x.py"
          owner: "<plan-id>"
      api:
        - path: "tests/api/test_x.py"
          owner: "<plan-id>"
      behaviour:
        - path: "tests/behaviour/test_x.py"
          owner: "<plan-id>"
      release:
        - path: "tests/release/test_x.py"
          owner: "<plan-id>"

# Execution groups for this sub-phase only.
# Cross-phase depends_on edges live in index.yaml cross_phase_dependencies.
execution_groups:
  <group-name>:
    scope: smoke | feature | regression | release
    phase: <n>
    tests:
      - "<test file path>"
    depends_on:
      - "<group-name>"       # intra-phase only

# Coverage for this sub-phase only — index.yaml holds the cross-phase view.
coverage:
  routes:
    covered: ["<route>"]
    partial: ["<route>"]
    missing: ["<route>"]
  events:
    covered: ["<event>"]
    partial: ["<event>"]
    missing: ["<event>"]
  invariants:
    covered: ["<invariant>"]
    partial: ["<invariant>"]
    missing: ["<invariant>"]

# Full audit history for this sub-phase.
# Every Test Architect or DevOps change gets an entry here.
# The index.yaml has no history block — this is the only history record.
history:
  - date: "<YYYY-MM-DD>"
    plan: "<plan-id>"
    tests_added: <n>
    tests_modified: <n>
    tests_removed: <n>
    result: "PASS | FAIL | PARTIAL"
    coverage_delta: >
      <prose description of what changed and why>
```

---

## Manifest Ownership Rules

The manifest is split-owned between the Test Architect and DevOps.
The division follows who has direct evidence for each field.

| Field | File | Owner | Rationale |
|---|---|---|---|
| `validation.implemented` | sub-phase | Test Architect | Only the Test Architect knows whether a test file was generated and exists on disk |
| `validation.executable` | sub-phase | DevOps | Only DevOps has run the suite and knows whether tests ran without errors |
| `validation.passed` | sub-phase | DevOps | Only DevOps has the actual pass/fail result |
| `status` progression | sub-phase | Test Architect | Promotion decisions are judgment calls, not transcription |
| `test_type` / `file_scope` | sub-phase | Test Architect | Set once by Step 3, read by every later Test Mode session on this plan instead of being re-derived |
| `history` | sub-phase | Test Architect | Full audit trail for this sub-phase — lives where the detail lives |
| `selection` groups | index | Test Architect | Which tests belong in smoke/regression/release is a design decision |
| `coverage` (cross-phase) | index | Test Architect | Updated when features are promoted |
| `cross_phase_dependencies` | index | Test Architect | Cross-phase execution group ordering |
| All other sub-phase fields | sub-phase | Test Architect | Features, protects, impacts, prerequisites |

**What this means in practice:**

When the Test Architect generates tests, it creates the sub-phase file, sets
`validation.implemented = true`, leaves `validation.executable` and
`validation.passed` as `false`, and updates `index.yaml`'s `selection.feature`
with the new test paths.

When DevOps runs the suite, it reads `index.yaml` for scope, reads the
current sub-phase file for prerequisites and feature list, then updates
`validation.executable` and `validation.passed` directly in the sub-phase
file within the same session.

When DevOps encounters infrastructure failures (import errors, greenlet
errors, fixture errors, connection errors), it may fix `tests/conftest.py`,
`pytest.ini`, `tests/payloads.py`, and `tests/*/__init__.py` directly. It
records every change in its report under `## Infrastructure Fixes`. The
Test Architect processes this report as Step 2 of its next cycle.

DevOps never modifies `test_*.py` assertion files. If a test fails with an
assertion error after infrastructure is fixed, hand back to the Test Architect.

When DevOps reports a full PASS, the Test Architect advances `status` to
`promoted` in the sub-phase file, rebuilds `index.yaml`'s `selection.regression`
and `selection.release` to include newly promoted tests, updates `index.yaml`'s
`coverage`, and appends a `history` entry to the sub-phase file describing
what changed and why.

No other agent modifies any manifest file for any reason.

---

## Selection Group Rules

* `smoke` and `feature` groups: include all tests where `validation.implemented = true`
* `regression` group: include only tests where `validation.passed = true`
  (set by DevOps after successful execution)
* `release` group: include only tests where `status = promoted`
  (advanced by Test Architect after reviewing DevOps report)

Never add a test to `regression` or `release` groups until it has passed.
`validation.executable` and `validation.passed` are set by DevOps within
the same session that executes the tests — the Test Architect does not
update them and does not wait for a report before generating tests.
