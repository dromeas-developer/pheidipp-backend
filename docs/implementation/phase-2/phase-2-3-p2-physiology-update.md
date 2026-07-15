# Implementation Plan: Phase-2.3 — Physiology Update Service (Bayesian Update)
## Plan ID: Phase-2.3-P2

## Sub-Phase Reference
Sub-Phase ID: Phase-2.3
Sub-Phase Title: Threshold Detection & Physiology Update

## Objective
Implement the `PhysiologyUpdateService` — the Bayesian update engine that
consumes threshold observations from `ThresholdDetectionService` (Plan P1),
applies the posterior update formula to `AthletePhysiology` in place, writes
append-only `PhysiologyMeasurement` records, and fires the
`physiology_updated` event when the posterior shifts by > 1 bpm. This plan
also implements confidence transition detection (LOW → MEDIUM at evidence
weight ≥ 4.0, MEDIUM → HIGH at ≥ 8.0) so `TwinRecalibrationService` (Plan P3)
can create `TwinState` records with correct `metric_confidence`.

## Scope
- `PhysiologyUpdateService` implementing the Bayesian update formula from
  `physiology-update.md`:
  - Prior decay: `decay_factor = exp(-days_since_last / 42)`
  - Posterior mean: weighted average of decayed prior and new observation
  - Posterior uncertainty: `σ_posterior = max(σ_prior * √(prior_weight /
    total_weight), 0.5)`
  - Dominant source derivation: observation dominates when its weight exceeds
    decayed prior weight
- Observation weight application per `evidence-mapping.md` (weights are
  carried on `ThresholdObservation` from Plan P1 — this service reads them,
  does not re-derive them)
- `AthletePhysiologyRepository` extension: `update_in_place` method for
  mutating the JSONB posterior state columns (`lt1`, `lt2`, `cp`, `max_hr`)
- `PhysiologyMeasurement` record writing (append-only) for every observation
  — the measurement record is always written regardless of whether the
  posterior shifts
- `physiology_updated` event firing via `EventPublisher` when any parameter
  posterior shifts by > 1 bpm (LT1/LT2 HR) or > 1 watt (CP)
- Confidence transition detection: compute per-metric confidence level from
  `prior_weight` using thresholds 4.0 (MEDIUM) and 8.0 (HIGH)
- Idempotency: duplicate observation detection (same `parameter`,
  `observed_value`, `measurement_date`, `source`, `activity_id`) — the
  `PhysiologyMeasurement` is still written but the posterior is not shifted
  and no event fires

## Out Of Scope
- `ThresholdDetectionService` (Plan P1 — produces observations)
- `TwinRecalibrationService` calibration trigger extension (Plan P3)
- Worker task and pipeline wiring (Plan P3)
- `twin_recalibrated` and `twin_confidence_upgraded` events (Plan P3)
- Lab test and field test manual ingestion flows (deferred per sub-phase)
- API endpoints for `GET/POST /physiology/measurements` (deferred — sub-phase
  focuses on training-derived pipeline)
- `max_hr` update from observed maximum HR across sessions (the architecture
  mentions this, but the sub-phase capabilities focus on LT1/LT2/CP —
  `max_hr` update from sessions is a natural extension but not explicitly
  required by the exit gate)

## Architecture Contracts
- `02-computations/physiology-update.md` — IMPLEMENTS (Bayesian update
  formula, observation weights, prior decay, ingestion flow)
- `02-computations/evidence-mapping.md` — DEPENDS ON (evidence source →
  metric mapping; weights are carried on `ThresholdObservation` from P1)
- `01-entities/athlete-physiology.md` — IMPLEMENTS (mutable posterior
  updates, `PhysiologyMeasurement` append-only writes, `physiology_updated`
  event production)
- `00-foundations/confidence-model.md` — DEPENDS ON (evidence weight
  thresholds 4.0/8.0 for confidence transitions; per-metric confidence
  derivation)
- `00-foundations/event-catalogue.md` → `physiology_updated` — PRODUCES
- `02-computations/threshold-detection.md` — DEPENDS ON (Plan P1
  `ThresholdObservation` data contract)
- `docs/adr/011-confidence-monotonicity-ratchet-location.md` — DECISION
  (the per-metric confidence monotonicity ratchet is NOT enforced in this
  plan — it is enforced in P3's `TwinRecalibrationService`. This plan outputs
  the raw computed `metric_confidence` from current `prior_weight`; P3
  applies `max(stored_level, computed_level)` per metric. Read before
  implementing Step 8.)

