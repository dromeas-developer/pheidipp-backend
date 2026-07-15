# Execution Manifest — Phase-2.3-P2 — Batch 1

## Manifest Metadata
Source Plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Batch: 1 of 3
Manifest Version: v1
Generated At: 2026-07-12T00:00:00Z
Source Plan Lines: 606
Manifest Lines: 0

## Objective
Extend `AthletePhysiologyRepository` with an in-place update method, implement the Bayesian update pure function per `physiology-update.md`, and create the `PhysiologyUpdateResult` dataclass — the foundational building blocks for the `PhysiologyUpdateService` that applies threshold observations to athlete physiology records.

## Preconditions
No preconditions — this is the first batch.

## Steps

### Step 1 — Extend `AthletePhysiologyRepository` with an `update_in_place` method
[OWNER: Coder] Extend `AthletePhysiologyRepository` with an `update_in_place` method. The method takes `athlete_id` and the updated JSONB column values (`lt1`, `lt2`, `cp`, `max_hr` as dicts) and writes them to the existing row. The method flushes but does not commit — the caller (worker task in Plan P3) owns the commit boundary. The method must NOT create a new row — it mutates the existing one. Follow the existing `add` method's flush pattern.

### Step 3 — Implement the Bayesian update formula as a pure function
[OWNER: Coder] Implement the Bayesian update formula as a pure function on `PhysiologyUpdateService` (or as a module-level helper for unit-test access). Per `physiology-update.md`:
```python
def bayesian_update(current: PhysiologyParameterState, observation) -> PhysiologyParameterState:
```
- `days_since_last = days_between(current.last_observation_date, observation.date)`
- `decay_factor = exp(-days_since_last / 42)`
- `decayed_weight = current.prior_weight * decay_factor`
- `new_total_weight = decayed_weight + observation.weight`
- `posterior_mean = (current.value * decayed_weight + observation.value * observation.weight) / new_total_weight`
- `posterior_uncertainty = max(current.uncertainty * sqrt(decayed_weight / new_total_weight), 0.5)`
- `dominant_source = observation.source if observation.weight > decayed_weight else current.dominant_source`
- `last_observation_date = observation.date`

The function operates on the JSONB `PhysiologyParameterState` dict shape (`{value, uncertainty, prior_weight, dominant_source, last_observation_date}`) — the same shape bootstrapped by `OnboardingService._bootstrap_signal`.

### Step 10 — Create `PhysiologyUpdateResult` dataclass
[OWNER: Coder] Create `PhysiologyUpdateResult` dataclass carrying:
- `physiology: AthletePhysiology` — the updated row
- `shifted_parameters: list[PhysiologyParameter]` — parameters that shifted > 1 unit
- `metric_confidence: dict` — per-metric confidence levels after update (same shape as `TwinState.metric_confidence`)
- `confidence_transitions: dict` — parameters that transitioned (`{parameter: (from_level, to_level)}`)
- `measurements_written: int` — count of `PhysiologyMeasurement` records

## Context Needed

### Step 1
**Primary:** `app/repositories/athlete_physiology_repository.py` (existing repository — extend with `update_in_place`), `app/models/athlete_physiology.py` (JSONB column shape)
**Secondary:** `app/repositories/raw_sensor_stream_repository.py` (flush pattern reference)
**Fallback:** —
**Forbidden:** —

### Step 3
**Primary:** `docs/architecture/02-computations/physiology-update.md` (Bayesian update formula — the exact formula to implement), `app/services/onboarding_service.py` (`_bootstrap_signal` function — the JSONB shape for `PhysiologyParameterState`)
**Secondary:** —
**Fallback:** —
**Forbidden:** —

### Step 10
**Primary:** `app/services/twin_recalibration_service.py` (`RecalibrationResult` dataclass — pattern to follow)
**Secondary:** —
**Fallback:** —
**Forbidden:** —

## Relevant Architecture Contracts
- `02-computations/physiology-update.md` — IMPLEMENTS (Bayesian update formula, observation weights, prior decay, ingestion flow)

