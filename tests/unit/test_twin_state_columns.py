"""Unit tests for the ``TwinState`` declarative surface (no DB).

Phase-1.2c introduces the ``TwinState`` schema-only foundation for
the digital twin. These tests pin column presence, nullability, the
append-only contract, the inline-snapshot shape, the JSONB
``metric_confidence`` default, and the partial unique index on
``(athlete_id, activity_id) WHERE activity_id IS NOT NULL``.

Invariants pinned here:

* Append-only — no ``update()`` / ``delete()`` methods on the mapper.
* ``training_goal_id``, ``model_version`` are non-null and frozen
  (the behavioural "no updates" guarantee is enforced by the service
  layer; the schema freezes the columns by NOT NULL).
* ``activity_id`` is nullable (non-activity triggers: questionnaire,
  physiology_input, wellness_update).
* ``metric_confidence`` defaults to ``{}`` JSONB object.
* Index ``uq_twin_states_athlete_activity`` is UNIQUE WHERE
  ``activity_id IS NOT NULL`` — non-activity triggers are exempt.
* Index ``idx_twin_states_latest`` on ``(athlete_id, created_at)``
  supports ``get_latest`` for the home view.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
Architecture: docs/architecture/01-entities/twin-state.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.enums import (
    DataTier,
    RecoveryModifierLevel,
    TwinConfidenceLevel,
    TwinTrigger,
    WellnessTrend,
)
from app.models.twin_state import TwinState
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_check_constraints,
    get_foreign_keys_referencing,
    get_enum_values,
    get_server_default_text,
)


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestTwinStateRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(TwinState)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_required_uuid(self) -> None:
        col = get_columns(TwinState)["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_cascade_fk_to_athletes(self) -> None:
        """Athlete FK ON DELETE CASCADE — twin history is wiped when
        the athlete account is deleted."""
        fks = get_foreign_keys_referencing(TwinState, "athlete_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "athletes"
        assert fk.ondelete == "CASCADE"

    def test_training_goal_id_required_uuid(self) -> None:
        col = get_columns(TwinState)["training_goal_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_training_goal_id_cascade_fk_to_training_goals(self) -> None:
        """TrainingGoal FK ON DELETE CASCADE — twin history is wiped
        when the goal is deleted (rare but possible)."""
        fks = get_foreign_keys_referencing(TwinState, "training_goal_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "training_goals"
        assert fk.ondelete == "CASCADE"

    def test_activity_id_nullable_uuid(self) -> None:
        col = get_columns(TwinState)["activity_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)

    def test_activity_id_set_null_fk_to_activities(self) -> None:
        """Activity FK ON DELETE SET NULL — twin history is
        preserved when an Activity is deleted (history outlives
        the source activity)."""
        fks = get_foreign_keys_referencing(TwinState, "activity_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "activities"
        assert fk.ondelete == "SET NULL"

    def test_data_tier_required_integer(self) -> None:
        """``data_tier`` is stored as INTEGER (the enum value's
        integer is persisted; the ORM column does NOT use SAEnum)."""
        col = get_columns(TwinState)["data_tier"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_confidence_level_required_enum(self) -> None:
        col = get_columns(TwinState)["confidence_level"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, TwinConfidenceLevel))
        assert actual == ["high", "low", "medium"]

    def test_trigger_required_enum(self) -> None:
        col = get_columns(TwinState)["trigger"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, TwinTrigger))
        expected = sorted(
            [
                "activity_sync",
                "calibration",
                "physiology_input",
                "questionnaire",
                "wellness_update",
            ]
        )
        assert actual == expected

    def test_model_version_required_string(self) -> None:
        col = get_columns(TwinState)["model_version"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 32

    def test_created_at_required_datetime(self) -> None:
        col = get_columns(TwinState)["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


class TestTwinStateInlineSnapshotColumns:
    """Fitness / fatigue / form / threshold inline snapshot — the
    historical record that downstream coaching consumers depend on.
    The schema persists these inline so historical TwinState records
    never drift as the operational layer mutates AthleteFitness /
    AthletePhysiology."""

    def test_fitness_required_float(self) -> None:
        col = get_columns(TwinState)["fitness"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    def test_fatigue_required_float(self) -> None:
        col = get_columns(TwinState)["fatigue"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    def test_form_required_float(self) -> None:
        col = get_columns(TwinState)["form"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    @pytest.mark.parametrize(
        "threshold_column",
        [
            "lt1_pace_sec_per_km",
            "lt1_power_watts",
            "lt1_hr_bpm",
            "lt2_pace_sec_per_km",
            "lt2_power_watts",
            "lt2_hr_bpm",
            "cp_watts",
        ],
    )
    def test_threshold_columns_nullable_float(self, threshold_column: str) -> None:
        """All threshold snapshot columns are nullable — null when
        no qualifying signal has been recorded yet."""
        col = get_columns(TwinState)[threshold_column]
        assert col.nullable is True, (
            f"{threshold_column} must be nullable — null when no "
            "signal has been recorded."
        )
        assert isinstance(col.type, Float), (
            f"{threshold_column} must be a Float column."
        )


class TestTwinStateReadinessColumns:
    def test_readiness_level_required_enum(self) -> None:
        col = get_columns(TwinState)["readiness_level"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, RecoveryModifierLevel))
        assert actual == ["amber", "green", "red"]

    def test_wellness_trend_nullable_enum(self) -> None:
        col = get_columns(TwinState)["wellness_trend"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, WellnessTrend))
        assert actual == ["declining", "improving", "stable"]


class TestTwinStateMetricConfidenceJsonb:
    """``metric_confidence`` is a JSONB column with the
    ``TwinState.metric_confidence`` shape (``lt1_hr``, ``lt1_power`` /
    ``lt1_pace``, ``lt2_hr``, ``lt2_power`` / ``lt2_pace``, ``cp``).
    Null fields use JSON ``null``; the default is the empty dict."""

    def test_metric_confidence_required_jsonb(self) -> None:
        col = get_columns(TwinState)["metric_confidence"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_metric_confidence_server_default_empty_dict(self) -> None:
        col = get_columns(TwinState)["metric_confidence"]
        rendered = get_server_default_text(col)
        assert "'{}'::jsonb" in rendered, (
            "metric_confidence.server_default must be `'{}'::jsonb` "
            f"so inserts that omit it still persist a valid empty dict. "
            f"Got: {rendered!r}"
        )


# ---------------------------------------------------------------------------
# Partial unique index on (athlete_id, activity_id) WHERE activity_id IS NOT NULL.
# ---------------------------------------------------------------------------


class TestTwinStatePartialUniqueIndex:
    """The deduplication contract: one TwinState per
    ``(athlete_id, activity_id)`` for activity-linked triggers
    (``activity_sync``, ``calibration``). Non-activity triggers
    (``questionnaire``, ``physiology_input``, ``wellness_update``)
    bypass the partial predicate via NULL ``activity_id``."""

    def test_athlete_activity_partial_unique_index_present(self) -> None:
        indexes = get_indexes(TwinState)
        assert "uq_twin_states_athlete_activity" in indexes, (
            "TwinState must declare `uq_twin_states_athlete_activity` "
            "to enforce one TwinState per (athlete_id, activity_id) "
            "for activity-linked triggers."
        )

    def test_athlete_activity_index_is_unique(self) -> None:
        idx = get_indexes(TwinState)["uq_twin_states_athlete_activity"]
        assert idx.unique is True

    def test_athlete_activity_partial_predicate_present(self) -> None:
        """Without the partial predicate the index would block
        multiple non-activity triggers (questionnaire,
        physiology_input, wellness_update) per athlete."""
        idx = get_indexes(TwinState)["uq_twin_states_athlete_activity"]
        predicate = idx.dialect_options.get("postgresql", {}).get("where")
        assert predicate is not None, (
            "uq_twin_states_athlete_activity must declare a "
            "postgresql_where predicate — without it the index would "
            "block multiple TwinStates per athlete for non-activity triggers."
        )

    def test_athlete_activity_partial_predicate_is_activity_not_null(self) -> None:
        idx = get_indexes(TwinState)["uq_twin_states_athlete_activity"]
        predicate = idx.dialect_options.get("postgresql", {}).get("where")
        rendered = str(predicate).lower()
        assert "activity_id" in rendered and "is not null" in rendered, (
            "uq_twin_states_athlete_activity partial predicate must "
            "constrain `activity_id IS NOT NULL`. "
            f"Got: {predicate!r}"
        )

    def test_athlete_activity_index_columns(self) -> None:
        idx = get_indexes(TwinState)["uq_twin_states_athlete_activity"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id", "activity_id"}


class TestTwinStateSecondaryIndexes:
    """``idx_twin_states_latest`` on ``(athlete_id, created_at)`` is
    the primary read pattern — the ``get_latest`` query for the home
    view."""

    def test_latest_index_present(self) -> None:
        indexes = get_indexes(TwinState)
        assert "idx_twin_states_latest" in indexes, (
            "TwinState must declare `idx_twin_states_latest` on "
            "(athlete_id, created_at) for the get_latest query."
        )

    def test_latest_index_columns(self) -> None:
        idx = get_indexes(TwinState)["idx_twin_states_latest"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id", "created_at"}

    def test_training_goal_lookup_index_present(self) -> None:
        """Reverse lookup from TrainingGoal — supports the
        get_by_training_goal history path."""
        indexes = get_indexes(TwinState)
        assert "ix_twin_states_training_goal" in indexes

    def test_activity_lookup_index_present(self) -> None:
        """Reverse lookup from Activity — supports the
        get_by_activity contract."""
        indexes = get_indexes(TwinState)
        assert "ix_twin_states_activity" in indexes


# ---------------------------------------------------------------------------
# Append-only contract — no update()/delete() helpers on the mapper.
# ---------------------------------------------------------------------------


class TestTwinStateAppendOnlyContract:
    """TwinState is append-only. The model exposes no ``update()`` or
    ``delete()`` methods — the future repository (Phase 1.3) restricts
    to ``insert`` / ``get_latest`` / ``get_by_activity`` / ``get_history``.
    These tests pin the absence of mutation helpers at the mapper
    surface."""

    def test_no_update_helper_methods(self) -> None:
        for attr_name in dir(TwinState):
            if attr_name.startswith("__"):
                continue
            attr = getattr(TwinState, attr_name, None)
            if callable(attr) and attr_name in (
                "update",
                "delete",
                "save",
                "merge",
            ):
                assert False, (
                    f"TwinState must not expose a `{attr_name}` method — "
                    "the table is append-only."
                )

    def test_no_class_level_session_methods(self) -> None:
        """No Session-bound helpers that would mutate rows."""
        for attr_name in ("upsert", "replace", "put", "patch"):
            assert not hasattr(TwinState, attr_name), (
                f"TwinState must not declare a `{attr_name}` method — "
                "append-only contract."
            )


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on TwinState.
# ---------------------------------------------------------------------------


class TestTwinStateSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # Append-only — never expose soft-delete columns.
            "deleted_at",
            "is_deleted",
            # Service-layer concerns — never on the schema.
            "twin_state_id",
            "coach_rationale",
            "llm_input",
            "llm_output",
            "raw_observation",
            # Updated_at — append-only, created_at only.
            "updated_at",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in get_columns(TwinState), (
            f"TwinState must not carry `{forbidden_field}`. The "
            "append-only contract restricts the row shape to the "
            "documented snapshot fields only."
        )