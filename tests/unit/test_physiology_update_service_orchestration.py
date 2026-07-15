"""Unit tests for ``PhysiologyUpdateService`` orchestration.

Phase-2.3-P2 introduces ``PhysiologyUpdateService`` — the orchestrator
that loads the athlete's posterior state, dedups duplicate observations,
applies the Bayesian update, persists ``PhysiologyMeasurement`` audit
records, mutates ``AthletePhysiology`` JSONB columns in place, detects
posterior shifts above the 1-unit threshold, detects monotonic
confidence transitions, and fires the ``physiology_updated`` event.

This test module covers:

* Service construction with dependency-injected repositories and
  event publisher.
* ``apply_observations()`` — happy path, missing-physiology error,
  measurement writing, posterior shift detection, event firing,
  idempotency, first-observation bootstrap, confidence transitions.
* ``_get_parameter_state()`` — JSONB path navigation.
* ``_apply_updated_states()`` — JSONB write-back with
  ``flag_modified``.
* Registration in ``app/services/__init__.py``.

All tests use ``AsyncMock`` for the repository and event-publisher
dependencies — no real DB connections, no real event publishing.

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/02-computations/physiology-update.md
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import (
    MeasurementSource,
    PhysiologyParameter,
)
from app.models.physiology_measurement import PhysiologyMeasurement
from app.repositories.athlete_physiology_repository import (
    UNSET_SENTINEL,
    AthletePhysiologyRepository,
)
from app.repositories.physiology_measurement_repository import (
    PhysiologyMeasurementRepository,
)
from app.services.event_publisher import EventPublisher
from app.services.physiology_update_service import (
    MissingAthletePhysiologyError,
    PhysiologyUpdateResult,
    PhysiologyUpdateService,
    bayesian_update,
    init_null_parameter_state,
)
from app.services.threshold_detection_service import ThresholdObservation


# ---------------------------------------------------------------------------
# Helpers — build the JSONB dict shapes and ORM model instances.
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


def _observation(
    *,
    parameter: PhysiologyParameter = PhysiologyParameter.LT2_HR,
    observed_value: float = 170.0,
    source: MeasurementSource = MeasurementSource.TRAINING_HR_DEFLECTION,
    weight: float = 1.0,
    activity_id: Optional[uuid.UUID] = None,
    measurement_date: date = date(2026, 6, 15),
    algorithm_used: str = "hr_deflection_v1",
    confidence_weight: float = 0.85,
) -> ThresholdObservation:
    """Build a real ``ThresholdObservation`` dataclass instance."""
    return ThresholdObservation(
        parameter=parameter,
        observed_value=observed_value,
        source=source,
        weight=weight,
        activity_id=activity_id or uuid.uuid4(),
        measurement_date=measurement_date,
        algorithm_used=algorithm_used,
        confidence_weight=confidence_weight,
    )


def _physiology_row(
    *,
    lt1: Optional[Dict[str, Any]] = None,
    lt2: Optional[Dict[str, Any]] = None,
    cp: Optional[Dict[str, Any]] = None,
    max_hr: Optional[Dict[str, Any]] = None,
) -> AthletePhysiology:
    """Build an in-memory ``AthletePhysiology`` row with the given
    JSONB columns. ``lt1`` and ``lt2`` default to the empty
    three-dimension container so the row is constructible without
    raising on the non-nullable columns."""
    return AthletePhysiology(
        athlete_id=uuid.uuid4(),
        lt1=lt1 if lt1 is not None else {"hr": None, "power": None, "pace": None},
        lt2=lt2 if lt2 is not None else {"hr": None, "power": None, "pace": None},
        cp=cp,
        max_hr=max_hr,
    )


def _make_service(
    *,
    physiology_row: Optional[AthletePhysiology] = None,
    insert_return: Optional[PhysiologyMeasurement] = None,
    recent_for_parameter: Optional[List[MagicMock]] = None,
) -> tuple[
    PhysiologyUpdateService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    """Build a fully-wired ``PhysiologyUpdateService`` with mocks.

    Returns the service plus the three dependency mocks so tests can
    assert against them directly.
    """
    mock_session = AsyncMock()
    mock_physiology_repo = AsyncMock(spec=AthletePhysiologyRepository)
    mock_measurement_repo = AsyncMock(spec=PhysiologyMeasurementRepository)
    mock_events = AsyncMock(spec=EventPublisher)

    if physiology_row is not None:
        mock_physiology_repo.get_by_athlete_id = AsyncMock(
            return_value=physiology_row
        )
    else:
        mock_physiology_repo.get_by_athlete_id = AsyncMock(return_value=None)

    mock_measurement_repo.insert = AsyncMock(
        return_value=insert_return or MagicMock(spec=PhysiologyMeasurement)
    )
    mock_measurement_repo.get_recent_for_parameter = AsyncMock(
        return_value=recent_for_parameter or []
    )

    service = PhysiologyUpdateService(
        mock_session,
        athlete_physiology_repository=mock_physiology_repo,
        physiology_measurement_repository=mock_measurement_repo,
        events=mock_events,
    )

    return service, mock_physiology_repo, mock_measurement_repo, mock_events


# ---------------------------------------------------------------------------
# Service construction.
# ---------------------------------------------------------------------------


class TestServiceConstruction:
    """``PhysiologyUpdateService`` accepts injected dependencies and
    defaults to building them from the session when not provided."""

    def test_construct_with_all_dependencies_injected(self) -> None:
        """All three dependencies can be injected as keyword args."""
        mock_session = AsyncMock()
        mock_physiology_repo = AsyncMock(spec=AthletePhysiologyRepository)
        mock_measurement_repo = AsyncMock(
            spec=PhysiologyMeasurementRepository
        )
        mock_events = AsyncMock(spec=EventPublisher)

        service = PhysiologyUpdateService(
            mock_session,
            athlete_physiology_repository=mock_physiology_repo,
            physiology_measurement_repository=mock_measurement_repo,
            events=mock_events,
        )

        assert service.session is mock_session
        assert service.athlete_physiology is mock_physiology_repo
        assert service.physiology_measurements is mock_measurement_repo
        assert service.events is mock_events

    def test_construct_with_events_none_builds_default_publisher(self) -> None:
        """When ``events=None``, the service builds a default
        ``EventPublisher`` from the session — the publisher is not
        ``None``."""
        mock_session = AsyncMock()
        mock_physiology_repo = AsyncMock(spec=AthletePhysiologyRepository)
        mock_measurement_repo = AsyncMock(
            spec=PhysiologyMeasurementRepository
        )

        service = PhysiologyUpdateService(
            mock_session,
            athlete_physiology_repository=mock_physiology_repo,
            physiology_measurement_repository=mock_measurement_repo,
            events=None,
        )

        assert service.events is not None
        assert isinstance(service.events, EventPublisher)


# ---------------------------------------------------------------------------
# apply_observations — missing physiology error.
# ---------------------------------------------------------------------------


class TestApplyObservationsMissingPhysiology:
    """``apply_observations`` raises ``MissingAthletePhysiologyError``
    when no ``AthletePhysiology`` row exists for the athlete."""

    @pytest.mark.asyncio
    async def test_raises_when_no_physiology_row(self) -> None:
        """A missing row raises ``MissingAthletePhysiologyError``."""
        service, mock_physiology_repo, mock_measurement_repo, mock_events = (
            _make_service(physiology_row=None)
        )
        athlete_id = uuid.uuid4()

        with pytest.raises(MissingAthletePhysiologyError):
            await service.apply_observations(
                athlete_id=athlete_id,
                observations=[],
            )

    @pytest.mark.asyncio
    async def test_no_measurement_inserts_on_missing_row(self) -> None:
        """No ``PhysiologyMeasurement`` rows are inserted when the
        physiology row is missing."""
        service, mock_physiology_repo, mock_measurement_repo, mock_events = (
            _make_service(physiology_row=None)
        )

        with pytest.raises(MissingAthletePhysiologyError):
            await service.apply_observations(
                athlete_id=uuid.uuid4(),
                observations=[_observation()],
            )

        mock_measurement_repo.insert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_event_published_on_missing_row(self) -> None:
        """No ``physiology_updated`` event is published when the
        physiology row is missing."""
        service, mock_physiology_repo, mock_measurement_repo, mock_events = (
            _make_service(physiology_row=None)
        )

        with pytest.raises(MissingAthletePhysiologyError):
            await service.apply_observations(
                athlete_id=uuid.uuid4(),
                observations=[_observation()],
            )

        mock_events.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# apply_observations — measurement writing.
# ---------------------------------------------------------------------------


class TestApplyObservationsMeasurementWriting:
    """``apply_observations`` writes one ``PhysiologyMeasurement`` row
    per observation, unconditionally — even when the posterior does
    not shift or the observation is a duplicate."""

    @pytest.mark.asyncio
    async def test_writes_one_measurement_per_observation(self) -> None:
        """Three observations produce three ``insert`` calls."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service, _, mock_measurement_repo, _ = _make_service(
            physiology_row=physiology,
        )
        observations = [_observation() for _ in range(3)]

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=observations,
        )

        assert mock_measurement_repo.insert.await_count == 3
        assert result.measurements_written == 3

    @pytest.mark.asyncio
    async def test_measurement_carries_all_observation_fields(self) -> None:
        """The ``PhysiologyMeasurement`` row carries every field from
        the observation: athlete_id, activity_id, parameter,
        observed_value, source, measurement_date, algorithm_used,
        confidence_weight."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service, _, mock_measurement_repo, _ = _make_service(
            physiology_row=physiology,
        )
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=1.0,
            activity_id=activity_id,
            measurement_date=date(2026, 6, 15),
            algorithm_used="hr_deflection_v1",
            confidence_weight=0.85,
        )

        await service.apply_observations(
            athlete_id=athlete_id,
            observations=[obs],
        )

        # Inspect the measurement passed to insert.
        call_kwargs = mock_measurement_repo.insert.await_args
        measurement = call_kwargs.args[0]
        assert measurement.athlete_id == athlete_id
        assert measurement.activity_id == activity_id
        assert measurement.parameter == PhysiologyParameter.LT2_HR
        assert measurement.observed_value == 170.0
        assert measurement.source == MeasurementSource.TRAINING_HR_DEFLECTION
        assert measurement.measurement_date == date(2026, 6, 15)
        assert measurement.algorithm_used == "hr_deflection_v1"
        assert measurement.confidence_weight == 0.85

    @pytest.mark.asyncio
    async def test_measurement_raw_data_reference_and_notes_are_none(
        self,
    ) -> None:
        """``raw_data_reference`` and ``notes`` are ``None`` for
        training-derived observations (lab/field test flows are
        deferred)."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service, _, mock_measurement_repo, _ = _make_service(
            physiology_row=physiology,
        )

        await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[_observation()],
        )

        measurement = mock_measurement_repo.insert.await_args.args[0]
        assert measurement.raw_data_reference is None
        assert measurement.notes is None


