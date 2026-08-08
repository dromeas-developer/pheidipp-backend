---
name: devops-analyzer-output-format
description: >
  Load this when s-test-analyzer has completed failure analysis and
  needs to produce the structured report. Contains the report template
  and category/confidence definitions. Loaded by s-test-analyzer only.
---

# DevOps Analyzer — Report Format

Save report using `write` as `reports/<plan-id>_devops.md`.

---

## Report Template

```markdown
# DevOps Report — <plan-id>
Date: <date>

## Result: PASS | FAIL

Tests: <n> total, <n> passed, <n> failed, <n> skipped

## Root Cause Analysis

### RC1 — <short title>
- **Category:** Implementation | Test Suite | Infrastructure | Specification / Plan Gap | Investigation Required
- **Owner:** p-coder-fix-mode | p-tester-fix-mode | p-devops | p-implementation-resolver | Unassigned
- **Confidence:** Confirmed | High | Medium | Low
- **Evidence:**
  - <specific observation, e.g. "14 failing assertions in test_foo.py">
  - <what you inspected, e.g. "inspected app/services/foo.py:bar()">
  - <what you found, e.g. "function returns X instead of Y">
  - <conclusion, e.g. "implementation bug — should return Y per contract">
- **Files:**
  - app: <source files to modify — p-coder-fix-mode scope; "none" if no app-code changes>
  - test: <test files to modify — p-tester-fix-mode scope; "none" if test is correct>
- **Affected failures:** <test names or count>
- **Suggested fix:** <when evidence converges on a fix direction; omit only when genuinely uncertain>

*(repeat as RC2, RC3, ... for every distinct root cause)*

## Routing Summary

| Owner | Root Causes | Failures |
|---|---|---|
| p-coder-fix-mode | RC1, RC2 | 4 |
| p-tester-fix-mode | RC3 | 8 |
| p-devops | — | — |
| p-implementation-resolver | — | — |
| Unassigned | — | — |
```

---

## Category Definitions

| Category | Definition | Owner |
|---|---|---|
| **Implementation** | Application code produces wrong behavior | p-coder-fix-mode |
| **Test Suite** | Test code is wrong (bad assertion, wrong fixture) | p-tester-fix-mode |
| **Infrastructure** | Framework, connection, environment, wiring | p-devops |
| **Specification / Plan Gap** | Plan or architecture docs incomplete/contradictory | p-implementation-resolver |
| **Investigation Required** | Cannot determine category with available evidence | Unassigned |

## Confidence Definitions

| Level | Definition |
|---|---|
| **Confirmed** | Evidence directly proves the root cause (traceback, constraint violation) |
| **High** | Strong circumstantial evidence, very likely correct |
| **Medium** | Probable cause but not certain, may need verification |
| **Low** | Educated guess, could be wrong |
