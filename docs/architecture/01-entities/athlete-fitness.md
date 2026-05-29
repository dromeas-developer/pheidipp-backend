# AthleteFitness — Banister Model Rolling State

## Purpose
- Stores the current Banister impulse-response model state: fitness and fatigue scores per dimension
- Updated on every calibration-eligible activity; the most frequently written entity in the system
- Separate from AthletePhysiology because fitness/fatigue update daily while physiological parameters update slowly

## TypeScript Schema

```typescript
type DimensionalScores = {
  fitness: number   // accumulated training stimulus; decays slowly (τ_fitness ≈ 42 days default)
  fatigue: number   // accumulated training load; decays faster (τ_fatigue ≈ 7 days default)
  form: number      // computed: fitness - fatigue; readiness signal
}

type BanisterTimeConstants = {
  fitness_tau_days: number   // population default: 42; individualised in Phase 6d
  fatigue_tau_days: number   // population default: 7;  individualised in Phase 6d
  source: 'population_default' | 'individual_fitted'
  fitted_at: string | null   // ISO date; null if source = 'population_default'
}

type AthleteFitness = {
  id: string                          // UUID, PK
  athlete_id: string                  // UUID, FK → Athlete (one-to-one; current state)

  // Phase 1-6b: single aggregate score pair
  aggregate: DimensionalScores

  // Phase 6c+: three-dimensional scores (null until Phase 6c activated)
  aerobic: DimensionalScores | null
  neuromuscular: DimensionalScores | null
  structural: DimensionalScores | null

  // Time constants used in the most recent update
  time_constants: BanisterTimeConstants

  // Context
  last_activity_id: string | null     // FK → Activity; the session that last updated this record
  updated_at: string                  // ISO 8601
}
```

## Banister Model Update Formula

Applied by `FitnessUpdateService` after every calibration-eligible activity:

```typescript
function banisterUpdate(
  current: DimensionalScores,
  load: number,          // the relevant load score from Activity (aerobic/neuromuscular/structural)
  constants: BanisterTimeConstants,
  days_since_last_update: number
): DimensionalScores {
  // Natural decay since last activity
  const fitness_decay = Math.exp(-days_since_last_update / constants.fitness_tau_days)
  const fatigue_decay = Math.exp(-days_since_last_update / constants.fatigue_tau_days)

  const new_fitness = current.fitness * fitness_decay + load
  const new_fatigue = current.fatigue * fatigue_decay + load
  const new_form = new_fitness - new_fatigue

  return { fitness: new_fitness, fatigue: new_fatigue, form: new_form }
}
```

This runs independently for each dimension once three-dimensional scoring is active (Phase 6c). Before that, `load` is the combined aerobic + neuromuscular load and only `aggregate` is updated.

## Individual Time Constants (Phase 6d+)

Population defaults are `fitness_tau = 42 days, fatigue_tau = 7 days`. Some athletes carry fatigue for 10+ days; others clear in 5. Individual constants are fitted from the athlete's response history by `TimeConstantFittingService` when ≥ 12 weeks of calibration-eligible data exist.

Once fitted, `BanisterTimeConstants.source` transitions from `population_default` to `individual_fitted` and subsequent updates use the individual values. The `TwinState` `model_version` increments to reflect the change.

## Form as a Readiness Signal

`form = fitness - fatigue` at the aggregate level is the primary readiness indicator consumed by `TwinContextAssemblerService`. It drives the descriptive readiness language surfaced to LLM agents:

```typescript
function formToDescriptor(form: number): string {
  if (form > 15)  return 'peaked — near-optimal readiness'
  if (form > 5)   return 'building — good readiness with fitness accumulating'
  if (form > -5)  return 'training load — normal accumulated fatigue'
  if (form > -15) return 'heavy load — significant accumulated fatigue'
  return 'overreached — fatigue substantially exceeds fitness'
}
```

This descriptor (not the raw number) is what the LLM agent receives. Raw form scores are never surfaced to athletes.

## Relationship to AthleteFitness vs AthletePhysiology

These two entities have a clean separation:

| Concern | Entity |
|---|---|
| LT1, LT2, FTP, VO2max, max HR | `AthletePhysiology` |
| Aerobic/neuromuscular/structural fitness and fatigue | `AthleteFitness` |
| Data tier, confidence level, snapshot assembly | `TwinState` |

`TwinState` references both `athlete_physiology_id` and `athlete_fitness_id`. When a session is processed:
- If `ThresholdDetectionService` finds a threshold signal → `AthletePhysiology` updates → new `TwinState` with updated `athlete_physiology_id`
- Always → `AthleteFitness` updates (load always contributes to fitness/fatigue) → new `TwinState` with updated `athlete_fitness_id`
- Both can update in the same session. One new `TwinState` is appended referencing both updated records.

