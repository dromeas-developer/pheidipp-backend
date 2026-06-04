# ExecutionObservation — Structured Session Analysis

## Purpose
- Stores pre-computed execution findings for a completed activity
- The structured digest that LLM agents receive — they narrate from it, never derive from raw data
- Versioned so analysis can be reprocessed as algorithms improve

## TypeScript Schema

```typescript
type SessionShape =
  | 'steady'
  | 'progressive_fade'
  | 'positive_split'
  | 'w_shape'
  | 'strong_finish'

type RepAnalysis = {
  rep_index: number
  inferred_state: PhysiologicalIntent
  confidence: number
  mean_gap_sec_per_km: number | null
  mean_hr_bpm: number | null
  drift_pct: number | null           // within-rep drift percentage
  vs_target_pct: number | null       // deviation from WorkoutStep target
}

type RecoveryAnalysis = {
  rep_index: number                  // the recovery after rep N
  pace_pullback_to_target: boolean | null
  hr_decline_direction: 'declining' | 'flat' | 'rising' | null
  hr_decline_rate_bpm_per_min: number | null
  // NOTE: hr_zone_during_recovery is deliberately absent
  // See vision/twin/execution-patterns.md for why HR zone is wrong here
}

type CoachingObservations = {
  headline: string                   // one-sentence summary
  session_type_specific: {
    // Aerobic sessions:
    cardiac_drift_score?: number
    decoupling_ratio?: number
    // Threshold/interval sessions:
    cross_rep_trend?: 'even' | 'progressive_fade' | 'positive_split' | 'w_shape'
    final_rep_delta_pct?: number
    recovery_quality?: 'good_hr_decline' | 'flat_hr' | 'incomplete_pace_pullback'
    // VO2max sessions:
    sandbagging_flag?: boolean
    positive_split_flag?: boolean
    controlled_fade_score?: number
  }
  per_rep_analysis?: RepAnalysis[]   // null until Phase 5c (segment-level analysis)
  recovery_analysis?: RecoveryAnalysis[]
  flags: string[]                    // notable anomalies
}

type IntentCompliance = {
  step_id: string
  prescribed_intent: PhysiologicalIntent
  actual_intent: PhysiologicalIntent
  compliance: 'compliant' | 'under' | 'over' | 'mismatch'
  deviation: number
  family: ComplianceFamily
}

type ExecutionObservation = {
  id: string                         // UUID, PK
  activity_id: string                // UUID, FK → Activity (one-to-one)
  session_shape: SessionShape
  intent_compliance: IntentCompliance[]  // step-level intent compliance
  effort_compliance: Record<string, unknown>  // lap-level compliance pre-5b
  key_signals: Record<string, unknown>
  coaching_observations: CoachingObservations
  analysis_version: string           // 'lap-v1' pre-5c; 'segment-v1' post-5c
}

type WorkoutComplianceSummary = {
  workout_id: string
  step_results: IntentCompliance[]
  overall_compliance: 'compliant' | 'under' | 'over' | 'mixed'
  intent_distribution: Record<PhysiologicalIntent, number>
  purpose: SessionPurpose
  summary: string  // plain English; narrated by agent
}
```

## Vision Cross-Reference

### Post-Workout Message Mapping

Maps vision message elements from `vision/coach/post-workout.md` to architecture data fields and agent paragraph assignment. The vision defines **what the athlete reads**; the architecture stores **what the agent narrates from**.

| Vision Message Element | Architecture Data Field(s) | Agent Paragraph | Notes |
|---|---|---|---|
| Session compliance — did the athlete execute the plan | `intent_compliance[]` (step-level compliance), `session_shape`, `coaching_observations.headline` | Para 1 | Agent context also includes `compliance.duration_delta_pct` and `compliance.session_type_match` |
| Rep-by-rep story — individual interval examination | `coaching_observations.per_rep_analysis[]`, `coaching_observations.session_type_specific` (cross_rep_trend, final_rep_delta_pct, recovery_quality, etc.), `coaching_observations.flags[]` | Para 2 | Pre-5c: null `per_rep_analysis`; agent falls back to `session_shape` and `session_type_specific` fields |
| Historical correlation — connection to comparable previous session | `comparable_session` context block (from `ComparableSessionService`); source: `execution_observation.coaching_observations` of the matched activity | Para 2 | If `comparable_session = null` (score < 0.50),Para 2 omits historical comparison entirely |
| Objective progress — directional movement on relevant objectives | `objective_updates[]` (from `ObjectiveUpdateService`); includes `direction_of_change`, `evidence`, `is_milestone` | Para 3 | If `objective_updates = []`, Para 3 focuses on plan position |

**Reading direction:** An implementer reading `post-workout.md` sees the four message elements. This table traces each element to the architecture fields that produce it and the agent paragraph that delivers it.

### Execution Pattern Detection Mapping

Maps vision concepts from `vision/twin/execution-patterns.md` to `coaching_observations` fields. This table is the authoritative reference for which vision patterns map to which architecture fields.

### Aerobic Session Patterns

| Vision Concept | Architecture Field | Threshold / Logic | Notes |
|---|---|---|---|
| Cardiac drift | `cardiac_drift_score` | Positive = HR rising while pace holds | Progressive HR increase during steady-pace effort |
| Decoupling ratio | `decoupling_ratio` | > 5% = significant divergence | HR-to-pace relationship over session duration |
| Pace drift | `decoupling_ratio` | Subsumed by decoupling | Pace direction inferred from HR-pace divergence |
| Zone encroachment | `flags[]` → `'zone_encroachment'` | Any tempo/threshold in easy session | Not a dedicated field; captured in flags array |

### Threshold and Interval Patterns

