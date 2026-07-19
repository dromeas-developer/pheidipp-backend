"""Unit tests for ``TwinRecalibrationService.recalibrate_for_calibration``.

Phase-2.3-P3 extends ``TwinRecalibrationService`` with a new
``recalibrate_for_calibration`` method that appends a calibration-
triggered ``TwinState`` and fires the ``twin_recalibrated`` and
``twin_confidence_upgraded`` events. Distinct from
``recalibrate`` (which handles ``activity_sync`` with Banister-only
updates), the calibration trigger:

* Snapshots the current ``AthleteFitness`` values (Banister
  update was already applied during ingestion).
* Snapshots the updated threshold values from
  ``AthletePhysiology`` (``lt1_hr_bpm``, ``lt2_hr_bpm``,
  ``cp_watts``).
* Carries ``metric_confidence`` derived from per-parameter
  ``prior_weight`` with the per-metric monotonicity ratchet
  (ADR-011).
* Carries ``confidence_level`` derived from
  ``min(lt1.hr.prior_weight, lt2.hr.prior_weight)`` with the
  global monotonicity ratchet.
* Uses ``model_version = "v2-threshold-detection"`` to
  distinguish from the activity_sync ``"v1-activity-sync"``.

These tests use ``AsyncMock`` for the repositories and event
publisher — no real DB connections, no real event publishing.

Reference plan: docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md
Reference architecture: docs/architecture/01-entities/twin-state.md
Reference ADR: docs/adr/011-confidence-monotonicity-ratchet-location.md
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import (
    DataTier,
    RecoveryModifierLevel,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from app.repositories.athlete_fitness_repository import AthleteFitnessRepository
from app.repositories.athlete_physiology_repository import (
    AthletePhysiologyRepository,
)
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.event_publisher import EventPublisher
from app.services.physiology_update_service import PhysiologyUpdateResult
from app.services.twin_recalibration_service import (
    MissingAthleteFitnessError,
    MissingTrainingGoalError,
    TwinRecalibrationService,
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-05-01",
) -> Dict[str, Any]:
    """Build a ``PhysiologyParameterState`` dict."""
    return {
        "value": value,
        "uncertainty": uncertainty,
        "prior_weight": prior_weight,
        "dominant_source": dominant_source,
        "last_observation_date": last_observation_date,
    }


def _physiology_row(
    *,
    lt1: Optional[Dict[str, Any]] = None,
    lt2: Optional[Dict[str, Any]] = None,
    cp: Optional[Dict[str, Any]] = None,
    max_hr: Optional[Dict[str, Any]] = None,
) -> AthletePhysiology:
    """Build an in-memory ``AthletePhysiology`` row."""
    return AthletePhysiology(
        athlete_id=uuid.uuid4(),
        lt1=lt1 if lt1 is not None else {"hr": None, "power": None, "pace": None},
        lt2=lt2 if lt2 is not None else {"hr": None, "power": None, "pace": None},
        cp=cp,
        max_hr=max_hr,
    )


def _goal_row(*, athlete_id: uuid.UUID) -> MagicMock:
    """Build a mock ``TrainingGoal`` row."""
    goal = MagicMock(spec=TrainingGoal)
    goal.athlete_id = athlete_id
    goal.id = uuid.uuid4()
    return goal


def _fitness_row(
    *,
    aggregate: Optional[Dict[str, float]] = None,
) -> MagicMock:
    """Build a mock ``AthleteFitness`` row with a JSONB aggregate."""
    fitness = MagicMock(spec=AthleteFitness)
    fitness.aggregate = aggregate or {"fitness": 50.0, "fatigue": 30.0, "form": 20.0}
    return fitness


def _previous_twin_state(
    *,
    confidence_level: TwinConfidenceLevel = TwinConfidenceLevel.LOW,
    trigger: str = TwinTrigger.ACTIVITY_SYNC.value,
    data_tier: DataTier = DataTier.TIER_3,
    metric_confidence: Optional[Dict[str, Optional[str]]] = None,
    lt1_hr_bpm: Optional[float] = None,
    lt2_hr_bpm: Optional[float] = None,
    cp_watts: Optional[float] = None,
    lt1_pace_sec_per_km: Optional[float] = None,
    lt1_power_watts: Optional[float] = None,
    lt2_pace_sec_per_km: Optional[float] = None,
    lt2_power_watts: Optional[float] = None,
    readiness_level: RecoveryModifierLevel = RecoveryModifierLevel.GREEN,
) -> MagicMock:
    """Build a mock previous ``TwinState`` row."""
    state = MagicMock(spec=TwinState)
    state.id = uuid.uuid4()
    state.confidence_level = confidence_level
    state.trigger = trigger
    state.data_tier = data_tier
    state.metric_confidence = metric_confidence or {}
    state.lt1_hr_bpm = lt1_hr_bpm
    state.lt2_hr_bpm = lt2_hr_bpm
    state.cp_watts = cp_watts
    state.lt1_pace_sec_per_km = lt1_pace_sec_per_km
    state.lt1_power_watts = lt1_power_watts
    state.lt2_pace_sec_per_km = lt2_pace_sec_per_km
    state.lt2_power_watts = lt2_power_watts
    state.readiness_level = readiness_level
    return state


def _make_service(
    *,
    goal: Optional[MagicMock] = None,
    fitness: Optional[MagicMock] = None,
    previous: Optional[MagicMock] = None,
    inserted_state: Optional[MagicMock] = None,
    event_publisher: Optional[AsyncMock] = None,
) -> tuple[
    TwinRecalibrationService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    """Build a fully-wired ``TwinRecalibrationService`` with mocks.

    Returns the service plus the four repository mocks and the
    event publisher mock so tests can assert on call counts and
    arguments.
    """
    mock_twin_states = AsyncMock(spec=TwinStateRepository)
    mock_athlete_fitness = AsyncMock(spec=AthleteFitnessRepository)
    mock_athlete_physiology = AsyncMock(spec=AthletePhysiologyRepository)
    mock_training_goals = AsyncMock(spec=TrainingGoalRepository)

    mock_training_goals.get_active = AsyncMock(return_value=goal)
    mock_athlete_fitness.get_by_athlete_id = AsyncMock(return_value=fitness)
    mock_twin_states.get_latest = AsyncMock(return_value=previous)
    mock_twin_states.get_by_activity_and_trigger = AsyncMock(return_value=None)
    mock_twin_states.get_by_activity = AsyncMock(return_value=None)
    # The repository's real ``insert`` returns the same object that
    # was passed in (after flush + refresh), preserving identity.
    # Mirroring that here so the dedup short-circuit's identity
    # check sees ``inserted is new_state`` → True and event firing
    # proceeds normally. The DB also assigns ``state.id`` via
    # ``flush() + refresh()``; the mock must simulate that for any
    # caller that reads ``inserted.id`` (e.g. event payloads that
    # include ``twin_state_id``).
    def _return_inserted(state: Any) -> Any:
        state.id = uuid.uuid4()
        return state

    mock_twin_states.insert = AsyncMock(side_effect=_return_inserted)

    if event_publisher is None:
        event_publisher = AsyncMock(spec=EventPublisher)

    service = TwinRecalibrationService(
        MagicMock(),  # session
        twin_states=mock_twin_states,
        athlete_fitness=mock_athlete_fitness,
        athlete_physiology=mock_athlete_physiology,
        training_goals=mock_training_goals,
        events=event_publisher,
    )

    return (
        service,
        mock_twin_states,
        mock_athlete_fitness,
        mock_athlete_physiology,
        mock_training_goals,
        event_publisher,
    )


def _make_physiology_result(
    *,
    physiology: AthletePhysiology,
    shifted_parameters: Optional[list[Any]] = None,
    metric_confidence: Optional[Dict[str, Optional[str]]] = None,
) -> PhysiologyUpdateResult:
    """Build a ``PhysiologyUpdateResult`` for the calibration flow."""
    return PhysiologyUpdateResult(
        physiology=physiology,
        shifted_parameters=shifted_parameters or [],
        metric_confidence=metric_confidence or {},
        confidence_transitions={},
        measurements_written=0,
    )


# ---------------------------------------------------------------------------
# Missing prerequisites — error paths.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationMissingPrerequisites:
    """The method raises ``MissingTrainingGoalError`` or
    ``MissingAthleteFitnessError`` when the prerequisite
    repositories return ``None``. These are data-integrity
    failures: the onboarding bootstrap always creates both
    rows, so a missing row is a system-level bug."""

    @pytest.mark.asyncio
    async def test_missing_training_goal_raises(self) -> None:
        goal: Optional[MagicMock] = None
        fitness = _fitness_row()

        service, _, _, _, _, _ = _make_service(
            goal=goal, fitness=fitness
        )

        with pytest.raises(MissingTrainingGoalError):
            await service.recalibrate_for_calibration(
                athlete_id=uuid.uuid4(),
                activity_id=uuid.uuid4(),
                physiology_result=_make_physiology_result(
                    physiology=_physiology_row()
                ),
            )

    @pytest.mark.asyncio
    async def test_missing_athlete_fitness_raises(self) -> None:
        goal = _goal_row(athlete_id=uuid.uuid4())
        fitness: Optional[MagicMock] = None

        service, _, _, _, _, _ = _make_service(
            goal=goal, fitness=fitness
        )

        with pytest.raises(MissingAthleteFitnessError):
            await service.recalibrate_for_calibration(
                athlete_id=uuid.uuid4(),
                activity_id=uuid.uuid4(),
                physiology_result=_make_physiology_result(
                    physiology=_physiology_row()
                ),
            )

    @pytest.mark.asyncio
    async def test_missing_fitness_does_not_publish_events(self) -> None:
        """A missing fitness row short-circuits before any
        ``twin_recalibrated`` event fires."""
        goal = _goal_row(athlete_id=uuid.uuid4())
        fitness: Optional[MagicMock] = None

        (
            service,
            _,
            _,
            _,
            _,
            mock_events,
        ) = _make_service(goal=goal, fitness=fitness)

        with pytest.raises(MissingAthleteFitnessError):
            await service.recalibrate_for_calibration(
                athlete_id=uuid.uuid4(),
                activity_id=uuid.uuid4(),
                physiology_result=_make_physiology_result(
                    physiology=_physiology_row()
                ),
            )

        mock_events.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# First snapshot — no previous TwinState.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationFirstSnapshot:
    """When no previous TwinState exists, the calibration
    TwinState is the first snapshot. The ratchet is a no-op
    because there is no prior level to compare against."""

    @pytest.mark.asyncio
    async def test_first_snapshot_uses_computed_confidence(self) -> None:
        """No previous TwinState → computed level is the stored
        level. ``previous`` lookup returns ``None``."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=6.0), "power": None, "pace": None},
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.MEDIUM
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            _,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        result = await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=activity_id,
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={
                    "lt1_hr": "medium",
                    "lt2_hr": "medium",
                },
            ),
        )

        # First snapshot: confidence_upgraded is False (no prior
        # to compare against). The returned TwinState is the
        # real ``new_state`` built by the service, not the mock
        # placeholder — the mock's ``side_effect`` returns the
        # passed-in argument by identity.
        assert result.confidence_upgraded is False
        assert result.twin_state.confidence_level == TwinConfidenceLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_first_snapshot_uses_data_tier_3_when_no_previous(self) -> None:
        """No previous TwinState → ``data_tier = TIER_3``
        (the default for first-time athletes)."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={"lt1_hr": "low", "lt2_hr": "low"},
            ),
        )

        # Inspect the new TwinState passed to insert.
        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.trigger == TwinTrigger.CALIBRATION
        assert inserted.model_version == "v2-threshold-detection"
        assert inserted.data_tier == DataTier.TIER_3
        assert inserted.confidence_level == TwinConfidenceLevel.LOW
        assert inserted.training_goal_id == goal.id
        assert inserted.activity_id is not None


# ---------------------------------------------------------------------------
# Subsequent snapshot — ratchet applies.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationRatchetApplies:
    """When a previous TwinState exists, the ratchet enforces
    monotonic confidence: the new level is
    ``max(previous_level, computed_level)``."""

    @pytest.mark.asyncio
    async def test_confidence_ratchet_preserves_higher_previous(self) -> None:
        """A computed level LOWER than the previous level does
        NOT downgrade the stored level. The previous MEDIUM
        level is preserved even when the current ``prior_weight``
        has decayed below 4.0."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM,
        )
        # Current physiology: prior_weight below 4.0 → computed
        # level is LOW. The ratchet must preserve MEDIUM.
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=1.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=2.0), "power": None, "pace": None},
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.MEDIUM
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={"lt1_hr": "low", "lt2_hr": "low"},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        # MEDIUM preserved by the ratchet.
        assert inserted.confidence_level == TwinConfidenceLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_confidence_ratchet_upgrades_to_higher_computed(self) -> None:
        """A computed level HIGHER than the previous level
        upgrades the stored level."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW,
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=12.0), "power": None, "pace": None},
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.HIGH
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            _,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        result = await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={"lt1_hr": "high", "lt2_hr": "high"},
            ),
        )

        # Confidence upgraded from LOW to HIGH.
        assert result.confidence_upgraded is True


# ---------------------------------------------------------------------------
# Per-metric ratchet (ADR-011).
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationPerMetricRatchet:
    """The per-metric monotonicity ratchet (ADR-011) is enforced
    here, not in ``PhysiologyUpdateService``. For each metric
    key in ``metric_confidence``, the final stored value is
    ``max(previous_twin_state.metric_confidence[metric],
    computed_level)``."""

    @pytest.mark.asyncio
    async def test_per_metric_ratchet_preserves_higher_previous(self) -> None:
        """A metric that previously reached MEDIUM stays MEDIUM
        even if its computed level is now LOW."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM,
            metric_confidence={
                "lt1_hr": "medium",
                "lt2_hr": "medium",
                "lt1_power": "medium",
            },
        )
        physiology = _physiology_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.MEDIUM
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={
                    "lt1_hr": "low",
                    "lt2_hr": "low",
                    "lt1_power": "low",
                },
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        # All three metrics stay MEDIUM (ratchet preserves).
        assert inserted.metric_confidence == {
            "lt1_hr": "medium",
            "lt2_hr": "medium",
            "lt1_power": "medium",
        }

    @pytest.mark.asyncio
    async def test_per_metric_ratchet_upgrades_to_higher_computed(self) -> None:
        """A metric whose computed level is HIGHER than the
        previous level upgrades to the computed value."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW,
            metric_confidence={"lt1_hr": "low", "lt2_hr": "low"},
        )
        physiology = _physiology_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.MEDIUM
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={
                    "lt1_hr": "medium",
                    "lt2_hr": "medium",
                },
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        # Both metrics upgraded to MEDIUM.
        assert inserted.metric_confidence == {
            "lt1_hr": "medium",
            "lt2_hr": "medium",
        }

    @pytest.mark.asyncio
    async def test_per_metric_ratchet_none_previous_uses_computed(self) -> None:
        """A metric that had no data before (None) but now has
        data: computed value wins. ``None`` means "no data",
        not "low confidence"."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        # Previous twin state has NO lt1_power (no power data before).
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW,
            metric_confidence={"lt1_hr": "low", "lt2_hr": "low"},
            # NOTE: no "lt1_power" key in previous
        )
        physiology = _physiology_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={
                    "lt1_hr": "low",
                    "lt2_hr": "low",
                    "lt1_power": "medium",  # new metric, no previous
                },
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.metric_confidence["lt1_power"] == "medium"

    @pytest.mark.asyncio
    async def test_per_metric_ratchet_mixed_high_and_low(self) -> None:
        """Mixed scenario: one metric upgrades, one metric is
        preserved by the ratchet, one metric is new."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM,
            metric_confidence={
                "lt1_hr": "medium",  # will stay medium (equal)
                "lt2_hr": "high",  # will stay high (ratchet)
                "lt1_power": "medium",  # will upgrade to high
            },
        )
        physiology = _physiology_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.HIGH
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={
                    "lt1_hr": "medium",  # equal
                    "lt2_hr": "low",  # downgraded by ratchet to high
                    "lt1_power": "high",  # upgraded
                },
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.metric_confidence["lt1_hr"] == "medium"
        assert inserted.metric_confidence["lt2_hr"] == "high"
        assert inserted.metric_confidence["lt1_power"] == "high"


# ---------------------------------------------------------------------------
# Threshold inline snapshot.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationThresholdSnapshot:
    """The calibration TwinState's threshold inline snapshot is
    populated from the updated ``AthletePhysiology`` row:
    ``lt1_hr_bpm``, ``lt2_hr_bpm``, ``cp_watts``."""

    @pytest.mark.asyncio
    async def test_threshold_snapshot_from_physiology(self) -> None:
        """The inline threshold fields are extracted from
        ``AthletePhysiology`` via ``_extract_param_value``."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        physiology = _physiology_row(
            lt1={"hr": _state(value=162.0), "power": None, "pace": None},
            lt2={"hr": _state(value=178.0), "power": None, "pace": None},
            cp={"value": 280.0},
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.MEDIUM
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.lt1_hr_bpm == 162.0
        assert inserted.lt2_hr_bpm == 178.0
        assert inserted.cp_watts == 280.0

    @pytest.mark.asyncio
    async def test_threshold_snapshot_null_when_physiology_null(self) -> None:
        """The inline threshold fields are ``None`` when the
        updated physiology has no HR data (no observations yet)."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        physiology = _physiology_row(
            lt1=None,
            lt2=None,
            cp=None,
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.lt1_hr_bpm is None
        assert inserted.lt2_hr_bpm is None
        assert inserted.cp_watts is None


# ---------------------------------------------------------------------------
# Fitness snapshot from AthleteFitness.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationFitnessSnapshot:
    """The calibration TwinState's fitness/fatigue/form values
    are read from the current ``AthleteFitness.aggregate`` block
    (the Banister update was already applied during ingestion)."""

    @pytest.mark.asyncio
    async def test_fitness_snapshot_from_aggregate(self) -> None:
        """The inline fitness/fatigue/form values are read from
        the ``AthleteFitness.aggregate`` JSONB."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row(
            aggregate={"fitness": 75.0, "fatigue": 25.0, "form": 50.0}
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 75.0
        result_state.fatigue = 25.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.fitness == 75.0
        assert inserted.fatigue == 25.0
        assert inserted.form == 50.0


