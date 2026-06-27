# Test Pack Refactor Report

**Date**: 2026-06-25
**Scope**: Full test suite across phases 1.1, 1.2a, 1.2b, 1.2c
**Author**: Test Architect

---

## 1. Executive Summary

The test suite has grown organically across four sub-phases and now exhibits significant **structural duplication**, **inconsistent idioms**, and **missing shared abstractions**. This report identifies every category of repetition, demonstrates the cost, and provides a concrete, prioritized roadmap for introducing a central `tests/utils/factories.py` and `tests/utils/schema_helpers.py` module to consolidate the shared logic. All changes are backward-compatible with existing tests.

**Business benefit**: Reduce per-new-phase overhead by ~50%, eliminate copy-paste schema inspection bugs, and guarantee that all tests use the validated "correct" patterns already documented in `tests/README.md`.

---

## 2. Categories of Duplication Found

### 2.1. 🔴 CRITICAL — Schema Inspection Helper Duplication

**Files affected**: 14 integration schema tests (Phase-1.2a through 1.2c)

**Problem**: Every integration schema test re-declares a private `_sync_url()` and a suite of `_columns()`, `_unique_constraints()`, `_check_constraints()`, `_indexes()`, and `_foreign_keys()` helpers. Two slightly divergent versions exist:

- **Version A** (Phase-1.2a, e.g. `test_athlete_profile_schema.py`): Inlines the DATABASE_URL logic inside each function, with `inspector = inspect(conn)` inside each `with` block. Spread: 3 files.
- **Version B** (Phase-1.2b/1.2c, e.g. `test_training_plan_schema.py`): Extracts `_sync_url()` once, then uses it in every helper. Spread: 11 files.

Counting exact lines, this is **~112 lines duplicated per file × 14 files = ~1,568 lines** of near-identical boilerplate. The only difference between files is the table name passed as a parameter.

**Current state** (excerpt from `test_checkpoint_schema.py`):

```python
def _sync_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://",
            "postgresql+psycopg2://",
        )
    return database_url


def _columns(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_columns(table))
    finally:
        engine.dispose()


def _unique_constraints(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_unique_constraints(table))
    finally:
        engine.dispose()

# … repeated for _check_constraints, _indexes, _foreign_keys
```

This exact pattern appears in: `test_training_plan_schema.py`, `test_twin_state_schema.py`, `test_checkpoint_schema.py`, `test_weekly_plan_schema.py`, `test_planned_session_schema.py`, `test_generated_workout_schema.py`, `test_generation_event_schema.py`, `test_athlete_fitness_schema.py`, `test_secondary_event_schema.py`, `test_regeneration_task_schema.py`, `test_coaching_message_schema.py`, `test_activity_schema.py`, `test_workout_step_schema.py`, plus two Phase-1.2a files (`test_athlete_profile_schema.py`, `test_athlete_preferences_schema.py`) that inline the URL conversion differently.

**Risk of inconsistency**: Any change to how sync engines are constructed (e.g. adding `pool_pre_ping=True` or switching to `psycopg2-binary` URL scheme) must be applied in 14 places. If missed, some tests run with stale connection behaviour.

### 2.2. 🟠 HIGH — Private `_columns()` / `_indexes()` Duplication in Unit Column Tests

**Files affected**: 16 unit column tests

**Problem**: Every `test_*_columns.py` file defines its own `_columns()` → `dict[str, Column]` or `_columns() -> dict[str, object]` helper, plus `_indexes()`, `_check_constraints()`, `_unique_constraints()`, and sometimes `_foreign_keys_referencing()`. The implementations are identical (query `Model.__table__.columns`, etc.).

Example from `test_activity_columns.py`:

```python
def _has_column(model, name: str) -> bool:
    return any(column.key == name for column in model.__table__.columns)
```

Example from `test_athlete_fitness_columns.py`:

```python
def _columns() -> dict[str, object]:
    return {column.key: column for column in AthleteFitness.__table__.columns}


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in AthleteFitness.__table__.indexes}


def _check_constraints() -> list[CheckConstraint]:
    return [c for c in AthleteFitness.__table__.constraints if isinstance(c, CheckConstraint)]


def _foreign_keys_referencing(column_key: str) -> list[ForeignKey]:
    return [fk for fk in AthleteFitness.__table__.foreign_keys if fk.parent.name == column_key]
```

