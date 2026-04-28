from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.health_service import check_database

health_router = APIRouter(prefix="/health")

@health_router.get("/live")
async def live():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }

@health_router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    try:
        database_status = await check_database(db)
        if database_status:
            return {"status": "ok", "database": "up"}
        else:
            return {"status": "degraded", "database": "down"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}