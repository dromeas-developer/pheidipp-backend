# Implementation Plan: Phase-1.2c — Add Missing Training Plan Twin State FK
## Plan ID: Phase-1.2c-P1-Fix

## Sub-Phase Reference
Sub-Phase ID: Phase-1.2c
Sub-Phase Title: Twin Fitness Coaching

## Objective
Resolve a database schema omission where the foreign key constraint linking `training_plans.twin_state_id` to `twin_states.id` was not created. The Phase-1.2b migration explicitly deferred this constraint to Phase-1.2c once the `twin_states` table was created. However, the SQLAlchemy model was not updated with the `ForeignKey` directive, meaning Alembic did not autogenerate the constraint in the Phase-1.2c migration. This plan adds the constraint via a new, supplementary migration, unblocking the Test Architect's schema verification.

## Scope
- Modify the SQLAlchemy model `app/models/training_plan.py` to include the deferred `ForeignKey` definition on the `twin_state_id` column.
- Generate a **new** Alembic migration reflecting this new constraint.

## Out Of Scope
- Modifying the already-committed `alembic/versions/79dc97d4e433_phase_1_2c_twin_fitness_coaching_.py` file.

## Architecture Contracts
- `01-entities/training-plan.md` — DEPENDS ON `twin-state` (`twin_state_id` records which twin version produced this plan).

## Invariants
- **`twin_state_id` records which twin version produced this plan.** A plan produced at LOW confidence will have different phase structures than one produced at MEDIUM or HIGH.

## Implementation Steps
Ordered list of steps to resolve the missing FK:

1. [OWNER: Coder] In `app/models/training_plan.py`, update the `twin_state_id` mapped column to include the deferred foreign key. Change it from:
   `twin_state_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)`
   to:
   `twin_state_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("twin_states.id", ondelete="SET NULL"), nullable=True)`
   Remove the now-resolved docstring comment stating the FK is delayed.
2. [OWNER: Coder] Ensure the database is currently at the head revision (`alembic upgrade head`) and generate a new migration file by running:
   `alembic revision --autogenerate -m "add_training_plans_twin_state_fk"`
3. [OWNER: Coder] Verify the generated migration file in `alembic/versions/` contains the `op.create_foreign_key('fk_training_plans_twin_state', 'training_plans', 'twin_states', ['twin_state_id'], ['id'], ondelete='SET NULL')` directive in its `upgrade()` block and the corresponding `op.drop_constraint` in its `downgrade()` block.
4. [OWNER: DevOps] Review and apply the newly generated Alembic revision to the test database.

## Event Contracts
- None (this is a purely structural schema fix).

## Pseudocode
```python
# 1. In app/models/training_plan.py
from sqlalchemy import ForeignKey

class TrainingPlan(Base):
    # ...
    twin_state_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("twin_states.id", ondelete="SET NULL"),
        nullable=True
    )

# 2. Generated via `alembic revision --autogenerate -m "add_training_plans_twin_state_fk"`

# 3. New migration file (e.g. alembic/versions/XXXX_add_training_plans_twin_state_fk.py):
def upgrade() -> None:
    op.create_foreign_key(
        'fk_training_plans_twin_state',
        source_table='training_plans',
        referent_table='twin_states',
        local_cols=['twin_state_id'],
        remote_cols=['id'],
        ondelete='SET NULL'
    )

def downgrade() -> None:
    op.drop_constraint('fk_training_plans_twin_state', 'training_plans', type_='foreignkey')
```

## Testing Requirements
- Running `alembic upgrade head` must successfully apply the new migration and create the `fk_training_plans_twin_state` foreign key constraint on the `training_plans` table pointing to `twin_states.id`.
- Running `alembic downgrade -1` must successfully roll back the new migration and drop the foreign key constraint without errors.
- The Test Architect's Phase-1.2c test pack inspection must pass its FK validation check.

## Coder Handoff Notes
The Test Architect flagged that the database schema was missing the foreign key constraint for `training_plans.twin_state_id`. 

The root cause was that during Phase 1.2b, the `twin_state_id` column was added to the `TrainingPlan` model without the `ForeignKey` directive to avoid coupling to a table that didn't exist yet. The docstring explicitly stated this FK would be added in 1.2c. However, when 1.2c was implemented, the model was never updated, and therefore Alembic autogenerate didn't create the constraint.

**Do not modify the existing `79dc97d4e433` migration file.** Instead, update the SQLAlchemy model and then generate a brand new Alembic migration. Use `ondelete='SET NULL'` to match the nullable definition of the column established in 1.2b.

```
## Coder Scope
Execute:  Steps 1, 2, 3  [OWNER: Coder]
Skip:     Step 4 (DevOps — migration review and application)
```