# ---------------------------------------------------------------------------
# Inherit from previous TwinState when present.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationInheritFromPrevious:
    """Non-threshold fields fall back to the previous TwinState's
    values when a previous TwinState exists. This includes
    ``lt1_pace_sec_per_km``, ``lt1_power_watts``,
    ``lt2_pace_sec_per_km``, ``lt2_power_watts``,
    ``readiness_level``, ``wellness_trend``, and ``data_tier``."""

    @pytest.mark.asyncio
    async def test_inherits_lt1_power_from_previous(self) -> None:
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW,
            lt1_power_watts=210.0,
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        # lt1_power_watts inherited from previous.
        assert inserted.lt1_power_watts == 210.0

    @pytest.mark.asyncio
    async def test_inherits_readiness_level_from_previous(self) -> None:
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW,
            readiness_level=RecoveryModifierLevel.AMBER,
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.readiness_level == RecoveryModifierLevel.AMBER

    @pytest.mark.asyncio
    async def test_inherits_data_tier_from_previous(self) -> None:
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW,
            data_tier=DataTier.TIER_1,
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=previous,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.data_tier == DataTier.TIER_1


# ---------------------------------------------------------------------------
# Model version.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationModelVersion:
    """The calibration TwinState's ``model_version`` is
    ``"v2-threshold-detection"`` — distinct from the
    activity_sync ``"v1-activity-sync"`` so downstream consumers
    can distinguish the two pipelines."""

    @pytest.mark.asyncio
    async def test_model_version_is_v2_threshold_detection(self) -> None:
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.model_version == "v2-threshold-detection"

    def test_model_version_class_constants(self) -> None:
        """The service exposes both model versions as class
        constants for downstream consumers."""
        assert (
            TwinRecalibrationService.MODEL_VERSION == "v1-activity-sync"
        )
        assert (
            TwinRecalibrationService.MODEL_VERSION_CALIBRATION
            == "v2-threshold-detection"
        )


