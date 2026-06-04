# Plan Generation — Maintenance Mode
*Rolling 4-week block with consistency tracking and transition detection.*

---

## Purpose

- Defines the deterministic phase arc construction for maintenance mode
- Minimal rolling 4-week block: weeks 1–3 consistent aerobic, week 4 recovery/consolidation
- No objectives, no progression — consistency and habit preservation
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Phase Arc Construction

```typescript
function computeMaintenanceArc(
  total_weeks: number,
  athlete_preferences: AthletePreferences
): PhaseArcEntry[] {
  const block_size = 4
  const num_blocks = Math.ceil(total_weeks / block_size)

  return Array.from({ length: total_weeks }, (_, i) => {
    const week_in_block = (i % block_size) + 1
    const is_recovery_week = week_in_block === 4

    return {
      week_number: i + 1,
      phase_label: 'rolling_block',
      methodology: {
        high_aerobic_volume: 0.6,
        low_intensity_dominant: 0.8,
        threshold_density: 0.1,
        high_intensity_sparse: 0.0,
        high_frequency: 0.5,
        structural_durability: 0.3,
        race_specificity: 0.0,
        variety_emphasis: 0.3,
        neuromuscular_support: 0.1,
        conservative_progression: 0.7
      },
      physiological_emphasis: is_recovery_week
        ? 'Recovery and consolidation'
        : 'Consistent aerobic development with form preservation',
      intensity_bias: is_recovery_week ? 'easy' : 'easy',
      target_session_count: is_recovery_week
        ? Math.max(2, athlete_preferences.preferred_sessions_per_week - 2)
        : athlete_preferences.preferred_sessions_per_week
    }
  })
}
```

---

## Block Structure

```
Rolling 4-week block
  ├── Weeks 1-3: Consistent aerobic training (85-90% easy)
  │   ├── Session types: easy_run, long_run, recovery_run
  │   ├── Intensity bias: easy
  │   └── Hard training: 5-10% of weekly volume maximum
  └── Week 4: Recovery / consolidation week
      ├── Session types: easy_run, recovery_run, rest
      ├── Intensity bias: easy
      └── Volume: 60-70% of weeks 1-3
      → Repeat with minor session type variation
```

---

## Checkpoint Scheduling (Maintenance-Specific)

```typescript
function generateMaintenanceCheckpoints(
  phase_arc: PhaseArcEntry[]
): CheckpointDescriptor[] {
  const checkpoints: CheckpointDescriptor[] = []

  // Benchmark every 8-12 weeks
  for (let week = 8; week <= phase_arc.length; week += 10) {
    checkpoints.push({
      type: 'benchmark',
      week_number: week,
      target_date: computeDateForWeek(week),
      target_metric: 'primary_performance_anchor',  // LT2 or CP
      session_type: 'test_session',
      planner_message: `Fitness maintenance check — this session confirms you're holding your current level`
    })
  }

  // Progress review every 4 weeks
  for (let week = 4; week <= phase_arc.length; week += 4) {
    checkpoints.push({
      type: 'progress_review',
      week_number: week,
      target_date: computeDateForWeek(week),
      target_metric: 'consistency_signal',
      session_type: 'easy',
      planner_message: `Weekly consistency check — reviewing your training pattern`
    })
  }

  return checkpoints
}
```

Checkpoint types and scheduling:

| Type | Scheduling |
|---|---|
| benchmark | Every 8–12 weeks |
| progress_review | Every 4 weeks (aligned with block completion) |
| calibration | Only if confidence drops (e.g., after extended break) |

---

## Intensity and Volume

```typescript
function computeMaintenanceIntensityAllocation(): number {
  return 0.05  // 5-10% hard training maximum
}

function computeMaintenanceVolumeChange(
  current_week: number,
  is_recovery_week: boolean
): number {
  if (is_recovery_week) return -0.30  // 30% reduction for recovery week
  return 0.0  // no progression in maintenance mode
}
```

---

## Consistency Metrics

```typescript
type ConsistencyMetrics = {
  session_completion_rate: number        // completed / total sessions
  weekly_volume_stability: number       // coefficient of variation of weekly volume
  recovery_week_compliance: boolean     // did athlete take the 4th week recovery
  consecutive_blocks_completed: number  // blocks without disruption
}

function evaluateConsistency(
  athlete_id: string,
  lookback_weeks: number
): ConsistencyMetrics {
  // Compute from PlannedSession status history
  // Used for transition detection to fitness_improvement
}
```

---

## Transition Detection

When the athlete demonstrates sufficient consistency and readiness, the coach proposes transitioning to fitness improvement mode:

```typescript
function shouldTransitionFromMaintenance(
  athlete_id: string,
  consistency: ConsistencyMetrics,
  twin_state: TwinState,
  adaptation_observations: AdaptationObservation[]
): { should_transition: boolean; target_mode: GoalType; reason: string } {

  // Consistency threshold: >90% session completion over 3+ blocks
  if (consistency.session_completion_rate > 0.90 &&
      consistency.consecutive_blocks_completed >= 3) {
    return {
      should_transition: true,
      target_mode: 'fitness_improvement',
      reason: 'Your consistency has been excellent. You have demonstrated capacity for progressive development.'
    }
  }

  // Confidence upgrade: LOW→MEDIUM or MEDIUM→HIGH
  if (twin_state.confidence_level === 'medium' || twin_state.confidence_level === 'high') {
    return {
      should_transition: true,
      target_mode: 'fitness_improvement',
      reason: 'Your data confidence has improved. We now have enough information for targeted development.'
    }
  }

  // Strong adaptation response
  if (adaptation_observations.length >= 3) {
    const avg_yield = mean(adaptation_observations.map(a => a.aerobic_yield))
    if (avg_yield > 1.0) {
      return {
        should_transition: true,
        target_mode: 'fitness_improvement',
        reason: 'Your body is responding well to training. You are ready for progressive development.'
      }
    }
  }

  return { should_transition: false, target_mode: 'maintenance', reason: '' }
}
```

---

## Regeneration Triggers (Maintenance)

| Trigger | Condition |
|---|---|
| confidence_upgrade | LOW→MEDIUM or MEDIUM→HIGH |
| persistent_disruption | >20% missed over 3 weeks |
| fitness_decline_detected | Benchmark shows material decline from baseline |

---

## Cross-References

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseArcEntry, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_arc, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for maintenance mode
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
