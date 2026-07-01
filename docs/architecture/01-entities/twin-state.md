# TwinState

Immutable historical record of what the twin system believed about an athlete at a specific point in time. Append-only — never updated or deleted.

## Purpose

Every coaching decision, race prediction, and training recommendation is grounded in a specific snapshot of the athlete's fitness, fatigue, form, thresholds, and readiness. `TwinState` is the audit trail that makes this reasoning transparent and reproducible.

## Schema

```typescript
type TwinTrigger =
  | 'questionnaire'    // onboarding bootstrap; initial AthletePhysiology + AthleteFitness created
  | 'activity_sync'    // calibration-eligible activity updated AthleteFitness (no threshold shift)
  | 'calibration'      // activity updated both AthleteFitness + AthletePhysiology threshold estimates
  | 'physiology_input' // lab_test or field_test updated AthletePhysiology without an activity
  | 'wellness_update'  // significant wellness trend detected; readiness context updated

type TwinConfidenceLevel = 'low' | 'medium' | 'high'

type TwinState = {
  id: string                          // UUID, PK
  athlete_id: string                  // UUID, FK → Athlete
  training_goal_id: string           // UUID, FK → TrainingGoal (active at creation)
  activity_id: string | null         // UUID, FK → Activity. Null for questionnaire/physiology_input/wellness_update.

  // Context fields owned by TwinState itself
  data_tier: 1 | 2 | 3 | 4 | 5 | 6
  confidence_level: TwinConfidenceLevel
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

## Design Rationale: Inline Snapshots vs. Foreign Keys

This design **inlines** fitness, fatigue, thresholds, and readiness values directly into `TwinState` rather than using foreign keys to mutable entities (`AthleteFitness`, `AthletePhysiology`, `AthleteWellness`).

**Why Inline Snapshots?**

1.  **Temporal Correctness**: `TwinState` is an audit trail — it must capture what the system believed at time T. If it held FKs to mutable records, those references would drift as the operational layer updates, breaking historical fidelity.
2.  **Query Simplicity**: Historical queries are straightforward: `SELECT * FROM twin_states WHERE athlete_id = ? ORDER BY created_at DESC` returns the complete fitness/threshold history without complex joins or temporal reconstruction logic.
3.  **Audit Trail Integrity**: Every coaching decision, race prediction, and training recommendation can be traced back to the exact snapshot that drove it. The snapshot is self-contained and immutable.

**Separation of Concerns:**

-   **`TwinState` (Immutable)**: Historical record — what the twin believed at time T. Never updated.
-   **`AthleteFitness`, `AthletePhysiology`, `AthleteWellness` (Mutable)**: Operational current state — updated in place as new data arrives.

This separation ensures the **historical layer** (TwinState) and **operational layer** (mutable entities) remain independent and serve their distinct purposes without coupling.

## Invariants

### 1. Append-Only
No `UPDATE` or `DELETE` at any layer. `TwinStateRepository` exposes only `insert`, `get_latest`, `get_by_activity`, and `get_history`.

### 2. One TwinState Per Calibration Event
Multiple TwinStates per day are possible (e.g., `activity_sync` followed by `wellness_update`), but only **one** TwinState per `activity_id`. See "Concurrency & Coordination" for deduplication logic.

### 3. Frozen Context
- `training_goal_id` is frozen at creation time — it records which goal was active when this snapshot was taken, even if the goal is later superseded.
- `model_version` is frozen — it identifies the exact computation pipeline version, enabling reproducibility audits.
- `activity_id` is frozen — it links the snapshot to the specific triggering event (if applicable).

### 4. Confidence Level Derivation
`confidence_level` is recomputed from `min(AthletePhysiology.lt1.hr.prior_weight, AthletePhysiology.lt2.hr.prior_weight)` at each snapshot. The global signal is the minimum of LT1 HR and LT2 HR confidence.

```typescript
function deriveConfidenceLevel(physiology: AthletePhysiology): TwinConfidenceLevel {
  const lt1_hr_weight = physiology.lt1.hr.prior_weight;
  const lt2_hr_weight = physiology.lt2.hr.prior_weight;
  const min_weight = Math.min(lt1_hr_weight, lt2_hr_weight);

  if (min_weight >= CONFIDENCE_THRESHOLD_HIGH) return 'high';
  if (min_weight >= CONFIDENCE_THRESHOLD_MEDIUM) return 'medium';
  return 'low';
}

