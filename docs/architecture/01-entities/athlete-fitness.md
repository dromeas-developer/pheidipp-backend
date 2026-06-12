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
  aerobic: {
    fitness_tau_days: number    // population default: 42
    fatigue_tau_days: number    // population default: 7
  }
  neuromuscular: {
    fitness_tau_days: number    // population default: 21
    fatigue_tau_days: number    // population default: 3
  }
  structural: {
    fitness_tau_days: number    // population default: 56
    fatigue_tau_days: number    // population default: 14
  }
  source: 'population_default' | 'individual_fitted'
  fitted_at: string | null     // ISO date; null if source = 'population_default'
}

type AthleteFitness = {
  id: string                          // UUID, PK
  athlete_id: string                  // UUID, FK → Athlete (one-to-one; current state)

  // Single aggregate score pair (always populated)
  aggregate: DimensionalScores

  // Three-dimensional scores (populated when data quality permits)
  aerobic: DimensionalScores | null
  neuromuscular: DimensionalScores | null
  structural: DimensionalScores | null

  // Time constants used in the most recent update
  time_constants: BanisterTimeConstants

  // Context
  last_activity_id: string | null     // FK → Activity; the session that last updated this record
  updated_at: string                  // ISO 8601
}

type AthleteFitnessResponse = {
  form_descriptor: string              // plain-language readiness (e.g., "fresh", "moderate fatigue")
  form_trend: 'improving' | 'stable' | 'declining'  // 7-day trend
  dimensional_readiness: {
    aerobic: string                    // plain-language descriptor
    neuromuscular: string | null       // null if dimensional scoring not active
    structural: string | null          // null if dimensional scoring not active
  }
  last_updated: string                 // ISO 8601
}
// This is the ONLY fitness response type. The internal AthleteFitness entity
// (with raw scores) is NEVER serialized to athletes.
```

## Invariants
- One `AthleteFitness` record per athlete. **Mutable current-state entity** — scores are updated in place on every calibration-eligible activity. Historical state is captured in `TwinState` (inline values).
- `aggregate` is always populated. `aerobic`, `neuromuscular`, `structural` are populated when data quality permits dimension-specific scoring.
- `form` is always a computed field (`fitness - fatigue`). It is stored for query convenience but derived value — it must always equal `fitness - fatigue`.
- `time_constants.source` starts as `population_default`. It transitions to `individual_fitted` **once** when `TimeConstantFittingService` produces a fit with sufficient data quality (≥ 12 weeks calibration-eligible data, R² threshold met). **It never reverts to `population_default`.**
  
  `BanisterTimeConstants.fit_quality_score` tracks R², residual variance, and prediction error on holdout. If `fit_quality_score` degrades below threshold over consecutive fittings, an alert is raised for manual review. A manual override endpoint allows admins to force `source = 'population_default'` when individual fitting produces poor results.
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
  # Contains ONLY descriptors and trends — raw scores (fitness, fatigue, form numbers) are never included
  # The numerical values are internal to the twin model
  # Enforced by the API layer — the repository returns the full entity but the response serializer strips raw scores
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

Note: Raw fitness/fatigue scores are never returned as numbers to the athlete. `GET /fitness` returns only the `form_descriptor`, `form_trend`, and `dimensional_readiness`. The numerical values are internal to the twin model.

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_fitness` table | mutable (scores updated in place) | strong | indefinite |

Unique constraint: `(athlete_id)` — one record per athlete.

Historical fitness state is captured in `TwinState` records (inline snapshot values). The `TwinState` is the authoritative historical record for fitness/fatigue/form at any point in time.

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
- The historical fitness arc (for visualisations like the prediction arc) is reconstructed from `TwinState` records, which contain inline snapshot values of fitness, fatigue, and form at each point in time.
- Banister update formula and time constant semantics are defined in `02-computations/banister-update.md`.
- Lab tests update `AthletePhysiology` — not `AthleteFitness`. A lab test triggers a new `TwinState` via `trigger = 'calibration'` but does not recalculate fitness/fatigue scores.