# Pheidipp — Release Plan Index
*Authoritative build sequence. Last updated May 2026.*

This index is the entry point for the release plan. Each sub-phase document is
self-contained and is the primary input to the synthesizer agent alongside the
architecture index and stack truth.

**This document set contains no architectural definitions and no vision decisions.**
For engineering constraints, see `architecture-index.md`.
For product behaviour and coach voice, see `vision-index.md`.

When this release plan conflicts with the architecture on technical design,
the architecture is authoritative. When the architecture conflicts on sequencing
or scope, this release plan is authoritative.

---

## How to Read This Index

Each sub-phase entry states: what the key deliverable is, what twin layer
activates, and which architecture documents the synthesizer must load.
The synthesizer reads the sub-phase document plus the listed arch references
to produce the operational brief.

---

## Phase 1 — Skeleton MVP
*The full coaching loop with no real data. Tier 3 bootstrap throughout.*
→ `phase-1/index.md`

| Sub-phase | Deliverable | Arch refs to load |
|---|---|---|
| **1a** Core Domain Models | Full DB schema — all domain models built right first time | `data-models.md`, `planning-and-sessions.md`, `twin-state.md`, `llm-and-agents.md` |
| **1b** Authentication | JWT lifecycle, refresh tokens, route protection | `principles.md`, `data-models.md` |
| **1c** Onboarding API | Atomic transaction → TwinState bootstrap | `twin-state.md`, `planning-and-sessions.md`, `load-and-thresholds.md` |
| **1d** Plan Generation | Pure-Python periodised plan from TwinState | `planning-and-sessions.md` |
| **1e** Coaching Agents Foundation | First message + day-of workout agents, PromptRegistry | `llm-and-agents.md`, `twin-state.md` |
| **1f** Activity Logging & Post-Workout | Manual logging, ComplianceService, PostWorkoutAgent | `llm-and-agents.md`, `data-models.md` |

---

## Phase 2 — Real Data
*FIT ingestion, load computation, structured workouts, threshold detection.*
*Layer 1 + Layer 2 real data. MEDIUM/HIGH confidence.*
→ `phase-2/index.md`

| Sub-phase | Deliverable | Arch refs to load |
|---|---|---|
| **2a** FIT Ingestion | intervals.icu, async pipeline, object storage, `fit_file_key` | `principles.md`, `data-models.md`, `versioning.md` |
| **2b** Load Computation & Twin L1 | Three load scores, calibration eligibility, Banister update | `load-and-thresholds.md`, `twin-state.md`, `versioning.md` |
| **2c** Structured Workout Generation | `PhysiologicalIntentState`, `WorkoutStep`, two-column targets | `shared-language.md`, `data-models.md`, `twin-state.md` |
| **2d** Threshold Detection & Twin L2 | HR deflection, RR inflection, Bayesian update, MEDIUM/HIGH | `load-and-thresholds.md`, `twin-state.md` |

---

## Phase 3 — Environmental Context
*Wellness, weather, menstrual cycle, recovery modifier.*
*Layer 4 active.*
→ `phase-3/index.md`

| Sub-phase | Deliverable | Arch refs to load |
|---|---|---|
| **3a** Wellness Ingestion | `AthleteWellness` model, passive wearable data | `wellness-and-modifiers.md` |
| **3b** Recovery Modifier | Baseline, trend detection, GREEN/AMBER/RED, adjusted targets | `wellness-and-modifiers.md`, `twin-state.md` |
| **3c** Menstrual Cycle | `CyclePhaseLog`, phase computation, modifier stacking | `wellness-and-modifiers.md` |
| **3d** Weather Integration | `WeatherForecast`, heat/wind formulas, luteal stacking | `wellness-and-modifiers.md`, `effort-normalisation.md` |

---

## Phase 4 — Coaching Intelligence
*Execution analysis, objectives, lifecycle, comparable sessions, race prediction.*
*Layer 5 beginning.*
→ `phase-4/index.md`

| Sub-phase | Deliverable | Arch refs to load |
|---|---|---|
| **4a** ExecutionObservation | FIT-derived analysis, session shape, `analysis_version` | `data-models.md`, `llm-and-agents.md`, `segmentation-pipeline.md` |
| **4b** Comparable Sessions | `ComparableSessionService`, historical references in messages | `coaching-services.md` |
| **4c** Objectives System | `Objective`, `ObjectiveUpdate`, seeding, daily integration | `coaching-services.md`, `llm-and-agents.md` |
| **4d** Session Lifecycle | Skip/miss/redistribute, `WorkoutLibraryEntry`, substitution | `planning-and-sessions.md` |
| **4e** Proactive Messages | Wellness alerts, phase transitions, plan notifications | `llm-and-agents.md`, `wellness-and-modifiers.md` |
| **4f** Cycle Personalisation | Individual cycle length, per-athlete phase adjustments | `wellness-and-modifiers.md` |
| **4g** Race Prediction | `RacePrediction`, baseline formula, course + weather adjustment | `coaching-services.md`, `effort-normalisation.md` |