## Invariants
- "One `AthletePhysiology` record per athlete. **Mutable current-state
  entity** — posterior estimates are updated in place on each threshold
  detection event." (athlete-physiology invariant)
- "`physiology_updated` event fires only when posterior shifts by > 1 bpm
  (to avoid noise)" (sub-phase invariant)
- "Bayesian update with 42-day prior decay for evidence staleness"
  (sub-phase invariant)
- "Confidence is monotonic (only increases, never decreases)" (sub-phase
  invariant)
- "Observation thresholds: 4.0 for LOW→MEDIUM, 8.0 for MEDIUM→HIGH (per
  metric)" (sub-phase invariant)
- "Per-metric evidence accumulation — a session contributes to specific
  metrics only" (sub-phase invariant)
- "The `PhysiologyMeasurement` record is always written regardless — it is
  the complete observation history." (physiology-update.md)
- "`cp` and `vo2max` are null until a qualifying observation is made. They
  are never bootstrapped from questionnaire estimates." (athlete-physiology
  invariant)
- "`prior_weight` decays over time via the formula above. After ~3 years
  with no new observations, the prior weight approaches zero."
  (athlete-physiology invariant)

## Implementation Steps

1. [OWNER: Coder] Extend `AthletePhysiologyRepository` with an
   `update_in_place` method. The method takes `athlete_id` and the updated
   JSONB column values (`lt1`, `lt2`, `cp`, `max_hr` as dicts) and writes
   them to the existing row. The method flushes but does not commit — the
   caller (worker task in Plan P3) owns the commit boundary. The method
   must NOT create a new row — it mutates the existing one. Follow the
   existing `add` method's flush pattern.

2. [OWNER: Coder] Create `PhysiologyUpdateService` in
   `app/services/physiology_update_service.py`. The service is constructed
   with an `AsyncSession`, `AthletePhysiologyRepository`,
   `PhysiologyMeasurementRepository`, and an optional `EventPublisher`.
   The primary entry point is:
   ```
   async def apply_observations(
       self, athlete_id: uuid.UUID,
       observations: list[ThresholdObservation]
   ) -> PhysiologyUpdateResult
   ```
   The service:
   - Loads the current `AthletePhysiology` row for the athlete.
   - For each observation, applies the Bayesian update (Step 3), writes a
     `PhysiologyMeasurement` record (Step 4), and tracks which parameters
     shifted by > 1 unit (Step 5).
   - Updates `AthletePhysiology` in place with all new posterior values
     (Step 6).
   - Fires `physiology_updated` event if any parameter shifted by > 1 unit
     (Step 7).
   - Returns a `PhysiologyUpdateResult` carrying: the updated
     `AthletePhysiology` row, the list of parameters that shifted, the
     per-metric confidence levels after the update, and whether any
     confidence transition occurred.

3. [OWNER: Coder] Implement the Bayesian update formula as a pure function
   on `PhysiologyUpdateService` (or as a module-level helper for unit-test
   access). Per `physiology-update.md`:
   ```
   bayesian_update(current: PhysiologyParameterState, observation) ->
       PhysiologyParameterState
   ```
   - `days_since_last = days_between(current.last_observation_date,
     observation.date)`
   - `decay_factor = exp(-days_since_last / 42)`
   - `decayed_weight = current.prior_weight * decay_factor`
   - `new_total_weight = decayed_weight + observation.weight`
   - `posterior_mean = (current.value * decayed_weight +
     observation.value * observation.weight) / new_total_weight`
   - `posterior_uncertainty = max(current.uncertainty *
     sqrt(decayed_weight / new_total_weight), 0.5)`
   - `dominant_source = observation.source if observation.weight >
     decayed_weight else current.dominant_source`
   - `last_observation_date = observation.date`
   The function operates on the JSONB `PhysiologyParameterState` dict shape
   (`{value, uncertainty, prior_weight, dominant_source,
   last_observation_date}`) — the same shape bootstrapped by
   `OnboardingService._bootstrap_signal`.

