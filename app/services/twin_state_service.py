import uuid
from app.core.unit_of_work import UnitOfWork
from app.schemas.twin_state import TwinStateResponse


class TwinStateService:
    def __init__(self):
        pass

    async def get_current_twin_state(
        self, athlete_id: uuid.UUID, uow: UnitOfWork
    ) -> TwinStateResponse | None:
        twin_state = await uow.twin_states.get_by_athlete_id(athlete_id)
        if twin_state is None:
            return None
        return TwinStateResponse.model_validate(twin_state)

    async def get_twin_state_history(
        self,
        athlete_id: uuid.UUID,
        uow: UnitOfWork,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[TwinStateResponse], int]:
        items, total = await uow.twin_states.get_history_by_athlete_id(
            athlete_id, limit, offset
        )
        return [TwinStateResponse.model_validate(t) for t in items], total