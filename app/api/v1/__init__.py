"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.auth import auth_router
from app.api.v1.coach import coach_router
from app.api.v1.health import health_router
from app.api.v1.onboarding import onboarding_router
from app.api.v1.plan import plan_router
from app.api.v1.workout import workout_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(onboarding_router)
api_router.include_router(plan_router)
api_router.include_router(coach_router)
api_router.include_router(workout_router)