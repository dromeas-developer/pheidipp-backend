"""Integration tests for the ``CoachingMessage`` schema at the DB level.

Phase-1.2c introduces the ``coaching_messages`` table — an immutable
LLM-generated message linked to the active ``TwinState`` at
generation time.

The DB-level invariants codified here:

* Partial unique index ``uq_coaching_messages_athlete_first_message``
  on ``(athlete_id) WHERE message_type = 'first_message'`` — one
  first_message per athlete.
* Partial unique index
  ``uq_coaching_messages_activity_post_workout`` on
  ``(activity_id) WHERE message_type = 'post_workout' AND
  activity_id IS NOT NULL`` — one post_workout per activity.
* CHECK ``ck_coaching_messages_content_non_empty`` — non-empty
  content.
* FKs: athlete_id (CASCADE), twin_state_id (CASCADE),
  activity_id (SET NULL).

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    ActivitySource,
    DataTier,
    GoalType,
    MessageType,
    RecoveryModifierLevel,
    TwinConfidenceLevel,
    TwinTrigger,
    TrainingGoalStatus,
)
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState


TABLE = "coaching_messages"


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


def _indexes(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_indexes(table))
    finally:
        engine.dispose()


def _check_constraints(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_check_constraints(table))
    finally:
        engine.dispose()


def _foreign_keys(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_foreign_keys(table))
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _new_athlete(db_session: AsyncSession, email: str) -> Athlete:
    a = Athlete(email=email)
    db_session.add(a)
    await db_session.flush()
    return a


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


async def _new_twin_state(
    db_session: AsyncSession, athlete: Athlete, goal: TrainingGoal
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


async def _new_activity(
    db_session: AsyncSession, athlete: Athlete
) -> Activity:
    activity = Activity(
        athlete_id=athlete.id,
        source=ActivitySource.MANUAL_ENTRY,
        external_id=None,
        activity_date=date(2026, 6, 19),
        start_time=datetime(2026, 6, 19, 7, 30, tzinfo=timezone.utc),
        duration_seconds=3600,
    )
    db_session.add(activity)
    await db_session.flush()
    return activity


def _coaching_message_factory(
    *,
    athlete_id: uuid.UUID,
    twin_state_id: uuid.UUID,
    activity_id: uuid.UUID | None = None,
    message_type: MessageType = MessageType.WELLNESS_ALERT,
    content: str = "Great work on your last session!",
    prompt_version: str = "v1.0",
) -> CoachingMessage:
    return CoachingMessage(
        athlete_id=athlete_id,
        twin_state_id=twin_state_id,
        activity_id=activity_id,
        message_type=message_type,
        content=content,
        prompt_version=prompt_version,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestCoachingMessageDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "twin_state_id",
            "activity_id",
            "message_type",
            "content",
            "prompt_version",
            "generated_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in _columns(TABLE)}
        assert expected_column in cols, (
            f"coaching_messages.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# Partial unique indexes.
# ---------------------------------------------------------------------------


class TestCoachingMessageFirstMessagePartialUniqueDB:
    """Two ``first_message`` rows for the same athlete must raise
    ``IntegrityError``."""

    def _partial_unique_index(self) -> dict | None:
        for idx in _indexes(TABLE):
            cols = set(idx.get("column_names") or ())
            if cols == {"athlete_id"} and idx.get("unique"):
                return idx
        return None

    async def test_partial_unique_index_present(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._partial_unique_index()
        assert idx is not None, (
            "Expected a UNIQUE index on (athlete_id) — the "
            "first_message partial unique constraint."
        )

    async def test_partial_predicate_is_first_message(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._partial_unique_index()
        assert idx is not None
        engine = create_engine(_sync_url())
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
        assert "message_type" in ddl and "first_message" in ddl, (
            f"first_message partial predicate must constrain "
            f"`message_type = 'first_message'`. DDL: {row[0]!r}"
        )

    async def test_two_first_message_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(
            db_session, "msg-dup-first@example.com"
        )
        goal = await _new_active_goal(db_session, athlete)
        state = await _new_twin_state(db_session, athlete, goal)

        m1 = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            message_type=MessageType.FIRST_MESSAGE,
        )
        m2 = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            message_type=MessageType.FIRST_MESSAGE,
        )
        db_session.add_all([m1, m2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_first_message_and_post_workout_coexist(
        self, db_session: AsyncSession
    ) -> None:
        """first_message (athlete-level) and post_workout
        (activity-level) are independent partial predicates — they
        must coexist."""
        athlete = await _new_athlete(
            db_session, "msg-first-and-post@example.com"
        )
        goal = await _new_active_goal(db_session, athlete)
        state = await _new_twin_state(db_session, athlete, goal)
        activity = await _new_activity(db_session, athlete)

        m_first = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            message_type=MessageType.FIRST_MESSAGE,
        )
        m_post = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            activity_id=activity.id,
            message_type=MessageType.POST_WORKOUT,
        )
        db_session.add_all([m_first, m_post])
        await db_session.flush()
        await db_session.refresh(m_first)
        await db_session.refresh(m_post)
        assert m_first.id != m_post.id


class TestCoachingMessagePostWorkoutPartialUniqueDB:
    """Two ``post_workout`` rows for the same activity must raise
    ``IntegrityError``."""

    def _activity_partial_unique_index(self) -> dict | None:
        for idx in _indexes(TABLE):
            cols = set(idx.get("column_names") or ())
            if cols == {"activity_id"} and idx.get("unique"):
                return idx
        return None

    async def test_activity_partial_unique_index_present(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._activity_partial_unique_index()
        assert idx is not None, (
            "Expected a UNIQUE index on (activity_id) — the "
            "post_workout partial unique constraint."
        )

    async def test_activity_partial_predicate(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._activity_partial_unique_index()
        assert idx is not None
        engine = create_engine(_sync_url())
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
        assert "post_workout" in ddl, (
            f"post_workout partial predicate must constrain "
            f"`message_type = 'post_workout'`. DDL: {row[0]!r}"
        )
        assert "activity_id" in ddl and "is not null" in ddl, (
            f"post_workout partial predicate must short-circuit on "
            f"NULL activity_id. DDL: {row[0]!r}"
        )

    async def test_two_post_workout_same_activity_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(
            db_session, "msg-dup-postworkout@example.com"
        )
        goal = await _new_active_goal(db_session, athlete)
        state = await _new_twin_state(db_session, athlete, goal)
        activity = await _new_activity(db_session, athlete)

        m1 = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            activity_id=activity.id,
            message_type=MessageType.POST_WORKOUT,
        )
        m2 = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            activity_id=activity.id,
            message_type=MessageType.POST_WORKOUT,
        )
        db_session.add_all([m1, m2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_post_workout_different_activities_coexist(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(
            db_session, "msg-multi-postworkout@example.com"
        )
        goal = await _new_active_goal(db_session, athlete)
        state = await _new_twin_state(db_session, athlete, goal)
        a1 = await _new_activity(db_session, athlete)
        a2 = await _new_activity(db_session, athlete)

        m1 = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            activity_id=a1.id,
            message_type=MessageType.POST_WORKOUT,
        )
        m2 = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            activity_id=a2.id,
            message_type=MessageType.POST_WORKOUT,
        )
        db_session.add_all([m1, m2])
        await db_session.flush()
        await db_session.refresh(m1)
        await db_session.refresh(m2)
        assert m1.id != m2.id


# ---------------------------------------------------------------------------
# CHECK — non-empty content.
# ---------------------------------------------------------------------------


class TestCoachingMessageContentNonEmptyCheckDB:
    def test_content_non_empty_check_present(self) -> None:
        checks = _check_constraints(TABLE)
        found = any(
            "length(content)" in (c.get("sqltext") or "")
            and "> 0" in (c.get("sqltext") or "")
            for c in checks
        )
        assert found, (
            "coaching_messages must declare CHECK constraint "
            "rejecting empty content (length(content) > 0)."
        )

    async def test_empty_content_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(
            db_session, "msg-empty@example.com"
        )
        goal = await _new_active_goal(db_session, athlete)
        state = await _new_twin_state(db_session, athlete, goal)

        msg = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            content="",  # empty content
        )
        db_session.add(msg)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestCoachingMessageForeignKeysDB:
    def test_athlete_id_fk_to_athletes(self) -> None:
        fks = _foreign_keys(TABLE)
        athlete_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks

    def test_twin_state_id_fk_to_twin_states(self) -> None:
        fks = _foreign_keys(TABLE)
        twin_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "twin_states"
            and tuple(fk.get("constrained_columns") or ())
            == ("twin_state_id",)
        ]
        assert twin_fks, (
            "coaching_messages.twin_state_id must reference twin_states(id)."
        )

    def test_activity_id_fk_to_activities(self) -> None:
        fks = _foreign_keys(TABLE)
        activity_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "activities"
            and tuple(fk.get("constrained_columns") or ())
            == ("activity_id",)
        ]
        assert activity_fks

    def test_athlete_fk_ondelete_is_cascade(self) -> None:
        engine = create_engine(_sync_url())
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
                          AND confrelid_table.relname = 'athletes'
                          AND conrelid_table.relname = :table_name
                        """
                    ),
                    {"table_name": TABLE},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None
        assert row[0] == "c", (
            f"coaching_messages.athlete_id FK ON DELETE must be CASCADE. "
            f"Got {row[0]!r}"
        )

    def test_twin_state_fk_ondelete_is_cascade(self) -> None:
        engine = create_engine(_sync_url())
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
                          AND confrelid_table.relname = 'twin_states'
                          AND conrelid_table.relname = :table_name
                        """
                    ),
                    {"table_name": TABLE},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None
        assert row[0] == "c", (
            f"coaching_messages.twin_state_id FK ON DELETE must be CASCADE. "
            f"Got {row[0]!r}"
        )

    def test_activity_fk_ondelete_is_set_null(self) -> None:
        engine = create_engine(_sync_url())
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
                          AND confrelid_table.relname = 'activities'
                          AND conrelid_table.relname = :table_name
                        """
                    ),
                    {"table_name": TABLE},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None
        assert row[0] == "n", (
            f"coaching_messages.activity_id FK ON DELETE must be "
            f"SET NULL (confdeltype='n'). Got {row[0]!r}"
        )


