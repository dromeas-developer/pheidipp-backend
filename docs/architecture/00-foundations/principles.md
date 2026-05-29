# Principles — Architectural Invariants & Core Decisions

## Purpose
- Defines the non-negotiable rules every engineer must internalise before touching any part of the system
- Establishes the five-layer separation of concerns that governs all data flow

## Invariants

1. **Activities are physiological observations, not workout summaries.** `Activity` stores what the twin model needs. It never stores avg_hr, avg_pace, avg_power, or lap dumps. The FIT file is the source of truth.

2. **The twin is deterministic Python. The LLM writes narrative.** All analytical computation — fitness scoring, threshold estimation, execution classification, load accumulation, wellness trend analysis — lives in Python services. LLM agents receive a pre-computed digest and write coaching text. They never derive findings.

3. **`fit_file_key` is a hard prerequisite.** No `Activity` record commits without its raw file stored in object storage. This is the reprocessing anchor. If object storage fails, the task retries. No exceptions.

4. **TwinState is append-only.** Every recalibration appends a new record. Old records are never updated or deleted. This is what makes coaching decisions auditable and reprocessing safe.

5. **Every analytical output is versioned.** `ingestion_pipeline_version`, `cleaning_pipeline_version`, `segmentation_version`, `analysis_version`, `model_version`. A version string is a frozen, reproducible pipeline snapshot — not a mutable label.

6. **No global session averages are persisted.** Average HR, pace, power — none of these are on `Activity`. Ever.

7. **All heavy processing is async.** FIT parsing, twin recalibration, post-workout analysis — all run in a worker queue (Celery or ARQ over Redis). API responses never wait for these.

8. **Non-running activities are excluded from twin calibration.** They appear in the training record. They never feed load computation, threshold detection, execution analysis, or adaptation modelling.

9. **Raw pace is never used.** Grade-adjusted pace (GAP) is the standard input throughout. See `02-computations/effort-normalisation.md`.

10. **Old analytical records are never deleted.** Superseded records receive `superseded_at`. New records are inserted alongside.

## Five-Layer Separation of Concerns

```
┌──────────────────────────────────────────────────────┐
│  5. TWIN INTERPRETATION                               │
│     TwinState recalibration · coaching signals        │
├──────────────────────────────────────────────────────┤
│  4. ADAPTATION OBSERVATION                            │
│     Block-level response · yield profiles             │
├──────────────────────────────────────────────────────┤
│  3. PHYSIOLOGICAL ANALYSIS                            │
│     ExecutionObservation · segmentation               │
├──────────────────────────────────────────────────────┤
│  2. WORKOUT EXECUTION STRUCTURE                       │
│     PlannedSegment · DeviceSegment · PhysSegment      │
├──────────────────────────────────────────────────────┤
│  1. RAW SENSOR INGESTION                              │
│     FIT file · stream cleaning · load computation     │
└──────────────────────────────────────────────────────┘
```

Lower layers feed upper layers. Upper layers never reach down to read raw data directly. Each layer can be upgraded independently as long as its output interface remains stable.

## Runtime Ownership

**Owns:**
- All invariants listed above as system-wide constraints
- The five-layer dependency direction

**Does Not Own:**
- Individual entity contracts → `01-entities/`
- Computation algorithms → `02-computations/`
- Agent architecture → `03-agents/`
- Platform concerns → `04-platform/`

## Implementation Notes
- The layer independence invariant is what makes segmentation algorithm upgrades (Gen 1 → Gen 3) safe — `PhysiologicalSegment` schema is stable; only `segmentation_version` changes
- The append-only TwinState invariant is what makes it possible to explain any historical coaching decision
- The LLM narration rule keeps context windows small (2k–6k tokens) and keeps analytical logic auditable in Python

## Open Questions
- None. These invariants are settled.
