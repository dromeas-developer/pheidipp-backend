# ActivityPowerProfile — Performance Expression Snapshot

## Purpose
- Stores a deterministic snapshot of the athlete's power-duration curve (PDC) derived from a single Activity
- Enables trend analysis of performance expression across training blocks
- NOT surfaced as charts or dashboards; used exclusively as LLM input for coaching narratives

## TypeScript Schema

```typescript
type PowerDurationAnchor = {
   duration_seconds: number    // e.g., 5, 60, 300, 1200 (5s, 1m, 5m, 20m)
   best_power_watts: number
   source: 'direct' | 'interpolated' | 'modeled'  // How the value was derived
 }

type StepPowerProfile = {
   step_number: number           // 1-based order in the workout
   execution_step_id: string     // FK → ExecutionStep
   power_zone: PowerZone         // Resolved zone for the step
   pdc_record: PowerDurationAnchor[]  // Anchors derived from this step's data
 }

type PowerZone = 'aerobic' | 'tempo' | 'threshold' | 'vo2max' | 'neuromuscular'

type ActivityPowerProfile = {
   id: string                // UUID, PK
   activity_id: string        // UUID, FK → Activity (one-to-one)
   athlete_id: string        // UUID, FK → Athlete

   // Core anchors: populated when power data is available
   anchors: PowerDurationAnchor[]

   // Computed summary metrics
   critical_power_watts: number | null      // CP derived from this session's data
   w_prime_kj: number | null                // W' derived from this session's data
   curve_version: string                    // 'pdc-v1'

   // Metadata
   data_quality_score: number | null        // 0-1; confidence in the PDC computation
   computation_basis: 'power_meter' | 'estimated_from_hr' | 'insufficient_data'

   // Optional step-level decomposition
   step_profiles?: StepPowerProfile[]        // Populated when session has ≥2 distinct zones

   created_at: string                      // ISO 8601
}
```

## Invariants
- One `ActivityPowerProfile` per `Activity` where `calibration_eligible = true` and `has_power = true`.
- `ActivityPowerProfile` is **append-only**. New computation versions create new records with new `id` values.
- `computation_basis = 'insufficient_data'` results in an empty `anchors` array and null `critical_power_watts`/`w_prime_kj`.
- `data_quality_score` is computed by `PowerProfileService` and stored for downstream filtering.
- `step_profiles` is populated when a session's `ExecutionStep` records show ≥2 distinct `power_zone` values; omitted for single-zone sessions.

## Step-Level Decomposition
When a structured workout contains multiple physiological zones, `step_profiles` provides per-step PDC snapshots:
- Enables zone-specific load and performance analysis
- `ContextBudgetService` prefers `step_profiles` when present; falls back to activity-level `anchors`
- `ComparableSessionService` uses `step_profiles` for zone-targeted session matching
- Load-fatigue engine consumes `step_profiles` for zone-specific load signatures

## Computation Trigger
Computed by `PowerProfileService` after the ingestion pipeline completes and `activity_calibration_eligible = true` with `has_power = true`.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `power_profile_computed` | ActivityPowerProfile successfully created | v1 | `{ activity_id: string, power_profile_id: string }` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_calibration_eligible` | Triggers `PowerProfileService` when `has_power = true` | v1 |

## APIs

`ActivityPowerProfile` is not exposed directly. It is consumed by:
- `ContextBudgetService` for LLM agent context assembly
- `ComparableSessionService` for performance-trend comparison

## Storage Model

| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `activity_power_profiles` table | append-only | strong | indefinite |

## Mutation Rules

| Layer | Read | Write | Delete |
|---|---|---|---|
| API | No (consumed indirectly) | No | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership

Owns:
- Performance expression snapshot for individual activities
- Power-duration curve anchors for trend analysis

Does Not Own:
- How PDC is computed → `02-computations/power-profile-computation.md` (future)
- Agent narration → `03-agents/post-workout-agent.md`
- Comparable session selection → `02-computations/comparable-sessions.md`

## Failure Semantics
- `PowerProfileService` failure → no `ActivityPowerProfile` created; task retries up to 3×
- Low data quality (`data_quality_score < 0.5`) → record still created but flagged for filtering

## Performance Constraints
- `PowerProfileService.compute()`: p95 < 3s (reads pre-cleaned data)

## Observability

Metrics:
- `power_profile.computed.total`: by computation_basis
- `power_profile.data_quality_score.distribution`
- `power_profile.anchor.count.per_activity`: histogram of anchors extracted

Logs:
- `power_profile.computed`: activity_id, athlete_id, data_quality_score

## Vision Cross-Reference

This entity implements the vision principle that Pheidipp tracks **how the athlete's system behaves under stress**, not just **how much stress they've accumulated**. It is the architectural foundation for:

- Energy system progression analysis (comparing PDC anchors across blocks)
- Performance expression context in post-workout messages
- "Comparable session" matching based on capability trends, not just session type

**Important:** These metrics are **never surfaced to athletes as raw numbers or charts**. They are purely analytical inputs for LLM-based coaching narratives, consistent with Pheidipp's "anti-dashboard" philosophy.