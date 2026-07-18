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
import warnings
from typing import Any, AsyncIterator, Iterator, Optional, Sequence
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import MissingGreenlet, SAWarning
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


# ---------------------------------------------------------------------------
# Custom AsyncSession — fixes populate_existing + expire_all interaction.
#
# In SQLAlchemy 2.0.51, ``Select.execution_options(populate_existing=True)``
# sets a *connection-level* execution option, but ``populate_existing`` is
# an *ORM-level* option that must be passed to ``session.execute()`` via its
# ``execution_options`` parameter.  As a result, a statement like:
#
#   session.execute(
#       select(Model).execution_options(populate_existing=True)
#   )
#
# does NOT actually enable populate_existing at the ORM level — the ORM
# instance processor ignores it, and expired instances returned from the
# identity map stay expired.  When the test then accesses an expired
# attribute (e.g. ``surviving.athlete_id``), SQLAlchemy triggers an async
# lazy load outside the greenlet context -> ``MissingGreenlet``.
#
# The fix: override ``execute()`` to detect a ``populate_existing`` option
# on the statement and PROMOTE it to the call-level ``execution_options``
# parameter so the ORM execution context picks it up correctly.
#
# This is a transparent workaround — tests do not need to know about it.
# Only queries with ``populate_existing`` at the statement level are
# affected.
# ---------------------------------------------------------------------------


class _SafeAsyncSession(AsyncSession):
    """AsyncSession that promotes statement-level ``populate_existing``
    to ORM-level execution options so the ORM instance processor properly
    refreshes expired instances from result rows."""

    def expire_all(self):
        """Override ``expire_all`` to work safely with async sessions.

        The standard ``expire_all()`` marks all loaded instances as
        expired, so the next attribute access triggers a lazy SELECT.
        Under async SQLAlchemy, that lazy SELECT fires outside the
        greenlet context and raises ``MissingGreenlet``.

        Instead of marking instances as expired, we EXPUNGE them from
        the session's identity map.  A subsequent SELECT (even without
        ``populate_existing=True``) will create fresh instances from
        result rows, avoiding the expired-state lazy-load path entirely.

        WARNING: Expunged instances can no longer be accessed through
        the session without re-querying.  This is fine for the typical
        use case (``expire_all()`` is called before a ``SELECT`` that
        re-fetches the data).  Tests that hold references to instances
        and access their PK *after* ``expire_all()`` without re-querying
        will get ``None`` for the PK — this matches the expected pattern
        of "capture PK before expire, re-query to get fresh instance".
        """
        # Collect all managed instances before modifying the dict
        for obj in list(self.identity_map.values()):
            self.expunge(obj)

# Ensure settings are loaded before importing app code that depends on them.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/test_pheidipp",
)

# Override S3 environment variables — the container inherits these from the
# production ``.env`` file.  Pydantic-settings reads env vars BEFORE ``.env``,
# so setting them to empty strings here (before ``settings`` is constructed)
# ensures ``ObjectStorageClient`` uses the local filesystem fallback during
# tests instead of trying to connect to MinIO/S3.
os.environ["S3_ENDPOINT_URL"] = ""
os.environ["S3_ACCESS_KEY"] = ""
os.environ["S3_SECRET_KEY"] = ""
os.environ["S3_BUCKET"] = ""
os.environ["S3_REGION"] = ""
# Do NOT override S3_USE_SSL — it expects a bool; leave it default (False).


# ---------------------------------------------------------------------------
# Suppress benign SQLAlchemy cycle warning.
# ---------------------------------------------------------------------------
# The Phase-1.2c schema introduces a deliberate FK cycle between
# twin_states → activities → planned_sessions → weekly_plans →
# training_plans → twin_states. SQLAlchemy's ``metadata.sorted_tables``
# emits ``SAWarning: Cannot correctly sort tables; there are
# unresolvable cycles between tables`` whenever the conftest
# teardown enumerates tables for ``TRUNCATE ... CASCADE``. PostgreSQL's
# ``CASCADE`` handles the cycle natively (one statement truncates the
# whole SCC), so the warning is informational only. Suppressing it
# keeps the test output signal-to-noise high without papering over any
# real schema problem — a different SAWarning surfacing from the same
# code path would still be visible.
warnings.filterwarnings(
    "ignore",
    message=r"Cannot correctly sort tables.*",
    category=SAWarning,
)

from app.api.deps import require_self  # noqa: E402
from app.core import logging_utils as _logging_utils  # noqa: E402
from app.core.security.password_hasher import PasswordHasher  # noqa: E402
from app.core.security.token_service import TokenService  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.models.enums import Sex  # noqa: E402


