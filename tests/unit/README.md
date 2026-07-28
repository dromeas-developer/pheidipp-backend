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

### Utilities & Security
| File | Covers |
|---|---|
| `test_ip_utils.py` | truncate_ip (IPv4 /24 CIDR, IPv6 /64 CIDR, None/empty/invalid/non-string) |
| `test_token_security.py` | safe_extra forbidden-key filtering (token_hash, hashed_password, ip_address, unknown keys), RefreshTokenRepository.discard_old_ips (7-day cutoff, zero-row case) |

## Mock Boundaries
- DB session (AsyncSession) is mocked; no `db_session` fixture needed — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Collaborator services and repositories are replaced with `MagicMock`/`AsyncMock` inline in each test file
- No shared conftest.py at this level; fixtures are defined per-file
