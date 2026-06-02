# AthleteWellness — Passive Daily Wellness Record

## Purpose
- One record per athlete per calendar date, storing passive physiological wellness signals
- The raw input for baseline computation and recovery modifier classification
- Populated from wearable platforms; never from questionnaires

## TypeScript Schema

```typescript
type WellnessSource = 'garmin' | 'whoop' | 'oura' | 'polar' | 'manual'

type BodyCompositionSource = 'garmin_scale' | 'withings' | 'manual'

type AthleteWellness = {
  athlete_id: string            // UUID, FK → Athlete
  date: string                  // YYYY-MM-DD; unique per athlete
  total_sleep_minutes: number | null
  deep_sleep_minutes: number | null
  rem_sleep_minutes: number | null
  avg_sleeping_hr_bpm: number | null
  min_sleeping_hr_bpm: number | null   // overnight minimum; used as resting HR anchor
  hrv_overnight_avg_ms: number | null  // RMSSD average
  hrv_overnight_min_ms: number | null
  source: WellnessSource
  source_record_id: string | null  // deduplication key from source platform
  ingested_at: string              // ISO 8601
}

// Body composition metrics (separate ingestion path, separate source)
type BodyCompositionRecord = {
  athlete_id: string                   // UUID, FK → Athlete
  date: string                         // YYYY-MM-DD; unique per athlete
  weight_kg: number                    // required for body composition record
  body_fat_pct: number | null
  muscle_mass_kg: number | null
  bone_mass_kg: number | null
  source: BodyCompositionSource
  source_record_id: string | null        // deduplication key from source platform
  ingested_at: string                   // ISO 8601
}
```

## Field Semantics

**`min_sleeping_hr_bpm`** is the overnight minimum — the true physiological floor during deepest sleep. This is the resting HR anchor used for zone calculations throughout the system. NOT `avg_sleeping_hr_bpm`. The distinction matters because `avg_sleeping_hr_bpm` is influenced by sleep quality and position, while `min_sleeping_hr_bpm` is more stable.

**`hrv_overnight_avg_ms`** is the average across the full overnight period, not a point measurement. This is more stable than a dedicated morning measurement, which athletes perform inconsistently and eventually abandon.

**`avg_sleeping_hr_bpm`** is the primary trend signal for recovery state. Rising trend over consecutive nights → early warning for overreaching or illness onset, often 3-4 days before the athlete consciously feels fatigued.

## Invariants
- Unique constraint on `(athlete_id, date)`. One record per day per athlete. **Upsert semantics:** a second ingestion for the same `(athlete_id, date)` updates non-null fields but does not overwrite existing non-null values with null. Different wearables may contribute different fields on the same day — the record is additive.
- No field is required to be non-null. Partial records (only some signals present) are valid and normal.
- Source `manual` records are accepted but weighted lower in modifier computation than wearable-derived records.
- Records are never deleted once created.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `wellness_record_ingested` | Record upserted | v1 | `{date, source, signals_present[]}` |

### Consumed
None. `AthleteWellness` records are read by `WellnessBaselineService` on a schedule.

## APIs

```yaml
POST /athletes/{athlete_id}/wellness
Request:
  date: string, required
  total_sleep_minutes?: number
  deep_sleep_minutes?: number
  rem_sleep_minutes?: number
  avg_sleeping_hr_bpm?: number
  min_sleeping_hr_bpm?: number
  hrv_overnight_avg_ms?: number
  hrv_overnight_min_ms?: number
Response: 201 | 200  # 200 if upsert
  wellness: AthleteWellnessResponse
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/wellness
Query:
  from?: date
  to?: date
  limit?: number (default 30)
Response: 200
  records: AthleteWellnessResponse[]
Auth: Bearer JWT, require_self

GET /athletes/{athlete_id}/wellness/{date}
Response: 200 | 404
  wellness: AthleteWellnessResponse
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_wellness` table | upsert (additive merge on conflict) | strong | indefinite |

Index: `(athlete_id, date DESC)` for rolling window queries.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes | POST (upsert) | No |
| Service | Yes | upsert() | No |
| Repository | Yes | upsert() with additive merge | No |

## Runtime Ownership
Owns:
- Raw daily wellness signals
- Upsert/merge semantics for multi-source records

Does Not Own:
- Baseline computation from wellness records → `01-entities/athlete-wellness-baseline.md`
- Recovery modifier classification → `02-computations/wellness-modifier.md`
- Cycle phase modifier → `01-entities/cycle-phase-log.md`

## Failure Semantics
- Upsert of a record with all-null fields → accepted; existing record unchanged
- Platform sync failure → no record created; retry on next sync cycle; no error surfaced to athlete

## Performance Constraints
- `POST /wellness` (upsert): p95 < 100ms
- `GET /wellness` (30-day window): p95 < 100ms

## Observability
Metrics:
- `athlete_wellness.coverage_rate`: percentage of athletes with ≥14 records in the past 28 days
- `athlete_wellness.signal_completeness`: by signal field (monitors what wearables are providing)
Logs:
- `athlete_wellness.ingested`: athlete_id, date, source, signals_present_count

## Implementation Notes
- The additive merge upsert: `INSERT ... ON CONFLICT (athlete_id, date) DO UPDATE SET col = COALESCE(EXCLUDED.col, col)` — this preserves existing non-null values when the new row has null for that field
- intervals.icu serves as the aggregator for Garmin, Whoop, Oura, and Polar data. Direct platform connections are future work.
- No single-night values are used for any coaching decision. The raw data lands here; interpretation is entirely in `WellnessBaselineService` and `WellnessModifierService`.
