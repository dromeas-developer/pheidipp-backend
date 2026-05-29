# 2a — FIT Ingestion Pipeline
*intervals.icu integration, async FIT processing, object storage*

## Objective

Build the reliable async pipeline that brings real training data into the system.
The FIT file stored in object storage is the reprocessing anchor for the entire
analytical pipeline — getting this right is the single most important infrastructure
task in Phase 2. Every Activity must commit with a `fit_file_key` or not at all.

## Scope

`AthleteIntegration` model. intervals.icu token connection. Async FIT ingestion worker.
Object storage client. FIT file parsing (fitparse or garmin-fit-sdk). Activity creation
from FIT file. Manual FIT upload endpoint. Duplicate detection.

## Non-Goals

- Load score computation — deferred to 2b (FIT parsing produces raw signals; load
  is computed in 2b)
- Calibration eligibility — deferred to 2b
- Twin recalibration — deferred to 2b
- Signal cleaning pipeline (artifact removal, smoothing) — deferred to 5a
- RawSensorStream model — deferred to 5a

## Architecture References

- `Activity` model field spec and the `fit_file_key` hard prerequisite:
  `architecture/data-models.md` → Ingestion Layer
- `fit_file_key` as reprocessing anchor: `architecture/versioning.md`
- Async processing requirement: `architecture/principles.md` → Processing Is Async
- No global averages on Activity: `architecture/principles.md` → Core Principle

## Dependencies

Requires 1a (Activity, AthleteIntegration models), 1b (auth).

## Models Introduced

**`AthleteIntegration`** — platform credentials and sync state.
Fields: `athlete_id` FK, `platform` (enum: `intervals_icu`, `garmin_connect`),
`credentials` (encrypted JSON — token storage), `last_synced_at`, `sync_cursor`
(opaque string for incremental sync position), `created_at`, `updated_at`.
Unique constraint on `(athlete_id, platform)`.

## Services & Tasks Introduced

**`ObjectStorageClient`** (async) — abstraction over S3-compatible storage.
- `upload(key, data) → str` — returns the storage key on success; raises on failure.
- `download(key) → bytes`
- Keys follow the pattern: `fit-files/{athlete_id}/{activity_date}/{uuid}.fit`

**`IntervalsIcuClient`** (async) — intervals.icu API client.
- `list_activities(token, since_cursor) → list[ActivitySummary]`
- `download_fit(token, activity_id) → bytes`

**`FitParserService`** (sync) — extracts structured data from raw FIT file bytes.
- `parse(fit_bytes) → FitData` — returns a dataclass with:
  - `start_time`, `duration_seconds`, `activity_date`
  - `has_hr`, `has_rr_intervals`, `has_power` (booleans)
  - `distance_m`, `elevation_gain_m` (for structural load computation in 2b)
  - Raw record arrays preserved for load computation — not averaged

**`FitIngestionTask`** (async Celery/ARQ worker) — full pipeline per FIT file.
1. Download FIT file bytes from source (intervals.icu or upload)
2. Upload raw bytes to object storage via `ObjectStorageClient` — get `fit_file_key`
3. Parse via `FitParserService` — get `FitData`
4. Deduplication check: query Activity by `(athlete_id, external_id, source)`;
   return existing if found
5. Create Activity with `fit_file_key` set, load scores null, `calibration_eligible = false`
   (load computation follows in 2b as a second pass or continuation of this task)
6. If object storage upload fails at step 2: do not create Activity; retry the task.

**`IntervalsIcuSyncTask`** (async Celery/ARQ worker — scheduled + on-demand).
- Reads `AthleteIntegration` for all athletes with `platform = intervals_icu`
- For each: calls `IntervalsIcuClient.list_activities(since=sync_cursor)`
- For each new activity: enqueues `FitIngestionTask`
- Updates `sync_cursor` and `last_synced_at` on successful completion

## Endpoints Introduced

- `POST /athletes/{athlete_id}/integrations/intervals-icu` — store intervals.icu
  token. Triggers `IntervalsIcuSyncTask` immediately for first sync.
  Protected by `require_self`.
- `GET /athletes/{athlete_id}/integrations` — list connected integrations and
  sync status. Protected by `require_self`.
- `DELETE /athletes/{athlete_id}/integrations/intervals-icu` — disconnect; removes
  credentials but retains Activity records.
- `POST /athletes/{athlete_id}/activities/upload` — manual FIT file upload.
  Accepts multipart file. Enqueues `FitIngestionTask`. Returns 202 Accepted.
  Protected by `require_self`.
- `GET /athletes/{athlete_id}/integrations/intervals-icu/sync` — trigger on-demand
  sync. Returns 202 Accepted. Protected by `require_self`.

## Key Constraints

- Object storage upload happens BEFORE Activity record creation. If upload fails,
  no Activity is created and the task retries. This invariant is absolute.
- `fit_file_key` is always set for `source ≠ manual_entry`. The application enforces
  this — the DB constraint `NOT NULL WHERE source != 'manual_entry'` follows in 2b
  once the pipeline is stable.
- No averaged fields are written to Activity — no `avg_hr`, `avg_pace`, `avg_power`.
  The FIT parser must not expose these; the Activity model must not have these columns.
- Duplicate detection is based on `(athlete_id, external_id, source)`. The same
  FIT file uploaded twice creates one Activity.
- The ingestion task is idempotent — running it twice for the same file is safe.

## Done Criteria

- Connecting intervals.icu and triggering a sync creates Activity records for
  recent sessions. Each Activity has a non-null `fit_file_key`.
- Manually uploading a FIT file creates a single Activity with `fit_file_key` set.
- Uploading the same FIT file twice creates one Activity, not two.
- If the object storage upload is simulated to fail, no Activity record is created.
- `GET /athletes/{athlete_id}/activities` returns the synced activities with
  correct `activity_date` and `has_hr` / `has_power` booleans.
