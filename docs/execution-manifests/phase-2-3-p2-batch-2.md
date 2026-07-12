# Execution Manifest — Phase-2.3-P2 — Batch 2
## Manifest Metadata
Source Plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Batch: 2 of 3
Manifest Version: v1
Generated At: 2026-07-11T00:00:00Z
Source Plan Lines: 606
Manifest Lines: 130

## Objective
Implement the `PhysiologyUpdateService` skeleton, `PhysiologyMeasurement` record writing, posterior shift detection, and in-place JSONB update logic as the core processing pipeline for the Bayesian update engine.

## Preconditions
Batches 1 through 1 are complete; their Batch Success Criteria hold.

## Steps
### Step 2 — Create `PhysiologyUpdateService` in `app/services/physiology_update_service.py`
[OWNER: Coder] Create `PhysiologyUpdateService` in `app/services/physiology_update_service.py`. The service is constructed with an `AsyncSession`, `AthletePhysiologyRepository`, `PhysiologyMeasurementRepository`, and an optional `EventPublisher`. The primary entry point is:
```async def apply_observations(
    self, athlete_id: uuid.UUID, observations: list[ThresholdObservation]
) -> PhysiologyUpdateResult```
The service:
- Loads the current `AthletePhysiology` row for the athlete.
- For each observation, applies the Bayesian update (Step 3), writes a `PhysiologyMeasurement` record (Step 4), and tracks which parameters shifted by > 1 unit (Step 5).
- Updates `AthletePhysiology` in place with all new posterior values (Step 6).
- Fires `physiology_updated` event if any parameter shifted by > 1 unit (Step 7).
- Returns a `PhysiologyUpdateResult` carrying: the updated `AthletePhysiology` row, the list of parameters that shifted, the per-metric confidence levels after the update, and whether any confidence transition occurred.

### Step 4 — Implement `PhysiologyMeasurement` record writing
[OWNER: Coder] Implement `PhysiologyMeasurement` record writing. For each observation, create a `PhysiologyMeasurement` row with: `athlete_id`, `activity_id` (from the observation), `parameter`, `observed_value`, `source`, `measurement_date` (from the observation), `algorithm_used`, `confidence_weight`, `raw_data_reference` (null for training-derived), `notes` (null for training-derived). Insert via `PhysiologyMeasurementRepository.insert`. The measurement is ALWAYS written, even if the posterior does not shift — it is the complete observation history.

### Step 5 — Implement posterior shift detection
[OWNER: Coder] Implement posterior shift detection. After applying the Bayesian update to a parameter, compare the new posterior mean to the old posterior mean. For HR parameters (LT1_HR, LT2_HR, MAX_HR): shift is `abs(new_value - old_value)`. For CP: shift is `abs(new_value - old_value)` in watts. The parameter "shifted" if the shift exceeds 1.0 (bpm for HR, watts for CP). Track all shifted parameters in a list for the event payload and the result.

### Step 6 — Implement `AthletePhysiology` in-place update
[OWNER: Coder] Implement `AthletePhysiology` in-place update. After all observations are processed, write the updated JSONB columns back to the `AthletePhysiology` row. The JSONB shape for `lt1` and `lt2` is `{hr: {...}, power: {...}, pace: {...}}` where each sub-dict is a `PhysiologyParameterState` or null. For `cp`, the JSONB is a single `PhysiologyParameterState` or null. For `max_hr`, same as `cp`. Use `AthletePhysiologyRepository.update_in_place` (Step 1). Only update columns that have changed — leave unchanged columns untouched to minimise write amplification.

## Context Needed
### Step 2
Primary: output of Step 1 (repository extension), `app/services/threshold_detection_service.py` (Plan P1 — `ThresholdObservation` dataclass), `app/services/twin_recalibration_service.py` (service construction pattern with AsyncSession)
Secondary: `app/repositories/physiology_measurement_repository.py` (Plan P1 — measurement repository)
Fallback: —
Forbidden: —

### Step 4
Primary: `app/repositories/physiology_measurement_repository.py` (Plan P1 — `insert` method), `app/models/physiology_measurement.py` (Plan P1 — model fields)
Secondary: —
Fallback: —
Forbidden: —

