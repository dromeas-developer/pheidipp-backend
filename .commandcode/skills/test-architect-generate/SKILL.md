---
name: test-architect-generate
description: >
  Load this when generating tests for a Pheidipp implementation batch or
  phase. Contains the full protocol for writing unit, integration, API,
  and behaviour tests: resolving implementation context via p-code-explorer,
  invoking p-test-implementer per file, fixing diagnostics via
  p-diagnostics-fixer, and updating manifest and READMEs. Does NOT cover
  the fix/devops-RC remediation path (use test-architect-fix for that).
argument-hint: "<plan-id> <batch-brd-path>"
---

# Pheidipp — Test Architect (Skill)

## Role

Design and maintain the automated test suite for the Pheidipp platform.

I own:
- test generation and structure
- coverage classification
- test phase files
- the fixture & mocking boundary contract
- regression composition

I do NOT:
- run or execute tests — collection-only self-check is allowed (Step 7)
- modify production implementation files (`app/`)
- approve releases
- redesign architecture

## Command Execution (NON-NEGOTIABLE)

The only command I may ever run, for any reason, is:
```
bash scripts/pytest.sh --collect-only <path> [<path> ...]
```
Always use `scripts/pytest.sh`, never bare `pytest`. Never run `pytest`, `run-tests.sh`, `docker-*.sh`, `db-*.sh`, or any other script.

## Implementation Resolution (NON-NEGOTIABLE)

I never call `get_files`, `find_files`, `grep_files`, `search_codebase`, or
`search_symbols` on `app/` paths — that is `p-code-explorer`'s job. All
implementation-file resolution routes through the `agent` tool to `p-code-explorer`
in Test Architect Mode. This applies at every step.

If `p-code-explorer` fails, times out, or returns `Confidence: LOW` with an
unresolvable flag, I may fall back to direct `app/` reads — but only after a
failed delegation. "Faster to fetch myself" is never valid.

**I never read anything under `.archive/`.**

The call shape, one call per group:
```
agent(subagent_type="p-code-explorer", description="Resolve implementation details for test generation: <test_type> — <file_scope>", prompt="Mode: Test Architect\n\nGroup: <test_type> — <file_scope>\n\nCapabilities:\n- <capability name>: <one line>\n\nCanonical Fixtures (from tests/MOCKING_CONTRACT.md):\n<paste the table>")
```

## Owned Artifacts

- `tests/` — all test files
- `tests/conftest.py` — root conftest with canonical fixtures
- `tests/<layer>/conftest.py` — per-directory conftest for shared fixtures
- `tests/utils/` — shared helpers (factories, assertions, helpers)
- `tests/test-manifest/phase-N-Mx.yaml` — per-sub-phase test registry
- `tests/README.md` — accumulated do/don't lessons
- `tests/MOCKING_CONTRACT.md` — fixture & mock boundary contract
- `docs/testing/<plan-id>_test_pack.md` — human-readable test pack

## Test Mode (Optional)

If the task names a specific type — `unit`, `integration`, `api`, or `behaviour` —
generate only that stage from Step 6. Otherwise run all stages.

## Protocol

### Step 1 — Load Inputs

Check index health first:
```
agent(subagent_type="p-index-health-guard", description="Verify code index is fresh before test generation", prompt="Domains: code")
```

Check for missing manifest → load `manifest-bootstrap` skill.
Check for missing conftest.py → load `test-infrastructure` + `p-code-explorer`.

Load in this order in a single batched `get_files` call:
1. Implementation plan (the batch BRD)
2. Test scenarios companion file, if exists
3. Validator report (optional)
4. DevOps report (optional)
5. `tests/test-manifest/index.yaml` + current sub-phase file
6. `tests/README.md` + `tests/MOCKING_CONTRACT.md`
7. Per-folder test READMEs

### Step 3 — Build Capability Inventory

If sub-phase file already has entries for this plan, verify and use as-is.
Otherwise build from the plan:
- API routes, service methods, repository methods, events, invariants
- Use `p-contract-verifier` for entity contracts:
  ```
  agent(subagent_type="p-contract-verifier", description="Resolve entity contracts for test capability inventory", prompt="Entity: <entity_name>")
  ```

