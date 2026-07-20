> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-3, verified against the current codebase on 2026-07-19.

## Batch Objective

Deliver the complete onboarding flow and its supporting read/write endpoints in a single coherent plan. The `POST /athletes/{id}/onboarding` endpoint executes one atomic database transaction that creates or updates six domain entities, flips the onboarding gate, and emits `onboarding_completed` via the transactional outbox. The plan also delivers the lightweight GET/PATCH endpoints for profile, preferences, twin state, and twin history that rely on the repositories built for onboarding. Together these form the first surface that writes real domain state; all prior sub-phases established schema only.

## Preconditions

- Athlete exists with authenticated credential (from phase-1-1 auth)
- AthleteProfile exists (created during `POST /auth/register` in phase-1-1)
- All six tables exist at head revision: `athletes`, `athlete_profiles`, `athlete_preferences`, `training_goals`, `athlete_physiology`, `athlete_fitness`, `twin_states`
- `athletes.onboarding_complete` boolean column exists
- No Alembic migration is needed — all schema is already in place

## Scope

- New repositories: `AthletePreferencesRepository`, `TrainingGoalRepository`, `AthletePhysiologyRepository`, `AthleteFitnessRepository`, `TwinStateRepository`
- New service: `OnboardingService` — hosts atomic onboarding transaction, read endpoints for status/profile/preferences/twin/twin-history, PATCH helpers for profile and preferences
- New domain-error module: `app/services/onboarding_errors.py`
- New request/response schemas: onboarding, profile, preferences, twin state, twin history
- New API router with 8 endpoints:
  - `POST /athletes/{id}/onboarding`
  - `GET /athletes/{id}/onboarding`
  - `GET /athletes/{id}/profile`
  - `PATCH /athletes/{id}/profile`
  - `GET /athletes/{id}/preferences`
  - `PATCH /athletes/{id}/preferences`
  - `GET /athletes/{id}/twin`
  - `GET /athletes/{id}/twin/history`
- Router and export registrations in all `__init__.py` files

## Out Of Scope

- `fitness_improvement`, `maintenance`, `recovery` goal types — rejected at onboarding
- `Objective` seeding
- Menstrual cycle tracking
- `WeeklyPlan` creation (plan generation — phase 1-4)
- First coach message generation (phase 1-5a)
- Any change to existing models, migrations, or schema
- Any LLM call or external HTTP call — bootstrap is pure Python
- Publication of `onboarding_completed` to message bus (publisher worker handles that)

## Steps

1. [OWNER: Coder] Create repositories: `AthletePreferencesRepository` (`get_by_athlete_id`, `add`), `TrainingGoalRepository` (`get_active`, `get_by_id`, `add`), `AthletePhysiologyRepository` (`get_by_athlete_id`, `add`), `AthleteFitnessRepository` (`get_by_athlete_id`, `add`), `TwinStateRepository` (`insert`, `get_latest`, `get_history` — append-only, no update/delete). All follow existing pattern (`AsyncSession`, flush, no commit). Register in `app/repositories/__init__.py`.

2. [OWNER: Coder] Create `app/services/onboarding_errors.py` with domain error classes: `OnboardingAlreadyCompleteError` (409), `AthleteNotFoundError` (404), `OnboardingIncompleteError` (409), `TrainingGoalConflictError` (409), `InvalidGoalTypeError` (422).

3. [OWNER: Coder] Create `OnboardingService` in `app/services/onboarding_service.py`. Constructor takes `AsyncSession`, constructs all new repos plus existing `AthleteRepository`, `AthleteProfileRepository`, `EventPublisher`. Methods:
   - `complete_onboarding(athlete_id, prefs, goal, profile)` — the atomic transaction (see Step 4)
   - `get_onboarding_status(athlete_id)` — returns completion status
   - `get_profile(athlete_id)` / `update_profile(athlete_id, patch)` — read/PATCH profile (mutable subset only)
   - `get_preferences(athlete_id)` / `update_preferences(athlete_id, patch)` — read/PATCH preferences (weekly_schedule merges at day level)
   - `get_twin_state(athlete_id)` / `get_twin_history(athlete_id, limit)` — thin wrappers

