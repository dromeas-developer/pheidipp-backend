---
name: test-architect-fix
description: >
  Load this when a devops report routes Test Suite RCs (root causes) to be
  fixed — stale test assertions, enum drifts, index expectation mismatches,
  or other test-side drift from model/schema changes. NOT for initial test
  generation (use test-architect-generate for that).
argument-hint: "<devops-report-path>"
---

# Test Architect — Fix Mode

## Context

A devops report has surfaced Test Suite RCs — test assertions that no longer
match the current model/schema state. The report tells you what changed and
which tests are affected. This is targeted remediation, not new test generation.

## Procedure

1. **Read the devops report** — specifically `## Routing Summary` for RCs
   routed to `p-test-architect` (Category `Test Suite`), and each RC's
   `## Root Cause Analysis` entry.

2. **For each RC**, update the affected test files' assertions to match
   current model/schema state. Use `p-code-explorer` via `agent` if you
   need implementation-file context to confirm the current state:
   ```
   agent(subagent_type="p-code-explorer", description="Resolve current model/schema state for fix", prompt="Mode: Test Architect\n\nGroup: fix — <file_scope>\n\nCapabilities:\n- <one line about what to verify>\n\nCanonical Fixtures (from tests/MOCKING_CONTRACT.md):\n<paste the table>")
   ```

3. **Update the sub-phase manifest** — flip `passed: false` on corrected
   functions (leave `executable` as-is; DevOps re-verifies).

4. **Invoke `p-diagnostics-fixer`** on each modified file (one per agent call):
   ```
   agent(subagent_type="p-diagnostics-fixer", description="Fix diagnostics on <file>", prompt="plan_id: <plan-id>\n\nfiles:\n<path/to/file.py>")
   ```

5. **Self-check** — run collection on every touched file:
   ```
   bash scripts/pytest.sh --collect-only <path> [<path> ...]
   ```

6. **Infrastructure boundary check** — if a fix requires changing a fixture,
   mock, or `conftest.py`, STOP. Check if the devops report's
   `## Infrastructure Fixes` covers it; if not, flag it for the next cycle.

## Rules

- Do NOT generate new tests for unrelated capabilities
- Do NOT run the full generate protocol
- Do NOT modify production code
