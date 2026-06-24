"""Unit tests for the ``PlannedSession`` declarative surface (no DB).

Phase-1.2b introduces the ``PlannedSession`` schema. The unit tests
pin column presence, nullability, the uniqueness contract on
``(weekly_plan_id, target_date, session_slot)``, the inline-union
CHECK constraints used to bound the slot / priority / block vocabularies,
and the FK to ``activities`` via the ``activity_id`` linkage column
(no DB-level FK declared in Phase-1.2b — the activity FK lands in a
later migration once the activity contract is settled).

Invariants pinned here:

* ``activity_id`` is a free-standing nullable UUID (no FK on the
  mapper yet — service layer owns that cross-table invariant).
* ``session_slot`` is nullable for single-session days and pairs with
  ``SessionSlot`` enum on double sessions.
* ``(weekly_plan_id, target_date, session_slot)`` is unique.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
Architecture: docs/architecture/01-entities/planned-session.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.enums import (
    CheckpointType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionSlot,
    SessionType,
)
from app.models.planned_session import PlannedSession


def _columns() -> dict[str, object]:
    return {column.key: column for column in PlannedSession.__table__.columns}


def _unique_constraints() -> list[UniqueConstraint]:
    return [
        c
        for c in PlannedSession.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]


def _check_constraints() -> list[CheckConstraint]:
    return [
        c
        for c in PlannedSession.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in PlannedSession.__table__.indexes}


def _foreign_keys_referencing(column_key: str) -> list[ForeignKey]:
    """Return the list of ``ForeignKey`` objects declared for the
    given column key. Useful when an ORM column maps multiple FKs
    (rare, but defensive against regressions)."""
    return [fk for fk in PlannedSession.__table__.foreign_keys if fk.parent.name == column_key]


class TestPlannedSessionRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_weekly_plan_id_required_uuid(self) -> None:
        col = _columns()["weekly_plan_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_training_plan_id_required_uuid_denormalized(self) -> None:
        """``training_plan_id`` is DENORMALISED — the source of truth
        remains ``WeeklyPlan.training_plan_id``. The denorm survives
        plan supersession; correct queries join through WeeklyPlan."""
        col = _columns()["training_plan_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_target_date_required_date(self) -> None:
        col = _columns()["target_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_week_number_required_integer(self) -> None:
        col = _columns()["week_number"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_phase_label_required_enum(self) -> None:
        col = _columns()["phase_label"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = set(col.type.values_callable(PhaseLabel))
        # All PhaseLabel members must appear at the DB layer.
        assert len(actual) == len(list(PhaseLabel))

    def test_session_type_required_enum(self) -> None:
        col = _columns()["session_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(SessionType))
        expected = sorted(
            [
                "rest",
                "recovery_run",
                "easy_run",
                "long_run",
                "medium_long_run",
                "steady_state",
                "tempo",
                "threshold",
                "vo2max",
                "hill_repeats",
                "fartlek",
                "strides",
                "drills_mobility",
                "cross_training",
                "test_session",
                "optional_run",
            ]
        )
        assert actual == expected

    def test_intent_description_required_string(self) -> None:
        col = _columns()["intent_description"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 512

    def test_approximate_duration_minutes_required_integer(self) -> None:
        col = _columns()["approximate_duration_minutes"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_checkpoint_type_nullable_enum(self) -> None:
        col = _columns()["checkpoint_type"]
        assert col.nullable is True
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

    def test_checkpoint_metric_nullable_string(self) -> None:
        col = _columns()["checkpoint_metric"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 128

    def test_status_required_enum(self) -> None:
        col = _columns()["status"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(PlannedSessionStatus))
        expected = sorted(
            [
                "pending",
                "generated",
                "completed",
                "skipped",
                "missed",
                "redistributed",
            ]
        )
        assert actual == expected

    def test_skip_reason_nullable_text(self) -> None:
        col = _columns()["skip_reason"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_redistributed_to_date_nullable_date(self) -> None:
        col = _columns()["redistributed_to_date"]
        assert col.nullable is True
        assert isinstance(col.type, Date)

    def test_activity_id_nullable_uuid_no_fk(self) -> None:
        """``activity_id`` is a free-standing nullable UUID in
        Phase-1.2b — no FK declared on the mapper because the
        service-layer ``session_completed`` consumer is still
        unshipped. The FK lands in a future migration once the
        activity contract is settled."""
        col = _columns()["activity_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)
        # No mapper-level FK declared to ``activities``.
        for fk in PlannedSession.__table__.foreign_keys:
            if fk.column.table.name == "activities":
                pytest.fail(
                    "planned_sessions.activity_id must NOT carry an "
                    "FK to activities in Phase-1.2b — the activity "
                    "service layer is unshipped."
                )

    def test_session_slot_nullable_enum(self) -> None:
        """``session_slot`` is nullable for single-session days."""
        col = _columns()["session_slot"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(SessionSlot))
        assert actual == ["am", "pm"]

    def test_session_priority_required_enum(self) -> None:
        col = _columns()["session_priority"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(SessionPriority))
        assert actual == ["primary", "secondary"]

    def test_block_id_nullable_string(self) -> None:
        col = _columns()["block_id"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 64

    def test_block_position_nullable_string(self) -> None:
        col = _columns()["block_position"]
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_block_session_count_nullable_integer(self) -> None:
        col = _columns()["block_session_count"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)

    def test_is_suggested_required_bool_default_false(self) -> None:
        col = _columns()["is_suggested"]
        assert col.nullable is False
        assert isinstance(col.type, Boolean)
        assert col.server_default.arg in {"false", "False", "0"}

    def test_created_at_required_datetime(self) -> None:
        col = _columns()["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


class TestPlannedSessionSlotDateUniqueConstraint:
    """``(weekly_plan_id, target_date, session_slot)`` is unique — the
    AM/PM disambiguation contract."""

    def test_plan_date_slot_unique_constraint_present(self) -> None:
        constraints = _unique_constraints()
        matching = [
            c
            for c in constraints
            if tuple(col.key for col in c.columns) == (
                "weekly_plan_id",
                "target_date",
                "session_slot",
            )
            and c.name == "uq_planned_sessions_plan_date_slot"
        ]
        assert matching, (
            "PlannedSession must declare UNIQUE "
            "(weekly_plan_id, target_date, session_slot) — the AM/PM "
            "disambiguation contract."
        )


class TestPlannedSessionCheckConstraints:
    def _check_text(self, check: CheckConstraint) -> str:
        expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
        return (str(expr) if expr is not None else "")

    def test_block_position_inline_union_check(self) -> None:
        text = " | ".join(
            self._check_text(c) for c in _check_constraints()
        ).lower()
        assert "block_position" in text
        for pos in ("first", "middle", "last"):
            assert pos in text, (
                f"PlannedSession.block_position check must include "
                f"`{pos}`. Found check texts: {text!r}"
            )

    def test_duration_positive_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "approximate_duration_minutes" in self._check_text(c)
            and ">" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "PlannedSession must declare a CHECK constraint "
            "`approximate_duration_minutes > 0`."
        )

    def test_week_number_positive_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "week_number" in self._check_text(c)
            and ">=" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "PlannedSession must declare a CHECK constraint "
            "`week_number >= 1`."
        )


class TestPlannedSessionIndexes:
    """Indexes support weekly-plan date lookup, the current-plan
    query path (training_plan_id + date + slot), and upstream
    status-of-session queries."""

    def test_plan_date_index_present(self) -> None:
        matched = [
            idx
            for idx in _indexes().values()
            if {c.key for c in idx.columns} >= {
                "weekly_plan_id",
                "target_date",
            }
        ]
        assert matched, (
            "Expected an index on (weekly_plan_id, target_date) for "
            "weekly-schedule lookup."
        )

    def test_training_plan_date_slot_index_present(self) -> None:
        """``(training_plan_id, target_date, session_slot)`` supports
        per-twin / per-calendar-window lookups using the
        denormalised FK."""
        matched = [
            idx
            for idx in _indexes().values()
            if {c.key for c in idx.columns} >= {
                "training_plan_id",
                "target_date",
                "session_slot",
            }
        ]
        assert matched, (
            "Expected an index on "
            "(training_plan_id, target_date, session_slot) for "
            "reverse lookup via the denormalised FK."
        )

    def test_status_date_index_present(self) -> None:
        matched = [
            idx
            for idx in _indexes().values()
            if {c.key for c in idx.columns} >= {"status", "target_date"}
        ]
        assert matched, (
            "Expected an index on (status, target_date) for the "
            "missed-session sweep query path."
        )


class TestPlannedSessionSchemaAntiGoals:
    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # No FIT-linkage columns; the activity owns its own file key.
            "fit_file_key",
            # No scheduled-vs-completed-since columns at the session
            # level (those are derived from ``status``).
            "completed_at",
            # No aggregate load scores (live on Activity).
            "aerobic_load",
            "neuromuscular_load",
            "structural_load",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _columns(), (
            f"PlannedSession must not carry `{forbidden_field}`."
        )
