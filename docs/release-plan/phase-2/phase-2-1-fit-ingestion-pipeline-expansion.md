# Phase 2 — FIT Ingestion Pipeline Expansion & Calibration Eligibility
## Sub-Phase ID: Phase-2.1

## Objective
Expand the FIT ingestion pipeline to process full sensor signals (power, GPS, RR intervals) and evaluate calibration eligibility per the five-rule gate (including sport-type filtering). This is the first phase toward enabling threshold detection and comparable sessions. Activities now properly populate the calibration pipeline, creating the foundation for real twin model updates from training data.

## Challenge Notes
This sub-phase must carefully preserve Phase 1.6 invariants while adding new capabilities. The key design decision is whether to implement auto-sync (intervals.icu, Garmin) or stick with manual upload. The architecture shows `AthleteIntegration` entity exists but Phase 1 deferred it. 

**Decision: Manual upload only for Phase 2.1** to keep scope focused. Auto-sync will come later. The main value here is processing power/GPS/RR data that was ignored in Phase 1, and properly evaluating the `calibration_eligible` flag rather than defaulting to false.

**Critical Finding Resolution:** The architecture previously had a gap where Principle #8 ("Non-running activities excluded from twin calibration") was not enforceable. This phase implements the `sport_type` field on `Activity` and the sport-type detection mechanism, closing that gap. Non-running activities are now identified at ingestion and excluded from the calibration pipeline.

**Simplifications deferred:**
- Signal cleaning (Phase 2.2) — raw FIT data used for calibration eligibility check but cleaned data deferred
- Comparable sessions (Phase 2.4) — algorithm exists but requires history; will be enabled after this phase
- Threshold detection (Phase 2.3) — algorithms exist but calibration eligibility comes first

## Capabilities Delivered
- `POST /athletes/{id}/activities/upload` accepts FIT files with power, GPS, RR interval data
- `FitParserService` extracts all sensor streams (HR, power, GPS, RR intervals, lap data) AND sport type from FIT sport field
- `SportTypeDetectionService` maps FIT sport values and Intervals.icu types to internal `sport_type` enum
- `CalibrationEligibilityService` evaluates the six-rule gate (sport-type + five-rule gate) and sets `calibration_eligible = true` where appropriate
- `LoadComputationService` computes power-based aerobic load for Tier 1-2 athletes
- `Activity` records properly populated with `has_power`, `has_rr_intervals`, `has_gps` flags AND `sport_type`
- `calibration_eligible` flag calculated per architecture rules (including sport-type exclusion)
- Power load metrics (`supra_threshold_joules`, `w_prime_depletion_pct` fields in coaching observations) computed where power available

## Architectural Contracts Required
- `01-entities/activity.md` — sport_type field, signal availability flags
- `01-entities/athlete-physiology.md`
- `00-foundations/data-tiers.md` — tier definitions and calibration eligibility
- `00-foundations/terminology.md`
- `02-computations/load-computation.md` — calibration eligibility gate (sport-type + five-rule)
- `02-computations/sport-type-detection.md` — NEW: sport type detection mechanism
- `02-computations/signal-cleaning.md` (for understanding input to cleaning)
- `04-platform/object-storage-client.md`

## Vision References Required
- `twin/load-fatigue.md` — three load dimensions, data tier capabilities
- `twin/confidence-and-uncertainty.md` — calibration eligibility feeds evidence accumulation
- `twin/training-zones.md` — signal-aware target selection context
- `twin/data-philosophy.md` — "Non-Running Data Does Not Corrupt the Running Model"

## Upstream Dependencies
- Phase-1.6 (Simple FIT Import) — Basic FIT parsing and Activity schema exist
- Phase-1.2c (Twin State) — `TwinState` schema exists for fitness/fatigue updates

## Downstream Enablement
- Phase-2.2 — `calibration_eligible = true` activities become input to SignalCleaningService
- Phase-2.3 — Calibration-eligible activities trigger threshold detection algorithms
- Phase-2.6 — Power profile computation requires `calibration_eligible = true` AND `has_power = true`

## Invariants To Preserve
- `fit_file_key` is REQUIRED for non-manual-entry sources. Object storage upload must complete before Activity record creation.
- No averaged fields (`avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data`) are stored on Activity.
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.
- `(athlete_id, external_id, source)` uniqueness constraint enforced for deduplication.
- `ActivityPowerProfile` is created only when `calibration_eligible = true` AND `has_power = true` (Phase 2.6 will implement this).
- **Sport-type invariant**: Non-running activities (sport_type != 'running') are NEVER calibration-eligible, regardless of signal quality (Principle #8).

## Exit Gate
- Uploading a running FIT file with power data creates an `Activity` with `sport_type = 'running'`, `has_power = true`, proper load scores, and `calibration_eligible = true` when it meets the six-rule gate.
- Uploading a cycling FIT file creates an `Activity` with `sport_type = 'cycling'` and `calibration_eligible = false` regardless of signal quality.
- Uploading a swimming FIT file creates an `Activity` with `sport_type = 'swimming'` and `calibration_eligible = false`.
- Uploading a FIT file without power but with RR intervals creates `Activity` with `has_rr_intervals = true` and `calibration_eligible = true` only if running AND eligible.
- Uploading a FIT file with optical HR only creates `Activity` with `has_rr_intervals = false` and `calibration_eligible = true` only if running AND HR deflection-eligible (≥3 intensity steps).
- Simulating a FIT file with undetectable sport creates `Activity` with `sport_type = 'unknown'` and `calibration_eligible = false`.
- `GET /athletes/{id}/activities/{aid}` shows all signal availability flags AND `sport_type` correctly populated.