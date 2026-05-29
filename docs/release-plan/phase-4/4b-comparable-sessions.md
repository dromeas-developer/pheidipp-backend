# 4b — Comparable Session Identification
*ComparableSessionService, historical references in post-workout messages*

## Objective

Every post-workout message references a genuinely comparable previous session.
This is the feature that makes coaching feel like it comes from someone who has
been watching the athlete over time rather than responding to isolated events.
The backend identifies the comparable session; the LLM narrates the comparison.

## Scope

`ComparableSessionService`. Two-pass matching algorithm (hard filters + weighted
similarity scoring). Integration into `PostWorkoutAgent` context assembly.

## Non-Goals

- Group session comparison (deferred — no group feature yet)
- Segmentation-level comparison (deferred to 5c — this phase compares at session
  level using Activity and ExecutionObservation, not PhysiologicalSegment)

## Architecture References

- `ComparableSessionService` full algorithm, pass definitions, and similarity weights:
  `architecture/coaching-services.md` → Comparable Session Identification
- Minimum similarity threshold (0.50) and null handling:
  `architecture/coaching-services.md` → ComparableSessionService
- What the agent receives as structured JSON:
  `architecture/coaching-services.md` → What the Agent Receives
- Vision-level importance of historical correlation:
  `vision/coach/post-workout.md` → Historical Correlation

## Dependencies

Requires 4a (`ExecutionObservation` must exist — comparable sessions are compared
on session shape and key signals, not just duration and type).
Requires at least 2 calibration-eligible sessions with `ExecutionObservation`
for any match to be possible.

## Models Introduced

None. `ComparableSessionService` reads existing `Activity`, `PlannedSession`,
`TwinState`, and `ExecutionObservation` records.

## Services Introduced

**`ComparableSessionService`** (sync, Python).
- `find(activity, athlete) → Activity | None`
  Two-pass algorithm from arch reference:
  Pass 1 — hard filters: same session_type, adjacent phase_label,
  6–90 days ago, same has_hr value.
  Pass 2 — weighted similarity: fitness proximity (0.35), duration similarity (0.25),
  load score similarity (0.25), phase position similarity (0.15).
  Returns the highest-scoring candidate above 0.50 threshold, or None.
- `build_summary(comparable_activity) → dict`
  Produces the structured JSON block the agent receives (from arch reference):
  date, weeks_ago, session_type, phase_label, session_shape, key_execution_signals,
  similarity_score.

## Services Modified

**`PostWorkoutAgent`** (updated) — `ContextBudgetService.build_post_workout_context()`
now calls `ComparableSessionService.find()` and includes the result.
- If comparable found: included as `comparable_session` in context.
- If null (no match above threshold): `comparable_session` key is absent from context.
  Agent prompt instructs: if no comparable session is provided, do not reference
  historical sessions. Never fabricate a comparison.

## Key Constraints

- The comparable session selection is pure Python — the LLM never selects it.
  The LLM receives a pre-identified session and narrates the comparison.
- If `ComparableSessionService.find()` returns null, the post-workout message is
  still valid — the third paragraph focuses on objective progress instead of
  historical comparison.
- The service must not select the current activity as its own comparable.
- Minimum 6-day lookback prevents comparing a session to one from yesterday
  (confounded by shared fatigue state).

## Done Criteria

- After syncing a second threshold session at least 6 days after the first:
  the post-workout message references the first session with a specific observation
  comparing execution (e.g. pace in final rep, session shape).
- When only one session exists for a given type, the comparable is null and the
  post-workout message contains no historical reference without errors.
- `similarity_score` is logged in `PostWorkoutAnalysis.execution_findings` for
  auditability — the comparable session ID and its score are stored.
