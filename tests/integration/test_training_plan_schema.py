"""Integration tests for the ``TrainingPlan`` schema at the DB level.

Phase-1.2b introduces the new ``training_plans`` table that persists
the plan-generation output for a goal. The schema stores phases,
weekly distributions, and the checkpoint schedule as JSONB so the
synthesis service can update them over time without migration churn.

DB-level invariants this plan codifies:

* A nullable ``training_goal_id`` FK with CASCADE on delete.
* A nullable ``twin_state_id`` column with NO foreign key yet — the
  FK is added in Phase-1.2c once ``twin_states`` exists.
* Plan status is bounded to ``active | superseded | completed``.
* Supersession is non-destructive: there is no ``deleted_at`` column,
  and superseded plans keep their rows.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import GoalType, TrainingGoalStatus, TrainingPlanStatus
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan


TABLE = "training_plans"


def _sync_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://",
            "postgresql+psycopg2://",
        )
    return database_url


def _columns(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_columns(table))
    finally:
        engine.dispose()


def _foreign_keys(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_foreign_keys(table))
    finally:
        engine.dispose()


def _indexes(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_indexes(table))
    finally:
        engine.dispose()


async def _new_athlete(db_session: AsyncSession, email: str) -> Athlete:
    athlete = Athlete(email=email)
    db_session.add(athlete)
    await db_session.flush()
    return athlete


async def _new_goal(
    db_session: AsyncSession,
    athlete_id: uuid.UUID,
    *,
    status: TrainingGoalStatus = TrainingGoalStatus.ACTIVE,
) -> TrainingGoal:
    goal = TrainingGoal(
        athlete_id=athlete_id,
        goal_type=GoalType.FITNESS_IMPROVEMENT,
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=status,
    )
    db_session.add(goal)
    await db_session.flush()
    return goal


def _plan_factory(
    *,
    training_goal_id: uuid.UUID,
    status: TrainingPlanStatus = TrainingPlanStatus.ACTIVE,
    twin_state_id: uuid.UUID | None = None,
    strategic_rationale: dict | None = None,
) -> TrainingPlan:
    return TrainingPlan(
        training_goal_id=training_goal_id,
        twin_state_id=twin_state_id,
        status=status,
        strategic_rationale=strategic_rationale,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestTrainingPlanDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "training_goal_id",
            "twin_state_id",
            "phases_summary",
            "phase_definitions",
            "weekly_distributions",
            "status",
            "superseded_at",
            "created_at",
            "strategic_rationale",
            "checkpoint_schedule",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in _columns(TABLE)}
        assert expected_column in cols, (
            f"training_plans.{expected_column} missing from DB schema."
        )

    async def test_twin_state_id_is_uuid_nullable(
        self, db_session: AsyncSession
    ) -> None:
        cols = {col["name"]: col for col in _columns(TABLE)}
        col = cols["twin_state_id"]
        assert col["nullable"] is True
        type_name = col["type"].__class__.__name__.upper()
        assert type_name in {"UUID", "PG_UUID"}, (
            f"training_plans.twin_state_id must be a UUID column. "
            f"Got: {col['type']!r}"
        )


# ---------------------------------------------------------------------------
# Twin-state FK is intentionally absent.
# ---------------------------------------------------------------------------


class TestTrainingPlanTwinStateFKWired:
    """Phase-1.2c wires the ``training_plans.twin_state_id -> twin_states.id``
    FK that was deferred in Phase-1.2b. Once ``twin_states`` exists, the FK
    is enforced at the DB layer.

    Reference: docs/implementation/phase-1/
    phase-1-2c-p1-twin-fitness-coaching-workouts.md
    """

    def test_fk_to_twin_states_present(self) -> None:
        """Phase-1.2c must declare an FK from training_plans.twin_state_id
        to twin_states.id."""
        fks = _foreign_keys(TABLE)
        matches = [
            fk
            for fk in fks
            if fk.get("referred_table") == "twin_states"
            and tuple(fk.get("constrained_columns") or ())
            == ("twin_state_id",)
        ]
        assert matches, (
            "Phase-1.2c must wire training_plans.twin_state_id -> "
            "twin_states.id as a foreign key. "
            f"Got: {[fk.get('referred_table') for fk in fks]}"
        )

    def test_twin_state_fk_ondelete_in_pg_catalog(self) -> None:
        """The FK ON DELETE behaviour is encoded as
        ``pg_constraint.confdeltype``. Pin the value so a Phase-1.2c
        migration that wires the FK with an unexpected cascade
        mode (e.g. RESTRICT) fails this tripwire."""
        from sqlalchemy import text

        engine = create_engine(_sync_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT c.confdeltype,
                               pg_get_constraintdef(c.oid) AS constraint_def
                        FROM pg_constraint c
                        JOIN pg_class conrelid_table
                          ON conrelid_table.oid = c.conrelid
                        JOIN pg_class confrelid_table
                          ON confrelid_table.oid = c.confrelid
                        WHERE c.contype = 'f'
                          AND confrelid_table.relname = 'twin_states'
                          AND conrelid_table.relname = :table_name
                        """
                    ),
                    {"table_name": TABLE},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None, (
            "training_plans.twin_state_id -> twin_states.id FK must "
            "exist on the migrated schema."
        )
        # PostgreSQL pg_constraint.confdeltype codes:
        # 'a' = NO ACTION (default).
        # 'r' = RESTRICT.
        # 'c' = CASCADE.
        # 'n' = SET NULL.
        # 'd' = SET DEFAULT.
        # The architecture pins SET NULL so deleting a TwinState
        # preserves the TrainingPlan row with twin_state_id NULL.
        assert row[0] == "n", (
            f"training_plans.twin_state_id FK ON DELETE must be SET "
            f"NULL so deleting a TwinState preserves the TrainingPlan "
            f"row. Got confdeltype={row[0]!r}, "
            f"constraint_def={row[1]!r}"
        )

    async def test_null_twin_state_id_persists(
        self, db_session: AsyncSession
    ) -> None:
        """NULL twin_state_id is permitted (twin_states may not yet
        exist for the goal)."""
        athlete = await _new_athlete(
            db_session, "twin-state-nullable@example.com"
        )
        goal = await _new_goal(db_session, athlete.id)
        plan = _plan_factory(
            training_goal_id=goal.id,
            twin_state_id=None,
        )
        db_session.add(plan)
        await db_session.flush()
        await db_session.refresh(plan)
        assert plan.twin_state_id is None

    async def test_random_uuid_in_twin_state_id_rejected(
        self, db_session: AsyncSession
    ) -> None:
        """Phase-1.2c wires the FK — a random UUID with no
        twin_states row must raise IntegrityError."""
        athlete = await _new_athlete(
            db_session, "twin-state-deferred@example.com"
        )
        goal = await _new_goal(db_session, athlete.id)
        plan = _plan_factory(
            training_goal_id=goal.id,
            twin_state_id=uuid.uuid4(),  # no twin_states row exists
        )
        db_session.add(plan)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# FK to training_goals with CASCADE.
