> **Baseline — test companion for** `batch-1-threshold-detection.md`, migrated from `docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md` **on** 2026-07-19.

## Test Scenarios

Derived from the test manifest (`tests/test-manifest/phase-2-3p1.yaml`) and actual test files.

### Unit — PhysiologyParameter Enum
**File:** `tests/unit/test_physiology_parameter_enum.py` (10 tests)
- Given the `PhysiologyParameter` enum, all 10 values (LT1_HR through MAX_HR) are present
- Each value maps to its expected string representation
- The enum is registered in `app/models/__init__.py`

### Unit — PhysiologyMeasurement Model
**File:** `tests/unit/test_physiology_measurement_model.py` (25 tests)
- Given a `PhysiologyMeasurement` instance, all columns (id, athlete_id, activity_id, parameter, observed_value, source, measurement_date, algorithm_used, confidence_weight, raw_data_reference, notes, created_at) are populated correctly
- `activity_id` is nullable with ON DELETE SET NULL
- `parameter` and `source` stored as non-native String enums
- `algorithm_used` and `confidence_weight` are nullable
- Append-only — no update/delete methods exposed

### Unit — PhysiologyMeasurementRepository
**File:** `tests/unit/test_physiology_measurement_repository.py` (16 tests)
- Given `insert(measurement)`, the row is flushed without committing
- Given `get_by_athlete(athlete_id, limit)`, returns rows in measurement_date DESC order
- Given `get_by_athlete_and_parameter(athlete_id, parameter, limit)`, filters by parameter
- Given `get_recent_for_parameter(athlete_id, parameter, source, from_date, limit)`, filters by source and from_date
- No update/delete methods exist on the repository

### Unit — ThresholdDetectionService
**File:** `tests/unit/test_threshold_detection_service.py` (33 tests)

**Gates:**
- Given an activity with `calibration_eligible = false`, `detect()` returns an empty list
- Given an activity with `sport_type != RUNNING`, `detect()` returns an empty list
- Given a missing `RawSensorStream`, `detect()` returns an empty list

**HR Deflection (Algorithm 1):**
- Given a cleaned stream with ≥3 distinct intensity steps and R² ≥ 0.80, produces `LT1_HR` and `LT2_HR` observations with source `TRAINING_HR_DEFLECTION` and weight 1.0
- Given <3 intensity steps, returns no observations
- Given R² < 0.80, returns no observations
- Bins with >80% null HR values are skipped
- `confidence_weight` derived from R² value

**RR Inflection (Algorithm 2):**
- Given RR data and ≥8 min per intensity level, produces `LT1_HR` and `LT2_HR` observations with source `TRAINING_RR_INFLECTION` and weight 2.5
- Given <8 min per intensity level, returns no observations
- Given no RR data, returns no observations
- RMSSD drop > 15% below baseline defines LT1 inflection

**Power-to-HR Ratio (Algorithm 3):**
- Given a clear ratio breakpoint, produces `CP` observation with source `TRAINING_POWER_HR_RATIO` and weight 1.5
- Given no clear breakpoint, returns no observations
- Only runs when `has_power = true`

**Signal Selection:**
- Given `has_rr_intervals`, runs RR inflection
- Given `has_hr` and `has_power`, runs HR deflection + power-to-HR ratio
- Given `has_hr` only, runs HR deflection
- RR inflection takes priority over HR deflection when both available
- Power-to-HR ratio runs alongside HR-based detection when power available

**Natural Training Analysis:**
- Given ≥3 easy runs with consistent HR (±5 bpm), produces `LT1_HR` observation with weight 0.5
- Given <3 easy runs, returns no observations
- Given HR spread > 5 bpm, returns no observations
- Skips silently when `PlannedSessionRepository` not provided

**HR Drift:**
- Given steady-state segment ≥20 min with drift > 5 bpm, produces `LT1_HR` observation with weight 1.0
- Given drift < 2 bpm, produces `LT1_HR` observation with weight 1.0
- Given drift between 2 and 5 bpm, returns no observations

**HR Recovery:**
- Given hard effort + fast recovery (>30 bpm in 2 min), produces `LT1_HR` observation with weight 0.5
- Given hard effort + slow recovery (<20 bpm in 2 min), produces `LT1_HR` observation with weight 0.5
- Given ambiguous recovery (20-30 bpm), returns no observations

### Integration — PhysiologyMeasurementRepository Persistence
**File:** `tests/integration/test_physiology_measurement_repository_integration.py` (21 tests)
- Given `insert()` with all columns populated, the row persists in the real DB with correct parameter and source enum values
- Given `get_by_athlete()`, rows return in measurement_date DESC order
- Given `get_by_athlete_and_parameter()`, filters to the requested parameter only
- Given `get_recent_for_parameter()`, filters by source AND from_date AND limit
- Given ON DELETE SET NULL on `activity_id`, the measurement row is preserved when the Activity is deleted
- Given ON DELETE CASCADE on `athlete_id`, measurements are removed when the Athlete is deleted

### Integration — ThresholdDetectionService End-to-End
**File:** `tests/integration/test_threshold_detection_service_integration.py` (11 tests)
- Given an HR-only stream, produces `TRAINING_HR_DEFLECTION` observations (LT1_HR + LT2_HR) with weight 1.0
- Given an RR + HR stream, produces `TRAINING_RR_INFLECTION` observations with weight 2.5
- Given a power + HR stream, also runs the power-to-HR ratio algorithm
- Given `calibration_eligible = false`, persists no observations and does not call object storage
- Given `sport_type != RUNNING`, persists no observations
- Given missing `RawSensorStream`, persists no observations and does not touch object storage
- `measurement_date` on observations is `activity.activity_date`, not detection runtime date
- `detect()` does NOT write to `PhysiologyMeasurement` — that is Plan P2's responsibility

### Behaviour — Full User Journey
**File:** `tests/behaviour/test_threshold_detection_user_journey.py`
- Given register → onboard → upload running activity → signal_clean → threshold detection, produces HR deflection observations with correct contract
- Given an RR + HR activity, produces RR inflection observations with weight 2.5
- Given calibration eligibility/sport type/missing RawSensorStream gates, returns no observations at the full journey boundary
- Given ≥3 historical easy runs with consistent HR, produces natural-training LT1_HR observation with weight 0.5
