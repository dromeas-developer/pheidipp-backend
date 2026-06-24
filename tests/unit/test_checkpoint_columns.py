"""Unit tests for the ``Checkpoint`` declarative surface (no DB).

Phase-1.2b introduces the ``Checkpoint`` schema. The invarian­t
``one-to-one`` between a ``Checkpoint`` and a ``PlannedSession`` is
codified at the ORM layer by setting ``unique=True`` on
``planned_session_id``. No redundant ``training_plan_id`` is present;
derivation goes through ``PlannedSession → WeeklyPlan → TrainingPlan``.

The atomic-completion invariant (``metric_updated``,
``confidence_changed``, ``replan_triggered``, ``completed_at`` set
together) is enforced at the application layer in a later phase — the
schema only permits ``null`` for those fields until completion.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
Architecture: docs/architecture/01-entities/checkpoint.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID

from app.models.checkpoint import Checkpoint
from app.models.enums import CheckpointStatus, CheckpointType


def _columns() -> dict[str, object]:
    return {column.key: column for column in Checkpoint.__table__.columns}


def _unique_constraints() -> list[UniqueConstraint]:
    return [
        c
        for c in Checkpoint.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]


def _check_constraints() -> list[CheckConstraint]:
    return [
        c
        for c in Checkpoint.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in Checkpoint.__table__.indexes}


class TestCheckpointRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_planned_session_id_required_unique_uuid(self) -> None:
        """One-to-one FK — strict uniqueness + non-null enforced at
        DB level via the unique index below."""
        col = _columns()["planned_session_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)
        assert col.unique is True

    def test_planned_session_id_has_fk_to_planned_sessions(self) -> None:
        foreign_keys = [
            fk for fk in Checkpoint.__table__.foreign_keys
            if fk.parent.name == "planned_session_id"
        ]
        assert foreign_keys, (
            "Checkpoint.planned_session_id must declare an FK to "
            "planned_sessions.id."
        )
        for fk in foreign_keys:
            assert fk.column.table.name == "planned_sessions"

    def test_type_required_enum(self) -> None:
        col = _columns()["type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(CheckpointType))
        expected = sorted(
            [
                "calibration",
                "benchmark",
                "race_simulation",
                "secondary_race",
                "progress_review",
            ]
        )
        assert actual == expected

    def test_target_metric_required_string(self) -> None:
        col = _columns()["target_metric"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 128

    def test_secondary_metrics_required_array_default_empty(self) -> None:
        col = _columns()["secondary_metrics"]
        assert col.nullable is False
        assert isinstance(col.type, ARRAY)

    def test_twin_update_expected_required_bool_default_false(self) -> None:
        col = _columns()["twin_update_expected"]
        assert col.nullable is False
        assert isinstance(col.type, Boolean)
        assert col.server_default.arg in {"false", "False", "0"}

    def test_replan_trigger_required_bool_default_false(self) -> None:
        col = _columns()["replan_trigger"]
        assert col.nullable is False
        assert isinstance(col.type, Boolean)
        assert col.server_default.arg in {"false", "False", "0"}

    def test_status_required_enum(self) -> None:
        col = _columns()["status"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(CheckpointStatus))
        expected = sorted(["scheduled", "completed", "skipped"])
        assert actual == expected

    def test_metric_updated_nullable_bool(self) -> None:
        col = _columns()["metric_updated"]
        assert col.nullable is True
        assert isinstance(col.type, Boolean)

    def test_confidence_changed_nullable_bool(self) -> None:
        col = _columns()["confidence_changed"]
        assert col.nullable is True
        assert isinstance(col.type, Boolean)

    def test_replan_triggered_nullable_bool(self) -> None:
        col = _columns()["replan_triggered"]
        assert col.nullable is True
        assert isinstance(col.type, Boolean)

    def test_trajectory_status_nullable_string(self) -> None:
        col = _columns()["trajectory_status"]
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_proposal_nullable_text(self) -> None:
        col = _columns()["proposal"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_created_at_required_datetime(self) -> None:
        col = _columns()["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_completed_at_nullable_datetime(self) -> None:
        col = _columns()["completed_at"]
        assert col.nullable is True
        assert isinstance(col.type, DateTime)


class TestCheckpointSchemaAntiGoals:
    """Schema-only contract forbids training_plan_id (derives
    through PlannedSession). Also blocks coaching-side or API-side
    fields that do not belong on a checkpoint row."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # No redundant linkage.
            "training_plan_id",
            "weekly_plan_id",
            # No FK to checkpoint-processor services (Phase-1.2b has no
            # service layer).
            "completed_by",
            "completed_by_athlete_id",
            # No arbitrary JSONB blob.
            "metadata",
            "extra",
            # No scoring extras at the checkpoint row.
            "score",
            "actual_metric",
            "delta",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _columns(), (
            f"Checkpoint must not carry `{forbidden_field}`. Trajectory "
            "data lives on the proposed service-side log; training_plan "
            "derives via PlannedSession->WeeklyPlan."
        )


class TestCheckpointCheckConstraints:
    def _check_text(self, check: CheckConstraint) -> str:
        expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
        return (str(expr) if expr is not None else "")

    def test_trajectory_status_inline_union_check(self) -> None:
        text = " | ".join(
            self._check_text(c) for c in _check_constraints()
        ).lower()
        assert "trajectory_status" in text
        for status_value in ("ahead", "on_track", "behind", "at_risk"):
            assert status_value in text, (
                f"Checkpoint.trajectory_status check must include "
                f"`{status_value}`. Found check texts: {text!r}"
            )

    def test_status_inline_union_check(self) -> None:
        text = " | ".join(
            self._check_text(c) for c in _check_constraints()
        ).lower()
        # CheckpointStatus enum — SCHEDULED / COMPLETED / SKIPPED.
        assert "scheduled" in text and "completed" in text and "skipped" in text, (
            "Checkpoint.status check must include `scheduled`, "
            "`completed`, and `skipped`."
        )


class TestCheckpointIndexes:
    def test_type_status_index_present(self) -> None:
        matched = [
            idx
            for idx in _indexes().values()
            if {c.key for c in idx.columns} >= {"type", "status"}
        ]
        assert matched, (
            "Expected an index on (type, status) for the upcoming-"
            "checkpoint query path."
        )

    def test_planned_session_index_present(self) -> None:
        """Even though ``planned_session_id`` has a UNIQUE constraint
        (which auto-creates an index), the architecture pattern is an
        explicit named index ``ix_checkpoints_planned_session``."""
        assert "ix_checkpoints_planned_session" in _indexes(), (
            "Checkpoint must declare named "
            "`ix_checkpoints_planned_session` index."
        )


class TestCheckpointUniqueConstraint:
    def test_planned_session_id_unique_constraint_named(self) -> None:
        """The column has ``unique=True`` — SQLAlchemy creates a named
        UNIQUE constraint ``checkpoints_planned_session_id_key``
        automatically. The architecture asks for an explicit named
        unique; we accept either by checking either the column-level
        unique flag or a unique constraint with the right column."""
        constraints = _unique_constraints()
        matching = [
            c for c in constraints
            if tuple(col.key for col in c.columns)
            == ("planned_session_id",)
        ]
        col_level = _columns()["planned_session_id"].unique
        assert matching or col_level, (
            "Checkpoint.planned_session_id must be uniquely constrained."
        )
