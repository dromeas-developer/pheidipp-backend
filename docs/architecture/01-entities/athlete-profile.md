# AthleteProfile — Stable Demographics

## Purpose
- Stores stable physiological and demographic identity distinct from training preferences
- Provides age and sex inputs required for Tier 3 twin bootstrap and cycle tracking

**Design Note — Body Composition Exclusion:**

`AthleteProfile` does not include `weight_kg` or other body composition metrics. These are time-series signals ingested via `AthleteWellness` and `BodyCompositionRecord` (see `01-entities/athlete-wellness.md`).

Rationale:
- Weight fluctuates and requires longitudinal tracking with dates and sources
- Body composition belongs to the wellness domain, not demographic identity
- Registration friction is reduced by deferring weight collection to first wellness sync

## TypeScript Schema

```typescript
type Sex = 'male' | 'female' | 'not_specified'

type AthleteProfile = {
  id: string                         // UUID, PK
  athlete_id: string          // UUID, FK → Athlete, one-to-one
  date_of_birth: string       // ISO date YYYY-MM-DD
  sex: Sex
  height_cm: number | null
  gap_curve_model: GapCurveModel | null           // per-athlete GAP curve (null = use population)
  weather_response_model: WeatherResponseModel | null  // per-athlete weather response (null = use population)
  banister_constants: BanisterConstants | null     // per-athlete fitted time constants (null = use population defaults in AthleteFitness)
  cycle_personal_model: CyclePersonalModel | null  // per-athlete cycle model (null = no cycle tracking)
  location_lat: number | null
  location_lng: number | null
  timezone: string                          // IANA timezone identifier, e.g. "Australia/Sydney", "America/Los_Angeles"
  training_window: {                        // athlete's preferred training time window (local time)
    start: string                           // HH:MM 24-hour, e.g. "06:00"
    end: string                             // HH:MM 24-hour, e.g. "20:00"
  } | null
  updated_at: string          // ISO 8601

  // Effort normalisation generation state (hysteresis)
  current_effort_generation: 1 | 2 | 3  // maintained by GapCurveFittingService; default: 1

  // Crossover athlete structural load adjustment
  structural_risk_flag: boolean          // true for crossover athletes (non-running primary sport background)
                                        // Computed at onboarding from AthletePreferences.sport_background
                                        // Conditions structural load density penalty (0.08 vs 0.12)
                                        // See 02-computations/load-computation.md

  // Per-athlete objective evaluation thresholds
  objective_thresholds: ObjectiveThresholds | null  // per-athlete thresholds for objective evaluation (null = use population defaults)
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
  aerobic: {
    fitness_tau_days: number          // population default: 42
    fatigue_tau_days: number          // population default: 7
  }
  neuromuscular: {
    fitness_tau_days: number          // population default: 21
    fatigue_tau_days: number          // population default: 3
  }
  structural: {
    fitness_tau_days: number          // population default: 56
    fatigue_tau_days: number          // population default: 14
  }
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
  luteal_temp_sensitivity: number  // multiplier on LUTEAL_TEMP_OFFSET_C (0.35); population default: 1.0
  fitted_from_cycles: number       // number of complete cycles used for fitting
  computed_at: string
}

type ObjectiveThresholds = {
  pacing_discipline?: number        // default: 0.03 (3% variance)
  encroachment_events?: number      // default: 3 events
  // ... other objective categories
}
```

