# Test Scenarios — Phase 1 Gap Analysis — Batch 6: FIT Import & Post-Workout

## Source: docs/implementation/phase-1/gap-analysis-phase-1/overview.md
## Sub-Phases Covered: 1.6 (Simple FIT Import & Post-Workout)

---

## Step 1 — Activity Upload (POST /athletes/{id}/activities/upload)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | Valid FIT file upload creates Activity with 202 | Authenticated athlete, valid FIT file bytes, `source="manual_upload"` | 202 Accepted with `activity` (source=MANUAL_UPLOAD, non-null `fit_file_key`, load scores null at creation), `task_id` (UUID), `ingestion_status="pending"`; FIT file stored in MinIO bucket `pheidipp-fit-files` | application-logic | external-only (mock MinIO client) |
| 2 | Object storage upload happens BEFORE Activity creation | Inject MinIO upload failure | No `Activity` row created; upload failure propagated to caller; no partial state | application-logic | external-only (mock MinIO client to raise) |
| 3 | fit_file_key always set for non-manual source | Upload with `source="manual_upload"` | `activity.fit_file_key` is non-null (the MinIO object key) | application-logic | external-only (mock MinIO client) |
| 4 | No averaged fields stored on Activity | Inspect created Activity row | `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence` columns do not exist on the row (model has no such columns) | application-logic | external-only (mock MinIO client) |
| 5 | Upload commits before fit_ingest task enqueued | Inspect upload handler flow | `session.commit()` called after `stage_upload()`, BEFORE `fit_ingest.defer()`; the Activity row is visible to the worker | application-logic | external-only (mock MinIO + mock procrastinate defer) |

## Step 2 — FIT Parsing (FitParserService)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 6 | Parse returns raw HR records, not summary stats | Valid FIT file with HR samples | `ParsedFitData.hr_records` is a list of per-sample HR values (integers), not a single averaged value; `duration_seconds` is the raw duration | application-logic | external-only (read fixture FIT file) |
| 7 | Parse runs via asyncio.to_thread | Inspect `parse_fit` implementation | FIT parsing call is wrapped in `asyncio.to_thread()` (CPU-bound, not blocking the event loop) | application-logic | none |
| 8 | Parse extracts sport type | Valid FIT file with sport type metadata | `ParsedFitData` includes detected `sport_type` (e.g. `RUNNING`); `sport_type_detection_version` set | application-logic | external-only (read fixture FIT file) |
| 9 | Unsupported FIT file fails gracefully | Malformed or unsupported FIT bytes | `FitParseError` (or equivalent) raised; no partial `ParsedFitData` returned | application-logic | external-only (read fixture FIT file) |

## Step 3 — Load Computation: Aerobic Load (HR-Reserve) (Fixture F2)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 10 | Aerobic load raw formula at LT1 (F2) | `hr_records`: 3600 samples all at hr=169 (hrr_pct=0.85), `max_hr_estimate=190`, `resting_hr=50`, `data_tier=TIER_4` | Per-sample weight `=e^(1.92×0.85)−1=e^1.632−1≈4.114` (from spec formula). Raw formula total `=3600×4.114/3600=4.114`. Test: (a) the formula is applied correctly to raw HR samples (not pre-averaged), (b) final normalised output for 1hr@LT1 falls in [80, 120] (per spec's "≈100 units" reference — range check, not exact). | application-logic | none |
| 11 | Output proportional to sample count | 1800 samples at hrr_pct=0.85 (half-hour) vs 3600 samples | Raw formula output for half-hour ≈ 2.057 (half of 4.114). Test: doubling duration roughly doubles output (linear with sample count). | application-logic | none |
| 12 | Output monotonic with hrr_pct | hrr_pct=0.50 vs hrr_pct=0.85 | Per-sample weight at 0.50 = e^0.96−1≈1.612; at 0.85 = ≈4.114. Higher hrr_pct → higher per-sample contribution → higher total output. | application-logic | none |
| 13 | hrr_pct=0 contributes approximately 0 | `hr_records`: 3600 samples at hr=resting_hr (hrr_pct=0.0) | Per-sample weight `=exp(1.92×0.0)−1=1.0−1=0.0`. Raw formula total ≈ 0.0 (±0.001). | application-logic | none |
| 14 | Missing HR records raises error | `hr_records=[]`, `data_tier=TIER_4` | `MissingHeartRateError("cannot compute aerobic load: parsed FIT has no HR records")` | application-logic | none |
| 15 | Power-based load for Tier 1-2 with power (F3) | `data_tier=TIER_1`, `power_records`: 3600 samples at watts=300, `cp_estimate=300` | `aerobic_load = Σ(300/300)^4 / 3600 = 3600×1.0/3600 = 1.0` (±0.001). Formula per spec: `Σ(watts/cp)^4 / 3600`. | application-logic | none |
| 16 | Power-based load with missing CP | `data_tier=TIER_1`, `power_records` present, `cp_estimate=None` | Uses population estimate (≥0); `aerobic_load = Σ(watts/cp)^4 / 3600` with estimated cp. Test: does not crash when CP is missing. | application-logic | none |
| 17 | CP <= 0 raises MissingCriticalPowerError | `cp_estimate=0`, power records present | `MissingCriticalPowerError("cp_estimate must be positive for power-based load")` — formula requires cp > 0 | application-logic | none |
| 18 | Power-based load: half intensity yields 1/16th output (F3) | `cp=300`, `watts=150` (half intensity), 3600 samples | `Σ(150/300)^4 / 3600 = Σ(0.5)^4 = 3600×0.0625/3600 = 0.0625`. At half intensity, output is 1/16th (fourth-power sensitivity). | application-logic | none |

