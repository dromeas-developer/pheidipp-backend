# Physiology Update — Bayesian Parameter Estimation

## Purpose
- Defines the Bayesian update mechanism that maintains `AthletePhysiology` posterior estimates
- Owns observation weights by source, prior decay, and the update formula
- Describes the ingestion flows for lab tests, field tests, and training-derived observations

## Inputs
```typescript
type PhysiologyUpdateInputs = {
  current: PhysiologyParameterState  // current posterior state for one parameter
  observation: {
    value: number                    // observed measurement
    weight: number                   // source-specific observation weight
    date: string                     // YYYY-MM-DD
    source: MeasurementSource        // lab_test, field_test, training-derived, etc.
  }
}
```

## Bayesian Update Formula

Applied by `PhysiologyUpdateService` for every new observation:

```typescript
function bayesianUpdate(
  current: PhysiologyParameterState,
  observation: { value: number; weight: number; date: string }
): PhysiologyParameterState {
  // Prior decay: evidence older than ~6 weeks (42 days) loses influence
  // An observation from 42 days ago carries ~37% of its original weight (e^-1)
  const days_since_last = daysBetween(current.last_observation_date, observation.date)
  const decay_factor = Math.exp(-days_since_last / 42)
  const decayed_weight = current.prior_weight * decay_factor

  const new_total_weight = decayed_weight + observation.weight
  const posterior_mean = (current.value * decayed_weight + observation.value * observation.weight)
                         / new_total_weight

  return {
    value: posterior_mean,
    uncertainty: computePosteriorUncertainty(current.uncertainty, observation.weight, new_total_weight),
    prior_weight: new_total_weight,
    dominant_source: observation.weight > decayed_weight
      ? deriveMeasurementSource(observation)
      : current.dominant_source,
    last_observation_date: observation.date
  }
}
```

The 42-day time constant is deliberately aligned with the aerobic fitness time constant in the Banister model. As fitness drifts, so does the reliability of older threshold observations.

### `computePosteriorUncertainty`

Called by `bayesianUpdate()` to compute the `uncertainty` field on the returned `PhysiologyParameterState`. This uncertainty value drives `IntentRange` width — as evidence accumulates, ranges narrow; as evidence ages and decays, ranges widen.

```typescript
function computePosteriorUncertainty(
  current_uncertainty: number,
  observation_weight: number,
  total_weight: number
): number {
  // Posterior uncertainty decreases as evidence accumulates
  // Formula: σ_posterior = σ_prior * √(prior_weight / total_weight)
  //
  // As total_weight grows (more observations), uncertainty shrinks.
  // A lab_test (weight 12–15) reduces uncertainty faster than
  // training_hr_deflection (weight 1.0).
  //
  // Floor: uncertainty never drops below 0.5 — even with massive
  // evidence, there is irreducible measurement noise.
  const prior_weight = total_weight - observation_weight
  const scaled = current_uncertainty * Math.sqrt(prior_weight / total_weight)
  return Math.max(scaled, 0.5)
}
```

## Observation Weights by Source

These weights determine how much each observation shifts the posterior. Higher weight = more authoritative measurement.

| Source | LT1 weight | LT2 weight | CP weight | VO2max weight | Max HR weight | Confidence Contribution |
|---|---|---|---|---|---|---|
| `questionnaire_estimate` | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | All metrics (low weight) |
| `training_hr_deflection` | 1.0 | 1.0 | — | — | 0.5 | lt1_hr, lt2_hr |
| `training_rr_inflection` | 2.5 | 2.5 | — | — | 0.5 | lt1_hr, lt2_hr (higher quality) |
| `training_power_hr_ratio` | — | — | 1.5 | — | — | cp |
| `field_test` | 2.0 | 4.0 | 5.0 | 3.0 | 2.0 | Specific metric tested (lt1, lt2, or cp) |
| `lab_test` | 12.0 | 15.0 | 10.0 | 15.0 | 8.0 | All measured metrics |

**Key insight**: Confidence transitions are per-metric. A source only affects confidence for metrics it provides evidence for. A field test for LT2 (weight 4.0) contributes to LT2 confidence, not LT1 confidence.

A lab test carries observation weight 12–15 depending on the parameter, which dominates a typical accumulated prior of 20–40 weight units built from 2 years of regular training.

## Lab Test — Ingestion Flow

A lab test is the highest-authority physiological input:

```
Clinician or athlete enters results
    │
    ▼
POST /athletes/{id}/physiology/measurements
    │  (source=lab_test, parameter values from report)
    ▼
PhysiologyInputService validates and creates PhysiologyMeasurement records
    │  (one record per reported parameter)
    ▼
PhysiologyUpdateService.bayesian_update() for each parameter
    │  (posterior recalculated with high-weight observations)
    ▼
AthletePhysiology.updated_at + all affected parameter states updated
    │
    ▼
physiology_updated event fires
    │
    ▼
TwinRecalibrationService triggered (trigger = 'calibration')
    │
    ▼
New TwinState appended referencing updated AthletePhysiology
    │
    ▼
If confidence transitions: twin_confidence_upgraded event
    │
    ▼
Next GeneratedWorkout uses updated threshold estimates
    │
    ▼
ProactiveMessageService creates confidence_upgrade CoachingMessage
    (coach tells the athlete their targets have been recalibrated)
```

## Field Test — How It Differs From Lab Test

A field test (20-minute FTP effort, critical power test, time trial) is athlete-executable without lab equipment. It is entered the same way as a lab test but with `source = 'field_test'` and lower weights.

For a 20-minute FTP test, the conventional estimate is `observed_power_20min * 0.95`. The system accepts the estimated CP value rather than computing it — the athlete or coach applies the 0.95 correction before entry.

Field tests are also detected automatically when the system identifies that a calibration-eligible session matches a known field test protocol (sustained high effort for 20+ minutes with no intervals). In this case, a `PhysiologyMeasurement` is created automatically with `source = 'field_test'` without requiring manual entry.

## Continuous Training-Derived Updates

These happen automatically as part of the `TwinRecalibrationTask` pipeline:

```
calibration-eligible session processed
    │
    ▼
ThresholdDetectionService produces observation
    │  {lt1_bpm, lt2_bpm, confidence_weight, algorithm_used}
    ▼
PhysiologyUpdateService.bayesian_update()
    │
    ▼
AthletePhysiology updated (posterior shifts toward observation)
    │
    ▼
physiology_updated event (only if posterior shifted by > 1 bpm)
    │  (avoids noise from minor fluctuations)
    ▼
TwinRecalibrationService creates new TwinState
```

The threshold is `> 1 bpm` change to avoid creating spurious TwinState records from training sessions that barely move the posterior. The `PhysiologyMeasurement` record is always written regardless — it is the complete observation history.

## Cross-References
- `AthletePhysiology` entity (where posterior is stored): `01-entities/athlete-physiology.md`
- Threshold detection algorithms (how observations are produced): `02-computations/threshold-detection.md`
- `TwinState` recalibration (triggered after update): `01-entities/twin-state.md`
- Confidence level transitions (downstream of posterior weight): `00-foundations/confidence-model.md`

## Version History
| Version | Change |
|---|---|
| `v1` | Initial Bayesian update with HR deflection sources |
| `v2-rr` | RR inflection source added (Phase 2d); higher weight for HRV |
| `v3-field-test` | Field test source added; automatic detection of CP efforts |
| `v4-lab-test` | Lab test ingestion with full weight dominance |
