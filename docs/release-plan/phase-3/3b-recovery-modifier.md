# 3b — Recovery Modifier
*Baseline computation, trend detection, GREEN/AMBER/RED, adjusted targets*

## Objective

Translate wellness trends into coaching action. The `adjusted_targets` on every
`GeneratedWorkout` now genuinely diverge from `theoretical_targets` when the twin
detects suppressed wellness. The two-column display becomes meaningful for the
first time.

## Scope

`AthleteWellnessBaseline` model. Baseline computation (28-day median/IQR).
Trend detection (3-night and 7-night rolling windows). Recovery modifier
classification (GREEN/AMBER/RED). `WellnessModifierService`. Updated
`WorkoutGenerationAgent` consuming the modifier. `wellness_update` TwinState trigger.

## Non-Goals

- Menstrual cycle stacking on the composite score — deferred to 3c
- Weather stacking on adjusted targets — deferred to 3d
- Proactive wellness alert coach messages — deferred to 4e
  (the modifier adjusts targets silently in this sub-phase; the coach message
  explaining why happens in 4e)

## Architecture References

- `AthleteWellnessBaseline` model: `architecture/wellness-and-modifiers.md`
  → Baseline Computation
- Deviation scoring formula and 3/7-night windows:
  `architecture/wellness-and-modifiers.md` → Trend Detection
- Signal weights and GREEN/AMBER/RED thresholds:
  `architecture/wellness-and-modifiers.md` → Recovery Modifier Classification
- Target adjustment percentages per level:
  `architecture/wellness-and-modifiers.md` → Recovery Modifier Classification
- `wellness_update` TwinState trigger:
  `architecture/twin-state.md` → Recalibration Triggers
- Vision-level example coach message for wellness concern:
  `vision/twin/external-modifiers.md` → Coach Communication

## Dependencies

Requires 3a (`AthleteWellness` records must exist).

## Models Introduced

**`AthleteWellnessBaseline`** — cached rolling baseline per signal.
Fields: `athlete_id` FK, `signal` (str — field name, e.g. `avg_sleeping_hr_bpm`),
`baseline_value` (float), `baseline_variability` (float — IQR),
`computed_from_date_range` (JSONB: `{from, to}`), `computed_at`.
Unique constraint on `(athlete_id, signal)` — one baseline row per signal per athlete,
overwritten on recomputation.

## Services & Tasks Introduced

**`WellnessBaselineService`** (sync, Python) — computes and caches baselines.
- `compute(athlete_id) → dict[str, AthleteWellnessBaseline]`
  Reads last 28 days of `AthleteWellness`. For each signal with ≥ 14 non-null values:
  computes median and IQR, upserts `AthleteWellnessBaseline`. Signals with < 14
  values are skipped — no baseline written, excluded from modifier computation.
- Triggered nightly via scheduled task for all athletes with new wellness data.

**`WellnessModifierService`** (sync, Python) — classifies recovery level.
- `classify(athlete_id, date) → (RecoveryModifierLevel, str)`
  Returns `(green|amber|red, plain_language_reason)`.
  1. Loads `AthleteWellnessBaseline` for the athlete
  2. Fetches last 7 `AthleteWellness` records
  3. Computes 3-night and 7-night deviation scores per signal
  4. Applies signal weights from arch reference
  5. Applies GREEN/AMBER/RED thresholds from arch reference
  6. Constructs `plain_language_reason` as a structured dict
     (agent translates to prose in 4e; for now stored as-is)
  7. If < 3 wellness records exist: returns `green` with reason `insufficient_data`

**`BaselineComputationTask`** (async worker — scheduled nightly).
Runs `WellnessBaselineService.compute()` for all athletes with wellness records
updated in the past 24 hours.

## Models Modified

**`TwinState`** — `wellness_update` trigger now used. When `WellnessModifierService`
produces an AMBER or RED classification that differs from the previous classification,
`TwinRecalibrationService` appends a new TwinState with `trigger = wellness_update`.
No change to fitness/fatigue scores — only the readiness context changes.

## Services Modified

**`WorkoutGenerationAgent`** (updated) — now calls `WellnessModifierService` before
building context. Passes modifier level and reason to `ContextBudgetService`.
- `adjusted_targets` on `GeneratedWorkout` now genuinely differs from
  `theoretical_targets` when modifier is AMBER or RED.
  AMBER: targets scaled by −5% to −10%; RED: −10% to −20%.
- `recovery_modifier_level` and `recovery_modifier_reason` written to
  `GeneratedWorkout` (were always `green`/null before).

## Key Constraints

- Baseline computation uses median, not mean — outlier nights (illness, travel)
  must not distort the baseline. See `architecture/wellness-and-modifiers.md`.
- `WellnessModifierService` is deterministic — same input always produces same
  classification. It is pure Python with no randomness and no LLM calls.
- Modifier defaults to `green` with `insufficient_data` reason when < 3 wellness
  records exist. No errors, no blocked workout generation.
- The `TwinState` append-only invariant applies — `wellness_update` recalibrations
  insert new records, never modify existing ones.
- `adjusted_targets` and `theoretical_targets` are always both written to
  `GeneratedWorkout`, even when they are identical (GREEN modifier).
  The two-column structure is always present.

## Done Criteria

- After 14+ days of wellness data, `AthleteWellnessBaseline` records exist for
  all available signals.
- On a day following a hard training block with elevated sleeping HR:
  `GET /athletes/{id}/today` returns a GeneratedWorkout where `recovery_modifier_level`
  is `amber` or `red` and `adjusted_targets` are measurably lower than
  `theoretical_targets`.
- On a recovery day with baseline wellness signals: `adjusted_targets` equals
  `theoretical_targets` and `recovery_modifier_level = green`.
- An athlete with only 2 wellness records receives `recovery_modifier_level = green`
  without errors.
- Each AMBER/RED classification creates a new TwinState with `trigger = wellness_update`.
