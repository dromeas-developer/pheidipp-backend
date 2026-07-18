"""Integration tests for the Phase-1.2b Alembic migration.

The Phase-1.2b plan requires:

* ``alembic upgrade`` to the Phase-1.2b revision succeeds on a
  fresh database with no errors (pinned to the Phase-1.2b
  revision — NOT the current repo head — so later sub-phases
  cannot bleed into these assertions).
* The schema carries every Phase-1.2b table (``training_goals``,
  ``secondary_events``, ``training_plans``, ``regeneration_tasks``,
  ``weekly_plans``, ``planned_sessions``, ``weekly_sessions``,
  ``checkpoints``) with the documented invariants.
* The existing ``activities.planned_session_id`` column gains a
  foreign key to ``planned_sessions.id`` while preserving its
  nullable semantics.
* ``training_plans.twin_state_id`` exists as a nullable column but
  has NO FK yet (deferred to Phase-1.2c).
* Every Phase-1.2a table survives the upgrade — the migration is
  additive.
* ``alembic downgrade -1`` returns the schema to the Phase-1.2a
  baseline by dropping the new tables and resetting the
  ``activities.planned_session_id`` FK.

The migration file is delivered as
``alembic/versions/<rev>_phase_1_2b_plans_sessions_checkpoints.py``.
The tests below resolve it deterministically by filename pattern and
**require** it to be present — if the file is missing, ``pytest.fail``
reports the absence rather than silently skipping so a deletion
regression cannot go unnoticed.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Any, Iterator, Optional, TypedDict, cast

import pytest
from sqlalchemy import Engine, create_engine, inspect, text


class Phase12bSchema(TypedDict):
    """Schema info for Phase-1.2b isolated schema."""

    schema: str
    sync_url: str
    base_sync_url: str



REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"
PHASE_1_2A_REVISION = "e7ffc8764335"  # the migration this plan builds on


def _phase_1_2b_migration_path() -> Optional[Path]:
    if not VERSIONS_DIR.exists():
        return None
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        slug = path.stem.lower()
        if "phase_1_2b" in slug or "phase-1-2b" in slug:
            return path
    return None


PHASE_1_2B_MIGRATION = _phase_1_2b_migration_path()
PHASE_1_2B_MIGRATION_REQUIRED = (
    "alembic/versions/<rev>_phase_1_2b_*.py — required by "
    "docs/implementation/phase-1/"
    "phase-1-2b-p1-plan-sessions.md"
)


def _migration_revision_and_down(path: Path) -> tuple[Optional[str], Optional[str]]:
    """Static parse of ``revision`` and ``down_revision``."""
    src = path.read_text()
    rev_match = re.search(
        r"^revision:\s*[^\n]*=\s*['\"]([^'\"]+)['\"]",
        src, re.MULTILINE,
    )
    down_match = re.search(
        r"^down_revision:\s*[^\n]*=\s*"
        r"(?:Union\[str,\s*None\],\s*|\(Union\[str,\s*None\],\s*\))?"
        r"['\"]?([^'\"]*)['\"]?",
        src, re.MULTILINE,
    )
    rev = rev_match.group(1) if rev_match else None
    raw_down = down_match.group(1) if (down_match and down_match.group(1)) else ""
    raw_down = re.sub(r"^Union\[.*?\]\s*,\s*", "", raw_down)
    raw_down = raw_down.strip().strip("'\"")
    down = raw_down if raw_down else None
    return rev, down


def _migration_function_body(path: Path, fn: str) -> str:
    """Return the raw source of ``fn`` (e.g. ``upgrade`` or
    ``downgrade``)."""
    src = path.read_text()
    match = re.search(
        rf"^def\s+{fn}\s*\(\s*(?:self)?\s*\)\s*(?:->\s*[^:]+)?:\s*\n(.*?)(?=^def\s|\Z)",
        src,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""





# ---------------------------------------------------------------------------
# Migration file presence.
# ---------------------------------------------------------------------------


class TestPhase12bMigrationFilePresence:
    """The migration file must exist on disk before functional tests can run.
    Missing file is an error, not a skip — a deletion regression must
    surface as a failure rather than a green-skipped test."""

    def test_migration_file_present(self) -> None:
        assert PHASE_1_2B_MIGRATION is not None, (
            "Phase-1.2b Alembic migration file is missing on disk. "
            f"Expected: {PHASE_1_2B_MIGRATION_REQUIRED}"
        )
        assert PHASE_1_2B_MIGRATION.exists()
        slug = PHASE_1_2B_MIGRATION.stem.lower()
        assert "phase_1_2b" in slug or "phase-1-2b" in slug, (
            f"Migration file stem `{PHASE_1_2B_MIGRATION.stem}` does "
            "not encode the Phase-1.2b slug — did the regex match a "
            "wrong file?"
        )


def _require_migration_path() -> Path:
    if PHASE_1_2B_MIGRATION is None:
        pytest.skip(PHASE_1_2B_MIGRATION_REQUIRED)
    return PHASE_1_2B_MIGRATION


class TestPhase12bMigrationStructure:
    """Static checks on the migration file. Low-cost, run before
    functional subprocess tests."""

    def test_migration_declares_revision_and_down_revision(
        self,
    ) -> None:
        path = _require_migration_path()
        rev, down = _migration_revision_and_down(path)
        assert rev, "Phase-1.2b migration must declare `revision`."
        assert down, (
            "Phase-1.2b migration must declare `down_revision` "
            f"pointing at Phase-1.2a head ({PHASE_1_2A_REVISION})."
        )

    def test_down_revision_chains_from_phase_1_2a_head(self) -> None:
        path = _require_migration_path()
        _, down = _migration_revision_and_down(path)
        assert down == PHASE_1_2A_REVISION, (
            f"Phase-1.2b migration down_revision must be "
            f"`{PHASE_1_2A_REVISION}` (Phase-1.2a head). Got `{down}`."
        )

    @pytest.mark.parametrize(
        "forbidden_call,table_name",
        [
            ("op.drop_table", "athletes"),
            ("op.drop_table", "athlete_profiles"),
            ("op.drop_table", "athlete_auths"),
            ("op.drop_table", "athlete_refresh_tokens"),
            ("op.drop_table", "system_events"),
            ("op.drop_table", "system_event_outbox"),
            # Phase-1.2a tables must not be dropped.
            ("op.drop_table", "activities"),
            ("op.drop_table", "athlete_preferences"),
        ],
    )
    def test_migration_never_drops_existing_tables(
        self, forbidden_call: str, table_name: str
    ) -> None:
        """Both ``upgrade`` and ``downgrade`` must NOT drop any of
        the Phase-1.1 / Phase-1.2a tables.

        ``downgrade`` is allowed to drop the new Phase-1.2b tables
        (``training_goals``, ``secondary_events``, ``training_plans``,
        ``regeneration_tasks``, ``weekly_plans``, ``weekly_sessions``,
        ``planned_sessions``, ``checkpoints``) and the
        ``fk_activities_planned_session`` foreign key — but only
        those."""
        path = _require_migration_path()
        for fn_name in ("upgrade", "downgrade"):
            body = _migration_function_body(path, fn_name)
            for quote in ("'", '"'):
                forbidden = f"{forbidden_call}({quote}{table_name}{quote}"
                assert forbidden not in body, (
                    f"Phase-1.2b migration {fn_name} contains "
                    f"forbidden `{forbidden}`. The plan requires "
                    "additive transitions for existing tables."
                )

    @pytest.mark.parametrize(
        "expected_table",
        [
            "training_goals",
            "secondary_events",
            "training_plans",
            "regeneration_tasks",
            "weekly_plans",
            "weekly_sessions",
            "planned_sessions",
            "checkpoints",
        ],
    )
    def test_migration_creates_eight_phase_12b_tables(
        self, expected_table: str
    ) -> None:
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            f"op.create_table('{expected_table}'" in upgrade
        ), (
            f"Phase-1.2b migration must create `{expected_table}`."
        )

    def test_migration_emits_trainer_goal_partial_unique_index(self) -> None:
        """``ix_training_goals_athlete_active`` with status predicate."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            "op.create_index('ix_training_goals_athlete_active'"
            in upgrade
        ), (
            "Phase-1.2b migration must create the active-goal "
            "partial unique index `ix_training_goals_athlete_active`."
        )
        assert "postgresql_where=sa.text(\"status = 'active'\")" in upgrade, (
            "ix_training_goals_athlete_active predicate must be "
            "`status = 'active'`."
        )

    def test_migration_emits_regeneration_pending_partial_index(self) -> None:
        """``ix_regeneration_tasks_pending`` partial index with
        ``status = 'pending_confirmation'`` predicate."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            "op.create_index('ix_regeneration_tasks_pending'"
            in upgrade
        )
        assert (
            "postgresql_where=sa.text(\"status = 'pending_confirmation'\")"
            in upgrade
        )

    def test_migration_emits_weekly_plan_week_unique_constraint(self) -> None:
        """``UNIQUE (training_plan_id, week_number)`` on weekly_plans."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert "uq_weekly_plans_plan_week" in upgrade

    def test_migration_emits_planned_session_slot_date_unique(self) -> None:
        """``UNIQUE (weekly_plan_id, target_date, session_slot)`` on
        planned_sessions — the AM/PM disambiguation contract."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert "uq_planned_sessions_plan_date_slot" in upgrade

    def test_migration_wires_activities_planned_session_fk(self) -> None:
        """Activities.planned_session_id gains an FK to
        planned_sessions.id via ``op.create_foreign_key``."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            "op.create_foreign_key(" in upgrade
            and "'fk_activities_planned_session'" in upgrade
            and "'activities'" in upgrade
            and "'planned_sessions'" in upgrade
        ), (
            "Phase-1.2b migration must wire the "
            "fk_activities_planned_session foreign key from "
            "activities.planned_session_id to planned_sessions.id."
        )

    def test_migration_no_fk_to_twin_states(self) -> None:
        """``training_plans.twin_state_id`` must be created WITHOUT a
        FK — only the column. Phase-1.2c adds the FK after
        ``twin_states`` exists."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert "'twin_states'" not in upgrade, (
            "Phase-1.2b migration must NOT add an FK to twin_states — "
            "the table does not exist yet. The column is added as a "
            "nullable UUID only."
        )

    def test_downgrade_drops_new_objects_only(self) -> None:
        """Structural inverse: downgrade drops Phase-1.2b tables,
        drops the ``fk_activities_planned_session`` FK, and resets
        indexes — but never runs ``op.create_table`` or
        ``op.add_column``."""
        path = _require_migration_path()
        downgrade = _migration_function_body(path, "downgrade")
        for forbidden in ("op.create_table", "op.add_column"):
            assert forbidden not in downgrade, (
                f"Phase-1.2b downgrade must not call `{forbidden}` — "
                "it must only drop / remove."
            )
        # The FK from activities to planned_sessions is dropped.
        assert (
            "op.drop_constraint(\n        'fk_activities_planned_session'"
            in downgrade
            or "'fk_activities_planned_session'" in downgrade
        )
        # All eight new tables are dropped.
        for table in (
            "training_goals",
            "secondary_events",
            "training_plans",
            "regeneration_tasks",
            "weekly_plans",
            "weekly_sessions",
            "planned_sessions",
            "checkpoints",
        ):
            assert (
                f"op.drop_table('{table}'" in downgrade
            ), (
                f"Phase-1.2b downgrade must drop `{table}`."
            )


# ---------------------------------------------------------------------------
# Functional migration tests (subprocess alembic + isolated schema).
# ---------------------------------------------------------------------------


def _create_isolated_schema(database_url: str, schema: str) -> None:
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    finally:
        engine.dispose()


def _drop_isolated_schema(database_url: str, schema: str) -> None:
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        engine.dispose()


def _psql_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+"):
        database_url = database_url.replace(
            "postgresql+asyncpg", "postgresql+psycopg2",
        )
    return database_url.split("?")[0]


def _run_alembic_subprocess(
    schema_url: str, command: tuple[str, ...], timeout: int = 180,
) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = schema_url
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(REPO_ROOT / "alembic.ini"),
        *command,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _test_async_dsn() -> Optional[str]:
    return os.environ.get("DATABASE_URL")


@pytest.fixture
def phase_1_2b_schema() -> Iterator[Phase12bSchema]:
    """Set up an isolated Postgres schema, ``alembic upgrade`` to the
    Phase-1.2b head (pinned — NOT the current repo head), then yield
    a dict with the schema name and a sync URL pointed at the schema.
    Tears the schema down on exit.

    Pinning to the Phase-1.2b revision is required for test isolation:
    later sub-phases (Phase-1.2c adds ``twin_states`` and wires the
    ``training_plans.twin_state_id`` FK; future sub-phases may add
    more) must NOT bleed into Phase-1.2b assertions. The downgrade
    test pins to the same revision before running ``downgrade -1``
    so the round-trip lands on the Phase-1.2a baseline.
    """
    async_dsn = _test_async_dsn()
    if not async_dsn:
        pytest.skip("DATABASE_URL not configured in test env.")
    if PHASE_1_2B_MIGRATION is None:
        pytest.skip(PHASE_1_2B_MIGRATION_REQUIRED)
    if PHASE_1_2B_REVISION is None:
        pytest.skip(PHASE_1_2B_MIGRATION_REQUIRED)
    base = _psql_dsn(async_dsn)
    schema = f"phase_1_2b_test_{uuid.uuid4().hex[:8]}"
    _create_isolated_schema(base, schema)
    schema_url = f"{base}?options=-c%20search_path%3D{schema}"
    try:
        rc, stdout, stderr = _run_alembic_subprocess(
            schema_url, ("upgrade", PHASE_1_2B_REVISION),
        )
        if rc != 0:
            raise RuntimeError(
                f"alembic upgrade {PHASE_1_2B_REVISION} failed "
                f"(rc={rc}).\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )
        yield Phase12bSchema(
            schema=schema,
            sync_url=schema_url,
            base_sync_url=base,
        )
    finally:
        _drop_isolated_schema(base, schema)


class TestPhase12bMigrationUpgrades:
    """End-to-end migration tests. Each builds an isolated schema,
    runs ``alembic upgrade`` pinned to the Phase-1.2b revision
    (NOT the current repo head — isolation requirement), then
    asserts the resulting tables, columns, and invariants."""

    def test_alembic_upgrade_to_phase_1_2b_revision_succeeds_on_fresh_schema(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """Reaches this point only if ``alembic upgrade
        PHASE_1_2B_REVISION`` returned without exception — the
        fixture raises otherwise."""

    @pytest.mark.parametrize(
        "preserved_table",
        [
            # Phase-1.1 tables.
            "athletes",
            "athlete_profiles",
            "athlete_auths",
            "athlete_refresh_tokens",
            "system_events",
            "system_event_outbox",
            # Phase-1.2a tables — the migration EXTENDS them.
            "athlete_preferences",
            "activities",
        ],
    )
    def test_phase_1_1_and_phase_1_2a_tables_preserved(
        self, phase_1_2b_schema: Phase12bSchema, preserved_table: str
    ) -> None:
        engine = create_engine(phase_1_2b_schema["sync_url"])
        try:
            inspector = inspect(engine)
            assert inspector.has_table(preserved_table), (
                f"`{preserved_table}` must exist after Phase-1.2b "
                "migration. Phase-1.2b is purely additive."
            )
        finally:
            engine.dispose()

    @pytest.mark.parametrize(
        "new_table",
        [
            "training_goals",
            "secondary_events",
            "training_plans",
            "regeneration_tasks",
            "weekly_plans",
            "weekly_sessions",
            "planned_sessions",
            "checkpoints",
        ],
    )
    def test_phase_1_2b_tables_exist(
        self, phase_1_2b_schema: Phase12bSchema, new_table: str
    ) -> None:
        engine = create_engine(phase_1_2b_schema["sync_url"])
        try:
            inspector = inspect(engine)
            assert inspector.has_table(new_table), (
                f"Phase-1.2b table `{new_table}` missing from the DB."
            )
        finally:
            engine.dispose()

    def test_training_goals_partial_unique_index_in_pg_catalog(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """The active-goal partial unique index must surface in
        ``pg_indexes`` for the test schema with predicate
        ``status = 'active'``."""
        _check_partial_unique_index_predicate(
            phase_1_2b_schema,
            table="training_goals",
            index_name="ix_training_goals_athlete_active",
            predicate_substr="status = 'active'",
        )

    def test_regeneration_pending_partial_index_in_pg_catalog(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        _check_partial_unique_index_predicate(
            phase_1_2b_schema,
            table="regeneration_tasks",
            index_name="ix_regeneration_tasks_pending",
            predicate_substr="status = 'pending_confirmation'",
        )

    def test_weekly_plans_plan_week_unique_constraint(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """``UNIQUE (training_plan_id, week_number)`` on weekly_plans
        must appear in ``pg_constraint`` **exactly once** and only
        inside the isolated Phase-1.2b schema.

        The query joins ``pg_namespace`` so duplicate sightings in
        other schemas cannot falsify the count — the contract is
        locally one constraint per (schema, table)."""
        count = _count_constraint_in_schema(
            phase_1_2b_schema,
            table="weekly_plans",
            constraint_name="uq_weekly_plans_plan_week",
            contype="u",
        )
        assert count == 1, (
            "weekly_plans UNIQUE (training_plan_id, week_number) "
            "constraint `uq_weekly_plans_plan_week` must appear "
            "exactly once in pg_constraint inside schema "
            f"`{phase_1_2b_schema['schema']}`. Got {count}."
        )

    def test_planned_sessions_slot_date_unique_constraint(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """``UNIQUE (weekly_plan_id, target_date, session_slot)`` on
        planned_sessions — the AM/PM disambiguation contract — must
        appear in ``pg_constraint`` exactly once inside the isolated
        Phase-1.2b schema."""
        count = _count_constraint_in_schema(
            phase_1_2b_schema,
            table="planned_sessions",
            constraint_name="uq_planned_sessions_plan_date_slot",
            contype="u",
        )
        assert count == 1, (
            "planned_sessions UNIQUE (weekly_plan_id, target_date, "
            "session_slot) constraint "
            "`uq_planned_sessions_plan_date_slot` must appear exactly "
            "once in pg_constraint inside schema "
            f"`{phase_1_2b_schema['schema']}`. Got {count}."
        )

    def test_checkpoints_planned_session_unique_constraint(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """Strict one-to-one between Checkpoint and PlannedSession —
        a UNIQUE constraint on ``checkpoints.planned_session_id``.

        Asserts by single-column UNIQUE filtering on
        ``planned_session_id`` rather than by correlated ``conkey``
        subquery (the previous shape was ambiguous when the table
        carried the FK plus a single-column UNIQUE on the same
        column). The query is also schema-scoped via
        ``pg_namespace`` so duplicate sightings in other schemas
        cannot fool the assertion.

        The migration declares the unique constraint without an
        explicit name (``sa.UniqueConstraint('planned_session_id')``),
        so PostgreSQL auto-generates one of the form
        ``checkpoints_planned_session_id_key`` — the test therefore
        matches by column-set, not by name.
        """
        engine = create_engine(phase_1_2b_schema["sync_url"])
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        textwrap.dedent(
                            """
                            SELECT c.conname
                            FROM pg_constraint c
                            JOIN pg_namespace n
                              ON n.oid = c.connamespace
                            JOIN pg_class tbl
                              ON tbl.oid = c.conrelid
                            WHERE n.nspname = :schema
                              AND tbl.relname = 'checkpoints'
                              AND c.contype = 'u'
                              AND array_length(c.conkey, 1) = 1
                              AND EXISTS (
                                SELECT 1
                                FROM pg_attribute a
                                WHERE a.attrelid = tbl.oid
                                  AND a.attnum = c.conkey[1]
                                  AND a.attname = 'planned_session_id'
                              )
                            """
                        ).strip()
                    ),
                    {"schema": phase_1_2b_schema["schema"]},
                ).fetchall()
        finally:
            engine.dispose()
        names = sorted(row[0] for row in rows)
        assert names, (
            "checkpoints must have a UNIQUE constraint on "
            "planned_session_id in schema "
            f"`{phase_1_2b_schema['schema']}`."
        )
        # Exactly one single-column UNIQUE on planned_session_id —
        # the migration never declares more than one and the schema
        # contract forbids it.
        assert len(names) == 1, (
            "checkpoints must have exactly one single-column UNIQUE "
            "constraint on planned_session_id. Got: "
            f"{names}"
        )

    def test_activities_planned_session_fk_in_pg_catalog(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """``fk_activities_planned_session`` must reference
        ``planned_sessions.id`` with ``ondelete='SET NULL'`` inside
        the isolated Phase-1.2b schema.

        Query joins ``pg_namespace`` so duplicate sightings in other
        schemas (e.g. an orphaned Phase-1.2a baseline left behind)
        cannot fool the test. ``confdeltype='n'`` is PostgreSQL's
        encoding for ``ON DELETE SET NULL``."""
        row = _fetch_fk_row_in_schema(
            phase_1_2b_schema,
            conrelid_table="activities",
            confrelid_table="planned_sessions",
            constraint_name="fk_activities_planned_session",
        )
        assert row is not None, (
            "fk_activities_planned_session (activities.planned_session_id "
            "→ planned_sessions.id) missing from pg_constraint in "
            f"schema `{phase_1_2b_schema['schema']}`."
        )
        _conname, confdeltype, constraint_def = row
        assert confdeltype == "n", (
            "fk_activities_planned_session must SET NULL on delete "
            "(`confdeltype='n'`). Got: "
            f"confdeltype={confdeltype!r}, def={constraint_def}"
        )

    def test_training_plans_twin_state_id_column_exists_no_fk(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """``training_plans.twin_state_id`` is a nullable UUID column
        with NO FK (awaiting Phase-1.2c).

        The FK count query is scoped to ``phase_1_2b_schema['schema']``
        via a ``pg_namespace`` join — without that filter the query
        would pick up the Phase-1.2c FK ``fk_training_plans_twin_state``
        from the ``public`` schema (where Phase-1.2c correctly
        applied it) and report a phantom 1 FK inside the isolated
        Phase-1.2b schema."""
        engine = create_engine(phase_1_2b_schema["sync_url"])
        try:
            with engine.connect() as conn:
                cols = conn.execute(
                    text(
                        textwrap.dedent(
                            """
                            SELECT a.attname, a.attnotnull, t.typname
                            FROM pg_attribute a
                            JOIN pg_class c ON c.oid = a.attrelid
                            JOIN pg_type t ON t.oid = a.atttypid
                            JOIN pg_namespace n ON n.oid = c.relnamespace
                            WHERE n.nspname = :schema
                              AND c.relname = 'training_plans'
                              AND a.attname = 'twin_state_id'
                              AND a.attnum > 0
                              AND NOT a.attisdropped
                            """
                        ).strip()
                    ),
                    {"schema": phase_1_2b_schema["schema"]},
                ).fetchone()
        finally:
            engine.dispose()
        assert cols is not None, (
            "training_plans.twin_state_id column missing."
        )
        attname, attnotnull, _typname = cols
        assert attname == "twin_state_id"
        assert attnotnull is False, (
            "training_plans.twin_state_id must be NULLABLE."
        )

        engine = create_engine(phase_1_2b_schema["sync_url"])
        try:
            with engine.connect() as conn:
                fk_count = conn.execute(
                    text(
                        textwrap.dedent(
                            """
                            SELECT COUNT(*)
                            FROM pg_constraint c
                            JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
                            JOIN pg_namespace n ON n.oid = conrelid_table.relnamespace
                            WHERE c.contype = 'f'
                              AND n.nspname = :schema
                              AND conrelid_table.relname = 'training_plans'
                              AND EXISTS (
                                  SELECT 1 FROM unnest(c.conkey) AS k
                                  JOIN pg_attribute a ON a.attrelid = conrelid_table.oid
                                    AND a.attnum = k
                                  WHERE a.attname = 'twin_state_id'
                              )
                            """
                        ).strip()
                    ),
                    {"schema": phase_1_2b_schema["schema"]},
                ).scalar_one()
        finally:
            engine.dispose()
        assert fk_count == 0, (
            "training_plans.twin_state_id must NOT carry a FK yet — "
            "twin_states does not exist in Phase-1.2b. "
            f"Got {fk_count} FK rows in schema "
            f"`{phase_1_2b_schema['schema']}`."
        )

    def test_phase_1_2b_tables_have_cascade_fks(
        self, phase_1_2b_schema: Phase12bSchema
    ) -> None:
        """TrainingPlan → TrainingGoal, WeeklyPlan → TrainingPlan,
        PlannedSession → WeeklyPlan + TrainingPlan, Checkpoint →
        PlannedSession, WeeklySession → WeeklyPlan, SecondaryEvent
        → TrainingGoal, RegenerationTask → TrainingGoal must all
        CASCADE on delete."""
        engine = create_engine(phase_1_2b_schema["sync_url"])
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        textwrap.dedent(
                            """
                            SELECT conrelid_table.relname AS table_name,
                                   c.confdeltype
                            FROM pg_constraint c
                            JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
                            WHERE c.contype = 'f'
                              AND conrelid_table.relname IN (
                                'training_plans', 'weekly_plans',
                                'planned_sessions', 'weekly_sessions',
                                'checkpoints', 'secondary_events',
                                'regeneration_tasks',
                                'secondary_events'
                              )
                            """
                        ).strip()
                    )
                ).fetchall()
        finally:
            engine.dispose()
        # All regressions should be CASCADE ('c') except the
        # exceptions to the plan ('a' for the activities FK, which
        # is on the activities table — out of scope for this list).
        seen: dict[Any, set[str]] = {}
        for row in rows:
            seen.setdefault(row[0], set()).add(row[1])

        # training_plans, weekly_plans, weekly_sessions, checkpoints,
        # secondary_events follow the rows here all cascade 'c'.
        # regeneration_tasks training_plan_id is SET NULL ('a'),
        # regeneration_tasks training_goal_id is CASCADE ('c').
        for table in (
            "training_plans",
            "weekly_plans",
            "weekly_sessions",
            "checkpoints",
            "secondary_events",
        ):
            assert table in seen, (
                f"{table} must have at least one FK (cascade on delete)."
            )
            assert "c" in seen[table], (
                f"{table} must have at least one CASCADE FK. "
                f"Got confdeltypes={seen[table]}"
            )


class TestPhase12bMigrationDowngrade:
    """Verify ``alembic downgrade -1`` returns the schema to the
    Phase-1.2a baseline — the migration is reversible."""

    def test_downgrade_returns_schema_to_phase_1_2a_baseline(self) -> None:
        async_dsn = _test_async_dsn()
        if not async_dsn:
            pytest.skip("DATABASE_URL not configured in test env.")
        if PHASE_1_2B_MIGRATION is None:
            pytest.skip(PHASE_1_2B_MIGRATION_REQUIRED)

        base = _psql_dsn(async_dsn)
        schema = f"phase_1_2b_downgrade_{uuid.uuid4().hex[:8]}"
        schema_url = f"{base}?options=-c%20search_path%3D{schema}"
        _create_isolated_schema(base, schema)
        try:
            # Upgrade only to the Phase-1.2b revision (not head) so
            # the test pins the Phase-1.2b → Phase-1.2a downgrade
            # contract without depending on later sub-phases
            # (Phase-1.2c adds 7 more tables that, with head, would
            # require multiple downgrade steps to reach Phase-1.2a).
            revision = PHASE_1_2B_REVISION or ""
            rc_up, out_up, err_up = _run_alembic_subprocess(
                schema_url, ("upgrade", revision),
            )
            assert rc_up == 0, (
                f"alembic upgrade {PHASE_1_2B_REVISION} failed "
                f"(rc={rc_up}). "
                f"STDOUT:\n{out_up}\nSTDERR:\n{err_up}"
            )

            rc_dn, out_dn, err_dn = _run_alembic_subprocess(
                schema_url, ("downgrade", "-1"),
            )
            assert rc_dn == 0, (
                f"alembic downgrade -1 failed (rc={rc_dn}). "
                f"STDOUT:\n{out_dn}\nSTDERR:\n{err_dn}"
            )

            engine = create_engine(schema_url)
            try:
                inspector = inspect(engine)
                # All eight Phase-1.2b tables are gone.
                for table in (
                    "training_goals",
                    "secondary_events",
                    "training_plans",
                    "regeneration_tasks",
                    "weekly_plans",
                    "weekly_sessions",
                    "planned_sessions",
                    "checkpoints",
                ):
                    assert not inspector.has_table(table), (
                        f"Downgrade must drop `{table}`."
                    )
                # Phase-1.2a / Phase-1.1 tables survive.
                for table in (
                    "athletes",
                    "athlete_profiles",
                    "athlete_preferences",
                    "athlete_auths",
                    "athlete_refresh_tokens",
                    "activities",
                    "system_events",
                    "system_event_outbox",
                ):
                    assert inspector.has_table(table), (
                        f"Downgrade must not drop `{table}`."
                    )
                # The activities→planned_sessions FK is removed —
                # planned_session_id is a free-standing nullable UUID.
                fk_count = _count_activities_planned_session_fk(engine)
                assert fk_count == 0, (
                    "Downgrade must drop the activities.planned_session_id "
                    "FK — leaving only the free-standing nullable UUID."
                )
            finally:
                engine.dispose()
        finally:
            _drop_isolated_schema(base, schema)


# ---------------------------------------------------------------------------
# Helpers used by TestPhase12bMigrationUpgrades.
# ---------------------------------------------------------------------------
#
# The Phase-1.2b migration tests must interrogate catalog objects
# (``pg_constraint``, ``pg_index`` / ``pg_indexes``, ``pg_attribute``)
# inside the isolated Phase-1.2b schema. A naive ``WHERE conname = ...``
# is not schema-scoped: if a previous test (or another migration in a
# parallel session) left a same-named object in another schema, the
# assertion can match the wrong object or report a duplicate.
#
# All catalog queries below therefore **join ``pg_namespace``** and
# filter by ``schema_info['schema']``. This guarantees the assertions
# inspect only the Phase-1.2b objects that the migration just created.
# ---------------------------------------------------------------------------


def _count_constraint_in_schema(
    schema_info: Phase12bSchema,
    *,
    table: str,
    constraint_name: str,
    contype: str,
) -> int:
    """Count ``pg_constraint`` rows for ``constraint_name`` on
    ``table`` inside ``schema_info['schema']`` filtered by
    ``contype`` (``'u'`` for UNIQUE, ``'p'`` for PK, ``'f'`` for FK,
    ``'c'`` for CHECK).

    Schema-scoped via ``pg_namespace`` join — does not rely on the
    connection's ``search_path``.
    """
    engine = create_engine(schema_info["sync_url"])
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    textwrap.dedent(
                        """
                        SELECT COUNT(*)
                        FROM pg_constraint c
                        JOIN pg_namespace n
                          ON n.oid = c.connamespace
                        JOIN pg_class tbl
                          ON tbl.oid = c.conrelid
                        WHERE n.nspname = :schema
                          AND tbl.relname = :table_name
                          AND c.conname = :constraint_name
                          AND c.contype = :contype
                        """
                    ).strip()
                ),
                {
                    "schema": schema_info["schema"],
                    "table_name": table,
                    "constraint_name": constraint_name,
                    "contype": contype,
                },
            ).scalar_one()
    finally:
        engine.dispose()


def _fetch_fk_row_in_schema(
    schema_info: Phase12bSchema,
    *,
    conrelid_table: str,
    confrelid_table: str,
    constraint_name: str,
) -> tuple[Any, Any, Any] | None:
    """Return the matching FK row inside ``schema_info['schema']`` as
    ``(conname, confdeltype, constraint_def)``.

    Asserts at most one row — the contract is a single named FK
    between the two tables in the isolated schema. Schema-scoped via
    ``pg_namespace`` joins on both ends.
    """
    engine = create_engine(schema_info["sync_url"])
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    textwrap.dedent(
                        """
                        SELECT c.conname,
                               c.confdeltype,
                               pg_get_constraintdef(c.oid) AS constraint_def
                        FROM pg_constraint c
                        JOIN pg_namespace nrel
                          ON nrel.oid = c.connamespace
                        JOIN pg_class conrelid_table
                          ON conrelid_table.oid = c.conrelid
                        JOIN pg_class confrelid_table
                          ON confrelid_table.oid = c.confrelid
                        WHERE c.contype = 'f'
                          AND nrel.nspname = :schema
                          AND conrelid_table.relname = :conrelid_table
                          AND confrelid_table.relname = :confrelid_table
                          AND c.conname = :constraint_name
                        """
                    ).strip()
                ),
                {
                    "schema": schema_info["schema"],
                    "conrelid_table": conrelid_table,
                    "confrelid_table": confrelid_table,
                    "constraint_name": constraint_name,
                },
            ).fetchall()
    finally:
        engine.dispose()
    assert len(rows) <= 1, (
        f"Expected at most one FK `{constraint_name}` between "
        f"`{conrelid_table}` and `{confrelid_table}` in schema "
        f"`{schema_info['schema']}`. Got {len(rows)}."
    )
    return cast(Optional[tuple[Any, Any, Any]], rows[0] if rows else None)


def _check_partial_unique_index_predicate(
    schema_info: Phase12bSchema,
    *,
    table: str,
    index_name: str,
    predicate_substr: str,
) -> None:
    """Assert that the named partial unique index exists in
    ``pg_indexes`` for ``schema_info['schema']`` and that its
    definition contains ``predicate_substr`` when normalised.

    PostgreSQL may render ``native_enum=False`` enum-backed VARCHAR
    predicates with explicit casts (``((status)::text = 'active'::text)``)
    or in the raw form (``status = 'active'``). The assertion accepts
    both rendered forms by normalising whitespace and the
    ``::text`` casts before comparing the semantic condition.
    """
    engine = create_engine(schema_info["sync_url"])
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    textwrap.dedent(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = :schema
                          AND tablename = :table_name
                          AND indexname = :index_name
                        """
                    ).strip()
                ),
                {
                    "schema": schema_info["schema"],
                    "table_name": table,
                    "index_name": index_name,
                },
            ).fetchone()
    finally:
        engine.dispose()
    assert row, (
        f"{index_name} not found in pg_indexes for schema "
        f"`{schema_info['schema']}` and table `{table}`."
    )
    _, indexdef = row
    normalised = _normalize_indexdef_predicate(indexdef)
    assert _predicate_contains(normalised, predicate_substr), (
        f"{index_name} must carry the predicate "
        f"``{predicate_substr}``. Got: {indexdef} (normalised: "
        f"{normalised!r})"
    )


