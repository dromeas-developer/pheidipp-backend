# WeatherForecast — Training Window Weather Data

## Purpose
- Stores fetched weather conditions for an athlete's planned training window on a given date
- Feeds adjusted_targets computation in GeneratedWorkout via WeatherAdjustmentService
- Also feeds race-day weather adjustment in RacePrediction within 14 days of the event

## TypeScript Schema

```typescript
type WeatherForecast = {
  id: string                      // UUID, PK
  athlete_id: string              // UUID, FK → Athlete
  forecast_date: string           // YYYY-MM-DD; unique per athlete per date
  training_window_start: string   // HH:MM; from AthletePreferences.training_time_of_day
  temperature_c: number
  humidity_pct: number            // 0–100
  heat_index_c: number            // computed from temperature + humidity
  wind_speed_ms: number
  wind_direction_degrees: number  // 0–360
  precipitation_probability: number  // 0.0–1.0
  source_api: string              // which weather API provided the data
  fetched_at: string              // ISO 8601
  forecast_horizon_hours: number  // how far ahead this forecast was when fetched
}
```

## Heat Index Computation

`heat_index_c` is computed from `temperature_c` and `humidity_pct` using the Rothfusz regression formula. This is the primary thermal stress input — not raw temperature.

```typescript
// Simplified Steadman approximation (valid for T >= 27°C, RH >= 40%)
// For lower temperatures/humidity, heat_index ≈ temperature_c
function computeHeatIndex(tempC: number, humidityPct: number): number {
  if (tempC < 27 || humidityPct < 40) return tempC
  const T = tempC * 9/5 + 32  // convert to Fahrenheit
  const H = humidityPct
  const HI = -42.379 + 2.04901523*T + 10.14333127*H
    - 0.22475541*T*H - 0.00683783*T*T
    - 0.05481717*H*H + 0.00122874*T*T*H
    + 0.00085282*T*H*H - 0.00000199*T*T*H*H
  return (HI - 32) * 5/9  // convert back to Celsius
}
```

## Adjustment Formulas

Applied by `WeatherAdjustmentService` to produce `adjusted_targets`:

```typescript
// Heat adjustment (pace and power targets only — HR targets unchanged)
// HR is relative to current physiology, not affected by environmental conditions
const NEUTRAL_HEAT_INDEX = 15.0   // °C
const HEAT_COEFFICIENT = 0.006    // population default; replaced by individual in 6b

function heatAdjustment(heatIndexC: number, individualCoeff?: number): number {
  const coeff = individualCoeff ?? HEAT_COEFFICIENT
  const heatStress = Math.max(0, heatIndexC - NEUTRAL_HEAT_INDEX)
  return 1.0 + (heatStress * coeff)
  // e.g. 28°C heat index → factor 1.078 → 7.8% pace reduction
}

// Wind adjustment (pace targets only)
function windAdjustment(windSpeedMs: number, isHeadwind: boolean): number {
  if (isHeadwind) return 1.0 + (windSpeedMs * 0.003)
  return 1.0 - (windSpeedMs * 0.001)  // tailwind benefit is ~1/3 of headwind cost
}

function applyWeatherAdjustment(
  targets: TargetSet,
  heatIndexC: number,
  windSpeedMs: number,
  isHeadwind: boolean,
  individualHeatCoeff?: number
): TargetSet {
  const heatFactor = heatAdjustment(heatIndexC, individualHeatCoeff)
  const windFactor = windAdjustment(windSpeedMs, isHeadwind)
  const combinedFactor = heatFactor * windFactor
  
  return {
    targets: targets.targets.map(target => {
      if (target.signal_type === 'gap' && target.primary.min !== null) {
        // GAP: environmental stress → slower pace → higher sec/km
        return {
          ...target,
          primary: {
            min: Math.round(target.primary.min * combinedFactor),
            max: target.primary.max !== null ? Math.round(target.primary.max * combinedFactor) : null,
            unit: target.primary.unit
          }
        }
      }
      if (target.signal_type === 'power' && target.primary.min !== null) {
        // Power: environmental stress → reduced sustainable power
        return {
          ...target,
          primary: {
            min: Math.round(target.primary.min / combinedFactor),
            max: target.primary.max !== null ? Math.round(target.primary.max / combinedFactor) : null,
            unit: target.primary.unit
          }
        }
      }
      // HR and description targets unchanged by weather
      return target
    }),
    description: targets.description
  }
}
```

The luteal thermoregulatory modifier (from `CyclePhaseLog`) adds to `heat_index_c` before these formulas run. The stacking is additive because the mechanisms are physiologically distinct.

## Invariants
- Unique constraint on `(athlete_id, forecast_date)`. Upsert on conflict — a later fetch for the same date updates the record with a fresher forecast.
- If the weather API fetch fails, no `WeatherForecast` record is created. `WorkoutGenerationAgent` proceeds with `adjusted_targets = theoretical_targets` and notes the absence in `recovery_modifier_reason`.
- `heat_index_c` is always computed at ingestion — never stored null.
- Location sourced from `AthleteProfile.location_lat/lng`. If null, weather fetch is skipped.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `weather_forecast_fetched` | Record upserted | v1 | `{athlete_id, forecast_date, heat_index_c, wind_speed_ms}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `training_plan_generated` | Prefetch for upcoming session dates | v1 |
| `planned_session_generated` | Fetch for this session's date | v1 |

## APIs
No public API. `WeatherForecast` is internal — read by `WeatherAdjustmentService` only.

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `weather_forecasts` table | upsert (fresher forecast wins) | eventual | 90 days |

Index: `(athlete_id, forecast_date)` for workout generation lookup.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | No | No | No |
| Service | Yes | upsert | No |
| Repository | Yes | upsert | No |

## Runtime Ownership
Owns:
- Fetched weather data and heat index computation
- Upsert semantics (fresher forecast replaces older)

Does Not Own:
- Adjustment formulas application → `02-computations/wellness-modifier.md`
- Personalised weather response curves → `01-entities/athlete-profile.md` (`weather_response_model`)
- Race day weather for prediction → `01-entities/race-prediction.md`

## Failure Semantics
- API fetch failure → no record; graceful degradation in workout generation
- No retry — weather will be re-fetched on the next workout generation trigger

## Performance Constraints
- Weather API call: p95 < 2s (external dependency; timeout at 3s)
- `WeatherFetchTask` scheduled prefetch: runs 18 hours before planned training window

## Observability
Metrics:
- `weather_forecast.fetch.success_rate`
- `weather_forecast.fetch.latency_ms`
- `weather_forecast.heat_index.distribution`: histogram monitoring condition extremes
