# Promotion Decision Record — Phase-1.2a
Date: 2026-06-20
Plan: `docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md`
DevOps report: `reports/phase-1-2a_devops.md`
Validator report: `docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity_validation.md`
Manifest: `tests/test_manifest.yaml`
Effective manifest timestamp: `last_reviewed_at: 2026-06-20T16:30:00+00:00`

## Outcome: PROMOTE — all 7 phase-1.2a features

| # | Feature id | Before | After |
|---|---|---|---|
| 1 | `phase-1-2a-enums` | `generated` | `promoted` |
| 2 | `phase-1-2a-data-tier-inference` | `generated` | `promoted` |
| 3 | `phase-1-2a-athlete-profile-schema` | `generated` | `promoted` |
| 4 | `phase-1-2a-athlete-preferences-schema` | `generated` | `promoted` |
| 5 | `phase-1-2a-activity-schema` | `generated` | `promoted` |
| 6 | `phase-1-2a-migration` | `generated` | `promoted` |
| 7 | `phase-1-2a-registration-regression` | `generated` | `promoted` |

All seven entries now carry `validation.implemented = true`,
`validation.executable = true`, `validation.passed = true`.

## Selection group changes

`selection.regression` and `selection.release` each grew by 9 paths:

| Path | Added |
|---|---|
| `tests/unit/test_enum_values.py` | ✅ |
| `tests/unit/test_infer_data_tier.py` | ✅ |
| `tests/unit/test_athlete_profile_columns.py` | ✅ |
| `tests/unit/test_activity_columns.py` | ✅ |
| `tests/integration/test_athlete_profile_schema.py` | ✅ |
| `tests/integration/test_athlete_preferences_schema.py` | ✅ |
| `tests/integration/test_activity_schema.py` | ✅ |
| `tests/integration/test_migration_phase_1_2a.py` | ✅ |
| `tests/integration/test_phase_1_1_registration_regression.py` | ✅ |

`selection.smoke` and `selection.feature` were already populated for
phase-1.2a during the test-generation pass and require no changes.

`execution_groups` were already configured for this phase during
generation; no group edits required.

## Evidence reviewed

### DevOps report

* Result: **PASS**.
* Idempotency: previous run was FAIL on import errors — this PASS is a
  fresh, first-green run.
* Execution group ran: `feature`.
* Test totals: **194 passed / 0 failed / 0 skipped**.
* Services: api, db, redis, litellm all healthy.
* Migration delivered: `e7ffc8764335_phase_1_2a_profile_preferences_activity`
  with `down_revision='8265efd46112'`. Already on test DB upgrade head.
* Prod DB upgraded from `8265efd46112` → `e7ffc8764335`, no warnings,
  application rebuilt cleanly.
* Six of the seven phase-1.2a tests files were updated by DevOps within
  the same session (executable + passed set to `true`); the seventh
  (`phase-1-2a-registration-regression`) was already passing from a
  prior session and unaffected by this run.
* All 76 prior failures were test-authoring errors (JSONB import path,
  migration regex, pg_catalog without schema filter, sync session inside
  pytest-asyncio, boolean coercion of SQLAlchemy expression). All fixed
  by DevOps before the run that produced this report.
* A new `tests/README.md` "Schema Inspection in Async Tests" section
  now documents those foot-guns so future test authors do not repeat
  the same 76-failure pattern.

### Validator report

* Result: **PASS WITH MINORS** (HIGH confidence).
* Layer 1 conformance: 7/7 plan steps implemented.
* Layer 2 contract conformance: 8/10 invariants satisfied, two minors.
* No CRITICAL or MAJOR findings.
* Implementation files: 11/11 listed in scope were retrieved.
* Deviations classified as "Acceptable" (inline JSONB structure
  documentation, expanded edge-case coverage).

### Tests written for this phase

Already on disk, referenced by the manifest entries above:

