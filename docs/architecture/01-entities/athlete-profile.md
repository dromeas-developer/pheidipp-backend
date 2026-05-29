# AthleteProfile — Stable Demographics

## Purpose
- Stores stable physiological and demographic identity distinct from training preferences
- Provides age and sex inputs required for Tier 3 twin bootstrap and cycle tracking

## TypeScript Schema

```typescript
type Sex = 'male' | 'female' | 'not_specified'

type AthleteProfile = {
  athlete_id: string          // UUID, FK → Athlete, one-to-one
  date_of_birth: string       // ISO date YYYY-MM-DD
  sex: Sex
  height_cm: number | null
  weight_kg: number | null
  // Extended fields added by later phases:
  gap_curve_model: GapCurveModel | null           // set by 5d
  weather_response_model: WeatherResponseModel | null  // set by 6b
  banister_constants: BanisterConstants | null    // set by 6d
  cycle_personal_model: CyclePersonalModel | null // set by 4f
  location_lat: number | null                     // added 3d
  location_lng: number | null                     // added 3d
  updated_at: string          // ISO 8601
}

type GapCurveModel = {
  formula: 'population_v1' | 'per_athlete_v1'
  coefficients: { a: number; b: number }
  fitted_from_sessions: number
  fitted_at: string
  r_squared: number
}

type WeatherResponseModel = {
  heat_sensitivity_coeff: number      // population default: 0.006
  fitted_from_sessions: number
  fitted_at: string
  r_squared: number
  heat_index_range_observed: [number, number]
}

type BanisterConstants = {
  aerobic_fitness_tau: number          // population default: 42 days
  aerobic_fatigue_tau: number          // population default: 7 days
  neuromuscular_fitness_tau: number    // population default: 21 days
  neuromuscular_fatigue_tau: number    // population default: 3 days
  structural_fitness_tau: number       // population default: 56 days
  structural_fatigue_tau: number       // population default: 14 days
  fitted_from_weeks: number
  fitted_at: string
}

type CyclePersonalModel = {
  avg_cycle_length_days: number
  phase_boundaries: {
    menstrual_end: number
    follicular_end: number
    ovulatory_end: number
  }
  phase_sensitivity: {
    menstrual: number    // 0.0–1.0; how strongly this athlete shows phase-correlated variation
    follicular: number
    ovulatory: number
    luteal: number
  }
  computed_at: string
}
```

## Invariants
- One `AthleteProfile` per `Athlete`. Created at registration.
- `sex = 'female'` enables menstrual cycle tracking (`CyclePhaseLog`) and cycle modifier in wellness computation.
- `gap_curve_model` is only applied when `r_squared >= 0.70`. Below this, the population formula is used.
- `weather_response_model` is only applied when `r_squared >= 0.65`.
- `banister_constants` replaces population defaults for all subsequent `TwinState` recalibrations once set.
- `cycle_personal_model.phase_sensitivity` of `0.0` means the model detected no phase correlation — cycle modifier is effectively zeroed for this athlete. This is a valid outcome.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| None | — | — | — |

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_ingested` (outdoor, ≥20 sessions) | Triggers `GapCurveFittingTask` | v1 |
| `cycle_day_one_logged` (≥3 complete cycles) | Triggers `CyclePersonalisationTask` | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/profile
Response: 200
  profile: AthleteProfile (gap_curve_model, weather_response_model, banister_constants excluded)
Auth: Bearer JWT, require_self

PATCH /athletes/{athlete_id}/profile
Request:
  height_cm?: number
  weight_kg?: number
  location_lat?: number
  location_lng?: number
Response: 200
  profile: AthleteProfile
Auth: Bearer JWT, require_self
Note: date_of_birth and sex are immutable after creation
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_profiles` | mutable (PATCH for user fields) | strong | indefinite |
| `gap_curve_model` JSONB | mutable (overwritten on refit) | strong | indefinite |
| `cycle_personal_model` JSONB | mutable (overwritten on refit) | strong | indefinite |

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (excluding model fields) | Partial (height, weight, location only) | No |
| Service | Yes | Yes (all fields) | No |
| Repository | Yes | Yes | No |

## Runtime Ownership
Owns:
- Stable demographic data
- Fitted personalisation models (GAP curve, weather, Banister constants, cycle model)

Does Not Own:
- Training preferences (mutable) → `01-entities/athlete-preferences.md`
- When fitting tasks trigger → `02-computations/effort-normalisation.md`, `02-computations/adaptation-signature.md`

## Failure Semantics
- If `GapCurveFittingService` produces `r_squared < 0.70`, `gap_curve_model` is not updated. Population formula continues.
- If location is null, weather fetch is skipped gracefully. No error surfaced.

## Performance Constraints
- `PATCH /athletes/{id}/profile`: p95 < 100ms

## Observability
Metrics:
- `athlete_profile.gap_curve.fitted`: count of athletes with `r_squared >= 0.70`
- `athlete_profile.banister_constants.fitted`: count of athletes with individual constants
Logs:
- `athlete_profile.gap_curve.fitted`: athlete_id, r_squared, session_count
- `athlete_profile.banister_constants.fitted`: athlete_id, fitted_from_weeks

## Implementation Notes
- `date_of_birth` and `sex` are immutable after creation. If an athlete needs to correct them, this requires a support process, not a self-service PATCH.
- The personalisation model JSONB fields are written by background computation services, never by the athlete directly.
- `location_lat/lng` is used only for weather fetch. It is populated from GPS tracks in recent Activity records if not explicitly set by the athlete.