# ---------------------------------------------------------------------------
# apply_observations — posterior shift detection and event firing.
# ---------------------------------------------------------------------------


class TestApplyObservationsShiftAndEvent:
    """``apply_observations`` fires ``physiology_updated`` when any
    parameter's posterior shifts by > 1 unit, with the correct payload."""

    @pytest.mark.asyncio
    async def test_fires_event_when_shift_exceeds_one_unit(self) -> None:
        """A posterior shift > 1 unit fires the ``physiology_updated``
        event with the shifted parameter in ``parameters_updated``."""
        # Current state value=160, observation value=170 → posterior
        # mean is between 160 and 170, well above the 1-unit threshold.
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service, _, _, mock_events = _make_service(physiology_row=physiology)
        athlete_id = uuid.uuid4()
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
        )

        result = await service.apply_observations(
            athlete_id=athlete_id,
            observations=[obs],
        )

        assert PhysiologyParameter.LT2_HR in result.shifted_parameters
        mock_events.publish.assert_awaited_once()
        call_kwargs = mock_events.publish.await_args.kwargs
        assert call_kwargs["event_type"] == "physiology_updated"
        assert call_kwargs["athlete_id"] == athlete_id
        payload = call_kwargs["payload"]
        assert payload["athlete_id"] == str(athlete_id)
        assert payload["parameters_updated"] == ["lt2_hr"]

    @pytest.mark.asyncio
    async def test_event_payload_includes_dominant_sources_and_weights(
        self,
    ) -> None:
        """The event payload includes ``dominant_sources`` and
        ``prior_weights`` dicts keyed by parameter name."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service, _, _, mock_events = _make_service(physiology_row=physiology)
        athlete_id = uuid.uuid4()
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
        )

        await service.apply_observations(
            athlete_id=athlete_id,
            observations=[obs],
        )

        payload = mock_events.publish.await_args.kwargs["payload"]
        assert "dominant_sources" in payload
        assert "prior_weights" in payload
        assert "lt2_hr" in payload["dominant_sources"]
        assert "lt2_hr" in payload["prior_weights"]

    @pytest.mark.asyncio
    async def test_does_not_fire_event_when_shift_le_one_unit(self) -> None:
        """A posterior shift <= 1 unit does NOT fire the event, but
        the measurement is still written and the posterior is still
        updated in place."""
        # Current state value=160, observation value=160.5 → posterior
        # mean is between 160 and 160.5, well below the 1-unit threshold.
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=10.0),
                "power": None,
                "pace": None,
            },
        )
        service, mock_physiology_repo, mock_measurement_repo, mock_events = (
            _make_service(physiology_row=physiology)
        )
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=160.5,
            weight=0.1,
        )

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        # No event fired.
        mock_events.publish.assert_not_awaited()
        assert result.shifted_parameters == []
        # But the measurement was still written.
        assert mock_measurement_repo.insert.await_count == 1
        # And the posterior was still updated in place.
        mock_physiology_repo.update_in_place.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_update_in_place_with_post_mutation_values(
        self,
    ) -> None:
        """``update_in_place`` is called with the post-mutation
        ``lt1`` / ``lt2`` / ``cp`` / ``max_hr`` values — only the
        touched columns are passed (others use the sentinel)."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service, mock_physiology_repo, _, _ = _make_service(
            physiology_row=physiology,
        )
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
        )

        await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        call_kwargs = mock_physiology_repo.update_in_place.await_args.kwargs
        # lt2 was touched → passed as a dict.
        assert call_kwargs["lt2"] is not None
        # lt1 was NOT touched → None (non-nullable column sentinel).
        assert call_kwargs["lt1"] is None
        # cp was NOT touched → UNSET_SENTINEL (nullable column sentinel).
        assert call_kwargs["cp"] is UNSET_SENTINEL
        # max_hr was NOT touched → UNSET_SENTINEL.
        assert call_kwargs["max_hr"] is UNSET_SENTINEL


