from fastapi import FastAPI
from app.config import settings
from app.api.routes.health import health_router
from app.api.routes.athletes import router as athletes_router
from app.api.routes.activities import router as activities_router
from app.api.routes.physiology import router as physiology_router
from app.api.routes.wellness import router as wellness_router
from app.api.routes.fitness import router as fitness_router
from app.api.routes.training_blocks import router as training_blocks_router 
from app.api.routes.athlete_preferences import router as athlete_preferences_router
from app.api.routes.twin_state import router as twin_state_router
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.settings = settings
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(lifespan=lifespan, openapi_url="/openapi.json", docs_url="/docs")
app.include_router(health_router)
app.include_router(athletes_router)
app.include_router(activities_router)
app.include_router(physiology_router)
app.include_router(wellness_router)
app.include_router(fitness_router)
app.include_router(training_blocks_router)
app.include_router(athlete_preferences_router)
app.include_router(twin_state_router)
