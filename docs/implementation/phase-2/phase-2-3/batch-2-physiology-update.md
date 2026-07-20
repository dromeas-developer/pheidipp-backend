> **Baseline — migrated from** `docs/implementation/phase-2/phase-2-3-p2-physiology-update.md` **on** 2026-07-19.
> This plan was implemented before the BRD format was introduced.
> It documents what was built, verified against the current codebase
> on 2026-07-19. See `## Coder Notes` for any gaps found during migration.

## Batch Objective

Implement the `PhysiologyUpdateService` — the Bayesian update engine that consumes threshold observations from `ThresholdDetectionService` (Plan P1), applies the posterior update formula to `AthletePhysiology` in place, writes append-only `PhysiologyMeasurement` records, and fires the `physiology_updated` event when the posterior shifts by > 1 bpm.

## Preconditions

Depends on Plan P1 (`ThresholdDetectionService`, `PhysiologyMeasurement` model and repository, `ThresholdObservation` dataclass, `PhysiologyParameter` enum).

## Scope

- `PhysiologyUpdateService` implementing the Bayesian update formula: prior decay (42-day half-life), posterior mean (weighted average), posterior uncertainty (floor 0.5), dominant source derivation
- `AthletePhysiologyRepository` extension: `update_in_place` method for mutating JSONB posterior state columns
- `PhysiologyMeasurement` record writing (append-only) for every observation — always written regardless of posterior shift
- `physiology_updated` event firing via `EventPublisher` when any parameter posterior shifts by > 1 bpm (LT1/LT2 HR) or > 1 watt (CP)
- Confidence transition detection: LOW→MEDIUM at evidence weight ≥ 4.0, MEDIUM→HIGH at ≥ 8.0 per metric
- Idempotency: duplicate observation detection — measurement still written but posterior not shifted, no event fires

## Steps

1. [OWNER: Coder] Extend `AthletePhysiologyRepository` with an `update_in_place` method. Takes `athlete_id` and updated JSONB column values (`lt1`, `lt2`, `cp`, `max_hr` as dicts). Mutates existing row; flushes but does not commit. Must NOT create a new row.

2. [OWNER: Coder] Create `PhysiologyUpdateService` in `app/services/physiology_update_service.py`. Primary entry point `async def apply_observations(self, athlete_id, observations) -> PhysiologyUpdateResult`. Loads current `AthletePhysiology`, applies Bayesian update per observation, writes `PhysiologyMeasurement` records, updates in place, fires event if shifted.

3. [OWNER: Coder] Implement the Bayesian update formula as a pure function. `decay_factor = exp(-days_since_last / 42)`. `decayed_weight = current.prior_weight * decay_factor`. `posterior_mean = weighted average`. `posterior_uncertainty = max(current.uncertainty * sqrt(decayed_weight / new_total_weight), 0.5)`. `dominant_source = observation.source if observation.weight > decayed_weight else current.dominant_source`.

4. [OWNER: Coder] Implement `PhysiologyMeasurement` record writing. For each observation, create a row with `athlete_id`, `activity_id`, `parameter`, `observed_value`, `source`, `measurement_date`, `algorithm_used`, `confidence_weight`. Always written — even if posterior does not shift.

5. [OWNER: Coder] Implement posterior shift detection. For HR parameters: shift is `abs(new_value - old_value)` in bpm. For CP: shift in watts. Parameter "shifted" if shift exceeds 1.0.

6. [OWNER: Coder] Implement `AthletePhysiology` in-place update. Write updated JSONB columns back to the row. Use `flag_modified` on each touched outer column so SQLAlchemy persists the mutation. Only update columns that changed.

7. [OWNER: Coder] Implement `physiology_updated` event firing. When any parameter shifted by > 1 unit, fire via `EventPublisher` with payload: `athlete_id`, `parameters_updated`, `dominant_sources`, `prior_weights`. Event written to transactional outbox in same transaction. Does NOT fire when no parameters shifted.

