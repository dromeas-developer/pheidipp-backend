# CyclePhaseLog — Menstrual Cycle Tracking Record

## Purpose
- Records each athlete-reported cycle start date, enabling phase computation
- The sole input for cycle phase classification; no ongoing daily input required
- Activates only for athletes with AthleteProfile.sex = 'female'

## TypeScript Schema

```typescript
type CycleLoggedBy = 'athlete_self_report' | 'coach_prompt_response'

type CyclePhaseLog = {
  id: string               // UUID, PK
  athlete_id: string       // UUID, FK → Athlete
  cycle_day_one_date: string  // YYYY-MM-DD; first day of menstruation
  logged_at: string        // ISO 8601
  logged_by: CycleLoggedBy
}

// Derived — not stored; computed on demand by CyclePhaseService
type CurrentCycleState = {
  phase: CyclePhase
  cycle_day_number: number        // 1-indexed from most recent cycle_day_one_date
  days_since_last_log: number
  using_personal_model: boolean   // true when AthleteProfile.cycle_personal_model is set
}
```

## Phase Computation

```typescript
// Default 28-day population boundaries
const DEFAULT_BOUNDARIES = {
  menstrual_end: 5,
  follicular_end: 13,
  ovulatory_end: 16
}

function computePhase(
  cycleDay: number,
  boundaries = DEFAULT_BOUNDARIES
): CyclePhase {
  if (cycleDay <= boundaries.menstrual_end) return 'menstrual'
  if (cycleDay <= boundaries.follicular_end) return 'follicular'
  if (cycleDay <= boundaries.ovulatory_end) return 'ovulatory'
  return 'luteal'
}

// Returns 'unknown' when:
// - No CyclePhaseLog exists for this athlete
// - Most recent log is > 45 days ago (anomaly/missing data)
```

When `AthleteProfile.cycle_personal_model` is set (Phase 4f+), the phase boundaries from the personal model replace `DEFAULT_BOUNDARIES`. The computation logic is identical; only the boundary values change.

## Recovery Modifier Composite Adjustments

These adjustments are applied by `WellnessModifierService` to the composite score before GREEN/AMBER/RED classification. Population priors until `cycle_personal_model` is set.

| Phase | Composite adjustment | Physiological rationale |
|---|---|---|
| `menstrual` | +0.2 to +0.4 (days 1-2 weighted higher) | Lowest oestrogen and progesterone; reduced readiness |
| `follicular` | −0.1 | Peak adaptation window; slight positive modifier |
| `ovulatory` | 0.0 | Performance peak; no adjustment |
| `luteal` early (days 17-23) | +0.2 | Progesterone rising; moderate readiness reduction |
| `luteal` late (days 24+) | +0.4 | Late luteal sleep degradation; strongest modifier |
| `unknown` | 0.0 | No adjustment when phase is unknown |

## Luteal Thermoregulatory Modifier

During the luteal phase, a temperature offset of +0.35°C (midpoint of +0.3–0.5°C range) is added to `WeatherForecast.heat_index_c` before weather adjustment computation. This stacks additively with ambient weather because the mechanisms are physiologically distinct (central thermostat shift vs ambient heat stress). See `02-computations/wellness-modifier.md`.

## Ovulatory Structural Load Flag

During the ovulatory phase, `Activity.quality_flags.elevated_laxity_risk = true` is set during FIT ingestion. This annotates the record for downstream coaching reference — it does not affect `calibration_eligible`.

## Invariants
- CyclePhaseLog only created for athletes with `AthleteProfile.sex = 'female'`. `POST /cycle` returns 403 for other athletes.
- No unique constraint on `(athlete_id, cycle_day_one_date)` — an athlete can correct a mis-entry by logging a new date. The most recent log is always the active one.
- No DELETE. Logs accumulate as the training history of the coaching relationship.
- Phase computation returns `unknown` (not an error) when no log exists or the most recent log is stale (> 45 days). This is a valid, graceful state.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `cycle_day_one_logged` | Log inserted | v1 | `{athlete_id, cycle_day_one_date, logged_by}` |
| `cycle_phase_changed` | Phase changes based on new log or day advancement | v1 | `{athlete_id, previous_phase, new_phase, cycle_day}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `cycle_day_one_logged` | Triggers `CyclePersonalisationTask` if ≥3 complete cycles | v1 |

## APIs

```yaml
POST /athletes/{athlete_id}/cycle
Request:
  cycle_day_one_date: string  # YYYY-MM-DD
Response: 201
  log: CyclePhaseLogResponse
  current_phase: CurrentCycleState
Auth: Bearer JWT, require_self
Note: Returns 403 if AthleteProfile.sex != 'female'

GET /athletes/{athlete_id}/cycle/current
Response: 200
  current: CurrentCycleState
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/cycle/history
Response: 200
  logs: CyclePhaseLogResponse[]  # ordered by cycle_day_one_date desc
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `cycle_phase_logs` table | append-only | strong | indefinite |

Index: `(athlete_id, cycle_day_one_date DESC)` for most-recent log query.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes | POST only | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- Cycle start date log records
- Phase computation (via `CyclePhaseService`)

Does Not Own:
- How phase feeds recovery modifier → `02-computations/wellness-modifier.md`
- Cycle personalisation model fitting → `01-entities/athlete-profile.md` (`cycle_personal_model`)
- Proactive check-in prompt timing → `03-agents/wellness-alert-agent.md`

## Failure Semantics
- `POST /cycle` for a non-female athlete → 403 Forbidden (not 422)
- Duplicate date logged → second log inserted; most recent is used; no error

## Performance Constraints
- `POST /cycle`: p95 < 100ms
- `GET /cycle/current`: p95 < 30ms (single indexed lookup)

## Observability
Metrics:
- `cycle_phase_log.athletes_tracking`: count of female athletes with ≥1 log
- `cycle_phase_log.coverage`: percentage of female athletes with active cycle tracking
Logs:
- `cycle_phase_log.created`: athlete_id, logged_by