# ---------------------------------------------------------------------------


class TestTrainingPlanGoalForeignKey:
    def test_training_goal_id_fk_to_training_goals(self) -> None:
        fks = _foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "training_goals"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_goal_id",)
        ]
        assert matches, (
            "training_plans.training_goal_id must reference "
            "training_goals(id). Got: "
            f"{[f for f in fks]}"
        )

    def test_training_goal_id_fk_cascade_in_pg_catalog(self) -> None:
        """``ondelete='CASCADE'`` is a name-independent catalog fact:
        ``pg_constraint.confdeltype='c'`` for the FK row above."""
        from sqlalchemy import text

        engine = create_engine(_sync_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT c.confdeltype,
                               pg_get_constraintdef(c.oid) AS constraint_def
                        FROM pg_constraint c
                        JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
                        JOIN pg_class confrelid_table ON confrelid_table.oid = c.confrelid
                        WHERE c.contype = 'f'
                          AND confrelid_table.relname = 'training_goals'
                          AND conrelid_table.relname = 'training_plans'
                        """
                    )
                ).fetchone()
        finally:
            engine.dispose()

        assert row is not None, (
            "training_plans.training_goal_id FK must exist in "
            "pg_constraint pointing to training_goals."
        )
        confdeltype, constraint_def = row
        assert confdeltype == "c", (
            "training_plans.training_goal_id FK must CASCADE on delete. "
            f"Got confdeltype={confdeltype!r}, def={constraint_def}"
        )

    async def test_cascade_delete_with_training_goal(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "cascade-plan-goal@example.com")
        goal = await _new_goal(db_session, athlete.id)
        plan = _plan_factory(training_goal_id=goal.id)
        db_session.add(plan)
        await db_session.flush()
        plan_id = plan.id

        from sqlalchemy import delete as sa_delete, select

        await db_session.execute(
            sa_delete(TrainingGoal).where(TrainingGoal.id == goal.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(TrainingPlan).where(TrainingPlan.id == plan_id)
        )
        assert remaining.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# JSONB defaults on the structural columns.
# ---------------------------------------------------------------------------


class TestTrainingPlanJSONBDefaults:
    """Empty-list defaults are server-applied so a freshly-inserted
    training_plans row has the expected JSONB shape.

    Per architecture docs, the structural columns default to ``[]`` so
    ``jsonb_set`` operations from later services can append without a
    coalesce."""

    async def test_plan_persists_with_empty_jsonb_defaults(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "jsonb-defaults@example.com")
        goal = await _new_goal(db_session, athlete.id)
        plan = _plan_factory(training_goal_id=goal.id)
        db_session.add(plan)
        await db_session.flush()
        await db_session.refresh(plan)
        assert plan.phases_summary == []
        assert plan.phase_definitions == []
        assert plan.weekly_distributions == []
        assert plan.checkpoint_schedule == []

    async def test_plan_persists_with_populated_jsonb(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "jsonb-populated@example.com")
        goal = await _new_goal(db_session, athlete.id)
        phases = [
            {
                "label": "aerobic_base",
                "start_date": "2026-06-01",
                "end_date": "2026-07-15",
                "weeks": 6,
                "primary_focus": "aerobic_base",
                "weekly_session_count": 5,
            },
        ]
        rationale = {
            "goal_mode": "fitness_improvement",
            "primary_objectives": ["aerobic_base"],
            "constraints": ["no_double_days"],
            "adaptation_rationale": [],
        }
        plan = _plan_factory(
            training_goal_id=goal.id,
            strategic_rationale=rationale,
        )
        plan.phases_summary = phases
        plan.phase_definitions = [
            {
                "label": "aerobic_base",
                "session_density_per_week": 5,
                "primary_zone": "aerobic",
                "intensity_budget": {"hard": 0.05, "moderate": 0.20, "easy": 0.75},
                "weekly_focus_progression": [],
            }
        ]
        plan.weekly_distributions = [{"week_number": 1, "intensity": "easy"}]
        plan.checkpoint_schedule = [
            {
                "type": "calibration",
                "target_metric": "max_hr",
                "secondary_metrics": ["hr_dropout_pct"],
            }
        ]
        db_session.add(plan)
        await db_session.flush()
        await db_session.refresh(plan)
        assert plan.phases_summary == phases
        assert plan.strategic_rationale == rationale
        assert plan.weekly_distributions[0]["intensity"] == "easy"
        assert plan.checkpoint_schedule[0]["type"] == "calibration"


# ---------------------------------------------------------------------------
# Supersession is non-destructive.
# ---------------------------------------------------------------------------


class TestTrainingPlanSupersession:
    """Old plans transition to ``superseded`` rather than being
    deleted. ``superseded_at`` records the moment of replacement."""

    async def test_supersede_path_zero_or_no_delete(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "supersede@example.com")
        goal = await _new_goal(db_session, athlete.id)
        plan_old = _plan_factory(training_goal_id=goal.id)
        db_session.add(plan_old)
        await db_session.flush()

        # Replace with a new plan; mark the old one supersedede.
        plan_new = _plan_factory(
            training_goal_id=goal.id,
            status=TrainingPlanStatus.ACTIVE,
        )
        plan_old.status = TrainingPlanStatus.SUPERSEDED
        plan_old.superseded_at = datetime.now(timezone.utc)
        db_session.add(plan_new)
        await db_session.flush()

        await db_session.refresh(plan_old)
        await db_session.refresh(plan_new)
        assert plan_old.status is TrainingPlanStatus.SUPERSEDED
        assert plan_old.superseded_at is not None
        assert plan_new.status is TrainingPlanStatus.ACTIVE
        # Both rows survive — no delete occurred.
        assert plan_old.id != plan_new.id

    async def test_no_deleted_at_column(self) -> None:
        cols = {col["name"] for col in _columns(TABLE)}
        assert "deleted_at" not in cols, (
            "training_plans.deleted_at must NOT exist — plans are "
            "superseded, not deleted."
        )


# ---------------------------------------------------------------------------
# Indexes.
# ---------------------------------------------------------------------------


class TestTrainingPlanIndexes:
    def test_goal_status_index_present(self) -> None:
        matched = [
            idx
            for idx in _indexes(TABLE)
            if set(idx.get("column_names") or []) >= {
                "training_goal_id",
                "status",
            }
        ]
        assert matched, (
            "Expected an index on (training_goal_id, status) for the "
            "current-plan lookup query."
        )

    def test_twin_state_index_present(self) -> None:
        """Reverse-lookup TwinState → plans uses the (deferred) FK."""
        matched = [
            idx
            for idx in _indexes(TABLE)
            if set(idx.get("column_names") or []) >= {"twin_state_id"}
        ]
        assert matched, (
            "Expected an index on (twin_state_id) for "
            "reverse-lookup even though the FK is added in Phase-1.2c."
        )
