# 4c — Objectives System
*Objective + ObjectiveUpdate models, seeding, daily integration*

## Objective

Give every session a visible purpose the athlete can track. Objectives are seeded
from the first message analysis, updated after relevant sessions, and surfaced
pre- and post-workout. An athlete always knows what they are working on and whether
they are moving toward it.

## Scope

`Objective` and `ObjectiveUpdate` models. `ObjectiveSeedingService`.
`ObjectiveUpdateService`. Day-of context filter by `session_types_relevant`.
Post-workout context integration. Weekly review task.

## Non-Goals

- Personalised weather response per objective — not applicable
- Cycle personalisation per objective — deferred to 4f
- Objectives from Phase 5+ segmentation data — deferred to 5c

## Architecture References

- `Objective` and `ObjectiveUpdate` full field specs:
  `architecture/coaching-services.md` → Objectives System
- Seeding rules (max 5 per block, at least one `maintain`, tier-based availability):
  `architecture/coaching-services.md` → Seeding
- Update cadence (post-session and weekly):
  `architecture/coaching-services.md` → Update Cadence
- Day-of integration (filter by `session_types_relevant`):
  `architecture/coaching-services.md` → Day-of Integration
- Vision-level objectives philosophy (strengths surfaced alongside gaps):
  `vision/coach/objectives.md`

## Dependencies

Requires 4a (`ExecutionObservation` — needed to evaluate objectives per session).
Requires 1e (`FirstMessageAgent` — objective seeding triggered after first message).

## Models Introduced

**`Objective`** — per-block coaching objective. Full field spec from arch reference:
`id`, `athlete_id` FK, `training_block_id` FK, `category`
(enum: `aerobic_base`, `threshold_quality`, `pacing_discipline`,
`intensity_distribution`, `structural_tolerance`, `neuromuscular_sharpness`,
`durability`, `zone_compliance`, `recovery_efficiency`),
`title`, `description`, `direction` (enum: `improve`, `maintain`, `address_risk`),
`status` (enum: `active`, `achieved`, `superseded`),
`seeded_by` (enum: `first_message_agent`, `post_workout_agent`, `plan_regeneration`),
`session_types_relevant` (JSONB), `last_updated_at`, `achieved_at`.

**`ObjectiveUpdate`** — append-only assessment log.
`objective_id` FK, `activity_id` FK (nullable), `direction_of_change`
(enum: `improving`, `regressing`, `stable`, `achieved`),
`evidence` (str — backend-computed, not LLM), `coach_note` (nullable str),
`created_at`.

## Services & Tasks Introduced

**`ObjectiveSeedingService`** (sync, Python + LLM for descriptions only).
- `seed(athlete_id) → list[Objective]`
  Triggered after first message is generated.
  Reads TwinState, any imported Activity records (Tier 1) or questionnaire data (Tier 3).
  Selects 3-5 categories, always including at least one `direction = maintain`.
  Creates `Objective` records with `seeded_by = first_message_agent`.
  Objective `title` and `description` are short LLM-generated strings (< 50 tokens
  each) — the category selection and direction are Python-determined, not LLM-determined.

**`ObjectiveUpdateService`** (sync, Python).
- `evaluate_post_session(athlete_id, activity_id) → list[ObjectiveUpdate]`
  For each active objective where `session_types_relevant` intersects the completed
  session type: reads `ExecutionObservation.coaching_observations`, computes
  `direction_of_change` and `evidence` string. Creates `ObjectiveUpdate` records.
  Flags milestone events (first `achieved`) for the post-workout agent.
- `weekly_review(athlete_id) → list[ObjectiveUpdate]`
  For objectives not updated by a post-session evaluation in the past 7 days:
  creates `stable` or trend-based updates from the week's execution observations.

**`ObjectiveWeeklyReviewTask`** (async worker — scheduled weekly).
Runs `ObjectiveUpdateService.weekly_review()` for all athletes with active objectives.

## Services Modified

**`ContextBudgetService`** (updated) — two new context builders:
- `build_workout_context()` updated: includes active objectives filtered by
  `session_types_relevant` for today's session type. Maximum 2 objectives to
  stay within budget.
- `build_post_workout_context()` updated: includes most recent `ObjectiveUpdate`
  for each relevant active objective. `ObjectiveUpdateService.evaluate_post_session()`
  is called before the agent runs — agent receives pre-computed updates.

**`PostWorkoutAgent`** (updated) — third paragraph now addresses objective progress
using pre-computed `ObjectiveUpdate` records. If a milestone (`achieved`) is flagged,
the agent explicitly acknowledges it before moving to the next challenge.

## Key Constraints

- Objective `direction_of_change` and `evidence` are Python-computed — never
  LLM-derived. The LLM only writes the `coach_note` that narrates the pre-computed finding.
- At least one `maintain` objective is always seeded. Surfacing strengths is an invariant.
  See `vision/coach/objectives.md`.
- Maximum 5 active objectives per athlete per block. New objectives supersede old ones
  — they don't stack indefinitely.
- `ObjectiveUpdateService` runs before `PostWorkoutAgent` — the agent receives
  complete, current objective state, not stale state.

## Done Criteria

- After first message generation, `GET /athletes/{id}/objectives` returns 3-5
  active objectives including at least one with `direction = maintain`.
- After a threshold session, relevant objectives show a new `ObjectiveUpdate` with
  non-null `direction_of_change` and `evidence`.
- `GET /athletes/{id}/today` includes the 1-2 objectives relevant to today's
  session type.
- Post-workout message third paragraph references specific objective movement
  derived from the `ExecutionObservation` findings.
- When an objective is first marked `achieved`, the post-workout message explicitly
  acknowledges it.
