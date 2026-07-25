# Type-Enforcement Conformance Audit — `app/`

**Scope:** Every module under `app/` (101 Python files)
**Mode:** Retrospective audit (no plan file)
**Date:** 2026-07-24
**Auditor:** p-implementation-validator
**Routing:** All findings → `p-coder`

---

## Summary

| Severity | Count |
|----------|-------|
| MAJOR    | 15    |
| MINOR    | 12    |
| **Total**| **27**|

---

## Layer 4: Type-Enforcement Conformance

### Check 1 — Visibility Correctness

| # | Item | Severity | Route | Finding |
|---|------|----------|-------|---------|
| V1 | `app/api/v1/coach.py` `get_coach_messages` | MAJOR | p-coder | Route handler imports `func`, `select` from `sqlalchemy` and `CoachingMessage` ORM model to build and execute a direct DB count query (`select(func.count()).where(CoachingMessage.athlete_id == ...)`). The repository already exposes `get_all_count()` — the handler should delegate to the repository instead of bypassing the service/repository layer. This is a layer-violation pattern (API constructing SQL), not strictly a visibility issue, but surfaces through the cross-module import of ORM model + SQLAlchemy internals into the API layer. |
| V2 | `app/api/v1/coach.py` `get_coach_messages` | MINOR | p-coder | `message_type` query parameter is typed `Optional[str]` and manually coerced to `MessageType` enum inside the handler body. The parameter should be typed `Optional[MessageType]` (or use a `Literal` union) so FastAPI handles enum coercion at the boundary. |

---

### Check 2 — Type Strictness

#### 2a — ORM Models: Raw `String`/`Text` columns that should be `SAEnum`

| # | Item | Severity | Route | Finding |
|---|------|----------|-------|---------|
| T1 | `app/models/regeneration_task.py` `RegenerationTask.status` | MAJOR | p-coder | Column is `Mapped[str] = mapped_column(Text)` with a CHECK constraint (`'pending_confirmation', 'confirmed', 'declined', 'expired'`). No `SAEnum` is used; no enum class exists in `app/models/enums.py`. Should define a `RegenerationTaskStatus` enum and use `SAEnum(RegenerationTaskStatus)`. |
| T2 | `app/models/regeneration_task.py` `RegenerationTask.trigger` | MAJOR | p-coder | Column is `Mapped[str] = mapped_column(Text)` with a CHECK constraint (`'trajectory_ahead', 'trajectory_at_risk', 'coach_conversation'`). No `SAEnum` is used; no enum class exists. Should define a `RegenerationTrigger` enum and use `SAEnum(RegenerationTrigger)`. |
| T3 | `app/models/checkpoint.py` `Checkpoint.trajectory_status` | MAJOR | p-coder | Column is `Mapped[str | None] = mapped_column(String(16))` with a CHECK constraint (`'ahead', 'on_track', 'behind', 'at_risk'`). No `SAEnum`; no enum class exists. Should define a `TrajectoryStatus` enum and use `SAEnum(TrajectoryStatus)`. |
| T4 | `app/models/planned_session.py` `PlannedSession.block_position` | MAJOR | p-coder | Column is `Mapped[str | None] = mapped_column(String(16))` with a CHECK constraint (`'first', 'middle', 'last'`). No `SAEnum`; no enum class exists. Should define a `BlockPosition` enum and use `SAEnum(BlockPosition)`. |
| T5 | `app/models/weekly_plan.py` `WeeklySession.block_position` | MAJOR | p-coder | Same pattern as T4 — `Mapped[str | None] = mapped_column(String(16))` with CHECK (`'first', 'middle', 'last'`). Should use the same `BlockPosition` enum as T4. |
| T6 | `app/models/weekly_plan.py` `WeeklySession.status` | MAJOR | p-coder | Column is `Mapped[str] = mapped_column(Text)` with CHECK (`'scheduled', 'completed', 'skipped', 'missed'`). No `SAEnum`; no enum class exists. The values partially overlap with `PlannedSessionStatus` but are not identical (different lifecycle). Should define a `WeeklySessionStatus` enum. |

#### 2b — Pydantic Schemas: `str` fields where architecture defines an Enum