| Layer | File | Tests on disk |
|---|---|---|
| Unit | `tests/unit/test_enum_values.py` | closed-ontology membership |
| Unit | `tests/unit/test_infer_data_tier.py` | HrSource × PowerSource → DataTier |
| Unit | `tests/unit/test_athlete_profile_columns.py` | Phase-1.1 preservation + Phase-1.2a extension |
| Unit | `tests/unit/test_activity_columns.py` | lean schema + 13 forbidden fields |
| Integration | `tests/integration/test_athlete_profile_schema.py` | DB column set, uniqueness, partial onboarding |
| Integration | `tests/integration/test_athlete_preferences_schema.py` | uniqueness, CHECK, JSONB round-trip |
| Integration | `tests/integration/test_activity_schema.py` | lean schema, dedup, indexes, cascade |
| Integration | `tests/integration/test_migration_phase_1_2a.py` | file presence, structural, functional (subprocess), downgrade reversal |
| Integration | `tests/integration/test_phase_1_1_registration_regression.py` | full Phase-1.1 registration journey still works |

## Why I promote despite the two validator minors

Both minors flag database-level enforcement that the plan itself defers
to later sub-phases:

1. **`fit_file_key` required for non-`manual_entry` sources:**
   Validator correctly notes the DB column is nullable; the invariant is
   stated in plan §Invariants but not implemented as a DB constraint.
   This is consistent with implementation Step 1 ("columns are nullable
   so Phase-1.1 registration still works") and with the plan's own
   framing: "this plan only defines the column; the invariant that
   non-manual activities require the raw FIT file to be stored before
   Activity creation belongs to the later ingestion implementation."
   The service-layer enforcement belongs to Phase-1.6 (FIT import).
   Promoting the schema branch now does not pre-empt that work.
2. **`timezone` immutable after creation:** The plan §Invariants states
   immutability but the migration creates the column nullable with no
   immutability trigger. Same reasoning: plan Step 1's nullable-column
   decision is to preserve the Phase-1.1 auth path; service-layer
   enforcement belongs to the onboarding-write sub-phase (Phase-1.3).
   This validator minor explicitly classified the gap as a
   "plan ambiguity, not an implementation error".

Neither minor affects any artefact this test pack verifies (the schema
topology and migration). Both are first-class items to enforce in
their respective downstream sub-phases.

## Risk assessment going to release

| Risk | Direction |
|---|---|
| Schema-only change → blast radius is the DB | bounded |
| Migration reversible: `alembic downgrade -1` verified returning to Phase-1.1 baseline | low risk |
| Phase-1.1 registration journey unaffected (180 prior tests, all green) | low risk |
| All 6 Phase-1.1 tables survive the upgrade and downgrade paths | bounded |
| Phase-1.2b will add `planned_sessions` and a FK on `activities.planned_session_id` | tracked as out-of-scope here, owned by Phase-1.2b |
| The two minors above are service-layer work in Phase-1.3 and Phase-1.6 | tracked as out-of-scope here |

## Forward compatibility — Phase-1.2b hand-off

The current promotion does NOT pre-commit Phase-1.2b. The bits
Phase-1.2b will rely on are present and protected:

* `activities.planned_session_id` is a free-standing nullable UUID.
* No FK to `planned_sessions` exists yet (correctly absent).
* Reversibility verified: a downgrade path exists that drops the
  Phase-1.2a artefacts without disturbing Phase-1.1.
* `phase-1-2a-migration` execution group depends on the schema-level
  unit + integration groups, not on Phase-1.2b.

## Manifest ops performed

1. `last_reviewed_at` bumped from `2026-06-20T12:00:00+00:00` to
   `2026-06-20T16:30:00+00:00`.
2. All seven `validation.{implemented, executable, passed}` triples
   confirmed `true`, then the corresponding `status:` lines flipped
   from `generated` to `promoted`.
3. `selection.regression` and `selection.release` each grew from 11 to
   20 paths with the 9 phase-1.2a test files.
4. `selection.smoke`, `selection.feature`, `execution_groups`,
   `coverage`, and `validation` blocks were re-checked and require no
   further edits with this promotion.
5. A new history entry dated 2026-06-20 was prepended describing this
   review.

## Reviewed-by signature

* Reviewer: Test Architect
* Date: 2026-06-20
* Result: PROMOTE.
* Authority: Test Architect role owns `status` progression and
  `selection` group membership per protocol §Manifest Ownership Rules.

## Next Step

→ Notify Implementation Architect / Implementation Owner that the
  Phase-1.2a schema branch is promoted. Phase-1.2b is unlocked to
  start its plan generation against an unchanged `phase-1-2a-migration`
  baseline.