## Step 4 — Load Computation: Structural Load (Fixtures F4, F5, F6)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 17 | Structural load with gradient and density (F4) | `total_distance_m=10000` (10km), `total_ascent_m=100`, `recent_structural_load_72h=50`, `structural_risk_flag=False`, `has_gps=True` | `base=10×1.0=10.0`, `gradient_cost=(100/100)×0.18×10=1.8`, `density_penalty=min(50×0.12, 15)=6.0`, `total=17.8` (tolerance ±0.01) | application-logic | none |
| 18 | Structural load with risk flag halves coefficient (F5) | Same as F4 but `structural_risk_flag=True` | `density_penalty=min(50×0.08, 15)=4.0`, `total=15.8` (tolerance ±0.01) | application-logic | none |
| 19 | Structural load density cap at 15 (F6) | `recent_structural_load_72h=200`, `structural_risk_flag=False` | `density_penalty=min(200×0.12, 15)=min(24, 15)=15.0` (capped) | application-logic | none |
| 20 | Structural load null without GPS | `has_gps=False` | `structural_load=None` | application-logic | none |
| 21 | Structural load null with zero distance | `has_gps=True`, `total_distance_m=0` | `structural_load=None` (guard: `total_distance_m <= 0`) | application-logic | none |
| 22 | Structural load with no ascent | `total_distance_m=10000`, `total_ascent_m=0` or None, `has_gps=True` | `gradient_cost=0.0`, `total=base+density_penalty` | application-logic | none |

## Step 5 — Load Computation: Neuromuscular Load

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 23 | Neuromuscular load null for Tier 5-6 | `data_tier=TIER_5` or `TIER_6` | `neuromuscular_load=None` | application-logic | none |
| 24 | Neuromuscular load computed for Tier 1-4 with power | `data_tier=TIER_1`, `power_records` with variability | `neuromuscular_load = cv × duration_hours + (time_above_vo2 / 3600 × 2.5)`; non-null float | application-logic | none |
| 25 | Neuromuscular load null without power records | `data_tier=TIER_3`, no `power_records` | `neuromuscular_load=None` (falls back to power, none available) | application-logic | none |

