# Plan Generation — Computation
*Converts TrainingBlock + TwinState into TrainingPlan + PlannedSessions via training length gate, hypothesis generation, validation, synthesis, and instantiation.*

---

## Purpose

- Defines the multi-phase algorithm that produces a training plan from athlete context
- For `race_event` mode: LLM-driven hypothesis generation with constraint-first validation → `plan-generation-race.md`
- For `fitness_improvement` mode: objective-driven rolling blocks → `plan-generation-fitness-improvement.md`
- For `maintenance` mode: deterministic consistency-focused rolling blocks → `plan-generation-maintenance.md`
- For `recovery` mode: severity-driven 3-phase arc with healing assessment → `plan-generation-recovery.md`
- Plan generation produces a **phase arc** (strategic intent per week) and the **first WeeklyPlan** atomically. Session-level detail for subsequent weeks is deferred to weekly synthesis.

---

## Mode Selection

| Goal Type | Approach | File |
|---|---|---|
| `race_event` | LLM-driven hypothesis generation → validation → synthesis | `plan-generation-race.md` |
| `fitness_improvement` | Objective-driven rolling blocks (6–12 weeks, constructed from seeded objectives) | `plan-generation-fitness-improvement.md` |
| `maintenance` | Rolling 4-week block (weeks 1–3 consistent aerobic, week 4 recovery) | `plan-generation-maintenance.md` |
| `recovery` | Severity-driven 3-phase arc (minimal load → gradual return → transition) | `plan-generation-recovery.md` |

---

## Inputs

```typescript
type PlanGenerationInputs = {
  training_block: TrainingBlock
  athlete_preferences: AthletePreferences
  twin_state: TwinState
  cycle_phase_log: CyclePhaseLog | null  // used to avoid key sessions in late luteal
  today: string  // YYYY-MM-DD
  secondary_events: SecondaryEvent[]     // B-events and C-events for disruption window calculation
}

// GoalType determines plan generation approach:
// - race_event: agent-driven hypothesis generation → validation → synthesis (Phase 1-2);
//              then validation and persistence (Phase 3)
// - fitness_improvement: objective-driven rolling blocks (6-12 weeks, constructed from seeded objectives)
// - maintenance: deterministic consistency-focused rolling blocks
// - recovery: deterministic conservative progression

// Secondary events create disruption windows within the phase arc:
// - B-events: 4 days pre-event, 3 days post-event (reduced load/recovery focus)
// - C-events: 2 days pre-event, 1 day post-event (minimal adjustment)
```

---

## Shared Types

These types are used across all modes. Mode-specific types are defined in the respective mode files.

```typescript
type PhaseArcEntry = {
  week_number: number
  phase_label: PhaseLabel
  methodology: MethodologyTraitVector
  physiological_emphasis: string      // plain English; what this week is about
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  race_considerations?: string        // "B-race this week, reduce pre-race"
  checkpoint_intent?: string          // "benchmark aerobic fitness"
  target_session_count: number        // coach's hint; availability and pre-week review may reduce
}

type CheckpointDescriptor = {
  type: CheckpointType
  week_number: number
  target_date: string
  target_metric: string
  session_type: SessionType
  planner_message: string
}
```

---

## Persistence (All Modes)

All modes share the same persistence logic. The first WeeklyPlan is created atomically with the TrainingPlan.

### persistPlan

```typescript
function persistPlan(
  framework: StrategicFramework,
  validation: ValidationResult,
  inputs: PlanGenerationInputs
): { plan: TrainingPlan; first_weekly_plan: WeeklyPlan; checkpoints: Checkpoint[] } {
  // Creates atomically:
  // 1. TrainingPlan (with phase_arc, strategic_rationale, checkpoint_schedule)
  // 2. First WeeklyPlan (synthesised from phase_arc[0] + current twin state)
  // 3. Checkpoint records (from checkpoint_schedule)
  // 4. Fires training_plan_generated event
  
  // The first WeeklyPlan is created by the weekly-synthesis-agent
  // reading phase_arc[0] as the adjusted intent (no pre-week review needed for week 1)
}
```

### createFirstWeeklyPlan

The first weekly plan is always created atomically with the training plan by PlanGenerationService — not by WeeklySynthesisAgent. This ensures the first message can reference specific sessions.

**Why atomic creation for week 1:** Week 1 has no prior execution data, so the pre-week review would be a no-op pass-through. Creating the first WeeklyPlan atomically avoids an unnecessary async hop through PreWeekReviewService and ensures the plan is immediately actionable.

**Producer distinction:** PlanGenerationService creates week 1. PreWeekReviewService + WeeklySynthesisAgent handle week 2 onward. WeeklySynthesisAgent's contract starts from week 2 — it never receives week 1 as input.

