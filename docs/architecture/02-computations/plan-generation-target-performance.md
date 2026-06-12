# Plan Generation — Target Performance Mode

- Defines the full pipeline for target_performance mode: gap analysis → training length gate → objective seeding → hypothesis generation → validation → synthesis → persistence
- The athlete specifies a distance + target time; the system determines the appropriate training date via gap analysis
- Uses race-like periodisation (hypothesis generation, taper, checkpoints) but with coach-driven date authority
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Gap Analysis Pipeline

### Step 1: Estimate Current Performance

```typescript
function estimateCurrentPerformance(
  twin_state: TwinState,
  target_distance_km: number
): number {
  // Uses twin's best performance data for the target distance
  // Returns estimated time in minutes
  // Falls back to age-graded tables if insufficient data
}
```

### Step 2: Calculate Gap

```typescript
function computeGapPercentage(
  current_estimate: number,
  target_time_minutes: number
): number {
  // Returns percentage gap: ((target - current) / current) * 100
  // Negative = already ahead of target
}
```

### Step 3: Classify Gap

```typescript
type GapClassification = 'small' | 'medium' | 'large' | 'very_large'

function classifyGap(gap_percentage: number): GapClassification {
  if (gap_percentage <= 3) return 'small'
  if (gap_percentage <= 8) return 'medium'
  if (gap_percentage <= 15) return 'large'
  return 'very_large'
}
```

### Step 4: Estimate Weeks to Target

```typescript
function estimateWeeksToTarget(
  gap_percentage: number,
  fitness_level: number
): number {
  // Small gap (≤3%): 4-6 weeks
  // Medium gap (3-8%): 6-10 weeks
  // Large gap (8-15%): 10-16 weeks
  // Very large gap (>15%): handled by training length gate
}
```

### Step 5: Set Target Date

```typescript
function setTargetDate(estimated_weeks: number): string {
  // Returns YYYY-MM-DD: today + estimated_weeks
  // This becomes the goal_event_date (system-determined, not athlete-set)
}
```

---

## Training Length Gate (Target Performance Variant)

### Gate Logic

