# Data Tiers — Hardware Capability Classification

## Purpose
- Defines the six data tiers that determine what signals are available for computation
- Establishes which tiers enable which analytical capabilities

## TypeScript Schema

```typescript
type DataTier = 1 | 2 | 3 | 4 | 5 | 6

type DataTierCapabilities = {
  tier: DataTier
  hardware: string
  has_power: boolean
  has_rr_intervals: boolean
  has_hr: boolean
  has_gps: boolean
  calibration_eligible: boolean
  load_dimensions_available: ('aerobic' | 'neuromuscular' | 'structural')[]
  threshold_detection: 'rrv_inflection' | 'hr_deflection' | 'inferred_only' | 'none'
  notes: string
}
```

## Tier Definitions

| Tier | Hardware | Power | RR | HR | GPS | Calibration | Threshold Detection | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Running power meter + chest strap (RR) | ✓ | ✓ | ✓ | ✓ | ✓ | HR deflection + RR inflection + power-to-HR ratio | Most precise. Passive threshold tracking via RR. |
| 2 | Running power meter + optical HR | ✓ | ✗ | ✓ | ✓ | ✓ | HR deflection + power-to-HR ratio only | Very strong for load. No RR for inflection detection. |
| 3 | Chest strap (RR) + GAP + GPS | ✗ | ✓ | ✓ | ✓ | ✓ | HR deflection + RR inflection | RR data available. GAP as mechanical proxy. |
| 4 | Optical HR + GAP + GPS | ✗ | ✗ | ✓ | ✓ | ✓ | HR deflection only | Realistic baseline for core audience. Fully usable. |
| 5 | GAP + GPS only (no HR) | ✗ | ✗ | ✓ | ✓ | ✗ | None (no HR signal) | Logged for record. Excluded from twin calibration. |
| 6 | Manual entry only | ✗ | ✗ | ✗ | ✗ | ✗ | None | Training record only. No analytical value. |

**Key insight**: Threshold detection requires intensity variation, not just HR accuracy. Easy runs are calibration-eligible (meet the five-rule gate) but do NOT provide threshold detection evidence because they lack the intensity variation needed for HR deflection/RR inflection algorithms. A calibration-eligible easy run contributes to fitness/fatigue scores, not threshold confidence.

## Load Dimensions by Tier

| Tier | Aerobic Load | Neuromuscular Load | Structural Load |
|---|---|---|---|
| 1 | Power-based (most precise) | ✓ | ✓ |
| 2 | Power-based | ✓ | ✓ |
| 3 | HR reserve integration | ✓ | ✓ |
| 4 | HR reserve integration | ✓ | ✓ |
| 5 | GAP-estimated (low confidence) | ✓ | ✓ |
| 6 | None | None | None |

## Threshold Detection by Tier

| Tier | Algorithm | Confidence Weight |
|---|---|---|
| 1, 3 | HRV inflection point (RR) | High |
| 1, 2 | Power-to-HR ratio analysis | Supplementary only |
| 2, 4 | HR deflection analysis | Moderate |
| 5, 6 | Historical inference only | No update |

**Vision ↔ Architecture note:** This table implements the vision's "Signal Hierarchy" from `docs/vision/twin/training-zones.md`. The vision describes five conceptual tiers (RR intervals → HR-based → Dedicated calibration → Lab/Test → Inference). This architecture table maps those to hardware-based data tiers:

| Vision Signal Tier | Architecture Equivalent | Observation Weight |
|---|---|---|
| Raw RR intervals (chest strap) | Tier 1, 3 → `training_rr_inflection` | 2.5 |
| HR-based signals without RR | Tier 2, 4 → `training_hr_deflection` | 1.0 |
| Dedicated calibration sessions | Calibration-eligible sessions with intensity variation → `field_test` | 2.0–5.0 |
| Lab/Test Uploads | `lab_test` source | 12.0–15.0 |
| Inference from training history | `questionnaire_estimate` source | 0.5 |

The vision's hierarchy is about signal quality. The architecture's tiers are about hardware capability. They overlap but are not identical — a Tier 1 athlete (power + RR) can still produce low-quality RR data if the chest strap is faulty, and a Tier 4 athlete (optical HR) can produce high-quality HR deflection data over many sessions.

## Vision ↔ Architecture: Data Philosophy

This section maps the five principles from `docs/vision/twin/data-philosophy.md` to their architectural implementations in this document and across the architecture layer. These principles are the design rationale behind the tier structure, invariants, and observation weights defined above.

### 1. Real Signals, Not Assumptions

The vision commits to using actual physiological data rather than estimated or inferred metrics. Grade-adjusted pace replaces raw pace. RR intervals are preferred over optical HR. Lab/test uploads are accepted with provenance.

| Philosophy Element | Architecture Implementation |
|---|---|
| GAP replaces raw pace | Invariant #9 in `principles.md`: "Raw pace is never used." |
| RR intervals preferred | Tier 1–3 have `has_rr = true`; RR enables `training_rr_inflection` (observation weight 2.5) vs `training_hr_deflection` (weight 1.0) |
| Lab/test uploads with provenance | `lab_test` source receives the highest observation weight (12.0–15.0) in the system |
| Honest confidence when data is poor | Tier 5–6 have `threshold_detection: 'none'`; `calibration_eligible = false` |

