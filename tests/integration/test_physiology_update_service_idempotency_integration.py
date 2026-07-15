"""Integration tests for ``PhysiologyUpdateService`` idempotency at the real-DB layer.

The unit tests in ``tests/unit/test_physiology_update_service_orchestration.py``
exercise the idempotency branch with ``AsyncMock``-backed repositories,
so they only prove the in-memory branching is correct. This integration
layer exercises the *real* test database to confirm the contract holds
end-to-end:

* The dedup lookup against
  ``PhysiologyMeasurementRepository.get_recent_for_parameter`` returns
  the matching row at the real-DB layer when the same observation has
  already been written.
* A duplicate observation (same ``parameter``, ``source``,
  ``measurement_date``, ``observed_value``, ``activity_id``) still
  writes the ``PhysiologyMeasurement`` audit row — the audit table is
  the complete observation history.
* A duplicate observation does NOT mutate the ``AthletePhysiology``
  JSONB columns — the prior state is preserved verbatim.
* A duplicate observation does NOT fire the ``physiology_updated``
  event — no ``SystemEvent`` row is written, no ``SystemEventOutbox``
  row is written.
* The dedup key matches the architecture contract: the same
  ``(parameter, observed_value, measurement_date, source)`` tuple
  (extended with ``activity_id`` to catch within-activity duplicates).

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
from app.models.physiology_measurement import PhysiologyMeasurement
from app.models.system_event import SystemEvent, SystemEventOutbox
from app.services.physiology_update_service import PhysiologyUpdateService
from app.services.threshold_detection_service import ThresholdObservation
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-06-15",
) -> Dict[str, Any]:
    """Build a full ``PhysiologyParameterState`` dict.

    ``last_observation_date`` defaults to ``"2026-06-15"`` to match
    the default ``measurement_date`` of the sibling ``_observation()``
    helper. Tests that need a different gap (e.g. an explicit 7-day
    decay exercise) pass the date explicitly. The previous default
    of ``"2026-05-01"`` created a 45-day gap that decayed the prior
    weight via the 42-day time constant, causing tests asserting
    same-day math to fail (the unit-test fix is recorded in
    ``tests/README.md`` dated 2026-07-13; this is the same fix
    extended to the integration layer).
    """
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
    """Build a real ``ThresholdObservation`` dataclass instance.

    ``activity_id`` defaults to ``None``. The
    ``physiology_measurements.activity_id`` column is nullable, so
    ``None`` bypasses the FK constraint cleanly. Tests that need
    a specific ``activity_id`` (e.g. for the dedup key tests) pass
    an explicit value AFTER creating the matching ``Activity`` row
    with the ``make_activity`` factory — see
    ``tests/utils/factories.py``. The previous default of
    ``uuid.uuid4()`` violated the FK because no corresponding
    ``Activity`` row existed.

    The ``cast(uuid.UUID, activity_id)`` is a type-system-only
    suppression: ``ThresholdObservation.activity_id`` is typed
    ``uuid.UUID`` (not ``Optional``) in the dataclass, but the
    production ``PhysiologyMeasurement`` column IS nullable, and
    the test helper explicitly supports the ``None`` case. At
    runtime Python does not enforce the dataclass type, so a
    ``None`` value is stored verbatim and the service writes
    ``activity_id=None`` to the DB row.
    """
    return ThresholdObservation(
        parameter=parameter,
        observed_value=observed_value,
        source=source,
        weight=weight,
        activity_id=cast(uuid.UUID, activity_id),
        measurement_date=measurement_date,
        algorithm_used=algorithm_used,
        confidence_weight=confidence_weight,
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
    columns. See the equivalent helper in
    ``test_physiology_update_service_integration.py`` for the
    conftest-listener rationale."""
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
# Duplicate detection — same observation twice.
# ---------------------------------------------------------------------------


