# Implementation Plan: Phase-2.3 — Twin Recalibration Extension + Pipeline Integration
## Plan ID: Phase-2.3-P3

## Sub-Phase Reference
Sub-Phase ID: Phase-2.3
Sub-Phase Title: Threshold Detection & Physiology Update

## Objective
Extend `TwinRecalibrationService` to support the `calibration` trigger —
creating a new `TwinState` with updated threshold snapshots and
`metric_confidence` derived from the updated `AthletePhysiology`. Wire the
full threshold detection pipeline as a procrastinate worker task that
orchestrates `ThresholdDetectionService` (P1) → `PhysiologyUpdateService`
(P2) → `TwinRecalibrationService` (this plan) in a single transaction,
triggered after signal cleaning completes. This plan delivers the end-to-end
pipeline that satisfies the sub-phase exit gate.

## Scope
- `TwinRecalibrationService` extension: new `recalibrate_for_calibration`
  method that creates a `TwinState` with `trigger = calibration`, updated
  threshold inline snapshots, and `metric_confidence` derived from
  `AthletePhysiology` prior weights
- `insert_if_not_exists` deduplication logic per `twin-state.md` Concurrency
  & Coordination section — calibration trigger supersedes activity_sync
- Alembic migration to drop the `uq_twin_states_athlete_activity` unique
  index (it prevents the calibration TwinState from coexisting with the
  activity_sync TwinState for the same activity — see Architecture
  Clarifications)
- `confidence_level` derivation from `min(lt1.hr.prior_weight,
  lt2.hr.prior_weight)` using thresholds 4.0/8.0
- `metric_confidence` derivation from per-parameter prior weights
- `twin_recalibrated` event firing when new TwinState is inserted
- `twin_confidence_upgraded` event firing when confidence_level increases
- New procrastinate worker task `threshold_detection` that orchestrates the
  full pipeline: load activity → threshold detection → physiology update →
  twin recalibration → event firing, all in one transaction
- Pipeline wiring: `signal_clean` worker task defers `threshold_detection`
  after its commit (same pattern as `fit_ingest` deferring `signal_clean`
  per ADR-009)
- `Activity.cleaning_pipeline_version` is NOT modified by this plan — it
  is already set by `SignalCleaningService`

## Out Of Scope
- `ThresholdDetectionService` algorithms (Plan P1)
- `PhysiologyUpdateService` Bayesian update (Plan P2)
- `PhysiologyMeasurement` model (Plan P1)
- `physiology_updated` event production (Plan P2)
- API endpoints for physiology or twin state (existing endpoints are
  unchanged — they already read from `TwinState` and `AthletePhysiology`)
- Reprocessing of historical activities through the new pipeline
  (Principle #14 — deferred to a later sub-phase)
- `twin_model_ready` event (fires on first TwinState at onboarding — already
  handled by `OnboardingService`)

## Architecture Contracts
- `01-entities/twin-state.md` — IMPLEMENTS (calibration trigger,
  append-only insert, deduplication, confidence_level derivation,
  metric_confidence, event production)
- `02-computations/physiology-update.md` — DEPENDS ON (pipeline order:
  threshold detection → physiology update → twin recalibration)
- `00-foundations/confidence-model.md` — DEPENDS ON (confidence thresholds
  4.0/8.0; per-metric confidence derivation; global confidence = min(LT1
  HR, LT2 HR))
- `00-foundations/event-catalogue.md` → `twin_recalibrated` — PRODUCES
- `00-foundations/event-catalogue.md` → `twin_confidence_upgraded` —
  PRODUCES
- `docs/adr/009-signal-cleaning-as-decoupled-async-task.md` — DEPENDS ON
  (pipeline decoupling pattern: signal_clean commits, then defers
  threshold_detection)
- `02-computations/threshold-detection.md` — DEPENDS ON (Plan P1
  `ThresholdDetectionService` entry point)
- `02-computations/physiology-update.md` — DEPENDS ON (Plan P2
  `PhysiologyUpdateService` entry point)
- `docs/adr/011-confidence-monotonicity-ratchet-location.md` — DECISION
  (the per-metric confidence ratchet `max(stored_level, computed_level)` is
  enforced in this plan's `TwinRecalibrationService`, NOT in P2's
  `PhysiologyUpdateService`. P2 outputs the raw computed level; P3 reads the
  previous TwinState and applies the ratchet per metric before inserting the
  new TwinState. Read before implementing Step 2.)

## Invariants
- "No `UPDATE` or `DELETE` at any layer. `TwinStateRepository` exposes only
  `insert`, `get_latest`, `get_by_activity`, and `get_history`."
  (twin-state invariant)
- "Multiple TwinStates per day are possible (e.g., `activity_sync` followed
  by `wellness_update`), but only **one** TwinState per `activity_id`. See
  'Concurrency & Coordination' for deduplication logic." (twin-state
  invariant — clarified: the concurrency section allows a calibration
  TwinState to coexist with a prior activity_sync TwinState for the same
  activity_id; the deduplication is application-level, not DB-level)
