# RacePrediction — Living Race Finish Time Estimate

## Purpose
- Point-in-time prediction of the athlete's finish time for their goal event
- Updates as fitness evolves; every update creates a new record (the prediction arc)
- B-race predictions generated for secondary events, providing calibration feedback without target-setting pressure
- Not surfaced at LOW confidence; not created for open training blocks

## Vision ↔ Architecture Mapping

> **Product Decision — Race Prediction Is Explicitly Exposed**
> 
> The "coach not dashboard" principle applies to **internal physiological metrics** (CTL/ATL, fitness/fatigue scores, load breakdowns). Race prediction is an **outcome prediction** — the one number a coach *would* tell an athlete: "You're on track for 3:45."
> 
> This is a deliberate exception documented in `docs/vision/coach/race-prediction.md`: *"Watching it improve is one of the most quietly motivating elements."*
> 
> **Boundary:** The prediction is surfaced as a **single number with context** (confidence level, weather adjustment, course adjustment), not as a dashboard of internal model state. The athlete sees the *outcome*, not the *machinery*.

| Vision Concept | Architecture Field / Formula | Notes |
|---|---|---|
| **Baseline Prediction** — "Derived from the twin's current threshold estimates, aerobic capacity indicators, and running economy signals. Assumes standard conditions." | `baseline_prediction_seconds` via `computeBaseline()` | Direct mapping. Uses `observed_pace_at_lt2_sec_per_km`, `lt1_estimate_bpm`, `lt2_estimate_bpm`, `target_distance_km`. |
| **Weather-Adjusted Prediction** — "The system fetches the race day weather forecast and applies the athlete's personalised weather response." | `weather_adjusted_seconds` via `weatherAdjustment()` | Direct mapping. Only computed within 14 days of `TrainingGoal.goal_event_date`. Uses `WeatherResponseModel.heat_sensitivity_coeff` from `AthleteProfile`. |
| **Course Profile Adjustment** — "If the race course profile is available, the prediction incorporates elevation data." | `course_adjusted_seconds` via `courseAdjustment()` | Direct mapping. Uses `ElevationProfile` and per-athlete `GapCurveModel`. |
| **Personalised Weather Response** — "Not how athletes in general respond to heat — how this athlete responds. Individual response curves learned from actual execution data." | `AthleteProfile.weather_response_model.heat_sensitivity_coeff` | Indirect mapping. The coefficient is stored on `AthleteProfile`. The accumulation mechanism (how session-level environmental context refines the coefficient) lives in `02-computations/wellness-modifier.md`, not in this entity. Default population coefficient: `0.006`. |
| **Prediction Arc** — "Watching it improve as fitness builds through a training plan is one of the most quietly motivating elements." | Append-only `race_predictions` table; `GET /prediction/history` returns ordered arc | Direct mapping. Each update creates a new record; old predictions retained indefinitely. |

### Unmapped Vision Requirements

| Vision Requirement | Status | Owner |
|---|---|---|
| "Plain-language explanation of the difference between baseline and weather-adjusted predictions" | **Not stored on entity.** The API response must compose this explanation. | Frontend / API response layer |
| "Weather response model feeds back into training design — suggests heat exposure sessions if race is in heat but athlete trains in mild conditions" | **Not owned by this entity.** This is a proactive coaching behaviour. | `WorkoutGenerationAgent` — should check weather delta between training conditions and race conditions when generating sessions near a goal event |

## TypeScript Schema

```typescript
type PredictionUpdateTrigger =
  | 'activity_sync'        // calibration-eligible session processed
  | 'weather_update'       // race-day forecast updated within 14 days
  | 'course_profile'       // athlete uploaded course GPX
  | 'new_goal'            // new training goal created

type RacePrediction = {
  id: string                             // UUID, PK
  athlete_id: string                     // UUID, FK → Athlete
  training_goal_id: string              // UUID, FK → TrainingGoal
  twin_state_id: string                  // UUID, FK → TwinState used for computation
  predicted_at: string                   // ISO 8601
  target_distance_km: number
  baseline_prediction_seconds: number    // flat course, neutral conditions, fresh athlete
  weather_adjusted_seconds: number | null  // set within 14 days of race; null otherwise
  course_adjusted_seconds: number | null   // set when course profile provided; null otherwise
  course_profile_source: string | null     // URL or upload reference
  weather_forecast_id: string | null       // UUID, FK → WeatherForecast used
  confidence_level: 'medium' | 'high'    // never 'low' — service returns null at LOW
  prediction_method_version: string
}
```

## Baseline Prediction Formula

