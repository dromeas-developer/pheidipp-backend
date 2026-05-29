# TwinState — Snapshot Assembler

## Purpose
- Records what the twin knew at a specific point in time by referencing the then-current AthletePhysiology and AthleteFitness records
- Append-only audit trail of every twin recalibration event
- The entity consumed by context assembly for LLM agents

## What Changed From the Previous Design

`TwinState` no longer duplicates physiological parameter values or fitness/fatigue scores inline. Instead it holds foreign keys to the `AthletePhysiology` and `AthleteFitness` records that were current at the time of the snapshot. This eliminates three problems:

1. **Noise**: A short easy jog previously caused a full TwinState row with unchanged threshold fields to be written. Now it causes `AthleteFitness` to update; `TwinState` appends a new row referencing the new fitness record and the unchanged physiology record.

2. **Duplication**: LT1, LT2, FTP, VO2max were duplicated between `TwinState` and the implicit physiology tracking. Now there is one authoritative source (`AthletePhysiology`) and `TwinState` references it.

3. **Lab test integration**: A lab test updates `AthletePhysiology` which triggers a new `TwinState` snapshot. The clean separation makes it obvious that the lab test updated physiology, not fitness/fatigue.

## TypeScript Schema

```typescript
type TwinTrigger =
  | 'questionnaire'    // onboarding bootstrap; initial AthletePhysiology + AthleteFitness created
  | 'activity_sync'    // calibration-eligible activity updated AthleteFitness
  | 'calibration'      // activity updated both AthleteFitness + AthletePhysiology threshold estimates
  | 'physiology_input' // lab_test or field_test updated AthletePhysiology without an activity
  | 'wellness_update'  // significant wellness trend detected; readiness context updated

type TwinState = {
  id: string                          // UUID, PK
  athlete_id: string                  // UUID, FK → Athlete
  training_block_id: string           // UUID, FK → TrainingBlock (active at creation)

  // References to the current state of the two domain entities
  athlete_physiology_id: string       // UUID, FK → AthletePhysiology
  athlete_fitness_id: string          // UUID, FK → AthleteFitness

  // Context fields owned by TwinState itself
  data_tier: 1 | 2 | 3 | 4 | 5 | 6
  confidence_level: 'low' | 'medium' | 'high'
  trigger: TwinTrigger
  model_version: string               // frozen pipeline snapshot identifier
  created_at: string                  // ISO 8601
}
```

## What Each Trigger Means for the Referenced Entities

| Trigger | AthletePhysiology changed? | AthleteFitness changed? |
|---|---|---|
| `questionnaire` | Yes — bootstrapped from population norms | Yes — initialised to zero fitness/fatigue |
| `activity_sync` | No — no threshold signal in this session | Yes — fitness/fatigue updated from load scores |
| `calibration` | Yes — threshold detection fired | Yes — fitness/fatigue also updated |
| `physiology_input` | Yes — lab or field test entered | No — fitness/fatigue unchanged |
| `wellness_update` | No | No — only readiness context changes |

## Confidence Level

Owned by `TwinState`, not by `AthletePhysiology`. Confidence reflects the accumulated Bayesian evidence across all physiological parameters, translated to the coaching-language tiers.

```typescript
// Confidence transitions — see 00-foundations/confidence-model.md for full detail
// LOW:    questionnaire bootstrap only
// MEDIUM: AthletePhysiology.lt2.prior_weight >= 4.0
//         (approx 4 HR deflection sessions at default weight)
// HIGH:   AthletePhysiology.lt2.prior_weight >= 8.0
//         OR ≥ 2 sessions with training_rr_inflection source
```

`confidence_level` is computed at TwinState creation time from the current `AthletePhysiology.lt2.prior_weight`. It ratchets upward only — it is never decreased on a new TwinState record even if the prior has partially decayed.

## Context Assembly — What Agents Receive

`TwinContextAssemblerService` reads the TwinState + its referenced entities and produces a coaching digest:

