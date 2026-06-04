# GeneratedWorkout — Day-of Workout for a PlannedSession

## Purpose
- The specific, target-bearing workout generated on the day from the athlete's current twin state
- Stores both theoretical and adjusted targets so the two-column display is always available
- Parent to WorkoutStep records; owned by a PlannedSession

## Vision ↔ Architecture Mapping

This entity implements the home screen (daily view) and the "Today's Session" element of plan visibility.

| Vision UI Element (Daily View) | Architecture Source | Field(s) | Notes |
|---|---|---|---|
| **Today's Workout** — "Full session structure including warmup, main set, and cooldown. Intensity segments colour-coded." | `GeneratedWorkout` + `workout_steps` (child) | `theoretical_targets`, `adjusted_targets`, `workout_steps[]` | Steps provide segment-level structure. Intensity colour-coding is derived from `WorkoutTarget.signal_type` and range values at render time. |
| **Two-Column Target Display** — "Theoretical targets (what the twin's current intent ranges suggest) and adjusted targets (what the coach recommends today)." | `GeneratedWorkout` | `theoretical_targets: TargetSet`, `adjusted_targets: TargetSet` | Both fields always written, even when identical (GREEN modifier with no weather). This is the core data backing the two-column display. |
| **Weather Impact** — "Humidity, wind, heat index, and time-of-day conditions. Already factored into adjusted targets, but surfaced so the athlete understands why." | `WeatherForecast` (external entity) | Referenced via `WeatherAdjustmentService` in the computation chain | **Weather explanation text is not stored on this entity.** The adjusted targets reflect the weather impact numerically, but the athlete-facing explanation ("26°C and humid — your adjusted target is around two minutes slower") must be composed at the API response layer using the `WeatherForecast` record linked to this workout's generation context. |
| **Recovery Status** — "A plain-language summary of the trend over recent days. Not a number or a gauge — a sentence." | `GeneratedWorkout` (partial) | `recovery_modifier_level`, `recovery_modifier_reason` | **Partial mapping.** `recovery_modifier_level` (green/amber/red) is a level indicator — the vision explicitly says "not a number or a gauge." `recovery_modifier_reason` is structured text from a narrated agent, which is closer to the vision's intent. However, the vision describes a *multi-day trend synthesis*, not a per-workout modifier. The multi-day trend aggregation is not owned by this entity; it is a computation concern of the wellness modifier service. The API response layer must compose the trend narrative. |
| **Relevant Objectives** — "Only the objectives this specific workout is designed to address. Not all objectives." | **Not stored on this entity** | N/A | **Gap.** `GeneratedWorkout` does not link to training objectives or a training purpose field. `WeeklySession.intent_description` captures session-level intent ("threshold development — 4x8min at LT2") but is not the same as specific objectives. The workout generation agent should annotate generated workouts with the objectives they serve, or this must be composed from `PlannedSession` → `WeeklySession` → `PhaseArcEntry.physiological_emphasis` at the API layer. |
| **Near-Term Session Preview** — "Next four to five planned sessions at headline level: session type, approximate duration, training intent." | `WeeklyPlan.sessions: WeeklySession[]` (not on this entity) | `session_type`, `intent_description`, `approximate_duration_minutes` | Sourced from `WeeklyPlan.WeeklySession[]`, not from `GeneratedWorkout`. The today's-view API (`GET /athletes/{athlete_id}/today`) must compose this from the active `WeeklyPlan`. |
| **Plan Position** — "Which week and phase the athlete is currently in, how far through the phase." | **Not on this entity** | N/A | Sourced from `TrainingPlan.phases[]` + `WeeklyPlan.week_number`. The today's-view API must compose current phase position from these entities. |

### Headline vs. Precise Boundary

The vision draws a clear boundary: near-term sessions are "headline level" (no specific targets), while today's session has "precise targets." The architecture implements this as:

- **Headline:** `WeeklySession` — `session_type`, `intent_description`, `approximate_duration_minutes`. No targets.
- **Precise:** `GeneratedWorkout` — `theoretical_targets`, `adjusted_targets`, `workout_steps[]`. Full targets.

`WeeklySession.intent_description` may contain detail like "threshold development — 4x8min at LT2." This is more than a bare headline but does not include target values. The boundary is: intent/description = headline; numeric targets = precise.

### Unmapped Vision Requirements

| Vision Requirement | Status | Owner |
|---|---|---|
| "Daily snapshots are saved and the athlete can navigate backward to see what the coach said on any previous day" | `generated_workouts` table is append-only; historical retrieval is possible via `GET /plan/sessions/{session_id}/workout`. No explicit "daily view history" API exists. | API layer — add a `GET /athletes/{athlete_id}/history` endpoint or document that `GET /prediction/history` + session-level queries serve this need |
| "Phase position always visible on home view" | Not on this entity. Must be composed from `TrainingPlan` + `WeeklyPlan`. | Today's-view API response layer |

## TypeScript Schema

```typescript
type TargetSet = {
  targets: WorkoutTarget[]
  description: string  // plain English; always present
}

type GeneratedWorkout = {
  id: string                         // UUID, PK
  planned_session_id: string         // UUID, FK → PlannedSession (one-to-one)
  twin_state_id: string              // UUID, FK → TwinState (the twin version used)
  theoretical_targets: TargetSet     // from current dynamic thresholds; no modifiers applied
  adjusted_targets: TargetSet        // after recovery modifier + cycle modifier + weather
  recovery_modifier_level: RecoveryModifierLevel  // default: 'green'
  recovery_modifier_reason: string | null  // structured text; narrated agent
  generated_at: string               // ISO 8601
}

type WorkoutTarget = {
  signal_type: 'power' | 'gap' | 'hr' | 'description'
  primary: {
    min: number | null
    max: number | null
    unit: string
  }
  fallback: WorkoutTarget | null
  description: string  // always present; plain English
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
  → theoretical_targets (range-based targets from IntentRanges)
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
