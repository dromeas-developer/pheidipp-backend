"""Integration tests for the procrastinate worker defer behaviour.

Covers the async ``defer_async`` calls in worker tasks (signal_clean,
generate_plan) and the conftest's ``_open_procrastinate_app`` fixture
compatibility with the async ``PsycopgConnector``.

These tests run with the conftest's session-scoped autouse fixture
which opens the procrastinate app via ``open_async()`` and applies
the schema via ``apply_schema_async()`` — the integration path
exercised by every real defer. The worker tasks open their own
session via ``AsyncSessionLocal``; per ``MOCKING_CONTRACT.md``
anti-pattern, the test monkeypatches this to the test session so
no second session is opened.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as session_module
from app.models.enums import ActivitySource
from app.services import signal_cleaning_service as scs_module
from app.worker import app as worker_app
from procrastinate import PsycopgConnector
from tests.utils.factories import (
    make_activity,
    make_athlete_fitness,
    make_athlete_physiology,
    make_athlete_preferences,
    make_athlete_with_profile,
    make_training_goal,
    make_twin_state,
)


class TestProcrastinateAppOpens:
    async def test_procrastinate_app_connector_is_async(self) -> None:
        assert isinstance(worker_app.app.connector, PsycopgConnector)

    async def test_procrastinate_app_open_async_succeeds(self) -> None:
        # The conftest's _open_procrastinate_app opens the app at session
        # start. This test re-enters the context manager to confirm the
        # open path is repeatable and the DuplicateObject handling in
        # apply_schema_async still suppresses the steady-state re-run.
        import psycopg
        from procrastinate.exceptions import ConnectorException

        async with worker_app.app.open_async():
            try:
                await worker_app.app.schema_manager.apply_schema_async()
            except ConnectorException as exc:
                if not isinstance(exc.__cause__, psycopg.errors.DuplicateObject):
                    raise

    async def test_procrastinate_jobs_table_exists(self, db_session: AsyncSession) -> None:
        # The conftest applies procrastinate's schema at session start.
        # If the table is missing, this query errors — which would also
        # fail every other integration test that defers, so this is a
        # regression guard for the fixture path.
        result = await db_session.execute(
            text(
                "SELECT 1 FROM procrastinate_jobs "
                "WHERE 1 = 0"
            )
        )
        result.fetchone()


class TestSignalCleanDefer:
    async def test_signal_clean_enqueues_threshold_detection_via_defer_async(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The cleaning is mocked so the test does not depend on real
        # FIT bytes; the worker still queries the activity via the
        # session and still commits via the test session.
        athlete, _ = await make_athlete_with_profile(db_session)
        activity = await make_activity(
            db_session,
            athlete_id=athlete.id,
            source=ActivitySource.GARMIN_DIRECT,
        )
        await db_session.commit()

        @asynccontextmanager
        async def _fake_session_local() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        monkeypatch.setattr(session_module, "AsyncSessionLocal", _fake_session_local)

        fake_result = SimpleNamespace(
            created=True,
            raw_sensor_stream_id=uuid.uuid4(),
            activity_id=activity.id,
        )

        async def _fake_clean(self: Any, *args: Any, **kwargs: Any) -> Any:
            return fake_result

        monkeypatch.setattr(scs_module.SignalCleaningService, "clean", _fake_clean)

        defer_mock = AsyncMock(return_value=42)
        monkeypatch.setattr(
            worker_app.threshold_detection, "defer_async", defer_mock
        )

        await worker_app.signal_clean(activity_id=str(activity.id))

        defer_mock.assert_awaited_once_with(activity_id=str(activity.id))


class TestGeneratePlanDefer:
    async def test_generate_plan_enqueues_generate_first_message_via_defer_async(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Full onboarding prerequisites so PlanGenerationService.generate_plan
        # can run end-to-end inside the worker task.
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        await make_athlete_fitness(db_session, athlete_id=athlete.id)
        await make_athlete_physiology(db_session, athlete_id=athlete.id)
        goal = await make_training_goal(db_session, athlete_id=athlete.id)
        await make_twin_state(
            db_session, athlete_id=athlete.id, training_goal_id=goal.id
        )
        await db_session.commit()

        @asynccontextmanager
        async def _fake_session_local() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        monkeypatch.setattr(session_module, "AsyncSessionLocal", _fake_session_local)

        defer_mock = AsyncMock(return_value=42)
        monkeypatch.setattr(
            worker_app.generate_first_message, "defer_async", defer_mock
        )

        await worker_app.generate_plan(athlete_id=str(athlete.id))

        defer_mock.assert_awaited_once_with(athlete_id=str(athlete.id))