8. [OWNER: Coder] Implement confidence transition detection. Compute per-metric confidence level from `prior_weight`: ≥ 8.0 → HIGH, ≥ 4.0 → MEDIUM, < 4.0 → LOW. P2 computes raw level from current `prior_weight` only — does NOT enforce monotonicity ratchet (that is P3's responsibility per ADR-011).

9. [OWNER: Coder] Implement idempotency for duplicate observations. Check if `PhysiologyMeasurement` exists with same `(athlete_id, activity_id, parameter, source, measurement_date, observed_value)`. If duplicate: still write measurement for audit, but do NOT apply Bayesian update, do NOT fire event.

10. [OWNER: Coder] Create `PhysiologyUpdateResult` dataclass carrying: `physiology` (updated row), `shifted_parameters`, `metric_confidence`, `confidence_transitions`, `measurements_written`.

11. [OWNER: Coder] Register `PhysiologyUpdateService` and `PhysiologyUpdateResult` in `app/services/__init__.py`.

## Context Needed

Step 1:
- Primary: `app/repositories/athlete_physiology_repository.py`, `app/models/athlete_physiology.py` (JSONB column shape)

Step 2:
- Primary: output of Step 1, `app/services/threshold_detection_service.py` (Plan P1 — `ThresholdObservation` dataclass), `app/services/twin_recalibration_service.py` (construction pattern)

Step 3:
- Primary: `docs/architecture/02-computations/physiology-update.md`, `app/services/onboarding_service.py` (`_bootstrap_signal` function — JSONB shape)

Step 4:
- Primary: `app/repositories/physiology_measurement_repository.py` (Plan P1), `app/models/physiology_measurement.py`

Step 5:
- Primary: output of Step 3 (bayesian_update function)

Step 6:
- Primary: `app/models/athlete_physiology.py` (JSONB column structure), SQLAlchemy `flag_modified` documentation

Step 7:
- Primary: `app/services/event_publisher.py`, `app/services/activity_ingestion_service.py` (event publishing pattern), `docs/architecture/00-foundations/event-catalogue.md`

Step 8:
- Primary: `docs/architecture/00-foundations/confidence-model.md` (CONFIDENCE_THRESHOLDS: 4.0/8.0), `app/services/onboarding_service.py` (`_bootstrap_metric_confidence`)

Step 9:
- Primary: `app/repositories/physiology_measurement_repository.py` (Plan P1 — dedup lookup), `docs/architecture/01-entities/athlete-physiology.md` (Idempotency section)

Step 10:
- Primary: `app/services/twin_recalibration_service.py` (`RecalibrationResult` dataclass pattern)

Step 11:
- Primary: `app/services/__init__.py` (existing registration pattern)

## Batch Success Criteria

Batch 1 (Steps 1, 3, 10) — Bayesian Core:
- `AthletePhysiologyRepository.update_in_place` mutates existing row (flush, no commit)
- `bayesian_update` pure function correctly computes posterior mean, uncertainty, prior_weight, dominant_source, last_observation_date
- `PhysiologyUpdateResult` dataclass exists with all specified fields

Batch 2 (Steps 2, 4, 5, 6) — Update Engine:
- `apply_observations` processes a list of `ThresholdObservation` objects
- Each observation produces a `PhysiologyMeasurement` record (always written)
- `AthletePhysiology` JSONB columns updated in place with new posterior values
- `flag_modified` called on updated JSONB columns
- Posterior shift detection correctly identifies parameters that shifted > 1 unit

Batch 3 (Steps 7, 8, 9, 11) — Events & Idempotency:
- `physiology_updated` event fires via `EventPublisher` when > 1 unit shift, with correct payload
- Event does NOT fire when no parameters shifted
- Confidence transition detection identifies LOW→MEDIUM (4.0) and MEDIUM→HIGH (8.0) per metric
- P2 computes from current `prior_weight` only — ratchet is P3's responsibility (ADR-011)
- Duplicate observations write measurement but do NOT shift posterior or fire event
- `PhysiologyUpdateService` and `PhysiologyUpdateResult` registered in `app/services/__init__.py`

## Files Expected To Change

- `app/repositories/athlete_physiology_repository.py` — add `update_in_place`
- `app/services/physiology_update_service.py` — new service with `PhysiologyUpdateResult`, Bayesian update, event firing, idempotency
- `app/services/__init__.py` — register service and result

## Coder Notes

- Verified against current codebase (2026-07-19): all entities, services, repositories, events, and tests exist. No discrepancies.
- Confidential threshold values: 4.0 (LOW→MEDIUM) and 8.0 (MEDIUM→HIGH) from `confidence-model.md` are authoritative. The 15.0/40.0 values in some code blocks are stale examples.
- P2 does NOT enforce the monotonicity ratchet — that is P3's responsibility per ADR-011.
- Test coverage: 4 unit files + 5 integration files + 1 behaviour file — all passing per manifest.
