---
name: consistency-report-format
description: >
  Load this at Step 6 of the consistency validation protocol when all
  findings have been gathered and need classification and routing.
  Contains the four disposition definitions (CRITICAL/MAJOR/CODER/OBSERVATION),
  routing rules, and the Consistency Validation Report output format.
  Loaded by p-consistency-validator only.
---

# Consistency Validation — Classification & Report Format

## Disposition Classification

Classify every finding into one of four dispositions before routing.

### CRITICAL — divergence that constitutes a runtime risk or will corrupt system behaviour

Requires architect review before the next sub-phase begins:
- Event name mismatch between producer and consumer
- Ownership boundary violated in a way that bypasses invariant enforcement
- Duplicate logic that has already diverged (the copies differ)
- Transaction boundary inconsistency that risks data integrity

### MAJOR — divergence that will cause maintenance problems or obscures correctness

Requires architect acknowledgement; architect decides whether to schedule
remediation or accept as-is:
- Pattern inconsistency within the same category of component (e.g. all
  but one service fires events after commit)
- Naming drift for the same concept across the codebase
- Accumulated service responsibilities clearly outside ownership boundary
- Duplicate logic that is currently identical but will diverge (3+ copies)

### CODER — findings with a clear, self-contained fix that does not require an
architectural decision

Routes directly to p-coder-fix-mode; no architect review needed:
- Rename a method or field to match the established name across the codebase
  (the correct name is already obvious from the majority pattern)
- Extract an identical utility that appears 3+ times and has an unambiguous
  home (e.g. a pagination helper that belongs in `app/core/utils/`)
- Fix an inconsistent error response where the correct behaviour is already
  established by the majority of parallel implementations
- Add a missing `TYPE_CHECKING` guard that is already used correctly elsewhere

### OBSERVATION — noted for awareness but no action required

Does not route anywhere; documented in the report for completeness:
- A large file that is cohesive and does not need splitting
- A pattern variation that appears intentional or inconsequential
- An import structure that is unusual but currently safe
- A borderline responsibility accumulation where the case for change is
  not clear-cut

---

## Consistency Validation Report Format

Save the report as `docs/implementation/consistency-<scope>.md` where
`<scope>` is the phase or subphase range (e.g. `phase-1` or
`phase-1-1-through-1-2b`).

