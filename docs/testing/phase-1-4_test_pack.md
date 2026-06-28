# Test Pack — Phase-1.4-P1 (Plan Generation)

Sub-phase: **Phase-1.4 — Plan Generation**
Plan ID: **phase-1-4-p1-plan-generation**
Plan: `docs/implementation/phase-1/phase-1-4-p1-plan-generation.md`
Validator: PASS — `docs/implementation/phase-1/phase-1-4-p1-plan-generation_validation.md`
Manifest: `tests/test-manifest/phase-1-4.yaml`

Operating mode: **Incremental** — existing test infrastructure + prior
phase manifests (Phase-1.1 / 1.2a / 1.2b / 1.2c / 1.3) carry forward;
six new test files and one new manifest file are introduced.

## What This Sub-Phase Delivers

`PlanGenerationService` — atomic, pure-Python plan generation for
`race_event` and `target_performance` goals (no LLM, no external API),
plus three plan persistence repositories and four read-only HTTP
endpoints. Plan hierarchy: `TrainingPlan` -> `WeeklyPlan[]` ->
`WeeklySession[]` -> `PlannedSession[]` -> `Checkpoint[]`. Event
contract: `training_plan_generated` via the transactional outbox inside
the same DB transaction as the producing domain state (ADR-004).
Onboarding integration: `OnboardingService.complete_onboarding`
invokes plan generation at the end of the onboarding transaction so
the two land atomically — `onboarding_complete` stays `False` on
plan-generation failure.

## Test Files Generated

| Path | Layer | Purpose |
|------|-------|---------|
| `tests/unit/test_plan_generation_templates.py` | unit | Pure-Python templates — gate, phase allocation, structural session rules, checkpoint scheduling |
| `tests/unit/test_plan_generation_errors.py` | unit | Exception surface — `PlanGenerationError`, `TrainingLengthGateError`, `InvalidGoalTypeError` |
| `tests/integration/test_plan_repositories.py` | integration | `TrainingPlanRepository` / `WeeklyPlanRepository` / `WeeklySessionRepository` / `CheckpointRepository` against the test DB |
| `tests/integration/test_plan_generation_service.py` | integration | End-to-end `generate_plan` happy path + structural invariants + supersession + event publication |
| `tests/api/test_plan_endpoints.py` | api | Four read-only endpoints — happy paths, 404 when no plan, 403 cross-athlete, 401 missing bearer |
| `tests/behaviour/test_plan_user_journey.py` | behaviour | Register -> onboarding -> plan live, plus cross-athlete / no-onboarding guards |

## Coverage Map (sub-phase only)

Routes:
- Covered: `GET /athletes/{id}/plan`, `GET /athletes/{id}/plan/sessions`,
  `GET /athletes/{id}/plan/upcoming`, `GET /athletes/{id}/plan/checkpoints`.

Events:
- Covered: `training_plan_generated` payload shape + outbox row
  (publication_status=`pending`) in the same transaction.

Invariants: see `tests/test-manifest/phase-1-4.yaml` -> `coverage.invariants.covered`.

## What Was Updated vs. Created

### Created
- `tests/unit/test_plan_generation_templates.py`
- `tests/unit/test_plan_generation_errors.py`
- `tests/integration/test_plan_repositories.py`
- `tests/integration/test_plan_generation_service.py`
- `tests/api/test_plan_endpoints.py`
- `tests/behaviour/test_plan_user_journey.py`
- `tests/test-manifest/phase-1-4.yaml`

### Modified (manifest only)
- `tests/test-manifest/index.yaml`
  - `selection.smoke` — added the two new Phase-1.4 unit tests.
  - `selection.feature` — replaced the previous Phase-1.3 paths with
    the new Phase-1.4 paths (per spec: `feature` holds the **current**
    sub-phase only).
  - `selection.regression` and `selection.release` — untouched.
    Per the manifest ownership rules, those groups only gain
    entries on promotion (`status: promoted`, `validation.passed: true`).
  - Cross-phase history, cross-phase coverage, and cross-phase
    dependencies — untouched; promotion only.

### Reused (no rewrite)
- `tests/conftest.py` — the existing `db_session`, `client`, and
  `_prepare_database` fixtures are reused as-is. No new infra needed.
