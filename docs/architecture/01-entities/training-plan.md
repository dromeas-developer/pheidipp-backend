# TrainingPlan — Periodised Plan for a TrainingBlock

## Purpose

- The generated periodised training structure for an active TrainingGoal
- One active plan per goal at a time; old plans are superseded, never deleted
- Contains the phase arc (strategic intent per week), strategic rationale (race_event mode), and checkpoint schedule
- Session-level detail lives on WeeklyPlan records, not on the TrainingPlan itself

## TypeScript Schema

```typescript
type TrainingPlanStatus = 'active' | 'superseded' | 'completed'

type PhaseDescriptor = {
  label: PhaseLabel
  start_date: string      // YYYY-MM-DD
  end_date: string        // YYYY-MM-DD
  weeks: number
  primary_focus: string   // plain English; surfaced in plan visibility API
  weekly_session_count: number
}

// PhaseLabel values: see 00-foundations/terminology.md

type PhaseArcEntry = {
  week_number: number
  phase_label: PhaseLabel
  methodology: MethodologyTraitVector
  physiological_emphasis: string      // plain English; what this week is about
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  race_considerations?: string        // "B-race this week, reduce pre-race"
  checkpoint_intent?: string          // "benchmark aerobic fitness"
  target_session_count: number        // hint, not constraint — weekly planner decides
}

type TrainingPlan = {
  id: string                      // UUID, PK
  training_goal_id: string       // UUID, FK → TrainingGoal
  twin_state_id: string           // UUID, FK → TwinState (the twin version that generated this plan)
  phases: PhaseDescriptor[]       // ordered array; non-overlapping; covers full duration
  phase_arc: PhaseArcEntry[]      // strategic intent per week; no session-level detail
  status: TrainingPlanStatus
  superseded_at: string | null    // set when a newer plan is created for the same goal
  created_at: string              // ISO 8601

  // Strategic rationale (set for race_event mode; null for other modes)
  strategic_rationale: StrategicRationale | null
  
  // Checkpoint schedule (set for race_event mode; empty for other modes)
  checkpoint_schedule: CheckpointDescriptor[]
}

type StrategicRationale = {
  primary_driver: string           // plain English; why this approach suits the athlete
  methodology_summary: string      // high-level approach description (internal reasoning summary)
  intensity_distribution: {
    low_aerobic: number            // percentage of session time (0-1)
    high_aerobic: number
    threshold: number
    vo2max: number
    neuromuscular: number
    recovery: number
  }
  risk_notes: string[]
}

type CheckpointDescriptor = {
  type: CheckpointType
  week_number: number
  target_date: string
  target_metric: string
  session_type: SessionType
  planner_message: string
}
```

## Invariants
- **One active plan per TrainingGoal at any time.** When a new plan is generated for a goal, the previous plan's `status` → `superseded` and `superseded_at` is set, atomically with the new plan's creation.
- **Old plans are never deleted.** `superseded_at` is the only mutation on an inactive plan.
- **`phases` is a non-overlapping, ordered array.** The combined date range covers from the plan start date to `TrainingGoal.goal_event_date` without gaps.
- **`phase_arc` contains strategic intent only.** No session-level detail. Session schedules live on `WeeklyPlan` records. The phase arc provides the methodology, physiological emphasis, and intensity bias for each week; the weekly synthesis agent produces the actual sessions.
- **`twin_state_id` records which twin version produced this plan.** A plan produced at LOW confidence will have different phase structures than one produced at MEDIUM or HIGH.
- **`strategic_rationale` is set only for `race_event` mode plans.** Contains the coach's rationale and resulting intensity distribution. Internal hypothesis exploration names are not persisted. For `fitness_improvement`, `maintenance`, and `recovery` modes, it is null.
- **`checkpoint_schedule` contains all checkpoints for the plan.** Checkpoints are scheduled during synthesis and correspond to PlannedSession records with `checkpoint_type` set.

## Phase Arc Computation

The phase arc is computed differently depending on `goal_type`:

### `race_event` mode

Phase structure is **LLM-derived**, not deterministic. The `PlanStructureAgent` generates strategic hypotheses that determine phase emphasis, duration, and focus areas. The resulting phase arc is synthesised from the selected hypothesis and stored in `phases`. See `02-computations/plan-generation.md` for the full pipeline.

