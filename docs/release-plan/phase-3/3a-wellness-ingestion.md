# 3a — Wellness Ingestion
*AthleteWellness model, passive wearable data, ingestion pipeline*

## Objective

Begin capturing passive wellness signals from the athlete's wearable platform.
The data lands in the database ready for baseline computation and modifier
classification in 3b. No coaching changes yet — this sub-phase is pure ingestion.

## Scope

`AthleteWellness` model. Wellness ingestion from intervals.icu (which aggregates
Garmin, Whoop, Oura, Polar data). Async wellness sync task. Manual wellness entry
endpoint as fallback.

## Non-Goals

- Baseline computation — deferred to 3b
- Recovery modifier classification — deferred to 3b
- Any change to workout targets or coaching messages — deferred to 3b
- Direct wearable platform connections (Garmin/Whoop/Oura native APIs) — intervals.icu
  aggregation is sufficient for launch

## Architecture References

- `AthleteWellness` full field spec:
  `architecture/wellness-and-modifiers.md` → AthleteWellness
- Resting HR definition (overnight minimum): 
  `architecture/wellness-and-modifiers.md` → AthleteWellness
- Overnight HRV preferred over morning measurement:
  `vision/twin/external-modifiers.md` → HRV

## Dependencies

Requires 2a (`AthleteIntegration` model and `IntervalsIcuClient` exist).

## Models Introduced

**`AthleteWellness`** — one record per athlete per calendar date.
Full field spec from `architecture/wellness-and-modifiers.md`:
`athlete_id` FK, `date`, `total_sleep_minutes`, `deep_sleep_minutes`,
`rem_sleep_minutes`, `avg_sleeping_hr_bpm`, `min_sleeping_hr_bpm`,
`hrv_overnight_avg_ms`, `hrv_overnight_min_ms`,
`source` (enum: `garmin`, `whoop`, `oura`, `polar`, `manual`),
`source_record_id` (nullable), `ingested_at`.
Unique constraint on `(athlete_id, date)` — one record per day, upsert on conflict.

## Services & Tasks Introduced

**`WellnessIngestionService`** (sync) — creates or updates `AthleteWellness` records.
- `upsert(athlete_id, date, data, source) → AthleteWellness`
  Upserts on `(athlete_id, date)` — partial updates allowed (null fields
  from the platform are ignored, not overwritten).

**`IntervalsIcuWellnessSyncTask`** (async worker — scheduled daily + on-demand).
- Fetches wellness data from intervals.icu for each connected athlete.
- Calls `WellnessIngestionService.upsert()` for each returned day.
- Updates `last_synced_at` on `AthleteIntegration` for wellness cursor.

## Endpoints Introduced

- `POST /athletes/{athlete_id}/wellness` — manual wellness entry. Accepts any
  subset of fields. Protected by `require_self`.
- `GET /athletes/{athlete_id}/wellness` — paginated wellness history, ordered
  by date desc. Accepts `?from=&to=` date filters. Protected by `require_self`.
- `GET /athletes/{athlete_id}/wellness/{date}` — single day record.
  Protected by `require_self`.

## Key Constraints

- Upsert semantics: a second ingestion for the same `(athlete_id, date)` updates
  non-null fields but does not overwrite existing non-null values with null.
  Platform data is additive — different wearables may contribute different fields.
- `min_sleeping_hr_bpm` is the overnight minimum — this is the resting HR anchor
  used for zone calculations, not `avg_sleeping_hr_bpm`. The ingestion service
  must map correctly from the source platform's field names.
- No single-night values are used for any coaching decision in this sub-phase.
  The data is stored; interpretation begins in 3b.

## Done Criteria

- Triggering a wellness sync for a connected athlete creates `AthleteWellness`
  records for available dates.
- Upserting the same date twice updates non-null fields without error and without
  overwriting existing non-null values.
- `GET /athletes/{athlete_id}/wellness` returns records with at least
  `min_sleeping_hr_bpm` and `hrv_overnight_avg_ms` populated for Garmin-connected
  athletes.
- Manual wellness entry via `POST` creates a record with `source = manual`.
