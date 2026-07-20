> **Baseline — test companion for** `batch-2-physiology-update.md`, migrated from `docs/implementation/phase-2/phase-2-3-p2-physiology-update.md` **on** 2026-07-19.

## Test Scenarios

Derived from the test manifest (`tests/test-manifest/phase-2-3p2.yaml`) and actual test files.

### Unit — Bayesian Update Pure Function
**File:** `tests/unit/test_physiology_update_service_bayesian.py`
- Given current state (value=165, prior_weight=0.5, uncertainty=1.0) and observation (value=170, weight=1.0), posterior mean is weighted toward the observation, prior_weight = 1.5, uncertainty < 1.0
- Given posterior uncertainty approaching zero, the 0.5 floor is enforced (UNCERTAINTY_FLOOR)
- Given observation.weight > decayed prior weight, dominant_source flips to the observation's source
- Given observation.weight ≤ decayed prior weight, dominant_source is preserved
- Given 42-day decay constant, `decay_factor = exp(-days_since_last / 42)`
- Given `days_since_last = 0` (same-day), prior weight stays intact
- Given large gap (1 year), decayed_weight shrinks toward 0
- Given ISO-8601 datetime string or bare date string in `last_observation_date`, parses correctly
- Given `datetime.date` or `datetime.datetime` observation, coerced to date
- Given `days_since_last` is negative (clock skew), clamped to `max(0, delta)`

### Unit — Init Null Parameter State
**File:** `tests/unit/test_physiology_update_service_bayesian.py`
- Given previously-null parameter + first observation, `init_null_parameter_state()` bootstraps a fresh `PhysiologyParameterState` with value, uncertainty (1.0), prior_weight, dominant_source, last_observation_date from the observation

### Unit — PhysiologyUpdateResult Dataclass
**File:** `tests/unit/test_physiology_update_service_bayesian.py`
- Given default construction, `shifted_parameters=[]`, `metric_confidence={}`, `confidence_transitions={}`, `measurements_written=0`

### Unit — Pure Helpers
**File:** `tests/unit/test_physiology_update_service_pure_helpers.py`
- Given `prior_weight >= 8.0`, `_compute_metric_confidence()` returns "high"
- Given `4.0 <= prior_weight < 8.0`, returns "medium"
- Given `prior_weight < 4.0`, returns "low"
- Given `None` prior_weight, returns "low"
- Given `physiology.cp` is null, cp entry returns None
- Given LOW→MEDIUM transition detected, `_detect_confidence_transitions()` returns `(LOW, MEDIUM)` tuple
- Given MEDIUM→HIGH detected, returns `(MEDIUM, HIGH)` tuple
- Given no change (MEDIUM→MEDIUM), NOT reported
- Given downward change (HIGH→LOW), NOT reported (monotonicity)

### Unit — Repository Update In Place
**File:** `tests/unit/test_athlete_physiology_repository_update_in_place.py`
- Given `update_in_place(athlete_id, lt1=mapping)`, mutates existing row, flushes without commit
- Given no row exists, raises RuntimeError
- Given `cp=None`, clears the column to NULL
- Given `cp=UNSET_SENTINEL`, column unchanged

### Unit — Service Orchestration
**File:** `tests/unit/test_physiology_update_service_orchestration.py`
- Given construction with explicit repos and event publisher, stores dependencies
- Given construction with only `AsyncSession`, auto-builds default event publisher
- Given `_get_parameter_state()` for `LT1_HR`, resolves to `physiology.lt1["hr"]`
- Given `_get_parameter_state()` for `LT2_HR`, resolves to `physiology.lt2["hr"]`
- Given `_get_parameter_state()` for `CP`, resolves to `physiology.cp`
- Given null sub-state, returns None (does not raise)
- Given unsupported `PhysiologyParameter`, raises ValueError
- Given `_apply_updated_states()`, writes new sub-state into JSONB, calls `flag_modified` on each touched outer column
- Given missing `AthletePhysiology` row, `apply_observations()` raises `MissingAthletePhysiologyError`
- Given observations, `physiology_measurements.insert` called once per observation (unconditional)
- Given posterior shift > 1 unit, `update_in_place` called and `physiology_updated` event published with correct payload
- Given posterior shift ≤ 1 unit, event NOT published but measurement still written and `update_in_place` still called
- Given duplicate observation (same parameter, value, date, source, activity_id), measurement written but posterior NOT shifted, event NOT fired
- Given first CP observation (cp=null), `init_null_parameter_state` applied — posterior moves from null to non-null dict
- Given 4 observations of weight 1.0 for LT2_HR, prior_weight reaches 4.0 → LOW→MEDIUM transition
- Given 8 observations of weight 1.0 for LT2_HR, prior_weight reaches 8.0 → MEDIUM→HIGH transition
- Given 2 RR observations (weight 2.5 each), prior_weight reaches 5.0 → LOW→MEDIUM transition

### Integration — End-to-End
**File:** `tests/integration/test_physiology_update_service_integration.py`
- Given `apply_observations()` against real DB, `AthletePhysiology` JSONB columns mutated in place
- Given `PhysiologyMeasurement` rows written for every observation (unconditional)
- Given posterior shift > 1 unit, `physiology_updated` SystemEvent + SystemEventOutbox PENDING in same transaction
- Given posterior shift ≤ 1 unit, no event persisted
- Given duplicate observation, measurement written but physiology NOT mutated and no event

### Integration — Confidence Transitions
**File:** `tests/integration/test_physiology_update_service_confidence_transitions_integration.py`
- Given 4 HR-deflection observations, prior_weight reaches 4.5 at DB layer (LOW→MEDIUM)
- Given 8 observations, prior_weight reaches 8.5 (MEDIUM→HIGH)
- Given 2 RR observations (weight=2.5), reach MEDIUM faster
- Given subsequent calls, accumulate against persisted state

### Behaviour — Full User Journey
**File:** `tests/behaviour/test_physiology_update_user_journey.py`
- Given HTTP register → activity → signal-cleaned stream → detect() → apply_observations(), `physiology_updated` event lands in outbox in same transaction as AthletePhysiology mutation
- Given duplicate observation across separate calls, measurement written but no event
- Given 4 observations accumulate, LOW→MEDIUM transition at DB layer
- Given first CP observation, cp bootstrapped from null to non-null

### Registered Services
- `from app.services import PhysiologyUpdateService` works
- `from app.services import PhysiologyUpdateResult` works
- `from app.services import MissingAthletePhysiologyError` works
