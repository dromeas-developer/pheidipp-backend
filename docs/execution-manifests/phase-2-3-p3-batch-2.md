# Execution Manifest — Phase-2.3-P3 — Batch 2

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md
Batch:             2 of 3
Manifest Version:  v1
Generated At:      2026-07-15T00:00:00Z
Source Plan Lines: 723
Manifest Lines:    211

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Batch 2 extends `TwinRecalibrationService` with the
`recalibrate_for_calibration` method that creates a calibration-triggered
`TwinState` with updated threshold snapshots, `confidence_level`, and
`metric_confidence`, and implements `twin_recalibrated` and
`twin_confidence_upgraded` event firing.

## Preconditions
Batches 1 through 1 are complete; their Batch Success Criteria hold.

## Steps
### Step 2 — [OWNER: Coder] Extend `TwinRecalibrationService` with a
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

### Step 4 — [OWNER: Coder] Implement `twin_recalibrated` event firing. When a new
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

### Step 5 — [OWNER: Coder] Implement `twin_confidence_upgraded` event firing. When
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

## Context Needed
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

## Relevant Architecture Contracts
- `00-foundations/event-catalogue.md` → `twin_recalibrated` — PRODUCES
- `00-foundations/event-catalogue.md` → `twin_confidence_upgraded` — PRODUCES
- `docs/adr/011-confidence-monotonicity-ratchet-location.md` — DECISION
  (the per-metric confidence ratchet `max(stored_level, computed_level)` is
  enforced in this plan's `TwinRecalibrationService`, NOT in P2's
  `PhysiologyUpdateService`. P2 outputs the raw computed level; P3 reads the
  previous TwinState and applies the ratchet per metric before inserting the
  new TwinState. Read before implementing Step 2.)

## Relevant Invariants
*(Omitted — no invariant is cited by name or ID in this batch's Context Needed.)*

## Relevant Event Contracts
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

## Relevant Notes
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
- **`recalibrate_for_calibration` does NOT re-run the Banister update**: the
  Banister update was already applied during ingestion (the `activity_sync`
  recalibration in `ActivityIngestionService._run_ingestion_pipeline`).
  The calibration TwinState snapshots the current `AthleteFitness` values
  (which already include the Banister update) alongside the updated
  threshold values. The calibration trigger carries the complete snapshot
  (thresholds + fitness), while the prior activity_sync trigger carried
  only fitness.
- **Confidence monotonicity vs. prior_weight decay**: the `prior_weight`
  decays over time (42-day half-life), so it can drop below 4.0 or 8.0.
  The confidence LEVEL must not decrease — it ratchets upward only. The
  implementation must store the highest confidence level ever achieved
  and use `max(stored_level, computed_level)` when deriving the current
  level. The simplest approach: read the previous TwinState's
  `confidence_level` and `metric_confidence`, and keep the higher value
  for each metric. This is the "monotonic ratchet" — the confidence level
  can only increase, never decrease, even if the prior_weight decays.

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
- [EXISTING — modified] `app/services/twin_recalibration_service.py`
- [EXISTING — reference only] `app/models/twin_state.py`
- [EXISTING — reference only] `docs/adr/011-confidence-monotonicity-ratchet-location.md`
- [EXISTING — reference only] `app/services/onboarding_service.py`
- [EXISTING — reference only] `app/services/event_publisher.py`
- [EXISTING — reference only] `app/services/activity_ingestion_service.py`
- [EXISTING — reference only] `docs/architecture/00-foundations/event-catalogue.md`

## Batch Success Criteria
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
