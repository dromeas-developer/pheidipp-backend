# Segmentation — Generation 3 HMM

## Purpose
- Defines the Hidden Markov Model segmentation that supersedes Generation 1
- Produces posterior probability distributions over states rather than hard classifications
- segmentation_version = 'hmm-v1'

## Why HMM Fits This Problem

**Temporal autocorrelation.** An athlete in THRESHOLD is more likely to remain in THRESHOLD than to jump to WARMUP. The HMM's transition matrix explicitly models self-continuity, smoothing out momentary signal noise.

**Physiological lag.** HR does not jump instantly when effort changes. The HMM handles this naturally through its transition probability structure.

**Multi-signal evidence.** HR, power, pace, cadence, and RR intervals provide complementary evidence for the same latent state. The HMM integrates all available signals through its emission distribution.

**Preserved uncertainty.** The HMM produces a probability distribution over states. A segment with 0.6 probability THRESHOLD and 0.4 probability HIGH_AEROBIC is handled differently to one with 0.95 probability THRESHOLD.

## HMM Architecture

```typescript
// 7 observable states for segment-level inference
// These are distinct from session-level PhysiologicalIntent — the HMM classifies
// time-series segments within a workout, not the session's adaptation target.
// 'unknown' is produced when max posterior < 0.45.
const HMM_STATES = [
  'warmup', 'low_aerobic', 'high_aerobic', 'threshold', 'vo2', 'recovery', 'cooldown'
] as const

// Transition matrix A[i][j] = P(state_j | state_i)
// Initialised from population priors; fine-tuned per athlete after 30+ labelled segments
// Population prior reflects known training patterns:
// - warmup → low_aerobic: high probability
// - threshold → threshold: high self-transition (athletes hold threshold for reps)
// - threshold → recovery: common transition after a rep
type TransitionMatrix = number[][]  // 7×7; rows sum to 1.0

// Emission model: Gaussian per state per feature
// Feature vector per time step from cleaned stream step 4:
type FeatureVector = {
  hr_30s_mean: number | null
  hr_60s_mean: number | null
  gap_30s_mean: number | null
  power_30s_mean: number | null
  variability_index: number | null
  hr_to_power_ratio: number | null
}
// Emission: P(observation | state) ~ N(μ_state, Σ_state)
// μ and Σ fitted from labelled segments (Gen 1 segments with confidence ≥ 0.6 as labels)
```

## Inference

```typescript
type HmmInferenceResult = {
  viterbi_sequence: string[]     // most likely state sequence (HMM_STATES values)
  posteriors: Record<string, number>[]  // per time step
  segment_posteriors: Record<string, number>  // aggregated per segment
}

function inferStates(
  cleaned_stream: CleanedStream,
  hmm_model: HmmModel  // loaded from object storage: models/hmm/population_v1.pkl or athlete-specific
): HmmInferenceResult {
  // 1. Viterbi algorithm: O(T * N²) where T=timesteps, N=7 states
  //    Produces the single most likely state sequence
  // 2. Forward-backward algorithm: O(T * N²)
  //    Produces posterior probability distributions per timestep
  // 3. Aggregate posteriors within changepoint-defined segments
  //    The changepoints from step 5 of preprocessing define segment boundaries;
  //    HMM inference smooths within those boundaries
}

function toPhysiologicalSegments(
  inference: HmmInferenceResult,
  changepoints: number[],
  planned_segments: PlannedSegment[]
): PhysiologicalSegment[] {
  return changepoints.map((cp, i) => {
    const next_cp = changepoints[i + 1] ?? inference.viterbi_sequence.length
    const posterior = inference.segment_posteriors[i]
    const inferred_state = argmax(posterior)
    const confidence = posterior[inferred_state]
    return {
      inferred_state: confidence < 0.45 ? 'unknown' : inferred_state,
      confidence,
      state_probabilities: posterior,  // full distribution; not null in Gen 3
      segmentation_version: 'hmm-v1',
      // ... alignment fields
    }
  })
}
```

## Model Training

**Population model:**
- Trained from Gen 1 `PhysiologicalSegment` records with `confidence >= 0.6` across the full athlete base
- Minimum: 1,000 labelled segments per state (varies; some states are rarer)
- Stored: `models/hmm/population_v1.pkl` in object storage
- Run as a one-off offline job when sufficient labelled data exists

**Per-athlete fine-tuning:**
- Triggered when an athlete accumulates 30+ labelled Gen 1 segments
- Fine-tunes transition matrix and emission parameters on athlete-specific data
- Stored: `models/hmm/athlete_{id}_v1.pkl`
- Subsequent segmentation for this athlete uses the fine-tuned model

## Fallback Chain

```
Per-athlete fine-tuned model (≥30 labelled segments)
  → Population model (default)
    → Generation 1 heuristic (if population model not yet trained)
```

## Cross-References
- Generation 1 (superseded by this): `02-computations/segmentation-heuristic.md`
- Cleaned stream inputs: `02-computations/signal-cleaning.md`
- PhysiologicalSegment schema (state_probabilities is non-null here): `01-entities/physiological-segment.md`
- Versioning when Gen 1 records are superseded: `04-platform/versioning-and-reprocessing.md`
