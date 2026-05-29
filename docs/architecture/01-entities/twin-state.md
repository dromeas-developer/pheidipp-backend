# TwinState — Append-Only Physiological Model Snapshot

## Purpose
- Records the twin's understanding of an athlete at a specific point in time
- Never updated in place; every recalibration appends a new record
- The most recent record is the current state; older records are the audit trail

## TypeScript Schema

```typescript
type TwinTrigger =
  | 'questionnaire'    // onboarding bootstrap
  | 'activity_sync'    // calibration-eligible activity processed
  | 'calibration'      // dedicated calibration session produced threshold update
  | 'wellness_update'  // significant wellness trend detected

type TwinState = {
  id: string                       // UUID, PK
  athlete_id: string               // UUID, FK → Athlete
  training_block_id: string        // UUID, FK → TrainingBlock (active at creation)

  // Layer 1 — Fitness & Fatigue (aggregate; splits into 6 fields in Phase 6c)
  fitness_score: number
  fatigue_score: number

  // Layer 1 — Three-dimensional (Phase 6c+; null until activated)
  aerobic_fitness: number | null
  aerobic_fatigue: number | null
  neuromuscular_fitness: number | null
  neuromuscular_fatigue: number | null
  structural_fitness: number | null
  structural_fatigue: number | null

  // Layer 2 — Thresholds
  lt1_estimate_bpm: number
  lt2_estimate_bpm: number
  max_hr_estimate_bpm: number
  ftp_estimate_watts: number | null    // null until power data processed
  vo2max_estimate: number | null       // ml/kg/min; null until sufficient data

  // Context
  data_tier: 1 | 2 | 3 | 4 | 5 | 6
  confidence_level: 'low' | 'medium' | 'high'
  trigger: TwinTrigger
  model_version: string               // frozen pipeline snapshot identifier
  created_at: string                  // ISO 8601
}
```

## Invariants
- **Append-only.** No UPDATE or DELETE operations exist on this table. The ORM model must not expose them. Enforcement is at repository level — `TwinStateRepository` has only `insert()` and `get_latest()` and `get_history()`.
- `ftp_estimate_watts` is null until at least one activity with `has_power = true` has been processed through threshold detection.
- `vo2max_estimate` is null until sufficient progressive effort data has been accumulated.
- `confidence_level` never decreases in a new record. It ratchets upward only.
- When the three-dimensional Layer 1 fields are null (Phases 1–6b), `fitness_score` and `fatigue_score` are the canonical Layer 1 values. When three-dimensional fields are populated (Phase 6c+), all six are written; the aggregate fields are retained for backward compatibility.
- `model_version` identifies the exact pipeline snapshot that produced this record. A change to the Banister time constants, load formulas, or threshold detection algorithm increments `model_version`.

## Confidence Level Transitions

See `00-foundations/confidence-model.md` for the authoritative definition.

| From | To | Requirement |
|---|---|---|
| `low` | `medium` | 4 calibration-eligible sessions with `has_hr = true` processed |
| `medium` | `high` | 2 sessions with `has_rr_intervals = true` OR 1 dedicated calibration run |

## Recalibration Triggers

### `questionnaire`
Onboarding completes. Produces the first TwinState with `confidence = low`. Values are derived from population norms filtered by age and `fitness_level` from `TrainingBlock`. `ftp_estimate_watts` and `vo2max_estimate` are null.

### `activity_sync`
A `calibration_eligible` activity is processed. `fitness_score` and `fatigue_score` update via the Banister model. For sessions with HR or RR data, threshold estimates may also update via the Bayesian mechanism. See `02-computations/threshold-detection.md`.

### `calibration`
A session explicitly structured to produce threshold signal (progressive intensity, ≥3 distinct steps) has been processed. Layer 2 threshold estimates receive a higher-weight Bayesian update. Used when `confidence_level` transitions or when a dedicated calibration session is detected.

### `wellness_update`
`WellnessModifierService` has detected a transition in the recovery modifier level (e.g. GREEN → AMBER). Layer 1 fitness/fatigue scores are unchanged. The new TwinState carries updated context for the context assembly service.

## Context Assembly — What Agents Receive

TwinState is never passed raw to an LLM agent. `TwinContextAssemblerService` translates fields into coaching-relevant language:

```typescript
type TwinContextSummary = {
  readiness_level: 'green' | 'amber' | 'red'
  readiness_reason: string           // plain language
  fitness_form_descriptor: string    // "building", "peaked", "tapering", "recovering"

  // Threshold targets expressed at confidence-appropriate precision:
  // LOW: effort descriptions ("Zone 2 effort")
  // MEDIUM: ranges ("5:30–5:50/km at threshold")
  // HIGH: point estimates ("5:38/km at threshold")
  threshold_target_description: string
  lt2_pace_sec_per_km: number | null  // null if LOW confidence

  data_tier: DataTier
  target_type: 'power' | 'pace' | 'effort_description'
  confidence_level: TwinConfidenceLevel
}
```

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `twin_recalibrated` | Every new TwinState insertion | v1 | `{twin_state_id, previous_id, trigger, confidence_level, fitness_score, fatigue_score}` |
| `twin_confidence_upgraded` | When `confidence_level` increases | v1 | `{twin_state_id, from, to}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_calibration_eligible` | Triggers `TwinRecalibrationTask` | v1 |
| `recovery_modifier_changed` (AMBER/RED) | Triggers `wellness_update` recalibration | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/twin
Response: 200
  twin_state: TwinStateResponse  # most recent TwinState
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/twin/history
Query:
  limit?: number (default 20, max 100)
Response: 200
  history: TwinStateResponse[]   # ordered by created_at desc
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `twin_states` table | append-only | strong | indefinite |

Index: `(athlete_id, created_at DESC)` for efficient `get_latest()` queries.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (read-only) | No | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

The `TwinStateRepository` exposes only:
- `insert(twin_state: TwinState) → TwinState`
- `get_latest(athlete_id: UUID) → TwinState`
- `get_history(athlete_id: UUID, limit: int) → list[TwinState]`

## Runtime Ownership
Owns:
- The append-only twin model snapshot
- Confidence level tracking
- Context assembly for LLM agents

Does Not Own:
- How load scores are computed → `02-computations/load-computation.md`
- How thresholds are detected → `02-computations/threshold-detection.md`
- How wellness modifier affects readiness → `02-computations/wellness-modifier.md`
- Plan generation decisions → `01-entities/training-plan.md`

## Failure Semantics
- `TwinRecalibrationTask` failure → previous TwinState remains current; task retries up to 3 times; alert after 3 failures
- If `confidence_level` cannot be determined (insufficient data), `low` is used

## Performance Constraints
- `get_latest()`: p95 < 20ms (indexed query)
- `insert()`: p95 < 50ms
- `get_history()`: p95 < 100ms

## Observability
Metrics:
- `twin_state.recalibrations.total`: by trigger type
- `twin_state.confidence_upgrades.total`: by transition (low→medium, medium→high)
- `twin_state.recalibration.latency_ms`
Logs:
- `twin_state.inserted`: athlete_id, trigger, confidence_level, model_version

## Implementation Notes
- The three-dimensional Layer 1 fields (6 new fields) are added as nullable columns in Phase 6c. Existing records are not backfilled — they retain null. The context assembly service handles both formats.
- `model_version` must be incremented whenever the Banister time constants, load computation formula, or threshold detection algorithm changes materially. This enables auditing of which algorithm produced a given TwinState.
- The Banister individual time constants from `AthleteProfile.banister_constants` are used in `TwinRecalibrationService` when non-null. The `model_version` reflects which constant set was used.
