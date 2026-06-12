# Phase 1 — Plan Generation
## Sub-Phase ID: Phase-1.4

## Objective
Generate a complete training plan from the bootstrapped twin and defined goal. This is a pure Python service — no LLM, no external API calls. The plan skeleton gives the coaching agents in 1.5 the phase context they need to generate meaningful messages and workouts. For Phase 1, only `race_event` and `target_performance` goal types are supported.

## Challenge Notes
Early drafts only created `TrainingPlan` and `PlannedSession`. The current architecture adds `WeeklyPlan` and `WeeklySession` to implement the "weekly coaching rhythm" from the vision. This means 1.4 creates the full hierarchy: TrainingPlan → WeeklyPlan → WeeklySession → PlannedSession, plus Checkpoints. The architect must be aware of the `PlannedSession.training_plan_id` denormalisation caveat — the authoritative plan reference is always through `WeeklyPlan`.

## Capabilities Delivered
- `TrainingPlan` with phase arc appropriate to `goal_type`
- `WeeklyPlan` + `WeeklySession` for all weeks
- `PlannedSession` records (with checkpoint flags) for all sessions
- `Checkpoint` records (calibration, benchmark, progress_review)
- `GET /athletes/{id}/plan` — returns plan with phases
- `GET /athletes/{id}/plan/sessions` — all sessions
- `GET /athletes/{id}/plan/upcoming` — next 5 sessions
- `GET /athletes/{id}/plan/checkpoints` — all checkpoints

## Architectural Contracts Required
- `01-entities/training-goal.md`
- `01-entities/training-plan.md`
- `01-entities/weekly-plan.md`
- `01-entities/planned-session.md`
- `01-entities/checkpoint.md`
- `01-entities/twin-state.md`
- `02-computations/plan-generation.md`
- `02-computations/plan-generation-race.md`
- `02-computations/plan-generation-target-performance.md`

## Vision References Required
- `product/plan-generation.md` — strategic roadmap concept
- `product/training-plan-checkpoints.md` — checkpoint hierarchy
- `coach/plan-visibility.md` — what the athlete sees
- `weekly-coaching-rhythm.md` — the weekly adjustment layer

## Upstream Dependencies
- Phase-1.3 (Onboarding) — `TrainingGoal` and `TwinState` must exist
- Phase-1.2b (Plan & Sessions) — schema must exist

## Downstream Enablement
- Phase-1.5a (First Coach Message) — references plan phases
- Phase-1.5b (Workout Generation) — generates workout for `PlannedSession`
- Phase-1.6 (FIT Import) — `Activity` links to `PlannedSession`

## Invariants To Preserve
- `PlanGenerationService` is pure Python — no LLM, no external API calls.
- Phases have correct proportional duration (race_event example: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week).
- `PlannedSession` records cover the full duration to the goal event with no gaps.
- No two consecutive quality sessions appear in generated schedule.
- Structural rules are invariant: long run always followed by rest or recovery, threshold always sandwiched between easy days.
- Superseded `TrainingPlan` records are never deleted — `superseded_at` is set.
- `Checkpoint` cannot be created retroactively — scheduled during plan synthesis, not after session completion.
- `PlannedSession` records for a superseded `TrainingPlan` retain the old `training_plan_id` — queries for "current plan sessions" must join through `WeeklyPlan`.
- `WeeklyPlan` sessions array is immutable once `status = active`.

## Non-Goals
- `fitness_improvement`, `maintenance`, `recovery` goal types — deferred
- Plan regeneration on confidence upgrade — deferred to Phase 2
- Session lifecycle management (skip, miss, redistribute) — deferred to Phase 4
- Workout library — deferred to Phase 4
- Plan regeneration on goal date change > 7 days — keep minimal, just re-generate

## Exit Gate
- After onboarding, `GET /athletes/{id}/plan` returns a `TrainingPlan` with correct phase sequence for the `goal_type`.
- Phases have correct proportional durations.
- `PlannedSession` records cover the full duration to the goal event with no gaps.
- No two consecutive quality sessions appear in the generated schedule.
- `GET /athletes/{id}/plan/checkpoints` returns scheduled checkpoints.

## Risks
- **Mental model shift**: The architect may expect to generate only `TrainingPlan` + `PlannedSession`. The `WeeklyPlan` / `WeeklySession` hierarchy adds complexity but is required for the weekly rhythm. Must be clear in handoff.
- **Checkpoint complexity**: Checkpoints are scheduled based on confidence gaps, race calendar, phase transitions, and regular intervals. The scheduling logic is non-trivial.

