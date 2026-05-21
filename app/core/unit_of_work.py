from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.athlete_repository import AthleteRepository
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from app.repositories.training_block_repository import TrainingBlockRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.coach_message_repository import CoachMessageRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.planned_session_repository import PlannedSessionRepository


class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._repos: dict[str, Any] = {}
        self._owns_transaction: bool = False

    async def __aenter__(self) -> "UnitOfWork":
        self._owns_transaction = not self.session.in_transaction()
        if self._owns_transaction:
            await self.session.begin()
        self._repos = {
            "athletes": AthleteRepository(self.session),
            "preferences": AthletePreferencesRepository(self.session),
            "blocks": TrainingBlockRepository(self.session),
            "twin_states": TwinStateRepository(self.session),
            "profiles": AthleteProfileRepository(self.session),
            "coach_messages": CoachMessageRepository(self.session),
            "training_plans": TrainingPlanRepository(self.session),
            "planned_sessions": PlannedSessionRepository(self.session),
        }
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.session.rollback()
        else:
            # Always commit if we're in a transaction, regardless of whether we started it.
            # flush() makes changes visible within the transaction but they won't persist
            # without commit. This ensures writes performed via the UoW are persisted.
            if self.session.in_transaction():
                await self.session.commit()

    def __getattr__(self, name: str) -> Any:
        if not self._repos:
            raise RuntimeError(
                "UnitOfWork must be used with 'async with' to access repositories"
            )
        if name in self._repos:
            return self._repos[name]
        available = list(self._repos.keys())
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'. "
            f"Available: {available}"
        )