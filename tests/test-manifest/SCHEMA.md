# Test Manifest Schema

The authoritative schema for the test manifest, split across `index.yaml`
(cross-phase) and one `phase-N-Mx.yaml` file per sub-phase. Phase files are
**immutable** — never edited after their sub-phase completes. Consumed by
`p-test-architect` (writes phase.yaml, reads phase files for context) and
`p-devops` (reads both, writes both — promotion is DevOps-owned).

---

## Manifest Structure

```
tests/test-manifest/
  index.yaml          # selection groups, cross-phase coverage
  phase-1-1.yaml      # per-sub-phase: files, validation state, sub-phase coverage
  phase-1-2a.yaml     # one file per sub-phase, immutable after completion
```

**Agents load only what they need:**
- DevOps (feature scope): reads `phase-N-Mx.yaml` only
- DevOps (regression/release/smoke): reads `index.yaml` only
- Test Architect: reads current `phase-N-Mx.yaml` + any prior phase files for context
- Implementation Architect: reads `index.yaml` only (for coverage gaps)

---

## Index Schema

```yaml
# tests/test-manifest/index.yaml
# Cross-phase registry. One thing lives here:
#   Resolved selection groups — pytest selectors (filename or filename::function)
version: "1.0"
last_reviewed_at: "<ISO 8601>"

selection:
  smoke:
    unit:         [<pytest selector>]   # critical path
    integration:  [<pytest selector>]
    behaviour:    [<pytest selector>]
    api:          [<pytest selector>]

  regression:
    unit:         [<pytest selector>]   # all promoted tests across all phases
    integration:  [<pytest selector>]
    behaviour:    [<pytest selector>]
    api:          [<pytest selector>]

  release:
    unit:         [<pytest selector>]   # current release phase — promoted, not yet gate-passed
    integration:  [<pytest selector>]
    behaviour:    [<pytest selector>]
    api:          [<pytest selector>]
```

### Pytest selector format

- **Whole file:** `test_auth_service.py` → DevOps expands to `tests/{type}/test_auth_service.py`
- **Module-level function:** `test_auth_service.py::test_register_atomic` → expands to `tests/integration/test_auth_service.py::test_register_atomic`
- **Class-based function:** `test_auth_service.py::ClassName::test_register_atomic` → expands to `tests/integration/test_auth_service.py::ClassName::test_register_atomic`
- A file that has all its known functions in one scope is listed as a whole file.
- A file split between scopes lists individual functions with `::`.
- When promotion collapses all functions into regression, the filename replaces the split entries.

### Class hierarchy

When a test function is defined inside a class, the phase file records the
class name in the function's `class` field. DevOps constructs the pytest
selector as `file.py::ClassName::function_name` when the `class` field is
present, and `file.py::function_name` when it is absent (module-level
functions). The `class` field is optional and backward-compatible —
existing entries without it continue to work as module-level functions.

### Selection group rules

- `smoke` — critical path only. Updated at release promotion when qualifying tests are identified.
- `regression` — all promoted tests across all phases. Grows at release promotion.
- `release` — current release phase's promoted tests. Grows at feature promotion, cleared at release promotion.

DevOps `feature` scope reads the phase file directly, not `index.yaml`.

---

## Sub-Phase File Schema

```yaml
# tests/test-manifest/phase-N-Mx.yaml
# Immutable after sub-phase completes. Per-file entries with per-function validation.
version: "1.0"
plan_id: "<plan-id>"
generated_at: "<ISO 8601>"
last_reviewed_at: "<ISO 8601>"

prerequisites:
  migrations: <bool>

files:
  <filename.py>:
    type: unit | integration | behaviour | api
    status: pending | generated | promoted
    functions:
      <test_function_name>: { class: <ClassName>, implemented: <bool> , executable: <bool> , passed: <bool> }

# Sub-phase coverage — merged into index.yaml at release promotion.
coverage:
  events:
    covered: ["<event>"]
  invariants:
    covered: ["<invariant>"]
```

### Status progression

- `pending` → Test Architect created the file entry, no functions generated yet
- `generated` → Test Architect wrote test functions, `implemented: true` per function
- `promoted` → DevOps: all functions passed, `passed: true` per function, added to `index.yaml` `selection.release`

### File immutability rule

**Old phase files are never edited.** They record the state at the time their sub-phase completed. If a later sub-phase adds functions to an existing test file, it creates a NEW entry for that file in its own phase.yaml. The two phase files may reference the same file but with different function lists.

---

## Manifest Ownership

| Operation | File | Owner |
|---|---|---|
| Create phase file (inventory, empty files list) | phase.yaml | Test Architect |
| Set `implemented: true` per function after generation | phase.yaml | Test Architect |
| Set `status: generated` per file after generation | phase.yaml | Test Architect |
| Write `coverage` section | phase.yaml | Test Architect |
| Set `executable: true/false` per function after execution | phase.yaml | DevOps |
| Set `passed: true/false` per function after execution | phase.yaml | DevOps |
| Set `status: promoted` when all functions passed | phase.yaml | DevOps |
| Add promoted entries to `index.yaml` `selection.release` | index.yaml | DevOps |
| Move `selection.release` → `selection.regression` on gate pass | index.yaml | DevOps |
| Read for gap analysis | phase.yaml | Implementation Architect |

No other agent modifies any manifest file for any reason.

---

## Promotion Flow

```
Phase sub-file creation:
  Test Architect → phase.yaml (files with empty functions list, status: pending)
  Test Architect → writes test files, sets implemented:true, status: generated

Feature run (per sub-phase):
  DevOps → reads phase.yaml
         → runs only functions with passed: false via path::function
         → sets executable:true, passed:true per function
         → if all functions in a file passed: sets status: promoted
         → adds file/functions to index.yaml selection.release

Release run (all sub-phases in current release):
  DevOps → reads index.yaml selection.release
         → runs full release suite
         → if all pass: moves selection.release → selection.regression
         → clears selection.release
```
