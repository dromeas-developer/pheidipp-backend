# Phase 1 — Simple FIT Import & Post-Workout
## Sub-Phase ID: Phase-1.6

## Objective
Close the loop: athlete uploads a FIT file, system extracts HR data, computes load, updates fitness/fatigue, produces a new TwinState snapshot, and generates a post-workout coach message. This is the first time real training data flows through the system. The scope is intentionally "simple" — HR data only, no calibration, no threshold detection, no segmentation. The goal is to prove end-to-end data flow before expanding to the full ingestion pipeline in Phase 2.

## Challenge Notes
Early drafts used a manual entry system with a `PostWorkoutAgent` that produced analysis from typed notes. This sub-phase replaces manual entry with a simple FIT file upload and a much more meaningful analysis — the post-workout message now references actual HR data, duration, and load. The `Activity` model and its invariants were designed with FIT data in mind; we are now putting them to use for the first time.

The key simplifications are:
- HR data only (not power, not GPS, not RR intervals)
- Heuristic load computation (not threshold-referenced)
- No calibration — all activities are `calibration_eligible = false`
- No `RawSensorStream` (cleaned stream storage) — data is parsed on-the-fly
- No `ExecutionObservation` or rep-level analysis — post-workout is just compliance + effort narrative
- Object storage stores the raw FIT file but `RawSensorStream` entity is not created

## Capabilities Delivered
- `POST /athletes/{id}/activities/upload` — accept FIT file, return 202 Accepted with task_id
- `POST /athletes/{id}/activities/{aid}/analyse` — trigger `PostWorkoutAgent`
- `GET /athletes/{id}/activities` — activity list
- `GET /athletes/{id}/activities/{aid}` — single activity
- `GET /athletes/{id}/activities/{aid}/analysis` — analysis + coaching message
- `FitParserService` — extracts HR data, duration, start_time from FIT file
- `ObjectStorageClient` — stores raw FIT file in object storage (first runtime use of storage)
- `LoadComputationService` — computes `aerobic_load` from HR data (heuristic formula)
- `TwinRecalibrationService` — updates `AthleteFitness` via Banister model
- New `TwinState` with `trigger = activity_sync`
- `ComplianceService` — compares actual session to `PlannedSession`
- `PostWorkoutAgent` — generates three-paragraph post-workout message
- `GenerationEvent` logging for every LLM call

## Architectural Contracts Required
- `01-entities/activity.md`
- `01-entities/twin-state.md`
- `01-entities/athlete-fitness.md`
- `01-entities/athlete-physiology.md`
- `01-entities/coaching-message.md`
- `01-entities/generation-event.md`
- `01-entities/generated-workout.md`
- `01-entities/planned-session.md`
- `02-computations/load-computation.md`
- `02-computations/banister-update.md`
- `03-agents/post-workout-agent.md`
- `04-platform/object-storage-client.md`

## Vision References Required
- `coach/post-workout.md` — post-workout message content rules, three-paragraph structure
- `coach/daily-view.md` — execution analysis for athlete
- `twin/confidence-and-uncertainty.md` — how execution is described under uncertainty
- `twin/training-zones.md` — how thresholds define zones

## Upstream Dependencies
- Phase-1.1 (Auth) — authenticated user
- Phase-1.2a (Profile & Activity) — `Activity` schema exists
- Phase-1.2c (Twin & Fitness) — `TwinState`, `AthleteFitness`, `AthletePhysiology` schema exists
- Phase-1.4 (Plan Generation) — `PlannedSession` must exist for compliance comparison
- Phase-1.5 (Coaching Agents) — `PostWorkoutAgent` builds on agent infrastructure from .5a

## Downstream Enablement
- Phase-2 (FIT Ingestion Pipeline) — expands from manual upload to auto-sync (intervals.icu, Garmin)
- Phase-2b (Load Computation) — adds power, GPS, structural load; threshold-referenced formulas
- Phase-4 (Execution Observation) — adds rep-level analysis, `ExecutionObservation` entity

## Invariants To Preserve
- Object storage upload happens BEFORE `Activity` record creation. If upload fails, no `Activity` is created and the task retries.
- `fit_file_key` is always set for `source != manual_entry`.
- No averaged fields (`avg_hr`, `avg_pace`, etc.) are stored on `Activity`.
- `LoadComputationService` must receive raw records from `FitParserService`, not summary stats.
- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService`.
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden. For Phase 1.6, all sessions are NOT calibration-eligible.
- `TwinState` is append-only. `TwinRecalibrationService` never updates the existing record.
- `PostWorkoutAgent` is idempotent — calling the endpoint twice returns the same `CoachingMessage` without calling the LLM again.
- Every LLM call writes a `GenerationEvent`.
- `Activity` deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null.

## Simplifications (Deferrals to Phase 2+)
- **No calibration**: `calibration_eligible = false` for all sessions. Threshold detection requires multiple sessions with specific structure.
- **No signal cleaning**: Raw FIT HR data used directly. Cleaning pipeline (Phase 5) will refine this.
- **No RawSensorStream**: Cleaned stream not stored. Data is parsed on-the-fly and discarded.
- **No ExecutionObservation**: Rep-level analysis requires segmentation and `WorkoutStep` mapping. Phase 4.
- **No comparable sessions**: Need history for this. Phase 4.
- **No wellness/weather modifiers on load or targets**: Phase 3.

## Exit Gate
- Uploading a valid FIT file creates an `Activity` with `source = manual_upload`, non-null `fit_file_key`, and populated load scores.
- `GET /athletes/{id}/twin/history` shows a new `TwinState` after the upload, with updated `fitness` and `fatigue` scores.
- `POST /athletes/{id}/activities/{aid}/analyse` returns a three-paragraph post-workout coach message.
- Calling the analyse endpoint twice returns the same message — no second LLM call.
- Simulating an object storage failure during upload does not create an `Activity` record.

## Risks
- **FIT parser brittleness**: Different devices (Garmin, Coros, etc.) write slightly different FIT structures. The parser must handle the common subset robustly and fail gracefully on unsupported files.
- **Load computation accuracy**: Heuristic formulas are imprecise but sufficient for Phase 1. The athlete must not be told these are definitive.
- **Object storage first use**: This is the first runtime use of object storage. If bucket permissions or connectivity are misconfigured, the entire flow fails. Mitigation: test upload path independently of the full pipeline.

