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
type WeeklyFeasibilityMatrix = {
  week_number: number
  available_days: string[]  // ['2026-06-01', '2026-06-03', ...] from athlete preferences

  // Hard constraints (LLM cannot violate)
  blocked_days: {
    date: string
    reason: 'checkpoint' | 'secondary_event' | 'travel' | 'unavailable'
  }[]

  // Physiological constraints (48h rule)
  quality_session_eligible_days: string[]  // Days where quality sessions are allowed
  long_run_candidates: string[]  // Days suitable for long run (typically 1-2 options)

  // Soft constraints (LLM should prefer)
  preferred_quality_days: string[]  // e.g., weekends for athletes with weekday travel
  preferred_recovery_days: string[]  // e.g., Mondays post-weekend long run

  // Pre-computed anchors (non-negotiable)
  long_run_day: string | null  // If athlete has explicit preference
  checkpoint_sessions: {
    date: string
    type: CheckpointType
    metric: string
  }[]
}

type WeeklySynthesisInput = {
  // What this week is about (after pre-week review)
  adjusted_intent: AdjustedWeeklyIntent

  // Current athlete state
  twin_state: TwinState
  athlete_preferences: AthletePreferences

  // Prior context
  prior_weeks_summary: PriorWeekSummary[]
  training_plan: TrainingPlan

  // Feasibility Matrix (pre-computed constraints)
  feasibility_matrix: WeeklyFeasibilityMatrix

  // Schedule constraints
  secondary_events: SecondaryEvent[]
  checkpoint_schedule: CheckpointDescriptor[]
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
- Athlete preferences (weekly_schedule for availability and long_workout)
- Prior weeks summary (for continuity and fatigue context)
- Training plan (phase context, race schedule, checkpoint schedule)
- Secondary events this week
- Checkpoint descriptors this week

### Instructions
1. Read `session_count` from `AdjustedWeeklyIntent` (pre-computed by PreWeekReviewService)
2. Read `feasibility_matrix` to understand hard constraints:
   - Do NOT place sessions on `blocked_days`
   - Do NOT place quality sessions on days NOT in `quality_session_eligible_days`
   - Place `checkpoint_sessions` on their specified dates
3. Place long run:
   - If `feasibility_matrix.long_run_day` is set → use it
   - Else → select from `long_run_candidates` based on athlete preferences
   - Ensure followed by rest/recovery day
4. Identify block candidates:
   - Only group consecutive quality sessions if:
     - Athlete has high training load (from `twin_state`)
     - Recovery capacity is adequate (from `adaptation_signature`)
     - No `blocked_days` interrupt the block
   - Max 3 sessions per block
   - Assign `block_id` and positions (`first`, `middle`, `last`)
5. Distribute remaining sessions:
   - Prioritize `preferred_quality_days` for threshold/vo2max
   - Ensure 48h between intense efforts (primary-to-primary)
   - Use `quality_session_eligible_days` as the only valid locations
6. Apply intensity bias:
   - Map `target_distribution` to session types using `SESSION_INTENT_MAP`
   - Adjust for `target_specificity` (race-specific variants if >0.7)
7. Handle doubles:
   - If `doubles_eligible` day and not long run → schedule AM primary + PM secondary
   - Secondary sessions are non-running suggestions (strength, yoga)
8. Write intent descriptions:
   - Plain English, natural language
   - Connect session to weekly objective (from `adjusted_intent.objective[]`)
   - Example: "Threshold session — 4x10min at LT2. Focus on controlled pacing."
9. Validate output BEFORE returning:
   - No quality sessions on consecutive dates (unless same block_id)
   - Long run followed by rest/recovery
   - All sessions on `available_days`
   - Session count matches `adjusted_intent.session_count`
10. If validation fails:
    - Retry ONCE with specific error feedback (e.g., "Quality sessions on Tue/Wed — separate them")
    - If second attempt fails → trigger template fallback

---

## Session Placement Rules

### Session Placement Rules

- Long run on `long_workout_day` (if available)
- Long run always followed by rest or `recovery_run`
- Quality sessions (`threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`) sandwiched between easy days
- No two quality sessions on consecutive dates
- Minimum 48 hours between intense efforts
- Sessions only on athlete's available days

### Weekly-Level Rules

Session count is computed deterministically by `PreWeekReviewService` (or `PlanGenerationService` for week 1) and provided as a pre-computed input in `AdjustedWeeklyIntent.session_count`. See `02-computations/session-count.md` for the computation logic.

The weekly synthesis agent reads `session_count` from `AdjustedWeeklyIntent` and distributes sessions across available days.

### Target Distribution → Session Type Distribution

The weekly synthesis agent reads `AdjustedWeeklyIntent.target_distribution` (continuous) instead of the former `intensity_bias` enum. The distribution directly drives session type counts.

**Distribution to session mapping:**

```
target_distribution = { low_aerobic: 0.55, high_aerobic: 0.15, threshold: 0.20, vo2max: 0.05, neuromuscular: 0.05 }
session_count = 5

→ Session types: 2-3 easy/low_aerobic, 1 high_aerobic (long run), 1 threshold, 0-1 vo2max/neuromuscular
```

**Specificity adjustment:** When `target_specificity` is high (>0.7), the agent selects race-specific variants of session types:
- `threshold` → marathon-pace threshold (not generic LT2 intervals)
- `high_aerobic` → marathon-pace long run (not easy long run)
- `low_aerobic` → general aerobic (unchanged)

**Objective guidance:** The `objective[]` array on `AdjustedWeeklyIntent` tells the agent WHY this week exists. The agent uses this to select specific workout types:
- `objective: ['threshold_quality']` → threshold sessions use LT2 intervals
- `objective: ['durability']` → long run includes sustained effort
- `objective: ['pacing_discipline']` → race-pace work included

**Recovery week adjustment:** When `is_recovery_week` is true (from weekly distribution), the agent:
- Shifts distribution toward easy (increases low_aerobic proportion)
- Reduces total session count by 1-2
- Avoids quality sessions entirely

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
      
      // Enforce 3-session cap: push block when full, even if next session is quality
      if (currentBlock.length === 3) {
        candidates.push(currentBlock)
        currentBlock = []
      }
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

Doubles capacity is read from `AthletePreferences.weekly_schedule[day].doubles_eligible`. No inference needed — the flag is set explicitly during onboarding or preference updates.

```typescript
function scheduleDoubles(
  sessions: WeeklySessionPlacement[],
  athlete_pref: AthletePreferences
): WeeklySessionPlacement[] {
  // Read doubles eligibility directly from schedule
  const doubles_days = Object.entries(athlete_pref.weekly_schedule)
    .filter(([_, schedule]) => schedule.available && schedule.doubles_eligible)
    .map(([day, _]) => day)
  
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
| LLM failure (timeout/API error) | Fall back to template (distribute session types across available days) |
| Invalid output (fails validation) | Retry ONCE with specific constraint feedback; then template fallback |
| Schedule constraints make synthesis impossible | Reduce session count until feasible; communicate to athlete via `adjustment_reason` |
| No available days this week | Return empty sessions; flag as `schedule_conflict` for athlete resolution |
| Feasibility matrix contradicts intent | Prioritize matrix (hard constraints); log warning for pre-week review audit |

---

## Template Fallback

When the LLM cannot produce a valid weekly plan:

```python
def template_fallback(
    intent: AdjustedWeeklyIntent,
    athlete_pref: AthletePreferences,
) -> list[WeeklySessionPlacement]:
    sessions = []
    session_count = intent.session_count  # from AdjustedWeeklyIntent

    # Read availability from structured weekly_schedule
    available_days = [day for day, schedule in athlete_pref.weekly_schedule.items() if schedule.available]
    long_workout_day = next((day for day, schedule in athlete_pref.weekly_schedule.items() if schedule.long_workout), None)

    # Distribute: easy sessions first, then quality
    easy_count = math.ceil(session_count * 0.7)
    quality_count = session_count - easy_count

    # Place long run on long_workout_day
    if long_workout_day and long_workout_day in available_days:
        sessions.append(WeeklySessionPlacement(
            target_date=next_date(long_workout_day),
            session_type="long_run",
            intent_description=intent.physiological_emphasis,
            approximate_duration_minutes=90,
            is_checkpoint=False,
        ))

    # Fill remaining sessions across available days
    # ... (simplified)

    return sessions
```

**Note:** The template fallback now receives the `feasibility_matrix` and respects all hard constraints (blocked days, quality eligibility). It performs a simple round-robin distribution but never violates physiological rules.

---

## Invariants

- **Weekly synthesis cannot change the plan's phase or strategic direction.** It only produces sessions within the adjusted intent's constraints.
- **Output is validated against hard invariants** before persistence: no back-to-back quality, 48h recovery, available days, long run recovery.
- **WeeklyPlan is created atomically.** All sessions are persisted together. Partial creation is rolled back.
- **Session count is pre-computed by PreWeekReviewService.** The weekly synthesis agent reads `AdjustedWeeklyIntent.session_count` and distributes sessions — it does not recompute.

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

## Decision Authority

Implements the **Plan Modification Authority** authority boundary from `docs/vision/coach/decision-authority.md`.

The weekly rhythm is the coach's decision, not the athlete's. This agent produces the actual session schedule within the adjusted intent constraints. The athlete sees the result — a week of sessions that fits their current state — but does not approve or negotiate the schedule. The invariant "weekly synthesis cannot change the plan's phase or strategic direction" enforces the boundary between tactical weekly scheduling and strategic plan modification. Session count, intensity bias, and session types are determined by the pre-week review (coach decision), not by athlete request.

---

## Cross-References

- Decision authority: `docs/vision/coach/decision-authority.md` → "Plan Modification Authority"
- Weekly plan entity: `01-entities/weekly-plan.md`
- Pre-week review: `03-agents/pre-week-review-agent.md` (Python service)
- Session count computation: `02-computations/session-count.md`
- Plan phase definitions: `01-entities/training-plan.md` → `phase_definitions`
- Session placement rules: session placement rules section below
- Workout generation: `03-agents/workout-generation-agent.md`
- Checkpoint scheduling: `01-entities/checkpoint.md`
- Secondary events: `01-entities/secondary-event.md` (if exists)

## Design Notes

- Week 1 is handled by PlanGenerationService (first WeeklyPlan created atomically). This agent starts from week 2 onward via `pre_week_review_completed`.
- Session count is a deterministic Python computation, not an LLM judgment call. PreWeekReviewService computes it via `compute_session_count()` and includes it in `AdjustedWeeklyIntent.session_count`. The weekly synthesis agent reads this value and distributes sessions — it does not recompute.
