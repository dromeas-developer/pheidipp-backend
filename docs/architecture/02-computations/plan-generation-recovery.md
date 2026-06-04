# Plan Generation — Recovery Mode
*Severity-driven 3-phase arc with healing assessment gating phase transitions.*

---

## Purpose

- Defines the deterministic phase arc construction for recovery mode
- Phase transitions are gated by healing assessment, not calendar time
- Setback detection and mode transition based on twin confidence
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Phase Arc Construction

```typescript
function computeRecoveryArc(
  injury_severity: InjurySeverity,
  athlete_preferences: AthletePreferences,
  pre_injury_baseline: TrainingBaseline
): PhaseArcEntry[] {
  const PHASE_DURATIONS: Record<InjurySeverity, { phase1: number; phase2: number }> = {
    minor: { phase1: 1, phase2: 1 },
    moderate: { phase1: 1.5, phase2: 1.5 },
    major: { phase1: 2, phase2: 2 }
  }

  const durations = PHASE_DURATIONS[injury_severity]
  const total_weeks = durations.phase1 + durations.phase2 + 1  // +1 for transition

  return Array.from({ length: total_weeks }, (_, i) => {
    const week = i + 1

    if (week <= durations.phase1) {
      // Phase 1: Minimal Load
      return {
        week_number: week,
        phase_label: 'recovery',
        methodology: {
          high_aerobic_volume: 0.3,
          low_intensity_dominant: 0.9,
          threshold_density: 0.0,
          high_intensity_sparse: 0.0,
          high_frequency: 0.3,
          structural_durability: 0.2,
          race_specificity: 0.0,
          variety_emphasis: 0.1,
          neuromuscular_support: 0.0,
          conservative_progression: 0.9
        },
        physiological_emphasis: 'Minimal load — healing and monitoring',
        intensity_bias: 'easy',
        target_session_count: 3
      }
    }

    if (week <= durations.phase1 + durations.phase2) {
      // Phase 2: Gradual Return
      const phase2_week = week - durations.phase1
      const volume_pct = 0.50 + (phase2_week * 0.125)  // 50% → 75% over phase 2
      const introduce_intensity = phase2_week > durations.phase2 / 2

      return {
        week_number: week,
        phase_label: 'recovery',
        methodology: {
          high_aerobic_volume: 0.5,
          low_intensity_dominant: 0.7,
          threshold_density: introduce_intensity ? 0.3 : 0.0,
          high_intensity_sparse: 0.0,
          high_frequency: 0.4,
          structural_durability: 0.3,
          race_specificity: 0.0,
          variety_emphasis: 0.2,
          neuromuscular_support: 0.0,
          conservative_progression: 0.8
        },
        physiological_emphasis: `Gradual return — ${Math.round(volume_pct * 100)}% of baseline volume`,
        intensity_bias: introduce_intensity ? 'moderate' : 'easy',
        target_session_count: 4
      }
    }

    // Phase 3: Transition
    return {
      week_number: week,
      phase_label: 'rolling_block',
      methodology: {
        high_aerobic_volume: 0.6,
        low_intensity_dominant: 0.6,
        threshold_density: 0.4,
        high_intensity_sparse: 0.1,
        high_frequency: 0.5,
        structural_durability: 0.4,
        race_specificity: 0.0,
        variety_emphasis: 0.3,
        neuromuscular_support: 0.1,
        conservative_progression: 0.6
      },
      physiological_emphasis: 'Transition — resuming normal training patterns',
      intensity_bias: 'balanced',
      target_session_count: athlete_preferences.preferred_sessions_per_week
    }
  })
}
```

---

## Phase Structure

```
Phase 1: Minimal Load (injury_severity-dependent duration)
  ├── Volume: 30-50% of pre-injury baseline
  ├── Intensity: easy only (below LT1)
  ├── Sessions per week: 3-4 (reduced from normal)
  ├── Session types: easy_run, recovery_run, rest
  └── Monitoring: wellness signals, athlete-reported comfort

Phase 2: Gradual Return (injury_severity-dependent duration)
  ├── Week 1: Volume 50-60% baseline, introduce moderate effort
  ├── Week 2: Volume 60-75% baseline, introduce threshold if healing markers OK
  ├── Sessions per week: 4-5 (gradually increasing)
  └── Session types: easy_run, long_run, threshold (in second half)

Phase 3: Transition
  ├── Volume: 75-90% baseline
  ├── Session types: normal session types resume
  ├── Checkpoint: calibration to verify threshold estimates
  └── Propose mode transition
```

