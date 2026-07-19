"""Unit tests for the ``Activity`` declarative surface (no DB).

Phase-1.2a codifies a strict "lean running observation index" contract:
no ``avg_hr``, no ``avg_pace``, no ``avg_power``, no ``avg_cadence``, no
lap data — ever. Adding a workout-summary column is an anti-pattern that
will silently bloat the index and break downstream services that read
from it. These tests are the tripwire.

Reference plan:
docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.activity import Activity
from app.models.enums import ActivitySource
from tests.utils.model_helpers import get_columns, has_column, get_server_default_text, get_enum_values, get_indexes


class TestActivityLeanSchemaFields:
    """Every required field from the architecture doc must be present."""

    def test_id_column_present(self) -> None:
        cols = get_columns(Activity)
        assert "id" in cols
        assert cols["id"].primary_key is True

    def test_athlete_id_present(self) -> None:
        cols = get_columns(Activity)
        assert "athlete_id" in cols
        assert cols["athlete_id"].nullable is False

    def test_planned_session_id_present_and_nullable_uuid(self) -> None:
        cols = get_columns(Activity)
        assert "planned_session_id" in cols
        col = cols["planned_session_id"]
        assert col.nullable is True
        # It is a UUID column. The FK to ``planned_sessions`` is added
        # by Phase-1.2b — this plan must NOT carry an FK constraint.
        assert isinstance(col.type, PG_UUID)

    def test_source_is_enum_backed_required(self) -> None:
        cols = get_columns(Activity)
        col = cols["source"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        produced = sorted(get_enum_values(col, ActivitySource))
        assert produced == sorted(
            [
                "intervals_icu",
                "manual_upload",
                "garmin_direct",
                "manual_entry",
            ]
        )

    def test_external_id_is_nullable_string(self) -> None:
        cols = get_columns(Activity)
        col = cols["external_id"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 128

    def test_activity_date_is_required_date(self) -> None:
        cols = get_columns(Activity)
        col = cols["activity_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_start_time_is_required_datetime(self) -> None:
        cols = get_columns(Activity)
        col = cols["start_time"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_duration_seconds_is_required_integer(self) -> None:
        cols = get_columns(Activity)
        col = cols["duration_seconds"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_load_scores_are_nullable_floats(self) -> None:
        cols = get_columns(Activity)
        for load_field in ("aerobic_load", "neuromuscular_load", "structural_load"):
            col = cols[load_field]
            assert col.nullable is True, f"{load_field} must be nullable"
            assert isinstance(col.type, Float), f"{load_field} must be Float"

    def test_signal_availability_booleans_default_false(self) -> None:
        cols = get_columns(Activity)
        for field in ("has_hr", "has_rr_intervals", "has_power"):
            col = cols[field]
            assert col.nullable is False
            assert isinstance(col.type, Boolean)
            # Database-level default keeps raw inserts honest.
            assert get_server_default_text(col) in {"false", "False", "0"}

    def test_calibration_eligible_default_false(self) -> None:
        cols = get_columns(Activity)
        col = cols["calibration_eligible"]
        assert col.nullable is False
        assert get_server_default_text(col) in {"false", "False", "0"}

    def test_quality_flags_is_required_jsonb(self) -> None:
        """``quality_flags`` is required per architecture contract;
        default ``{}`` keeps new rows honest rather than null-noise."""
        cols = get_columns(Activity)
        col = cols["quality_flags"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_fit_file_key_nullable_string(self) -> None:
        cols = get_columns(Activity)
        col = cols["fit_file_key"]
        # Null ONLY for ``manual_entry`` — enforced at the ingestion
        # boundary; the DB column is universally nullable so the
        # constraint lives in the service, not the schema.
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_versioning_fields_present_and_nullable(self) -> None:
        cols = get_columns(Activity)
        expected_lengths = {
            "ingestion_pipeline_version": 16,
            "cleaning_pipeline_version": 32,
        }
        for field, length in expected_lengths.items():
            col = cols[field]
            assert col.nullable is True
            assert isinstance(col.type, String)
            assert col.type.length == length

    def test_notes_is_text_nullable(self) -> None:
        cols = get_columns(Activity)
        col = cols["notes"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_created_at_required(self) -> None:
        cols = get_columns(Activity)
        col = cols["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


class TestActivityLeanSchemaAntiGoals:
    """The Activity table MUST NOT carry workout-summary fields.

    Each assertion is a single tripwire — a future regression that
    adds ``avg_hr`` (or any sibling) breaks the lean-schema invariant
    and is caught here before the column ships.
    """

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            "avg_hr",
            "avg_pace",
            "avg_power",
            "avg_cadence",
            "max_hr",
            "max_pace",
            "max_power",
            "lap_data",
            "laps",
            "splits",
            "elevation_gain",
            "calories",
            "training_effect",
        ],
    )
    def test_forbidden_workout_summary_fields_are_absent(
        self, forbidden_field: str
    ) -> None:
        """The architecture forbids these columns. Adding any of them
        is a breaking change to the lean-schema invariant."""
        assert not has_column(Activity, forbidden_field), (
            f"Activity must not carry `{forbidden_field}`. The lean "
            f"observation index stores what the twin needs; workout "
            f"summary belongs in the FIT file or execution-analysis "
            f"records."
        )


class TestActivityTableIndexes:
    """The mover planner query (recent activity windows) needs indexes
    on (athlete_id, activity_date) and (athlete_id, start_time); the
    deduplication invariant relies on a partial unique index on
    (athlete_id, external_id, source) WHERE external_id IS NOT NULL."""

    def _get_indexes(self) -> dict[str, Index]:
        from tests.utils.model_helpers import get_indexes
        return get_indexes(Activity)

    def test_partial_unique_dedup_index_present(self) -> None:
        indexes = self._get_indexes()
        # The ORM Index constructor passed ``uq_...``; tolerate either
        # name but require a partial unique covering the right column
        # triple.
        partial_unique = [
            idx
            for idx in indexes.values()
            if idx.unique
            and any(
                col.key == "athlete_id" for col in idx.columns
            )
            and any(
                col.key == "external_id" for col in idx.columns
            )
            and any(col.key == "source" for col in idx.columns)
        ]
        assert partial_unique, (
            "Expected a partial unique index covering "
            "(athlete_id, external_id, source)"
        )

    def test_dedup_index_partial_predicate_is_external_id_not_null(self) -> None:
        """The dedup index is partial: it only constrains
        non-null external_ids. ``manual_entry`` rows have
        ``external_id IS NULL`` and must NOT be subject to the
        constraint."""
        # The Index's ``dialect_options['postgresql']['where']`` holds
        # the predicate (Alembic-autogen-round-trips this verbatim).
        partial_unique: list[Any] = []
        for idx_ in get_indexes(Activity).values():
            if not idx_.unique:
                continue
            dialect_opts: Any = idx_.dialect_options
            if dialect_opts.get("postgresql", {}).get("where") is not None:
                partial_unique.append(idx_)
        assert partial_unique, (
            "Expected the dedup index to declare a postgresql_where "
            "predicate — without one it would constrain "
            "manual_entry rows too, blocking stale-retry ingestion."
        )
        for idx_ in partial_unique:
            predicate: Any = idx_.dialect_options["postgresql"]["where"]
            rendered = str(predicate).lower()
            assert "external_id" in rendered and "not null" in rendered, (
                f"Expected the partial predicate to constrain `external_id IS NOT NULL`. Got: {predicate}"
            )

    def test_athlete_date_index_present(self) -> None:
        indexes = self._get_indexes()
        matching = [
            idx
            for idx in indexes.values()
            if {c.key for c in idx.columns} >= {"athlete_id", "activity_date"}
        ]
        assert matching, "Expected an index on (athlete_id, activity_date)"

    def test_athlete_start_time_index_present(self) -> None:
        indexes = self._get_indexes()
        matching = [
            idx
            for idx in indexes.values()
            if {c.key for c in idx.columns} >= {"athlete_id", "start_time"}
        ]
        assert matching, "Expected an index on (athlete_id, start_time)"
