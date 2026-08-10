---
name: test-execution-protocol
description: >
  Loaded by p-test-runner, p-coder-fix-mode, p-tester-fix-mode, and
  p-infra-fixer at session start. Contains the shared s-test-executor
  delegation protocol: sequential execution, scoped selectors, iteration
  cap, bash prohibition, and Juice interpretation. Agent-specific task
  templates, sequencing examples, and services-check preconditions
  remain inline in each agent's own prompt.
---

## s-test-executor Delegation Protocol

All agents that delegate test execution to `s-test-executor` follow
these rules. Task templates (with agent-specific label formats) and
sequencing examples stay inline in each agent's prompt.

### 1. Sequential Execution (NON-NEGOTIABLE)

Issue ONE `s-test-executor` `task` call at a time. Wait for it to
return PASS or FAIL before issuing the next call. NEVER place two or
more `s-test-executor` calls in the same assistant message.

Parallel runs against the same `test_pheidipp` database cause
`asyncpg.exceptions.TooManyConnectionsError` (connection pool
exhaustion) and cross-test interference (transactions, locks) that
do not exist in single-pack runs.

This overrides the AGENTS.md batching discipline for s-test-executor
calls specifically — test packs are NOT independent even when they
target different selectors.

### 2. Scoped Selectors Only

Delegate scoped re-runs to `s-test-executor` with ONLY the selectors
from the report's `Affected failures` list — not the full test suite.
This gives a tight verify loop without running the entire pack.

### 3. Iteration Cap

If 2 fix iterations fail for the same item (RC or finding), STOP and
report. Do not loop indefinitely.

### 4. Never Run Tests via Bash

Do NOT run `bash scripts/run-tests.sh` directly. All test execution
goes through `s-test-executor` via `task`. Running tests via bash
gives raw pytest output (potentially 125k+ tokens) instead of the
compact Juice that `s-test-executor` extracts.

### 5. Juice Interpretation

`s-test-executor` returns:

- `PASS` + counts → the fix landed. Move to the next item or declare
  completion.
- `FAIL` + Juice → the fix didn't work or introduced a new failure.
  The Juice is verbatim `FAILED`/`ERROR` lines, each with pytest's
  `- <reason>` suffix (the exception class+message). You know what
  you just changed — matching the failure to your edit is trivial.
  Iterate: adjust the fix and re-invoke `s-test-executor` with the
  same selectors.