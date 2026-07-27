import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete


async def make_athlete(db_session: AsyncSession, *, email: str | None = None) -> Athlete:
    athlete = Athlete(email=email or f"test-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete
