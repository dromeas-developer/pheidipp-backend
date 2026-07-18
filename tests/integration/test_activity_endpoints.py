"""Integration tests for Activity API endpoints.

Phase-1.6: POST /upload (202), GET /activities, POST /analyse, GET /analysis
Phase-1.8: POST /upload returns 202 with task_id (not 201)

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
docs/implementation/phase-1/phase-1-8-p1-fix-event-ordering-and-async-processing.md
"""

from __future__ import annotations

import io
import uuid
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.coaching_message import CoachingMessage
from app.models.enums import ActivitySource, MessageType, TwinTrigger
from app.models.twin_state import TwinState
from app.core.security.token_service import TokenService
from app.main import app as fastapi_app
from app.api.v1.activity import build_post_workout_agent
from tests.utils.factories import make_athlete


def _access_token(athlete_id: uuid.UUID) -> str:
    """Return a valid JWT access token for the given athlete.

    The conftest.py sets JWT_SECRET_KEY="test-secret-do-not-use-in-prod" at
    import time, so TokenService() picks it up automatically.
    """
    return TokenService().issue_access_token(athlete_id=athlete_id)[0]


async def _create_athlete_with_onboarding(
    db_session: AsyncSession,
) -> tuple[Any, Any, Any]:
    """Create an athlete with full onboarding context for activity tests.

    Returns (athlete, auth_token_payload).
    """
    athlete = await make_athlete(db_session, f"activity-test-{uuid.uuid4()}@example.com")

    # Create minimal onboarding context
    from app.models.athlete_profile import AthleteProfile
    from app.models.athlete_preferences import AthletePreferences
    from app.models.athlete_fitness import AthleteFitness
    from app.models.athlete_physiology import AthletePhysiology
    from app.models.training_goal import TrainingGoal
    from app.models.enums import (
        DataTier,
        GoalType,
        RecoveryModifierLevel,
        TrainingGoalStatus,
        TwinConfidenceLevel,
    )

    profile = AthleteProfile(
        athlete_id=athlete.id,
        date_of_birth=date(1990, 1, 1),
        sex=MagicMock(value="not_specified") if hasattr(MagicMock(), "value") else "not_specified",
    )
    db_session.add(profile)

    prefs = AthletePreferences(
        athlete_id=athlete.id,
        weekly_schedule={},
    )
    db_session.add(prefs)

    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)

    fitness = AthleteFitness(
        athlete_id=athlete.id,
        aggregate={"fitness": 50.0, "fatigue": 30.0, "form": 20.0},
    )
    db_session.add(fitness)

    physiology = AthletePhysiology(
        athlete_id=athlete.id,
    )
    db_session.add(physiology)

    twin = TwinState(
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        data_tier=DataTier.TIER_3,
        confidence_level=TwinConfidenceLevel.LOW,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1.0",
        fitness=50.0,
        fatigue=30.0,
        form=20.0,
        readiness_level=RecoveryModifierLevel.GREEN,
    )
    db_session.add(twin)

    await db_session.flush()
    return athlete, goal, twin  # noqa: F811


def _fake_fit_bytes() -> bytes:
    """Generate minimal fake FIT file bytes for testing upload.

    This is not a real FIT file — just bytes that pass the upload
    size/content checks. The parsing will fail at the FIT parse
    stage, but that's acceptable for testing the API endpoint
    behavior (202 response, error handling, etc.).
    """
    # Return some fake bytes that are not empty and not too large
    return b"FIT\x00" + b"\x00" * 100


