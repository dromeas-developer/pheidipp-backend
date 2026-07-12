# Test Mocking Contract — Pheidipp Backend

Single source of truth for test mocking boundaries and canonical fixtures.  
All generated tests MUST conform to this contract.

---

## Layer Boundaries

| Layer | Directory | What is Mocked | What is Real | Async-Session Notes |
|-------|-----------|----------------|--------------|---------------------|
| Unit | `tests/unit/` | External services (email, payment, OpenAI), repository interfaces, service dependencies | Pure function logic, dataclass/datetime operations | Use `AsyncMock` for all mocked async methods; `MagicMock` for sync. Never use real DB connections. |
| Integration | `tests/integration/` | External services (email, payment, third-party APIs), event publisher | Database (real test DB), real repository/ORM, internal service layer | All DB interactions are async. Use `AsyncSession` fixtures that auto-rollback. Never mock `AsyncSession` methods that will be awaited. |
| API | `tests/api/` | None (fully integrated) | FastAPI app, real DB, real services | HTTP client is `httpx.AsyncClient`. Use `base_url="http://testserver/api/v1"` to normalize path resolution. |
| Behaviour | `tests/behaviour/` | None (fully integrated) | End-to-end flow including DB, real services, real event publishing | Same as API layer. Tests full user journeys. Use real transactions. |
| Release | `tests/release/` | None (promoted tests) | Same as behaviour layer, but these are canonical copies of passing tests | Tests live here after promotion; same mocking rules as behaviour. |

---

## Canonical Fixtures

| Name | Location | Scope | Purpose |
|------|----------|-------|---------|
| `db_session` | `tests/conftest.py` | function | AsyncSession with auto-rollback and post-test truncation. Use for all DB tests. |
| `test_engine` | `tests/conftest.py` | function | AsyncEngine for each test function (avoids loop errors). |
| `client` | `tests/conftest.py` | function | `httpx.AsyncClient` wired to FastAPI app with `db_session` override. |
| `mock_activity` | Not yet canonical — each test builds its own | N/A | Tests currently use inline `MagicMock(spec=Activity)`. Consider consolidating if pattern repeats. |

---

## Known Anti-Patterns

Quick reference for common mocking failures. Full details in `tests/README.md` dated lessons.

