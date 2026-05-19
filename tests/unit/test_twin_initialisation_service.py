"""Unit tests for TwinInitialisationService."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import (
    TwinTrigger,
    ConfidenceLevel,
    DataTier,
    SportBackground,
    HrSource,
    PowerSource,
)
from app.services.twin_initialisation_service import TwinInitialisationService
from tests.factories.athlete_preferences_factory import make_athlete_preferences_full
from tests.factories.training_block_factory import make_training_block_full
from tests.factories.athlete_factory import make_athlete_profile


@pytest.fixture
def service():
    """TwinInitialisationService instance."""
    return TwinInitialisationService()


@pytest.fixture
def mock_uow():
    """Mock UnitOfWork with twin_states repository."""
    uow = MagicMock()
    uow.twin_states = MagicMock()
    uow.twin_states.session = MagicMock()
    uow.twin_states.session.add = MagicMock()
    uow.twin_states.session.flush = AsyncMock()
    return uow


@pytest.fixture
def sample_preferences():
    """Sample AthletePreferences for testing."""
    return make_athlete_preferences_full(
        sport_background=SportBackground.RUNNING_PRIMARY,
        hr_source=HrSource.CHEST_STRAP,
        power_source=PowerSource.RUNNING_POWER,
        years_structured_training=5.0,
    )


@pytest.fixture
def sample_training_block():
    """Sample TrainingBlock for testing."""
    return make_training_block_full(weekly_volume_hours=10.0)


@pytest.fixture
def sample_profile_male():
    """Sample AthleteProfile (male, age 30) for testing."""
    return make_athlete_profile(
        date_of_birth=date(1994, 5, 15),
        gender="male",
    )


@pytest.fixture
def sample_profile_female():
    """Sample AthleteProfile (female, age 30) for testing."""
    return make_athlete_profile(
        date_of_birth=date(1994, 5, 15),
        gender="female",
    )


class TestInitialise:
    """Tests for TwinInitialisationService.initialise()."""

    @pytest.mark.asyncio
    async def test_raises_value_error_when_date_of_birth_none(
        self, service, mock_uow, sample_preferences, sample_training_block
    ):
        """Verify initialise() raises ValueError when profile.date_of_birth is None."""
        profile = make_athlete_profile(date_of_birth=None)
        athlete_id = uuid.uuid4()

        with pytest.raises(ValueError) as exc_info:
            await service.initialise(
                athlete_id, sample_preferences, sample_training_block, profile, mock_uow
            )

        assert "date_of_birth" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_computes_all_fields_and_returns_twin_state(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify initialise() computes all fields and returns a TwinState ORM object."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result is not None
        assert result.athlete_id == athlete_id
        assert result.athlete_preferences_id == sample_preferences.id

    @pytest.mark.asyncio
    async def test_calls_session_add_and_flush(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify initialise() calls session.add() and session.flush() on the UoW's twin_states session."""
        athlete_id = uuid.uuid4()

        await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        mock_uow.twin_states.session.add.assert_called_once()
        mock_uow.twin_states.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_trigger_questionnaire(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify the returned TwinState has trigger=TwinTrigger.QUESTIONNAIRE."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result.trigger == TwinTrigger.QUESTIONNAIRE

    @pytest.mark.asyncio
    async def test_returns_confidence_level_low(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify the returned TwinState has confidence_level=ConfidenceLevel.LOW."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result.confidence_level == ConfidenceLevel.LOW

    @pytest.mark.asyncio
    async def test_returns_fatigue_score_zero(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify the returned TwinState has fatigue_score=0.0."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result.fatigue_score == 0.0

    @pytest.mark.asyncio
    async def test_returns_fitness_time_constant_42(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify the returned TwinState has fitness_time_constant=42.0."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result.fitness_time_constant == 42.0

    @pytest.mark.asyncio
    async def test_returns_fatigue_time_constant_7(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify the returned TwinState has fatigue_time_constant=7.0."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result.fatigue_time_constant == 7.0

    @pytest.mark.asyncio
    async def test_returns_lt1_pace_estimate_none(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify the returned TwinState has lt1_pace_estimate=None."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result.lt1_pace_estimate is None

    @pytest.mark.asyncio
    async def test_returns_lt2_pace_estimate_none(
        self, service, mock_uow, sample_preferences, sample_training_block, sample_profile_male
    ):
        """Verify the returned TwinState has lt2_pace_estimate=None."""
        athlete_id = uuid.uuid4()

        result = await service.initialise(
            athlete_id, sample_preferences, sample_training_block, sample_profile_male, mock_uow
        )

        assert result.lt2_pace_estimate is None


class TestComputeAge:
    """Tests for TwinInitialisationService._compute_age()."""

    def test_age_for_birthday_already_passed_this_year(self):
        """Verify correct age for a birthday that has already passed this year."""
        # Born May 15, 1994, today is say June 1, 2024 -> age is 30
        dob = date(1994, 5, 15)
        # We need to mock date.today() or test with a specific date
        # Since _compute_age uses date.today(), we test with known values
        age = TwinInitialisationService._compute_age(dob)
        today = date.today()
        expected_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        assert age == expected_age

    def test_age_for_birthday_not_yet_passed_this_year(self):
        """Verify correct age for a birthday that has not yet passed this year."""
        dob = date(1994, 12, 31)
        age = TwinInitialisationService._compute_age(dob)
        today = date.today()
        expected_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        assert age == expected_age

    def test_age_for_birthday_exactly_on_today(self):
        """Verify correct age for a birthday exactly on today's date."""
        today = date.today()
        dob = date(1994, today.month, today.day)
        age = TwinInitialisationService._compute_age(dob)
        assert age == today.year - dob.year


class TestMaxHr:
    """Tests for TwinInitialisationService._max_hr()."""

    def test_gulati_formula_for_female(self):
        """Verify Gulati formula for female: 206 - (0.88 * age)."""
        age = 30
        max_hr = TwinInitialisationService._max_hr(age, "female")
        expected = 206 - (0.88 * age)
        assert abs(max_hr - expected) < 0.01

    def test_tanaka_formula_for_male(self):
        """Verify Tanaka formula for male: 208 - (0.7 * age)."""
        age = 30
        max_hr = TwinInitialisationService._max_hr(age, "male")
        expected = 208 - (0.7 * age)
        assert abs(max_hr - expected) < 0.01

    def test_tanaka_formula_for_none_gender(self):
        """Verify Tanaka formula for None gender (defaults to male formula)."""
        age = 30
        max_hr = TwinInitialisationService._max_hr(age, None)
        expected = 208 - (0.7 * age)
        assert abs(max_hr - expected) < 0.01

    def test_tanaka_formula_for_non_binary_gender(self):
        """Verify Tanaka formula for 'non_binary' gender."""
        age = 30
        max_hr = TwinInitialisationService._max_hr(age, "non_binary")
        expected = 208 - (0.7 * age)
        assert abs(max_hr - expected) < 0.01


class TestCalculateFitnessScore:
    """Tests for TwinInitialisationService._calculate_fitness_score()."""

    def test_base_calculation(self):
        """Verify base calculation: (weekly_volume_hours * 2) + (years_structured_training * 5)."""
        weekly_volume_hours = 6.0
        years = 5.0
        score = TwinInitialisationService._calculate_fitness_score(
            weekly_volume_hours, years, SportBackground.RUNNING_PRIMARY
        )
        expected = (6 * 2) + (5 * 5)
        assert score == expected

    def test_crossover_adjustment_cycling(self):
        """Verify crossover adjustment (×0.8) for CYCLING_CROSSOVER."""
        weekly_volume_hours = 10.0
        years = 5.0
        score = TwinInitialisationService._calculate_fitness_score(
            weekly_volume_hours, years, SportBackground.CYCLING_CROSSOVER
        )
        base = (10 * 2) + (5 * 5)
        expected = base * 0.8
        assert score == expected

    def test_crossover_adjustment_swimming(self):
        """Verify crossover adjustment (×0.8) for SWIMMING_CROSSOVER."""
        weekly_volume_hours = 10.0
        years = 5.0
        score = TwinInitialisationService._calculate_fitness_score(
            weekly_volume_hours, years, SportBackground.SWIMMING_CROSSOVER
        )
        base = (10 * 2) + (5 * 5)
        expected = base * 0.8
        assert score == expected

    def test_no_adjustment_running_primary(self):
        """Verify no adjustment for RUNNING_PRIMARY."""
        weekly_volume_hours = 10.0
        years = 5.0
        score = TwinInitialisationService._calculate_fitness_score(
            weekly_volume_hours, years, SportBackground.RUNNING_PRIMARY
        )
        base = (10 * 2) + (5 * 5)
        assert score == base

    def test_clamping_to_0_when_negative(self):
        """Verify clamping to 0 when inputs produce negative score."""
        score = TwinInitialisationService._calculate_fitness_score(
            0, 0, SportBackground.RUNNING_PRIMARY
        )
        assert score == 0.0

    def test_clamping_to_100_when_exceeds(self):
        """Verify clamping to 100 when inputs exceed 100."""
        score = TwinInitialisationService._calculate_fitness_score(
            100, 100, SportBackground.RUNNING_PRIMARY
        )
        assert score == 100.0

    def test_exact_computation_for_52_score(self):
        """Verify exact computation for 30-year-old male, fitness_score=52 scenario."""
        # weekly_volume_hours=11, years=6 -> (11*2)+(6*5) = 22+30 = 52
        score = TwinInitialisationService._calculate_fitness_score(
            11, 6, SportBackground.RUNNING_PRIMARY
        )
        assert score == 52


class TestCalculateThresholds:
    """Tests for TwinInitialisationService._calculate_thresholds()."""

    def test_beginner_band_0_20(self):
        """Verify beginner band (0-20): LT1=0.65, LT2=0.80."""
        max_hr = 180.0
        lt1, lt2 = TwinInitialisationService._calculate_thresholds(max_hr, 10)
        assert lt1 == round(180 * 0.65, 1)
        assert lt2 == round(180 * 0.80, 1)

    def test_intermediate_band_21_50(self):
        """Verify intermediate band (21-50): LT1=0.70, LT2=0.83."""
        max_hr = 180.0
        lt1, lt2 = TwinInitialisationService._calculate_thresholds(max_hr, 35)
        assert lt1 == round(180 * 0.70, 1)
        assert lt2 == round(180 * 0.83, 1)

    def test_advanced_band_51_80(self):
        """Verify advanced band (51-80): LT1=0.73, LT2=0.85."""
        max_hr = 180.0
        lt1, lt2 = TwinInitialisationService._calculate_thresholds(max_hr, 65)
        assert lt1 == round(180 * 0.73, 1)
        assert lt2 == round(180 * 0.85, 1)

    def test_elite_band_81_100(self):
        """Verify elite band (81-100): LT1=0.76, LT2=0.88."""
        max_hr = 180.0
        lt1, lt2 = TwinInitialisationService._calculate_thresholds(max_hr, 90)
        assert lt1 == round(180 * 0.76, 1)
        assert lt2 == round(180 * 0.88, 1)

    def test_exact_values_for_fitness_52_male(self):
        """Verify exact values for fitness_score=52, max_hr=187."""
        max_hr = 187.0
        lt1, lt2 = TwinInitialisationService._calculate_thresholds(max_hr, 52)
        # fitness_score 52 is in intermediate band (21-50), so LT1=0.70, LT2=0.83
        assert lt1 == round(187 * 0.70, 1)  # 130.9
        assert lt2 == round(187 * 0.83, 1)  # 155.21

    def test_exact_values_for_fitness_52_female(self):
        """Verify exact values for fitness_score=52, max_hr=179.6."""
        max_hr = 179.6
        lt1, lt2 = TwinInitialisationService._calculate_thresholds(max_hr, 52)
        # fitness_score 52 is in intermediate band (21-50), so LT1=0.70, LT2=0.83
        assert lt1 == round(179.6 * 0.70, 1)  # 125.72
        assert lt2 == round(179.6 * 0.83, 1)  # 149.068


class TestInferDataTier:
    """Tests for TwinInitialisationService._infer_data_tier()."""

    def test_tier1_power_and_chest_hr(self):
        """Verify TIER1: power_source=RUNNING_POWER AND hr_source=CHEST_STRAP."""
        prefs = make_athlete_preferences_full(
            power_source=PowerSource.RUNNING_POWER,
            hr_source=HrSource.CHEST_STRAP,
        )
        tier = TwinInitialisationService._infer_data_tier(prefs)
        assert tier == DataTier.TIER1

    def test_tier2_power_and_wrist_hr(self):
        """Verify TIER2: power_source=RUNNING_POWER AND hr_source=WRIST_OPTICAL."""
        prefs = make_athlete_preferences_full(
            power_source=PowerSource.RUNNING_POWER,
            hr_source=HrSource.WRIST_OPTICAL,
        )
        tier = TwinInitialisationService._infer_data_tier(prefs)
        assert tier == DataTier.TIER2

    def test_tier3_no_power_and_chest_hr(self):
        """Verify TIER3: power_source=NONE AND hr_source=CHEST_STRAP."""
        prefs = make_athlete_preferences_full(
            power_source=PowerSource.NONE,
            hr_source=HrSource.CHEST_STRAP,
        )
        tier = TwinInitialisationService._infer_data_tier(prefs)
        assert tier == DataTier.TIER3

    def test_tier4_no_power_and_wrist_hr(self):
        """Verify TIER4: power_source=NONE AND hr_source=WRIST_OPTICAL."""
        prefs = make_athlete_preferences_full(
            power_source=PowerSource.NONE,
            hr_source=HrSource.WRIST_OPTICAL,
        )
        tier = TwinInitialisationService._infer_data_tier(prefs)
        assert tier == DataTier.TIER4

    def test_tier5_no_power_and_no_hr(self):
        """Verify TIER5: power_source=NONE AND hr_source=NONE."""
        prefs = make_athlete_preferences_full(
            power_source=PowerSource.NONE,
            hr_source=HrSource.NONE,
        )
        tier = TwinInitialisationService._infer_data_tier(prefs)
        assert tier == DataTier.TIER5

    def test_tier5_power_and_no_hr(self):
        """Verify TIER5: power_source=RUNNING_POWER AND hr_source=NONE."""
        prefs = make_athlete_preferences_full(
            power_source=PowerSource.RUNNING_POWER,
            hr_source=HrSource.NONE,
        )
        tier = TwinInitialisationService._infer_data_tier(prefs)
        assert tier == DataTier.TIER5


class TestStructuralCapacityScore:
    """Tests for TwinInitialisationService._structural_capacity_score()."""

    def test_running_primary(self):
        """Verify RUNNING_PRIMARY returns 0.7."""
        score = TwinInitialisationService._structural_capacity_score(
            SportBackground.RUNNING_PRIMARY
        )
        assert score == 0.7

    def test_multi_sport(self):
        """Verify MULTI_SPORT returns 0.5."""
        score = TwinInitialisationService._structural_capacity_score(
            SportBackground.MULTI_SPORT
        )
        assert score == 0.5

    def test_cycling_crossover(self):
        """Verify CYCLING_CROSSOVER returns 0.2."""
        score = TwinInitialisationService._structural_capacity_score(
            SportBackground.CYCLING_CROSSOVER
        )
        assert score == 0.2

    def test_swimming_crossover(self):
        """Verify SWIMMING_CROSSOVER returns 0.2."""
        score = TwinInitialisationService._structural_capacity_score(
            SportBackground.SWIMMING_CROSSOVER
        )
        assert score == 0.2

    def test_other(self):
        """Verify OTHER returns 0.5."""
        score = TwinInitialisationService._structural_capacity_score(
            SportBackground.OTHER
        )
        assert score == 0.5

    def test_unknown_background_defaults_to_0_5(self):
        """Verify unknown/None background defaults to 0.5."""
        score = TwinInitialisationService._structural_capacity_score(None)
        assert score == 0.5


class TestBuildSummary:
    """Tests for TwinInitialisationService._build_summary()."""

    def test_summary_contains_all_fields(self):
        """Verify summary string contains age, gender, fitness score, data tier, structural capacity, and max HR formula name."""
        summary = TwinInitialisationService._build_summary(
            age=30,
            fitness_score=52.0,
            data_tier=DataTier.TIER1,
            structural_capacity_score=0.7,
            gender="male",
        )
        assert "30" in summary
        assert "male" in summary
        assert "52.0" in summary
        assert "tier1" in summary
        assert "0.70" in summary
        assert "Tanaka" in summary

    def test_summary_uses_not_specified_for_none_gender(self):
        """Verify summary uses 'not specified' when gender is None."""
        summary = TwinInitialisationService._build_summary(
            age=30,
            fitness_score=52.0,
            data_tier=DataTier.TIER1,
            structural_capacity_score=0.7,
            gender=None,
        )
        assert "not specified" in summary


class TestBuildMetadata:
    """Tests for TwinInitialisationService._build_metadata()."""

    def test_metadata_contains_all_required_keys(self):
        """Verify metadata dict contains all required keys."""
        metadata = TwinInitialisationService._build_metadata(
            age=30,
            fitness_score=52.0,
            data_tier=DataTier.TIER1,
            structural_capacity_score=0.7,
            gender="male",
        )
        assert "age" in metadata
        assert "fitness_score" in metadata
        assert "data_tier" in metadata
        assert "structural_capacity_score" in metadata
        assert "gender" in metadata
        assert "max_hr_formula" in metadata

    def test_max_hr_formula_gulati_for_female(self):
        """Verify max_hr_formula is 'Gulati' for female."""
        metadata = TwinInitialisationService._build_metadata(
            age=30,
            fitness_score=52.0,
            data_tier=DataTier.TIER1,
            structural_capacity_score=0.7,
            gender="female",
        )
        assert metadata["max_hr_formula"] == "Gulati"

    def test_max_hr_formula_tanaka_for_others(self):
        """Verify max_hr_formula is 'Tanaka' for all others."""
        for gender in ["male", "non_binary", None]:
            metadata = TwinInitialisationService._build_metadata(
                age=30,
                fitness_score=52.0,
                data_tier=DataTier.TIER1,
                structural_capacity_score=0.7,
                gender=gender,
            )
            assert metadata["max_hr_formula"] == "Tanaka"