4. [OWNER: Coder] Implement `complete_onboarding` as a single atomic sequence:
   - Reject if `onboarding_complete == true` → 409
   - Validate goal type ∈ `{race_event, target_performance}` → 422 if not
   - Validate timezone is valid IANA identifier → 422 if not
   - Update `AthleteProfile`: set `timezone`, `training_window` (if supplied), `structural_risk_flag = (sport_background != running_primary)`
   - Create `AthletePreferences`
   - Infer `data_tier` from `hr_source` + `power_source`
   - Create `TrainingGoal` (status = `active`; 409 on one-active-goal conflict)
   - Create `AthletePhysiology` bootstrap: `max_hr = 220 - age`, `lt1.hr = 0.75 * max_hr`, `lt2.hr = 0.875 * max_hr`, all with `measurement_source = questionnaire_estimate`, `prior_weight = 0.5`; power/pace/cp/vo2max all null
   - Create `AthleteFitness` bootstrap: `aggregate = {fitness: 0.0, fatigue: 0.0, form: 0.0}`, dimensional blocks null, population time constants (aerobic 42/7, neuromuscular 21/3, structural 56/14)
   - Create `TwinState` (append-only INSERT): `trigger = questionnaire`, `confidence_level = low`, `model_version = v1-questionnaire-bootstrap`, inline snapshot values, `metric_confidence = {lt1_hr: low, lt2_hr: low; others null}`, `readiness_level = green`, `activity_id = null`
   - Set `athlete.onboarding_complete = true`
   - Publish `onboarding_completed` via outbox in same transaction
   - Commit
   - On caught DB exception: `await session.rollback()` before re-raising (ADR-006)
   - `PlanGenerationService` optionally injected — when present, plan generation runs after onboarding commit

5. [OWNER: Coder] Create request/response schemas in `app/schemas/onboarding.py`: `OnboardingRequest` (profile, preferences, goal sub-schemas), `OnboardingResponse`, `OnboardingStatusResponse`, `AthleteProfilePatchIn` (mutable subset only), `AthleteProfileResponse`, `AthletePreferencesPatchIn` (weekly_schedule merges at day level), `AthletePreferencesResponse`, `TwinStateResponse`, `TwinStateHistoryResponse`, `WeeklyScheduleIn`/`Out`. Register in `app/schemas/__init__.py`.

6. [OWNER: Coder] Create `app/api/v1/onboarding.py` with 8 endpoints, all behind `require_self`. Each endpoint delegates to `OnboardingService`, translates domain errors to `HTTPException`. Status codes: 201 on POST success, 409 on already-onboarded or goal conflict, 422 on invalid input, 404 on missing resources (preferences/twin before onboarding), 403 on cross-athlete access.

7. [OWNER: Coder] Wire everything: add `build_onboarding_service()` dependency, register `onboarding_router` in `app/api/v1/__init__.py`, export all new classes from repository/service/schema `__init__.py` files. Ensure `PlanGenerationService` is optionally injected into `OnboardingService` for plan generation integration.

## Context Needed

- `01-entities/athlete.md` — `onboarding_complete` gate
- `01-entities/athlete-profile.md` — profile fields, immutable vs mutable
- `01-entities/athlete-preferences.md` — preference fields, weekly_schedule structure
- `01-entities/training-goal.md` — goal types, active goal invariant
- `01-entities/athlete-physiology.md` — bootstrap posterior states
- `01-entities/athlete-fitness.md` — zero fitness/fatigue, population time constants
- `01-entities/twin-state.md` — first append, trigger, confidence level
- `00-foundations/data-tiers.md` — data tier inference
- `00-foundations/confidence-model.md` — bootstrap confidence = `low`
- `04-platform/events.md` — `onboarding_completed` event contract
- `docs/adr/006-explicit-rollback-after-caught-db-exception.md` — rollback before re-raise pattern

## Batch Success Criteria

