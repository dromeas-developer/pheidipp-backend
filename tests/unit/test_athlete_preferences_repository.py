"""Integration tests for AthletePreferencesRepository."""

import uuid

import pytest
from sqlalchemy import select

from app.models.athlete import Athlete
from app.models.athlete_preferences import AthletePreferences
from app.models.enums import AthleteStatus, SportBackground
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from tests.factories.athlete_factory import make_athlete
from tests.factories.athlete_preferences_factory import make_athlete_preferences, make_athlete_preferences_full


@pytest.mark.asyncio
async def test_get_by_athlete_returns_preferences(test_db_session):
    """Test get_by_athlete returns preferences for a given athlete."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()
    await test_db_session.refresh(athlete)

    # Create preferences for the athlete
    prefs = make_athlete_preferences_full(athlete_id=athlete.id)
    test_db_session.add(prefs)
    await test_db_session.commit()
    await test_db_session.refresh(prefs)

    # Retrieve preferences
    repo = AthletePreferencesRepository(test_db_session)
    result = await repo.get_by_athlete(athlete.id)

    assert result is not None
    assert result.id == prefs.id
    assert result.athlete_id == athlete.id
    assert result.sport_background == SportBackground.RUNNING_PRIMARY


@pytest.mark.asyncio
async def test_get_by_athlete_returns_none_when_not_found(test_db_session):
    """Test get_by_athlete returns None when no preferences exist for the athlete."""
    # Create athlete without preferences
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    # Try to retrieve preferences
    repo = AthletePreferencesRepository(test_db_session)
    result = await repo.get_by_athlete(athlete.id)

    assert result is None


@pytest.mark.asyncio
async def test_create(test_db_session):
    """Test creating athlete preferences."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    # Create preferences
    prefs = make_athlete_preferences(athlete_id=athlete.id)
    result = await test_db_session.execute(
        select(AthletePreferences).where(AthletePreferences.athlete_id == athlete.id)
    )
    existing = result.scalar_one_or_none()
    assert existing is None

    # Use repository to create
    repo = AthletePreferencesRepository(test_db_session)
    created = await repo.create(
        athlete_id=athlete.id,
        sport_background=SportBackground.RUNNING_PRIMARY,
    )

    await test_db_session.commit()
    await test_db_session.refresh(created)

    assert created.id is not None
    assert created.athlete_id == athlete.id
    assert created.sport_background == SportBackground.RUNNING_PRIMARY


@pytest.mark.asyncio
async def test_get_by_id(test_db_session):
    """Test getting preferences by ID."""
    # Create athlete and preferences
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    prefs = make_athlete_preferences_full(athlete_id=athlete.id)
    test_db_session.add(prefs)
    await test_db_session.commit()
    await test_db_session.refresh(prefs)

    # Retrieve by ID
    repo = AthletePreferencesRepository(test_db_session)
    result = await repo.get_by_id(prefs.id)

    assert result is not None
    assert result.id == prefs.id


@pytest.mark.asyncio
async def test_update(test_db_session):
    """Test updating athlete preferences."""
    # Create athlete and preferences
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    prefs = make_athlete_preferences(athlete_id=athlete.id)
    test_db_session.add(prefs)
    await test_db_session.commit()
    await test_db_session.refresh(prefs)

    # Update preferences
    repo = AthletePreferencesRepository(test_db_session)
    updated = await repo.update(
        prefs.id,
        sport_background=SportBackground.CYCLING_CROSSOVER,
    )

    await test_db_session.commit()
    await test_db_session.refresh(updated)

    assert updated.sport_background == SportBackground.CYCLING_CROSSOVER


@pytest.mark.asyncio
async def test_delete(test_db_session):
    """Test deleting athlete preferences."""
    # Create athlete and preferences
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    prefs = make_athlete_preferences(athlete_id=athlete.id)
    test_db_session.add(prefs)
    await test_db_session.commit()
    await test_db_session.refresh(prefs)

    # Delete preferences
    repo = AthletePreferencesRepository(test_db_session)
    await repo.delete(prefs.id)

    await test_db_session.commit()

    # Verify deleted
    result = await repo.get_by_id(prefs.id)
    assert result is None