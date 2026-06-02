# Terminology — Canonical Domain Definitions

## Purpose
- Defines every domain term used across architecture documents with precision
- Eliminates ambiguity when terms have common meanings that differ from their Pheidipp meaning

## Core Domain Terms

### Activity
A lean physiological observation record for a single completed training session. Not a workout summary. Stores what the twin needs, never what Garmin already computed. See `01-entities/activity.md`.

### Calibration-Eligible
An `Activity` that meets the five-rule gate for twin recalibration. See `02-computations/load-computation.md`. A session that is not calibration-eligible still exists in the training record but does not update the twin model.

### Coaching Observation
A pre-computed structured finding produced by the `ExecutionAnalysisService` and stored in `ExecutionObservation.coaching_observations`. The LLM receives this and writes narrative from it. The LLM does not produce the observation.

### Confidence Level
An assertion about how much real training data the twin has learned from for a given athlete. Three values: `low`, `medium`, `high`. Affects coaching language precision and whether race predictions are surfaced. See `00-foundations/confidence-model.md`.

### Data Tier
A classification of an athlete's hardware capability that determines which signals are available for load computation and threshold detection. Six tiers from Tier 1 (running power + chest strap RR) to Tier 6 (manual entry only). See `00-foundations/data-tiers.md`.

### Digital Twin
The ensemble of all TwinState, ExecutionObservation, AdaptationObservation, AthleteWellness, and CyclePhaseLog records for an athlete, plus the computation services that interpret them. Not a single entity — a living model of the athlete's physiological state.

### Effort Normalisation
The process of converting raw pace to a physiologically comparable effort measure, accounting for terrain grade and eventually individual biomechanics. Three generations: static GAP → per-athlete curve → personalised cost model. See `02-computations/effort-normalisation.md`.

### FIT File
The binary file format produced by Garmin and other sports devices. The raw, immutable source record for all analytical computation. Stored in object storage; never modified; referenced by `fit_file_key` on every `Activity`.

### `fit_file_key`
The object storage key referencing the raw FIT file for an Activity. The reprocessing anchor for the entire analytical pipeline. Required on every Activity that is not a manual entry.

### GAP (Grade-Adjusted Pace)
Pace normalised for terrain gradient so that uphill and flat efforts are comparable. The system-wide standard for all pace-based computations. Raw pace is never used in any calculation. See `02-computations/effort-normalisation.md`.

### Generation Event
A log record written for every LLM API call attempt, whether successful or failed. The primary operational observability primitive for the coaching layer. See `01-entities/generation-event.md`.

### Hard Block
A training unit of two to three quality sessions in close succession. The atomic unit for adaptation signature computation. See `02-computations/adaptation-signature.md`.

### LT1
Lactate threshold 1 — the intensity at which blood lactate first begins to rise above resting baseline. Corresponds to the aerobic threshold and the lower boundary of the high aerobic zone. Estimated by threshold detection from HR or RR signal.

### LT2
Lactate threshold 2 — the intensity at which lactate accumulation exceeds the body's buffering capacity. Corresponds to the anaerobic threshold / functional threshold. The primary reference for threshold zone workout targets.

### PhysiologicalIntent
The canonical enum representing the physiological adaptation a session targets. Eight values: `low_aerobic`, `high_aerobic`, `threshold`, `vo2max`, `race_specific`, `neuromuscular`, `recovery_support`, `calibration`. This is the middle layer of the three-layer hierarchy: MethodologyTraitVector → PhysiologicalIntent → SessionType. See `00-foundations/terminology.md` → Shared Enums.

### Readiness
The twin's current assessment of an athlete's capacity for today's training, computed from the combination of TwinState fitness/fatigue scores and Layer 4 wellness modifier. Expressed as GREEN / AMBER / RED in the recovery modifier and as plain language in coaching messages.

