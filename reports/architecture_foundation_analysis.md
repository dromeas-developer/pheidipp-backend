# Architecture Foundation Analysis Report

## Executive Summary

The new architecture documentation under `docs/architecture/00-foundations` and `docs/architecture/01-definitions` represents a **fundamental departure** from both the product vision and the previous architecture (`docs/architecture-old`). The new docs describe a generic fitness-tracking entity model with traditional metrics (TSS/CTL/ATL), CRUD workout APIs, and brand-based hardware classification. The old architecture described an event-driven, pipeline-oriented coaching system with a five-layer digital twin, signal-quality data tiers, append-only state, and deterministic Python analytics with LLM narration.

**Critical finding:** The new architecture violates multiple vision-level invariants and would produce a product that contradicts Pheidipp's core identity as defined in `docs/vision/`.

---

## 1. Fundamental Model Inconsistencies

### 1.1 The Twin Has Disappeared

**Vision (`twin/core.md`, `twin/layers.md`):**
- The Digital Twin is the single source of truth, with five layers: fitness/fatigue, thresholds, adaptation, external modifiers, execution patterns
- Non-running activities are explicitly excluded from twin calibration
- The twin is always honest about confidence

**Old Architecture (`architecture-old/twin/twin-state.md`):**
- `TwinState` is append-only — every recalibration appends a new record
- Four recalibration triggers: questionnaire, activity_sync, calibration, wellness_update
- Layer 1 three-dimensional evolution plan (aerobic, neuromuscular, structural fitness/fatigue)
- Individual time constants learned per athlete

**New Architecture (`01-definitions/athlete.md`):**
- `TwinState` is reduced to a UUID field on the `Athlete` entity: `twinStateId: UUID`
- No mention of append-only invariant, recalibration triggers, or five-layer structure
- No confidence model, no layer separation, no individual time constants

**Impact:** The new model cannot support the vision's coaching intelligence. Without append-only TwinState, historical coaching decisions are not auditable. Without the five-layer structure, the system cannot model the interactions between fitness, fatigue, wellness, and execution patterns.

### 1.2 Load & Fatigue Model Replaced with Generic TrainingPeaks Metrics

**Vision (`twin/load-fatigue.md`):**
- Three-dimensional load: aerobic, neuromuscular, structural — each with distinct accumulation and recovery timelines
- Rejects single-number fitness scores
- Individual time constants learned per athlete
- Crossover athlete profile (aerobic capacity high, structural tolerance low)

**Old Architecture (`architecture-old/analytical pipeline/load-and-thresholds.md`):**
- Detailed formulas for all three load dimensions
- Aerobic load: HR reserve integration or power-based, normalised so 1 hour at LT1 ≈ 100 units
- Neuromuscular load: variability index + time above VO2 threshold
- Structural load: distance + elevation + surface modifier + session density penalty

**New Architecture (`01-definitions/athlete_fitness.md`):**
- Includes the three loads (`aerobicLoad`, `neuromuscularLoad`, `structuralLoad`) **but also adds:**
  - `tss` — Training Stress Score (composite)
  - `atl` — Acute Training Load (short-term fatigue)
  - `ctl` — Chronic Training Load (long-term fitness)
  - `tsb` — Training Stress Balance (ctl - atl)

**Impact:** TSS/CTL/ATL/TSB are TrainingPeaks metrics that the vision explicitly avoids. The vision states "General fitness proxies are insufficient for running adaptation" and "Conclusions matter more than metrics." Adding these traditional metrics contradicts the product's differentiator of sport-specific modeling. The `athlete_fitness.md` document even says "TSS, ATL, CTL, TSB are derived from aerobic, neuromuscular, and structural load dimensions" — but these are not derivable from the three-dimensional model described in the vision. They are a parallel, incompatible model.

### 1.3 Raw Workout Summaries Persisted (Violates Core Invariant)