The strategic framework determines:
- Phase durations and emphasis (base, build, race-specific, taper)
- Intensity distribution across phases
- Checkpoint placement
- Race integration windows

### Non-race modes (deterministic)

Computed by `PlanGenerationService` from `TrainingBlock`. See `02-computations/plan-generation.md` for the authoritative formulas.

**`fitness_improvement`:** Progressive development with threshold emphasis. No taper. Fixed 8-week rolling progression.

**`maintenance`:** Consistency-focused. 4-week rolling block emphasizing aerobic base and form preservation. No intensity peaks.

**`recovery`:** Healing-focused. Conservative load distribution, gradual return progression over 2-4 weeks based on injury severity.

## Regeneration Triggers

A new plan is generated (old one superseded) when:
- A new TrainingGoal is created
- `goal_event_date` changes by more than 7 days
- TwinState `confidence_level` upgrades (LOW → MEDIUM allows more precise session targets)
- More than 20% of PlannedSession records within a 3-week window are `skipped` or `missed`
- `checkpoint_completed` event fires with `replan_triggered = true` (confidence changed materially)
- `secondary_event_added` or `secondary_event_removed` — when B/C-races change and disruption window cannot be accommodated

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `training_plan_generated` | Plan inserted | v1 | `{training_plan_id, training_goal_id, phase_count, total_weeks, supersedes_plan_id, trigger}` |

### Consumed

| Event | Action | Version |
|---|---|---|
| `twin_model_ready` | Triggers initial plan generation + first weekly plan | v1 |
| `twin_confidence_upgraded` | Triggers plan regeneration (if old plan was at LOW confidence) | v1 |
| `session_skipped` / `session_missed` | Feeds into weekly pre-week review (NOT full regeneration) | v1 |
| `checkpoint_completed` | Triggers replanning if `replan_triggered = true` | v1 |
| `secondary_event_added` | May trigger redistribution or regeneration | v1 |
| `secondary_event_removed` | May trigger redistribution or regeneration | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/plan
Response: 200
  plan: TrainingPlanResponse  # includes phase_arc, strategic_rationale, checkpoint_schedule
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/plan/sessions
Response: 200
  sessions: PlannedSessionResponse[]  # sessions from the ACTIVE WeeklyPlan (resolves through WeeklyPlan FK)
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/plan/upcoming
Response: 200
  sessions: PlannedSessionResponse[]  # next N sessions from active + synthesised WeeklyPlans
Auth: Bearer JWT, require_self
```

## Storage Model

| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `training_plans` table | append-only (status/superseded_at mutable) | strong | indefinite |
| `weekly_plans` table | append-only (status mutable) | strong | indefinite |

Note: `planned_sessions` are children of `weekly_plans`, not `training_plans` directly. The FK chain is `training_plans → weekly_plans → planned_sessions`.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (read-only) | No | No |
| Service | Yes | status, superseded_at only | No |
| Repository | Yes | Yes | No |

## Runtime Ownership

Owns:
- Phase arc structure (strategic intent per week)
- Supersession chain between plans
- Strategic rationale and checkpoint schedule (race_event mode)

Does Not Own:
- Phase arc computation → `02-computations/plan-generation.md`
- Strategic framework synthesis (race_event mode) → `03-agents/hypothesis-selector-agent.md`
- Hypothesis generation (race_event mode) → `03-agents/hypothesis-agent.md`
- Weekly session schedule → `01-entities/weekly-plan.md` and `03-agents/weekly-synthesis-agent.md`
- Pre-week intent review → `03-agents/pre-week-review-agent.md`
- Individual session management → `01-entities/planned-session.md`
- Day-of workout generation → `01-entities/generated-workout.md`

## Failure Semantics
- `PlanGenerationService` failure → existing active plan retained; error logged; retry scheduled
- Supersession is atomic: old plan marked superseded and new plan inserted in one transaction

## Performance Constraints
- `GET /plan`: p95 < 100ms
- `GET /plan/upcoming`: p95 < 50ms

## Observability
Metrics:
- `training_plan.generated.total`: by trigger type
- `training_plan.phase_counts.distribution`: histogram of phase counts per plan
Logs:
- `training_plan.generated`: athlete_id, plan_id, trigger, phase_count, total_weeks, supersedes_plan_id
