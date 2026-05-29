# 1d — Plan Generation
*Pure-Python periodised training plan from twin state*

## Objective

Generate a coherent multi-phase training plan from the active `TrainingBlock` and
`TwinState`. This is a pure Python service — no LLM. The plan skeleton gives the
coaching agents in 1e the phase context they need to generate meaningful messages
and workouts.

## Scope

`PlanGenerationService` — phase arc computation, session distribution, `TrainingPlan`
and `PlannedSession` creation. Plan retrieval endpoints. Plan regeneration on goal
date change.

## Non-Goals

- Day-of workout generation (targets are not generated here — only intent)
- Session lifecycle management (skip, miss, redistribute) — deferred to 4d
- Workout library — deferred to 4d
- Plan regeneration on twin confidence upgrade — deferred to 2c
  (twin confidence upgrades don't happen until real data flows in Phase 2)

## Architecture References

- Plan generation service, phase arc formula, session distribution rules:
  `architecture/planning-and-sessions.md` → Plan Generation Service
- Session distribution structural rules (long run → rest; threshold sandwiched):
  `architecture/planning-and-sessions.md` → Session Distribution
- Crossover athlete structural ramp: `architecture/planning-and-sessions.md`
  → Crossover Athlete Structural Capacity Ramp
- Phase label enum values and `TrainingPlan.phases` JSONB structure:
  `architecture/data-models.md` → Planning Layer
- Vision-level plan visibility rules: `vision/coach/plan-visibility.md`

## Dependencies

Requires 1a (TrainingPlan, PlannedSession models), 1b (auth), 1c (onboarding —
TwinState and TrainingBlock must exist before a plan can be generated).

## Models Modified

No new models. `TrainingPlan` and `PlannedSession` defined in 1a are first populated here.

## Services & Tasks Introduced

**`PlanGenerationService`** (sync, Python only — no LLM).
- `generate(athlete_id) → TrainingPlan` — reads active TrainingBlock + current
  TwinState, computes phase arc, creates TrainingPlan and all PlannedSession records.
  If a TrainingPlan already exists for this block, marks it `superseded` before creating
  the new one.
- `regenerate(athlete_id, reason) → TrainingPlan` — same as generate; used when
  goal date changes or twin confidence upgrade triggers a replanning event.

Phase arc computation follows the formula in `architecture/planning-and-sessions.md`.
Session distribution enforces the structural rules (long run followed by rest,
threshold sandwiched between easy days) which simultaneously serve coaching quality
and adaptation data collection.

## Endpoints Introduced

- `GET /athletes/{athlete_id}/plan` — returns active TrainingPlan with phases array.
  Phase arc varies by goal_type: race_event uses periodised structure; fitness_improvement uses progressive development; maintenance uses consistency-focused rolling blocks; recovery uses conservative progression. Protected by `require_self`.
- `GET /athletes/{athlete_id}/plan/sessions` — returns all PlannedSession records
  for the active plan, orderable by `target_date`. Protected by `require_self`.
- `GET /athletes/{athlete_id}/plan/upcoming` — returns the next 5 PlannedSession
  records from today, with `status = pending` or `generated`.
  Protected by `require_self`.
- `PATCH /athletes/{athlete_id}/plan/block` — update `goal_event_date` or
  `goal_description` on the active TrainingBlock; triggers plan regeneration if
  `goal_event_date` changes by more than 7 days. Protected by `require_self`.

## Key Constraints

- `PlanGenerationService` is pure Python — no LLM, no external API calls.
- The service must not create a plan if no active TrainingBlock exists.
- The service must not create a plan if no TwinState exists for the athlete.
- `PlannedSession` records are created for the full plan duration, not just the
  next few weeks. Future sessions have `status = pending`.
- Superseded TrainingPlan records are never deleted — `superseded_at` is set.
- Structural rules are invariant: no two quality sessions on consecutive days,
  long run always followed by rest or recovery, threshold always sandwiched.

## Done Criteria

- After onboarding, calling the plan endpoint returns a TrainingPlan with the
  correct phase sequence for the goal_type (race_event: periodised; fitness_improvement: progressive development; maintenance: consistency rolling; recovery: conservative progression).
- Phases have the correct proportional duration (40% base / 30% threshold /
  15% race-specific / 2 weeks taper / 1 week race-week for race_event goals).
  Fitness improvement uses threshold-emphasis progression; maintenance uses 4-week rolling;
  recovery uses injury-severity-based conservative phases.
- `PlannedSession` records cover the full duration to the goal event with no gaps.
- No two consecutive quality sessions appear in the generated schedule.
- Changing `goal_event_date` by more than 7 days via PATCH creates a new TrainingPlan
  and marks the previous one `superseded`.