**Vision (`product/constraints.md`, `twin/data-philosophy.md`):**
- "No raw data surfaces"
- "Conclusions matter more than metrics"
- Activities are physiological observations, not workout summaries

**Old Architecture (`architecture-old/transversal/principles.md`, `architecture-old/data/data-models.md`):**
- Invariant #1: "Activities are physiological observations, not workout summaries. Activity stores what the twin model needs. It never stores avg_hr, avg_pace, avg_power, or lap dumps."
- Invariant #6: "No global session averages are persisted."
- `Activity` model has no avg_hr, avg_pace, avg_power fields

**New Architecture (`01-definitions/athlete_workout.md`):**
```typescript
paceData: {
  overall: number | null
  avg: number | null
  min: number | null
  max: number | null
  segments: Array<{distance: number, pace: number}> | null
}
hrData: {
  avg: number | null
  min: number | null
  max: number | null
  zones: Array<{duration: number, zone: number}> | null
}
```

**Impact:** The new `AthleteWorkout` model is exactly the "workout summary" that the old architecture forbade. It stores averages, min/max, and zone distributions — all things that Garmin already computes. This violates the core principle that "the Activity table does not store the averages that Garmin already computes."

### 1.4 FIT File and Reprocessing Anchor Missing

**Vision (`twin/data-philosophy.md`):**
- "Real signals, not assumptions"
- RR intervals preferred over optical HR
- Overnight minimum HR used as resting HR anchor

**Old Architecture (`architecture-old/transversal/principles.md`, `architecture-old/data/data-models.md`):**
- Invariant #3: "`fit_file_key` is a hard prerequisite. No Activity record commits without its raw file stored in object storage."
- The FIT file is the reprocessing anchor for the entire analytical pipeline
- `Activity` model has `fit_file_key: str` — required, never null

**New Architecture:**
- No mention of FIT files anywhere
- `AthleteWorkout` has `gpsData: string | null`, `powerData: string | null` — but these are generic strings, not structured FIT file references
- No `fit_file_key`, no reprocessing anchor, no versioning of pipeline outputs

**Impact:** Without FIT file storage, the system cannot reprocess historical data as algorithms improve. Without the reprocessing anchor, the versioning strategy described in the old architecture is impossible. The vision's emphasis on "continuous learning from real training" requires the ability to re-analyse historical sessions.

---

## 2. Missing Domain Concepts

### 2.1 Confidence Model Completely Absent

**Vision (`twin/confidence-and-uncertainty.md`):**
- Three confidence levels: LOW, MEDIUM, HIGH
- LOW: questionnaire-only bootstrap, conservative language, no race prediction
- MEDIUM: after 4 calibration-eligible HR sessions, threshold-referenced ranges
- HIGH: after 2 RR sessions or 1 dedicated calibration run, point estimates
- Confidence ratchets upward only

**Old Architecture (`architecture-old/twin/twin-state.md`, `00-foundations/confidence-model.md`):**
- Detailed transition thresholds and downstream effects
- Confidence stored on every `TwinState` record
- Race prediction suppressed at LOW confidence (204 No Content)
- Workout generation agent uses confidence to determine target precision

**New Architecture:**
- `confidence` appears as a 0-100 number on `AthleteWorkout`, `AthletePhysiology`, `AthleteTrainingBlock` — but without the three-tier semantics
- No confidence transitions, no downstream effects, no coaching language implications

**Impact:** The confidence model is central to the vision's "honesty invariant." Without it, the system cannot modulate coaching precision based on data quality, and cannot communicate uncertainty appropriately to athletes.

### 2.2 Data Tiers Replaced with Brand-Based Sources

**Vision (`twin/load-fatigue.md`):**
- Six data tiers based on signal quality: Tier 1 (power + RR) through Tier 6 (manual entry)
- Tiers determine which analytical capabilities are available
- Tier 5-6 excluded from twin calibration

**Old Architecture (`00-foundations/data-tiers.md`):**
- Complete tier definitions with hardware mappings
- Tier inference function from `hr_source` and `power_source`
- Load dimensions and threshold detection algorithms per tier
- Tier stored on `TwinState` at creation time

