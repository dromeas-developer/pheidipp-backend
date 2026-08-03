---
name: validation-classification-and-report
description: >
  Load this at Step 7 of the implementation validation protocol when
  all findings have been gathered and need classification and routing.
  Contains the severity definitions, Resolution Path procedure,
  illustrative examples, and the Validation Report output format.
  Also used by p-devops when producing validation-aligned reports.
---

# Validation — Classification & Report Format

## Severity Classification

Classify every finding into one of four severities before routing.

### CRITICAL — architecture broken

- Architecture invariant violated
- Wrong ownership boundary
- Layer skipping or reversal
- Missing required file
- Event produced with wrong payload or wrong ordering
- Silent deviation that constitutes an architectural decision

### MAJOR — behaviour deviates

- Transaction not atomic where plan requires it
- Event ordering assumption violated
- Endpoint contract mismatch (wrong status code, wrong response shape)
- Incomplete event payload
- Plan gap (contract missing from the plan that should be there)
- Async rule violated

### MINOR — implementation hygiene

Always routes to `p-coder-fix-mode` directly — no Resolution Path assessment needed.

- Missing `__init__.py` export
- Missing type hint
- Wrong Pydantic method
- `native_enum` missing
- `exclude_unset` missing on PATCH
- Naming inconsistency with plan

### DEVIATION — unauthorized scope

Requires architect acknowledgement; may or may not need ADR. Always routes
to `p-implementation-resolver` — see Step 5 (Deviation Detection) in the
validator prompt. This is a judgement about whether unauthorized scope
should be accepted, not a code-defect question, so the Resolution Path
test below does not apply to Layer 3 findings.

## Resolution Path

Required for every CRITICAL and MAJOR finding. Do not apply to DEVIATION
or Layer 3 findings — those always route to `p-implementation-resolver`.

Use the canonical test defined in the `no-silent-deviations` skill.
That skill is the single source of truth for the implementation/architecture
boundary. Apply its six-bullet test:

- **No to all six** → `Resolution Path: Implementation Fix`, routes to `p-coder-fix-mode`.
- **Yes to any** → `Resolution Path: Architecture Change Required`, routes to `p-implementation-resolver`.

If you are not confident which side of the test a finding falls on, route
it to `p-implementation-resolver`. An unnecessary architect review costs
less than asking `p-coder-fix-mode` to make an architecture decision it is
separately instructed to refuse.

