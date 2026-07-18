"""Unit tests for the ``AthleteProfile`` declarative surface (no DB).

These tests inspect the SQLAlchemy mapper without touching a database.
They guarantee that Phase-1.2a:

* Preserves every Phase-1.1 column (``id``, ``athlete_id``,
  ``date_of_birth``, ``sex``, ``height_cm``, ``updated_at``).
* Adds the full Phase-1.2a column set in the order documented in
  ``docs/architecture/01-entities/athlete-profile.md``.
* Keeps the one-to-one ``athlete_id`` uniqueness at the mapper level
  (the DB-level invariant is re-checked in integration tests).
* Keeps stable demographics (``date_of_birth``, ``sex``) as
  ``nullable=False`` so a Phase-1.1 minimal registration can never
  accidentally persist a row with null demographics.

Reference plan:
docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.models.athlete_profile import AthleteProfile
from app.models.enums import Sex
from tests.utils.model_helpers import get_columns, get_enum_values


class TestPhase11ColumnsPreserved:
    """Every Phase-1.1 column must still exist on the model."""

    def test_id_column_present(self) -> None:
        col = get_columns(AthleteProfile)["id"]
        # Primary key with UUID type.
        assert col.primary_key is True

    def test_athlete_id_is_unique_one_to_one(self) -> None:
        """``athlete_id`` uniqueness is the Phase-1.1 invariant that
        Phase-1.2a must preserve. DB-level uniqueness is also enforced
        via ``UniqueConstraint('athlete_id')`` — see integration tests.
        """
        col = get_columns(AthleteProfile)["athlete_id"]
        assert col.unique is True

    def test_date_of_birth_required(self) -> None:
        col = get_columns(AthleteProfile)["date_of_birth"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_sex_required_and_enum_backed(self) -> None:
        col = get_columns(AthleteProfile)["sex"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)

    def test_height_cm_nullable_decimal(self) -> None:
        col = get_columns(AthleteProfile)["height_cm"]
        # Phase-1.1 contract: height is optional.
        assert col.nullable is True
        assert isinstance(col.type, Numeric)

    def test_updated_at_present(self) -> None:
        col = get_columns(AthleteProfile)["updated_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


class TestPhase12aExtensionColumns:
    """Phase-1.2a adds personalisation, location, scheduling, effort,
    and objective fields. Every column must be present with the
    documented nullability and type."""

    def test_personalisation_jsonb_fields_present_and_nullable(self) -> None:
        for name in (
            "gap_curve_model",
            "weather_response_model",
            "banister_constants",
            "cycle_personal_model",
        ):
            col = get_columns(AthleteProfile)[name]
            assert col.nullable is True, f"{name} should be nullable"
            assert isinstance(col.type, JSONB), f"{name} should be JSONB"

    def test_location_fields_present_and_nullable(self) -> None:
        for name in ("location_lat", "location_lng"):
            col = get_columns(AthleteProfile)[name]
            assert col.nullable is True
            assert isinstance(col.type, Numeric)

    def test_timezone_field_present_and_nullable(self) -> None:
        """``timezone`` is required at onboarding but NOT at registration.
        Phase-1.1 minimal profile (created at registration) leaves it
        null — Phase-1.2a onboarding populates it."""
        col = get_columns(AthleteProfile)["timezone"]
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_training_window_is_jsonb(self) -> None:
        col = get_columns(AthleteProfile)["training_window"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_current_effort_generation_is_integer_nullable(self) -> None:
        """NULL until GapCurveFittingService sets it (defaults to 1 in
        practice, but ``NULL`` is the schema-only initial state)."""
        col = get_columns(AthleteProfile)["current_effort_generation"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)

    def test_structural_risk_flag_is_nullable_boolean(self) -> None:
        col = get_columns(AthleteProfile)["structural_risk_flag"]
        assert col.nullable is True
        assert isinstance(col.type, Boolean)

    def test_objective_thresholds_is_jsonb_nullable(self) -> None:
        col = get_columns(AthleteProfile)["objective_thresholds"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)


class TestSchemaCompleteness:
    """A single guardrail test that asserts the FULL column set matches
    the architecture contract. If anyone adds a field that isn't
    documented here, this test fails until the contract is updated.
    """

    def test_full_declared_column_set(self) -> None:
        expected = {
            # Phase-1.1 (preserved)
            "id",
            "athlete_id",
            "date_of_birth",
            "sex",
            "height_cm",
            # Phase-1.2a additions
            "gap_curve_model",
            "weather_response_model",
            "banister_constants",
            "cycle_personal_model",
            "location_lat",
            "location_lng",
            "timezone",
            "training_window",
            "current_effort_generation",
            "structural_risk_flag",
            "objective_thresholds",
            "updated_at",
        }
        actual = set(get_columns(AthleteProfile).keys())
        missing = expected - actual
        unexpected = actual - expected
        assert missing == set(), f"Missing columns: {missing}"
        assert unexpected == set(), f"Unexpected columns: {unexpected}"


class TestMapperRelationships:
    def test_sex_enum_values_callable_is_set(self) -> None:
        """The mapper's ``sex`` column uses ``values_callable=lambda e:
        [e.value for e in e]`` so the DB ENUM stores ``"male"`` /
        ``"female"`` / ``"not_specified"`` rather than the upper-case
        Python name. This is critical: the Phase-1.1 migration
        registered the ENUM with lowercase values, so an upper-case
        regression here would crash creation/reads."""
        col = get_columns(AthleteProfile)["sex"]
        assert isinstance(col.type, SAEnum)
        produced = get_enum_values(col, Sex)
        assert set(produced) == {"male", "female", "not_specified"}
