from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.db.session import get_db
from app.repositories.training_block_repository import TrainingBlockRepository
from app.services.training_block_service import TrainingBlockService
from app.schemas.training_block import TrainingBlockUpdate, TrainingBlockResponse

router = APIRouter(prefix="/training-blocks", tags=["training-blocks"])


def get_service(db: AsyncSession = Depends(get_db)) -> TrainingBlockService:
    return TrainingBlockService(TrainingBlockRepository(db))


@router.get("/{block_id}", response_model=TrainingBlockResponse)
async def get_block(
    block_id: UUID,
    service: TrainingBlockService = Depends(get_service),
):
    result = await service.repo.get_by_id(block_id)
    if not result:
        raise HTTPException(status_code=404, detail="Training block not found")
    return result


@router.patch("/{block_id}", response_model=TrainingBlockResponse)
async def update_block(
    block_id: UUID,
    payload: TrainingBlockUpdate,
    service: TrainingBlockService = Depends(get_service),
):
    """
    Permitted updates: status, goal_event_date, goal_description.
    Semantic fields (goal_type, event_type, bootstrap snapshot) are immutable.
    To change goal type or event, close this block and open a new one.
    """
    result = await service.update(block_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Training block not found")
    return result

# No DELETE endpoint — blocks are closed, not deleted