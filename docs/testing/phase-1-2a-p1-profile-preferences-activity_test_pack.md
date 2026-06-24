# Test Pack: Phase-1.2a — Profile, Preferences, Activity Schema

Plan: `docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md`

## Summary

Phase-1.2a is a **schema-only** extension of Phase-1.1. It adds the full
``AthleteProfile`` column set (preserving Phase-1.1 columns), introduces
two new tables (``athlete_preferences``, ``activities``), and registers
the closed ontologies required by the architecture contract.

This test pack covers every documented invariant at three layers:

1. **Declarative ORM** — pure-Python assertions on the SQLAlchemy
   mapper (no DB).
2. **DB-enforced** — ``SQLAlchemy Inspector`` introspection of the live
   Postgres test DB plus INSERT/UNIQUE/CHECK exercises.
3. **Migration** — sub-process `alembic upgrade head` and
   `alembic downgrade -1` against an isolated Postgres schema,
   pinned by static structural assertions on the migration file
   (delivery as `e7ffc8764335_phase_1_2a_profile_preferences_activity.py`
   with `down_revision='8265efd46112'`). Missing migration file is a
   hard-fail so a deletion regression cannot go unnoticed.

No API tests and no behaviour tests: Phase-1.2a is explicitly
out-of-scope for endpoints, onboarding writes, FIT upload, load
computation, calibration, and event publication. Those lands on later
sub-phases (Phase-1.2b, Phase-1.3, Phase-1.4, Phase-1.5).

---

## Generated Tests

### Unit tests — pure function / mapper surface checks, no DB

| File | What it pins down |
|---|---|
| `tests/unit/test_enum_values.py` | Closed-ontology membership for ``Sex``, ``ActivitySource`` (4 values), ``DataTier`` (6 values), and 6 supporting enums. Re-export guard for ``app.models.__init__`` so Alembic autogen discovers every ENUM type. |
| `tests/unit/test_infer_data_tier.py` | Pure ``infer_data_tier(hr_source, power_source)`` mapping. Every (Hr × Power) combination gets a name-check against the canonical table. Includes a regression guard that mirrors the architecture pseudocode line-for-line. |
| `tests/unit/test_athlete_profile_columns.py` | Phase-1.1 column preservation (id / athlete_id / date_of_birth / sex / height_cm / updated_at) and the full Phase-1.2a extension surface. Single unified guardrail test asserts the complete column set matches the architecture document. |
| `tests/unit/test_activity_columns.py` | Lean-schema field-by-field assertions for ``Activity``. Parametrised anti-goal tripwire for 13 forbidden columns (``avg_hr``, ``avg_pace``, ``avg_power``, ``avg_cadence``, ``max_*``, ``laps``, ``splits``, ``elevation_gain``, ``calories``, ``training_effect``, ``lap_data``). Partial-unique-index predicate inspected via mapper ``dialect_options``. |

### Integration tests — schema at the DB level

