# Objective Management — Seeding, Evaluation, and Update Cadence

## Purpose
- Defines the Python logic for objective seeding, post-session evaluation, and weekly review
- Category selection and direction are always Python-determined; LLM writes descriptions only

## Seeding Logic

```typescript
type SeedingInputs = {
  twin_state: TwinState
  execution_observations: ExecutionObservation[]  // from imported history (Tier 1); empty for Tier 3
  athlete_preferences: AthletePreferences
  training_goal: TrainingGoal
}

// Tier-based category availability
const TIER3_CATEGORIES: ObjectiveCategory[] = [
  'aerobic_base', 'structural_tolerance', 'pacing_discipline'
]
const ALL_CATEGORIES: ObjectiveCategory[] = [
  'aerobic_base', 'threshold_quality', 'pacing_discipline',
  'intensity_distribution', 'structural_tolerance', 'neuromuscular_sharpness',
  'durability', 'intensity_compliance', 'recovery_efficiency'
]

// Race-Type-Aware Objective Priority
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

function seedTargetPerformanceObjectives(inputs: SeedingInputs): ObjectiveSeed[] {
  const { training_goal, twin_state } = inputs
  const race_type_priority = RACE_TYPE_OBJECTIVE_PRIORITY[training_goal.goal_event_type]
  
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

function seedObjectives(inputs: SeedingInputs): ObjectiveSeed[] {
  const available_categories = inputs.execution_observations.length > 0
    ? ALL_CATEGORIES : TIER3_CATEGORIES

  // Goal-type-aware seeding
  if (inputs.training_goal.goal_type === 'race_event') {
    return seedRaceEventObjectives(inputs)
  } else if (inputs.training_goal.goal_type === 'target_performance') {
    return seedTargetPerformanceObjectives(inputs)
  } else if (inputs.training_goal.goal_type === 'fitness_improvement') {
    return seedFitnessImprovementObjectives(inputs)
  } else if (inputs.training_goal.goal_type === 'maintenance') {
    return seedMaintenanceObjectives(inputs)
  } else if (inputs.training_goal.goal_type === 'recovery') {
    return seedRecoveryObjectives(inputs)
  }

  // Default: standard seeding
  const gaps = identifyGaps(inputs)
  const strengths = identifyStrengths(inputs)
  const selected_gaps = gaps.slice(0, 4)
  const selected_strength = strengths.slice(0, 1)

  return [...selected_gaps, ...selected_strength]
    .map(seed => ({
      category: seed.category,
      direction: seed.direction,
      session_types_relevant: deriveRelevantSessionTypes(seed.category),
    }))
}
```

## Post-Session Evaluation

```typescript
function evaluateObjectivePostSession(
  objective: Objective,
  execution_observation: ExecutionObservation,
  athlete_profile: AthleteProfile
): ObjectiveUpdate {
  // Python-computed; never LLM-derived
  // Reads coaching_observations to determine direction_of_change

  const signals = execution_observation.coaching_observations.session_type_specific
  let direction: ObjectiveDirectionOfChange = 'stable'
  let evidence = ''

  // Confidence-weighted: low confidence observations produce direction: 'stable'
  if (execution_observation.confidence_level === 'calibration') {
    return {
      direction_of_change: 'stable',
      evidence: 'Observation confidence too low to drive objective change',
      coach_note: null
    }
  }

  switch (objective.category) {
    case 'pacing_discipline':
      const final_rep_delta = signals.final_rep_delta_pct ?? 0
      const pacing_threshold = athlete_profile.objective_thresholds?.pacing_discipline ?? 0.03
      if (Math.abs(final_rep_delta) < pacing_threshold) {
        direction = 'improving'; evidence = `Final rep within ${Math.abs(final_rep_delta).toFixed(1)}% of target`
      } else if (final_rep_delta > pacing_threshold * 2.5) {
        direction = 'regressing'; evidence = `Final rep ${final_rep_delta.toFixed(1)}% slower than target`
      }
      break

    case 'intensity_compliance':
      const encroachments = signals.intent_encroachment_events ?? 0
      const encroachment_threshold = athlete_profile.objective_thresholds?.encroachment_events ?? 3
      direction = encroachments === 0 ? 'improving' : encroachments > encroachment_threshold ? 'regressing' : 'stable'
      evidence = `${encroachments} intent encroachment event(s) detected`
      break

    // ... other categories
  }

  return {
    direction_of_change: direction,
    evidence,  // Python-written; describes the specific signal
    coach_note: null  // null for automatic updates; set by LLM for milestone events
  }
}
```

