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
}
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

### Open Training Mode

Rolling 8-week `rolling_block` phases. No taper. Regenerated at the start of each new rolling block.

```typescript
function computeOpenTrainingArc(): PhaseDescriptor[] {
  return [{
    label: 'rolling_block',
    start_date: today,
    end_date: addWeeks(today, 8),
    weeks: 8,
    primary_focus: 'Consistent aerobic development',
    weekly_session_count: computeSessionCount(athlete_preferences)
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

function shouldRegenerate(trigger: RegenerationTrigger, old_plan: TrainingPlan, new_twin: TwinState): boolean {
  // goal_date_change: only if abs(new_date - old_date) > 7 days
  // confidence_upgrade: only if old plan was generated at 'low' confidence
  // session_dropout: checked by nightly monitoring task
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