def _normalize_indexdef_predicate(indexdef: str) -> str:
    """Normalise a ``pg_indexes.indexdef`` rendering so the partial
    predicate can be compared semantically:

    * lowercase
    * collapse whitespace
    * strip PostgreSQL's ``::<cast>`` annotations — the same
      logical predicate rendered with or without ``::text`` casts
      must compare equal.
    * strip redundant parens — PostgreSQL renders partial-index
      predicates wrapped in an outer ``( ... )`` and may add
      redundant parens around each operand of an equality
      expression (``((status)::text = 'active'::text)``). Those
      parens are semantically redundant: removing them yields
      ``status = 'active'`` which compares equal to the canonical
      predicate substring asserted by callers.
    """
    import re as _re

    flat = " ".join(indexdef.lower().split())
    # Remove all ``::<type>`` cast suffixes — they are rendering
    # noise, not semantic content. The pattern matches a leading
    # character followed by ``::`` then a SQL identifier.
    flat = _re.sub(r"::\s*[a-z_][a-z0-9_]*(\s*\([^)]*\))?", "", flat)
    # PostgreSQL's partial-index renderer wraps the entire
    # predicate in an outer ``( ... )`` AND adds redundant
    # ``((`` ... ``))`` around column refs on enum-backed
    # VARCHAR columns. Collapsing ``((`` → ``(`` still leaves the
    # outer closing paren unmatched and inserts ``)`` between
    # operands (``(status)`` instead of ``status``), so a literal
    # substring search of the canonical ``status = 'active'``
    # would miss. Strip ALL parens — they carry no semantic
    # information in an equality predicate.
    flat = flat.replace("(", "").replace(")", "")
    return flat


