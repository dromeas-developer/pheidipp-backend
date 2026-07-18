"""Integration tests for ``PhysiologyUpdateService`` first-observation bootstrap at the real-DB layer.

The architecture invariant states: "cp and vo2max are null until a
qualifying observation is made. They are never bootstrapped from
questionnaire estimates."

The unit tests in
``tests/unit/test_physiology_update_service_orchestration.py`` exercise
the ``init_null_parameter_state`` branch with ``AsyncMock``-backed
repositories, so they only prove the in-memory branching is correct.
This integration layer exercises the *real* test database to confirm:

* A first CP observation against a previously-null ``cp`` column
  transitions the column from NULL to a non-null
  ``PhysiologyParameterState`` dict at the real-DB layer.
* The bootstrapped state's ``value``, ``uncertainty``,
  ``prior_weight``, ``dominant_source``, and
  ``last_observation_date`` fields match the observation exactly.
* A second CP observation applies ``bayesian_update`` against the
  PERSISTED bootstrapped state — the prior_weight grows from
  ``observation.weight`` to ``observation.weight + observation.weight``.
* The shift detection for the first observation does NOT add CP to
  ``shifted_parameters`` (the architecture's ``> 1 unit`` gate
  applies only to parameters with an existing estimate) — this
  pins the documented behaviour at the real-DB layer.

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, Optional, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import (
    MeasurementSource,
    PhysiologyParameter,
)
from app.services.physiology_update_service import PhysiologyUpdateService
from app.services.threshold_detection_service import ThresholdObservation
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _observation(
    *,
    parameter: PhysiologyParameter = PhysiologyParameter.CP,
    observed_value: float = 250.0,
    source: MeasurementSource = (
        MeasurementSource.TRAINING_POWER_HR_RATIO
    ),
    weight: float = 1.0,
    measurement_date: date = date(2026, 6, 15),
) -> ThresholdObservation:
    """Build a real ``ThresholdObservation`` for a CP observation.

    ``activity_id`` defaults to ``None`` so the
    ``physiology_measurements.activity_id`` FK is bypassed — the
    column is nullable. Successive observations in a test session
    are distinguished by the
    ``(parameter, source, measurement_date, observed_value)`` tuple
    (the dedup key does not require ``activity_id``), so a
    ``None`` ``activity_id`` does not cause spurious dedup
    matches across separate observations.

    The ``cast(uuid.UUID, None)`` is a type-system-only suppression:
    ``ThresholdObservation.activity_id`` is typed ``uuid.UUID``
    (not ``Optional``) in the dataclass, but the production
    ``PhysiologyMeasurement`` column IS nullable. At runtime
    Python does not enforce the dataclass type, so ``None`` is
    stored verbatim and the service writes ``activity_id=None``
    to the DB row.
    """
    return ThresholdObservation(
        parameter=parameter,
        observed_value=observed_value,
        source=source,
        weight=weight,
        activity_id=cast(uuid.UUID, None),
        measurement_date=measurement_date,
        algorithm_used="training_power_hr_ratio_v1",
        confidence_weight=0.85,
    )


async def _create_physiology_row(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    lt1: Optional[Dict[str, Any]] = None,
    lt2: Optional[Dict[str, Any]] = None,
    cp: Optional[Dict[str, Any]] = None,
    max_hr: Optional[Dict[str, Any]] = None,
) -> AthletePhysiology:
    """Insert a real ``AthletePhysiology`` row with the given JSONB
    columns. ``cp`` defaults to ``None`` so the test exercises the
    null-→-non-null bootstrap path."""
    row = AthletePhysiology(
        athlete_id=athlete_id,
        lt1=lt1 if lt1 is not None else {"hr": None, "power": None, "pace": None},
        lt2=lt2 if lt2 is not None else {"hr": None, "power": None, "pace": None},
        cp=cp,
        max_hr=max_hr,
    )
    db_session.add(row)
    await db_session.flush()
    return row


# ---------------------------------------------------------------------------
# First CP observation — null → bootstrapped state.
# ---------------------------------------------------------------------------


class TestFirstCpObservation:
    """The first CP observation bootstraps a fresh
    ``PhysiologyParameterState`` from ``init_null_parameter_state``,
    transitioning the ``cp`` column from NULL to a non-null dict."""

    @pytest.mark.asyncio
    async def test_cp_transitions_from_null_to_physiology_parameter_state(
        self, db_session: AsyncSession
    ) -> None:
        """The first CP observation writes a non-null
        ``PhysiologyParameterState`` to the ``cp`` column at the
        real-DB layer."""
        athlete = await make_athlete(db_session)
        # cp is null at insert time.
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=None,
        )
        # Sanity check — the pre-call state has cp=null.
        pre = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert pre.cp is None

        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=250.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=1.0,
            measurement_date=date(2026, 6, 15),
        )

        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        await db_session.commit()

        # Post-commit fresh read — cp is now non-null.
        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.cp is not None
        assert isinstance(fresh.cp, dict)

    @pytest.mark.asyncio
    async def test_bootstrapped_state_carries_observation_fields(
        self, db_session: AsyncSession
    ) -> None:
        """The bootstrapped state's fields match the observation
        and the architecture constants:
        ``value = observed_value``,
        ``uncertainty = INITIAL_UNCERTAINTY`` (1.0),
        ``prior_weight = observation.weight``,
        ``dominant_source = observation.source.value``,
        ``last_observation_date = observation.measurement_date``.
        """
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=None,
        )
        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=260.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=1.5,
            measurement_date=date(2026, 6, 15),
        )

        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.cp is not None
        assert fresh.cp["value"] == pytest.approx(260.0)
        # INITIAL_UNCERTAINTY = 1.0 per the architecture constants.
        assert fresh.cp["uncertainty"] == pytest.approx(1.0)
        assert fresh.cp["prior_weight"] == pytest.approx(1.5)
        # dominant_source is the MeasurementSource.value string.
        assert fresh.cp["dominant_source"] == (
            MeasurementSource.TRAINING_POWER_HR_RATIO.value
        )
        # last_observation_date is the ISO-8601 date string.
        assert fresh.cp["last_observation_date"] == "2026-06-15"

    @pytest.mark.asyncio
    async def test_first_observation_does_not_fire_event(
        self, db_session: AsyncSession
    ) -> None:
        """The first observation for a previously-null parameter
        does NOT fire ``physiology_updated`` — the shift detection
        is short-circuited by the ``current_state is None`` guard
        (the architecture's ``> 1 unit`` gate applies only to
        parameters with an existing estimate)."""
        from app.models.system_event import SystemEvent

        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=None,
        )
        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=250.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=1.0,
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        # shifted_parameters does NOT contain CP — the
        # current_state is None guard suppresses the shift
        # detection on the first observation.
        assert result.shifted_parameters == []
        # The audit row was still written.
        assert result.measurements_written == 1
        await db_session.commit()

        # No SystemEvent row was written.
        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "physiology_updated",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(events) == 0


# ---------------------------------------------------------------------------
# Second CP observation — bayesian_update against the bootstrapped state.
# ---------------------------------------------------------------------------


class TestSecondCpObservation:
    """The second CP observation applies ``bayesian_update`` against
    the PERSISTED bootstrapped state — the prior_weight grows and
    the posterior value shifts."""

    @pytest.mark.asyncio
    async def test_second_observation_grows_prior_weight(
        self, db_session: AsyncSession
    ) -> None:
        """After the first observation, ``prior_weight = 1.0``.
        The second observation (weight=1.0, same date guard
        bypassed by a different date) grows ``prior_weight`` to
        2.0 at the real-DB layer."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=None,
        )
        service = PhysiologyUpdateService(db_session)

        # First observation — bootstraps the state.
        first = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=250.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=1.0,
            measurement_date=date(2026, 6, 15),
        )
        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[first],
        )

        # Second observation — same date as the first, but
        # distinct ``observed_value`` (260 vs 250) so the dedup
        # key ``(parameter, source, measurement_date,
        # observed_value)`` does not catch it. Same-day ensures
        # the 42-day decay factor is ``exp(-0/42) = 1.0``
        # between observations, so the expected prior_weight
        # of 2.0 matches the implementation's linear
        # accumulation. The decay-between-observations behaviour
        # is covered by ``TestBayesianUpdatePriorDecay`` in the
        # unit tests.
        second = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=260.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=1.0,
            measurement_date=date(2026, 6, 15),
        )
        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[second],
        )
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.cp is not None
        # prior_weight: 0 (cp was null) + 1.0 (first) + 1.0 (second)
        # = 2.0. The architecture's init_null_parameter_state uses
        # the observation's weight as the initial prior_weight.
        assert fresh.cp["prior_weight"] == pytest.approx(2.0)
        # Posterior value is the weighted blend of both
        # observations: (250 * 1.0 + 260 * 1.0) / 2.0 = 255.0.
        assert fresh.cp["value"] == pytest.approx(255.0)

    @pytest.mark.asyncio
    async def test_second_observation_fires_event_when_shift_exceeds_one(
        self, db_session: AsyncSession
    ) -> None:
        """The second observation's posterior shift (vs the
        bootstrapped state's value) exceeds 1 watt, so the
        ``physiology_updated`` event fires."""
        from app.models.system_event import SystemEvent

        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            cp=None,
        )
        service = PhysiologyUpdateService(db_session)

        # First observation — bootstraps cp=250.
        first = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=250.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=1.0,
            measurement_date=date(2026, 6, 15),
        )
        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[first],
        )

        # Second observation — same date, distinct
        # ``observed_value`` (260 vs 250) to avoid dedup; see
        # ``test_second_observation_grows_prior_weight`` for the
        # rationale on same-day vs multi-day dates. Value 260
        # is 10 watts above the bootstrapped state. The shift
        # from 250 to 260 is > 1 watt, so the event fires.
        second = _observation(
            parameter=PhysiologyParameter.CP,
            observed_value=260.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=1.0,
            measurement_date=date(2026, 6, 15),
        )
        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[second],
        )
        # CP is in shifted_parameters (the second observation's
        # shift exceeded 1 watt).
        assert PhysiologyParameter.CP in result.shifted_parameters
        await db_session.commit()

        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "physiology_updated",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(events) == 1
        event = events[0]
        assert event.payload["parameters_updated"] == ["cp"]
        assert "cp" in event.payload["dominant_sources"]
        assert "cp" in event.payload["prior_weights"]
        # The prior_weight in the payload is the post-update total.
        assert event.payload["prior_weights"]["cp"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# max_hr first observation — same bootstrap path.
# ---------------------------------------------------------------------------


class TestFirstMaxHrObservation:
    """The first ``max_hr`` observation against a previously-null
    ``max_hr`` column also bootstraps a fresh
    ``PhysiologyParameterState``."""

    @pytest.mark.asyncio
    async def test_max_hr_bootstraps_from_null(
        self, db_session: AsyncSession
    ) -> None:
        """The first ``max_hr`` observation transitions
        ``max_hr`` from NULL to a non-null state at the real-DB
        layer."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            max_hr=None,
        )
        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.MAX_HR,
            observed_value=195.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=1.0,
        )

        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.max_hr is not None
        assert fresh.max_hr["value"] == pytest.approx(195.0)
        assert fresh.max_hr["prior_weight"] == pytest.approx(1.0)
        assert fresh.max_hr["uncertainty"] == pytest.approx(1.0)
        assert fresh.max_hr["last_observation_date"] == "2026-06-15"
