---
name: type-hygiene-standards
description: >
  Load this when generating code (tests or production) to write type
  annotations at creation time, not as post-hoc cleanup. Defines canonical
  annotations for test fixtures, production function signatures, and
  Pydantic schema fields. Prevents the cascade where one untyped parameter
  causes 100+ reportUnknown* errors in pyright strict mode. Loaded by
  p-test-architect (Step 6 — before test generation) and p-coder-batch-mode/p-coder-fix-mode
  (pre-flight — before any implementation). Not for s-diagnostics-fixer
  (already knows these patterns) or p-implementation-validator (uses
  type-enforcement-conformance for auditing).
---

# Type Hygiene Standards

## Agent Scope

| Section | p-test-architect | p-coder-batch-mode/p-coder-fix-mode |
|---|---|---|
| §1 Shared — Cascade Prevention | ✅ Load | ✅ Load |
| §2 Shared — Import Patterns | ✅ Load | ✅ Load |
| §3 Shared — Unused Cleanup | ✅ Load | ✅ Load |
| §4 Shared — pyrightconfig Interaction | ✅ Load | ✅ Load |
| §5 Test-Specific — Fixture Annotations | ✅ Load | Skip |
| §6 Test-Specific — Helper & Inner Functions | ✅ Load | Skip |
| §7 Production-Specific — Function Annotations | Skip | ✅ Load |
| §8 Production-Specific — Pydantic Fields | Skip | ✅ Load |

---

## §1 Shared — Cascade Prevention

In pyright strict mode, every untyped function parameter is treated as
`Unknown`. From that single `Unknown` parameter, everything derived
cascades:

```
db_session untyped (Unknown)
  → db_session.get(...)    → Unknown  (reportUnknownMemberType)
  → athlete = result       → Unknown  (reportUnknownVariableType)
  → athlete.id             → Unknown  (reportUnknownMemberType)
  → assert athlete.id == X → Unknown  (reportUnknownVariableType)
```

One untyped parameter → **20–200+ errors** in a single file. Adding the
type annotation eliminates every error in the cascade at once — at a cost
of one line per parameter: `db_session: AsyncSession`.

**Rule: every function parameter must carry a type annotation. No
exceptions for test files, helper functions, inner functions, or
monkeypatched closures.**

---

## §2 Shared — Import Patterns

Merge new imports into existing import blocks. Never create a duplicate
`from <module> import` line.

```python
# Good — merged into existing blocks
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# Bad — duplicate import line
from sqlalchemy.ext.asyncio import AsyncSession  # already exists above
```

---

## §3 Shared — Unused Cleanup

Before a file is considered complete, remove:
- **Unused imports** — remove the name from the import statement. If it's
  the last name in a multi-line `from X import (...)` block, collapse to
  single-line or remove the block entirely.
- **Unused variables** — replace with `_`. Example: `athlete, result = ...`
  where `result` is unused → `athlete, _ = ...`.

---

## §4 Shared — pyrightconfig Interaction

