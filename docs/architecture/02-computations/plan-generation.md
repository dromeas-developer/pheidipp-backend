# Plan Generation — Phase Arc and Session Distribution

## Purpose
- Defines the pure-Python algorithm that converts TrainingBlock + TwinState into TrainingPlan + PlannedSessions
- No LLM involved; deterministic output for a given input

## Inputs

```typescript
type PlanGenerationInputs = {
  training_block: TrainingBlock
  athlete_preferences: AthletePreferences
  twin_state: TwinState
  cycle_phase_log: CyclePhaseLog | null  // used to avoid key sessions in late luteal
  today: string  // YYYY-MM-DD
  secondary_events: SecondaryEvent[]     // B-races and C-races for disruption window calculation
}

// GoalType determines phase arc structure:
// - race_event: peaking/tapering toward goal event date
// - fitness_improvement: progressive development, threshold emphasis
// - maintenance: consistency-focused rolling blocks
// - recovery: conservative progression, healing priority

// Secondary events create disruption windows within the phase arc:
// - B-races: 4 days pre-race, 3 days post-race (reduced load/recovery focus)
// - C-races: 2 days pre-race, 1 day post-race (minimal adjustment)
```

## Phase Arc Formula

### Race Event Mode

```typescript
function computePhaseArc(
  total_weeks: number,
  goal_event_type: GoalEventType
): PhaseDescriptor[] {
  const taper_weeks = goal_event_type === 'ultra' ? 3 : 2

  let base_building   = Math.max(2, Math.round(total_weeks * 0.40))
  let threshold       = Math.max(1, Math.round(total_weeks * 0.30))
  let race_specific   = Math.max(1, Math.round(total_weeks * 0.15))
  const race_week     = 1
  const fixed_end     = taper_weeks + race_week

  // Absorb rounding remainder into base_building
  const remainder = total_weeks - base_building - threshold - race_specific - fixed_end
  base_building += remainder

  // Edge case: < 5 weeks total
  if (total_weeks < 5) {
    threshold = 0; race_specific = 0  // base + taper + race_week only
  }

  return buildPhaseArray(base_building, threshold, race_specific, taper_weeks, race_week, today)
}
```

### Fitness Improvement Mode

```typescript
function computeFitnessImprovementArc(
  total_weeks: number,
  athlete_preferences: AthletePreferences
): PhaseDescriptor[] {
  // 8-week rolling progression with threshold emphasis
  const base_weeks = Math.min(total_weeks, 8)

  if (total_weeks >= 8) {
    // Full 8-week arc
    return [
      { label: 'base_building', weeks: 4, ... }
    , { label: 'threshold_development', weeks: 3, ... }
    , { label: 'race_specific', weeks: 1, ... }  // repurposed: capacity building
    ]
  } else {
    return [{ label: 'rolling_block', weeks: total_weeks, primary_focus: 'Progressive development' }]
  }
}
```

### Maintenance Mode

```typescript
function computeMaintenanceArc(
  total_weeks: number,
  athlete_preferences: AthletePreferences
): PhaseDescriptor[] {
  // 4-week rolling block emphasizing consistency and form preservation
  return [{
    label: 'rolling_block',
    weeks: Math.min(total_weeks, 4),
    primary_focus: 'Consistent aerobic development with form preservation'
  }]
}
```

### Recovery Mode

```typescript
function computeRecoveryArc(
  injury_severity: InjurySeverity,
  athlete_preferences: AthletePreferences
): PhaseDescriptor[] {
  // Conservative load progression based on injury severity
  const phase_weeks = injury_severity === 'minor' ? 2 : injury_severity === 'major' ? 4 : 3

  return [{
    label: 'recovery',
    weeks: phase_weeks,
    primary_focus: 'Healing and gradual return to training'
  }]
}
```

## Session Distribution

Sessions are assigned to days within each phase following structural rules that serve both coaching quality and adaptation data collection:

```typescript
const QUALITY_SESSION_TYPES: SessionType[] = [
  'threshold', 'vo2max_intervals', 'tempo', 'long_run'
]

function distributeSessionsInWeek(
  phase: PhaseDescriptor,
  week_number: number,
  available_days: DaySchedule[],
  session_count: number
): PlannedSession[] {
  // Rule 1: Long run on a day with long_workout = true
  // Rule 2: Long run always followed by rest or recovery_run
  // Rule 3: Quality sessions sandwiched between easy or rest days
  // Rule 4: No two quality sessions on consecutive dates
  // Rule 5: Session count respects weekly_session_count from phase

  // These rules are constraints, not suggestions.
  // Distribution is rejected and retried if any rule would be violated.
  // Maximum 10 retries; if exceeded, session_count is reduced by 1.
}
```

## Crossover Athlete Structural Ramp

When `AthletePreferences.sport_background !== 'running_primary'`:

```typescript
// First training block: structural load is capped regardless of stated weekly_volume_hours
// The cardiovascular system tolerates volume the tendons cannot yet handle
const MAX_STRUCTURAL_LOAD_PER_WEEK_CROSSOVER = 0.7 * POPULATION_MAX_WEEK_1

// Applied as a constraint on session count and long_run duration in weeks 1-4
// Relaxed by week 5 if no injury flags in quality_flags or skip_reason
```

## Regeneration Triggers

```typescript
type RegenerationTrigger =
  | 'new_block'
  | 'goal_date_change'      // goal_event_date moved by > 7 days
  | 'confidence_upgrade'    // twin moved from low→medium; plan can be more precise
  | 'session_dropout'       // > 20% of sessions in 3-week window skipped or missed
  | 'secondary_event_added' // B-race or C-race added within active plan date range
  | 'secondary_event_removed' // Secondary event removed, sessions restored

function shouldRegenerate(trigger: RegenerationTrigger, old_plan: TrainingPlan, new_twin: TwinState): boolean {
  // goal_date_change: only if abs(new_date - old_date) > 7 days
  // confidence_upgrade: only if old plan was generated at 'low' confidence
  // session_dropout: checked by nightly monitoring task
  // secondary_event changes: triggers redistribution, not full regeneration unless
  //   the disruption window cannot be accommodated within existing phase structure
}
```

## Outputs

Creates atomically:
- One `TrainingPlan` (status=active; old plan superseded)
- N `PlannedSession` records covering the full plan duration
- Fires `training_plan_generated` event

## Cross-References
- TrainingPlan entity: `01-entities/training-plan.md`
- PlannedSession entity: `01-entities/planned-session.md`
- TrainingBlock inputs: `01-entities/training-block.md`
- AthletePreferences (weekly_schedule, sport_background): `01-entities/athlete-preferences.md`
- Adaptation data collection rationale for structural rules: `02-computations/adaptation-signature.md`
