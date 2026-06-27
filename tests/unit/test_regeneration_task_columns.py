"""Unit tests for the ``RegenerationTask`` declarative surface (no DB).

Phase-1.2b adds ``RegenerationTask`` as the supporting storage for a
coach-proposed date change against a ``TrainingGoal``. Lifetime is
short (≤ 14 days); the unit tests pin column presence, nullability,
the FK to ``training_goals``, the nullable FK to ``training_plans``,
the inline-status CHECK, and the partial pending-proposal index.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
Architecture: docs/architecture/01-entities/training-goal.md (RegenerationTask section)
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    Date,
    DateTime,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.regeneration_task import RegenerationTask
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_check_constraints,
    get_check_text,
    get_foreign_keys_referencing,
)


class TestRegenerationTaskRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(RegenerationTask)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_training_goal_id_required_uuid(self) -> None:
        col = get_columns(RegenerationTask)["training_goal_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_training_plan_id_nullable_uuid(self) -> None:
        """``training_plan_id`` is nullable: it points to the new
        plan created when the task is confirmed; for
        pending / declined / expired rows it stays null."""
        col = get_columns(RegenerationTask)["training_plan_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)

    def test_proposed_date_required_date(self) -> None:
        col = get_columns(RegenerationTask)["proposed_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_rationale_required_text(self) -> None:
        col = get_columns(RegenerationTask)["rationale"]
        assert col.nullable is False
        assert isinstance(col.type, Text)

    def test_trigger_required_text(self) -> None:
        """``trigger`` is a free-text inline-union column with a CHECK
        constraint enforcing membership in the closed vocabulary
        {trajectory_ahead | trajectory_at_risk | coach_conversation}.
        At the ORM layer it is just a Text column."""
        col = get_columns(RegenerationTask)["trigger"]
        assert col.nullable is False
        assert isinstance(col.type, Text)

    def test_status_required_text_with_check(self) -> None:
        col = get_columns(RegenerationTask)["status"]
        assert col.nullable is False
        assert isinstance(col.type, Text)

    def test_proposed_at_required_datetime(self) -> None:
        col = get_columns(RegenerationTask)["proposed_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_decided_at_nullable_datetime(self) -> None:
        col = get_columns(RegenerationTask)["decided_at"]
        assert col.nullable is True
        assert isinstance(col.type, DateTime)

    def test_expires_at_required_datetime(self) -> None:
        col = get_columns(RegenerationTask)["expires_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


class TestRegenerationTaskForeignKeys:
    def test_training_goal_id_has_fk_to_training_goals(self) -> None:
        foreign_keys = get_foreign_keys_referencing(RegenerationTask, "training_goal_id")
        assert foreign_keys, (
            "RegenerationTask.training_goal_id must declare an FK to "
            "training_goals.id."
        )
        for fk in foreign_keys:
            assert fk.column.table.name == "training_goals"

    def test_training_plan_id_has_fk_to_training_plans(self) -> None:
        """``training_plan_id`` is nullable but carries an FK — it is
        the FK for ``training_plans.id``."""
        foreign_keys = get_foreign_keys_referencing(RegenerationTask, "training_plan_id")
        assert foreign_keys, (
            "RegenerationTask.training_plan_id must declare an FK to "
            "training_plans.id (nullable)."
        )
        for fk in foreign_keys:
            assert fk.column.table.name == "training_plans"


class TestRegenerationTaskCheckConstraints:
    def test_status_inline_union_check(self) -> None:
        text = " | ".join(
            get_check_text(c) for c in get_check_constraints(RegenerationTask)
        ).lower()
        for status_value in (
            "pending_confirmation",
            "confirmed",
            "declined",
            "expired",
        ):
            assert status_value in text, (
                f"RegenerationTask.status check must include "
                f"`{status_value}`. Found check texts: {text!r}"
            )


class TestRegenerationTaskPendingPartialIndex:
    """Partial index on pending proposals per goal supports the
    "Stagnant Proposals" alert query path."""

    def test_pending_partial_index_present(self) -> None:
        indexes = get_indexes(RegenerationTask)
        assert "ix_regeneration_tasks_pending" in indexes, (
            "RegenerationTask must declare "
            "`ix_regeneration_tasks_pending` partial index."
        )
        idx = indexes["ix_regeneration_tasks_pending"]
        columns = {c.key for c in idx.columns}
        assert columns == {"training_goal_id", "status"}

    def test_pending_partial_predicate_is_status_pending_confirmation(self) -> None:
        idx = get_indexes(RegenerationTask)["ix_regeneration_tasks_pending"]
        predicate = idx.dialect_options.get("postgresql", {}).get("where")
        assert predicate is not None, (
            "ix_regeneration_tasks_pending must declare a "
            "postgresql_where predicate."
        )
        rendered = str(predicate).lower()
        assert "status" in rendered and "pending_confirmation" in rendered, (
            "ix_regeneration_tasks_pending partial predicate must "
            "constrain status = 'pending_confirmation'. "
            f"Got: {predicate!r}"
        )


class TestRegenerationTaskSchemaAntiGoals:
    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # Schema-only — no coaching UI fields.
            "athlete_notes",
            "coach_notes",
            # No event-publication columns: schema-only plan emits no
            # events.
            "event_id",
            "published_at",
            # No approval coordinates — the lifecycle is the athlete
            # decision, not a multi-party approval.
            "approved_by",
            "approved_at",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in get_columns(RegenerationTask), (
            f"RegenerationTask must not carry `{forbidden_field}`. "
            "Schema-only, event-less, no approval workflow."
        )
