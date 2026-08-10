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
from sqlalchemy.pool import NullPool

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


def _ensure_procrastinate_test_url() -> None:
    """Ensure PROCRASTINATE_DATABASE_URL points at the test database.

    The procrastinate app is constructed at import time in
    ``app.worker.app`` and the DSN is evaluated eagerly. Without
    this, the DSN comes from ``.env`` (dev URL pointing at the
    ``pheidipp`` database) and any test that triggers a
    ``procrastinate_app.tasks[...].defer(...)`` call would enqueue
    against the dev schema. Set the env var to the test database
    *before* the app is imported so the DSN resolves correctly.

    This must run *before* ``app.main`` is imported: importing
    ``app.main`` transitively imports ``app.worker.app`` which
    eagerly constructs the procrastinate connector from this env
    var. If the env var is not set first, the connector binds to
    the dev database and the whole test session fails to open.

    The previous "return early if already set" guard was incorrect:
    ``.env`` (or a developer shell) sets
    ``PROCRASTINATE_DATABASE_URL`` to the *dev* database, so the
    early-return path silently bound the worker connector to the
    dev schema. The conftest's job is to pin the test session to
    the test database — always override, unconditionally.
    """
    test_asyncpg_url = _get_test_database_url()
    os.environ["PROCRASTINATE_DATABASE_URL"] = test_asyncpg_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )


_ensure_procrastinate_test_url()


import app.models  # noqa: E402, F401  # type: ignore[reportUnusedImport]
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="function")
def test_engine() -> Generator[AsyncEngine, None, None]:
    """Per-test AsyncEngine with NullPool — closes each connection
    on ``session.close()`` so all locks (row-level on the
    application table, ``RowShareLock`` on the FK target) are
    released before the next fixture or the cleanup
    ``TRUNCATE TABLE ... CASCADE`` starts. The previous
    ``poolclass=None`` (which is the default
    ``AsyncAdaptedQueuePool`` — not NullPool) returned
    connections to the pool on close; the pool's
    ``reset_on_return='rollback'`` did not always release locks
    in the same event loop, and the still-open connection
    deadlocked with the TRUNCATE in the ``db_session`` teardown
    when the TRUNCATE acquired ``AccessExclusiveLock`` on a
    table the prior INSERT's FK check was still holding a
    ``RowShareLock`` on (e.g. ``activities`` ↔
    ``athlete_profiles``). NullPool sidesteps the pool entirely:
    every checkout opens a fresh connection, every close drops
    it, every transaction ends with the connection.
    """
    url = _get_test_database_url()
    eng = create_async_engine(url, poolclass=NullPool)
    yield eng
    eng.sync_engine.dispose()