```typescript
type TargetPerformanceGateInput = {
  gap_percentage: number
  fitness_level: number
  goal_event_type: GoalEventType
  experience_level: ExperienceLevel
}

type TargetPerformanceGateResult = {
  action: 'proceed' | 'propose_fitness_improvement'
  message: string
  target_date?: string           // YYYY-MM-DD; set by system
  estimated_weeks?: number
  gate_reason?: string
}

const TARGET_PERFORMANCE_GATE_THRESHOLDS: Record<GoalEventType, Record<ExperienceLevel, number>> = {
  marathon:      { novice: 12, intermediate: 16, experienced: 20 },
  half_marathon: { novice: 10, intermediate: 14, experienced: 18 },
  '10k':         { novice: 8,  intermediate: 12, experienced: 16 },
  '5k':          { novice: 6,  intermediate: 10, experienced: 14 },
  ultra:         { novice: 16, intermediate: 20, experienced: 26 },
  trail_race:    { novice: 12, intermediate: 16, experienced: 20 },
  custom:        { novice: 12, intermediate: 16, experienced: 20 },
}

function evaluateTargetPerformanceGate(
  input: TargetPerformanceGateInput
): TargetPerformanceGateResult {
  // Small/medium/large gaps: proceed with target_performance plan
  if (input.gap_percentage <= 15) {
    const estimated_weeks = estimateWeeksToTarget(input.gap_percentage, input.fitness_level)
    const target_date = addWeeksToDate(today, estimated_weeks)
    
    return {
      action: 'proceed',
      message: `Based on your current fitness, we estimate ${estimated_weeks} weeks to reach your target. ` +
               `The plan will start on ${today} and target ${target_date}.`,
      target_date,
      estimated_weeks
    }
  }
  
  // Very large gap (>15%): propose fitness_improvement first
  const threshold = TARGET_PERFORMANCE_GATE_THRESHOLDS[input.goal_event_type]?.[input.experience_level] ?? 16
  
  return {
    action: 'propose_fitness_improvement',
    message: `The gap between your current fitness and your target is significant (${input.gap_percentage.toFixed(1)}%). ` +
             `Rather than jumping straight into race-specific training, we recommend a ${threshold}-week ` +
             `fitness development block to build the aerobic and structural foundation you'll need. ` +
             `After that block, we'll reassess and set up your target performance plan.`,
    gate_reason: 'gap_too_large'
  }
}
```

### Gate Actions

| Gap Classification | Action | Behaviour |
|---|---|---|
| Small (≤3%) | `proceed` | Generate target_performance plan with 4-6 week timeline |
| Medium (3-8%) | `proceed` | Generate target_performance plan with 6-10 week timeline |
| Large (8-15%) | `proceed` | Generate target_performance plan with 10-16 week timeline |
| Very Large (>15%) | `propose_fitness_improvement` | Propose fitness_improvement goal first; athlete must accept or abandon |

---

## Objective Seeding (Target Performance)

### Race-Type-Aware Objective Priority

```typescript
const RACE_TYPE_OBJECTIVE_PRIORITY: Record<GoalEventType, {
  critical: ObjectiveCategory[]
  important: ObjectiveCategory[]
  optional: ObjectiveCategory[]
}> = {
  marathon: {
    critical: ['aerobic_base', 'durability', 'pacing_discipline'],
    important: ['threshold_quality', 'intensity_distribution'],
    optional: ['structural_tolerance', 'intensity_compliance']
  },
  half_marathon: {
    critical: ['aerobic_base', 'threshold_quality', 'pacing_discipline'],
    important: ['intensity_distribution', 'durability'],
    optional: ['structural_tolerance', 'neuromuscular_sharpness']
  },
  '10k': {
    critical: ['threshold_quality', 'pacing_discipline', 'intensity_distribution'],
    important: ['aerobic_base', 'neuromuscular_sharpness'],
    optional: ['structural_tolerance', 'durability']
  },
  '5k': {
    critical: ['threshold_quality', 'neuromuscular_sharpness', 'pacing_discipline'],
    important: ['aerobic_base', 'intensity_distribution'],
    optional: ['structural_tolerance', 'durability']
  },
  ultra: {
    critical: ['aerobic_base', 'durability', 'recovery_efficiency'],
    important: ['structural_tolerance', 'pacing_discipline'],
    optional: ['threshold_quality', 'intensity_compliance']
  },
  trail_race: {
    critical: ['aerobic_base', 'structural_tolerance', 'durability'],
    important: ['pacing_discipline', 'recovery_efficiency'],
    optional: ['threshold_quality', 'intensity_distribution']
  },
  custom: {
    critical: ['aerobic_base', 'pacing_discipline'],
    important: ['threshold_quality', 'structural_tolerance'],
    optional: ['durability', 'intensity_distribution']
  }
}
```

### Seeding Logic

```typescript
function seedTargetPerformanceObjectives(inputs: {
  gap_classification: GapClassification
  goal_event_type: GoalEventType
  twin_state: TwinState
  race_type_priority: typeof RACE_TYPE_OBJECTIVE_PRIORITY[GoalEventType]
}): ObjectiveSeed[] {
  const { gap_classification, goal_event_type, twin_state, race_type_priority } = inputs
  
  const selected: ObjectiveSeed[] = []
  
  // 1. Always include critical objectives (if twin state flags them)
  for (const category of race_type_priority.critical) {
    if (isCategoryRelevant(category, twin_state)) {
      selected.push({
        category,
        direction: getDirectionForCategory(category, twin_state),
        session_types_relevant: deriveRelevantSessionTypes(category)
      })
    }
  }
  
  // 2. Add important objectives if space allows (max 5 total)
  for (const category of race_type_priority.important) {
    if (selected.length >= 5) break
    if (isCategoryRelevant(category, twin_state)) {
      selected.push({
        category,
        direction: getDirectionForCategory(category, twin_state),
        session_types_relevant: deriveRelevantSessionTypes(category)
      })
    }
  }
  
  // 3. Add optional objectives if still under limit
  for (const category of race_type_priority.optional) {
    if (selected.length >= 5) break
    if (isCategoryRelevant(category, twin_state)) {
      selected.push({
        category,
        direction: getDirectionForCategory(category, twin_state),
        session_types_relevant: deriveRelevantSessionTypes(category)
      })
    }
  }
  
  // 4. Ensure at least 1 strength (maintain) objective
  if (!selected.some(s => s.direction === 'maintain')) {
    const strength = identifyStrength(twin_state)
    if (strength) {
      selected.push({
        category: strength.category,
        direction: 'maintain',
        session_types_relevant: deriveRelevantSessionTypes(strength.category)
      })
    }
  }
  
  return selected.slice(0, 5)  // enforce max 5
}
```

---

## Plan Generation Pipeline

### Overview

```typescript
async function generateTargetPerformancePlan(
  inputs: PlanGenerationInputs
): Promise<{ plan: TrainingPlan; first_weekly_plan: WeeklyPlan; checkpoints: Checkpoint[] }> {
  
  // Phase 0: Gap Analysis
  const current_estimate = estimateCurrentPerformance(inputs.twin_state, inputs.training_goal.target_distance_km)
  const gap_percentage = computeGapPercentage(current_estimate, inputs.training_goal.target_time_minutes)
  
  // Phase 0b: Training Length Gate (target_performance variant)
  const gateResult = evaluateTargetPerformanceGate({
    gap_percentage,
    fitness_level: inputs.training_goal.fitness_level,
    goal_event_type: inputs.training_goal.goal_event_type,
    experience_level: inputs.athlete_preferences.experience_level
  })
  
  if (gateResult.action === 'propose_fitness_improvement') {
    return handleFitnessImprovementProposal(gateResult, inputs)
  }
  
  // Phase 1: Objective Seeding (using gap analysis + race type)
  const objectives = seedTargetPerformanceObjectives({
    gap_classification: classifyGap(gap_percentage),
    goal_event_type: inputs.training_goal.goal_event_type,
    twin_state: inputs.twin_state,
    race_type_priority: RACE_TYPE_OBJECTIVE_PRIORITY[inputs.training_goal.goal_event_type]
  })
  
  // Phase 2: Generate Hypotheses (race-like, but with objective context)
  const hypotheses = await hypothesisAgent.generate({
    twin_state: inputs.twin_state,
    twin_context: await assembleTwinContext(inputs.twin_state),
    athlete_preferences: inputs.athlete_preferences,
    goal: {
      description: inputs.training_goal.goal_description,
      event_type: inputs.training_goal.goal_event_type,
      event_date: gateResult.target_date  // system-determined date
    },
    secondary_events: inputs.secondary_events,
    confidence_gaps: identifyConfidenceGaps(inputs.twin_state),
    objectives  // NEW: objectives inform hypothesis generation
  })
  
  // Phase 3: Select Hypothesis and Synthesize Framework
  const { strategic_framework } = await hypothesisSelectorAgent.select({
    hypotheses: hypotheses.hypotheses,
    twin_context: await assembleTwinContext(inputs.twin_state),
    athlete_preferences: inputs.athlete_preferences,
    goal: {
      event_type: inputs.training_goal.goal_event_type,
      event_date: gateResult.target_date
    },
    secondary_events: inputs.secondary_events,
    objectives  // NEW: objectives inform selection
  })
  
  // Phase 4: Validate and Persist
  const validation = validatePhaseArc(strategic_framework, inputs)
  
  if (!validation.valid) {
    return handleValidationFailure(validation, inputs)
  }
  
  // Phase 5: Set goal_event_date (system-determined)
  await updateGoalEventDate(inputs.training_goal.id, gateResult.target_date)
  
  return persistPlan(strategic_framework, validation, inputs)
}
```

---

## Phase Structure

Target performance uses a race-like phase structure, but with emphasis on trajectory validation:

```typescript
type TargetPerformancePhaseStructure = {
  // Base phase: build aerobic foundation
  base: {
    weeks: number  // 3-6 weeks depending on gap
    distribution: { low_aerobic: number; high_aerobic: number; threshold: number; vo2max: number; neuromuscular: number }
    specificity: number  // 0.0–0.3
  }
  
  // Build phase: develop race-specific fitness
  build: {
    weeks: number  // 4-8 weeks depending on gap
    distribution: { low_aerobic: number; high_aerobic: number; threshold: number; vo2max: number; neuromuscular: number }
    specificity: number  // 0.3–0.6
  }
  
  // Race-specific phase: target pace work
  race_specific: {
    weeks: number  // 2-4 weeks
    distribution: { low_aerobic: number; high_aerobic: number; threshold: number; vo2max: number; neuromuscular: number }
    specificity: number  // 0.6–0.8
  }
  
  // Sharpen phase: final preparation
  sharpen: {
    weeks: number  // 1-2 weeks
    distribution: { low_aerobic: number; high_aerobic: number; threshold: number; vo2max: number; neuromuscular: number }
    specificity: number  // 0.8–1.0
  }
  
  // Optional taper (if target is a race)
  taper?: {
    weeks: number  // 1-2 weeks
    distribution: { low_aerobic: number; high_aerobic: number; threshold: number; vo2max: number; neuromuscular: number }
    specificity: number  // 0.0
  }
}
```

---

## Secondary Events

Secondary events are supported identically to race mode:

### Disruption Windows

| Event Type | Pre-Event | Post-Event | Behaviour |
|---|---|---|---|
| B-event | 4 days | 3 days | Reduced load, recovery focus |
| C-event | 2 days | 1 day | Minimal adjustment |

### Invariants

- Secondary events cannot conflict with primary target date
- Max 3 secondary events per goal
- Secondary events are mutable via dedicated endpoints

---

## Checkpoint Trajectory Validation

### New Checkpoint Fields

```typescript
type CheckpointDescriptor = {
  // ... existing fields ...
  
  // Trajectory validation (target_performance mode only)
  trajectory_status?: 'ahead' | 'on_track' | 'behind' | 'at_risk'
  proposal?: string  // Coach-driven proposal when trajectory changes
}
```

### Trajectory Computation

```typescript
type TargetPerformanceCheckpointResult = {
  metric_updated: boolean
  confidence_changed: boolean
  new_confidence_level?: 'low' | 'medium' | 'high'
  replan_triggered: boolean
  trajectory_status: 'ahead' | 'on_track' | 'behind' | 'at_risk'
  proposal?: string
}

