# AthletePhysiology — Physiological Parameter Estimates

## Purpose
- Stores the current best estimate of the athlete's stable physiological parameters
- Maintains the full measurement history that produced each estimate
- The authoritative source of LT1, LT2, FTP, VO2max, and max HR for all downstream consumers

## TypeScript Schema

```typescript
type PhysiologyParameter = 'lt1_bpm' | 'lt2_bpm' | 'ftp_watts' | 'vo2max_ml_kg_min' | 'max_hr_bpm'

type MeasurementSource =
  | 'questionnaire_estimate'   // Tier 3 bootstrap from age/fitness_level population norms
  | 'training_hr_deflection'   // HR deflection analysis from calibration-eligible session
  | 'training_rr_inflection'   // HRV inflection from RR intervals — higher quality than HR deflection
  | 'training_power_hr_ratio'  // Power-to-HR ratio breakpoint — supplementary; FTP only
  | 'field_test'               // Structured field protocol (20-min FTP, critical power, time trial)
  | 'lab_test'                 // Gold standard: lactate profile, VO2max direct measurement

// One record per parameter with its full posterior state
type PhysiologyParameterState = {
  value: number                      // posterior mean — the current best estimate
  uncertainty: number                // posterior standard deviation
  prior_weight: number               // accumulated Bayesian evidence weight (decayed over time)
  dominant_source: MeasurementSource // the source type that currently dominates the posterior
  last_observation_date: string      // YYYY-MM-DD; when the most recent observation was made
}

type AthletePhysiology = {
  id: string                        // UUID, PK
  athlete_id: string                // UUID, FK → Athlete (one-to-one; current state)
  lt1: PhysiologyParameterState
  lt2: PhysiologyParameterState
  ftp: PhysiologyParameterState | null    // null until power data processed
  vo2max: PhysiologyParameterState | null // null until sufficient progressive data
  max_hr: PhysiologyParameterState
  updated_at: string                // ISO 8601; updated on every Bayesian update
}

// Append-only log of every observation that contributed to the posterior
type PhysiologyMeasurement = {
  id: string                        // UUID, PK
  athlete_id: string                // UUID, FK → Athlete
  parameter: PhysiologyParameter
  observed_value: number
  source: MeasurementSource
  observation_weight: number        // the weight this observation carries in the posterior
  measurement_date: string          // YYYY-MM-DD; when the measurement was taken
  activity_id: string | null        // FK → Activity; for training-derived observations
  raw_data_reference: string | null // for lab tests: URL or upload reference
  notes: string | null              // free text; e.g. "Sprint Triathlon Physiology Lab, March 2024"
  created_at: string
}
```

## Observation Weights by Source

These weights determine how much each observation shifts the posterior. Higher weight = more authoritative measurement.

| Source | LT1 weight | LT2 weight | FTP weight | VO2max weight | Max HR weight |
|---|---|---|---|---|---|
| `questionnaire_estimate` | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| `training_hr_deflection` | 1.0 | 1.0 | — | — | 0.5 |
| `training_rr_inflection` | 2.5 | 2.5 | — | — | 0.5 |
| `training_power_hr_ratio` | — | 1.0 | 1.5 | — | — |
| `field_test` | 2.0 | 4.0 | 5.0 | 3.0 | 2.0 |
| `lab_test` | 12.0 | 15.0 | 10.0 | 15.0 | 8.0 |

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

## Lab Test — How It Flows Through the System

A lab test is the highest-authority physiological input. It carries observation weight 12-15 depending on the parameter, which dominates a typical accumulated prior of 20-40 weight units built from 2 years of regular training.

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

For a 20-minute FTP test, the conventional estimate is `observed_power_20min * 0.95`. The system accepts the estimated FTP value rather than computing it — the athlete or coach applies the 0.95 correction before entry.

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

## Invariants
- One `AthletePhysiology` record per athlete. **Mutable** — posterior estimates are updated in place. The full history is in `PhysiologyMeasurement` which is append-only.
- `ftp` and `vo2max` are null until a qualifying observation is made. They are never bootstrapped from questionnaire estimates — the uncertainty would be too high to be useful.
- `max_hr` is bootstrapped from `220 - age` at onboarding. It updates from observed maximum HR across sessions and is often the most accurate estimate for experienced athletes.
- `dominant_source` on each parameter reflects the source that currently dominates the posterior. For a recently lab-tested athlete this is `lab_test`; for a well-trained athlete with no lab data this is `training_rr_inflection`.
- `prior_weight` decays over time via the formula above. After ~3 years with no new observations, the prior weight approaches zero — the system becomes appropriately uncertain and reverts toward more conservative coaching language.

## State Transitions