// Example thresholds (finalize with data science):
const CONFIDENCE_THRESHOLD_MEDIUM = 15.0;  // ~3 calibration sessions
const CONFIDENCE_THRESHOLD_HIGH = 40.0;    // ~8-10 calibration sessions + consistency
```

### 5. Confidence Field Usage
- **`confidence_level`** is a **convenience signal** derived as `min(LT1 HR, LT2 HR)`. It exists for simple consumers (plan structure gates, race prediction availability, first-message language tier).
- **`metric_confidence`** is the **primary confidence mechanism** — per-metric breakdown used by workout generation, checkpoint scheduling, and post-workout analysis.

**Decision rule:** If the consumer's behavior changes based on *which* metric is uncertain, use `metric_confidence`. If it needs a single "is this athlete ready for precise coaching?" gate, use `confidence_level`.

See `00-foundations/confidence-model.md` for full semantics.

## Concurrency & Coordination

### Dual-Trigger Sessions
A calibration-eligible session can trigger BOTH `fitness_updated` AND `physiology_updated` (if threshold posterior shifted > 1 bpm). Both events independently trigger `TwinRecalibrationService`, which would otherwise create two `TwinState` records from the same session.

**Resolution:** The `fitness_updated` event handler MUST skip insertion when it detects a `TwinState` record already exists for the same `activity_id`.

```python
# TwinRecalibrationService.insert_if_not_exists
def insert_if_not_exists(athlete_id, activity_id, trigger, snapshot_data) -> TwinState:
    # Check for ANY existing TwinState linked to this activity
    existing = repo.get_by_activity(athlete_id, activity_id)
    
    if existing:
        if existing.trigger == 'calibration':
            # Calibration is the most complete snapshot; skip any subsequent triggers for this activity
            return existing
        elif trigger == 'calibration':
            # We have a fitness-only snapshot, but now we have calibration.
            # Insert the calibration record (the fitness-only record remains as history).
            pass 
        else:
            # Duplicate non-calibration trigger; skip
            return existing
    
    return repo.insert(athlete_id, activity_id, trigger, snapshot_data)
```

**Rationale:**
- TwinState is append-only (Principle #4). The repository exposes no `update()` method.
- The calibration trigger carries the complete physiological snapshot (thresholds + fitness scores inline).
- A subsequent `physiology_updated` trigger for the same activity adds no new information if a calibration record already exists.
- Skipping preserves the append-only invariant and the 1:1 `activity_id` → `TwinState` mapping for calibration triggers.

**Do not:** Read-then-update the record inserted by the first trigger. This violates the repository contract and creates a second write path that bypasses append-only guarantees.

**Event Ordering Guarantee:** The async pipeline should prioritize `physiology_updated` (calibration) events before `fitness_updated` events for the same activity to ensure the most complete snapshot is captured first.

## Events

### Produced

| Event | Trigger | Version | Payload |
|---|---|---|---|
| `twin_recalibrated` | new TwinState inserted | v1 | `{athlete_id, twin_state_id, activity_id, trigger, confidence_level, fitness, fatigue, form, readiness_level}` |
| `twin_confidence_upgraded` | confidence_level increased | v1 | `{athlete_id, from_level, to_level, twin_state_id}` |
| `twin_model_ready` | first TwinState created (onboarding complete) | v1 | `{athlete_id, twin_state_id, data_tier, confidence_level}` |

### Consumed

| Event | Action | Version |
|---|---|---|
| `fitness_updated` | Create new TwinState with latest scores + current thresholds | v1 |
| `physiology_updated` | Create new TwinState with latest thresholds + current scores | v1 |
| `recovery_modifier_changed` (AMBER or RED only) | Create new TwinState with updated readiness context | v1 |

### Trigger Semantics

| Trigger | AthletePhysiology changed? | AthleteFitness changed? | What TwinState inlines |
|---|---|---|---|
| `questionnaire` | Yes — bootstrapped from population norms | Yes — initialised to zero fitness/fatigue | Initial thresholds + zero fitness/fatigue/form |
| `activity_sync` | No — no threshold signal in this session | Yes — fitness/fatigue updated from load scores | Updated fitness/fatigue/form, unchanged thresholds |
| `calibration` | Yes — threshold detection fired | Yes — fitness/fatigue also updated | Updated thresholds + updated fitness/fatigue/form |
| `physiology_input` | Yes — lab or field test entered | No — fitness/fatigue unchanged | Updated thresholds, unchanged fitness/fatigue/form |
| `wellness_update` | No | No — only readiness context changes | Unchanged fitness/fatigue/thresholds, updated readiness |

## Reprocessing Semantics

When the computation pipeline changes (e.g., `model_version` increments):

1.  **Historical TwinState records are NOT updated.** They remain as originally computed with their original `model_version`.
2.  **Reprocessing creates new TwinState records** alongside old ones, with:
    -   New `model_version` string
    -   Recomputed inline values (fitness, thresholds, etc.)
    -   Same `trigger` type and approximately same `created_at` timestamp
3.  **The "latest" TwinState** for an athlete is always the one with the highest `created_at` (or highest `model_version` if timestamps collide).

This preserves the audit trail: you can always see what the system believed at time T with model version V.

## Context Assembly

Context assembly is performed by `TwinContextAssemblerService`, which translates raw `TwinState` values into coaching-ready language and targets.

**Output:** `TwinContextSummary` (includes `form_descriptor`, `readiness_level`, confidence-calibrated targets, and intent ranges).

**Location:** Full assembly algorithm and output contract defined in `02-computations/twin-context-assembler.md`.

## APIs

```yaml
GET /athletes/{athlete_id}/twin
Description: Returns the latest TwinState for the athlete.
Response: 200
  twin_state: TwinStateResponse  # includes inline fitness, thresholds, readiness values
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/twin/history
Description: Returns historical TwinState records.
Query:
  limit?: number (default 20, max 100)