**New Architecture (`01-definitions/athlete_training_preferences.md`):**
```typescript
hrSource: "garmin" | "polar" | "whoop" | "apple" | "other" | null
powerSource: "stages" | "garmin" | "wahoo" | "rotor" | "crank" | "pedal" | null
```

**Impact:** Brand-based sources do not indicate signal quality. A Garmin watch could be using optical HR (Tier 4) or chest strap RR (Tier 1-3). The new model cannot determine data tier from brand names, which breaks load computation, threshold detection, and calibration eligibility gating.

### 2.3 PhysiologicalIntentState Enum Missing

**Vision (`coach/voice-and-format.md`):**
- Coach speaks in concepts, not zone numbers or percentages

**Old Architecture (`architecture-old/transversal/shared-language.md`, `00-foundations/terminology.md`):**
- `PhysiologicalIntentState` is "the most important unifying concept in the architecture"
- Eight values: warmup, low_aerobic, high_aerobic, threshold, vo2, recovery, cooldown, unknown
- Used across all five layers: workout generation, execution analysis, segmentation, adaptation modelling, twin reasoning

**New Architecture:**
- `sessionType` on `AthleteWorkout`: `"easy" | "tempo" | "interval" | "race" | "strength" | "recovery"`
- No `PhysiologicalIntentState` anywhere
- No segmentation pipeline, no planned vs. actual comparison

**Impact:** Without `PhysiologicalIntentState`, the system cannot compare prescribed intent with actual execution. This breaks execution analysis, compliance assessment, and adaptation signature learning — all core to the vision.

### 2.4 Segmentation Pipeline Missing

**Old Architecture (`architecture-old/analytical pipeline/segmentation-pipeline.md`):**
- Three pipeline generations: heuristic (Gen 1), statistical PELT/BOCPD (Gen 2), HMM (Gen 3)
- Signal preprocessing order: 7 fixed steps
- Three segment types: `PlannedSegment`, `DeviceSegment`, `PhysiologicalSegment`
- HMM architecture with states, observations, transition matrix, emission distributions

**New Architecture:**
- No segmentation pipeline
- No `PhysiologicalSegment` model
- No execution analysis service
- `AthleteWorkout` has `paceData.segments` but these are distance/pace pairs, not physiological state segments

**Impact:** Segmentation is how the system determines what physiological state the athlete was in at each moment. Without it, there is no execution analysis, no compliance assessment, and no adaptation signature.

### 2.5 External Modifiers / Wellness Simplified Beyond Recognition

**Vision (`twin/external-modifiers.md`):**
- Sleep, HRV, menstrual cycle, time-of-day as trend-based modifiers
- Single-night anomalies ignored
- Overnight min HR used (not morning spot checks)
- Cycle phase weighted by individual correlation

**Old Architecture (`architecture-old/operational layer/wellness-and-modifiers.md`):**
- `AthleteWellness` with specific fields: `total_sleep_minutes`, `deep_sleep_minutes`, `rem_sleep_minutes`, `avg_sleeping_hr_bpm`, `min_sleeping_hr_bpm`, `hrv_overnight_avg_ms`, `hrv_overnight_min_ms`
- Baseline computation: 28-day median and IQR
- Trend detection: 3-night and 7-night rolling windows
- Recovery modifier: GREEN/AMBER/RED with specific signal weights (sleeping HR 0.35, HRV 0.30, sleep duration 0.20, etc.)
- Menstrual cycle: `CyclePhaseLog` with phase computation, integration with recovery modifier, structural load flag for ovulatory phase, thermoregulatory modifier for luteal phase
- Weather: `WeatherForecast` with heat index, wind, luteal modifier stacking

