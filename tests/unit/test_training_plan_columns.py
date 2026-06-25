"""Unit tests for the ``TrainingPlan`` declarative surface (no DB).

Phase-1.2b introduces the ``TrainingPlan`` schema-only foundation. The
Plan carries the plan-generation output (phases, weekly distributions,
checkpoint_schedule, strategic_rationale) as JSONB so the synthesis
service can land later without DB migration churn.

Invariants pinned here:

* ``twin_state_id`` is present, nullable UUID, and the FK to
  ``twin_states.id`` is declared ``ON DELETE SET NULL``. The column
  was added in Phase-1.2b without a constraint; the FK was wired in
  Phase-1.2c once ``twin_states`` existed.
* JSONB structural columns are non-nullable with a sensible default
  (empty list / null dict) so plan-synthesis can ``jsonb_set`` over
  them without an INSERT-side coalesce.
* Lifecycle is non-destructive: ``superseded_at`` records the moment
  the plan is replaced.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
Architecture: docs/architecture/01-entities/training-plan.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.enums import TrainingPlanStatus
from app.models.training_plan import TrainingPlan


def _columns() -> dict[str, object]:
    return {column.key: column for column in TrainingPlan.__table__.columns}


def _indexes() -> dict[str, "object"]:
    return {idx.name: idx for idx in TrainingPlan.__table__.indexes}


class TestTrainingPlanRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        cols = _columns()
        assert "id" in cols
        assert cols["id"].primary_key is True
        assert isinstance(cols["id"].type, PG_UUID)

    def test_training_goal_id_required_uuid(self) -> None:
        col = _columns()["training_goal_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_twin_state_id_nullable_uuid_with_set_null_fk(self) -> None:
        """``twin_state_id`` is a nullable UUID column with an FK to
        ``twin_states.id`` declared ``ON DELETE SET NULL``.

        Phase-1.2b added the column without an FK; Phase-1.2c wired
        the FK once ``twin_states`` existed. Orphaning a twin state
        must not cascade-delete the plan — the SET NULL semantics
        match the column's nullability and the architecture contract.
        """
        col = _columns()["twin_state_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)
        # Exactly one FK points at ``twin_states.id`` and it must be
        # declared SET NULL — the cascade-delete invariant is
        # explicitly NOT allowed on this FK.
        twin_fks = [
            fk
            for fk in TrainingPlan.__table__.foreign_keys
            if fk.column.table.name == "twin_states"
        ]
        assert len(twin_fks) == 1, (
            "training_plans.twin_state_id must carry exactly one FK "
            "to twin_states (wired in Phase-1.2c). "
            f"Got {len(twin_fks)}."
        )
        assert twin_fks[0].ondelete == "SET NULL", (
            "training_plans.twin_state_id FK must ON DELETE SET NULL "
            "— orphaning a twin state must NOT cascade-delete the plan."
        )

    def test_phases_summary_required_jsonb_with_default(self) -> None:
        col = _columns()["phases_summary"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_phase_definitions_required_jsonb_with_default(self) -> None:
        col = _columns()["phase_definitions"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_weekly_distributions_required_jsonb_with_default(self) -> None:
        col = _columns()["weekly_distributions"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_status_required_enum(self) -> None:
        col = _columns()["status"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(TrainingPlanStatus))
        assert actual == ["active", "completed", "superseded"]

    def test_superseded_at_nullable_datetime(self) -> None:
        col = _columns()["superseded_at"]
        assert col.nullable is True
        assert isinstance(col.type, DateTime)

    def test_created_at_required_datetime(self) -> None:
        col = _columns()["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_strategic_rationale_nullable_jsonb(self) -> None:
        """Strategic rationale is null for fitness_improvement /
        maintenance / recovery modes — null allowed at the DB layer."""
        col = _columns()["strategic_rationale"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_checkpoint_schedule_required_jsonb(self) -> None:
        col = _columns()["checkpoint_schedule"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)


class TestTrainingPlanIndexes:
    def test_goal_status_index_present(self) -> None:
        """Active / superseded lookup — find the current plan for a goal."""
        matched = [
            idx
            for idx in _indexes().values()
            if {c.key for c in idx.columns} >= {
                "training_goal_id",
                "status",
            }
        ]
        assert matched, (
            "Expected an index on (training_goal_id, status) for the "
            "current-plan lookup."
        )

    def test_twin_state_index_present(self) -> None:
        """Reverse-lookup TwinState → plans uses the FK target.
        Indexed for the production query path."""
        matched = [
            idx
            for idx in _indexes().values()
            if {c.key for c in idx.columns} >= {"twin_state_id"}
        ]
        assert matched, (
            "Expected an index on (twin_state_id) for "
            "reverse-lookup TwinState → plans."
        )


class TestTrainingPlanSchemaAntiGoals:
    """Tripwires: columns that would silently break the schema-only
    plan or the non-destructive supersession invariant."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # No deletion marker — plans are never deleted.
            "deleted_at",
            "is_deleted",
            # No plan-generation-input fields (those live on TrainingGoal).
            "athlete_id",
            "weekly_volume_hours",
            "weekly_volume_km",
            "fitness_level",
            # No API-side coarse flags driven by services that do not
            # exist yet (own nothing in Phase-1.2b).
            "is_current",
            "owned_by_coach",
            "approval_state",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _columns(), (
            f"TrainingPlan must not carry `{forbidden_field}`. The "
            "schema-only contract forbids it."
        )
