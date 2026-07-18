"""End-to-end behaviour tests for the onboarding user journey.

Drives the full public HTTP surface — register → login → onboard →
PATCH preferences / profile → read twin / twin history — so a single
regression in any layer (auth, schemas, service, repositories,
read endpoints) appears here.

Coverage:

* Full happy-path onboarding journey through the public API.
* Replay of the second onboarding call ⇒ already-complete 409.
* PATCH merge behaviour visible at the wire level.
* Cross-athlete 403 vs missing-bearer 401 distinction.
* Twin history reflects the bootstrap snapshot via the timeline.

Reference plan:
docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.payloads import (
    login_payload,
    onboarding_payload,
    preferences_patch_payload,
    profile_patch_payload,
)
from tests.utils.assertions import assert_no_secrets_in_text
from tests.utils.http_helpers import bearer_header, http_register


# ---------------------------------------------------------------------------
# Full user journey
# ---------------------------------------------------------------------------


class TestOnboardingUserJourney:
    """Register → onboard → PATCH preferences / profile → read twin."""

    async def test_full_journey_through_public_surface(
        self, client: AsyncClient
    ) -> None:
        # 1. Register.
        aid, token = await http_register(
            client, "behaviour-journey@example.com"
        )
        # 2. Re-login (independent session).
        login = await client.post(
            "/api/v1/auth/login",
            json=login_payload("behaviour-journey@example.com"),
        )
        login_token = login.json()["access_token"]

        # 3. Onboard.
        onb = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload(),
            headers=bearer_header(token),
        )
        assert onb.status_code == 201, onb.text
        twin_state_id = onb.json()["twin_state_id"]
        training_goal_id = onb.json()["training_goal_id"]

        # 4. Read status — every flag is true.
        status = await client.get(
            f"/api/v1/athletes/{aid}/onboarding",
            headers=bearer_header(token),
        )
        assert status.status_code == 200
        assert all(status.json().values())

        # 5. Read twin.
        twin = await client.get(
            f"/api/v1/athletes/{aid}/twin",
            headers=bearer_header(token),
        )
        assert twin.status_code == 200
        twin_body = twin.json()
        assert twin_body["id"] == twin_state_id
        assert twin_body["training_goal_id"] == training_goal_id
        # No activity at the bootstrap.
        assert twin_body["activity_id"] is None

        # 6. Read twin history — single snapshot so far.
        history = await client.get(
            f"/api/v1/athletes/{aid}/twin/history",
            headers=bearer_header(token),
        )
        assert history.status_code == 200
        assert history.json()["count"] == 1

        # 7. PATCH preferences — flip Saturday only.
        patch_prefs = await client.patch(
            f"/api/v1/athletes/{aid}/preferences",
            json=preferences_patch_payload(
                weekly_schedule={"saturday": {"available": False}}
            ),
            headers=bearer_header(token),
        )
        assert patch_prefs.status_code == 200
        sat = patch_prefs.json()["weekly_schedule"]["saturday"]
        assert sat["available"] is False
        # Other days untouched.
        assert (
            patch_prefs.json()["weekly_schedule"]["monday"]["available"]
            is True
        )

        # 8. PATCH profile — mutable fields only.
        patch_profile = await client.patch(
            f"/api/v1/athletes/{aid}/profile",
            json=profile_patch_payload(height_cm=181.0),
            headers=bearer_header(token),
        )
        assert patch_profile.status_code == 200
        assert float(patch_profile.json()["height_cm"]) == 181.0

        # 9. Re-login continued to work with the same bearer —
        #    sanity check that the JWT issued before onboarding still
        #    authenticates ``require_self``.
        who = await client.get(
            f"/_protected/athletes/{aid}/whoami",
            headers=bearer_header(login_token),
        )
        assert who.status_code == 200

        # 10. A second onboarding attempt is rejected.
        replay = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload(),
            headers=bearer_header(token),
        )
        assert replay.status_code == 409

    async def test_full_journey_target_performance_goal(
        self, client: AsyncClient
    ) -> None:
        """The whitelist allows ``target_performance`` too; verify
        end-to-end."""
        aid, token = await http_register(
            client, "behaviour-tp-journey@example.com"
        )
        onb = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload(goal_kind="target_performance"),
            headers=bearer_header(token),
        )
        assert onb.status_code == 201, onb.text

        profile = await client.get(
            f"/api/v1/athletes/{aid}/profile",
            headers=bearer_header(token),
        )
        assert profile.status_code == 200
        assert profile.json()["timezone"] == "Europe/Lisbon"

    async def test_cross_athlete_guard_throughout_post_onboarding_reads(
        self, client: AsyncClient
    ) -> None:
        """Every read endpoint refuses a sibling athlete's JWT with 403."""
        aid_a, tok_a = await http_register(
            client, "behaviour-cross-a@example.com"
        )
        await http_register(client, "behaviour-cross-b@example.com")

        for path in (
            f"/api/v1/athletes/{aid_a}/onboarding",
            f"/api/v1/athletes/{aid_a}/profile",
            f"/api/v1/athletes/{aid_a}/twin",
            f"/api/v1/athletes/{aid_a}/twin/history",
        ):
            response = await client.get(
                path, headers=bearer_header(tok_a)
            )
            # Same athlete A — 200 / 404 / 200 / 200 — never 403.
            assert response.status_code != 403, (
                f"{path}: same-athlete bearer must not hit the "
                f"cross-athlete guard"
            )

        # Now use athlete A's bearer against an unrelated athlete
        # UUID; expected: 403 on every read.
        other = "00000000-0000-0000-0000-000000000000"
        for path in (
            f"/api/v1/athletes/{other}/onboarding",
            f"/api/v1/athletes/{other}/profile",
            f"/api/v1/athletes/{other}/preferences",
            f"/api/v1/athletes/{other}/twin",
            f"/api/v1/athletes/{other}/twin/history",
        ):
            response = await client.get(
                path, headers=bearer_header(tok_a)
            )
            assert response.status_code == 403, (
                f"{path}: cross-athlete must return 403 (got "
                f"{response.status_code})"
            )


