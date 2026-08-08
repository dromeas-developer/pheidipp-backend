# Test Manifest Schema

## index.yaml — Cross-phase Registry

```yaml
version: "1.0"
selection:
  release:
    unit:
      - tests/unit/test_foo.py::TestB
    integration: []
    api: []
    behaviour: []
  regression:
    unit:
      - path: tests/unit/test_foo.py
        exclude: [TestB]
    integration:
      - tests/integration/test_bar.py
    api: []
    behaviour: []
  smoke: []
```

### Selector Format

Three selector forms:

- `filename.py` — run ALL functions in this file (file only in one section)
- `filename.py::ClassName` — run ALL functions in this class (release side of partial promotion)
- `{ path: filename.py, exclude: [ClassName, ...] }` — run ALL functions EXCEPT listed classes (regression side of partial promotion)

**Rule:** When a file appears in BOTH `selection.release` and `selection.regression`:
- Release side: use `filename.py::ClassName` for each new class
- Regression side: use `{ path: filename.py, exclude: [<new classes>] }` — keeps file-level coverage minus the promoted classes

When all classes for a file are eventually in regression, collapse to `filename.py` (no exclude needed).

### Ownership
- `selection.*` groups: DevOps only — populated via promotion from phase files
- `version`: incremented by DevOps on schema changes

### Promotion Rules
- DevOps reads `phase-N-Mx.yaml` for feature runs
- When all tests in a file pass → status promoted, selectors added to `selection.release`
- When release scope passes → `selection.release` → `selection.regression`, release cleared
- Collapse: if ALL classes in a file are in `selection.regression`, collapse to `filename.py`
- Test Architect never writes to `index.yaml` (bootstrap creation excepted)

### Excluded Fields
The following fields do NOT exist in this schema:
- `last_reviewed_at`

---

## phase-N-Mx.yaml — Per-Sub-Phase File

```yaml
version: "1.0"
plan_id: <string>
sub_phase: <string>
files:
  <relative_test_file_path>:
    type: unit | integration | api | behaviour
    status: pending | generated | promoted
    classes:
      <ClassName>: [<function_name>, ...]
    module_level: [<function_name>, ...]
```

### Field Rules

**files — top-level key**
- Each key is a relative path to a test file (e.g., `tests/unit/test_auth_service.py`)
- `type`: one of `unit`, `integration`, `api`, `behaviour`
- `status`: lifecycle — `pending` (Test Architect) → `generated` (Test Architect) → `promoted` (DevOps)

**files.<file>.classes**
- Each key is a class name (e.g., `TestRefreshToken`)
- Value is a list of function names in that class

**files.<file>.module_level**
- List of function names not inside a class
- Omit if empty

### Ownership
- **Test Architect owns:** file list, `type`, `status` (pending→generated), `classes`, `module_level`
- **DevOps owns:** `status` (generated→promoted), execution results (pass/fail counts per file)
- **Immutable after sub-phase completion:** entire file

### Excluded Fields
The following fields do NOT exist in this schema:
- `generated_at`, `last_reviewed_at`, `prerequisites`, `coverage`
- `implemented`, `executable`, `passed` per function (replaced by file-level status in index.yaml)
- `class` per function (replaced by nesting under `classes:`)
- `description`, `protects`, `impacts`, `file_scope`, `plan`, `owned_by_plan`
- `execution_prerequisites` (per-feature)
- `history`
- `execution_groups`