- "`confidence_level` is recomputed from
  `min(AthletePhysiology.lt1.hr.prior_weight,
  AthletePhysiology.lt2.hr.prior_weight)` at each snapshot." (twin-state
  invariant)
- "The confidence level of a `TwinState` never changes after creation"
  (confidence-model invariant)
- "A new `TwinState` record is created when confidence transitions"
  (confidence-model invariant)
- "Confidence is monotonic (only increases, never decreases)" (sub-phase
  invariant)
- "Threshold detection only runs for `calibration_eligible = true`
  activities" (sub-phase invariant)
- "`physiology_updated` event fires only when posterior shifts by > 1 bpm"
  (sub-phase invariant — the `threshold_detection` task calls
  `PhysiologyUpdateService` which handles this; the task does not
  re-evaluate the threshold)

## Implementation Steps

1. [OWNER: Coder] Generate Alembic migration to drop the
   `uq_twin_states_athlete_activity` unique index on `twin_states`. The
   index currently enforces one TwinState per `(athlete_id, activity_id)`
   where `activity_id IS NOT NULL`, but the architecture's Concurrency &
   Coordination section explicitly allows a calibration TwinState to be
   inserted when an activity_sync TwinState already exists for the same
   activity. Replace the unique index with a non-unique index on
   `(athlete_id, activity_id)` to support the reverse lookup
   (`get_by_activity`) without preventing the dual-trigger scenario. The
   application-level `insert_if_not_exists` logic (Step 3) is the
   authoritative deduplication mechanism. Name the migration
   `phase_2_3_p3_drop_twin_states_activity_unique.py`.

2. [OWNER: Coder] Extend `TwinRecalibrationService` with a
   `recalibrate_for_calibration` method. This method is distinct from the
   existing `recalibrate` method (which handles the `activity_sync` trigger
   with Banister-only updates). The new method:
   - Accepts `athlete_id`, `activity_id`, and a
     `PhysiologyUpdateResult` (from Plan P2 — carries the updated
     `AthletePhysiology`, shifted parameters, `metric_confidence`, and
     confidence transitions).
   - Reads the current `AthleteFitness` row for the inline fitness/fatigue/
     form snapshot (these were already updated by the `activity_sync`
     recalibration during ingestion — the calibration TwinState snapshots
     the current values).
   - Reads the active `TrainingGoal` for the `training_goal_id` FK.
   - Derives `confidence_level` from `min(lt1.hr.prior_weight,
     lt2.hr.prior_weight)` using thresholds 4.0 (MEDIUM) and 8.0 (HIGH).
     Confidence is monotonic — compare against the previous TwinState's
     confidence_level and keep the higher value (`max(previous, computed)`).
   - Derives `metric_confidence` from per-parameter prior weights using the
     same 4.0/8.0 thresholds. For parameters with null prior_weight (e.g.,
     `lt1_power` when no power data), the metric confidence is null.
     **Per-metric monotonicity ratchet (ADR-011)**: for each metric key in
     `metric_confidence`, the final stored value is
     `max(previous_twin_state.metric_confidence[metric], computed_level)`.
     Read the previous TwinState via `TwinStateRepository.get_latest` and
     apply the ratchet per metric — a metric that previously reached MEDIUM
     stays MEDIUM even if `prior_weight` has since decayed below 4.0. If
     there is no previous TwinState (first snapshot), the computed level is
     the final level. For metrics where the previous value is null (no power
     data before) and the computed value is non-null (power data now
     available), use the computed value — null means "no data", not "low
     confidence".
   - Builds the inline threshold snapshot from the updated
     `AthletePhysiology`: `lt1_hr_bpm`, `lt2_hr_bpm`, `cp_watts` (from the
     JSONB posterior values).
   - Calls `insert_if_not_exists` (Step 3) to handle deduplication.
   - Fires `twin_recalibrated` event (Step 4).
   - If `confidence_level` increased from the previous TwinState, fires
     `twin_confidence_upgraded` event (Step 5).
   - Returns a `CalibrationRecalibrationResult` carrying the new
     `TwinState` and whether confidence was upgraded.

