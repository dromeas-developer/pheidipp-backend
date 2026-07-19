# Test Mocking Contract — Pheidipp Backend

Single source of truth for test mocking boundaries and canonical fixtures.
All generated tests MUST conform to this contract.

This document is the **contract**: layer boundaries, the canonical-fixtures
table, the Known Anti-Patterns table (one line per pattern), and the Change
Log (one line per change). Every pattern row in the tables below points to
the corresponding long-form lesson in `tests/README.md` "Dated Lessons" — the
README is the canonical home for symptom, root cause, code blocks, and
meta-rules. Do not duplicate long-form content here.

---

## Layer Boundaries

| Layer | Directory | What is Mocked | What is Real | Async-Session Notes |
|-------|-----------|----------------|--------------|---------------------|
| Unit | `tests/unit/` | External services (email, payment, OpenAI), repository interfaces, service dependencies | Pure function logic, dataclass/datetime operations | Use `AsyncMock` for all mocked async methods; `MagicMock` for sync. Never use real DB connections. |
| Integration | `tests/integration/` | External services (email, payment, third-party APIs), event publisher | Database (real test DB), real repository/ORM, internal service layer | All DB interactions are async. Use `AsyncSession` fixtures that auto-rollback. See README.md "Async session teardown fires `MissingGreenlet` when the pool defers close" for the `NullPool` requirement. Never mock `AsyncSession` methods that will be awaited. |
| API | `tests/api/` | None (fully integrated) | FastAPI app, real DB, real services | HTTP client is `httpx.AsyncClient`. Use `base_url="http://testserver/api/v1"` to normalize path resolution. |
| Behaviour | `tests/behaviour/` | None (fully integrated) | End-to-end flow including DB, real services, real event publishing | Same as API layer. Tests full user journeys. Use real transactions. |
| Release | `tests/release/` | None (promoted tests) | Same as behaviour layer, but these are canonical copies of passing tests | Tests live here after promotion; same mocking rules as behaviour. |

---

## Canonical Fixtures

Every fixture below is the canonical one. New tests MUST reuse these rather than
re-implementing them inline. If a new helper is created, add a row here the
moment it is introduced.

