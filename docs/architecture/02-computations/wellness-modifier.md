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
  deep_sleep_minutes: 0.05,
  rem_sleep_minutes: 0.08
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
    targets: theoretical_targets.targets.map(target => {
      if (target.signal_type === 'power' && target.primary.min !== null) {
        return {
          ...target,
          primary: {
            min: Math.round(target.primary.min * scale),
            max: target.primary.max !== null ? Math.round(target.primary.max * scale) : null,
            unit: target.primary.unit
          }
        }
      }
      if (target.signal_type === 'gap' && target.primary.min !== null) {
        // GAP: slower pace = higher sec/km value
        return {
          ...target,
          primary: {
            min: Math.round(target.primary.min / scale),
            max: target.primary.max !== null ? Math.round(target.primary.max / scale) : null,
            unit: target.primary.unit
          }
        }
      }
      // HR targets unchanged by recovery modifier (HR is relative to current physiology)
      return target
    }),
    description: theoretical_targets.description
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

## REM Sleep — Coaching Semantics

REM sleep captures cognitive and emotional recovery — distinct from deep sleep's physical/tissue repair role. The vision defines REM as "relevant for motivation, perceived effort, and decision-making capacity, particularly relevant for race situations."

**Weight rationale (0.08):** REM is more variable night-to-night than deep sleep (sensitive to alcohol, stress, medication, circadian disruption). Higher noise justifies lower weight. Its primary coaching value is pattern detection (sustained REM suppression = cognitive fatigue accumulation) rather than daily composite influence. At 0.08, total weights sum to 1.08; the normalisation in `computeCompositeScore` handles this by dividing by `weight_total`.

**Direction of concern:** Reduced below baseline (same as deep_sleep, total_sleep). REM is not an HR signal, so `computeDeviationScore` applies `-raw_deviation` — negative deviation = worse.

**Coaching message patterns:**

| Pattern | Trigger | Message approach |
|---|---|---|
| Low REM (3+ nights) | 3-night rolling avg below baseline | Note cognitive recovery deficit; flag relevance for upcoming quality sessions or race week |
| Sustained REM suppression (7+ nights) | 7-night rolling avg below baseline | Flag accumulated cognitive load; suggest mindfulness of effort pacing |
| REM + deep sleep both suppressed | Both signals below baseline simultaneously | Compound recovery deficit; system managing more than it can absorb |

**REM × cycle phase interaction:** Luteal phase degrades sleep quality, likely affecting REM disproportionately (REM is concentrated in latter half of sleep, which is more disrupted by elevated core temperature). The composite score already includes a luteal cycle phase adjustment (+0.2 to +0.4). Adding a REM-specific cycle modifier would double-count the same physiological effect. REM deviation captures the luteal sleep degradation indirectly through the signal itself.

**REM × race preparation:** During race-prep blocks (final 2–3 weeks before a goal race), sustained REM suppression can trigger a cognitive readiness flag in coaching messages — independent of the composite GREEN/AMBER/RED. This is a coaching-layer concern (agent reasoning), not a computation-layer concern. The `WellnessModifierService` computes the composite; the coaching agent receives full wellness context including REM trends and applies race-context interpretation.

## TwinState wellness_update Trigger

When `WellnessModifierService` produces an AMBER or RED classification that differs from the most recent `TwinState`'s implied modifier:
- `TwinRecalibrationService` appends a new `TwinState` with `trigger = 'wellness_update'`
- Fitness/fatigue scores are unchanged; the new record captures updated readiness context for agent consumption

## Cross-References

### Vision Signal Mapping

The following maps vision signal descriptions (`docs/vision/twin/external-modifiers.md`) to architecture computation steps. This table is the authoritative cross-reference for verifying that the architecture faithfully implements the vision's interpretation philosophy.

| Vision Signal | Architecture Key | Weight | Vision Philosophy | Architecture Implementation |
|---|---|---|---|---|
| Total sleep duration | `total_sleep_minutes` | 0.20 | "Trends over multiple nights matter more than any single night" | 3-night rolling average; baseline is 28-day median |
| Deep sleep duration | `deep_sleep_minutes` | 0.05 | "Physical recovery and tissue repair; consistently low is early warning for accumulated fatigue" | Lowest weight — rationale: high wearable measurement noise relative to other signals |
| REM proportion | `rem_sleep_minutes` | 0.08 | "Cognitive and emotional recovery; relevant for motivation, perceived effort, decision-making, particularly race situations" | Absolute REM minutes (not proportion); proportion refinement deferred to Phase 4f+ |
| Average sleeping HR | `avg_sleeping_hr_bpm` | 0.35 | "Primary trend signal for recovery state; rising over consecutive nights is most reliable early indicator of overreaching or illness" | Highest weight; matches vision emphasis |
| Minimum sleeping HR | `min_sleeping_hr_bpm` | 0.10 | "True physiological floor; used as resting HR anchor for zone calculations" | Zone-calculation anchor use is in separate pipeline; wellness weight is secondary |
| HRV overnight | `hrv_overnight_avg_ms` | 0.30 | "Monitored across rolling 3/7/14 day windows; single-night values never reacted to" | 3-night window for composite; 7-night confirms RED upgrade; 14-day window not implemented |
| Training time of day | [computed externally] | — | "Adjusts correlation between wellness signals and execution quality based on morning vs afternoon training" | Modifies correlation, not composite score directly; lives in agent reasoning layer |
| Trend interpretation | IQR-normalised deviation | — | "All signals interpreted as deviations from athlete's own baseline, never absolute values vs population norms" | Stage 2: deviation in IQR units; 3-night patterns trigger adjustments; 7-night patterns confirm RED |

**Vision-to-architecture alignment notes:**
- Vision: "3-night patterns trigger model adjustments" → Architecture: 3-night composite drives GREEN/AMBER/RED classification
- Vision: "7-night patterns may trigger proactive coach communication" → Architecture: 7-night composite confirms or upgrades amber→RED
- Vision: "single-night anomalies treated as noise" → Architecture: 3-night rolling window inherently filters single-night outliers
- Vision: "patterns across 7+ nights may prompt plan restructuring" → Architecture: RED classification triggers target adjustment (-15%) and wellness_update TwinState

### Entity References
- AthleteWellness raw records: `01-entities/athlete-wellness.md`
- AthleteWellnessBaseline storage: `01-entities/athlete-wellness-baseline.md`
- CyclePhaseLog and phase computation: `01-entities/cycle-phase-log.md`
- WeatherForecast storage: `01-entities/weather-forecast.md`
- GeneratedWorkout adjusted_targets: `01-entities/generated-workout.md`
- Individual weather response curve storage: `01-entities/athlete-profile.md` → `weather_response_model`
- Vision signal descriptions: `docs/vision/twin/external-modifiers.md`