## Step 6 — Calibration Eligibility Gate (Fixture F13)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 26 | All conditions met → eligible | `sport_type=RUNNING`, `has_hr=True`, `source="manual_upload"`, `duration_seconds=1800`, `quality_flags={}` | `calibration_eligible=True` | application-logic | none |
| 27 | Non-running sport → not eligible | `sport_type=CYCLING`, all other conditions met | `calibration_eligible=False` | application-logic | none |
| 28 | No HR → not eligible | `has_hr=False`, all other conditions met | `calibration_eligible=False` | application-logic | none |
| 29 | Manual entry → not eligible | `source="manual_entry"`, all other conditions met | `calibration_eligible=False` | application-logic | none |
| 30 | Duration < 1200s → not eligible | `duration_seconds=1199`, all other conditions met | `calibration_eligible=False` | application-logic | none |
| 31 | Duration = 1200s boundary → eligible | `duration_seconds=1200`, all other conditions met | `calibration_eligible=True` (boundary: `< 1200` fails, `>= 1200` passes) | application-logic | none |
| 32 | HR dropout > 20% → not eligible | `quality_flags={"hr_dropout_pct": 0.21}`, all other conditions met | `calibration_eligible=False` | application-logic | none |
| 33 | HR dropout = 20% boundary → eligible | `quality_flags={"hr_dropout_pct": 0.20}`, all other conditions met | `calibration_eligible=True` (boundary: `> 0.20` fails, `<= 0.20` passes) | application-logic | none |
| 34 | GPS loss → not eligible | `quality_flags={"gps_loss": True}`, all other conditions met | `calibration_eligible=False` | application-logic | none |
| 35 | Sensor malfunction → not eligible | `quality_flags={"sensor_malfunction": True}`, all other conditions met | `calibration_eligible=False` | application-logic | none |
| 36 | Phase 1.6: all sessions NOT calibration-eligible | Any Phase 1 activity | `calibration_eligible=False` for all Phase 1.6 activities (no calibration in Phase 1) | application-logic | none |

## Step 7 — Banister Update (Fixture F1)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 37 | Banister update with load=50, days_since=3 (F1) | `fitness_row.aggregate={"fitness": 100, "fatigue": 40, "form": 60}`, `aerobic_load=50`, `time_constants={"fitness_tau_days": 42, "fatigue_tau_days": 7, "source": "population_default"}` | `new_fitness = 100×e^(-3/42) + 50 = 100×0.93107 + 50 = 143.107`; `new_fatigue = 40×e^(-3/7) + 50 = 40×0.65144 + 50 = 76.058`; `new_form = 143.107 - 76.058 = 67.049` (tolerance ±0.05 on each) | application-logic | none |
| 38 | Banister update with no decay (days_since=0) | `days_since=0`, `aerobic_load=50`, same fitness_row | `new_fitness = 100×e^0 + 50 = 150.0`; `new_fatigue = 40×e^0 + 50 = 90.0`; `new_form = 60.0` (no exponential decay) | application-logic | none |
| 39 | Banister update with zero load (pure decay, days_since=3) | `aerobic_load=0`, `days_since=3`, same fitness_row | `new_fitness = 100×e^(-3/42) = 93.107`; `new_fatigue = 40×e^(-3/7) = 26.058`; `new_form = 67.049` (fitness decays faster than fatigue, form improves) | application-logic | none |
| 40 | Banister update with negative load clamped to zero | `aerobic_load=-10` | `max(0.0, -10) = 0.0`; same as zero-load scenario — negative loads are not valid per the model, must not subtract from fitness | application-logic | none |
| 41 | Banister update writes form = fitness - fatigue | Any Banister update | `aggregate["form"]` = `aggregate["fitness"] - aggregate["fatigue"]` after update; DB CHECK `ck_athlete_fitness_aggregate_form_invariant` validates | application-logic + database | none |
| 42 | Population time constants read correctly | `fitness_row.time_constants=None` | `read_time_constants` returns `{"fitness_tau_days": 42, "fatigue_tau_days": 7, "source": "population_default"}` (defaults from spec) | application-logic | none |

## Step 8 — Twin Recalibration (TwinRecalibrationService.recalibrate)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 43 | Recalibrate appends new TwinState | Athlete with active goal, AthleteFitness, AthletePhysiology, latest TwinState; `activity_id=A1`, `aerobic_load=50` | New `TwinState` inserted with `trigger=ACTIVITY_SYNC`, `model_version="v1-activity-sync"`, updated fitness/fatigue/form from Banister update; `twin_recalibrated` event in outbox | application-logic | db-session |
| 44 | Recalibrate preserves threshold values from latest TwinState | Latest TwinState has `lt1_hr_bpm=138.0`, `lt2_hr_bpm=161.0` | New TwinState copies `lt1_hr_bpm=138.0`, `lt2_hr_bpm=161.0` from latest (thresholds unchanged at activity_sync) | application-logic | db-session |
| 45 | Recalibrate preserves confidence_level from latest | Latest TwinState has `confidence_level=LOW` | New TwinState has `confidence_level=LOW` (unchanged at activity_sync — only calibration trigger can upgrade) | application-logic | db-session |
| 46 | Missing active goal raises | Athlete with no active TrainingGoal | `MissingTrainingGoalError("no active training goal for athlete ...")` | application-logic | db-session |
| 47 | Missing AthleteFitness raises | Athlete with no AthleteFitness row | `MissingAthleteFitnessError("no athlete_fitness row for athlete ...")` | application-logic | db-session |
| 48 | TwinState append-only — recalibrate never updates existing | Inspect recalibrate flow | `TwinStateRepository.insert` called (not update); new row created; old TwinState rows unchanged | application-logic | db-session |

