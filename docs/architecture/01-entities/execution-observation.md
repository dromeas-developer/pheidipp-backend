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
