import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile
from app.models.enums import Sex


async def make_athlete(
    db_session: AsyncSession, *, email: str | None = None
) -> Athlete:
    athlete = Athlete(email=email or f"test-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete


async def make_athlete_with_profile(
    db_session: AsyncSession,
    *,
    email: str | None = None,
    date_of_birth: date | None = None,
    sex: Sex | None = None,
) -> tuple[Athlete, AthleteProfile]:
    athlete = Athlete(email=email or f"test-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()
    profile = AthleteProfile(
        athlete_id=athlete.id,
        date_of_birth=date_of_birth or date(1990, 1, 15),
        sex=sex or Sex.MALE,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(athlete)
    await db_session.refresh(profile)
    return athlete, profile
