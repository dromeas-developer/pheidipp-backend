---
name: stack-truth-conformance
description: >
  Load this when validating implementation code against stack-truth rules.
  Contains the severity classification for stack-truth violations —
  which rules are CRITICAL, MAJOR, or MINOR when broken. Stack-truth
  itself (the rules) is already in global context via
  `.opencode/instructions/001-stack-truth.md` — this skill adds the
  validation severity mapping only, not a restatement of the rules.
---

# Stack-Truth Conformance — Validation Severity Mapping

Stack-truth rules are defined in `.opencode/instructions/001-stack-truth.md`
(already in context). This skill maps each rule category to the severity
the validator assigns when the rule is violated.

Apply the severity classification below. The rules themselves are in
stack-truth — reference them by name, not by restating them.

## CRITICAL — architecture broken

These violations always route through the Resolution Path test (Step 7)
before final routing — a CRITICAL label does not automatically mean
`p-implementation-resolver`.

| Stack-Truth Rule | Stack-Truth Reference |
|---|---|
| Layer skipping or reversal (api → repository directly) | Layer Architecture |
| Business logic outside the service layer | Layers: api, services |
| Ownership boundary crossed (entity logic in wrong service) | Layers: services, repositories |
| Direct provider SDK usage bypassing the LiteLLM proxy | LLM Access (STRICT) |
| LLM proxy bypass — custom retries, rate limiting, or circuit-breaker in agent code | LLM Access (STRICT) |
| LLM proxy bypass — reading provider API keys directly | LLM Access (STRICT) |

## MAJOR — behaviour deviates

| Stack-Truth Rule | Stack-Truth Reference |
|---|---|
| DB access not using AsyncSession (sync SQLAlchemy) | Async Rules |
| Transaction not atomic where plan requires atomicity | Async Rules (inferred: atomicity expectation) |
| Event produced before successful commit | Async Rules (inferred: event-after-commit pattern) |
| Business logic in the api layer | Layer Architecture |
| Direct repository access from the api layer | Layer Architecture |
| Direct repository access outside services | Layer Architecture |
| Service method not returning `tuple[list[Model], int]` for list endpoints | List Endpoints |
| Route handler calling repository directly | List Endpoints |
| Route handler executing SQLAlchemy query directly | List Endpoints |
| Worker task with sync def instead of async def | Background Jobs |
| Hardcoded values instead of environment variables | Configuration |

## MINOR — implementation hygiene

Always routes to `p-coder-fix-mode` directly — no Resolution Path assessment needed.

| Stack-Truth Rule | Stack-Truth Reference |
|---|---|
| Using `parse_obj()` or `.dict()` instead of `model_validate`/`model_dump` | Pydantic v2 |
| PATCH handler not using `model_dump(exclude_unset=True)` | Pydantic v2 (inferred: partial update pattern) |
| Cross-model relationship import not using `TYPE_CHECKING` guard | Async Rules (inferred: prevents circular imports at runtime) |
| SQLAlchemy Enum column using `native_enum=True` | Database (inferred: TimescaleDB compatibility) |
| New model not exported in `app/models/__init__.py` | Database: Schema defined in ORM models |
| New schema not exported in `app/schemas/__init__.py` | schemas/ layer |
| Route file outside `app/api/v1/` | Layers: api |

## Validation Procedure

1. Reference stack-truth in global context for the full rule text.
2. For each implementation file loaded in Step 2, check against every
   applicable rule.
3. Classify each violation using the severity table above.
4. Feed CRITICAL and MAJOR findings through Step 7's Resolution Path test.
5. Route MINOR findings directly to `p-coder-fix-mode`.