3. [OWNER: Coder] Implement `insert_if_not_exists` deduplication logic on
   `TwinRecalibrationService`. Per `twin-state.md` Concurrency & Coordination:
   ```
   existing = twin_states.get_by_activity(activity_id)
   if existing:
       if existing.trigger == 'calibration':
           # Calibration is the most complete snapshot; skip
           return existing
       elif trigger == 'calibration':
           # We have a fitness-only snapshot, but now we have calibration.
           # Insert the calibration record (the fitness-only record
           # remains as history).
           pass  # fall through to insert
       else:
           # Duplicate non-calibration trigger; skip
           return existing
   return twin_states.insert(new_state)
   ```
   This logic is application-level deduplication — the DB unique index was
   dropped in Step 1. The `get_by_activity` query returns the most recent
   TwinState for the activity (there may be multiple after the unique index
   is dropped — use `ORDER BY created_at DESC LIMIT 1` or check all
   existing records for a calibration trigger).

4. [OWNER: Coder] Implement `twin_recalibrated` event firing. When a new
   `TwinState` is inserted by `recalibrate_for_calibration`, fire the event
   via `EventPublisher`:
   ```
   event_type = "twin_recalibrated"
   payload = {
       "athlete_id": str(athlete_id),
       "twin_state_id": str(new_state.id),
       "previous_twin_state_id": str(previous.id) if previous else None,
       "trigger": "calibration",
       "confidence_level": new_state.confidence_level.value,
       "fitness_score": new_state.fitness,
       "fatigue_score": new_state.fatigue
   }
   ```
   The event is written to the transactional outbox in the same transaction
   as the TwinState insert. The event fires for every new calibration
   TwinState — it is not gated by a threshold (unlike `physiology_updated`
   which is gated by > 1 bpm shift).

5. [OWNER: Coder] Implement `twin_confidence_upgraded` event firing. When
   the new TwinState's `confidence_level` is higher than the previous
   TwinState's `confidence_level`, fire:
   ```
   event_type = "twin_confidence_upgraded"
   payload = {
       "athlete_id": str(athlete_id),
       "from_level": previous.confidence_level.value,
       "to_level": new_state.confidence_level.value,
       "twin_state_id": str(new_state.id)
   }
   ```
   This event fires in addition to `twin_recalibrated` (not instead of).
   Both events are written to the outbox in the same transaction. The
   ordering in the outbox is: `physiology_updated` (from P2) →
   `twin_recalibrated` → `twin_confidence_upgraded` (if applicable).

6. [OWNER: Coder] Create the `threshold_detection` procrastinate worker task
   in `app/worker/app.py`. The task:
   - Opens its own `AsyncSession` (same pattern as `signal_clean`).
   - Constructs `ThresholdDetectionService` (P1), `PhysiologyUpdateService`
     (P2), and `TwinRecalibrationService` with the shared session.
     **Important**: `ThresholdDetectionService` MUST be constructed with
     `PlannedSessionRepository` — without it, the natural training analysis
     (LT1 passive inference method 3) is silently skipped. The
     `PlannedSessionRepository` is an optional constructor parameter on P1's
     service (defaults to `None`), but the production worker task must pass
     it so the full algorithm suite runs.
   - Calls `threshold_detection.detect(athlete_id, activity_id)` → returns
     `list[ThresholdObservation]`.
   - If observations is empty, returns early (no threshold signal in this
     session — not an error).
   - Calls `physiology_update.apply_observations(athlete_id, observations)`
     → returns `PhysiologyUpdateResult`.
   - If `PhysiologyUpdateResult.shifted_parameters` is empty, returns early
     (posterior did not shift > 1 unit — no recalibration needed; the
     `physiology_updated` event was not fired by P2).
   - Calls `twin_recalibration.recalibrate_for_calibration(athlete_id,
     activity_id, physiology_update_result)` → returns
     `CalibrationRecalibrationResult`.
   - Commits the session (single commit boundary — all writes land
     atomically: `AthletePhysiology` update, `PhysiologyMeasurement`
     records, `TwinState` insert, and all outbox events).
   - Returns `{"activity_id": str, "twin_state_id": str,
     "observations_count": int, "shifted": bool, "confidence_upgraded":
     bool}`.
   - The task is registered on the shared `procrastinate_app` instance.

