"""Shared test factories for creating domain model instances.

These are async helpers that use the per-test db_session fixture.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.enums import ActivitySource, AuthProvider, SportType

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken


async def make_athlete(db_session, email: str | None = None) -> Athlete:
    """Create and flush an Athlete with a unique email."""
    if email is None:
        email = f"athlete-{uuid.uuid4()}@example.com"
    athlete = Athlete(email=email)
    db_session.add(athlete)
    await db_session.flush()
    return athlete


async def make_auth(
    db_session,
    *,
    athlete_id: uuid.UUID,
    provider: AuthProvider = AuthProvider.EMAIL,
    is_primary: bool = True,
) -> AthleteAuth:
    """Create and flush an AthleteAuth row."""
    auth = AthleteAuth(
        athlete_id=athlete_id,
        provider=provider,
        is_primary=is_primary,
    )
    db_session.add(auth)
    await db_session.flush()
    return auth


async def make_activity(
    db_session,
    *,
    athlete_id: uuid.UUID,
    activity_date=None,
    sport_type: SportType = SportType.RUNNING,
    calibration_eligible: bool = True,
    has_hr: bool = True,
    has_rr_intervals: bool = False,
    has_power: bool = False,
) -> Activity:
    """Create and flush an Activity row with sensible defaults.

    Used by integration tests that need a real Activity row to
    satisfy the ``physiology_measurements.activity_id`` foreign key
    (the column is nullable, but a non-null value must reference
    an existing ``activities.id``). The minimum field set the
    calibration-eligible / sport-type gates need is set; tests
    that exercise other fields can pass them through.
    """
    from datetime import date as _date

    if activity_date is None:
        activity_date = _date.today()
    activity = Activity(
        athlete_id=athlete_id,
        source=ActivitySource.MANUAL_UPLOAD,
        external_id=None,
        activity_date=activity_date,
        start_time=datetime(
            activity_date.year,
            activity_date.month,
            activity_date.day,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        duration_seconds=600,
        aerobic_load=85.0,
        has_hr=has_hr,
        has_rr_intervals=has_rr_intervals,
        has_power=has_power,
        has_gps=True,
        sport_type=sport_type,
        calibration_eligible=calibration_eligible,
        quality_flags={},
        fit_file_key="fit-files/test/uploaded.fit",
        ingestion_pipeline_version="v1-simple-fit",
        cleaning_pipeline_version="v1-signal-cleaning",
    )
    db_session.add(activity)
    await db_session.flush()
    return activity


async def make_refresh_token(
    db_session,
    athlete_id: uuid.UUID,
    *,
    token_hash: str | None = None,
    ip_address: str | None = None,
    expires_at: datetime | None = None,
) -> "RefreshToken":
    """Create a RefreshToken row with sensible defaults."""
    if token_hash is None:
        token_hash = f"hash-{uuid.uuid4()}"

    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    from app.models.refresh_token import RefreshToken

    token = RefreshToken(
        athlete_id=athlete_id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
    )
    db_session.add(token)
    await db_session.flush()
    return token
