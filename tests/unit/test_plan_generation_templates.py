from datetime import date

import pytest

from app.models.enums import PhaseLabel
from app.services.plan_generation_templates import (
    PhaseAllocation,
    allocate_race_event_phases,
    derive_experience_level,
    evaluate_training_length_gate,
    schedule_checkpoints,
)


class TestAllocateRaceEventPhases:
    def test_24_week_phase_allocation(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=24)

        assert len(allocations) == 5
        total = sum(a.weeks for a in allocations)
        assert total == 24

        labels = [a.label for a in allocations]
        assert labels == [
            PhaseLabel.AEROBIC_BASE,
            PhaseLabel.THRESHOLD_BUILD,
            PhaseLabel.SPECIFIC_ENDURANCE,
            PhaseLabel.TAPER,
            PhaseLabel.RACE_WEEK,
        ]

        taper = next(a for a in allocations if a.label == PhaseLabel.TAPER)
        race = next(a for a in allocations if a.label == PhaseLabel.RACE_WEEK)
        assert taper.weeks == 2
        assert race.weeks == 1

        base = next(a for a in allocations if a.label == PhaseLabel.AEROBIC_BASE)
        threshold = next(a for a in allocations if a.label == PhaseLabel.THRESHOLD_BUILD)
        race_specific = next(a for a in allocations if a.label == PhaseLabel.SPECIFIC_ENDURANCE)
        assert base.weeks >= threshold.weeks >= race_specific.weeks

    def test_16_week_phase_allocation(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=16)

        assert len(allocations) == 5
        total = sum(a.weeks for a in allocations)
        assert total == 16

        taper = next(a for a in allocations if a.label == PhaseLabel.TAPER)
        race = next(a for a in allocations if a.label == PhaseLabel.RACE_WEEK)
        assert taper.weeks == 2
        assert race.weeks == 1

    def test_short_plan_falls_back_to_taper_and_race_week(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=3)

        assert len(allocations) == 2
        labels = [a.label for a in allocations]
        assert labels == [PhaseLabel.TAPER, PhaseLabel.RACE_WEEK]

        total = sum(a.weeks for a in allocations)
        assert total == 3

    def test_phase_labels_correct_order(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=24)

        labels = [a.label for a in allocations]
        assert labels == [
            PhaseLabel.AEROBIC_BASE,
            PhaseLabel.THRESHOLD_BUILD,
            PhaseLabel.SPECIFIC_ENDURANCE,
            PhaseLabel.TAPER,
            PhaseLabel.RACE_WEEK,
        ]

    def test_phase_specificity_values(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=24)

        specificity = {a.label: a.specificity for a in allocations}
        assert specificity[PhaseLabel.AEROBIC_BASE] == pytest.approx(0.1)
        assert specificity[PhaseLabel.THRESHOLD_BUILD] == pytest.approx(0.4)
        assert specificity[PhaseLabel.SPECIFIC_ENDURANCE] == pytest.approx(0.7)
        assert specificity[PhaseLabel.TAPER] == pytest.approx(0.5)
        assert specificity[PhaseLabel.RACE_WEEK] == pytest.approx(1.0)


class TestDeriveExperienceLevel:
    def test_novice_years_less_than_2(self) -> None:
        assert derive_experience_level(1) == "novice"

    def test_intermediate_boundary_years_2(self) -> None:
        assert derive_experience_level(2) == "intermediate"

    def test_intermediate_boundary_years_5(self) -> None:
        assert derive_experience_level(5) == "intermediate"

    def test_experienced_years_greater_than_5(self) -> None:
        assert derive_experience_level(6) == "experienced"

    def test_zero_years(self) -> None:
        assert derive_experience_level(0) == "novice"