| Name | Location | Scope | Purpose |
|------|----------|-------|---------|
| `db_session` | `tests/conftest.py:562` | function | `AsyncSession` with auto-rollback and post-test truncation. Use for all DB tests. |
| `test_engine` | `tests/conftest.py:380` | function | `AsyncEngine` for each test function (avoids loop errors). |
| `test_session_local` | `tests/conftest.py:399` | function | `async_sessionmaker[AsyncSession]` bound to `test_engine`. |
| `client` | `tests/conftest.py:658` | function | `httpx.AsyncClient` wired to FastAPI app with `db_session` override. |
| `password_hasher` | `tests/conftest.py:719` | function | Argon2 `PasswordHasher` instance for hashing and verification. |
| `token_service` | `tests/conftest.py:724` | function | `TokenService` for issuing and verifying JWTs. |
| `cap_auth_logs` | `tests/conftest.py:745` | function | Log-capture context manager for asserting on auth-layer log records. |
| `find_record` | `tests/conftest.py:768` | function | Helper to locate a log record by event name in captured records. |
| `json_payload` | `tests/conftest.py:776` | function | Helper to extract the JSON payload from a `logging.LogRecord`. |
| `make_register_payload` | `tests/conftest.py:707` | function | Builder for the standard register HTTP request body. |
| `make_login_payload` | `tests/conftest.py:713` | function | Builder for the standard login HTTP request body. |
| `make_athlete` | `tests/utils/factories.py:22` | function | Async factory for an `Athlete` row (commits). |
| `make_auth` | `tests/utils/factories.py:35` | function | Async factory for an `AthleteAuth` row paired with an `athlete_id` (commits). |
| `make_activity` | `tests/utils/factories.py:53` | function | Async factory for an `Activity` row (commits). Uses `ActivitySource.MANUAL_UPLOAD` and `SportType.RUNNING` by default. |
| `make_refresh_token` | `tests/utils/factories.py:108` | function | Async factory for a `RefreshToken` row (commits). |
| `db_columns` | `tests/utils/schema_helpers.py:37` | function | DB schema introspection: list columns of a table (uses a sync psycopg2 engine). |
| `db_unique_constraints` | `tests/utils/schema_helpers.py:42` | function | DB schema introspection: list unique constraints of a table. |
| `db_check_constraints` | `tests/utils/schema_helpers.py:47` | function | DB schema introspection: list check constraints of a table. |
| `db_indexes` | `tests/utils/schema_helpers.py:52` | function | DB schema introspection: list indexes of a table. |
| `db_foreign_keys` | `tests/utils/schema_helpers.py:57` | function | DB schema introspection: list foreign keys of a table. |
| `get_sync_database_url` | `tests/utils/schema_helpers.py:13` | function | Convert the asyncpg test URL to a psycopg2 URL for sync schema inspection. |
| `get_columns` | `tests/utils/model_helpers.py:13` | function | ORM model introspection: dict of columns (no DB required). |
| `get_indexes` | `tests/utils/model_helpers.py:29` | function | ORM model introspection: dict of indexes. |
| `get_check_constraints` | `tests/utils/model_helpers.py:38` | function | ORM model introspection: list of `CheckConstraint` objects. |
| `get_unique_constraints` | `tests/utils/model_helpers.py:44` | function | ORM model introspection: list of `UniqueConstraint` objects. |
| `get_foreign_keys_referencing` | `tests/utils/model_helpers.py:50` | function | ORM model introspection: list of FKs that reference the given table. |
| `get_check_text` | `tests/utils/model_helpers.py:60` | function | ORM model introspection: extract the source expression of a `CheckConstraint`. |
| `get_server_default_text` | `tests/utils/model_helpers.py:66` | function | ORM model introspection: extract the server-default text of a column. |
| `get_enum_values` | `tests/utils/model_helpers.py:95` | function | ORM model introspection: list the permitted values of an enum-typed column. |
| `assert_no_secrets_in_text` | `tests/utils/assertions.py:15` | function | Assert no secret field (`hashed_password`, `token_hash`, `provider_tokens`, `provider_user_id`, `password`) appears in a text payload. |
| `assert_no_secrets_in_logs` | `tests/utils/assertions.py:22` | function | Assert no secret field appears in any captured log record. |
| `bearer_header` | `tests/utils/http_helpers.py:16` | function | Build the `{"Authorization": "Bearer <token>"}` header for behaviour tests. |
| `http_register` | `tests/utils/http_helpers.py:21` | function | Run the standard register HTTP call against an `AsyncClient`; returns `(athlete_id, access_token)`. |
| `mock_activity` (inline) | tests build their own | function | `MagicMock(spec=Activity)` with `planned_session_id=None` and `sport_type=SportType.RUNNING` set explicitly. Used in 26+ unit tests. See README.md "Variable name `mock` must not be reused for `ParsedFitData`" (2026-07-09) for the naming convention. |

---

## Known Anti-Patterns

One-line summaries. Full details (symptom, root cause, code blocks, meta-rules)
in `tests/README.md` "Dated Lessons" — the H3 title in the README matches the
`Reference` column below.

