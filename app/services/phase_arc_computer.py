from datetime import date, timedelta
from typing import Optional

from app.models.training_block import TrainingBlock
from app.models.twin_state import TwinState
from app.models.athlete_preferences import AthletePreferences
from app.models.enums import (
    GoalEventType,
    SportBackground,
    TrainingPhase,
)
from app.schemas.plan_generation import PhaseArc, PhaseArcPhase


PHASE_ARC_VERSION = "v1"


class PhaseArcComputer:
    def compute(
        self,
        training_block: TrainingBlock,
        twin_state: TwinState,
        preferences: AthletePreferences,
    ) -> PhaseArc:
        goal_event_date = training_block.goal_event_date
        if goal_event_date is None:
            raise ValueError("TrainingBlock.goal_event_date is required for phase arc computation")

        today = date.today()
        weeks_to_goal = self._weeks_between(today, goal_event_date)

        if weeks_to_goal < 4:
            # Very short timeline — return a compact plan with taper compressed
            total_weeks = max(1, weeks_to_goal)
            phases = [PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=total_weeks)]
            return PhaseArc(total_weeks=total_weeks, phases=phases, recovery_weeks=[])

        goal_event_type = training_block.goal_event_type
        fitness_score = twin_state.fitness_score
        structural_capacity = twin_state.structural_capacity_score
        sport_background = preferences.sport_background

        # Base phase: minimum 4 weeks unless compressed by timeline
        min_base_weeks = 4
        # Taper: 2 weeks for races, 1 week for shorter events
        if goal_event_type in (
            GoalEventType.MARATHON,
            GoalEventType.HALF_MARATHON,
            GoalEventType.ULTRA,
        ):
            taper_weeks = 2
        else:
            taper_weeks = 1

        # Build phase: remaining weeks after base and taper
        build_weeks = max(1, weeks_to_goal - min_base_weeks - taper_weeks)

        # Recovery weeks: every 3-4 weeks based on structural capacity
        recovery_weeks = self._compute_recovery_weeks(
            weeks_to_goal, structural_capacity, sport_background
        )

        phases = [
            PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=min_base_weeks),
            PhaseArcPhase(
                phase=TrainingPhase.BUILD,
                start_week=min_base_weeks + 1,
                end_week=min_base_weeks + build_weeks,
            ),
        ]

        # Insert peak phase if sufficient time (> 10 weeks total)
        if weeks_to_goal > 10:
            peak_start = min_base_weeks + build_weeks + 1
            peak_weeks = min(3, weeks_to_goal - peak_start - taper_weeks + 1)
            phases.append(
                PhaseArcPhase(
                    phase=TrainingPhase.PEAK,
                    start_week=peak_start,
                    end_week=peak_start + peak_weeks - 1,
                )
            )
            taper_start = peak_start + peak_weeks
        else:
            taper_start = min_base_weeks + build_weeks + 1

        # Taper phase
        if weeks_to_goal > 6:
            phases.append(
                PhaseArcPhase(
                    phase=TrainingPhase.TAPER,
                    start_week=taper_start,
                    end_week=weeks_to_goal,
                )
            )
        else:
            # Merge taper into build for very short plans
            phases[-1] = PhaseArcPhase(
                phase=TrainingPhase.BUILD,
                start_week=phases[-1].start_week,
                end_week=weeks_to_goal,
            )

        return PhaseArc(total_weeks=weeks_to_goal, phases=phases, recovery_weeks=recovery_weeks)

    def _weeks_between(self, start: date, end: date) -> int:
        delta = end - start
        return max(1, delta.days // 7)

    def _compute_recovery_weeks(
        self,
        total_weeks: int,
        structural_capacity: float,
        sport_background: Optional[SportBackground],
    ) -> list[int]:
        # Recovery every 3-4 weeks based on structural durability
        interval = 3 if structural_capacity < 0.5 else 4
        recovery = []
        week = interval + 1
        while week < total_weeks:
            recovery.append(week)
            week += interval
        return recovery