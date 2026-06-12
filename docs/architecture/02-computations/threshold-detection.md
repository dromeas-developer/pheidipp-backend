# Threshold Detection — Algorithms and Bayesian Update

## Purpose
- Defines the three threshold detection algorithms and the Bayesian update mechanism
- These algorithms produce the lt1/lt2/cp estimates stored on AthletePhysiology

## Signal Selection

```typescript
function selectDetectionAlgorithm(activity: Activity): DetectionAlgorithm {
  if (activity.has_rr_intervals) return 'rrv_inflection'
  if (activity.has_hr) {
    if (activity.has_power) return 'hr_deflection_with_power'
    return 'hr_deflection'
  }
  return 'none'  // no update from this session
}
```

## Algorithm 1: HR Deflection

Applied to progressive effort sessions. Requires ≥ 3 distinct intensity steps in the session.

```typescript
type DeflectionResult = {
  lt1_hr_bpm: number | null
  lt2_hr_bpm: number | null
  confidence_weight: number  // 0.0–1.0; higher for cleaner signal
}

// Process:
// 1. Segment session into intensity bins using GAP or power
// 2. For each bin: compute mean HR and mean intensity
// 3. Fit linear HR-intensity regression across bins
// 4. LT1: first bin where slope increases above baseline (first departure from linearity)
// 5. LT2: second, steeper departure
// Returns null if < 3 distinct steps or R² < 0.80
```

## Algorithm 2: HRV Inflection (RR Intervals)

Applied to sessions with continuous RR data. Requires ≥ 8 minutes at each intensity level.

```typescript
type RrvResult = {
  lt1_hr_bpm: number | null
  lt2_hr_bpm: number | null
  lt1_rr_signal_quality: number
  confidence_weight: number  // higher than HR deflection; RR is richer signal
}

// Process:
// 1. Clean RR series (artifact detection; values outside ±20% of rolling median removed)
// 2. Compute RMSSD in 60-second rolling windows throughout session
// 3. Align RMSSD time-series with intensity time-series
// 4. LT1: first significant decrease in RMSSD as intensity rises
//    (threshold: RMSSD drops > 15% below pre-effort baseline within the window)
// 5. LT2: second inflection; typically less distinct; requires more data
// Returns null if < 8 minutes at each required intensity level
```

## Algorithm 3: Power-to-HR Ratio (Supplementary)

Used alongside HR-based detection when power data available. Not standalone.

```typescript
// At sub-threshold: power/HR ratio stable within a session
// Above LT2: ratio begins sustained decline (cardiovascular cost rises faster than output)
// Produces LT2 in watts → stored as cp_estimate_watts on AthletePhysiology
// Only written when power series shows clear ratio breakpoint
```

## Bayesian Update Mechanism

The Bayesian update formula, observation weights, and prior decay are defined in `02-computations/physiology-update.md`. The threshold detection algorithms produce observations that feed into that update mechanism.

```typescript
type ThresholdPrior = {
  lt1_bpm: number
  lt2_bpm: number
  prior_weight: number  // accumulated evidence weight
  last_observation_date: string
}

// The update formula is applied by PhysiologyUpdateService:
// See 02-computations/physiology-update.md for the full bayesian_update() function
```

## Confidence Level Transitions

Triggered by `TwinRecalibrationService` after Bayesian update. Transitions are **per-metric**: each parameter accumulates evidence independently.

| Transition | Condition |
|---|---|
| LOW → MEDIUM | Per-metric. When `lt2.hr.prior_weight >= 4.0` OR `lt1.hr.prior_weight >= 4.0` OR `cp.prior_weight >= 4.0` (approx 4 HR deflection sessions at default weight, or 1 field test, or 1 lab test) |
| MEDIUM → HIGH | Per-metric. When `lt2.hr.prior_weight >= 8.0` OR `lt1.hr.prior_weight >= 8.0` OR `cp.prior_weight >= 8.0` OR (≥ 2 RR-based sessions processed, which carry higher weight) |

For LT1 specifically: evidence also comes from natural training analysis (HR ceiling, drift analysis, recovery analysis) and optional active tests (MAF test, controlled progression test).

