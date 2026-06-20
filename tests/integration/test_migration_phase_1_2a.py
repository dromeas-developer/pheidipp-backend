"""Integration tests for the Phase-1.2a Alembic migration.

The Phase-1.2a plan requires:

* ``alembic upgrade head`` succeeds on a fresh database with no errors.
* The resulting schema carries the full Phase-1.2a column set.
* Existing Phase-1.1 schema objects (``athletes``, ``athlete_profiles``,
  ``athlete_auths``, ``athlete_refresh_tokens``, ``system_events``,
  ``system_event_outbox``) remain intact — the migration EXTENDS
  rather than re-creates them.
* The new ``athlete_preferences`` and ``activities`` tables exist with
  every documented invariant (uniqueness, CHECK, partial dedup index,
  cascade delete).

The migration file is delivered as
``alembic/versions/<rev>_phase_1_2a_*.py``. The tests below resolve it
deterministically by filename pattern and **require** it to be present
— if the file is missing, ``pytest.fail`` reports the absence rather
than silently skipping, so a deletion regression cannot go unnoticed.

Reference plan:
docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy import create_engine, inspect, text


REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"
PHASE_1_1_P3_REVISION = "8265efd46112"
PHASE_1_2A_REVISION = "e7ffc8764335"  # the revision the coder delivered


def _phase_1_2a_migration_path() -> Optional[Path]:
    """Locate the Phase-1.2a Alembic file on disk.

    Filename patterns tolerated: contains either ``phase_1_2a`` or
    ``phase-1-2a`` substring. Returns ``None`` only if no candidate
    file exists.
    """
    if not VERSIONS_DIR.exists():
        return None
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        slug = path.stem.lower()
        if "phase_1_2a" in slug or "phase-1-2a" in slug:
            return path
    return None


PHASE_1_2A_MIGRATION = _phase_1_2a_migration_path()
PHASE_1_2A_MIGRATION_REQUIRED = (
    "alembic/versions/<rev>_phase_1_2a_*.py — required by "
    "docs/implementation/phase-1/"
    "phase-1-2a-p1-profile-preferences-activity.md"
)


def _migration_revision_and_down(path: Path) -> tuple[Optional[str], Optional[str]]:
    """Extract ``revision`` and ``down_revision`` declarations from a
    migration file by static parsing. Avoids executing the module so
    type annotations and string types do not need to evaluate.
    """
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
    # Strip optional Union type-annotation noise.
    raw_down = re.sub(r"^Union\[.*?\]\s*,\s*", "", raw_down)
    raw_down = raw_down.strip().strip("'\"")
    down = raw_down if raw_down else None
    return rev, down


def _migration_function_body(path: Path, fn: str) -> str:
    """Return the raw source of ``fn`` (e.g. ``upgrade`` or
    ``downgrade``) for static regex checks.

    Alembic module-level migration functions are declared
    ``def upgrade() -> None:`` / ``def downgrade() -> None:`` per the
    standard ``script.py.mako`` template — there is NO ``self``
    parameter (those are module-level, not method-level). The body
    extraction must therefore allow an empty parameter list. A
    stray ``self`` parameter is still tolerated for forward
    compatibility with hand-rolled class-based migrations.
    """
    src = path.read_text()
    match = re.search(
        rf"^def\s+{fn}\s*\(\s*(?:self)?\s*\)\s*(?:->\s*[^:]+)?:\s*\n(.*?)(?=^def\s|\Z)",
        src,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _migration_columns_added_in_upgrade(path: Path, table: str) -> list[str]:
    """Return the list of column names ``op.add_column('<table>', ...)``
    emissions in the upgrade body, in source order.
    """
    body = _migration_function_body(path, "upgrade")
    pattern = re.compile(
        rf"op\.add_column\(\s*['\"]{re.escape(table)}['\"]\s*"
        r",\s*sa\.Column\(\s*['\"]([^'\"]+)['\"]"
    )
    return pattern.findall(body)


# ---------------------------------------------------------------------------
# Migration file presence
# ---------------------------------------------------------------------------


class TestPhase12aMigrationFilePresence:
    """The migration file must exist on disk before these tests can run.
    Missing file is an error, not a skip — a deletion regression must
    surface as a failure rather than a green-skipped test.
    """

    def test_migration_file_present(self) -> None:
        assert PHASE_1_2A_MIGRATION is not None, (
            "Phase-1.2a Alembic migration file is missing on disk. "
            f"Expected: {PHASE_1_2A_MIGRATION_REQUIRED}"
        )
        assert PHASE_1_2A_MIGRATION.exists()
        slug = PHASE_1_2A_MIGRATION.stem.lower()
        assert "phase_1_2a" in slug or "phase-1-2a" in slug, (
            f"Migration file stem `{PHASE_1_2A_MIGRATION.stem}` does "
            "not encode the Phase-1.2a slug — did the regex match a "
            "wrong file?"
        )


# ---------------------------------------------------------------------------
# Static structural checks on the migration file.
# ---------------------------------------------------------------------------


def _require_migration_path() -> Path:
    """Return the migration path, or skip the test when missing.

    The presence test above is a hard fail; subsequent structure
    tests use this helper to avoid noisy assertions on a missing
    file.
    """
    if PHASE_1_2A_MIGRATION is None:
        pytest.skip(PHASE_1_2A_MIGRATION_REQUIRED)
    return PHASE_1_2A_MIGRATION


class TestPhase12aMigrationStructure:
    """Static checks on the migration file. Low-cost, run before
    functional subprocess tests."""

    def test_migration_declares_revision_and_down_revision(
        self,
    ) -> None:
        path = _require_migration_path()
        rev, down = _migration_revision_and_down(path)
        assert rev, "Phase-1.2a migration must declare `revision`."
        assert down, (
            "Phase-1.2a migration must declare `down_revision` "
            f"pointing at Phase-1.1 P3 head ({PHASE_1_1_P3_REVISION})."
        )

    def test_down_revision_chains_from_phase_1_1_p3_head(self) -> None:
        """The migration must build on Phase-1.1 P3 head. A fork from
        an earlier revision would orphan the
        ``ix_athlete_auths_single_primary`` partial unique index.
        """
        path = _require_migration_path()
        _, down = _migration_revision_and_down(path)
        assert down == PHASE_1_1_P3_REVISION, (
            f"Phase-1.2a migration down_revision must be "
            f"`{PHASE_1_1_P3_REVISION}` (Phase-1.1 P3 head). Got `{down}`."
        )

    def test_migration_never_drops_existing_tables(
        self,
    ) -> None:
        """Defence-in-depth: the plan requires the migration to be
        additive. Both ``upgrade`` and ``downgrade`` must NOT call
        ``op.drop_table`` for any of the six Phase-1.1 tables.
        (Downgrading Phase-1.2a -1 only is allowed to drop the new
        tables ``activities`` and ``athlete_preferences``.)
        """
        path = _require_migration_path()
        for fn_name in ("upgrade", "downgrade"):
            body = _migration_function_body(path, fn_name)
            for forbidden in (
                "op.drop_table('athlete_profiles')",
                'op.drop_table("athlete_profiles")',
                "op.drop_table('athletes')",
                'op.drop_table("athletes")',
                "op.drop_table('athlete_auths')",
                'op.drop_table("athlete_auths")',
                "op.drop_table('athlete_refresh_tokens')",
                'op.drop_table("athlete_refresh_tokens")',
                "op.drop_table('system_events')",
                'op.drop_table("system_events")',
                "op.drop_table('system_event_outbox')",
                'op.drop_table("system_event_outbox")',
            ):
                assert forbidden not in body, (
                    f"Phase-1.2a migration {fn_name} contains forbidden "
                    f"`{forbidden}`. The plan requires additive ALTER / "
                    "CREATE TABLE for new tables only — never drop "
                    "existing tables."
                )

    def test_migration_creates_athlete_preferences_and_activities(
        self,
    ) -> None:
        """The migration must create ``athlete_preferences`` and
        ``activities``.
        """
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert "op.create_table('athlete_preferences'" in upgrade, (
            "Phase-1.2a migration must create `athlete_preferences`."
        )
        assert "op.create_table('activities'" in upgrade, (
            "Phase-1.2a migration must create `activities`."
        )

    def test_migration_extends_athlete_profiles_via_eleven_add_column(
        self,
    ) -> None:
        """``athlete_profiles`` is extended, not re-created. The plan
        exactly adds the 11 documented columns:
            gap_curve_model, weather_response_model, banister_constants,
            cycle_personal_model, location_lat, location_lng, timezone,
            training_window, current_effort_generation,
            structural_risk_flag, objective_thresholds
        """
        path = _require_migration_path()
        cols = _migration_columns_added_in_upgrade(path, "athlete_profiles")
        expected = [
            "gap_curve_model",
            "weather_response_model",
            "banister_constants",
            "cycle_personal_model",
            "location_lat",
            "location_lng",
            "timezone",
            "training_window",
            "current_effort_generation",
            "structural_risk_flag",
            "objective_thresholds",
        ]
        assert cols == expected, (
            f"Phase-1.2a migration must add the exact 11 documented "
            f"columns to `athlete_profiles` in this order. Got {cols}."
        )

    def test_migration_adds_years_structured_training_check_constraint(
        self,
    ) -> None:
        """``years_structured_training >= 0`` is enforced as a named
        CHECK constraint at the DB layer.
        """
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            "ck_athlete_preferences_years_structured_training_non_negative"
            in upgrade
        ), (
            "Phase-1.2a migration must declare the named CHECK "
            "constraint `ck_athlete_preferences_years_structured_training_non_negative`."
        )

    def test_migration_creates_partial_unique_dedup_index_on_activities(
        self,
    ) -> None:
        """The migration must emit the partial unique dedup index
        ``uq_activities_athlete_external_source`` with a
        ``postgresql_where=external_id IS NOT NULL`` predicate.
        """
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            "op.create_index('uq_activities_athlete_external_source'"
            in upgrade
        ), (
            "Phase-1.2a migration must create the partial unique "
            "index `uq_activities_athlete_external_source`."
        )
        assert "postgresql_where=sa.text('external_id IS NOT NULL')" in (
            upgrade
        ), (
            "Partial dedup index must use the predicate "
            "`external_id IS NOT NULL`."
        )

    def test_downgrade_drops_new_objects_only(self) -> None:
        """Sanity check: the downgrade is structurally inverse to
        upgrade — drops the new indexes, drops the new tables,
        drops the new columns from ``athlete_profiles``.
        """
        path = _require_migration_path()
        downgrade = _migration_function_body(path, "downgrade")
        for forbidden in (
            "op.create_table",
            "op.add_column",
        ):
            assert forbidden not in downgrade, (
                f"Phase-1.2a downgrade must not call `{forbidden}` — "
                "it must only drop / remove."
            )
        assert "op.drop_table('activities'" in downgrade
        assert "op.drop_table('athlete_preferences'" in downgrade
        assert (
            "op.drop_index('uq_activities_athlete_external_source'"
            in downgrade
        )


# ---------------------------------------------------------------------------
# Functional migration tests (subprocess alembic + isolated schema).
# ---------------------------------------------------------------------------


def _create_isolated_schema(database_url: str, schema: str) -> None:
    """Create ``schema`` so the subprocess alembic invocation can
    land tables inside it. AUTOCOMMIT isolation is required so the
    CREATE SCHEMA does not implicitly open a transaction.
    """
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    finally:
        engine.dispose()


def _drop_isolated_schema(database_url: str, schema: str) -> None:
    """Best-effort DROP of the temporary schema. Tolerates failure."""
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        engine.dispose()


def _psql_dsn(database_url: str) -> str:
    """Convert an asyncpg DSN into a sync psycopg2 DSN.

    Strips any existing query string so the caller can append its own
    ``options=-c search_path=...`` parameter.
    """
    if database_url.startswith("postgresql+"):
        database_url = database_url.replace(
            "postgresql+asyncpg", "postgresql+psycopg2",
        )
    return database_url.split("?")[0]


def _run_alembic_subprocess(
    schema_url: str, command: tuple[str, ...], timeout: int = 120,
) -> tuple[int, str, str]:
    """Invoke an ``alembic`` command against ``schema_url`` (which
    already encodes the search_path).

    The subprocess CWD is the **repo root** so that
    ``alembic.ini``'s ``prepend_sys_path = .`` (which resolves to
    ``cwd``) puts the repo on ``sys.path`` — required for
    ``from app.db.base import Base`` and ``import app.models`` in
    ``alembic/env.py``. We override ``DATABASE_URL`` via the
    subprocess env so the project's ``.env`` (which points at the
    dev DB) does not override the test DB. ``alembic.ini`` is
    reachable via the explicit ``-c`` argument.
    """
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
    """Read the test ``DATABASE_URL`` from the env. Tells pytest to
    skip migration tests when no DB is configured.
    """
    return os.environ.get("DATABASE_URL")


@pytest.fixture
def phase_1_2a_schema():
    """Set up an isolated Postgres schema, ``alembic upgrade head``
    to Phase-1.2a, then yield a dict with the schema name and a
    sync URL pointed at the schema. Tears the schema down on exit."""
    async_dsn = _test_async_dsn()
    if not async_dsn:
        pytest.skip("DATABASE_URL not configured in test env.")
    if PHASE_1_2A_MIGRATION is None:
        pytest.skip(PHASE_1_2A_MIGRATION_REQUIRED)

    base = _psql_dsn(async_dsn)
    schema = f"phase_1_2a_test_{uuid.uuid4().hex[:8]}"

    _create_isolated_schema(base, schema)
    schema_url = f"{base}?options=-c%20search_path%3D{schema}"
    try:
        rc, stdout, stderr = _run_alembic_subprocess(
            schema_url, ("upgrade", "head"),
        )
        if rc != 0:
            raise RuntimeError(
                f"alembic upgrade head failed (rc={rc}).\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )
        yield {
            "schema": schema,
            "sync_url": schema_url,
            "base_sync_url": base,
        }
    finally:
        _drop_isolated_schema(base, schema)


class TestPhase12aMigrationUpgrades:
    """End-to-end migration tests. Each builds an isolated schema,
    runs ``alembic upgrade head``, then asserts the resulting tables
    and columns."""

    def test_alembic_upgrade_head_succeeds_on_fresh_schema(
        self, phase_1_2a_schema
    ) -> None:
        """Reaches this point only if alembic upgrade returned
        without exception — the fixture raises otherwise."""

    def test_phase_1_1_tables_are_preserved(self, phase_1_2a_schema) -> None:
        """The Phase-1.1 tables the migration is built on must all
        exist after ``alembic upgrade head``. Their existence proves
        the migration chain ran every prior migration in the chain.
        """
        engine = create_engine(phase_1_2a_schema["sync_url"])
        try:
            inspector = inspect(engine)
            for table in (
                "athletes",
                "athlete_profiles",
                "athlete_auths",
                "athlete_refresh_tokens",
                "system_events",
                "system_event_outbox",
            ):
                assert inspector.has_table(table), (
                    f"Phase-1.1 table `{table}` must exist after "
                    "Phase-1.2a migration."
                )
        finally:
            engine.dispose()

    def test_migration_extends_athlete_profiles_with_phase_1_2a_columns(
        self, phase_1_2a_schema
    ) -> None:
        """``athlete_profiles`` carries the full Phase-1.2a column
        set AND retains the unique-on-athlete_id invariant."""
        engine = create_engine(phase_1_2a_schema["sync_url"])
        try:
            inspector = inspect(engine)
            cols = {
                c["name"]
                for c in inspector.get_columns("athlete_profiles")
            }
            for column in (
                "gap_curve_model",
                "weather_response_model",
                "banister_constants",
                "cycle_personal_model",
                "location_lat",
                "location_lng",
                "timezone",
                "training_window",
                "current_effort_generation",
                "structural_risk_flag",
                "objective_thresholds",
            ):
                assert column in cols, (
                    f"athlete_profiles.{column} missing after migration."
                )
            uniques = inspector.get_unique_constraints("athlete_profiles")
            athlete_id_unique = any(
                tuple(u["column_names"]) == ("athlete_id",)
                for u in uniques
            )
            assert athlete_id_unique, (
                "athlete_profiles.athlete_id must remain unique after "
                "the Phase-1.2a migration."
            )
        finally:
            engine.dispose()

    def test_migration_creates_athlete_preferences_with_check_constraint(
        self, phase_1_2a_schema
    ) -> None:
        """The new table exists with all expected columns, a unique
        constraint on ``athlete_id``, and the named CHECK constraint
        ``years_structured_training >= 0``.
        """
        engine = create_engine(phase_1_2a_schema["sync_url"])
        try:
            inspector = inspect(engine)
            assert inspector.has_table("athlete_preferences")
            cols = {
                c["name"]
                for c in inspector.get_columns("athlete_preferences")
            }
            for column in (
                "id",
                "athlete_id",
                "sport_background",
                "years_structured_training",
                "training_time_of_day",
                "weekly_schedule",
                "gps_source",
                "hr_source",
                "power_source",
                "primary_training_platform",
                "updated_at",
            ):
                assert column in cols, (
                    f"athlete_preferences.{column} missing after migration."
                )

            uniques = inspector.get_unique_constraints(
                "athlete_preferences"
            )
            assert any(
                tuple(u["column_names"]) == ("athlete_id",)
                for u in uniques
            ), (
                "athlete_preferences.athlete_id must be uniquely "
                "constrained after the migration."
            )

            checks = inspector.get_check_constraints("athlete_preferences")
            found = any(
                "years_structured_training" in (c.get("sqltext") or "")
                and ">=" in (c.get("sqltext") or "")
                for c in checks
            )
            assert found, (
                "athlete_preferences CHECK constraint "
                "`years_structured_training >= 0` missing after migration."
            )
        finally:
            engine.dispose()

    def test_migration_creates_activities_with_lean_schema(
        self, phase_1_2a_schema
    ) -> None:
        """The new table exists with the lean column set and no
        workout-summary fields."""
        engine = create_engine(phase_1_2a_schema["sync_url"])
        try:
            inspector = inspect(engine)
            assert inspector.has_table("activities")

            cols = {c["name"] for c in inspector.get_columns("activities")}
            required = {
                "id",
                "athlete_id",
                "planned_session_id",
                "source",
                "external_id",
                "activity_date",
                "start_time",
                "duration_seconds",
                "aerobic_load",
                "neuromuscular_load",
                "structural_load",
                "has_hr",
                "has_rr_intervals",
                "has_power",
                "calibration_eligible",
                "quality_flags",
                "fit_file_key",
                "ingestion_pipeline_version",
                "cleaning_pipeline_version",
                "notes",
                "created_at",
            }
            assert required <= cols, (
                "Activities schema missing required columns: "
                f"{required - cols}"
            )

            forbidden = {
                "avg_hr", "avg_pace", "avg_power", "avg_cadence",
            }
            assert forbidden.isdisjoint(cols), (
                "Activities schema carries forbidden workout-summary "
                f"fields: {forbidden & cols}"
            )
        finally:
            engine.dispose()

    def test_migration_partial_dedup_index_in_pg_catalog(
        self, phase_1_2a_schema
    ) -> None:
        """The partial unique index on activities must surface in
        the Postgres catalog with the predicate visible. SQLAlchemy
        Inspector does not expose predicate text, so we query
        ``pg_indexes`` directly.
        """
        engine = create_engine(phase_1_2a_schema["sync_url"])
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        textwrap.dedent(
                            """
                            SELECT indexname, indexdef
                            FROM pg_indexes
                            WHERE schemaname = :schema
                              AND tablename = 'activities'
                              AND indexname =
                                  'uq_activities_athlete_external_source'
                            """
                        ).strip()
                    ),
                    {"schema": phase_1_2a_schema["schema"]},
                ).fetchall()
            assert result, (
                "uq_activities_athlete_external_source not found in "
                "pg_indexes for schema "
                f"`{phase_1_2a_schema['schema']}`."
            )
            _, indexdef = result[0]
            assert indexdef.lower().startswith("create unique index"), (
                f"uq_activities_athlete_external_source must be UNIQUE: "
                f"{indexdef}"
            )
            assert "external_id is not null" in indexdef.lower(), (
                f"uq_activities_athlete_external_source must carry the "
                f"`external_id IS NOT NULL` predicate: {indexdef}"
            )
        finally:
            engine.dispose()

    def test_migration_athlete_fk_cascade_in_pg_catalog(
        self, phase_1_2a_schema,
    ) -> None:
        """The two new tables declare ``ondelete='CASCADE'`` on
        ``athlete_id`` so the activity/preferences rows vanish when
        the parent athlete is deleted. Postgres auto-names FK
        constraints so we don't pattern-match on the name — instead
        we filter by ``confkey`` matching the first PK column of
        ``athletes``. ``pg_constraint.confdeltype='c'`` means
        CASCADE.

        ``pg_get_constraintdef()`` returns the FK definition
        (``REFERENCES athletes(id) ON DELETE CASCADE``) so the test
        can be read verbatim from a failing assertion.
        """
        engine = create_engine(phase_1_2a_schema["sync_url"])
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        textwrap.dedent(
                            """
                            SELECT 
                                conrelid_table.relname AS table_name,
                                c.confdeltype,
                                pg_get_constraintdef(c.oid) AS constraint_def
                            FROM pg_constraint c
                            JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
                            JOIN pg_namespace conrelid_ns ON conrelid_ns.oid = conrelid_table.relnamespace
                            JOIN pg_class confrelid_table ON confrelid_table.oid = c.confrelid
                            WHERE c.contype = 'f'
                              AND confrelid_table.relname = 'athletes'
                              AND conrelid_ns.nspname = :schema
                              AND conrelid_table.relname IN ('activities', 'athlete_preferences')
                            """
                        ).strip()
                    ),
                    {"schema": phase_1_2a_schema["schema"]},
                ).fetchall()
            seen = {row[0]: (row[1], row[2]) for row in rows}
            for table in ("activities", "athlete_preferences"):
                assert table in seen, (
                    f"{table} must have a FK to athletes(id). Got {seen}."
                )
                confdeltype, constraint_def = seen[table]
                assert confdeltype == "c", (
                    f"{table}.athlete_id FK must CASCADE. Got "
                    f"confdeltype={confdeltype!r}, define={constraint_def}."
                )
        finally:
            engine.dispose()
            engine.dispose()


class TestPhase12aMigrationDowngrade:
    """Verify ``alembic downgrade -1`` returns the schema to the
    Phase-1.1 P3 baseline — the migration is reversible."""

    def test_downgrade_returns_schema_to_phase_1_1_baseline(self) -> None:
        async_dsn = _test_async_dsn()
        if not async_dsn:
            pytest.skip("DATABASE_URL not configured in test env.")
        if PHASE_1_2A_MIGRATION is None:
            pytest.skip(PHASE_1_2A_MIGRATION_REQUIRED)

        base = _psql_dsn(async_dsn)
        schema = f"phase_1_2a_downgrade_{uuid.uuid4().hex[:8]}"
        schema_url = f"{base}?options=-c%20search_path%3D{schema}"
        _create_isolated_schema(base, schema)
        try:
            # 1) Apply Phase-1.2a (full chain incl. Phase-1.1).
            rc_up, out_up, err_up = _run_alembic_subprocess(
                schema_url, ("upgrade", "head"),
            )
            assert rc_up == 0, (
                f"alembic upgrade head failed (rc={rc_up}). "
                f"STDOUT:\n{out_up}\nSTDERR:\n{err_up}"
            )

            # 2) Downgrade one revision.
            rc_dn, out_dn, err_dn = _run_alembic_subprocess(
                schema_url, ("downgrade", "-1"),
            )
            assert rc_dn == 0, (
                f"alembic downgrade -1 failed (rc={rc_dn}). "
                f"STDOUT:\n{out_dn}\nSTDERR:\n{err_dn}"
            )

            # 3) The Phase-1.2a tables and columns are gone.
            engine = create_engine(schema_url)
            try:
                inspector = inspect(engine)
                assert not inspector.has_table("activities"), (
                    "Downgrade must drop `activities`."
                )
                assert not inspector.has_table("athlete_preferences"), (
                    "Downgrade must drop `athlete_preferences`."
                )
                cols = {
                    c["name"]
                    for c in inspector.get_columns("athlete_profiles")
                }
                for column in (
                    "gap_curve_model",
                    "weather_response_model",
                    "banister_constants",
                    "cycle_personal_model",
                    "location_lat",
                    "location_lng",
                    "training_window",
                    "current_effort_generation",
                    "structural_risk_flag",
                    "objective_thresholds",
                ):
                    assert column not in cols, (
                        f"Downgrade must drop athlete_profiles.{column}."
                    )
                # Phase-1.1 athletes is still here.
                assert inspector.has_table("athletes"), (
                    "Downgrade must not drop `athletes` (Phase-1.1)."
                )
            finally:
                engine.dispose()
        finally:
            _drop_isolated_schema(base, schema)


# ---------------------------------------------------------------------------
# Helper constants exposed for downstream tests (registry) — the
# migration revision is now a stable, audited delivery.
# ---------------------------------------------------------------------------

PHASE_1_2A_DELIVERED_REVISION = PHASE_1_2A_REVISION