### Recovery Modifier
The GREEN / AMBER / RED classification of an athlete's current readiness relative to their wellness baseline. Computed by `WellnessModifierService`. Applied to `GeneratedWorkout.adjusted_targets`. See `02-computations/wellness-modifier.md`.

### Reprocessing Anchor
The `fit_file_key` stored on every non-manual Activity. Because the raw FIT file is always available, any analytical record derived from it (load scores, segments, execution observations) can be regenerated through an improved algorithm. See `00-foundations/data-tiers.md` and `04-platform/versioning-and-reprocessing.md`.

### Session Shape
A classification of how a session unfolded relative to prescribed intent. Values: `steady`, `progressive_fade`, `positive_split`, `w_shape`, `strong_finish`. Computed by `ExecutionAnalysisService`; stored on `ExecutionObservation`.

### Training Goal
A period of goal-directed training with a defined start, status, and optional goal event. The temporal container for a `TrainingPlan`. One active goal per athlete at a time. See `01-entities/training-goal.md`.

### TwinState
An append-only snapshot of the twin's understanding of an athlete at a point in time. Never updated in place. The most recent TwinState is the current state; older records are the audit trail. See `01-entities/twin-state.md`.

### Version String
A frozen identifier for a specific pipeline snapshot. Format: `v1`, `v1.1`, `v2-rr-threshold`. Stored on every analytical record. Enables offline reprocessing and historical record comparison. See `04-platform/versioning-and-reprocessing.md`.

## Shared Enums

### PhysiologicalIntent
```typescript
type PhysiologicalIntent =
  | 'low_aerobic'
  | 'high_aerobic'
  | 'threshold'
  | 'vo2max'
  | 'neuromuscular'
  | 'recovery'
```
The physiological adaptation a session targets. Each workout step has exactly one intent. This is the primary coaching abstraction — the system works directly with intents, not zones. Many:1 mapping from SessionType (16 sessions → 6 intents).

**Compliance families:**
- **Aerobic family** (intensity ladder): `recovery` → `low_aerobic` → `high_aerobic` → `threshold` → `vo2max`
- **Neuromuscular family** (orthogonal): `neuromuscular`

Neuromuscular efforts are not "above VO2max" or "below threshold" — they are a different physiological system entirely.

### TwinConfidenceLevel
```typescript
type TwinConfidenceLevel = 'low' | 'medium' | 'high'
```

### RecoveryModifierLevel
```typescript
type RecoveryModifierLevel = 'green' | 'amber' | 'red'
```

### SessionType
```typescript
type SessionType =
  | 'rest'
  | 'recovery_run'
  | 'easy_run'
  | 'long_run'
  | 'medium_long_run'
  | 'steady_state'
  | 'tempo'
  | 'threshold'
  | 'vo2max'
  | 'hill_repeats'
  | 'fartlek'
  | 'strides'
  | 'drills_mobility'
  | 'cross_training'
  | 'test_session'
  | 'optional_run'
```
The concrete workout prescription. The coaching construct that appear on the calendar. Maps to PhysiologicalIntent via `SESSION_INTENT_MAP`.

Note: `race_specific` is NOT a SessionType — it is a SessionPurpose. A marathon pace long run is `session_type: long_run, purpose: race_specific`.

### SessionPurpose
```typescript
type SessionPurpose =
  | 'general'            // Standard training session
  | 'race_specific'      // Race-pace, race strategy
  | 'calibration'        // Test, time trial, benchmark
```
The contextual reason for the session. Not the adaptation, but the coaching rationale. Affects how results are interpreted, not compliance assessment.

**Interpretation rules:**
- `general`: Standard compliance assessment (was intensity matched?)
- `race_specific`: Execution quality assessment (did the athlete race well?)
- `calibration`: Data quality assessment (was sufficient signal collected?)

### SessionSlot
```typescript
type SessionSlot = 'am' | 'pm'
```
Used to distinguish AM/PM sessions on double-day schedules. Null for single-session days.

