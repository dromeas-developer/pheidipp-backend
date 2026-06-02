# weekly-synthesis-agent

## Purpose

- Produces the actual session schedule for a single week
- Reads the adjusted intent from the pre-week review and the current athlete state
- Outputs a WeeklyPlan with session count, types, days, and approximate duration

---

## Context Budget: ~3k–5k tokens

---

## Trigger

Triggered by `pre_week_review_completed` event. Runs once per week, before the week starts.

---

## Context Type

```typescript
type WeeklySynthesisInput = {
  // What this week is about (after pre-week review)
  adjusted_intent: AdjustedWeeklyIntent
  
  // Current athlete state
  twin_state: TwinState
  athlete_preferences: AthletePreferences  // available days, long_workout_day, weekly_session_count preference
  
  // Prior context
  prior_weeks_summary: PriorWeekSummary[]  // for continuity
  training_plan: TrainingPlan              // for phase context and race schedule
  
  // Schedule constraints
  secondary_events: SecondaryEvent[]       // any B/C races this week
  checkpoint_schedule: CheckpointDescriptor[]  // checkpoints for THIS week (pre-filtered by caller)
}
```

---

## Output Contract

```typescript
type WeeklySynthesisOutput = {
  sessions: WeeklySessionPlacement[]
}

type WeeklySessionPlacement = {
  target_date: string                  // YYYY-MM-DD
  session_type: SessionType
  intent_description: string
  approximate_duration_minutes: number
  is_checkpoint: boolean
  checkpoint_type?: CheckpointType
  checkpoint_metric?: string
  
  // Slot designation (for doubles)
  session_slot: SessionSlot | null     // null = single session; 'am'/'pm' = double day
  session_priority: SessionPriority    // default: 'primary'
  
  // Block membership
  block_id: string | null              // null = standalone; non-null = part of block
  block_position: 'first' | 'middle' | 'last' | null
  block_session_count: number | null   // total sessions in block
  
  // Non-running session support
  is_suggested: boolean                // true = suggested (strength, yoga); false = full workout
}
```

---

## Prompt Structure

### System Prompt
- Session type definitions (16 values: rest, recovery_run, easy_run, long_run, medium_long_run, steady_state, tempo, threshold, vo2max, hill_repeats, fartlek, strides, drills_mobility, cross_training, test_session, optional_run)
- Session→Intent mapping (SESSION_INTENT_MAP)
- MethodologyTraitVector and trait→intent aggregation
- Structural rules (long run → rest, no back-to-back quality, 48h recovery)
- Phase-specific guidance (base = mostly easy, build = add quality, peak = race-specific)
- Race integration rules (taper, recovery windows)
- Checkpoint placement rules
- Weekly synthesis rules (session count from adjusted intent, intensity bias drives type distribution)

### Context
- AdjustedWeeklyIntent from pre-week review
- Athlete preferences (available days, long_workout_day)
- Prior weeks summary (for continuity and fatigue context)
- Training plan (phase context, race schedule, checkpoint schedule)
- Secondary events this week
- Checkpoint descriptors this week

### Instructions
1. Receive session count as a pre-computed input (from `PreWeekReviewService` or `PlanGenerationService`)
2. Identify which days are available (including doubles capacity)
3. Place long run on long_workout_day (if available)
4. Place checkpoints if scheduled this week (checkpoint_schedule is pre-filtered to this week by caller)
5. Identify potential block candidates (2-3 consecutive quality sessions)
6. If blocks are appropriate, assign block_id and block positions
7. Distribute remaining sessions across available days
8. Ensure no back-to-back quality sessions unless they share a block_id
9. Ensure long run followed by rest or recovery
10. Ensure minimum 48h between intense efforts (primary to primary)
11. Apply intensity bias to session type distribution
12. For doubles days: assign AM primary, PM secondary
13. For non-running sessions: set is_suggested = true, session_priority = 'secondary'
14. Return WeeklySessionPlacement[]

---

