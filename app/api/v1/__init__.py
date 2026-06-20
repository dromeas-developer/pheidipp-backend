"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.auth import auth_router
from app.api.v1.health import health_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(auth_router)