Response: 200
  history: TwinStateResponse[]  # ordered by created_at desc; each contains inline snapshot
Auth: Bearer JWT, require_self
```

## Performance Constraints

-   Reads from single TwinState record; no joins needed.
-   `get_latest(athlete_id)` is the most frequent query in the system — indexed on `(athlete_id, created_at DESC)`.
-   History endpoint bounded by `limit` parameter (max 100).
-   p95 latency for `GET /twin`: < 50ms (served directly from PostgreSQL covering index; cache re-evaluated if latency degrades at scale).

## Index Strategy

```sql
-- Most common query: latest TwinState for an athlete
CREATE INDEX idx_twin_states_latest ON twin_states (athlete_id, created_at DESC);

-- Covering index for common read pattern (avoids table lookup)
CREATE INDEX idx_twin_states_latest_covering 
  ON twin_states (athlete_id, created_at DESC) 
  INCLUDE (fitness, fatigue, form, confidence_level, readiness_level, data_tier);

-- Unique index for deduplication (optional, if DB-level enforcement desired)
CREATE UNIQUE INDEX idx_twin_states_per_activity 
  ON twin_states (athlete_id, activity_id) 
  WHERE activity_id IS NOT NULL;
```

## Retention

Indefinite. TwinState records accumulate over time — this is by design. Each record is small (~500 bytes). At one record per calibration event (roughly 2–5 per week for active athletes), this is ~100–260 records per year, or ~100KB–260KB per year per athlete.

## Storage Model

| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `twin_states` table | append-only | strong | indefinite |

## Observability

Metrics:
-   `twin_state.created.total`: count of new TwinState records
-   `twin_state.confidence_upgrades.total`: count of transitions from low→medium or medium→high
-   `twin_state.per_athlete.daily_rate`: histogram of records per athlete per day

Logs:
-   `twin_state.inserted`: athlete_id, trigger, confidence_level, model_version
-   `twin_state.duplicate_skipped`: athlete_id, activity_id, existing_trigger, new_trigger (when `insert_if_not_exists` skips)

Alerts:
-   **High Insertion Rate:** Alert if `per_athlete.daily_rate` > 5 for any single athlete (indicates recalibration loop).
-   **Stagnant Confidence:** Alert if an athlete has > 20 TwinState records with no `confidence_upgraded` event (indicates calibration failure).

## Cross-References

-   **Confidence Model:** `00-foundations/confidence-model.md` (per-metric confidence semantics)
-   **Wellness Modifier:** `02-computations/wellness-modifier.md` (readiness computation)
-   **Context Assembly:** `02-computations/twin-context-assembler.md` (translation to coaching language)
-   **Event Catalogue:** `00-foundations/event-catalogue.md` (event schemas)
-   **Principles:** `00-foundations/principles.md` (Invariant #4: Append-Only)