## Relevant Invariants
(No invariants explicitly named in this batch's `Context Needed` entries.)

## Relevant Event Contracts
(No event contracts — no step in this batch explicitly fires, consumes, or directly touches an event.)

## Relevant Notes

### Implementation Clarifications — `PhysiologyParameterState` JSONB shape
The existing `AthletePhysiology` model stores `lt1` and `lt2` as JSONB dicts with shape `{hr: {...}, power: {...}, pace: {...}}`. Each sub-dict is either a `PhysiologyParameterState` (with fields `value`, `uncertainty`, `prior_weight`, `dominant_source`, `last_observation_date`) or null. The `cp` and `max_hr` columns are single `PhysiologyParameterState` dicts or null. The `bayesian_update` function operates on the inner `PhysiologyParameterState` dict, not the outer `lt1`/`lt2` container.

### Implementation Clarifications — Parameter → JSONB path mapping
`LT1_HR` → `physiology.lt1["hr"]`, `LT2_HR` → `physiology.lt2["hr"]`, `CP` → `physiology.cp`, `MAX_HR` → `physiology.max_hr`. The service needs a helper to navigate from a `PhysiologyParameter` enum value to the correct JSONB path.

### Implementation Clarifications — First observation for CP
`physiology.cp` starts as null. The first `TRAINING_POWER_HR_RATIO` observation creates a new `PhysiologyParameterState` from scratch — the initial `value` is the observed value, `uncertainty` is a population default (e.g., 1.0), `prior_weight` is the observation weight, `dominant_source` is the observation source, and `last_observation_date` is the observation date. This follows the architecture invariant: "cp and vo2max are null until a qualifying observation is made."

### Known Risks — Decay computation date basis
The `days_since_last` computation uses `current["last_observation_date"]` (ISO string) and the observation's `measurement_date` (date object). The service must parse the ISO string to a date for the computation. Time zones are not relevant — both are calendar dates.

## Relevant Pseudocode
```python
PhysiologyUpdateService.apply_observations(athlete_id, observations):
    physiology = athlete_physiology.get_by_athlete_id(athlete_id)
    if physiology is None:
        raise MissingAthletePhysiologyError(athlete_id)
    shifted_parameters = []
    updated_states = {} # parameter -> new PhysiologyParameterState
    measurements_written = 0
    old_confidence = _compute_metric_confidence(physiology)
    for obs in observations:
        # Idempotency check
        if _is_duplicate(athlete_id, obs):
            _write_measurement(obs) # still write for audit
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
        current["last_observation_date"],
        observation.date
    )
    decay_factor = exp(-days_since_last / 42)
    decayed_weight = current["prior_weight"] * decay_factor
    new_total_weight = decayed_weight + observation.weight
    posterior_mean = (
        current["value"] * decayed_weight
        + observation.value * observation.weight
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
        if weight >= 8.0:
            return "high"
        if weight >= 4.0:
            return "medium"
        return "low"
    return {
        "lt1_hr": level(physiology.lt1["hr"]["prior_weight"]),
        "lt1_power": level(physiology.lt1["power"]["prior_weight"]) if physiology.lt1.get("power") else None,
        "lt1_pace": ...,
        "lt2_hr": level(physiology.lt2["hr"]["prior_weight"]),
        "lt2_power": ...,
        "lt2_pace": ...,
        "cp": level(physiology.cp["prior_weight"]) if physiology.cp else None,
    }
```

## Files Expected To Change
- [EXISTING — modified] `app/repositories/athlete_physiology_repository.py`
- [EXISTING — reference only] `app/models/athlete_physiology.py`
- [EXISTING — reference only] `docs/architecture/02-computations/physiology-update.md`
- [EXISTING — reference only] `app/services/onboarding_service.py`
- [EXISTING — reference only] `app/services/twin_recalibration_service.py`

## Batch Success Criteria
Batch 1 complete when:
- `AthletePhysiologyRepository.update_in_place` method exists and mutates the existing row (flush, no commit)
- `bayesian_update` pure function exists and correctly computes posterior mean, uncertainty, prior_weight, dominant_source, and last_observation_date per the formula in `physiology-update.md`
- `PhysiologyUpdateResult` dataclass exists with all specified fields
