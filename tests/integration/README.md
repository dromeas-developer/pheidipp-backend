# tests/integration/

## Purpose
Verifies that services, repositories, and ORM models interact correctly against a real
PostgreSQL test database. External APIs and the message bus are mocked, but the database
session, transaction boundaries, and constraint enforcement are exercised end-to-end through
the `db_session` fixture.

## Contents
### Authentication
| File | Covers |
|---|---|
| `test_auth_db.py` | Athlete email uniqueness (duplicate email IntegrityError pgcode 23505, case-insensitive matching via normalize_email before the functional lower(email) index fires) |

### Coaching & Workout
| File | Covers |
|---|---|
| `test_coaching_workout_db.py` | CoachingMessage (first_message singleton, post_workout singleton, post_workout null activity exempt, content empty rejected), GeneratedWorkout (unique plan+date, theoretical_targets not object, adjusted_targets null, recovery_modifier invalid), WorkoutStep (unique workout+step_order, physiological_intent NOT NULL, step_order < 1 rejected, description empty rejected, duration_seconds negative rejected, duration_seconds null accepted) |

### Fitness & Physiology
| File | Covers |
|---|---|
| `test_fitness_physiology_db.py` | AthleteFitness (unique athlete_id, aggregate form invariant valid/invalid, dimensional form invariant valid/invalid/null-skips, time_constants.source validation), AthletePhysiology (unique athlete_id) |

### Profile, Preferences & Activity
| File | Covers |
|---|---|
| `test_profile_preferences_activity_db.py` | AthleteProfile (unique athlete_id), AthletePreferences (unique athlete_id, years_structured_training negative), Activity (external_id dedup, null external_id manual-entry exempt) |

### System Events
| File | Covers |
|---|---|
| `test_system_event_db.py` | SystemEvent (athlete_id NOT NULL) |

### Training Goal & Plan
| File | Covers |
|---|---|
| `test_training_goal_plan_db.py` | TrainingGoal (single active per athlete, multiple inactive allowed, fitness_level range, weekly_volume_hours/km negative), WeeklyPlan (unique plan+week), Checkpoint (planned_session_id one-to-one) |

## Mock Boundaries
- External APIs and message bus are mocked; DB (test_pheidipp) is real — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Uses the `db_session` fixture from `tests/conftest.py` (function-scoped, auto-rollback + post-test truncation)
- No shared conftest.py at this level; fixtures are defined per-file