### Step 5
Primary: output of Step 3 (bayesian_update function — provides new and old values for shift comparison)
Secondary: —
Fallback: —
Forbidden: —

### Step 6
Primary: `app/models/athlete_physiology.py` (JSONB column structure: `lt1`, `lt2`, `cp`, `max_hr`), `app/services/onboarding_service.py` (how `_bootstrap_signal` shapes the JSONB — the service must update the same shape)
Secondary: SQLAlchemy `flag_modified` documentation (JSONB dirty tracking)
Fallback: —
Forbidden: —

## Relevant Architecture Contracts
(omit — none explicitly named in this batch's Context Needed)

## Relevant Invariants
(omit — none explicitly named in this batch's Context Needed)

## Relevant Event Contracts
(omit — no step in this batch touches an event)

## Relevant Notes
### Implementation Clarifications
- **`PhysiologyParameterState` JSONB shape**: the existing `AthletePhysiology` model stores `lt1` and `lt2` as JSONB dicts with shape `{hr: {...}, power: {...}, pace: {...}}`. Each sub-dict is either a `PhysiologyParameterState` (with fields `value`, `uncertainty`, `prior_weight`, `dominant_source`, `last_observation_date`) or null. The `cp` and `max_hr` columns are single `PhysiologyParameterState` dicts or null. The `bayesian_update` function operates on the inner `PhysiologyParameterState` dict, not the outer `lt1`/`lt2` container.
- **Parameter → JSONB path mapping**: `LT1_HR` → `physiology.lt1["hr"]`, `LT2_HR` → `physiology.lt2["hr"]`, `CP` → `physiology.cp`, `MAX_HR` → `physiology.max_hr`. The service needs a helper to navigate from a `PhysiologyParameter` enum value to the correct JSONB path.
- **First observation for CP**: `physiology.cp` starts as null. The first `TRAINING_POWER_HR_RATIO` observation creates a new `PhysiologyParameterState` from scratch — the initial `value` is the observed value, `uncertainty` is a population default (e.g., 1.0), `prior_weight` is the observation weight, `dominant_source` is the observation source, and `last_observation_date` is the observation date. This follows the architecture invariant: "cp and vo2max are null until a qualifying observation is made."

### Known Risks
- **JSONB mutation detection**: SQLAlchemy does not automatically detect in-place mutations to JSONB columns. The service must explicitly flag the column as modified (`flag_modified(physiology, "lt1")`) after updating the JSONB dict, or the update will not persist. This is a common SQLAlchemy gotcha — the coder must use `from sqlalchemy.orm.attributes import flag_modified` or assign a new dict to trigger dirty tracking.
- **Multiple observations for the same parameter in one session**: the HR deflection algorithm can produce both `LT1_HR` and `LT2_HR` observations from the same session. The RR inflection algorithm can also produce both. If both algorithms run (RR + HR deflection), there may be 4 observations for 2 parameters. The service applies them sequentially — the second observation for the same parameter uses the posterior from the first update as its prior. This is correct Bayesian behaviour.

## Files Expected To Change
- [NEW] `app/services/physiology_update_service.py`
- [EXISTING] `app/services/threshold_detection_service.py`
- [EXISTING] `app/services/twin_recalibration_service.py`
- [EXISTING] `app/repositories/physiology_measurement_repository.py`
- [EXISTING] `app/models/physiology_measurement.py`
- [EXISTING] `app/models/athlete_physiology.py`
- [EXISTING] `app/services/onboarding_service.py`

## Batch Success Criteria
Batch 2 assumes Batch 1 is complete.
Batch 2 complete when:
- `PhysiologyUpdateService.apply_observations` method exists and processes a list of `ThresholdObservation` objects
- Each observation produces a `PhysiologyMeasurement` record (always written)
- `AthletePhysiology` JSONB columns are updated in place with new posterior values
- `flag_modified` is called on updated JSONB columns so SQLAlchemy persists the changes
- Posterior shift detection correctly identifies parameters that shifted > 1 unit
