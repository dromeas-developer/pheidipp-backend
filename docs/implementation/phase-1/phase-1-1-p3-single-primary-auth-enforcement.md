# Implementation Plan: Phase-1.1-P3 — Single Primary AthleteAuth Enforcement
## Plan ID: Phase-1.1-P3

## Sub-Phase Reference
Sub-Phase ID: Phase-1.1
Sub-Phase Title: Phase 1 — Email/Password Authentication (Patch 3)

## Objective
Enforce at the database level the invariant that exactly one `AthleteAuth` record per athlete must have `is_primary = true`. This patch adds a partial unique index to prevent application-layer bugs from creating multiple primary methods or zero primary methods for a single athlete. No other auth behaviour is changed.

## Scope
- **Database constraint:** Add a partial unique index `CREATE UNIQUE INDEX ON athlete_auths (athlete_id) WHERE is_primary = true`.
- **Migration:** Alembic migration adding the index in `upgrade()` and dropping it in `downgrade()`.
- **Documentation:** Update `01-entities/athlete-auth.md` to explicitly state the DB-level enforcement mechanism.
- **Verification:** Integration test asserting that inserting a second `is_primary = true` row for the same `athlete_id` raises an `IntegrityError`.

## Out Of Scope
- OAuth providers, account linking, primary-method switching, or password-change endpoints.
- Changes to registration, login, or refresh-token rotation logic (application layer already sets `is_primary = true` correctly).
- Changes to `AthleteProfile`, `RefreshToken`, or event publication.
- Schema changes to `AthleteAuth` columns themselves (only an index is added).

## Architecture Contracts
- `01-entities/athlete-auth.md` — DEPENDS ON (invariant now explicitly enforced at DB layer via partial unique index).
- `docs/release-plan/phase-1/phase-1-1-email-password-auth.md` — DEPENDS ON (updated invariants section to reference DB enforcement).
- `docs/adr/005-ip-address-and-token-hash-security.md` — UNCHANGED (this patch is orthogonal to IP/token-hash concerns).

## Invariants
- **Exactly one `AthleteAuth` per athlete must have `is_primary = true`.** Previously enforced at application layer only; now enforced at DB layer via partial unique index. Attempting to insert a second `is_primary = true` row for the same `athlete_id` raises `IntegrityError` (HTTP 500 at API surface, but effectively impossible in normal operation).
- **Zero primary methods are prevented.** If an athlete has one `AthleteAuth` where `is_primary = true` and it is deleted or set to `false`, the index allows a new primary to be created, but race conditions during primary reassignment are now caught at DB level.
- All other invariants from Phase-1.1 remain in force.

## Implementation Steps
1. **Create Alembic migration:**
   - Generate new migration file: `alembic/versions/<rev>_phase_1_1_p3_single_primary_auth.py`.
   - In `upgrade()`: `op.create_index('ix_athlete_auths_single_primary', 'athlete_auths', ['athlete_id'], unique=True, postgresql_where="is_primary = true")`.
   - In `downgrade()`: `op.drop_index('ix_athlete_auths_single_primary', table_name='athlete_auths')`.
   - Note: Use `postgresql_where` syntax for partial index; this is PostgreSQL-specific but matches the project's DB engine.

2. **Update architecture documentation:**
   - Edit `docs/architecture/01-entities/athlete-auth.md`:
     - In the "Invariants" section, add: "Database enforcement: unique partial index `ix_athlete_auths_single_primary` on `(athlete_id) WHERE is_primary = true` prevents multiple primaries at the storage layer."
     - Reference the migration file by revision ID once created.

3. **Add integration test:**
   - Create or extend test file `tests/integration/test_athlete_auth_primary_enforcement.py` (or equivalent in project structure).
   - Test case: Given an athlete with one `AthleteAuth` where `is_primary = true`, attempt to insert a second `AthleteAuth` with `is_primary = true` for the same athlete.
   - Assert: `sqlalchemy.exc.IntegrityError` is raised.
   - Test case: Given an athlete with zero `AthleteAuth` rows, verify that inserting one with `is_primary = true` succeeds (sanity check).
   - Test case: Given an athlete with one `is_primary = false` row, verify that inserting another `is_primary = false` succeeds (no regression on non-primary multiplicity).

4. **Run migration against fresh database:**
   - Execute `scripts/db-upgrade.sh` (or `alembic upgrade head`) to apply the migration.
   - Verify the index exists: `\di athlete_auths` in psql shows `ix_athlete_auths_single_primary`.

## Pseudocode
```python
# Alembic migration (simplified)
def upgrade():
    op.create_index(
        'ix_athlete_auths_single_primary',
        'athlete_auths',
        ['athlete_id'],
        unique=True,
        postgresql_where="is_primary = true"
    )

def downgrade():
    op.drop_index('ix_athlete_auths_single_primary', table_name='athlete_auths')

# Integration test pseudocode
async def test_cannot_create_two_primaries():
    athlete = await create_test_athlete()
    await create_auth(athlete_id=athlete.id, is_primary=True)  # succeeds
    with pytest.raises(IntegrityError):
        await create_auth(athlete_id=athlete.id, is_primary=True)  # fails

async def test_can_create_multiple_non_primaries():
    athlete = await create_test_athlete()
    await create_auth(athlete_id=athlete.id, is_primary=False)  # succeeds
    await create_auth(athlete_id=athlete.id, is_primary=False)  # also succeeds
```

## Testing Requirements
- **`test_cannot_create_two_primary_auth_methods`**: Insert two `AthleteAuth` rows with `is_primary = true` for the same `athlete_id` within separate transactions; the second insert raises `IntegrityError`.
- **`test_can_create_multiple_non_primary_auth_methods`**: Insert two `AthleteAuth` rows with `is_primary = false` for the same `athlete_id`; both succeed.
- **`test_primary_can_be_created_when_none_exist`**: Insert one `AthleteAuth` with `is_primary = true` for a new athlete; succeeds.
- **`test_migration_applies_cleanly`**: Run `alembic upgrade head` on a fresh database with no errors; index appears in `\di` output.
- **`test_migration_rollback_cleanly`**: Run `alembic downgrade -1`; index disappears without error.

## Coder Handoff Notes
- **Migration naming:** Use the project's Alembic naming convention (e.g., `phase_1_1_p3_single_primary_auth`). The revision ID will be auto-generated.
- **Partial index syntax:** The `postgresql_where` parameter is SQLAlchemy's escape hatch for PostgreSQL-specific partial indexes. Do not attempt to make this engine-agnostic — the project uses PostgreSQL exclusively.
- **Race conditions:** The application layer already sets `is_primary = true` correctly during registration. This migration defends against future code paths (e.g., OAuth linking, primary reassignment) that might accidentally introduce multiple primaries. It also prevents the "zero primaries" edge case during buggy reassignment logic.
- **No application-layer changes needed:** The existing `AuthService.register()` already sets `is_primary = true` for the first (and only) `AthleteAuth` row. No service code changes are required.
- **Test isolation:** The integration test must run in a transaction that is rolled back after each test to avoid polluting the test database with orphaned `AthleteAuth` rows.
- **Documentation update:** The architecture doc update is mandatory — this is a DB-level invariant that future architects must know about when reasoning about auth-method linking/unlinking.
- **If the project already has a `tests/` directory structure:** place the test in `tests/integration/repository/test_athlete_auth_repository.py` or a dedicated `test_athlete_auth_primary_enforcement.py` file. If no test structure exists, create a minimal `tests/` directory with `__init__.py`, `conftest.py` (if needed), and the test file.