### SessionPriority
```typescript
type SessionPriority = 'primary' | 'secondary'
```
Primary sessions receive full workout generation. Secondary sessions may be suggested without detailed targets (e.g. strength, yoga). Recovery time is measured from primary to primary.

### InjurySeverity
```typescript
type InjurySeverity = 'minor' | 'moderate' | 'major'
```
Used when `goal_type = 'recovery'` to determine phase duration and load progression.

### GoalType
```typescript
type GoalType =
  | 'race_event'        // periodised toward specific goal; peaking, tapering, race-specific preparation
  | 'fitness_improvement' // active development; progressive overload; measurable gains
  | 'maintenance'       // consistency-focused; habit preservation; fitness preservation
  | 'recovery'          // healing-focused; conservative load; protective coaching
```

### PhaseLabel
```typescript
type PhaseLabel =
  | 'base_building'
  | 'threshold_development'
  | 'race_specific'
  | 'taper'
  | 'race_week'
  | 'recovery'
  | 'rolling_block'
```

### CyclePhase
```typescript
type CyclePhase = 'menstrual' | 'follicular' | 'ovulatory' | 'luteal' | 'unknown'
```

### DataTier
```typescript
type DataTier = 1 | 2 | 3 | 4 | 5 | 6
```
See `00-foundations/data-tiers.md` for hardware mapping.

### CheckpointType

```typescript
type CheckpointType =
  | 'calibration'        // test workout for specific metric
  | 'benchmark'          // standardised progress measurement
  | 'race_simulation'    // race-pace effort without full stress
  | 'secondary_race'     // B-race or C-race as assessment
  | 'progress_review'    // periodic adaptation check
```

### MethodologyTrait
```typescript
type MethodologyTrait =
  | 'high_aerobic_volume'
  | 'low_intensity_dominant'
  | 'threshold_density'
  | 'high_intensity_sparse'
  | 'high_frequency'
  | 'structural_durability'
  | 'race_specificity'
  | 'variety_emphasis'
  | 'neuromuscular_support'
  | 'conservative_progression'
```
One of ten fixed dimensions describing coaching philosophy expression. Closed ontology — not extensible. Hidden from athletes, optionally explainable in plain language.

### MethodologyTraitVector
```typescript
type MethodologyTraitVector = {
  high_aerobic_volume: number        // 0.0 - 1.0 expression
  low_intensity_dominant: number
  threshold_density: number
  high_intensity_sparse: number
  high_frequency: number
  structural_durability: number
  race_specificity: number
  variety_emphasis: number
  neuromuscular_support: number
  conservative_progression: number
}
```
Fixed vector — all traits present, omitted = zero. Expression/strength values (0.0–1.0), not weights. Highest layer of the three-layer hierarchy: MethodologyTraitVector → PhysiologicalIntent → SessionType. Phase-level evolution, not weekly.

### SessionIntentMapping
```typescript
type SessionIntentMapping = {
  [key in SessionType]: PhysiologicalIntent
}

const SESSION_INTENT_MAP: SessionIntentMapping = {
  'rest': 'recovery',
  'recovery_run': 'recovery',
  'easy_run': 'low_aerobic',
  'long_run': 'high_aerobic',
  'medium_long_run': 'high_aerobic',
  'steady_state': 'high_aerobic',
  'tempo': 'threshold',
  'threshold': 'threshold',
  'vo2max': 'vo2max',
  'hill_repeats': 'vo2max',
  'fartlek': 'vo2max',
  'strides': 'neuromuscular',
  'drills_mobility': 'neuromuscular',
  'cross_training': 'low_aerobic',
  'test_session': 'vo2max',  // default; actual intent depends on test protocol
  'optional_run': 'recovery'
}
```
Many:1 mapping from 16 session types to 6 intents. Canonical reference for session→intent derivation. Note: `test_session` intent depends on the specific test protocol — the default is `vo2max` but may be `threshold` or `high_aerobic` depending on the test.