Example from `test_training_goal_columns.py`:

```python
def _columns() -> dict[str, object]:
    return {column.key: column for column in TrainingGoal.__table__.columns}


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in TrainingGoal.__table__.indexes}


def _check_constraints() -> list[CheckConstraint]:
    return [c for c in TrainingGoal.__table__.constraints if isinstance(c, CheckConstraint)]
```

These are **pure functions with no side effects** and nearly zero arguments. They should live once in a shared module.

### 2.3. 🟠 HIGH — Athlete Factory Duplication

**Files affected**: `test_refresh_token_repository.py`, `test_discard_refresh_token_ips.py`, `test_athlete_auth_primary_enforcement.py`

**Problem**: The same `_make_athlete(db_session)` helper is defined in three separate integration tests. It always does the same thing: create an `Athlete` with a unique UUID email, add/flush, and return.

```python
# Identical in all three files:
async def _make_athlete(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(email=f"athlete-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()
    return athlete
```

### 2.4. 🟡 MEDIUM — `_register_kwargs` Duplication

**Files affected**: `test_auth_service.py`, `test_phase_1_1_registration_regression.py`

The `_register_kwargs()` helper is defined in both files with the same default parameters. They differ only in the default `email` string, making them candidates for a shared factory with an `email` override.

### 2.5. 🟡 MEDIUM — `_check_text` Duplication

**Files affected**: `test_training_goal_columns.py`, `test_planned_session_columns.py`, `test_checkpoint_columns.py`, `test_athlete_fitness_columns.py`

The same `_check_text(check)` helper — unwrapping `CheckConstraint.expression` or `.sqltext` — is copy-pasted in every unit column test that asserts on check constraints.

```python
def _check_text(self, check: CheckConstraint) -> str:
    expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
    return (str(expr) if expr is not None else "")
```

### 2.6. 🟢 LOW — Secret-Leakage Scan Lists

**Files affected**: `test_auth_endpoints.py`, `behaviour/test_auth_user_journey.py`

Both API and behaviour tests iterate the same tuple of forbidden strings:

```python
("hashed_password", "token_hash", "provider_tokens", "provider_user_id")
```

If a new secret field is ever introduced, both files must be updated or one will miss it.

### 2.7. 🟢 LOW — Consistency Smells

| Smell | Location | Example |
|-------|----------|---------|
| Import block duplication | All unit column tests | `from sqlalchemy import CheckConstraint, DateTime, ...` is 80%+ identical; a shared import pattern or re-export could halve the import noise. |
| Mixed quoting styles | `test_auth_service.py` | `_register_kwargs` uses `=` for default but some integration tests use `*` for kwarg-only — no functional issue, but the inconsistency is jarring when diffing. |
| Unused `os` import | `test_athlete_profile_schema.py` | `import os` appears twice in the file (due to duplicate imports from a copy-paste error). |
| Duplicate import block | `test_athlete_profile_schema.py` | The entire import block is repeated verbatim (`from __future__` through `TABLE = "athlete_profiles"`). |
| Mixed `TABLE` constant style | All schema tests | Some files define `TABLE = "checkpoints"`, others `WEEKLY_PLANS = "weekly_plans"`; this is fine per-file, but the lack of a canonical `SchemaInspector(table_name=...)` helper forces each file to repeat the table-name plumbing. |

---

## 3. Proposed Centralization Architecture

### 3.1. New File: `tests/utils/schema_helpers.py`

A single, zero-side-effect module for all DB schema introspection that does **not** need a live session.

```python
"""Pure helpers for SQLAlchemy declarative schema introspection.

No database engine is created at import time.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


def get_sync_database_url() -> str:
    """Return a synchronous psycopg2 DATABASE_URL from the environment."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )
    return database_url

def _inspect_method(method_name: str, table: str) -> list[dict]:
    """Generic sync-engine inspect helper."""
    engine = create_engine(get_sync_database_url())
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            method = getattr(inspector, method_name)
            return list(method(table))
    finally:
        engine.dispose()

def db_columns(table: str) -> list[dict]:
    return _inspect_method("get_columns", table)

def db_unique_constraints(table: str) -> list[dict]:
    return _inspect_method("get_unique_constraints", table)

def db_check_constraints(table: str) -> list[dict]:
    return _inspect_method("get_check_constraints", table)

def db_indexes(table: str) -> list[dict]:
    return _inspect_method("get_indexes", table)

def db_foreign_keys(table: str) -> list[dict]:
    return _inspect_method("get_foreign_keys", table)
```

