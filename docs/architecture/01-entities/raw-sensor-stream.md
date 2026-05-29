# RawSensorStream — Cleaned Time-Series Metadata Record

## Purpose
- DB metadata record for the cleaned sensor stream stored in object storage after Phase 5a
- The cleaned stream is the input for segmentation; the metadata record enables efficient lookup
- Separate key from the raw FIT file — both are retained

## TypeScript Schema

```typescript
type AvailableChannels = {
  hr: boolean
  rr_intervals: boolean
  power: boolean
  pace: boolean
  cadence: boolean
  elevation: boolean
}

type RawSensorStream = {
  id: string                       // UUID, PK
  activity_id: string              // UUID, FK → Activity (one-to-one)
  fit_file_key: string             // object storage key for CLEANED stream (not raw FIT)
  sampling_rate_hz: number         // after resampling; typically 1 Hz
  available_channels: AvailableChannels
  cleaning_pipeline_version: string
  created_at: string
}
```

## Object Storage Key Pattern
- Raw FIT: `fit-files/{athlete_id}/{activity_date}/{uuid}.fit`
- Cleaned stream: `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`

Both keys are retained indefinitely. The raw FIT is the reprocessing anchor; the cleaned stream is the segmentation input.

## Invariants
- One `RawSensorStream` per `Activity`. Created atomically with the cleaned stream upload.
- If cleaning fails (stream too short, all HR artifacts), no `RawSensorStream` is created. The Activity exists with null `cleaning_pipeline_version`. Segmentation is skipped for this activity.
- The `fit_file_key` on `RawSensorStream` is the cleaned stream key — different from `Activity.fit_file_key` (raw FIT). The naming is intentional: both entities use the same field name pointing to different keys.
- `available_channels` reflects what survived artifact removal — an activity that had HR but all values were flagged as artifacts will have `hr: false`.

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `raw_sensor_streams` table | append-only | strong | indefinite |
| Cleaned stream (object storage) | immutable | eventual | indefinite |

## Runtime Ownership
Owns:
- Reference to cleaned stream in object storage
- Channel availability after cleaning

Does Not Own:
- Cleaning algorithm → `02-computations/signal-cleaning.md`
- Segmentation that reads this stream → `01-entities/physiological-segment.md`