# ---------------------------------------------------------------------------
# apply_observations — idempotency.
# ---------------------------------------------------------------------------


class TestApplyObservationsIdempotency:
    """``apply_observations`` detects duplicate observations via
    ``get_recent_for_parameter`` and writes the measurement but does
    NOT shift the posterior and does NOT fire the event."""

    @pytest.mark.asyncio
    async def test_duplicate_observation_writes_measurement(self) -> None:
        """A duplicate observation still produces a
        ``PhysiologyMeasurement`` row (audit completeness)."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        activity_id = uuid.uuid4()
        existing = MagicMock(spec=PhysiologyMeasurement)
        existing.measurement_date = date(2026, 6, 15)
        existing.observed_value = 170.0
        existing.activity_id = activity_id

        service, _, mock_measurement_repo, _ = _make_service(
            physiology_row=physiology,
            recent_for_parameter=[existing],
        )
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            activity_id=activity_id,
            measurement_date=date(2026, 6, 15),
        )

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        # Measurement was still written.
        assert mock_measurement_repo.insert.await_count == 1
        assert result.measurements_written == 1

    @pytest.mark.asyncio
    async def test_duplicate_observation_does_not_shift_posterior(
        self,
    ) -> None:
        """A duplicate observation does NOT contribute to
        ``shifted_parameters`` — the posterior is not shifted."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        activity_id = uuid.uuid4()
        existing = MagicMock(spec=PhysiologyMeasurement)
        existing.measurement_date = date(2026, 6, 15)
        existing.observed_value = 170.0
        existing.activity_id = activity_id

        service, _, _, _ = _make_service(
            physiology_row=physiology,
            recent_for_parameter=[existing],
        )
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            activity_id=activity_id,
            measurement_date=date(2026, 6, 15),
        )

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        assert result.shifted_parameters == []

    @pytest.mark.asyncio
    async def test_duplicate_observation_does_not_fire_event(self) -> None:
        """A duplicate observation does NOT contribute to the
        ``physiology_updated`` event payload."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        activity_id = uuid.uuid4()
        existing = MagicMock(spec=PhysiologyMeasurement)
        existing.measurement_date = date(2026, 6, 15)
        existing.observed_value = 170.0
        existing.activity_id = activity_id

        service, _, _, mock_events = _make_service(
            physiology_row=physiology,
            recent_for_parameter=[existing],
        )
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            activity_id=activity_id,
            measurement_date=date(2026, 6, 15),
        )

        await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        mock_events.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_duplicate_observation_proceeds_normally(self) -> None:
        """An observation that does NOT match any existing record
        proceeds through the normal Bayesian update path."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        # No existing records → not a duplicate.
        service, _, _, mock_events = _make_service(
            physiology_row=physiology,
            recent_for_parameter=[],
        )
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
        )

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        # Shift detected, event fired.
        assert PhysiologyParameter.LT2_HR in result.shifted_parameters
        mock_events.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# apply_observations — first observation for null parameter.