---

## Phase 5 — Signal Processing
*Cleaning pipeline, heuristic segmentation, rep-level analysis, per-athlete GAP.*
*Layer 5 active with Gen 1 segmentation.*
→ `phase-5/index.md`

| Sub-phase | Deliverable | Arch refs to load |
|---|---|---|
| **5a** Cleaning Pipeline | 7-step preprocessing, `RawSensorStream`, `cleaning_pipeline_version` | `segmentation-pipeline.md`, `versioning.md`, `data-models.md` |
| **5b** Gen 1 Segmentation | `PlannedSegment`, `DeviceSegment`, `PhysiologicalSegment` heuristic | `segmentation-pipeline.md`, `shared-language.md`, `data-models.md` |
| **5c** Rep-Level Analysis | `ExecutionObservation` upgraded from lap to segment data | `segmentation-pipeline.md`, `coaching-services.md` |
| **5d** Per-Athlete GAP | Individual grade response curve, Gen 2 normalisation | `effort-normalisation.md`, `versioning.md` |

---

## Phase 6 — Advanced Twin
*HMM, adaptation, 3D load, individual time constants, Gen 3 effort model.*
*All five layers active.*
→ `phase-6/index.md`

| Sub-phase | Deliverable | Arch refs to load |
|---|---|---|
| **6a** HMM Segmentation | Gen 3 pipeline, population HMM, `state_probabilities` | `segmentation-pipeline.md`, `versioning.md` |
| **6b** Personalised Weather | Individual heat sensitivity curves, updated prediction | `effort-normalisation.md`, `wellness-and-modifiers.md` |
| **6c** 3D Load & Adaptation | `AdaptationObservation`, Layer 3, 3D `TwinState` fields | `twin-state.md`, `data-models.md`, `coaching-services.md` |
| **6d** Individual Time Constants | Per-athlete Banister constants, full Layer 1 | `twin-state.md` |
| **6e** Gen 3 Effort Model | Personalised physiological cost model, full terrain | `effort-normalisation.md` |

---

## Phase Gate Summary

| Gate | Criteria |
|---|---|
| Phase 1 → 2 | Coach messages pass voice quality review; onboarding is atomic; all routes require JWT |
| Phase 2 → 3 | Every Activity has `fit_file_key`; ingestion runs without manual intervention; no duplicate activities; TwinState history auditable |
| Phase 3 → 4 | Recovery modifier is deterministic; weather failures degrade gracefully; cycle tracking activates only for female athletes who opt in |
| Phase 4 → 5 | `ExecutionObservation` created for every calibration-eligible activity; comparable session null-handled gracefully; session lifecycle has no orphan records |
| Phase 5 → 6 | `RawSensorStream` exists for all new sessions; Gen 1 segments flag low-confidence correctly; per-athlete GAP falls back to population formula cleanly |

---

## Complete Model Inventory by Phase

| Model | Introduced | Phase |
|---|---|---|
| `Athlete` | 1a | Core |
| `AthleteProfile` | 1a | Core |
| `AthletePreferences` | 1a | Core |
| `TrainingBlock` | 1a | Core |
| `TrainingPlan` | 1a | Core |
| `PlannedSession` | 1a | Core |
| `TwinState` | 1a | Core |
| `CoachingMessage` | 1a | Core |
| `GenerationEvent` | 1a | Core |
| `GeneratedWorkout` | 1a | Core |
| `Activity` | 1a | Core |
| `PostWorkoutAnalysis` | 1a | Core |
| `RefreshToken` | 1b | Auth |
| `WorkoutStep` | 2c | Real data |
| `AthleteIntegration` | 2a | Real data |
| `AthleteWellness` | 3a | Environment |
| `AthleteWellnessBaseline` | 3b | Environment |
| `CyclePhaseLog` | 3c | Environment |
| `WeatherForecast` | 3d | Environment |
| `ExecutionObservation` | 4a | Intelligence |
| `Objective` | 4c | Intelligence |
| `ObjectiveUpdate` | 4c | Intelligence |
| `WorkoutLibraryEntry` | 4d | Intelligence |
| `RacePrediction` | 4g | Intelligence |
| `RawSensorStream` | 5a | Signal processing |
| `PlannedSegment` | 5b | Signal processing |
| `DeviceSegment` | 5b | Signal processing |
| `PhysiologicalSegment` | 5b | Signal processing |
| `AdaptationObservation` | 6c | Advanced twin |