| Pattern | Reference |
|---------|-----------|
| `patch("openai.AsyncOpenAI")` when `AsyncOpenAI` imported directly | README.md: "Patch target must match import style in post_workout_agent" (2026-07-01) |
| `mock_activity.planned_session_id` unset auto-creates truthy MagicMock | README.md: "planned_session_id must be explicitly set to None in post_workout_agent tests" (2026-07-01) |
| `mock_repo.update` asserted when code calls `update_load_scores` | README.md: "Method name mismatch: update vs update_load_scores" (2026-07-01) |
| `session.flush()` with `MagicMock` instead of `AsyncMock` | README.md: "Common Pitfalls" → `expire()` section (top-level, not a dated lesson) |
| Schema inspection with `sync_session.connection()` | README.md: "Schema Inspection in Async Tests" section (top-level, not a dated lesson) |
| Tests asserting JWT access token uniqueness | README.md: "Test Patterns — JWT Token Uniqueness" section (top-level, not a dated lesson) |
| Mocking `session.execute()` when implementation uses repository methods | README.md: "Repository mocking requires scalar_one_or_none() not first()" (2026-07-07) |
| Omitting `sport_type` in Activity factory after sport-type gate implementation | README.md: "sport_type field must be set in Activity factory for calibration eligibility tests" (2026-07-07) |
| `start_time=None` in `ParsedFitData` test fixtures (production reads the field unconditionally) | README.md: "Test fixtures must populate every field the production code reads unconditionally" (2026-07-09) |
| Strict `==` equality on values produced by Savitzky-Golay / EMA / FFT / rolling-median filters | README.md: "Use `pytest.approx` for numerically-filtered samples" (2026-07-09) |
| Test data designed for a downstream gate but rejected by an earlier gate (e.g. short-stream vs null-fraction) | README.md: "Test data must clear every gate in the chain before the one under test" (2026-07-09) |
| Reusing the variable name `mock` for a `ParsedFitData` when the helper takes both a `MagicMock` and a domain object | README.md: "Variable name `mock` must not be reused for `ParsedFitData`" (2026-07-09) |
| `WeeklyPlan(athlete_id=...)` / `PlannedSession(athlete_id=...)` in fixture helpers — those columns do not exist on the models | README.md: "Test fixture helpers must match the FK chain of the production models" (2026-07-11) |
| Asserting a post-cascade column value without `expire_all()` between the cascade commit and the post-cascade SELECT | README.md: "`ON DELETE SET NULL` cascade tests must `expire_all()` before re-reading the cascaded row" (2026-07-11) |
| Accessing an attribute of an in-memory instance AFTER `expire_all()` (e.g. `measurement.id` in a WHERE clause) — triggers async lazy load outside the greenlet | README.md: "`expire_all()` + async lazy load on captured scalar — capture scalars BEFORE `expire_all()`" (2026-07-11) |
| Calling a fixture helper that builds a parent chain (e.g. `_create_planned_session()`) multiple times for the same athlete | README.md: "Multi-call `_create_planned_session()` creates duplicate active TrainingGoals — share the parent chain" (2026-07-11) |
| Bare `create_async_engine(url)` in `conftest.py` (no `poolclass=NullPool`) | README.md: "Async session teardown fires `MissingGreenlet` when the pool defers close — `NullPool` is the fix" (2026-07-11) |
| Post-cascade SELECT without `.execution_options(populate_existing=True)` — identity map returns the expired instance | README.md: "`expire_all()` + identity-map return — add `.execution_options(populate_existing=True)` to the post-cascade SELECT" (2026-07-11) |
| Test data with max deviation exactly equal to a strict-greater-than threshold (e.g. `[140, 145, 150]` against `> 5.0`) | README.md: "Test data for a strict-greater-than threshold must exceed the threshold by a clear margin" (2026-07-11) |
| End-to-end `alembic downgrade` test (becomes stale once later sub-phases build on top of the migration) | README.md: "End-to-end `alembic downgrade` tests become stale once later sub-phases build on top of the migration" (2026-07-11) |
| Post-commit SELECT on a JSONB-mutated row using `.scalar_one()` — identity map returns the pre-update instance | README.md: "Post-commit JSONB reads must use `.scalars().all()[0]`, not `.scalar_one()`" (2026-07-13) |
| `str(enum_member)` for `class Foo(str, Enum)` — returns `'ClassName.MEMBER_NAME'`, not `.value` | README.md: "`str(enum_member)` is NOT the `.value` for `class Foo(str, Enum)` — use `source.value`" (2026-07-13) |
| Test helper defaulting `activity_id=uuid.uuid4()` for a column with a FK to `activities.id` | README.md: "`_observation()` helper default `activity_id=uuid.uuid4()` violates the FK chain" (2026-07-13) |
| Behaviour tests calling `http_register` then a service that requires an `AthletePhysiology` row | README.md: "`http_register` does not create `AthletePhysiology` — behaviour tests must insert it explicitly" (2026-07-13) |
| Test fixtures with default `last_observation_date` causing 45-day decay when assertions assume same-day math | README.md: "Test fixtures with default `last_observation_date` cause 45-day decay when assertions assume same-day" (2026-07-13) |
| Asserting an `onupdate=` hook fires on a no-op `flush()` | README.md: "`onupdate=` hook fires only when a column is mutated — not on a no-op flush" (2026-07-13) |
| Integration `_state()` helper default date (`"2026-05-01"`) introducing a 45-day gap from sibling `_observation()` helper | README.md: "Integration `_state()` helper default date causes 23 failures when assertions assume same-day math" (2026-07-14) |
| Asserting a sequence of intermediate confidence transitions in a single `apply_observations` call | README.md: "`apply_observations` batch transition is `(pre_call_level, post_call_level)`, not per-observation transitions" (2026-07-14) |
| `flush()`-only fixture rows that get rolled back along with the service call's modifications | README.md: "Rollback tests must commit fixture rows in their own transaction — `flush()` does not survive `rollback()`" (2026-07-14) |
| Behaviour tests asserting on a posterior shift against an empty `AthletePhysiology` row | README.md: "Behaviour tests must pre-populate `AthletePhysiology` when asserting on a posterior shift — bootstrap suppresses shift detection" (2026-07-14) |
| Integration tests asserting linear `prior_weight` accumulation with multi-day `measurement_date` | README.md: "Integration tests asserting linear `prior_weight` accumulation with multi-day `measurement_date` fail due to 42-day decay" (2026-07-14, pass 2) |
| Loop pattern asserting `from_level == "low"` on the Nth `apply_observations` call for a high-weight source | README.md: "Loop pattern cannot observe `from_level == \"low\"` on the Nth call when the (N-1)th call already crossed MEDIUM/HIGH" (2026-07-14, pass 2) |
| Accessing an ORM attribute (e.g. `fresh.lt2["hr"]["value"]`) on a freshly-loaded instance AFTER `db_session.rollback()` | README.md: "Post-rollback ORM attribute access triggers `MissingGreenlet` — use column-level SELECT for JSONB reads" (2026-07-14, pass 2) |
| Accessing an ORM attribute (e.g. `athlete.id`, `token.token_hash`) in a WHERE clause AFTER `db_session.rollback()` | README.md: "Post-rollback PK access in WHERE clauses triggers `MissingGreenlet` — capture the PK before `rollback()`" (2026-07-14, pass 3) |
| Mocked `Repository.insert()` returning the same object by identity but without simulating the database's PK assignment | README.md: "Mocked `Repository.insert()` must simulate database PK assignment — set `state.id = uuid.uuid4()` in the `side_effect`" (2026-07-19) |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-01 | Initial seeding from README lessons and DevOps incident #phase-1-6-7-8-p1 | p-test-architect |
| 2026-07-07 | Added `scalar_one_or_none` anti-pattern; documented repository mocking strategy; added `sport_type` factory requirement | p-test-architect |
| 2026-07-09 | Added fixture field-set rule, `pytest.approx` for filtered samples, gate-ordering data design, and mock-variable shadowing (Phase-2.2-P2 RR-deviation-filter-remediation) | p-test-architect |
| 2026-07-11 | Added fixture FK-chain rule, post-cascade `expire_all` rule, and `NullPool` conftest rule (Phase-2.3-P1 threshold-detection) | p-test-architect |
| 2026-07-11 | Added `expire_all()` + captured-scalar rule and multi-call `_create_planned_session()` parent-chain rule (Phase-2.3-P1, run 2) | p-test-architect |
| 2026-07-11 | Added `populate_existing=True` post-cascade SELECT rule and strict-greater-than threshold test-data rule (Phase-2.3-P1, run 3) | p-test-architect |
| 2026-07-11 | Added end-to-end alembic downgrade staleness rule; deleted the test that asserted a stale property | p-test-architect |
| 2026-07-13 | Added str-enum `.value` rule, FK-helper default rule, `http_register` topology rule, date-default fixture rule, and `onupdate=` no-op rule (Phase-2.3-P2 physiology-update, 51 failures: 49 fixed here, 2 routed to p-coder) | p-test-architect |
| 2026-07-14 | Added integration date-default rule, batch transition rule, rollback fixture-isolation rule, and behaviour pre-population rule (Phase-2.3-P2 test pack re-run, 23 failures, all fixed here) | p-test-architect |
| 2026-07-14 | Added integration multi-day accumulation rule, loop `from_level` rule, and post-rollback column-level SELECT rule (Phase-2.3-P2 test pack re-run, pass 2, 8 failures: 7 fixed here, 1 fix) | p-test-architect |
| 2026-07-14 | Added post-rollback PK access rule (Phase-2.3-P2 test pack re-run, pass 3, 1 failure fixed here) | p-test-architect |
| 2026-07-19 | Added mocked-insert PK simulation rule (oneoff-unitary-validation re-analysis, 3 test-side failures fixed in 3 files). The `StrEnum.__eq__` value-equality lesson is a test-expectation rule that lives in README only — it does not cross a mocking boundary, so it is NOT added to the Known Anti-Patterns table above | p-test-architect |
| 2026-07-19 | Refactored contract for scannability: tightened the `Async-Session Notes` column with README cross-references, expanded the Canonical Fixtures table to 34 entries covering every `tests/conftest.py` and `tests/utils/*.py` helper, replaced the stale `mock_activity` placeholder with the actual inline `MagicMock(spec=Activity)` convention, and shortened every Known Anti-Patterns row and Change Log entry to a one-line summary that points to the README's H3 title | p-test-architect |