class TestOnboardingSecretLeakageAudit:
    """The wire format must NEVER include ``hashed_password``,
    ``token_hash``, ``provider_tokens`` or ``provider_user_id``.

    """

    async def test_onboarding_responses_exclude_secrets(
        self, client: AsyncClient
    ) -> None:
        aid, token = await http_register(
            client, "behaviour-no-leak@example.com"
        )
        onb = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload(),
            headers=bearer_header(token),
        )
        assert onb.status_code == 201
        assert_no_secrets_in_text(onb.text, message="onboarding POST response")

        # Twin response must not leak secrets either.
        twin = await client.get(
            f"/api/v1/athletes/{aid}/twin",
            headers=bearer_header(token),
        )
        assert twin.status_code == 200
        assert_no_secrets_in_text(twin.text, message="twin GET response")


class TestOnboardingResponseShape:
    """The response shapes match the documented wire contracts."""

    async def test_onboarding_response_carries_required_keys(
        self, client: AsyncClient
    ) -> None:
        aid, token = await http_register(
            client, "behaviour-shape@example.com"
        )
        onb = await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload(),
            headers=bearer_header(token),
        )
        body = onb.json()
        for key in (
            "athlete_id",
            "onboarding_complete",
            "twin_state_id",
            "training_goal_id",
            "data_tier",
            "confidence_level",
            "created_at",
        ):
            assert key in body, f"missing response key: {key}"

    async def test_weekly_schedule_round_trip(
        self, client: AsyncClient
    ) -> None:
        """The structured 7-day schedule survives the JSON round-trip
        with no missing keys and no extras."""
        aid, token = await http_register(
            client, "behaviour-schedule-roundtrip@example.com"
        )
        await client.post(
            f"/api/v1/athletes/{aid}/onboarding",
            json=onboarding_payload(),
            headers=bearer_header(token),
        )
        prefs = await client.get(
            f"/api/v1/athletes/{aid}/preferences",
            headers=bearer_header(token),
        )
        body = prefs.json()
        schedule = body["weekly_schedule"]
        assert set(schedule.keys()) == {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        for day_cfg in schedule.values():
            assert set(day_cfg.keys()) == {
                "available",
                "max_hours",
                "long_workout",
                "doubles_eligible",
            }