class TestDuplicateObservationInSameCall:
    """Submitting the same observation twice in one
    ``apply_observations`` call: the second copy is detected as a
    duplicate and treated as audit-only."""

    @pytest.mark.asyncio
    async def test_second_observation_writes_measurement_but_does_not_mutate(
        self, db_session: AsyncSession
    ) -> None:
        """Two identical observations in the same batch produce two
        ``PhysiologyMeasurement`` rows (audit completeness) but the
        ``AthletePhysiology`` JSONB columns reflect the state after
        the FIRST observation only — the second is deduped."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        # Create a real Activity row so the
        # ``physiology_measurements.activity_id`` FK is satisfied.
        # The dedup key includes ``activity_id``, so this test
        # specifically needs a non-null value here.
        from tests.utils.factories import make_activity

        activity = await make_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        service = PhysiologyUpdateService(db_session)
        observation = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
            activity_id=activity.id,
            measurement_date=date(2026, 6, 15),
        )
        # Two copies of the same observation in the same batch.
        observations = [observation, observation]

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=observations,
        )
        # Both observations wrote a measurement row.
        assert result.measurements_written == 2
        await db_session.commit()

        # Two measurement rows exist (audit completeness).
        measurements = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(measurements) == 2

        # The posterior reflects the FIRST observation only —
        # the second was deduped so the prior_weight is 1.5, not
        # 2.5 (which it would be if both observations had been
        # applied).
        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.lt2["hr"]["prior_weight"] == pytest.approx(1.5)

    @pytest.mark.asyncio
    async def test_second_observation_does_not_fire_event(
        self, db_session: AsyncSession
    ) -> None:
        """When the second copy of the observation is deduped, no
        ``SystemEvent`` row is written and no outbox row is
        written. The event fires only for the first observation's
        shift (or not at all if the shift is < 1 unit)."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service = PhysiologyUpdateService(db_session)
        observation = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
        )
        observations = [observation, observation]

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=observations,
        )
        # Both observations wrote a measurement row, but only the
        # first contributed to shifted_parameters.
        assert result.measurements_written == 2
        assert result.shifted_parameters == [PhysiologyParameter.LT2_HR]
        await db_session.commit()

        # Exactly one event — for the first observation's shift.
        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "physiology_updated",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(events) == 1

        # Exactly one outbox row — paired with the event.
        outbox_rows = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        assert len(outbox_rows) == 1


# ---------------------------------------------------------------------------
# Duplicate detection — same observation across separate calls.
# ---------------------------------------------------------------------------


