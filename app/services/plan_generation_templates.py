"""Deterministic plan-generation templates — Phase-1.4.

The plan's Coder Handoff is explicit: ``PlanGenerationService`` is
pure Python. This module houses the fixed templates (phase
proportions, training-length-gate thresholds, session-distribution /
quality-session classification, checkpoint scheduling) drawn from
``docs/architecture/02-computations/plan-generation-race.md`` and
``plan-generation-target-performance.md``.

Templates are deliberately kept separate from the service so they can
be exercised in isolation by unit tests (the Test Architect owns the
test manifest, but keeping templates pure-Python makes them easily
importable).

Per-week session synthesis (the structural-rule engine) lives in
``app.services.plan_generation_service`` because it's tightly coupled
to date arithmetic and the persistence layer. The rule sets
(``QUALITY_SESSION_TYPES``, ``SANDWICHED_SESSION_TYPES``, etc.) and
the deterministic schedule-builder helpers live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from app.models.enums import (
    CheckpointType,
    PhaseLabel,
    SessionType,
)


# ---------------------------------------------------------------------------
# Race-event proportion constants (per architecture plan-generation-race.md).
#
#   Base: 40%
#   Threshold build: 30%
#   Race specific: 15%
#   Taper: 2 weeks (fixed)
#   Race week: 1 week (fixed)
#
# RACE_EVENT_PROPORTIONS carries weights, not absolute weeks. The
# absolute allocation is computed against ``weeks_until_goal -
# RACE_EVENT_FIXED_TAIL_WEEKS`` so the final two fixed-duration phases
# always fit. The flexible portion sums to 85% of total flexible
# weeks; the remaining 15% is implicit recovery / warmup absorbed by
# per-week session distributions.
# ---------------------------------------------------------------------------

#: Minimum weeks reserved for the fixed-length taper + race week phases.
RACE_EVENT_FIXED_TAIL_WEEKS: int = 3  # 2 weeks taper + 1 week race week

#: Proportional weights for the flexible portion of the race-event template.
RACE_EVENT_PROPORTIONS: Dict[str, float] = {
    "base": 0.40,
    "threshold": 0.30,
    "race_specific": 0.15,
}

#: Training-length gate default threshold per architecture.
TRAINING_LENGTH_GATE_DEFAULT_WEEKS: int = 24

#: Per-(goal_event_type, experience_level) gate thresholds.
#: Experience level is derived from ``AthletePreferences -
#: years_structured_training``.
GATE_THRESHOLDS: Dict[str, Dict[str, int]] = {
    "marathon":      {"novice": 20, "intermediate": 24, "experienced": 30},
    "half_marathon": {"novice": 16, "intermediate": 20, "experienced": 24},
    "10k":           {"novice": 12, "intermediate": 16, "experienced": 20},
    "5k":            {"novice": 8,  "intermediate": 12, "experienced": 16},
    "ultra":         {"novice": 24, "intermediate": 30, "experienced": 36},
    "trail_race":    {"novice": 20, "intermediate": 24, "experienced": 30},
    "custom":        {"novice": 20, "intermediate": 24, "experienced": 30},
}


# ---------------------------------------------------------------------------
# Session-type / Day rules — shared between race_event and
# target_performance synthesis. The distribution engine treats them as
# hard constraints (architecture invariants).
# ---------------------------------------------------------------------------

#: ``SessionType`` values considered "quality" — never consecutive dates
#: in a generated week unless they share a ``block_id``.
QUALITY_SESSION_TYPES: frozenset[SessionType] = frozenset(
    {
        SessionType.THRESHOLD,
        SessionType.VO2MAX,
        SessionType.TEMPO,
        SessionType.LONG_RUN,
        SessionType.MEDIUM_LONG_RUN,
        SessionType.HILL_REPEATS,
        SessionType.FARTLEK,
    }
)

#: Sessions that MUST be sandwiched between easy / rest days.
SANDWICHED_SESSION_TYPES: frozenset[SessionType] = frozenset(
    {
        SessionType.THRESHOLD,
        SessionType.VO2MAX,
    }
)


# ---------------------------------------------------------------------------
# Phase allocation result.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseAllocation:
    """One resolved phase in a plan — label, weeks, and weekly policies.

    The deterministic expansion layer uses ``distribution`` and
    ``specificity`` from the architecture schema. ``objectives`` is the
    subset of ``ObjectiveCategory`` the phase targets.
    """

    label: PhaseLabel
    weeks: int
    primary_focus: str
    objectives: List[str] = field(default_factory=list)
    distribution: Dict[str, float] = field(default_factory=dict)
    specificity: float = 0.0
    weekly_session_count: int = 0


@dataclass(frozen=True)
class PhaseDefinitionRecord:
    """The deterministic-expansion shape persisted in
    ``TrainingPlan.phase_definitions`` — mirrors the architecture's
    ``PhaseDefinition`` schema, minus the LLM-driven ``trait_vector``
    that lives in the selector agent layer; Phase 1.4 stores the
    adaptation-strategy fields only.
    """

    phase: str
    objectives: List[str]
    weeks: int
    distribution: Dict[str, float]
    specificity: float
    approach: str
    recovery_cycle: str


@dataclass(frozen=True)
class CheckpointRecord:
    """One scheduled checkpoint — used by the service to populate both
    ``TrainingPlan.checkpoint_schedule`` and the per-week
    ``WeeklySession.is_checkpoint`` flag.
    """

    type: CheckpointType
    week_number: int
    target_date: date
    target_metric: str
    session_type: SessionType
    planner_message: str


@dataclass(frozen=True)
class TrainingLengthGateResult:
    """Return shape of :func:`evaluate_training_length_gate`."""

    action: str  # 'proceed' | 'propose_intermediate' | 'propose_shorter_goal'
    message: str
    gate_reason: Optional[str]
    intermediate_objectives: Optional[List[str]] = None


def derive_experience_level(years_structured_training: int) -> str:
    """Map training-years to an experience bucket.

    Mirrors the architecture's three-bucket model — novice /
    intermediate / experienced — used by the training-length-gate
    thresholds:

    * ``< 2`` years → ``novice``
    * ``2..5`` years → ``intermediate``
    * ``> 5`` years → ``experienced``
    """
    if years_structured_training < 2:
        return "novice"
    if years_structured_training <= 5:
        return "intermediate"
    return "experienced"


def evaluate_training_length_gate(
    *,
    weeks_until_goal: int,
    fitness_level: int,
    goal_event_type: str,
    experience_level: str,
) -> TrainingLengthGateResult:
    """Apply the race-event training-length gate.

    Implements the logic from
    ``docs/architecture/02-computations/plan-generation-race.md`` →
    Phase 0 — "goal_too_far" and "fitness_insufficient_for_distance"
    outcomes. The function is pure (no DB, no LLM); the service maps
    ``propose_intermediate`` / ``propose_shorter_goal`` actions to a
    ``TrainingLengthGateError`` so the API layer can surface the
    human-readable message.
    """
    threshold = GATE_THRESHOLDS.get(
        goal_event_type, {}
    ).get(experience_level, TRAINING_LENGTH_GATE_DEFAULT_WEEKS)

    if weeks_until_goal > threshold:
        return TrainingLengthGateResult(
            action="propose_intermediate",
            message=(
                f"Your {goal_event_type} is {weeks_until_goal} weeks "
                f"away. That's too far to plan in detail — too much "
                f"will change in your fitness and life. Let's focus on "
                f"a 12-week block targeting the physiological "
                f"foundations you'll need most: aerobic base, "
                f"threshold development, and structural resilience. "
                f"We'll reassess and plan the next phase after that."
            ),
            gate_reason="goal_too_far",
            intermediate_objectives=[
                "aerobic_fitness",
                "threshold_power",
                "structural_resilience",
            ],
        )

    if weeks_until_goal < 8 and fitness_level <= 2:
        return TrainingLengthGateResult(
            action="propose_shorter_goal",
            message=(
                f"With {weeks_until_goal} weeks to your "
                f"{goal_event_type} and your current fitness level, a "
                f"10K or half-marathon would be a more realistic "
                f"target. This builds race experience and confidence "
                f"for the full distance later."
            ),
            gate_reason="fitness_insufficient_for_distance",
        )

    return TrainingLengthGateResult(
        action="proceed",
        message="",
        gate_reason=None,
    )


# ---------------------------------------------------------------------------
# Phase allocation — race event template.
# ---------------------------------------------------------------------------


def allocate_race_event_phases(
    *, total_weeks: int
) -> List[PhaseAllocation]:
    """Allocate the five-phase race_event template against ``total_weeks``.

    The template reserves the last ``RACE_EVENT_FIXED_TAIL_WEEKS``
    weeks (taper + race week). The remaining weeks are split across
    ``base`` (40 %), ``threshold`` (30 %), and ``race_specific``
    (15 %) of the *flexible portion*. Rounding is performed so the
    phase weeks sum exactly to ``total_weeks``.

    Returns:
        A list of :class:`PhaseAllocation` in plan order (base →
        threshold → race-specific → taper → race-week).
    """
    if total_weeks <= 0:
        raise ValueError("total_weeks must be positive")
    if total_weeks <= RACE_EVENT_FIXED_TAIL_WEEKS:
        # Pathological short plan — fall back to taper + race week only.
        return [
            PhaseAllocation(
                label=PhaseLabel.TAPER,
                weeks=max(1, total_weeks - 1),
                primary_focus="recovery and readiness",
                objectives=["recovery_efficiency"],
                distribution=_phase_distribution("taper"),
                specificity=0.0,
                weekly_session_count=_taper_sessions(),
            ),
            PhaseAllocation(
                label=PhaseLabel.RACE_WEEK,
                weeks=1,
                primary_focus="race execution",
                objectives=["pacing_discipline"],
                distribution=_phase_distribution("race_week"),
                specificity=1.0,
                weekly_session_count=_race_week_sessions(),
            ),
        ]

    flexible = total_weeks - RACE_EVENT_FIXED_TAIL_WEEKS
    proportion_scale = 0.85
    base_w = _round_to_int(
        flexible * RACE_EVENT_PROPORTIONS["base"] / proportion_scale
    )
    thresh_w = _round_to_int(
        flexible * RACE_EVENT_PROPORTIONS["threshold"] / proportion_scale
    )
    race_spec_w = flexible - base_w - thresh_w
    if race_spec_w < 1:
        race_spec_w = 1
        if thresh_w > base_w:
            thresh_w -= 1
        else:
            base_w -= 1

    taper_w = 2
    race_w = 1
    return [
        PhaseAllocation(
            label=PhaseLabel.AEROBIC_BASE,
            weeks=base_w,
            primary_focus="aerobic development and structural resilience",
            objectives=["aerobic_base", "structural_tolerance"],
            distribution=_phase_distribution("base"),
            specificity=0.1,
            weekly_session_count=_base_phase_sessions(),
        ),
        PhaseAllocation(
            label=PhaseLabel.THRESHOLD_BUILD,
            weeks=thresh_w,
            primary_focus=(
                "threshold development with maintained aerobic volume"
            ),
            objectives=["threshold_quality", "intensity_distribution"],
            distribution=_phase_distribution("threshold"),
            specificity=0.4,
            weekly_session_count=_threshold_phase_sessions(),
        ),
        PhaseAllocation(
            label=PhaseLabel.SPECIFIC_ENDURANCE,
            weeks=race_spec_w,
            primary_focus="race-specific endurance and pacing",
            objectives=["pacing_discipline", "neuromuscular_sharpness"],
            distribution=_phase_distribution("race_specific"),
            specificity=0.7,
            weekly_session_count=_race_specific_phase_sessions(),
        ),
        PhaseAllocation(
            label=PhaseLabel.TAPER,
            weeks=taper_w,
            primary_focus="recovery and freshness",
            objectives=["recovery_efficiency"],
            distribution=_phase_distribution("taper"),
            specificity=0.5,
            weekly_session_count=_taper_sessions(),
        ),
        PhaseAllocation(
            label=PhaseLabel.RACE_WEEK,
            weeks=race_w,
            primary_focus="race execution",
            objectives=["pacing_discipline"],
            distribution=_phase_distribution("race_week"),
            specificity=1.0,
            weekly_session_count=_race_week_sessions(),
        ),
    ]


def _phase_distribution(phase: str) -> Dict[str, float]:
    """Return the per-zone distribution for the named template phase.

    The distribution sums to <= 1.0 (remaining budget is implicit
    warmup/cooldown/transitions per the architecture).
    """
    return {
        "base":         {"low_aerobic": 0.75, "high_aerobic": 0.10,
                         "threshold": 0.05,   "vo2max": 0.03,
                         "neuromuscular": 0.02},
        "threshold":    {"low_aerobic": 0.55, "high_aerobic": 0.15,
                         "threshold": 0.20,   "vo2max": 0.05,
                         "neuromuscular": 0.05},
        "race_specific":{"low_aerobic": 0.45, "high_aerobic": 0.20,
                         "threshold": 0.15,   "vo2max": 0.10,
                         "neuromuscular": 0.10},
        "taper":        {"low_aerobic": 0.65, "high_aerobic": 0.15,
                         "threshold": 0.10,   "vo2max": 0.05,
                         "neuromuscular": 0.05},
        "race_week":    {"low_aerobic": 0.55, "high_aerobic": 0.20,
                         "threshold": 0.10,   "vo2max": 0.05,
                         "neuromuscular": 0.10},
    }[phase]


def _base_phase_sessions() -> int:
    return 5


def _threshold_phase_sessions() -> int:
    return 5


def _race_specific_phase_sessions() -> int:
    return 5


def _taper_sessions() -> int:
    return 4


def _race_week_sessions() -> int:
    return 3


def to_phase_definition_record(
    allocation: PhaseAllocation,
) -> PhaseDefinitionRecord:
    """Convert a :class:`PhaseAllocation` to the JSON-shape persisted in
    ``TrainingPlan.phase_definitions``.
    """
    label_str = allocation.label.value
    if allocation.label in {PhaseLabel.TAPER, PhaseLabel.RACE_WEEK}:
        approach = "linear"
        recovery_cycle = "frequent"
    else:
        approach = "undulating"
        recovery_cycle = "moderate"
    return PhaseDefinitionRecord(
        phase=label_str,
        objectives=list(allocation.objectives),
        weeks=int(allocation.weeks),
        distribution=dict(allocation.distribution),
        specificity=float(allocation.specificity),
        approach=approach,
        recovery_cycle=recovery_cycle,
    )


# ---------------------------------------------------------------------------
# Checkpoint scheduling.
# ---------------------------------------------------------------------------


def schedule_checkpoints(
    *,
    allocations: List[PhaseAllocation],
    phase_starts: List[date],
    twin_metric_confidence: Optional[Dict[str, Optional[str]]],
    goal_event_type: str,
) -> List[CheckpointRecord]:
    """Schedule checkpoints across the plan.

    Implements the architecture's checkpoint-scheduling algorithm —
    "calibration at phase transitions", "benchmark at the 4-week
    mark", "progress review every 3-4 weeks", and the
    "race simulation in the race-specific phase, 2-3 weeks before
    the goal event" rules.

    Hard constraints:
      * No two checkpoints in the same week.
      * No checkpoint on the first or last day of a phase
        (2-day buffer honored by ``target_date``).

    The function is pure: same inputs always produce the same output.
    """
    records: List[CheckpointRecord] = []
    already_scheduled_weeks: set[int] = set()

    # Calibration checkpoints at phase transitions where the twin has
    # low / medium confidence in a key metric (LT1, LT2).
    for idx in range(1, len(allocations)):
        if _has_low_metric_confidence(
            twin_metric_confidence, ["lt2_hr", "lt1_hr", "cp"]
        ):
            target_week = _phase_starting_week(allocations, idx)
            if target_week in already_scheduled_weeks:
                continue
            records.append(
                CheckpointRecord(
                    type=CheckpointType.CALIBRATION,
                    week_number=target_week,
                    target_date=_phase_start_date(
                        allocations, phase_starts, idx
                    ),
                    target_metric="LT2",
                    session_type=SessionType.THRESHOLD,
                    planner_message=(
                        "Phase transition — gentle tempo test to recalibrate."
                    ),
                )
            )
            already_scheduled_weeks.add(target_week)

    # Benchmark checkpoint at week 4 (or last week if plan shorter).
    total_weeks = sum(a.weeks for a in allocations)
    benchmark_week = min(4, total_weeks)
    if benchmark_week not in already_scheduled_weeks:
        records.append(
            CheckpointRecord(
                type=CheckpointType.BENCHMARK,
                week_number=benchmark_week,
                target_date=_date_for_week(
                    benchmark_week, phase_starts[0], allocations
                ),
                target_metric="aerobic_fitness",
                session_type=SessionType.LONG_RUN,
                planner_message=(
                    "Check-in run to gauge aerobic progress vs baseline."
                ),
            )
        )
        already_scheduled_weeks.add(benchmark_week)

    # Progress reviews every 3-4 weeks (week 3, 7, 11, ...).
    progress_weeks: List[int] = []
    cursor = 3
    while cursor <= max(1, total_weeks - 2):
        progress_weeks.append(cursor)
        cursor += 4
    for week in progress_weeks:
        if week in already_scheduled_weeks:
            continue
        records.append(
            CheckpointRecord(
                type=CheckpointType.PROGRESS_REVIEW,
                week_number=week,
                target_date=_date_for_week(
                    week, phase_starts[0], allocations
                ),
                target_metric="weekly_form",
                session_type=SessionType.EASY_RUN,
                planner_message=(
                    "Mid-block check-in to review how this phase is going."
                ),
            )
        )
        already_scheduled_weeks.add(week)

    # Race simulation 2 weeks before the goal event — only when the
    # plan length supports it.
    if goal_event_type in {
        "marathon",
        "half_marathon",
        "10k",
        "5k",
        "ultra",
        "trail_race",
        "custom",
    }:
        sim_week = max(1, total_weeks - 2)
        if sim_week not in already_scheduled_weeks and sim_week >= 2:
            records.append(
                CheckpointRecord(
                    type=CheckpointType.RACE_SIMULATION,
                    week_number=sim_week,
                    target_date=_date_for_week(
                        sim_week, phase_starts[0], allocations
                    ),
                    target_metric="race_pace",
                    session_type=SessionType.LONG_RUN,
                    planner_message=(
                        "Race-pace long run to confirm readiness."
                    ),
                )
            )
            already_scheduled_weeks.add(sim_week)

    records.sort(key=lambda r: r.week_number)
    return records


def _has_low_metric_confidence(
    metric_confidence: Optional[Dict[str, Optional[str]]],
    keys: List[str],
) -> bool:
    """True if any of the listed twin metric confidences is ``low`` or ``None``."""
    if not metric_confidence:
        return True
    return any(
        metric_confidence.get(key) in (None, "low")
        for key in keys
    )


def _phase_starting_week(
    allocations: List[PhaseAllocation], phase_index: int
) -> int:
    """Return the 1-indexed week number at which *phase_index* begins."""
    return 1 + sum(a.weeks for a in allocations[:phase_index])


def _phase_start_date(
    allocations: List[PhaseAllocation],
    phase_starts: List[date],
    phase_index: int,
) -> date:
    """Return the start-of-phase date plus a 2-day buffer so the
    checkpoint never lands on the first day of the phase.
    """
    start_of_phase = phase_starts[phase_index]
    return start_of_phase + timedelta(days=2)


def _date_for_week(
    week_number: int,
    plan_start: date,
    allocations: List[PhaseAllocation],
) -> date:
    """Resolve a 1-indexed plan week to a calendar date with a 2-day buffer."""
    return plan_start + timedelta(days=(week_number - 1) * 7 + 2)


def _round_to_int(value: float) -> int:
    """Round-to-int helper mirroring Python's built-in ``round``."""
    return int(round(value))


__all__ = [
    "ALLOCATED_PHASE_LABELS",
    "CheckpointRecord",
    "GATE_THRESHOLDS",
    "PhaseAllocation",
    "PhaseDefinitionRecord",
    "QUALITY_SESSION_TYPES",
    "RACE_EVENT_FIXED_TAIL_WEEKS",
    "RACE_EVENT_PROPORTIONS",
    "SANDWICHED_SESSION_TYPES",
    "TRAINING_LENGTH_GATE_DEFAULT_WEEKS",
    "TrainingLengthGateResult",
    "allocate_race_event_phases",
    "derive_experience_level",
    "evaluate_training_length_gate",
    "schedule_checkpoints",
    "to_phase_definition_record",
]


ALLOCATED_PHASE_LABELS: Tuple[PhaseLabel, ...] = (
    PhaseLabel.AEROBIC_BASE,
    PhaseLabel.THRESHOLD_BUILD,
    PhaseLabel.SPECIFIC_ENDURANCE,
    PhaseLabel.TAPER,
    PhaseLabel.RACE_WEEK,
)
