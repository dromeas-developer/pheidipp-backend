# Plan Generation — Maintenance Mode

- Defines the deterministic phase definitions construction for maintenance mode
- Minimal rolling 4-week block: weeks 1–3 consistent aerobic, week 4 recovery/consolidation
- No objectives, no progression — consistency and habit preservation
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Phase Definitions Construction

```typescript
function computeMaintenancePhases(
  total_weeks: number,
  athlete_preferences: AthletePreferences
): PhaseDefinition[] {
  const block_size = 4
  const num_blocks = Math.ceil(total_weeks / block_size)
  const phases: PhaseDefinition[] = []

  for (let block = 0; block < num_blocks; block++) {
    const weeks_in_block = Math.min(block_size, total_weeks - (block * block_size))
    
    // Each 4-week block has 3 consistent weeks + 1 recovery week
    // Represented as a single phase definition with recovery_cycle = 'moderate'
    // (every 4th week is recovery)
    phases.push({
      phase: 'rolling_block',
      objective: ['aerobic_base', 'recovery_efficiency'],
      weeks: weeks_in_block,
      distribution: {
        low_aerobic: 0.75,
        high_aerobic: 0.15,
        threshold: 0.05,
        vo2max: 0.03,
        neuromuscular: 0.02
      },
      specificity: 0.0,
      approach: 'linear',
      recovery_cycle: 'moderate'  // every 4th week is recovery
    })
  }

  return phases
}
```

The deterministic expansion function handles the within-block pattern: weeks 1–3 at full distribution, week 4 shifted toward easy (recovery week). This is driven by `recovery_cycle: 'moderate'` in the phase definition.

---

## Checkpoint Scheduling (Maintenance-Specific)

```typescript
function generateMaintenanceCheckpoints(
  phase_definitions: PhaseDefinition[]
): CheckpointDescriptor[] {
  const checkpoints: CheckpointDescriptor[] = []
  const totalWeeks = phase_definitions.reduce((sum, p) => sum + p.weeks, 0)

  // Benchmark every 8-12 weeks
  for (let week = 8; week <= totalWeeks; week += 10) {
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
  for (let week = 4; week <= totalWeeks; week += 4) {
    checkpoints.push({
      type: 'progress_review',
      week_number: week,
      target_date: computeDateForWeek(week),
      target_metric: 'consistency_signal',
      session_type: 'easy_run',
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
| calibration | Only if fitness metrics need re-estimation (coach-triggered) |

---

## Cross-References

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseDefinition, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_definitions, weekly_distributions, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for maintenance mode
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
