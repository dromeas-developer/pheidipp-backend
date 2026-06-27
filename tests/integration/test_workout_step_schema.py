"""Integration tests for the ``WorkoutStep`` schema at the DB level.

Phase-1.2c introduces the ``workout_steps`` table — one ordered
segment inside a ``GeneratedWorkout``. Carries the three-layer
hierarchy (``session_type`` / ``physiological_intent`` /
``session_purpose``), the range-bearing ``WorkoutTarget`` JSONB, the
duration, and a plain-English description.

The DB-level invariants codified here:

* UNIQUE ``(generated_workout_id, step_order)`` — one step per
  order position per workout.
* CHECK ``step_order >= 1`` — 1-indexed and positive.
* CHECK ``duration_seconds IS NULL OR >= 0`` — non-negative when
  present.
* CHECK ``length(description) > 0`` — non-empty description.
* FK ``generated_workout_id`` ON DELETE CASCADE.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import (
    DataTier,
    GoalType,
    PhysiologicalIntent,
    PlannedSessionStatus,
    RecoveryModifierLevel,
    SessionPriority,
    SessionPurpose,
    SessionSlot,
    SessionType,
    StepType,
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
from app.models.workout_step import WorkoutStep
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_columns,
    db_foreign_keys,
    db_indexes,
    db_unique_constraints,
    get_sync_database_url,
)

TABLE = "workout_steps"


# ---------------------------------------------------------------------------
# Helpers — build the parent chain (athlete → goal → plan → week →
# session → workout) so a ``WorkoutStep`` can be inserted.
# ---------------------------------------------------------------------------

async def _new_full_chain(
    db_session: AsyncSession, athlete: Athlete
) -> tuple[GeneratedWorkout, TrainingGoal]:
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

    workout = GeneratedWorkout(
        planned_session_id=session.id,
        twin_state_id=state.id,
        theoretical_targets={"targets": [], "description": "stub"},
        adjusted_targets={"targets": [], "description": "stub"},
        generation_date=date(2026, 6, 24),
    )
    db_session.add(workout)
    await db_session.flush()
    return workout, goal


def _default_target() -> dict:
    return {
        "signal_type": "hr",
        "primary": {"min": 130, "max": 145, "unit": "bpm"},
        "fallback": None,
        "description": "Keep heart rate in aerobic zone",
    }


def _workout_step_factory(
    *,
    generated_workout_id: uuid.UUID,
    step_order: int,
    step_type: StepType = StepType.WORK,
    session_type: SessionType = SessionType.EASY_RUN,
    physiological_intent: PhysiologicalIntent = PhysiologicalIntent.LOW_AEROBIC,
    session_purpose: SessionPurpose = SessionPurpose.GENERAL,
    target: dict | None = None,
    duration_seconds: int | None = 1800,
    description: str = "20-minute easy aerobic run",
) -> WorkoutStep:
    return WorkoutStep(
        generated_workout_id=generated_workout_id,
        step_order=step_order,
        step_type=step_type,
        session_type=session_type,
        physiological_intent=physiological_intent,
        session_purpose=session_purpose,
        target=target or _default_target(),
        duration_seconds=duration_seconds,
        description=description,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestWorkoutStepDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "generated_workout_id",
            "step_order",
            "step_type",
            "session_type",
            "physiological_intent",
            "session_purpose",
            "target",
            "duration_seconds",
            "description",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"workout_steps.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# UNIQUE (generated_workout_id, step_order).
# ---------------------------------------------------------------------------


class TestWorkoutStepStepOrderUniqueDB:
    def test_step_order_unique_constraint_present(self) -> None:
        uniques = db_unique_constraints(TABLE)
        matched = [
            u
            for u in uniques
            if tuple(u.get("column_names") or ())
            == ("generated_workout_id", "step_order")
            and u.get("name")
            == "uq_workout_steps_generated_workout_step_order"
        ]
        assert matched, (
            "workout_steps must declare UNIQUE "
            "(generated_workout_id, step_order). "
            f"Got: {[u.get('column_names') for u in uniques]}"
        )

    async def test_duplicate_step_order_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-dup-step@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)

        s1 = _workout_step_factory(
            generated_workout_id=workout.id, step_order=1
        )
        s2 = _workout_step_factory(
            generated_workout_id=workout.id, step_order=1
        )
        db_session.add_all([s1, s2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_distinct_step_orders_coexist(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-distinct-orders@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)

        warmup = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            step_type=StepType.WARMUP,
            description="10-minute easy warmup",
            duration_seconds=600,
        )
        work = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=2,
            step_type=StepType.WORK,
            description="20-minute main set",
            duration_seconds=1200,
        )
        cooldown = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=3,
            step_type=StepType.COOLDOWN,
            description="10-minute easy cooldown",
            duration_seconds=600,
        )
        db_session.add_all([warmup, work, cooldown])
        await db_session.flush()
        await db_session.refresh(warmup)
        await db_session.refresh(work)
        await db_session.refresh(cooldown)
        assert warmup.id != work.id != cooldown.id


# ---------------------------------------------------------------------------
# CHECK — step_order >= 1.
# ---------------------------------------------------------------------------


class TestWorkoutStepStepOrderCheckDB:
    async def test_step_order_zero_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-step-zero@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id, step_order=0
        )
        db_session.add(s)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_step_order_negative_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-step-neg@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id, step_order=-1
        )
        db_session.add(s)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_step_order_one_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-step-one@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id, step_order=1
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.step_order == 1


# ---------------------------------------------------------------------------
# CHECK — duration_seconds non-negative.
# ---------------------------------------------------------------------------


class TestWorkoutStepDurationCheckDB:
    async def test_negative_duration_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-neg-duration@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            duration_seconds=-100,
        )
        db_session.add(s)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_zero_duration_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-zero-duration@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            duration_seconds=0,
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.duration_seconds == 0

    async def test_null_duration_accepted(
        self, db_session: AsyncSession
    ) -> None:
        """NULL is permitted — warmup / cooldown can be null for some
        workout variants. The CHECK constraint short-circuits on NULL."""
        athlete = await make_athlete(
            db_session, "ws-null-duration@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            duration_seconds=None,
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.duration_seconds is None


# ---------------------------------------------------------------------------
# CHECK — description non-empty.
# ---------------------------------------------------------------------------


class TestWorkoutStepDescriptionCheckDB:
    async def test_empty_description_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-empty-desc@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            description="",
        )
        db_session.add(s)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestWorkoutStepForeignKeysDB:
    def test_generated_workout_id_fk_to_generated_workouts(self) -> None:
        fks = db_foreign_keys(TABLE)
        workout_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "generated_workouts"
            and tuple(fk.get("constrained_columns") or ())
            == ("generated_workout_id",)
        ]
        assert workout_fks

    def test_generated_workout_fk_ondelete_is_cascade(self) -> None:
        engine = create_engine(get_sync_database_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT c.confdeltype
                        FROM pg_constraint c
                        JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
                        JOIN pg_class confrelid_table ON confrelid_table.oid = c.confrelid
                        WHERE c.contype = 'f'
                          AND confrelid_table.relname = 'generated_workouts'
                          AND conrelid_table.relname = :table_name
                        """
                    ),
                    {"table_name": TABLE},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None
        assert row[0] == "c", (
            f"workout_steps.generated_workout_id FK ON DELETE "
            f"must be CASCADE. Got {row[0]!r}"
        )