7. [OWNER: Coder] Wire the pipeline: extend the `signal_clean` worker task
   in `app/worker/app.py` to defer `threshold_detection` after its commit.
   After `session.commit()` in `signal_clean`, if `result.created` is True
   (a `RawSensorStream` was created), defer the `threshold_detection` task
   with `activity_id=str(activity_uuid)`. Follow the exact same defer
   pattern used by `ActivityIngestionService._defer_signal_clean` — swallow
   defer failures after logging so the cleaning commit still succeeds. The
   defer happens AFTER the commit, not inside the transaction — this
   follows ADR-009's decoupling principle: a threshold detection failure
   must not roll back the already-committed cleaned stream.

8. [OWNER: Coder] Register the `threshold_detection` task name and any new
   result dataclasses (`CalibrationRecalibrationResult`) in
   `app/services/__init__.py` and ensure `TwinRecalibrationService` exports
   the new method. Update `app/services/__init__.py` imports to include
   `CalibrationRecalibrationResult`.

9. [OWNER: Test Architect] Generate test files and update the test manifest
   for Phase 2.3 P3. Tests include:
   - Unit tests for `insert_if_not_exists` deduplication logic (calibration
     supersedes activity_sync, duplicate calibration is skipped, duplicate
     activity_sync is skipped).
   - Unit tests for `confidence_level` derivation (min of LT1/LT2 HR
     prior_weight, thresholds 4.0/8.0, monotonicity).
   - Unit tests for `metric_confidence` derivation from per-parameter prior
     weights.
   - Unit tests for `twin_recalibrated` and `twin_confidence_upgraded`
     event firing.
   - Integration test for the `threshold_detection` worker task with mock
     services — verifies the full pipeline: detect → apply_observations →
     recalibrate_for_calibration → commit.
   - Integration test for the `signal_clean` → `threshold_detection`
     defer wiring.
   - Behaviour test: after uploading a calibration-eligible session with
     ≥3 intensity steps, `TwinState` shows updated `metric_confidence.lt2_hr`
     with `prior_weight > 0`.
   - Behaviour test: after sufficient sessions (4+ HR deflection-eligible),
     `metric_confidence.lt2_hr` transitions to "medium" when
     `prior_weight >= 4.0`.
   - Test manifest entry update: `tests/test-manifest/phase-2-3.yaml`.

## Event Contracts

| Event | Role | Payload Fields Required | Ordering |
|---|---|---|---|
| `twin_recalibrated` | PRODUCES | `athlete_id`, `twin_state_id`, `previous_twin_state_id` (null if first), `trigger` ("calibration"), `confidence_level`, `fitness_score`, `fatigue_score` | Fires after `TwinState` is inserted and `physiology_updated` (from P2) has been written to the outbox. Same transaction. |
| `twin_confidence_upgraded` | PRODUCES | `athlete_id`, `from_level`, `to_level`, `twin_state_id` | Fires after `twin_recalibrated` when `confidence_level` increased. Same transaction. Only fires on upgrade, not on every recalibration. |

**Event ordering within the `threshold_detection` transaction:**
1. `physiology_updated` (produced by `PhysiologyUpdateService` — Plan P2)
2. `twin_recalibrated` (produced by `TwinRecalibrationService` — this plan)
3. `twin_confidence_upgraded` (produced by `TwinRecalibrationService` — this
   plan, only if confidence increased)

All three events are written to the transactional outbox in insertion order
within the same transaction. The external publisher reads them in order
after the transaction commits.

## Pseudocode

