# Implementation Plan: Phase 1 Consistency Cleanup — Repository Boundary Restoration
## Plan ID: phase-1-cleanup-P1

## Sub-Phase Reference
Derived from `docs/implementation/consistency-phase-1.md` (Phase 1, Sub-Phases 1-1 through 1-4).
No formal sub-phase ID exists for a cross-phase consistency remediation; this plan is scoped to the actionable findings in the report.

## Objective
Resolve known cross-implementation inconsistencies and restore the repository-layer ownership boundary that was bypassed in read-only route handlers, without introducing new architecture or altering existing behavioural contracts. This plan addresses the three CODER findings and one MAJOR finding from the consistency report; the second MAJOR finding (OnboardingService responsibility extraction) is deferred.

## Scope
- Extract duplicated PostgreSQL unique-violation detection (`23505`) into a single shared utility under `app/db/integrity_utils.py` and update both original call sites.
- Fix the bare `"active"` string literal in `TrainingPlanRepository.get_active_for_athlete` to `TrainingGoalStatus.ACTIVE`.
- Add full type annotations to `WeeklySessionRepository.add_many`.
- Introduce `PlannedSessionRepository` with read methods for the active plan and refactor `app/api/v1/plan.py` to delegate all query construction to repositories (`PlannedSessionRepository` and `CheckpointRepository`).
- Register the new repository in `app/repositories/__init__.py`.
- Update unit and integration tests that reference the removed module-level `TrainingGoalRepository_unique_violation` helper.