> **Per-Athlete Evaluation Thresholds:**
> 
> Objective evaluation uses athlete-relative thresholds, not population defaults. Each threshold is stored in `AthleteProfile.objective_thresholds` (JSON, per-category) with population defaults as fallback.
> 
> ```typescript
> type ObjectiveThresholds = {
>   pacing_discipline?: number        // default: 0.03 (3% variance)
>   encroachment_events?: number      // default: 3 events
>   // ... other objective categories
> }
> ```
> 
> **Confidence-weighted evaluation:** Low confidence observations (`confidence_level: 'calibration'`) produce `direction: 'stable'` regardless of magnitude. This prevents noisy early data from driving objective changes.

## Update Cadence

```typescript
// Post-session: after every calibration-eligible session
// Runs BEFORE PostWorkoutAgent — agent receives pre-computed updates
function postSessionUpdate(activity_id: string): ObjectiveUpdate[] {
  // For each active objective where session_types_relevant includes this session type
  // Calls evaluateObjectivePostSession()
  // Flags milestones (first 'achieved') for agent to acknowledge
}

// Weekly review: for objectives not updated by post-session in past 7 days
// Runs as nightly scheduled task
function weeklyReview(athlete_id: string): ObjectiveUpdate[] {
  // Trend-based updates from the week's execution observations
  // Creates 'stable' updates for objectives with no session-level signal
}
```

**Note on achievement speed variance:** The "3 improving updates" criterion behaves differently by objective category. High-frequency objectives (e.g., `intensity_compliance` — updated every session) may achieve in 1–2 weeks. Low-frequency objectives (e.g., `threshold_quality` — updated only on threshold sessions) may take 6+ weeks. This is intentional: achievement reflects demonstrated consistency, not calendar time. The weekly review task creates 'stable' updates for objectives with no session-level signal, ensuring low-frequency objectives still progress (albeit slowly).

## Objective Achievement

```typescript
function checkAchievement(objective: Objective, updates: ObjectiveUpdate[]): boolean {
  // Last 3 post-session updates all show 'improving'
  const recent = updates.slice(-3)
  return recent.length === 3 && recent.every(u => u.direction_of_change === 'improving')
}
// When achieved: status → 'achieved'; achieved_at set
// PostWorkoutAgent receives milestone flag and explicitly acknowledges
```

## Vision ↔ Architecture Alignment

The following maps vision concepts (`docs/vision/coach/objectives.md`) to architecture implementation. This table is the authoritative cross-reference for verifying that the architecture faithfully implements the vision's intent.

| Vision Concept | Architecture Key | Vision Philosophy | Architecture Implementation |
|---|---|---|---|
| What Objectives Are | `Objective` entity schema; `ObjectiveCategory` enum | “Bridge between individual sessions and long-term development”; “physiological insights that the twin can see” | 9 categories map to physiological domains; entity purpose states “bridges individual sessions to long-term physiological development” |
| Initial Seeding | `ObjectiveSeedingService.seedObjectives()`; seeding rules in `objective.md` | “First coach message seeds initial objectives based on twin model analysis”; “strengths explicitly alongside improvement opportunities” | Python logic (`identifyGaps`, `identifyStrengths`) determines categories/directions; invariant: at least one `direction = 'maintain'` always seeded; LLM writes only titles/descriptions |
| Living Updates (weekly rhythm) | `weeklyReview()` in `objective-management.md` | “Update on slower rhythm than workouts — weekly or after significant sessions” | Nightly task updates objectives not touched by post-session in 7 days |
| Post-session connection | `evaluateObjectivePostSession()` | “After each relevant workout, coach briefly connects session to applicable objective” | Runs before `PostWorkoutAgent`; creates `ObjectiveUpdate` with Python-computed direction/evidence |
| Achievement = sustained improvement | `checkAchievement()` | “Achievement determined by sustained improvement, not a single session” | Last 3 post-session updates must all be `improving` |
| Pre-workout filtering | `filterForSession()` in `objective.md`; `GET /objectives/for-session/{session_id}` API | “Only objectives relevant to today’s workout are surfaced” | Filters by `session_types_relevant`; max 2 in context |
| Post-workout feedback | `PostWorkoutAgent` receives pre-computed `ObjectiveUpdate` records | “Coach message explicitly addresses movement on those same objectives” | Agent receives milestone flag and pre-computed direction/evidence; writes only narration |
| Strengths maintained | Seeding invariant: at least one `direction = 'maintain'` | “Strengths surfaced explicitly alongside gaps” | Python-identified strengths always included in initial set |

## Cross-References

- Objective entity schema: `01-entities/objective.md`
- ExecutionObservation (source of evaluation signals): `01-entities/execution-observation.md`
- Post-workout agent that narrates updates: `03-agents/post-workout-agent.md`
- Plan generation (block renewal calls `ObjectiveSeedingService.seedObjectives()`): `02-computations/plan-generation-fitness-improvement.md`