- `tests/payloads.py` — `_weekly_schedule_payload` is reused by the
  API and behaviour tests for plan-endpoint fixtures.
- `tests/utils/factories.py` — `make_athlete` is reused by repository
  tests for seeding. JWT helpers (`http_register`, `bearer_header`)
  used by the API + behaviour tests.

## Operating Mode Decisions

1. **No migration test.** Step 8 of the plan is a no-op because
   Phase-1.2b already created the `training_plans` / `weekly_plans` /
   `planned_sessions` / `checkpoints` tables with the required
   indexes and JSONB defaults. There is no Phase-1.4 Alembic
   migration to test, and no `tests/integration/test_migration_phase_1_4.py`
   is introduced.
2. **Smoke group includes the two new unit tests.** Pure-Python
   tests of templates and exceptions are the cheapest tripwire for
   the plan's largest invariant — pure-Python plan generation —
   and fit the smoke group's "lightweight, no DB" profile.
3. **Feature group contains Phase-1.4 only.** Per spec, the feature
   group tracks the **current** active sub-phase; previous
   Phase-1.3 paths are removed from `feature` and remain in the
   `regression` and `release` groups (preserved by promotion).
4. **Status: generated.** All seven new features in
   `phase-1-4.yaml` carry `validation.implemented: true`,
   `validation.executable: false`, `validation.passed: false`.
   Promotion to `status: promoted` happens after the DevOps PASS
   report per the manifest ownership rules.

## Open Items / Coverage Gaps

The following remain declared `missing` in
`tests/test-manifest/phase-1-4.yaml` -> `coverage.invariants.missing`:

- LLM-driven hypothesis exploration for race events (out of Phase 1.4
  scope).
- Plan regeneration on confidence upgrade (Phase 2).
- Session lifecycle management — skip / miss / redistribute (Phase 4).
- Workout library and workout generation (Phase 1.5b / Phase 4).
- Pre-week review and session redistribution logic (deferred).
- Phase-1.5a first-coach-message emission wired to this plan.

These are explicitly out of Phase-1.4 scope per the plan's "Out Of
Scope" section and will be picked up by their respective sub-phases.

## DevOps Hand-off Checklist

When DevOps picks up Phase-1.4-P1 for execution:

1. Read `tests/test-manifest/index.yaml` -> `selection.feature` to
   resolve execution scope (the 6 Phase-1.4 test files).
2. Read `tests/test-manifest/phase-1-4.yaml` for prerequisites — see
   `features.*.execution_prerequisites` (migrations=false, seed_data=false,
   external_services=[]).
3. Run the suite; on PASS, set
   `validation.executable: true` and `validation.passed: true` per
   feature in `tests/test-manifest/phase-1-4.yaml`.
4. Hand the report back to the Test Architect for promotion.

The fixtures from `tests/conftest.py` already wire the test database
to the live Phase-1.2b schema. No additional setup is required for
Phase-1.4.

## Inherited Test Infrastructure Notes

The `tests/README.md` guide captures hard-won lessons from prior test
failures (async session pitfalls, schema inspection anti-patterns,
JWT determinism). Phase-1.4 tests honor those:

- Every integration test uses the `db_session` fixture; no manual
  session construction.
- No test asserts on JWT access-token uniqueness — refresh-token
  uniqueness is the actual security property, and even then we use
  per-test fixtures rather than comparing issued tokens.
- DB schema introspection (when needed) goes through
  `tests/utils/schema_helpers.py` — not direct `sync_session.connection()`
  calls.
- HTTP tests use `httpx.AsyncClient` against the real FastAPI app via
  the `client` fixture, with `Authorization: Bearer <token>` headers
  built through `tests/utils/http_helpers.py::bearer_header` and
  fresh tokens via `http_register`.

## Reference

- Plan: `docs/implementation/phase-1/phase-1-4-p1-plan-generation.md`
- Validator (PASS): `docs/implementation/phase-1/phase-1-4-p1-plan-generation_validation.md`
- Manifest: `tests/test-manifest/phase-1-4.yaml`
- Index: `tests/test-manifest/index.yaml`
- Architecture: `docs/architecture/02-computations/plan-generation.md`,
  `docs/architecture/02-computations/plan-generation-race.md`,
  `docs/architecture/02-computations/plan-generation-target-performance.md`