## Session Placement Rules

### Inherited from Session Planner Agent

- Long run on `long_workout_day` (if available)
- Long run always followed by rest or `recovery_run`
- Quality sessions (`threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`) sandwiched between easy days
- No two quality sessions on consecutive dates
- Minimum 48 hours between intense efforts
- Sessions only on athlete's available days

### Weekly-Level Rules

Session count is computed deterministically by `PreWeekReviewService` (or `PlanGenerationService` for week 1) and provided as a pre-computed input. See `02-computations/session-count.md` for the computation logic.

The weekly synthesis agent receives `session_count` as part of `AdjustedWeeklyIntent` and distributes sessions across available days.

### Intensity Bias → Session Type Distribution

| Intensity Bias | Easy Sessions | Quality Sessions | Notes |
|---|---|---|---|
| `easy` | 80–100% | 0–20% | Recovery or fatigue correction weeks |
| `balanced` | 60–70% | 30–40% | Standard base building |
| `moderate` | 50–60% | 40–50% | Build phase, threshold development |
| `quality` | 40–50% | 50–60% | Race-specific, sharpening |

The weekly planner distributes session types to match the bias while respecting structural rules.

### Block Creation Logic

When consecutive quality sessions are appropriate (advanced athletes, schedule constraints), the agent groups them into blocks:

```typescript
function identifyBlockCandidates(
  sessions: WeeklySessionPlacement[]
): WeeklySessionPlacement[][] {
  // Find consecutive quality sessions
  const quality_types = ['threshold', 'vo2max', 'tempo', 'hill_repeats', 'fartlek']
  const candidates: WeeklySessionPlacement[][] = []
  let currentBlock: WeeklySessionPlacement[] = []
  
  for (const session of sessions.sort((a, b) => a.target_date.localeCompare(b.target_date))) {
    if (quality_types.includes(session.session_type)) {
      currentBlock.push(session)
    } else {
      if (currentBlock.length >= 2) {
        candidates.push(currentBlock)
      }
      currentBlock = []
    }
  }
  if (currentBlock.length >= 2) {
    candidates.push(currentBlock)
  }
  
  return candidates
}

function assignBlockMetadata(
  block: WeeklySessionPlacement[],
  block_id: string
): void {
  block.forEach((session, index) => {
    session.block_id = block_id
    session.block_session_count = block.length
    if (index === 0) session.block_position = 'first'
    else if (index === block.length - 1) session.block_position = 'last'
    else session.block_position = 'middle'
  })
}
```

**When to create blocks:**
- Advanced athletes with high training load
- Schedule constraints requiring compressed quality
- When adaptation signature learning benefits from compound stimuli

Note: When assigning `block_id` to consecutive quality sessions, the agent is creating what the adaptation signature layer later observes as an adaptation window. The `block_id` is the planning mechanism; the adaptation window is the observation purpose.

**When NOT to create blocks:**
- Beginners or athletes with low training load
- When recovery capacity is limited
- When the phase emphasis is on recovery or base building

### Doubles Scheduling

For athletes with doubles capacity:

```typescript
function scheduleDoubles(
  sessions: WeeklySessionPlacement[],
  athlete_pref: AthletePreferences
): WeeklySessionPlacement[] {
  const doubles_days = athlete_pref.doubles_days || [] // e.g. ['Tuesday', 'Thursday']
  
  for (const session of sessions) {
    const day_of_week = getDayOfWeek(session.target_date)
    
    if (doubles_days.includes(day_of_week) && session.session_type !== 'long_run') {
      // This session becomes the primary on a doubles day
      session.session_slot = 'am'
      session.session_priority = 'primary'
      
      // Add a secondary session for PM (non-running suggestion)
      sessions.push({
        target_date: session.target_date,
        session_type: 'drills_mobility',
        intent_description: 'Mobility & form drills — 30 min',
        approximate_duration_minutes: 30,
        is_checkpoint: false,
        session_slot: 'pm',
        session_priority: 'secondary',
        block_id: null,
        block_position: null,
        block_session_count: null,
        is_suggested: true
      })
    }
  }
  
  return sessions
}
```