**Root cause taxonomy reference:** For the full root cause category
definitions, owner mapping, and confidence levels used by `p-devops`
(which this validator's routing aligns with), see
`docs/architecture/04-platform/root-cause-taxonomy.md`.

## Illustrative Examples

| Finding | Severity | Resolution Path | Route |
|---|---|---|---|
| A required file from the plan's CREATE scope was never created | CRITICAL | Implementation Fix — coder has not finished this step; only reclassify if you have specific evidence the omission was deliberate (see Layer 3) | p-coder-fix-mode |
| A stated invariant ("hashed_password never returned") is violated because the field is present in a response | CRITICAL | Implementation Fix | p-coder-fix-mode |
| An endpoint returns 404 where the plan explicitly states 403 | CRITICAL | Implementation Fix | p-coder-fix-mode |
| Business logic sits in the API layer; the plan already names the service that should own it | CRITICAL | Implementation Fix — relocate the code | p-coder-fix-mode |
| Business logic sits in a service, and the plan does not clearly say which service should own it | CRITICAL | Architecture Change Required | p-implementation-resolver |
| An event contract in the plan lists 5 required payload fields; the code sets 3 | MAJOR | Implementation Fix | p-coder-fix-mode |
| The plan requires atomicity for an operation the code splits across two transactions | MAJOR | Implementation Fix | p-coder-fix-mode |
| The plan has no invariant at all for a behaviour the code needs to satisfy | MAJOR (Plan Gap) | Architecture Change Required | p-implementation-resolver |
| A deviation adds a new persistence entity outside the plan's scope | DEVIATION | not applicable — Layer 3 always routes to p-implementation-resolver | p-implementation-resolver |

---

## Validation Report Format

Save report using `write` as `reports/<plan-id>_validation.md`.

```markdown
# Validation Report — <Plan ID>
Date: <date>
Plan: docs/implementation/<path-to-plan>.md

## Result: PASS | PASS WITH MINORS | FAIL | FAIL WITH DEVIATIONS

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Route | Finding |
|------|-------------|----------|-------|---------|
| 1 | Persistence models created | ✅ | | |
| 5 | Registration atomicity | MAJOR | p-coder-fix-mode | Event emitted before transaction commit in register() |
| 8 | require_self 403 vs 404 | CRITICAL | p-coder-fix-mode | Returns 404 on athlete mismatch |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Route | Finding |
|----------|-------|----------|-------|---------|
| Invariant: hashed_password never returned | ✅ | | | |
| Invariant: refresh rotation atomic | MAJOR | p-coder-fix-mode | auth_service.py: insert and revoke in separate transactions |
| Event: athlete_registered after commit | ✅ | | | |
| Event: athlete_logged_in token_type field | MINOR | p-coder-fix-mode | Field present but typed as str not Literal |
| PLAN GAP: no invariant for ip_address anonymisation | MAJOR | p-implementation-resolver | Plan omits this invariant from athlete-auth.md |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Route | Action |
|------|---------------|----------------|-------|--------|
| app/models/event_log.py | New EventLog persistence model | DEVIATION | p-implementation-resolver | Architect review — new entity outside plan scope |
| requirements.txt: bcrypt | Dependency added | Acceptable | — | Routine, no action needed |

---

## Stack-Truth

### CRITICAL
- <finding>: <file> — <description> — Route: p-coder-fix-mode | p-implementation-resolver

### MAJOR
- <finding>: <file> — <description> — Route: p-coder-fix-mode | p-implementation-resolver

### MINOR
- <finding>: <file> — <description> — Route: p-coder-fix-mode

---

## Validation Confidence

**Level: HIGH | MEDIUM | LOW**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes / no |
| Implementation files retrieved | X of Y listed in scope |
| Release alignment checked | yes / no |
| Deviation scan complete | yes / no |
| Dynamic context available | yes / no |

Confidence is LOW if contracts are missing from the plan or fewer than half
the scope files were retrievable. Confidence is MEDIUM if dynamic context
was unavailable but all scope files loaded. Confidence is HIGH when all
dimensions are yes.

---

## Routing Summary

*Every finding with an action attached to it appears exactly once below,
grouped by owner. A report can — and often will — route some findings to
`p-coder-fix-mode` and others to `p-implementation-resolver` in the same run; that is expected,
not a sign of an inconsistent report.*

| Owner | Findings |
|---|---|
| p-coder-fix-mode | Layer 1 Step 5, Layer 1 Step 8, Layer 2 (refresh rotation atomic), Layer 2 (token_type field), Stack-Truth MINOR (…) |
| p-implementation-resolver | Layer 2 (PLAN GAP: ip_address anonymisation), Layer 3 (event_log.py) |
| p-devops | — |

## Routing — How To Read The Summary Above

| Finding | Route To |
|---------|----------|
| CRITICAL / MAJOR — Resolution Path: Implementation Fix | p-coder-fix-mode + this report |
| CRITICAL / MAJOR — Resolution Path: Architecture Change Required | p-implementation-resolver + this report |
| MAJOR (plan gap) | p-implementation-resolver + this report — plan needs updating; always Architecture Change Required, see Step 7 |
| DEVIATION / Layer 3 CRITICAL | p-implementation-resolver + this report — architect acknowledges or requests ADR |
| MINOR (hygiene) | p-coder-fix-mode + this report |
| Migration incomplete | p-devops + this report |
| No findings | p-devops |
```

Confirm the report was saved, then STOP.
