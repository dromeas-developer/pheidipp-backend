# weekly-plan

## Purpose

- Stores the session schedule for a single week within a training plan
- Created by the weekly synthesis agent before the week begins
- Consumed by daily workout generation and by the next pre-week review as accumulated execution data

---

## TypeScript Schema

```typescript
type WeeklyPlanStatus = 
  | 'synthesised'    // sessions defined, week not yet started
  | 'active'         // week in progress, at least one session completed
  | 'completed'      // all sessions in the week are completed or missed

type WeeklyPlan = {
  id: string                           // UUID, PK
  training_plan_id: string             // UUID, FK → TrainingPlan
  week_number: number                  // 1-indexed within the plan
  
  // What this week is about
  adjusted_intent: AdjustedWeeklyIntent  // from pre-week review
  
  // The sessions
  sessions: WeeklySession[]
  
  // Status
  status: WeeklyPlanStatus
  
  // Execution summary (populated as sessions complete)
  sessions_completed: number
  sessions_missed: number
  sessions_skipped: number
  accumulated_fatigue_delta: number    // net fatigue change from prior weeks
  doubles_days_count: number           // number of days with AM/PM sessions
  
  created_at: string                   // ISO 8601
  week_starts_at: string               // YYYY-MM-DD
  week_ends_at: string                 // YYYY-MM-DD
}

type WeeklySession = {
  id: string                           // UUID, PK
  weekly_plan_id: string               // UUID, FK → WeeklyPlan
  target_date: string                  // YYYY-MM-DD
  session_type: SessionType
  intent_description: string           // "threshold development — 4x8min at LT2"
  approximate_duration_minutes: number
  is_checkpoint: boolean
  checkpoint_type?: CheckpointType
  checkpoint_metric?: string
  status: 'scheduled' | 'completed' | 'skipped' | 'missed'
  planned_session_id: string | null    // UUID, FK → PlannedSession (created when workout is generated)
}
```

---

## Invariants

- **One WeeklyPlan per week per TrainingPlan.** Cannot create two plans for the same `(training_plan_id, week_number)`.
- **weekly_plan_created fires before the week starts.** The plan is synthesised in advance, not retroactively.
- **week_completed fires after the last session.** Only when all sessions in the week are completed or missed.
- **Sessions array is immutable once active.** No mid-week session additions after status transitions to `active`.
- **accumulated_fatigue_delta feeds forward.** It is the sum of all session fatigue contributions minus recovery. It feeds into the next pre-week review.
- **One WeeklySession per PlannedSession.** When a workout is generated for a session, the `planned_session_id` FK is set on the WeeklySession. This link is established lazily at workout generation time, not at WeeklyPlan creation. The WeeklyPlan is created with sessions; PlannedSession records are created later when the workout generation agent runs.

---

## Events

### Produced

| Event | Trigger | Version | Payload |
|---|---|---|---|
| `weekly_plan_created` | Status → synthesised | v1 | `{weekly_plan_id, training_plan_id, week_number, session_count}` |
| `week_completed` | All sessions completed/missed | v1 | `{weekly_plan_id, week_number, sessions_completed, sessions_missed, accumulated_fatigue_delta}` |

### Consumed

| Event | Action | Version |
|---|---|---|
| `pre_week_review_completed` | Weekly synthesis agent creates WeeklyPlan from AdjustedWeeklyIntent | v1 |
| `session_completed` | Update WeeklySession status; check if week is complete | v1 |
| `session_missed` | Update WeeklySession status; check if week is complete | v1 |

Note: The `pre_week_review_completed` event payload contains `{training_plan_id, week_number, adjustment_made, adjustment_source}` — NOT `weekly_plan_id`, because the WeeklyPlan does not exist yet at the time of the review. The weekly synthesis agent uses `training_plan_id` + `week_number` to look up the phase arc entry and create the WeeklyPlan.

---

## Weekly Load Calculation

Weekly load is based on **total athlete availability**, including doubles capacity.

```typescript
function computeWeeklyLoad(sessions: WeeklySession[]): WeeklyLoad {
  // Group by date
  const byDate = groupByDate(sessions)
  
  let totalLoad = 0
  let doublesDays = 0
  
  for (const [date, daySessions] of Object.entries(byDate)) {
    if (daySessions.length === 1) {
      // Single session day
      totalLoad += estimateLoad(daySessions[0])
    } else {
      // Double day — sum both, but cap at 1.5x single session max
      const dayLoad = daySessions.reduce((sum, s) => sum + estimateLoad(s), 0)
      const maxSingleDay = maxLoadForSingleSession()
      totalLoad += Math.min(dayLoad, maxSingleDay * 1.5)
      doublesDays++
    }
  }
  
  return { totalLoad, doublesDays }
}
```

The weekly synthesis agent uses total availability (including doubles capacity) when defining macro weekly load in the phase arc.

---

## Runtime Ownership

Owns:
- Week-level session schedule storage
- Session status tracking within the week
- Accumulated fatigue delta computation
- Week completion detection
- Doubles day tracking

Does Not Own:
- How sessions are synthesised → `03-agents/weekly-synthesis-agent.md`
- How intent is adjusted → `03-agents/pre-week-review-agent.md` (Python service)
- How individual workouts are generated → `03-agents/workout-generation-agent.md`
- Plan-level phase arc → `01-entities/training-plan.md`

---

## Failure Semantics

- Weekly synthesis fails → no WeeklyPlan created; fallback to template-based session distribution for that week
- Week completion detection fails → nightly sweep checks for all sessions completed/missed; fires event if overdue
- accumulated_fatigue_delta computation fails → defaults to 0; flagged for manual review

---

## Performance Constraints

- `GET /plan/weekly/{week_number}`: p95 < 50ms (indexed lookup)
- Weekly plan creation: p95 < 5s (LLM synthesis + persistence)

---

## Observability

Metrics:
- `weekly_plan.created.total`: per week number
- `weekly_plan.sessions_completed.rate`: completed / total per week
- `weekly_plan.adjustment_rate`: percentage of weeks where pre-week review adjusted intent

Logs:
- `weekly_plan.created`: weekly_plan_id, week_number, session_count, adjustment_made
- `weekly_plan.completed`: weekly_plan_id, sessions_completed, sessions_missed, accumulated_fatigue_delta