| # | Item | Severity | Route | Finding |
|---|------|----------|-------|---------|
| T7 | `app/schemas/onboarding.py` `AthleteProfileResponse.sex` | MAJOR | p-coder | Field typed as `sex: str` but the ORM model uses `SAEnum(Sex)` and `app.models.enums.Sex` exists. Should use `sex: Sex` to enforce the closed set at the schema boundary. |
| T8 | `app/schemas/onboarding.py` `AthletePreferencesResponse.training_time_of_day` | MAJOR | p-coder | Field typed as `training_time_of_day: str` but `app.models.enums.TrainingTimeOfDay` exists with values `morning/afternoon/evening/variable`. Should use `training_time_of_day: TrainingTimeOfDay`. |

#### 2c — `Any` usage where concrete types are inferable

| # | Item | Severity | Route | Finding |
|---|------|----------|-------|---------|
| T9 | `app/services/physiology_update_service.py` `source_value(source: Any)` | MINOR | p-coder | Parameter typed `Any` but the function body checks `isinstance(source, MeasurementSource)` and falls back to `str(source)`. Should be `source: MeasurementSource | str`. |
| T10 | `app/services/physiology_update_service.py` `parse_iso_date(value: Any)` | MINOR | p-coder | Parameter typed `Any` but the function body checks `isinstance` for `date`, `datetime`, and `str`. Should be `value: str | date | datetime`. |
| T11 | `app/services/physiology_update_service.py` `coerce_observation_date(value: Any)` | MINOR | p-coder | Parameter typed `Any` but only accepts `datetime` or `date`. Should be `value: date | datetime`. |
| T12 | `app/schemas/onboarding.py` `OnboardingPreferencesIn.weekly_schedule` | MINOR | p-coder | Typed as `Dict[str, Any]` but the `@model_validator` validates each value as `WeeklyScheduleDayIn`. Could be `Dict[str, WeeklyScheduleDayIn]` (the `WeeklyScheduleIn` type alias is already defined in the file but unused on this field). |
| T13 | `app/schemas/onboarding.py` `AthletePreferencesResponse.weekly_schedule` | MINOR | p-coder | Typed as `Dict[str, WeeklyScheduleDayOut]` — this is actually correct and well-typed. (Flagging for completeness; no action needed.) |
| T14 | `app/schemas/onboarding.py` `AthletePreferencesPatchIn.weekly_schedule` | MINOR | p-coder | Typed as `Optional[Dict[str, Any]]` — the validator coerces to `WeeklyScheduleDayPatchIn` dicts. Could use `Optional[Dict[str, WeeklyScheduleDayPatchIn]]`. |
| T15 | `app/worker/app.py` all task functions | MINOR | p-coder | All 7 task functions (`fit_ingest`, `recalibrate_twin`, `signal_clean`, `threshold_detection`, `generate_plan`, `generate_first_message`, `outbox_publisher`) return `dict[str, Any]`. While procrastinate tasks serialize to JSON, the return dicts have known shapes that could be expressed as `TypedDict` or dataclass for internal type safety. |

#### 2d — Missing return type annotations on public functions

| # | Item | Severity | Route | Finding |
|---|------|----------|-------|---------|
| T16 | `app/api/v1/health.py` `live()` | MINOR | p-coder | Public endpoint function missing return type annotation. Should be `-> dict[str, str]` or a response schema. |
| T17 | `app/api/v1/health.py` `ready()` | MINOR | p-coder | Public endpoint function missing return type annotation. Should be `-> dict[str, str]` or a response schema. |
| T18 | `app/api/v1/activity.py` `_shared_prompt_registry()` | MINOR | p-coder | Private helper missing return type annotation. Should be `-> PromptRegistry`. |

---

### Check 3 — Enforcement Layer Placement

**Skipped** — no plan exists to provide RC6 enforcement-layer classifications.

---

### Check 4 — Custom Validator Presence

| # | Item | Severity | Route | Finding |
|---|------|----------|-------|---------|
| CV1 | `app/schemas/auth.py` `RegisterRequest.password` | MINOR | p-coder | No `@field_validator('password')` for minimum length or complexity at the schema boundary. If the service layer enforces this, the schema should still reject obviously invalid inputs (empty string, whitespace-only) before the service runs. `EmailStr` is used for email validation, establishing the pattern that input format checks belong in the schema. |
| CV2 | `app/schemas/onboarding.py` `OnboardingTrainingGoalIn.target_event_date` | MINOR | p-coder | No validator ensuring `target_event_date` is in the future when `goal_type == RACE_EVENT`. The `@model_validator` checks presence but not temporal validity. |
| CV3 | `app/schemas/onboarding.py` `OnboardingProfileIn.training_window` | MINOR | p-coder | Field is `Optional[Dict[str, Any]]` with no structural validator. If `training_window` has a known shape (start/end times), a `@model_validator` or nested schema would prevent malformed data from reaching the service. |