```typescript
type TwinContextSummary = {
  // From AthleteFitness
  form_descriptor: string            // e.g. "building — good readiness with fitness accumulating"
  readiness_level: RecoveryModifierLevel  // after wellness modifier applied

  // From AthletePhysiology (precision depends on confidence_level)
  threshold_target_description: string
  // LOW:    "comfortably hard effort, about Zone 3"
  // MEDIUM: "5:30–5:50/km at threshold, roughly 165–170 bpm"
  // HIGH:   "5:38/km at threshold, 168 bpm"

  lt2_pace_sec_per_km: number | null   // null if LOW confidence
  ftp_watts: number | null             // null if no power data ever processed

  // From TwinState itself
  data_tier: DataTier
  target_type: 'power' | 'pace' | 'effort_description'
  confidence_level: TwinConfidenceLevel
}
```

The LLM agent receives `TwinContextSummary` — never raw `AthletePhysiology` or `AthleteFitness` fields.

## Append-Only Invariant

TwinState records are never updated or deleted. The `TwinStateRepository` exposes only:
- `insert(state: TwinState) → TwinState`
- `get_latest(athlete_id: UUID) → TwinState`
- `get_history(athlete_id: UUID, limit: int) → list[TwinState]`

No `update()` or `delete()` methods exist at any layer.

## When a New TwinState Is Written

```typescript
// A new TwinState row is appended when any of the following change:
// 1. AthleteFitness.aggregate.form changes by > 1 unit (meaningful fitness shift)
// 2. AthletePhysiology is updated (any parameter posterior shift > 1 unit)
// 3. confidence_level transitions (always writes a new row regardless of magnitude)
// 4. wellness_update trigger fires (readiness context changes)

// A new TwinState is NOT written when:
// - A non-calibration-eligible activity is processed (no fitness/physiology change)
// - A wellness record is ingested but the modifier level does not change
// - AthleteFitness.form changes by ≤ 1 unit (noise threshold)
```

## model_version

Identifies the exact pipeline snapshot that produced this TwinState. Increments when:
- Load computation formula changes (ingestion_pipeline_version changes)
- Banister time constants transition from population to individual fitted
- Confidence level transition thresholds are revised

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `twin_recalibrated` | Every new TwinState insertion | v1 | `{twin_state_id, previous_id, trigger, confidence_level, athlete_fitness_id, athlete_physiology_id}` |
| `twin_confidence_upgraded` | When `confidence_level` increases | v1 | `{twin_state_id, from, to}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `fitness_updated` | If form shift > 1: append new TwinState | v1 |
| `physiology_updated` | Append new TwinState | v1 |
| `recovery_modifier_changed` (AMBER/RED) | Append new TwinState with `wellness_update` trigger | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/twin
Response: 200
  twin_state: TwinStateResponse
  physiology: AthletePhysiologyResponse  # current referenced physiology
  fitness_summary: { form_descriptor: string, readiness_level: string }
  # raw fitness scores are never included
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/twin/history
Query:
  limit?: number (default 20, max 100)
Response: 200
  history: TwinStateResponse[]  # ordered by created_at desc
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `twin_states` table | append-only | strong | indefinite |

Index: `(athlete_id, created_at DESC)` for `get_latest()`.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (read-only) | No | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- The append-only snapshot audit trail
- `data_tier`, `confidence_level`, `trigger`, `model_version`
- Context assembly for LLM agents (via `TwinContextAssemblerService`)

Does Not Own:
- Physiological parameter estimates → `01-entities/athlete-physiology.md`
- Fitness/fatigue/form scores → `01-entities/athlete-fitness.md`
- How load scores are computed → `02-computations/load-computation.md`
- How thresholds are detected → `02-computations/threshold-detection.md`
- How wellness modifier affects readiness → `02-computations/wellness-modifier.md`

## Failure Semantics
- TwinState insert failure → previous TwinState remains current; retry; alert after 3 failures
- Referenced `athlete_physiology_id` or `athlete_fitness_id` not found → integrity violation; alert

## Performance Constraints
- `get_latest()`: p95 < 20ms
- `insert()`: p95 < 50ms
- `TwinContextAssemblerService.assemble()`: p95 < 30ms (reads 3 entities; all cached)

## Observability
Metrics:
- `twin_state.created.total`: by trigger type
- `twin_state.confidence_upgrades.total`: by transition (low→medium, medium→high)
- `twin_state.per_athlete.daily_rate`: average TwinState records per athlete per day (monitors noise)
Logs:
- `twin_state.inserted`: athlete_id, trigger, confidence_level, model_version