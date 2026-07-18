"""Integration tests for the ``GeneratedWorkout`` schema at the DB level.

Phase-1.2c introduces the ``generated_workouts`` table — an
append-only day-of-workout record attached to a PlannedSession with
the two-column ``TargetSet`` JSONB shape (theoretical / adjusted).

The DB-level invariants codified here:

* UNIQUE ``(planned_session_id, generation_date)`` — idempotency
  contract for the workout generation pipeline.
* CHECK ``ck_generated_workouts_targets_are_objects`` — both
  ``theoretical_targets`` and ``adjusted_targets`` must be JSONB
  objects.
* CHECK ``ck_generated_workouts_recovery_modifier_level_valid`` —
  bounded to ``green|amber|red``.
* ``recovery_modifier_level`` server_default is ``green``.
* FK ``planned_session_id`` ON DELETE CASCADE; FK ``twin_state_id``
  ON DELETE CASCADE.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import (
    DataTier,
    GoalType,
    PlannedSessionStatus,
    RecoveryModifierLevel,
    SessionPriority,
    SessionSlot,
    SessionType,
    TwinConfidenceLevel,
    TwinTrigger,
    TrainingGoalStatus,
    TrainingPlanStatus,
)
from app.models.generated_workout import GeneratedWorkout
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_check_constraints,
    db_columns,
    db_foreign_keys,
    db_indexes,
    db_unique_constraints,
)


TABLE = "generated_workouts"


# ---------------------------------------------------------------------------
# Helpers — build up the parent chain (athlete → goal → plan → week →
# session) so that a ``GeneratedWorkout`` can be inserted.
# ---------------------------------------------------------------------------


async def _new_goal_plan_week_session(
    db_session: AsyncSession, athlete: Athlete
) -> tuple[TrainingGoal, TrainingPlan, WeeklyPlan, PlannedSession]:
    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.FITNESS_IMPROVEMENT,
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()

    plan = TrainingPlan(
        training_goal_id=goal.id, status=TrainingPlanStatus.ACTIVE,
    )
    db_session.add(plan)
    await db_session.flush()

    week = WeeklyPlan(
        training_plan_id=plan.id,
        week_number=1,
        adjusted_intent={"session_count": 5},
        status="synthesised",
        week_starts_at=date(2026, 6, 22),
        week_ends_at=date(2026, 6, 28),
    )
    db_session.add(week)
    await db_session.flush()

    session = PlannedSession(
        weekly_plan_id=week.id,
        training_plan_id=plan.id,
        target_date=date(2026, 6, 24),
        week_number=1,
        phase_label="aerobic_base",
        session_type=SessionType.EASY_RUN,
        intent_description="comfortable aerobic",
        approximate_duration_minutes=45,
        status=PlannedSessionStatus.PENDING,
        session_slot=SessionSlot.AM,
        session_priority=SessionPriority.PRIMARY,
    )
    db_session.add(session)
    await db_session.flush()
    return goal, plan, week, session


async def _new_twin_state(
    db_session: AsyncSession,
    athlete: Athlete,
    goal: TrainingGoal,
) -> TwinState:
    state = TwinState(
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        data_tier=DataTier.TIER_5,
        confidence_level=TwinConfidenceLevel.LOW,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1.0",
        fitness=0.0,
        fatigue=0.0,
        form=0.0,
        readiness_level=RecoveryModifierLevel.GREEN,
        metric_confidence={},
    )
    db_session.add(state)
    await db_session.flush()
    return state


def _default_targets() -> dict[str, Any]:
    """A typical TargetSet JSONB shape — targets list + description."""
    return {
        "targets": [
            {
                "signal_type": "gap",
                "primary": {"min": 270, "max": 300, "unit": "sec/km"},
                "fallback": None,
                "description": "Easy aerobic pace",
            }
        ],
        "description": "Recovery run at conversational pace",
    }


def _generated_workout_factory(
    *,
    planned_session_id: uuid.UUID,
    twin_state_id: uuid.UUID,
    theoretical_targets: object = None,
    adjusted_targets: object = None,
    recovery_modifier_level: RecoveryModifierLevel = RecoveryModifierLevel.GREEN,
    recovery_modifier_reason: str | None = None,
    generation_date: date = date(2026, 6, 24),
) -> GeneratedWorkout:
    return GeneratedWorkout(
        planned_session_id=planned_session_id,
        twin_state_id=twin_state_id,
        theoretical_targets=theoretical_targets or _default_targets(),
        adjusted_targets=adjusted_targets or _default_targets(),
        recovery_modifier_level=recovery_modifier_level,
        recovery_modifier_reason=recovery_modifier_reason,
        generation_date=generation_date,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "planned_session_id",
            "twin_state_id",
            "theoretical_targets",
            "adjusted_targets",
            "recovery_modifier_level",
            "recovery_modifier_reason",
            "generation_date",
            "generated_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"generated_workouts.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# UNIQUE (planned_session_id, generation_date) — idempotency.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutIdempotencyUniqueDB:
    def test_idempotency_unique_constraint_present(self) -> None:
        uniques = db_unique_constraints(TABLE)
        matched = [
            u
            for u in uniques
            if tuple(u.get("column_names") or ())
            == ("planned_session_id", "generation_date")
            and u.get("name")
            == "uq_generated_workouts_planned_session_generation_date"
        ]
        assert matched, (
            "generated_workouts must declare UNIQUE "
            "(planned_session_id, generation_date). "
            f"Got: {[u.get('column_names') for u in uniques]}"
        )

    async def test_duplicate_session_date_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "gw-dup@example.com"
        )
        _, _, _, session = await _new_goal_plan_week_session(
            db_session, athlete
        )
        goal = await db_session.get(TrainingGoal, None)  # ignored, just placeholder
        # re-fetch goal directly:

        result = await db_session.execute(
            select(TrainingGoal).where(
                TrainingGoal.athlete_id == athlete.id
            )
        )
        goal = result.scalar_one()
        state = await _new_twin_state(db_session, athlete, goal)

        w1 = _generated_workout_factory(
            planned_session_id=session.id,
            twin_state_id=state.id,
            generation_date=date(2026, 6, 24),
        )
        w2 = _generated_workout_factory(
            planned_session_id=session.id,
            twin_state_id=state.id,
            generation_date=date(2026, 6, 24),
        )
        db_session.add_all([w1, w2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_same_session_different_dates_coexist(
        self, db_session: AsyncSession
    ) -> None:
        """Two workouts for the same planned session on different
        generation dates coexist (the next day's regeneration)."""
        athlete = await make_athlete(
            db_session, "gw-multi-date@example.com"
        )
        _, _, _, session = await _new_goal_plan_week_session(
            db_session, athlete
        )

        result = await db_session.execute(
            select(TrainingGoal).where(
                TrainingGoal.athlete_id == athlete.id
            )
        )
        goal = result.scalar_one()
        state = await _new_twin_state(db_session, athlete, goal)

        w1 = _generated_workout_factory(
            planned_session_id=session.id,
            twin_state_id=state.id,
            generation_date=date(2026, 6, 24),
        )
        w2 = _generated_workout_factory(
            planned_session_id=session.id,
            twin_state_id=state.id,
            generation_date=date(2026, 6, 25),
        )
        db_session.add_all([w1, w2])
        await db_session.flush()
        await db_session.refresh(w1)
        await db_session.refresh(w2)
        assert w1.id != w2.id


# ---------------------------------------------------------------------------
# CHECK — JSONB target objects.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutTargetsAreObjectsCheckDB:
    def test_targets_are_objects_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "jsonb_typeof" in (c.get("sqltext") or "").lower()
            and "theoretical_targets" in (c.get("sqltext") or "").lower()
            and "adjusted_targets" in (c.get("sqltext") or "").lower()
            and "object" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "generated_workouts must declare CHECK constraint "
            "enforcing `jsonb_typeof(theoretical_targets) = 'object' AND "
            "jsonb_typeof(adjusted_targets) = 'object'`."
        )

    async def test_non_object_targets_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "gw-bad-targets@example.com"
        )
        _, _, _, session = await _new_goal_plan_week_session(
            db_session, athlete
        )

        result = await db_session.execute(
            select(TrainingGoal).where(
                TrainingGoal.athlete_id == athlete.id
            )
        )
        goal = result.scalar_one()
        state = await _new_twin_state(db_session, athlete, goal)

        w = _generated_workout_factory(
            planned_session_id=session.id,
            twin_state_id=state.id,
            theoretical_targets=[1, 2, 3],  # not an object — array
            adjusted_targets=_default_targets(),
        )
        db_session.add(w)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# CHECK — recovery_modifier_level valid.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutRecoveryModifierLevelCheckDB:
    def test_modifier_level_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "recovery_modifier_level" in (c.get("sqltext") or "").lower()
            and "green" in (c.get("sqltext") or "").lower()
            and "amber" in (c.get("sqltext") or "").lower()
            and "red" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "generated_workouts must declare CHECK constraint "
            "bounding `recovery_modifier_level` to "
            "`green|amber|red`."
        )


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutForeignKeysDB:
    def test_planned_session_id_fk_to_planned_sessions(self) -> None:
        fks = db_foreign_keys(TABLE)
        session_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "planned_sessions"
            and tuple(fk.get("constrained_columns") or ())
            == ("planned_session_id",)
        ]
        assert session_fks

    def test_twin_state_id_fk_to_twin_states(self) -> None:
        fks = db_foreign_keys(TABLE)
        twin_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "twin_states"
            and tuple(fk.get("constrained_columns") or ())
            == ("twin_state_id",)
        ]
        assert twin_fks, (
            "generated_workouts.twin_state_id must reference twin_states(id)."
        )

    def test_planned_session_fk_ondelete_is_cascade(self) -> None:
        fks = db_foreign_keys(TABLE)
        session_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "planned_sessions"
            and tuple(fk.get("constrained_columns") or ())
            == ("planned_session_id",)
        ]
        assert session_fks, (
            "generated_workouts.planned_session_id FK ON DELETE "
            "must be CASCADE."
        )
        assert session_fks[0].get("options", {}).get("ondelete") == "CASCADE"

    def test_twin_state_fk_ondelete_is_cascade(self) -> None:
        fks = db_foreign_keys(TABLE)
        twin_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "twin_states"
            and tuple(fk.get("constrained_columns") or ())
            == ("twin_state_id",)
        ]
        assert twin_fks, (
            "generated_workouts.twin_state_id FK ON DELETE must be CASCADE."
        )
        assert twin_fks[0].get("options", {}).get("ondelete") == "CASCADE"