# ---------------------------------------------------------------------------
# Round-trip persistence.
# ---------------------------------------------------------------------------


class TestCoachingMessageRoundTripDB:
    async def test_minimal_message_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(
            db_session, "msg-roundtrip@example.com"
        )
        goal = await _new_active_goal(db_session, athlete)
        state = await _new_twin_state(db_session, athlete, goal)

        msg = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            message_type=MessageType.WEEKLY_SUMMARY,
            content="Solid week — keep it up.",
        )
        db_session.add(msg)
        await db_session.flush()
        msg_id = msg.id

        from sqlalchemy import select

        result = await db_session.execute(
            select(CoachingMessage).where(CoachingMessage.id == msg_id)
        )
        loaded = result.scalar_one()
        assert loaded.message_type == MessageType.WEEKLY_SUMMARY
        assert loaded.content == "Solid week — keep it up."
        assert loaded.activity_id is None
        assert loaded.twin_state_id == state.id

    async def test_null_activity_id_accepted_for_non_post_workout(
        self, db_session: AsyncSession
    ) -> None:
        """``activity_id`` is NULL for every MessageType other than
        ``post_workout`` — schema permits NULL."""
        athlete = await _new_athlete(
            db_session, "msg-no-activity@example.com"
        )
        goal = await _new_active_goal(db_session, athlete)
        state = await _new_twin_state(db_session, athlete, goal)

        msg = _coaching_message_factory(
            athlete_id=athlete.id,
            twin_state_id=state.id,
            activity_id=None,
            message_type=MessageType.PHASE_TRANSITION,
        )
        db_session.add(msg)
        await db_session.flush()
        await db_session.refresh(msg)
        assert msg.activity_id is None