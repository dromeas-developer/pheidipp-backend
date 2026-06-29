# Validation Report — Phase-1.3-P1
Date: 2026-06-24
Plan: docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md

## Result: PASS WITH MINORS

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | Persistence repositories created | ✅ | All 5 repositories created following established pattern |
| 2 | Onboarding domain errors created | ✅ | All 5 error classes in `onboarding_errors.py` |
| 3 | OnboardingService created | ✅ | Service with all required methods |
| 4 | Atomic onboarding transaction | ✅ | Single transaction with event outbox pattern |
| 5 | Request/response schemas created | ✅ | All schemas in `onboarding.py` |
| 6 | API router with 8 endpoints | ✅ | All endpoints registered with `require_self` |
| 7 | Export registrations | ✅ | All exports in `__init__.py` files |
| 8 | Test files | N/A | Skipped per coder handoff notes |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: onboarding single transaction | ✅ | | All entity creation in one AsyncSession, single commit |
| Invariant: event outbox pattern | ✅ | | `events.publish()` writes SystemEvent + SystemEventOutbox before commit |
| Invariant: TwinState append-only | ✅ | | TwinStateRepository has only `insert`, no `update`/`delete` |
| Invariant: goal type whitelist | ✅ | | Only `race_event`/`target_performance` accepted |
| Invariant: structural_risk_flag computed | ✅ | | Computed as `sport_background != RUNNING_PRIMARY` |
| Invariant: data tier inferred | ✅ | | Uses `infer_data_tier(hr_source, power_source)` |
| Invariant: threshold bootstrap formula | ✅ | | `max_hr = 220-age`, `lt1 = 0.75×max_hr`, `lt2 = 0.875×max_hr` |
| Invariant: fitness bootstrap zero | ✅ | | `aggregate = {fitness: 0, fatigue: 0, form: 0}` |
| Invariant: twin confidence = low | ✅ | | `confidence_level = 'low'`, `trigger = 'questionnaire'` |
| Event: onboarding_completed payload | ✅ | | Contains training_goal_id, twin_state_id, data_tier, confidence_level |
| Event: ordering after commit | ✅ | | Event written via outbox BEFORE commit, published AFTER by worker |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| `_ProfileInput.height_cm` | Optional height_cm in profile input | Acceptable | Implementation detail, within coder authority |
| Explicit rollback on IntegrityError | `await self.session.rollback()` before raising TrainingGoalConflictError | Acceptable | Defensive pattern, does not break atomicity guarantee |
| `OnboardingTrainingGoalIn` schema | Separate schema for training goal in onboarding | Acceptable | Matches plan's OnboardingRequest structure |

---

## Stack-Truth

### CRITICAL
- None

### MAJOR
- **IntegrityError rollback pattern**: `app/services/onboarding_service.py:374` — Explicit `await self.session.rollback()` called before raising `TrainingGoalConflictError`. While this does not break the atomicity guarantee (exception still propagates, no commit happens), it is redundant since SQLAlchemy auto-rollback on exception. This could confuse future maintainers about transaction ownership. The plan states "SQLAlchemy session rolls back on exception; callers re-raise" — the explicit rollback is not described.

### MINOR
- **`model_validate` usage**: `app/api/v1/onboarding.py:68` — Uses `TwinStateResponse.model_validate(twin)` correctly. However, the helper functions `_build_profile_response` and `_build_preferences_response` construct response objects manually rather than using `model_validate`. This is not incorrect, just inconsistent with the pattern used for twin response.
- **Missing internal type exports**: `app/services/__init__.py` does NOT export `_GoalInput`, `_PreferencesInput`, `_ProfileInput` (the typed input classes). The implemented-state snapshot flags this as "Missing Exports". These are internal implementation details (note the leading underscore), so this is acceptable, but the implemented-state flagged it.

---

## Validation Confidence

**Level: MEDIUM**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes |
| Implementation files retrieved | 16 of 16 listed in scope |
| Release alignment checked | yes |
| Deviation scan complete | yes |
| Dynamic context available | yes |

Confidence is MEDIUM (not HIGH) because:
1. The implemented-state file was available (HIGH priority context)
2. All scope files were successfully loaded
3. The IntegrityError rollback pattern warrants a MAJOR finding for architect acknowledgement
4. No test pack created yet (expected per user, but reduces verification confidence)

---

## Routing

| Finding | Route To |
|---------|----------|
| MAJOR (rollback pattern) | p-architect + this report — clarify if explicit rollback is intended or if auto-rollback on exception is preferred |
| MINOR (response construction) | p-coder + this report — consider using `model_validate` consistently for response construction |
| MINOR (missing exports) | p-coder + this report — documented in implemented-state; decide if internal types should be exported for testing |