## Step 9 — Confidence Ratchet (ADR-011) (Fixture F9)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 49 | Global confidence ratchet: MEDIUM stays MEDIUM | `previous.confidence_level=MEDIUM`, `computed_level=LOW` | `max_confidence_level(MEDIUM, LOW) = MEDIUM` (never decreases — ADR-011) | application-logic | none |
| 50 | Global confidence ratchet: LOW → HIGH upgrade | `previous.confidence_level=LOW`, `computed_level=HIGH` | `max_confidence_level(LOW, HIGH) = HIGH` (upgrade allowed) | application-logic | none |
| 51 | Per-metric ratchet: previously-unmeasured metric gains data | `previous.metric_confidence={"lt1_hr": "low", "lt1_power": null}`, new physiology gives `computed={"lt1_hr": "low", "lt1_power": "medium"}` | `lt1_power` changes from null to "medium" — newly available data must be reflected, not stuck at the bootstrapped null. `lt1_hr` stays "low" (no change). | application-logic | none |
| 52 | Per-metric ratchet: HIGH never drops to MEDIUM | `previous={"lt1_hr": "high"}`, `computed={"lt1_hr": "medium"}` | `max_confidence_level_string("high", "medium") = "high"` (never decreases) | application-logic | none |
| 53 | twin_confidence_upgraded event only fires on increase | `previous.confidence_level=LOW`, `computed=HIGH` | `twin_confidence_upgraded` event published with `from_level="low"`, `to_level="high"` | application-logic | db-session |
| 54 | No twin_confidence_upgraded event when level unchanged | `previous.confidence_level=MEDIUM`, `computed=MEDIUM` | No `twin_confidence_upgraded` event published | application-logic | db-session |

## Step 10 — Confidence Level Derivation (Fixture F8)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 55 | min(lt1, lt2) = 3.0 → LOW (below 4.0 threshold) | `lt1.hr.prior_weight=5.0`, `lt2.hr.prior_weight=3.0` | `min(5.0, 3.0) = 3.0` → confidence = LOW (< 4.0 per spec threshold) | application-logic | none |
| 56 | min(lt1, lt2) = 4.0 → MEDIUM (at threshold) | `lt1.hr.prior_weight=4.0`, `lt2.hr.prior_weight=6.0` | `min(4.0, 6.0) = 4.0` → confidence = MEDIUM (≥ 4.0 per spec threshold) | application-logic | none |
| 57 | min(lt1, lt2) = 8.0 → HIGH (at threshold) | `lt1.hr.prior_weight=9.0`, `lt2.hr.prior_weight=8.0` | `min(9.0, 8.0) = 8.0` → confidence = HIGH (≥ 8.0 per spec threshold) | application-logic | none |
| 58 | Conservative default: no data for one parameter → LOW | `lt1.hr` has no observation (missing/null/absent), `lt2.hr.prior_weight=5.0` | Confidence must be LOW — the spec says the global level is the minimum across HR parameters. Without data for one, the minimum cannot exceed the data-less parameter. | application-logic | none |
| 59 | Conservative default: no data for both parameters → LOW | Neither `lt1.hr` nor `lt2.hr` has observations | Confidence must be LOW — no data can never produce confidence ≥ MEDIUM | application-logic | none |