## Out Of Scope
- Refactoring profile/preferences/twin read endpoints out of `OnboardingService` into a separate service (deferred; the service's Phase 1 responsibilities remain coherent, and extraction is unnecessary before Phase 2 scope).
- Any database migrations (no schema changes are required).
- Fixing unrelated `Missing Exports` in `app/api/__init__.py` or `app/schemas/__init__.py` that were not flagged by the consistency report.

## Architecture Contracts
- `docs/architecture/01-entities/planned-session.md` — IMPLEMENTS (repository read surface for PlannedSession)
- `docs/architecture/01-entities/athlete.md` — DEPENDS ON (repository pattern for `AthleteRepository` and shared integrity helpers)
- `docs/architecture/01-entities/training-plan.md` — MODIFIES (must use enum constant for `TrainingGoalStatus` comparison)
- `docs/architecture/00-foundations/storage-topology.md` — DEPENDS ON (denormalised `PlannedSession.training_plan_id` invariant: queries must join through `WeeklyPlan.training_plan_id`)
- `docs/adr/006-explicit-rollback-after-caught-db-exception.md` — DEPENDS ON (integrity-error detection used inside explicit rollback paths)

## Invariants
- **Repository layer owns query construction.** The API layer may not build SQLAlchemy `select()` statements with `join()` and `where()`. Reads must be provided by repository methods.
- **Never filter `PlannedSession` directly by `training_plan_id`.** The denormalised FK can be stale after supersession. All current-plan queries must join through `WeeklyPlan.training_plan_id` per `storage-topology.md`.
- **Service layer owns commit boundaries.** Flushes happen in repositories, commits happen once at the end of the service method. Events are published (flushed) before the commit.
- **TwinState is append-only.** Not directly touched by this plan, but must not be violated by any shared utility or repository changes.
- **`fit_file_key` is a hard prerequisite.** Not directly touched by this plan, but must not be violated.

## Implementation Steps

1. [OWNER: Coder] Create `app/db/integrity_utils.py` with a single `is_unique_violation(error: IntegrityError) -> bool` function that detects PostgreSQL `23505` by reading `error.orig.pgcode`.

2. [OWNER: Coder] Refactor `AthleteRepository.is_unique_violation` to delegate to the new shared utility. Preserve the existing method signature so `AuthService` does not need to change. The method body becomes a one-line call to the utility.

3. [OWNER: Coder] In `app/services/onboarding_service.py`, replace the module-level `TrainingGoalRepository_unique_violation` function with an import of the shared utility. Update `OnboardingService.complete_onboarding` to call `is_unique_violation` from `app.db.integrity_utils` and remove the now-duplicate module-level helper and its docstring.

4. [OWNER: Coder] In `app/repositories/training_plan_repository.py`, replace the bare string comparison `TrainingGoal.status == "active"` in `get_active_for_athlete` with `TrainingGoal.status == TrainingGoalStatus.ACTIVE`. Ensure the enum is imported.

5. [OWNER: Coder] In `app/repositories/weekly_plan_repository.py`, annotate `WeeklySessionRepository.add_many(self, sessions: List[WeeklySession]) -> List[WeeklySession]`. Ensure `WeeklySession` is imported for type-checking (use `TYPE_CHECKING` guard if needed to avoid runtime cycles).

6. [OWNER: Coder] Create `app/repositories/planned_session_repository.py` containing:
   - `PlannedSessionRepository.__init__(self, session: AsyncSession)`
   - `get_for_training_plan(self, training_plan_id: uuid.UUID) -> List[PlannedSession]` — joins through `WeeklyPlan.training_plan_id`, orders by `PlannedSession.target_date ASC, PlannedSession.session_slot ASC`.
   - `get_upcoming_for_training_plan(self, training_plan_id: uuid.UUID, from_date: date, limit: int = 5) -> List[PlannedSession]` — same join, adds `PlannedSession.target_date >= from_date`, applies `limit`, same ordering.
   Both methods must not query `PlannedSession.training_plan_id` directly.

7. [OWNER: Coder] Refactor `app/api/v1/plan.py`:
   - Add `PlannedSessionRepository` and `CheckpointRepository` dependency factories (similar to `build_plan_repository`).
   - Replace inline `select(PlannedSession) ...` in `get_plan_sessions` with `await planned_sessions.get_for_training_plan(plan_id)`.
   - Replace inline `select(PlannedSession) ...` in `get_upcoming_sessions` with `await planned_sessions.get_upcoming_for_training_plan(plan_id, from_date=today)`.
   - Replace inline `select(Checkpoint) ...` in `get_plan_checkpoints` with `await checkpoints.get_for_training_plan(plan_id)`.
   - Remove unused `select`, `PlannedSession`, `WeeklyPlan`, and `Checkpoint` imports from the route module (retain only what is still needed for dependency construction and response mapping).

8. [OWNER: Coder] Register `PlannedSessionRepository` in `app/repositories/__init__.py`. Verify `app/repositories/__init__.py` exports `PlannedSessionRepository` after registration.

9. [OWNER: Test Architect] Update test files affected by the refactor:
   - In `tests/unit/test_onboarding_service.py`, remove or repurpose `TestIntegrityErrorDetection` to test `app.db.integrity_utils.is_unique_violation` instead of the deleted `TrainingGoalRepository_unique_violation`. Verify all assertions remain valid.
   - Verify `tests/integration/test_athlete_repositories.py` still passes (behaviour unchanged via delegation).
   - Verify route-level tests (`tests/api/test_plan_endpoints.py`, `tests/behaviour/test_plan_user_journey.py`) continue to pass with identical JSON output after moving queries to repositories.

## Event Contracts
No events are produced or consumed by this plan. The changes are purely structural refactors with no behavioural impact on event publication or consumption.

## Pseudocode
### Before (inline route query — to be removed)
```
result = await session.execute(
    select(PlannedSession)
    .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
    .where(WeeklyPlan.training_plan_id == plan_id)
    .order_by(PlannedSession.target_date.asc(), PlannedSession.session_slot.asc())
)
rows = list(result.scalars().all())
```

### After (repository delegation)
```
# Dependency injection
sessions_repo = PlannedSessionRepository(session)

# Route handler
rows = await sessions_repo.get_for_training_plan(plan_id)
return [PlannedSessionResponse.model_validate(r) for r in rows]
```

## Testing Requirements
- `app.db.integrity_utils.is_unique_violation` returns `True` for a mocked `IntegrityError` whose `orig.pgcode == '23505'`, and `False` for all other pgcode values or when `orig` is absent.
- `TrainingPlanRepository.get_active_for_athlete` continues to resolve the active training plan for an athlete with an active goal; existing integration tests for plan retrieval pass.
- `WeeklySessionRepository.add_many` passes static type checks (e.g. `mypy` or `pyright`) without errors.
- The three plan read endpoints (`GET /plan/sessions`, `GET /plan/upcoming`, `GET /plan/checkpoints`) return byte-for-byte identical JSON responses compared to the inline query implementation for a fixed database state.
- Existing suite (unit, integration, API, behaviour) passes with no regressions.

## Coder Handoff Notes

### Coder Scope
Execute: Steps 1, 2, 3, 4, 5, 6, 7, 8 — all application code changes [OWNER: Coder]
Skip: Step 9 — test updates and validation [OWNER: Test Architect]

### Risks
- **Import cycles:** `app/db/integrity_utils.py` imports only `IntegrityError` from SQLAlchemy and has no project-module imports; it is safe from cycles.
- **Type-checking cycles:** In Step 5, `WeeklySession` is defined in `app/models/weekly_plan.py`. The repository module already imports `WeeklyPlan` from that model file. Use a `TYPE_CHECKING` import for `WeeklySession` to avoid a runtime circular import if one exists.
- **Route response shape change:** The response schemas (`PlannedSessionResponse`, `CheckpointResponse`) remain the source-of-truth for JSON shape. The repository must return ORM instances so `model_validate` works identically. Do not switch to raw `Row` tuples in the repository.
- **Dependency injection tests:** If any route tests monkeypatch or override `Depends(get_db)`, they should continue to work because the new repositories are built from the same `AsyncSession`.

### Clarifications
- For Step 2, keeping `AthleteRepository.is_unique_violation` as a delegating static method is the intended design. `AuthService` should not change.
- For Step 3, the module-level `TrainingGoalRepository_unique_violation` is to be fully deleted, not kept as a deprecated alias.
- For Step 7, the `CheckpointRepository` already has `get_for_training_plan`; the route should simply inject it and use it. Do not duplicate the query.
- The `OnboardingService` extraction decision is explicitly deferred. Do—not attempt to extract `update_profile`, `update_preferences`, or `get_twin_state` into a new service.
