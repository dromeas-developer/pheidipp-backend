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

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-01 | Initial seeding from README lessons and DevOps incident #phase-1-6-7-8-p1 | p-test-architect |
| 2026-07-07 | Added scalar_one_or_none anti-pattern; documented repository mocking strategy; added sport_type factory requirement | p-test-architect |
| 2026-07-09 | Added fixture field-set rule, pytest.approx for filtered samples, gate-ordering data design, and mock-variable shadowing — seeded from DevOps incident #phase-2-2-p2-rr-deviation-filter-remediation (Categories A and B) | p-test-architect |
