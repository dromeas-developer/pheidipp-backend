# TwinState

Immutable historical record of what the twin system believed about an athlete at a specific point in time. Append-only — never updated or deleted.

## Purpose

Every coaching decision, race prediction, and training recommendation is grounded in a specific snapshot of the athlete's fitness, fatigue, form, thresholds, and readiness. `TwinState` is the audit trail that makes this reasoning transparent and reproducible.

## Schema

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
  training_goal_id: string           // UUID, FK → TrainingGoal (active at creation)

  // Context fields owned by TwinState itself
  data_tier: 1 | 2 | 3 | 4 | 5 | 6
  confidence_level: 'low' | 'medium' | 'high'
  trigger: TwinTrigger
  model_version: string               // frozen pipeline snapshot identifier
  created_at: string                  // ISO 8601

  // Inline snapshot — what the system believed at this point in time
  // These are the actual values used by coaching decisions, not references to mutable records
  fitness: number                     // aerobic equivalent
  fatigue: number                     // accumulated training load
  form: number                        // computed: fitness - fatigue

  // Threshold snapshots
  lt1_pace_sec_per_km: number | null
  lt1_power_watts: number | null
  lt1_hr_bpm: number | null
  lt2_pace_sec_per_km: number | null
  lt2_power_watts: number | null
  lt2_hr_bpm: number | null
  cp_watts: number | null             // Critical Power; null if no power data

  // Readiness context
  readiness_level: RecoveryModifierLevel  // from WellnessModifierService
  wellness_trend: WellnessTrend | null    // 7-day composite trend at snapshot time

  // Per-metric confidence breakdown (separate from coarse confidence_level)
  // Derived from threshold detection prior weights at snapshot time
  metric_confidence: {
    lt1_hr: TwinConfidenceLevel
    lt1_power: TwinConfidenceLevel | null    // null if no power data
    lt1_pace: TwinConfidenceLevel | null     // null if no pace data
    lt2_hr: TwinConfidenceLevel
    lt2_power: TwinConfidenceLevel | null      // null if no power data
    lt2_pace: TwinConfidenceLevel | null       // null if no pace data
    cp: TwinConfidenceLevel | null              // null if no power data
  }
}
```

## What Changed from the Previous Design

`TwinState` previously held foreign keys to `AthletePhysiology` and `AthleteFitness` records. This was broken: those records are mutable (updated in place), so TwinState FKs became stale over time. A TwinState claiming "at time T, fitness was record 123" would point to the current state of record 123, not its state at time T.

The current design inlines the actual values (fitness, fatigue, form, thresholds, readiness) at snapshot time. `TwinState` is now the authoritative historical record. `AthleteFitness`, `AthletePhysiology`, and `AthleteWellness` remain mutable current-state entities — they are the operational layer, not the historical layer.

This solves:

1. **Broken FK references**: TwinState owns its snapshot values. No stale pointers to mutable records.
2. **Historical fidelity**: Every TwinState contains the exact scores and thresholds that drove coaching decisions at that point in time.
3. **Query simplicity**: `SELECT * FROM twin_states WHERE athlete_id = ? ORDER BY created_at DESC` gives full fitness/threshold history without reconstruction logic.

## Invariants

- Append-only. No `UPDATE` or `DELETE` at any layer. `TwinStateRepository` exposes only `insert`, `get_latest`, and `get_history`.
- One TwinState per calibration event. Multiple TwinStates per day are possible (e.g. `activity_sync` followed by `wellness_update`).
- `training_goal_id` is frozen at creation time — it records which goal was active when this snapshot was taken, even if the goal is later superseded.
- `model_version` is frozen — it identifies the exact computation pipeline version, enabling reproducibility audits.
- `confidence_level` is recomputed from `AthletePhysiology.lt2.prior_weight` at each snapshot.

## Events

### Produced

| Event | Trigger | Version | Payload |
|---|---|---|---|
| `twin_recalibrated` | new TwinState inserted | v1 | `{athlete_id, twin_state_id, trigger, confidence_level, form, lt2_bpm, readiness_level}` |
| `twin_confidence_upgraded` | confidence_level increased | v1 | `{athlete_id, from_level, to_level, twin_state_id}` |
| `twin_model_ready` | first TwinState created (onboarding complete) | v1 | `{athlete_id}` |

### Consumed

| Event | Action | Version |
|---|---|---|
| `fitness_updated` | Create new TwinState with latest scores + current thresholds | v1 |
| `physiology_updated` | Create new TwinState with latest thresholds + current scores | v1 |
| `recovery_modifier_changed` (AMBER or RED only) | Create new TwinState with updated readiness context | v1 |

### What Each Trigger Means for the Mutable State Layer

| Trigger | AthletePhysiology changed? | AthleteFitness changed? | What TwinState inlines |
|---|---|---|---|
| `questionnaire` | Yes — bootstrapped from population norms | Yes — initialised to zero fitness/fatigue | Initial thresholds + zero fitness/fatigue/form |
| `activity_sync` | No — no threshold signal in this session | Yes — fitness/fatigue updated from load scores | Updated fitness/fatigue/form, unchanged thresholds |
| `calibration` | Yes — threshold detection fired | Yes — fitness/fatigue also updated | Updated thresholds + updated fitness/fatigue/form |
| `physiology_input` | Yes — lab or field test entered | No — fitness/fatigue unchanged | Updated thresholds, unchanged fitness/fatigue/form |
| `wellness_update` | No | No — only readiness context changes | Unchanged fitness/fatigue/thresholds, updated readiness |

## APIs

```yaml
GET /athletes/{athlete_id}/twin
Response: 200
  twin_state: TwinStateResponse  # includes inline fitness, thresholds, readiness values
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/twin/history
Query:
  limit?: number (default 20, max 100)