See `00-foundations/confidence-model.md` for downstream effects and evidence weight thresholds.

## Outputs → AthletePhysiology

```typescript
// AthletePhysiology fields updated by threshold detection:
// (via PhysiologyUpdateService.bayesian_update())
{
  lt1: {
    hr: PhysiologyParameterState,      // posterior mean + uncertainty
    power: PhysiologyParameterState | null,
    pace: PhysiologyParameterState | null
  },
  lt2: {
    hr: PhysiologyParameterState,      // posterior mean + uncertainty (primary confidence driver)
    power: PhysiologyParameterState | null,
    pace: PhysiologyParameterState | null
  },
  cp: PhysiologyParameterState | null
}
// A new TwinState is then appended with inline snapshot of the updated threshold values
// TwinState.confidence_level is derived from min(AthletePhysiology.lt1.hr.prior_weight, AthletePhysiology.lt2.hr.prior_weight)
// TwinState.metric_confidence is derived from respective parameter prior weights
```
## Version History

| Version | Change |
|---|---|
| `threshold-v1` | HR deflection only |
| `threshold-v2-rr` | RR inflection added |

## Cross-References
- AthletePhysiology (where posterior estimates are stored): `01-entities/athlete-physiology.md`
- TwinState confidence transitions: `00-foundations/confidence-model.md`
- Signal cleaning (produces cleaned RR series input): `02-computations/signal-cleaning.md`
- Data tier constraints on which algorithm applies: `00-foundations/data-tiers.md`

### Vision ↔ Architecture Mapping

The vision document `docs/vision/twin/training-zones.md` describes the philosophy and user experience. This section maps those concepts to their architecture implementations.

| Vision Concept | Architecture Implementation | Document |
|---|---|---|
| **Signal Hierarchy** (RR → HR → Dedicated → Lab → Inference) | Data Tier 1–6 classification determines which algorithms apply. Observation weights by source (`lab_test` = 12–15, `training_rr_inflection` = 2.5, `training_hr_deflection` = 1.0, `questionnaire_estimate` = 0.5) encode signal quality into the Bayesian update. | `00-foundations/data-tiers.md`, `02-computations/physiology-update.md` |
| **Calibration Confidence Degradation** (staleness → wider ranges) | 42-day prior decay in `bayesianUpdate()`. Older observations lose weight exponentially (`e^(-days/42)`). Increasing `uncertainty` on `PhysiologyParameterState` produces wider intent ranges at workout generation. | `02-computations/physiology-update.md` |
| **Passive Calibration** (normal training → threshold signal) | Calibration-eligible gate (`02-computations/load-computation.md`) plus algorithm selection based on session characteristics (≥3 intensity steps for HR deflection, ≥8 min/level for RR inflection). Easy runs are calibration-eligible but do NOT produce threshold evidence. | `02-computations/threshold-detection.md`, `00-foundations/data-tiers.md` |
| **Range-Based Targets** (athlete sees `165-172 bpm`, never "Zone 2") | `IntentRange` computed from `PhysiologyParameterState` posterior mean ± uncertainty. `WorkoutTarget` type carries signal-specific ranges with fallback chains. | `00-foundations/terminology.md` |
| **Signal-Aware Target Selection** (HR for easy, power for threshold) | `WorkoutTarget.signal_type` selection based on session type, physiological intent, signal availability, and signal quality. Fallback chain when primary signal unavailable. | `00-foundations/terminology.md` |
| **Multi-Dimensional Physiology** (LT1/LT2 as states with HR/power/pace expressions) | `PhysiologyParameterState` with `hr`, `power`, `pace` sub-fields. Each threshold (LT1, LT2) stored as separate parameter states per signal type. | `01-entities/athlete-physiology.md` |
| **Confidence Per-Metric** (each parameter accumulates independently) | `TwinMetricConfidence` on `TwinState`. Global confidence = `min(lt1_hr, lt2_hr)`. Transition thresholds: 4.0 for MEDIUM, 8.0 for HIGH (evidence weight units). | `00-foundations/confidence-model.md` |