**Doubles rules:**
- AM primary + PM secondary is preferred ordering
- Long runs are never scheduled as part of doubles
- Secondary sessions are non-running suggestions (strength, yoga, mobility)
- Recovery is measured from primary to primary

### Race Week Rules

If a secondary event is scheduled this week:
- Pre-race: reduce load 3–4 days before (B-race) or 1–2 days before (C-race)
- Post-race: recovery focus for 2–5 days depending on race role
- Session count reduced to accommodate disruption window

If a checkpoint is scheduled this week:
- Place checkpoint session on the optimal day (typically mid-week for calibration, weekend for benchmark)
- Ensure pre-checkpoint session is easy (athlete arrives fresh)
- Ensure post-checkpoint session accounts for recovery needs

---

## Failure Semantics

| Scenario | Behaviour |
|---|---|
| LLM failure | Fall back to template: distribute plan's default session types across available days |
| Invalid output | Retry once with validation feedback; then template fallback |
| Schedule constraints make synthesis impossible | Reduce session count until feasible; communicate to athlete |
| No available days this week | Return empty sessions; flag as schedule conflict for athlete resolution |

---

## Template Fallback

When the LLM cannot produce a valid weekly plan:

```python
def template_fallback(
    intent: AdjustedWeeklyIntent,
    athlete_pref: AthletePreferences,
    session_count: int,
) -> list[WeeklySessionPlacement]:
    sessions = []
    available_days = athlete_pref.available_days

    # Distribute: easy sessions first, then quality
    easy_count = math.ceil(session_count * 0.7)
    quality_count = session_count - easy_count

    # Place long run on long_workout_day
    sessions.append(WeeklySessionPlacement(
        target_date=next_date(athlete_pref.long_workout_day),
        session_type="long_run",
        intent_description=intent.physiological_emphasis,
        approximate_duration_minutes=90,
        is_checkpoint=False,
    ))

    # Fill remaining sessions across available days
    # ... (simplified)

    return sessions
```

---

## Invariants

- **Weekly synthesis cannot change the plan's phase or strategic direction.** It only produces sessions within the adjusted intent's constraints.
- **Output is validated against hard invariants** before persistence: no back-to-back quality, 48h recovery, available days, long run recovery.
- **WeeklyPlan is created atomically.** All sessions are persisted together. Partial creation is rolled back.
- **Session count respects both adjusted intent and athlete preference.** The lower of the two wins when they conflict.

---

## Idempotency

- **Not idempotent.** Different inputs may produce different session schedules.
- Same inputs → same schedule (deterministic for same context).

---

## Events

### Produced

| Event | Trigger | Version | Payload |
|---|---|---|---|
| `weekly_plan_created` | WeeklyPlan persisted | v1 | `{weekly_plan_id, training_plan_id, week_number, session_count}` |

### Consumed

| Event | Action | Version |
|---|---|---|
| `pre_week_review_completed` | Trigger weekly synthesis | v1 |

---

## Cross-References

- Weekly plan entity: `01-entities/weekly-plan.md`
- Pre-week review: `03-agents/pre-week-review-agent.md` (Python service)
- Session count computation: `02-computations/session-count.md`
- Plan phase arc: `01-entities/training-plan.md` → `phase_arc`
- Session planner (base rules): `03-agents/session-planner-agent.md`
- Workout generation: `03-agents/workout-generation-agent.md`
- Checkpoint scheduling: `01-entities/checkpoint.md`
- Secondary events: `01-entities/secondary-event.md` (if exists)

## Design Notes

- Week 1 is handled by PlanGenerationService (first WeeklyPlan created atomically). This agent starts from week 2 onward via `pre_week_review_completed`.
- Session count is a deterministic Python computation, not an LLM judgment call. The agent receives it as a pre-computed input.