# ---------------------------------------------------------------------------
# Server default — session_purpose defaults to 'general'.
# ---------------------------------------------------------------------------


class TestWorkoutStepServerDefaultsDB:
    async def test_session_purpose_defaults_to_general(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-default-purpose@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        # Omit session_purpose — let the server_default fire.
        s = WorkoutStep(
            generated_workout_id=workout.id,
            step_order=1,
            step_type=StepType.WORK,
            session_type=SessionType.EASY_RUN,
            physiological_intent=PhysiologicalIntent.LOW_AEROBIC,
            target=_default_target(),
            duration_seconds=600,
            description="Easy aerobic",
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.session_purpose == SessionPurpose.GENERAL


# ---------------------------------------------------------------------------
# Three-layer hierarchy — different StepType / session_type /
# physiological_intent combinations round-trip.
# ---------------------------------------------------------------------------


class TestWorkoutStepThreeLayerHierarchyDB:
    async def test_warmup_step_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-warmup@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            step_type=StepType.WARMUP,
            physiological_intent=PhysiologicalIntent.RECOVERY,
            description="10-minute warmup",
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.step_type == StepType.WARMUP
        assert s.physiological_intent == PhysiologicalIntent.RECOVERY

    async def test_work_step_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-work@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=2,
            step_type=StepType.WORK,
            session_type=SessionType.VO2MAX,
            physiological_intent=PhysiologicalIntent.VO2MAX,
            description="5x3min hard",
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.step_type == StepType.WORK
        assert s.session_type == SessionType.VO2MAX
        assert s.physiological_intent == PhysiologicalIntent.VO2MAX

    async def test_cooldown_step_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-cooldown@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=3,
            step_type=StepType.COOLDOWN,
            physiological_intent=PhysiologicalIntent.RECOVERY,
            description="10-minute cooldown",
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.step_type == StepType.COOLDOWN
        assert s.physiological_intent == PhysiologicalIntent.RECOVERY

    async def test_race_specific_session_purpose_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        """``race_specific`` is a SessionPurpose annotation — used to
        distinguish race-specific sessions from generic easy runs."""
        athlete = await make_athlete(
            db_session, "ws-race-specific@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            session_purpose=SessionPurpose.RACE_SPECIFIC,
            description="Race-pace intervals",
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.session_purpose == SessionPurpose.RACE_SPECIFIC

    async def test_calibration_session_purpose_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        """``calibration`` annotates test sessions — compliance
        family uses data-quality assessment instead of standard
        compliance assessment."""
        athlete = await make_athlete(
            db_session, "ws-calibration@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            session_type=SessionType.TEST_SESSION,
            session_purpose=SessionPurpose.CALIBRATION,
            description="Threshold test",
        )
        db_session.add(s)
        await db_session.flush()
        await db_session.refresh(s)
        assert s.session_purpose == SessionPurpose.CALIBRATION


# ---------------------------------------------------------------------------
# Ordered read index.
# ---------------------------------------------------------------------------


class TestWorkoutStepOrderedReadIndexDB:
    async def test_ordered_read_index_present(
        self, db_session: AsyncSession
    ) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ())
            == {"generated_workout_id", "step_order"}
        ]
        assert matched, (
            "Expected an index on (generated_workout_id, step_order) "
            "for the ordered read pattern."
        )


# ---------------------------------------------------------------------------
# Round-trip persistence.
# ---------------------------------------------------------------------------


class TestWorkoutStepRoundTripDB:
    async def test_full_step_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ws-roundtrip@example.com"
        )
        workout, _ = await _new_full_chain(db_session, athlete)

        target = {
            "signal_type": "hr",
            "primary": {"min": 130, "max": 145, "unit": "bpm"},
            "fallback": {
                "signal_type": "pace",
                "primary": {"min": 270, "max": 300, "unit": "sec/km"},
                "fallback": None,
                "description": "Conversational pace",
            },
            "description": "Easy aerobic",
        }
        s = _workout_step_factory(
            generated_workout_id=workout.id,
            step_order=1,
            step_type=StepType.WORK,
            session_type=SessionType.TEMPO,
            physiological_intent=PhysiologicalIntent.THRESHOLD,
            session_purpose=SessionPurpose.GENERAL,
            target=target,
            duration_seconds=1800,
            description="30-minute tempo",
        )
        db_session.add(s)
        await db_session.flush()
        s_id = s.id

        from sqlalchemy import select

        result = await db_session.execute(
            select(WorkoutStep).where(WorkoutStep.id == s_id)
        )
        loaded = result.scalar_one()
        assert loaded.step_type == StepType.WORK
        assert loaded.session_type == SessionType.TEMPO
        assert loaded.physiological_intent == PhysiologicalIntent.THRESHOLD
        assert loaded.session_purpose == SessionPurpose.GENERAL
        assert loaded.target == target
        assert loaded.duration_seconds == 1800
        assert loaded.description == "30-minute tempo"
        assert loaded.step_order == 1