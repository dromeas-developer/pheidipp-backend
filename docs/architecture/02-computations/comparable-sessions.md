# Comparable Session Identification

## Purpose
- Defines the two-pass algorithm that identifies the most relevant previous session for post-workout comparison
- The backend selects; the LLM narrates. The LLM never chooses the comparable session.

## Algorithm

```typescript
type ComparableSessionResult = {
  activity: Activity
  execution_observation: ExecutionObservation
  similarity_score: number  // 0.0–1.0; minimum 0.50 required
  weeks_ago: number
} | null  // null when no session meets the threshold

function findComparableSession(
  current_activity: Activity,
  current_planned_session: PlannedSession,
  current_twin_state: TwinState,
  athlete_history: Activity[]
): ComparableSessionResult {
  // Pass 1: Hard filters
  const candidates = athlete_history.filter(a =>
    a.id !== current_activity.id &&
    a.calibration_eligible &&
    a.planned_session_id !== null &&  // must have been part of a plan
    // Same session type
    getSessionType(a) === current_planned_session.session_type &&
    // Adjacent phase (same or ±1 phase in plan progression)
    isAdjacentPhase(getPhaseLabel(a), current_planned_session.phase_label) &&
    // 6–90 day lookback window
    daysBetween(a.activity_date, current_activity.activity_date) >= 6 &&
    daysBetween(a.activity_date, current_activity.activity_date) <= 90 &&
    // Same HR availability (ensures signal comparability)
    a.has_hr === current_activity.has_hr
  )

  if (candidates.length === 0) return null

  // Pass 2: Weighted similarity scoring
  const scored = candidates.map(candidate => {
    const candidate_twin = getTwinStateAtDate(candidate.activity_date)  // closest prior twin state
    const fitness_proximity = 1 - Math.abs(
      candidate_twin.fitness_score - current_twin_state.fitness_score
    ) / current_twin_state.fitness_score

    const duration_similarity = 1 - Math.abs(
      candidate.duration_seconds - current_activity.duration_seconds
    ) / current_activity.duration_seconds

    const load_similarity = 1 - Math.abs(
      (candidate.aerobic_load ?? 0) - (current_activity.aerobic_load ?? 0)
    ) / (current_activity.aerobic_load ?? 1)

    const phase_position_similarity = 1 - Math.abs(
      getWeekInPhase(candidate) - getWeekInPhase(current_planned_session)
    ) / getPhaseWeeks(current_planned_session.phase_label)

    const score =
      fitness_proximity * 0.35 +
      duration_similarity * 0.25 +
      load_similarity * 0.25 +
      phase_position_similarity * 0.15

    return { activity: candidate, score }
  })

  const best = scored.sort((a, b) => b.score - a.score)[0]
  if (best.score < 0.50) return null  // minimum threshold

  return {
    activity: best.activity,
    execution_observation: getExecutionObservation(best.activity.id),
    similarity_score: best.score,
    weeks_ago: Math.floor(daysBetween(best.activity.activity_date, current_activity.activity_date) / 7)
  }
}
```

## Agent Context Block

When a comparable session is found, the post-workout agent receives:

```typescript
type ComparableSessionContext = {
  date: string                  // YYYY-MM-DD
  weeks_ago: number
  session_type: SessionType
  phase_label: PhaseLabel
  session_shape: SessionShape   // from ExecutionObservation
  key_execution_signals: {
    cross_rep_trend?: string
    final_rep_delta_pct?: number
    cardiac_drift_score?: number
    session_shape?: SessionShape
  }
  similarity_score: number
}
```

When `null` (no comparable found): the key `comparable_session` is absent from the agent context entirely. The agent prompt instructs: if no comparable session is provided, do not reference historical sessions and do not fabricate a comparison.

## Invariants
- The comparable session selection is pure Python. The LLM receives the pre-selected session and narrates the comparison. The LLM never makes the selection.
- Minimum similarity threshold: 0.50. Below this, the third paragraph of the post-workout message focuses on objective progress instead.
- The current activity is never selected as its own comparable (filtered by `a.id !== current_activity.id`).
- 6-day minimum lookback prevents comparing against yesterday's session (shared fatigue state would confound the comparison).

## Cross-References
- ExecutionObservation schema (key_execution_signals source): `01-entities/execution-observation.md`
- PostWorkoutAgent context assembly: `03-agents/post-workout-agent.md`
- Similarity score stored for audit: `01-entities/execution-observation.md` → `coaching_observations.comparable_session_id`
- Vision historical correlation requirements: `vision/coach/post-workout.md` → "Historical correlation" element
- Post-workout message mapping (vision element → architecture field → agent paragraph): `01-entities/execution-observation.md` → "Post-Workout Message Mapping"