**New Architecture (`01-definitions/athlete_wellness.md`, `01-definitions/external_modifiers.md`):**
- `AthleteWellness` has generic `sleepData` with light/awake/rem/deep/total — but no `avg_sleeping_hr_bpm` or `min_sleeping_hr_bpm`
- `overnightHRV` is present but no `hrv_overnight_min_ms`
- `ExternalModifiers` has `sleepScore`, `sleepQuality`, `hrv`, `hrvTrend` — but no specific weights, no GREEN/AMBER/RED, no cycle phase adjustments
- `menstrualCycleDay` is present but no `CyclePhaseLog`, no phase computation, no integration with recovery modifier
- No `WeatherForecast` model, no weather adjustment formulas

**Impact:** The new wellness model loses the specific signal hierarchy, baseline computation, trend detection, and cycle integration that the vision describes. A generic `sleepScore` cannot replace the weighted composite of specific physiological signals.

### 2.6 Plan Generation and Session Lifecycle Missing

**Vision (`coach/plan-visibility.md`, `product/goal-modes.md`):**
- Full macro plan visibility with phase labels
- Specific workouts generated only on the day
- Four goal modes: race/event, fitness improvement, maintenance, recovery

**Old Architecture (`architecture-old/operational layer/planning-and-sessions.md`):**
- `PlanGenerationService`: pure Python, no LLM
- Phase arc computation formulas for race vs open training
- Session distribution structural rules (long run placement, quality session spacing)
- Crossover athlete structural capacity ramp
- Session lifecycle state machine: pending → generated → completed/skipped/missed/redistributed
- Skip and redistribution flow with classification agent
- Illness and injury handling
- Workout library with substitution query logic

**New Architecture (`01-definitions/athlete_training_block.md`):**
- `AthleteTrainingBlock` has `phase`: `"base" | "build" | "peak" | "race" | "recovery" | "maintenance"`
- No plan generation service
- No session distribution rules
- No skip/redistribution flow
- No workout library
- No illness/injury handling

**Impact:** The new model has training blocks but no plan generation logic, no session lifecycle management, and no substitution system. The vision's "same-day workout generation" and "plan visibility" cannot be implemented without these components.

### 2.7 Coaching Services Missing

**Vision (`coach/voice-and-format.md`, `coach/post-workout.md`, `coach/first-message.md`, `coach/objectives.md`, `coach/race-prediction.md`, `coach/substitution.md`):**
- Three-paragraph coach messages, no bullets/headers/emojis
- Post-workout analysis: compliance, execution story, historical correlation, objective progress
- First message: four paragraphs demonstrating genuine data analysis
- Objectives: living objectives seeded from twin analysis, updated weekly
- Race prediction: living predictions adjusted for weather, course profile
- Substitution: bounded conversations for workout changes

**Old Architecture (`architecture-old/LLM Layer/llm-and-agents.md`, `architecture-old/operational layer/coaching-services.md`):**
- LLM agents: workout generation, post-workout analysis, first message, skip conversation
- Context window targets: 2k-6k tokens per agent
- `GenerationEvent` logging for every LLM call
- `ContextBudget` abstraction
- Objectives system: `Objective` and `ObjectiveUpdate` models, seeding rules, update cadence
- Comparable session identification: two-pass algorithm (hard filters + similarity scoring)
- Race prediction: `RacePrediction` model with baseline formula, weather/course adjustments

**New Architecture:**
- No LLM agents
- No `GenerationEvent` model
- No objectives system
- No comparable session identification
- No race prediction
- No coach voice or message format rules

**Impact:** The coaching layer is entirely absent from the new architecture. The product vision is fundamentally about coaching, not data tracking. Without these services, the system cannot produce the coaching experience described in the vision.

### 2.8 Execution Patterns and Adaptation Signature Missing

**Vision (`twin/execution-patterns.md`, `twin/adaptation-signature.md`):**
- Rep-level execution patterns: drift, fade, sandbagging
- Session shapes: steady, progressive_fade, positive_split, w_shape, strong_finish
- Hard blocks as atomic stimulus units
- 6-8 weeks for meaningful adaptation signal
- Female cycle phase controlled for in adaptation measurements