class TestEvaluateTrainingLengthGate:
    def test_marathon_novice_at_threshold(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=20,
            fitness_level=3,
            goal_event_type="marathon",
            experience_level="novice",
        )
        assert result.action == "proceed"

    def test_marathon_novice_above_threshold(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=21,
            fitness_level=3,
            goal_event_type="marathon",
            experience_level="novice",
        )
        assert result.action == "propose_intermediate"
        assert result.gate_reason == "goal_too_far"

    def test_5k_experienced_at_threshold(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=16,
            fitness_level=3,
            goal_event_type="5k",
            experience_level="experienced",
        )
        assert result.action == "proceed"

    def test_5k_experienced_above_threshold(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=17,
            fitness_level=3,
            goal_event_type="5k",
            experience_level="experienced",
        )
        assert result.action == "propose_intermediate"
        assert result.gate_reason == "goal_too_far"

    def test_ultra_intermediate_at_threshold(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=30,
            fitness_level=3,
            goal_event_type="ultra",
            experience_level="intermediate",
        )
        assert result.action == "proceed"

    def test_short_goal_with_low_fitness(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=6,
            fitness_level=2,
            goal_event_type="marathon",
            experience_level="novice",
        )
        assert result.action == "propose_shorter_goal"
        assert result.gate_reason == "fitness_insufficient_for_distance"

    def test_short_goal_with_adequate_fitness_proceeds(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=6,
            fitness_level=3,
            goal_event_type="5k",
            experience_level="novice",
        )
        assert result.action == "proceed"

    def test_unknown_goal_event_type_uses_default_threshold(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=25,
            fitness_level=3,
            goal_event_type="unknown_type",
            experience_level="novice",
        )
        assert result.action == "propose_intermediate"
        assert result.gate_reason == "goal_too_far"


class TestScheduleCheckpoints:
    def _make_allocations(self, total_weeks: int) -> list[PhaseAllocation]:
        return allocate_race_event_phases(total_weeks=total_weeks)

    def _make_phase_starts(self, total_weeks: int) -> list[date]:
        start = date(2026, 1, 5)
        allocations = self._make_allocations(total_weeks)
        starts: list[date] = []
        current = start
        for alloc in allocations:
            starts.append(current)
            from datetime import timedelta

            current += timedelta(weeks=alloc.weeks)
        return starts

    def test_calibration_checkpoint_at_phase_transition_with_low_confidence(self) -> None:
        allocations = self._make_allocations(24)
        phase_starts = self._make_phase_starts(24)
        confidence: dict[str, str | None] = {
            "lt2_hr": "low",
            "lt1_hr": "low",
            "cp": None,
        }

        checkpoints = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=confidence,
            goal_event_type="marathon",
        )

        from app.models.enums import CheckpointType

        calibration = [c for c in checkpoints if c.type == CheckpointType.CALIBRATION]
        assert len(calibration) >= 1

    def test_benchmark_checkpoint_at_week_4(self) -> None:
        allocations = self._make_allocations(24)
        phase_starts = self._make_phase_starts(24)

        checkpoints = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=None,
            goal_event_type="marathon",
        )

        from app.models.enums import CheckpointType

        benchmark = [c for c in checkpoints if c.type == CheckpointType.BENCHMARK]
        assert len(benchmark) == 1
        assert benchmark[0].week_number == 4

    def test_progress_review_every_4_weeks(self) -> None:
        allocations = self._make_allocations(24)
        phase_starts = self._make_phase_starts(24)

        checkpoints = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=None,
            goal_event_type="marathon",
        )

        from app.models.enums import CheckpointType

        reviews = [c for c in checkpoints if c.type == CheckpointType.PROGRESS_REVIEW]
        week_numbers = [c.week_number for c in reviews]
        assert week_numbers == [3, 7, 11, 15, 19]

    def test_race_simulation_2_weeks_before_goal(self) -> None:
        allocations = self._make_allocations(24)
        phase_starts = self._make_phase_starts(24)

        checkpoints = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=None,
            goal_event_type="marathon",
        )

        from app.models.enums import CheckpointType

        race_sim = [c for c in checkpoints if c.type == CheckpointType.RACE_SIMULATION]
        assert len(race_sim) == 1
        assert race_sim[0].week_number == 22

    def test_checkpoints_sorted_by_week_number(self) -> None:
        allocations = self._make_allocations(24)
        phase_starts = self._make_phase_starts(24)

        checkpoints = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=None,
            goal_event_type="marathon",
        )

        week_numbers = [c.week_number for c in checkpoints]
        assert week_numbers == sorted(week_numbers)
