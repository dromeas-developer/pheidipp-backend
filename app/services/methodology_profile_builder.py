from app.models.enums import (
    MethodologyTrait,
    GoalEventType,
    SportBackground,
    ConfidenceLevel,
)
from app.models.athlete_preferences import AthletePreferences
from app.schemas.plan_generation import MethodologyProfile


class MethodologyProfileBuilder:
    def build(
        self,
        event_type: GoalEventType | None,
        weeks_to_goal: int,
        training_age: float | None,
        available_days: int,
        structural_capacity_score: float,
        adaptation_confidence_level: ConfidenceLevel,
        consistency_score: float,
    ) -> MethodologyProfile:
        if event_type == GoalEventType.MARATHON:
            weights = self._marathon_profile(weeks_to_goal, training_age, structural_capacity_score)
        elif event_type == GoalEventType.HALF_MARATHON:
            weights = self._half_marathon_profile(weeks_to_goal, training_age, structural_capacity_score)
        elif event_type in (GoalEventType.FIVE_K, GoalEventType.TEN_K):
            weights = self._track_profile(weeks_to_goal, training_age, structural_capacity_score)
        elif event_type == GoalEventType.ULTRA:
            weights = self._ultra_profile(weeks_to_goal, training_age, structural_capacity_score)
        else:
            weights = self._default_profile(weeks_to_goal, training_age, structural_capacity_score)

        self._apply_experience_modifier(weights, training_age, consistency_score)
        self._apply_durability_modifier(weights, structural_capacity_score, available_days)
        self._normalize_weights(weights)
        return MethodologyProfile(trait_weights=weights)

    def _base_phase_weights(self) -> dict[MethodologyTrait, float]:
        return {
            MethodologyTrait.HIGH_AEROBIC_VOLUME: 0.9,
            MethodologyTrait.CONSERVATIVE_PROGRESSION: 0.8,
            MethodologyTrait.THRESHOLD_DENSITY: 0.2,
            MethodologyTrait.HIGH_INTENSITY_SPARSE: 0.3,
            MethodologyTrait.LOW_INTENSITY_DOMINANT: 0.8,
            MethodologyTrait.HIGH_FREQUENCY: 0.7,
            MethodologyTrait.STRUCTURAL_DURABILITY: 0.6,
            MethodologyTrait.RACE_SPECIFICITY: 0.2,
            MethodologyTrait.VARIETY_EMPHASIS: 0.5,
            MethodologyTrait.NEUROMUSCULAR_SUPPORT: 0.5,
        }

    def _build_phase_weights(self) -> dict[MethodologyTrait, float]:
        return {
            MethodologyTrait.HIGH_AEROBIC_VOLUME: 0.7,
            MethodologyTrait.CONSERVATIVE_PROGRESSION: 0.6,
            MethodologyTrait.THRESHOLD_DENSITY: 0.7,
            MethodologyTrait.HIGH_INTENSITY_SPARSE: 0.5,
            MethodologyTrait.LOW_INTENSITY_DOMINANT: 0.5,
            MethodologyTrait.HIGH_FREQUENCY: 0.6,
            MethodologyTrait.STRUCTURAL_DURABILITY: 0.7,
            MethodologyTrait.RACE_SPECIFICITY: 0.9,
            MethodologyTrait.VARIETY_EMPHASIS: 0.5,
            MethodologyTrait.NEUROMUSCULAR_SUPPORT: 0.4,
        }

    def _taper_phase_weights(self) -> dict[MethodologyTrait, float]:
        return {
            MethodologyTrait.HIGH_AEROBIC_VOLUME: 0.3,
            MethodologyTrait.CONSERVATIVE_PROGRESSION: 1.0,
            MethodologyTrait.THRESHOLD_DENSITY: 0.2,
            MethodologyTrait.HIGH_INTENSITY_SPARSE: 0.1,
            MethodologyTrait.LOW_INTENSITY_DOMINANT: 0.9,
            MethodologyTrait.HIGH_FREQUENCY: 0.4,
            MethodologyTrait.STRUCTURAL_DURABILITY: 0.3,
            MethodologyTrait.RACE_SPECIFICITY: 1.0,
            MethodologyTrait.VARIETY_EMPHASIS: 0.6,
            MethodologyTrait.NEUROMUSCULAR_SUPPORT: 0.7,
        }

    def _marathon_profile(
        self, weeks: int, training_age: float | None, structural: float
    ) -> dict[MethodologyTrait, float]:
        weights = {**self._base_phase_weights()}
        weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] = 1.0
        weights[MethodologyTrait.STRUCTURAL_DURABILITY] = 0.9
        if weeks < 12:
            weights[MethodologyTrait.CONSERVATIVE_PROGRESSION] = 1.0
            weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] = 0.8
        return weights

    def _half_marathon_profile(
        self, weeks: int, training_age: float | None, structural: float
    ) -> dict[MethodologyTrait, float]:
        weights = {**self._build_phase_weights()}
        weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] = 0.8
        weights[MethodologyTrait.THRESHOLD_DENSITY] = 0.8
        return weights

    def _track_profile(
        self, weeks: int, training_age: float | None, structural: float
    ) -> dict[MethodologyTrait, float]:
        weights = {**self._build_phase_weights()}
        weights[MethodologyTrait.HIGH_INTENSITY_SPARSE] = 0.9
        weights[MethodologyTrait.RACE_SPECIFICITY] = 1.0
        weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] = 0.4
        return weights

    def _ultra_profile(
        self, weeks: int, training_age: float | None, structural: float
    ) -> dict[MethodologyTrait, float]:
        weights = {**self._base_phase_weights()}
        weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] = 1.0
        weights[MethodologyTrait.STRUCTURAL_DURABILITY] = 1.0
        weights[MethodologyTrait.VARIETY_EMPHASIS] = 0.9
        weights[MethodologyTrait.CONSERVATIVE_PROGRESSION] = 0.9
        return weights

    def _default_profile(
        self, weeks: int, training_age: float | None, structural: float
    ) -> dict[MethodologyTrait, float]:
        weights = {**self._build_phase_weights()}
        return weights

    def _apply_experience_modifier(
        self,
        weights: dict[MethodologyTrait, float],
        training_age: float | None,
        consistency_score: float,
    ) -> None:
        if training_age is None or training_age < 1:
            weights[MethodologyTrait.CONSERVATIVE_PROGRESSION] = max(
                weights.get(MethodologyTrait.CONSERVATIVE_PROGRESSION, 0.5) * 1.2, 1.0
            )
            weights[MethodologyTrait.HIGH_INTENSITY_SPARSE] = min(
                weights.get(MethodologyTrait.HIGH_INTENSITY_SPARSE, 0.5) * 0.8, 1.0
            )
        if consistency_score < 0.6:
            weights[MethodologyTrait.CONSERVATIVE_PROGRESSION] = max(
                weights.get(MethodologyTrait.CONSERVATIVE_PROGRESSION, 0.5) * 1.2, 1.0
            )

    def _apply_durability_modifier(
        self,
        weights: dict[MethodologyTrait, float],
        structural_capacity_score: float,
        available_days: int,
    ) -> None:
        if structural_capacity_score < 0.4:
            weights[MethodologyTrait.STRUCTURAL_DURABILITY] = 1.0
            weights[MethodologyTrait.LOW_INTENSITY_DOMINANT] = 1.0
        if available_days >= 6:
            weights[MethodologyTrait.HIGH_FREQUENCY] = 1.0
        elif available_days <= 4:
            weights[MethodologyTrait.HIGH_FREQUENCY] = 0.4

    def _normalize_weights(
        self, weights: dict[MethodologyTrait, float]
    ) -> None:
        max_weight = max(weights.values()) if weights else 1.0
        if max_weight > 1.0:
            for trait in weights:
                weights[trait] = min(weights[trait] / max_weight, 1.0)