---

## Observations (No Action Required)

| # | Item | Note |
|---|------|------|
| O1 | `app/models/enums.py` | 38 enum classes defined — comprehensive coverage of domain ontologies. The gaps identified in T1–T6 are the only inline-union columns not yet promoted to `SAEnum`. |
| O2 | `app/schemas/onboarding.py` validators | Well-structured validators for timezone (`ZoneInfo`), weekly schedule keys, goal-type conditional fields, and immutable field rejection. Pattern should be replicated for the gaps in CV1–CV3. |
| O3 | `app/repositories/` | 14 of 22 repository files have fully annotated methods with no issues. The remaining 8 have methods where the AST parser shows only `self` as parameter — this appears to be an artifact of keyword-only parameters (`*`) not being surfaced by the structure explorer, not actual missing parameters. Verified by reading the source: `ActivityRepository.update_load_scores(self, *, activity_id, ...)` has proper parameters. |
| O4 | `app/services/` | Service layer is well-typed overall. The `Any` usage in T9–T11 is concentrated in `physiology_update_service.py` helper functions that bridge between JSONB dict shapes and typed Python — tightening these is straightforward. |
| O5 | `app/api/v1/coach.py` layer violation | The direct SQLAlchemy query in `get_coach_messages` is the only route handler in the codebase that constructs SQL. All other handlers delegate to repositories. The fix is to use `coaching_messages.get_all_count(athlete_id, message_type=mt)` which already exists. |

---

## Findings Index

| ID | Check | Severity | File | Symbol |
|----|-------|----------|------|--------|
| V1 | Visibility | MAJOR | `app/api/v1/coach.py` | `get_coach_messages` |
| V2 | Visibility | MINOR | `app/api/v1/coach.py` | `message_type` param |
| T1 | Type Strictness | MAJOR | `app/models/regeneration_task.py` | `RegenerationTask.status` |
| T2 | Type Strictness | MAJOR | `app/models/regeneration_task.py` | `RegenerationTask.trigger` |
| T3 | Type Strictness | MAJOR | `app/models/checkpoint.py` | `Checkpoint.trajectory_status` |
| T4 | Type Strictness | MAJOR | `app/models/planned_session.py` | `PlannedSession.block_position` |
| T5 | Type Strictness | MAJOR | `app/models/weekly_plan.py` | `WeeklySession.block_position` |
| T6 | Type Strictness | MAJOR | `app/models/weekly_plan.py` | `WeeklySession.status` |
| T7 | Type Strictness | MAJOR | `app/schemas/onboarding.py` | `AthleteProfileResponse.sex` |
| T8 | Type Strictness | MAJOR | `app/schemas/onboarding.py` | `AthletePreferencesResponse.training_time_of_day` |
| T9 | Type Strictness | MINOR | `app/services/physiology_update_service.py` | `source_value(source: Any)` |
| T10 | Type Strictness | MINOR | `app/services/physiology_update_service.py` | `parse_iso_date(value: Any)` |
| T11 | Type Strictness | MINOR | `app/services/physiology_update_service.py` | `coerce_observation_date(value: Any)` |
| T12 | Type Strictness | MINOR | `app/schemas/onboarding.py` | `OnboardingPreferencesIn.weekly_schedule` |
| T13 | Type Strictness | MINOR | `app/schemas/onboarding.py` | `AthletePreferencesResponse.weekly_schedule` |
| T14 | Type Strictness | MINOR | `app/schemas/onboarding.py` | `AthletePreferencesPatchIn.weekly_schedule` |
| T15 | Type Strictness | MINOR | `app/worker/app.py` | All task return types |
| T16 | Type Strictness | MINOR | `app/api/v1/health.py` | `live()` |
| T17 | Type Strictness | MINOR | `app/api/v1/health.py` | `ready()` |
| T18 | Type Strictness | MINOR | `app/api/v1/activity.py` | `_shared_prompt_registry()` |
| CV1 | Validator | MINOR | `app/schemas/auth.py` | `RegisterRequest.password` |
| CV2 | Validator | MINOR | `app/schemas/onboarding.py` | `OnboardingTrainingGoalIn.target_event_date` |
| CV3 | Validator | MINOR | `app/schemas/onboarding.py` | `OnboardingProfileIn.training_window` |