# ---------------------------------------------------------------------------
# Read-pattern indexes.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutSecondaryIndexesDB:
    async def test_twin_state_reverse_lookup_index_present(
        self, db_session: AsyncSession
    ) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ()) == {"twin_state_id"}
        ]
        assert matched, (
            "Expected an index on (twin_state_id) for reverse lookup."
        )

    async def test_planned_session_generated_index_present(
        self, db_session: AsyncSession
    ) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ())
            == {"planned_session_id", "generated_at"}
        ]
        assert matched, (
            "Expected an index on (planned_session_id, generated_at) "
            "for the today-view fast path."
        )


# ---------------------------------------------------------------------------
# Server default — recovery_modifier_level defaults to 'green'.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutServerDefaultsDB:
    async def test_recovery_modifier_level_defaults_to_green(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "gw-default-modifier@example.com"
        )
        _, _, _, session = await _new_goal_plan_week_session(
            db_session, athlete
        )

        result = await db_session.execute(
            select(TrainingGoal).where(
                TrainingGoal.athlete_id == athlete.id
            )
        )
        goal = result.scalar_one()
        state = await _new_twin_state(db_session, athlete, goal)

        # Omit recovery_modifier_level — let the server_default fire.
        w = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=state.id,
            theoretical_targets=_default_targets(),
            adjusted_targets=_default_targets(),
            generation_date=date(2026, 6, 24),
        )
        db_session.add(w)
        await db_session.flush()
        await db_session.refresh(w)
        assert w.recovery_modifier_level == RecoveryModifierLevel.GREEN


