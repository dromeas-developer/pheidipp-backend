# 3d — Weather Integration
*WeatherForecast model, heat/wind adjustment, two-column distinction fully live*

## Objective

Apply weather context to every generated workout. The two-column display now has
three independent modifiers feeding `adjusted_targets`: the recovery modifier
(from 3b), the cycle thermoregulatory modifier (from 3c), and weather. An athlete
on a hot humid day receives targets that reflect actual physiological conditions.

## Scope

`WeatherForecast` model. Weather API client. Async weather fetch task.
Heat index and wind adjustment computation. Stacking with existing modifiers.
`adjusted_targets` updated to reflect all three modifiers combined.

## Non-Goals

- Personalised weather response curves (replacing population adjustments with
  individual curves) — deferred to 6b (requires accumulated execution history
  across varied conditions)
- Race-day weather prediction in the race prediction service — deferred to 4g
  (race prediction itself is 4g)
- Weather-based proactive coach messages — deferred to 4e

## Architecture References

- `WeatherForecast` model fields:
  `architecture/wellness-and-modifiers.md` → WeatherForecast
- Heat index and wind adjustment formulas:
  `architecture/wellness-and-modifiers.md` → Weather Adjustment Computation
- Luteal modifier stacking with weather (additive on heat_index_c):
  `architecture/wellness-and-modifiers.md` → Thermoregulatory Modifier — Luteal Phase
- Graceful degradation when forecast unavailable:
  `architecture/wellness-and-modifiers.md` → WeatherForecast

## Dependencies

Requires 3b (adjusted_targets infrastructure), 3c (luteal temperature offset
available on context object for stacking).

## Models Introduced

**`WeatherForecast`** — weather data per athlete per training date.
Full field spec from `architecture/wellness-and-modifiers.md`:
`athlete_id` FK, `forecast_date`, `training_window_start`,
`temperature_c`, `humidity_pct`, `heat_index_c`, `wind_speed_ms`,
`wind_direction_degrees`, `precipitation_probability`,
`source_api`, `fetched_at`, `forecast_horizon_hours`.
Unique constraint on `(athlete_id, forecast_date)` — upsert on new forecast.

## Services & Tasks Introduced

**`WeatherApiClient`** (async) — abstraction over a weather API.
- `fetch_forecast(lat, lng, date, hour) → WeatherData`
- Weather API provider is configurable — abstracted behind this interface.
- Athlete location sourced from `AthletePreferences` (location field added — see
  Models Modified below) or derived from GPS tracks in recent Activity records.

**`WeatherFetchTask`** (async worker) — fetches and stores forecast for upcoming
workout days.
- Runs on workout generation trigger and daily as a proactive prefetch.
- Calls `WeatherApiClient.fetch_forecast()` for the athlete's training window.
- Upserts `WeatherForecast` record.
- On fetch failure: logs the failure, proceeds with null forecast.
  Workout generation falls back to `adjusted_targets = theoretical_targets`
  with `recovery_modifier_reason` noting weather data was unavailable.

**`WeatherAdjustmentService`** (sync, Python) — computes pace adjustment factor.
- `compute(weather_forecast, cycle_temp_offset_c) → (float, str)`
  Returns `(pace_adjustment_factor, plain_language_reason)`.
  Applies the heat index formula and wind formula from arch reference.
  Stacks `cycle_temp_offset_c` (from `CyclePhaseService`, 0.0 if not applicable)
  onto `heat_index_c` before computing heat stress.
  Returns factor of 1.0 (no adjustment) when forecast is null.

## Models Modified

**`AthletePreferences`** — adds `location_lat` (nullable float) and `location_lng`
(nullable float). Used as the weather fetch location.
Populated from GPS tracks in recent Activity records if not explicitly set.
Added via migration.

## Services Modified

**`WorkoutGenerationAgent`** (updated) — full modifier stack now applied:
1. `WellnessModifierService.classify()` → recovery modifier level + target scale
2. `CyclePhaseService.get_current_phase()` → cycle temp offset for female athletes
3. `WeatherAdjustmentService.compute()` → weather pace factor
4. Combined `pace_adjustment_factor` applied to `theoretical_targets` to produce
   `adjusted_targets`.
5. `recovery_modifier_reason` updated to include weather context as a structured
   component alongside the wellness reason.

## Key Constraints

- Weather fetch failures are silent from the athlete's perspective — the workout
  is generated without weather adjustment. No error is surfaced to the athlete.
- `adjusted_targets` and `theoretical_targets` are always both written.
  On a neutral day (no wellness suppression, no heat, no cycle modifier):
  they are identical.
- The `pace_adjustment_factor` is applied to pace targets only. HR zone targets
  are not scaled — the athlete's HR zones do not change in heat, but their pace
  at a given HR does.
- Location is required for weather fetch. If neither `location_lat/lng` nor recent
  GPS activity tracks exist, the weather fetch is skipped gracefully.

## Done Criteria

- A workout generated on a forecast day of 28°C and 70% humidity shows
  `adjusted_targets` with pace targets approximately 3-5% slower than
  `theoretical_targets`, with a plain-language reason referencing heat conditions.
- A workout generated on a 12°C day with no wind shows `adjusted_targets`
  equal to `theoretical_targets`.
- A weather API fetch failure produces a valid workout with `adjusted_targets`
  equal to `theoretical_targets` — no errors, no blocked generation.
- A luteal-phase female athlete on a 24°C day receives a combined adjustment
  reflecting both the thermal modifier and the weather, greater than either alone.