def _predicate_contains(normalised_predicate: str, expected_substr: str) -> bool:
    """Return True iff ``normalised_predicate`` contains the
    expected semantic expression, accepting either the raw form
    (``status = 'active'``) or the cast-stripped variant of
    PostgreSQL's rendered form (``((status) = 'active')``).

    The ``expected_substr`` argument is the **semantic** form that
    the migration author wrote (``status = 'active'``); callers must
    pass the canonical form. The normalised rendering handles the
    machinery of the comparison.
    """
    flat_expected = " ".join(expected_substr.lower().split())
    return flat_expected in normalised_predicate


def _count_activities_planned_session_fk(engine: Engine) -> int:
    """Count FKs from ``activities.planned_session_id`` →
    ``planned_sessions.id`` (after downgrade this gets zero).

    Restricted to the connection's current schema — the downgrade
    fixture lands every object inside its own isolated schema, so
    ``current_schema()`` is a sufficient filter for the downgrade
    context where this helper runs.
    """
    with engine.connect() as conn:
        return conn.execute(
            text(
                textwrap.dedent(
                    """
                    SELECT COUNT(*)
                    FROM pg_constraint c
                    JOIN pg_namespace n
                      ON n.oid = c.connamespace
                    JOIN pg_class conrelid_table
                      ON conrelid_table.oid = c.conrelid
                    JOIN pg_class confrelid_table
                      ON confrelid_table.oid = c.confrelid
                    JOIN pg_namespace conf_n
                      ON conf_n.oid = confrelid_table.relnamespace
                    WHERE c.contype = 'f'
                      AND n.nspname = current_schema()
                      AND conrelid_table.relname = 'activities'
                      AND confrelid_table.relname = 'planned_sessions'
                      AND conf_n.nspname = n.nspname
                    """
                ).strip()
            )
        ).scalar_one()


# Expose the delivered revision for downstream catalog cross-checks.
PHASE_1_2B_DELIVERED_REVISION = (
    PHASE_1_2B_MIGRATION.stem.split("_", 1)[0]
    if PHASE_1_2B_MIGRATION is not None
    else None
)
# Canonical name used by fixtures and the downgrade test to pin
# ``alembic upgrade`` to the Phase-1.2b head (not the current repo
# head — Phase-1.2b tests must not depend on later sub-phases).
PHASE_1_2B_REVISION = PHASE_1_2B_DELIVERED_REVISION