## How a Lab Test Interacts With AthleteFitness

A lab test updates `AthletePhysiology` — not `AthleteFitness`. It does not change the athlete's current fitness or fatigue state. What changes is the precision of the threshold estimates that define zones, which in turn affects how subsequent training loads are computed (once threshold-referenced load formulas are active from Phase 2d).

A lab test therefore triggers a new `TwinState` via `trigger = 'calibration'` but does not recalculate `AthleteFitness` scores — those reflect training history and are not affected by a measurement of stable physiological parameters.

## Invariants
- One `AthleteFitness` record per athlete. **Mutable** — scores are updated in place on every calibration-eligible activity.
- `aggregate` is always populated. `aerobic`, `neuromuscular`, `structural` are null until Phase 6c activation.
- `form` is always a computed field (`fitness - fatigue`). It is stored for query convenience but derived value — it must always equal `fitness - fatigue`.
- `time_constants.source` starts as `population_default`. It transitions to `individual_fitted` only once, when `TimeConstantFittingService` produces a fit with sufficient data quality. It never reverts to `population_default`.
- Negative `form` is valid and normal. It indicates the athlete is in a training load phase. An athlete with `form = -20` is heavily loaded but not necessarily overreached.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `fitness_updated` | `AthleteFitness` written after session | v1 | `{athlete_id, aggregate_form, last_activity_id}` |
| `fitness_time_constants_fitted` | Individual constants activated | v1 | `{athlete_id, fitness_tau, fatigue_tau, fitted_from_weeks}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_calibration_eligible` | Triggers `FitnessUpdateService` | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/fitness
Response: 200
  fitness: AthleteFitnessResponse
  # form_descriptor: string (plain language readiness; not raw scores)
  # raw scores are not included in the response — they are internal
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/fitness/history
Description: Rolling fitness/fatigue/form over time (for the prediction arc visualisation)
Query:
  days?: number (default 90, max 365)
Response: 200
  # Reconstructed from TwinState history; not a separate time-series table
  history: FitnessHistoryPoint[]
Auth: Bearer JWT, require_self
```

Note: Raw fitness/fatigue scores are never returned as numbers to the athlete. `GET /fitness` returns only the `form_descriptor` and contextual information. The numerical values are internal to the twin model.

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_fitness` table | mutable (scores updated in place) | strong | indefinite |

Unique constraint: `(athlete_id)` — one record per athlete.

Historical fitness state is reconstructable from `TwinState` history (each TwinState references `athlete_fitness_id` at the time of creation) rather than maintaining a separate time-series table.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (form_descriptor only) | No | No |
| Service | Yes | update (scores + time_constants) | No |
| Repository | Yes | Yes | No |

## Runtime Ownership
Owns:
- Banister model fitness, fatigue, and form scores
- Time constants (population or individual)

Does Not Own:
- Load scores that feed the Banister update → `01-entities/activity.md`
- Threshold estimates that define zones → `01-entities/athlete-physiology.md`
- TwinState snapshot assembly → `01-entities/twin-state.md`

## Failure Semantics
- `FitnessUpdateService` failure → previous scores remain current; retry scheduled; `TwinState` for this session not appended until retry succeeds
- Negative fitness score (should not occur) → alert; value clamped to 0; investigation required

## Performance Constraints
- `FitnessUpdateService.update()`: p95 < 50ms
- `GET /fitness`: p95 < 30ms

## Observability
Metrics:
- `athlete_fitness.form.distribution`: histogram of current form scores across athlete base
- `athlete_fitness.time_constants.fitted.total`: athletes with individual constants
- `athlete_fitness.update.latency_ms`
Logs:
- `athlete_fitness.updated`: athlete_id, aggregate_form, last_activity_id
- `athlete_fitness.time_constants.fitted`: athlete_id, fitness_tau, fatigue_tau

## Implementation Notes
- The `form_descriptor` is the only fitness signal exposed to athletes and LLM agents. Raw scores produce anxiety and gaming behaviour — athletes optimise for the number rather than the training. The coach uses the descriptor to contextualise readiness in plain language.
- The historical fitness arc (for visualisations like the prediction arc) is reconstructed from `TwinState.athlete_fitness_id` chain rather than a dedicated time-series. This avoids a second time-series table while preserving the full history.
- When three-dimensional scores activate (Phase 6c), a migration adds the `aerobic`, `neuromuscular`, and `structural` columns as nullable. Existing `AthleteFitness` records are not backfilled — they retain the aggregate pair only. `FitnessUpdateService` populates all four when dimensional scoring is active.