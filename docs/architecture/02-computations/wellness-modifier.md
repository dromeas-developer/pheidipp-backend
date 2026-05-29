# Wellness Modifier — Baseline, Trend Detection, and Recovery Classification

## Purpose
- Defines how raw AthleteWellness records become the GREEN/AMBER/RED recovery modifier
- Includes the menstrual cycle composite adjustment and weather adjustment formulas
- Output feeds GeneratedWorkout.adjusted_targets and TwinState wellness_update trigger

## Stage 1 — Baseline Computation

See `01-entities/athlete-wellness-baseline.md` for the storage contract.

```typescript
// Requires minimum 14 non-null values in the past 28 calendar days
// Uses median (not mean) — resistant to outlier nights
// Uses IQR (not std dev) — resistant to outlier nights

function computeBaseline(values: number[]): { median: number; iqr: number } | null {
  if (values.length < 14) return null  // insufficient data
  const sorted = [...values].sort((a, b) => a - b)
  const q1 = sorted[Math.floor(sorted.length * 0.25)]
  const q3 = sorted[Math.floor(sorted.length * 0.75)]
  return {
    median: sorted[Math.floor(sorted.length * 0.5)],
    iqr: q3 - q1
  }
}
```

Computed nightly by `BaselineComputationTask` for all athletes with new wellness data. Stored in `AthleteWellnessBaseline`.

## Stage 2 — Deviation Scoring

```typescript
type RollingWindows = {
  three_night: number[]
  seven_night: number[]
}

function computeDeviationScore(
  rolling_avg: number,
  baseline: AthleteWellnessBaseline,
  signal: WellnessSignal
): number {
  // Normalised deviation from baseline in units of IQR
  const raw_deviation = (rolling_avg - baseline.baseline_value) / baseline.baseline_variability

  // Sign convention: positive = WORSE than baseline for both HR and HRV signals
  const HR_SIGNALS: WellnessSignal[] = ['avg_sleeping_hr_bpm', 'min_sleeping_hr_bpm']
  return HR_SIGNALS.includes(signal) ? raw_deviation : -raw_deviation
}
```

## Stage 3 — Composite Scoring

Signal weights (see `01-entities/athlete-wellness-baseline.md` for the authoritative table):

```typescript
const SIGNAL_WEIGHTS: Record<WellnessSignal, number> = {
  avg_sleeping_hr_bpm: 0.35,
  hrv_overnight_avg_ms: 0.30,
  total_sleep_minutes: 0.20,
  min_sleeping_hr_bpm: 0.10,
  deep_sleep_minutes: 0.05
}

function computeCompositeScore(
  three_night_deviations: Partial<Record<WellnessSignal, number>>,
  cycle_phase_adjustment: number  // from CyclePhaseService; 0.0 if not applicable
): number {
  let weighted_sum = 0
  let weight_total = 0
  for (const [signal, weight] of Object.entries(SIGNAL_WEIGHTS)) {
    const dev = three_night_deviations[signal as WellnessSignal]
    if (dev !== undefined) {
      weighted_sum += dev * weight
      weight_total += weight
    }
  }
  const signal_composite = weight_total > 0 ? weighted_sum / weight_total : 0
  return signal_composite + cycle_phase_adjustment
}
```

## Stage 4 — GREEN/AMBER/RED Classification

```typescript
// Primary classification from 3-night window
// 7-night window confirms or upgrades amber → red
function classifyRecoveryModifier(
  composite_3night: number,
  composite_7night: number
): RecoveryModifierLevel {
  if (composite_3night < 0.5 && composite_7night < 0.3) return 'green'
  if (composite_3night >= 1.0 || composite_7night >= 0.7) return 'red'
  return 'amber'
}

// Insufficient data fallback (< 3 wellness records)
function classifyWithInsufficientData(): RecoveryModifierLevel {
  return 'green'  // conservative default; flagged as insufficient_data in reason
}
```

## Target Adjustment by Level

