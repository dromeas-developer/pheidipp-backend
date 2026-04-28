from fastapi import FastAPI
from app.config import settings
from app.api.routes.health import health_router
from app.api.routes.athletes import router as athletes_router
from app.api.routes.swagger_test import router as swagger_test_router
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
app.include_router(swagger_test_router, tags=["Swagger Test"])