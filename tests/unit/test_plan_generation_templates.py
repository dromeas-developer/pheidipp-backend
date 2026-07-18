"""Unit tests for the deterministic plan-generation templates.

The Phase-1.4 plan codifies that ``PlanGenerationService`` is pure
Python — no LLM, no external API. The templates module houses the
fixed inputs to that engine (phase proportions, training-length-gate
thresholds, checkpoint scheduling, structural session rules).

These tests are intentionally pure (no DB, no HTTP). They cover:

* ``evaluate_training_length_gate`` — goal_too_far action, fitness
  insufficient-for-distance action, success action.
* ``allocate_race_event_phases`` — five-phase template, fixed-width
  taper + race-week, weekly-hours summing to ``total_weeks``,
  pathological short-plan fallback.
* ``derive_experience_level`` — year-based bucket mapping.
* Schedule helpers — ``to_phase_definition_record``, ``schedule_checkpoints``,
  ``_phase_starting_week``, ``_compute_phase_date_ranges`` (via
  indirect assertions on ``_compute_phase_date_ranges`` semantics).
* Quality / sandwiched session-type constants match the architecture
  closed ontology.

Reference plan:
docs/implementation/phase-1/phase-1-4-p1-plan-generation.md
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from app.models.enums import (
    CheckpointType,
    PhaseLabel,
    SessionType,
)
from app.services.plan_generation_templates import (
    GATE_THRESHOLDS,
    QUALITY_SESSION_TYPES,
    RACE_EVENT_FIXED_TAIL_WEEKS,
    RACE_EVENT_PROPORTIONS,
    SANDWICHED_SESSION_TYPES,
    TrainingLengthGateResult,
    allocate_race_event_phases,
    derive_experience_level,
    evaluate_training_length_gate,
    schedule_checkpoints,
    to_phase_definition_record,
)


# ---------------------------------------------------------------------------
# derive_experience_level — the year-bucketed mapper.
# ---------------------------------------------------------------------------


class TestDeriveExperienceLevel:
    """The thresholds are < 2 -> novice, 2..5 -> intermediate, > 5 -> experienced."""

    @pytest.mark.parametrize("years", [0, 1])
    def test_below_two_years_is_novice(self, years: int) -> None:
        assert derive_experience_level(years) == "novice"

    @pytest.mark.parametrize("years", [2, 3, 5])
    def test_two_to_five_years_is_intermediate(self, years: int) -> None:
        assert derive_experience_level(years) == "intermediate"

    @pytest.mark.parametrize("years", [6, 10, 25])
    def test_above_five_years_is_experienced(self, years: int) -> None:
        assert derive_experience_level(years) == "experienced"


# ---------------------------------------------------------------------------
# QUALITY_SESSION_TYPES / SANDWICHED_SESSION_TYPES
# ---------------------------------------------------------------------------


class TestQualityAndSandwichedSets:
    """Closed ontologies — match the architecture structural rules."""

    def test_quality_set_contains_threshold_and_vo2max(self) -> None:
        assert SessionType.THRESHOLD in QUALITY_SESSION_TYPES
        assert SessionType.VO2MAX in QUALITY_SESSION_TYPES

    def test_quality_set_contains_long_run(self) -> None:
        assert SessionType.LONG_RUN in QUALITY_SESSION_TYPES

    def test_sandwiched_set_is_sandwiched_only(self) -> None:
        # Only threshold + vo2max — tempo is quality but not strictly
        # sandwiched between easy/rest.
        assert SANDWICHED_SESSION_TYPES == frozenset(
            {SessionType.THRESHOLD, SessionType.VO2MAX}
        )

    def test_sandwiched_is_subset_of_quality(self) -> None:
        """Invariant: every sandwiched session is also a quality session."""
        assert SANDWICHED_SESSION_TYPES.issubset(QUALITY_SESSION_TYPES)


# ---------------------------------------------------------------------------
# evaluate_training_length_gate
# ---------------------------------------------------------------------------


class TestTrainingLengthGateRejectsGoalTooFar:
    """``propose_intermediate`` action when ``weeks_until_goal > threshold``."""

    @pytest.mark.parametrize(
        "goal_event_type,experience_level,threshold",
        [
            ("marathon", "novice", 20),
            ("marathon", "intermediate", 24),
            ("marathon", "experienced", 30),
            ("half_marathon", "novice", 16),
            ("half_marathon", "experienced", 24),
            ("10k", "novice", 12),
            ("ultra", "experienced", 36),
            ("trail_race", "intermediate", 24),
        ],
    )
    def test_threshold_plus_one_week_is_rejected(
        self,
        goal_event_type: str,
        experience_level: str,
        threshold: int,
    ) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=threshold + 1,
            fitness_level=4,
            goal_event_type=goal_event_type,
            experience_level=experience_level,
        )
        assert isinstance(result, TrainingLengthGateResult)
        assert result.action == "propose_intermediate"
        assert result.gate_reason == "goal_too_far"
        assert result.message  # human-readable message populated
        assert result.intermediate_objectives is not None
        assert len(result.intermediate_objectives) > 0


class TestTrainingLengthGateRejectsInsufficientFitness:
    """``propose_shorter_goal`` when short horizon + low fitness."""

    @pytest.mark.parametrize(
        "goal_event_type,fitness_level",
        [
            ("marathon", 1),
            ("marathon", 2),
            ("5k", 1),
        ],
    )
    def test_low_fitness_short_horizon_rejected(
        self,
        goal_event_type: str,
        fitness_level: int,
    ) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=4,
            fitness_level=fitness_level,
            goal_event_type=goal_event_type,
            experience_level="intermediate",
        )
        assert result.action == "propose_shorter_goal"
        assert result.gate_reason == "fitness_insufficient_for_distance"
        assert result.message


class TestTrainingLengthGateProceed:
    """``proceed`` action when both criteria pass."""

    @pytest.mark.parametrize("experience_level", ["novice", "intermediate", "experienced"])
    def test_within_threshold_long_horizon_proceeds(self, experience_level: str) -> None:
        threshold = GATE_THRESHOLDS["marathon"][experience_level]
        result = evaluate_training_length_gate(
            weeks_until_goal=threshold,  # exactly at threshold
            fitness_level=5,
            goal_event_type="marathon",
            experience_level=experience_level,
        )
        assert result.action == "proceed"
        assert result.gate_reason is None
        assert result.message == ""

    def test_long_horizon_within_custom_threshold_proceeds(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=20,
            fitness_level=4,
            goal_event_type="custom",
            experience_level="intermediate",
        )
        assert result.action == "proceed"


class TestTrainingLengthGateUnknownEventType:
    """Unknown ``goal_event_type`` falls back to
    ``TRAINING_LENGTH_GATE_DEFAULT_WEEKS`` semantics.
    """

    def test_unknown_event_type_uses_default_threshold(self) -> None:
        """24 weeks exactly — equals the default threshold — should proceed."""
        result = evaluate_training_length_gate(
            weeks_until_goal=24,
            fitness_level=5,
            goal_event_type="not_a_real_event",
            experience_level="intermediate",
        )
        assert result.action == "proceed"

    def test_unknown_event_type_default_threshold_rejects_too_far(self) -> None:
        result = evaluate_training_length_gate(
            weeks_until_goal=30,
            fitness_level=4,
            goal_event_type="not_a_real_event",
            experience_level="intermediate",
        )
        assert result.action == "propose_intermediate"


# ---------------------------------------------------------------------------
# allocate_race_event_phases — five-phase template.
# ---------------------------------------------------------------------------


class TestRaceEventPhaseAllocation:
    """Race-event template allocations across the plan span."""

    def test_allocations_cover_full_total_weeks(self) -> None:
        for total in [4, 8, 12, 16, 20, 24, 30]:
            allocations = allocate_race_event_phases(total_weeks=total)
            allocated = sum(a.weeks for a in allocations)
            assert allocated == total, (
                f"total_weeks={total} should equal sum(weeks); got {allocated}"
            )

    def test_five_phases_for_normal_plan(self) -> None:
        """Normal plans produce 5 phases in plan order."""
        allocations = allocate_race_event_phases(total_weeks=20)
        assert len(allocations) == 5
        labels = [a.label for a in allocations]
        assert labels == [
            PhaseLabel.AEROBIC_BASE,
            PhaseLabel.THRESHOLD_BUILD,
            PhaseLabel.SPECIFIC_ENDURANCE,
            PhaseLabel.TAPER,
            PhaseLabel.RACE_WEEK,
        ]

    def test_taper_is_two_weeks(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=20)
        taper = next(a for a in allocations if a.label is PhaseLabel.TAPER)
        assert taper.weeks == 2

    def test_race_week_is_one_week(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=20)
        race_week = next(
            a for a in allocations if a.label is PhaseLabel.RACE_WEEK
        )
        assert race_week.weeks == 1

    def test_flexible_proportions_roughly_match_template(self) -> None:
        """For ``total_weeks=20`` the flexible portion is
        ``20 - RACE_EVENT_FIXED_TAIL_WEEKS = 17`` weeks. The
        flexible weights are 40% / 30% / 15% of 85%, so:

        base ~ 0.40/0.85 * 17 ≈ 8
        threshold ~ 0.30/0.85 * 17 ≈ 6
        race_specific = 17 - 8 - 6 ≈ 3

        Allowing for integer rounding we require each flexible
        phase to fall within ±1 week of the brand formula.
        """
        allocations = allocate_race_event_phases(total_weeks=20)
        flex = 20 - RACE_EVENT_FIXED_TAIL_WEEKS
        weight_scale = 0.85
        base_expected = round(flex * RACE_EVENT_PROPORTIONS["base"] / weight_scale)
        threshold_expected = round(
            flex * RACE_EVENT_PROPORTIONS["threshold"] / weight_scale
        )
        base = next(a for a in allocations if a.label is PhaseLabel.AEROBIC_BASE)
        thresh = next(
            a for a in allocations if a.label is PhaseLabel.THRESHOLD_BUILD
        )
        assert base.weeks == pytest.approx(base_expected, abs=1)
        assert thresh.weeks == pytest.approx(threshold_expected, abs=1)

    def test_short_plan_falls_back_to_taper_and_race_week(self) -> None:
        """When ``total_weeks <= 3``, the flexible proportions can't
        fit (33% of 17w is 5.6w, but with only 2 flexible weeks
        allocated we'd exceed the plan). A pathological short plan
        returns just TAPER + RACE_WEEK."""
        allocations = allocate_race_event_phases(total_weeks=3)
        assert len(allocations) == 2
        labels = [a.label for a in allocations]
        assert PhaseLabel.TAPER in labels
        assert PhaseLabel.RACE_WEEK in labels

    def test_total_weeks_zero_or_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            allocate_race_event_phases(total_weeks=0)
        with pytest.raises(ValueError):
            allocate_race_event_phases(total_weeks=-3)

    def test_each_allocation_carries_primary_focus(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=12)
        for allocation in allocations:
            assert allocation.primary_focus
            assert allocation.objectives
            assert allocation.distribution
            assert 0.0 <= allocation.specificity <= 1.0
            assert allocation.weekly_session_count >= 0


# ---------------------------------------------------------------------------
# to_phase_definition_record — JSON-shape converter.
# ---------------------------------------------------------------------------


class TestToPhaseDefinitionRecord:
    """PhaseDefinitionRecord carries the persisted JSON shape."""

    def test_record_carries_canonical_keys(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=12)
        for allocation in allocations:
            record = to_phase_definition_record(allocation)
            assert record.phase == allocation.label.value
            assert record.objectives == list(allocation.objectives)
            assert record.weeks == int(allocation.weeks)
            assert record.distribution == dict(allocation.distribution)
            assert record.specificity == float(allocation.specificity)
            assert record.approach in {"linear", "undulating"}
            assert record.recovery_cycle in {"frequent", "moderate"}

    def test_taper_and_race_week_use_linear_approach(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=12)
        taper = next(a for a in allocations if a.label is PhaseLabel.TAPER)
        race_week = next(
            a for a in allocations if a.label is PhaseLabel.RACE_WEEK
        )
        assert to_phase_definition_record(taper).approach == "linear"
        assert to_phase_definition_record(taper).recovery_cycle == "frequent"
        assert to_phase_definition_record(race_week).approach == "linear"


# ---------------------------------------------------------------------------
# schedule_checkpoints — algorithm under the architecture's rules.
# ---------------------------------------------------------------------------


class _CI:
    """Confidence input shortcut — every metric turns low so calibration
    fires at every transition."""

    @staticmethod
    def lt2_low() -> dict[str, Any]:
        return {
            "lt1_hr": "low",
            "lt2_hr": "low",
            "lt1_power": None,
            "cp": "low",
        }


class TestCheckpointScheduling:
    """Coverage of the scheduling algorithm's rules."""

    def test_no_two_checkpoints_in_same_week(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=24)
        phase_starts = [
            date(2026, 7, 1) + timedelta(days=sum(a.weeks for a in allocations[:i]) * 7)
            for i in range(len(allocations))
        ]
        records = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=_CI.lt2_low(),
            goal_event_type="marathon",
        )
        weeks = [r.week_number for r in records]
        assert len(weeks) == len(set(weeks)), (
            f"duplicate week numbers found: {weeks}"
        )

    def test_includes_at_least_one_calibration_on_transition(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=16)
        phase_starts = [
            date(2026, 7, 1) + timedelta(days=sum(a.weeks for a in allocations[:i]) * 7)
            for i in range(len(allocations))
        ]
        records = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=_CI.lt2_low(),
            goal_event_type="marathon",
        )
        types = {r.type for r in records}
        assert CheckpointType.CALIBRATION in types

    def test_includes_benchmark_and_progress_review_for_long_plan(self) -> None:
        """A 16+-week plan must include benchmark + progress_review."""
        allocations = allocate_race_event_phases(total_weeks=24)
        phase_starts = [
            date(2026, 7, 1) + timedelta(days=sum(a.weeks for a in allocations[:i]) * 7)
            for i in range(len(allocations))
        ]
        records = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=_CI.lt2_low(),
            goal_event_type="marathon",
        )
        types = {r.type for r in records}
        assert CheckpointType.BENCHMARK in types
        assert CheckpointType.PROGRESS_REVIEW in types

    def test_records_are_sorted_by_week(self) -> None:
        allocations = allocate_race_event_phases(total_weeks=24)
        phase_starts = [
            date(2026, 7, 1) + timedelta(days=sum(a.weeks for a in allocations[:i]) * 7)
            for i in range(len(allocations))
        ]
        records = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=_CI.lt2_low(),
            goal_event_type="marathon",
        )
        weeks = [r.week_number for r in records]
        assert weeks == sorted(weeks)

    def test_race_simulation_included_for_long_plan(self) -> None:
        """Long plans schedule a race simulation 2 weeks before the goal,
        but only when not colliding with a calibration checkpoint.

        ``total_weeks=18`` is chosen because under HIGH twin metric
        confidence (no calibration at phase transitions), the schedule
        produces {BENCHMARK (week 4), PROGRESS_REVIEW (week 7, 11, 15),
        RACE_SIMULATION (week 16)} — exercising all three
        "longplan"-eligible checkpoint types without collisions.

        With LOW twin confidence (the bootstrap state produced at
        onboarding), every phase transition fires a calibration
        checkpoint and the race-simulation slot (week 16) collides
        with the calibration at TAPER start (also week 16). The
        algorithm's "no two checkpoints in the same week" invariant
        then drops the race simulation. With HIGH confidence the
        constraint doesn't fire and the race simulation is preserved.
        """
        allocations = allocate_race_event_phases(total_weeks=18)
        phase_starts = [
            date(2026, 7, 1) + timedelta(days=sum(a.weeks for a in allocations[:i]) * 7)
            for i in range(len(allocations))
        ]
        high_confidence: dict[str, str | None] = {
            "lt1_hr": "high",
            "lt2_hr": "high",
            "lt1_power": "high",
            "cp": "high",
        }
        records = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=high_confidence,
            goal_event_type="marathon",
        )
        types = {r.type for r in records}
        assert CheckpointType.RACE_SIMULATION in types
