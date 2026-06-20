"""Pytest configuration and fixtures for Pheidipp backend tests.

Provides:

* An async test database engine sharing the project's metadata so each
  test session runs against the same schema as production.
* Per-test transaction isolation through a single ``AsyncSession`` that
  is rolled back at the end of the test (faster than DROP/CREATE).
* ``client`` — an ``httpx.AsyncClient`` wired to the real FastAPI app
  with the dependency-overridden session so requests and tests see the
  same transactional state.
* ``cap_auth_logs`` — a context manager that captures every record
  emitted on the ``pheidipp.auth`` logger so tests can assert that
  credential/PII fields never appear in audit output.
* Factory helpers for fresh athletes, tokens, and refresh-token
  rotation, kept thin — the tests spell out the expected behaviour, the
  fixtures only handle repetitive plumbing.

The ``require_self`` dependency is exercised through a tiny
stand-alone FastAPI sub-app that mounts
``GET /athletes/{athlete_id}/whoami`` — see
``_build_protected_app`` below. This keeps the production API surface
clean while letting the dependency be tested through the same
HTTP-layer plumbing as everything else.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import AsyncIterator, Iterator, Optional, Sequence
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure settings are loaded before importing app code that depends on them.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/test_pheidipp",
)

from app.api.deps import require_self  # noqa: E402
from app.core import logging_utils as _logging_utils  # noqa: E402
from app.core.security.password_hasher import PasswordHasher  # noqa: E402
from app.core.security.token_service import TokenService  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


# ---------------------------------------------------------------------------
# Database engine — session-scoped, schema built once.
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


async def _create_schema(engine) -> None:
    """Create all tables declared on the project's metadata."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_schema(engine) -> None:
    """Drop the full schema to leave the test DB clean for the next session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def test_engine():
    """Create an async engine for the current test.

    Creating a fresh engine per test avoids "Future attached to a different
    loop" errors because each test runs in its own event loop (pytest-asyncio's
    default function scope). The engine is disposed at the end of the test,
    ensuring all connections are properly closed.

    The schema is created once at session start by the ``_prepare_database``
    fixture, so this engine can immediately start creating sessions.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        yield engine
    finally:
        engine.sync_engine.dispose()