# ---------------------------------------------------------------------------


class TestApplyObservationsFirstObservationForNullParameter:
    """``apply_observations`` bootstraps a fresh
    ``PhysiologyParameterState`` via ``init_null_parameter_state`` when
    the first observation for a previously-null parameter arrives."""

    @pytest.mark.asyncio
    async def test_first_cp_observation_bootstraps_state(self) -> None:
        """A first CP observation against a null ``physiology.cp``
        bootstraps a fresh state via ``init_null_parameter_state``."""
        physiology = _physiology_row(cp=None)
        service, _, _, _ = _make_service(physiology_row=physiology)
        obs = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=260.0,
            weight=1.5,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
        )

        await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        # physiology.cp is now populated (was None before).
        assert physiology.cp is not None
        assert physiology.cp["value"] == 260.0
        assert physiology.cp["prior_weight"] == 1.5
        assert (
            physiology.cp["dominant_source"] == "training_power_hr_ratio"
        )

    @pytest.mark.asyncio
    async def test_first_observation_does_not_count_as_shift(self) -> None:
        """A first observation for a null parameter does NOT count
        as a shift — the ``> 1 unit`` gate only applies to parameters
        with an existing estimate."""
        physiology = _physiology_row(cp=None)
        service, _, _, mock_events = _make_service(physiology_row=physiology)
        obs = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=260.0,
            weight=1.5,
        )

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=[obs],
        )

        # No shift detected (current_state was None).
        assert result.shifted_parameters == []
        # No event fired.
        mock_events.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# apply_observations — confidence transitions.
