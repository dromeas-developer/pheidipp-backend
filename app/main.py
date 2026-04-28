from fastapi import FastAPI
from app.config import Settings
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.settings = Settings()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(lifespan=lifespan)