| File | What it pins down |
|---|---|
| `tests/integration/test_athlete_profile_schema.py` | DB-level column set (parametrised over all 17 columns). ``athlete_profiles.athlete_id`` uniqueness preserved at the DB level + duplicate-insert rejection. Phase-1.1 minimal profile still persistable (every new column nullable). Partial-onboarding PATCH exercises (timezone-only, location-only, gap-only, structural_risk_flag=true). ID column type guard guards against a not-drop-and-recreate regression. |
| `tests/integration/test_athlete_preferences_schema.py` | DB-level column set, uniqueness on ``athlete_id``, ``years_structured_training >= 0`` CHECK constraint enforced at the DB layer (including zero-boundary case and negative-value rejection). JSONB ``weekly_schedule`` round-trip preserves ``long_workout``, ``doubles_eligible``, ``available``, ``max_hours``. |
| `tests/integration/test_activity_schema.py` | DB-level column set + 13 forbidden-fields-absent guardrail. Partial-unique dedup index presence + duplicate-rejection (same source) + same-external-id-different-source allowed + manual-entry rows bypass dedup via NULL external_id. Indexes on (athlete_id, activity_date) and (athlete_id, start_time). Manual-entry patterns (fit_file_key=null OK). ``planned_session_id`` is a free-standing UUID with no FK. Cascade delete with parent Athlete. |
| `tests/integration/test_migration_phase_1_2a.py` | Phase-1.2a Alembic migration delivered as `alembic/versions/e7ffc8764335_phase_1_2a_profile_preferences_activity.py` (down_revision=`8265efd46112`). Hard-fail file presence check (no longer skip-if-absent), then static structural assertions pinning the deliverable: 11 `op.add_column` calls on `athlete_profiles` in the documented order, the named CHECK constraint `ck_athlete_preferences_years_structured_training_non_negative`, the partial unique index `uq_activities_athlete_external_source` with `postgresql_where=external_id IS NOT NULL`, downgrade drops new objects only (no `op.create_table` / `op.add_column`), both upgrade AND downgrade bodies checked for forbidden `op.drop_table` calls on every Phase-1.1 table. Functional subprocess tests: `alembic upgrade head` on an isolated Postgres schema returns rc=0; all six Phase-1.1 tables survive; the dedup index appears in `pg_indexes` with the predicate visible; both new tables declare an `athletes(id)` FK with `confdeltype='c'` (CASCADE); `alembic downgrade -1` returns the schema to Phase-1.1 P3 baseline (new tables gone, 11 new columns gone, `athletes` still present). |
| `tests/integration/test_phase_1_1_registration_regression.py` | The full Phase-1.1 registration journey (one Athlete + one email AthleteAuth + one minimal AthleteProfile with every Phase-1.2a column null + one RefreshToken) still works against the Phase-1.2a-extended schema. Duplicate-email path still raises ``DuplicateEmailError``. Round-trip retrieval succeeds. |

---

## Coverage map — every Testing Requirement → at least one test