@pytest.fixture(scope="function")
def test_session_local(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """async_sessionmaker bound to the per-test engine."""
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _cleanup_lock() -> AsyncGenerator[asyncio.Lock, None]:
    """Session-scoped lock that serializes the per-test TRUNCATE.

    The marker hook at the bottom of this file binds every async
    test to ``loop_scope="session"``, which means the
    ``db_session`` teardown (rollback, close, open cleanup
    session, execute TRUNCATE one-table-at-a-time, commit, close)
    and the next test's ``db_session`` setup run in the same
    event loop. Under that timing model the teardown's ``await``
    yields expose the ``AccessExclusiveLock`` acquired by each
    per-table TRUNCATE to the next test's INSERTs — and because
    two test-engine connections can then enter a lock-acquisition
    cycle across the ``Base.metadata`` FK graph (e.g.
    ``activities`` ↔ ``athlete_profiles`` ↔ ``athletes``),
    PostgreSQL surfaces ``DeadlockDetectedError`` even though
    each individual test passes in isolation (see RC1 in
    ``reports/phase-1-7-batch-1_devops.md`` for the full
    diagnosis).

    The lock must live in the session event loop, not at import
    time: ``asyncio.Lock()`` binds to whatever loop is current
    when the constructor runs. The fixture is declared with
    ``loop_scope="session"`` so its body executes in the same
    loop as the tests, and the Lock it yields is shared across
    every per-test ``db_session`` instance. ``NullPool`` on the
    test engine still guarantees every connection is closed
    before the lock is released; the lock only serialises the
    TRUNCATE phase against the next test's setup phase, not the
    connection lifetimes themselves.
    """
    yield asyncio.Lock()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def db_session(
    test_session_local: async_sessionmaker[AsyncSession],
    _cleanup_lock: asyncio.Lock,
) -> AsyncGenerator[AsyncSession, None]:
    """Isolated AsyncSession with auto-rollback and post-test truncation.

    Explicit ``loop_scope="session"`` binds the fixture body to the
    session-scoped event loop. The marker hook at the bottom of this
    file binds every async test to ``loop_scope="session"`` (so the
    procrastinate app's open-context ``ContextVar`` is set on the
    session loop, not the function loop — see
    ``pytest_collection_modifyitems`` for the full rationale), and
    pytest-asyncio's "fixture loop scope is determined by the test"
    rule means function-scoped fixtures *should* inherit that loop
    scope automatically. The explicit declaration removes the
    inheritance dependency: under ``asyncio_mode = auto`` and with
    per-file async fixtures in some test files declared as bare
    ``@pytest.fixture`` on ``async def`` (e.g.
    ``tests/api/test_onboarding_endpoints.py::athlete_with_profile``),
    pytest-asyncio's loop-scope resolution path is sensitive to the
    order in which the marker injection and fixture loop-scope
    resolution happen. Without the explicit declaration, a subtle
    ordering artefact can leave the ``AsyncSession`` constructed in
    one loop context and awaited in another, surfacing as
    ``RuntimeError: got Future attached to a different loop`` (see
    RC2 in ``reports/phase-1-7-batch-1_devops.md`` for the full
    diagnosis)."""
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
        async with _cleanup_lock:
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


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient wired to FastAPI app with db_session override.

    Explicit ``loop_scope="session"`` binds the fixture body to the
    session-scoped event loop — same rationale as ``db_session``.
    The ``ASGITransport`` and ``AsyncClient`` capture the current
    loop at construction time, and the ``async with AsyncClient(...)``
    context manager binds response/timeout Futures to that loop.
    Under the marker hook's session-loop binding the explicit
    declaration guarantees the transport/client Futures match the
    session loop that the handler's async DB round-trip awaits them
    in. See RC2 in ``reports/phase-1-7-batch-1_devops.md`` for the
    full diagnosis."""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver/api/v1"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    """Create all application tables once at session start.

    The engine uses ``NullPool`` and is fully disposed after
    ``create_all`` so no connections from this fixture survive
    into the test body. The previous ``poolclass=None`` (default
    ``AsyncAdaptedQueuePool``) plus ``sync_engine.dispose()`` left
    idle connections in the pool; those connections could still
    hold ``RowShareLock`` on application tables from internal
    catalog queries, and a second TRUNCATE in the
    ``db_session`` teardown deadlocked against the still-open
    connection's catalog-level lock. ``NullPool`` plus a full
    ``await prep_engine.dispose()`` (run via the session loop)
    guarantees every connection is closed before the tests start.
    """
    import asyncio as _asyncio

    from sqlalchemy.ext.asyncio import create_async_engine as _cae
    from sqlalchemy.pool import NullPool as _NP

    url = _get_test_database_url()
    prep_engine = _cae(url, poolclass=_NP)

    async def _create_and_dispose() -> None:
        try:
            async with prep_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await prep_engine.dispose()

    _asyncio.get_event_loop().run_until_complete(_create_and_dispose())


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _open_procrastinate_app() -> AsyncGenerator[None, None]:
    """Open the procrastinate app for the entire test session.

    The upload route at
    ``app/api/v1/activity.py:post_upload_activity`` calls
    ``await fit_ingest.defer_async(...)``
    to enqueue the heavy ingestion pipeline (ADR-014 — async
    connector). The ``defer_async`` call requires the app to be
    open — without this fixture the call raises
    ``procrastinate.exceptions.AppNotOpen`` and the API tests in
    ``tests/api/test_activity_upload.py`` fail before reaching the
    response assertions.

    The schema is applied so the procrastinate tables
    (``procrastinate_jobs``, ``procrastinate_workers``,
    ``procrastinate_filelock``, ``procrastinate_filelock_queue``,
    ``procrastinate_periodic_defers``) exist on the test database.
    ``procrastinate.schema.SchemaManager.apply_schema_async`` is
    *not* idempotent — procrastinate's ``PsycopgConnector`` wraps
    every ``psycopg.Error`` (including ``DuplicateObject``) into
    ``procrastinate.exceptions.ConnectorException`` before
    propagating it out of ``execute_query_async``. The original
    ``psycopg.errors.DuplicateObject`` is preserved on
    ``__cause__``. A re-run of the suite is the common case; the
    schema is otherwise created by the worker on first defer, so
    the duplicate-DDL path is the expected steady state and is
    safe to skip.

    The ``async with procrastinate_app.open_async()`` block must
    wrap the ``yield`` (not just the schema application). The
    previous sync-generator implementation closed the app after
    the schema was applied but before the test session ran, so
    every ``defer_async`` call in the test body raised
    ``AppNotOpen``. The schema application itself also needs the
    open connection — DDL issued against the connector pool is
    committed only while the connector is open, so closing the
    app immediately after ``apply_schema_async`` rolled the
    schema back on session-end, surfacing as
    ``UndefinedTableError: relation "procrastinate_jobs" does
    not exist`` in the integration tests.

    The test database is wiped clean of any pre-existing
    procrastinate objects (tables, types, functions, indexes)
    before the schema is applied. Without this step, a stale
    schema from an earlier procrastinate version (e.g. 2.x) trips
    the first ``CREATE TYPE`` with ``DuplicateObject``; psycopg
    aborts the rest of the multi-statement schema script in the
    same transaction, leaving the new objects —
    ``procrastinate_workers``, the
    ``procrastinate_job_to_defer_v1`` composite type, and the
    ``procrastinate_defer_jobs_v1`` function — uncreated. The
    test body then fails at the first ``defer_async`` with
    ``psycopg.errors.UndefinedObject: type
    "procrastinate_job_to_defer_v1[]" does not exist``. The
    drop-and-recreate path runs only against the *test* database
    (``PROCRASTINATE_DATABASE_URL`` is unconditionally overridden
    in ``_ensure_procrastinate_test_url``), so production data
    in the ``pheidipp`` database is never touched.
    """
    import psycopg

    from app.worker.app import app as procrastinate_app

    # Drop any pre-existing procrastinate objects on the test
    # database before the new schema is applied. The drop covers
    # every object kind procrastinate creates in the public
    # schema: tables, enum and composite types, and functions
    # (including trigger procedures and overloads like
    # ``procrastinate_finish_job`` and its v1 variant). A
    # targeted per-name ``DROP`` would drift every time
    # procrastinate adds a new function in a patch release, so
    # the loop instead scans ``pg_class`` / ``pg_proc`` /
    # ``pg_type`` for anything matching the ``procrastinate``
    # prefix and drops it via ``DROP ... IF EXISTS ... CASCADE``.
    # The drop is scoped to the test DSN — see
    # ``_ensure_procrastinate_test_url`` — so the production
    # ``pheidipp`` database is never touched.
    test_dsn = os.environ["PROCRASTINATE_DATABASE_URL"].replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    with psycopg.connect(test_dsn, autocommit=True) as reset_conn:
        with reset_conn.cursor() as cur:
            cur.execute(
                "DO $$\n"
                "DECLARE\n"
                "    obj record;\n"
                "BEGIN\n"
                "    FOR obj IN\n"
                "        SELECT 'DROP TABLE public.' || quote_ident(relname)\n"
                "               || ' CASCADE' AS ddl\n"
                "          FROM pg_class c\n"
                "          JOIN pg_namespace n ON n.oid = c.relnamespace\n"
                "         WHERE n.nspname = 'public'\n"
                "           AND c.relkind IN ('r', 'p')\n"
                "           AND c.relname LIKE 'procrastinate%'\n"
                "    LOOP\n"
                "        EXECUTE obj.ddl;\n"
                "    END LOOP;\n"
                "    FOR obj IN\n"
                "        SELECT 'DROP TYPE public.' || quote_ident(typname)\n"
                "               || ' CASCADE' AS ddl\n"
                "          FROM pg_type t\n"
                "          JOIN pg_namespace n ON n.oid = t.typnamespace\n"
                "         WHERE n.nspname = 'public'\n"
                "           AND t.typname LIKE 'procrastinate%'\n"
                "    LOOP\n"
                "        EXECUTE obj.ddl;\n"
                "    END LOOP;\n"
                "    FOR obj IN\n"
                "        SELECT 'DROP FUNCTION public.' || quote_ident(proname)\n"
                "               || '(' || pg_get_function_identity_arguments(p.oid)\n"
                "               || ')' AS ddl\n"
                "          FROM pg_proc p\n"
                "          JOIN pg_namespace n ON n.oid = p.pronamespace\n"
                "         WHERE n.nspname = 'public'\n"
                "           AND p.proname LIKE 'procrastinate%'\n"
                "    LOOP\n"
                "        EXECUTE obj.ddl;\n"
                "    END LOOP;\n"
                "END $$;"
            )

    async with procrastinate_app.open_async():
        await procrastinate_app.schema_manager.apply_schema_async()
        yield


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Bind every async test to the session-scoped event loop.

    The procrastinate app is opened by ``_open_procrastinate_app``
    in a session-scoped event loop (``loop_scope="session"``), so
    the ``PsycopgConnector`` async pool is created in the session
    loop and remains open for the whole test run. Async tests
    that run in the default function-scoped event loop would
    trigger ``procrastinate.exceptions.AppNotOpen`` when the
    upload route calls ``defer_async`` (see RC1 in
    ``reports/phase-1-7-batch-1_devops.md`` for the full
    diagnosis) because the app's open-context ``ContextVar`` is
    set on the session loop, not the function loop.

    The ``asyncio_default_test_loop_scope`` ini key documented
    in ``pytest.ini`` is *not* honored by the installed
    ``pytest-asyncio`` (the key was added in a later release than
    the one pinned in ``requirements.txt``), so the loop binding
    is enforced here via marker injection instead. Every item
    that pytest-asyncio has auto-marked with the ``asyncio``
    keyword (which is every test in ``asyncio_mode = auto``) gets
    an additional ``@pytest.mark.asyncio(loop_scope="session")``
    marker.     The function-scoped async fixtures (``db_session``,
    ``client``) are now declared with explicit
    ``loop_scope="session"`` — see their own docstrings. The
    explicit declaration removes the previous dependence on
    pytest-asyncio's "fixture loop scope is determined by the
    test" inheritance rule, which under ``asyncio_mode = auto``
    proved sensitive to the resolution order between marker
    injection and per-file bare ``@pytest.fixture``-on-``async
    def`` declarations (e.g. the ``athlete_with_profile`` fixtures
    in ``tests/api/test_onboarding_endpoints.py`` and
    ``tests/api/test_require_self.py``), surfacing as
    ``RuntimeError: got Future attached to a different loop`` in
    the cross-test sequencing (see RC2 in
    ``reports/phase-1-7-batch-1_devops.md`` for the full
    diagnosis).
    """
    session_loop_mark = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        if "asyncio" in item.keywords:
            item.add_marker(session_loop_mark)