@pytest.fixture
def test_session_local(test_engine):
    """Create a session factory bound to the current test's engine.

    This is function-scoped (default) to match the engine scope, ensuring
    the factory and engine share the same event loop.
    """
    return async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """Build the schema once per test session and clean data before tests.

    Creates all tables at the start of the test session using a temporary
    engine. This avoids the "Future attached to a different loop" error
    because we create and dispose the engine within the same async context.
    
    Tables created with ``Base.metadata.create_all`` have ``IF NOT EXISTS``
    semantics, so this is safe to run against an existing test database.
    
    Before running tests, all data is truncated to ensure a clean state.
    This prevents cross-session contamination from previous test runs.
    
    Uses SQLAlchemy's metadata to dynamically discover all tables — no
    manual maintenance required when adding new models.
    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from app.db.base import Base
    
    async def _setup_schema() -> None:
        # Create a temporary engine just for schema setup
        temp_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        try:
            # Dynamically discover all tables from SQLAlchemy metadata
            # reversed() ensures child tables are truncated before parents
            table_names = [table.name for table in reversed(Base.metadata.sorted_tables)]
            
            # First truncate all existing data (if any tables exist)
            if table_names:
                async with temp_engine.begin() as conn:
                    await conn.execute(
                        text(f"TRUNCATE TABLE {', '.join(table_names)} CASCADE")
                    )
            
            # Then ensure schema exists
            async with temp_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await temp_engine.dispose()
    
    asyncio.run(_setup_schema())
    yield


# ---------------------------------------------------------------------------
# Per-test transactional session.
# ---------------------------------------------------------------------------


class _TestSessionFactory:
    """Holds the per-test session and offers a ``commit()`` roll-out helper.

    Tests that exercise the service layer (which calls ``session.commit``
    itself) keep this session as the binding; on teardown we roll back so
    no test can leave rows that affect the next test.
    """

    def __init__(self, session_factory) -> None:
        self.session: Optional[AsyncSession] = None
        self._session_factory = session_factory

    async def begin(self) -> AsyncSession:
        self.session = self._session_factory()
        return self.session

    async def finish(self) -> None:
        if self.session is not None:
            try:
                await self.session.rollback()
            finally:
                await self.session.close()
                self.session = None


@pytest.fixture
async def db_session(test_session_local) -> AsyncIterator[AsyncSession]:
    """Yield a single AsyncSession for the current test.

    The session is rolled back at teardown, ensuring test isolation.
    Since both the engine and session factory are function-scoped, they
    share the same event loop as the test, avoiding loop mismatch errors.
    
    After rollback, all tables are truncated to ensure committed data from
    service-layer tests doesn't leak into subsequent tests.
    
    ⚠️  CRITICAL: DO NOT remove the truncation logic below. Service-layer
    code (AuthService, EventPublisher, etc.) calls session.commit() which
    permanently persists data. Rollback only undoes uncommitted changes.
    Without truncation, tests that commit data will contaminate later tests.
    
    ⚠️  ASYNC ORM PITFALL: Never use db_session.expire(obj) then access
    lazy attributes. This triggers async IO outside the proper greenlet
    context and raises MissingGreenlet errors.
    
    ✅ CORRECT PATTERN:
        token_hash = token.token_hash  # Capture BEFORE expire
        db_session.expire(token)
        refreshed = await repo.get_by_token_hash(token_hash)  # Fresh query
    
    ✅ BETTER: Skip expire() entirely and just query fresh by ID/hash.
    
    ⚠️  JWT UNIQUENESS: Access tokens issued within the same second will
    be identical (deterministic JWT claims). This is expected behavior.
    Tests asserting access_token uniqueness should either:
    - Add a small delay between issue calls, or
    - Assert refresh_token uniqueness instead (the actual security property)
    """
    from sqlalchemy import text
    
    factory = _TestSessionFactory(test_session_local)
    session = await factory.begin()
    try:
        yield session
    finally:
        await factory.finish()
        # Truncate all tables to clean up any committed data
        # This is required because service-layer code calls session.commit()
        # which persists data permanently — rollback only undoes uncommitted work
        try:
            async with test_session_local() as cleanup_session:
                async with cleanup_session.begin():
                    # Dynamically discover all tables from SQLAlchemy metadata
                    # reversed() ensures child tables are truncated before parents
                    from app.db.base import Base
                    table_names = [table.name for table in reversed(Base.metadata.sorted_tables)]
                    if table_names:
                        await cleanup_session.execute(
                            text(f"TRUNCATE TABLE {', '.join(table_names)} CASCADE")
                        )
        except Exception:
            # If truncation fails (e.g., no data), continue
            pass


# ---------------------------------------------------------------------------
# FastAPI client with dependency overrides.
# ---------------------------------------------------------------------------


def _build_protected_app() -> FastAPI:
    """A minimal sub-app that mounts ``/athletes/{athlete_id}/whoami``.

    The production app has no athlete-scoped routes yet (Phase 1.1 only
    shipped auth). To exercise ``require_self`` end-to-end we mount a
    throwaway endpoint here that depends on the real
    ``get_current_athlete_id``/``require_self`` chain. The route lives in
    the test infrastructure so production code is untouched.
    """

    protected = FastAPI()

    @protected.get("/athletes/{athlete_id}/whoami")
    async def whoami(
        athlete_id: uuid.UUID,
        token_athlete_id: uuid.UUID = Depends(require_self),
    ) -> dict[str, str]:
        return {"athlete_id": str(token_athlete_id), "path_athlete_id": str(athlete_id)}

    return protected


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Yield an HTTP client wired to the real FastAPI app.

    Overrides ``get_db`` so the real app's request handlers operate on
    the same ``db_session`` fixture the test is using. This lets tests
    inspect the database state after each call without juggling two sessions.

    A throwaway sub-app that exercises ``require_self`` is mounted at
    ``/_protected`` so athlete-scoped routes can be tested through the
    same HTTP plumbing as the production app.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    if not getattr(fastapi_app, "_test_protected_mounted", False):
        protected = _build_protected_app()
        fastapi_app.mount("/_protected", protected)
        fastapi_app._test_protected_mounted = True  # type: ignore[attr-defined]

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers — payload factories live in ``tests.payloads`` so test
# files can import them directly without dragging in the conftest
# (which constructs a database engine at import time). The fixtures
# here expose those same factories under short pytest names so tests
# can use ``def test_x(make_register_payload)`` style as well.
# ---------------------------------------------------------------------------


from tests.payloads import make_login_payload as _make_login_payload
from tests.payloads import make_register_payload as _make_register_payload


@pytest.fixture
def make_register_payload():
    """Factory that returns a fresh registration payload per call."""
    return _make_register_payload


@pytest.fixture
def make_login_payload():
    """Factory that returns a fresh login payload per call."""
    return _make_login_payload


@pytest.fixture
def password_hasher() -> PasswordHasher:
    return PasswordHasher()


@pytest.fixture
def token_service() -> TokenService:
    return TokenService()


# ---------------------------------------------------------------------------
# Logging capture — assert secrets never appear in audit logs.
# ---------------------------------------------------------------------------


class _AuthLogCapture(logging.Handler):
    """Capture handler that records every LogRecord emitted on the auth logger."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        self.records.append(record)