**Old Architecture (`architecture-old/data/data-models.md`, `architecture-old/analytical pipeline/load-and-thresholds.md`):**
- `ExecutionObservation` with `session_shape`, `effort_compliance`, `key_signals`, `coaching_observations`
- `AdaptationObservation` with `yield_by_intent_state`, `fitness_delta`, `recovery_trajectory`
- Block-level adaptation signal computation

**New Architecture:**
- No `ExecutionObservation` model
- No `AdaptationObservation` model
- No session shapes
- No hard block concept
- No adaptation signature learning

**Impact:** These are Layer 3, 4, and 5 of the twin. Without them, the system cannot learn from execution, cannot build adaptation signatures, and cannot personalise plans based on individual response patterns.

---

## 3. Specific Inconsistencies

### 3.1 "No Workout Builder" Constraint Violated

**Vision (`product/constraints.md`):**
- "Athletes cannot create, edit, or customise workouts. The coach owns all workout design."
- Agency limited to: accept, substitute from coach-suggested alternatives, or skip

**New Architecture (`01-definitions/athlete_workout.md`):**
```yaml
POST /api/v1/athletes/{id}/workouts
Request: RecordWorkoutRequest
Response: 201 Created, WorkoutResponse

PATCH /api/v1/athletes/{id}/workouts/{id}
Request: UpdateWorkoutRequest
Response: 200 OK, WorkoutResponse
```

**Impact:** These APIs allow athletes to create and update workouts directly, violating a hard product constraint.

### 3.2 Gender vs. Sex Enum Mismatch

**Old Architecture (`architecture-old/operational layer/planning-and-sessions.md`):**
```python
sex: enum: male, female, not_specified
# female enables menstrual cycle tracking
```

**New Architecture (`01-definitions/athlete_account_profile.md`):**
```typescript
gender: "male" | "female" | "other" | null
```

**Impact:** `not_specified` vs. `other` is a semantic difference. More importantly, the new model uses "gender" while the old used "sex" — for physiological modeling (menstrual cycle tracking), biological sex is the relevant attribute. The vision's women's cycle integration (`twin/womens-cycle.md`) depends on this.

### 3.3 Sport Background Enum Changed and Simplified

**Old Architecture (`architecture-old/operational layer/planning-and-sessions.md`):**
```python
sport_background: running_primary, cycling, swimming, triathlon, team_sport, gym_fitness, none
# crossover athletes (non-running primary) trigger structural capacity risk flag
```

**New Architecture (`01-definitions/athlete_training_preferences.md`):**
```typescript
sportBackground: "runner" | "triathlete" | "cyclist" | "beginner" | "intermediate" | "advanced" | null
```

**Impact:** The new enum mixes sport (runner, triathlete, cyclist) with experience level (beginner, intermediate, advanced). The vision's crossover athlete profile detection requires knowing if the athlete's background is running-primary or not. "Beginner" does not indicate sport background — a beginner could be a runner or a cyclist.

### 3.4 GAP (Grade-Adjusted Pace) Missing

**Vision (`twin/load-fatigue.md`):**
- "Grade-Adjusted Pace — Always, Never Raw Pace"
- Raw pace without grade adjustment "corrupts load calculations and historical comparisons"

**Old Architecture (`architecture-old/analytical pipeline/effort-normalisation.md`):**
- Three generations of normalisation: static GAP → per-athlete curve → personalised cost model
- Static formula: `correction_factor = 1 + 0.033 * grade + 0.00012 * grade²`

**New Architecture (`01-definitions/athlete_workout.md`):**
- `paceData` stores raw pace values with no mention of grade adjustment
- No effort normalisation service
- No grade response curve

**Impact:** Without GAP, pace-based computations are systematically wrong on varied terrain. This corrupts load scores, threshold estimates, and historical comparisons.

### 3.5 Versioning Strategy Missing