4. [OWNER: Coder] Implement `PhysiologyMeasurement` record writing. For
   each observation, create a `PhysiologyMeasurement` row with:
   `athlete_id`, `activity_id` (from the observation), `parameter`,
   `observed_value`, `source`, `measurement_date` (from the observation),
   `algorithm_used`, `confidence_weight`, `raw_data_reference` (null for
   training-derived), `notes` (null for training-derived). Insert via
   `PhysiologyMeasurementRepository.insert`. The measurement is ALWAYS
   written, even if the posterior does not shift — it is the complete
   observation history.

5. [OWNER: Coder] Implement posterior shift detection. After applying the
   Bayesian update to a parameter, compare the new posterior mean to the
   old posterior mean. For HR parameters (LT1_HR, LT2_HR, MAX_HR): shift
   is `abs(new_value - old_value)`. For CP: shift is
   `abs(new_value - old_value)` in watts. The parameter "shifted" if the
   shift exceeds 1.0 (bpm for HR, watts for CP). Track all shifted
   parameters in a list for the event payload and the result.

6. [OWNER: Coder] Implement `AthletePhysiology` in-place update. After all
   observations are processed, write the updated JSONB columns back to the
   `AthletePhysiology` row. The JSONB shape for `lt1` and `lt2` is
   `{hr: {...}, power: {...}, pace: {...}}` where each sub-dict is a
   `PhysiologyParameterState` or null. For `cp`, the JSONB is a single
   `PhysiologyParameterState` or null. For `max_hr`, same as `cp`. Use
   `AthletePhysiologyRepository.update_in_place` (Step 1). Only update
   columns that have changed — leave unchanged columns untouched to
   minimise write amplification.

7. [OWNER: Coder] Implement `physiology_updated` event firing. When any
   parameter shifted by > 1 unit, fire the event via `EventPublisher`:
   ```
   event_type = "physiology_updated"
   payload = {
       "athlete_id": str(athlete_id),
       "parameters_updated": [param.value for param in shifted_parameters],
       "dominant_sources": {param: source.value for each updated param},
       "prior_weights": {param: new_prior_weight for each updated param}
   }
   ```
   The event is written to the transactional outbox (SystemEvent +
   SystemEventOutbox) in the same transaction as the `AthletePhysiology`
   update — following the existing `EventPublisher` pattern used by
   `ActivityIngestionService` and `OnboardingService`. The event does NOT
   fire when no parameters shifted — this avoids noise from minor
   fluctuations.

8. [OWNER: Coder] Implement confidence transition detection. After all
   observations are processed, compute the per-metric confidence level for
   each parameter from its `prior_weight`:
   - `prior_weight >= 8.0` → HIGH
   - `prior_weight >= 4.0` → MEDIUM
   - `prior_weight < 4.0` → LOW
   Return the per-metric confidence dict in the `PhysiologyUpdateResult`.
   Also detect whether any metric transitioned (was LOW and is now MEDIUM,
   or was MEDIUM and is now HIGH) — this is used by Plan P3's
   `TwinRecalibrationService` to fire `twin_confidence_upgraded`. This
   service computes the raw confidence level from current `prior_weight` —
   it does NOT enforce the monotonicity ratchet. The ratchet
   (`max(stored_level, computed_level)` per metric) is enforced in P3's
   `TwinRecalibrationService`, which reads the previous TwinState and keeps
   the higher level. See ADR-011. P2's `metric_confidence` output CAN be
   lower than the previous TwinState's stored level after a long gap — this
   is expected and correct; P3 applies the ratchet before writing the new
   TwinState.

9. [OWNER: Coder] Implement idempotency for duplicate observations. Before
   applying the Bayesian update, check if a `PhysiologyMeasurement` already
   exists with the same `(athlete_id, activity_id, parameter, source,
   measurement_date, observed_value)`. If it does, the observation is a
   duplicate — still write the `PhysiologyMeasurement` record (for audit
   completeness) but do NOT apply the Bayesian update and do NOT fire the
   event. This follows the architecture's idempotency contract: "Submitting
   identical lab test measurements twice creates two PhysiologyMeasurement
   records but shifts the posterior only once from the first."

10. [OWNER: Coder] Create `PhysiologyUpdateResult` dataclass carrying:
    - `physiology: AthletePhysiology` — the updated row
    - `shifted_parameters: list[PhysiologyParameter]` — parameters that
      shifted > 1 unit
    - `metric_confidence: dict` — per-metric confidence levels after update
      (same shape as `TwinState.metric_confidence`)
    - `confidence_transitions: dict` — parameters that transitioned
      (`{parameter: (from_level, to_level)}`)
    - `measurements_written: int` — count of `PhysiologyMeasurement` records

