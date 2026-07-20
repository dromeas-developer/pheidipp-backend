> **Baseline — test companion for** `batch-1-fit-ingestion-expansion.md`, migrated from `docs/implementation/phase-2/phase-2-1-p1-fit-ingestion-expansion.md`, `phase-2-1-p2-validation-remediation.md`, and `phase-2-1-p3-sport-type-filtering.md` **on** 2026-07-19.

## Test Scenarios

Derived from the test manifest (`tests/test-manifest/phase-2-1.yaml`) and actual test files.

### Unit — FitParserService
**File:** `tests/unit/test_fit_parser_service.py`

**GPS and sensor extraction:**
- Given a FIT file with GPS records, `ParsedFitData.gps_records` populated, `has_gps = true`, `total_distance_m` and `total_ascent_m` present
- Given a FIT file with RR intervals, `rr_records` carries values in milliseconds, `has_rr_intervals = true`
- Given GPS speed > 25 m/s, flagged as artifact (GPS spike)
- Given empty GPS data, `has_gps = false`
- Given session-level totals (distance, ascent), populated from FIT session message

**Sport type extraction:**
- Given a running FIT file (sport=1), `sport_type = 'running'`, `detection_confidence = 'high'`
- Given a cycling FIT file (sport=2), `sport_type = 'cycling'`
- Given a swimming FIT file (sport=5), `sport_type = 'swimming'`
- Given a trail-running FIT file (sport=1, sub_sport=14), `sport_type = 'running'` (sub_sport does not override running)
- Given sport=0 (generic) or missing sport field, `sport_type = 'unknown'`, `detection_confidence = 'unknown'`
- Given an unrecognized sport integer (e.g. 99), `sport_type = 'other'`, `detection_confidence = 'low'`
- Given indoor-cycling (sport=2, sub_sport=8), `sport_type = 'cycling'`

### Unit — LoadComputationService
**File:** `tests/unit/test_load_computation_service.py`

**Aerobic load:**
- Given Tier 1-2 athlete with power data, power-based aerobic load computed via fourth-power intensity factor (sum of (watts/cp)^4 normalised to 3600s)
- Given Tier 3-4 athlete without power data, HR-based aerobic load computed

**Neuromuscular load:**
- Given Tier 1-4, neuromuscular load = variability index (CV of power or GAP) + time above VO2max (95% LT2)
- Given Tier 5-6, returns null

**Structural load:**
- Given GPS data, structural_load = base (distance × surface_modifier 1.0) + gradient_cost + density_penalty
- Given density penalty capped at 15 with extreme recent load values
- Given crossover athlete (`structural_risk_flag = true`), density coefficient = 0.08
- Given non-crossover athlete, density coefficient = 0.12
- Given no GPS data (`has_gps = false`), structural load returns null

### Unit — CalibrationEligibilityService
**File:** `tests/unit/test_calibration_eligibility_service.py`

**Sport-type gate (first check):**
- Given `sport_type = 'running'` + passes five rules → `calibration_eligible = true`
- Given `sport_type = 'cycling'` → `false` regardless of HR/duration/quality
- Given `sport_type = 'swimming'` → `false`
- Given `sport_type = 'unknown'` → `false`
- Given `sport_type = 'strength'` → `false`
- Given `sport_type = 'other'` → `false`
- Given sport-type check runs before all other rules (cycling with HR dropout > 20% fails at sport check, not HR check)

**Five-rule gate (running activities only):**
- Given all five rules pass, `calibration_eligible = true`
- Given `source = manual_entry`, returns `false`
- Given `has_hr = false`, returns `false`
- Given duration < 1200s, returns `false`
- Given HR dropout > 20%, returns `false`
- Given `gps_loss = true`, returns `false`
- Given `sensor_malfunction = true`, returns `false`
- Given Tier 5-6 activity, returns `false`

### Unit — ActivityIngestionService
**Files:** `tests/unit/test_activity_ingestion_service.py`, `tests/unit/test_activity_ingestion_service_signal_clean.py`

**Quality flags (gps_loss):**
- Given a GPS stream with a 31-second gap between consecutive timestamps, `gps_loss = true`
- Given largest gap is exactly 30 seconds, `gps_loss = false`
- Given several sub-30s gaps, `gps_loss = false`
- Given `has_gps = true` but empty GPS record list, `gps_loss = true`
- Given `has_gps = false`, `gps_loss = false`
- Given out-of-order timestamps (negative delta), not treated as a gap

**structural_risk_flag:**
- Given athlete with `AthleteProfile.structural_risk_flag = true`, density penalty uses crossover coefficient (0.08)
- Given athlete with no `AthleteProfile`, defaults to `False` (coefficient 0.12)

**Pipeline integration:**
- Given full pipeline with power + GPS + RR data, all three load scores produced
- Given `activity_calibration_eligible` event fires when eligible with `{activity_id, aerobic_load, neuromuscular_load, structural_load}`
- Given event does NOT fire when `calibration_eligible = false`
- Given `has_gps` populated correctly from parsed FIT data
- Given data tier inferred from athlete preferences
- Given non-running activity, `data_tier` overridden to `TIER_6`

**Event firing:**
- Given `sport_type_detected` fires with `{activity_id, sport_type, detection_confidence, detection_version}` for all non-manual-entry sources
- Given `sport_type_detected` fires before `activity_calibration_eligible`
- Given `source = 'manual_entry'`, `sport_type_detected` does NOT fire

**API responses:**
- Given `GET /athletes/{id}/activities/{aid}`, returns `has_gps`, `sport_type`, `sport_type_detection_version`

### Integration — Activity Ingestion Signal Clean Enqueue
**File:** `tests/integration/test_activity_ingestion_signal_clean_enqueue_integration.py`
- Given eligible running activity, `signal_clean` task deferred after ingestion

### Behaviour — Full User Journey
- Given uploading a running FIT file with power data, `Activity.sport_type = 'running'`, `calibration_eligible = true` when meeting gate, load scores populated
- Given uploading a cycling FIT file, `sport_type = 'cycling'`, `calibration_eligible = false`, `data_tier = TIER_6`
- Given uploading a FIT file with undetectable sport, `sport_type = 'unknown'`, `calibration_eligible = false`
- Given existing Phase-2.1 test fixtures (running FIT files), continue to pass — no regression
- Given a running activity that fails the five rules (e.g. duration < 1200s), remains `calibration_eligible = false`
