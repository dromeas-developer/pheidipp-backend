"""API tests for the plan-router endpoints after the ``PlanQueryService`` refactor.

The Phase-2.7 Batch 3 plan-router layer fix (closing G-07) introduces
``PlanQueryService`` so the three read endpoints (``/plan/sessions``,
``/plan/upcoming``, ``/plan/checkpoints``) delegate to a service
instead of executing SQLAlchemy queries directly in the route
handlers. The user-visible contract — response shape, status codes,
data — is unchanged.

These tests verify:

* ``GET /plan`` returns 200 with the TrainingPlan body after the
  ``generate_plan`` worker task completes (scenario 11).
* The three sub-endpoints return the same response shape before and
  after the refactor (scenario 23).

Reference plan: ``docs/implementation/phase-2/phase-2-7/batch-3-event-flow-plan-router-fix.md``
Scenarios 11, 23.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

import app.worker.app as worker_module
from app.db.session import AsyncSessionLocal as _production_session_local
from tests.utils.http_helpers import bearer_header, http_register


@pytest.fixture
async def onboarded_athlete_with_plan(
    client: AsyncClient,
    test_session_local: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[uuid.UUID, str]:
    """Register + complete onboarding, then run the ``generate_plan``
    worker task in-process so the athlete ends up with an active plan.

    This is the same data-setup pattern used by the existing
    ``tests/api/test_plan_endpoints.py::onboarded_with_plan`` fixture;
    duplicated here so the async-specific tests don't have to depend
    on the order-of-fixtures contract of the existing fixture.
    """
    aid, tok = await http_register(
        client, f"plan-async-{uuid.uuid4()}@example.com"
    )
    from tests.payloads import onboarding_payload

    onboarding_resp = await client.post(
        f"/api/v1/athletes/{aid}/onboarding",
        json=onboarding_payload(),
        headers=bearer_header(tok),
    )
    assert onboarding_resp.status_code == 201, onboarding_resp.text

    monkeypatch.setattr(worker_module, "AsyncSessionLocal", test_session_local)
    try:
        await worker_module.generate_plan(athlete_id=str(aid))
    finally:
        monkeypatch.setattr(
            worker_module, "AsyncSessionLocal", _production_session_local
        )

    return aid, tok


class TestGetPlanAfterWorkerTask:
    """``GET /plan`` returns 200 with the TrainingPlan body after the
    ``generate_plan`` worker task has completed."""

    async def test_get_plan_returns_200_with_plan_body(
        self,
        client: AsyncClient,
        onboarded_athlete_with_plan: tuple[uuid.UUID, str],
    ) -> None:
        aid, tok = onboarded_athlete_with_plan

        response = await client.get(
            f"/api/v1/athletes/{aid}/plan",
            headers=bearer_header(tok),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "active"
        assert body["training_goal_id"] is not None
        assert body["twin_state_id"] is not None
        assert "phase_definitions" in body
        assert "phases" in body


class TestPlanRouterResponseShape:
    """The three sub-endpoints return the same response shape before
    and after the ``PlanQueryService`` refactor. The refactor is
    already shipped; this test pins the response shape so future
    refactors don't break the public contract."""

    async def test_get_plan_sessions_returns_expected_shape(
        self,
        client: AsyncClient,
        onboarded_athlete_with_plan: tuple[uuid.UUID, str],
    ) -> None:
        aid, tok = onboarded_athlete_with_plan

        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/sessions",
            headers=bearer_header(tok),
        )

        assert response.status_code == 200, response.text
        body: list[Any] = response.json()
        assert isinstance(body, list)
        if body:
            item = body[0]
            for key in (
                "id",
                "target_date",
                "session_type",
                "status",
                "weekly_plan_id",
                "training_plan_id",
            ):
                assert key in item, f"missing key {key} in /plan/sessions item"

    async def test_get_plan_upcoming_returns_expected_shape(
        self,
        client: AsyncClient,
        onboarded_athlete_with_plan: tuple[uuid.UUID, str],
    ) -> None:
        aid, tok = onboarded_athlete_with_plan

        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/upcoming",
            headers=bearer_header(tok),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert "sessions" in body
        assert isinstance(body["sessions"], list)
        assert len(body["sessions"]) <= 5

    async def test_get_plan_checkpoints_returns_expected_shape(
        self,
        client: AsyncClient,
        onboarded_athlete_with_plan: tuple[uuid.UUID, str],
    ) -> None:
        aid, tok = onboarded_athlete_with_plan

        response = await client.get(
            f"/api/v1/athletes/{aid}/plan/checkpoints",
            headers=bearer_header(tok),
        )

        assert response.status_code == 200, response.text
        body: list[Any] = response.json()
        assert isinstance(body, list)
        if body:
            item = body[0]
            for key in (
                "id",
                "planned_session_id",
                "type",
                "target_metric",
                "status",
            ):
                assert key in item, f"missing key {key} in /plan/checkpoints item"
