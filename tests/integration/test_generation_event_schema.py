"""Integration tests for the ``GenerationEvent`` schema at the DB level.

Phase-1.2c introduces the ``generation_events`` table — an
append-only audit log for every LLM API call, successful or failed.
The ``LLMInstrumentationService`` (later phase) is the sole writer;
rows are never updated or deleted.

The DB-level invariants codified here:

* CHECK ``ck_generation_events_failure_reason_consistency`` —
  ``failure_reason IS NOT NULL iff success = false``.
* CHECK ``ck_generation_events_token_counts_non_negative`` —
  ``input_token_count >= 0 AND output_token_count >= 0``.
* CHECK ``ck_generation_events_latency_non_negative`` —
  ``latency_ms >= 0``.
* FK ``athlete_id`` ON DELETE CASCADE.
* Three read-pattern indexes: ``(athlete_id, created_at)``,
  ``(agent_name, created_at)``, ``(success, created_at)``.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.generation_event import GenerationEvent
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_check_constraints,
    db_columns,
    db_foreign_keys,
    db_indexes,
)


TABLE = "generation_events"


def _generation_event_factory(
    *,
    athlete_id: uuid.UUID,
    agent_name: str = "PostWorkoutAgent",
    prompt_version: str = "v1.0",
    trigger_context: str = "manual_trigger",
    input_token_count: int = 100,
    output_token_count: int = 200,
    latency_ms: int = 1500,
    success: bool = True,
    failure_reason: str | None = None,
) -> GenerationEvent:
    return GenerationEvent(
        athlete_id=athlete_id,
        agent_name=agent_name,
        prompt_version=prompt_version,
        trigger_context=trigger_context,
        input_token_count=input_token_count,
        output_token_count=output_token_count,
        latency_ms=latency_ms,
        success=success,
        failure_reason=failure_reason,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestGenerationEventDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "agent_name",
            "prompt_version",
            "trigger_context",
            "input_token_count",
            "output_token_count",
            "latency_ms",
            "success",
            "failure_reason",
            "created_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"generation_events.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# CHECK — failure_reason consistency.
# ---------------------------------------------------------------------------


class TestGenerationEventFailureReasonConsistencyCheckDB:
    """``failure_reason IS NOT NULL`` iff ``success = false``."""

    def test_failure_reason_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "failure_reason" in (c.get("sqltext") or "").lower()
            and "success" in (c.get("sqltext") or "").lower()
            and "IS NULL" in (c.get("sqltext") or "").upper()
            and "IS NOT NULL" in (c.get("sqltext") or "").upper()
            for c in checks
        )
        assert found, (
            "generation_events must declare CHECK constraint "
            "enforcing failure_reason <-> success consistency."
        )

    async def test_success_row_with_failure_reason_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-success-with-failure@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            success=True,
            failure_reason="this shouldn't be set",
        )
        db_session.add(evt)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_failure_row_without_failure_reason_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-failure-no-reason@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            success=False,
            failure_reason=None,
        )
        db_session.add(evt)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_success_row_no_failure_reason_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-success-clean@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            success=True,
            failure_reason=None,
        )
        db_session.add(evt)
        await db_session.flush()
        await db_session.refresh(evt)
        assert evt.success is True
        assert evt.failure_reason is None

    async def test_failure_row_with_reason_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-failure-with-reason@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            success=False,
            failure_reason="LLM timeout after 30s",
        )
        db_session.add(evt)
        await db_session.flush()
        await db_session.refresh(evt)
        assert evt.success is False
        assert evt.failure_reason == "LLM timeout after 30s"


# ---------------------------------------------------------------------------
# CHECK — token counts and latency non-negative.
# ---------------------------------------------------------------------------


class TestGenerationEventNonNegativeCheckDB:
    async def test_negative_input_token_count_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-neg-input@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            input_token_count=-1,
        )
        db_session.add(evt)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_negative_output_token_count_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-neg-output@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            output_token_count=-1,
        )
        db_session.add(evt)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_negative_latency_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-neg-latency@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id, latency_ms=-100
        )
        db_session.add(evt)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_zero_token_counts_and_latency_accepted(
        self, db_session: AsyncSession
    ) -> None:
        """Zero is valid — a failure-before-counts row still
        persists with token counts at 0."""
        athlete = await make_athlete(
            db_session, "ge-zero@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            input_token_count=0,
            output_token_count=0,
            latency_ms=0,
            success=False,
            failure_reason="rate_limited",
        )
        db_session.add(evt)
        await db_session.flush()
        await db_session.refresh(evt)
        assert evt.input_token_count == 0
        assert evt.output_token_count == 0
        assert evt.latency_ms == 0


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestGenerationEventForeignKeysDB:
    def test_athlete_id_fk_to_athletes(self) -> None:
        fks = db_foreign_keys(TABLE)
        athlete_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks

    def test_athlete_fk_ondelete_is_cascade(self) -> None:
        fks = db_foreign_keys(TABLE)
        athlete_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks, (
            "generation_events.athlete_id FK ON DELETE must be CASCADE."
        )
        assert athlete_fks[0].get("options", {}).get("ondelete") == "CASCADE"


# ---------------------------------------------------------------------------
# Read-pattern indexes.
# ---------------------------------------------------------------------------


class TestGenerationEventReadIndexesDB:
    async def test_athlete_audit_index_present(
        self, db_session: AsyncSession
    ) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ())
            == {"athlete_id", "created_at"}
        ]
        assert matched, (
            "Expected an index on (athlete_id, created_at) for the "
            "per-athlete audit feed."
        )

    async def test_agent_monitoring_index_present(
        self, db_session: AsyncSession
    ) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ())
            == {"agent_name", "created_at"}
        ]
        assert matched, (
            "Expected an index on (agent_name, created_at) for the "
            "per-agent monitoring dashboards."
        )

    async def test_failure_dashboard_index_present(
        self, db_session: AsyncSession
    ) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ())
            == {"success", "created_at"}
        ]
        assert matched, (
            "Expected an index on (success, created_at) for the "
            "failure-rate dashboards."
        )


# ---------------------------------------------------------------------------
# Round-trip persistence.
# ---------------------------------------------------------------------------


class TestGenerationEventRoundTripDB:
    async def test_minimal_event_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-roundtrip@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            agent_name="TestAgent",
            prompt_version="v2.3",
            input_token_count=512,
            output_token_count=256,
            latency_ms=1500,
            success=True,
            failure_reason=None,
        )
        db_session.add(evt)
        await db_session.flush()
        evt_id = evt.id

        from sqlalchemy import select

        result = await db_session.execute(
            select(GenerationEvent).where(GenerationEvent.id == evt_id)
        )
        loaded = result.scalar_one()
        assert loaded.agent_name == "TestAgent"
        assert loaded.prompt_version == "v2.3"
        assert loaded.input_token_count == 512
        assert loaded.output_token_count == 256
        assert loaded.latency_ms == 1500
        assert loaded.success is True
        assert loaded.failure_reason is None

    async def test_failure_event_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-failure-roundtrip@example.com"
        )
        evt = _generation_event_factory(
            athlete_id=athlete.id,
            agent_name="TestAgent",
            success=False,
            failure_reason="parse_error",
        )
        db_session.add(evt)
        await db_session.flush()
        evt_id = evt.id

        from sqlalchemy import select

        result = await db_session.execute(
            select(GenerationEvent).where(GenerationEvent.id == evt_id)
        )
        loaded = result.scalar_one()
        assert loaded.success is False
        assert loaded.failure_reason == "parse_error"


# ---------------------------------------------------------------------------
# Server defaults — failure-before-counts row still inserts.
# ---------------------------------------------------------------------------


class TestGenerationEventServerDefaultsDB:
    """Token counts default to 0 in the table so a
    failure-before-counts row can still be inserted without
    violating NOT NULL."""

    async def test_default_token_counts_apply_when_omitted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "ge-defaults@example.com"
        )
        # Provide explicit failure_reason — pass NULL for token
        # counts to let server_default fire.
        evt = GenerationEvent(
            athlete_id=athlete.id,
            agent_name="CrashAgent",
            prompt_version="v1.0",
            trigger_context="synthetic_failure",
            success=False,
            failure_reason="crash",
        )
        db_session.add(evt)
        await db_session.flush()
        await db_session.refresh(evt)
        assert evt.input_token_count == 0
        assert evt.output_token_count == 0
        assert evt.latency_ms == 0