### 2. Data Quality Over Quantity

The vision commits to excluding sessions without device data from twin calibration. Noisy or incomplete data corrupts the model more than gaps do. The twin always knows the data quality tier and weights learning accordingly.

| Philosophy Element | Architecture Implementation |
|---|---|
| Manual entry excluded from calibration | `calibration_eligible = false` for `manual_entry` source; Tier 6 invariant |
| Noisy data excluded | Tier 5–6 never calibration-eligible; Tier 6 null loads |
| Quality-aware weighting | Observation weights by source (0.5–15.0 range encodes quality into Bayesian update) |
| Confidence reflects data quality | Per-metric confidence from prior weights; `metric_confidence` on TwinState |

### 3. Continuous Learning From Real Training

The vision commits to updating the twin from every real training session. Individual time constants, threshold estimates, and adaptation patterns improve as data accumulates.

| Philosophy Element | Architecture Implementation |
|---|---|
| Every session updates the twin | TwinState is append-only (invariant #4 in `principles.md`); recalibration appends new record |
| Continuous improvement over time | Bayesian update with observation weights; confidence transitions LOW → MEDIUM → HIGH |
| Historical reprocessing | Algorithm improvements reprocess recent history (invariant #14 in `principles.md`) |
| Auditability of learning | Append-only + version strings make every historical decision explainable |

### 4. Non-Running Data Does Not Corrupt the Running Model

The vision commits to logging non-running activities but never calibrating them into the twin. No arbitrary conversion factors. The twin waits for the next run.

| Philosophy Element | Architecture Implementation |
|---|---|
| Non-running excluded from calibration | Invariant #8 in `principles.md`: "Non-running activities are excluded from twin calibration" |
| No conversion factors | Anti-goal #11 in `principles.md`: "no multi-sport conversion factors" enforced as architectural constraint |
| Activities logged but not calibrated | `calibration_eligible = false` for non-running; Activity record exists but twin does not learn from it |

### 5. The Honesty Invariant

The vision commits to always being honest about evidence confidence. Conservative language, target ranges rather than point estimates, cautious plan structures. As evidence confidence grows, coaching becomes more specific.

| Philosophy Element | Architecture Implementation |
|---|---|
| Conservative at low confidence | RacePrediction returns null at LOW confidence (204, no record) |
| Per-metric honesty | Confidence is per-metric, not global; each parameter accumulates independently |
| Unknown states preserved | `inferred_state = 'unknown'` when confidence < 0.45; coach makes no claims about unknown segments |
| Range over point estimates | Bayesian posterior distributions (`state_probabilities`); confidence intervals on thresholds |
| Plans reflect confidence level | `twin_state_id` on TrainingPlan records which twin version produced it; LOW confidence → different phase structures |

### Summary: Why the Tier Structure Exists

The six-tier hardware classification is not an arbitrary technical decision. It is the architectural expression of five philosophical commitments:

1. **Tiers exist** because real signals vary in quality, and the system must be explicit about what it can and cannot know.
2. **Tier 5–6 exclusion** exists because gaps are preferred over noise — the system refuses to learn from data it cannot trust.
3. **Observation weights vary by source** because not all evidence is equal, and the Bayesian update must reflect that.
4. **Non-running activities are logged but not calibrated** because the running model must not be corrupted by signals it was not designed to process.
5. **Confidence is per-metric and visible** because the system must never overstate what it knows.

## Tier Inference from AthletePreferences

Tier is inferred from `AthletePreferences.hr_source` and `power_source`:

```typescript
function inferDataTier(hrSource: HrSource, powerSource: PowerSource): DataTier {
  if (powerSource === 'running_power_meter') {
    return hrSource === 'chest_strap_rr' ? 1 : 2
  }
  if (hrSource === 'chest_strap_rr') return 3
  if (hrSource === 'chest_strap_no_rr' || hrSource === 'wrist_optical') return 4
  if (hrSource === 'none') return 5
  return 6  // manual entry
}
```

## Invariants
- Tier 5 and 6 activities are never `calibration_eligible`
- Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`
- A session without GPS (`has_gps = false`) defaults to Tier 6 for structural load purposes even if HR is present
- Optical HR (`wrist_optical`) is adequate for zone-based load calculation. Its limitation versus chest strap is specifically the absence of RR intervals for threshold detection — not HR accuracy for sustained aerobic efforts
- Threshold detection capability is determined by data tier (see Tier Definitions table). Tiers 1–4 provide different levels of threshold detection; Tiers 5–6 provide none.
- Easy runs are calibration-eligible for load computation but do NOT provide threshold detection evidence (insufficient intensity variation for HR deflection/RR inflection algorithms)

## Runtime Ownership
Owns:
- Tier classification from hardware signals
- Which analytical capabilities each tier enables

Does Not Own:
- The load formulas themselves → `02-computations/load-computation.md`
- The threshold detection algorithms → `02-computations/threshold-detection.md`

## Implementation Notes
- Tier is stored on `TwinState.data_tier` at the time of the TwinState creation
- If an athlete upgrades their hardware (e.g. adds a power meter), the new tier is reflected in the next TwinState after an activity is processed
- The tier ceiling is determined at onboarding from preferences but may differ per-session if the athlete forgets their chest strap (Tier 4 session for a Tier 3 athlete)