11. [OWNER: Coder] Register `PhysiologyUpdateService` and
    `PhysiologyUpdateResult` in `app/services/__init__.py`. Export the
    service class, the result dataclass, and any error classes.

12. [OWNER: Test Architect] Generate test files and update the test manifest
    for Phase 2.3 P2. Tests include:
    - Unit tests for `bayesian_update` pure function with known inputs and
      expected outputs (verify posterior mean, uncertainty, prior_weight,
      dominant_source, decay factor).
    - Unit tests for posterior shift detection (> 1 bpm threshold).
    - Unit tests for confidence transition detection (4.0 and 8.0
      thresholds, monotonicity).
    - Unit tests for idempotency (duplicate observation does not shift
      posterior).
    - Integration test for `PhysiologyUpdateService.apply_observations()`
      with mock observations — verifies `AthletePhysiology` is mutated in
      place, `PhysiologyMeasurement` records are written, and
      `physiology_updated` event fires only when posterior shifts > 1 unit.
    - Test manifest entry update: `tests/test-manifest/phase-2-3.yaml`.

## Event Contracts
| Event | Role | Payload Fields Required | Ordering |
|---|---|---|---|
| `physiology_updated` | PRODUCES | `athlete_id`, `parameters_updated` (list of parameter names), `dominant_sources` (dict parameter→source), `prior_weights` (dict parameter→weight) | Fires after `AthletePhysiology` is updated in place and `PhysiologyMeasurement` records are written, all in the same transaction. Fires only when at least one parameter posterior shifted by > 1 unit. |

## Pseudocode

```
PhysiologyUpdateService.apply_observations(athlete_id, observations):
    physiology = athlete_physiology.get_by_athlete_id(athlete_id)
    if physiology is None:
        raise MissingAthletePhysiologyError(athlete_id)

    shifted_parameters = []
    updated_states = {}  # parameter -> new PhysiologyParameterState
    measurements_written = 0
    old_confidence = _compute_metric_confidence(physiology)

    for obs in observations:
        # Idempotency check
        if _is_duplicate(athlete_id, obs):
            _write_measurement(obs)  # still write for audit
            measurements_written += 1
            continue

        # Get current parameter state from JSONB
        current_state = _get_parameter_state(physiology, obs.parameter)
        if current_state is None:
            # First observation for this parameter (e.g., CP)
            current_state = _init_null_parameter_state()

        # Apply Bayesian update
        new_state = bayesian_update(current_state, obs)
        updated_states[obs.parameter] = new_state

        # Write measurement record (always)
        _write_measurement(obs)
        measurements_written += 1

        # Check shift
        shift = abs(new_state["value"] - current_state["value"])
        if shift > 1.0:
            shifted_parameters.append(obs.parameter)

    # Update AthletePhysiology in place
    _apply_updated_states(physiology, updated_states)
    athlete_physiology.update_in_place(athlete_id, physiology)

    # Compute new confidence
    new_confidence = _compute_metric_confidence(physiology)
    transitions = _detect_transitions(old_confidence, new_confidence)

    # Fire event if any parameter shifted
    if shifted_parameters:
        events.publish(
            event_type="physiology_updated",
            athlete_id=athlete_id,
            payload={
                "athlete_id": str(athlete_id),
                "parameters_updated": [p.value for p in shifted_parameters],
                "dominant_sources": {...},
                "prior_weights": {...},
            }
        )

    return PhysiologyUpdateResult(
        physiology=physiology,
        shifted_parameters=shifted_parameters,
        metric_confidence=new_confidence,
        confidence_transitions=transitions,
        measurements_written=measurements_written
    )


bayesian_update(current, observation):
    days_since_last = days_between(
        current["last_observation_date"], observation.date
    )
    decay_factor = exp(-days_since_last / 42)
    decayed_weight = current["prior_weight"] * decay_factor
    new_total_weight = decayed_weight + observation.weight
    posterior_mean = (
        current["value"] * decayed_weight +
        observation.value * observation.weight
    ) / new_total_weight
    posterior_uncertainty = max(
        current["uncertainty"] * sqrt(decayed_weight / new_total_weight),
        0.5
    )
    dominant_source = (
        observation.source.value
        if observation.weight > decayed_weight
        else current["dominant_source"]
    )
    return {
        "value": posterior_mean,
        "uncertainty": posterior_uncertainty,
        "prior_weight": new_total_weight,
        "dominant_source": dominant_source,
        "last_observation_date": observation.date.isoformat()
    }


_compute_metric_confidence(physiology):
    def level(weight):
        if weight >= 8.0: return "high"
        if weight >= 4.0: return "medium"
        return "low"
    return {
        "lt1_hr": level(physiology.lt1["hr"]["prior_weight"]),
        "lt1_power": level(physiology.lt1["power"]["prior_weight"])
            if physiology.lt1.get("power") else None,
        "lt1_pace": ...,
        "lt2_hr": level(physiology.lt2["hr"]["prior_weight"]),
        "lt2_power": ...,
        "lt2_pace": ...,
        "cp": level(physiology.cp["prior_weight"])
            if physiology.cp else None,
    }
```