| Vision Concept | Architecture Field | Threshold / Logic | Notes |
|---|---|---|---|
| Cross-rep trend | `cross_rep_trend` | `'even'` / `'progressive_fade'` / `'positive_split'` / `'w_shape'` | Direct mapping to session shape enum |
| Final rep degradation | `final_rep_delta_pct` | > 8% = notable fade | Percentage deviation from target in final rep |
| Recovery quality | `recovery_quality` | Categorical: `'good_hr_decline'` / `'flat_hr'` / `'incomplete_pace_pullback'` | Avoids HR zone during recovery (see vision rationale) |
| HR decline rate | `RecoveryAnalysis.hr_decline_rate_bpm_per_min` | Higher = faster recovery | Fitness signal; rate of HR decline during recovery interval |
| Pace pullback | `RecoveryAnalysis.pace_pullback_to_target` | `true` = hit recovery pace | Grade-adjusted pace during recovery |

### VO2max Session Patterns

| Vision Concept | Architecture Field | Threshold / Logic | Notes |
|---|---|---|---|
| Sandbagging | `sandbagging_flag` | All reps strong, HR well below max, no degradation | Boolean flag; targets likely need revising upward |
| Positive splitting | `positive_split_flag` | Hard early, fade after rep 3-4 | Pacing discipline becomes coaching objective |
| Controlled fade | `controlled_fade_score` | 2-3% degradation in final reps = correct intensity | Score indicates fade magnitude |

### Session Shape Classification

| Vision Concept | Architecture Field | Values | Notes |
|---|---|---|---|
| Even execution | `session_shape` | `'steady'` | Vision uses "even execution"; architecture uses "steady" |
| Progressive fade | `session_shape` | `'progressive_fade'` | Consistent degradation across session |
| Positive split | `session_shape` | `'positive_split'` | Hard early, slow late |
| W-shape blowup | `session_shape` | `'w_shape'` | Blowup and recovery pattern |
| Strong finish | `session_shape` | `'strong_finish'` | Faster final segment |

### Longitudinal Behavioural Profile

| Vision Concept | Architecture Field | Notes |
|---|---|---|
| Characteristic tendencies under fatigue | `coaching_observations.flags[]` | Recurring patterns surface as flags across sessions |
| Zone discipline | `intent_compliance[].compliance` | Aggregated across sessions by `ObjectiveUpdateService` |
| Pacing instincts | `session_shape` distribution | `ComparableSessionService` matches on shape patterns |
| Recovery patterns | `recovery_analysis[].hr_decline_rate_bpm_per_min` | Trend tracked by `ObjectiveUpdateService` |
| Recurring patterns → coaching objectives | `ObjectiveUpdateService` | Reads `coaching_observations` to evaluate objective direction |

### Gaps Requiring Implementation Decisions

| Vision Concept | Status | Resolution Needed |
|---|---|---|
| Zone encroachment | No dedicated field | Define flag value and trigger threshold |
| Pace drift direction | Subsumed by `decoupling_ratio` | Confirm decoupling ratio captures both directions |
| HR decline rate as fitness signal | Stored but not trended | Define aggregation logic in `ObjectiveUpdateService` |
| Behavioural profile entity | No architecture entity | Either create `BehaviouralProfile` entity or confirm services handle aggregation |
| Flag value taxonomy | `flags: string[]` is unbounded | Define canonical flag values per session type |

## Invariants
- One `ExecutionObservation` per `Activity`. One-to-one.
- Only created for `calibration_eligible = true` activities with a linked `GeneratedWorkout` (the prescribed intent must be known for compliance assessment). Activities without `planned_session_id` or without `calibration_eligible = true` receive a simplified analysis with null `per_rep_analysis` and `effort_compliance`.
- `coaching_observations` is computed by Python services — never by an LLM.
- `per_rep_analysis` and `recovery_analysis` are null until Phase 5c. Pre-5c analysis works from lap data; post-5c it works from `PhysiologicalSegment` records.
- `analysis_version` must be updated when the analysis algorithm changes materially. Old records retain the old version string for auditability.

## Phase Evolution

| Phase | `analysis_version` | Source data | `per_rep_analysis` |
|---|---|---|---|
| 4a | `lap-v1` | FIT lap messages + raw time-series | null |
| 5c | `segment-v1` | `PhysiologicalSegment` records | populated |

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| None | — | — | ExecutionObservation is consumed by agents directly |

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_calibration_eligible` | Triggers `ExecutionAnalysisService` | v1 |

## APIs

ExecutionObservation is not exposed directly. It is consumed by:
- `PostWorkoutAgent` (via `ContextBudgetService`)
- `ComparableSessionService` (reads `coaching_observations` for matching)
- `ObjectiveUpdateService` (reads `coaching_observations` for objective evaluation)

```yaml
GET /athletes/{athlete_id}/activities/{activity_id}/analysis
Response: 200
  post_workout_analysis: PostWorkoutAnalysisResponse  # includes coaching_message + execution_findings summary
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `execution_observations` table | append-only | strong | indefinite |

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (via PostWorkoutAnalysis) | No | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- Pre-computed execution findings
- The structured digest for agent narration

Does Not Own:
- How findings are computed → `02-computations/execution-analysis.md`
- Agent narration → `03-agents/post-workout-agent.md`
- Comparable session selection → `02-computations/comparable-sessions.md`

## Failure Semantics
- `ExecutionAnalysisService` failure → no `ExecutionObservation` created; post-workout message proceeds without it (agent uses compliance-only context)
- FIT file fetch failure during analysis → task retried up to 3 times

## Performance Constraints
- `ExecutionAnalysisService.analyse()`: p95 < 10s (reads from object storage)

## Observability
Metrics:
- `execution_observation.created.total`: by analysis_version
- `execution_observation.session_shape.distribution`
- `execution_observation.analysis.latency_ms`
