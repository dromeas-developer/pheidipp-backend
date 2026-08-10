# tests/unit/

## Purpose
Verifies individual units in isolation — services, repositories, schemas, and utility
functions — with the database session and all external dependencies mocked. No real
database connection is made; each test constructs its own mocks for `AsyncSession`,
collaborator services, and repositories.

## Contents
### Authentication
| File | Covers |
|---|---|
| `test_auth_service.py` | AuthService: register (atomic 4-entity creation + event, rollback on failure), login (success, wrong password 401, nonexistent email constant-time), rotate_refresh_token (rotation, old token rejected, expired rejected, unknown rejected, atomicity rollback) |
| `test_auth_schemas.py` | RegisterRequest password blank/whitespace validation, AuthResponse and TokenPairResponse token_hash and hashed_password exclusion |

### Models & Repositories
| File | Covers |
|---|---|
| `test_model_repository_contracts.py` | TestActivityModelColumns (no avg_hr/summary/lap columns), TestTwinStateRepositoryContract (6 methods: insert, get_latest, get_by_id, get_by_activity, get_by_activity_and_trigger, get_history; no update/delete), TestCoachingMessageRepositoryContract (6 methods: insert, get_by_athlete_id, get_by_athlete_and_type, get_existing_first_message, get_by_activity_and_type, get_all_count; no update/delete), TestSystemEventRepositoryContract (only add method; no read/update/delete) |

### Onboarding & Twin Bootstrap
| File | Covers |
|---|---|
| `test_bootstrap_helpers.py` | TestAgeInYears (birthday-based year computation), TestBootstrapSignal (prior_weight=0.5, uncertainty=1.0, dominant_source=questionnaire_estimate), TestBootstrapMetricConfidence (only lt1_hr/lt2_hr low, all other keys null) |
| `test_data_tier.py` | TestInferDataTier (6-tier inference from hr_source×power_source cartesian product, Tier 1-6 including T6 fallback) |
| `test_goal_type_whitelist.py` | TestGoalTypeWhitelist (race_event + target_performance accepted, fitness_improvement/maintenance/recovery rejected with exact error) |
| `test_onboarding_schemas.py` | TestOnboardingProfileTimezone (IANA timezone validation), TestWeeklyScheduleCompleteness (7-day completeness + extra-day rejection), TestGoalRequiredFieldsPerType (race_event/target_performance required fields), TestGoalEventDateInFuture (past/today rejected, future accepted), TestOnboardingFieldBounds (years_structured_training 0-80, fitness_level 1-5, weekly_volume_hours/km, height_cm), TestProfileImmutability (date_of_birth/sex/timezone rejected, extra="forbid") |
| `test_structural_risk_flag.py` | TestStructuralRiskFlag (sport_background != RUNNING_PRIMARY truth table across all 9 SportBackground enum members) |

### Calibration
| File | Covers |
|---|---|
| `test_calibration_eligibility_service.py` | CalibrationEligibilityService: eligibility gate (running sport, hr present, auto source, duration ≥1200s, hr dropout ≤20%, no gps loss, no sensor malfunction, null quality flags eligible) |

### Twin Recalibration
| File | Covers |
|---|---|
| `test_twin_recalibration_service.py` | TwinRecalibrationService: Banister update (load 50 applies one-day decay, zero days no decay, zero load pure decay, negative clamped to zero, form=fitness-fatigue, in-place mutation), time constants (none→population defaults, existing passed through, missing keys default), max confidence level (higher rank wins, monotonic, equal keeps first), confidence level string (previous none→computed, computed none→previous, both none→none, high never drops to medium, low upgrades to medium), confidence derivation (weight 3→low, 4→medium, 8→high, no lt1 data→low, no data for both→low, lt1 below threshold lt2 above→low) |

### FIT Parsing
| File | Covers |
|---|---|
| `test_fit_parser_service.py` | FitParserService: raw record extraction (hr/power per-sample values, total distance/ascent), sport type detection (running detected, unknown when omitted), parse failures (corrupt bytes, unsupported fit, no partial result), empty records (empty hr raises FitParseEmpty which subclasses FitParseError), parse delegates to executor |

