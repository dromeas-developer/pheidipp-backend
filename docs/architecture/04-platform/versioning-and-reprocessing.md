# Versioning and Reprocessing

- Defines how analytical records are versioned so algorithms can improve without breaking history
- Establishes the reprocessing protocol for upgrading historical records

---

## Version Fields

Every analytical record carries version strings identifying the exact pipeline that produced it:

```typescript
type VersionedRecord = {
  ingestion_pipeline_version: string | null   // on Activity
  cleaning_pipeline_version: string | null    // on Activity; set after signal cleaning runs
  segmentation_version: string | null         // on PhysiologicalSegment
  analysis_version: string | null             // on ExecutionObservation, AdaptationObservation
  model_version: string | null                // on TwinState
  prediction_method_version: string | null    // on RacePrediction
}
```

---

## Version String Format

`v{major}` or `v{major}.{minor}` or `v{major}-{descriptor}`

Examples:
- `v1` — initial version
- `v2-threshold-referenced` — formula updated to use real threshold data
- `v2-per-athlete-gap` — per-athlete GAP curve introduced
- `heuristic-v1` — segmentation generation 1
- `hmm-v1` — segmentation generation 3

A version string is a frozen, reproducible pipeline snapshot. It is not a mutable label.

---

## The Reprocessing Test

Before persisting any computed field, apply this test:

> **"Can this field be recomputed from the stored FIT file?"**

If **yes** and no performance justification exists → do NOT persist it.
If **yes** and it is queried frequently across history windows → persist it with a version field.
If **no** (derived from inputs not in the FIT file, e.g. wellness signals) → persist it.

Fields that pass the performance justification test: `aerobic_load`, `neuromuscular_load`, `structural_load` (queried by TwinRecalibrationService across rolling 90-day windows).

---

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

---

## Reprocessing Is Offline

Pipeline upgrades and historical reprocessing run as offline batch jobs:
- Live system continues operating against existing records
- Reprocessing runs in background using a separate worker queue
- Once validated, new records become the primary version (old records superseded)
- No cutover required; consuming systems read by version string

---

## Alternative Pattern: In-Place Updates with Version Tracking

Most analytical records follow the supersession pattern (insert new, mark old as superseded). Load scores on `Activity` use an **alternative pattern**: in-place updates with version tracking via `ingestion_pipeline_version`.

**When to Use Each Pattern:**

| Pattern | Use When | Example |
|---------|----------|---------|
| **Supersession** (insert new, supersede old) | Historical fidelity matters; consumers need to query "what did we believe at time T?" | `PhysiologicalSegment`, `ExecutionObservation`, `TwinState` |
| **In-place update** (update current, track version) | Current state only matters; historical values are reconstructible from source data | `Activity` load scores, `AthletePhysiology` posterior estimates |

### Load Scores: Design Rationale

Load scores (`aerobic_load`, `neuromuscular_load`, `structural_load`) are updated in place on `Activity` when the formula improves. The `ingestion_pipeline_version` field records which formula produced the current values.

**Why In-Place Updates for Load Scores?**

1.  **Query Simplicity**: Consumers (e.g., `TwinRecalibrationService`) query rolling 90-day windows. In-place updates avoid the need for `WHERE superseded_at IS NULL` filters or joins to a history table on every query.
2.  **Reconstructibility**: Load scores pass the reprocessing test — they can be recomputed from the FIT file (`fit_file_key`). The version string is the audit trail; the raw data is the source of truth.
3.  **Audit Trail Integrity**: Coaching decisions are audited through `TwinState` (append-only), not through load scores. Load scores are intermediate derived values, not final analytical outputs.
4.  **Change Frequency**: Load formula improvements are rare (once or twice per year). The marginal auditability gain of database-stored history doesn't justify permanent query complexity.

**Re-Evaluation Triggers:**

This pattern should be reconsidered if:
- Load formula changes become frequent (quarterly+)
- Regulatory/compliance requirements mandate database-stored historical values
- Query patterns evolve to require historical load score comparison (e.g., "show me how load estimates changed over time")

**Compatibility with Append-Only Principles:**

This pattern is compatible with Invariant #10 ("Old analytical records are never deleted") because:
- `TwinState` (the authoritative audit trail for coaching decisions) remains append-only
- Load scores are intermediate computations, not final analytical records
- The `ingestion_pipeline_version` field preserves provenance and enables reconstruction

**Migration Behavior:**

Existing `Activity` records have `ingestion_pipeline_version` set to the version that produced their current load scores. No backfill is required when formula versions change — new computations simply use the new version string.

---

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

---

## Automatic Reprocessing on Algorithm Improvement

When a pipeline version improves, recent history is reprocessed rather than waiting for new data to arrive gradually.

### Reprocessing Window

- **Default window:** Recent calibration-eligible sessions (typically 90 days)
- **Rationale:** Covers approximately one full training cycle, providing sufficient data for the Bayesian posterior to benefit from improved observations without reprocessing the entire athlete history

### What Gets Updated

| Entity | Action | Rationale |
|--------|--------|-----------|
| `AthletePhysiology` | Posterior updated in place | Current state reflects best available algorithm |
| `PhysiologyMeasurement` | New records appended alongside old | Append-only history; old records retained |
| `AthleteFitness` | Scores updated in place | Current state reflects improved threshold estimates |
| `TwinState` | New record appended if posterior shifts materially | Append-only audit trail |
| `ExecutionObservation` | New records created; old superseded | Version string tracks which algorithm produced each |
| `PhysiologicalSegment` | New records created; old superseded | Version string tracks which algorithm produced each |
| `ConfidenceLevel` | May decrease if new algorithm reveals weaker evidence | Confidence represents certainty, not progress |

### What Never Changes

| Entity | Reason |
|--------|--------|
| Old `TwinState` records | Audit trail — what the twin knew at that point in time |
| Old coaching messages | Historical decisions are not retroactively modified |
| `Activity` load scores | Updated in place (exception to supersession rule) |

### Trigger Conditions

Automatic reprocessing fires when:

1. A new pipeline version is registered in `CURRENT_VERSIONS`
2. The version change is classified as a **calibration improvement** (not a minor fix)
3. The athlete has calibration-eligible sessions within the reprocessing window

### Communication Protocol

When reprocessing causes a material change in threshold estimates or confidence, the coach communicates:

> "We've improved how we detect your lactate threshold. Your actual threshold is slightly [higher/lower] than we estimated, which means [more precise targets / adjusted training zones]. This isn't a change in your fitness — it's a better reading of where you are."

If confidence decreases due to improved detection methods:

> "We've improved our detection methods, and your threshold estimate is less certain than we previously thought. Your targets will be wider ranges for now — this is honest uncertainty, not a step backward."

This builds trust through transparency rather than hiding the algorithm improvement.

### Why Old Coaching Decisions Remain Valid

Coaching recommendations are always made using the best understanding available at the time. Improved models may produce more accurate future guidance, but they do not imply previous recommendations were incorrect. An athlete who followed their coach's guidance with a less precise model trained correctly — they simply had wider targets. The improved model narrows those targets going forward.

This is analogous to how a human coach operates. A coach who learns something new about their athlete doesn't regret their previous advice — they apply the new knowledge to future decisions. The twin does the same.

---

## Cross-References

- fit_file_key as reprocessing anchor: `00-foundations/principles.md`
- Version fields per entity: `01-entities/activity.md`, `01-entities/physiological-segment.md`, `01-entities/twin-state.md`
- Ingestion pipeline task: `04-platform/async-pipeline.md`