### WorkoutTarget
```typescript
type WorkoutTarget = {
  signal_type: 'power' | 'gap' | 'hr' | 'description'
  primary: {
    min: number | null
    max: number | null
    unit: string
  }
  fallback: WorkoutTarget | null
  description: string  // always present; plain English
}
```
Range-based target for a workout step. The athlete sees explicit numbers (e.g., "250-280W"), never zone numbers. The system selects the best signal type based on session type, physiological intent, signal availability, and signal quality.

### IntentRange
```typescript
type IntentRange = {
  min: number
  max: number | null  // null for open-ended ranges
}

type IntentRanges = {
  [key in PhysiologicalIntent]: {
    hr: IntentRange | null
    power: IntentRange | null
    gap: IntentRange | null
  }
}
```
Computed on-the-fly from the athlete's current PhysiologyThresholds. Not stored as a separate entity. Architecture owns "intent → physiological region"; exact multiplier constants belong in implementation.

### ComplianceFamily
```typescript
type ComplianceFamily =
  | 'aerobic'        // recovery, low_aerobic, high_aerobic, threshold, vo2max
  | 'neuromuscular'  // neuromuscular only
```
Physiological intents belong to compliance families. Compliance is assessed within families only. Neuromuscular is orthogonal to the aerobic intensity ladder.

### ComplianceResult
```typescript
type ComplianceResult = {
  step_id: string
  prescribed_intent: PhysiologicalIntent
  actual_intent: PhysiologicalIntent
  compliance: 'compliant' | 'under' | 'over' | 'mismatch'
  deviation: number
  family: ComplianceFamily
  session_purpose: SessionPurpose
  purpose_interpretation: string
}
```
Step-level compliance result. Prescribed vs actual intent, assessed within compliance families.

### WorkoutComplianceSummary
```typescript
type WorkoutComplianceSummary = {
  workout_id: string
  step_results: ComplianceResult[]
  overall_compliance: 'compliant' | 'under' | 'over' | 'mixed'
  intent_distribution: Record<PhysiologicalIntent, number>
  purpose: SessionPurpose
  summary: string  // plain English; narrated by agent
}
```
Session-level compliance aggregation. Combines step-level results into an overall workout assessment.

### Weekly Synthesis Types

```typescript
type PhaseArcEntry = {
  week_number: number
  phase_label: PhaseLabel
  methodology: MethodologyTraitVector
  physiological_emphasis: string
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  race_considerations?: string
  checkpoint_intent?: string
  target_session_count: number
}

type AdjustedWeeklyIntent = {
  phase_label: PhaseLabel
  methodology: MethodologyTraitVector
  physiological_emphasis: string
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  adjustment_made: boolean
  adjustment_reason: string | null
  adjustment_source: 'plan_unchanged' | 'fatigue_correction' | 'schedule_constraint' | 'adaptation_acceleration' | 'checkpoint_result'
  max_sessions: number | null
  session_types_preferred: SessionType[] | null
  avoid_session_types: SessionType[] | null
}

type WeeklyPlanStatus = 'synthesised' | 'active' | 'completed'

type PriorWeekSummary = {
  week_number: number
  phase_label: PhaseLabel
  planned_sessions: number
  completed_sessions: number
  missed_sessions: number
  skipped_sessions: number
  accumulated_fatigue_delta: number
  average_recovery_modifier: RecoveryModifierLevel
  adaptation_block_completed: boolean
  checkpoint_completed: boolean
  checkpoint_result?: {
    metric_updated: boolean
    confidence_changed: boolean
  }
  session_type_distribution: Record<SessionType, number>
}

```

## Implementation Notes
- When a term in this document conflicts with common industry usage, the definition here is authoritative within this system
- `PhysiologicalIntent` is the most important enum — any new system that touches sessions must speak this language