@pytest.fixture
def cap_auth_logs() -> Iterator[_AuthLogCapture]:
    """Capture every record written to ``pheidipp.auth`` during a test.

    Captures are reset per test so ordering is deterministic.
    """

    handler = _AuthLogCapture()
    logger = _logging_utils.get_auth_logger()
    previous_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


# ---------------------------------------------------------------------------
# Misc helpers — centralise repeated patterns so tests stay terse.
# ---------------------------------------------------------------------------


def find_record(records: Sequence[logging.LogRecord], *, event: str) -> Optional[logging.LogRecord]:
    """Return the first LogRecord whose ``event`` field matches ``event``."""
    for record in records:
        if getattr(record, "event", None) == event:
            return record
    return None


def json_payload(rec: logging.LogRecord) -> dict:
    """Extract the allow-listed extra dict from a LogRecord."""
    return dict(getattr(rec, "__dict__", {}))


@contextmanager
def frozen_time(now: datetime):
    """Patch ``datetime.now(timezone.utc)`` so refresh-token TTL math is exact.

    The 30-day expiry invariant is asserted on absolute timestamps; this
    keeps that assertion stable regardless of when CI runs.
    """
    with patch("app.services.auth_service.datetime") as ms, patch(
        "app.core.security.token_service.datetime"
    ) as ts:
        for mod in (ms, ts):
            mod.now.return_value = now
            mod.now.side_effect = None
        yield


@asynccontextmanager
async def captured_metric_context() -> AsyncIterator[dict[str, dict[str, int]]]:
    """Yield the current metric snapshot, with restore-on-exit semantics.

    Tests that assert metric deltas use this so a leaked increment from
    an earlier test cannot masquerade as the increment under test.
    """
    snapshot_before = _logging_utils.snapshot_metrics()
    try:
        yield snapshot_before
    finally:
        # Reset to the pre-test snapshot so metric tests stay isolated.
        with _logging_utils._metrics_lock:  # type: ignore[attr-defined]
            for key in list(_logging_utils._metrics.keys()):  # type: ignore[attr-defined]
                _logging_utils._metrics[key] = _logging_utils.CollectionsCounter()  # type: ignore[attr-defined]
            for key, bucket in snapshot_before.items():
                _logging_utils._metrics[key] = _logging_utils.CollectionsCounter(bucket)  # type: ignore[attr-defined]


__all__ = [
    "TEST_DATABASE_URL",
    "test_engine",
    "test_session_local",
    "db_session",
    "client",
    "cap_auth_logs",
    "find_record",
    "json_payload",
    "frozen_time",
    "captured_metric_context",
    "make_register_payload",
    "make_login_payload",
    "password_hasher",
    "token_service",
    "AuthService",
    "Sex",
]


