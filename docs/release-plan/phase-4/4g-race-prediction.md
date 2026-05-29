# 4g — Race Prediction
*RacePrediction model, baseline formula, course and weather adjustment*

## Objective

Surface a living predicted race time that updates as the athlete's fitness evolves.
The prediction is grounded in actual observed threshold performance — not just model
estimates — and updates after every significant training block. Watching it improve
is one of the most motivating features in the product.

## Scope

`RacePrediction` model. `RacePredictionService`. Baseline prediction from threshold
pace + endurance factor. Course profile adjustment. Weather-adjusted prediction
in the 14 days before the race. Update triggers.

## Non-Goals

- Personalised weather response curves (individual vs population adjustment) —
  deferred to 6b (requires accumulated execution history across varied conditions)
- VO2max-based prediction refinement — deferred to 6a
  (requires fuller segmentation data for reliable VO2max estimates)

## Architecture References

- `RacePrediction` model full field spec:
  `architecture/coaching-services.md` → RacePrediction
- Baseline prediction formula:
  `architecture/coaching-services.md` → Baseline Prediction Computation
- Confidence gating (not surfaced at LOW):
  `architecture/coaching-services.md` → Baseline Prediction Computation
- Course adjustment using effort normalisation:
  `architecture/coaching-services.md` → Course Profile Adjustment
- Weather adjustment on race prediction:
  `architecture/coaching-services.md` → Weather Adjustment
- Vision-level race prediction components:
  `vision/coach/race-prediction.md`

## Dependencies

Requires 2d (threshold estimates at MEDIUM+ confidence — prediction not surfaced at LOW).
Requires 3d (`WeatherForecast` model — weather-adjusted prediction uses it).
Requires 4a (`ExecutionObservation` — `observed_pace_at_lt2` sourced from recent
calibration sessions, not raw TwinState estimate).

## Models Introduced

**`RacePrediction`** — point-in-time prediction record. Full field spec from arch reference:
`athlete_id` FK, `training_block_id` FK, `twin_state_id` FK,
`predicted_at`, `target_distance_km`, `baseline_prediction_seconds`,
`weather_adjusted_seconds` (nullable), `course_adjusted_seconds` (nullable),
`course_profile_source` (nullable), `weather_forecast_id` FK (nullable),
`confidence_level`, `prediction_method_version`.

## Services Introduced

**`RacePredictionService`** (sync, Python).
- `compute(athlete_id) → RacePrediction | None`
  Returns None if `TwinState.confidence_level = low`.
  1. Reads current TwinState threshold estimates
  2. Computes `observed_pace_at_lt2` from the 3 most recent calibration-eligible
     threshold or tempo sessions (more grounded than raw model estimate)
  3. Derives `endurance_factor` from `target_distance_km` and `aerobic_base_ratio`
     (lt1/lt2 HR fraction) using the formula from arch reference
  4. Computes `baseline_prediction_seconds`
  5. If race is within 14 days and `WeatherForecast` exists for race location and date:
     computes `weather_adjusted_seconds`
  6. If course profile provided: computes `course_adjusted_seconds`
  7. Writes new `RacePrediction` record

**`CourseAdjustmentService`** (sync, Python).
- `compute(athlete_id, elevation_data) → float` — returns `course_difficulty_factor`.
  Uses effort normalisation Generation 2 formula if per-athlete curve exists,
  otherwise Generation 1 static GAP formula.

## Endpoints Introduced

- `GET /athletes/{athlete_id}/prediction` — returns the most recent `RacePrediction`
  for the active training block. Returns 204 if confidence is LOW or no active
  race goal. Protected by `require_self`.
- `POST /athletes/{athlete_id}/prediction/course-profile` — athlete uploads course
  GPX or provides a URL. Triggers recomputation with course adjustment.
  Protected by `require_self`.
- `GET /athletes/{athlete_id}/prediction/history` — returns all `RacePrediction`
  records for the active block, ordered by `predicted_at`. The prediction arc.
  Protected by `require_self`.

## Key Constraints

- `RacePredictionService` returns null at LOW confidence — the endpoint returns 204.
  No speculative prediction is shown until the twin has real threshold data.
- `observed_pace_at_lt2` requires at least 1 calibration-eligible threshold
  session. If none exist, fallback to raw `lt2_estimate_bpm` converted to pace
  via a population HR-to-pace curve (lower confidence — flagged in response).
- Race prediction is created for `goal_type = race_event` only. Open training
  blocks (`goal_type = open_training`) return 204.
- Each update trigger creates a new record — old predictions are retained for
  the history endpoint.

## Done Criteria

- A MEDIUM confidence athlete with a race goal sees a non-null prediction on
  `GET /athletes/{id}/prediction`.
- A LOW confidence athlete receives 204.
- After a significant threshold session, `GET /prediction/history` shows a new
  entry with an updated (hopefully improved) `baseline_prediction_seconds`.
- Within 14 days of the goal event, `weather_adjusted_seconds` is non-null
  when a weather forecast is available.
- An athlete on an open training block receives 204.