- Submitting complete onboarding request with `race_event` goal creates exactly one `TrainingGoal` (status=`active`), one `AthletePhysiology`, one `AthleteFitness`, one `TwinState`, one `AthletePreferences`, and flips `onboarding_complete` to `true` in one transaction
- `onboarding_completed` `SystemEvent` + `SystemEventOutbox` rows exist with correct payload in same transaction
- Mid-transaction failure (e.g. corrupt JSONB) rolls back: no entity rows exist, `onboarding_complete` still `false`, no event row exists
- Calling `POST /athletes/{id}/onboarding` twice returns 409; no new rows, no new outbox
- `GET /athletes/{id}/twin` returns `confidence_level=low`, `trigger=questionnaire`, `fitness=0`, `fatigue=0`, `form=0`, non-null `lt1_hr_bpm`/`lt2_hr_bpm` from age-graded formula, `readiness_level=green`
- Data tier matches `infer_data_tier(hr_source, power_source)` for all combinations
- Goal types outside `{race_event, target_performance}` return 422; `target_performance` without required fields returns 422; `race_event` without required fields returns 422
- Second active goal for same athlete raises `TrainingGoalConflictError` → 409
- PATCHing immutable profile fields (`date_of_birth`, `sex`, `timezone`) returns 422, values unchanged
- PATCHing mutable profile fields (`height_cm`, `location_lat`, `location_lng`, `training_window`) updates correctly
- PATCHing `weekly_schedule` with partial day input merges at day level (e.g. `{saturday: {available: false}}` flips only Saturday)
- GET endpoints for preferences/twin/twin-history return 404 before onboarding; return populated records after
- All endpoints return 403 (never 404) on JWT/path athlete_id mismatch
- DB exception caught and translated → `await session.rollback()` called before re-raising (ADR-006)

## Files Expected To Change

- `app/repositories/athlete_preferences_repository.py` — new
- `app/repositories/training_goal_repository.py` — new
- `app/repositories/athlete_physiology_repository.py` — new
- `app/repositories/athlete_fitness_repository.py` — new
- `app/repositories/twin_state_repository.py` — new
- `app/repositories/__init__.py` — register new repos
- `app/services/onboarding_errors.py` — new error classes
- `app/services/onboarding_service.py` — new service
- `app/services/__init__.py` — register service + errors
- `app/schemas/onboarding.py` — new request/response schemas
- `app/schemas/__init__.py` — register schemas
- `app/api/v1/onboarding.py` — new routes
- `app/api/v1/__init__.py` — register `onboarding_router`
- `app/api/deps.py` — add `build_onboarding_service`

## Coder Notes

- **No migration.** All six tables already exist at head. Do not create a new Alembic revision.
- **AthleteProfile is an update, not a create.** The profile row was created during `POST /auth/register`. Onboarding enriches it. Never `add()` a second profile.
- **Transaction pattern.** Same `AsyncSession` for every repository call. Commit exactly once at the end. On caught DB exception: `await session.rollback()` before re-raising (ADR-006 — not redundant, required).
- **Event persistence.** Use `EventPublisher.publish(...)` inside the transaction. Writes `SystemEvent` + `SystemEventOutbox` in same session. Publication to message bus is out of scope.
- **structural_risk_flag.** Compute server-side: `sport_background != running_primary`. Never trust client input.
- **Data tier.** Reuse `infer_data_tier` from `app.models.athlete_preferences`. Persist `.value` (integer) on `TwinState.data_tier`.
- **Physiology bootstrap shapes.** JSONB nested shape: `{value, uncertainty, prior_weight, dominant_source, last_observation_date}`. `dominant_source = questionnaire_estimate` for bootstrap rows. `cp` and `vo2max` are `null` (never estimated from questionnaire).
- **Fitness bootstrap.** Aggregate-only: `{fitness: 0.0, fatigue: 0.0, form: 0.0}`. Dimensional blocks `null`. Time constants `source = population_default`.
- **TwinState append-only.** `TwinStateRepository` exposes only `insert`, `get_latest`, `get_history`, `get_by_activity`. No `update()` / `delete()`.
- **Metric confidence bootstrap.** Only `lt1_hr` and `lt2_hr` populated, both `low`. All other keys explicitly `null`.
- **activity_id = null on bootstrap.** The `questionnaire` trigger has no triggering activity. Partial unique index on `(athlete_id, activity_id) WHERE activity_id IS NOT NULL` allows any number of non-activity-triggered TwinStates.
- **Timezone validation.** Use `zoneinfo.ZoneInfo` for IANA validation. Reject invalid with 422 before writing. Timezone is immutable on AthleteProfile after creation.
- **Goal-type whitelist.** Only `race_event` and `target_performance` permitted at onboarding. Others rejected with `InvalidGoalTypeError` → 422.
- **require_self on every endpoint.** All 8 endpoints require `require_self`. 403 (never 404) on mismatch.
- **PATCH idempotency.** Re-applying same patch yields same state and response. `weekly_schedule` merges at day level.
- **PlanGenerationService integration.** Injected as optional dependency (default `None`). When present, `generate_plan` called after onboarding commit. When `None`, plan generation skipped (test backward compatibility).
