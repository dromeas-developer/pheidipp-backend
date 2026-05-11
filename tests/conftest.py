"""Pytest configuration and fixtures for Pheidipp backend tests."""

import uuid
from datetime import date, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

# Add the project root to the Python path
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app


# ============================================================================
# Test Database Fixtures (PostgreSQL via docker-compose)
# ============================================================================


@pytest.fixture(scope="session")
def test_db_connection_url():
    """Get the PostgreSQL connection URL for tests."""
    import os

    # Use test_pheidipp database for isolation from development data
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/test_pheidipp"
    )


@pytest.fixture(scope="session")
def test_db_engine(test_db_connection_url):
    """Create an async SQLAlchemy engine for the test database."""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
    from sqlalchemy.pool import NullPool

    engine: AsyncEngine = create_async_engine(
        test_db_connection_url,
        echo=False,
        poolclass=NullPool,  # Each session gets a fresh connection
    )

    # Import Base to ensure models are registered
    from app.db.base import Base

    # Create all tables once per session
    async def _init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Get or create an event loop for the session
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_init_db())

    yield engine

    async def _dispose():
        await engine.dispose()

    loop.run_until_complete(_dispose())


@pytest.fixture
async def test_db_session(test_db_engine):
    """Create an async session for each test."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    session_factory = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    session = session_factory()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture(autouse=True)
async def clean_db_tables(test_db_engine):
    """Clean all test tables before each test for isolation within the test DB."""
    from app.db.base import Base
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Get all table objects from Base.metadata
    tables = list(Base.metadata.tables.values())

    # Create a fresh session for cleanup
    session_factory = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        # Delete all data from each table in reverse dependency order
        for table in reversed(tables):
            await session.execute(delete(table))
        await session.commit()

    yield


# ============================================================================
# Fixtures for FastAPI Application
# ============================================================================


@pytest.fixture(name="app")
def app_fixture() -> FastAPI:
    """Fixture to get the FastAPI application instance."""
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Fixture to create an httpx AsyncClient for testing."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# ============================================================================
# Factory Fixtures for Test Data
# ============================================================================


@pytest.fixture
def athlete_data() -> dict[str, Any]:
    """Factory fixture for athlete data."""
    return {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "testpassword123",
    }


@pytest.fixture
def athlete_profile_data() -> dict[str, Any]:
    """Factory fixture for athlete profile data."""
    return {
        "first_name": "Test",
        "last_name": "Athlete",
        "display_name": "test_athlete",
        "date_of_birth": date(1990, 1, 1),
        "gender": "male",
        "country_code": "US",
        "timezone": "America/New_York",
        "language_code": "en",
        "unit_preference": "metric",
    }


@pytest.fixture
def activity_data() -> dict[str, Any]:
    """Factory fixture for activity data."""
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + datetime.timedelta(hours=1)
    return {
        "athlete_id": str(uuid.uuid4()),
        "activity_type": "running",
        "title": "Test Run",
        "description": "A test activity",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "perceived_effort": "moderate",
        "avg_heart_rate": 145,
        "max_heart_rate": 175,
        "distance_meters": 10000.0,
        "calories": 500,
    }


@pytest.fixture
def physiology_data() -> dict[str, Any]:
    """Factory fixture for athlete physiology data."""
    return {
        "ftp": 280,
        "lt1": 220,
        "lt2": 250,
        "vo2_max": 65.5,
        "max_hr": 190,
        "source": "manual",
        "effective_from": date(2024, 1, 1).isoformat(),
        "effective_to": date(2024, 12, 31).isoformat(),
    }


@pytest.fixture
def wellness_data() -> dict[str, Any]:
    """Factory fixture for athlete wellness data."""
    return {
        "metric_date": date(2024, 1, 1).isoformat(),
        "sleep_total": 480,
        "sleep_light": 240,
        "sleep_deep": 120,
        "sleep_rem": 90,
        "sleep_awake": 30,
        "resting_hr": 55,
        "hrv": 65,
        "weight": 75.5,
        "source": "manual",
        "timezone": "UTC",
    }


# ============================================================================
# Mock Fixtures for External Services
# ============================================================================


@pytest.fixture
def mock_redis():
    """Mock fixture for Redis."""
    from unittest.mock import AsyncMock
    return AsyncMock()


@pytest.fixture
def mock_minio():
    """Mock fixture for MinIO."""
    from unittest.mock import AsyncMock
    return AsyncMock()