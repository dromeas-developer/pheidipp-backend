"""HTTP endpoint tests for the Phase-1.4 plan API surface.

Four endpoints mounted on ``app.api.v1.plan``:

* ``GET /api/v1/athletes/{athlete_id}/plan`` — the periodised plan.
* ``GET /api/v1/athletes/{athlete_id}/plan/sessions`` — PlannedSessions.
* ``GET /api/v1/athletes/{athlete_id}/plan/upcoming`` — next 5 sessions.
* ``GET /api/v1/athletes/{athlete_id}/plan/checkpoints`` — checkpoints.

All endpoints are read-only and behind ``require_self``. Cross-athlete
access returns 403 (NEVER 404); missing-plan access returns 404.

Reference plan:
docs/implementation/phase-1/phase-1-4-p1-plan-generation.md
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.payloads import _weekly_schedule_payload
from tests.utils.http_helpers import bearer_header, http_register


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
async def onboarded_with_plan(
    client: AsyncClient,
) -> tuple[str, str]:
    """Register + complete onboarding for a fresh athlete. Returns
    ``(athlete_id, access_token)``.

    Onboarding wires a PlanGenerationService into the transaction, so
    completing it is the canonical way to land an active plan for the
    HTTP surface test.

    The goal event date is set 16 weeks out — below the
    ``marathon + intermediate`` training-length-gate threshold (24
    weeks) so the gate proceeds and a plan is generated. 16 weeks
    produces enough weeks/phase variety to exercise the documented
    endpoints (five phases, ~80+ planned sessions, multiple
    checkpoints of each type) without colliding on the
    race-simulation/checkpoint slot at week ``total - 2``.
    """
    aid, tok = await http_register(client, f"plan-http-{uuid.uuid4()}@example.com")
    event_date = (date.today() + timedelta(weeks=16)).isoformat()
    payload = {
        "profile": {
            "timezone": "Europe/Lisbon",
            "training_window": None,
            "height_cm": 180.0,
        },
        "preferences": {
            "sport_background": "running_primary",
            "years_structured_training": 3,
            "training_time_of_day": "morning",
            "weekly_schedule": _weekly_schedule_payload(),
            "gps_source": "garmin_watch",
            "hr_source": "chest_strap_rr",
            "power_source": "none",
            "primary_training_platform": "manual",
        },
        "goal": {
            "goal_type": "race_event",
            "goal_event_type": "marathon",
            "goal_event_name": "Test Marathon",
            "goal_event_date": event_date,  # 16 weeks out — within
            # the marathon+intermediate gate threshold of 24 weeks.
            "custom_distance_km": None,
            "goal_description": None,
            "weekly_volume_hours": 6.0,
            "weekly_volume_km": 40.0,
            "fitness_level": 3,
            "recent_injury": None,
            "injury_severity": None,
            "target_distance_km": None,
            "target_time_minutes": None,
        },
    }
    response = await client.post(
        f"/api/v1/athletes/{aid}/onboarding",
        json=payload,
        headers=bearer_header(tok),
    )
    assert response.status_code == 201, response.text
    return aid, tok


# ---------------------------------------------------------------------------
# GET /plan
# ---------------------------------------------------------------------------


class TestGetPlanEndpoint:
    async def test_happy_path_returns_200_with_training_plan(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"]
        assert body["training_goal_id"]
        assert body["status"] == "active"
        assert body["phases"]
        # At minimum five documented phase labels.
        labels = [p["label"] for p in body["phases"]]
        assert "aerobic_base" in labels
        assert "taper" in labels
        assert "race_week" in labels

    async def test_returns_phase_definitions_and_distributions(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        # Both JSONB columns serialise as lists.
        assert isinstance(body["phase_definitions"], list)
        assert isinstance(body["weekly_distributions"], list)
        assert len(body["phase_definitions"]) == len(body["phases"])

    async def test_strategic_rationale_populated(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        """``strategic_rationale`` is non-null for race_event plans."""
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["strategic_rationale"] is not None
        assert "primary_driver" in body["strategic_rationale"]

    async def test_no_active_plan_returns_404(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, f"no-plan-{uuid.uuid4()}@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan",
            headers=bearer_header(tok),
        )
        assert response.status_code == 404

    async def test_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, f"cross-{uuid.uuid4()}@example.com"
        )
        other = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other}/plan",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403

    async def test_missing_bearer_returns_401(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, _ = onboarded_with_plan
        response = await client.get(f"/api/v1/athletes/{aid}/plan")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /plan/sessions
# ---------------------------------------------------------------------------


class TestGetPlanSessionsEndpoint:
    async def test_happy_path_returns_list(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/sessions",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list)
        assert len(body) > 0

        # Every session has status='scheduled' and a non-null phase_label.
        for session in body:
            assert session["status"] == "scheduled"
            assert session["phase_label"]
            assert session["target_date"]
            assert session["session_type"]

    async def test_sessions_ordered_by_target_date(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/sessions",
            headers=bearer_header(tok),
        )
        body = response.json()
        dates = [s["target_date"] for s in body]
        assert dates == sorted(dates)

    async def test_no_active_plan_returns_404(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, f"no-sess-{uuid.uuid4()}@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/sessions",
            headers=bearer_header(tok),
        )
        assert response.status_code == 404

    async def test_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, f"cross-sess-{uuid.uuid4()}@example.com"
        )
        other = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other}/plan/sessions",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /plan/upcoming
# ---------------------------------------------------------------------------


class TestGetPlanUpcomingEndpoint:
    async def test_happy_path_returns_upcoming_capped_at_5(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/upcoming",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "sessions" in body
        # Cap at 5.
        assert len(body["sessions"]) <= 5
        assert len(body["sessions"]) > 0

    async def test_all_upcoming_sessions_in_future(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        from datetime import date as _date, datetime

        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/upcoming",
            headers=bearer_header(tok),
        )
        body = response.json()
        today = datetime.now().date()
        for s in body["sessions"]:
            # Date strings compared against today.
            assert _date.fromisoformat(s["target_date"]) >= today

    async def test_no_active_plan_returns_404(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, f"no-up-{uuid.uuid4()}@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/upcoming",
            headers=bearer_header(tok),
        )
        assert response.status_code == 404

    async def test_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, f"cross-up-{uuid.uuid4()}@example.com"
        )
        other = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other}/plan/upcoming",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /plan/checkpoints
# ---------------------------------------------------------------------------


class TestGetPlanCheckpointsEndpoint:
    async def test_happy_path_returns_checkpoints(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/checkpoints",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list)
        assert len(body) > 0

    async def test_checkpoint_types_include_three_documented_ones(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/checkpoints",
            headers=bearer_header(tok),
        )
        body = response.json()
        types = {c["type"] for c in body}
        # Documented mix — calibration, benchmark, progress_review.
        assert "calibration" in types
        assert "benchmark" in types
        assert "progress_review" in types

    async def test_all_checkpoints_scheduled(
        self, client: AsyncClient, onboarded_with_plan: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_with_plan
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/checkpoints",
            headers=bearer_header(tok),
        )
        body = response.json()
        for c in body:
            assert c["status"] == "scheduled"
            assert c["planned_session_id"]
            assert c["target_metric"]

    async def test_no_active_plan_returns_404(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, f"no-cp-{uuid.uuid4()}@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/checkpoints",
            headers=bearer_header(tok),
        )
        assert response.status_code == 404

    async def test_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, f"cross-cp-{uuid.uuid4()}@example.com"
        )
        other = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other}/plan/checkpoints",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403
