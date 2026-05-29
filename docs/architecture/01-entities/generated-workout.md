# GeneratedWorkout — Day-of Workout for a PlannedSession

## Purpose
- The specific, target-bearing workout generated on the day from the athlete's current twin state
- Stores both theoretical and adjusted targets so the two-column display is always available
- Parent to WorkoutStep records; owned by a PlannedSession

## TypeScript Schema

```typescript
type TargetSet = {
  // Targets populated based on data tier:
  // Tier 1-2: power targets primary
  // Tier 3-4: pace targets primary
  // Tier 5-6: description only; numeric targets null
  pace_sec_per_km: number | null     // always GAP; never raw pace
  power_watts: number | null
  hr_zone: number | null             // 1–5
  description: string                // plain English; always present
}

type GeneratedWorkout = {
  id: string                         // UUID, PK
  planned_session_id: string         // UUID, FK → PlannedSession (one-to-one)
  twin_state_id: string              // UUID, FK → TwinState (the twin version used)
  theoretical_targets: TargetSet     // from current dynamic zones; no modifiers applied
  adjusted_targets: TargetSet        // after recovery modifier + cycle modifier + weather
  recovery_modifier_level: RecoveryModifierLevel  // default: 'green'
  recovery_modifier_reason: string | null  // structured text; narrated by agent
  generated_at: string               // ISO 8601
  // Note: workout_structure JSONB (Phase 1) removed when WorkoutStep records exist (2c+)
}
```

## Invariants
- One `GeneratedWorkout` per `PlannedSession`. Generation is idempotent for the same `(planned_session_id, date)` — calling the generation endpoint twice returns the existing workout.
- `theoretical_targets` and `adjusted_targets` are always both written, even when identical (GREEN modifier with no weather).
- `pace_sec_per_km` in both target sets uses GAP values only. Never raw pace.
- `recovery_modifier_level` defaults to `green`. It is set to `amber` or `red` only when `WellnessModifierService` produces that classification.
- `twin_state_id` records which twin version drove target generation. If the twin is recalibrated after a workout is generated, the generated workout is not retroactively updated.

## Target Computation Chain

```
TwinState (threshold estimates)
  ↓ TwinContextAssemblerService
  → theoretical_targets (zone-based targets from dynamic zones)
    ↓ WellnessModifierService (recovery level + scale factor)
    ↓ CyclePhaseService (luteal temp offset if applicable)
    ↓ WeatherAdjustmentService (heat_index + wind)
    → adjusted_targets
```

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `workout_generated` | GeneratedWorkout inserted | v1 | `{generated_workout_id, planned_session_id, recovery_modifier_level}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `twin_recalibrated` | Informs next workout generation; does not update existing workouts | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/today
Response: 200
  planned_session: PlannedSessionResponse
  generated_workout: GeneratedWorkoutResponse  # triggers generation if not exists
  steps: WorkoutStepResponse[]
Auth: Bearer JWT, require_self

POST /athletes/{athlete_id}/plan/sessions/{session_id}/generate-workout
Response: 201 | 200  # 200 if already generated (idempotent)
  generated_workout: GeneratedWorkoutResponse
  steps: WorkoutStepResponse[]
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/plan/sessions/{session_id}/workout
Response: 200 | 404
  generated_workout: GeneratedWorkoutResponse
  steps: WorkoutStepResponse[]
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `generated_workouts` table | append-only (no mutations after creation) | strong | indefinite |
| `workout_steps` table | append-only | strong | indefinite |

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (read-only) | Via generate endpoints | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- The day-of workout structure and targets
- Two-column target storage (theoretical and adjusted)
- Recovery modifier annotation

Does Not Own:
- Target computation → `WorkoutGenerationAgent` in `03-agents/workout-generation-agent.md`
- Recovery modifier computation → `02-computations/wellness-modifier.md`
- Weather adjustment → `02-computations/wellness-modifier.md`
- Step-level detail → `01-entities/workout-step.md`

## Idempotency
- Generating a workout for a session that already has one → returns existing (200, not 201)

## Failure Semantics
- LLM agent failure → 503; `GenerationEvent` written with success=false; workout not created
- Weather fetch failure → workout generated with adjusted_targets = theoretical_targets; noted in recovery_modifier_reason

## Performance Constraints
- `GET /today`: p95 < 500ms (may trigger synchronous generation)
- Pre-generated workout retrieval: p95 < 50ms

## Observability
Metrics:
- `generated_workout.generation.latency_ms`
- `generated_workout.recovery_modifier.distribution`: by level (green/amber/red)
- `generated_workout.target_delta`: percentage difference between theoretical and adjusted (monitors modifier effectiveness)
Logs:
- `generated_workout.created`: session_id, recovery_modifier_level, twin_state_id, data_tier