`pyrightconfig.json` sets `typeCheckingMode: "strict"`. The `tests/`
execution environment suppresses `reportMissingParameterType` ("this
parameter should have an annotation") but does **not** suppress
`reportUnknownParameterType` ("this parameter's type is Unknown").

| Suppressed in tests/ | Still active in tests/ |
|---|---|
| `reportMissingParameterType` | `reportUnknownParameterType` |
| `reportPrivateUsage` | `reportUnknownVariableType` |
| `reportUnusedFunction` | `reportUnknownMemberType` |
| | `reportUnknownArgumentType` |

**Do not assume the `tests/` environment lets you skip annotations.**
It silences the "please annotate" warning but not the "type is Unknown"
error and its entire cascade.

---

## §5 Test-Specific — Fixture Annotations (p-test-architect)

Every pytest fixture parameter in a test function must carry the canonical
type annotation. Copy these exactly — do not substitute or abbreviate.

| Fixture parameter | Type annotation | Import needed |
|---|---|---|
| `db_session` | `AsyncSession` | `from sqlalchemy.ext.asyncio import AsyncSession` |
| `client` | `httpx.AsyncClient` | (already available via `httpx` usage) |
| `monkeypatch` | `pytest.MonkeyPatch` | `import pytest` (already standard) |
| `mock_*` | `AsyncMock` or `MagicMock` | `from unittest.mock import AsyncMock, MagicMock` |

### Example

```python
# Correct — every fixture parameter annotated
async def test_onboarding_creates_athlete(self, db_session: AsyncSession):
    ...

async def test_defer_failure(self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    ...

# Wrong — cascade will produce 100+ errors
async def test_onboarding_creates_athlete(self, db_session):
    ...
```

---

## §6 Test-Specific — Helper & Inner Functions (p-test-architect)

### Helper functions defined in test files

Every parameter must be annotated. Use `dict[str, Any] | None` for
optional kwargs dicts.

```python
async def _run_full_onboarding(
    db_session: AsyncSession,
    *,
    profile_kwargs: dict[str, Any] | None = None,
    prefs_kwargs: dict[str, Any] | None = None,
    goal_kwargs: dict[str, Any] | None = None,
) -> tuple[Athlete, OnboardingResult]:
```

`Any` is acceptable here — these are test helpers wiring up fixtures,
not production contracts. The `dict[str, Any]` annotation prevents the
`Unknown` cascade without over-specifying what the test builder functions
return.

### Monkeypatched inner functions

When replacing a method via `monkeypatch.setattr`, the inner function's
parameter types must match the original method's signature.

```python
# Original signature: async def _defer_generate_plan(self, athlete_id: uuid.UUID) -> None

# Correct — types match the original
async def failing_defer(self: OnboardingService, athlete_id: uuid.UUID) -> None:
    raise RuntimeError("procrastinate defer failed")

# Wrong — self and athlete_id will be Unknown, cascading to monkeypatch.setattr
async def failing_defer(self, athlete_id):
    raise RuntimeError("procrastinate defer failed")
```

---

## §7 Production-Specific — Function Annotations (p-coder-batch-mode/p-coder-fix-mode)

### Public functions and methods

Every public function (no `_` prefix) must annotate **all parameters and
the return type**. This is non-negotiable in strict mode.

```python
# Correct
async def create_athlete(
    db_session: AsyncSession,
    profile: AthleteProfileInput,
    preferences: AthletePreferencesInput | None = None,
) -> Athlete:
    ...

# Wrong — missing return type triggers reportMissingReturnType;
# missing parameter types trigger reportUnknownParameterType
async def create_athlete(db_session, profile, preferences=None):
    ...
```

### Private methods (`_prefix`)

Annotate parameters. The return type may be omitted if the function is
short and the return is obvious from the body — but annotating it
costs one line and prevents any cascade from callers.

### `Any` in production code

Avoid `Any` in production code unless there is genuinely no narrower type.
A function parameter that accepts "anything" is usually a design problem,
not a typing problem. Use `dict[str, Any]` only for truly dynamic data
(e.g., raw JSONB payloads before validation).

---

## §8 Production-Specific — Pydantic Fields (p-coder-batch-mode/p-coder-fix-mode)

### Use the narrowest type that matches the contract

| Instead of | Use | Why |
|---|---|---|
| `str` for a known set of values | `Literal["a", "b", "c"]` | Catches invalid values at the schema boundary, before the service sees them |
| `str` for a domain concept with an existing Enum | The Enum class (e.g., `SportBackground`) | Architecture already defines the set; `str` lets any value through |
| `int` for a positive-only value | `int` with `gt=0` in `Field(...)` | Pydantic `Field` constraints are type-level enforcement |
| `Optional[X]` for a required field | `X` (non-optional) | Optional where the contract says "always present" masks real bugs |
| `Any` | The concrete type | `Any` disables type checking for that field and everything derived from it |

### Custom validators

Use `@field_validator` or `@model_validator` for rules that can't be
expressed by type annotations alone (cross-field validation, conditional
required fields, format checks beyond what Pydantic provides natively).
A `@field_validator` that only checks `isinstance(x, str)` is redundant —
the type annotation already enforces that.
