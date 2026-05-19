"""DB-backed regression tests for PhysiologyRepository.has_overlap method."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import AthleteStatus
from app.models.physiology import AthletePhysiology
from app.models.enums import DataSource
from app.repositories.physiology_repository import PhysiologyRepository


@pytest.fixture
async def athlete(test_db_session: AsyncSession) -> Athlete:
    """Create a test athlete in the database."""
    athlete = Athlete(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=None,
        status=AthleteStatus.ACTIVE,
    )
    test_db_session.add(athlete)
    await test_db_session.commit()
    await test_db_session.refresh(athlete)
    return athlete


@pytest.fixture
def physiology_repo(test_db_session: AsyncSession) -> PhysiologyRepository:
    """Create a PhysiologyRepository instance with the test session."""
    return PhysiologyRepository(test_db_session)


async def _create_physiology(
    session: AsyncSession,
    athlete_id: uuid.UUID,
    effective_from: date,
    effective_to: date | None,
) -> AthletePhysiology:
    """Helper to create a physiology record in the database."""
    physiology = AthletePhysiology(
        athlete_id=athlete_id,
        ftp=280,
        source=DataSource.MANUAL,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    session.add(physiology)
    await session.commit()
    await session.refresh(physiology)
    return physiology


class TestHasOverlapClosedVsClosed:
    """Test overlapping ranges where both records have closed date ranges."""

    async def test_overlap_returns_true_for_overlapping_closed_ranges(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns True when new closed range overlaps with existing closed range."""
        # Create existing record: Jan 1 - Jun 30
        await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
        )

        # New record overlaps: Mar 1 - Aug 31
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 3, 1),
            effective_to=date(2024, 8, 31),
        )

        assert has_overlap is True

    async def test_overlap_returns_true_for_exactly_adjacent_ranges(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns True when new range starts exactly when existing ends."""
        # Create existing record: Jan 1 - Jun 30
        await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
        )

        # New record starts exactly on the day after existing ends
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 7, 1),
            effective_to=date(2024, 12, 31),
        )

        # The existing record ends on Jun 30, new starts on Jul 1 - they don't overlap
        assert has_overlap is False


class TestHasOverlapOpenEndedExisting:
    """Test overlapping when existing record has open-ended date range."""

    async def test_overlap_returns_true_when_existing_is_open_ended_and_new_starts_during(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns True when existing record has no end date and new starts during it."""
        # Create existing record with no end date: Jan 1 - None (open-ended)
        await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=None,
        )

        # New record starts during the open range
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 6, 15),
            effective_to=date(2024, 12, 31),
        )

        assert has_overlap is True


class TestHasOverlapOpenEndedNew:
    """Test overlapping when new record has open-ended date range."""

    async def test_overlap_returns_true_when_new_is_open_ended_and_starts_inside_closed_range(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns True when new record has no end date and starts inside existing closed range."""
        # Create existing record: Jan 1 - Dec 31
        await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 12, 31),
        )

        # New record is open-ended and starts inside the existing range
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 6, 15),
            effective_to=None,
        )

        assert has_overlap is True


class TestHasOverlapNoOverlap:
    """Test non-overlapping ranges."""

    async def test_returns_false_when_new_range_is_entirely_before_existing(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns False when new range is entirely before existing range."""
        # Create existing record: Jun 1 - Dec 31
        await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 6, 1),
            effective_to=date(2024, 12, 31),
        )

        # New record is entirely before: Jan 1 - May 31
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 5, 31),
        )

        assert has_overlap is False

    async def test_returns_false_when_new_range_is_entirely_after_existing(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns False when new range is entirely after existing range."""
        # Create existing record: Jan 1 - Jun 30
        await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
        )

        # New record is entirely after: Jul 1 - Dec 31
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 7, 1),
            effective_to=date(2024, 12, 31),
        )

        assert has_overlap is False


class TestHasOverlapWithExcludeId:
    """Test has_overlap with exclude_id parameter for update operations."""

    async def test_exclude_id_returns_false_for_record_being_updated(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns False when checking the record being updated."""
        # Create existing record: Jan 1 - Jun 30
        existing = await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
        )

        # Update the same record (should not detect overlap with itself)
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
            exclude_id=existing.id,
        )

        assert has_overlap is False

    async def test_exclude_id_returns_true_for_different_overlapping_record(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns True when another record overlaps (excluding the target)."""
        # Create first record: Jan 1 - Jun 30
        first = await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
        )

        # Create second record: Jul 1 - Dec 31
        await _create_physiology(
            session=physiology_repo.session,
            athlete_id=athlete.id,
            effective_from=date(2024, 7, 1),
            effective_to=date(2024, 12, 31),
        )

        # Try to update first record to overlap with second (should detect overlap)
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 5, 1),
            effective_to=date(2024, 8, 31),
            exclude_id=first.id,
        )

        assert has_overlap is True


class TestHasOverlapEdgeCases:
    """Edge case tests for has_overlap method."""

    async def test_no_existing_records_returns_false(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
    ):
        """Test has_overlap returns False when no existing records for the athlete."""
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 12, 31),
        )

        assert has_overlap is False

    async def test_different_athlete_no_overlap(
        self,
        athlete: Athlete,
        physiology_repo: PhysiologyRepository,
        test_db_session: AsyncSession,
    ):
        """Test has_overlap returns False when records belong to different athletes."""
        # Create record for a different athlete
        other_athlete = Athlete(
            id=uuid.uuid4(),
            email=f"other_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(other_athlete)
        await test_db_session.commit()

        await _create_physiology(
            session=test_db_session,
            athlete_id=other_athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 12, 31),
        )

        # Check overlap for original athlete - should be False
        has_overlap = await physiology_repo.has_overlap(
            athlete_id=athlete.id,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 12, 31),
        )

        assert has_overlap is False