```
# threshold_detection worker task
async def threshold_detection(*, activity_id: str, athlete_id: str):
    async with AsyncSessionLocal() as session:
        threshold_service = ThresholdDetectionService(session, ...)
        physiology_service = PhysiologyUpdateService(session, ...)
        twin_service = TwinRecalibrationService(session, ...)

        observations = await threshold_service.detect(
            athlete_id=uuid.UUID(athlete_id),
            activity_id=uuid.UUID(activity_id)
        )

        if not observations:
            await session.commit()  # nothing to do
            return {"activity_id": activity_id, "observations_count": 0,
                    "shifted": False, "twin_state_id": None}

        update_result = await physiology_service.apply_observations(
            athlete_id=uuid.UUID(athlete_id),
            observations=observations
        )

        if not update_result.shifted_parameters:
            await session.commit()  # measurements written, no recalibration
            return {"activity_id": activity_id,
                    "observations_count": len(observations),
                    "shifted": False, "twin_state_id": None}

        recalibration = await twin_service.recalibrate_for_calibration(
            athlete_id=uuid.UUID(athlete_id),
            activity_id=uuid.UUID(activity_id),
            physiology_result=update_result
        )

        await session.commit()

        return {
            "activity_id": activity_id,
            "observations_count": len(observations),
            "shifted": True,
            "twin_state_id": str(recalibration.twin_state.id),
            "confidence_upgraded": recalibration.confidence_upgraded
        }


# signal_clean task — extended
async def signal_clean(*, activity_id: str):
    async with AsyncSessionLocal() as session:
        service = SignalCleaningService(...)
        result = await service.clean(uuid.UUID(activity_id))
        await session.commit()

    # Defer threshold detection AFTER commit (ADR-009 pattern)
    if result.created:
        try:
            app.tasks["threshold_detection"].defer(
                activity_id=activity_id,
                athlete_id=str(result.athlete_id)  # if available
            )
        except Exception as exc:
            log_event(event="threshold_detection.enqueue.failure", ...)

    return {...}


# TwinRecalibrationService.recalibrate_for_calibration
async def recalibrate_for_calibration(self, athlete_id, activity_id,
                                       physiology_result):
    goal = await training_goals.get_active(athlete_id)
    fitness = await athlete_fitness.get_by_athlete_id(athlete_id)
    previous = await twin_states.get_latest(athlete_id)

    # Derive confidence from updated physiology
    new_confidence = _derive_confidence_level(physiology_result.physiology)
    old_confidence = previous.confidence_level if previous else LOW
    # Monotonic: keep the higher level
    confidence_level = max(new_confidence, old_confidence)

    # Per-metric monotonicity ratchet (ADR-011)
    computed_metric_confidence = _derive_metric_confidence(
        physiology_result.physiology
    )
    if previous and previous.metric_confidence:
        metric_confidence = {
            k: _max_level(
                previous.metric_confidence.get(k),
                computed_metric_confidence.get(k)
            )
            for k in computed_metric_confidence
        }
    else:
        metric_confidence = computed_metric_confidence

    # Build inline snapshot from updated physiology
    lt1_hr = _extract_param_value(physiology_result.physiology.lt1, "hr")
    lt2_hr = _extract_param_value(physiology_result.physiology.lt2, "hr")
    cp_watts = physiology_result.physiology.cp["value"] if physiology_result.physiology.cp else None

    new_state = TwinState(
        athlete_id=athlete_id,
        training_goal_id=goal.id,
        activity_id=activity_id,
        data_tier=previous.data_tier if previous else DataTier.TIER_3,
        confidence_level=confidence_level,
        trigger=TwinTrigger.CALIBRATION,
        model_version="v2-threshold-detection",
        fitness=fitness.aggregate["fitness"],
        fatigue=fitness.aggregate["fatigue"],
        form=fitness.aggregate["form"],
        lt1_hr_bpm=lt1_hr,
        lt2_hr_bpm=lt2_hr,
        cp_watts=cp_watts,
        # ... other threshold fields from previous or physiology
        readiness_level=previous.readiness_level if previous else GREEN,
        wellness_trend=previous.wellness_trend if previous else None,
        metric_confidence=metric_confidence
    )

    inserted = self._insert_if_not_exists(activity_id, new_state)

    # Fire events
    await events.publish("twin_recalibrated", ...)
    if confidence_level > old_confidence:
        await events.publish("twin_confidence_upgraded", ...)

    return CalibrationRecalibrationResult(
        twin_state=inserted,
        confidence_upgraded=confidence_level > old_confidence
    )
```

## Testing Requirements
- After uploading a calibration-eligible session with ≥3 intensity steps,
  `TwinState` shows updated `metric_confidence.lt2_hr` with
  `prior_weight > 0` (exit gate condition 1).
- After 4+ HR deflection-eligible sessions, `metric_confidence.lt2_hr`
  transitions to "medium" when `prior_weight >= 4.0` (exit gate condition 2).
- `AthletePhysiology.lt2.hr.value` shows posterior mean shifted from
  population default toward observed values (exit gate condition 3).
