> **Baseline — test companion for** `batch-1-consistency-cleanup.md`, migrated from `docs/implementation/phase-1/phase-consistency-p1-fix-patterns-and-documentation.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements — this is a refactoring/documentation pass with no functional changes. All tests are regression guards.

### Email Normalization — Behavioral Equivalence
- Given email `"  User@Example.com  "`, `normalize_email()` returns `"user@example.com"`
- Given email `"user@example.com"` (already normalized), returns unchanged
- Given `AuthService.register()` with mixed-case email, registration succeeds and stored email is normalized
- Given `AuthService.login()` with mixed-case email, login succeeds (case-insensitive matching)
- Given `AthleteRepository.get_by_normalized_email("User@Example.com")`, finds the athlete registered with `"user@example.com"`
- Given `AthleteRepository.email_exists("User@Example.com")`, returns True when athlete exists
- Given `AthleteAuthRepository.get_email_auth_by_normalized_email("User@Example.com")`, finds the auth record
- Given all existing auth tests pass after refactoring (no import errors, no behavioral change)

### Documentation
- Given `event-topology.md` contains "Event Firing Timing Clarification" section
- Given section explains both `[after_commit]` and `[uncommitted]` labels follow the transactional outbox pattern

### Service Comments
- Given `ActivityIngestionService.ingest()` has a comment before the event publication referencing the outbox pattern
- Given `ActivityIngestionService.ingest_async()` has a comment before the event publication referencing the outbox pattern

### No Regressions
- Given no new Alembic migrations generated (`alembic check` passes)
- Given all imports in `app/services/__init__.py` resolve correctly
- Given `app/utils/` is a proper Python package (has `__init__.py`)
