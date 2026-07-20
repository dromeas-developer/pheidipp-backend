> **Baseline — migrated from** `docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md` **on** 2026-07-19.
> This plan was implemented before the BRD format was introduced.
> It documents what was built, verified against the current codebase
> on 2026-07-19. See `## Coder Notes` for any gaps found during migration.

## Batch Objective

Extend `TwinRecalibrationService` to support the `calibration` trigger — creating a new `TwinState` with updated threshold snapshots and `metric_confidence` derived from the updated `AthletePhysiology`. Wire the full threshold detection pipeline as a procrastinate worker task: `ThresholdDetectionService` (P1) → `PhysiologyUpdateService` (P2) → `TwinRecalibrationService` (this plan) in a single transaction, triggered after signal cleaning completes.

## Preconditions

Depends on Plan P1 (`ThresholdDetectionService`, `ThresholdObservation` dataclass, `PhysiologyMeasurement` model) and Plan P2 (`PhysiologyUpdateService`, `PhysiologyUpdateResult`, `physiology_updated` event).

## Scope

- `TwinRecalibrationService` extension: new `recalibrate_for_calibration` method creating `TwinState` with `trigger = calibration`, updated threshold inline snapshots, and `metric_confidence` from `AthletePhysiology` prior weights
- `insert_if_not_exists` deduplication: calibration supersedes activity_sync; duplicate calibration skipped
- Alembic migration to drop `uq_twin_states_athlete_activity` unique index (replace with non-unique index)
- Per-metric confidence monotonicity ratchet: `max(stored_level, computed_level)` per metric (ADR-011)
- `confidence_level` derivation from `min(lt1.hr.prior_weight, lt2.hr.prior_weight)` using thresholds 4.0/8.0
- `twin_recalibrated` and `twin_confidence_upgraded` event firing
- New procrastinate worker task `threshold_detection` orchestrating the full pipeline in one transaction
- Pipeline wiring: `signal_clean` worker task defers `threshold_detection` after its commit (ADR-009 pattern)

## Steps

1. [OWNER: Coder] Generate Alembic migration to drop `uq_twin_states_athlete_activity` unique index on `twin_states`. Replace with a non-unique index on `(athlete_id, activity_id)`. The application-level `insert_if_not_exists` is the authoritative deduplication mechanism.

2. [OWNER: Coder] Extend `TwinRecalibrationService` with `recalibrate_for_calibration` method. Accepts `athlete_id`, `activity_id`, and `PhysiologyUpdateResult` (from P2). Reads current `AthleteFitness`, active `TrainingGoal`, derives `confidence_level` and `metric_confidence` from updated `AthletePhysiology`. Applies per-metric monotonicity ratchet (ADR-011): `max(previous.metric_confidence[metric], computed[metric])` per metric. Builds inline threshold snapshot from updated physiology. Calls `insert_if_not_exists`. Fires `twin_recalibrated` event. If `confidence_level` increased, fires `twin_confidence_upgraded`. Returns `CalibrationRecalibrationResult`.

3. [OWNER: Coder] Implement `insert_if_not_exists` deduplication. If existing calibration TwinState → skip. If existing non-calibration + incoming calibration → insert new (prior remains as history). If existing non-calibration + incoming non-calibration → skip. Check ALL existing TwinStates for the activity, not just the first.

4. [OWNER: Coder] Implement `twin_recalibrated` event firing. When new `TwinState` inserted, fire via `EventPublisher` with payload: `athlete_id`, `twin_state_id`, `previous_twin_state_id`, `trigger` ("calibration"), `confidence_level`, `fitness_score`, `fatigue_score`. Fires for every new calibration TwinState.

5. [OWNER: Coder] Implement `twin_confidence_upgraded` event firing. When `confidence_level` is higher than previous, fire with payload: `athlete_id`, `from_level`, `to_level`, `twin_state_id`. Fires in addition to `twin_recalibrated`, not instead of.

6. [OWNER: Coder] Create `threshold_detection` procrastinate worker task in `app/worker/app.py`. Opens own `AsyncSession`. Constructs `ThresholdDetectionService` (must pass `PlannedSessionRepository` — without it, natural training analysis is silently skipped), `PhysiologyUpdateService`, and `TwinRecalibrationService`. Orchestrates: detect → apply_observations → recalibrate_for_calibration → commit. Returns early if observations empty or no parameters shifted. Single commit boundary — all writes atomic.

