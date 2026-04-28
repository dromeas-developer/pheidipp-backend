import pytest
from fastapi import FastAPI
from httpx import AsyncClient


@pytest.fixture(name="app")
def app_fixture() -> FastAPI:
    """Fixture to get the FastAPI application instance."""
    from app.main import app
    return app


@pytest.fixture(name="client")
async def client_fixture(app: FastAPI) -> AsyncClient:
    """Fixture to create an httpx AsyncClient for testing."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client
