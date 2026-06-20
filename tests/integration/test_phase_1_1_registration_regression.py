"""Phase-1.2a regression: the Phase-1.1 registration journey still works.

Phase-1.2a EXTENDS ``athlete_profiles`` with a longer column set. The
plan explicitly codifies that the Phase-1.1 registration path must
continue to work exactly as before:

* One ``Athlete`` row.
* One email-provider ``AthleteAuth`` row.
* One minimal ``AthleteProfile`` row with ``date_of_birth``, ``sex``,
  and optional ``height_cm``. NOTHING ELSE populated.
* One ``RefreshToken`` row (with token_hash).

The schema-only extension must not break the service-layer end-to-end
flow. This test exercises the production ``AuthService.register``
against the Phase-1.2a-extended schema and asserts the four-row graph
materialises correctly.

Reference plan:
docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.athlete_profile import AthleteProfile
from app.models.enums import AuthProvider, Sex
from app.models.refresh_token import RefreshToken
from app.services.auth_service import AuthService


@pytest.fixture
def service(db_session: AsyncSession) -> AuthService:
    return AuthService(session=db_session)


def _register_kwargs(
    email: str = "phase-1-2a-regression@example.com",
    password: str = "ValidPass123!",
) -> dict:
    return {
        "email": email,
        "password": password,
        "date_of_birth": datetime(1990, 1, 1, tzinfo=timezone.utc).date(),
        "sex": Sex.NOT_SPECIFIED,
        "height_cm": 180.0,
        "ip_address": "192.0.2.10",
        "user_agent": "PheidippTest/1.0",
    }


class TestRegistrationJourneyUnchanged:
    """The full registration journey must remain exactly as in
    Phase-1.1: one row per artefact, no partial state, no regression
    induced by the Phase-1.2a extension."""

    async def test_registration_creates_exactly_one_athlete(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="r-athlete@example.com"))

        rows = await db_session.execute(
            select(Athlete).where(Athlete.email == "r-athlete@example.com")
        )
        athletes = rows.scalars().all()
        assert len(athletes) == 1
        assert athletes[0].onboarding_complete is False

    async def test_registration_creates_exactly_one_email_auth(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="r-auth@example.com")
        )

        rows = await db_session.execute(
            select(AthleteAuth).where(
                AthleteAuth.athlete_id == result.athlete_id
            )
        )
        auths = rows.scalars().all()
        assert len(auths) == 1
        assert auths[0].provider is AuthProvider.EMAIL
        assert auths[0].is_primary is True
        assert auths[0].hashed_password is not None
        assert auths[0].hashed_password.startswith("$2")

    async def test_registration_creates_minimal_profile_with_phase_1_2a_columns_null(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        """The registration-created profile is still the Phase-1.1
        minimal one — every Phase-1.2a enrichment column is null."""
        result = await service.register(
            **_register_kwargs(email="r-profile@example.com")
        )

        rows = await db_session.execute(
            select(AthleteProfile).where(
                AthleteProfile.athlete_id == result.athlete_id
            )
        )
        profiles = rows.scalars().all()
        assert len(profiles) == 1
        profile = profiles[0]

        # Phase-1.1 minimal fields populated.
        assert profile.date_of_birth == datetime(1990, 1, 1, tzinfo=timezone.utc).date()
        assert profile.sex is Sex.NOT_SPECIFIED
        assert profile.height_cm is not None
        assert profile.id is not None

        # Phase-1.2a enrichment fields — every one is NULL after registration.
        assert profile.gap_curve_model is None
        assert profile.weather_response_model is None
        assert profile.banister_constants is None
        assert profile.cycle_personal_model is None
        assert profile.location_lat is None
        assert profile.location_lng is None
        assert profile.timezone is None
        assert profile.training_window is None
        assert profile.current_effort_generation is None
        assert profile.structural_risk_flag is None
        assert profile.objective_thresholds is None
        # updated_at is auto-populated, but not by the Phase-1.2a path.
        assert profile.updated_at is not None

    async def test_registration_creates_exactly_one_refresh_token(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="r-refresh@example.com")
        )

        rows = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.athlete_id == result.athlete_id
            )
        )
        tokens = rows.scalars().all()
        assert len(tokens) == 1
        assert tokens[0].token_hash is not None
        assert tokens[0].revoked_at is None


class TestRegistrationIdempotency:
    """Re-running registration for the same email still races against
    the unique email index — the Phase-1.2a migration must not have
    changed the underlying email-uniqueness invariant."""

    async def test_duplicate_email_registration_still_rejected(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        from app.services.auth_errors import DuplicateEmailError

        await service.register(**_register_kwargs(email="dup@example.com"))
        with pytest.raises(DuplicateEmailError):
            await service.register(**_register_kwargs(email="dup@example.com"))


class TestRetrievalAfterRegistration:
    """Reading a freshly-registered profile through the model still
    yields the same shape. This guards against a silent migration that
    broke column ordering or nullability."""

    async def test_profile_can_be_retrieved_and_refreshed_post_phase_1_2a(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="retrieve@example.com")
        )

        fresh = await db_session.execute(
            select(AthleteProfile).where(
                AthleteProfile.athlete_id == result.athlete_id
            )
        )
        profile = fresh.scalar_one()
        # Round-trip — refresh attribute access through the ORM (catches
        # e.g. dropped column or type regression).
        await db_session.refresh(profile)
        assert profile.id is not None
        assert profile.athlete_id == result.athlete_id
        # Phase-1.2a columns should still appear on the mapper (they
        # were simply never set).
        assert hasattr(profile, "gap_curve_model")
        assert hasattr(profile, "timezone")
        assert hasattr(profile, "structural_risk_flag")