function processTargetPerformanceCheckpoint(
  checkpoint: Checkpoint,
  session: PlannedSession,
  activity: Activity,
  original_gap_analysis: GapAnalysis
): TargetPerformanceCheckpointResult {
  // 1. Analyse activity data against checkpoint.target_metric
  const current_estimate = analysePerformance(activity, checkpoint.target_metric)
  
  // 2. Recompute trajectory
  const weeks_elapsed = weeksSincePlanStart(session.training_plan_id)
  const expected_progress = (weeks_elapsed / original_gap_analysis.estimated_weeks) * 100
  const actual_progress = computeProgress(current_estimate, original_gap_analysis.target)
  
  // 3. Determine trajectory status
  let trajectory_status: 'ahead' | 'on_track' | 'behind' | 'at_risk'
  if (actual_progress > expected_progress * 1.1) {
    trajectory_status = 'ahead'
  } else if (actual_progress > expected_progress * 0.9) {
    trajectory_status = 'on_track'
  } else if (actual_progress > expected_progress * 0.7) {
    trajectory_status = 'behind'
  } else {
    trajectory_status = 'at_risk'
  }
  
  // 4. Generate proposal if trajectory changes materially
  let proposal: string | undefined
  if (trajectory_status === 'ahead') {
    const new_date = estimateEarlierDate(current_estimate, original_gap_analysis.target)
    proposal = `You're ahead of schedule. We could hit your target by ${new_date} instead of ${original_gap_analysis.target_date}.`
  } else if (trajectory_status === 'at_risk') {
    const adjusted_date = estimateLaterDate(current_estimate, original_gap_analysis.target)
    proposal = `The target is at risk. We could extend to ${adjusted_date} or adjust the target to ${adjusted_target}.`
  }
  
  // 5. Update twin state if metric changed materially
  const metric_updated = updateTwinStateMetric(current_estimate)
  const confidence_changed = checkConfidenceChange()
  
  // 6. Trigger replanning if trajectory changed materially
  const replan_triggered = trajectory_status === 'ahead' || trajectory_status === 'at_risk'
  
  return {
    metric_updated,
    confidence_changed,
    new_confidence_level: confidence_changed ? getNewConfidenceLevel() : undefined,
    replan_triggered,
    trajectory_status,
    proposal
  }
}
```

### Early Achievement Logic

When benchmarks show ahead-of-schedule trajectory, two options:

1. **Pull date forward**: Propose moving `goal_event_date` earlier
   - Example: "You're ahead of schedule - we could hit your 10K target in 6 weeks instead of 8"

2. **Stretch target**: Propose a faster target time
   - Example: "You're on track for 50 minutes - want to aim for 48?"

Both require coach judgment. The system proposes; the coach decides.

---

## Regeneration Triggers (Target Performance)

### What Triggers Regeneration

| Trigger | Behaviour |
|---|---|
| `goal_date_change` | NOT applicable (athlete cannot PATCH date in target_performance mode) |
| `confidence_upgrade` | Only if old plan was at LOW confidence |
| `secondary_event_added/removed` | Only if disruption cannot be accommodated |
| `checkpoint_completed` | Only if trajectory_status is 'ahead' or 'at_risk' AND replan_triggered = true |
| `coach_date_adjustment` | Coach proposes new date via coaching conversation; athlete confirms; full plan regeneration with new goal_event_date |
| `trajectory_ahead` | Coach proposes pulling date forward or stretching target |
| `trajectory_at_risk` | Coach proposes extending date or adjusting target |

### What Does NOT Trigger Regeneration

| Disruption | How It's Absorbed |
|---|---|
| Missed sessions | Next pre-week review adjusts intent |
| Faster/slower than expected recovery | Weekly synthesis adjusts session count/intensity |
| Minor schedule disruptions | Weekly synthesis works with new availability |
| Adaptation yield better/worse than expected | Pre-week review adjusts intensity bias |

---

## Coaching Messages (Target Performance)

### Language Cues

| Context | Language |
|---|---|
| Plan view | "Your trajectory toward [target] is [on track/ahead/behind]" |
| Daily view | "Today's session supports [objective name] — you're [X]% toward your target" |
| Phase transition | "Moving into [phase] — focus shifts to [objective]" |
| Checkpoint approach | "This checkpoint validates your trajectory toward [target]" |
| Checkpoint completion | "Your [metric] confirms you're [trajectory_status] — [proposal if applicable]" |
| Early achievement | "You're ahead of schedule — [pull date forward OR stretch target option]" |

### Objective Reference

All coaching messages should reference objectives by name at:
- Plan view: "This plan targets [objective1], [objective2], and [objective3]"
- Daily view: "Today's session supports [objective name]"
- Phase transitions: "Focus shifts to [objective]"

---

## Cross-References

- **Merged with race_event mode.** Target-performance now uses the same pipeline as `plan-generation-race.md`. This document is retained for reference on gap analysis, trajectory validation, and objective seeding logic — all of which are now preprocessing/checkpoint behaviours within the unified race_event pipeline.
- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs (includes `athlete_objectives`), PhaseDefinition, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **Race event mode (unified):** `plan-generation-race.md` — hypothesis generation, validation, synthesis, persistence; mode-specific preprocessing (gap analysis → date) and trajectory validation
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_definitions, weekly_distributions, strategic_rationale, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records with trajectory_status and proposal
- **TrainingGoal entity:** `01-entities/training-goal.md` — target_distance_km, target_time_minutes fields
- **Objective entity:** `01-entities/objective.md` — RACE_TYPE_OBJECTIVE_PRIORITY mapping
- **Objective management:** `02-computations/objective-management.md` — seedTargetPerformanceObjectives()
- **Vision goal modes:** `docs/vision/product/goal-modes.md` — coaching posture for target_performance mode
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept