# Phase 1 — Core Models: Plan & Sessions
## Sub-Phase ID: Phase-1.2b

## Objective
Establish the schema for the training plan hierarchy: from the athlete's goal, through the strategic plan and weekly breakdown, to individual planned sessions and scheduled checkpoints. This is a purely schema sub-phase — no services or endpoints are built here. The plan generation logic (1.4) will populate these tables, and the coaching agents (1.5) will query them.

## Challenge Notes
The plan generation service and the `TrainingPlan`/`PlannedSession` schema were initially treated as a single feature. This sub-phase separates the schema from the generation logic so the architect can reason about each independently. The `TrainingBlock` entity from early drafts has been replaced by `TrainingGoal` with a richer set of fields and support for multiple goal types. The `WeeklyPlan` / `WeeklySession` hierarchy is new in the current architecture — it implements the "weekly coaching rhythm" from the vision.

## Capabilities Delivered
- Schema for `TrainingGoal` (goal definition, immutable after creation)
- Schema for `TrainingPlan` (phase arc, checkpoint schedule)
- Schema for `WeeklyPlan` (weekly session list, immutable once active)
- Schema for `WeeklySession` (links `WeeklyPlan` to `PlannedSession`)
- Schema for `PlannedSession` (individual session with intent, checkpoint flags)
- Schema for `Checkpoint` (calibration, benchmark, race_simulation, secondary_race, progress_review)
- All constraints, indexes, and enums (`GoalType`, `PhaseLabel`, `SessionType`, `CheckpointType`, etc.)

## Architectural Contracts Required
- `01-entities/training-goal.md`
- `01-entities/training-plan.md`
- `01-entities/weekly-plan.md`
- `01-entities/planned-session.md`
- `01-entities/checkpoint.md`
- `00-foundations/terminology.md`

## Vision References Required
- `product/plan-generation.md` — strategic roadmap concept
- `product/training-plan-checkpoints.md` — checkpoint hierarchy and scheduling
- `coach/plan-visibility.md` — what the athlete sees

## Upstream Dependencies
- Phase-1.1 (Auth) — `Athlete` must exist before `TrainingGoal` can reference it.
- Phase-1.2a (Profile & Preferences) — `AthletePreferences.weekly_schedule` contains the `long_workout` day used by plan generation.

## Downstream Enablement
- Phase-1.3 (Onboarding) — creates the `TrainingGoal`
- Phase-1.4 (Plan Generation) — populates `TrainingPlan`, `WeeklyPlan`, `PlannedSession`, `Checkpoint`
- Phase-1.5b (Workout Generation) — queries `PlannedSession` for `GeneratedWorkout`
- Phase-1.6 (FIT Import) — `Activity.planned_session_id` FK links to `PlannedSession`

## Invariants To Preserve
- `TrainingGoal`: one active per athlete (partial unique index on `athlete_id WHERE status = 'active'`).
- `TrainingGoal` fields `goal_type`, `goal_event_type`, `fitness_level`, etc. are immutable after creation.
- `TrainingPlan` is never deleted — `superseded_at` is set when replaced.
- `WeeklyPlan`: one per `(training_plan_id, week_number)`. Sessions array is immutable once `status = active`.
- `PlannedSession` records for a superseded `TrainingPlan` retain the old `training_plan_id` — queries for "current plan sessions" must join through `WeeklyPlan`.
- `Checkpoint` cannot be created retroactively — scheduled during plan synthesis.
- `Checkpoint` completion fields (`metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`) are set atomically.

## Non-Goals
- Plan generation logic — deferred to 1.4
- Session lifecycle (skip, miss, reschedule) — deferred to Phase 4
- Workout library — deferred to Phase 4
- Plan regeneration on confidence upgrade — deferred to Phase 2

## Exit Gate
- All migrations run cleanly.
- `TrainingGoal` enforces single active goal per athlete at DB level.
- `WeeklyPlan` enforces one per `(training_plan_id, week_number)`.
- `Checkpoint` enforces `planned_session_id` as one-to-one with `PlannedSession`.

## Risks
- **Checkpoint-PlannedSession circular reference**: `Checkpoint` references `PlannedSession`, and `PlannedSession` has `checkpoint_type`/`checkpoint_metric` fields. The architect must decide whether `Checkpoint` is created first or atomically with the `PlannedSession`. Recommended approach: atomic creation in the plan generation service.
- **Plan supersession cascade**: When a plan is superseded, `PlannedSession` records retain the old `training_plan_id`. If 1.2b misses the denormalisation warning, queries may return stale sessions. Mitigation: document the correct query pattern in the schema.
