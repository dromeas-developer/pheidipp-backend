# Running and Debugging Tests

Operational guide for running the test suite and debugging common failures.
This document is the home for "how do I run the tests" and "what does this
failure mean" questions — it is NOT the contract. The mocking contract
(what fixtures exist, what is mocked at each layer, what anti-patterns to
avoid) lives in `tests/MOCKING_CONTRACT.md`. Long-form reusable lessons
(symptom, root cause, code blocks, meta-rules) live in `tests/README.md`
"Dated Lessons".

---

## Running Tests

```bash
# Full suite
bash scripts/run-tests.sh tests/

# Specific file
bash scripts/run-tests.sh tests/integration/test_auth_service.py

# Specific test
bash scripts/run-tests.sh tests/integration/test_auth_service.py::TestClass::test_method

# Verbose output
bash scripts/run-tests.sh tests/ -v
```

For collection-only checks (no test execution, no DB, no infrastructure
required — verifies a file imports and its tests/fixtures are discoverable):

```bash
bash scripts/pytest.sh --collect-only <path> [<path> ...]
```

Always use `scripts/pytest.sh` (or `scripts/run-tests.sh`), never bare
`pytest` — pytest is installed in `.venv` and a bare `pytest` invocation
will not have activated it.

---

## Debugging Test Failures

### Symptom: "409 Conflict" on registration
**Cause:** Leftover data from previous test.
**Fix:** Ensure the test uses a unique email (e.g. `f"{uuid.uuid4()}@example.com"`).

### Symptom: `MissingGreenlet` error
**Cause:** Async IO attempted outside the greenlet context. Most often
triggered by accessing an expired ORM attribute after `expire_all()` or
`rollback()` — see the dated lessons
"Post-rollback ORM attribute access triggers `MissingGreenlet` — use column-level SELECT for JSONB reads"
and "Post-rollback PK access in WHERE clauses triggers `MissingGreenlet` — capture the PK before `rollback()`"
in `tests/README.md` for the canonical patterns.

### Symptom: Test passes alone but fails in suite
**Cause:** Data contamination from an earlier test.
**Fix:** Check whether the test commits data; ensure unique identifiers
(athletes, tokens, activities) per test.

### Symptom: `IntegrityError` on a unique constraint during fixture setup
**Cause:** A helper builds a parent chain (e.g. `TrainingGoal`) that
violates a partial unique index when invoked multiple times. See
"Multi-call `_create_planned_session()` creates duplicate active TrainingGoals"
in `tests/README.md`.

### Symptom: `assert 'None' == '<expected-uuid>'` on a payload field like
`twin_state_id` / `athlete_id`
**Cause:** The mocked `Repository.insert()` does not simulate the database's
PK assignment. See "Mocked `Repository.insert()` must simulate database PK
assignment" in `tests/README.md`.

### Symptom: `DID NOT RAISE` when a test expects an exception on a raw
string passed to a `StrEnum`-typed parameter
**Cause:** `StrEnum.__eq__` makes the membership test succeed by value, the
reject branch is never entered, and no exception is raised. See
"`StrEnum.__eq__` silently accepts raw strings whose value matches a
whitelist member" in `tests/README.md`.

### Symptom: `assert 'ClassName.MEMBER_NAME' == 'member_name'` on an enum
field (e.g. `MeasurementSource`)
**Cause:** `str(enum_member)` returns the qualified name, not the `.value`.
Use `enum_member.value` instead. See "`str(enum_member)` is NOT the `.value`
for `class Foo(str, Enum)`" in `tests/README.md`.

### Symptom: `IndexError: list index out of range` on
`(await db_session.execute(select(...))).scalars().all()[0]`
**Cause:** A fixture row that the post-service-call SELECT depends on was
rolled back along with the service call's modifications. The fixture helper
called `flush()` (not `commit()`) and the test then called
`db_session.rollback()`. See "Rollback tests must commit fixture rows in
their own transaction — `flush()` does not survive `rollback()`" in
`tests/README.md`.

---

## See Also

- `tests/MOCKING_CONTRACT.md` — the mocking contract: layer boundaries,
  canonical fixtures, Known Anti-Patterns table, Change Log.
- `tests/README.md` — the test guide: shared utilities, test isolation,
  Common Pitfalls, and Dated Lessons (long-form reusable lessons).
- `tests/conftest.py` — fixture definitions and cleanup logic.
- `pytest.ini` — pytest configuration.
- `docs/vision/` — product vision and constraints.
- `docs/adr/` — architecture decision records.
