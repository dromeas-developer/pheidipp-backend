# Phase 1 — Core Models: Twin, Fitness, Physiology, Coaching & Workouts
## Sub-Phase ID: Phase-1.2c

## Objective
Establish the schema for the athlete's digital twin (fitness, physiology, snapshots), coaching output (messages, generation events), and workout structure. This is the most complex schema sub-phase — it defines how the system tracks the athlete's physiological state over time, how coaching messages are stored, and how workouts are structured. No services or endpoints are built here; this is pure schema and migration.

## Challenge Notes
This sub-phase isolates the twin/coaching/workout cluster so the architect can reason about append-only vs mutable storage, inline snapshot design, and the relationship between `TwinState`, `AthletePhysiology`, and `AthleteFitness` without being overwhelmed by the full schema. The initial design used `TrainingBlock` as a single entity; the Phase 1 plan separates `TrainingGoal` (in 1.2b) from `AthletePhysiology` and `AthleteFitness` (mutable current-state tables), with `TwinState` as an append-only inline snapshot.

## Capabilities Delivered
- Schema for `TwinState` (append-only inline snapshots of fitness/fatigue/thresholds)
- Schema for `AthletePhysiology` (per-dimension Bayesian state, mutable)
- Schema for `AthleteFitness` (Banister scores, mutable)
- Schema for `CoachingMessage` (write-once, append-only)
- Schema for `GenerationEvent` (every LLM call, success or failure)
- Schema for `GeneratedWorkout` (two-column target structure, immutable)
- Schema for `WorkoutStep` (individual steps with physiological intent)
- All constraints, indexes, and enums (`TwinConfidenceLevel`, `TwinTrigger`, `MessageType`, `PhysiologicalIntentState`, etc.)

## Architectural Contracts Required
- `01-entities/twin-state.md`
- `01-entities/athlete-physiology.md`
- `01-entities/athlete-fitness.md`
- `01-entities/coaching-message.md`
- `01-entities/generation-event.md`
- `01-entities/generated-workout.md`
- `01-entities/workout-step.md`
- `00-foundations/terminology.md`
- `00-foundations/confidence-model.md`

## Vision References Required
- `twin/confidence-and-uncertainty.md` — confidence levels and athlete communication
- `twin/load-fatigue.md` — three-dimensional approach rationale
- `coach/daily-view.md` — what the athlete sees on the daily screen

## Upstream Dependencies
- Phase-1.1 (Auth) — `Athlete` must exist before any of these entities can reference it.
- Phase-1.2b (Plan & Sessions) — `GeneratedWorkout` FKs to `PlannedSession`.

## Downstream Enablement
- Phase-1.3 (Onboarding) — bootstraps `AthletePhysiology`, `AthleteFitness`, first `TwinState`
- Phase-1.5 (Coaching Agents) — writes `CoachingMessage`, `GenerationEvent`, `GeneratedWorkout`, `WorkoutStep`
- Phase-1.6 (FIT Import) — updates `AthleteFitness`, creates new `TwinState`, triggers `PostWorkoutAgent`

## Invariants To Preserve
- `TwinState` is append-only — no UPDATE or DELETE. `TwinStateRepository` exposes only `insert`, `get_latest`, `get_history`.
- `TwinState` `training_goal_id`, `model_version`, and `activity_id` are frozen at creation.
- `TwinState.confidence_level` is derived as `min(LT1 HR, LT2 HR)` from `AthletePhysiology`.
- `AthleteFitness`: one per athlete, mutable. `form` must always equal `fitness - fatigue`.
- `AthletePhysiology`: one per athlete, mutable. `max_hr` bootstrapped from `220 - age`.
- `CoachingMessage` is immutable after creation. `first_message` — only one per active goal. `post_workout` — one per `activity_id`.
- `GenerationEvent` is written for every LLM call, success or failure. Records are never modified.
- `GeneratedWorkout` is append-only. `theoretical_targets` and `adjusted_targets` always both written.
- `WorkoutStep.physiological_intent` is never null.

## Non-Goals
- No data is written to any of these tables in this sub-phase.
- Services (load computation, twin recalibration, workout generation) — deferred to later sub-phases.
- `ExecutionObservation`, `RawSensorStream`, `PhysiologicalSegment` — deferred to Phases 4-6.

## Exit Gate
- All migrations run cleanly.
- `TwinState` has no `update()` or `delete()` methods in the ORM.
- `AthleteFitness` enduces `form = fitness - fatigue` at application level.
- `GeneratedWorkout` enuces unique constraint on `(planned_session_id, generation_date)`.
- `WorkoutStep` enuces unique constraint on `(generated_workout_id, step_order)`.

## Risks
- **Schema drift**: The interaction between `TwinState` (append-only snapshots) and `AthleteFitness`/`AthletePhysiology` (mutable current state) is subtle. If the architect inverts the dependency (e.g., storing fitness scores directly on `TwinState` rather than snapshotting them), the system will be harder to audit.
- **Missing enums**: `PhysiologicalIntentState` is the most important enum in the codebase and is used by every agent and computation. If it's wrong, every downstream phase breaks. Mitigation: copy exact values from `terminology.md`.
