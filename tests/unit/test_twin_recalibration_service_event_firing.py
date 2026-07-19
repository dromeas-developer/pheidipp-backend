"""Unit tests for ``twin_recalibrated`` and ``twin_confidence_upgraded`` event firing.

Phase-2.3-P3 introduces two new events fired by
``TwinRecalibrationService.recalibrate_for_calibration``:

* ``twin_recalibrated`` — fires for every new calibration
  TwinState (no threshold gate, unlike ``physiology_updated``
  which is gated by > 1 unit shift). The payload includes
  ``athlete_id``, ``twin_state_id``, ``previous_twin_state_id``
  (``None`` on first snapshot), ``trigger`` (``"calibration"``),
  ``confidence_level``, ``fitness_score``, and ``fatigue_score``.

* ``twin_confidence_upgraded`` — fires only when the new
  TwinState's ``confidence_level`` is strictly higher than the
  previous TwinState's. Fires in addition to ``twin_recalibrated``
  (not instead of). The payload includes ``athlete_id``,
  ``from_level``, ``to_level``, and ``twin_state_id``.

Event ordering within the ``threshold_detection`` transaction:
``physiology_updated`` (P2) → ``twin_recalibrated`` (P3) →
``twin_confidence_upgraded`` (P3, only on upgrade).

These tests use ``AsyncMock`` for the event publisher — no real
DB connections, no real outbox writes.

Reference plan: docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md
Reference architecture: docs/architecture/00-foundations/event-catalogue.md
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
from app.services.twin_recalibration_service import TwinRecalibrationService


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
) -> AthletePhysiology:
    """Build an in-memory ``AthletePhysiology`` row."""
    return AthletePhysiology(
        athlete_id=uuid.uuid4(),
        lt1=lt1 if lt1 is not None else {"hr": None, "power": None, "pace": None},
        lt2=lt2 if lt2 is not None else {"hr": None, "power": None, "pace": None},
        cp=cp,
    )


def _goal_row(*, athlete_id: uuid.UUID) -> MagicMock:
    goal = MagicMock(spec=TrainingGoal)
    goal.athlete_id = athlete_id
    goal.id = uuid.uuid4()
    return goal


def _fitness_row() -> MagicMock:
    fitness = MagicMock(spec=AthleteFitness)
    fitness.aggregate = {"fitness": 50.0, "fatigue": 30.0, "form": 20.0}
    return fitness


def _previous_twin_state(
    *,
    confidence_level: TwinConfidenceLevel,
    metric_confidence: Optional[Dict[str, Optional[str]]] = None,
    data_tier: DataTier = DataTier.TIER_3,
) -> MagicMock:
    state = MagicMock(spec=TwinState)
    state.id = uuid.uuid4()
    state.confidence_level = confidence_level
    state.data_tier = data_tier
    state.metric_confidence = metric_confidence or {}
    return state


def _new_twin_state(
    *,
    confidence_level: TwinConfidenceLevel,
    fitness: float = 55.0,
    fatigue: float = 25.0,
) -> MagicMock:
    state = MagicMock(spec=TwinState)
    state.id = uuid.uuid4()
    state.confidence_level = confidence_level
    state.fitness = fitness
    state.fatigue = fatigue
    return state


def _make_service(
    *,
    goal: Optional[MagicMock] = None,
    fitness: Optional[MagicMock] = None,
    previous: Optional[MagicMock] = None,
    inserted_state: Optional[MagicMock] = None,
) -> tuple[
    TwinRecalibrationService,
    AsyncMock,
]:
    """Build a service with a mock event publisher that can be inspected."""
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

    mock_events = AsyncMock(spec=EventPublisher)

    service = TwinRecalibrationService(
        MagicMock(),
        twin_states=mock_twin_states,
        athlete_fitness=mock_athlete_fitness,
        athlete_physiology=mock_athlete_physiology,
        training_goals=mock_training_goals,
        events=mock_events,
    )

    return service, mock_events


def _make_physiology_result(
    *,
    physiology: AthletePhysiology,
    metric_confidence: Optional[Dict[str, Optional[str]]] = None,
) -> PhysiologyUpdateResult:
    return PhysiologyUpdateResult(
        physiology=physiology,
        shifted_parameters=[],
        metric_confidence=metric_confidence or {},
        confidence_transitions={},
        measurements_written=0,
    )


# ---------------------------------------------------------------------------
# twin_recalibrated — always fires on new calibration TwinState.
# ---------------------------------------------------------------------------


class TestTwinRecalibratedAlwaysFires:
    """``twin_recalibrated`` fires for every new calibration
    TwinState (no threshold gate)."""

    @pytest.mark.asyncio
    async def test_twin_recalibrated_fires_on_first_snapshot(self) -> None:
        """The event fires on the first calibration TwinState
        (no previous TwinState)."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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

        # At least one publish call happened for twin_recalibrated.
        twin_recalibrated_calls = [
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_recalibrated"
        ]
        assert len(twin_recalibrated_calls) == 1

    @pytest.mark.asyncio
    async def test_twin_recalibrated_fires_on_subsequent_snapshot(self) -> None:
        """The event fires even when a previous TwinState exists."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        twin_recalibrated_calls = [
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_recalibrated"
        ]
        assert len(twin_recalibrated_calls) == 1


# ---------------------------------------------------------------------------
# twin_recalibrated — payload fields.
# ---------------------------------------------------------------------------


class TestTwinRecalibratedPayload:
    """The ``twin_recalibrated`` payload includes the required
    fields per the event catalogue."""

    @pytest.mark.asyncio
    async def test_payload_includes_required_fields(self) -> None:
        """The payload includes ``athlete_id``, ``twin_state_id``,
        ``previous_twin_state_id`` (None for first snapshot),
        ``trigger`` ('calibration'), ``confidence_level``,
        ``fitness_score``, ``fatigue_score``."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM,
            fitness=55.0,
            fatigue=25.0,
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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

        twin_recalibrated_call = next(
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_recalibrated"
        )
        payload = twin_recalibrated_call.kwargs["payload"]

        assert payload["athlete_id"] == str(athlete_id)
        assert uuid.UUID(payload["twin_state_id"])  # valid UUID
        assert payload["previous_twin_state_id"] is None
        assert payload["trigger"] == "calibration"
        assert payload["confidence_level"] == "medium"
        assert isinstance(payload["fitness_score"], (int, float))
        assert isinstance(payload["fatigue_score"], (int, float))

    @pytest.mark.asyncio
    async def test_payload_includes_previous_twin_state_id_when_present(
        self,
    ) -> None:
        """When a previous TwinState exists, its ID is included
        in the payload as ``previous_twin_state_id``."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        twin_recalibrated_call = next(
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_recalibrated"
        )
        payload = twin_recalibrated_call.kwargs["payload"]
        assert payload["previous_twin_state_id"] == str(previous.id)

    @pytest.mark.asyncio
    async def test_payload_athlete_id_matches_event_athlete_id(self) -> None:
        """The ``athlete_id`` in the event publisher call matches
        the payload's ``athlete_id`` field."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.LOW
        )
        physiology = _physiology_row()

        service, mock_events = _make_service(
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

        twin_recalibrated_call = next(
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_recalibrated"
        )
        assert twin_recalibrated_call.kwargs["athlete_id"] == athlete_id
        assert (
            twin_recalibrated_call.kwargs["payload"]["athlete_id"]
            == str(athlete_id)
        )


# ---------------------------------------------------------------------------
# twin_confidence_upgraded — only fires on upgrade.
# ---------------------------------------------------------------------------


class TestTwinConfidenceUpgradedFires:
    """``twin_confidence_upgraded`` fires only when the new
    TwinState's ``confidence_level`` is strictly higher than
    the previous TwinState's."""

    @pytest.mark.asyncio
    async def test_upgrade_low_to_medium_fires(self) -> None:
        """A LOW → MEDIUM upgrade fires the event."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        upgraded_calls = [
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_confidence_upgraded"
        ]
        assert len(upgraded_calls) == 1

    @pytest.mark.asyncio
    async def test_upgrade_medium_to_high_fires(self) -> None:
        """A MEDIUM → HIGH upgrade fires the event."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.HIGH
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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
                metric_confidence={"lt1_hr": "high", "lt2_hr": "high"},
            ),
        )

        upgraded_calls = [
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_confidence_upgraded"
        ]
        assert len(upgraded_calls) == 1

    @pytest.mark.asyncio
    async def test_no_upgrade_does_not_fire(self) -> None:
        """Equal confidence (no upgrade) does NOT fire the
        ``twin_confidence_upgraded`` event."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        upgraded_calls = [
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_confidence_upgraded"
        ]
        assert len(upgraded_calls) == 0

    @pytest.mark.asyncio
    async def test_downgrade_does_not_fire(self) -> None:
        """A downgrade (MEDIUM → LOW) does NOT fire
        ``twin_confidence_upgraded``. The ratchet prevents
        downgrades, but the event-firing logic must also
        guard against it defensively."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        # Simulate the ratchet preserving MEDIUM despite a
        # downgrade attempt — the result_state has MEDIUM.
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=1.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=1.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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

        upgraded_calls = [
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_confidence_upgraded"
        ]
        assert len(upgraded_calls) == 0