```typescript
async function createFirstWeeklyPlan(
  plan: TrainingPlan,
  inputs: PlanGenerationInputs
): Promise<WeeklyPlan> {
  // Week 1 uses the phase arc entry directly as the adjusted intent
  // (no pre-week review — this is the initial synthesis)
  
  // Compute session count for week 1 (same logic as PreWeekReviewService)
  const maxAvailable = deriveMaxAvailable(inputs.athlete_preferences.weekly_schedule)
  const week1_session_count = computeSessionCount({
    target_session_count: plan.phase_arc[0].target_session_count,
    intensity_bias: plan.phase_arc[0].intensity_bias,
    max_available: maxAvailable,
    max_sessions: null
  })
  
  const week1_intent: AdjustedWeeklyIntent = {
    ...plan.phase_arc[0],
    session_count: week1_session_count,
    adjustment_made: false,
    adjustment_reason: null,
    adjustment_source: 'plan_unchanged'
  }
  
  // Weekly synthesis agent produces sessions for week 1
  const weekly_output = await weeklySynthesisAgent.generate({
    adjusted_intent: week1_intent,
    twin_state: inputs.twin_state,
    athlete_preferences: inputs.athlete_preferences,
    prior_weeks_summary: [],  // no prior weeks
    training_plan: plan,
    secondary_events: inputs.secondary_events,
    checkpoint_schedule: plan.checkpoint_schedule.filter(cp => cp.week_number === 1)
  })
  
  // Persist WeeklyPlan with sessions
  return persistWeeklyPlan(plan.id, 1, week1_intent, weekly_output.sessions)
}
```

---

## Regeneration Triggers (All Modes)

Full plan regeneration (replacing the phase arc) is reserved for major structural changes. Most disruptions are absorbed by weekly synthesis.

```typescript
type RegenerationTrigger =
  | 'new_block'
  | 'goal_date_change'        // goal_event_date moved by > 7 days
  | 'confidence_upgrade'      // twin moved from low→medium or medium→high (only if plan was at low)
  | 'secondary_event_added'   // B-race or C-race that conflicts with phase structure
  | 'secondary_event_removed' // Secondary event removed, phase arc needs restructuring
  | 'checkpoint_completed'    // Checkpoint resulted in confidence change AND replan_triggered = true

function shouldRegenerate(trigger: RegenerationTrigger, old_plan: TrainingPlan, new_twin: TwinState): boolean {
  // goal_date_change: only if abs(new_date - old_date) > 7 days
  // confidence_upgrade: only if old plan was generated at 'low' confidence
  // secondary_event changes: only if disruption cannot be accommodated within existing phase arc
  // checkpoint_completed: only if confidence_changed = true AND replan_triggered = true
}
```

### What Does NOT Trigger Regeneration

The following disruptions are absorbed by weekly synthesis, not plan regeneration:

| Disruption | How It's Absorbed |
|---|---|
| Missed sessions (schedule changes, motivation) | Next pre-week review adjusts intent |
| Faster/slower than expected recovery | Weekly synthesis adjusts session count/intensity |
| Minor schedule disruptions (travel, work) | Weekly synthesis works with new availability |
| Adaptation yield better/worse than expected | Pre-week review adjusts intensity bias |
| Persistent disruption (>20% missed over 3 weeks) | Surfaced as coaching signal via `disruption_threshold_exceeded`; coach decides whether to restructure |

### Checkpoint Completion Flow (All Modes)

When a checkpoint completes, the system processes the result:

```typescript
type CheckpointCompletionResult = {
  metric_updated: boolean
  confidence_changed: boolean
  new_confidence_level?: 'low' | 'medium' | 'high'
  replan_triggered: boolean
}

function processCheckpointCompletion(
  checkpoint: Checkpoint,
  session: PlannedSession,
  activity: Activity
): CheckpointCompletionResult {
  // 1. Analyse activity data against checkpoint.target_metric
  // 2. Update twin state if metric changed materially
  // 3. Check if confidence level changed
  // 4. If confidence changed significantly, trigger replanning
  // 5. Return result for event payload
}
```

---

## Cross-References

- **Race event mode:** `plan-generation-race.md` — training length gate, hypothesis generation, validation, synthesis, persistence
- **Fitness improvement mode:** `plan-generation-fitness-improvement.md` — objective-driven blocks, block renewal, checkpoint scheduling
- **Maintenance mode:** `plan-generation-maintenance.md` — rolling 4-week block, consistency metrics, transition detection
- **Recovery mode:** `plan-generation-recovery.md` — severity-driven arc, healing assessment, setback detection
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_arc, strategic_rationale, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **Objective entity:** `01-entities/objective.md` — fitness improvement mode uses seeded objectives
- **Objective management:** `02-computations/objective-management.md` — ObjectiveSeedingService.seedObjectives()
- **WeeklyPlan entity:** `01-entities/weekly-plan.md` — first WeeklyPlan created atomically with TrainingPlan
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for all four modes
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
- **Vision hypothesis selection:** `docs/vision/product/hypothesis-selection.md` — why three hypotheses, scoring criteria
- **Vision checkpoints:** `docs/vision/product/training-plan-checkpoints.md` — checkpoint hierarchy and scheduling
