import uuid
from app.models.athlete_profile import  AthleteProfile
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.schemas.athlete_profile import AthleteProfileUpdate


class AthleteProfileService:
    def __init__(self, profile_repo: AthleteProfileRepository,):
        self.profile_repo = profile_repo

    async def get_profile(self, athlete_id: uuid.UUID) -> AthleteProfile | None:
        return await self.profile_repo.get_by_athlete_id(athlete_id)

    async def upsert_profile(self, athlete_id: uuid.UUID, data: AthleteProfileUpdate) -> AthleteProfile:
        existing_profile = await self.profile_repo.get_by_athlete_id(athlete_id)
        profile_data = data.model_dump(exclude_unset=True)
        if existing_profile:
            result = await self.profile_repo.update_by_athlete_id(athlete_id, **profile_data)
            if result is None:
                raise RuntimeError(f"Profile unexpectedly missing for athlete {athlete_id}")
            return result
        else:
            profile_data["athlete_id"] = athlete_id
            return await self.profile_repo.create(**profile_data)
