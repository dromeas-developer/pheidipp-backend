import uuid
from datetime import date
from typing import Optional

from app.core.unit_of_work import UnitOfWork
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.training_block import TrainingBlock
from app.models.twin_state import TwinState
from app.models.enums import (
    TwinTrigger,
    ConfidenceLevel,
    DataTier,
    SportBackground,
    HrSource,
    PowerSource,
)


class TwinInitialisationService:
    def __init__(self):
        pass

    async def initialise(
        self,
        athlete_id: uuid.UUID,
        preferences: AthletePreferences,
        training_block: TrainingBlock,
        profile: AthleteProfile,
        uow: UnitOfWork,
    ) -> TwinState:
        if profile.date_of_birth is None:
            raise ValueError("AthleteProfile.date_of_birth is required for twin initialization")

        age = self._compute_age(profile.date_of_birth)
        # Handle both enum and string types for gender
        if profile.gender is None:
            gender = None
        elif hasattr(profile.gender, "value"):
            gender = profile.gender.value
        else:
            gender = profile.gender
        data_tier = self._infer_data_tier(preferences)

        weekly_volume_hours = training_block.weekly_volume_hours or 0.0
        fitness_score = self._calculate_fitness_score(
            weekly_volume_hours,
            preferences.years_structured_training or 0,
            preferences.sport_background,
        )

        max_hr = self._max_hr(age, gender)
        lt1_hr, lt2_hr = self._calculate_thresholds(max_hr, fitness_score)

        structural_capacity_score = self._structural_capacity_score(
            preferences.sport_background
        )

        summary = self._build_summary(
            age, fitness_score, data_tier, structural_capacity_score, gender
        )
        metadata = self._build_metadata(
            age, fitness_score, data_tier, structural_capacity_score, gender
        )

        twin = TwinState(
            athlete_id=athlete_id,
            athlete_preferences_id=preferences.id,
            trigger=TwinTrigger.QUESTIONNAIRE,
            confidence_level=ConfidenceLevel.LOW,
            data_tier=data_tier,
            fitness_score=fitness_score,
            fatigue_score=0.0,
            max_hr_estimate=max_hr,
            lt1_hr_estimate=lt1_hr,
            lt2_hr_estimate=lt2_hr,
            lt1_pace_estimate=None,
            lt2_pace_estimate=None,
            structural_capacity_score=structural_capacity_score,
            fitness_time_constant=42.0,
            fatigue_time_constant=7.0,
            computation_summary=summary,
            computation_metadata=metadata,
        )

        uow.twin_states.session.add(twin)
        await uow.twin_states.session.flush()
        return twin

    @staticmethod
    def _compute_age(date_of_birth: date) -> int:
        today = date.today()
        age = today.year - date_of_birth.year
        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1
        return age

    @staticmethod
    def _max_hr(age: int, gender: Optional[str]) -> float:
        if gender == "female":
            return 206.0 - (0.88 * age)
        return 208.0 - (0.7 * age)

    @staticmethod
    def _calculate_fitness_score(
        weekly_volume_hours: float,
        years_structured_training: float,
        sport_background: Optional[SportBackground],
    ) -> float:
        base_score = (weekly_volume_hours * 2) + (years_structured_training * 5)

        if sport_background in (SportBackground.CYCLING_CROSSOVER, SportBackground.SWIMMING_CROSSOVER):
            base_score *= 0.8

        return max(0.0, min(100.0, base_score))

    @staticmethod
    def _calculate_thresholds(max_hr: float, fitness_score: float) -> tuple[float, float]:
        # Bands ordered from highest threshold to lowest
        # Use > to ensure fitness_score falls into the correct band:
        # 81-100: >81, 51-80: >51, 21-50: >21, 0-20: >0
        threshold_bands = [
            (81, 0.76, 0.88),
            (52, 0.73, 0.85),
            (21, 0.70, 0.83),
            (0, 0.65, 0.80),
        ]

        lt1_frac, lt2_frac = 0.65, 0.80  # default to beginner band
        for threshold, lt1, lt2 in threshold_bands:
            if fitness_score > threshold:
                lt1_frac, lt2_frac = lt1, lt2
                break

        return round(max_hr * lt1_frac, 1), round(max_hr * lt2_frac, 1)

    @staticmethod
    def _infer_data_tier(preferences: AthletePreferences) -> DataTier:
        power_source = preferences.power_source
        hr_source = preferences.hr_source

        # TIER1: power + chest strap HR
        if power_source == PowerSource.RUNNING_POWER and hr_source == HrSource.CHEST_STRAP:
            return DataTier.TIER1
        # TIER2: power + wrist optical HR
        if power_source == PowerSource.RUNNING_POWER and hr_source == HrSource.WRIST_OPTICAL:
            return DataTier.TIER2
        # TIER3: no power + chest strap HR
        if power_source != PowerSource.RUNNING_POWER and hr_source == HrSource.CHEST_STRAP:
            return DataTier.TIER3
        # TIER4: no power + wrist optical HR
        if power_source != PowerSource.RUNNING_POWER and hr_source == HrSource.WRIST_OPTICAL:
            return DataTier.TIER4
        # TIER5: no power source OR no HR source (including NONE)
        return DataTier.TIER5

    @staticmethod
    def _structural_capacity_score(sport_background: Optional[SportBackground]) -> float:
        mapping = {
            SportBackground.RUNNING_PRIMARY: 0.7,
            SportBackground.MULTI_SPORT: 0.5,
            SportBackground.CYCLING_CROSSOVER: 0.2,
            SportBackground.SWIMMING_CROSSOVER: 0.2,
            SportBackground.OTHER: 0.5,
        }
        return mapping.get(sport_background, 0.5)

    @staticmethod
    def _build_summary(
        age: int,
        fitness_score: float,
        data_tier: DataTier,
        structural_capacity_score: float,
        gender: Optional[str],
    ) -> str:
        gender_str = gender or "not specified"
        return (
            f"Age {age}, {gender_str}, fitness score {fitness_score:.1f}, "
            f"data tier {data_tier.value}, structural capacity {structural_capacity_score:.2f}, "
            f"max HR formula: {'Gulati' if gender == 'female' else 'Tanaka'}"
        )

    @staticmethod
    def _build_metadata(
        age: int,
        fitness_score: float,
        data_tier: DataTier,
        structural_capacity_score: float,
        gender: Optional[str],
    ) -> dict:
        return {
            "age": age,
            "fitness_score": fitness_score,
            "data_tier": data_tier.value,
            "structural_capacity_score": structural_capacity_score,
            "gender": gender,
            "max_hr_formula": "Gulati" if gender == "female" else "Tanaka",
        }