**Impact**: ~1,568 lines of duplicated schema introspection across 14 files can be replaced by a single import and a one-line call:

```python
from tests.utils.schema_helpers import db_columns, db_unique_constraints

# Before (24 lines)
def _columns(table: str) -> list[dict]: ...

# After (1 line each)
cols = db_columns("training_plans")
```

### 3.2. New File: `tests/utils/model_helpers.py`

A module for pure functions that inspect SQLAlchemy ORM mappers (unit tests, no DB).

```python
"""Pure helpers for ORM mapper introspection (no DB required)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
    from sqlalchemy.orm import DeclarativeBase


def get_columns(model) -> dict[str, object]:
    return {column.key: column for column in model.__table__.columns}


def get_indexes(model) -> dict[str, Index]:
    return {idx.name: idx for idx in model.__table__.indexes}


def get_check_constraints(model) -> list[CheckConstraint]:
    return [c for c in model.__table__.constraints if isinstance(c, CheckConstraint)]


def get_unique_constraints(model) -> list[UniqueConstraint]:
    return [c for c in model.__table__.constraints if isinstance(c, UniqueConstraint)]


def get_foreign_keys_referencing(model, column_key: str) -> list[ForeignKey]:
    return [fk for fk in model.__table__.foreign_keys if fk.parent.name == column_key]


def get_check_text(check) -> str:
    """Unwrap a CheckConstraint's text expression."""
    expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
    return str(expr) if expr is not None else ""


def has_column(model, name: str) -> bool:
    return any(column.key == name for column in model.__table__.columns)
```

### 3.3. New File: `tests/utils/factories.py`

Shared model factories and payload builders for integration tests that hit the DB.

```python
"""Shared test factories for creating domain model instances.

These are async helpers that use the per-test db_session fixture.
"""
from __future__ import annotations

import uuid

from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.enums import AuthProvider, Sex


async def make_athlete(db_session, email: str | None = None) -> Athlete:
    """Create and flush an Athlete with a unique email."""
    if email is None:
        email = f"athlete-{uuid.uuid4()}@example.com"
    athlete = Athlete(email=email)
    db_session.add(athlete)
    await db_session.flush()
    return athlete


async def make_auth(
    db_session,
    *,
    athlete_id: uuid.UUID,
    provider: AuthProvider = AuthProvider.EMAIL,
    is_primary: bool = True,
) -> AthleteAuth:
    """Create and flush an AthleteAuth row."""
    auth = AthleteAuth(
        athlete_id=athlete_id,
        provider=provider,
        is_primary=is_primary,
    )
    db_session.add(auth)
    await db_session.flush()
    return auth


async def make_token_row(
    db_session,
    athlete_id: uuid.UUID,
    *,
    token_hash: str | None = None,
    ip_address: str | None = None,
) -> "RefreshToken":
    """Create a RefreshToken row with sensible defaults."""
    if token_hash is None:
        token_hash = f"hash-{uuid.uuid4()}"
    from datetime import datetime, timedelta, timezone
    from app.models.refresh_token import RefreshToken

    token = RefreshToken(
        athlete_id=athlete_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        ip_address=ip_address,
    )
    db_session.add(token)
    await db_session.flush()
    return token
```

### 3.4. New File: `tests/utils/assertions.py`

Shared assertion helpers that codify architectural invariants once, reused everywhere.

```python
"""Shared assertion patterns that codify security and domain invariants."""
from __future__ import annotations

# Security invariants
SECRET_LEAKAGE_FIELDS = (
    "hashed_password",
    "token_hash",
    "provider_tokens",
    "provider_user_id",
)


def assert_no_secrets_in_text(text: str, *, message: str = "") -> None:
    """Assert that no forbidden credential/PII fields appear in text."""
    lower = text.lower()
    for field in SECRET_LEAKAGE_FIELDS:
        assert field not in lower, f"{message or 'Forbidden field'} '{field}' found in response/text."


def assert_no_secrets_in_logs(records: list, *, extra_keys: tuple[str, ...] = ()) -> None:
    """Scan LogRecord.__dict__ for forbidden fields.

    Complements ``cap_auth_logs`` fixture in behaviour tests.
    """
    rendered = " ".join(str(r.__dict__) for r in records).lower()
    for field in (*SECRET_LEAKAGE_FIELDS, "password", *extra_keys):
        assert field not in rendered, f"Secret field '{field}' leaked into logs."
```