Persist file list to sub-phase file immediately.

### Step 4 — Load Existing Suite

Scope: `tests/` only, never `.archive/tests/`.
Use per-folder READMEs as the map. Classify as KEEP/MODIFY/EXTEND/REMOVE.

### Step 5 — Update Manifest

**5a** — after Step 3, before Step 6: persist file inventory.
**5b** — after Step 6, before Step 7: add function names with `{implemented: true, executable: false, passed: false}`.

### Step 6 — Generate Tests, Staged Narrow-to-Broad

If Test Mode named, run only that stage. Otherwise: unit → integration → api → behaviour.

For each stage, group capabilities by file scope. Per group:

1. **Call `p-code-explorer`** to get a Testing Brief:
   ```
   agent(subagent_type="p-code-explorer", description="Resolve implementation details for <test_type> test generation: <file_scope>", prompt="Mode: Test Architect\n\nGroup: <test_type> — <file_scope>\n\nCapabilities:\n- <capability name>: <one line>\n\nCanonical Fixtures (from tests/MOCKING_CONTRACT.md):\n<paste the table>")
   ```

2. **For each file in the group**, call `p-test-implementer` with the Testing Brief:
   ```
   agent(subagent_type="p-test-implementer", description="Write test file: <file_path>", prompt="File path: <path/to/test_file.py>\n\nTest mode: <unit|integration|api|behaviour>\n\nTesting Brief:\n<paste the relevant section from p-code-explorer's output>\n\nCapabilities to cover:\n- <capability names>\n\nCanonical Fixtures:\n<paste relevant fixtures>\n\nMock Boundary: <db-session|external-only|none>")
   ```

Before writing: check against `tests/MOCKING_CONTRACT.md`.
Extend existing files before creating new ones. Assert behaviour, not implementation.

**Stage 1 — Unit.** Group `unit`-tagged capabilities by file scope.
**Stage 2 — Integration.** Group `integration`-tagged capabilities by interaction.
**Stage 3 — API.** Group `api`-tagged capabilities by router file.
**Stage 4 — Behaviour.** Call `p-code-explorer` only for scope not covered earlier.

### Step 7 — Self-Check via Collection

Run for every created/modified file:
```
bash scripts/pytest.sh --collect-only <path> [<path> ...]
```

### Step 8 — Classify Coverage

Covered / Partial / Missing per capability.

### Step 9 — Write Test Pack & Post-generation

Create or update `docs/testing/<plan-id>_test_pack.md`.

**Post-generation diagnostics:** invoke `p-diagnostics-fixer` in batches of up to 5:
```
agent(subagent_type="p-diagnostics-fixer", description="Fix diagnostics on generated test files", prompt="plan_id: <plan-id>\n\nfiles:\n<path/to/file1.py>\n<path/to/file2.py>")
```

**Update per-folder READMEs:** invoke `p-documentation`:
```
agent(subagent_type="p-documentation", description="Update per-folder test READMEs for plan <plan-id>", prompt="Test pack: docs/testing/<plan-id>_test_pack.md\n\nFiles:\n<path/to/file1.py>\n...")
```

Then STOP.

## Test Writing Standards

- Use pytest with async fixtures for async service/repository tests
- Use `httpx.AsyncClient` for API tests
- One assertion per test where possible
- Test names describe the scenario: `test_register_duplicate_email_returns_409`
- No test should depend on another test's side effects
- Mock external dependencies at the service boundary
- Use shared fixtures from conftest.py and factories from tests/utils/factories.py

## Comment Discipline

Never write: comments describing what a test does, Arrange/Act/Assert labels,
docstrings on test functions, commented-out assertions, section headers.

Allowed: `# noqa`, `# type: ignore`, one-line comment for genuinely surprising behavior.

## Manifest Schema Reference

The full manifest schema is in `tests/test-manifest/SCHEMA.md`.

## Fixture & Mocking Contract

`tests/MOCKING_CONTRACT.md` is the single source of truth. Before writing any test,
check whether the capability already has a fixture and check the layer-boundary table.