7. [OWNER: Coder] Wire pipeline: extend `signal_clean` worker task to defer `threshold_detection` after its commit when `result.created` is True. Follow ADR-009 pattern: defer after commit, swallow defer failures after logging.

8. [OWNER: Coder] Register `threshold_detection` task, `CalibrationRecalibrationResult` in `app/services/__init__.py`.

## Context Needed

Step 1:
- Primary: `app/models/twin_state.py` (index definition to drop), latest Alembic migration (down_revision)

Step 2:
- Primary: `app/services/twin_recalibration_service.py` (existing `recalibrate` method), `app/models/twin_state.py`, output of Plan P2 (`PhysiologyUpdateResult`), `docs/adr/011-confidence-monotonicity-ratchet-location.md`

Step 3:
- Primary: `docs/architecture/01-entities/twin-state.md` (Concurrency & Coordination section), `app/repositories/twin_state_repository.py`

Step 4-5:
- Primary: `app/services/event_publisher.py`, `docs/architecture/00-foundations/event-catalogue.md`

Step 6:
- Primary: `app/worker/app.py` (existing task patterns), output of P1 and P2, output of Step 2

Step 7:
- Primary: `app/worker/app.py` (`signal_clean` task), `app/services/activity_ingestion_service.py` (`_defer_signal_clean` pattern), `docs/adr/009-signal-cleaning-as-decoupled-async-task.md`

Step 8:
- Primary: `app/services/__init__.py`, `app/services/twin_recalibration_service.py`

## Batch Success Criteria

Batch 1 (Steps 1, 3) — Migration & Dedup:
- Alembic migration drops unique index, replaces with non-unique index
- `insert_if_not_exists` correctly implements deduplication: calibration supersedes activity_sync, duplicate calibration skipped, duplicate non-calibration skipped
- `get_by_activity_and_trigger` supports calibration lookup

Batch 2 (Steps 2, 4, 5) — Recalibration & Events:
- `recalibrate_for_calibration` creates TwinState with `trigger = calibration`, updated thresholds, `metric_confidence` from `AthletePhysiology`
- `confidence_level` derived as `min(lt1.hr.prior_weight, lt2.hr.prior_weight)` with monotonic ratchet
- Per-metric ratchet: `max(previous.metric_confidence[metric], computed[metric])` per metric (ADR-011)
- `twin_recalibrated` fires for every new calibration TwinState
- `twin_confidence_upgraded` fires only when confidence_level increases
- Event ordering: `physiology_updated` (P2) → `twin_recalibrated` → `twin_confidence_upgraded`

Batch 3 (Steps 6, 7, 8) — Worker & Wiring:
- `threshold_detection` procrastinate task orchestrates full pipeline
- Returns early with no recalibration when observations empty or no parameters shifted
- Commits atomically — all writes land or none do
- `signal_clean` defers `threshold_detection` after commit when `result.created` is True
- Defer failures swallowed after logging (ADR-009 pattern)
- `CalibrationRecalibrationResult` registered in `app/services/__init__.py`

## Files Expected To Change

- `alembic/versions/<migration>.py` — drop unique index migration
- `app/services/twin_recalibration_service.py` — add `recalibrate_for_calibration`, `insert_if_not_exists`, confidence ratchet, event firing
- `app/repositories/twin_state_repository.py` — add `get_by_activity_and_trigger`
- `app/worker/app.py` — new `threshold_detection` task, extend `signal_clean` defer
- `app/services/__init__.py` — register `CalibrationRecalibrationResult`

## Coder Notes

- Verified against current codebase (2026-07-19): all entities, services, repositories, worker tasks, events, and tests exist. No discrepancies.
- ADR-011 constraint: the per-metric confidence ratchet is enforced here (P3), NOT in P2. P2 outputs raw computed level; P3 applies `max(stored, computed)`.
- The `ThresholdDetectionService` in the worker task MUST receive `PlannedSessionRepository` — without it, natural training analysis is silently skipped.
- `model_version` for calibration TwinStates: `"v2-threshold-detection"`.
