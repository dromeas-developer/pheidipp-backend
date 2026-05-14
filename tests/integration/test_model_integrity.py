"""Integration tests for model integrity and database constraints."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.physiology import AthletePhysiology
from app.models.enums import ActivityType, DataSource


from tests.factories.activity_factory import make_activity
from tests.factories.athlete_factory import make_athlete
from tests.factories.physiology_factory import make_athlete_physiology


class TestActivityModelForeignKeys:
    """Tests for Activity model foreign key integrity."""

    @pytest.mark.asyncio
    async def test_activity_model_has_required_foreign_keys(self, test_db_session):
        """Verify athlete relationships are enforced.

        This test verifies that:
        1. Activity requires a valid athlete_id (not nullable)
        2. Deleting an athlete cascades to their activities
        """
        # Create an athlete to use as reference
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        # Save athlete ID early - session will expire after rollbacks later
        athlete_id = athlete.id

        # Test 1: Activity can be created with valid athlete_id
        activity = make_activity(athlete_id=athlete.id)
        test_db_session.add(activity)
        await test_db_session.commit()
        await test_db_session.refresh(activity)

        assert activity.id is not None
        assert activity.athlete_id == athlete.id

        # Test 2: Activity cannot be created with NULL athlete_id
        activity_null = make_activity(athlete_id=None)
        test_db_session.add(activity_null)
        with pytest.raises(IntegrityError) as exc_info:
            await test_db_session.commit()
        await test_db_session.rollback()

        # Verify the error is about the foreign key / not null constraint
        assert "null" in str(exc_info.value).lower() or "foreign key" in str(exc_info.value).lower()

        # Test 3: Activity cannot be created with non-existent athlete_id
        fake_athlete_id = uuid.uuid4()
        activity_invalid = make_activity(athlete_id=fake_athlete_id)
        test_db_session.add(activity_invalid)
        with pytest.raises(IntegrityError) as exc_info:
            await test_db_session.commit()
        await test_db_session.rollback()

        # Verify the error is about foreign key constraint
        assert "foreign key" in str(exc_info.value).lower() or "violates" in str(exc_info.value).lower()

        # Test 4: Deleting athlete cascades to activities
        # Re-fetch athlete after rollbacks - session is expired and accessing
        # expired athlete.id would trigger a lazy-load causing a greenlet error
        result = await test_db_session.execute(
            select(Athlete).where(Athlete.id == athlete_id)
        )
        athlete = result.scalar_one()
        # Create another activity for the same athlete
        activity2 = make_activity(athlete_id=athlete.id)
        test_db_session.add(activity2)
        await test_db_session.commit()

        # Verify activities exist
        result = await test_db_session.execute(
            select(Activity).where(Activity.athlete_id == athlete.id)
        )
        activities = list(result.scalars().all())
        assert len(activities) == 2

        # Delete the athlete using direct SQL to bypass ORM relationship handling
        # The database-level CASCADE will handle deleting related activities
        await test_db_session.execute(
            delete(Athlete).where(Athlete.id == athlete.id)
        )
        await test_db_session.commit()

        # Verify activities were cascade deleted
        result = await test_db_session.execute(
            select(Activity).where(Activity.athlete_id == athlete.id)
        )
        activities_after = list(result.scalars().all())
        assert len(activities_after) == 0

class TestPhysiologyRecordsOrdering:
    """Tests for AthletePhysiology ordering by effective_date."""

    @pytest.mark.asyncio
    async def test_physiology_records_are_ordered_by_effective_date(self, test_db_session):
        """Verify chronological retrieval consistency.

        This test verifies that:
        1. Multiple physiology records for an athlete can be stored
        2. Records are retrieved in descending order by effective_from
        3. The ordering is consistent and deterministic
        """
        # Create an athlete
        athlete = make_athlete()
        test_db_session.add(athlete)
        await test_db_session.commit()
        await test_db_session.refresh(athlete)

        # Create physiology records with different effective_from dates
        # Order: oldest to newest
        phys_2023 = make_athlete_physiology(
            athlete_id=athlete.id,
            ftp=250,
            effective_from=date(2023, 1, 1),
            effective_to=date(2023, 6, 30),
            source=DataSource.MANUAL,
        )
        phys_2024_jan = make_athlete_physiology(
            athlete_id=athlete.id,
            ftp=270,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
            source=DataSource.MANUAL,
        )
        phys_2024_jul = make_athlete_physiology(
            athlete_id=athlete.id,
            ftp=280,
            effective_from=date(2024, 7, 1),
            effective_to=None,  # Current
            source=DataSource.MANUAL,
        )

        # Add in random order to test ordering
        test_db_session.add(phys_2024_jul)
        await test_db_session.commit()
        test_db_session.add(phys_2023)
        await test_db_session.commit()
        test_db_session.add(phys_2024_jan)
        await test_db_session.commit()

        # Test: Query physiology records ordered by effective_from DESC
        result = await test_db_session.execute(
            select(AthletePhysiology)
            .where(AthletePhysiology.athlete_id == athlete.id)
            .order_by(AthletePhysiology.effective_from.desc())
        )
        physiology_records = list(result.scalars().all())

        # Verify we have 3 records
        assert len(physiology_records) == 3

        # Verify ordering: most recent first (descending)
        assert physiology_records[0].effective_from == date(2024, 7, 1)
        assert physiology_records[1].effective_from == date(2024, 1, 1)
        assert physiology_records[2].effective_from == date(2023, 1, 1)

        # Verify FTP values match the expected ordering
        assert physiology_records[0].ftp == 280  # Most recent
        assert physiology_records[1].ftp == 270
        assert physiology_records[2].ftp == 250  # Oldest

        # Test: Verify the repository method also returns ordered results
        # (This simulates what the service/repository layer would do)
        result = await test_db_session.execute(
            select(AthletePhysiology)
            .where(AthletePhysiology.athlete_id == athlete.id)
            .order_by(AthletePhysiology.effective_from.desc())
            .limit(2)
        )
        top_2 = list(result.scalars().all())

        # Should get the 2 most recent records
        assert len(top_2) == 2
        assert top_2[0].effective_from == date(2024, 7, 1)
        assert top_2[1].effective_from == date(2024, 1, 1)

        # Test: Deleting athlete cascades to all physiology records
        await test_db_session.delete(athlete)
        await test_db_session.commit()

        result = await test_db_session.execute(
            select(AthletePhysiology).where(AthletePhysiology.athlete_id == athlete.id)
        )
        phys_after = list(result.scalars().all())
        assert len(phys_after) == 0, "All physiology records should be cascade deleted"