| Plan testing requirement | Test(s) |
|---|---|
| ``alembic upgrade head`` on a fresh DB succeeds | `test_migration_phase_1_2a.py::TestPhase12aMigrationUpgrades::test_alembic_upgrade_head_succeeds_on_fresh_schema` (fixture raises if rc != 0) |
| ``alembic downgrade -1`` returns schema to Phase-1.1 P3 baseline | `test_migration_phase_1_2a.py::TestPhase12aMigrationDowngrade::test_downgrade_returns_schema_to_phase_1_1_baseline` |
| Migration never drops Phase-1.1 tables (athletes, athlete_profiles, athlete_auths, athlete_refresh_tokens, system_events, system_event_outbox) | `test_migration_phase_1_2a.py::test_migration_never_drops_existing_tables` (static check on upgrade + downgrade) + `TestPhase12aMigrationUpgrades::test_phase_1_1_tables_are_preserved` (post-upgrade DB check) |
| Migration adds the 11 documented columns to athlete_profiles (correct order) | `test_migration_phase_1_2a.py::test_migration_extends_athlete_profiles_via_eleven_add_column` |
| Migration CHECK constraint `years_structured_training >= 0` | `test_migration_phase_1_2a.py::test_migration_adds_years_structured_training_check_constraint` + DB equivalent in `TestPhase12aMigrationUpgrades::test_migration_creates_athlete_preferences_with_check_constraint` |
| Partial unique dedup index with `external_id IS NOT NULL` predicate | `test_migration_phase_1_2a.py::test_migration_creates_partial_unique_dedup_index_on_activities` + DB equivalent in `TestPhase12aMigrationUpgrades::test_migration_partial_dedup_index_in_pg_catalog` |
| FK `athlete_id` on both new tables uses `ON DELETE CASCADE` | `TestPhase12aMigrationUpgrades::test_migration_athlete_fk_cascade_in_pg_catalog` (queries `pg_constraint.confdeltype`) |
| Migration file present and structurally well-formed | `TestPhase12aMigrationFilePresence::test_migration_file_present` + `test_migration_declares_revision_and_down_revision` + `test_down_revision_chains_from_phase_1_1_p3_head` |
| Phase-1.1 registration journey still creates exactly one of each artefact | `test_phase_1_1_registration_regression.py::TestRegistrationJourneyUnchanged` |
| ``athlete_profiles`` carries the full Phase-1.2a column set | `test_athlete_profile_columns.py::TestSchemaCompleteness::test_full_declared_column_set` + `test_athlete_profile_schema.py::TestAthleteProfileDBSchemaColumns` |
| ``athlete_profiles.athlete_id`` remains unique | `test_athlete_profile_columns.py::TestPhase11ColumnsPreserved:: test_athlete_id_is_unique_one_to_one` + `test_athlete_profile_schema.py::TestAthleteProfileUniqueConstraintPreserved` |
| ``athlete_preferences.athlete_id`` is unique | `test_athlete_preferences_schema.py::TestAthletePreferencesUniqueness` |
| ``years_structured_training >= 0`` enforced | `test_athlete_preferences_schema.py::TestYearsStructuredTrainingNonNegative` |
| ``activities`` carries the lean field set | `test_activity_columns.py::TestActivityLeanSchemaFields` + `test_activity_schema.py::TestActivityDBSchemaColumns` |
| No ``avg_hr/avg_pace/avg_power/avg_cadence``/lap-data columns | `test_activity_columns.py::TestActivityLeanSchemaAntiGoals` (parametrised over 13 forbidden fields) + `test_activity_schema.py::TestActivityDBSchemaColumns::test_workout_summary_columns_are_absent` |
| Duplicate ``(athlete_id, external_id, source)`` with non-null external_id rejected | `test_activity_schema.py::TestActivityDedupPartialUniqueIndex:: test_duplicate_non_null_external_id_rejected` |
| ``ActivitySource`` exactly 4 values | `test_enum_values.py::TestActivitySourceContract::test_activity_source_has_exactly_four_values` |
| ``DataTier`` exactly 6 values | `test_enum_values.py::TestDataTierContract::test_data_tier_has_exactly_six_values` |
| Tier inference maps per the canonical table | `test_infer_data_tier.py::TestInferenceAlgorithm` |
| Existing auth & repository tests continue pass | Indirectly guaranteed — the regression test verifies AuthService.register still produces the four-row graph against the Phase-1.2a-extended schema. The Phase-1.1 test suite was not modified. |

---

## How the test infra treats this branch right now

* ``tests/conftest.py::_prepare_database`` (autouse session fixture)
  uses ``Base.metadata.create_all`` to provision the schema. Since the
  Phase-1.2a model classes are registered through
  ``app/models/__init__.py``, ``create_all`` emits the new tables and
  ALTERs ``athlete_profiles`` for integration tests.
* All enums use ``values_callable=lambda x: [e.value for e in x]`` so
  the DB stores the lowercase ``.value`` form. This is critical for
  Phase-1.1 row continuity — the Phase-1.1 migration registered the
  ``sex`` ENUM as ``male/female/not_specified`` rather than
  ``MALE/FEMALE/NOT_SPECIFIED``.
* ``db_session`` commits nothing on its own; service-layer
  ``self.session.commit()`` calls commit but the autouse teardown
  truncates all tables so state never leaks between tests.

---

## Migration tests — current state

The Phase-1.2a Alembic migration has been delivered:

* **Deliverable:** `alembic/versions/e7ffc8764335_phase_1_2a_profile_preferences_activity.py`
* **Down-revision:** `8265efd46112` (Phase-1.1 P3 head).
* **Upgrade:** `op.create_table('activities')`, `op.create_table('athlete_preferences')`,
  11 `op.add_column` calls on `athlete_profiles`, 3 `op.create_index`
  statements (two non-unique on (athlete_id, activity_date) and
  (athlete_id, start_time), one PARTIAL UNIQUE on
  (athlete_id, external_id, source) WHERE external_id IS NOT NULL),
  one `sa.CheckConstraint('years_structured_training >= 0', ...)`,
  `op.drop_table(*)` in the down direction only.
