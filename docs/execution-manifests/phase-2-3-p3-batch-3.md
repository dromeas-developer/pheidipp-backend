# Execution Manifest — Phase-2.3-P3 — Batch 3

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md
Batch:             3 of 3
Manifest Version:  v1
Generated At:      2026-07-15T00:00:00Z
Source Plan Lines: 723
Manifest Lines:    189

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Batch 3 creates the `threshold_detection` procrastinate worker task that
orchestrates the full detection → physiology update → recalibration
pipeline in a single transaction, wires `signal_clean` to defer it after
commit, and registers the new task and dataclasses.

## Preconditions
Batches 1 through 2 are complete; their Batch Success Criteria hold.

## Steps
### Step 6 — [OWNER: Coder] Create the `threshold_detection` procrastinate worker task
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

### Step 7 — [OWNER: Coder] Wire the pipeline: extend the `signal_clean` worker task
   in `app/worker/app.py` to defer `threshold_detection` after its commit.
   After `session.commit()` in `signal_clean`, if `result.created` is True
   (a `RawSensorStream` was created), defer the `threshold_detection` task
   with `activity_id=str(activity_uuid)`. Follow the exact same defer
   pattern used by `ActivityIngestionService._defer_signal_clean` — swallow
   defer failures after logging so the cleaning commit still succeeds. The
   defer happens AFTER the commit, not inside the transaction — this
   follows ADR-009's decoupling principle: a threshold detection failure
   must not roll back the already-committed cleaned stream.

### Step 8 — [OWNER: Coder] Register the `threshold_detection` task name and any new
   result dataclasses (`CalibrationRecalibrationResult`) in
   `app/services/__init__.py` and ensure `TwinRecalibrationService` exports
   the new method. Update `app/services/__init__.py` imports to include
   `CalibrationRecalibrationResult`.

## Context Needed
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

## Relevant Architecture Contracts
- `docs/adr/009-signal-cleaning-as-decoupled-async-task.md` — DEPENDS ON
  (pipeline decoupling pattern: signal_clean commits, then defers
  threshold_detection)

## Relevant Invariants
*(Omitted — no invariant is cited by name or ID in this batch's Context Needed.)*

## Relevant Event Contracts
*(Omitted — no step in this batch explicitly states it fires, consumes, or directly touches an event.)*

## Relevant Notes
- **Event ordering**: within the `threshold_detection` transaction, events
  are written to the outbox in this order: `physiology_updated` (P2) →
  `twin_recalibrated` (P3) → `twin_confidence_upgraded` (P3, only on
  upgrade). The outbox publisher reads them in insertion order after
  commit. This ordering is important: `physiology_updated` must land before
  `twin_recalibrated` so downstream consumers that observe both events
  see the physiology change before the twin state change.
- **`ThresholdDetectionService` must receive `PlannedSessionRepository` in
  the worker task**: P1's service constructor accepts
  `PlannedSessionRepository` as an optional parameter (defaults to `None`).
  The `threshold_detection` worker task (Step 6) MUST construct the service
  with a `PlannedSessionRepository` instance — without it, the natural
  training analysis algorithm (LT1 passive inference method 3) is silently
  skipped, and the athlete will never get LT1 observations from easy-run
  HR patterns. This is a production wiring requirement, not a test
  convenience.
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
- **Race condition: signal_clean and threshold_detection**: the
  `signal_clean` task defers `threshold_detection` after its commit. If
  the defer fails (queue outage), the threshold detection is never
  enqueued. The activity remains in a "cleaned but not threshold-detected"
  state. This is the same risk as `fit_ingest` deferring `signal_clean`
  (ADR-009). The mitigation is the same: swallow the defer failure after
  logging, and rely on Phase 2.4 backfill (Principle #14 reprocessing) to
  cover the missed enqueue. Do NOT retry the defer inside the
  `signal_clean` task — that would block the worker.

## Relevant Pseudocode
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

## Files Expected To Change
- [EXISTING — modified] `app/worker/app.py`
- [EXISTING — modified] `app/services/__init__.py`
- [EXISTING — reference only] `app/services/twin_recalibration_service.py`
- [EXISTING — reference only] `app/services/activity_ingestion_service.py`
- [EXISTING — reference only] `docs/adr/009-signal-cleaning-as-decoupled-async-task.md`

## Batch Success Criteria
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
