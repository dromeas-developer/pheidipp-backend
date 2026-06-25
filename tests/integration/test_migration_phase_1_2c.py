"""Integration tests for the Phase-1.2c Alembic migration.

The Phase-1.2c plan requires:

* ``alembic upgrade head`` succeeds on a fresh database with no errors.
* The schema carries every Phase-1.2c table (``twin_states``,
  ``athlete_physiology``, ``athlete_fitness``, ``coaching_messages``,
  ``generation_events``, ``generated_workouts``, ``workout_steps``)
  with the documented invariants.
* All partial unique indexes are emitted
  (``uq_twin_states_athlete_activity``,
  ``uq_coaching_messages_athlete_first_message``,
  ``uq_coaching_messages_activity_post_workout``).
* All CHECK constraints are emitted:
  - ``ck_generation_events_failure_reason_consistency``
  - ``ck_generation_events_token_counts_non_negative``
  - ``ck_generation_events_latency_non_negative``
  - ``ck_athlete_fitness_*_form_invariant`` (4 constraints)
  - ``ck_athlete_fitness_time_constants_source_valid``
  - ``ck_coaching_messages_content_non_empty``
  - ``ck_generated_workouts_targets_are_objects``
  - ``ck_generated_workouts_recovery_modifier_level_valid``
  - ``ck_workout_steps_step_order_positive``
  - ``ck_workout_steps_duration_non_negative``
  - ``ck_workout_steps_description_non_empty``
* The existing ``training_plans.twin_state_id`` column gains a
  foreign key to ``twin_states.id`` while preserving its nullable
  semantics (deferred from Phase-1.2b).
* Every Phase-1.1 / Phase-1.2a / Phase-1.2b table survives the
  upgrade — the migration is additive.
* ``alembic downgrade -2`` returns the schema to the Phase-1.2b
  baseline: the FK follow-up drops the
  ``training_plans.twin_state_id`` FK, then the primary migration
  drops the seven new tables.

The Phase-1.2c lineage is delivered as one or more stacked
migrations (the primary ``alembic/versions/<rev>_phase_1_2c_*.py``
plus any follow-up revisions that chain from it), all reachable from
``alembic upgrade head``. The tests resolve the lineage
deterministically by filename + ``down_revision`` walk and **require**
it to be present — if the primary migration is missing,
``pytest.fail`` reports the absence rather than silently skipping so a
deletion regression cannot go unnoticed.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy import create_engine, inspect, text


REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"
PHASE_1_2B_REVISION = "1b9e9026db1e"  # the migration this plan builds on
PHASE_1_2C_HEAD_REVISION = "d1579f4430e7"  # final FK-follow-up revision


def _phase_1_2c_migration_path() -> Optional[Path]:
    if not VERSIONS_DIR.exists():
        return None
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        slug = path.stem.lower()
        if "phase_1_2c" in slug or "phase-1-2c" in slug:
            return path
    return None


PHASE_1_2C_MIGRATION = _phase_1_2c_migration_path()
PHASE_1_2C_MIGRATION_REQUIRED = (
    "alembic/versions/<rev>_phase_1_2c_*.py — required by "
    "docs/implementation/phase-1/"
    "phase-1-2c-p1-twin-fitness-coaching-workouts.md"
)


def _phase_1_2c_followup_migration_paths() -> list[Path]:
    """Return all Phase-1.2c-lineage migration files (main + any
    follow-up revisions that build on it).

    Phase-1.2c is sometimes delivered as multiple stacked migrations
    (for example, a primary ``phase_1_2c_*`` migration that introduces
    the seven new tables, plus a follow-up migration that wires the
    ``training_plans.twin_state_id`` foreign key now that
    ``twin_states`` exists). The follow-ups live in the same
    alembic chain (``down_revision`` points at the previous
    Phase-1.2c revision) but their filenames no longer carry the
    ``phase_1_2c`` substring — they encode the change
    (``add_training_plans_twin_state_fk``). Discover both the
    primary and follow-ups so static-structure tests can verify
    that the *cumulative* Phase-1.2c lineage wires every contract
    the plan describes.
    """
    if PHASE_1_2C_MIGRATION is None:
        return []
    primary = PHASE_1_2C_MIGRATION
    primary_rev, _ = _migration_revision_and_down(primary)
    chain: list[Path] = [primary]
    seen_revs: set[str] = {primary_rev} if primary_rev else set()
    frontier: list[str] = [primary_rev] if primary_rev else []
    while frontier:
        next_rev = frontier.pop()
        for path in sorted(VERSIONS_DIR.glob("*.py")):
            rev_str, down_rev = _migration_revision_and_down(path)
            if not rev_str or rev_str in seen_revs:
                continue
            if down_rev == next_rev:
                chain.append(path)
                seen_revs.add(rev_str)
                frontier.append(rev_str)
    return chain


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


def _migration_creates_table(path: Path, name: str) -> bool:
    return (
        f"op.create_table('{name}'"
        in _migration_function_body(path, "upgrade")
    )


def _migration_creates_index(path: Path, name: str) -> bool:
    return (
        f"op.create_index('{name}'"
        in _migration_function_body(path, "upgrade")
    )


def _migration_creates_check(path: Path, name: str) -> bool:
    body = _migration_function_body(path, "upgrade")
    # SAEnum inline or CreateTable column-level CheckConstraint
    # patterns: name='ck_xxx' OR sa.CheckConstraint('...', name='ck_xxx')
    return (
        f"name='{name}'" in body
        or f'name="{name}"' in body
    )


def _migration_emits_fk_to_table(path: Path, table_name: str) -> bool:
    """Detect ``op.create_foreign_key`` targeting ``table_name``."""
    body = _migration_function_body(path, "upgrade")
    return (
        f"op.create_foreign_key(" in body
        and f"'{table_name}'" in body
    )


# ---------------------------------------------------------------------------
# Migration file presence.
# ---------------------------------------------------------------------------


class TestPhase12cMigrationFilePresence:
    """The migration file must exist on disk before functional tests
    can run. Missing file is an error, not a skip — a deletion
    regression must surface as a failure rather than a
    green-skipped test."""

    def test_migration_file_present(self) -> None:
        assert PHASE_1_2C_MIGRATION is not None, (
            "Phase-1.2c Alembic migration file is missing on disk. "
            f"Expected: {PHASE_1_2C_MIGRATION_REQUIRED}"
        )
        assert PHASE_1_2C_MIGRATION.exists()
        slug = PHASE_1_2C_MIGRATION.stem.lower()
        assert "phase_1_2c" in slug or "phase-1-2c" in slug, (
            f"Migration file stem `{PHASE_1_2C_MIGRATION.stem}` does "
            "not encode the Phase-1.2c slug — did the regex match a "
            "wrong file?"
        )


def _require_migration_path() -> Path:
    if PHASE_1_2C_MIGRATION is None:
        pytest.skip(PHASE_1_2C_MIGRATION_REQUIRED)
    return PHASE_1_2C_MIGRATION


# ---------------------------------------------------------------------------
# Static migration structure.
# ---------------------------------------------------------------------------


class TestPhase12cMigrationStructure:
    """Static checks on the migration file. Low-cost, run before
    functional subprocess tests."""

    def test_migration_declares_revision_and_down_revision(self) -> None:
        path = _require_migration_path()
        rev, down = _migration_revision_and_down(path)
        assert rev, "Phase-1.2c migration must declare `revision`."
        assert down, (
            "Phase-1.2c migration must declare `down_revision` "
            f"pointing at Phase-1.2b head ({PHASE_1_2B_REVISION})."
        )

    def test_down_revision_chains_from_phase_1_2b_head(self) -> None:
        path = _require_migration_path()
        _, down = _migration_revision_and_down(path)
        assert down == PHASE_1_2B_REVISION, (
            f"Phase-1.2c migration down_revision must be "
            f"`{PHASE_1_2B_REVISION}` (Phase-1.2b head). Got `{down}`."
        )

    @pytest.mark.parametrize(
        "forbidden_call,table_name",
        [
            # Phase-1.1 tables must not be dropped.
            ("op.drop_table", "athletes"),
            ("op.drop_table", "athlete_profiles"),
            ("op.drop_table", "athlete_auths"),
            ("op.drop_table", "athlete_refresh_tokens"),
            ("op.drop_table", "system_events"),
            ("op.drop_table", "system_event_outbox"),
            # Phase-1.2a tables must not be dropped.
            ("op.drop_table", "activities"),
            ("op.drop_table", "athlete_preferences"),
            # Phase-1.2b tables must not be dropped (only the new
            # Phase-1.2c tables are droppable in downgrade).
            ("op.drop_table", "training_goals"),
            ("op.drop_table", "secondary_events"),
            ("op.drop_table", "training_plans"),
            ("op.drop_table", "regeneration_tasks"),
            ("op.drop_table", "weekly_plans"),
            ("op.drop_table", "weekly_sessions"),
            ("op.drop_table", "planned_sessions"),
            ("op.drop_table", "checkpoints"),
        ],
    )
    def test_migration_never_drops_existing_tables(
        self, forbidden_call: str, table_name: str
    ) -> None:
        """Both ``upgrade`` and ``downgrade`` must NOT drop any of
        the Phase-1.1 / Phase-1.2a / Phase-1.2b tables.

        ``downgrade`` is allowed to drop the new Phase-1.2c tables
        only (``twin_states``, ``athlete_physiology``,
        ``athlete_fitness``, ``coaching_messages``,
        ``generation_events``, ``generated_workouts``,
        ``workout_steps``)."""
        path = _require_migration_path()
        for fn_name in ("upgrade", "downgrade"):
            body = _migration_function_body(path, fn_name)
            for quote in ("'", '"'):
                forbidden = f"{forbidden_call}({quote}{table_name}{quote}"
                assert forbidden not in body, (
                    f"Phase-1.2c migration {fn_name} contains "
                    f"forbidden `{forbidden}`. The plan requires "
                    "additive transitions for existing tables."
                )

    @pytest.mark.parametrize(
        "expected_table",
        [
            "twin_states",
            "athlete_physiology",
            "athlete_fitness",
            "coaching_messages",
            "generation_events",
            "generated_workouts",
            "workout_steps",
        ],
    )
    def test_migration_creates_seven_phase_12c_tables(
        self, expected_table: str
    ) -> None:
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            f"op.create_table('{expected_table}'" in upgrade
        ), (
            f"Phase-1.2c migration must create `{expected_table}`."
        )

    def test_migration_emits_twin_state_activity_partial_index(self) -> None:
        """``uq_twin_states_athlete_activity`` with predicate
        ``activity_id IS NOT NULL``."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            "op.create_index('uq_twin_states_athlete_activity'" in upgrade
        ), (
            "Phase-1.2c migration must create the TwinState activity "
            "partial unique index."
        )
        assert (
            "postgresql_where=sa.text('activity_id IS NOT NULL')"
            in upgrade
        ), (
            "uq_twin_states_athlete_activity predicate must be "
            "`activity_id IS NOT NULL`."
        )

    def test_migration_emits_coaching_message_partial_indexes(self) -> None:
        """``uq_coaching_messages_athlete_first_message`` and
        ``uq_coaching_messages_activity_post_workout``."""
        path = _require_migration_path()
        upgrade = _migration_function_body(path, "upgrade")
        assert (
            "op.create_index('uq_coaching_messages_athlete_first_message'"
            in upgrade
        ), (
            "Phase-1.2c migration must create the CoachingMessage "
            "first_message partial unique index."
        )
        assert (
            "op.create_index('uq_coaching_messages_activity_post_workout'"
            in upgrade
        ), (
            "Phase-1.2c migration must create the CoachingMessage "
            "post_workout partial unique index."
        )

    def test_migration_emits_failure_reason_check(self) -> None:
        path = _require_migration_path()
        assert _migration_creates_check(
            path, "ck_generation_events_failure_reason_consistency"
        ), (
            "Phase-1.2c migration must emit "
            "ck_generation_events_failure_reason_consistency."
        )

    def test_migration_emits_token_count_and_latency_checks(self) -> None:
        path = _require_migration_path()
        assert _migration_creates_check(
            path, "ck_generation_events_token_counts_non_negative"
        )
        assert _migration_creates_check(
            path, "ck_generation_events_latency_non_negative"
        )

    def test_migration_emits_athlete_fitness_form_invariant_checks(
        self,
    ) -> None:
        """``ck_athlete_fitness_*_form_invariant`` for aggregate +
        each populated dimension."""
        path = _require_migration_path()
        for variant in (
            "aggregate",
            "aerobic",
            "neuromuscular",
            "structural",
        ):
            assert _migration_creates_check(
                path, f"ck_athlete_fitness_{variant}_form_invariant"
            ), (
                f"Phase-1.2c migration must emit "
                f"ck_athlete_fitness_{variant}_form_invariant."
            )

    def test_migration_emits_athlete_fitness_time_constants_check(self) -> None:
        path = _require_migration_path()
        assert _migration_creates_check(
            path, "ck_athlete_fitness_time_constants_source_valid"
        )

    def test_migration_emits_coaching_message_content_check(self) -> None:
        path = _require_migration_path()
        assert _migration_creates_check(
            path, "ck_coaching_messages_content_non_empty"
        )

    def test_migration_emits_generated_workout_checks(self) -> None:
        path = _require_migration_path()
        assert _migration_creates_check(
            path, "ck_generated_workouts_targets_are_objects"
        )
        assert _migration_creates_check(
            path,
            "ck_generated_workouts_recovery_modifier_level_valid",
        )

    def test_migration_emits_workout_step_checks(self) -> None:
        path = _require_migration_path()
        assert _migration_creates_check(
            path, "ck_workout_steps_step_order_positive"
        )
        assert _migration_creates_check(
            path, "ck_workout_steps_duration_non_negative"
        )
        assert _migration_creates_check(
            path, "ck_workout_steps_description_non_empty"
        )

    def test_migration_wires_training_plans_twin_state_fk(self) -> None:
        """``training_plans.twin_state_id`` gains a FK to
        ``twin_states.id`` — Phase-1.2c finally wires it after
        ``twin_states`` exists.

        The FK may live in the primary ``phase_1_2c_*.py``
        migration OR in a follow-up migration chained from it
        (for example, a dedicated
        ``add_training_plans_twin_state_fk.py`` revision). This
        test scans the *entire* Phase-1.2c lineage so the
        contract is verified regardless of where the FK emission
        is delivered."""
        if PHASE_1_2C_MIGRATION is None:
            pytest.skip(PHASE_1_2C_MIGRATION_REQUIRED)
        migrations = _phase_1_2c_followup_migration_paths()
        assert migrations, (
            "Failed to resolve any Phase-1.2c migration lineage "
            "from `alembic/versions/`."
        )
        wired = False
        for path in migrations:
            upgrade = _migration_function_body(path, "upgrade")
            if (
                "op.create_foreign_key(" in upgrade
                and "twin_states" in upgrade
                and "training_plans" in upgrade
            ):
                wired = True
                break
        assert wired, (
            "Phase-1.2c lineage (primary + any follow-up migrations) "
            "must wire training_plans.twin_state_id -> twin_states.id "
            "via op.create_foreign_key. The FK was not found in any "
            f"migration in the chain: {[p.name for p in migrations]}"
        )

    def test_downgrade_drops_new_objects_only(self) -> None:
        """Structural inverse: the primary migration's downgrade
        drops the seven new Phase-1.2c tables — but never runs
        ``op.create_table`` or ``op.add_column``. The
        ``training_plans.twin_state_id`` FK is dropped by the
        follow-up migration's downgrade (it was added there,
        so its removal lives there). structural-mode contract
        tests live separately in ``test_followup_drop_removes_fk``."""
        path = _require_migration_path()
        downgrade = _migration_function_body(path, "downgrade")
        for forbidden in ("op.create_table", "op.add_column"):
            assert forbidden not in downgrade, (
                f"Phase-1.2c downgrade must not call `{forbidden}` — "
                "it must only drop / remove."
            )
        # All seven new tables are dropped.
        for table in (
            "twin_states",
            "athlete_physiology",
            "athlete_fitness",
            "coaching_messages",
            "generation_events",
            "generated_workouts",
            "workout_steps",
        ):
            assert (
                f"op.drop_table('{table}'" in downgrade
            ), (
                f"Phase-1.2c downgrade must drop `{table}`."
            )

    def test_followup_drops_training_plans_twin_state_fk(self) -> None:
        """The follow-up migration(s) chained from the primary
        ``phase_1_2c`` revision must drop the
        ``training_plans.twin_state_id`` FK in their ``downgrade()``
        so that ``alembic downgrade -2`` returns the schema to the
        Phase-1.2b baseline.

        Some migrations instead keep the FK removal inside the
        primary; this test accepts either location so the contract
        is verified regardless of how the FK was delivered."""
        if PHASE_1_2C_MIGRATION is None:
            pytest.skip(PHASE_1_2C_MIGRATION_REQUIRED)
        # Have ANY migration in the lineage dropped the FK?
        fk_removed = False
        primary_downgrade = _migration_function_body(
            PHASE_1_2C_MIGRATION, "downgrade"
        )
        if (
            "'fk_training_plans_twin_state'" in primary_downgrade
            or "op.drop_constraint" in primary_downgrade
        ):
            fk_removed = True
        if not fk_removed:
            for path in _phase_1_2c_followup_migration_paths():
                downgrade = _migration_function_body(path, "downgrade")
                if (
                    "'fk_training_plans_twin_state'" in downgrade
                    or "op.drop_constraint" in downgrade
                    and "training_plans" in downgrade
                ):
                    fk_removed = True
                    break
        assert fk_removed, (
            "Phase-1.2c lineage must drop the "
            "training_plans.twin_state_id FK somewhere in the "
            "primary migration's downgrade() or a follow-up's "
            "downgrade() so a full `alembic downgrade -2` returns "
            "to the Phase-1.2b baseline cleanly."
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
def phase_1_2c_schema():
    """Set up an isolated Postgres schema, ``alembic upgrade head``
    to Phase-1.2c, then yield a dict with the schema name and a
    sync URL pointed at the schema. Tears the schema down on exit."""
    async_dsn = _test_async_dsn()
    if not async_dsn:
        pytest.skip("DATABASE_URL not configured in test env.")
    if PHASE_1_2C_MIGRATION is None:
        pytest.skip(PHASE_1_2C_MIGRATION_REQUIRED)
    base = _psql_dsn(async_dsn)
    schema = f"phase_1_2c_test_{uuid.uuid4().hex[:8]}"
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


class TestPhase12cUpgradeFunctional:
    """The Phase-1.2c migration runs cleanly on a fresh database and
    produces every documented table with its invariants."""

    def test_all_phase_12c_tables_created(
        self, phase_1_2c_schema: dict
    ) -> None:
        engine = create_engine(phase_1_2c_schema["sync_url"])
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                expected_tables = {
                    "twin_states",
                    "athlete_physiology",
                    "athlete_fitness",
                    "coaching_messages",
                    "generation_events",
                    "generated_workouts",
                    "workout_steps",
                }
                actual_tables = set(inspector.get_table_names())
                missing = expected_tables - actual_tables
                assert not missing, (
                    f"Phase-1.2c upgrade did not create tables: "
                    f"{missing}"
                )
        finally:
            engine.dispose()

    def test_phase_12a_and_12b_tables_survive(
        self, phase_1_2c_schema: dict
    ) -> None:
        """Every Phase-1.1 / 1.2a / 1.2b table survives the upgrade
        — the migration is purely additive."""
        engine = create_engine(phase_1_2c_schema["sync_url"])
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                actual_tables = set(inspector.get_table_names())
                for required in (
                    # Phase-1.1
                    "athletes",
                    "athlete_profiles",
                    "athlete_auths",
                    "athlete_refresh_tokens",
                    "system_events",
                    "system_event_outbox",
                    # Phase-1.2a
                    "activities",
                    "athlete_preferences",
                    # Phase-1.2b
                    "training_goals",
                    "secondary_events",
                    "training_plans",
                    "regeneration_tasks",
                    "weekly_plans",
                    "weekly_sessions",
                    "planned_sessions",
                    "checkpoints",
                ):
                    assert required in actual_tables, (
                        f"Phase-1.2c upgrade lost table `{required}` — "
                        "the migration must be additive."
                    )
        finally:
            engine.dispose()

    def test_twin_state_partial_unique_index_present(
        self, phase_1_2c_schema: dict
    ) -> None:
        """``uq_twin_states_athlete_activity`` must exist in the
        upgraded schema."""
        engine = create_engine(phase_1_2c_schema["sync_url"])
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT 1 FROM pg_index i "
                        "JOIN pg_class c ON c.oid = i.indexrelid "
                        "WHERE c.relname = 'uq_twin_states_athlete_activity'"
                    )
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None, (
            "uq_twin_states_athlete_activity must exist in the "
            "upgraded schema."
        )

    def test_training_plans_twin_state_fk_present(
        self, phase_1_2c_schema: dict
    ) -> None:
        """``training_plans.twin_state_id`` must have an FK to
        ``twin_states.id`` after the upgrade."""
        engine = create_engine(phase_1_2c_schema["sync_url"])
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM pg_constraint c
                        JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
                        JOIN pg_class confrelid_table ON confrelid_table.oid = c.confrelid
                        WHERE c.contype = 'f'
                          AND confrelid_table.relname = 'twin_states'
                          AND conrelid_table.relname = 'training_plans'
                        """
                    )
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None, (
            "training_plans.twin_state_id must have an FK to "
            "twin_states.id after the Phase-1.2c upgrade."
        )

    def test_athlete_fitness_form_invariant_check_active(
        self, phase_1_2c_schema: dict
    ) -> None:
        """``ck_athlete_fitness_aggregate_form_invariant`` must be
        active on the upgraded schema."""
        engine = create_engine(phase_1_2c_schema["sync_url"])
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conname = 'ck_athlete_fitness_aggregate_form_invariant'"
                    )
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None, (
            "ck_athlete_fitness_aggregate_form_invariant must be "
            "active on the upgraded schema."
        )

    def test_generation_events_failure_reason_check_active(
        self, phase_1_2c_schema: dict
    ) -> None:
        """``ck_generation_events_failure_reason_consistency`` must
        be active on the upgraded schema."""
        engine = create_engine(phase_1_2c_schema["sync_url"])
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conname = "
                        "'ck_generation_events_failure_reason_consistency'"
                    )
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None, (
            "ck_generation_events_failure_reason_consistency must be "
            "active on the upgraded schema."
        )


class TestPhase12cDowngradeFunctional:
    """``alembic downgrade -2`` returns the schema to the Phase-1.2b
    baseline: the FK follow-up migration drops the
    ``training_plans.twin_state_id`` FK, then the primary
    ``phase_1_2c`` migration drops the seven new tables.

    ``downgrade -1`` is not sufficient because Phase-1.2c ships as
    two stacked revisions (``79dc97d4e433`` primary +
    ``d1579f4430e7`` FK follow-up); a single step only reverts the
    FK follow-up, leaving all seven new tables in the schema."""

    def test_downgrade_returns_to_phase_12b_baseline(self) -> None:
        """End-to-end: upgrade to head, downgrade two steps, verify
        Phase-1.2c tables are gone and Phase-1.2a / 1.2b tables
        survive."""
        async_dsn = _test_async_dsn()
        if not async_dsn:
            pytest.skip("DATABASE_URL not configured in test env.")
        if PHASE_1_2C_MIGRATION is None:
            pytest.skip(PHASE_1_2C_MIGRATION_REQUIRED)
        base = _psql_dsn(async_dsn)
        schema = f"phase_1_2c_down_{uuid.uuid4().hex[:8]}"
        _create_isolated_schema(base, schema)
        schema_url = f"{base}?options=-c%20search_path%3D{schema}"
        try:
            # Upgrade to head.
            rc, stdout, stderr = _run_alembic_subprocess(
                schema_url, ("upgrade", "head"),
            )
            assert rc == 0, (
                f"alembic upgrade head failed (rc={rc}).\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

            # Downgrade TWO steps. -1 would only revert the FK
            # follow-up (d1579f4430e7) and leave the seven new
            # tables in place; -2 reaches Phase-1.2b head where
            # the tables are gone and the FK is removed.
            rc, stdout, stderr = _run_alembic_subprocess(
                schema_url, ("downgrade", "-2"),
            )
            assert rc == 0, (
                f"alembic downgrade -2 failed (rc={rc}).\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

            # Phase-1.2c tables must be gone.
            engine = create_engine(schema_url)
            try:
                with engine.connect() as conn:
                    inspector = inspect(conn)
                    actual_tables = set(inspector.get_table_names())
                    for phase_1_2c_table in (
                        "twin_states",
                        "athlete_physiology",
                        "athlete_fitness",
                        "coaching_messages",
                        "generation_events",
                        "generated_workouts",
                        "workout_steps",
                    ):
                        assert phase_1_2c_table not in actual_tables, (
                            f"Phase-1.2c downgrade did not drop "
                            f"`{phase_1_2c_table}`."
                        )
            finally:
                engine.dispose()

            # Phase-1.2a / 1.2b tables must survive.
            engine = create_engine(schema_url)
            try:
                with engine.connect() as conn:
                    inspector = inspect(conn)
                    actual_tables = set(inspector.get_table_names())
                    for required in (
                        "athletes",
                        "activities",
                        "athlete_preferences",
                        "training_goals",
                        "training_plans",
                        "planned_sessions",
                    ):
                        assert required in actual_tables, (
                            f"Phase-1.2c downgrade lost table "
                            f"`{required}` — the downgrade must be "
                            "non-destructive for existing tables."
                        )
            finally:
                engine.dispose()
        finally:
            _drop_isolated_schema(base, schema)