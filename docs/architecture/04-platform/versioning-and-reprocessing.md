# Versioning and Reprocessing

## Purpose
- Defines how analytical records are versioned so algorithms can improve without breaking history
- Establishes the reprocessing protocol for upgrading historical records

## Version Fields

Every analytical record carries version strings identifying the exact pipeline that produced it:

```typescript
type VersionedRecord = {
  ingestion_pipeline_version: string | null   // on Activity
  cleaning_pipeline_version: string | null    // on Activity; set after Phase 5a
  segmentation_version: string | null         // on PhysiologicalSegment
  analysis_version: string | null             // on ExecutionObservation, AdaptationObservation
  model_version: string | null                // on TwinState
  prediction_method_version: string | null    // on RacePrediction
}
```

## Version String Format

`v{major}` or `v{major}.{minor}` or `v{major}-{descriptor}`

Examples:
- `v1` — initial version
- `v2-threshold-referenced` — formula updated to use real threshold data
- `v2-per-athlete-gap` — per-athlete GAP curve introduced
- `heuristic-v1` — segmentation generation 1
- `hmm-v1` — segmentation generation 3

A version string is a frozen, reproducible pipeline snapshot. It is not a mutable label.

## The Reprocessing Test

Before persisting any computed field, apply this test:

> **"Can this field be recomputed from the stored FIT file?"**

If **yes** and no performance justification exists → do NOT persist it.
If **yes** and it is queried frequently across history windows → persist it with a version field.
If **no** (derived from inputs not in the FIT file, e.g. wellness signals) → persist it.

Fields that pass the performance justification test: `aerobic_load`, `neuromuscular_load`, `structural_load` (queried by TwinRecalibrationService across rolling 90-day windows).

## Supersession Protocol

When a pipeline version improves and historical records need updating:

```typescript
// Never overwrite old records
// Insert new records alongside old; mark old records with superseded_at

async function reprocessActivity(
  activity_id: string,
  new_pipeline_version: string
): Promise<void> {
  // 1. Fetch raw FIT from object storage via fit_file_key
  const fit_bytes = await ObjectStorageClient.download(activity.fit_file_key)

  // 2. Run new pipeline version
  const new_results = await new_pipeline.process(fit_bytes)

  // 3. Insert new records
  await PhysiologicalSegmentRepository.insert_many(new_results.segments)

  // 4. Mark old records superseded (not deleted)
  await PhysiologicalSegmentRepository.supersede_all(
    activity_id,
    old_version,
    superseded_at = now()
  )
}
```

## Reprocessing Is Offline

Pipeline upgrades and historical reprocessing run as offline batch jobs:
- Live system continues operating against existing records
- Reprocessing runs in background using a separate worker queue
- Once validated, new records become the primary version (old records superseded)
- No cutover required; consuming systems read by version string

## Exception: Load Score Updates

Load scores on `Activity` are an exception to the "insert new, supersede old" rule. Load scores are a computed field that passes the performance test, but they are not analytical outputs in the same sense as `PhysiologicalSegment` records. When the load formula improves (e.g. Gen 2 per-athlete GAP), load scores are updated in place on `Activity`. The `ingestion_pipeline_version` records which formula produced the current values.

Rationale: load scores are frequently aggregated (rolling sums for twin recalibration). Two sets of load scores per activity (old and new) would complicate every query. The version string is the audit trail.

## Version Registry

All active pipeline version strings are maintained in `app/core/pipeline_versions.py`:

```python
CURRENT_VERSIONS = {
    "ingestion": "v2-threshold-referenced",
    "cleaning": "v1",
    "segmentation": "hmm-v1",
    "analysis": "segment-v1",
    "model": "v1",
}
```

When a new version is released, the constant is updated here and all subsequent records use the new version. Historical records retain their original version string.

## Cross-References
- fit_file_key as reprocessing anchor: `00-foundations/principles.md`
- Version fields per entity: `01-entities/activity.md`, `01-entities/physiological-segment.md`, `01-entities/twin-state.md`
- Ingestion pipeline task: `04-platform/async-pipeline.md`
