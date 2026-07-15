# Execution Manifest — Phase-2.3-P2 — Batch 3

## Manifest Metadata
Source Plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Batch: 3 of 3
Manifest Version: v1
Generated At: 2026-07-12T00:00:00Z
Source Plan Lines: 606
Manifest Lines: 0

## Objective
Implement `physiology_updated` event firing via `EventPublisher`, confidence transition detection with monotonic LOW→MEDIUM→HIGH progression, idempotency for duplicate observations, and register `PhysiologyUpdateService` and `PhysiologyUpdateResult` in `app/services/__init__.py` — completing the `PhysiologyUpdateService` pipeline.

## Preconditions
Batches 1 through 2 are complete; their Batch Success Criteria hold.

## Steps

### Step 7 — Implement `physiology_updated` event firing
[OWNER: Coder] Implement `physiology_updated` event firing. When any parameter shifted by > 1 unit, fire the event via `EventPublisher`:
```python
event_type = "physiology_updated"
payload = {
    "athlete_id": str(athlete_id),
    "parameters_updated": [param.value for param in shifted_parameters],
    "dominant_sources": {param: source.value for each updated param},
    "prior_weights": {param: new_prior_weight for each updated param}
}
```
The event is written to the transactional outbox (SystemEvent + SystemEventOutbox) in the same transaction as the `AthletePhysiology` update — following the existing `EventPublisher` pattern used by `ActivityIngestionService` and `OnboardingService`. The event does NOT fire when no parameters shifted — this avoids noise from minor fluctuations.

### Step 8 — Implement confidence transition detection
[OWNER: Coder] Implement confidence transition detection. After all observations are processed, compute the per-metric confidence level for each parameter from its `prior_weight`:
- `prior_weight >= 8.0` → HIGH
- `prior_weight >= 4.0` → MEDIUM
- `prior_weight < 4.0` → LOW

Return the per-metric confidence dict in the `PhysiologyUpdateResult`. Also detect whether any metric transitioned (was LOW and is now MEDIUM, or was MEDIUM and is now HIGH) — this is used by Plan P3's `TwinRecalibrationService` to fire `twin_confidence_upgraded`. Confidence is monotonic — it never decreases. If prior_weight drops below a threshold due to decay, the confidence level stays at its current level (the decay affects recommendation strength, not the confidence enum).

### Step 9 — Implement idempotency for duplicate observations
[OWNER: Coder] Implement idempotency for duplicate observations. Before applying the Bayesian update, check if a `PhysiologyMeasurement` already exists with the same `(athlete_id, activity_id, parameter, source, measurement_date, observed_value)`. If it does, the observation is a duplicate — still write the `PhysiologyMeasurement` record (for audit completeness) but do NOT apply the Bayesian update and do NOT fire the event. This follows the architecture's idempotency contract: "Submitting identical lab test measurements twice creates two PhysiologyMeasurement records but shifts the posterior only once from the first."

### Step 11 — Register `PhysiologyUpdateService` and `PhysiologyUpdateResult` in `app/services/__init__.py`
[OWNER: Coder] Register `PhysiologyUpdateService` and `PhysiologyUpdateResult` in `app/services/__init__.py`. Export the service class, the result dataclass, and any error classes.

## Context Needed

### Step 7
**Primary:** `app/services/event_publisher.py` (EventPublisher — `publish` method and pattern), `app/services/activity_ingestion_service.py` (existing event publishing pattern — `events.publish(event_type=..., ...)`), `docs/architecture/00-foundations/event-catalogue.md` (`physiology_updated` event payload)
**Secondary:** —
**Fallback:** —
**Forbidden:** —

### Step 8
**Primary:** `docs/architecture/00-foundations/confidence-model.md` (CONFIDENCE_THRESHOLDS: 4.0 for MEDIUM, 8.0 for HIGH), `app/services/onboarding_service.py` (`_bootstrap_metric_confidence` — the metric_confidence JSONB shape)
**Secondary:** `docs/architecture/02-computations/evidence-mapping.md` (transition thresholds table)
**Fallback:** —
**Forbidden:** —

### Step 9
**Primary:** `app/repositories/physiology_measurement_repository.py` (Plan P1 — `get_recent_for_parameter` method for dedup lookup), `docs/architecture/01-entities/athlete-physiology.md` (Idempotency section)
**Secondary:** —
**Fallback:** —
**Forbidden:** —

### Step 11
**Primary:** `app/services/__init__.py` (existing registration pattern)
**Secondary:** —
**Fallback:** —
**Forbidden:** —

