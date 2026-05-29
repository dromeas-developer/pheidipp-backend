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

| Tier | Hardware | Power | RR | HR | GPS | Calibration | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Running power meter + chest strap (RR) | ✓ | ✓ | ✓ | ✓ | ✓ | Most precise. Passive threshold tracking via RR. |
| 2 | Running power meter + optical HR | ✓ | ✗ | ✓ | ✓ | ✓ | Very strong for load. No RR for threshold detection. |
| 3 | Chest strap (RR) + GAP + GPS | ✗ | ✓ | ✓ | ✓ | ✓ | RR data available. GAP as mechanical proxy. |
| 4 | Optical HR + GAP + GPS | ✗ | ✗ | ✓ | ✓ | ✓ | Realistic baseline for core audience. Fully usable. |
| 5 | GAP + GPS only (no HR) | ✗ | ✗ | ✗ | ✓ | ✗ | Logged for record. Excluded from twin calibration. |
| 6 | Manual entry only | ✗ | ✗ | ✗ | ✗ | ✗ | Training record only. No analytical value. |

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