---

## Checkpoint Scheduling (Healing-Focused)

```typescript
function generateRecoveryCheckpoints(
  phase_arc: PhaseArcEntry[],
  injury_severity: InjurySeverity
): CheckpointDescriptor[] {
  const checkpoints: CheckpointDescriptor[] = []
  const PHASE_DURATIONS = { minor: 1, moderate: 1.5, major: 2 }

  // Progress review at Phase 1→2 transition
  checkpoints.push({
    type: 'progress_review',
    week_number: Math.ceil(PHASE_DURATIONS[injury_severity]) + 1,
    target_date: computeDateForWeek(Math.ceil(PHASE_DURATIONS[injury_severity]) + 1),
    target_metric: 'healing_signal',
    session_type: 'easy',
    planner_message: `Healing assessment — checking whether you're ready to increase load`
  })

  // Progress review at Phase 2→3 transition
  checkpoints.push({
    type: 'progress_review',
    week_number: Math.ceil(PHASE_DURATIONS[injury_severity] * 2) + 1,
    target_date: computeDateForWeek(Math.ceil(PHASE_DURATIONS[injury_severity] * 2) + 1),
    target_metric: 'healing_signal',
    session_type: 'easy',
    planner_message: `Recovery progress check — assessing readiness to resume normal training`
  })

  // Calibration at Phase 3 transition
  checkpoints.push({
    type: 'calibration',
    week_number: phase_arc.length,
    target_date: computeDateForWeek(phase_arc.length),
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
| calibration | At Phase 3 transition |

---

## Phase 1 Configuration (Minimal Load)

```typescript
const PHASE1_CONFIG: Record<InjurySeverity, {
  volume_pct_range: [number, number]
  sessions_per_week: number
  intensity_ceiling: 'easy'
}> = {
  minor: { volume_pct_range: [0.40, 0.50], sessions_per_week: 4, intensity_ceiling: 'easy' },
  moderate: { volume_pct_range: [0.35, 0.45], sessions_per_week: 3, intensity_ceiling: 'easy' },
  major: { volume_pct_range: [0.30, 0.40], sessions_per_week: 3, intensity_ceiling: 'easy' }
}
```

---

## Phase 2 Configuration (Gradual Return)

```typescript
function computePhase2WeekConfig(
  phase2_week: number,
  phase2_total_weeks: number,
  injury_severity: InjurySeverity
): { volume_pct: number; introduce_intensity: boolean } {
  const base_volume = injury_severity === 'minor' ? 0.50 : injury_severity === 'moderate' ? 0.45 : 0.40
  const weekly_increase = 0.125  // 12.5% per week

  const volume_pct = Math.min(base_volume + (phase2_week * weekly_increase), 0.75)
  const introduce_intensity = phase2_week > phase2_total_weeks / 2

  return { volume_pct, introduce_intensity }
}
```

---

## Healing Assessment

```typescript
type HealingAssessment = {
  wellness_baseline_returned: boolean     // wellness signals back to athlete's own baseline
  comfort_reported: boolean               // athlete reports no discomfort (if pain tracking implemented)
  consecutive_green_days: number          // GREEN recovery modifier for N days
  volume_tolerance: boolean               // completed Phase 2 load without setback
}

function assessHealing(
  athlete_id: string,
  lookback_days: number
): HealingAssessment {
  const wellness = getWellnessHistory(athlete_id, lookback_days)
  const recovery_modifiers = getRecoveryModifierHistory(athlete_id, lookback_days)

  return {
    wellness_baseline_returned: checkWellnessBaselineReturn(wellness),
    comfort_reported: true,  // placeholder — depends on pain tracking implementation
    consecutive_green_days: countConsecutiveGreen(recovery_modifiers),
    volume_tolerance: checkVolumeTolerance(athlete_id)
  }
}
```

---

## Phase Transition Criteria

Phase transitions are gated by healing assessment, not calendar time:

```typescript
function canTransitionPhase(
  current_phase: 'phase1' | 'phase2' | 'phase3',
  healing: HealingAssessment,
  injury_severity: InjurySeverity
): { can_transition: boolean; reason: string } {

  if (current_phase === 'phase1') {
    // Phase 1→2: wellness signals returned to baseline for 7+ consecutive days
    if (healing.consecutive_green_days >= 7) {
      return { can_transition: true, reason: 'Wellness signals stable — ready to increase load' }
    }
    return { can_transition: false, reason: 'Recovery signals not yet stable' }
  }

  if (current_phase === 'phase2') {
    // Phase 2→3: completed Phase 2 without setback + volume at 75%+ baseline
    if (healing.volume_tolerance && healing.consecutive_green_days >= 5) {
      return { can_transition: true, reason: 'Load tolerance confirmed — ready to resume normal training' }
    }
    return { can_transition: false, reason: 'Still assessing load tolerance' }
  }

  // Phase 3→mode transition
  return { can_transition: true, reason: 'Recovery complete' }
}
```

---

## Setback Detection

```typescript
function detectSetback(
  athlete_id: string,
  lookback_days: number
): { setback_detected: boolean; severity: 'minor' | 'major'; action: string } {
  const wellness = getWellnessHistory(athlete_id, lookback_days)
  const recovery_modifiers = getRecoveryModifierHistory(athlete_id, lookback_days)

  // Check for wellness degradation
  const recent_trend = computeWellnessTrend(wellness.slice(-7))
  const prior_trend = computeWellnessTrend(wellness.slice(-14, -7))

  if (recent_trend < prior_trend - 0.5) {
    return {
      setback_detected: true,
      severity: recent_trend < prior_trend - 1.0 ? 'major' : 'minor',
      action: recent_trend < prior_trend - 1.0
        ? 'Extend Phase 1 by 1 week, reduce volume by 20%'
        : 'Maintain current phase, monitor closely'
    }
  }

  return { setback_detected: false, severity: 'minor', action: '' }
}
```

---

## Transition Detection

When recovery is complete, the target mode depends on twin confidence:

```typescript
function shouldTransitionFromRecovery(
  athlete_id: string,
  healing: HealingAssessment,
  injury_severity: InjurySeverity,
  twin_state: TwinState
): { should_transition: boolean; target_mode: GoalType; reason: string } {

  // Check healing completeness
  const phase3_criteria = {
    wellness_baseline_returned: healing.wellness_baseline_returned,
    consecutive_green_days: healing.consecutive_green_days >= 5,
    volume_tolerance: healing.volume_tolerance
  }

  const all_criteria_met = Object.values(phase3_criteria).every(Boolean)

  if (!all_criteria_met) {
    return { should_transition: false, target_mode: 'recovery', reason: 'Recovery not yet complete' }
  }

  // Determine target mode based on confidence and readiness
  if (twin_state.confidence_level === 'low') {
    return {
      should_transition: true,
      target_mode: 'maintenance',
      reason: 'Recovery complete. Your confidence is still low — let\'s focus on consistency before progressive development.'
    }
  }

  return {
    should_transition: true,
    target_mode: 'fitness_improvement',
    reason: 'Recovery complete. You are ready for progressive development.'
  }
}
```

---

## Regeneration Triggers (Recovery)

| Trigger | Condition |
|---|---|
| setback_detected | Wellness signals degrade during recovery |
| early_recovery | Healing markers return to baseline faster than expected |
| phase_completed | Normal phase transition |
| confidence_upgrade | LOW→MEDIUM or MEDIUM→HIGH |

---

## Cross-References

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseArcEntry, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_arc, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **Wellness modifier:** `02-computations/wellness-modifier.md` — recovery modifier pipeline (GREEN/AMBER/RED)
- **Wellness baseline:** `01-entities/athlete-wellness-baseline.md` — baseline computation for healing assessment
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for recovery mode
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
