# Threshold Detection — Algorithms and Bayesian Update

## Purpose
- Defines the three threshold detection algorithms and the Bayesian update mechanism
- These algorithms produce the lt1/lt2/ftp estimates stored on TwinState

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
// Produces LT2 in watts → stored as ftp_estimate_watts on TwinState
// Only written when power series shows clear ratio breakpoint
```

## Bayesian Update Mechanism

Combines a new detection observation with the existing prior on TwinState:

```typescript
type ThresholdPrior = {
  lt1_bpm: number
  lt2_bpm: number
  prior_weight: number  // accumulated evidence weight
  last_observation_date: string
}

function bayesianUpdate(
  prior: ThresholdPrior,
  observation: { lt1_bpm: number | null; lt2_bpm: number | null; confidence_weight: number },
  days_since_last_observation: number
): ThresholdPrior {
  // Prior decay: observations > 6 weeks old carry reduced weight
  const decay_factor = Math.exp(-days_since_last_observation / 42)
  const decayed_prior_weight = prior.prior_weight * decay_factor

  const new_weight = observation.confidence_weight

  const posterior_lt1 = observation.lt1_bpm !== null
    ? (prior.lt1_bpm * decayed_prior_weight + observation.lt1_bpm * new_weight)
      / (decayed_prior_weight + new_weight)
    : prior.lt1_bpm  // no update if observation was null

  return {
    lt1_bpm: posterior_lt1,
    lt2_bpm: /* same pattern */ 0,
    prior_weight: decayed_prior_weight + new_weight,
    last_observation_date: new Date().toISOString().split('T')[0]
  }
}
```

## Confidence Level Transitions

Triggered by `TwinRecalibrationService` after Bayesian update:

| Transition | Condition |
|---|---|
| LOW → MEDIUM | `prior_weight >= 4.0` (approx 4 HR deflection sessions at default weight) |
| MEDIUM → HIGH | `prior_weight >= 8.0` OR (≥ 2 RR-based sessions processed, which carry higher weight) |

See `00-foundations/confidence-model.md` for downstream effects.

## Outputs → TwinState

```typescript
// New TwinState fields updated by threshold detection:
{
  lt1_estimate_bpm: number,       // posterior mean
  lt2_estimate_bpm: number,       // posterior mean
  ftp_estimate_watts: number | null,  // from power-to-HR ratio; null if no power data
  confidence_level: TwinConfidenceLevel  // updated if threshold crossed
}
```

## Version History
| Version | Change |
|---|---|
| `threshold-v1` | HR deflection only |
| `threshold-v2-rr` | RR inflection added (Phase 2d) |

## Cross-References
- TwinState confidence transitions: `00-foundations/confidence-model.md`
- Signal cleaning (produces cleaned RR series input): `02-computations/signal-cleaning.md`
- Data tier constraints on which algorithm applies: `00-foundations/data-tiers.md`
