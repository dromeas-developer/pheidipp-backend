# Plan Generation — Fitness Improvement Mode
*Objective-driven rolling blocks with phase definitions construction from seeded objectives.*

---

## Purpose

- Defines the deterministic phase definitions construction for fitness_improvement mode
- Phase definitions are constructed from the athlete's seeded objectives using `OBJECTIVE_TO_PHASE` mapping
- Block duration (6–12 weeks) is computed from objective count and twin confidence
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Objective-to-Phase Mapping

Each objective category maps to a phase label, distribution template, and set of relevant session types:

```typescript
const OBJECTIVE_TO_PHASE: Record<ObjectiveCategory, {
  phase_label: PhaseLabel
  primary_focus: string
  distribution: {
    low_aerobic: number
    high_aerobic: number
    threshold: number
    vo2max: number
    neuromuscular: number
  }
  specificity: number
  relevant_session_types: SessionType[]
}> = {
  aerobic_base: {
    phase_label: 'aerobic_base',
    primary_focus: 'Aerobic foundation development',
    distribution: { low_aerobic: 0.75, high_aerobic: 0.15, threshold: 0.05, vo2max: 0.03, neuromuscular: 0.02 },
    specificity: 0.1,
    relevant_session_types: ['easy_run', 'long_run', 'recovery_run']
  },
  threshold_quality: {
    phase_label: 'threshold_build',
    primary_focus: 'Threshold capacity development',
    distribution: { low_aerobic: 0.55, high_aerobic: 0.15, threshold: 0.20, vo2max: 0.05, neuromuscular: 0.05 },
    specificity: 0.3,
    relevant_session_types: ['threshold', 'tempo', 'fartlek']
  },
  structural_tolerance: {
    phase_label: 'hill_phase',
    primary_focus: 'Structural resilience building',
    distribution: { low_aerobic: 0.65, high_aerobic: 0.15, threshold: 0.10, vo2max: 0.05, neuromuscular: 0.05 },
    specificity: 0.2,
    relevant_session_types: ['easy_run', 'long_run', 'hill_repeats']
  },
  pacing_discipline: {
    phase_label: 'specific_endurance',
    primary_focus: 'Pacing consistency under fatigue',
    distribution: { low_aerobic: 0.50, high_aerobic: 0.15, threshold: 0.20, vo2max: 0.05, neuromuscular: 0.10 },
    specificity: 0.7,
    relevant_session_types: ['threshold', 'tempo', 'long_run']
  },
  neuromuscular_sharpness: {
    phase_label: 'vo2max_development',
    primary_focus: 'Neuromuscular activation and speed',
    distribution: { low_aerobic: 0.50, high_aerobic: 0.10, threshold: 0.15, vo2max: 0.15, neuromuscular: 0.10 },
    specificity: 0.4,
    relevant_session_types: ['vo2max', 'strides', 'hill_repeats']
  },
  durability: {
    phase_label: 'aerobic_build',
    primary_focus: 'Sustained effort capacity',
    distribution: { low_aerobic: 0.60, high_aerobic: 0.20, threshold: 0.10, vo2max: 0.05, neuromuscular: 0.05 },
    specificity: 0.5,
    relevant_session_types: ['long_run', 'steady_state', 'medium_long_run']
  },
  intensity_distribution: {
    phase_label: 'rolling_block',
    primary_focus: 'Training load balance',
    distribution: { low_aerobic: 0.60, high_aerobic: 0.15, threshold: 0.15, vo2max: 0.05, neuromuscular: 0.05 },
    specificity: 0.3,
    relevant_session_types: ['easy_run', 'threshold', 'vo2max']
  },
  recovery_efficiency: {
    phase_label: 'rolling_block',
    primary_focus: 'Recovery and adaptation optimisation',
    distribution: { low_aerobic: 0.80, high_aerobic: 0.10, threshold: 0.05, vo2max: 0.03, neuromuscular: 0.02 },
    specificity: 0.1,
    relevant_session_types: ['recovery_run', 'easy_run', 'rest']
  },
  intensity_compliance: {
    phase_label: 'rolling_block',
    primary_focus: 'Intensity discipline and targeting',
    distribution: { low_aerobic: 0.60, high_aerobic: 0.15, threshold: 0.15, vo2max: 0.05, neuromuscular: 0.05 },
    specificity: 0.3,
    relevant_session_types: ['threshold', 'tempo', 'easy_run']
  }
}
```

---

## Mesocycle Duration Computation

Mesocycle duration is computed from the objective set and twin confidence level, clamped to 6–12 weeks:

```typescript
function computeMesocycleWeeks(
  objectives: Objective[],
  confidence: TwinConfidenceLevel
): number {
  const phase_groups = groupObjectivesByPhase(objectives)
  const base_weeks = phase_groups.length * 3  // ~3 weeks per phase group

  const confidence_adjustment: Record<TwinConfidenceLevel, number> = {
    low: +2,      // more time for data accumulation
    medium: 0,    // standard
    high: -1      // can move faster
  }

  return clamp(base_weeks + confidence_adjustment[confidence], 6, 12)
}
```

