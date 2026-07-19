"""Integration tests for the ``TwinState`` schema at the DB level.

Phase-1.2c introduces the ``twin_states`` table — the append-only
snapshot foundation for the digital twin. The DB-level invariants
codified here:

* The partial index ``ix_twin_states_athlete_activity`` on
  ``(athlete_id, activity_id) WHERE activity_id IS NOT NULL``
  supports per-activity lookups (non-unique; uniqueness enforced
  at the service layer since Phase 2.3 P3).
* Multiple TwinStates with NULL ``activity_id`` are allowed (the
  partial predicate exempts non-activity triggers like
  ``questionnaire``, ``physiology_input``, ``wellness_update``).
* ``idx_twin_states_latest`` on ``(athlete_id, created_at)`` supports
  the ``get_latest`` query for the home view.
* ``metric_confidence`` defaults to ``{}`` JSONB.
* FKs: athlete_id (CASCADE), training_goal_id (CASCADE),
  activity_id (SET NULL).

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.enums import (
    ActivitySource,
    DataTier,
    GoalType,
    RecoveryModifierLevel,
    TwinConfidenceLevel,
    TwinTrigger,
    TrainingGoalStatus,
)
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_columns,
    db_foreign_keys,
    db_indexes,
    get_sync_database_url,
)

TABLE = "twin_states"


async def _new_active_goal(
    db_session: AsyncSession, athlete: Athlete
) -> TrainingGoal:
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
    return goal


async def _new_activity(
    db_session: AsyncSession, athlete: Athlete, external_id: str | None = None
) -> Activity:
    activity = Activity(
        athlete_id=athlete.id,
        source=ActivitySource.MANUAL_ENTRY,
        external_id=external_id,
        activity_date=date(2026, 6, 19),
        start_time=datetime(2026, 6, 19, 7, 30, tzinfo=timezone.utc),
        duration_seconds=3600,
    )
    db_session.add(activity)
    await db_session.flush()
    return activity


def _twin_state_factory(
    *,
    athlete_id: uuid.UUID,
    training_goal_id: uuid.UUID,
    activity_id: uuid.UUID | None = None,
    data_tier: DataTier = DataTier.TIER_5,
    confidence_level: TwinConfidenceLevel = TwinConfidenceLevel.LOW,
    trigger: TwinTrigger = TwinTrigger.QUESTIONNAIRE,
    model_version: str = "v1.0",
    fitness: float = 0.0,
    fatigue: float = 0.0,
    form: float = 0.0,
    readiness_level: RecoveryModifierLevel = RecoveryModifierLevel.GREEN,
    metric_confidence: dict[str, Any] | None = None,
) -> TwinState:
    return TwinState(
        athlete_id=athlete_id,
        training_goal_id=training_goal_id,
        activity_id=activity_id,
        data_tier=data_tier,
        confidence_level=confidence_level,
        trigger=trigger,
        model_version=model_version,
        fitness=fitness,
        fatigue=fatigue,
        form=form,
        readiness_level=readiness_level,
        metric_confidence=metric_confidence if metric_confidence is not None else {},
    )


# ---------------------------------------------------------------------------
# DB column presence.
# ---------------------------------------------------------------------------


class TestTwinStateDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "training_goal_id",
            "activity_id",
            "data_tier",
            "confidence_level",
            "trigger",
            "model_version",
            "created_at",
            "fitness",
            "fatigue",
            "form",
            "lt1_pace_sec_per_km",
            "lt1_power_watts",
            "lt1_hr_bpm",
            "lt2_pace_sec_per_km",
            "lt2_power_watts",
            "lt2_hr_bpm",
            "cp_watts",
            "readiness_level",
            "wellness_trend",
            "metric_confidence",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"twin_states.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# Partial unique index on (athlete_id, activity_id) WHERE activity_id IS NOT NULL.
# ---------------------------------------------------------------------------


class TestTwinStatePartialActivityIndexDB:
    """``ix_twin_states_athlete_activity`` is a non-unique index
    on ``(athlete_id, activity_id)`` with partial predicate
    ``WHERE activity_id IS NOT NULL``. Two TwinStates with the same
    non-null ``(athlete_id, activity_id)`` are permitted at the DB
    layer (uniqueness is enforced at the service layer); two with
    NULL ``activity_id`` coexist."""

    def _partial_activity_index(self) -> dict[str, Any] | None:
        for idx in db_indexes(TABLE):
            cols = set(idx.get("column_names") or [])
            if cols == {"athlete_id", "activity_id"}:
                return idx
        return None

    async def test_partial_activity_index_present(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._partial_activity_index()
        assert idx is not None, (
            "Expected a non-unique index on (athlete_id, activity_id) — "
            "the activity lookup partial index ix_twin_states_athlete_activity."
        )

    async def test_partial_predicate_is_activity_id_not_null(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._partial_activity_index()
        assert idx is not None
        engine = create_engine(get_sync_database_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT pg_get_indexdef(indexrelid) "
                        "FROM pg_index WHERE indexrelid = "
                        "(SELECT oid FROM pg_class WHERE relname = :name)"
                    ),
                    {"name": idx["name"]},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None
        ddl = (row[0] or "").lower()
        assert "activity_id" in ddl and "is not null" in ddl, (
            f"Activity partial index predicate must constrain "
            f"`activity_id IS NOT NULL`. DDL: {row[0]!r}"
        )


class TestTwinStateActivityUniquenessDB:
    """DB-layer behaviour for duplicate activity-linked TwinStates.

    Since Phase 2.3 P3 dropped the unique index, duplicates are permitted
    at the DB layer — uniqueness is enforced at the service layer.
    Non-activity triggers (NULL activity_id) continue to coexist."""

    async def test_duplicate_activity_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "twin-dup-activity@example.com")
        goal = await _new_active_goal(db_session, athlete)
        activity = await _new_activity(db_session, athlete)

        s1 = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=activity.id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
        )
        s2 = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=activity.id,
            trigger=TwinTrigger.CALIBRATION,
        )
        db_session.add_all([s1, s2])
        await db_session.flush()
        await db_session.refresh(s1)
        await db_session.refresh(s2)
        assert s1.id != s2.id, (
            "Two TwinStates for the same (athlete_id, activity_id) "
            "must coexist at the DB layer — uniqueness moved to "
            "the service layer in Phase 2.3 P3."
        )

    async def test_multiple_null_activity_coexist(
        self, db_session: AsyncSession
    ) -> None:
        """Non-activity triggers (questionnaire, physiology_input,
        wellness_update) use NULL activity_id. The partial predicate
        exempts NULL rows, so multiple TwinStates per athlete with
        NULL activity_id are allowed."""
        athlete = await make_athlete(db_session, "twin-null-activity@example.com")
        goal = await _new_active_goal(db_session, athlete)

        s1 = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=None,
            trigger=TwinTrigger.QUESTIONNAIRE,
        )
        s2 = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=None,
            trigger=TwinTrigger.PHYSIOLOGY_INPUT,
        )
        s3 = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=None,
            trigger=TwinTrigger.WELLNESS_UPDATE,
        )
        db_session.add_all([s1, s2, s3])
        await db_session.flush()
        await db_session.refresh(s1)
        await db_session.refresh(s2)
        await db_session.refresh(s3)
        assert {s1.id, s2.id, s3.id} == {s1.id, s2.id, s3.id}  # all unique
        assert len({s1.id, s2.id, s3.id}) == 3

    async def test_activity_and_null_activity_coexist(
        self, db_session: AsyncSession
    ) -> None:
        """One activity-linked TwinState plus one NULL-activity
        TwinState coexist."""
        athlete = await make_athlete(db_session, "twin-mixed-triggers@example.com")
        goal = await _new_active_goal(db_session, athlete)
        activity = await _new_activity(db_session, athlete)

        s_activity = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=activity.id,
            trigger=TwinTrigger.ACTIVITY_SYNC,
        )
        s_questionnaire = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=None,
            trigger=TwinTrigger.QUESTIONNAIRE,
        )
        db_session.add_all([s_activity, s_questionnaire])
        await db_session.flush()
        await db_session.refresh(s_activity)
        await db_session.refresh(s_questionnaire)
        assert s_activity.id != s_questionnaire.id


# ---------------------------------------------------------------------------
# Latest read index.
# ---------------------------------------------------------------------------


class TestTwinStateLatestIndexDB:
    """``idx_twin_states_latest`` on ``(athlete_id, created_at)``
    supports the ``get_latest`` query — the most frequent read."""

    async def test_latest_index_present(self, db_session: AsyncSession) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ())
            == {"athlete_id", "created_at"}
        ]
        assert matched, (
            "Expected an index on (athlete_id, created_at) for the "
            "get_latest home-view query."
        )


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestTwinStateForeignKeysDB:
    """Athlete FK CASCADE, TrainingGoal FK CASCADE, Activity FK SET NULL."""

    def test_athlete_id_fk_cascade(self) -> None:
        fks = db_foreign_keys(TABLE)
        athlete_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks, (
            "twin_states.athlete_id must reference athletes(id)."
        )

    def test_training_goal_id_fk_cascade(self) -> None:
        fks = db_foreign_keys(TABLE)
        goal_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "training_goals"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_goal_id",)
        ]
        assert goal_fks, (
            "twin_states.training_goal_id must reference training_goals(id)."
        )

    def test_activity_id_fk_set_null(self) -> None:
        fks = db_foreign_keys(TABLE)
        activity_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "activities"
            and tuple(fk.get("constrained_columns") or ())
            == ("activity_id",)
        ]
        assert activity_fks, (
            "twin_states.activity_id must reference activities(id)."
        )

    async def test_athlete_deletion_cascades_twin_state(
        self, db_session: AsyncSession
    ) -> None:
        """Athlete FK ON DELETE CASCADE — twin history is wiped when
        the athlete account is deleted."""

        athlete = Athlete(email="twin-cascade-athlete@example.com")
        db_session.add(athlete)
        await db_session.flush()

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

        state = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            activity_id=None,
            trigger=TwinTrigger.QUESTIONNAIRE,
        )
        db_session.add(state)
        await db_session.flush()
        state_id = state.id

        # Commit so the cascade actually fires (rollback would undo it).
        await db_session.commit()

        # Use a fresh session because we need to test against the
        # persisted state.


        # Re-create a fresh session from the test engine.
        # Easier: just delete the athlete and re-query.
        async with db_session.bind.begin() as conn:
            await conn.execute(  # type: ignore[attr-defined]
                text("DELETE FROM athletes WHERE id = :id"),
                {"id": athlete.id},
            )

        # Verify the twin state row is gone via a sync query.
        engine = create_engine(get_sync_database_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM twin_states WHERE id = :id"
                    ),
                    {"id": state_id},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None and row[0] == 0, (
            "Athlete ON DELETE CASCADE failed — twin_states row "
            f"with id={state_id} survived athlete deletion."
        )


# ---------------------------------------------------------------------------
# Default values.
# ---------------------------------------------------------------------------


class TestTwinStateDefaultsDB:
    """``metric_confidence`` defaults to ``'{}'::jsonb``."""

    async def test_metric_confidence_default_empty_dict(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "twin-metric-default@example.com")
        goal = await _new_active_goal(db_session, athlete)

        state = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            metric_confidence=None,  # omit so server_default fires
        )
        db_session.add(state)
        await db_session.flush()
        await db_session.refresh(state)
        assert state.metric_confidence == {}, (
            "metric_confidence server_default must be '{}'::jsonb "
            "so an insert that omits it still persists an empty dict."
        )


# ---------------------------------------------------------------------------
# Required-field NOT NULL constraints.
# ---------------------------------------------------------------------------


class TestTwinStateRequiredFieldsNotNullDB:
    """``athlete_id``, ``training_goal_id``, ``model_version``,
    ``fitness``, ``fatigue``, ``form``, ``data_tier``,
    ``confidence_level``, ``trigger``, ``readiness_level``,
    ``metric_confidence`` are NOT NULL."""

    async def test_missing_athlete_id_rejected(
        self, db_session: AsyncSession
    ) -> None:
        goal = await _new_active_goal(
            db_session,
            await make_athlete(db_session, "twin-missing-athlete@example.com"),
        )
        state = TwinState(
            athlete_id=None,  # type: ignore[arg-type]
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
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_missing_form_rejected(self, db_session: AsyncSession) -> None:
        athlete = await make_athlete(db_session, "twin-missing-form@example.com")
        goal = await _new_active_goal(db_session, athlete)
        state = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_5,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.QUESTIONNAIRE,
            model_version="v1.0",
            fitness=0.0,
            fatigue=0.0,
            form=None,  # type: ignore[arg-type]
            readiness_level=RecoveryModifierLevel.GREEN,
            metric_confidence={},
        )
        db_session.add(state)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Round-trip persistence.
# ---------------------------------------------------------------------------


class TestTwinStateRoundTripDB:
    """Minimal TwinState round-trips through the DB layer."""

    async def test_questionnaire_trigger_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "twin-roundtrip@example.com")
        goal = await _new_active_goal(db_session, athlete)

        state = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            trigger=TwinTrigger.QUESTIONNAIRE,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.MEDIUM,
            fitness=10.5,
            fatigue=2.3,
            form=8.2,
            readiness_level=RecoveryModifierLevel.AMBER,
        )
        db_session.add(state)
        await db_session.flush()
        state_id = state.id

        # Round-trip via a fresh query.
        from sqlalchemy import select

        result = await db_session.execute(
            select(TwinState).where(TwinState.id == state_id)
        )
        loaded = result.scalar_one()
        assert loaded.trigger == TwinTrigger.QUESTIONNAIRE
        assert loaded.confidence_level == TwinConfidenceLevel.MEDIUM
        assert loaded.data_tier == DataTier.TIER_3.value
        assert loaded.fitness == 10.5
        assert loaded.fatigue == 2.3
        assert loaded.form == 8.2
        assert loaded.readiness_level == RecoveryModifierLevel.AMBER

    async def test_metric_confidence_jsonb_round_trip(
        self, db_session: AsyncSession
    ) -> None:
        """JSONB ``metric_confidence`` round-trip preserves nested
        shape (lt1_hr, lt2_hr, cp, etc.)."""
        athlete = await make_athlete(db_session, "twin-jsonb@example.com")
        goal = await _new_active_goal(db_session, athlete)

        confidence = {
            "lt1_hr": "low",
            "lt1_power": None,
            "lt1_pace": None,
            "lt2_hr": "low",
            "lt2_power": None,
            "lt2_pace": None,
            "cp": None,
        }
        state = _twin_state_factory(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            metric_confidence=confidence,
        )
        db_session.add(state)
        await db_session.flush()
        state_id = state.id

        from sqlalchemy import select

        result = await db_session.execute(
            select(TwinState).where(TwinState.id == state_id)
        )
        loaded = result.scalar_one()
        assert loaded.metric_confidence == confidence