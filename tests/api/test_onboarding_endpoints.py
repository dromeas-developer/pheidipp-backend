"""HTTP endpoint tests for the onboarding API surface.

Exercises the eight Phase-1.3 endpoints mounted on
``app.api.v1.onboarding`` against the real FastAPI app through
``httpx.AsyncClient``. Coverage:

* ``POST /athletes/{id}/onboarding`` — 201 happy path, 409 idempotency
  guard, 422 invalid input, 422 rejected goal types, 403 cross-athlete.
* ``GET  /athletes/{id}/onboarding`` — status flags before/after.
* ``GET  /athletes/{id}/profile`` — 200 always (Phase-1.1 invariant).
* ``PATCH /athletes/{id}/profile`` — 200 mutable fields, 422 immutable
  fields, 403 cross-athlete.
* ``GET  /athletes/{id}/preferences`` — 404 before onboarding, 200 after.
* ``PATCH /athletes/{id}/preferences`` — partial 200, 404 before, 403.
* ``GET  /athletes/{id}/twin`` — 404 before, 200 after.
* ``GET  /athletes/{id}/twin/history`` — empty list before, single record
  after, ``?limit`` clamped via ``le=100``, 403 cross-athlete.

``require_self`` is exercised on every endpoint — cross-athlete access
returns 403 (NEVER 404), so authentication and authorization failures
remain distinguishable.

Reference plan:
docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.payloads import (
    _onboarding_payload,
    _preferences_patch_payload,
    _profile_patch_payload,
    _register_payload,
    _weekly_schedule_payload,
)
from tests.utils.assertions import assert_no_secrets_in_text
from tests.utils.http_helpers import bearer_header, http_register


@pytest.fixture
async def onboarded_athlete(client: AsyncClient):
    """Register + complete onboarding; return
    ``(athlete_id, access_token, second_id)`` so tests can also probe
    the cross-athlete guard with a co-registered athlete in the same
    session."""
    aid, tok = await http_register(
        client, "onboarding-http@example.com"
    )

    payload = _onboarding_payload()
    response = await client.post(
        f"/api/v1/athletes/{aid}/onboarding",
        json=payload,
        headers=bearer_header(tok),
    )
    assert response.status_code == 201, response.text
    return aid, tok


# ---------------------------------------------------------------------------
# POST /athletes/{athlete_id}/onboarding
# ---------------------------------------------------------------------------


class TestCompleteOnboardingEndpoint:
    """``POST /api/v1/athletes/{id}/onboarding``."""

    async def test_happy_path_returns_201(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "happy-path-onboarding@example.com"
        )
        payload = _onboarding_payload()
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=payload,
            headers=bearer_header(tok),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        # Identifiers returned.
        assert body["athlete_id"] == str(aid)
        assert body["onboarding_complete"] is True
        assert "twin_state_id" in body
        assert "training_goal_id" in body
        assert "data_tier" in body
        assert body["data_tier"] in {1, 2, 3, 4, 5, 6}
        assert body["confidence_level"] == "low"

    async def test_happy_path_remembers_dob_derived_thresholds(
        self, client: AsyncClient
    ) -> None:
        """After onboarding, ``GET /twin`` exposes the dob-derived
        thresholds the bootstrap wired inline."""
        aid, tok = await http_register(
            client, "thresholds-via-http@example.com"
        )
        await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=_onboarding_payload(),
            headers=bearer_header(tok),
        )
        twin = await client.get(
            f"/api/v1/athletes/{aid}/twin",
            headers=bearer_header(tok),
        )
        assert twin.status_code == 200
        body = twin.json()
        assert float(body["lt1_hr_bpm"]) == pytest.approx(138.0)
        assert float(body["lt2_hr_bpm"]) == pytest.approx(161.0)
        assert body["trigger"] == "questionnaire"
        assert body["confidence_level"] == "low"
        assert body["readiness_level"] == "green"
        assert body["activity_id"] is None

    async def test_second_call_returns_409(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=_onboarding_payload(),
            headers=bearer_header(tok),
        )
        assert response.status_code == 409
        assert "already" in response.json()["detail"].lower()

    async def test_invalid_timezone_returns_422(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "bad-timezone@example.com"
        )
        payload = _onboarding_payload(timezone="Not/A/Real/Zone")
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=payload,
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_invalid_goal_type_returns_422(
        self, client: AsyncClient
    ) -> None:
        """The wire-format schema rejects ``fitness_improvement`` —
        the GoalType enum is strict at the boundary."""
        aid, tok = await http_register(
            client, "bad-goal-type@example.com"
        )
        payload = _onboarding_payload()
        payload["goal"]["goal_type"] = "fitness_improvement"
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=payload,
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_race_event_missing_required_field_returns_422(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "race-event-missing@example.com"
        )
        payload = _onboarding_payload(goal_kind="race_event")
        # Drop the required event name.
        del payload["goal"]["goal_event_name"]
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=payload,
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_target_performance_missing_required_field_returns_422(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "tp-missing@example.com"
        )
        payload = _onboarding_payload(goal_kind="target_performance")
        del payload["goal"]["target_distance_km"]
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=payload,
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_target_performance_goal_succeeds(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "tp-ok@example.com"
        )
        payload = _onboarding_payload(goal_kind="target_performance")
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=payload,
            headers=bearer_header(tok),
        )
        assert response.status_code == 201, response.text

    async def test_missing_weekly_schedule_day_returns_422(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "missing-day@example.com"
        )
        payload = _onboarding_payload()
        # Drop sunday from the weekly schedule.
        del payload["preferences"]["weekly_schedule"]["sunday"]
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=payload,
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        """A JWT for athlete A hitting athlete B's onboarding path
        returns 403, never 404."""
        aid_a, tok_a = await http_register(
            client, "cross-athlete-a@example.com"
        )
        await http_register(
            client, "cross-athlete-b@example.com"
        )

        # Try to onboard athlete B using athlete A's token.
        response = await client.post(
            f"/api/v1/athletes/{aid_a}/onboarding",
            json=_onboarding_payload(),
            headers=bearer_header(tok_a),
        )
        # Athlete A is the JWT owner — 201, no cross-athlete mismatch.
        # To exercise cross-athlete 403 we send athlete A's bearer
        # against an *unknown* athlete UUID.
        unknown_id = str(uuid.uuid4())
        cross = await client.post(
            f"/api/v1/athletes/{unknown_id}/onboarding",
            json=_onboarding_payload(),
            headers=bearer_header(tok_a),
        )
        assert cross.status_code == 403
        # Sanity: keeper-call still works.
        assert response.status_code == 201
        _ = aid_a

    async def test_missing_bearer_returns_401(
        self, client: AsyncClient
    ) -> None:
        aid, _ = await http_register(
            client, "missing-bearer@example.com"
        )
        response = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=_onboarding_payload(),
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /athletes/{athlete_id}/onboarding
# ---------------------------------------------------------------------------


class TestGetOnboardingStatusEndpoint:
    """``GET /api/v1/athletes/{id}/onboarding`` — status flags."""

    async def test_status_before_onboarding(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "status-pre-http@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/onboarding",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["onboarding_complete"] is False
        assert body["has_profile"] is True
        assert body["has_preferences"] is False
        assert body["has_training_goal"] is False
        assert body["has_twin_state"] is False

    async def test_status_after_onboarding(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.get(
            f"/api/v1/athletes/{aid}/onboarding",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["onboarding_complete"] is True
        assert body["has_profile"] is True
        assert body["has_preferences"] is True
        assert body["has_training_goal"] is True
        assert body["has_twin_state"] is True

    async def test_status_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, "status-cross@example.com"
        )
        other_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other_id}/onboarding",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /athletes/{athlete_id}/profile
# ---------------------------------------------------------------------------


class TestGetProfileEndpoint:
    async def test_get_profile_returns_200_post_registration(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "profile-get@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/profile",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["athlete_id"] == str(aid)
        assert body["date_of_birth"]
        # Per the architecture, personalisation model JSONBs are
        # excluded from the public view.
        for forbidden in (
            "gap_curve_model",
            "weather_response_model",
            "banister_constants",
            "cycle_personal_model",
            "objective_thresholds",
        ):
            assert forbidden not in body

    async def test_profile_response_excludes_secrets(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "profile-no-leak@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/profile",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        assert_no_secrets_in_text(response.text, message="/athletes/{id}/profile response")

    async def test_get_profile_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, "profile-cross@example.com"
        )
        other_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other_id}/profile",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /athletes/{athlete_id}/profile
# ---------------------------------------------------------------------------


class TestPatchProfileEndpoint:
    async def test_mutable_fields_patch_succeeds(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/profile",
            json=_profile_patch_payload(
                height_cm=183.5,
                location_lat=38.7,
                location_lng=-9.1,
                training_window={
                    "start": "06:00",
                    "end": "20:00",
                    "timezone": "Europe/Lisbon",
                },
            ),
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert float(body["height_cm"]) == pytest.approx(183.5)
        assert float(body["location_lat"]) == pytest.approx(38.7)
        assert float(body["location_lng"]) == pytest.approx(-9.1)
        assert body["training_window"]["start"] == "06:00"

    async def test_immutable_date_of_birth_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/profile",
            json={
                "height_cm": 180.0,
                "date_of_birth": "1985-05-05",
            },
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_immutable_sex_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/profile",
            json={"sex": "male"},
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_immutable_timezone_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/profile",
            json={"timezone": "America/New_York"},
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_extra_field_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        """The PATCH schema uses ``extra='forbid'`` — exactly the four
        documented mutable fields are accepted."""
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/profile",
            json={
                "height_cm": 180.0,
                "gap_curve_model": {"r_squared": 0.5},
            },
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_patch_profile_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, "patch-profile-cross@example.com"
        )
        other_id = str(uuid.uuid4())
        response = await client.patch(
            f"/api/v1/athletes/{other_id}/profile",
            json={"height_cm": 180.0},
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /athletes/{athlete_id}/preferences
# ---------------------------------------------------------------------------


class TestGetPreferencesEndpoint:
    async def test_get_preferences_returns_404_before_onboarding(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "get-prefs-pre@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/preferences",
            headers=bearer_header(tok),
        )
        assert response.status_code == 404
        assert "preferences" in response.json()["detail"].lower()

    async def test_get_preferences_returns_200_after_onboarding(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.get(
            f"/api/v1/athletes/{aid}/preferences",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["athlete_id"] == str(aid)
        # Weekly schedule structured JSON round-tripped.
        assert "monday" in body["weekly_schedule"]
        assert body["weekly_schedule"]["monday"]["available"] is True

    async def test_get_preferences_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, "get-prefs-cross@example.com"
        )
        other_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other_id}/preferences",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /athletes/{athlete_id}/preferences
# ---------------------------------------------------------------------------


class TestPatchPreferencesEndpoint:
    async def test_patch_weekly_schedule_flips_only_saturday(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=_preferences_patch_payload(
                weekly_schedule={"saturday": {"available": False}}
            ),
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # Saturday flipped; others preserved.
        assert body["weekly_schedule"]["saturday"]["available"] is False
        assert body["weekly_schedule"]["saturday"]["max_hours"] == 3.0
        assert body["weekly_schedule"]["monday"]["available"] is True
        assert body["weekly_schedule"]["monday"]["max_hours"] == 1.5

    async def test_patch_idempotent(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        sat_patch = _preferences_patch_payload(
            weekly_schedule={"saturday": {"available": False}}
        )
        first = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=sat_patch,
            headers=bearer_header(tok),
        )
        second = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=sat_patch,
            headers=bearer_header(tok),
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["weekly_schedule"] == (
            second.json()["weekly_schedule"]
        )

    async def test_patch_weekly_schedule_partial_merge_preserves_omitted_days(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        """A partial ``weekly_schedule`` patch merges at the day level.

        Sending a payload that lists six of the seven days (Sunday
        omitted) succeeds with ``200`` and leaves the stored Sunday
        entry untouched. The seven-day XOR check belongs to the POST
        path; the PATCH schema accepts the partial subset explicitly
        because the day-level merge is the entire point of the public
        contract.
        """
        aid, tok = onboarded_athlete
        # Drop Sunday from a full schedule — surface a partial patch.
        partial = _weekly_schedule_payload()
        del partial["sunday"]
        response = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=_preferences_patch_payload(weekly_schedule=partial),
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # The omitted Sunday kept its stored value (max_hours = 1.0).
        assert (
            body["weekly_schedule"]["sunday"]["max_hours"]
            == (_weekly_schedule_payload())["sunday"]["max_hours"]
        )
        # The explicit days were written through.
        for day in partial:
            assert body["weekly_schedule"][day] == partial[day]

    async def test_patch_weekly_schedule_unknown_day_key_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        """Unknown weekday keys are still rejected in a PATCH body.

        Only the seven canonical days are accepted in
        ``weekly_schedule``; a key like ``"funday"`` must 422 so a
        buggy client cannot drop schedule entries silently.
        """
        aid, tok = onboarded_athlete
        bad = {"funday": {"available": True, "max_hours": 1.0}}
        response = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=_preferences_patch_payload(weekly_schedule=bad),
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_patch_weekly_schedule_partial_day_config_succeeds(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        """A partial per-day payload — only one field set — is accepted.

        ``WeeklyScheduleDayPatchIn`` declares every field optional so
        a delta like ``{"saturday": {"available": false}}`` passes
        validation. The PATCH contract is "merge at the day level;
        top-level fields overwrite", which means the omitted fields
        on the patched day are preserved.
        """
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=_preferences_patch_payload(
                weekly_schedule={"saturday": {"available": False}}
            ),
            headers=bearer_header(tok),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # Saturday: only `available` flipped; the other three fields
        # must keep their stored values.
        sat = body["weekly_schedule"]["saturday"]
        assert sat["available"] is False
        assert sat["max_hours"] == 3.0
        assert sat["long_workout"] is True
        assert sat["doubles_eligible"] is False
        # Other days entirely untouched.
        assert body["weekly_schedule"]["monday"]["available"] is True
        assert body["weekly_schedule"]["sunday"]["max_hours"] == 1.0

    async def test_patch_weekly_schedule_invalid_field_value_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        """Per-field validation still fires on partial patches.

        ``max_hours`` is bounded ``[0, 24]``; sending ``99`` must 422
        even when the rest of the day payload is valid. Same rule
        applies to a non-bool ``available``.
        """
        aid, tok = onboarded_athlete
        response = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=_preferences_patch_payload(
                weekly_schedule={"saturday": {"max_hours": 99}}
            ),
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

        response = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=_preferences_patch_payload(
                weekly_schedule={"sunday": {"available": "maybe"}}
            ),
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_patch_preferences_returns_404_before_onboarding(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "patch-prefs-pre@example.com"
        )
        response = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json={"years_structured_training": 5},
            headers=bearer_header(tok),
        )
        assert response.status_code == 404

    async def test_patch_preferences_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, "patch-prefs-cross@example.com"
        )
        other_id = str(uuid.uuid4())
        response = await client.patch(
            f"/api/v1/athletes/{other_id}/preferences",
            json={"years_structured_training": 5},
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /athletes/{athlete_id}/twin
# ---------------------------------------------------------------------------


class TestGetTwinStateEndpoint:
    async def test_get_twin_returns_404_before_onboarding(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "twin-pre@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/twin",
            headers=bearer_header(tok),
        )
        assert response.status_code == 404

    async def test_get_twin_returns_200_after_onboarding(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.get(
            f"/api/v1/athletes/{aid}/twin",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["athlete_id"] == str(aid)
        assert body["confidence_level"] == "low"
        assert body["trigger"] == "questionnaire"
        assert body["readiness_level"] == "green"
        assert body["activity_id"] is None

    async def test_get_twin_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, "twin-cross@example.com"
        )
        other_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other_id}/twin",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /athletes/{athlete_id}/twin/history
# ---------------------------------------------------------------------------


class TestGetTwinHistoryEndpoint:
    async def test_history_is_empty_before_onboarding(
        self, client: AsyncClient
    ) -> None:
        aid, tok = await http_register(
            client, "history-pre@example.com"
        )
        response = await client.get(
            f"/api/v1/athletes/{aid}/twin/history",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["count"] == 0

    async def test_history_returns_one_after_onboarding(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.get(
            f"/api/v1/athletes/{aid}/twin/history",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["athlete_id"] == str(aid)

    async def test_history_limit_query_parameter_respected(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.get(
            f"/api/v1/athletes/{aid}/twin/history?limit=1",
            headers=bearer_header(tok),
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1

    async def test_history_limit_above_max_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        """``?limit=101`` is outside the ``le=100`` bound."""
        aid, tok = onboarded_athlete
        response = await client.get(
            f"/api/v1/athletes/{aid}/twin/history?limit=101",
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_history_limit_zero_returns_422(
        self, client: AsyncClient, onboarded_athlete: tuple[str, str]
    ) -> None:
        aid, tok = onboarded_athlete
        response = await client.get(
            f"/api/v1/athletes/{aid}/twin/history?limit=0",
            headers=bearer_header(tok),
        )
        assert response.status_code == 422

    async def test_history_cross_athlete_returns_403(
        self, client: AsyncClient
    ) -> None:
        _, tok = await http_register(
            client, "history-cross@example.com"
        )
        other_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/athletes/{other_id}/twin/history",
            headers=bearer_header(tok),
        )
        assert response.status_code == 403