* **Downgrade:** symmetric to upgrade — drops the new tables, drops
  the new indexes, drops the 11 new columns from `athlete_profiles`,
  adds nothing.

The migration tests now operate in **enforce mode** (no `pytest.skip`).
Missing migration file is a hard-fail — `TestPhase12aMigrationFilePresence
::test_migration_file_present` raises an explicit assertion with the
expected path so a deletion regression cannot go unnoticed as a
green-skipped test.

A first-time `alembic upgrade head` against an isolated Postgres schema
is expected to return rc=0 with all six Phase-1.1 tables still present
and the new tables / columns added. Both downgrade-and-upgrade paths
are functional subprocess tests; failure modes below.

| Failure mode | Test that catches it |
|---|---|
| `down_revision` forked from earlier revision | `test_migration_phase_1_2a.py::test_down_revision_chains_from_phase_1_1_p3_head` |
| `op.drop_table` slipped into `upgrade()` on any Phase-1.1 table | `test_migration_phase_1_2a.py::test_migration_never_drops_existing_tables` |
| `op.drop_table` slipped into `downgrade()` on any Phase-1.1 table (defence-in-depth) | same — checks both function bodies |
| `athlete_preferences` not created | `test_migration_phase_1_2a.py::test_migration_creates_athlete_preferences_and_activities` |
| `activities` table not created | `test_migration_phase_1_2a.py::test_migration_creates_athlete_preferences_and_activities` |
| Wrong number / wrong order of `op.add_column` on `athlete_profiles` | `test_migration_phase_1_2a.py::test_migration_extends_athlete_profiles_via_eleven_add_column` |
| Years-Structured-Training CHECK name typo or missing | `test_migration_phase_1_2a.py::test_migration_adds_years_structured_training_check_constraint` |
| Partial dedup index predicate drifted (e.g. `external_id = NULL`) | `test_migration_phase_1_2a.py::test_migration_creates_partial_unique_dedup_index_on_activities` |
| Downgrade accidentally creates tables/columns | `test_migration_phase_1_2a.py::test_downgrade_drops_new_objects_only` |
| Upgrade-head blunders on empty schema | `tests/integration/test_migration_phase_1_2a.py::TestPhase12aMigrationUpgrades::test_alembic_upgrade_head_succeeds_on_fresh_schema` |
| Phase-1.1 tables silently dropped during upgrade | `TestPhase12aMigrationUpgrades::test_phase_1_1_tables_are_preserved` (`athletes`, `athlete_profiles`, `athlete_auths`, `athlete_refresh_tokens`, `system_events`, `system_event_outbox`) |
| Partial dedup index predicate not visible at the DB layer | `TestPhase12aMigrationUpgrades::test_migration_partial_dedup_index_in_pg_catalog` (queries `pg_indexes` directly) |
| `athlete_id` FK missing `ON DELETE CASCADE` | `TestPhase12aMigrationUpgrades::test_migration_athlete_fk_cascade_in_pg_catalog` (queries `pg_constraint` directly — name-independent) |
| Downgrade doesn't fully reverse the migration | `TestPhase12aMigrationDowngrade::test_downgrade_returns_schema_to_phase_1_1_baseline` (subprocess `alembic downgrade -1` against isolated schema, asserts new tables and 11 new columns are gone, `athletes` survives) |

### Subprocess driver

The migration tests run `alembic` as a subprocess so they can:

1. Fork a fresh interpreter — no event-loop collision with the
   per-test `db_session` fixture.
2. Override `DATABASE_URL` via subprocess env, which guarantees the
   project's `.env` (pointing at the dev DB) cannot leak in.
3. Use `cwd=REPO_ROOT` so `alembic.ini`'s `prepend_sys_path = .`
   resolves to the repo, putting `app/` on `sys.path` — required for
   `from app.db.base import Base` and `import app.models` in
   `alembic/env.py`.