**Old Architecture (`architecture-old/analytical pipeline/versioning.md`, `00-foundations/principles.md`):**
- Five version fields: `ingestion_pipeline_version`, `cleaning_pipeline_version`, `segmentation_version`, `analysis_version`, `model_version`
- Version strings are frozen, reproducible pipeline snapshots
- Immutable historical records with `superseded_at`
- Reprocessing test: "Can this be recomputed from the stored FIT file?"

**New Architecture:**
- No version fields on any model
- No `superseded_at` pattern
- No reprocessing strategy

**Impact:** Without versioning, algorithm improvements cannot be applied to historical data. The system cannot compare outputs across pipeline versions, and computed fields cannot be safely regenerated.

### 3.6 Event Catalogue Simplified Beyond Recognition

**Old Architecture (`00-foundations/event-catalogue.md`):**
- 20+ event types covering ingestion, twin, wellness, planning, coaching, cycle
- Producer/consumer contracts for each event
- Event schemas with specific payloads

**New Architecture (`01-definitions/*.md`):**
- Generic events: `athlete.created`, `wellness.recorded`, `workout.completed`, `twin.state_updated`
- No `fit_file_received`, `activity_calibration_eligible`, `twin_confidence_upgraded`, `recovery_modifier_changed`, `session_skipped`, `coaching_message_generated`, etc.

**Impact:** The event catalogue is the primary mechanism for decoupling async pipeline stages. Without the specific domain events, the system cannot coordinate the complex async workflows described in the vision (FIT ingestion → load computation → threshold detection → twin recalibration → workout generation → post-workout analysis).

---

## 4. Empty Directories

The following directories in the new architecture are completely empty, indicating major sections are missing:

- `docs/architecture/02-inference/` — Missing all computation algorithms:
  - Load computation (`load-and-thresholds.md`)
  - Threshold detection (`load-and-thresholds.md`)
  - Effort normalisation (`effort-normalisation.md`)
  - Segmentation pipeline (`segmentation-pipeline.md`)
  - Wellness modifier computation (`wellness-and-modifiers.md`)

- `docs/architecture/03-orchestration/` — Missing all application services:
  - Plan generation (`planning-and-sessions.md`)
  - Session lifecycle management (`planning-and-sessions.md`)
  - Coaching services (`coaching-services.md`)
  - LLM agents (`llm-and-agents.md`)

- `docs/architecture/04-platform/` — Missing all infrastructure concerns:
  - Versioning and reprocessing (`versioning.md`)
  - Event topology and routing
  - Failure handling and retry policies
  - Async worker queue configuration

- `docs/architecture/05-api-contracts/` — Missing all API specifications

---

## 5. What the New Architecture Gets Right

Despite the gaps, the new architecture introduces some useful patterns not present in the old docs:

1. **Structured document template** (`document_template.md`) — Consistent schema for all definition documents
2. **Runtime ownership boundaries** — Clear "Owns / Does Not Own" sections
3. **Mutation rules per layer** — API / Service / Repository / Read Model access patterns
4. **Performance constraints** — Specific p95 latency targets
5. **Observability** — Metrics, logs, and traces defined per entity
6. **Idempotency** — Idempotency rules for creation and updates
7. **Authorization delegation** — Consistent pattern of delegating to auth-service

These are good engineering practices that could be incorporated into the old architecture's structure.

---

## 6. Recommendations

### 6.1 Do Not Build from the New Architecture as Currently Written

The new architecture would produce a generic fitness tracking app, not the coaching system described in the vision. Key invariants are violated, core domain concepts are missing, and the model cannot support the product's differentiators.

### 6.2 Reconcile the Two Architectures

The old architecture (`docs/architecture-old/`) is much closer to the vision. The new architecture's structural improvements (document template, runtime ownership, performance constraints) should be applied to the old architecture's content, not the other way around.

### 6.3 Specific Actions Needed

