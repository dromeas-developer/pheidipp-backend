"""Unit tests for the ``PhysiologyMeasurement`` declarative surface (no DB).

Phase-2.3-P1 introduces the ``PhysiologyMeasurement`` schema — an
append-only observation history table that ``ThresholdDetectionService``
appends to and that ``PhysiologyUpdateService`` (Phase 2.3-P2) reads
to update the per-athlete ``AthletePhysiology`` posterior state.

Invariants pinned here:

* Append-only — no UPDATE/DELETE methods on the repository.
* ``activity_id`` is nullable with ``ON DELETE SET NULL`` — lab/field
  test measurements are recorded without an associated Activity.
* ``parameter`` and ``source`` are stored as non-native ``String``
  enums (``native_enum=False``).
* ``algorithm_used`` and ``confidence_weight`` are nullable — manual
  entries have no algorithm.
* Indexes: ``(athlete_id, measurement_date)`` for history queries,
  ``(athlete_id, parameter, source)`` for dedup lookup.

Reference plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import Date, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.physiology_measurement import PhysiologyMeasurement
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_foreign_keys_referencing,
    get_server_default_text,
)


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestPhysiologyMeasurementRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(PhysiologyMeasurement)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_required_uuid(self) -> None:
        col = get_columns(PhysiologyMeasurement)["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_cascade_fk_to_athletes(self) -> None:
        """Athlete FK ON DELETE CASCADE — physiology rows are wiped
        when the athlete account is deleted."""
        fks = get_foreign_keys_referencing(
            PhysiologyMeasurement, "athlete_id"
        )
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "athletes"
        assert fk.ondelete == "CASCADE"

    def test_activity_id_nullable_uuid(self) -> None:
        """``activity_id`` is nullable — lab/field test measurements
        are recorded without an associated Activity."""
        col = get_columns(PhysiologyMeasurement)["activity_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)

    def test_activity_id_set_null_fk_to_activities(self) -> None:
        """Activity FK ON DELETE SET NULL — deleting an activity
        preserves the historical observation record."""
        fks = get_foreign_keys_referencing(
            PhysiologyMeasurement, "activity_id"
        )
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "activities"
        assert fk.ondelete == "SET NULL"

    def test_parameter_required_string_enum(self) -> None:
        """``parameter`` is NOT NULL — stored as non-native String enum."""
        col = get_columns(PhysiologyMeasurement)["parameter"]
        assert col.nullable is False
        # Non-native enum is stored as String.
        assert isinstance(col.type, String)

    def test_observed_value_required_float(self) -> None:
        col = get_columns(PhysiologyMeasurement)["observed_value"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    def test_source_required_string_enum(self) -> None:
        """``source`` is NOT NULL — stored as non-native String enum."""
        col = get_columns(PhysiologyMeasurement)["source"]
        assert col.nullable is False
        assert isinstance(col.type, String)

    def test_measurement_date_required_date(self) -> None:
        col = get_columns(PhysiologyMeasurement)["measurement_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_algorithm_used_nullable_string(self) -> None:
        """``algorithm_used`` is nullable — manual entries have no algorithm."""
        col = get_columns(PhysiologyMeasurement)["algorithm_used"]
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_confidence_weight_nullable_float(self) -> None:
        """``confidence_weight`` is nullable — manual entries omit it."""
        col = get_columns(PhysiologyMeasurement)["confidence_weight"]
        assert col.nullable is True
        assert isinstance(col.type, Float)

    def test_raw_data_reference_nullable_string(self) -> None:
        col = get_columns(PhysiologyMeasurement)["raw_data_reference"]
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_notes_nullable_text(self) -> None:
        col = get_columns(PhysiologyMeasurement)["notes"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_created_at_required_datetime(self) -> None:
        col = get_columns(PhysiologyMeasurement)["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_created_at_has_server_default_now(self) -> None:
        """``created_at`` server_default is ``now()`` so inserts
        without an explicit value still produce a usable timestamp."""
        col = get_columns(PhysiologyMeasurement)["created_at"]
        assert col.server_default is not None
        assert "now" in get_server_default_text(col).lower()


# ---------------------------------------------------------------------------
# Indexes — history queries and dedup lookup.
# ---------------------------------------------------------------------------


class TestPhysiologyMeasurementIndexes:
    """Two indexes support the two primary query patterns:

    * ``ix_physiology_measurements_athlete_date`` — history queries
      (newest first per athlete).
    * ``ix_physiology_measurements_athlete_parameter_source`` — dedup
      lookup (find prior observations for the same tuple).
    """

    def test_athlete_date_index_present(self) -> None:
        indexes = get_indexes(PhysiologyMeasurement)
        assert "ix_physiology_measurements_athlete_date" in indexes

    def test_athlete_date_index_columns(self) -> None:
        idx = get_indexes(PhysiologyMeasurement)[
            "ix_physiology_measurements_athlete_date"
        ]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id", "measurement_date"}

    def test_athlete_parameter_source_index_present(self) -> None:
        indexes = get_indexes(PhysiologyMeasurement)
        assert (
            "ix_physiology_measurements_athlete_parameter_source"
            in indexes
        )

    def test_athlete_parameter_source_index_columns(self) -> None:
        idx = get_indexes(PhysiologyMeasurement)[
            "ix_physiology_measurements_athlete_parameter_source"
        ]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id", "parameter", "source"}


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on PhysiologyMeasurement.
# ---------------------------------------------------------------------------


class TestPhysiologyMeasurementSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the append-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # Append-only — no updated_at column.
            "updated_at",
            # No soft-delete columns.
            "deleted_at",
            "is_deleted",
            # No version column — append-only means no optimistic locking.
            "version",
            # No FK to AthletePhysiology — observations are independent
            # of the current posterior state.
            "athlete_physiology_id",
            # No FK to TwinState — observations are independent of
            # twin snapshots.
            "twin_state_id",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in get_columns(PhysiologyMeasurement), (
            f"PhysiologyMeasurement must not carry `{forbidden_field}`. "
            "The table is append-only — corrections are made by "
            "inserting a new observation with a higher "
            "confidence_weight or a more authoritative source."
        )


# ---------------------------------------------------------------------------
# Tablename.
# ---------------------------------------------------------------------------


class TestPhysiologyMeasurementTablename:
    def test_tablename_is_physiology_measurements(self) -> None:
        assert PhysiologyMeasurement.__tablename__ == "physiology_measurements"
