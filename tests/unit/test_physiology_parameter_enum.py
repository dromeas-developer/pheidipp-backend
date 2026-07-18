"""Unit tests for the PhysiologyParameter enum contract.

Phase-2.3-P1 introduces the ``PhysiologyParameter`` closed ontology
that ``PhysiologyMeasurement`` rows reference. The values are part of
the public architecture contract: changing them is a breaking change
for downstream services (threshold detection, physiology update,
twin recalibration).

Reference plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations


from app.models.enums import PhysiologyParameter


class TestPhysiologyParameterContract:
    """``PhysiologyParameter`` is the closed ontology of physiological
    parameters tracked per athlete. Each value identifies a single
    (parameter, signal) pair."""

    def test_physiology_parameter_has_exactly_ten_values(self) -> None:
        """The plan specifies exactly 10 values."""
        assert {member.value for member in PhysiologyParameter} == {
            "lt1_hr",
            "lt1_power",
            "lt1_pace",
            "lt2_hr",
            "lt2_power",
            "lt2_pace",
            "cp",
            "vo2max_ml_kg_min",
            "vo2max_power",
            "max_hr",
        }

    def test_physiology_parameter_values_are_lowercase_strings(self) -> None:
        for member in PhysiologyParameter:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()

    def test_physiology_parameter_includes_lt1_hr(self) -> None:
        """LT1_HR is the primary LT1 observation produced by HR-based
        threshold detection algorithms."""
        assert PhysiologyParameter.LT1_HR.value == "lt1_hr"

    def test_physiology_parameter_includes_lt2_hr(self) -> None:
        """LT2_HR is the primary LT2 observation produced by HR-based
        threshold detection algorithms."""
        assert PhysiologyParameter.LT2_HR.value == "lt2_hr"

    def test_physiology_parameter_includes_cp(self) -> None:
        """CP is the critical power observation produced by the
        power-to-HR ratio algorithm."""
        assert PhysiologyParameter.CP.value == "cp"

    def test_physiology_parameter_includes_lt1_power_and_lt1_pace(self) -> None:
        """LT1 has three signal variants: HR, power, pace."""
        assert PhysiologyParameter.LT1_POWER.value == "lt1_power"
        assert PhysiologyParameter.LT1_PACE.value == "lt1_pace"

    def test_physiology_parameter_includes_lt2_power_and_lt2_pace(self) -> None:
        """LT2 has three signal variants: HR, power, pace."""
        assert PhysiologyParameter.LT2_POWER.value == "lt2_power"
        assert PhysiologyParameter.LT2_PACE.value == "lt2_pace"

    def test_physiology_parameter_includes_vo2max_variants(self) -> None:
        """VO2max has two signal variants: ml_kg_min and power."""
        assert (
            PhysiologyParameter.VO2MAX_ML_KG_MIN.value == "vo2max_ml_kg_min"
        )
        assert PhysiologyParameter.VO2MAX_POWER.value == "vo2max_power"

    def test_physiology_parameter_includes_max_hr(self) -> None:
        """MAX_HR is the maximum heart rate observation."""
        assert PhysiologyParameter.MAX_HR.value == "max_hr"


class TestPhysiologyParameterReExport:
    """``PhysiologyParameter`` must be re-exported from
    ``app.models.__init__`` so Alembic autogenerate discovers it."""

    def test_physiology_parameter_is_exported_from_models_package(self) -> None:
        import app.models as models_pkg  # noqa: PLC0415

        assert hasattr(models_pkg, "PhysiologyParameter"), (
            "`PhysiologyParameter` must be re-exported from "
            "`app.models.__init__` — Alembic autogen will otherwise "
            "miss the enum and emit DROP/CREATE rather than ALTER."
        )
        assert (
            models_pkg.PhysiologyParameter is PhysiologyParameter
        )