## Relevant Architecture Contracts
- `00-foundations/event-catalogue.md` → `physiology_updated` — PRODUCES
- `00-foundations/confidence-model.md` — DEPENDS ON (evidence weight thresholds 4.0/8.0 for confidence transitions; per-metric confidence derivation)
- `02-computations/evidence-mapping.md` — DEPENDS ON (evidence source → metric mapping; weights are carried on `ThresholdObservation` from P1)
- `01-entities/athlete-physiology.md` — IMPLEMENTS (mutable posterior updates, `PhysiologyMeasurement` append-only writes, `physiology_updated` event production)

## Relevant Invariants
(No invariants explicitly named in this batch's `Context Needed` entries.)

## Relevant Event Contracts
| Event | Role | Payload Fields Required | Ordering |
|---|---|---|---|
| `physiology_updated` | PRODUCES | `athlete_id`, `parameters_updated` (list of parameter names), `dominant_sources` (dict parameter→source), `prior_weights` (dict parameter→weight) | Fires after `AthletePhysiology` is updated in place and `PhysiologyMeasurement` records are written, all in the same transaction. Fires only when at least one parameter posterior shifted by > 1 unit. |

## Relevant Notes

### Architecture Clarifications — Confidence threshold values
The `TwinState` architecture document shows example thresholds of 15.0/40.0 in a code block marked "Example thresholds (finalize with data science)." The authoritative thresholds are 4.0 (LOW→MEDIUM) and 8.0 (MEDIUM→HIGH) from `confidence-model.md`, `evidence-mapping.md`, `threshold-detection.md`, and the sub-phase document. Use 4.0/8.0 — the 15.0/40.0 values are a stale example that was never updated.

### Architecture Clarifications — `physiology_updated` event fires only when posterior shifts > 1 unit
The threshold is > 1 bpm for HR parameters and > 1 watt for CP. The `PhysiologyMeasurement` record is always written regardless — it is the complete observation history. This means a session can produce measurements without firing an event, but never the reverse.

### Implementation Clarifications — `PhysiologyParameterState` JSONB shape
The existing `AthletePhysiology` model stores `lt1` and `lt2` as JSONB dicts with shape `{hr: {...}, power: {...}, pace: {...}}`. Each sub-dict is either a `PhysiologyParameterState` (with fields `value`, `uncertainty`, `prior_weight`, `dominant_source`, `last_observation_date`) or null. The `cp` and `max_hr` columns are single `PhysiologyParameterState` dicts or null. The `bayesian_update` function operates on the inner `PhysiologyParameterState` dict, not the outer `lt1`/`lt2` container.

### Implementation Clarifications — Parameter → JSONB path mapping
`LT1_HR` → `physiology.lt1["hr"]`, `LT2_HR` → `physiology.lt2["hr"]`, `CP` → `physiology.cp`, `MAX_HR` → `physiology.max_hr`. The service needs a helper to navigate from a `PhysiologyParameter` enum value to the correct JSONB path.

### Implementation Clarifications — First observation for CP
`physiology.cp` starts as null. The first `TRAINING_POWER_HR_RATIO` observation creates a new `PhysiologyParameterState` from scratch — the initial `value` is the observed value, `uncertainty` is a population default (e.g., 1.0), `prior_weight` is the observation weight, `dominant_source` is the observation source, and `last_observation_date` is the observation date. This follows the architecture invariant: "cp and vo2max are null until a qualifying observation is made."

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
- [EXISTING — modified] `app/services/__init__.py`
- [EXISTING — reference only] `app/services/event_publisher.py`
- [EXISTING — reference only] `app/services/activity_ingestion_service.py`
- [EXISTING — reference only] `docs/architecture/00-foundations/event-catalogue.md`
- [EXISTING — reference only] `docs/architecture/00-foundations/confidence-model.md`
- [EXISTING — reference only] `app/services/onboarding_service.py`
- [EXISTING — reference only] `docs/architecture/02-computations/evidence-mapping.md`
- [EXISTING — reference only] `app/repositories/physiology_measurement_repository.py`
- [EXISTING — reference only] `docs/architecture/01-entities/athlete-physiology.md`

## Batch Success Criteria
Batch 3 complete when:
- `physiology_updated` event fires via `EventPublisher` when any parameter shifted > 1 unit, with correct payload (`parameters_updated`, `dominant_sources`, `prior_weights`)
- `physiology_updated` does NOT fire when no parameters shifted
- Confidence transition detection correctly identifies LOW→MEDIUM (at 4.0) and MEDIUM→HIGH (at 8.0) transitions
- Confidence is monotonic — a metric that reached MEDIUM stays MEDIUM even if prior_weight decays below 4.0
- Duplicate observations (same parameter, value, date, source, activity_id) write the measurement but do NOT shift the posterior or fire the event
- `PhysiologyUpdateService` and `PhysiologyUpdateResult` are registered in `app/services/__init__.py`
