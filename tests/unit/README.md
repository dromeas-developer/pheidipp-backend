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

## Mock Boundaries
- DB session (AsyncSession) is mocked; no `db_session` fixture needed — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Collaborator services and repositories are replaced with `MagicMock`/`AsyncMock` inline in each test file
- No shared conftest.py at this level; fixtures are defined per-file
