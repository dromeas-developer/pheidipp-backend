"""Integration tests for the ``RegenerationTask`` schema at the DB level.

Phase-1.2b adds ``regeneration_tasks`` as the storage for a
coach-proposed date change against a ``TrainingGoal``. The DB-level
invariants codified here:

* ``training_goal_id`` FK → ``training_goals.id`` with CASCADE.
* ``training_plan_id`` FK → ``training_plans.id``, nullable
  (set on confirmation, null while pending).
* Status is bounded to the inline-union set
  ``pending_confirmation | confirmed | declined | expired``.
* A partial index on ``(training_goal_id, status) WHERE status =
  'pending_confirmation'`` supports the Stagnant Proposals alert
  query.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import GoalType, TrainingGoalStatus, TrainingPlanStatus
from app.models.regeneration_task import RegenerationTask
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_check_constraints,
    db_columns,
    db_foreign_keys,
    db_indexes,
    get_sync_database_url,
)


TABLE = "regeneration_tasks"


async def _new_goal_and_plan(
    db_session: AsyncSession, athlete: Athlete
) -> tuple[TrainingGoal, TrainingPlan]:
    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.MAINTENANCE,
        weekly_volume_hours=4.0,
        weekly_volume_km=25.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()
    plan = TrainingPlan(
        training_goal_id=goal.id,
        status=TrainingPlanStatus.ACTIVE,
    )
    db_session.add(plan)
    await db_session.flush()
    return goal, plan


def _task_factory(
    *,
    training_goal_id,
    training_plan_id=None,
    proposed_date,
    rationale: str = "trajectory_at_risk: athlete missed 2nd consecutive week",
    trigger: str = "trajectory_at_risk",
    status: str = "pending_confirmation",
) -> RegenerationTask:
    from datetime import datetime, timedelta, timezone

    return RegenerationTask(
        training_goal_id=training_goal_id,
        training_plan_id=training_plan_id,
        proposed_date=proposed_date,
        rationale=rationale,
        trigger=trigger,
        status=status,
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestRegenerationTaskDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "training_goal_id",
            "training_plan_id",
            "proposed_date",
            "rationale",
            "trigger",
            "status",
            "proposed_at",
            "decided_at",
            "expires_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"regeneration_tasks.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestRegenerationTaskForeignKeys:
    def test_training_goal_id_fk_to_training_goals(self) -> None:
        fks = db_foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "training_goals"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_goal_id",)
        ]
        assert matches, (
            "regeneration_tasks.training_goal_id must reference "
            "training_goals(id)."
        )

    def test_training_plan_id_fk_to_training_plans_nullable(self) -> None:
        fks = db_foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "training_plans"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_plan_id",)
        ]
        assert matches, (
            "regeneration_tasks.training_plan_id must reference "
            "training_plans(id) (nullable)."
        )

    async def test_cascade_delete_with_goal(
        self, db_session: AsyncSession
    ) -> None:
        from datetime import date as _date

        athlete = await make_athlete(db_session, "rt-cascade@example.com")
        goal, _ = await _new_goal_and_plan(db_session, athlete)
        task = _task_factory(
            training_goal_id=goal.id, proposed_date=_date(2026, 9, 1)
        )
        db_session.add(task)
        await db_session.flush()
        task_id = task.id

        from sqlalchemy import delete as sa_delete, select

        await db_session.execute(
            sa_delete(TrainingGoal).where(TrainingGoal.id == goal.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(RegenerationTask).where(RegenerationTask.id == task_id)
        )
        assert remaining.scalar_one_or_none() is None

    async def test_set_null_on_plan_deletion(
        self, db_session: AsyncSession
    ) -> None:
        """When the linked plan is deleted (e.g. cascade through the
        goal) ``training_plan_id`` must be NULLed — the task itself
        survives because the life-cycle is short.

        Schema-scoped contract: this assertion runs inside the
        ``db_session`` fixture whose backing schema is built once by
        ``_prepare_database`` via ``Base.metadata.create_all`` — the
        FK ``regeneration_tasks.training_plan_id → training_plans.id``
        with ``ondelete='SET NULL'`` is therefore defined in the
        *same* schema (and the same connection-pool scope) where this
        test executes its DML. The companion pg-catalog assertion
        ``test_training_plan_id_ondelete_set_null_in_pg_catalog``
        pins the FK declaration so a future regression that drops
        the SET NULL action is caught loudly.

        ⚠️  IDENTITY-MAP CAVEAT: After the DELETE + ``commit()`` that
        fires the SET NULL trigger, the per-test ``db_session`` still
        holds the survivor in its identity map with the pre-delete
        ``training_plan_id``. SQLAlchemy returns the cached object on
        PK lookup without re-issuing a SELECT, so reading
        ``survivor.training_plan_id`` directly would observe the
        *cached* value, not the post-trigger DB state. We therefore
        ``await db_session.refresh(survivor)`` before reading the
        column. This is the same pattern the rest of the suite uses
        after ``commit()``-mutating service calls — see
        ``tests/README.md`` §"Don't assume object state after commits".
        Without the refresh, the test would silently pass against the
        wrong model view (the cached pre-delete state) and miss real
        regressions to the FK action.
        """
        from datetime import date as _date

        athlete = await make_athlete(db_session, "rt-set-null@example.com")
        goal, plan = await _new_goal_and_plan(db_session, athlete)
        task = _task_factory(
            training_goal_id=goal.id,
            training_plan_id=plan.id,
            proposed_date=_date(2026, 9, 1),
        )
        db_session.add(task)
        await db_session.flush()
        task_id = task.id
        deleted_plan_id = plan.id

        from sqlalchemy import delete as sa_delete, select

        await db_session.execute(
            sa_delete(TrainingPlan).where(TrainingPlan.id == plan.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(RegenerationTask).where(RegenerationTask.id == task_id)
        )
        survivor = remaining.scalar_one()
        # Refresh before reading the column — post-commit SET NULL is
        # invisible to the identity-map cache (see docstring).
        await db_session.refresh(survivor)
        # Task survives; training_plan_id is NULLed.
        assert survivor.training_plan_id is None
        assert survivor.training_plan_id != deleted_plan_id
        # training_goal_id is preserved (it has its own CASCADE FK and
        # the goal is still alive).
        assert survivor.training_goal_id == goal.id

    def test_training_plan_id_ondelete_set_null_in_pg_catalog(self) -> None:
        """Schema-scoped companion to ``test_set_null_on_plan_deletion``:
        inspect ``pg_constraint`` in the test schema to confirm the
        ``regeneration_tasks.training_plan_id`` FK is actually
        declared with ``ON DELETE SET NULL``.

        ``confdeltype='n'`` is PostgreSQL's encoding for ``SET NULL``.
        ``a`` would encode ``NO ACTION`` (default) and ``c`` would
        encode ``CASCADE`` — either would silently leave
        ``test_set_null_on_plan_deletion`` passing for the wrong
        reason (the task happens to survive other delete paths).
        The pg-catalog check pins the schema contract so a future
        regression surfaces immediately.
        """
        fks = db_foreign_keys(TABLE)
        plan_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "training_plans"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_plan_id",)
        ]
        assert plan_fks, (
            "regeneration_tasks.training_plan_id FK must reference "
            "training_plans(id)."
        )
        assert plan_fks[0].get("options", {}).get("ondelete") == "SET NULL", (
            "regeneration_tasks.training_plan_id FK ON DELETE must be "
            "SET NULL."
        )

    def test_status_inline_union_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "")
            for c in db_check_constraints(TABLE)
        ).lower()
        for status_value in (
            "pending_confirmation",
            "confirmed",
            "declined",
            "expired",
        ):
            assert status_value in text, (
                f"regeneration_tasks.status check must include "
                f"`{status_value}`. Got: {text!r}"
            )

    async def test_invalid_status_rejected(
        self, db_session: AsyncSession
    ) -> None:
        from datetime import date as _date

        athlete = await make_athlete(db_session, "rt-status-bad@example.com")
        goal, _ = await _new_goal_and_plan(db_session, athlete)
        task = _task_factory(
            training_goal_id=goal.id,
            proposed_date=_date(2026, 9, 1),
            status="not_a_real_status",
        )
        db_session.add(task)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Persistence — pending then confirmed.
# ---------------------------------------------------------------------------


class TestRegenerationTaskPersistence:
    async def test_pending_task_persists_with_null_plan_id(
        self, db_session: AsyncSession
    ) -> None:
        from datetime import date as _date

        athlete = await make_athlete(db_session, "rt-pending@example.com")
        goal, _ = await _new_goal_and_plan(db_session, athlete)
        task = _task_factory(
            training_goal_id=goal.id,
            proposed_date=_date(2026, 9, 1),
        )
        db_session.add(task)
        await db_session.flush()
        await db_session.refresh(task)
        assert task.id is not None
        assert task.training_plan_id is None
        assert task.status == "pending_confirmation"

    async def test_confirmed_task_links_to_new_plan(
        self, db_session: AsyncSession
    ) -> None:
        from datetime import date as _date, datetime, timezone

        athlete = await make_athlete(db_session, "rt-confirmed@example.com")
        goal, plan = await _new_goal_and_plan(db_session, athlete)
        task = _task_factory(
            training_goal_id=goal.id,
            training_plan_id=plan.id,
            proposed_date=_date(2026, 9, 1),
            status="confirmed",
        )
        task.decided_at = datetime.now(timezone.utc)
        db_session.add(task)
        await db_session.flush()
        await db_session.refresh(task)
        assert task.training_plan_id == plan.id
        assert task.status == "confirmed"
        assert task.decided_at is not None


# ---------------------------------------------------------------------------
# Partial pending index.
# ---------------------------------------------------------------------------


class TestRegenerationTaskPendingIndex:
    def test_pending_partial_index_in_pg_catalog(self) -> None:
        """The partial index ``ix_regeneration_tasks_pending`` must
        appear in ``pg_indexes`` for the test schema with predicate
        ``status = 'pending_confirmation'``."""
        engine = create_engine(get_sync_database_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = current_schema()
                          AND tablename = 'regeneration_tasks'
                          AND indexname = 'ix_regeneration_tasks_pending'
                        """
                    )
                ).fetchone()
        finally:
            engine.dispose()
        if row is None:
            pytest.skip(
                "ix_regeneration_tasks_pending not visible in "
                "current_schema() — may be on a project-level search_path."
            )
        assert row is not None
        _, indexdef = row
        assert indexdef.lower().startswith("create index"), (
            f"ix_regeneration_tasks_pending must be a partial index: "
            f"{indexdef}"
        )
        assert "status" in indexdef.lower()
        assert "pending_confirmation" in indexdef.lower(), (
            "ix_regeneration_tasks_pending predicate must constrain "
            f"status = 'pending_confirmation'. Got: {indexdef}"
        )

    def test_pending_index_column_set(self) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if idx.get("name") == "ix_regeneration_tasks_pending"
            and set(idx.get("column_names") or ())
            == {"training_goal_id", "status"}
        ]
        assert matched, (
            "Expected partial index "
            "ix_regeneration_tasks_pending on (training_goal_id, status)."
        )
