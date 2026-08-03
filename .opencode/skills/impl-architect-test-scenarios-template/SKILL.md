---
name: impl-architect-test-scenarios-template
description: >
  Load this when writing the test scenarios file (batch-N-<theme>-tests.md)
  alongside a batch BRD in Step 9 of the Implementation Planning Process.
  Contains the template and writing rules. Loaded by p-implementation-architect.
---

# Test Scenarios Template

Write to `docs/implementation/phase-N/phase-N-M/batch-N-<theme>-tests.md`.

This file is loaded by the test architect, never by the coder. Each
scenario gives the test architect a concrete input/output pair to
generate assertions from. Omit this file entirely if the batch has no
behavioural changes worth a dedicated test scenario (purely structural
changes like adding a field or renaming a column do not need scenarios —
the test architect derives those from contracts).

## Template

```markdown
# Test Scenarios — Phase N.M — Batch N: <theme>

## Step <number> — <step description>

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | <scenario name> | <concrete input> | <concrete expected output> | type-system / database / application-logic | none / external-only / db-session |
| 2 | <scenario name> | <concrete input> | <concrete expected output> | type-system / database / application-logic | none / external-only / db-session |

...
```

## Rules

- One table per step that has behavioural changes. Multiple steps can
  share a table if they form a single workflow — label the step as
  "Steps N–M" in the header.
- Input/Expected must be concrete enough to turn into assertions. "Returns
  a valid X" is not concrete; "Returns `X(id=1, status='active')`" is.
- **Enforcement column** — which layer rejects invalid input for this
  scenario. `type-system` scenarios are skipped by the test architect
  (framework-enforced, not your logic). `database` scenarios get one
  integration test per constraint. `application-logic` scenarios get
  full branch coverage. See the architect's RC6 table for the full
  classification.
- **Mock Boundary column** — what the test architect should mock for this
  scenario. `none` — pure function, mock nothing. `external-only` — mock
  only out-of-process dependencies (HTTP, S3, LLM proxy), let all
  internal code run real. `db-session` — unit test, mock the DB session
  but let the service logic run real. The principle: mock at the
  external boundary, not the internal boundary.
- Include edge cases: missing data, boundary values, error conditions.
  A coder who passes every scenario has built what the plan intended.
- Scenarios are derived from the step's own prose, the Architecture
  Contracts, and the Invariants — they do not introduce new requirements.
  If you discover a requirement while writing scenarios that the step
  doesn't state, the step is incomplete — fix the step first.
- Scenarios for computational invariants must use the exact fixtures
  pinned in RC1 — same input, same expected output, same tolerance.
- Omit this file for batches with no behavioural changes. The test
  architect handles those from contracts alone.