4. Pin the connection to a random per-test `phase_1_2a_test_<uuid>`
   schema via `?options=-c search_path=…`. The migration lands there
   and is torn down on test exit, regardless of pass / fail.

Note that the isolated-schema approach is purely about test isolation
— it does NOT replace the always-rebuild-via-`Base.metadata.create_all`
habit that the conftest tier uses for the rest of the test suite (see
the next section). The migration tests are checking that the migration
file applies cleanly on a *blank* Postgres database.

---

## Manifest updates

Manifest `tests/test_manifest.yaml` entries added:

* Seven new features (added during the initial generation pass on
  2026-06-19):
  * ``phase-1-2a-enums``
  * ``phase-1-2a-data-tier-inference``
  * ``phase-1-2a-athlete-profile-schema``
  * ``phase-1-2a-athlete-preferences-schema``
  * ``phase-1-2a-activity-schema``
  * ``phase-1-2a-migration``
  * ``phase-1-2a-registration-regression``

### Update after migration delivery (2026-06-19T23:00:00+00:00)

When the coder delivered `e7ffc8764335_phase_1_2a_profile_preferences_activity.py`,
manifest updates flowed as follows for the `phase-1-2a-migration`
feature entry:

* `description` extended: "reversible via downgrade -1".
* `protects` list tightened:
  * Dropped the "tests skip gracefully until file is delivered"
    invariant (the file IS delivered). Added:
  * "alembic downgrade -1 returns schema to Phase-1.1 P3 baseline"
  * "delivered revision equals `e7ffc8764335`"
  * "Migration adds exactly the 11 documented Phase-1.2a columns
    to athlete_profiles, in the documented order"
  * "Migration creates partial unique `uq_activities_athlete_external_source`
    index with predicate `external_id IS NOT NULL`"
  * "Migration declares athlete_id FKs with `ondelete=CASCADE` for
    both new tables (verified via `pg_constraint.confdeltype`)"
  * "Phase-1.1 tables survive the migration"
* `external_services`: previously `[]`, now `["postgres"]` — the
  subprocess tests require a running Postgres to apply / downgrade.
