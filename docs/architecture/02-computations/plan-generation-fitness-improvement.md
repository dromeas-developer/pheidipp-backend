# Plan Generation — Fitness Improvement Mode
*Objective-driven rolling blocks with phase arc construction from seeded objectives.*

---

## Purpose

- Defines the deterministic phase arc construction for fitness_improvement mode
- Phase arc is constructed from the athlete's seeded objectives using `OBJECTIVE_TO_PHASE` mapping
- Block duration (6–12 weeks) is computed from objective count and twin confidence
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Objective-to-Phase Mapping

Each objective category maps to a phase label, primary focus, intensity bias, and set of relevant session types:

```typescript
const OBJECTIVE_TO_PHASE: Record<ObjectiveCategory, {
  phase_label: PhaseLabel
  primary_focus: string
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  relevant_session_types: SessionType[]
}> = {
  aerobic_base: {
    phase_label: 'base_building',
    primary_focus: 'Aerobic foundation development',
    intensity_bias: 'easy',
    relevant_session_types: ['easy', 'long_run', 'recovery_run']
  },
  threshold_quality: {
    phase_label: 'threshold_development',
    primary_focus: 'Threshold capacity development',
    intensity_bias: 'quality',
    relevant_session_types: ['threshold', 'tempo', 'fartlek']
  },
  structural_tolerance: {
    phase_label: 'base_building',
    primary_focus: 'Structural resilience building',
    intensity_bias: 'moderate',
    relevant_session_types: ['easy', 'long_run', 'hill_repeats']
  },
  pacing_discipline: {
    phase_label: 'threshold_development',
    primary_focus: 'Pacing consistency under fatigue',
    intensity_bias: 'quality',
    relevant_session_types: ['threshold', 'tempo', 'race_pace']
  },
  neuromuscular_sharpness: {
    phase_label: 'threshold_development',
    primary_focus: 'Neuromuscular activation and speed',
    intensity_bias: 'quality',
    relevant_session_types: ['vo2max', 'strides', 'hill_repeats']
  },
  durability: {
    phase_label: 'base_building',
    primary_focus: 'Sustained effort capacity',
    intensity_bias: 'moderate',
    relevant_session_types: ['long_run', 'steady_state', 'medium_long_run']
  },
  intensity_distribution: {
    phase_label: 'rolling_block',
    primary_focus: 'Training load balance',
    intensity_bias: 'balanced',
    relevant_session_types: ['easy', 'threshold', 'vo2max']
  },
  recovery_efficiency: {
    phase_label: 'rolling_block',
    primary_focus: 'Recovery and adaptation optimisation',
    intensity_bias: 'easy',
    relevant_session_types: ['recovery_run', 'easy', 'rest']
  },
  zone_compliance: {
    phase_label: 'rolling_block',
    primary_focus: 'Intensity discipline and targeting',
    intensity_bias: 'balanced',
    relevant_session_types: ['threshold', 'tempo', 'easy']
  }
}
```

---

## Block Duration Computation

Block duration is computed from the objective set and twin confidence level, clamped to 6–12 weeks:

```typescript
function computeBlockWeeks(
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
function buildFitnessImprovementArc(
  objectives: Objective[],
  total_weeks: number,
  twin_state: TwinState
): PhaseArcEntry[] {

  // Group objectives by phase compatibility
  // aerobic_base + structural_tolerance + durability = base_building phase
  // threshold_quality + pacing_discipline + neuromuscular_sharpness = threshold_development phase
  // Others are rolling_block (distributed across the plan)

  const phase_groups = groupObjectivesByPhase(objectives)

  // Distribute weeks across phase groups based on:
  // 1. Number of objectives in each group
  // 2. Confidence level (LOW → more time for base; HIGH → faster progression)
  // 3. Gap severity (larger gaps → more time)

  const week_allocation = allocateWeeks(phase_groups, total_weeks, twin_state)

  // Build PhaseArcEntry for each week
  return week_allocation.flatMap(group =>
    Array.from({ length: group.weeks }, (_, i) => ({
      week_number: group.start_week + i,
      phase_label: group.phase_label,
      methodology: deriveMethodology(group),
      physiological_emphasis: group.objectives.map(o => o.title).join('; '),
      intensity_bias: group.intensity_bias,
      checkpoint_intent: i === group.weeks - 1
        ? `Assess progress on ${group.objectives.map(o => o.title).join(', ')}`
        : undefined,
      target_session_count: deriveSessionCount(group, twin_state)
    }))
  )
}
```