# ---------------------------------------------------------------------------


class TestApplyObservationsConfidenceTransitions:
    """``apply_observations`` returns per-metric confidence transitions
    in ``PhysiologyUpdateResult`` when a metric moves from LOW to
    MEDIUM (at prior_weight >= 4.0) or MEDIUM to HIGH (>= 8.0)."""

    @pytest.mark.asyncio
    async def test_four_observations_reach_medium(self) -> None:
        """Four observations of weight 1.0 for LT2_HR push the
        prior_weight to 4.0 and trigger a LOW→MEDIUM transition."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.0),
                "power": None,
                "pace": None,
            },
        )
        service, _, _, _ = _make_service(physiology_row=physiology)
        observations = [
            _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=160.0,
                weight=1.0,
                measurement_date=date(2026, 6, 15),
            )
            for _ in range(4)
        ]

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=observations,
        )

        assert "lt2_hr" in result.confidence_transitions
        assert result.confidence_transitions["lt2_hr"] == ("low", "medium")

    @pytest.mark.asyncio
    async def test_eight_observations_reach_high(self) -> None:
        """Eight observations of weight 1.0 for LT2_HR push the
        prior_weight to 8.0 and trigger a LOW→HIGH transition.

        Note: the transition is reported as ``("low", "high")``,
        NOT ``("medium", "high")`` — ``apply_observations`` computes
        the pre- and post-call confidence levels and reports the
        batch transition between them, not the per-observation
        transitions. A single batch that starts at LOW (prior_weight
        0.0) and ends at HIGH (prior_weight 8.0) reports a direct
        LOW→HIGH transition. The MEDIUM level is reached internally
        at observation 4 but is not a snapshot the service reports.
        """
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.0),
                "power": None,
                "pace": None,
            },
        )
        service, _, _, _ = _make_service(physiology_row=physiology)
        observations = [
            _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=160.0,
                weight=1.0,
                measurement_date=date(2026, 6, 15),
            )
            for _ in range(8)
        ]

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=observations,
        )

        assert "lt2_hr" in result.confidence_transitions
        # Batch transition: pre-call confidence = LOW (prior_weight
        # 0.0), post-call confidence = HIGH (prior_weight 8.0).
        # MEDIUM is reached mid-batch but is not a snapshot the
        # service reports.
        assert result.confidence_transitions["lt2_hr"] == ("low", "high")

    @pytest.mark.asyncio
    async def test_rr_observations_reach_medium_faster(self) -> None:
        """RR observations carry weight 2.5 — two observations
        reach MEDIUM (2 × 2.5 = 5.0 >= 4.0)."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(value=160.0, prior_weight=0.0),
                "power": None,
                "pace": None,
            },
        )
        service, _, _, _ = _make_service(physiology_row=physiology)
        observations = [
            _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=160.0,
                weight=2.5,
                source=MeasurementSource.TRAINING_RR_INFLECTION,
                measurement_date=date(2026, 6, 15),
            )
            for _ in range(2)
        ]

        result = await service.apply_observations(
            athlete_id=uuid.uuid4(),
            observations=observations,
        )

        assert "lt2_hr" in result.confidence_transitions
        assert result.confidence_transitions["lt2_hr"] == ("low", "medium")


