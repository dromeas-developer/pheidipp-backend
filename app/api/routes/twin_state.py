from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.unit_of_work import UnitOfWork
from app.db.session import get_db
from app.schemas.twin_state import TwinStateResponse
from app.services.twin_state_service import TwinStateService
from app.api.dependencies.services import get_twin_state_service
from app.api.dependencies.auth import require_self

router = APIRouter(prefix="/athletes/{athlete_id}/twin", tags=["twin"])


class TwinStateHistoryResponse(BaseModel):
    items: list[TwinStateResponse]
    total: int


@router.get("/", response_model=TwinStateResponse)
async def get_current_twin_state(
    athlete_id: UUID,
    _: UUID = Depends(require_self),
    service: TwinStateService = Depends(get_twin_state_service),
    db: AsyncSession = Depends(get_db),
):
    async with UnitOfWork(db) as uow:
        twin_state = await service.get_current_twin_state(athlete_id, uow)
        if twin_state is None:
            raise HTTPException(
                status_code=404,
                detail="No twin state found for this athlete",
            )
        return twin_state


@router.get("/history", response_model=TwinStateHistoryResponse)
async def get_twin_state_history(
    athlete_id: UUID,
    _: UUID = Depends(require_self),
    service: TwinStateService = Depends(get_twin_state_service),
    limit: int = Query(ge=1, le=1000, default=100),
    offset: int = Query(ge=0, default=0),
    db: AsyncSession = Depends(get_db),
):
    async with UnitOfWork(db) as uow:
        items, total = await service.get_twin_state_history(
            athlete_id, uow, limit, offset
        )
        return TwinStateHistoryResponse(items=items, total=total)