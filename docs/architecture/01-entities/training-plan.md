# TrainingPlan — Periodised Plan for a TrainingBlock

## Purpose
- The generated periodised training structure for an active TrainingBlock
- One active plan per block at a time; old plans are superseded, never deleted
- Contains the phase arc; PlannedSession records are its children

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

type TrainingPlan = {
  id: string                      // UUID, PK
  training_block_id: string       // UUID, FK → TrainingBlock
  twin_state_id: string           // UUID, FK → TwinState (the twin version that generated this plan)
  phases: PhaseDescriptor[]       // ordered array; non-overlapping; covers full duration
  status: TrainingPlanStatus
  superseded_at: string | null    // set when a newer plan is created for the same block
  created_at: string              // ISO 8601

  // Hypothesis metadata (set for race_event mode; null for other modes)
  selected_hypothesis: SelectedHypothesis | null
  
  // Checkpoint schedule (set for race_event mode; empty for other modes)
  checkpoint_schedule: CheckpointDescriptor[]
}

type SelectedHypothesis = {
  name: string
  methodology: string
  approach: string
  recovery_cycle: string
  load_distribution: {
    zone1_2: number
    zone3: number
    zone4_5: number
  }
  rationale: string
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
- One active plan per TrainingBlock at any time. When a new plan is generated for a block, the previous plan's `status` → `superseded` and `superseded_at` is set, atomically with the new plan's creation.
- Old plans are never deleted. `superseded_at` is the only mutation on an inactive plan.
- `phases` is a non-overlapping, ordered array. The combined date range covers from the plan start date to `TrainingBlock.goal_event_date` without gaps.
- `twin_state_id` records which twin version produced this plan. A plan produced at LOW confidence will have different phase structures than one produced at MEDIUM or HIGH.
- `selected_hypothesis` is set only for `race_event` mode plans. For `fitness_improvement`, `maintenance`, and `recovery` modes, it is null.
- `checkpoint_schedule` contains all checkpoints for the plan. Checkpoints are scheduled during synthesis and correspond to PlannedSession records with `checkpoint_type` set.

## Phase Arc Formula

Computed by `PlanGenerationService` from `TrainingBlock`. See `02-computations/plan-generation.md` for the authoritative formula. Summary:

For `goal_type = 'race_event'`:
```
base_building_weeks   = max(2, round(total_weeks * 0.40))
threshold_weeks       = max(1, round(total_weeks * 0.30))
race_specific_weeks   = max(1, round(total_weeks * 0.15))
taper_weeks           = 2  (ultra: 3)
race_week_weeks       = 1
```

For `goal_type = 'fitness_improvement'`: progressive development with threshold emphasis. No taper. Fixed 8-week rolling progression.

For `goal_type = 'maintenance'`: consistency-focused. 4-week rolling block emphasizing aerobic base and form preservation. No intensity peaks.

For `goal_type = 'recovery'`: healing-focused. Conservative load distribution, gradual return progression over 2-4 weeks based on injury severity.

## Regeneration Triggers
A new plan is generated (old one superseded) when:
- A new TrainingBlock is created
- `goal_event_date` changes by more than 7 days
- TwinState `confidence_level` upgrades (LOW → MEDIUM allows more precise session targets)
- More than 20% of PlannedSession records within a 3-week window are `skipped` or `missed`

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `training_plan_generated` | Plan inserted | v1 | `{training_plan_id, training_block_id, phase_count, total_weeks, supersedes_plan_id, trigger}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `twin_confidence_upgraded` | Triggers plan regeneration | v1 |
| `onboarding_completed` | Triggers initial plan generation | v1 |
| `session_skipped` / `session_missed` | Monitored for dropout rate gate | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/plan
Response: 200 | 404
  plan: TrainingPlanResponse  # active plan with full phases array
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/plan/sessions
Query:
  from?: date
  to?: date
  status?: PlannedSessionStatus
  limit?: number (default 50)
Response: 200
  sessions: PlannedSessionResponse[]
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/plan/upcoming
Response: 200
  sessions: PlannedSessionResponse[]  # next 5 pending/generated sessions
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `training_plans` table | append-only (status/superseded_at mutable) | strong | indefinite |
| `planned_sessions` table | append-only (status mutable) | strong | indefinite |

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (read-only) | No | No |
| Service | Yes | status, superseded_at only | No |
| Repository | Yes | Yes | No |

## Runtime Ownership
Owns:
- Phase arc structure and session counts
- Supersession chain between plans

Does Not Own:
- Phase arc computation → `02-computations/plan-generation.md`
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
