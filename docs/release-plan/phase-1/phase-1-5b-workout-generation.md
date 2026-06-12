# Phase 1 — Workout Generation
## Sub-Phase ID: Phase-1.5b

## Objective
Enable the athlete to see their workout for the day, generated on-demand from the planned session and current twin state. At LOW confidence, targets are expressed as effort descriptions and broad ranges rather than precise numbers. The workout structure is a set of `WorkoutStep` records, each carrying a `physiological_intent`. This is the second major user-facing coaching moment — it must feel purposeful and appropriate to the athlete's data tier.

## Challenge Notes
Early drafts included workout generation but used a JSON blob for the workout structure. The current architecture requires `WorkoutStep` records from day one — this is the foundation for all downstream session analysis. The `GeneratedWorkout` has a two-column target structure (`theoretical_targets` + `adjusted_targets`) that is always both written, even when identical. At this phase, `adjusted_targets` = `theoretical_targets` because no wellness or weather modifiers exist yet.

The architect must be aware of the data tier system. Tier 1-2 (power available) get power-based targets; Tier 3-4 (HR + GPS) get GAP-based targets; Tier 5-6 (no HR) get description-only workouts. The data tier is inferred from `AthletePreferences` during onboarding.

## Capabilities Delivered
- `GET /athletes/{id}/today` — returns `GeneratedWorkout` for today's `PlannedSession`
- `POST /athletes/{id}/sessions/{sid}/generate-workout` — explicit generation trigger
- `WorkoutGenerationAgent` service (async, LLM)
- Workout generation is idempotent for `(planned_session_id, date)`
- `GeneratedWorkout` + `WorkoutStep` creation

## Architectural Contracts Required
- `01-entities/generated-workout.md`
- `01-entities/workout-step.md`
- `01-entities/twin-state.md`
- `01-entities/planned-session.md`
- `00-foundations/data-tiers.md`
- `03-agents/workout-generation-agent.md`
- `04-platform/context-budget-service.md`

## Vision References Required
- `coach/daily-view.md` — what the athlete sees (Today's Workout, Two-Column Target Display)
- `twin/training-zones.md` — how targets are expressed at different confidence levels
- `twin/confidence-and-uncertainty.md` — Tier 3 language tier

## Upstream Dependencies
- Phase-1.3 (Onboarding) — `AthletePreferences` (data tier), `TwinState` (threshold estimates)
- Phase-1.4 (Plan Generation) — `PlannedSession` must exist
- Phase-1.5a (First Coach Message) — shared infrastructure (`ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler`)

## Downstream Enablement
- Phase-1.6 (FIT Import) — athlete executes the workout, uploads FIT file, system compares actual to `GeneratedWorkout`
- Phase-2 (Structured Workouts) — this is already using `WorkoutStep`, so 2c is mainly about richer structure

## Invariants To Preserve
- `WorkoutStep.physiological_intent` is never null — every step has an intent.
- `WorkoutStep.step_order` is unique within `GeneratedWorkout`.
- `GeneratedWorkout` is idempotent for `(planned_session_id, generation_date)`. Calling twice returns the existing workout.
- `theoretical_targets` and `adjusted_targets` always both written, even when identical.
- `pace_sec_per_km` uses GAP values only. Never raw pace.
- `twin_state_id` records which twin version drove generation. If twin recalibrates after generation, the workout is not retroactively updated.
- Target type depends on data tier:
  - Tier 1-2: `target_power_watts` primary, `target_gap_sec_per_km` secondary
  - Tier 3-4: `target_gap_sec_per_km` primary, `target_hr_zone` secondary
  - Tier 5-6: `description` only, numeric targets null
- Recovery modifier defaults to `green`, reason null (modifiers not yet available).

## Non-Goals
- Recovery modifier (wellness) on `adjusted_targets` — deferred to Phase 3
- Weather modifier on `adjusted_targets` — deferred to Phase 3
- Segmentation (PlannedSegment / PhysiologicalSegment) — deferred to Phase 5
- Objectives in workout — deferred to Phase 4

## Exit Gate
- `GET /athletes/{id}/today` returns a `GeneratedWorkout` with linked `WorkoutStep` records, each carrying a non-null `physiological_intent`.
- A threshold session produces `WorkoutStep` records with appropriate states: warmup → low_aerobic → threshold (per rep) → recovery (between reps) → cooldown.
- Targets are expressed in units appropriate to data tier (power for Tier 1-2, GAP for Tier 3-4, description for Tier 5-6).
- Calling generation twice for the same `(planned_session_id, date)` returns the existing `GeneratedWorkout` without calling the LLM again.

## Risks
- **Data tier edge cases**: An athlete says they have a power meter but doesn't. The system must gracefully fall back to lower-tier targets without crashing. Mitigation: validate data tier against actual hardware during FIT ingestion (Phase 2), but for now, trust what the athlete told us.
- **Template vs genuine coaching**: At LOW confidence, targets are broad. The workout must still feel purposeful, not like a fill-in-the-blank template. The prompt engineering challenge is significant.