```mermaid
stateDiagram-v2
    [*] --> bootstrapped : questionnaire_estimate\n(all parameters; low weight)
    bootstrapped --> training_calibrated : training_hr_deflection or\ntraining_rr_inflection\n(4 sessions → MEDIUM confidence)
    training_calibrated --> training_calibrated : ongoing training updates\n(slow posterior drift)
    training_calibrated --> field_calibrated : field_test observation\n(dominant source shifts)
    training_calibrated --> lab_calibrated : lab_test observation\n(dominant source shifts strongly)
    field_calibrated --> lab_calibrated : lab_test supersedes
    lab_calibrated --> training_calibrated : prior decays over ~18 months\n(lab weight < training accumulated weight)
```

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `physiology_updated` | Any parameter posterior shifts > 1 unit | v1 | `{athlete_id, parameters_updated: PhysiologyParameter[], dominant_sources: Record<string, MeasurementSource>}` |
| `physiology_lab_test_ingested` | lab_test measurement created | v1 | `{athlete_id, parameters_measured: PhysiologyParameter[], notes}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_calibration_eligible` | Triggers `ThresholdDetectionService` → `PhysiologyUpdateService` | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/physiology
Response: 200
  physiology: AthletePhysiologyResponse
  # Includes parameter states but not full measurement history
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/physiology/measurements
Query:
  parameter?: PhysiologyParameter
  source?: MeasurementSource
  from?: date
  to?: date
  limit?: number (default 50)
Response: 200
  measurements: PhysiologyMeasurementResponse[]
Auth: Bearer JWT, require_self

POST /athletes/{athlete_id}/physiology/measurements
Description: Enter lab test, field test, or manual measurement results
Request:
  measurements:
    - parameter: PhysiologyParameter, required
      observed_value: number, required
      source: MeasurementSource, required  # field_test or lab_test only; training sources are auto-detected
      measurement_date: string, required
      raw_data_reference?: string
      notes?: string
Response: 201
  measurements: PhysiologyMeasurementResponse[]
  updated_physiology: AthletePhysiologyResponse
  recalibration_triggered: boolean
Auth: Bearer JWT, require_self
Note: source must be 'field_test' or 'lab_test' for manual entry.
      Training-derived sources are created automatically by ThresholdDetectionService.
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_physiology` table | mutable (posterior updated in place) | strong | indefinite |
| `physiology_measurements` table | append-only | strong | indefinite |

Unique constraint: `(athlete_id)` on `athlete_physiology` — one record per athlete.
Index: `(athlete_id, parameter, measurement_date DESC)` on `physiology_measurements`.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes | POST /measurements only | No |
| Service | Yes | upsert (physiology), insert (measurements) | No |
| Repository | Yes | Yes | No |

## Runtime Ownership
Owns:
- Current posterior estimates for all physiological parameters
- Full measurement history (source, weight, date)
- The Bayesian update computation

Does Not Own:
- How training sessions produce observations → `02-computations/threshold-detection.md`
- Fitness and fatigue Banister scores → `01-entities/athlete-fitness.md`
- TwinState assembly → `01-entities/twin-state.md`

## Idempotency
- Submitting identical lab test measurements twice creates two `PhysiologyMeasurement` records but shifts the posterior only once from the first. The second is a duplicate that does not trigger recalibration (detected by: same `parameter`, `observed_value`, `measurement_date`, `source`).

## Failure Semantics
- `PhysiologyUpdateService` failure → `PhysiologyMeasurement` still written; posterior not updated; retry scheduled; existing estimates remain valid
- Invalid measurement value (e.g. LT2 < LT1) → 422 with specific validation error; no record written

## Performance Constraints
- `GET /physiology`: p95 < 30ms
- `POST /physiology/measurements` (with recalibration): p95 < 500ms (recalibration is async)

## Observability
Metrics:
- `athlete_physiology.dominant_source.distribution`: by parameter (monitors data quality across athlete base)
- `athlete_physiology.lab_test.ingested.total`: count of lab test inputs
- `athlete_physiology.prior_weight.distribution`: by parameter (monitors how well-calibrated athletes are)
Logs:
- `physiology.updated`: athlete_id, parameters_updated, dominant_source_after
- `physiology.lab_test.ingested`: athlete_id, parameters_measured

## Implementation Notes
- The `dominant_source` field is informational — it reflects the source type that currently holds the most weight in the posterior, not the most recent observation. A training session done today does not make `dominant_source = training_hr_deflection` if the prior is still dominated by last month's lab test.
- The prior decay formula uses 42 days as the time constant. This is the same time constant used for aerobic fitness in the Banister model — a deliberate alignment so that threshold estimates and fitness scores decay at roughly the same rate. As fitness drifts, so does the reliability of older threshold observations.
- For onboarding, `max_hr = 220 - age` with weight 0.5 is the bootstrap. It is quickly superseded by the first session where the athlete reaches near-maximum HR. The questionnaire does not ask for max HR directly because self-reported max HR is notoriously inaccurate.