# ---------------------------------------------------------------------------
# _get_parameter_state — JSONB path navigation.
# ---------------------------------------------------------------------------


class TestGetParameterState:
    """``_get_parameter_state`` resolves a ``PhysiologyParameter`` to
    the correct JSONB path on the ``AthletePhysiology`` row."""

    def test_lt1_hr_resolves_to_lt1_hr_substate(self) -> None:
        """``LT1_HR`` resolves to ``physiology.lt1["hr"]``."""
        hr_state = _state(value=150.0)
        physiology = _physiology_row(
            lt1={"hr": hr_state, "power": None, "pace": None},
        )

        result = PhysiologyUpdateService._get_parameter_state(
            physiology, PhysiologyParameter.LT1_HR
        )

        assert result == hr_state

    def test_lt2_hr_resolves_to_lt2_hr_substate(self) -> None:
        """``LT2_HR`` resolves to ``physiology.lt2["hr"]``."""
        hr_state = _state(value=175.0)
        physiology = _physiology_row(
            lt2={"hr": hr_state, "power": None, "pace": None},
        )

        result = PhysiologyUpdateService._get_parameter_state(
            physiology, PhysiologyParameter.LT2_HR
        )

        assert result == hr_state

    def test_cp_resolves_to_cp_column(self) -> None:
        """``CP`` resolves to ``physiology.cp`` (single-state column)."""
        cp_state = _state(value=260.0)
        physiology = _physiology_row(cp=cp_state)

        result = PhysiologyUpdateService._get_parameter_state(
            physiology, PhysiologyParameter.CP
        )

        assert result == cp_state

    def test_max_hr_resolves_to_max_hr_column(self) -> None:
        """``MAX_HR`` resolves to ``physiology.max_hr`` (single-state
        column)."""
        max_hr_state = _state(value=195.0)
        physiology = _physiology_row(max_hr=max_hr_state)

        result = PhysiologyUpdateService._get_parameter_state(
            physiology, PhysiologyParameter.MAX_HR
        )

        assert result == max_hr_state

    def test_returns_none_when_substate_is_null(self) -> None:
        """A null sub-state (e.g. ``lt1["hr"] = None``) returns ``None``."""
        physiology = _physiology_row(
            lt1={"hr": None, "power": None, "pace": None},
        )

        result = PhysiologyUpdateService._get_parameter_state(
            physiology, PhysiologyParameter.LT1_HR
        )

        assert result is None

    def test_returns_none_when_cp_is_null(self) -> None:
        """A null ``cp`` column returns ``None``."""
        physiology = _physiology_row(cp=None)

        result = PhysiologyUpdateService._get_parameter_state(
            physiology, PhysiologyParameter.CP
        )

        assert result is None

    def test_returns_shallow_copy_not_reference(self) -> None:
        """The returned dict is a shallow copy — mutating it does
        NOT mutate the original ``PhysiologyParameterState``."""
        hr_state = _state(value=150.0)
        physiology = _physiology_row(
            lt1={"hr": hr_state, "power": None, "pace": None},
        )

        result = PhysiologyUpdateService._get_parameter_state(
            physiology, PhysiologyParameter.LT1_HR
        )

        assert result is not None
        assert result is not hr_state
        result["value"] = 999.0
        assert hr_state["value"] == 150.0

    def test_unsupported_parameter_raises_value_error(self) -> None:
        """A parameter not in ``_PARAMETER_PATH`` raises ``ValueError``."""
        physiology = _physiology_row()

        with pytest.raises(ValueError, match="unsupported physiology parameter"):
            PhysiologyUpdateService._get_parameter_state(
                physiology, "not_a_real_parameter"  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# _apply_updated_states — JSONB write-back with flag_modified.
# ---------------------------------------------------------------------------


class TestApplyUpdatedStates:
    """``_apply_updated_states`` writes the new sub-state back into
    the JSONB container and calls ``flag_modified`` on every touched
    outer column."""

    def test_lt1_hr_substate_replaced(self) -> None:
        """Updating ``lt1["hr"]`` replaces the sub-state inside the
        container."""
        physiology = _physiology_row(
            lt1={
                "hr": _state(value=140.0),
                "power": _state(value=200.0),
                "pace": None,
            },
        )
        new_hr_state = _state(value=142.0)

        PhysiologyUpdateService._apply_updated_states(
            physiology,
            {PhysiologyParameter.LT1_HR: new_hr_state},
        )

        assert physiology.lt1["hr"]["value"] == 142.0
        # power sub-state is preserved.
        assert physiology.lt1["power"]["value"] == 200.0

    def test_cp_column_replaced_wholesale(self) -> None:
        """Updating ``cp`` replaces the column wholesale."""
        physiology = _physiology_row(cp=_state(value=260.0))
        new_cp_state = _state(value=265.0)

        PhysiologyUpdateService._apply_updated_states(
            physiology,
            {PhysiologyParameter.CP: new_cp_state},
        )

        assert physiology.cp is not None
        assert physiology.cp["value"] == 265.0

    def test_flag_modified_called_on_touched_column(self) -> None:
        """``flag_modified`` is called on every touched outer column
        exactly once."""
        physiology = _physiology_row(
            lt1={
                "hr": _state(value=140.0),
                "power": None,
                "pace": None,
            },
        )

        with patch(
            "app.services.physiology_update_service.flag_modified"
        ) as mock_flag:
            PhysiologyUpdateService._apply_updated_states(
                physiology,
                {PhysiologyParameter.LT1_HR: _state(value=142.0)},
            )

        mock_flag.assert_called_once_with(physiology, "lt1")

    def test_flag_modified_called_once_per_column_even_with_multiple_substates(
        self,
    ) -> None:
        """``flag_modified`` is called once per outer column even if
        multiple sub-states within the same container changed."""
        physiology = _physiology_row(
            lt1={
                "hr": _state(value=140.0),
                "power": _state(value=200.0),
                "pace": None,
            },
        )

        with patch(
            "app.services.physiology_update_service.flag_modified"
        ) as mock_flag:
            PhysiologyUpdateService._apply_updated_states(
                physiology,
                {
                    PhysiologyParameter.LT1_HR: _state(value=142.0),
                    PhysiologyParameter.LT1_POWER: _state(value=205.0),
                },
            )

        # Both sub-states are in the same lt1 container → flag_modified
        # called once for "lt1".
        assert mock_flag.call_count == 1
        mock_flag.assert_called_once_with(physiology, "lt1")

    def test_null_container_builds_fresh_three_dimension_dict(self) -> None:
        """A null ``lt1`` container is replaced with a fresh
        ``{hr: None, power: None, pace: None}`` dict with the new
        sub-state populated."""
        physiology = _physiology_row(lt1=None)

        PhysiologyUpdateService._apply_updated_states(
            physiology,
            {PhysiologyParameter.LT1_HR: _state(value=142.0)},
        )

        assert physiology.lt1 is not None
        assert physiology.lt1["hr"]["value"] == 142.0
        assert physiology.lt1["power"] is None
        assert physiology.lt1["pace"] is None


# ---------------------------------------------------------------------------
# Registration in app/services/__init__.py.
# ---------------------------------------------------------------------------


class TestServiceRegistration:
    """``PhysiologyUpdateService``, ``PhysiologyUpdateResult``, and
    ``MissingAthletePhysiologyError`` are importable from
    ``app.services``."""

    def test_physiology_update_service_importable_from_app_services(
        self,
    ) -> None:
        """``from app.services import PhysiologyUpdateService`` works."""
        from app.services import PhysiologyUpdateService as Imported

        assert Imported is PhysiologyUpdateService

    def test_physiology_update_result_importable_from_app_services(
        self,
    ) -> None:
        """``from app.services import PhysiologyUpdateResult`` works."""
        from app.services import PhysiologyUpdateResult as Imported

        assert Imported is PhysiologyUpdateResult

    def test_missing_physiology_error_importable_from_app_services(
        self,
    ) -> None:
        """``from app.services import MissingAthletePhysiologyError``
        works."""
        from app.services import MissingAthletePhysiologyError as Imported

        assert Imported is MissingAthletePhysiologyError