---

## 4. Migration Plan (Non-Breaking, Per Phase)

Because every test file is self-contained and the helpers are private functions (`_columns`, etc.), the refactor is **not urgent for correctness** but **high value for maintainability**. The recommended strategy is a gradual, per-phase cut-over rather than a big-bang rewrite.

### Phase A: Introduce the Modules (Immediate)

1. Create `tests/utils/__init__.py` (empty, for package).
2. Add `tests/utils/schema_helpers.py` (section 3.1).
3. Add `tests/utils/model_helpers.py` (section 3.2).
4. Add `tests/utils/factories.py` (section 3.3).
5. Add `tests/utils/assertions.py` (section 3.4).
6. Add one representative test file (e.g. `test_training_plan_schema.py`) that imports from the new modules to validate the API surface.

### Phase B: Backfill Schema Helpers (Next sub-phase)

As part of the **next** sub-phase's test generation pass (whenever Test Architect runs for a new plan), for each existing schema test:

- **Delete** the private `_sync_url`, `_columns`, `_unique_constraints`, etc.
- **Replace** with `from tests.utils.schema_helpers import db_columns, db_unique_constraints, ...`
- Ensure no behavioural changes (the helpers return exactly the same types).

This can be done incrementally — the old and new patterns coexist without conflict.

### Phase C: Backfill Unit Column Helpers (Next sub-phase)

Same pattern for the 16 unit column tests:

- Delete local `_columns`, `_indexes`, `_check_constraints`, `_foreign_keys_referencing`, `_check_text`, `_has_column`.
- Replace with imports from `tests.utils.model_helpers`.

### Phase D: Backfill Factories & Assertions (Opportunistic)

When any integration test file isnext touched (e.g. for a bug fix or new sub-phase):

- Replace local `_make_athlete`, `_make_auth`, `_make_token` with imports from `tests.utils.factories`.
- Replace secret-leakage tuple literals with `from tests.utils.assertions import assert_no_secrets_in_text`.

---

## 5. Rejected Alternatives

| Approach | Rationale For Rejection |
|----------|------------------------|
| Put everything in `conftest.py` | `conftest.py` already >470 lines and includes engine/session setup. Mixing pure helpers with pytest fixtures would bloat the file and make it harder to reason about import order. Modular packages are cleaner. |
| Use a third-party library (e.g. `pytest-factoryboy`) | Adds external dependency for something that maps 1:1 to our domain. Keeps test suite self-contained and reduces dependency attack surface. |
| Convert to pytest fixtures | Schema introspection helpers are pure functions with no per-test state. Making them fixtures adds boilerplate (`@pytest.fixture`) and makes them harder to use inside loops or parametrized tests. Factories (which DO have side effects) could be fixtures, but factory functions are more flexible for varying arguments. |

---

## 6. Manifest Update

No manifest entries need to change for this refactor. The test file paths remain identical; only internal imports are affected. Once all files are migrated, `tests/README.md` should be updated to reference the new `tests/utils/` package and deprecate the old inline helpers pattern.

---

## 7. Summary

| Category | Duplication Count | Estimated Lines Saved | Priority |
|----------|------------------|----------------------|----------|
| Schema inspection helpers | 14 files | ~1,568 | Critical |
| Unit ORM introspection helpers | 16 files | ~320 | High |
| Athlete factory | 3 files | ~20 | High |
| Register kwargs | 2 files | ~15 | Medium |
| Check-text helper | 4 files | ~16 | Medium |
| Secret-leakage lists | 2 files | ~8 | Low |
| **Total** | **39 files** | **~1,947 lines** | — |

The proposed `tests/utils/` package would consolidate these patterns, eliminate ~1,950 lines of copy-paste code, and guarantee that all future tests use the validated correct pattern for schema introspection, ORM unit tests, and security assertions.
