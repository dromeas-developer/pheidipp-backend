# 5d — Per-Athlete GAP
*Individual grade response curve, Generation 2 effort normalisation*

## Objective

Replace the static population GAP formula with a per-athlete grade response curve
for athletes with sufficient outdoor session history. Load scores become more
accurate; threshold detection becomes more precise; session comparisons across
different terrain become genuinely meaningful.

## Scope

Per-athlete grade response curve fitting. `AthleteProfile.gap_curve_model` field.
`EffortNormalisationService` Generation 2. `ingestion_pipeline_version` increment
for affected athletes. Historical load score reprocessing for athletes above the
threshold.

## Non-Goals

- Full personalised physiological cost model (Generation 3) — deferred to 6c
  (requires accumulated execution data with HMM segmentation for full terrain
  and fatigue-state inputs)

## Architecture References

- Generation 2 per-athlete curve definition and 20-session requirement:
  `architecture/effort-normalisation.md` → Generation 2
- Fallback to population formula for athletes below threshold:
  `architecture/effort-normalisation.md` → Generation 1
- `ingestion_pipeline_version` and reprocessing:
  `architecture/versioning.md`
- GAP rule (always grade-adjusted, never raw pace):
  `architecture/principles.md` → Authoritative Decisions

## Dependencies

Requires 5a (cleaned streams — GAP curve is fitted from cleaned session data).
Requires sufficient outdoor session history: 20+ activities with elevation data.

## Models Modified

**`AthleteProfile`** — adds `gap_curve_model` (JSONB, nullable):
```json
{
  "formula": "per_athlete_v1",
  "coefficients": {"a": 0.031, "b": 0.000115},
  "fitted_from_sessions": 24,
  "fitted_at": "2026-02-01",
  "r_squared": 0.87
}
```
Population formula uses `a=0.033, b=0.00012`. Per-athlete model replaces these.

## Services Introduced

**`GapCurveFittingService`** (sync, Python).
- `fit(athlete_id) → GapCurveModel | None`
  Returns None if < 20 outdoor activities with elevation data exist.
  Reads cleaned HR, pace, and grade data from stored `RawSensorStream` records.
  Filters to sessions where the athlete was in aerobic zones (avoids anaerobic
  confounding). Fits `correction_factor = 1 + a * grade + b * grade²` using
  least squares regression. Returns the fitted coefficients and fit quality (R²).
  Stores result in `AthleteProfile.gap_curve_model`.
- `should_refit(athlete_id) → bool`
  Returns True if 5+ new outdoor sessions have accumulated since last fit.

**`GapCurveFittingTask`** (async worker — triggered after FIT ingestion when
`should_refit` is True).

**`EffortNormalisationService`** (updated) — returns per-athlete coefficients
when `AthleteProfile.gap_curve_model` is non-null and R² ≥ 0.70.
Falls back to population formula otherwise.

## Services Modified

**`LoadComputationService`** (updated) — calls `EffortNormalisationService` for
GAP computation. For athletes with a valid per-athlete model, this changes the
GAP values used in load formulas.
`ingestion_pipeline_version` incremented to `v2-per-athlete-gap` for newly
processed activities.

**Historical reprocessing** — `ReprocessLoadTask` can be enqueued for historical
activities of athletes whose curve has just been fitted. Reprocesses load scores
from stored FIT files using the new GAP model. New Activities are NOT created —
load scores are updated in place (exception to the immutable record rule, because
load scores are a computed field, not an analytical output, and the reprocessing
test justifies it; see `architecture/versioning.md`).

## Key Constraints

- Per-athlete GAP is only used when `r_squared ≥ 0.70`. Below this, the fit is
  too noisy and the population formula is safer.
- For athletes below 20 outdoor sessions, load computation silently uses the
  population formula. No indication is surfaced to the athlete.
- Load score updates from reprocessing do not create new TwinState records —
  only load scores on Activity are updated. The next `TwinRecalibrationTask`
  will naturally incorporate the improved scores.

## Done Criteria

- An athlete with 22+ outdoor sessions has a non-null `gap_curve_model` on
  `AthleteProfile` with `r_squared ≥ 0.70`.
- An athlete with 10 outdoor sessions has null `gap_curve_model` and load
  computation uses population coefficients without errors.
- After curve fitting, the next threshold workout target uses the athlete's
  personal GAP coefficients, producing slightly different pace targets from
  the population formula (visible difference in hilly terrain).