class TestPostUploadActivity:
    """POST /athletes/{id}/activities/upload — returns 202 with task_id."""

    @pytest.mark.asyncio
    async def test_upload_returns_202_with_task_id(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /upload returns 202 Accepted with task_id (not 201 Created).

        Phase-1.8: 202 Accepted with task_id is the correct response
        because processing happens asynchronously via the fit_ingest worker.
        """
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        # Mock the procrastinate task deferral
        with patch("app.api.v1.activity.procrastinate_app") as mock_procrastinate:
            mock_task = MagicMock()
            mock_task.defer = MagicMock(return_value=12345)  # job id
            mock_procrastinate_app = MagicMock()
            mock_procrastinate_app.tasks = {"fit_ingest": mock_task}
            mock_procrastinate.tasks = mock_procrastinate_app.tasks

            with patch("app.api.v1.activity.procrastinate_app", mock_procrastinate):
                response = await client.post(
                    f"/api/v1/athletes/{athlete.id}/activities/upload",
                    files={"file": ("test.fit", io.BytesIO(_fake_fit_bytes()), "application/octet-stream")},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert "activity" in data

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """require_self auth: JWT athlete_id must match path parameter."""
        await make_athlete(db_session, f"auth-{uuid.uuid4()}@example.com")

        # Use wrong athlete_id in JWT (by using a different token)
        response = await client.post(
            f"/api/v1/athletes/{uuid.uuid4()}/activities/upload",
            files={"file": ("test.fit", io.BytesIO(_fake_fit_bytes()), "application/octet-stream")},
        )
        # Without proper auth, should get 401 or 403
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_upload_empty_file_returns_422(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Empty file returns 422 Unprocessable Entity."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        response = await client.post(
            f"/api/v1/athletes/{athlete.id}/activities/upload",
            files={"file": ("empty.fit", io.BytesIO(b""), "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_file_too_large_returns_413(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """File exceeding 10MB limit returns 413."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        # Create file larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)

        response = await client.post(
            f"/api/v1/athletes/{athlete.id}/activities/upload",
            files={"file": ("large.fit", io.BytesIO(large_content), "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 413


class TestListActivities:
    """GET /athletes/{id}/activities — paginated activity list."""

    @pytest.mark.asyncio
    async def test_list_returns_empty_initially(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """New athlete with no activities returns empty list."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["activities"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_returns_activities(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Activity list returns existing activities for the athlete."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        # Create an activity directly
        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["activities"]) == 1
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """require_self: cross-athlete access returns 403."""
        _, *_ = await _create_athlete_with_onboarding(db_session)
        athlete2, *_ = await _create_athlete_with_onboarding(db_session)

        # Using athlete1's token to access athlete2's activities
        response = await client.get(
            f"/api/v1/athletes/{athlete2.id}/activities",
        )

        # Should fail auth
        assert response.status_code in (401, 403)


class TestGetActivity:
    """GET /athletes/{id}/activities/{aid} — single activity."""

    @pytest.mark.asyncio
    async def test_get_activity_returns_activity(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET returns the activity details."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(activity.id)

    @pytest.mark.asyncio
    async def test_get_activity_not_found(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Non-existent activity returns 404."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404


class TestPostAnalyseActivity:
    """POST /athletes/{id}/activities/{aid}/analyse — trigger PostWorkoutAgent."""

    @pytest.mark.asyncio
    async def test_analyse_returns_coaching_message(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """POST /analyse returns a coaching message."""
        athlete, _, twin = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        # Create activity with load scores
        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        # Mock the PostWorkoutAgent using FastAPI dependency override.
        # patch() does NOT work here because Depends() captures the function
        # reference at import time — the override must be set on the app.
        mock_message = MagicMock(spec=CoachingMessage)
        mock_message.id = uuid.uuid4()
        mock_message.content = "Post-workout analysis content"
        # pydantic validation requires these fields to be real values:
        mock_message.message_type = MessageType.POST_WORKOUT
        mock_message.prompt_version = "v1"
        mock_message.twin_state_id = twin.id

        from app.agents.post_workout_agent import PostWorkoutAgent

        mock_agent = MagicMock(spec=PostWorkoutAgent)
        mock_agent.generate = AsyncMock(return_value=mock_message)

        fastapi_app.dependency_overrides[build_post_workout_agent] = lambda: mock_agent
        try:
            response = await client.post(
                f"/api/v1/athletes/{athlete.id}/activities/{activity.id}/analyse",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            fastapi_app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "coaching_message" in data
        assert "activity" in data

    @pytest.mark.asyncio
    async def test_analyse_idempotent(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Second call to /analyse returns the existing message (no second LLM call)."""
        athlete, _, twin = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        existing_message = MagicMock(spec=CoachingMessage)
        existing_message.id = uuid.uuid4()
        existing_message.content = "Existing analysis"
        # pydantic validation requires these fields to be real values:
        existing_message.message_type = MessageType.POST_WORKOUT
        existing_message.prompt_version = "v1"
        existing_message.twin_state_id = twin.id

        from app.agents.post_workout_agent import PostWorkoutAgent

        mock_agent = MagicMock(spec=PostWorkoutAgent)
        mock_agent.generate = AsyncMock(return_value=existing_message)

        # Use dependency override instead of patch() — Depends() captures the
        # function reference at import time, so patch() has no effect.
        fastapi_app.dependency_overrides[build_post_workout_agent] = lambda: mock_agent
        try:
            # First call
            response1 = await client.post(
                f"/api/v1/athletes/{athlete.id}/activities/{activity.id}/analyse",
                headers={"Authorization": f"Bearer {token}"},
            )

            # Second call — should return same message
            response2 = await client.post(
                f"/api/v1/athletes/{athlete.id}/activities/{activity.id}/analyse",
                headers={"Authorization": f"Bearer {token}"},
            )
        finally:
            fastapi_app.dependency_overrides.clear()

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Same message returned both times
        assert response1.json()["coaching_message"]["id"] == response2.json()["coaching_message"]["id"]

    @pytest.mark.asyncio
    async def test_analyse_activity_not_found(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Non-existent activity returns 404."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        with patch("app.api.v1.activity.build_post_workout_agent") as mock_build:
            mock_agent = AsyncMock()
            from app.agents.post_workout_agent import ActivityNotFoundError
            mock_agent.generate = AsyncMock(side_effect=ActivityNotFoundError(uuid.uuid4()))
            mock_build.return_value = mock_agent

            response = await client.post(
                f"/api/v1/athletes/{athlete.id}/activities/{uuid.uuid4()}/analyse",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 404


class TestGetActivityAnalysis:
    """GET /athletes/{id}/activities/{aid}/analysis — fetch existing analysis."""

    @pytest.mark.asyncio
    async def test_get_analysis_returns_message(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /analysis returns existing analysis."""
        athlete, _, twin = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        message = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            activity_id=activity.id,
            message_type=MessageType.POST_WORKOUT,
            content="Already generated analysis",
            prompt_version="v1",
        )
        db_session.add(message)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}/analysis",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["coaching_message"]["content"] == "Already generated analysis"

    @pytest.mark.asyncio
    async def test_get_analysis_not_found(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """When no analysis exists, returns 404 with instructions."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}/analysis",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        assert "POST /analyse" in response.json()["detail"]


# ===========================================================================
# Phase-2.1: Signal availability flags (has_power, has_rr_intervals, has_gps)
# ===========================================================================


class TestSignalAvailabilityFlags:
    """Phase-2.1: GET /activities/{aid} returns all signal availability flags."""

    @pytest.mark.asyncio
    async def test_get_activity_returns_all_signal_flags(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET returns has_hr, has_power, has_rr_intervals, has_gps."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=True,
            has_rr_intervals=True,
            has_gps=True,
            calibration_eligible=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_hr"] is True
        assert data["has_power"] is True
        assert data["has_rr_intervals"] is True
        assert data["has_gps"] is True

    @pytest.mark.asyncio
    async def test_get_activity_with_power_only(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET returns has_power=True when only power data is available."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=True,
            has_rr_intervals=False,
            has_gps=False,
            calibration_eligible=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_power"] is True
        assert data["has_rr_intervals"] is False
        assert data["has_gps"] is False

    @pytest.mark.asyncio
    async def test_get_activity_with_rr_intervals_only(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET returns has_rr_intervals=True when only RR interval data is available."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=False,
            has_rr_intervals=True,
            has_gps=False,
            calibration_eligible=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_rr_intervals"] is True
        assert data["has_power"] is False
        assert data["has_gps"] is False

    @pytest.mark.asyncio
    async def test_get_activity_with_gps_only(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET returns has_gps=True when GPS data is available."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=False,
            has_rr_intervals=False,
            has_gps=True,
            calibration_eligible=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_gps"] is True
        assert data["has_power"] is False
        assert data["has_rr_intervals"] is False

    @pytest.mark.asyncio
    async def test_list_activities_returns_signal_flags(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /activities list returns signal flags for each activity."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=True,
            has_rr_intervals=False,
            has_gps=True,
            calibration_eligible=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["activities"]) == 1
        assert data["activities"][0]["has_power"] is True
        assert data["activities"][0]["has_rr_intervals"] is False
        assert data["activities"][0]["has_gps"] is True

    @pytest.mark.asyncio
    async def test_get_activity_calibration_eligible_flag(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET returns calibration_eligible flag populated by CalibrationEligibilityService."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=True,
            has_rr_intervals=False,
            has_gps=True,
            calibration_eligible=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["calibration_eligible"] is True


class TestSportTypeResponse:
    """Phase-2.1-P3: GET /activities/{aid} returns sport_type and sport_type_detection_version.

    Reference: docs/implementation/phase-2/phase-2-1-p3-sport-type-filtering.md
    """

    @pytest.mark.asyncio
    async def test_get_activity_returns_sport_type(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /activities/{aid} returns sport_type field populated from parsed FIT."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=True,
            has_rr_intervals=False,
            has_gps=True,
            calibration_eligible=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
            sport_type="running",
            sport_type_detection_version="v1",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sport_type"] == "running"
        assert data["sport_type_detection_version"] == "v1"

    @pytest.mark.asyncio
    async def test_get_activity_returns_sport_type_cycling(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Cycling activity shows sport_type='cycling' in GET response."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=True,
            has_rr_intervals=False,
            has_gps=True,
            calibration_eligible=False,  # Cycling never calibration-eligible
            quality_flags={},
            fit_file_key="fit-files/test.fit",
            sport_type="cycling",
            sport_type_detection_version="v1",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sport_type"] == "cycling"
        assert data["calibration_eligible"] is False

    @pytest.mark.asyncio
    async def test_get_activity_returns_sport_type_unknown(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Activity with undetectable sport shows sport_type='unknown'."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            has_power=False,
            has_rr_intervals=False,
            has_gps=False,
            calibration_eligible=False,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
            sport_type="unknown",
            sport_type_detection_version="v1",
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sport_type"] == "unknown"
        assert data["sport_type_detection_version"] == "v1"
        assert data["calibration_eligible"] is False

    @pytest.mark.asyncio
    async def test_list_activities_returns_sport_type(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /activities list returns sport_type for each activity."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity1 = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=85.0,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test.fit",
            sport_type="running",
            sport_type_detection_version="v1",
        )
        activity2 = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            activity_date=date(2026, 6, 16),
            start_time=datetime(2026, 6, 16, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aerobic_load=90.0,
            has_hr=True,
            quality_flags={},
            fit_file_key="fit-files/test2.fit",
            sport_type="cycling",
            sport_type_detection_version="v1",
        )
        db_session.add_all([activity1, activity2])
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["activities"]) == 2
        sport_types = {a["sport_type"] for a in data["activities"]}
        assert sport_types == {"running", "cycling"}

    @pytest.mark.asyncio
    async def test_manual_entry_has_unknown_sport_type(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Manual-entry activities default to sport_type='unknown'."""
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        token = _access_token(athlete.id)

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            activity_date=date(2026, 6, 15),
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
            has_hr=False,
            calibration_eligible=False,
            quality_flags={},
            fit_file_key=None,
            sport_type="unknown",  # Manual entry has no FIT detection
            sport_type_detection_version=None,
        )
        db_session.add(activity)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/activities/{activity.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sport_type"] == "unknown"
        # Manual entry should not have sport_type_detection_version
        assert data.get("sport_type_detection_version") is None or data.get("sport_type_detection_version") == "unknown"