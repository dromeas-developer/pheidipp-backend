import uuid

from app.core.unit_of_work import UnitOfWork
from app.schemas.onboarding import OnboardingRequest
from app.services.athlete_service import AthleteService
from app.services.athlete_preferences_service import AthletePreferencesService
from app.services.training_block_service import TrainingBlockService
from app.services.twin_initialisation_service import TwinInitialisationService
from app.models.athlete_preferences import AthletePreferences
from app.models.training_block import TrainingBlock
from app.models.twin_state import TwinState


class OnboardingService:
    def __init__(
        self,
        athlete_service: AthleteService,
        athlete_preferences_service: AthletePreferencesService,
        training_block_service: TrainingBlockService,
        twin_initialisation_service: TwinInitialisationService,
    ):
        self.athlete_service = athlete_service
        self.athlete_preferences_service = athlete_preferences_service
        self.training_block_service = training_block_service
        self.twin_initialisation_service = twin_initialisation_service

    async def complete_onboarding(
        self,
        athlete_id: uuid.UUID,
        payload: OnboardingRequest,
        uow: UnitOfWork,
    ) -> tuple[AthletePreferences, TrainingBlock, TwinState]:
        # Step 1: Create preferences
        preferences = await self.athlete_preferences_service.create_for_athlete_uow(
            athlete_id, payload.preferences, uow
        )

        # Step 2: Create training block (enforces 409 if duplicate)
        training_block = await self.training_block_service.create_for_athlete_uow(
            athlete_id, payload.training_block, uow
        )

        # Step 3: Get profile
        profile = await self.athlete_service.get_profile_uow(athlete_id, uow)

        # Step 4: Validate date_of_birth
        if profile is None or profile.date_of_birth is None:
            raise ValueError(
                "Athlete profile is incomplete. "
                "Create a profile with at least date_of_birth before onboarding."
            )

        # Step 5: Create twin state
        twin_state = await self.twin_initialisation_service.initialise(
            athlete_id, preferences, training_block, profile, uow
        )

        # Step 6 (LAST): Set onboarding_complete=True
        await self.athlete_service.set_onboarding_complete_uow(athlete_id, uow)

        return preferences, training_block, twin_state