# ---------------------------------------------------------------------------
# Trigger is CALIBRATION.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationTrigger:
    """The calibration TwinState's ``trigger`` is
    ``TwinTrigger.CALIBRATION`` — distinct from
    ``activity_sync``, ``wellness_update``, or ``questionnaire``."""

    @pytest.mark.asyncio
    async def test_trigger_is_calibration(self) -> None:
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={},
            ),
        )

        inserted = mock_twin_states.insert.await_args.args[0]
        assert inserted.trigger == TwinTrigger.CALIBRATION

    @pytest.mark.asyncio
    async def test_insert_called_with_calibration_trigger(self) -> None:
        """The ``insert_if_not_exists`` gate receives
        ``trigger = TwinTrigger.CALIBRATION`` so the
        deduplication logic can identify calibration records."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.LOW
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=_physiology_row(),
                metric_confidence={},
            ),
        )

        # insert was called (through insert_if_not_exists) with the
        # new TwinState.
        mock_twin_states.insert.assert_awaited_once()


# ---------------------------------------------------------------------------
# Deduplication integration — calibration supersedes activity_sync.
# ---------------------------------------------------------------------------


class TestRecalibrateForCalibrationDeduplication:
    """The calibration flow routes through ``insert_if_not_exists``:
    a prior ``activity_sync`` TwinState does not block the
    calibration insert, but a prior calibration TwinState is
    returned unchanged."""

    @pytest.mark.asyncio
    async def test_prior_calibration_returns_existing(self) -> None:
        """A prior calibration TwinState causes the method to
        return the existing record without inserting a new one."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        existing = _make_existing_calibration_twin_state(
            activity_id=activity_id
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.MEDIUM
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            mock_events,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,
            inserted_state=result_state,
        )
        # Configure the calibration lookup to return the existing record.
        mock_twin_states.get_by_activity_and_trigger = AsyncMock(
            return_value=existing
        )

        result = await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=activity_id,
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        # The existing record is returned, not the result_state.
        assert result.twin_state is existing
        # No insert happened.
        mock_twin_states.insert.assert_not_awaited()
        # No events fired either — the gate short-circuits before
        # the event publishing step.
        mock_events.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_prior_activity_sync_does_not_block_calibration(self) -> None:
        """A prior activity_sync TwinState does NOT block the
        calibration insert — calibration supersedes activity_sync."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        prior_activity_sync = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC.value,
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )
        result_state = MagicMock(spec=TwinState)
        result_state.id = uuid.uuid4()
        result_state.confidence_level = TwinConfidenceLevel.MEDIUM
        result_state.fitness = 50.0
        result_state.fatigue = 30.0

        (
            service,
            mock_twin_states,
            _,
            _,
            _,
            _,
        ) = _make_service(
            goal=goal,
            fitness=fitness,
            previous=prior_activity_sync,
            inserted_state=result_state,
        )
        # No prior calibration.
        mock_twin_states.get_by_activity_and_trigger = AsyncMock(
            return_value=None
        )
        # But a prior activity_sync exists.
        mock_twin_states.get_by_activity = AsyncMock(
            return_value=prior_activity_sync
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=activity_id,
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        # The new calibration TwinState WAS inserted.
        mock_twin_states.insert.assert_awaited_once()


# ---------------------------------------------------------------------------
# Local helper for the deduplication test.
# ---------------------------------------------------------------------------


def _make_existing_calibration_twin_state(
    *, activity_id: uuid.UUID
) -> MagicMock:
    """Build a mock existing calibration TwinState for dedup tests."""
    state = MagicMock(spec=TwinState)
    state.id = uuid.uuid4()
    state.activity_id = activity_id
    state.trigger = TwinTrigger.CALIBRATION.value
    state.confidence_level = TwinConfidenceLevel.MEDIUM
    return state
