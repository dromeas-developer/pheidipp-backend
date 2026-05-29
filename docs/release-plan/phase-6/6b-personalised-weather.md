# 6b — Personalised Weather Response
*Individual weather curves replacing population adjustments*

## Objective

Replace the population-level weather adjustment formula with individual curves
learned from the athlete's actual execution history across varied conditions.
Some athletes are heat-resilient; others degrade significantly above 18°C. The
model now knows which.

## Scope

`WeatherResponseCurveFittingService`. `AthleteProfile.weather_response_model` field.
`WeatherAdjustmentService` updated to use individual curve when available.
Race prediction updated to use individual curve.

## Architecture References

- Generation 3 personalised effort model (weather response is a component):
  `architecture/effort-normalisation.md` → Generation 3
- Weather adjustment formulas (population defaults to replace):
  `architecture/wellness-and-modifiers.md` → Weather Adjustment Computation
- Vision-level weather response individualisation:
  `vision/coach/race-prediction.md` → Personalised Weather Response Modelling

## Dependencies

Requires 3d (`WeatherForecast` model — weather conditions recorded per session).
Requires 4a (`ExecutionObservation` — execution quality across varied conditions).
Requires sufficient execution history across varied temperature/humidity conditions
(typically 20+ outdoor sessions with a meaningful range of heat index values).

## Models Modified

**`AthleteProfile`** — adds `weather_response_model` (JSONB, nullable):
```json
{
  "heat_sensitivity_coeff": 0.0082,
  "fitted_from_sessions": 28,
  "fitted_at": "2026-03-10",
  "r_squared": 0.74,
  "heat_index_range_observed": [8, 31]
}
```
Population default coefficient is `0.006`. Higher individual coefficient means
greater heat sensitivity.

## Services Introduced

**`WeatherResponseCurveFittingService`** (sync, Python).
- `fit(athlete_id) → WeatherResponseModel | None`
  Returns None if < 20 outdoor sessions with concurrent WeatherForecast records
  spanning < 10°C heat index range.
  Correlates `heat_index_c` at session time with pace degradation relative to
  expected pace from current TwinState threshold estimates.
  Fits `pace_adjustment_factor = 1 + sensitivity * max(0, heat_index - 15)`.
  Stores in `AthleteProfile.weather_response_model`.

## Services Modified

**`WeatherAdjustmentService`** (updated) — uses individual `heat_sensitivity_coeff`
when `AthleteProfile.weather_response_model` is non-null and `r_squared ≥ 0.65`.
Falls back to population coefficient `0.006` otherwise.

**`RacePredictionService`** (updated) — uses individual curve for weather-adjusted
prediction when available.

## Done Criteria

- An athlete with varied heat exposure history has a non-null `weather_response_model`.
- An athlete identified as heat-sensitive (high coefficient) receives larger target
  reductions on hot days than the population formula would produce.
- An athlete with insufficient heat range history uses the population formula silently.
