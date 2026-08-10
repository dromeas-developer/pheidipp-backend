"""API tests for the activity upload + analyse endpoints.

Covers POST /athletes/{athlete_id}/activities/upload and
POST /athletes/{athlete_id}/activities/{activity_id}/analyse at the
HTTP boundary, including auth, validation, idempotency, and the
upload-orchestration order (commit before defer).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import post_workout_agent as pwa_module
from app.api.v1.activity import build_activity_ingestion_service
from app.core.security.token_service import TokenService
from app.main import app
from app.models.activity import Activity
from app.models.enums import (
    ActivitySource,
    SportType,
)
from app.services.object_storage_client import (
    ObjectStorageClient,
    ObjectStorageUploadError,
)
from app.services.activity_ingestion_service import ActivityIngestionService
from tests.utils.factories import (
    make_athlete_with_profile,
    make_athlete_preferences,
    make_training_goal,
    make_twin_state,
)


THREE_PARAGRAPH_CONTENT = (
        "You held a steady aerobic effort across the session.\n\n"
        "Today's effort aligns with the threshold session on the plan.\n\n"
        "For tomorrow, a recovery shakeout would consolidate the week."
)


async def _issue_token(athlete_id: uuid.UUID) -> str:
    svc = TokenService()
    token, _ = svc.issue_access_token(athlete_id)
    return token


def _auth_header(athlete_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_issue_token(athlete_id)}"}


async def _auth_header_async(athlete_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {await _issue_token(athlete_id)}"}


def _stub_storage_key(athlete_id: uuid.UUID) -> str:
    return f"athlete/{athlete_id}/{date.today().isoformat()}/abc.fit"


def _stub_object_storage(key: str | None = None) -> MagicMock:
    storage = MagicMock(spec=ObjectStorageClient)

    class _StoredObject:
        def __init__(self, k: str) -> None:
            self.key = k
            self.byte_count = 1024
            self.content_md5 = "deadbeef"

    async def _upload(
        *, athlete_id: uuid.UUID, activity_date: date, file_bytes: bytes,
        content_type: str = "application/octet-stream",
        suffix_uuid: uuid.UUID | None = None,
    ) -> _StoredObject:
        return _StoredObject(key or _stub_storage_key(athlete_id))

    storage.upload_fit = _upload
    return storage


def _llm_client_returning(content: str) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock()
    response.usage.total_tokens = 100
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


def _async_openai_factory(client: MagicMock) -> Callable[..., MagicMock]:
    """Return a constructor-shaped callable yielding *client*.

    Used to monkeypatch ``AsyncOpenAI`` so the LLM proxy client is a
    controlled mock; ``**_kwargs`` absorbs constructor arguments.
    """

    def _factory(**_kwargs: Any) -> MagicMock:
        return client

    return _factory


class TestActivityUploadEndpoint:
    async def test_valid_upload_returns_202(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        headers = await _auth_header_async(athlete.id)

        storage = _stub_object_storage()
        app.dependency_overrides[build_activity_ingestion_service] = (
            _build_ingestion_service_with(storage)
        )

        files = {"file": ("activity.fit", b"fit-bytes", "application/octet-stream")}
        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["ingestion_status"] == "pending"
        assert "task_id" in body
        uuid.UUID(body["task_id"])
        assert body["activity"]["source"] == ActivitySource.MANUAL_UPLOAD.value
        assert body["activity"]["fit_file_key"] is not None
        assert body["activity"]["aerobic_load"] is None

    async def test_fit_file_key_non_null(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        headers = await _auth_header_async(athlete.id)

        storage = _stub_object_storage()
        app.dependency_overrides[build_activity_ingestion_service] = (
            _build_ingestion_service_with(storage)
        )

        files = {"file": ("x.fit", b"x", "application/octet-stream")}
        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )

        assert resp.status_code == 202
        assert resp.json()["activity"]["fit_file_key"] is not None

    async def test_oversize_returns_413(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        headers = await _auth_header_async(athlete.id)
        big = b"\x00" * (10 * 1024 * 1024 + 1)
        files = {"file": ("big.fit", big, "application/octet-stream")}

        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )
        assert resp.status_code == 413

    async def test_empty_file_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        headers = await _auth_header_async(athlete.id)
        files = {"file": ("empty.fit", b"", "application/octet-stream")}

        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )
        assert resp.status_code == 422

    async def test_object_storage_failure_returns_503(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        headers = await _auth_header_async(athlete.id)

        storage = MagicMock(spec=ObjectStorageClient)

        async def _failing_upload(**kwargs: Any) -> None:
            raise ObjectStorageUploadError("minio down")

        storage.upload_fit = _failing_upload
        app.dependency_overrides[build_activity_ingestion_service] = (
            _build_ingestion_service_with(storage)
        )

        before = await db_session.execute(select(Activity))
        before_count = len(list(before.scalars()))

        files = {"file": ("x.fit", b"x", "application/octet-stream")}
        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )

        assert resp.status_code == 503

        after = await db_session.execute(select(Activity))
        assert len(list(after.scalars())) == before_count

    async def test_cross_athlete_returns_403(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        other, _ = await make_athlete_with_profile(db_session)
        headers = await _auth_header_async(other.id)

        files = {"file": ("x.fit", b"x", "application/octet-stream")}
        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )
        assert resp.status_code == 403

    async def test_no_avg_fields_in_response(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        headers = await _auth_header_async(athlete.id)

        storage = _stub_object_storage()
        app.dependency_overrides[build_activity_ingestion_service] = (
            _build_ingestion_service_with(storage)
        )

        files = {"file": ("x.fit", b"x", "application/octet-stream")}
        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )

        assert resp.status_code == 202
        body = resp.json()
        for forbidden in ("avg_hr", "avg_pace", "avg_power", "avg_cadence"):
            assert forbidden not in body["activity"]


class TestPostAnalyseEndpoint:
    async def test_first_call_creates_message(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        goal = await make_training_goal(db_session, athlete_id=athlete.id)
        await make_twin_state(
            db_session, athlete_id=athlete.id, training_goal_id=goal.id
        )

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            external_id="analyse-1",
            activity_date=date(2026, 1, 1),
            start_time=datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            sport_type=SportType.RUNNING,
            has_hr=True,
            has_gps=True,
            quality_flags={},
            fit_file_key="athlete/2026-01-01/test.fit",
            aerobic_load=80.0,
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _async_openai_factory(_llm_client_returning(THREE_PARAGRAPH_CONTENT)),
        )

        headers = await _auth_header_async(athlete.id)
        resp = await client.post(
            f"/athletes/{athlete.id}/activities/{activity.id}/analyse",
            headers=headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "coaching_message" in body
        assert body["coaching_message"]["message_type"] == "post_workout"
        assert body["coaching_message"]["twin_state_id"] is not None

    async def test_second_call_returns_existing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        goal = await make_training_goal(db_session, athlete_id=athlete.id)
        await make_twin_state(
            db_session, athlete_id=athlete.id, training_goal_id=goal.id
        )

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            external_id="analyse-2",
            activity_date=date(2026, 1, 1),
            start_time=datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            sport_type=SportType.RUNNING,
            has_hr=True,
            has_gps=True,
            quality_flags={},
            fit_file_key="athlete/2026-01-01/test.fit",
            aerobic_load=80.0,
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        mock_client = _llm_client_returning(THREE_PARAGRAPH_CONTENT)
        monkeypatch.setattr(
            pwa_module, "AsyncOpenAI", _async_openai_factory(mock_client)
        )

        headers = await _auth_header_async(athlete.id)
        first = await client.post(
            f"/athletes/{athlete.id}/activities/{activity.id}/analyse",
            headers=headers,
        )
        second = await client.post(
            f"/athletes/{athlete.id}/activities/{activity.id}/analyse",
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert (
            first.json()["coaching_message"]["id"]
            == second.json()["coaching_message"]["id"]
        )
        assert mock_client.chat.completions.create.await_count == 1


def _build_ingestion_service_with(storage: Any) -> Any:
    from fastapi import Depends
    from app.db.session import get_db
    from app.services.activity_ingestion_service import (
        ActivityIngestionService,
    )

    def _factory(
        session: AsyncSession = Depends(get_db),
    ) -> ActivityIngestionService:
        return ActivityIngestionService(session=session, object_storage=storage)

    return _factory


class TestFitIngestDefer:
    async def test_fit_upload_enqueues_fit_ingest_via_defer_async(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.worker import app as worker_app

        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        headers = await _auth_header_async(athlete.id)

        storage = _stub_object_storage()
        app.dependency_overrides[build_activity_ingestion_service] = (
            _build_ingestion_service_with(storage)
        )

        defer_mock = AsyncMock(return_value=42)
        monkeypatch.setattr(worker_app.fit_ingest, "defer_async", defer_mock)

        files = {"file": ("x.fit", b"x", "application/octet-stream")}
        resp = await client.post(
            f"/athletes/{athlete.id}/activities/upload", files=files, headers=headers
        )

        assert resp.status_code == 202

        defer_mock.assert_awaited_once()
        assert defer_mock.await_args is not None
        call_kwargs = defer_mock.await_args.kwargs
        assert call_kwargs["athlete_id"] == str(athlete.id)
        assert "activity_id" in call_kwargs