1. **Restore the five-layer twin model** with append-only `TwinState`, confidence levels, and recalibration triggers
2. **Restore data tiers** (1-6) based on signal quality, not brand names
3. **Restore `PhysiologicalIntentState`** as the shared language across all layers
4. **Restore the segmentation pipeline** with three generations and `PhysiologicalSegment` as the stable interface
5. **Restore FIT file ingestion** with `fit_file_key` as the reprocessing anchor
6. **Remove TSS/CTL/ATL/TSB** from the fitness model — these contradict the vision
7. **Remove raw workout averages** (avg pace, avg HR) from `AthleteWorkout` — these violate the core invariant
8. **Restore the coaching layer**: LLM agents, objectives system, comparable session identification, race prediction
9. **Restore plan generation and session lifecycle** with structural rules and skip/redistribution flow
10. **Restore wellness signal specifics**: sleeping HR, HRV with weights, cycle phase integration, weather adjustments
11. **Restore versioning strategy** with `superseded_at` and the reprocessing test
12. **Restore the event catalogue** with all domain-specific events
13. **Fix the workout builder violation** — remove POST/PATCH workout APIs or restrict them to system use only
14. **Fix sport background enum** — separate sport from experience level
15. **Fix gender/sex field** — use "sex" with `male`, `female`, `not_specified` for physiological modeling

### 6.4 Use the New Structure, Keep the Old Content

The new directory structure (`00-foundations`, `01-definitions`, `02-inference`, `03-orchestration`, `04-platform`, `05-api-contracts`) is reasonable. The old content should be migrated into this structure while preserving the domain model and invariants.

---

## 7. Summary Table: Vision Requirements vs. New Architecture

| Vision Requirement | Old Architecture | New Architecture | Status |
|---|---|---|---|
| Five-layer twin | ✅ Full spec | ❌ Missing | **Critical gap** |
| Append-only TwinState | ✅ Invariant | ❌ Mutable field | **Critical gap** |
| Confidence model (LOW/MEDIUM/HIGH) | ✅ Full spec | ❌ Generic 0-100 | **Critical gap** |
| Data tiers (1-6) | ✅ Full spec | ❌ Brand-based | **Critical gap** |
| FIT file anchor | ✅ Invariant | ❌ Missing | **Critical gap** |
| No raw averages persisted | ✅ Invariant | ❌ Stored on Workout | **Invariant violated** |
| GAP (never raw pace) | ✅ Three generations | ❌ Missing | **Critical gap** |
| PhysiologicalIntentState | ✅ Central enum | ❌ Missing | **Critical gap** |
| Segmentation pipeline | ✅ Three generations | ❌ Missing | **Critical gap** |
| Three load dimensions | ✅ Formulas | ⚠️ Present + TSS/CTL | **Model corrupted** |
| External modifiers (weighted) | ✅ Specific weights | ❌ Generic scores | **Critical gap** |
| Women's cycle integration | ✅ Full spec | ⚠️ Partial (day only) | **Major gap** |
| Plan generation (Python) | ✅ Full spec | ❌ Missing | **Critical gap** |
| Session lifecycle | ✅ State machine | ❌ Missing | **Critical gap** |
| LLM agents (narrate only) | ✅ Full spec | ❌ Missing | **Critical gap** |
| Objectives system | ✅ Full spec | ❌ Missing | **Critical gap** |
| Race prediction | ✅ Full spec | ❌ Missing | **Critical gap** |
| No workout builder | ✅ Constraint | ❌ APIs exist | **Constraint violated** |
| Versioning (5 fields) | ✅ Full spec | ❌ Missing | **Critical gap** |
| Event catalogue (20+ types) | ✅ Full spec | ❌ Generic events | **Major gap** |
| Coach voice (3 paragraphs) | ✅ Format rules | ❌ Missing | **Critical gap** |

**Conclusion:** Of 21 key vision requirements, the new architecture fully satisfies 0, partially satisfies 2, and misses or violates 19. This is not a viable foundation for the product described in the vision.