## Testing Requirements
- Given a current `PhysiologyParameterState` with value=165, prior_weight=0.5,
  uncertainty=1.0, and an observation with value=170, weight=1.0, the
  `bayesian_update` function returns a posterior with value between 165 and
  170 (weighted toward the prior due to low observation weight), prior_weight
  = 1.5 (0.5 decayed + 1.0 new), and uncertainty < 1.0.
- Given an observation that shifts the posterior by > 1 bpm,
  `apply_observations` fires `physiology_updated` with the shifted parameter
  in `parameters_updated`.
- Given an observation that shifts the posterior by < 1 bpm,
  `apply_observations` does NOT fire `physiology_updated` but still writes
  the `PhysiologyMeasurement` record.
- Given 4 observations with weight 1.0 each for `LT2_HR`, the
  `prior_weight` reaches 4.0 and the confidence transitions from LOW to
  MEDIUM.
- Given 8 observations with weight 1.0 each for `LT2_HR`, the
  `prior_weight` reaches 8.0 and the confidence transitions from MEDIUM to
  HIGH.
- Given a duplicate observation (same parameter, value, date, source,
  activity_id), `apply_observations` writes the measurement but does NOT
  shift the posterior and does NOT fire the event.
- `AthletePhysiologyRepository.update_in_place` mutates the existing row
  without creating a new one.
- For athletes with RR observations (weight 2.5), the posterior shifts
  faster than with HR deflection observations (weight 1.0) — 2 RR
  observations reach MEDIUM confidence (2 × 2.5 = 5.0 ≥ 4.0).
- For athletes with power observations, `CP` parameter is updated from null
  to a non-null `PhysiologyParameterState` on the first qualifying
  observation.

## Notes

### Architecture Clarifications
- **Confidence threshold values**: the `TwinState` architecture document shows
  example thresholds of 15.0/40.0 in a code block marked "Example thresholds
  (finalize with data science)." The authoritative thresholds are 4.0
  (LOW→MEDIUM) and 8.0 (MEDIUM→HIGH) from `confidence-model.md`,
  `evidence-mapping.md`, `threshold-detection.md`, and the sub-phase
  document. Use 4.0/8.0 — the 15.0/40.0 values are a stale example that was
  never updated.
- **Confidence is monotonic — but the ratchet is enforced in P3, not P2**:
  the `prior_weight` decays over time (42-day half-life), which means it can
  drop below a threshold. The confidence LEVEL (LOW/MEDIUM/HIGH) never
  decreases — it ratchets upward only. If `prior_weight` drops below 4.0 due
  to decay, a MEDIUM-confidence metric stays MEDIUM. The decay affects
  recommendation strength (wider ranges, more conservative coaching), not the
  confidence enum. **However, this service (P2) does NOT enforce the ratchet.**
  P2 computes `metric_confidence` purely from current `prior_weight` — this
  is the "computed level" and it CAN be lower than the previous TwinState's
  stored level after a long gap. The monotonicity ratchet
  (`max(stored_level, computed_level)` per metric) is enforced in P3's
  `TwinRecalibrationService.recalibrate_for_calibration`, which reads the
  previous TwinState and applies the ratchet before writing the new TwinState.
  See ADR-011 (`docs/adr/011-confidence-monotonicity-ratchet-location.md`).
  P2 must NOT add a `TwinStateRepository` dependency to try to enforce the
  ratchet — that crosses an ownership boundary.
