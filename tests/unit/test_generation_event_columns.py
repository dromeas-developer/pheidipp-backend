"""Unit tests for the ``GenerationEvent`` declarative surface (no DB).

Phase-1.2c introduces the ``GenerationEvent`` schema — an append-only
audit log for every LLM API call, successful or failed. The
``LLMInstrumentationService`` (later phase) is the sole writer; rows
are never updated or deleted.

Invariants pinned here:

* Append-only — no ``update()`` / ``delete()`` helpers.
* ``failure_reason IS NOT NULL`` iff ``success = false`` (CHECK).
* Token counts and ``latency_ms`` are non-negative (CHECK).
* ``input_token_count``, ``output_token_count``, ``latency_ms``,
  ``success`` carry server defaults so a failure-before-counts row
  can still be inserted.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
Architecture: docs/architecture/01-entities/generation-event.md
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
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.generation_event import GenerationEvent


def _columns() -> dict[str, object]:
    return {column.key: column for column in GenerationEvent.__table__.columns}


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in GenerationEvent.__table__.indexes}


def _check_constraints() -> list[CheckConstraint]:
    return [
        c
        for c in GenerationEvent.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]


def _foreign_keys_referencing(column_key: str) -> list[ForeignKey]:
    return [
        fk
        for fk in GenerationEvent.__table__.foreign_keys
        if fk.parent.name == column_key
    ]


def _check_text(check: CheckConstraint) -> str:
    """Return the SQL expression text of a CheckConstraint as a string.

    Shared helper across multiple test classes so that each class does
    not have to redefine it. SQLAlchemy exposes the constraint's
    expression via ``.expression`` (modern) or ``.sqltext`` (legacy) —
    this helper accepts either.
    """
    expr = getattr(check, "expression", None) or getattr(
        check, "sqltext", None
    )
    return str(expr) if expr is not None else ""


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestGenerationEventRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_required_uuid(self) -> None:
        col = _columns()["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_cascade_fk_to_athletes(self) -> None:
        """Athlete FK ON DELETE CASCADE — audit rows are wiped when
        the athlete account is deleted."""
        fks = _foreign_keys_referencing("athlete_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "athletes"
        assert fk.ondelete == "CASCADE"

    def test_agent_name_required_string(self) -> None:
        col = _columns()["agent_name"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 96

    def test_prompt_version_required_string(self) -> None:
        col = _columns()["prompt_version"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 32

    def test_trigger_context_required_text(self) -> None:
        col = _columns()["trigger_context"]
        assert col.nullable is False
        assert isinstance(col.type, Text)

    def test_input_token_count_required_integer_with_default(self) -> None:
        col = _columns()["input_token_count"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)
        assert col.server_default is not None
        assert "0" in str(col.server_default.arg)

    def test_output_token_count_required_integer_with_default(self) -> None:
        col = _columns()["output_token_count"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)
        assert col.server_default is not None
        assert "0" in str(col.server_default.arg)

    def test_latency_ms_required_integer_with_default(self) -> None:
        col = _columns()["latency_ms"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)
        assert col.server_default is not None
        assert "0" in str(col.server_default.arg)

    def test_success_required_boolean_with_default(self) -> None:
        col = _columns()["success"]
        assert col.nullable is False
        assert isinstance(col.type, Boolean)
        assert col.server_default is not None

    def test_failure_reason_nullable_text(self) -> None:
        """``failure_reason`` is NULL on success rows, non-NULL on
        failure rows. CHECK constraint enforces consistency."""
        col = _columns()["failure_reason"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_created_at_required_datetime(self) -> None:
        col = _columns()["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


# ---------------------------------------------------------------------------
# CHECK constraints — failure_reason consistency + token / latency non-negative.
# ---------------------------------------------------------------------------


class TestGenerationEventFailureReasonConsistencyCheck:
    """The architectural invariant: ``failure_reason IS NOT NULL``
    when ``success = false``, and ``failure_reason IS NULL`` when
    ``success = true``. The CHECK constraint enforces consistency
    at the DB layer so a buggy instrumentation adapter cannot insert
    a contradictory row."""

    def test_failure_reason_consistency_check_present(self) -> None:
        checks = _check_constraints()
        found = any(
            "failure_reason" in _check_text(c)
            and "success" in _check_text(c)
            and "IS NULL" in _check_text(c).upper()
            and "IS NOT NULL" in _check_text(c).upper()
            for c in checks
        )
        assert found, (
            "GenerationEvent must declare a CHECK constraint "
            "enforcing `failure_reason IS NOT NULL iff success = false`."
        )


class TestGenerationEventNonNegativeCheck:
    """``input_token_count``, ``output_token_count``, and
    ``latency_ms`` must all be non-negative."""

    def test_token_counts_non_negative_check_present(self) -> None:
        checks = _check_constraints()
        found = any(
            "input_token_count" in _check_text(c)
            and "output_token_count" in _check_text(c)
            and ">=" in _check_text(c)
            for c in checks
        )
        assert found, (
            "GenerationEvent must declare a CHECK constraint "
            "bounding input/output token counts to >= 0."
        )

    def test_latency_non_negative_check_present(self) -> None:
        checks = _check_constraints()
        found = any(
            "latency_ms" in _check_text(c)
            and ">=" in _check_text(c)
            for c in checks
        )
        assert found, (
            "GenerationEvent must declare a CHECK constraint "
            "bounding latency_ms to >= 0."
        )


# ---------------------------------------------------------------------------
# Read-pattern indexes.
# ---------------------------------------------------------------------------


class TestGenerationEventReadIndexes:
    """Three read patterns are pinned at the schema layer:

