# Adaptation Observation

## Purpose

- Records the relationship between training load applied and fitness change produced for an **adaptation observation window** (2-3 quality sessions followed by recovery)
- The source data for the athlete's adaptation signature and yield profiles
- Drives plan personalisation in PlanGenerationService once sufficient observations accumulate

---

## TypeScript Schema

```typescript
type AdaptationObservation = {
  id: string                          // UUID, PK
  athlete_id: string                  // UUID, FK → Athlete
  adaptation_window_id: string          // UUID, identifies the adaptation observation window (2-3 quality sessions + recovery)
  window_start_date: string           // YYYY-MM-DD
  window_end_date: string               // YYYY-MM-DD

  // Unit classification
  unit_type: 'hard_window' | 'isolated' | 'recovery'
    // 'hard_window': 2-3 quality sessions treated as single compound stimulus
    // 'isolated': single quality session flanked by easy days (cleanest signal, highest analytical weight)
    // 'recovery': recovery/easy period observation (active observation window, no stimulus to measure fatigue against)

  // Stimulus profile (aggregate load across the window)
  total_aerobic_load: number
  total_neuromuscular_load: number
  total_structural_load: number

  // Response measurements
  fitness_delta: number               // TwinState fitness_score change across window
  fatigue_depth: number | null        // Immediate post-window fatigue magnitude (HRV suppression, sleeping HR elevation, sleep quality drop relative to baseline)
                                      // Null for recovery-period observations (no stimulus to measure fatigue against)
  recovery_trajectory: RecoveryTrajectory  // How quickly wellness signals return to personal baseline
  execution_quality_delta: number | null   // Performance change on first quality session after recovery, relative to recent baseline for that session type
                                           // Null if no quality session occurred after the recovery window
                                           // The confirmation signal: strong delta + full recovery = adequate window; degraded delta = insufficient window

  // Contextual fields
  cycle_phase: string | null          // Current menstrual cycle phase during observation window
                                      // Required for female athletes, null for male athletes
                                      // All response dimensions are read through this lens — late luteal suppression differs from mid-follicular suppression
  confidence_level: 'calibration' | 'emerging' | 'established'
    // 'calibration': < 6 weeks of data, low signal reliability
    // 'emerging': 6-8 weeks, meaningful individual signal starting to appear
    // 'established': full training cycle completed, high confidence in signature

  // Structural compliance
  structurally_compliant: boolean     // Whether observation window satisfied plan structure rules
                                      // (easy days flanking hard work, rest after long runs)
  compliance_deviation: string | null // Human-readable description of what deviated from structural rules
                                      // Null if structurally_compliant = true
                                      // Examples: "skipped easy day before threshold session",
                                      //           "extra quality session added between easy days",
                                      //           "long run not followed by rest day"
                                      // Downstream weight adjustment scales by deviation severity:
                                      //   skipped easy day → mild contamination, moderate weight reduction
                                      //   extra hard session → significant contamination, heavy weight reduction
                                      //   missed rest after long run → moderate contamination, moderate weight reduction

  // Metadata
  yield_by_intent_state: Partial<Record<PhysiologicalIntentState, number>>
  analysis_version: string
}
```

---

## Vision ↔ Architecture Cross-Reference

This section maps adaptation-signature vision concepts to architecture fields explicitly.

| Vision Concept | Architecture Field(s) | Notes |
|---|---|---|
| Adaptation window (2-3 quality sessions as single compound stimulus) | `adaptation_window_id`, `window_start_date`, `window_end_date` | Groups sessions into one observation unit |
| Three training unit types (hard window, isolated session, recovery period) | `unit_type` | Explicit classification; isolated sessions weighted more heavily |
| Compound stimulus profile | `total_aerobic_load`, `total_neuromuscular_load`, `total_structural_load` | Aggregate load across all three dimensions |
| Short-term fatigue depth | `fatigue_depth` | Distinct from recovery speed — deep fatigue with fast recovery is physiologically different from shallow fatigue with slow recovery |
| Recovery trajectory | `recovery_trajectory` | How quickly wellness signals return to baseline |
| Execution quality at next session | `execution_quality_delta` | Confirmation signal: was the recovery window sufficient? |
| Cycle phase lens (female athletes) | `cycle_phase` | All three response dimensions read through this context |
| Yield per training emphasis | `yield_by_intent_state` | Per-state fitness change per unit load |
| Confidence accumulation | `confidence_level` | Distinguishes calibration-phase data from reliable signature data |
| Plan structure as experimental control | `structurally_compliant`, `compliance_deviation` | Flags contaminated observations; deviation text enables scaled weight adjustment |
| Fitness change produced | `fitness_delta` | Net fitness score change across the window |