* `coverage.inv`: the two previously `partial` items
  ("`alembic upgrade head` on fresh DB succeeds — skipped until
  delivered" and "Migration chains from Phase-1.1 P3 head") were
  removed from `partial`; 12 new migration-related invariants were
  promoted into `covered`.
* `last_reviewed_at` bumped from `2026-06-19T21:30:00+00:00` to
  `2026-06-19T23:00:00+00:00`.
* A new history entry was prepended documenting the rewrite of
  `tests/integration/test_migration_phase_1_2a.py` (skip-pattern
  retired; static + functional + downgrade tests added; subprocess
  driver fixed: `cwd=REPO_ROOT` for `app/` on `sys.path`; isolated
  schema via `?options=-c search_path=…`).
* `validation.executable` and `validation.passed` remain `false`
  for the migration feature — DevOps still needs to apply the test
  suite once and update them within the same session, since the Test
  Architect does not run subprocess invocations against a real DB.
* `selection.regression` and `selection.release` are still
  unchanged — promotion to those buckets follows the same path
  (DevOps PASS → Test Architect promotion).

### Initial-pass selection-group state (still in effect)

* ``selection.smoke`` now includes the four new unit test files
  (sub-second each, no DB, no migration dependency — the cheapest
  tripwire for enum/contraction/declarative-schema regressions).
* ``selection.feature`` lists every new test file alongside the
  Phase-1.1 set.
* New ``execution_groups``:
  * ``p1-2a-p1-unit`` (smoke-side pure unit tests).
  * ``p1-2a-p1-integration`` (DB-side schema + dedup + constraints).
  * ``p1-2a-p1-migration`` (depends on unit + integration).
  * ``p1-2a-smoke`` (mirrors ``selection.smoke`` for Phase-1.2a).
* ``coverage.inv`` block extended with 16 Phase-1.2a invariants under
  ``covered``, the Phase-1.2a out-of-scope items under ``missing``,
  and (after the migration was delivered) 12 migration-specific
  invariants promoted from `partial` into `covered`.
* ``coverage.events.missing`` extended with the four Phase-1.2a events
  the plan codifies as ``NOT PRODUCED`` / ``NOT CONSUMED``
  (``activity_ingested``, ``activity_calibration_eligible``,
  ``session_completed``, ``onboarding_completed``).
* A new history entry dated 2026-06-19 records the generation with
  counts and a full delta description.

---

## Out of scope — explicit non-coverage

By design, the following are NOT covered by this test pack:

* Profile / preferences / activity API endpoints.
* AthleteProfile onboarding-write service.
* AthletePreferences onboarding-write service.
* FIT upload / object storage ingestion.
* Manual activity entry API / service.
* ``LoadComputationService`` population of
  ``aerobic/neuromuscular/structural`` loads on actual ingested
  sessions.
* ``CalibrationEligibilityService`` population of
  ``calibration_eligible``.
* Onboarding completion gate (``athletes.onboarding_complete =
  true``).
* Data-tier inference at the per-Activity boundary (the pure
  ``infer_data_tier`` helper is wired at the preferences layer; the
  call into the Activity ingestion path is implemented in a later
  sub-phase).

These belong to later sub-phases (Phase-1.2b, Phase-1.3 onward). The
manifest's ``coverage.missing`` block names them explicitly so a future
Test Architect knows they're deferred, not forgotten.

---

## Validation ownership

The Test Architect sets ``validation.implemented = true`` on each new
feature because the test files exist on disk. ``validation.executable``
and ``validation.passed`` remain ``false`` until DevOps runs the suite
within the same session — those fields reflect runtime evidence the
Test Architect does not have. A single DevOps pass that returns 0 on
the new tests flips these to ``true``; the Test Architect decides on
the next execution whether to advance ``status`` from ``generated``
to ``passing`` and to promote tests into ``selection.regression`` /
``selection.release``.

---

## DevOps rerun — Test-Architect fixes (2026-06-20)

The DevOps report `reports/phase-1-2a_devops.md` flagged **76 failures
+ 1 collection error** in the Phase-1.2a test group. The Test
Architect acted on the two clear test-authoring errors and deferred
the third category for follow-up.

### Issue 1 — `tests/unit/test_athlete_profile_columns.py`: `ImportError: cannot import name 'JSONB' from 'sqlalchemy'`

**Root cause.** The file imported `JSONB` from the top-level
`sqlalchemy` namespace. `JSONB` is a Postgres-only dialect type and
lives at `sqlalchemy.dialects.postgresql`. Importing it from the
core namespace raises `ImportError` at pytest collection time, which
silently blocks the entire module — including the 16 downstream
integration assertions in `tests/integration/test_athlete_profile_schema.py`
that share a collection pass.

**Fix.** Split the import: keep `Boolean / Date / DateTime / Integer /
Numeric / String / Enum` from `sqlalchemy`, and import `JSONB` from
`sqlalchemy.dialects.postgresql`. The class identity is preserved
(`isinstance(col.type, JSONB)` still works).

### Issue 2 — `tests/integration/test_migration_phase_1_2a.py`: regex bug in `_migration_function_body()`

**Root cause.** The helper static-parses the migration file to extract
the body of `def upgrade():` / `def downgrade():`. Its regex was
`\s*\(\s*self.*?\)\s*->\s*None:\s*:[^\n]*\n`, which requires a `self`
parameter and a `:` docstring delimiter after the return annotation.
The Alembic `script.py.mako` template emits
`def upgrade() -> None:` — module-level, no `self`, no docstring.
The regex therefore returned the empty body for every structural
assertion: forbidden-drop checks, create_table presence, the
eleven-ADD-COLUMN order, the named CHECK constraint, the partial
dedup index, the downgrade-drops-new-objects-only invariant, etc.
Nine migration tests failed in lockstep with this single bug.

**Fix.** Rewrote the regex to
`\(\s*(?:self)?\s*\)\s*(?:->\s*[^:]+)?:\s*\n`, which:
* Accepts the actual module-level signature (`def upgrade() -> None:`).
* Tolerates an optional `self` parameter for forward-compat with
  hand-rolled class-based migrations.
* Tolerates any return-annotation text (or none).
* Anchors on the trailing `:\n` rather than the spurious `:`
  docstring delimiter.

The body extraction itself (`.*?` until the next `^def ` or EOF) is
unchanged, so the structural assertions see the real upgrade and
downgrade bodies.

### Issue 3 — DEFERRED: schema inspection failures (16 + 12 + 38 tests)

The DevOps report attributes 66 failures across
`test_athlete_profile_schema.py`, `test_athlete_preferences_schema.py`,
and `test_activity_schema.py` to "schema inspection queries failing"
or "tests connecting to the wrong database". The unit failure
`TestActivityTableIndexes::test_dedup_index_partial_predicate_is_external_id_not_null`
in `tests/unit/test_activity_columns.py` is grouped with this
category and was not addressed here.

The DevOps report explicitly logs a clean test-DB upgrade to
`e7ffc8764335`, so the schema is on-disk. The likely root cause is
one of:
* `AsyncSession.sync_session.connection()` not being inside a
  greenlet context that SQLAlchemy expects.
* The `_prepare_database` fixture truncating tables whose names
  weren't discovered via `Base.metadata.sorted_tables` because some
  Phase-1.2a model files aren't transitively imported from
  `app.main`.
* A test-transaction-isolation issue where
  `Inspector.get_columns()` does not see schema-level objects while
  inside an idle transaction.

Each of these requires running pytest under the project's docker
stack to diagnose — a runtime action the Test Architect does not have.
Per the protocol, schema-inspection fixes that may require either
test or fixture rewrites belong to a follow-up Test-Architect cycle,
not bundled with the two author-side import/regex bugs fixed here.

Once the investigation lands, the same `tests/integration/*.py`
files will need updates — likely to switch the inspector target from
`db_session.sync_session.connection()` to a fresh connection bound
to the project's sync engine, plus adding `models` to
`app/main.py`'s import chain so `_prepare_database` discovers the
Phase-1.2a tables.

---

## DevOps rerun (cross-phase) — Test-Architect fixes (2026-06-21)

The DevOps retry report `reports/phase-1-2b_devops.md` (Phase-1.2b
retry that re-ran the previously-failing four tests after round-1
fixes) surfaced **two remaining Phase-1.2a test failures** plus
**one Phase-1.2b collection error**. Although routed to p-coder by
default, all three live in files Test Architect owns (the test
surface); the DevOps report's "Route to p-coder" label is a
fallback attribution, not an authoritative ownership claim. Both
issues are documented here; the Phase-1.2b collection-error issue
is documented under the Phase-1.2b test pack's Remediation Log
(`docs/testing/phase-1-2b-p1-plan-sessions_test_pack.md`).

Note on terminology: the original Phase-1.2a test-author for
`test_activity_schema.py` is the Phase-1.2a plan; the file was
later extended in Phase-1.2b to exercise the new `planned_session_id`
FK linkage behaviour. The `SessionType.EASY` bad reference is on a
code path the Phase-1.2b extension added, which is why this entry
is recorded in this test pack — the file's Test Architect history
covers both phase variants under
`phase-1-2a-activity-schema` (Phase-1.2a origin) and
`phase-1-2b-activity-schema-extension` (Phase-1.2b extension).

### Issue 1 — `tests/integration/test_activity_schema.py::test_planned_session_id_is_nullable_uuid_with_or_without_fk`: `AttributeError: SessionType.EASY`

**Root cause.** At ~L589, the new `PlannedSession` fixture constructed
in Phase-1.2b passes `session_type=SessionType.EASY` where the
canonical production enum (`app/models/enums.py::SessionType`) defines
`EASY_RUN = "easy_run"` and has no `EASY` member. This yielded
`AttributeError: type object 'SessionType' has no attribute 'EASY'`
during collection/run.

The actual DB string value the test cares about is `"easy_run"` (the
enum `.value`); the test asserts FK linkage behaviour
(`activity.planned_session_id == planned_id`, then `is None`), not
the session_type value itself. Any legal `SessionType` member is
semantically equivalent here — `EASY_RUN` matches the intent string
`"Light aerobic opener"` and aligns with the canonical enum and
every other reference in the codebase.

Cross-codebase consistency check (grep across `tests/` and `app/`):

* `SessionType.EASY_RUN` (canonical, production enum) — used in
  `test_planned_session_schema.py:150`,
  `test_weekly_plan_schema.py:196`, every `test_enum_values.py`
  parametrize list, every `_norm`/`TODO` column assertion.
* `"easy_run"` (string value) — listed in
  `tests/unit/test_enum_values.py:511`,
  `tests/unit/test_planned_session_columns.py:129`,
  `tests/unit/test_weekly_plan_columns.py:282`.
* `SessionType.EASY` — **only** at the failing L589 site. Single,
  isolated outlier. Confirms the production enum is the source of
  truth and the test had the wrong member.

**Fix.** Single-character change: `SessionType.EASY` →
`SessionType.EASY_RUN` at L589. Enum-string value `"easy_run"`
agrees with the production enum and every consumer. No production
enum change — that would invert the bug and break every other test
caller. No test scope change — the test still asserts the FK-linkage
invariant it was written for.

### Issue 2 — `tests/integration/test_migration_phase_1_2a.py::test_downgrade_returns_schema_to_phase_1_1_baseline`: alembic parent-revision syntax unsupported

**Root cause.** The Phase-1.2b chain extension forced a rewrite of
the downgrade target: `downgrade -1` now reverts only Phase-1.2b
and leaves Phase-1.2a intact, so the test instead targets the
revision preceding `e7ffc8764335` to reach the Phase-1.1 P3
baseline. The original code chose `f"{e7ffc8764335}^"` — Alembic's
**caret parent-of-revision operator**.

Alembic 1.13.1 (the version pinned by this project — also visible
in the DevOps observation) does **not** parse `^` as a parent
operator on the `downgrade` sub-command. `^` only became a
canonical revision-target operator in Alembic 1.14+. Result: a
parser-level error rather than the intended downgrade semantics.

**Fix.** Use the existing `PHASE_1_1_P3_REVISION = "8265efd46112"`
constant (already declared at L42 of the same file) directly as
the downgrade target. This is:

* **Equivalence-preserving.** `8265efd46112` is exactly the parent
  revision of `e7ffc8764335` (the `down_revision` declared on the
  Phase-1.2a migration file), so the `<rev>^` semantics are
  preserved despite the syntax change.
* **Self-documenting.** The constant name (`PHASE_1_1_P3_REVISION`)
  + the inline comment (`parent of {PHASE_1_2A_REVISION}`) carry the
  intent forward without relying on operator knowledge.
* **Alembic-portable.** Bare revision IDs are valid in every
  Alembic version since 0.9; the `^` operator remains useful in
  1.14+ but isn't required for this test.

The error message and the `assert rc_dn == 0` failure path now
reference `PHASE_1_1_P3_REVISION` (with the parent relationship
explained in the f-string), so a future CI regression names the
correct downgrade target instead of an obscure `^` expression.

**Cross-cutting risk: none.** Localised to one downgrade call site.
`_run_alembic_subprocess`, the schema-isolation helper, and the
post-downgrade `inspector.has_table("activities")` /
`inspector.has_table("athlete_preferences")` assertions are all
untouched.

### Test-Architect-level fix in Phase-1.2b (cross-reference)

Issue 3 in the same retry report is the `import pytest` collection
error in `tests/unit/test_training_goal_columns.py`. Handled under
the Phase-1.2b test pack Remediation Log (this file is a Phase-1.2a
document and does not own the Phase-1.2b unit suite).