## Invariants
- One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.
- `sex = 'female'` enables menstrual cycle tracking (`CyclePhaseLog`) and cycle modifier in wellness computation.
- `gap_curve_model` is applied when `current_effort_generation >= 2`. Upgrade to Gen 2 requires `r_squared >= 0.70`; downgrade to Gen 1 requires `r_squared < 0.65`. See `02-computations/effort-normalisation.md` for the hysteresis state machine.
- `weather_response_model` is only applied when `r_squared >= 0.65`.
- `banister_constants` stores per-athlete fitted time constants. When set, `AthleteFitness.time_constants` references these values (source='individual_fitted'). When null, `AthleteFitness.time_constants` uses population defaults (source='population_default').
- `cycle_personal_model.phase_sensitivity` of `0.0` means the model detected no phase correlation — cycle modifier is effectively zeroed for this athlete. This is a valid outcome.
- `cycle_personal_model.luteal_temp_sensitivity` of `1.0` means the population default thermoregulatory offset applies. Values <1.0 indicate lower-than-average thermal sensitivity; >1.0 indicate higher. When `cycle_personal_model` is null, `LUTEAL_TEMP_OFFSET_C` (0.35) applies at full population weight.
- `timezone` is required at onboarding (validated against IANA tz database). Immutable after creation — changing timezone requires a support process. All scheduled tasks (MissedSessionSweepTask, WorkoutPrefetchTask) and date interpretations use this timezone.
- `training_window` defaults to 06:00–20:00 if not set. Mutable via PATCH. Only used by WorkoutPrefetchTask for prefetch timing. MissedSessionSweepTask uses timezone only, not training_window.
- `structural_risk_flag` is computed at onboarding from `AthletePreferences.sport_background`. When `true`, the structural load density penalty coefficient is 0.08 (vs 0.12 population default). See `02-computations/load-computation.md`.
- `objective_thresholds` stores per-athlete evaluation thresholds for objective management. When null, population defaults are used (0.03 for pacing discipline, 3 for encroachment events). See `02-computations/objective-management.md`.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| None | — | — | — |

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_ingested` (outdoor, ≥20 sessions) | Triggers `GapCurveFittingTask` | v1 |
| `activity_ingested` (outdoor, ≥25 sessions, heat_index range ≥10°C) | Triggers `WeatherResponseCurveFittingTask` | v1 |
| `cycle_day_one_logged` (≥3 complete cycles) | Triggers `CyclePersonalisationTask` | v1 |

## Cycle Personalisation Fitting

`CyclePersonalisationTask` runs when `cycle_day_one_logged` fires and ≥3 complete cycles exist. It produces `cycle_personal_model` — a JSONB field overwritten on each refit.

### Fitting Stages

**Stage 1 — Cycle length:** Compute median interval between consecutive `cycle_day_one_date` entries. Minimum 3 intervals (4 log entries). Stored as `avg_cycle_length_days`.

**Stage 2 — Phase boundaries:** Analyse execution data (pace-at-HR ratio, GAP deviation, RPE) across cycles to detect phase transitions. Fit `menstrual_end`, `follicular_end`, `ovulatory_end` to observed transition points. Fallback: proportional boundaries (`cycle_length * 5/28`, etc.) if execution data is insufficient.

**Stage 3 — Phase sensitivity:** For each phase, compare execution quality in that phase vs overall baseline. Compute `phase_sensitivity[phase]` as a multiplier on the population prior adjustment:
- `0.0` = no phase correlation detected (adjustment zeroed)
- `1.0` = full population effect
- `>1.0` = stronger than population average

**Stage 4 — Luteal thermoregulation:** Compare pace-at-HR in luteal vs follicular phases, controlling for ambient temperature (using `weather_response_model`). Compute `luteal_temp_sensitivity` as a multiplier on `LUTEAL_TEMP_OFFSET_C` (0.35). Population default: 1.0.

### Fitting Prerequisites

| Stage | Minimum data | Graceful fallback |
|---|---|---|
| Cycle length | 3 complete cycles (4 log entries) | Use 28-day default |
| Phase boundaries | 3 cycles + ≥2 quality sessions per phase per cycle | Proportional boundaries from cycle length |
| Phase sensitivity | 3 cycles + sufficient execution data per phase | `phase_sensitivity` = 1.0 (full population effect) |
| Luteal thermoregulation | 3 cycles + outdoor sessions in both luteal and follicular at similar ambient temps | `luteal_temp_sensitivity` = 1.0 (population default) |

### Refit Behaviour

`cycle_personal_model` is overwritten on each refit (not accumulated). The fitting task re-runs when new cycle data arrives (≥3 complete cycles). Earlier fits with fewer cycles produce less reliable models; later fits with more cycles produce more reliable models. The system always uses the most recent fit.

## APIs

```yaml
GET /athletes/{athlete_id}/profile
Response: 200
  profile: AthleteProfile (gap_curve_model, weather_response_model, banister_constants excluded)
Auth: Bearer JWT, require_self

PATCH /athletes/{athlete_id}/profile
Request:
  height_cm?: number
  location_lat?: number
  location_lng?: number
  training_window?: { start: string; end: string }  // athlete's preferred training time window (local time)
Response: 200
  profile: AthleteProfile
Auth: Bearer JWT, require_self
Note: date_of_birth, sex, and timezone are immutable after creation
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_profiles` table | mutable (PATCH for user fields) | strong | indefinite |
| `gap_curve_model` JSONB | mutable (overwritten on refit) | strong | indefinite |
| `cycle_personal_model` JSONB | mutable (overwritten on refit) | strong | indefinite |

Unique constraint: `(athlete_id)` — one record per athlete.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (excluding model fields) | height_cm, location_lat, location_lng, training_window | No |
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
- If `GapCurveFittingService` produces `r_squared < 0.70` and `current_effort_generation == 1`, `gap_curve_model` is not updated. Population formula continues.
- If `GapCurveFittingService` produces `r_squared < 0.65` and `current_effort_generation == 2`, `current_effort_generation` is downgraded to 1.
- If `GapCurveFittingService` produces `r_squared >= 0.70` and `current_effort_generation == 1`, `current_effort_generation` is upgraded to 2.
- If location is null, weather fetch is skipped gracefully. No error surfaced.

## Performance Constraints
- `PATCH /athletes/{id}/profile`: p95 < 100ms

## Observability
Metrics:
- `athlete_profile.gap_curve.fitted`: count of athletes with `r_squared >= 0.70`
- `athlete_profile.gap_curve.generation_transition`: count of generation upgrades and downgrades (by direction)
- `athlete_profile.banister_constants.fitted`: count of athletes with individual constants
- `athlete_profile.cycle_personal_model.fitted`: count of athletes with fitted cycle models
- `athlete_profile.cycle_personal_model.sensitivity_zeroed`: count of athletes where `phase_sensitivity` = 0.0 for any phase (no correlation detected)
Logs:
- `athlete_profile.gap_curve.fitted`: athlete_id, r_squared, session_count
- `athlete_profile.banister_constants.fitted`: athlete_id, fitted_from_weeks
- `athlete_profile.cycle_personal_model.fitted`: athlete_id, fitted_from_cycles, avg_cycle_length_days

## Implementation Notes
- `date_of_birth` and `sex` are immutable after creation. If an athlete needs to correct them, this requires a support process, not a self-service PATCH.
- The personalisation model JSONB fields are written by background computation services, never by the athlete directly.
- `location_lat/lng` is used only for weather fetch. It is populated from GPS tracks in recent Activity records if not explicitly set by the athlete.
