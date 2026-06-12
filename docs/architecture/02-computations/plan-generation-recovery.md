# Plan Generation — Recovery Mode

- Defines the deterministic phase definitions construction for recovery mode
- Phase transitions are gated by healing assessment, not calendar time
- Setback detection and mode transition based on twin confidence
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Phase Definitions Construction

```typescript
function computeRecoveryPhases(
  injury_severity: InjurySeverity,
  athlete_preferences: AthletePreferences,
  pre_injury_baseline: TrainingBaseline
): PhaseDefinition[] {
  const PHASE_DURATIONS: Record<InjurySeverity, { phase1: number; phase2: number }> = {
    minor: { phase1: 1, phase2: 1 },
    moderate: { phase1: 1.5, phase2: 1.5 },
    major: { phase1: 2, phase2: 2 }
  }

  const durations = PHASE_DURATIONS[injury_severity]

  return [
    // Phase 1: Minimal Load
    {
      phase: 'recovery',
      objective: ['recovery_efficiency'],
      weeks: Math.ceil(durations.phase1),
      distribution: {
        low_aerobic: 0.90,
        high_aerobic: 0.05,
        threshold: 0.03,
        vo2max: 0.0,
        neuromuscular: 0.02
      },
      specificity: 0.0,
      approach: 'linear',
      recovery_cycle: 'frequent'
    },
    // Phase 2: Gradual Return
    {
      phase: 'recovery',
      objective: ['recovery_efficiency', 'structural_tolerance'],
      weeks: Math.ceil(durations.phase2),
      distribution: {
        low_aerobic: 0.70,
        high_aerobic: 0.15,
        threshold: 0.10,
        vo2max: 0.03,
        neuromuscular: 0.02
      },
      specificity: 0.0,
      approach: 'linear',
      recovery_cycle: 'moderate'
    },
    // Phase 3: Transition
    {
      phase: 'rolling_block',
      objective: ['aerobic_base'],
      weeks: 1,
      distribution: {
        low_aerobic: 0.55,
        high_aerobic: 0.20,
        threshold: 0.15,
        vo2max: 0.05,
        neuromuscular: 0.05
      },
      specificity: 0.0,
      approach: 'linear',
      recovery_cycle: 'infrequent'
    }
  ]
}
```

Phase transitions are driven by healing state, not calendar time. The function returns 3 phases (minimal load → gradual return → transition), but in practice the deterministic expansion will extend each phase to fill the required weeks based on injury severity.

---

## Checkpoint Scheduling (Healing-Focused)

```typescript
function generateRecoveryCheckpoints(
  phase_definitions: PhaseDefinition[],
  injury_severity: InjurySeverity
): CheckpointDescriptor[] {
  const checkpoints: CheckpointDescriptor[] = []
  const totalWeeks = phase_definitions.reduce((sum, p) => sum + p.weeks, 0)
  const PHASE_DURATIONS = { minor: 1, moderate: 1.5, major: 2 }

  // Progress review at Phase 1→2 transition
  checkpoints.push({
    type: 'progress_review',
    week_number: Math.ceil(PHASE_DURATIONS[injury_severity]) + 1,
    target_date: computeDateForWeek(Math.ceil(PHASE_DURATIONS[injury_severity]) + 1),
    target_metric: 'healing_signal',
    session_type: 'easy_run',
    planner_message: `Healing assessment — checking whether you're ready to increase load`
  })

  // Progress review at Phase 2→3 transition
  checkpoints.push({
    type: 'progress_review',
    week_number: Math.ceil(PHASE_DURATIONS[injury_severity] * 2) + 1,
    target_date: computeDateForWeek(Math.ceil(PHASE_DURATIONS[injury_severity] * 2) + 1),
    target_metric: 'healing_signal',
    session_type: 'easy_run',
    planner_message: `Recovery progress check — assessing readiness to resume normal training`
  })

  // Calibration at Phase 3 transition
  checkpoints.push({
    type: 'calibration',
    week_number: totalWeeks,
    target_date: computeDateForWeek(totalWeeks),
    target_metric: 'primary_threshold',
    session_type: 'test_session',
    planner_message: `Post-recovery calibration — verifying your threshold estimates after the recovery period`
  })

  return checkpoints
}
```

Checkpoint types and scheduling:

| Type | Scheduling |
|---|---|
| progress_review | At each phase transition (Phase 1→2, Phase 2→3) |
| calibration | At Phase 3 transition (end of recovery) |

---

## Mode Transition Rules

Recovery mode transitions to another mode when:

1. **Healing is complete** (all healing phases passed checkpoint)
2. **Twin confidence** reaches a level where structured training can resume
3. **The athlete's goal** determines which mode to transition to (race_event, fitness_improvement, or maintenance)

The mode transition is NOT automatic — it requires coach decision (the planner agent recommends, the coach decides).

---

## Cross-References

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseDefinition, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_definitions, weekly_distributions, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for recovery mode
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