# ---------------------------------------------------------------------------
# twin_confidence_upgraded — first snapshot does not fire.
# ---------------------------------------------------------------------------


class TestTwinConfidenceUpgradedFirstSnapshot:
    """The first calibration TwinState has no previous TwinState,
    so ``twin_confidence_upgraded`` does NOT fire — there is no
    prior level to upgrade from."""

    @pytest.mark.asyncio
    async def test_first_snapshot_does_not_fire_upgraded(self) -> None:
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.HIGH
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
            goal=goal,
            fitness=fitness,
            previous=None,  # first snapshot
            inserted_state=result_state,
        )

        await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=uuid.uuid4(),
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={"lt1_hr": "high", "lt2_hr": "high"},
            ),
        )

        upgraded_calls = [
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_confidence_upgraded"
        ]
        assert len(upgraded_calls) == 0


# ---------------------------------------------------------------------------
# twin_confidence_upgraded — payload fields.
# ---------------------------------------------------------------------------


class TestTwinConfidenceUpgradedPayload:
    """The ``twin_confidence_upgraded`` payload includes
    ``athlete_id``, ``from_level``, ``to_level``, and
    ``twin_state_id``."""

    @pytest.mark.asyncio
    async def test_payload_includes_required_fields(self) -> None:
        """The payload includes ``athlete_id``, ``from_level``,
        ``to_level``, and ``twin_state_id``."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.HIGH
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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
                metric_confidence={"lt1_hr": "high", "lt2_hr": "high"},
            ),
        )

        upgraded_call = next(
            call
            for call in mock_events.publish.await_args_list
            if call.kwargs.get("event_type") == "twin_confidence_upgraded"
        )
        payload = upgraded_call.kwargs["payload"]

        assert payload["athlete_id"] == str(athlete_id)
        assert payload["from_level"] == "low"
        assert payload["to_level"] == "high"
        assert uuid.UUID(payload["twin_state_id"])  # valid UUID


# ---------------------------------------------------------------------------
# Event ordering — twin_recalibrated before twin_confidence_upgraded.
# ---------------------------------------------------------------------------


class TestEventOrdering:
    """Event ordering within the calibration transaction:
    ``twin_recalibrated`` fires BEFORE
    ``twin_confidence_upgraded`` (when applicable)."""

    @pytest.mark.asyncio
    async def test_twin_recalibrated_before_twin_confidence_upgraded(self) -> None:
        """On a confidence upgrade, the call order is:
        ``twin_recalibrated`` → ``twin_confidence_upgraded``.
        The outbox insertion order matches the publish call order."""
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, mock_events = _make_service(
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
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        call_events = [
            call.kwargs.get("event_type")
            for call in mock_events.publish.await_args_list
        ]

        # Both events were called.
        assert "twin_recalibrated" in call_events
        assert "twin_confidence_upgraded" in call_events

        # twin_recalibrated came first.
        idx_recalibrated = call_events.index("twin_recalibrated")
        idx_upgraded = call_events.index("twin_confidence_upgraded")
        assert idx_recalibrated < idx_upgraded


# ---------------------------------------------------------------------------
# No events on dedup short-circuit.
# ---------------------------------------------------------------------------


class TestNoEventsOnDedupShortCircuit:
    """When the deduplication gate returns an existing calibration
    TwinState (prior calibration already exists), the event
    publishing step is skipped — no events fire."""

    @pytest.mark.asyncio
    async def test_no_events_when_prior_calibration_exists(self) -> None:
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        existing = MagicMock(spec=TwinState)
        existing.id = uuid.uuid4()
        existing.activity_id = activity_id
        existing.trigger = TwinTrigger.CALIBRATION.value
        existing.confidence_level = TwinConfidenceLevel.MEDIUM
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )

        # Build the service directly with a custom twin_states
        # mock that returns the existing calibration TwinState
        # from the dedup gate.
        mock_twin_states_repo = AsyncMock(spec=TwinStateRepository)
        mock_twin_states_repo.get_by_activity_and_trigger = AsyncMock(
            return_value=existing
        )
        mock_twin_states_repo.get_by_activity = AsyncMock(return_value=None)
        mock_twin_states_repo.get_latest = AsyncMock(return_value=None)
        mock_twin_states_repo.insert = AsyncMock(return_value=result_state)

        from app.repositories.athlete_fitness_repository import (
            AthleteFitnessRepository,
        )
        from app.repositories.athlete_physiology_repository import (
            AthletePhysiologyRepository,
        )
        from app.repositories.training_goal_repository import (
            TrainingGoalRepository,
        )

        mock_athlete_fitness = AsyncMock(spec=AthleteFitnessRepository)
        mock_athlete_fitness.get_by_athlete_id = AsyncMock(return_value=fitness)
        mock_athlete_physiology = AsyncMock(
            spec=AthletePhysiologyRepository
        )
        mock_training_goals = AsyncMock(spec=TrainingGoalRepository)
        mock_training_goals.get_active = AsyncMock(return_value=goal)

        mock_events = AsyncMock(spec=EventPublisher)

        service = TwinRecalibrationService(
            MagicMock(),
            twin_states=mock_twin_states_repo,
            athlete_fitness=mock_athlete_fitness,
            athlete_physiology=mock_athlete_physiology,
            training_goals=mock_training_goals,
            events=mock_events,
        )

        result = await service.recalibrate_for_calibration(
            athlete_id=athlete_id,
            activity_id=activity_id,
            physiology_result=_make_physiology_result(
                physiology=physiology,
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        # The existing record is returned.
        assert result.twin_state is existing
        # No events were published — the gate short-circuits
        # before the event publishing step.
        mock_events.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# Return value — CalibrationRecalibrationResult.
# ---------------------------------------------------------------------------


class TestReturnValue:
    """The method returns a ``CalibrationRecalibrationResult``
    carrying the new ``TwinState`` and the
    ``confidence_upgraded`` flag."""

    @pytest.mark.asyncio
    async def test_returns_calibration_recalibration_result(self) -> None:
        from app.services.twin_recalibration_service import (
            CalibrationRecalibrationResult,
        )

        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.LOW
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, _ = _make_service(
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
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        assert isinstance(result, CalibrationRecalibrationResult)
        # The returned TwinState is the real ``new_state`` built by
        # the service, not the mock placeholder — the mock's
        # ``side_effect`` returns the passed-in argument by
        # identity, mirroring the repository's flush+refresh
        # behaviour.
        assert result.twin_state.confidence_level == TwinConfidenceLevel.MEDIUM
        assert result.confidence_upgraded is True

    @pytest.mark.asyncio
    async def test_returns_confidence_upgraded_false_on_no_upgrade(self) -> None:
        athlete_id = uuid.uuid4()
        goal = _goal_row(athlete_id=athlete_id)
        fitness = _fitness_row()
        previous = _previous_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        result_state = _new_twin_state(
            confidence_level=TwinConfidenceLevel.MEDIUM
        )
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )

        service, _ = _make_service(
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
                metric_confidence={"lt1_hr": "medium", "lt2_hr": "medium"},
            ),
        )

        assert result.confidence_upgraded is False
