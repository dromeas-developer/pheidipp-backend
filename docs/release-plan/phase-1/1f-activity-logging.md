# 1f — Activity Logging & Post-Workout Analysis
*Manual session logging and the first post-workout coaching message*

## Objective

Close the Phase 1 coaching loop. The athlete logs a session manually (no FIT file
yet) and receives a post-workout analysis that references the planned session,
assesses compliance, and coaches specifically on what was done. This is the second
magic moment of the product — it must feel like the coach actually read the data,
not like it filled in a template.

## Scope

Manual activity creation endpoint. Compliance computation (Python). Post-workout
analysis agent. `PostWorkoutAnalysis` creation. Session status update on completion.

## Non-Goals

- FIT file upload or ingestion — deferred to 2a
- Load score computation (`aerobic_load`, `neuromuscular_load`, `structural_load`) —
  deferred to 2b (requires FIT data)
- Calibration eligibility — deferred to 2b
- Twin recalibration from activity data — deferred to 2b
- Comparable session identification — deferred to 4b (no history exists yet)
- Objectives in post-workout message — deferred to 4c
- ExecutionObservation model — deferred to 4a (requires real FIT data)

## Architecture References

- Post-workout agent context window target (~3k–6k tokens):
  `architecture/llm-and-agents.md` → Context Window Targets by Agent
- Post-workout message format (three paragraphs): `vision/coach/voice-and-format.md`
- Post-workout analysis content rules: `vision/coach/post-workout.md`
- `Activity` model field spec (manual_entry source):
  `architecture/data-models.md` → Ingestion Layer

## Dependencies

Requires 1a (Activity, PostWorkoutAnalysis, CoachingMessage, GenerationEvent models),
1b (auth), 1c (TwinState — needed for post-workout context), 1d (PlannedSession —
needed for compliance computation), 1e (agents foundation, PromptRegistry,
ContextBudgetService, GenerationEvent logging pattern).

## Models Modified

**`PlannedSession`** — `status` updated to `completed` and `activity_id` FK set
when a manual Activity is linked to it. No new fields (defined in 1a).

## Services & Tasks Introduced

**`ActivityService`** (sync) — creates manual Activity records.
- `create_manual(athlete_id, data) → Activity`
  - Sets `source = manual_entry`
  - `fit_file_key = null`
  - `calibration_eligible = false`
  - `aerobic_load`, `neuromuscular_load`, `structural_load` = null
  - `has_hr`, `has_rr_intervals`, `has_power` set from submitted data
  - If `planned_session_id` provided, links to PlannedSession and transitions
    its status to `completed`
- `get(activity_id) → Activity`
- `list_by_athlete(athlete_id, params) → list[Activity]`

**`ComplianceService`** (sync, Python) — computes session compliance relative to plan.
- `compute(activity, planned_session, generated_workout) → dict`
- Outputs: `duration_delta_pct`, `effort_delta` (if RPE captured),
  `session_type_match` (bool), `notes_summary`.
- This is Python computation — not LLM-derived.

**`PostWorkoutAgent`** (async) — generates the post-workout coach message.
- `generate(athlete_id, activity_id) → CoachingMessage`
- Context assembled by `ContextBudgetService.build_post_workout_context()`:
  - Prescribed session summary (session_type, intent, approximate duration)
  - Pre-computed compliance summary from `ComplianceService`
  - Manual execution data (duration, effort, pace, HR if provided, notes)
  - Phase label and week number in plan
  - TwinState readiness summary
  - Note: no comparable session in Phase 1 (none exist yet)
- Enforces 3k–6k token budget
- Writes `GenerationEvent`, then `CoachingMessage` with `message_type = post_workout`
- Writes `PostWorkoutAnalysis` linking activity, coaching message, compliance summary

## Endpoints Introduced

- `POST /athletes/{athlete_id}/activities` — create manual activity. If
  `planned_session_id` provided, links and transitions PlannedSession to `completed`.
  Protected by `require_self`.
- `POST /athletes/{athlete_id}/activities/{activity_id}/analyse` — trigger
  post-workout analysis. Returns `CoachingMessage`. Protected by `require_self`.
  Idempotent — returns existing analysis if one already exists for this activity.
- `GET /athletes/{athlete_id}/activities` — paginated activity list.
  Protected by `require_self`.
- `GET /athletes/{athlete_id}/activities/{activity_id}` — single activity.
  Protected by `require_self`.
- `GET /athletes/{athlete_id}/activities/{activity_id}/analysis` — returns
  PostWorkoutAnalysis + linked CoachingMessage. Protected by `require_self`.

## Key Constraints

- Manual activities always have `calibration_eligible = false` — they never trigger
  twin recalibration.
- `fit_file_key` is always null for `source = manual_entry`. This is not an error
  condition for manual entries.
- Post-workout analysis is idempotent — calling the endpoint twice returns the same
  CoachingMessage without calling the LLM again.
- `PostWorkoutAnalysis` is linked one-to-one with `Activity`. A second analysis
  cannot be created for the same activity.
- The post-workout message must be three natural paragraphs. No headers, no bullets,
  no emojis. Voice quality is evaluated against the criteria in
  `vision/coach/voice-and-format.md`.

## Done Criteria

- `POST /athletes/{athlete_id}/activities` creates an Activity with `source = manual_entry`
  and, when `planned_session_id` is provided, transitions the PlannedSession to
  `status = completed`.
- `POST /athletes/{athlete_id}/activities/{activity_id}/analyse` returns a three-paragraph
  coach message that references the planned session type, notes whether the athlete
  completed it as planned, and coaches on at least one specific aspect of the execution.
- Calling the analyse endpoint twice returns the same message — no second LLM call.
- An activity with no `planned_session_id` (unplanned session) also produces a valid
  post-workout analysis without errors.