- For athletes with RR intervals, `training_rr_inflection` observations
  have weight 2.5 (exit gate condition 4).
- For athletes with power, `training_power_hr_ratio` observations
  contribute to CP estimate (exit gate condition 5).
- `insert_if_not_exists` skips when a calibration TwinState already exists
  for the activity.
- `insert_if_not_exists` inserts a calibration TwinState when an
  activity_sync TwinState already exists for the same activity.
- `twin_recalibrated` event fires for every new calibration TwinState.
- `twin_confidence_upgraded` fires only when confidence_level increases,
  not on every recalibration.
- The `threshold_detection` worker task commits atomically — all writes
  (AthletePhysiology, PhysiologyMeasurement, TwinState, events) land or
  none do.
- The `signal_clean` task defers `threshold_detection` only when
  `result.created` is True (a RawSensorStream was created).
- Confidence is monotonic — a TwinState's confidence_level is never lower
  than the previous TwinState's confidence_level.

## Notes

### Architecture Clarifications
- **Unique index `uq_twin_states_athlete_activity` must be dropped**: the
  current DB-level unique index on `(athlete_id, activity_id) WHERE
  activity_id IS NOT NULL` prevents the calibration TwinState from being
  inserted when an activity_sync TwinState already exists for the same
  activity. The architecture's Concurrency & Coordination section
  explicitly allows this dual-trigger scenario: "We have a fitness-only
  snapshot, but now we have calibration. Insert the calibration record (the
  fitness-only record remains as history)." The architecture's index
  strategy section marks this unique index as "optional, if DB-level
  enforcement desired" — the application-level `insert_if_not_exists` logic
  is the authoritative deduplication mechanism. The migration drops the
  unique index and replaces it with a non-unique index for the
  `get_by_activity` lookup.
- **Confidence threshold values**: use 4.0 (LOW→MEDIUM) and 8.0
  (MEDIUM→HIGH) from `confidence-model.md` and `evidence-mapping.md`. The
  `twin-state.md` document shows 15.0/40.0 in a code block marked "Example
  thresholds (finalize with data science)" — these are stale examples. The
  sub-phase document, confidence-model, evidence-mapping, and
  threshold-detection documents all agree on 4.0/8.0.
- **Event ordering**: within the `threshold_detection` transaction, events
  are written to the outbox in this order: `physiology_updated` (P2) →
  `twin_recalibrated` (P3) → `twin_confidence_upgraded` (P3, only on
  upgrade). The outbox publisher reads them in insertion order after
  commit. This ordering is important: `physiology_updated` must land before
  `twin_recalibrated` so downstream consumers that observe both events
  see the physiology change before the twin state change.

### Implementation Clarifications
- **`ThresholdDetectionService` must receive `PlannedSessionRepository` in
  the worker task**: P1's service constructor accepts
  `PlannedSessionRepository` as an optional parameter (defaults to `None`).
  The `threshold_detection` worker task (Step 6) MUST construct the service
  with a `PlannedSessionRepository` instance — without it, the natural
  training analysis algorithm (LT1 passive inference method 3) is silently
  skipped, and the athlete will never get LT1 observations from easy-run
  HR patterns. This is a production wiring requirement, not a test
  convenience.
- **`recalibrate_for_calibration` does NOT re-run the Banister update**: the
  Banister update was already applied during ingestion (the `activity_sync`
  recalibration in `ActivityIngestionService._run_ingestion_pipeline`).
  The calibration TwinState snapshots the current `AthleteFitness` values
  (which already include the Banister update) alongside the updated
  threshold values. The calibration trigger carries the complete snapshot
  (thresholds + fitness), while the prior activity_sync trigger carried
  only fitness.
- **`model_version` for calibration TwinStates**: use
  `"v2-threshold-detection"` to distinguish from the activity_sync
  `"v1-activity-sync"` model version. This enables reproducibility audits
  — a future reprocessing would know which pipeline version produced each
  TwinState.
- **`signal_clean` defer needs `athlete_id`**: the current `signal_clean`
  task signature only takes `activity_id`. The `threshold_detection` task
  needs both `activity_id` and `athlete_id`. The `signal_clean` task
  already has access to the activity (it loads it via
  `ActivityRepository`), so it can extract `athlete_id` from the activity
  row and pass it to the defer. Alternatively, the `threshold_detection`
  task can load the activity itself and extract `athlete_id` — this is
  simpler and avoids changing the `signal_clean` return shape. Prefer the
  latter: `threshold_detection` loads the activity and extracts
  `athlete_id` itself, so the defer only needs `activity_id`.

