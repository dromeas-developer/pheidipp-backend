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

### PhysiologicalIntentState
The canonical enum shared across all system layers representing what physiological state an effort intends to achieve or achieves. Eight values: `warmup`, `low_aerobic`, `high_aerobic`, `threshold`, `vo2`, `recovery`, `cooldown`, `unknown`. See `00-foundations/terminology.md` → Shared Enums.

### Readiness
The twin's current assessment of an athlete's capacity for today's training, computed from the combination of TwinState fitness/fatigue scores and Layer 4 wellness modifier. Expressed as GREEN / AMBER / RED in the recovery modifier and as plain language in coaching messages.

### Recovery Modifier
The GREEN / AMBER / RED classification of an athlete's current readiness relative to their wellness baseline. Computed by `WellnessModifierService`. Applied to `GeneratedWorkout.adjusted_targets`. See `02-computations/wellness-modifier.md`.

### Reprocessing Anchor
The `fit_file_key` stored on every non-manual Activity. Because the raw FIT file is always available, any analytical record derived from it (load scores, segments, execution observations) can be regenerated through an improved algorithm. See `00-foundations/data-tiers.md` and `04-platform/versioning-and-reprocessing.md`.

### Session Shape
A classification of how a session unfolded relative to prescribed intent. Values: `steady`, `progressive_fade`, `positive_split`, `w_shape`, `strong_finish`. Computed by `ExecutionAnalysisService`; stored on `ExecutionObservation`.

### Training Block
A period of goal-directed training with a defined start, status, and optional goal event. The temporal container for a `TrainingPlan`. One active block per athlete at a time. See `01-entities/training-block.md`.

### TwinState
An append-only snapshot of the twin's understanding of an athlete at a point in time. Never updated in place. The most recent TwinState is the current state; older records are the audit trail. See `01-entities/twin-state.md`.

### Version String
A frozen identifier for a specific pipeline snapshot. Format: `v1`, `v1.1`, `v2-rr-threshold`. Stored on every analytical record. Enables offline reprocessing and historical record comparison. See `04-platform/versioning-and-reprocessing.md`.

## Shared Enums

### PhysiologicalIntentState
```typescript
type PhysiologicalIntentState =
  | 'warmup'
  | 'low_aerobic'
  | 'high_aerobic'
  | 'threshold'
  | 'vo2'
  | 'recovery'
  | 'cooldown'
  | 'unknown'
```
`unknown` is not an error. It is the correct output when inference confidence is below threshold.

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
  | 'easy_aerobic'
  | 'long_run'
  | 'threshold'
  | 'vo2max_intervals'
  | 'tempo'
  | 'recovery_run'
  | 'strength_conditioning'
  | 'cross_training'
  | 'rest'
```

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

## Implementation Notes
- When a term in this document conflicts with common industry usage, the definition here is authoritative within this system
- `PhysiologicalIntentState` is the most important enum — any new system that touches sessions must speak this language
