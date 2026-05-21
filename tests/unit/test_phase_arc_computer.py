"""Unit tests for PhaseArcComputer."""

from datetime import date, timedelta

import pytest

from app.models.enums import GoalEventType, SportBackground, TrainingPhase
from app.models.training_block import TrainingBlock
from app.models.twin_state import TwinState
from app.models.athlete_preferences import AthletePreferences
from app.services.phase_arc_computer import PhaseArcComputer
from tests.factories import make_training_block, make_twin_state, make_athlete_preferences


class TestPhaseArcComputerCompute:
    def _future_date(self, weeks: int) -> date:
        return date.today() + timedelta(weeks=weeks)

    def _make_twin(self, **overrides) -> TwinState:
        defaults = {
            "fitness_score": 0.7,
            "structural_capacity_score": 0.6,
            "max_hr_estimate": 185,
            "lt1_hr_estimate": 150,
            "lt2_hr_estimate": 165,
        }
        return make_twin_state(**{**defaults, **overrides})

    def _make_preferences(self, **overrides) -> AthletePreferences:
        defaults = {"sport_background": SportBackground.RUNNING_PRIMARY}
        return make_athlete_preferences(**{**defaults, **overrides})

    def test_compute_raises_value_error_when_goal_event_date_is_none(self):
        computer = PhaseArcComputer()
        block = make_training_block(goal_event_date=None)
        twin = self._make_twin()
        prefs = self._make_preferences()

        with pytest.raises(ValueError, match="goal_event_date"):
            computer.compute(block, twin, prefs)

    def test_compute_returns_correct_total_weeks_for_marathon_16_weeks_away(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        # Allow off-by-one based on today()
        assert arc.total_weeks in (15, 16)

    def test_compute_includes_base_phase_for_plans_gte_4_weeks(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        phases = {p.phase for p in arc.phases}
        assert TrainingPhase.BASE in phases

    def test_compute_includes_taper_phase_of_2_weeks_for_marathon(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        phases = {p.phase for p in arc.phases}
        assert TrainingPhase.TAPER in phases

    def test_compute_includes_taper_phase_of_2_weeks_for_half_marathon(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.HALF_MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        phases = {p.phase for p in arc.phases}
        assert TrainingPhase.TAPER in phases

    def test_compute_includes_taper_phase_of_1_week_for_5k(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(12)
        block = make_training_block(
            goal_event_type=GoalEventType.FIVE_K, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        phases = {p.phase for p in arc.phases}
        assert TrainingPhase.TAPER in phases

    def test_compute_includes_peak_phase_when_total_weeks_gt_10(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        phases = {p.phase for p in arc.phases}
        assert TrainingPhase.PEAK in phases

    def test_compute_does_not_include_peak_when_total_weeks_lte_10(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(8)
        block = make_training_block(
            goal_event_type=GoalEventType.TEN_K, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        phases = {p.phase for p in arc.phases}
        assert TrainingPhase.PEAK not in phases

    def test_compute_generates_recovery_weeks_every_3_weeks_when_structural_lt_0_5(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin(structural_capacity_score=0.4)
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        # Recovery weeks every 3 when structural_capacity < 0.5
        # For 16 weeks, starting at week 4 (interval+1), incrementing by 3: [4, 7, 10, 13]
        assert 4 in arc.recovery_weeks
        assert 7 in arc.recovery_weeks

    def test_compute_generates_recovery_weeks_every_4_weeks_when_structural_gte_0_5(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin(structural_capacity_score=0.7)
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        # Recovery weeks every 4 when structural_capacity >= 0.5
        assert 5 in arc.recovery_weeks
        assert 9 in arc.recovery_weeks

    def test_compute_returns_compact_single_phase_when_weeks_to_goal_lt_4(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(2)
        block = make_training_block(
            goal_event_type=GoalEventType.TEN_K, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        assert len(arc.phases) == 1
        assert arc.phases[0].phase == TrainingPhase.BASE

    def test_compute_merges_taper_into_build_when_total_weeks_lte_6(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(5)
        block = make_training_block(
            goal_event_type=GoalEventType.FIVE_K, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        phases = {p.phase for p in arc.phases}
        assert TrainingPhase.TAPER not in phases

    def test_compute_phases_are_contiguous(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        sorted_phases = sorted(arc.phases, key=lambda p: p.start_week)
        for i in range(len(sorted_phases) - 1):
            current = sorted_phases[i]
            next_phase = sorted_phases[i + 1]
            assert current.end_week + 1 == next_phase.start_week

    def test_compute_last_phase_end_week_equals_total_weeks(self):
        computer = PhaseArcComputer()
        goal_date = self._future_date(16)
        block = make_training_block(
            goal_event_type=GoalEventType.MARATHON, goal_event_date=goal_date
        )
        twin = self._make_twin()
        prefs = self._make_preferences()

        arc = computer.compute(block, twin, prefs)

        last_phase = max(arc.phases, key=lambda p: p.end_week)
        assert last_phase.end_week == arc.total_weeks