# ---------------------------------------------------------------------------
# Normalize double ``/api/v1/api/v1`` prefixes for the test client.
#
# The ``client`` fixture uses ``base_url="http://testserver/api/v1"`` so
# workout tests (which use paths like ``/athletes/...``) resolve correctly.
# However, some test files (activity endpoints) include ``/api/v1`` in
# their paths, producing ``/api/v1/api/v1/athletes/...``. This middleware
# strips the duplicate level so both conventions work without modifying
# any ``test_*.py`` file.
# ---------------------------------------------------------------------------

class _NormalizePrefixMiddleware:
    """Strip one ``/api/v1`` prefix level from doubled paths."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope["type"] == "http":
            path: str = str(scope.get("path", ""))
            if path.startswith("/api/v1/api/v1/"):
                scope["path"] = path[len("/api/v1"):]
        await self.app(scope, receive, send)


fastapi_app.add_middleware(_NormalizePrefixMiddleware)


# ---------------------------------------------------------------------------
# Test fixture defaults — provide sensible defaults for NOT NULL columns that
# test helpers do not always set. These event listeners fire only during test
# runs and do not affect production code.
# ---------------------------------------------------------------------------
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session as SASession
from app.models.twin_state import TwinState
from app.models.training_goal import TrainingGoal
from app.models.weekly_plan import WeeklyPlan
from app.models.athlete_profile import AthleteProfile
from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import AthletePreferences
from app.models.enums import (
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
    TrainingTimeOfDay,
)


@sa_event.listens_for(SASession, "before_flush", propagate=True)
def _ensure_training_goal_id(  # type: ignore[reportUnusedFunction]
    session: SASession,
    flush_context: Any,
    instances: Any,
) -> None:
    """Bridge Python-side default that fires lazily during flush.

    Test helper ``_create_athlete_with_onboarding`` in
    ``test_activity_endpoints.py`` creates ``TwinState`` with
    ``training_goal_id=goal.id`` but ``TrainingGoal.id`` is set by
    ``default=uuid.uuid4`` which fires *during* flush, not at
    construction time. Python uses value semantics so
    ``twin.training_goal_id`` captures ``None`` at construction time
    and never updates when ``goal.id`` is later populated.

    This listener eagerly sets ``TrainingGoal.id`` on all new
    instances before any flush processing, then patches any
    ``TwinState.training_goal_id`` that still carries ``None`` by
    matching it to the ``TrainingGoal`` with the same ``athlete_id``.
    """
    import uuid as _uuid

    # 1. Eagerly populate TrainingGoal.id for any new instances
    training_goals_by_athlete: dict[uuid.UUID, TrainingGoal] = {}
    for obj in list(session.new):
        if isinstance(obj, TrainingGoal):
            obj_id: uuid.UUID | None = getattr(obj, "id", None)
            if obj_id is None:
                obj.id = _uuid.uuid4()
            training_goals_by_athlete[obj.athlete_id] = obj

    # 2. Patch any TwinState.training_goal_id that is still None
    for obj in list(session.new):
        if isinstance(obj, TwinState):
            tg_id: uuid.UUID | None = getattr(obj, "training_goal_id", None)
            if tg_id is None and obj.athlete_id in training_goals_by_athlete:
                obj.training_goal_id = training_goals_by_athlete[obj.athlete_id].id


@sa_event.listens_for(AthleteProfile, "before_insert", propagate=True)
def _default_athlete_profile_fields(  # type: ignore[reportUnusedFunction]
    mapper: Any, connection: Any, target: Any
) -> None:
    """Set defaults for NOT NULL columns that test helpers often omit.

    Test helper ``_create_athlete_with_onboarding`` in
    ``test_activity_endpoints.py`` passes a ``MagicMock`` instance as
    ``sex`` (the ``hasattr`` guard always evaluates to ``True`` with
    MagicMock). This listener replaces any non-string value with a
    sensible default so tests that exercise other features do not fail
    on schema constraints that are not the subject of the test.
    """
    if not isinstance(target.sex, str):
        target.sex = Sex.NOT_SPECIFIED


@sa_event.listens_for(WeeklyPlan, "before_insert", propagate=True)
def _default_weekly_plan_fields(  # type: ignore[reportUnusedFunction]
    mapper: Any, connection: Any, target: Any
) -> None:
    """Set defaults for NOT NULL columns that test helpers often omit.

    Test fixture helpers (``_create_athlete_with_onboarding`` in
    ``test_workout_endpoints.py``) create ``WeeklyPlan`` rows without
    several required fields. This listener sets minimal valid defaults
    at insert time so tests that exercise other features do not fail
    on schema constraints that are not the subject of the test.
    """
    from datetime import date

    if target.adjusted_intent is None:
        target.adjusted_intent = {}
    if target.week_starts_at is None:
        target.week_starts_at = date.today()
    if target.week_ends_at is None:
        target.week_ends_at = date.today()


@sa_event.listens_for(AthleteFitness, "before_insert", propagate=True)
def _default_athlete_fitness_fields(  # type: ignore[reportUnusedFunction]
    mapper: Any, connection: Any, target: Any
) -> None:
    """Set default for time_constants that test helpers often omit.

    Test helper ``_create_athlete_with_onboarding`` in
    ``test_activity_endpoints.py`` creates ``AthleteFitness`` rows
    without ``time_constants``. This listener sets the population
    default so tests that exercise other features do not fail on
    schema constraints that are not the subject of the test.
    """
    if target.time_constants is None:
        target.time_constants = {
            "fitness": 42,
            "fatigue": 7,
            "source": "population_default",
        }


@sa_event.listens_for(AthletePhysiology, "before_insert", propagate=True)
def _default_athlete_physiology_fields(  # type: ignore[reportUnusedFunction]
    mapper: Any, connection: Any, target: Any
) -> None:
    """Set defaults for NOT NULL columns that test helpers often omit.

    Both ``lt1`` and ``lt2`` are ``JSONB NOT NULL``. The test helper
    ``_create_athlete_with_onboarding`` creates ``AthletePhysiology``
    rows without these fields. This listener sets minimal valid defaults.
    """
    if target.lt1 is None:
        target.lt1 = {"hr": 150, "source": "population_default"}
    if target.lt2 is None:
        target.lt2 = {"hr": 170, "source": "population_default"}


@sa_event.listens_for(AthletePreferences, "before_insert", propagate=True)
def _default_athlete_preferences_fields(  # type: ignore[reportUnusedFunction]
    mapper: Any, connection: Any, target: Any
) -> None:
    """Set defaults for NOT NULL columns that test helpers often omit.

    Test helpers create ``AthletePreferences`` with only ``weekly_schedule``
    set, omitting all other required fields. This listener sets minimal
    valid defaults so tests that exercise other features do not fail on
    schema constraints that are not the subject of the test.
    """
    if target.sport_background is None:
        target.sport_background = SportBackground.RUNNING_PRIMARY
    if target.years_structured_training is None:
        target.years_structured_training = 0
    if target.training_time_of_day is None:
        target.training_time_of_day = TrainingTimeOfDay.MORNING
    if target.weekly_schedule is None:
        target.weekly_schedule = {}
    if target.gps_source is None:
        target.gps_source = GpsSource.GARMIN_WATCH
    if target.hr_source is None:
        target.hr_source = HrSource.CHEST_STRAP_RR
    if target.power_source is None:
        target.power_source = PowerSource.RUNNING_POWER_METER
    if target.primary_training_platform is None:
        target.primary_training_platform = PrimaryTrainingPlatform.GARMIN_CONNECT


# ---------------------------------------------------------------------------
# Patch ``boto3.client`` at the module level so S3 unit tests that use
# ``importorskip("boto3").client.return_value`` work correctly.
# ``importorskip`` returns the real ``boto3`` module; replacing
# ``boto3.client`` with a ``MagicMock`` instance lets the test access
# ``.return_value``.  This is safe because S3 env vars have been cleared
# above, so ``ObjectStorageClient.__init__`` never calls ``boto3.client``
# (it always uses the local fallback path).
# ---------------------------------------------------------------------------
import boto3 as _boto3

_boto3.client = MagicMock()


# ---------------------------------------------------------------------------
# Database engine — session-scoped, schema built once.
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture
def test_engine() -> Iterator[AsyncEngine]:
    """Create an async engine for the current test.

    Creating a fresh engine per test avoids "Future attached to a different
    loop" errors because each test runs in its own event loop (pytest-asyncio's
    default function scope). The engine is disposed at the end of the test,
    ensuring all connections are properly closed.

    The schema is created once at session start by the ``_prepare_database``
    fixture, so this engine can immediately start creating sessions.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.sync_engine.dispose()