```markdown
# Consistency Validation Report — <scope>
Date: <date>

## Result: PASS | PASS WITH CODER FIXES | FINDINGS REQUIRING ARCHITECT REVIEW

---

## Summary

| Category | CRITICAL | MAJOR | CODER | OBSERVATION |
|----------|----------|-------|-------|-------------|
| Cross-Implementation Inconsistency | N | N | N | N |
| Technical Debt | N | N | N | N |
| **Total** | **N** | **N** | **N** | **N** |

---

## Category 1 — Cross-Implementation Inconsistency

### Naming Drift

| Finding | Disposition | Locations | Description |
|---------|-------------|-----------|-------------|
| `superseded_at` vs `deprecated_at` | MAJOR | `app/models/twin_state.py`, `app/models/plan.py` | Same soft-delete semantic, different field names — correct name not obvious from context; architect to decide canonical name |
| `get_by_athlete` vs `find_by_athlete_id` | CODER | `app/repositories/activity_repo.py`, `app/repositories/wellness_repo.py` | Identical operation; `get_by_athlete` is used in 4 of 5 repositories; rename the outlier |

*If none found: No naming drift detected.*

### Ownership Blur

| Finding | Disposition | Location | Description |
|---------|-------------|----------|-------------|
| Query construction in route | CRITICAL | `app/api/v1/activities.py:L142` | Direct session query bypasses repository layer |

*If none found: No ownership boundary violations detected.*

### Pattern Inconsistency

| Pattern | Consistent Locations | Inconsistent Location | Disposition | Description |
|---------|---------------------|-----------------------|-------------|-------------|
| Event firing after commit | athlete_service.py, activity_service.py (4 of 5) | twin_service.py | MAJOR | Event fired before commit in twin_service — runtime risk if transaction rolls back; architect to confirm whether intentional |

*If none found: No pattern inconsistencies detected.*

### Duplicate Logic

| Logic | Locations | Disposition | Description |
|-------|-----------|-------------|-------------|
| Load score normalisation | `app/services/load.py:L88`, `app/services/analysis.py:L210` | MAJOR | Same formula, independently implemented, currently identical — will diverge; architect to decide extraction boundary |
| Offset/limit pagination | `app/services/activity_service.py`, `app/services/wellness_service.py`, `app/services/plan_service.py` | CODER | Three identical copies; unambiguous home in `app/core/utils/pagination.py`; no architectural decision required |

*If none found: No duplicate logic detected.*

### Inconsistent Error Handling

| Condition | Consistent Approach | Inconsistent Location | Disposition | Description |
|-----------|--------------------|-----------------------|-------------|-------------|
| Missing entity | `EntityNotFoundError` raised (4 of 5 services) | `app/services/wellness.py` returns `None` | CODER | Correct behaviour established by majority; wellness service is the outlier; raise `EntityNotFoundError` to match |

*If none found: No error handling inconsistencies detected.*

---

## Category 2 — Technical Debt

### Oversized Files

| File | Approximate Lines | Disposition | Description |
|------|------------------|-------------|-------------|
| `app/services/twin_service.py` | ~620 | MAJOR | Owns threshold detection, fitness update, TwinState assembly, and event production — four responsibilities each with independent change reasons; boundary decision requires architect |
| `app/models/athlete.py` | ~480 | OBSERVATION | Large but cohesive — all fields relate to a single entity; no split warranted |

*If none found: No oversized files with separable concerns detected.*

### Accumulated Service Responsibilities

| Service | Core Boundary | Accumulated Capability | Disposition | Description |
|---------|--------------|------------------------|-------------|-------------|
| `app/services/activity_service.py` | Activity ingestion | Calibration eligibility computation | MAJOR | Eligibility logic is a distinct capability with its own rules; belongs in a calibration service per architecture — architect to decide boundary |

*If none found: No accumulated responsibility drift detected.*

### Extractable Shared Logic

*Duplicate logic findings with a clear extraction path are reported under
Category 1 — Duplicate Logic above. This section covers structural patterns
only.*

| Pattern | Locations | Disposition | Description |
|---------|-----------|-------------|-------------|
| Async session fixture wiring | `tests/conftest.py` (correctly centralised) | OBSERVATION | Already extracted; no action needed |

*If none found: No additional extractable shared logic identified.*

### Import Tangles

| Finding | Disposition | Description |
|---------|-------------|-------------|
| `twin_service` ↔ `physiology_service` | OBSERVATION | Mutual import via `TYPE_CHECKING` on both sides — currently safe; flag if either side adds a runtime import of the other |

*If none found: No import tangles detected.*

---

## Observations

Findings that were considered but do not warrant action. Documented here
so the next consistency validation knows they were reviewed.

| Item | Reason Not Flagged |
|------|--------------------|
| `app/models/athlete.py` ~480 lines | Cohesive; all fields belong to the same entity |
| `twin_service` ↔ `physiology_service` import | Safely managed via TYPE_CHECKING; no runtime risk |

---

## Validation Confidence

**Level: HIGH | MEDIUM | LOW**

| Dimension | Status |
|-----------|--------|
| All scope files structurally surveyed (Step 2) | X of Y |
| Verification Queue drained (Step 5) | X of Y items resolved |
| Naming drift scan complete | yes / partial |
| Ownership scan complete | yes / partial |
| Pattern consistency scan complete | yes / partial |
| Duplicate logic scan complete | yes / partial |
| Technical debt scan complete | yes / partial |

Confidence is LOW if fewer than half the scope files were surveyable.
Confidence is MEDIUM if all scope files were surveyed but some patterns
had sparse matches. Confidence is HIGH when all dimensions are
yes/complete — note that "all scope files surveyed" does not mean all
were loaded in full; it means every file was covered by the Step 2
structural pass, and every item that entered the Verification Queue in
Steps 3-4 was resolved in Step 5.

---

## Routing

| Disposition | Count | Route |
|-------------|-------|-------|
| CRITICAL | N | → p-implementation-resolver immediately; block next sub-phase until resolved |
| MAJOR | N | → p-implementation-resolver to decide: remediation plan, absorb into upcoming sub-phase, or accept with ADR |
| CODER | N | → p-coder-fix-mode directly with this report; no architect review needed |
| OBSERVATION | N | No action; documented above |
```