## Step 11 — Activity Deduplication

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 60 | Duplicate (athlete_id, external_id, source) rejected | Insert two Activity rows with same `(athlete_id, external_id="garmin-123", source="manual_upload")` | `IntegrityError` from `uq_activities_athlete_external_source` partial unique index | database | db-session |
| 61 | Same external_id, different source allowed | `(athlete_id, external_id="ext-1", source="garmin")` and `(athlete_id, external_id="ext-1", source="strava")` | Both inserts succeed (unique is on the triple) | database | db-session |
| 62 | manual_entry with null external_id exempt from dedup | Two Activity rows with `external_id=None`, `source="manual_entry"` | Both succeed (partial unique predicate `WHERE external_id IS NOT NULL` excludes them) | database | db-session |

## Step 12 — PostWorkoutAgent: Idempotency & Three-Paragraph Structure

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 63 | Post-workout message generated successfully | Athlete with completed Activity, TwinState, PlannedSession link; no existing post_workout message for activity | `CoachingMessage` with `message_type=POST_WORKOUT`, `activity_id` linked, `twin_state_id` linked, 3-paragraph content; `coaching_message_generated` event; `GenerationEvent(success=true)` | application-logic | external-only (mock LLM proxy) |
| 64 | Second analyse call returns existing message | Call `POST .../analyse` twice for same activity | Second call returns existing `CoachingMessage` (idempotent); no LLM call; no new `GenerationEvent`; `CoachingMessageRepository.get_by_activity_and_type` returns existing | application-logic | external-only (mock LLM proxy — assert NOT called on second) |
| 65 | DB partial unique enforces post_workout singleton | Direct insert of second `post_workout` for same `activity_id` | `IntegrityError` from `uq_coaching_messages_activity_post_workout` | database | db-session |
| 66 | Post-workout message has exactly 3 paragraphs | Mock LLM returns 3-paragraph message | Parsed `content` has exactly 3 paragraphs | application-logic | external-only (mock LLM proxy) |
| 67 | Post-workout message references actual HR data and load | Activity with `aerobic_load=80`, `duration_seconds=3600` | Message content references the actual HR data, duration, and load (not generic) | application-logic | external-only (mock LLM proxy) |

## Step 13 — PostWorkoutAgent: LLM Failure & GenerationEvent

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 68 | LLM failure writes GenerationEvent(success=false) | Mock LLM proxy raises | `GenerationEvent(success=false, failure_reason=...)`; 503 returned; no CoachingMessage created | application-logic | external-only (mock LLM proxy to raise) |
| 69 | PostWorkoutAgent routes through LiteLLM proxy | Inspect `PostWorkoutAgent` LLM client | `AsyncOpenAI(base_url=settings.LITELLM_BASE_URL)`; no direct provider SDK | application-logic | none |

## Step 14 — ComplianceService

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 70 | Compliance compares actual to PlannedSession | Activity linked to PlannedSession (threshold session, target HR zone 4); actual HR data shows zone 3 | Compliance result indicates under-execution relative to planned intent | application-logic | db-session |
| 71 | Activity without PlannedSession link | `activity.planned_session_id=None` | Compliance comparison skipped (no plan to compare against); post-workout message notes unplanned session | application-logic | db-session |

## Step 15 — Ingestion Pipeline Orchestration

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 72 | Full pipeline: parse → detect sport → compute loads → check eligibility → recalibrate → emit events | Valid FIT file uploaded, `fit_ingest` worker task runs | `Activity` row updated with `aerobic_load`, `neuromuscular_load`, `structural_load` populated; `calibration_eligible` set; new `TwinState` appended; `activity_ingested` event in outbox; `sport_type_detected` event if sport detected | application-logic | external-only (mock MinIO for FIT download) |
| 73 | Load scores null at creation, populated by LoadComputationService | Inspect Activity after upload (before pipeline) vs after pipeline | After upload: `aerobic_load=None`, `neuromuscular_load=None`, `structural_load=None`; After pipeline: load scores populated (or null if tier 5-6) | application-logic | external-only (mock MinIO) |
| 74 | LoadComputationService receives raw records, not summaries | Inspect `LoadComputationInputs.parsed_fit` | `parsed_fit.hr_records` is a list of per-sample values; `LoadComputationService` does not receive pre-averaged stats | application-logic | none |
| 75 | Worker commits after pipeline completes | Inspect `fit_ingest` task | `session.commit()` called after `ingest_async()` completes; all updates (Activity load scores, TwinState, events) in one transaction | application-logic | external-only (mock MinIO) |