class TestDuplicateObservationAcrossCalls:
    """The second ``apply_observations`` call detects the observation
    written by the first call via the
    ``get_recent_for_parameter`` query at the real-DB layer."""

    @pytest.mark.asyncio
    async def test_second_call_dedupes_observation_written_by_first(
        self, db_session: AsyncSession
    ) -> None:
        """The first call writes a measurement and shifts the
        posterior. The second call (with the same observation) is
        deduped at the real-DB layer — it writes a second
        measurement but does not shift the posterior further."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        # Create a real Activity row so the
        # ``physiology_measurements.activity_id`` FK is satisfied
        # for both calls. The dedup key includes ``activity_id``,
        # so the test needs a stable activity reference across the
        # two ``apply_observations`` calls.
        from tests.utils.factories import make_activity

        activity = await make_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        service = PhysiologyUpdateService(db_session)
        observation = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
            activity_id=activity.id,
            measurement_date=date(2026, 6, 15),
        )

        # First call — new observation, shifts the posterior.
        first_result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[observation],
        )
        assert first_result.shifted_parameters == [
            PhysiologyParameter.LT2_HR
        ]
        assert first_result.measurements_written == 1
        await db_session.commit()

        # Capture the post-first-call state.
        after_first = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        prior_weight_after_first = after_first.lt2["hr"]["prior_weight"]
        value_after_first = after_first.lt2["hr"]["value"]

        # Second call — same observation. Deduped at the DB layer.
        second_result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[observation],
        )
        # The second call's observation was deduped — it
        # contributed nothing to shifted_parameters.
        assert second_result.shifted_parameters == []
        # But it still wrote the audit row.
        assert second_result.measurements_written == 1
        await db_session.commit()

        # Posterior is unchanged from the first call.
        after_second = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert after_second.lt2["hr"]["prior_weight"] == pytest.approx(
            prior_weight_after_first
        )
        assert after_second.lt2["hr"]["value"] == pytest.approx(
            value_after_first
        )

        # Two measurement rows total (audit completeness).
        measurements = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(measurements) == 2

        # Exactly one event (the first call fired it; the second
        # call's observation was deduped so no new event).
        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "physiology_updated",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(events) == 1


# ---------------------------------------------------------------------------
# Duplicate detection — different observations are NOT duplicates.
# ---------------------------------------------------------------------------


class TestNonDuplicatesAreNotDeduped:
    """Observations that differ on any of the dedup-key fields are
    treated as distinct and both contribute to the posterior update."""

    @pytest.mark.asyncio
    async def test_different_observed_value_is_not_a_duplicate(
        self, db_session: AsyncSession
    ) -> None:
        """Two observations with the same parameter, source, date,
        and activity_id but different ``observed_value`` are NOT
        duplicates — both contribute to the posterior."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        # Create a real Activity row so the
        # ``physiology_measurements.activity_id`` FK is satisfied.
        from tests.utils.factories import make_activity

        activity = await make_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        service = PhysiologyUpdateService(db_session)
        first = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
            activity_id=activity.id,
            measurement_date=date(2026, 6, 15),
        )
        second = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=172.0,  # different value
            weight=1.0,
            activity_id=activity.id,
            measurement_date=date(2026, 6, 15),
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[first, second],
        )
        # Both observations were applied — neither was deduped.
        # (shifted_parameters still depends on the > 1 unit gate.)
        assert result.measurements_written == 2
        await db_session.commit()

        # Two measurement rows.
        measurements = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(measurements) == 2
        # Posterior reflects BOTH observations.
        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        # prior_weight = 0.5 + 1.0 + 1.0 = 2.5
        assert fresh.lt2["hr"]["prior_weight"] == pytest.approx(2.5)

    @pytest.mark.asyncio
    async def test_different_activity_id_is_not_a_duplicate(
        self, db_session: AsyncSession
    ) -> None:
        """Two observations with the same parameter, source, date,
        and value but different ``activity_id`` are NOT
        duplicates — both contribute to the posterior."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        # Two real Activity rows so the FK is satisfied and the
        # two observations carry distinct ``activity_id`` values
        # (the dedup key includes ``activity_id``).
        from tests.utils.factories import make_activity

        activity1 = await make_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity2 = await make_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 16),
        )
        service = PhysiologyUpdateService(db_session)
        # Different activity_id — same parameter/source/date/value.
        first = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
            activity_id=activity1.id,
            measurement_date=date(2026, 6, 15),
        )
        second = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
            activity_id=activity2.id,  # different activity
            measurement_date=date(2026, 6, 15),
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[first, second],
        )
        assert result.measurements_written == 2
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.lt2["hr"]["prior_weight"] == pytest.approx(2.5)

    @pytest.mark.asyncio
    async def test_different_source_is_not_a_duplicate(
        self, db_session: AsyncSession
    ) -> None:
        """Two observations with the same parameter, date, value,
        and activity_id but different ``source`` are NOT
        duplicates — the source is part of the dedup key."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        # Real Activity row so the FK is satisfied.
        from tests.utils.factories import make_activity

        activity = await make_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        service = PhysiologyUpdateService(db_session)
        first = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=1.0,
            activity_id=activity.id,
            measurement_date=date(2026, 6, 15),
        )
        second = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            source=MeasurementSource.TRAINING_RR_INFLECTION,  # different source
            weight=1.0,
            activity_id=activity.id,
            measurement_date=date(2026, 6, 15),
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[first, second],
        )
        # Both applied — different sources, so neither is a
        # duplicate of the other.
        assert result.measurements_written == 2
        await db_session.commit()

        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]
        assert fresh.lt2["hr"]["prior_weight"] == pytest.approx(2.5)