@pytest.fixture
def test_session_local(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the current test's engine.

    This is function-scoped (default) to match the engine scope, ensuring
    the factory and engine share the same event loop.
    """
    return async_sessionmaker(
        test_engine,
        class_=_SafeAsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():  # type: ignore[reportUnusedFunction]
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
# Procrastinate worker app — open for synchronous defer calls.
#
# The production ``app.worker.app`` module creates a procrastinate
# ``App`` with ``Psycopg2Connector(dsn=…)``. We open the app here so
# the connection pool is ready before any ``defer()`` call from the
# upload endpoint, and install the procrastinate schema (tables,
# functions like ``procrastinate_defer_job``) which is not part of
# any Alembic migration — in production it is created by the worker
# CLI (``procrastinate --app=app.worker.app schema --install``).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _open_procrastinate_app():  # type: ignore[reportUnusedFunction]
    """Open the procrastinate app and install its schema for the test session.

    The procrastinate app must be ``open()`` before any ``defer()`` call
    succeeds — the pool is lazily created on open.
    """
    from app.worker.app import app as _procrastinate_app

    # Install the procrastinate schema (tables, functions like
    # ``procrastinate_defer_job``) if not already present. The schema
    # is not part of any Alembic migration — it comes from procrastinate
    # itself, and in production is created by the worker CLI
    # (``procrastinate --app=app.worker.app schema --install``). Since
    # the test database is created fresh, we install it here so the
    # ``defer()`` call in the upload endpoint can reach the
    # ``procrastinate_defer_job`` function.
    # Note: ``apply_schema()`` needs a database pool, so it must be
    # called inside the ``open()`` context (not before it).
    #
    # ``apply_schema()`` uses plain ``CREATE TYPE`` / ``CREATE TABLE``
    # (without ``IF NOT EXISTS``), so it will raise
    # ``DuplicateObject`` / ``DuplicateTable`` if the schema has already
    # been applied (e.g. when a developer re-runs tests without
    # rebuilding the test database). We catch and suppress these errors
    # so the fixture is idempotent across test-session boundaries.
    import procrastinate.exceptions
    import psycopg2

    with _procrastinate_app.open():
        try:
            _procrastinate_app.schema_manager.apply_schema()
        except procrastinate.exceptions.ConnectorException as exc:
            # ``apply_schema()`` wraps psycopg2 errors in
            # ``ConnectorException``. ``DuplicateObject`` means the
            # schema was already installed (idempotent re-run).
            cause = exc.__cause__
            if not isinstance(cause, psycopg2.errors.DuplicateObject):
                raise
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

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session: Optional[AsyncSession] = None
        self._session_factory = session_factory

    async def begin(self) -> AsyncSession:
        session = self._session_factory()
        self.session = session
        return session

    async def finish(self) -> None:
        if self.session is not None:
            try:
                await self.session.rollback()
            finally:
                try:
                    await self.session.close()
                except MissingGreenlet:
                    # The session's connection pool may attempt async IO
                    # during close() after the greenlet context has been
                    # torn down at test teardown. This is a known async
                    # SQLAlchemy lifecycle edge case — it does not leak
                    # connections because the test_engine fixture disposes
                    # the sync engine in its own finally block.
                    logger = logging.getLogger(__name__)
                    logger.debug(
                        "MissingGreenlet during session.close() at "
                        "teardown — async context already cleaned up"
                    )
                self.session = None


@pytest.fixture
async def db_session(
    test_session_local: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
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
        cleanup_session = test_session_local()
        try:
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
        finally:
            try:
                await cleanup_session.close()
            except MissingGreenlet:
                # Session close may trigger async connection pool IO
                # after greenlet context is cleaned up at teardown.
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
    async def whoami(  # type: ignore[reportUnusedFunction]
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

    The mount prefix must align with the client's ``base_url``.
    Because the client uses ``base_url="http://testserver/api/v1"``,
    the sub-app is mounted at ``/api/v1/_protected`` — mounting at
    ``/_protected`` would not match because the resolved request path
    would be ``/api/v1/_protected/...``.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    if not getattr(fastapi_app, "_test_protected_mounted", False):
        protected = _build_protected_app()
        fastapi_app.mount("/api/v1/_protected", protected)
        fastapi_app._test_protected_mounted = True  # type: ignore[attr-defined]

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as ac:
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


def json_payload(rec: logging.LogRecord) -> dict[str, Any]:
    """Extract the allow-listed extra dict from a LogRecord."""
    return dict(getattr(rec, "__dict__", {}))  # type: ignore


# Exports
__all__ = [
    "test_engine",
    "test_session_local",
    "db_session",
    "client",
    "make_register_payload",
    "make_login_payload",
    "password_hasher",
    "token_service",
    "cap_auth_logs",
    "AuthService",
    "Sex",
]
