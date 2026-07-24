---
name: devops-report-format
description: >
  Load this at the Output Format step of the Full Pipeline Mode protocol
  when results are ready to be written. Contains the Full Pipeline Mode
  report format including the Checks table, Root Cause Analysis structure,
  Routing Summary, and Recommended Execution Order. Loaded by p-devops
  only in Full Pipeline Mode. For Test Pack Mode, load
  devops-testpack-report-format instead.
---

# DevOps — Full Pipeline Report Format

Save report using `write` as `reports/<plan-id>_devops.md`.

```markdown
# DevOps Report — <plan-id>
Date: <date>
Validator report: reports/<plan-id>_validation.md
Test execution group: <smoke|feature|regression|release>

## Implementation State
base_commit: <from git-session-delta skill>
current_commit: <from git-session-delta skill>
db_revision: <discovered in Step 4 via db-revision-test.sh "check">

## Result: PASS | FAIL

Tests: <n> passed / <n> failed / <n> skipped (omit if tests did not run
this session, e.g. a Step 1–4 failure stopped the run before Step 5)
Root causes identified: <n> (present only when Result = FAIL)

## Checks

| Check | Status | Notes |
|---|---|---|
| Idempotency (no prior PASS) | ✅ / ❌ / N/A | |
| Implementation state read | ✅ / ❌ | or "unavailable" |
| Validator pre-flight | ✅ / ❌ | |
| Test manifest present | ✅ / ❌ | |
| Services healthy | ✅ / ❌ | |
| Migration file present (coder-generated) | ✅ / ❌ | |
| Migration drift reviewed | ✅ / ❌ | removed tables, if any |
| TimescaleDB augmentation | ✅ / ❌ / N/A | not required for this plan |
| Test DB upgrade clean | ✅ / ❌ | |
| No pending model changes (test DB) | ✅ / ❌ | via db-revision-test.sh |
| Test suite | ✅ / ❌ | X passed, Y failed, Z skipped |
| Manifest updated (executable + passed) | ✅ / ❌ | written by DevOps in Step 5 |
| Prod DB upgrade clean | ✅ / ❌ | |
| Application build clean | ✅ / ❌ | |

## Test Execution

Execution group: <group>
Tests run: <list of paths from manifest>

## Infrastructure Fixes

*Only present if DevOps modified test infrastructure files in this session.*

| File | Change | Reason |
|---|---|---|
| tests/conftest.py | <description> | <error that triggered it> |

If empty: no infrastructure changes were made.

## Root Cause Analysis

*Present only when Result = FAIL. Every failure reason this session — test
failures, migration drift, a failed pending-changes check, a build
failure — is expressed as one or more RC entries below, even when there
is only one. Do not fall back to a single blanket description here.*

### RC1 — <short title>
- **Category:** Implementation | Test Suite | Infrastructure | Specification / Plan Gap | Investigation Required
- **Owner:** p-coder | p-test-architect | p-devops | p-implementation-architect | Unassigned
- **Confidence:** Confirmed | High | Medium | Low
- **Evidence:**
  - <specific observation, e.g. "14 failing assertions">
  - <what you inspected, e.g. "inspected physiology_update_service.py">
  - <what you found, e.g. "apply_observations() rereads ORM state every iteration">
  - <the conclusion it supports, e.g. "working_state overwritten instead of accumulated">
- **Files:**
  - app: <application source files to modify — p-coder scope; list "none" if no app-code changes are needed>
  - test: <test files to modify — p-test-architect scope; if the test files listed in Evidence are diagnostic only, state that explicitly>
- **Affected failures:** <test/check name(s) or numeric range — representative sample + total count if >5>
- **Suggested fix:** <strongly preferred. Include whenever the evidence
  converges on a fix direction, even if multi-line or conditional. Omit
  only when genuinely uncertain — not when the fix is merely "not a
  one-liner" or "might require architecture review." A suggested fix can
  be conditional: "if this is an app bug, add a type guard; if the test
  expectation is wrong, update the assertion to expect None." This is
  context to save the owner from repeating your investigation, not an
  instruction they must follow.>

*(repeat as RC2, RC3, ... for every distinct root cause)*

## Routing Summary

| Owner | Root Causes | Failures |
|---|---|---|
| p-coder | RC1, RC2 | 4 |
| p-test-architect | RC3 | 8 |
| p-devops | — | — |
| p-implementation-architect | — | — |
| Unassigned | — | — |

## Recommended Execution Order

*Only needed when there is more than one RC, or when one RC might mask or
produce misleading signal for another (e.g. an infra failure should
usually be resolved and re-verified before assessing whether remaining
assertion failures are real).*

1. <RC id and one-line reason for going first>
2. <RC id(s) that can proceed independently/in parallel>

## Full Failure Detail

*Group failure details under `### RC<N> — <title> (<count> failures)` headers.
Tag individual entries with `[RC#]` for cross-reference.*

### RC1 — <short title> (<count> failures)

### <test or check name> [RC1]
<captured output or error summary>

## Next Step *(PASS only)*
→ PASS: implementation complete — notify p-test-architect to review
  promotion (status: passing → promoted) and selection group membership

*(When Result = FAIL, routing lives in Routing Summary above — do not add
a single blanket "send to X" line here; different RCs may have different
owners.)*
```
