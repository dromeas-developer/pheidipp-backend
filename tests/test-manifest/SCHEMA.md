# Test Manifest Schema

## index.yaml — Cross-phase Registry

```yaml
version: "1.0"
last_reviewed_at: <ISO 8601>
selection:
  release:
    unit: []
    integration: []
    api: []
    behaviour: []
  regression:
    unit: []
    integration: []
    api: []
    behaviour: []
  smoke: []
```

### Ownership
- `selection.*` groups: DevOps only — populated via promotion from phase files
- `last_reviewed_at`: DevOps
- `version`: incremented by DevOps on schema changes

### Promotion Rules
- DevOps reads `phase-N-Mx.yaml` for feature runs
- When all functions in a file pass → status promoted, entries added to `selection.release`
- When release scope passes → `selection.release` → `selection.regression`, release cleared
- Test Architect never writes to `index.yaml` (bootstrap creation excepted)

---

## phase-N-Mx.yaml — Per-Sub-Phase File

```yaml
version: "1.0"
plan_id: <string>
sub_phase: <string>
generated_at: <ISO 8601>
last_reviewed_at: <ISO 8601>
prerequisites:
  migrations: <bool>
files:
  <relative_test_file_path>:
    type: unit | integration | api | behaviour
    status: pending | generated | promoted
    functions:
      <function_name>: { class: <ClassName>, implemented: true, executable: false, passed: false }   # class is optional — present for class-based tests only
      <function_name>: { implemented: true, executable: false, passed: false }                        # module-level test (no class)
      ...
  ...
coverage:
  events:
    covered:
      - <event_type>
  invariants:
    covered:
      - <invariant_id_or_description>
```

### Field Rules

**files — top-level key**
- Each key is a relative path to a test file (e.g., `tests/unit/test_auth_service.py`)
- `type`: one of `unit`, `integration`, `api`, `behaviour`
- `status`: lifecycle — `pending` (Test Architect) → `generated` (Test Architect) → `promoted` (DevOps)

**files.<file>.functions**
- Each key is a function name
- `class`: optional string — present only when the test function is defined inside a class (e.g., `class TestRefreshToken:`) and pytest needs the fully-qualified path
- `implemented`: set to `true` by Test Architect when the function body is written
- `executable`: set to `true` by DevOps when the function imports and collects successfully
- `passed`: set to `true` by DevOps when the function's assertions pass

**coverage**
- `events.covered`: list of event types this sub-phase tests (e.g., `athlete_registered`)
- `invariants.covered`: list of invariants this sub-phase tests

**prerequisites**
- `migrations`: `true` if alembic migrations must run before tests; `false` if `create_all` suffices

### Ownership
- **Test Architect owns:** file list, `type`, `status` (pending→generated), `functions.*.implemented`, `class`, `coverage`, `generated_at`, `prerequisites.migrations`
- **DevOps owns:** `functions.*.executable`, `functions.*.passed`, `status` (generated→promoted), `last_reviewed_at`
- **Immutable after sub-phase completion:** entire file

### Excluded Fields
The following fields do NOT exist in this schema:
- `description`, `protects`, `impacts`, `file_scope`, `plan`, `owned_by_plan`
- `execution_prerequisites` (per-feature)
- `history`
- `execution_groups`