- **`physiology_updated` event fires only when posterior shifts > 1 unit**:
  the threshold is > 1 bpm for HR parameters and > 1 watt for CP. The
  `PhysiologyMeasurement` record is always written regardless — it is the
  complete observation history. This means a session can produce
  measurements without firing an event, but never the reverse.

### Implementation Clarifications
- **`PhysiologyParameterState` JSONB shape**: the existing
  `AthletePhysiology` model stores `lt1` and `lt2` as JSONB dicts with shape
  `{hr: {...}, power: {...}, pace: {...}}`. Each sub-dict is either a
  `PhysiologyParameterState` (with fields `value`, `uncertainty`,
  `prior_weight`, `dominant_source`, `last_observation_date`) or null. The
  `cp` and `max_hr` columns are single `PhysiologyParameterState` dicts or
  null. The `bayesian_update` function operates on the inner
  `PhysiologyParameterState` dict, not the outer `lt1`/`lt2` container.
- **Parameter → JSONB path mapping**: `LT1_HR` → `physiology.lt1["hr"]`,
  `LT2_HR` → `physiology.lt2["hr"]`, `CP` → `physiology.cp`,
  `MAX_HR` → `physiology.max_hr`. The service needs a helper to navigate
  from a `PhysiologyParameter` enum value to the correct JSONB path.
- **First observation for CP**: `physiology.cp` starts as null. The first
  `TRAINING_POWER_HR_RATIO` observation creates a new
  `PhysiologyParameterState` from scratch — the initial `value` is the
  observed value, `uncertainty` is a population default (e.g., 1.0),
  `prior_weight` is the observation weight, `dominant_source` is the
  observation source, and `last_observation_date` is the observation date.
  This follows the architecture invariant: "cp and vo2max are null until a
  qualifying observation is made."

### Known Risks
- **JSONB mutation detection**: SQLAlchemy does not automatically detect
  in-place mutations to JSONB columns. The service must explicitly flag the
  column as modified (`flag_modified(physiology, "lt1")`) after updating the
  JSONB dict, or the update will not persist. This is a common SQLAlchemy
  gotcha — the coder must use `from sqlalchemy.orm.attributes import flag_modified`
  or assign a new dict to trigger dirty tracking.
- **Decay computation date basis**: the `days_since_last` computation uses
  `current["last_observation_date"]` (ISO string) and the observation's
  `measurement_date` (date object). The service must parse the ISO string
  to a date for the computation. Time zones are not relevant — both are
  calendar dates.
- **Multiple observations for the same parameter in one session**: the HR
  deflection algorithm can produce both `LT1_HR` and `LT2_HR` observations
  from the same session. The RR inflection algorithm can also produce both.
  If both algorithms run (RR + HR deflection), there may be 4 observations
  for 2 parameters. The service applies them sequentially — the second
  observation for the same parameter uses the posterior from the first
  update as its prior. This is correct Bayesian behaviour.

## Coder Handoff Notes

### Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 [OWNER: Coder]
Skip:     Step 12 (Test Architect — tests)

### Coder Batches
Batch 1: Steps 1, 3, 10       — Repository extension, Bayesian update pure function, result dataclass
Batch 2: Steps 2, 4, 5, 6     — Service skeleton, measurement writing, shift detection, in-place update
Batch 3: Steps 7, 8, 9, 11    — Event firing, confidence transitions, idempotency, registration

### Batch Success Criteria
Batch 1 complete when:
- `AthletePhysiologyRepository.update_in_place` method exists and mutates
  the existing row (flush, no commit)
- `bayesian_update` pure function exists and correctly computes posterior
  mean, uncertainty, prior_weight, dominant_source, and
  last_observation_date per the formula in `physiology-update.md`
- `PhysiologyUpdateResult` dataclass exists with all specified fields

Batch 2 assumes Batch 1 is complete. Batch 2 complete when:
- `PhysiologyUpdateService.apply_observations` method exists and processes
  a list of `ThresholdObservation` objects
- Each observation produces a `PhysiologyMeasurement` record (always
  written)
- `AthletePhysiology` JSONB columns are updated in place with new posterior
  values
- `flag_modified` is called on updated JSONB columns so SQLAlchemy persists
  the changes
