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

### Cycle Length Learning

The default 28-day assumption is a population prior. Individual athletes vary from ~21 to ~35 days. Using the wrong cycle length misclassifies phases — an athlete with a 32-day cycle classified under 28-day boundaries would be marked "luteal" 4 days too early, receiving a readiness penalty (+0.15 to +0.30) during what is actually still her follicular adaptation window (−0.10).

**Learning mechanism:** `CyclePersonalisationTask` (triggered by `cycle_day_one_logged` event when ≥3 complete cycles exist) computes the athlete's actual cycle length from logged data:

```
cycle_length[i] = cycle_day_one_date[i] - cycle_day_one_date[i-1]
median_cycle_length = median(cycle_length[1..n])
```

**Minimum data:** 3 complete cycles (3 intervals → 4 log entries). Until then, `DEFAULT_BOUNDARIES` (28-day assumption) applies.

**Storage:** `AthleteProfile.cycle_personal_model.avg_cycle_length_days`

**Fallback:** When `cycle_personal_model` is null, the 28-day default applies. The day-number calculation (`cycle_day_number = today - cycle_day_one_date + 1`) works regardless of assumed cycle length — the issue is that phase boundaries shift for shorter/longer cycles.

### Phase Boundary Fitting

Cycle length alone doesn't resolve phase boundaries — different athletes have different relative phase proportions. The vision says the model learns "phase durations" (plural), implying per-phase boundary fitting from execution data.

**Approach:** `CyclePersonalisationTask` analyses execution data across multiple cycles to detect phase transitions:

1. For each completed cycle, compute execution quality metrics per day (pace-at-HR ratio, GAP deviation, RPE)
2. Identify day ranges where execution metrics shift consistently across cycles
3. Fit phase boundaries to the observed transition points
4. Store fitted boundaries in `cycle_personal_model.phase_boundaries`

**Minimum data:** 3+ complete cycles with sufficient quality sessions in each phase to detect patterns. A higher bar than cycle-length learning.

**Fallback:** Use cycle-length-proportional boundaries (`menstrual_end = cycle_length * 5/28`, etc.) until individual data is sufficient.

### Execution Correlation Analysis

The vision promises the model learns "how this specific athlete's execution data and wellness signals correlate with each phase." This analysis determines whether the athlete is phase-affected and how strongly.

**Execution correlation:**
- For each phase, compute average execution quality relative to the athlete's overall baseline
- If execution is consistently worse in luteal across multiple cycles, the athlete is phase-affected
- `phase_sensitivity[phase]` scales the population prior adjustment (0.0 = no correlation, 1.0 = full population effect, >1.0 = stronger than population average)

**Wellness correlation (Phase 4f+):**
- For each wellness signal, check whether HRV, sleeping HR, and sleep quality show phase-dependent patterns
- If HRV is systematically lower in luteal, the wellness deviation score should use a luteal-adjusted baseline to avoid double-counting (cycle adjustment + wellness deviation)
- Requires per-phase baselines (one baseline per signal per phase per athlete) — a future extension of `AthleteWellnessBaseline`

**Storage:** `AthleteProfile.cycle_personal_model.phase_sensitivity: Record<CyclePhase, number>`

## Recovery Modifier Composite Adjustments

These adjustments are applied by `WellnessModifierService` to the composite score before GREEN/AMBER/RED classification. Population priors until `cycle_personal_model` is set. Values are in **IQR units** (see `02-computations/wellness-modifier.md` for derivation).

| Phase | Composite adjustment (IQR units) | Physiological rationale |
|---|---|---|
| `menstrual` | +0.30 (day ≤2), +0.15 (day 3-5) | Lowest oestrogen and progesterone; reduced readiness |
| `follicular` | −0.10 | Peak adaptation window; slight positive modifier |
| `ovulatory` | 0.0 | Performance peak; no adjustment |
| `luteal` early (days 17-23) | +0.15 | Progesterone rising; moderate readiness reduction |
| `luteal` late (days 24+) | +0.30 | Late luteal sleep degradation; strongest modifier |
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
- **Mutability vs Immutability Tension:** `CyclePhaseLog` allows correction (new log with corrected `cycle_day_one_date` supersedes). `AdaptationObservation` is append-only and stores `cycle_phase` at observation time. If an athlete corrects their cycle day one date, all past `AdaptationObservation` records have incorrect `cycle_phase` values that **cannot be updated**.
  
  **Resolution:**
  1. `AdaptationObservation.cycle_phase` is a **point-in-time classification** based on the log active at observation time. It is not retroactively corrected.
  2. `CyclePersonalisationTask` (≥ 3 complete cycles) re-fits the personal model using **all historical logs**. The personal model absorbs corrections.
  3. For analysis requiring accurate historical phases: re-compute phase from the corrected log history at query time (not from stored `cycle_phase`).
  
  **Audit trail:** `AdaptationObservation.cycle_phase_computation_basis` records whether phase was derived from default boundaries or personal model at observation time.

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

### Vision Phase Mapping

The following maps vision phase descriptions (`docs/vision/twin/womens-cycle.md`) to architecture computation steps.

| Vision Phase | Architecture Phase | Day Boundaries (Default) | Composite Adjustment | Additional Effects |
|---|---|---|---|---|
| Menstrual (days 1-5, "approximately") | `menstrual` | ≤5 (hard cutoff) | +0.30 (day ≤2), +0.15 (day 3-5) | None |
| Follicular (days 6-13, "approximately") | `follicular` | 6-13 | −0.10 | None |
| Ovulatory (days 12-16, "approximately") | `ovulatory` | 14-16 | 0.0 | `elevated_laxity_risk` flag |
| Luteal (days 17-28, "approximately") | `luteal` | 17+ | +0.15 (early), +0.30 (late ≥24) | +0.35°C temp offset in weather adjustment |

**Vision-to-architecture alignment notes:**
- Vision: "approximately" day ranges → Architecture: hard cutoffs via `DEFAULT_BOUNDARIES`; personal model replaces with fitted boundaries
- Vision: "first two days weighted highest" in menstrual → Architecture: day ≤2 → +0.30, day 3-5 → +0.15
- Vision: "lean into quality sessions" in follicular → Architecture: −0.10 composite adjustment (readiness boost)
- Vision: "performance peak" in ovulatory → Architecture: 0.0 composite = no penalty (peak is implicit, not a positive adjustment); injury risk is explicit via flag
- Vision: "core temp +0.3-0.5°C in luteal" → Architecture: `LUTEAL_TEMP_OFFSET_C = 0.35` (midpoint); feeds into weather adjustment, not composite
- Vision: "sleep quality degrades toward end of luteal" → Architecture: late luteal (day ≥24) gets +0.30; compounding with sleep deviation is implicit in weighted sum
- Vision: "model learns individual pattern" → Architecture: `cycle_personal_model` replaces boundaries and scales adjustments via `phase_sensitivity`
- Vision: "3 cycles before calibration" → Architecture: `CyclePersonalisationTask` triggered by `cycle_day_one_logged` event when ≥3 complete cycles
- Vision: "athlete logs day one only" → Architecture: `POST /cycle` accepts `cycle_day_one_date`; no ongoing daily input
- Vision: "coach references phase only when relevant" → Architecture: coaching agent receives phase context; language guidance is vision-only (correctly out of scope for architecture)

**Unknown phase handling:** Vision doesn't explicitly address missing cycle data. Architecture returns `unknown` with 0.0 adjustment — graceful degradation that preserves composite accuracy when phase data is unavailable.

### Entity References

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