# ---------------------------------------------------------------------------
# Round-trip persistence.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutRoundTripDB:
    async def test_minimal_workout_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "gw-roundtrip@example.com"
        )
        _, _, _, session = await _new_goal_plan_week_session(
            db_session, athlete
        )

        result = await db_session.execute(
            select(TrainingGoal).where(
                TrainingGoal.athlete_id == athlete.id
            )
        )
        goal = result.scalar_one()
        state = await _new_twin_state(db_session, athlete, goal)

        theoretical = {
            "targets": [
                {
                    "signal_type": "hr",
                    "primary": {"min": 130, "max": 145, "unit": "bpm"},
                    "fallback": None,
                    "description": "Easy aerobic",
                }
            ],
            "description": "Easy aerobic run",
        }
        adjusted = {
            "targets": [
                {
                    "signal_type": "hr",
                    "primary": {"min": 125, "max": 140, "unit": "bpm"},
                    "fallback": None,
                    "description": "Reduced pace — wellness amber",
                }
            ],
            "description": "Wellness-adjusted easy aerobic",
        }
        w = _generated_workout_factory(
            planned_session_id=session.id,
            twin_state_id=state.id,
            theoretical_targets=theoretical,
            adjusted_targets=adjusted,
            recovery_modifier_level=RecoveryModifierLevel.AMBER,
            recovery_modifier_reason="wellness_drop_24h",
        )
        db_session.add(w)
        await db_session.flush()
        w_id = w.id

        result = await db_session.execute(
            select(GeneratedWorkout).where(GeneratedWorkout.id == w_id)
        )
        loaded = result.scalar_one()
        assert loaded.theoretical_targets == theoretical
        assert loaded.adjusted_targets == adjusted
        assert loaded.recovery_modifier_level == RecoveryModifierLevel.AMBER
        assert loaded.recovery_modifier_reason == "wellness_drop_24h"
        assert loaded.generation_date == date(2026, 6, 24)

    async def test_identical_targets_allowed(
        self, db_session: AsyncSession
    ) -> None:
        """GREEN modifier, no weather adjustment — both target
        columns identical. The two-column display contract allows
        identical values."""
        athlete = await make_athlete(
            db_session, "gw-identical@example.com"
        )
        _, _, _, session = await _new_goal_plan_week_session(
            db_session, athlete
        )

        result = await db_session.execute(
            select(TrainingGoal).where(
                TrainingGoal.athlete_id == athlete.id
            )
        )
        goal = result.scalar_one()
        state = await _new_twin_state(db_session, athlete, goal)

        targets = _default_targets()
        w = _generated_workout_factory(
            planned_session_id=session.id,
            twin_state_id=state.id,
            theoretical_targets=targets,
            adjusted_targets=targets,  # identical — allowed
            recovery_modifier_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(w)
        await db_session.flush()
        await db_session.refresh(w)
        assert w.theoretical_targets == w.adjusted_targets