### Known Risks
- **Race condition: signal_clean and threshold_detection**: the
  `signal_clean` task defers `threshold_detection` after its commit. If
  the defer fails (queue outage), the threshold detection is never
  enqueued. The activity remains in a "cleaned but not threshold-detected"
  state. This is the same risk as `fit_ingest` deferring `signal_clean`
  (ADR-009). The mitigation is the same: swallow the defer failure after
  logging, and rely on Phase 2.4 backfill (Principle #14 reprocessing) to
  cover the missed enqueue. Do NOT retry the defer inside the
  `signal_clean` task — that would block the worker.
- **Dual TwinState for the same activity**: after dropping the unique
  index, `get_by_activity` may return multiple TwinStates for the same
  activity. The `insert_if_not_exists` logic must check ALL existing
  TwinStates for the activity, not just the first one returned. Use a
  query that checks for any existing TwinState with
  `trigger = 'calibration'` for this activity — if one exists, skip the
  insert. The `get_by_activity` method should be updated (or a new
  `get_by_activity_and_trigger` method added) to support this lookup.
- **Confidence monotonicity vs. prior_weight decay**: the `prior_weight`
  decays over time (42-day half-life), so it can drop below 4.0 or 8.0.
  The confidence LEVEL must not decrease — it ratchets upward only. The
  implementation must store the highest confidence level ever achieved
  and use `max(stored_level, computed_level)` when deriving the current
  level. The simplest approach: read the previous TwinState's
  `confidence_level` and `metric_confidence`, and keep the higher value
  for each metric. This is the "monotonic ratchet" — the confidence level
  can only increase, never decrease, even if the prior_weight decays.

## Coder Handoff Notes

### Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8 [OWNER: Coder] — includes migration
          generation (Step 1)
Skip:     Step 9 (Test Architect — tests)

### Coder Batches
Batch 1: Steps 1, 3          — Migration (drop unique index), deduplication logic
Batch 2: Steps 2, 4, 5       — recalibrate_for_calibration, event firing
Batch 3: Steps 6, 7, 8       — Worker task, pipeline wiring, registration

### Batch Success Criteria
Batch 1 complete when:
- Alembic migration exists and drops the `uq_twin_states_athlete_activity`
  unique index, replacing it with a non-unique index on
  `(athlete_id, activity_id)`
- `insert_if_not_exists` method exists on `TwinRecalibrationService` and
  correctly implements the deduplication logic: calibration supersedes
  activity_sync (inserts), duplicate calibration is skipped, duplicate
  non-calibration is skipped
- `get_by_activity` (or a new `get_by_activity_and_trigger`) supports
  checking for existing calibration TwinStates

Batch 2 assumes Batch 1 is complete. Batch 2 complete when:
- `recalibrate_for_calibration` method exists on `TwinRecalibrationService`
  and creates a TwinState with `trigger = calibration`, updated threshold
  inline snapshots, and `metric_confidence` from `AthletePhysiology`
- `confidence_level` is derived as `min(lt1.hr.prior_weight,
  lt2.hr.prior_weight)` using thresholds 4.0/8.0, with monotonic ratchet
  (never lower than previous TwinState)
- Per-metric `metric_confidence` also ratchets: each metric key uses
  `max(previous_twin_state.metric_confidence[metric], computed_level)` —
  a metric that previously reached MEDIUM stays MEDIUM even if `prior_weight`
  has decayed below 4.0 (ADR-011)
- `twin_recalibrated` event fires for every new calibration TwinState with
  correct payload
- `twin_confidence_upgraded` event fires only when confidence_level
  increases, with correct `from_level` and `to_level`
- Event ordering in the outbox: `physiology_updated` (from P2) →
  `twin_recalibrated` → `twin_confidence_upgraded`

Batch 3 assumes Batch 2 is complete. Batch 3 complete when:
- `threshold_detection` procrastinate task exists in `app/worker/app.py`
  and orchestrates: detect → apply_observations →
  recalibrate_for_calibration → commit
- Task returns early with no recalibration when observations list is empty
- Task returns early with no recalibration when no parameters shifted
- Task commits atomically — all writes land or none do
- `signal_clean` task defers `threshold_detection` after its commit when
  `result.created` is True
- Defer failures are swallowed after logging (same pattern as
  `_defer_signal_clean`)
- `CalibrationRecalibrationResult` is registered in `app/services/__init__.py`

### Context Needed
Step 1:
  Primary:    `app/models/twin_state.py` (the `uq_twin_states_athlete_activity`
              index definition to drop),
              `alembic/versions/84d65f756e09_widen_cleaning_pipeline_version_columns_.py`
              (latest migration — down_revision for the new migration)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 2:
  Primary:    `app/services/twin_recalibration_service.py` (existing
              `recalibrate` method — the new method follows the same
              construction pattern but with calibration trigger),
              `app/models/twin_state.py` (TwinState fields to populate),
              output of Plan P2 (`PhysiologyUpdateResult` dataclass —
              carries updated physiology, shifted parameters,
              metric_confidence, transitions),
              `docs/adr/011-confidence-monotonicity-ratchet-location.md`
              (DECISION — the per-metric ratchet lives here, not in P2)
  Secondary:  `app/services/onboarding_service.py` (how `_bootstrap_signal`
              and `_bootstrap_metric_confidence` shape the JSONB — the
              calibration TwinState must use the same shapes)
  Fallback:   —
  Forbidden:  —
Step 3:
  Primary:    `docs/architecture/01-entities/twin-state.md` (Concurrency &
              Coordination section — the exact deduplication logic),
              `app/repositories/twin_state_repository.py` (`get_by_activity`
              method)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 4:
  Primary:    `app/services/event_publisher.py` (EventPublisher.publish
              pattern),
              `app/services/activity_ingestion_service.py` (existing event
              publishing examples),
              `docs/architecture/00-foundations/event-catalogue.md`
              (`twin_recalibrated` event payload)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 5:
  Primary:    `docs/architecture/00-foundations/event-catalogue.md`
              (`twin_confidence_upgraded` event payload),
              output of Step 4 (event publishing pattern)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 6:
  Primary:    `app/worker/app.py` (existing `signal_clean` and `fit_ingest`
              task patterns — the new task follows the same structure),
              output of Plan P1 (`ThresholdDetectionService` constructor
              and `detect` method — note: must pass
              `PlannedSessionRepository` to the constructor for natural
              training analysis to run),
              output of Plan P2 (`PhysiologyUpdateService` constructor and
              `apply_observations` method),
              output of Step 2 (`recalibrate_for_calibration` method)
  Secondary:  `app/services/activity_ingestion_service.py`
              (`_defer_signal_clean` — defer pattern reference)
  Fallback:   —
  Forbidden:  —
Step 7:
  Primary:    `app/worker/app.py` (the `signal_clean` task function —
              extend it to defer `threshold_detection` after commit),
              `app/services/activity_ingestion_service.py`
              (`_defer_signal_clean` — the exact defer pattern to follow),
              `docs/adr/009-signal-cleaning-as-decoupled-async-task.md`
              (decoupling principle: defer after commit, swallow failures)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 8:
  Primary:    `app/services/__init__.py` (registration pattern),
              `app/services/twin_recalibration_service.py` (export the new
              result dataclass)
  Secondary:  —
  Fallback:   —
  Forbidden:  —

(This is everything relevant to the steps above. Primary items are fetched
together in Pre-Flight Step 3; Secondary and Fallback are requested only on
demand.)

### ADR Constraint

**ADR-011** (`docs/adr/011-confidence-monotonicity-ratchet-location.md`)
imposes a constraint the coder must not violate: the per-metric confidence
monotonicity ratchet (`max(stored_level, computed_level)` per metric) is
enforced in `TwinRecalibrationService.recalibrate_for_calibration` (this
plan, Step 2), NOT in `PhysiologyUpdateService` (Plan P2). P2's
`PhysiologyUpdateResult.metric_confidence` is the raw computed level from
current `prior_weight` — it can be lower than the previous TwinState's
stored level if `prior_weight` has decayed. This is expected and correct:
P3 reads the previous TwinState via `TwinStateRepository.get_latest` and
applies `max(previous.metric_confidence[metric], computed[metric])` per
metric before writing the new TwinState. Do NOT add `TwinStateRepository`
as a dependency of `PhysiologyUpdateService` to try to enforce the ratchet
in P2 — that crosses an ownership boundary. The ratchet is a TwinState-level
concern (historical audit trail), not a physiology-level concern (operational
current state).