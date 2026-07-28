import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_event import SystemEvent


class TestSystemEventAthleteIdNotNull:
    async def test_null_athlete_id_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        event = SystemEvent(
            event_type="test.event",
            athlete_id=None,
            payload={},
        )
        db_session.add(event)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()