- Posterior shift detection correctly identifies parameters that shifted >
  1 unit

Batch 3 assumes Batch 2 is complete. Batch 3 complete when:
- `physiology_updated` event fires via `EventPublisher` when any parameter
  shifted > 1 unit, with correct payload (`parameters_updated`,
  `dominant_sources`, `prior_weights`)
- `physiology_updated` does NOT fire when no parameters shifted
- Confidence transition detection correctly identifies LOW→MEDIUM (at 4.0)
  and MEDIUM→HIGH (at 8.0) transitions within a single `apply_observations`
  call
- P2 computes `metric_confidence` from current `prior_weight` only — it does
  NOT enforce the monotonicity ratchet (that is P3's responsibility per
  ADR-011). P2's output CAN be lower than the previous TwinState's level
  after a long gap; P3 applies `max(stored, computed)` before writing the
  new TwinState
- Duplicate observations (same parameter, value, date, source, activity_id)
  write the measurement but do NOT shift the posterior or fire the event
- `PhysiologyUpdateService` and `PhysiologyUpdateResult` are registered in
  `app/services/__init__.py`

### Context Needed
Step 1:
  Primary:    `app/repositories/athlete_physiology_repository.py` (existing
              repository — extend with `update_in_place`),
              `app/models/athlete_physiology.py` (JSONB column shape)
  Secondary:  `app/repositories/raw_sensor_stream_repository.py` (flush
              pattern reference)
  Fallback:   —
  Forbidden:  —
Step 2:
  Primary:    output of Step 1 (repository extension),
              `app/services/threshold_detection_service.py` (Plan P1 —
              `ThresholdObservation` dataclass),
              `app/services/twin_recalibration_service.py` (service
              construction pattern with AsyncSession)
  Secondary:  `app/repositories/physiology_measurement_repository.py` (Plan P1
              — measurement repository)
  Fallback:   —
  Forbidden:  —
Step 3:
  Primary:    `docs/architecture/02-computations/physiology-update.md`
              (Bayesian update formula — the exact formula to implement),
              `app/services/onboarding_service.py` (`_bootstrap_signal`
              function — the JSONB shape for `PhysiologyParameterState`)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 4:
  Primary:    `app/repositories/physiology_measurement_repository.py` (Plan P1 —
              `insert` method), `app/models/physiology_measurement.py` (Plan P1 —
              model fields)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 5:
  Primary:    output of Step 3 (bayesian_update function — provides new and
              old values for shift comparison)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 6:
  Primary:    `app/models/athlete_physiology.py` (JSONB column structure:
              `lt1`, `lt2`, `cp`, `max_hr`),
              `app/services/onboarding_service.py` (how `_bootstrap_signal`
              shapes the JSONB — the service must update the same shape)
  Secondary:  SQLAlchemy `flag_modified` documentation (JSONB dirty tracking)
  Fallback:   —
  Forbidden:  —
Step 7:
  Primary:    `app/services/event_publisher.py` (EventPublisher — `publish`
              method and pattern),
              `app/services/activity_ingestion_service.py` (existing event
              publishing pattern — `events.publish(event_type=..., ...)`),
              `docs/architecture/00-foundations/event-catalogue.md`
              (`physiology_updated` event payload)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 8:
  Primary:    `docs/architecture/00-foundations/confidence-model.md`
              (CONFIDENCE_THRESHOLDS: 4.0 for MEDIUM, 8.0 for HIGH),
              `app/services/onboarding_service.py` (`_bootstrap_metric_confidence`
              — the metric_confidence JSONB shape)
  Secondary:  `docs/architecture/02-computations/evidence-mapping.md`
              (transition thresholds table)
  Fallback:   —
  Forbidden:  —
Step 9:
  Primary:    `app/repositories/physiology_measurement_repository.py` (Plan P1 —
              `get_recent_for_parameter` method for dedup lookup),
              `docs/architecture/01-entities/athlete-physiology.md`
              (Idempotency section)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 10:
  Primary:    `app/services/twin_recalibration_service.py`
              (`RecalibrationResult` dataclass — pattern to follow)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 11:
  Primary:    `app/services/__init__.py` (existing registration pattern)
  Secondary:  —
  Fallback:   —
  Forbidden:  —

(This is everything relevant to the steps above. Primary items are fetched
together in Pre-Flight Step 3; Secondary and Fallback are requested only on
demand.)