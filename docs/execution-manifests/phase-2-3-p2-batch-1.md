# Execution Manifest — Phase-2.3-P2 — Batch 1
## Manifest Metadata
Source Plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Batch: 1 of 3
Manifest Version: v1
Generated At: 2026-07-11T00:00:00Z
Source Plan Lines: 606
Manifest Lines: 86

## Objective
Implement the foundational components for the `PhysiologyUpdateService`: extend `AthletePhysiologyRepository` with in-place mutation support, implement the Bayesian update pure function per the `physiology-update.md` formula, and define the `PhysiologyUpdateResult` dataclass.

## Preconditions
No preconditions — this is the first batch.

## Steps
### Step 1 — Extend `AthletePhysiologyRepository` with an `update_in_place` method
[OWNER: Coder] Extend `AthletePhysiologyRepository` with an `update_in_place` method. The method takes `athlete_id` and the updated JSONB column values (`lt1`, `lt2`, `cp`, `max_hr` as dicts) and writes them to the existing row. The method flushes but does not commit — the caller (worker task in Plan P3) owns the commit boundary. The method must NOT create a new row — it mutates the existing one. Follow the existing `add` method's flush pattern.

### Step 3 — Implement the Bayesian update formula
[OWNER: Coder] Implement the Bayesian update formula as a pure function on `PhysiologyUpdateService` (or as a module-level helper for unit-test access). Per `physiology-update.md`:
```bayesian_update(current: PhysiologyParameterState, observation) -> PhysiologyParameterState```
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
Primary: `app/repositories/athlete_physiology_repository.py` (existing repository — extend with `update_in_place`), `app/models/athlete_physiology.py` (JSONB column shape)
Secondary: `app/repositories/raw_sensor_stream_repository.py` (flush pattern reference)
Fallback: —
Forbidden: —

### Step 3
Primary: `docs/architecture/02-computations/physiology-update.md` (Bayesian update formula — the exact formula to implement), `app/services/onboarding_service.py` (`_bootstrap_signal` function — the JSONB shape for `PhysiologyParameterState`)
Secondary: —
Fallback: —
Forbidden: —

### Step 10
Primary: `app/services/twin_recalibration_service.py` (`RecalibrationResult` dataclass — pattern to follow)
Secondary: —
Fallback: —
Forbidden: —

## Relevant Architecture Contracts
`02-computations/physiology-update.md` — IMPLEMENTS (Bayesian update formula, observation weights, prior decay, ingestion flow)

## Relevant Invariants
(omit — none explicitly named in this batch's Context Needed)

## Relevant Event Contracts
(omit — no step in this batch touches an event)

## Relevant Notes
### Implementation Clarifications
- **`PhysiologyParameterState` JSONB shape**: the existing `AthletePhysiology` model stores `lt1` and `lt2` as JSONB dicts with shape `{hr: {...}, power: {...}, pace: {...}}`. Each sub-dict is either a `PhysiologyParameterState` (with fields `value`, `uncertainty`, `prior_weight`, `dominant_source`, `last_observation_date`) or null. The `cp` and `max_hr` columns are single `PhysiologyParameterState` dicts or null. The `bayesian_update` function operates on the inner `PhysiologyParameterState` dict, not the outer `lt1`/`lt2` container.
- **Parameter → JSONB path mapping**: `LT1_HR` → `physiology.lt1["hr"]`, `LT2_HR` → `physiology.lt2["hr"]`, `CP` → `physiology.cp`, `MAX_HR` → `physiology.max_hr`. The service needs a helper to navigate from a `PhysiologyParameter` enum value to the correct JSONB path.
- **First observation for CP**: `physiology.cp` starts as null. The first `TRAINING_POWER_HR_RATIO` observation creates a new `PhysiologyParameterState` from scratch — the initial `value` is the observed value, `uncertainty` is a population default (e.g., 1.0), `prior_weight` is the observation weight, `dominant_source` is the observation source, and `last_observation_date` is the observation date. This follows the architecture invariant: "cp and vo2max are null until a qualifying observation is made."

## Files Expected To Change
- [EXISTING] `app/repositories/athlete_physiology_repository.py`
- [EXISTING] `app/models/athlete_physiology.py`
- [EXISTING] `app/repositories/raw_sensor_stream_repository.py`
- [EXISTING] `app/services/onboarding_service.py`
- [EXISTING] `app/services/twin_recalibration_service.py`

## Batch Success Criteria
Batch 1 complete when:
- `AthletePhysiologyRepository.update_in_place` method exists and mutates the existing row (flush, no commit)
- `bayesian_update` pure function exists and correctly computes posterior mean, uncertainty, prior_weight, dominant_source, and last_observation_date per the formula in `physiology-update.md`
- `PhysiologyUpdateResult` dataclass exists with all specified fields