---

## Yield Profiles

`yield_by_intent_state` maps `PhysiologicalIntentState` → `fitness_change_per_unit_load`:

```typescript
// Example observation:
{
  threshold: 0.042,     // 0.042 fitness points gained per unit of threshold load
  low_aerobic: 0.018,   // lower yield from easy aerobic
  vo2: 0.031
}
```

Over multiple adaptation windows, these values build the athlete's adaptation signature. An athlete with high threshold yield gets more threshold work in the plan; an athlete with high aerobic volume yield gets more volume. See `02-computations/adaptation-signature.md`.

**Weighting rules:**
- Observations with `unit_type = 'isolated'` receive higher analytical weight (cleaner experimental conditions)
- Observations with `structurally_compliant = false` receive reduced weight scaled by deviation severity (see `compliance_deviation` field)
- Observations with `confidence_level = 'calibration'` receive reduced weight until sufficient data accumulates
- Observations where `cycle_phase` indicates late luteal should be flagged — fatigue and recovery signals during this phase are partly hormonal, not purely load-response

---

## Block Boundary Detection

`AdaptationBlockDetectionTask` identifies adaptation window boundaries as:
- 2+ quality sessions (`threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`, `long_run`) in the preceding 5 days followed by 2+ `easy_run` or `rest` sessions — the "hard adaptation window + recovery" pattern
- OR: week boundaries in the `TrainingPlan.phases` array

In planned training, `block_id` groups on `PlannedSession` records are the primary input for this detection. The weekly synthesis agent creates `block_id` groups precisely to generate the pattern that `AdaptationBlockDetectionTask` later identifies as adaptation windows. The `block_id` is the planning mechanism; the adaptation window is the observation purpose.

**Unit type detection:**
- If the detected block contains 2+ quality sessions → `unit_type = 'hard_window'`
- If the detected block contains exactly 1 quality session flanked by easy days → `unit_type = 'isolated'`
- Recovery periods between blocks → `unit_type = 'recovery'` (active observation window, no stimulus)

---

## Invariants

- `AdaptationObservation` is only created for athletes with ≥ 6 weeks of calibration-eligible sessions (earlier data lacks sufficient signal).
- Records are append-only. Analysis version changes increment `analysis_version` and new records are created alongside old ones (old records receive `superseded_at`).
- `yield_by_intent_state` only contains keys for states that appeared in the adaptation window's `PhysiologicalSegment` records. Missing keys mean no exposure to that state during the adaptation window.
- `unit_type` must match the pattern detected by `AdaptationBlockDetectionTask` — hard window requires 2+ quality sessions, isolated requires exactly 1 quality session flanked by easy days, recovery is not an observation trigger for stimulus measurement.
- `fatigue_depth` must be null for `unit_type = 'recovery'` observations (no stimulus to measure fatigue against).
- `execution_quality_delta` must be null if no quality session occurred after the recovery window.
- `cycle_phase` is required for female athletes, null for male athletes.
- Observations with `structurally_compliant = false` should be excluded from yield profile computation or flagged with reduced weight in downstream consumers. The `compliance_deviation` text informs the severity of weight adjustment.

---

## Events

### Produced

| Event | Trigger | Version | Payload |
|---|---|---|---|
| `adaptation_observation_created` | Record inserted | v1 | `{observation_id, adaptation_window_id, fitness_delta, days_to_baseline_return, unit_type, confidence_level}` |

---

## Storage Model

| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `adaptation_observations` table | append-only | strong | indefinite |

---

## Runtime Ownership

Owns:
- Adaptation window-level adaptation measurements

Does Not Own:
- How yield profiles drive plan generation → `02-computations/plan-generation.md`
- Adaptation signature computation → `02-computations/adaptation-signature.md`

---

## Cross-References

- Adaptation signature entity: `02-computations/adaptation-signature.md`
- Plan generation consuming adaptation constraints: `02-computations/plan-generation.md` (shared types and regeneration triggers)
- Plan generation fitness improvement mode: `02-computations/plan-generation-fitness-improvement.md` (block renewal uses adaptation observations)
- PhysiologicalSegment yield computation (what state was the athlete in): `01-entities/physiological-segment.md`
- Vision-level description of adaptation learning: `vision/twin/adaptation-signature.md`