```typescript
function applyRecoveryModifier(
  theoretical_targets: TargetSet,
  level: RecoveryModifierLevel
): TargetSet {
  const scale = { green: 1.0, amber: 0.92, red: 0.85 }[level]
  // amber: -5% to -10%; red: -10% to -20% (midpoints used)
  return {
    ...theoretical_targets,
    pace_sec_per_km: theoretical_targets.pace_sec_per_km
      ? theoretical_targets.pace_sec_per_km / scale  // slower pace = higher sec/km value
      : null,
    power_watts: theoretical_targets.power_watts
      ? theoretical_targets.power_watts * scale
      : null,
    hr_zone: theoretical_targets.hr_zone  // HR zones unchanged by modifier
  }
}
```

## Menstrual Cycle Composite Adjustments

Applied to `cycle_phase_adjustment` input of `computeCompositeScore`.

**Population priors** (replaced by `AthleteProfile.cycle_personal_model.phase_sensitivity` when set):

```typescript
function getCyclePhaseAdjustment(
  phase: CyclePhase,
  cycle_day: number,
  personal_sensitivity?: Record<CyclePhase, number>
): number {
  const DEFAULT_ADJUSTMENTS: Record<CyclePhase, number> = {
    menstrual:  cycle_day <= 2 ? 0.40 : 0.20,
    follicular: -0.10,
    ovulatory:  0.00,
    luteal:     cycle_day >= 24 ? 0.40 : 0.20,
    unknown:    0.00
  }

  if (personal_sensitivity) {
    // Replace population prior with individual sensitivity
    return DEFAULT_ADJUSTMENTS[phase] * personal_sensitivity[phase]
  }
  return DEFAULT_ADJUSTMENTS[phase]
}
```

**Luteal thermoregulatory modifier** (fed into weather adjustment, not composite score):
```typescript
const LUTEAL_TEMP_OFFSET_C = 0.35  // midpoint of 0.3–0.5°C range
// Added to WeatherForecast.heat_index_c before weather adjustment computation
```

## Weather Adjustment Formulas

```typescript
const NEUTRAL_HEAT_INDEX_C = 15.0

function computeWeatherPaceAdjustment(
  weather: WeatherForecast,
  luteal_temp_offset_c: number,            // 0.0 if not luteal phase
  individual_heat_coeff?: number           // from AthleteProfile.weather_response_model
): number {
  const coeff = individual_heat_coeff ?? 0.006  // population default
  const effective_heat_index = weather.heat_index_c + luteal_temp_offset_c
  const heat_stress = Math.max(0, effective_heat_index - NEUTRAL_HEAT_INDEX_C)
  const heat_factor = 1.0 + (heat_stress * coeff)

  // Wind: assume worst-case headwind direction if unknown
  const wind_factor = 1.0 + (weather.wind_speed_ms * 0.003)

  return heat_factor * wind_factor
  // > 1.0 means pace target should be SLOWER (higher sec/km)
}
```

Note: The luteal thermoregulatory modifier stacks additively with weather because the mechanisms are physiologically distinct. The same formula applies with `luteal_temp_offset_c = 0.0` for non-luteal athletes.

## TwinState wellness_update Trigger

When `WellnessModifierService` produces an AMBER or RED classification that differs from the most recent `TwinState`'s implied modifier:
- `TwinRecalibrationService` appends a new `TwinState` with `trigger = 'wellness_update'`
- Fitness/fatigue scores are unchanged; the new record captures updated readiness context for agent consumption

## Cross-References
- AthleteWellness raw records: `01-entities/athlete-wellness.md`
- AthleteWellnessBaseline storage: `01-entities/athlete-wellness-baseline.md`
- CyclePhaseLog and phase computation: `01-entities/cycle-phase-log.md`
- WeatherForecast storage: `01-entities/weather-forecast.md`
- GeneratedWorkout adjusted_targets: `01-entities/generated-workout.md`
- Individual weather response curve storage: `01-entities/athlete-profile.md` → `weather_response_model`
