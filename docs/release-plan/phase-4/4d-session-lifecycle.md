# 4d — Session Lifecycle
*Skip, miss, redistribute, WorkoutLibrary, substitution flow*

## Objective

Handle the reality that training plans meet real life. An athlete skips sessions,
gets ill, has time pressure. The system must respond intelligently — rescheduling
load where appropriate, adjusting the plan where not, and maintaining twin model
integrity throughout. The coaching never treats a missed session as a failure.

## Scope

`WorkoutLibraryEntry` model. `SessionLifecycleService`. Skip/redistribute flow.
`SkipConversationAgent`. Illness and injury handling. Missed session nightly sweep.
`MissedSessionService`.

## Non-Goals

- Free Coach Chat — deferred to post-Phase 6
- Group plan management — deferred to post-Phase 6
- Personalised cycle phase adaptation of the library query — deferred to 4f

## Architecture References

- Session lifecycle state machine and all status transitions:
  `architecture/planning-and-sessions.md` → Session Lifecycle
- Skip and redistribution flow (5 steps):
  `architecture/planning-and-sessions.md` → Skip and Redistribution Flow
- Illness and injury handling:
  `architecture/planning-and-sessions.md` → Illness and Injury Handling
- `WorkoutLibraryEntry` model and substitution query logic:
  `architecture/planning-and-sessions.md` → Workout Library
- Vision-level substitution flow design:
  `vision/coach/substitution.md`

## Dependencies

Requires 1d (`PlannedSession` status machine exists from 1a/1d).
Requires 1e (`ContextBudgetService`, `PromptRegistry`, `GenerationEvent` logging).
Requires 2c (`WorkoutStep` — library entries embed same step structure).

## Models Introduced

**`WorkoutLibraryEntry`** — curated substitution template. Full field spec from
arch reference: `id`, `session_type`, `approximate_duration_minutes`,
`data_tier_minimum`, `phase_labels` (JSONB), `steps` (JSONB — same structure
as WorkoutStep but embedded, not FK-linked), `intent_description`,
`times_offered`, `times_accepted`, `acceptance_rate` (computed),
`created_at`, `created_by` (enum: `seed`, `generated`).

Initial seed data: a curated set of library entries covering all `session_type`
values, written as a data migration. Minimum 3 entries per session type.

## Services & Tasks Introduced

**`SessionLifecycleService`** (sync) — manages `PlannedSession` status transitions.
- `skip(session_id, reason_text) → PlannedSession`
  Sets `status = skipped`, `skip_reason = reason_text`.
  Enqueues `SkipConversationTask`.
- `complete(session_id, activity_id) → PlannedSession`
  Sets `status = completed`, `activity_id`.
- `redistribute(session_id, target_date) → PlannedSession`
  Sets original to `status = redistributed`, `redistributed_to_date = target_date`.
  Creates a new `PlannedSession` for the target date with same type and intent.
  Validates the target date does not violate structural rules (no consecutive
  quality sessions).
- `find_redistribution_window(athlete_id, session_type, from_date) → date | None`
  Finds the nearest eligible available day within 5 days that does not violate
  structural rules.

**`WorkoutLibraryService`** (sync, Python).
- `find_substitutes(planned_session, athlete, reason) → list[WorkoutLibraryEntry]`
  Implements the substitution query from arch reference: session_type match,
  duration ±20%, data tier filter, phase_labels filter.
  Returns up to 3 candidates ordered by `acceptance_rate` desc.
- `record_acceptance(entry_id) → None` — increments `times_accepted`.
- `record_offer(entry_id) → None` — increments `times_offered`.

**`SkipConversationAgent`** (async, lightweight LLM — ~1k token context).
- `classify(athlete_id, session_id, reason_text) → SkipClassification`
  Classifies the skip reason into:
  `fatigue`, `time_constraint`, `injury_concern`, `motivation`, `illness`,
  `external_constraint`.
  Based on classification:
  - `fatigue` / `illness`: no redistribution offered; plan adjusts forward.
    For illness: triggers illness handling in `PlanGenerationService`.
  - `time_constraint` / `motivation` / `external_constraint`: calls
    `SessionLifecycleService.find_redistribution_window()`; offers substitutes
    from `WorkoutLibraryService`.
  - `injury_concern`: escalates to injury flow; calls `PlanGenerationService`
    with injury flag.

**`MissedSessionService`** (sync, Python).
- `sweep(date) → int` — transitions all `PlannedSession` records where
  `status = generated` and `target_date < date` (yesterday or earlier) to
  `status = missed`. Returns count of records transitioned.

**`MissedSessionSweepTask`** (async worker — scheduled nightly).
Runs `MissedSessionService.sweep(today)`.
Creates a `CoachingMessage` with `message_type = wellness_alert` for each
athlete with newly missed sessions, prompting how to proceed.

## Endpoints Introduced

- `POST /athletes/{athlete_id}/sessions/{session_id}/skip` — athlete signals skip.
  Accepts optional `reason` field. Triggers `SkipConversationAgent`.
  Protected by `require_self`.
- `POST /athletes/{athlete_id}/sessions/{session_id}/redistribute` — move session
  to a different date. Accepts `target_date`. Protected by `require_self`.
- `GET /athletes/{athlete_id}/sessions/{session_id}/substitutes` — returns up to
  3 `WorkoutLibraryEntry` substitutes. Protected by `require_self`.
- `POST /athletes/{athlete_id}/sessions/{session_id}/accept-substitute` — athlete
  accepts a library entry as today's session. Creates `GeneratedWorkout` from the
  library entry's steps. Protected by `require_self`.

## Key Constraints

- Redistribution validates structural rules — the `find_redistribution_window()`
  method must refuse dates that create consecutive quality sessions.
- `MissedSessionSweepTask` only transitions `generated` sessions — never `pending`
  ones (sessions not yet due).
- Library entries with `created_by = generated` are only promoted when
  `times_accepted ≥ 3` and `acceptance_rate ≥ 0.6`. This is enforced by a nightly
  promotion task, not immediately.
- `SkipConversationAgent` writes a `GenerationEvent`. All LLM calls are logged.

## Done Criteria

- `POST /skip` on a session triggers classification and offers appropriate
  substitutes for a `time_constraint` reason.
- Accepting a substitute creates a `GeneratedWorkout` from the library entry's steps.
- A session with `target_date` in the past and `status = generated` is transitioned
  to `missed` by the nightly sweep.
- Redistribution to a date that would create consecutive quality sessions is rejected
  with a clear error message.
- An illness skip triggers plan restructuring — the next 3 sessions after recovery
  are `easy_aerobic` or `recovery_run` regardless of plan phase.
