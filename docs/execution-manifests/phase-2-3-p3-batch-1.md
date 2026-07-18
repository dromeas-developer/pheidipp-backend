# Execution Manifest — Phase-2.3-P3 — Batch 1

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md
Batch:             1 of 3
Manifest Version:  v1
Generated At:      2026-07-15T00:00:00Z
Source Plan Lines: 723
Manifest Lines:    178

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Enable the calibration trigger by dropping the unique index that prevents
dual-trigger TwinStates and implementing the application-level
deduplication logic that ensures correct coexistence of calibration and
activity_sync TwinStates for the same activity.

## Preconditions
No preconditions — this is the first batch.

## Steps
### Step 1 — [OWNER: Coder] Generate Alembic migration to drop the
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

### Step 3 — [OWNER: Coder] Implement `insert_if_not_exists` deduplication logic on
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

## Context Needed
Step 1:
  Primary:    `app/models/twin_state.py` (the `uq_twin_states_athlete_activity`
              index definition to drop),
              `alembic/versions/84d65f756e09_widen_cleaning_pipeline_version_columns_.py`
              (latest migration — down_revision for the new migration)
  Secondary:  —
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

## Relevant Architecture Contracts
- `01-entities/twin-state.md` — IMPLEMENTS (calibration trigger,
  append-only insert, deduplication, confidence_level derivation,
  metric_confidence, event production)

## Relevant Invariants
- "Multiple TwinStates per day are possible (e.g., `activity_sync` followed
  by `wellness_update`), but only **one** TwinState per `activity_id`. See
  'Concurrency & Coordination' for deduplication logic." (twin-state
  invariant — clarified: the concurrency section allows a calibration
  TwinState to coexist with a prior activity_sync TwinState for the same
  activity_id; the deduplication is application-level, not DB-level)

## Relevant Event Contracts
*(Omitted — no step in this batch touches an event.)*

## Relevant Notes
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
- **Dual TwinState for the same activity**: after dropping the unique
  index, `get_by_activity` may return multiple TwinStates for the same
  activity. The `insert_if_not_exists` logic must check ALL existing
  TwinStates for the activity, not just the first one returned. Use a
  query that checks for any existing TwinState with
  `trigger = 'calibration'` for this activity — if one exists, skip the
  insert. The `get_by_activity` method should be updated (or a new
  `get_by_activity_and_trigger` method added) to support this lookup.

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
- [NEW] `alembic/versions/phase_2_3_p3_drop_twin_states_activity_unique.py`
- [EXISTING — modified] `app/services/twin_recalibration_service.py`
- [EXISTING — modified] `app/repositories/twin_state_repository.py`
- [EXISTING — reference only] `app/models/twin_state.py`
- [EXISTING — reference only] `alembic/versions/84d65f756e09_widen_cleaning_pipeline_version_columns_.py`
- [EXISTING — reference only] `docs/architecture/01-entities/twin-state.md`

## Batch Success Criteria
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