---

## Phase Arc Construction from Objectives

The block is divided into phase groups based on objective clustering. Objectives mapping to the same phase label are grouped together. Each phase group receives 2–4 weeks, with an integration phase at the end that consolidates across all objectives.

```typescript
function buildFitnessImprovementPhases(
  objectives: Objective[],
  total_weeks: number,
  twin_state: TwinState
): PhaseDefinition[] {

  // Group objectives by phase compatibility
  // aerobic_base + structural_tolerance + durability = aerobic_base phase
  // threshold_quality + pacing_discipline + neuromuscular_sharpness = threshold_build phase
  // Others are rolling_block (distributed across the plan)

  const phase_groups = groupObjectivesByPhase(objectives)

  // Distribute weeks across phase groups based on:
  // 1. Number of objectives in each group
  // 2. Confidence level (LOW → more time for base; HIGH → faster progression)
  // 3. Gap severity (larger gaps → more time)

  const week_allocation = allocateWeeks(phase_groups, total_weeks, twin_state)

  // Build PhaseDefinition for each phase group
  return week_allocation.map(group => {
    const group_objectives = group.objectives.map(o => o.category as ObjectiveCategory)
    const template = OBJECTIVE_TO_PHASE[group_objectives[0]]
    
    return {
      phase: group.phase_label,
      objective: group_objectives,
      weeks: group.weeks,
      distribution: template.distribution,
      specificity: template.specificity,
      approach: group.weeks > 4 ? 'undulating' : 'linear',
      recovery_cycle: group.weeks > 6 ? 'moderate' : 'infrequent'
    }
  })
}
```

---

## Mesocycle Structure

A mesocycle is 6–12 weeks organised into three phase groups:

```
Mesocycle N (6-12 weeks, computed from objectives and confidence level)
  ├── Phase Group 1: Addresses objective group A (2-4 weeks)
  │   ├── Week 1-2: Introduction / adaptation
  │   └── Week 3-4: Development / consolidation
  ├── Phase Group 2: Addresses objective group B (2-3 weeks)
  │   ├── Week 5-6: Introduction / adaptation
  │   └── Week 7: Development / consolidation
  └── Phase Group 3: Integration (1-2 weeks)
      └── Week 8: Consolidation across all objectives
      → Mesocycle N+1 begins with adjusted objectives based on Mesocycle N outcomes
```

---

## Checkpoint Scheduling (Objective-Targeted)

Checkpoints in fitness improvement mode are driven by objectives, not race calendar:

```typescript
function generateObjectiveCheckpoints(
  objectives: Objective[],
  phase_definitions: PhaseDefinition[]
): CheckpointDescriptor[] {
  const checkpoints: CheckpointDescriptor[] = []
  const totalWeeks = phase_definitions.reduce((sum, p) => sum + p.weeks, 0)

  // 1. Calibration checkpoints for confidence gaps
  const confidence_gaps = identifyConfidenceGaps(twin_state)
  for (const gap of confidence_gaps) {
    if (gap.priority === 'high') {
      const target_week = findWeekForMetric(phase_definitions, gap.metric)
      checkpoints.push({
        type: 'calibration',
        week_number: target_week,
        target_date: computeDateForWeek(target_week),
        target_metric: gap.metric,
        session_type: deriveCalibrationSessionType(gap.metric),
        planner_message: `Calibrate your ${gap.metric} estimate — this session helps refine the twin's understanding of your ${gap.metric}`
      })
    }
  }

  // 2. Benchmark checkpoints at phase transitions
  let running_week = 0
  for (let i = 1; i < phase_definitions.length; i++) {
    running_week += phase_definitions[i - 1].weeks
    const relevant_objectives = objectives.filter(o =>
      phase_definitions[i].objective.includes(o.category as ObjectiveCategory)
    )
    if (relevant_objectives.length > 0) {
      checkpoints.push({
        type: 'benchmark',
        week_number: running_week,
        target_date: computeDateForWeek(running_week),
        target_objective_id: relevant_objectives[0]?.id,
        target_metric: deriveObjectiveMetric(relevant_objectives[0]),
        session_type: deriveBenchmarkSessionType(relevant_objectives[0]),
        planner_message: `Assess your ${relevant_objectives.map(o => o.title).join(', ')} objective — this session measures whether your development is on track`
      })
    }
  }

  // 3. Progress review checkpoints every 3-4 weeks
  for (let week = 4; week <= totalWeeks; week += 3) {
    checkpoints.push({
      type: 'progress_review',
      week_number: week,
      target_date: computeDateForWeek(week),
      target_metric: 'adaptation_signal',
      session_type: 'easy',  // non-disruptive
      planner_message: `Weekly progress review — checking in on your overall training response`
    })
  }

  return checkpoints
}
```

Checkpoint types and scheduling:

| Type | Scheduling |
|---|---|
| calibration | When confidence gaps exist for metrics that affect training targets |
| benchmark | At each phase transition within a block (end of base → start of threshold) |
| progress_review | Every 3-4 weeks |

---

## Checkpoint Completion Flow (Fitness Improvement)

Extends the base `CheckpointCompletionResult` with objective tracking:

```typescript
type CheckpointCompletionResult = {
  metric_updated: boolean
  confidence_changed: boolean
  new_confidence_level?: 'low' | 'medium' | 'high'
  objective_progressed: boolean
  replan_triggered: boolean
}

