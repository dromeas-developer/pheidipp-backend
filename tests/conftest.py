import asyncio
import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401  # type: ignore[reportUnusedImport]
from app.db.base import Base
from app.db.session import get_db
from app.main import app


def _get_test_database_url() -> str:
    """Derive test DB URL from TEST_DATABASE_URL, falling back to local derivation."""
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        return test_url
    base = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://pheidipp:pheidipp@localhost:5432/pheidipp"
    )
    if base.endswith("/pheidipp"):
        return base.replace("/pheidipp", "/test_pheidipp")
    return base


@pytest.fixture(scope="function")
def test_engine() -> Generator[AsyncEngine, None, None]:
    """Per-test AsyncEngine with NullPool — avoids loop errors."""
    url = _get_test_database_url()
    eng = create_async_engine(url, poolclass=None)
    yield eng
    eng.sync_engine.dispose()


@pytest.fixture(scope="function")
def test_session_local(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """async_sessionmaker bound to the per-test engine."""
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


@pytest_asyncio.fixture(scope="function")
async def db_session(
    test_session_local: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Isolated AsyncSession with auto-rollback and post-test truncation."""
    session = test_session_local()
    session.sync_session.expire_on_commit = False
    try:
        yield session
    finally:
        try:
            await session.rollback()
        except BaseException:
            pass
        try:
            await session.close()
        except BaseException:
            pass
        cleanup_session = test_session_local()
        try:
            tables = Base.metadata.sorted_tables
            for table in reversed(tables):
                await cleanup_session.execute(
                    text(f"TRUNCATE TABLE {table.name} CASCADE")
                )
            await cleanup_session.commit()
        finally:
            try:
                await cleanup_session.close()
            except BaseException:
                pass


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient wired to FastAPI app with db_session override."""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver/api/v1"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    """Create all tables once at session start."""
    url = _get_test_database_url()
    prep_engine = create_async_engine(url, poolclass=None)

    async def _create() -> None:
        async with prep_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_create())
    prep_engine.sync_engine.dispose()