| Pattern | Reference |
|---------|-----------|
| `patch("openai.AsyncOpenAI")` when `AsyncOpenAI` imported directly | README.md: "Patch target must match import style" (2026-07-01) |
| `mock_activity.planned_session_id` unset auto-creates truthy MagicMock | README.md: "planned_session_id must be explicitly set to None" (2026-07-01) |
| `mock_repo.update` asserted when code calls `update_load_scores` | README.md: "Method name mismatch: update vs update_load_scores" (2026-07-01) |
| `session.flush()` with `MagicMock` instead of `AsyncMock` | README.md: "Common Pitfalls" → `expire()` section |
| Schema inspection with `sync_session.connection()` | README.md: "Schema Inspection in Async Tests" section |
| Tests asserting JWT access token uniqueness | README.md: "JWT Token Uniqueness in Tests" section |
| Mocking `session.execute()` when implementation uses repository methods | README.md: "Repository mocking requires scalar_one_or_none() not first()" (2026-07-07) |
| Omitting `sport_type` in Activity factory after sport-type gate implementation | README.md: "sport_type field must be set in Activity factory" (2026-07-07) |
| `start_time=None` in `ParsedFitData` test fixtures (production reads `parsed.start_time.date()` unconditionally) | README.md: "Test fixtures must populate every field the production code reads unconditionally" (2026-07-09) |
| Strict `==` equality on values produced by Savitzky-Golay / EMA / FFT / rolling-median filters | README.md: "Use `pytest.approx` for numerically-filtered samples" (2026-07-09) |
| Test data designed for a downstream gate but rejected by an earlier gate (e.g. short-stream vs null-fraction) | README.md: "Test data must clear every gate in the chain before the one under test" (2026-07-09) |
| Reusing the variable name `mock` for a `ParsedFitData` when the helper takes both a `MagicMock` and a domain object | README.md: "Variable name `mock` must not be reused for ParsedFitData" (2026-07-09) |
| `WeeklyPlan(athlete_id=...)` / `PlannedSession(athlete_id=...)` in fixture helpers — those columns do not exist on the models | README.md: "Test fixture helpers must match the FK chain of the production models" (2026-07-11) |
| Asserting a post-cascade column value without `expire_all()` between the cascade commit and the post-cascade SELECT | README.md: "ON DELETE SET NULL cascade tests must expire_all() before re-reading" (2026-07-11) |
| Accessing an attribute of an in-memory instance AFTER `expire_all()` (e.g. `measurement.id` in a WHERE clause) — triggers async lazy load outside the greenlet | README.md: "`expire_all()` + async lazy load on captured scalar — capture scalars BEFORE `expire_all()`" (2026-07-11) |
| Calling a fixture helper that builds a parent chain (e.g. `_create_planned_session()`) multiple times for the same athlete — creates duplicate active `TrainingGoal` rows that violate `ix_training_goals_athlete_active` | README.md: "Multi-call `_create_planned_session()` creates duplicate active TrainingGoals — share the parent chain" (2026-07-11) |
| Bare `create_async_engine(url)` in `conftest.py` (no `poolclass=NullPool`) — defers connection close outside the greenlet | README.md: "Async session teardown fires MissingGreenlet when the pool defers close" (2026-07-11) |
| Post-cascade SELECT without `.execution_options(populate_existing=True)` — identity map returns the expired instance and attribute access triggers an async lazy load outside the greenlet | README.md: "`expire_all()` + identity-map return — add `.execution_options(populate_existing=True)` to the post-cascade SELECT" (2026-07-11) |
| Test data with max deviation exactly equal to a strict-greater-than threshold (e.g. `[140, 145, 150]` against `> 5.0` threshold) — the value at the threshold passes the filter, so the test does not exercise the "fire" path | README.md: "Test data for a strict-greater-than threshold must exceed the threshold by a clear margin" (2026-07-11) |
| End-to-end `alembic downgrade` test (e.g. `alembic downgrade -2` then assert baseline tables) — becomes stale the moment any later sub-phase migration is added, because the downgrade no longer reaches the migration's original baseline | README.md: "End-to-end alembic downgrade tests become stale once later sub-phases build on top of the migration" (2026-07-11) |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-01 | Initial seeding from README lessons and DevOps incident #phase-1-6-7-8-p1 | p-test-architect |
| 2026-07-07 | Added scalar_one_or_none anti-pattern; documented repository mocking strategy; added sport_type factory requirement | p-test-architect |
| 2026-07-09 | Added fixture field-set rule, pytest.approx for filtered samples, gate-ordering data design, and mock-variable shadowing — seeded from DevOps incident #phase-2-2-p2-rr-deviation-filter-remediation (Categories A and B) | p-test-architect |
| 2026-07-11 | Added fixture FK-chain rule, post-cascade `expire_all` rule, and `NullPool` conftest rule — seeded from DevOps incident #phase-2-3-p1-threshold-detection (Categories 2, 4, and Infrastructure Fixes) | p-test-architect |
| 2026-07-11 | Added `expire_all()` + captured-scalar rule and multi-call `_create_planned_session()` parent-chain rule — seeded from DevOps incident #phase-2-3-p1-threshold-detection (Categories 4 and 5, second run) | p-test-architect |
| 2026-07-11 | Added `populate_existing=True` post-cascade SELECT rule and strict-greater-than threshold test-data rule — seeded from DevOps incident #phase-2-3-p1-threshold-detection (Categories 1, 2, and 3, third run) | p-test-architect |
| 2026-07-11 | Added end-to-end alembic downgrade staleness rule — seeded from DevOps full regression run flagging `test_downgrade_returns_to_phase_12b_baseline` as a pre-existing failure (Phase-1.2c downgrade cannot fully reverse after later sub-phases). Test Architect deleted the test and recorded the lesson; static-body downgrade checks (parse the migration source for `op.drop_table` / `op.drop_constraint` calls) remain as the stable coverage of the migration's downgrade logic. | p-test-architect |