* Per-athlete audit → ``(athlete_id, created_at)``
* Per-agent monitoring → ``(agent_name, created_at)``
* Failure dashboards → ``(success, created_at)``
"""

    def test_athlete_audit_index_present(self) -> None:
        indexes = _indexes()
        assert "ix_generation_events_athlete_at" in indexes
        idx = indexes["ix_generation_events_athlete_at"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id", "created_at"}

    def test_agent_monitoring_index_present(self) -> None:
        indexes = _indexes()
        assert "ix_generation_events_agent_at" in indexes
        idx = indexes["ix_generation_events_agent_at"]
        columns = {c.key for c in idx.columns}
        assert columns == {"agent_name", "created_at"}

    def test_failure_dashboard_index_present(self) -> None:
        indexes = _indexes()
        assert "ix_generation_events_success_at" in indexes
        idx = indexes["ix_generation_events_success_at"]
        columns = {c.key for c in idx.columns}
        assert columns == {"success", "created_at"}


# ---------------------------------------------------------------------------
# Append-only contract — no update()/delete() helpers on the mapper.
# ---------------------------------------------------------------------------


class TestGenerationEventAppendOnlyContract:
    """GenerationEvent is append-only — the audit log never mutates.
    The model exposes no ``update()`` or ``delete()`` methods."""

    def test_no_update_helper_methods(self) -> None:
        for attr_name in dir(GenerationEvent):
            if attr_name.startswith("__"):
                continue
            attr = getattr(GenerationEvent, attr_name, None)
            if callable(attr) and attr_name in (
                "update",
                "delete",
                "save",
                "merge",
                "upsert",
                "replace",
                "put",
                "patch",
            ):
                assert False, (
                    f"GenerationEvent must not expose a `{attr_name}` "
                    "method — the audit log is append-only."
                )

    def test_no_updated_at_column(self) -> None:
        """Append-only contract: ``updated_at`` would imply a
        mutation semantic the schema must not permit."""
        assert "updated_at" not in _columns(), (
            "GenerationEvent must not carry an `updated_at` column — "
            "audit rows are immutable after insert."
        )


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on GenerationEvent.
# ---------------------------------------------------------------------------


class TestGenerationEventSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # Soft-delete / mutation columns.
            "deleted_at",
            "is_deleted",
            "updated_at",
            # Coaching message fields — separate entity.
            "message_type",
            "content",
            "twin_state_id",
            "activity_id",
            "generated_at",
            "prompt_version_text",
            # Twin / fitness fields.
            "twin_state",
            "fitness_score",
            "fatigue_score",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _columns(), (
            f"GenerationEvent must not carry `{forbidden_field}`. "
            "The audit log row shape is restricted to "
            "agent_name / prompt_version / trigger_context / "
            "token counts / latency / success / failure_reason."
        )