---

## Block Structure

A block is 6–12 weeks organised into three phase groups:

```
Block N (6-12 weeks, computed from objectives and confidence level)
  ├── Phase Group 1: Addresses objective group A (2-4 weeks)
  │   ├── Week 1-2: Introduction / adaptation
  │   └── Week 3-4: Development / consolidation
  ├── Phase Group 2: Addresses objective group B (2-3 weeks)
  │   ├── Week 5-6: Introduction / adaptation
  │   └── Week 7: Development / consolidation
  └── Phase Group 3: Integration (1-2 weeks)
      └── Week 8: Consolidation across all objectives
      → Block N+1 begins with adjusted objectives based on Block N outcomes
```

---

## Checkpoint Scheduling (Objective-Targeted)

Checkpoints in fitness improvement mode are driven by objectives, not race calendar:

```typescript
function generateObjectiveCheckpoints(
  objectives: Objective[],
  phase_arc: PhaseArcEntry[]
): CheckpointDescriptor[] {
  const checkpoints: CheckpointDescriptor[] = []

  // 1. Calibration checkpoints for confidence gaps
  const confidence_gaps = identifyConfidenceGaps(twin_state)
  for (const gap of confidence_gaps) {
    if (gap.priority === 'high') {
      const target_week = findWeekForMetric(phase_arc, gap.metric)
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
  for (let i = 1; i < phase_arc.length; i++) {
    if (phase_arc[i].phase_label !== phase_arc[i-1].phase_label) {
      const relevant_objectives = objectives.filter(o =>
        OBJECTIVE_TO_PHASE[o.category].phase_label === phase_arc[i].phase_label
      )
      checkpoints.push({
        type: 'benchmark',
        week_number: phase_arc[i].week_number,
        target_date: computeDateForWeek(phase_arc[i].week_number),
        target_objective_id: relevant_objectives[0]?.id,
        target_metric: deriveObjectiveMetric(relevant_objectives[0]),
        session_type: deriveBenchmarkSessionType(relevant_objectives[0]),
        planner_message: `Assess your ${relevant_objectives.map(o => o.title).join(', ')} objective — this session measures whether your development is on track`
      })
    }
  }

  // 3. Progress review checkpoints every 3-4 weeks
  for (let week = 4; week <= phase_arc.length; week += 3) {
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

When all objectives are achieved mid-block, the next block is seeded immediately:

```typescript
function handleEarlyAchievement(
  objectives: Objective[],
  current_week: number,
  block_end_week: number
): { action: 'continue' | 'renew_early'; new_objectives?: Objective[] } {
  const all_achieved = objectives.every(o => o.status === 'achieved')

  if (all_achieved && current_week < block_end_week) {
    // All objectives achieved before block ends
    // Seed new objectives immediately and start next block
    return { action: 'renew_early' }
  }

  return { action: 'continue' }
}
```

---

## Block Renewal

When a block completes, achieved objectives are replaced and the next block is constructed from the combined set:

```typescript
function renewBlock(
  athlete_id: string,
  completed_block: BlockSummary,
  current_twin: TwinState
): { next_block: PhaseArcEntry[]; new_objectives: Objective[]; carried_objectives: Objective[] } {

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

  // 4. Build next block from combined objectives
  const next_block = buildFitnessImprovementArc(combined, BLOCK_SIZE_WEEKS, current_twin)

  return { next_block, new_objectives, carried_objectives: remaining }
}
```

---

## Regeneration Triggers (Fitness Improvement)

| Trigger | Condition |
|---|---|
| block_completed | Normal block renewal |
| progress_plateau | 2+ consecutive blocks with no metric improvement |
| confidence_upgrade | LOW→MEDIUM or MEDIUM→HIGH |
| persistent_disruption | >20% missed over 3 weeks |

---

## Cross-References

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseArcEntry, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **Objective entity:** `01-entities/objective.md` — Objective and ObjectiveUpdate schemas, seeding rules
- **Objective management:** `02-computations/objective-management.md` — ObjectiveSeedingService.seedObjectives(), post-session evaluation
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_arc, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for fitness improvement mode
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
