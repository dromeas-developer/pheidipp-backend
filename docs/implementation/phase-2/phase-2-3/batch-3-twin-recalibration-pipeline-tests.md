> **Baseline — test companion for** `batch-3-twin-recalibration-pipeline.md`, migrated from `docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md` **on** 2026-07-19.

## Test Scenarios

Derived from the test manifest (`tests/test-manifest/phase-2-3p3.yaml`) and actual test files.

### Unit — Pure Helpers (Confidence Derivation)
**File:** `tests/unit/test_twin_recalibration_service_calibration_pure_helpers.py`
- Given `_confidence_rank()`, LOW=0, MEDIUM=1, HIGH=2
- Given `_max_confidence_level()` returns the higher of two levels
- Given `_max_confidence_level_string()` per-metric ratchet: None previous + non-null computed → computed wins; higher computed → computed wins; lower computed → previous preserved
- Given `_state_prior_weight()`, extracts prior_weight from PhysiologyParameterState dict; returns None for None/missing
- Given `_min_prior_weight()`, returns smaller value; treats None as zero
- Given `_prior_weight_to_level()`: 3.99 → LOW, 4.0 → MEDIUM, 8.0 → HIGH, None → LOW
- Given `_derive_confidence_level()`: both below 4.0 → LOW; one above 4.0, one below → LOW (weakest link); both above 4.0 but below 8.0 → MEDIUM; both above 8.0 → HIGH
- Given `_extract_param_value()`, returns value field from PhysiologyParameterState sub-state; returns None when container/sub-state/value is None or missing

### Unit — insert_if_not_exists Deduplication
**File:** `tests/unit/test_twin_recalibration_service_insert_if_not_exists.py`
- Given prior calibration + new calibration → skip insert, return existing
- Given prior calibration + new activity_sync → skip insert
- Given prior activity_sync + new calibration → insert new (prior remains as history)
- Given prior wellness_update + new calibration → insert new
- Given duplicate activity_sync (both non-calibration) → skip insert
- Given no existing TwinState → insert regardless of trigger
- Given calibration check runs first via `get_by_activity_and_trigger`, then falls back to `get_by_activity`

### Unit — recalibrate_for_calibration Orchestration
**File:** `tests/unit/test_twin_recalibration_service_calibration.py`
- Given missing training goal → raises `MissingTrainingGoalError`
- Given missing athlete fitness → raises `MissingAthleteFitnessError`
- Given no previous TwinState (first snapshot): uses computed confidence, data_tier defaults to TIER_3, trigger is CALIBRATION, model_version is "v2-threshold-detection"
- Given previous MEDIUM + computed LOW → stored MEDIUM (ratchet preserves)
- Given previous LOW + computed HIGH → stored HIGH (upgraded)
- Given per-metric ratchet: previous medium + computed low → stored medium; None previous + computed medium → stored medium (None = no data)
- Given threshold snapshot populated from updated AthletePhysiology row
- Given fitness/fatigue/form read from current AthleteFitness.aggregate JSONB
- Given non-threshold fields (lt1_power_watts, readiness_level, data_tier) inherited from previous TwinState
- Given prior activity_sync, calibration insert not blocked
- Given prior calibration, existing record returned unchanged (no insert, no events)

### Unit — Event Firing
**File:** `tests/unit/test_twin_recalibration_service_event_firing.py`
- Given new calibration TwinState, `twin_recalibrated` fires with correct payload (athlete_id, twin_state_id, previous_twin_state_id, trigger="calibration", confidence_level, fitness_score, fatigue_score)
- Given LOW→MEDIUM upgrade, `twin_confidence_upgraded` fires with correct from_level/to_level
- Given MEDIUM→HIGH upgrade, fires
- Given equal levels (no upgrade), does NOT fire
- Given downgrade attempt, does NOT fire (ratchet preserves)
- Given first snapshot (no previous), does NOT fire
- Given `twin_recalibrated` fires BEFORE `twin_confidence_upgraded` (ordering)
- Given dedup short circuit (existing calibration returned), no events published
- Given upgrade, `confidence_upgraded` flag is True on result

### Integration — Worker Task
**File:** `tests/integration/test_threshold_detection_task_integration.py`
- Given full pipeline (detect → apply_observations → recalibrate_for_calibration → commit), commits atomically
- Given empty observations from threshold detection, returns early (no physiology update, no twin recalibration)
- Given no shifted parameters from physiology update, returns early (no twin recalibration)
- Given missing activity, raises error before any service call

### Integration — signal_clean Defer Wiring
**File:** `tests/integration/test_signal_clean_threshold_detection_defer_integration.py`
- Given successful signal_clean that creates RawSensorStream, `threshold_detection` deferred with activity_id
- Given signal_clean that does NOT create (manual entry, already cleaned), `threshold_detection` NOT deferred
- Given defer failure (queue backend outage), failure swallowed after logging — RawSensorStream still committed
- Given defer fires AFTER commit, not inside transaction (ADR-009 decoupling)

### Behaviour — Full User Journey
**File:** `tests/behaviour/test_twin_recalibration_calibration_user_journey.py`
- Given full pipeline against real DB, calibration TwinState appended with `trigger=CALIBRATION`, `model_version="v2-threshold-detection"`, `metric_confidence` includes `lt2_hr`
- Given calibration-eligible session with ≥3 intensity steps, `AthletePhysiology.lt2.hr.prior_weight` grows from prior value (exit gate condition 1)
- Given posterior mean shifts from population default toward observed values (exit gate condition 3)
- Given 4+ HR deflection-eligible sessions, `metric_confidence.lt2_hr` transitions to "medium" when prior_weight >= 4.0 (exit gate condition 2)
- Given consecutive recalibrations, confidence_level never decreases (monotonicity invariant)
- Given calibration TwinState, `twin_recalibrated` and `twin_confidence_upgraded` events land in transactional outbox in same transaction
