"""End-to-end behaviour test: register → onboarding → plan is live.

Mirrors the plan's exit-gate scenario in the **Implementation Steps**:

> "Onboarding → plan generation → GET /plan returns valid plan with
> phases"

The journey exercises the full HTTP surface for the Phase-1.4 closing
the loop: authentication, onboarding, the deferred ``generate_plan``
worker task (Phase-2.7 Batch 3, closing G-03), and the four read-only
plan endpoints.

The Phase-2.7 Batch 3 plan decouples plan generation from the
onboarding transaction — ``POST /onboarding`` returns 201 before the
``generate_plan`` procrastinate task runs. To assert the public plan
endpoints, the test invokes the worker task in-process via the
standard ``AsyncSessionLocal`` monkey-patch (the same pattern as
``test_outbox_publisher_task_integration.py``).

Reference plan:
docs/implementation/phase-1/phase-1-4-p1-plan-generation.md
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

import app.worker.app as worker_module
from app.db.session import AsyncSessionLocal as _production_session_local
from tests.payloads import weekly_schedule_payload
from tests.utils.http_helpers import bearer_header, http_register


@pytest.fixture
async def register_payload() -> dict[str, Any]:
    """Fresh registration payload — unique email avoids 409 collisions."""
    return {
        "email": f"plan-journey-{uuid.uuid4()}@example.com",
        "password": "ValidPass123!",
        "profile": {
            "date_of_birth": "1992-04-15",
            "sex": "not_specified",
            "height_cm": 180.0,
        },
    }


@pytest.fixture
async def onboarding_payload() -> dict[str, Any]:
    """Default onboarding payload — race_event, marathon, dates configured
    far enough out to pass the training-length gate."""
    from datetime import date, timedelta

    return {
        "profile": {
            "timezone": "Europe/Lisbon",
            "training_window": None,
            "height_cm": 180.0,
        },
        "preferences": {
            "sport_background": "running_primary",
            "years_structured_training": 3,
            "training_time_of_day": "morning",
            "weekly_schedule": weekly_schedule_payload(),
            "gps_source": "garmin_watch",
            "hr_source": "chest_strap_rr",
            "power_source": "none",
            "primary_training_platform": "manual",
        },
        "goal": {
            "goal_type": "race_event",
            "goal_event_type": "marathon",
            "goal_event_name": "Test Marathon",
            "goal_event_date": (
                date.today() + timedelta(days=120)
            ).isoformat(),
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


class TestOnboardingToPlanJourney:
    """End-to-end journey — register, complete onboarding, run the
    deferred ``generate_plan`` worker task, exercise the plan
    endpoints, and assert the documented contract."""

    async def _run_generate_plan(
        self,
        athlete_id: uuid.UUID,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(worker_module, "AsyncSessionLocal", test_session_local)
        try:
            await worker_module.generate_plan(athlete_id=str(athlete_id))
        finally:
            monkeypatch.setattr(
                worker_module, "AsyncSessionLocal", _production_session_local
            )

    async def test_full_journey_produces_a_valid_plan(
        self,
        client: AsyncClient,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
        register_payload: dict[str, Any],
        onboarding_payload: dict[str, Any],
    ) -> None:
        # 1. Register.
        register_response = await client.post(
            "/api/v1/auth/register", json=register_payload
        )
        assert register_response.status_code == 201, register_response.text
        body = register_response.json()
        aid = body["athlete"]["id"]
        access_token = body["access_token"]

        # 2. Complete onboarding (returns 201; plan generation is now
        #    deferred to the generate_plan worker task — Phase-2.7
        #    Batch 3, G-03).
        ob_response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload,
            headers=bearer_header(access_token),
        )
        assert ob_response.status_code == 201, ob_response.text
        ob_body = ob_response.json()
        assert ob_body["onboarding_complete"] is True
        assert ob_body["twin_state_id"]
        assert ob_body["training_goal_id"]

        # 2a. Run the deferred generate_plan task in-process so the
        #     plan is available for the read endpoints.
        await self._run_generate_plan(aid, test_session_local, monkeypatch)

        # 3. GET /plan must now return a valid TrainingPlanResponse.
        plan_response = await client.get(
            f"/api/v1/athletes/{aid}/plan",
            headers=bearer_header(access_token),
        )
        assert plan_response.status_code == 200, plan_response.text
        plan = plan_response.json()
        assert plan["id"]
        assert plan["status"] == "active"
        labels = [p["label"] for p in plan["phases"]]
        # Five-phase template ends in taper + race_week.
        assert labels == [
            "aerobic_base",
            "threshold_build",
            "specific_endurance",
            "taper",
            "race_week",
        ]
        # strategic_rationale is set for race_event.
        assert plan["strategic_rationale"] is not None

        # 4. GET /plan/sessions returns populated list.
        sessions_response = await client.get(
            f"/api/v1/athletes/{aid}/plan/sessions",
            headers=bearer_header(access_token),
        )
        assert sessions_response.status_code == 200
        sessions: list[dict[str, Any]] = sessions_response.json()
        assert isinstance(sessions, list)
        assert len(sessions) > 0
        for s in sessions:
            assert s["status"] == "scheduled"

        # 5. GET /plan/upcoming returns up to 5 future sessions.
        upcoming_response = await client.get(
            f"/api/v1/athletes/{aid}/plan/upcoming",
            headers=bearer_header(access_token),
        )
        assert upcoming_response.status_code == 200
        upcoming = upcoming_response.json()
        assert 0 < len(upcoming["sessions"]) <= 5

        # 6. GET /plan/checkpoints returns at least one of each type.
        cp_response = await client.get(
            f"/api/v1/athletes/{aid}/plan/checkpoints",
            headers=bearer_header(access_token),
        )
        assert cp_response.status_code == 200
        cps = cp_response.json()
        cps_types = {c["type"] for c in cps}
        assert "calibration" in cps_types
        assert "benchmark" in cps_types
        assert "progress_review" in cps_types

    async def test_cross_athlete_cannot_access_other_athletes_plan(
        self,
        client: AsyncClient,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
        onboarding_payload: dict[str, Any],
    ) -> None:
        # First athlete — onboards + gets a plan.
        first_register = {
            "email": f"plan-journey-A-{uuid.uuid4()}@example.com",
            "password": "ValidPass123!",
            "profile": {
                "date_of_birth": "1990-01-01",
                "sex": "not_specified",
                "height_cm": 180.0,
            },
        }
        first_response = await client.post(
            "/api/v1/auth/register", json=first_register
        )
        first_body = first_response.json()
        first_id = first_body["athlete"]["id"]
        first_token = first_body["access_token"]
        ob = await client.post(
            f"/api/v1/athletes/{first_id}/onboarding",
            json=onboarding_payload,
            headers=bearer_header(first_token),
        )
        assert ob.status_code == 201

        await self._run_generate_plan(first_id, test_session_local, monkeypatch)

        # Second athlete — separate JWT.
        second_register = {
            "email": f"plan-journey-B-{uuid.uuid4()}@example.com",
            "password": "ValidPass123!",
            "profile": {
                "date_of_birth": "1990-01-01",
                "sex": "not_specified",
                "height_cm": 180.0,
            },
        }
        second_response = await client.post(
            "/api/v1/auth/register", json=second_register
        )
        second_token = second_response.json()["access_token"]

        # Second athlete tries to read first athlete's plan → 403.
        plan_response = await client.get(
            f"/api/v1/athletes/{first_id}/plan",
            headers=bearer_header(second_token),
        )
        assert plan_response.status_code == 403

        # Same athlete — fetching their own plan still works.
        own_response = await client.get(
            f"/api/v1/athletes/{first_id}/plan",
            headers=bearer_header(first_token),
        )
        assert own_response.status_code == 200

    async def test_journey_with_no_onboarding_returns_404_on_plan_endpoints(
        self,
        client: AsyncClient,
    ) -> None:
        """A registered athlete who has not completed onboarding
        receives 404 from each plan endpoint."""
        aid, tok = await http_register(
            client, f"no-ob-{uuid.uuid4()}@example.com"
        )
        for path in (
            "/plan",
            "/plan/sessions",
            "/plan/upcoming",
            "/plan/checkpoints",
        ):
            response = await client.get(
                f"/api/v1/athletes/{aid}{path}",
                headers=bearer_header(tok),
            )
            assert response.status_code == 404, (
                f"GET {path}: expected 404, got {response.status_code}"
            )

    async def test_plan_endpoints_return_404_between_onboarding_and_worker_task(
        self,
        client: AsyncClient,
        register_payload: dict[str, Any],
        onboarding_payload: dict[str, Any],
    ) -> None:
        """The Phase-2.7 Batch 3 plan decouples plan generation from
        the onboarding transaction. After POST /onboarding returns 201,
        GET /plan must return 404 until the ``generate_plan`` worker
        task runs. This is the new contract — pre-Batch-3 the plan
        was generated synchronously and 404 was impossible here."""
        register_response = await client.post(
            "/api/v1/auth/register", json=register_payload
        )
        body = register_response.json()
        aid = body["athlete"]["id"]
        access_token = body["access_token"]

        ob_response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload,
            headers=bearer_header(access_token),
        )
        assert ob_response.status_code == 201, ob_response.text
        assert ob_response.json()["onboarding_complete"] is True

        for path in (
            "/plan",
            "/plan/sessions",
            "/plan/upcoming",
            "/plan/checkpoints",
        ):
            response = await client.get(
                f"/api/v1/athletes/{aid}{path}",
                headers=bearer_header(access_token),
            )
            assert response.status_code == 404, (
                f"GET {path}: expected 404 before generate_plan runs, "
                f"got {response.status_code}: {response.text}"
            )