Response: 200
  history: TwinStateResponse[]  # ordered by created_at desc; each contains inline snapshot
Auth: Bearer JWT, require_self
```

## Context Assembly — What Agents Receive

`TwinContextAssemblerService` reads a single TwinState record (which contains inline snapshot values) and produces a coaching digest. No joins to AthleteFitness or AthletePhysiology needed — all values are already in TwinState.

```typescript
type TwinContextSummary = {
  // Derived from inline TwinState snapshot values
  form_descriptor: string            // e.g. "building — good readiness with fitness accumulating"
  readiness_level: RecoveryModifierLevel  // from inline readiness_level

  // Threshold targets (precision depends on metric_confidence for that signal)
  threshold_target_description: string
  // LOW:    "comfortably hard effort"
  // MEDIUM: "5:30–5:50/km at threshold, roughly 165–170 bpm"
  // HIGH:   "5:38/km at threshold, 168 bpm"

  lt2_pace_sec_per_km: number | null   // null if lt2_pace confidence is LOW or no threshold data
  lt2_power_watts: number | null       // null if lt2_power confidence is LOW or no power data
  cp_watts: number | null              // Critical Power; null if cp confidence is LOW

  // From TwinState itself
  data_tier: DataTier
  target_type: 'power' | 'gap' | 'description'
  confidence_level: TwinConfidenceLevel       // coarse signal derived from lt2.hr
  metric_confidence: TwinMetricConfidence     // per-metric confidence for precision consumers

  // Computed intent ranges (derived from inline threshold values)
  intent_ranges: IntentRange[]
}
```

## Performance Constraints

- Reads from single TwinState record; no joins needed.
- `get_latest(athlete_id)` is the most frequent query in the system — indexed on `(athlete_id, created_at DESC)`.
- History endpoint bounded by `limit` parameter (max 100).

## Retention

Indefinite. TwinState records accumulate over time — this is by design. Each record is small (~500 bytes). At one record per calibration event (roughly 2–5 per week for active athletes), this is ~100–260 records per year, or ~100KB–260KB per year per athlete.

## Append-Only Invariant

TwinState records are never updated or deleted. The `TwinStateRepository` exposes only:
- `insert(state: TwinState) → TwinState`
- `get_latest(athlete_id: UUID) → TwinState`
- `get_history(athlete_id: UUID, limit: int) → list[TwinState]`

No `update()` or `delete()` methods exist at any layer.

## Storage Model

| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `twin_states` table | append-only | strong | indefinite |

## Observability

- `twin_state.inserted` — every insert is logged
- `twin_state.per_athlete.daily_rate` — alert if > 5/day (indicates recalibration loop)
- `twin_state.confidence_upgrades.total` — tracks progress toward high confidence
- `twin_state.created.total` — overall volume metric