function processCheckpointCompletion(
  checkpoint: Checkpoint,
  session: PlannedSession,
  activity: Activity,
  objectives: Objective[]
): CheckpointCompletionResult {
  // 1. Analyse activity data against checkpoint.target_metric
  // 2. Update twin state if metric changed materially
  // 3. Check if confidence level changed
  // 4. Check if relevant objective progressed
  // 5. If confidence changed significantly OR objective achieved, trigger replanning
  // 6. Return result for event payload
}
```

---

## Volume Progression

Weekly volume increase is capped and adjusted by confidence and sport background:

```typescript
function computeWeeklyVolumeIncrease(
  current_week: number,
  confidence: TwinConfidenceLevel,
  sport_background: SportBackground
): number {
  const BASE_INCREASE = 0.10  // 10% weekly cap

  const confidence_adjustment: Record<TwinConfidenceLevel, number> = {
    low: 0.7,      // conservative when LOW confidence
    medium: 1.0,   // standard
    high: 1.2      // can be more aggressive
  }

  const sport_adjustment: Record<SportBackground, number> = {
    running_primary: 1.0,
    crossover: 0.7,   // structural ramp (existing rule)
    multi_sport: 0.9
  }

  return BASE_INCREASE * confidence_adjustment[confidence] * sport_adjustment[sport_background]
}
```

---

## Intensity Progression

Uses the existing `computeIntensityAllocation()` from adaptation yield. Default hard percentage is 15–20% (vs. 5–10% for maintenance), adjusted by adaptation signature yield when available:

```typescript
function computeIntensityAllocation(
  yield_by_intent: YieldByIntentState,
  default_hard_percentage: number  // from strategic framework (e.g. 0.15)
): number {
  // Same logic as race mode
  // Floor: 5% hard training minimum
  // Ceiling: strategic framework's original allocation
}
```

---

## Early Achievement Handling

When all objectives are achieved mid-mesocycle, the next mesocycle is seeded immediately:

```typescript
function handleEarlyAchievement(
  objectives: Objective[],
  current_week: number,
  mesocycle_end_week: number
): { action: 'continue' | 'renew_early'; new_objectives?: Objective[] } {
  const all_achieved = objectives.every(o => o.status === 'achieved')

  if (all_achieved && current_week < mesocycle_end_week) {
    // All objectives achieved before mesocycle ends
    // Seed new objectives immediately and start next mesocycle
    return { action: 'renew_early' }
  }

  return { action: 'continue' }
}
```

---

## Mesocycle Renewal

When a mesocycle completes, achieved objectives are replaced and the next mesocycle is constructed from the combined set:

```typescript
function renewMesocycle(
  athlete_id: string,
  completed_mesocycle: MesocycleSummary,
  current_twin: TwinState
): { next_mesocycle: PhaseArcEntry[]; new_objectives: Objective[]; carried_objectives: Objective[] } {

  // 1. Evaluate which objectives were achieved
  const all_objectives = getActiveObjectives(athlete_id)
  const achieved = all_objectives.filter(o => o.status === 'achieved')
  const remaining = all_objectives.filter(o => o.status === 'active')

  // 2. Seed new objectives to replace achieved ones
  const new_objectives = ObjectiveSeedingService.seedObjectives({
    twin_state: current_twin,
    execution_observations: getRecentObservations(athlete_id),
    athlete_preferences: getPreferences(athlete_id),
    training_goal: getActiveGoal(athlete_id)
  })

  // 3. Combine remaining + new (max 5 active)
  const combined = [...remaining, ...new_objectives].slice(0, 5)

  // 4. Build next mesocycle from combined objectives
  const next_mesocycle = buildFitnessImprovementArc(combined, MESOCYCLE_SIZE_WEEKS, current_twin)

  return { next_mesocycle, new_objectives, carried_objectives: remaining }
}
```

---

## Regeneration Triggers (Fitness Improvement)

| Trigger | Condition |
|---|---|
| mesocycle_completed | Normal mesocycle renewal |
| progress_plateau | 2+ consecutive mesocycles with no metric improvement |
| confidence_upgrade | LOW→MEDIUM or MEDIUM→HIGH |
| persistent_disruption | >20% missed over 3 weeks |

---

## Cross-References

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseDefinition, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **Objective entity:** `01-entities/objective.md` — Objective and ObjectiveUpdate schemas, seeding rules
- **Objective management:** `02-computations/objective-management.md` — ObjectiveSeedingService.seedObjectives(), post-session evaluation
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_definitions, weekly_distributions, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for fitness improvement mode
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