```typescript
// Grounded in actual observed threshold pace from recent sessions,
// not just the TwinState lt2_estimate_bpm
// This makes the prediction more robust to model uncertainty

type BaselinePredictionInputs = {
  observed_pace_at_lt2_sec_per_km: number  // from last 3 calibration threshold sessions
  lt1_estimate_bpm: number                 // from TwinState
  lt2_estimate_bpm: number                 // from TwinState
  target_distance_km: number
}

function computeBaseline(inputs: BaselinePredictionInputs): number {
  const { observed_pace_at_lt2_sec_per_km, lt1_estimate_bpm, lt2_estimate_bpm, target_distance_km } = inputs

  // Aerobic base ratio: how wide the aerobic base is relative to threshold
  // Higher ratio → better aerobic efficiency → less pace degradation over distance
  const aerobic_base_ratio = lt1_estimate_bpm / lt2_estimate_bpm

  // Endurance factor: how much slower than threshold pace for a given distance
  // population curve; adjusted by aerobic_base_ratio
  const endurance_factor = distanceEnduranceCurve(target_distance_km, aerobic_base_ratio)
  // Examples: 5K ≈ 0.97, half marathon ≈ 0.90, marathon ≈ 0.83 at median base ratio

  const predicted_pace = observed_pace_at_lt2_sec_per_km / endurance_factor
  return Math.round(predicted_pace * target_distance_km)
}
```

`observed_pace_at_lt2_sec_per_km` requires at least 1 calibration-eligible threshold session. If none exist, falls back to raw `lt2_estimate_bpm` converted via population HR-to-pace curve. Confidence is flagged lower in this fallback case.

## Course Adjustment

```typescript
// Uses effort normalisation Generation 2 or 3 (per athlete profile)
function courseAdjustment(
  baseline_seconds: number,
  elevation_data: ElevationProfile,
  gap_model: GapCurveModel | null
): number {
  const difficulty_factor = computeCourseDifficultyFactor(elevation_data, gap_model)
  return Math.round(baseline_seconds * difficulty_factor)
}
// difficulty_factor > 1.0 for net positive elevation; < 1.0 for net negative
```

## Weather Adjustment (Race Day)

```typescript
function weatherAdjustment(
  baseline_seconds: number,
  weather_forecast: WeatherForecast,
  weather_response_model: WeatherResponseModel | null,
  cycle_temp_offset_c: number  // 0.0 if not luteal phase
): number {
  const effective_heat_index = weather_forecast.heat_index_c + cycle_temp_offset_c
  const coeff = weather_response_model?.heat_sensitivity_coeff ?? 0.006
  const heat_factor = heatPaceAdjustment(effective_heat_index, coeff)
  const wind_factor = windPaceAdjustment(weather_forecast.wind_speed_ms, true)  // assume headwind
  return Math.round(baseline_seconds * heat_factor * wind_factor)
}
```

## Invariants
- `RacePredictionService` returns `null` and writes no record when `TwinState.confidence_level = 'low'`. The API endpoint returns 204.
- Only created for `TrainingGoal.goal_type = 'race_event'`. Open training goals return 204.
- Every update trigger creates a new record. Old predictions are retained — they form the prediction arc visible in history.
- `weather_adjusted_seconds` is only computed and set within 14 days of `TrainingGoal.goal_event_date`. Before that window, it is null.
- Records are never modified after creation.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `race_prediction_updated` | New record created | v1 | `{race_prediction_id, training_goal_id, baseline_prediction_seconds, confidence_level, update_trigger}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `twin_recalibrated` | Triggers `RacePredictionService.compute()` | v1 |
| `weather_forecast_fetched` (within 14 days) | Triggers weather adjustment recomputation | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/prediction
Response: 200 | 204
  prediction: RacePredictionResponse  # most recent for active block
  # 204 when: confidence=low, goal_type≠race_event, or no prediction yet
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/prediction/history
Response: 200
  predictions: RacePredictionResponse[]  # all for active block; ordered predicted_at desc
  # The prediction arc — shows fitness progression
Auth: Bearer JWT, require_self

POST /athletes/{athlete_id}/prediction/course-profile
Request:
  profile_url?: string      # public URL to GPX
  # or multipart GPX file upload
Response: 200
  prediction: RacePredictionResponse  # recomputed with course adjustment
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `race_predictions` table | append-only | strong | indefinite |

Index: `(athlete_id, training_goal_id, predicted_at DESC)` for latest prediction query.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (read-only except course-profile trigger) | No | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- Prediction record storage and arc history
- Confidence gating (null at LOW; not written at LOW)

Does Not Own:
- Prediction formula → `02-computations/race-prediction.md`
- Course adjustment formula → `02-computations/effort-normalisation.md`
- Weather adjustment formula → `02-computations/wellness-modifier.md`

## Failure Semantics
- `RacePredictionService` failure → previous prediction remains current; error logged; no 5xx to athlete (prediction is background-computed)
- `observed_pace_at_lt2` fallback (no threshold sessions yet) → prediction created with note in `prediction_method_version`

## Performance Constraints
- `GET /prediction`: p95 < 50ms (indexed lookup)
- `RacePredictionService.compute()`: p95 < 500ms (reads recent sessions + TwinState)

## Observability
Metrics:
- `race_prediction.created.total`: by update_trigger
- `race_prediction.confidence_distribution`: medium vs high at creation
- `race_prediction.improvement_rate`: percentage of consecutive predictions where baseline improved