### Load Computation
| File | Covers |
|---|---|
| `test_load_computation_service.py` | LoadComputationService: aerobic load (hr reserve formula on raw samples, lt1 intensity ~100 units/hour, monotonic with hrr_pct, zero contributes zero, empty hr raises MissingHeartRateError), aerobic load power (power at cp = unit load/hour, half intensity = 1/16, missing cp uses population estimate, cp zero raises MissingCriticalPowerError), structural load (gradient+density formula, risk flag lowers density, density capped at 15, null on no gps/zero distance, zero ascent = zero gradient cost), neuromuscular load (T5/T6 null, T1 produces load, no power records null), returns three load fields (aerobic, structural, neuromuscular) |

### Plan Generation
| File | Covers |
|---|---|
| `test_plan_generation_templates.py` | TestAllocateRaceEventPhases: phase allocation (24-week, 16-week, short-plan fallback, label order, specificity values) · TestDeriveExperienceLevel: experience level derivation (novice <2, intermediate 2-5, experienced >5, zero years) · TestEvaluateTrainingLengthGate: training length gate (marathon/5k/ultra thresholds, fitness gate, unknown goal type default) · TestScheduleCheckpoints: checkpoint scheduling (calibration at phase transition, benchmark week 4, progress review every 4 weeks, race simulation 2 weeks before goal, sorted by week number) |

### Coaching Agents
| File | Covers |
|---|---|
| `test_first_message_agent.py` | FirstMessageAgent: paragraph count validation (4 accepted, 3/5/1/empty rejected, whitespace trimmed), LiteLLM proxy routing (AsyncOpenAI base_url, no direct provider SDK), logical model identifier format (provider/model) |
| `test_workout_generation_agent.py` | WorkoutGenerationAgent: coerce int/int-range helpers, target type by data tier (T1-2 power, T3-4 GAP, T5-6 description), session intent mapping (rest→recovery, easy→low_aerobic, long→high_aerobic, threshold→threshold, vo2max→vo2max), step physiological intent (warmup/cooldown/recovery→recovery), output parsing & validation (warmup-work-cooldown sequence, sequential one-indexed steps, first=warmup, last=cooldown, work intent matches session, target type field constraints, empty/null/invalid JSON, session purpose), step target building (power→watts, gap→sec_per_km, description→no primary), target set assembly, two-column target structure (theoretical+adjusted NOT NULL, recovery_modifier=green, twin_state_id version) |

### Context Budget
| File | Covers |
|---|---|
| `test_context_budget_service.py` | ContextBudgetService: token estimation (JSON length / 4, zero for empty, scales with payload, nested structures), max tokens per agent (first_message=5000, workout_generation=3000, post_workout=6000), ContextSection (name/priority/budget, immutable), to_dict serialization, budget enforcement |

### Utilities & Security
| File | Covers |
|---|---|
| `test_ip_utils.py` | truncate_ip (IPv4 /24 CIDR, IPv6 /64 CIDR, None/empty/invalid/non-string) |
| `test_token_security.py` | safe_extra forbidden-key filtering (token_hash, hashed_password, ip_address, unknown keys), RefreshTokenRepository.discard_old_ips (7-day cutoff, zero-row case) |

### Worker
| File | Covers |
|---|---|
| `test_alembic_env.py` | TestAlembicEnv (env.py references settings.DATABASE_URL, does not reference POSTGRES_DSN) |
| `test_worker_app.py` | TestWorkerAppConnector (PsycopgConnector type, not Psycopg2Connector, conninfo keyword, receives get_procrastinate_dsn), TestWorkerAppTaskRegistration (signal_clean, threshold_detection, generate_plan, generate_first_message tasks registered) |

## Mock Boundaries
- DB session (AsyncSession) is mocked; no `db_session` fixture needed — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Collaborator services and repositories are replaced with `MagicMock`/`AsyncMock` inline in each test file
- No shared conftest.py at this level; fixtures are defined per-file
