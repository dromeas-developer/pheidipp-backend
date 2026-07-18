"""Integration tests for ``PhysiologyUpdateService`` end-to-end DB round-trip.

The unit tests in ``tests/unit/test_physiology_update_service_orchestration.py``
exercise the service with ``AsyncMock``-backed repositories and a mocked
``EventPublisher``, so they only prove the in-memory branching is
correct. This integration layer exercises the *real* test database
to confirm the service ↔ real repositories ↔ real event outbox
contract holds end-to-end:

* ``AthletePhysiology`` JSONB columns (``lt1``, ``lt2``, ``cp``,
  ``max_hr``) are mutated in place and the mutation persists at
  the DB layer — ``flag_modified`` triggers SQLAlchemy to emit the
  JSONB change.
* ``PhysiologyMeasurement`` rows are written for every observation
  in the batch (unconditional — even when the posterior does not
  shift) and carry every observation field.
* A ``SystemEvent`` row with ``event_type="physiology_updated"`` is
  written in the same transaction as the ``AthletePhysiology``
  update, paired with a ``SystemEventOutbox`` row in ``PENDING``
  status, ONLY when at least one parameter shifted by > 1 unit.
* No ``physiology_updated`` event is written when every parameter's
  posterior shifted by <= 1 unit.
* The ``AthletePhysiology`` row ``id`` is preserved across the
  update — no second row is created.
* The ``updated_at`` ``onupdate=`` hook fires on ``update_in_place``.

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/02-computations/physiology-update.md
              docs/architecture/01-entities/athlete-physiology.md
              docs/architecture/00-foundations/event-catalogue.md
              docs/adr/004-event-persistence-atomicity.md (transactional outbox)
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
from app.models.system_event import (
    EventPublicationStatus,
    SystemEvent,
    SystemEventOutbox,
)
from app.services.physiology_update_service import (
    MissingAthletePhysiologyError,
    PhysiologyUpdateService,
)
from app.services.threshold_detection_service import ThresholdObservation
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers — small focused builders for the test fixtures.
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

    The conftest ``_default_athlete_physiology_fields`` before_insert
    listener fills ``lt1`` / ``lt2`` with
    ``{"hr": 150, "source": "population_default"}`` when the column
    is null at insert time. That shape is NOT a valid
    ``PhysiologyParameterState`` — the Bayesian update will fail when
    it tries to read ``uncertainty`` or ``prior_weight``. This helper
    always returns a full PhysiologyParameterState so the service can
    navigate the JSONB path without raising.

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


def _empty_lt1() -> Dict[str, Any]:
    """Empty three-dimension container — no estimates yet."""
    return {"hr": None, "power": None, "pace": None}


def _empty_lt2() -> Dict[str, Any]:
    """Empty three-dimension container — no estimates yet."""
    return {"hr": None, "power": None, "pace": None}


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
    ``None`` bypasses the FK constraint cleanly. Tests that
    specifically want to attach a measurement to a real activity
    (e.g. for the idempotency dedup test) pass an explicit
    ``activity_id`` AFTER creating the matching ``Activity`` row
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
    columns.

    ``lt1`` and ``lt2`` default to the empty three-dimension
    container so the row satisfies the NOT NULL constraint. If the
    caller passes a full ``PhysiologyParameterState`` for one of
    the sub-dimensions, it lands verbatim in the JSONB column.

    Uses ``session.add`` + ``flush`` so the row is visible inside
    the transaction but not committed — the service's
    ``update_in_place`` flush will see it and mutate it in place.
    """
    row = AthletePhysiology(
        athlete_id=athlete_id,
        lt1=lt1 if lt1 is not None else _empty_lt1(),
        lt2=lt2 if lt2 is not None else _empty_lt2(),
        cp=cp,
        max_hr=max_hr,
    )
    db_session.add(row)
    await db_session.flush()
    return row


# ---------------------------------------------------------------------------
# Service construction — real DB.
# ---------------------------------------------------------------------------


class TestServiceConstructionIntegration:
    """``PhysiologyUpdateService`` builds with default dependencies
    from a real ``AsyncSession``."""

    @pytest.mark.asyncio
    async def test_service_builds_default_repos_and_publisher(
        self, db_session: AsyncSession
    ) -> None:
        """The service can be constructed with only ``db_session`` —
        repositories and the ``EventPublisher`` are built from the
        session. The default publisher is bound to the same
        session, so the event rows land in the same transaction
        as the physiology update."""
        service = PhysiologyUpdateService(db_session)

        # The default repos are constructed from the session.
        assert service.athlete_physiology is not None
        assert service.physiology_measurements is not None
        assert service.events is not None
        # Session identity is preserved (no copy).
        assert service.session is db_session

    @pytest.mark.asyncio
    async def test_service_with_missing_physiology_raises_at_db_layer(
        self, db_session: AsyncSession
    ) -> None:
        """``apply_observations`` raises
        ``MissingAthletePhysiologyError`` when no row exists for
        ``athlete_id`` at the real-DB layer."""
        athlete = await make_athlete(db_session)
        service = PhysiologyUpdateService(db_session)

        with pytest.raises(MissingAthletePhysiologyError):
            await service.apply_observations(
                athlete_id=athlete.id,
                observations=[_observation()],
            )


# ---------------------------------------------------------------------------
# AthletePhysiology JSONB persistence — posterior shift > 1 unit.
# ---------------------------------------------------------------------------


class TestApplyObservationsPersistsPosterior:
    """``apply_observations`` mutates the ``AthletePhysiology`` JSONB
    columns at the real-DB layer."""

    @pytest.mark.asyncio
    async def test_lt2_hr_posterior_persists_after_commit(
        self, db_session: AsyncSession
    ) -> None:
        """An observation that shifts ``lt2.hr`` posterior by > 1
        bpm persists the new value to the JSONB column at the
        real-DB layer (verified by a fresh SELECT after commit)."""
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
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
            measurement_date=date(2026, 6, 15),
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        # Commit the transaction so the JSONB mutation is visible
        # to a fresh SELECT.
        await db_session.commit()

        # Fresh read — uses a new ORM identity, no in-memory state.
        fresh = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()[0]

        # The lt2.hr value is between 160 (prior) and 170 (obs),
        # weighted toward the prior due to its higher weight
        # after decay: posterior mean = (160*0.5 + 170*1.0) / 1.5.
        expected_value = (160.0 * 0.5 + 170.0 * 1.0) / 1.5
        assert fresh.lt2["hr"]["value"] == pytest.approx(
            expected_value, abs=0.01
        )
        # prior_weight grew from 0.5 to 1.5.
        assert fresh.lt2["hr"]["prior_weight"] == pytest.approx(1.5)
        # The in-memory return value matches the persisted state.
        assert result.physiology.lt2["hr"]["value"] == pytest.approx(
            expected_value, abs=0.01
        )

    @pytest.mark.asyncio
    async def test_existing_lt2_hr_value_persists_when_only_lt1_updated(
        self, db_session: AsyncSession
    ) -> None:
        """Only the touched JSONB sub-state changes — sibling
        sub-states (and the other outer column) are preserved at
        the DB layer. An ``lt1.hr`` update must not disturb
        ``lt2.hr``."""
        athlete = await make_athlete(db_session)
        original_lt1_hr = _state(value=150.0, prior_weight=0.5)
        original_lt2_hr = _state(value=170.0, prior_weight=2.0)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt1={
                "hr": original_lt1_hr,
                "power": None,
                "pace": None,
            },
            lt2={
                "hr": original_lt2_hr,
                "power": None,
                "pace": None,
            },
        )
        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=155.0,
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

        # lt1.hr was updated — new value blends prior and obs.
        expected_lt1 = (150.0 * 0.5 + 155.0 * 1.0) / 1.5
        assert fresh.lt1["hr"]["value"] == pytest.approx(
            expected_lt1, abs=0.01
        )
        # lt2.hr is unchanged at the DB layer.
        assert fresh.lt2["hr"]["value"] == pytest.approx(170.0)
        assert fresh.lt2["hr"]["prior_weight"] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_athlete_physiology_row_id_preserved_across_update(
        self, db_session: AsyncSession
    ) -> None:
        """The ``AthletePhysiology.id`` is preserved across the
        update — no second row is created by ``update_in_place``."""
        athlete = await make_athlete(db_session)
        row = await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0),
                "power": None,
                "pace": None,
            },
        )
        original_id = row.id
        service = PhysiologyUpdateService(db_session)

        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[_observation()],
        )
        await db_session.commit()

        # Count rows for the athlete — must be exactly 1.
        rows = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].id == original_id

    @pytest.mark.asyncio
    async def test_updated_at_hook_fires_on_update_in_place(
        self, db_session: AsyncSession
    ) -> None:
        """The ``AthletePhysiology.updated_at`` ``onupdate=`` hook
        fires when ``update_in_place`` flushes the mutation."""
        athlete = await make_athlete(db_session)
        row = await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0),
                "power": None,
                "pace": None,
            },
        )
        await db_session.commit()
        original_updated_at = row.updated_at

        # Sleep a tiny amount to make the timestamp difference
        # observable at second granularity. ``updated_at`` is a
        # ``DateTime(timezone=True)`` — second-precision is the
        # minimum the DB will store.
        import asyncio
        await asyncio.sleep(1.1)

        service = PhysiologyUpdateService(db_session)
        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[_observation()],
        )
        await db_session.commit()

        # Refresh to get the latest updated_at from the DB.
        await db_session.refresh(row)
        assert row.updated_at > original_updated_at


# ---------------------------------------------------------------------------
# PhysiologyMeasurement audit rows — unconditional write.
# ---------------------------------------------------------------------------


class TestApplyObservationsWritesMeasurements:
    """``apply_observations`` writes one ``PhysiologyMeasurement``
    row per observation, unconditionally, at the real-DB layer."""

    @pytest.mark.asyncio
    async def test_measurement_row_persists_for_single_observation(
        self, db_session: AsyncSession
    ) -> None:
        """A single observation produces a persisted
        ``PhysiologyMeasurement`` row with all observation fields."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0),
                "power": None,
                "pace": None,
            },
        )
        # Create a real Activity row so the
        # ``physiology_measurements.activity_id`` FK is satisfied
        # — the test asserts ``row.activity_id == activity_id`` so
        # it specifically needs a real Activity reference.
        from tests.utils.factories import make_activity

        activity = await make_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=1.0,
            activity_id=activity.id,
            measurement_date=date(2026, 6, 15),
            algorithm_used="hr_deflection_v1",
            confidence_weight=0.92,
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        assert result.measurements_written == 1
        await db_session.commit()

        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.athlete_id == athlete.id
        assert row.activity_id == activity.id
        assert row.parameter == PhysiologyParameter.LT2_HR
        assert row.observed_value == pytest.approx(170.0)
        assert row.source == MeasurementSource.TRAINING_HR_DEFLECTION
        assert row.measurement_date == date(2026, 6, 15)
        assert row.algorithm_used == "hr_deflection_v1"
        assert row.confidence_weight == pytest.approx(0.92)
        # Training-derived observations carry NULL on the
        # lab/field-test-only columns.
        assert row.raw_data_reference is None
        assert row.notes is None

    @pytest.mark.asyncio
    async def test_one_measurement_per_observation_in_batch(
        self, db_session: AsyncSession
    ) -> None:
        """Three observations in one batch produce three persisted
        ``PhysiologyMeasurement`` rows."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=160.0),
                "power": None,
                "pace": None,
            },
        )
        service = PhysiologyUpdateService(db_session)
        observations = [_observation() for _ in range(3)]

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=observations,
        )
        assert result.measurements_written == 3
        await db_session.commit()

        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_measurement_written_even_when_posterior_does_not_shift(
        self, db_session: AsyncSession
    ) -> None:
        """The ``PhysiologyMeasurement`` row is written even when
        the posterior shift is < 1 unit (the audit row is
        unconditional — only the ``physiology_updated`` event is
        gated on the > 1 unit shift)."""
        athlete = await make_athlete(db_session)
        # Current value=170, observation value=170.5 — posterior
        # is between 170 and 170.5, a shift of well under 1 bpm.
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=170.0, prior_weight=10.0),
                "power": None,
                "pace": None,
            },
        )
        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.5,
            weight=1.0,
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        # Posterior did NOT shift by > 1 unit.
        assert result.shifted_parameters == []
        # Measurement was still written.
        assert result.measurements_written == 1
        await db_session.commit()

        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# physiology_updated event — transactional outbox (ADR-004).
# ---------------------------------------------------------------------------


class TestPhysiologyUpdatedEvent:
    """``apply_observations`` writes the ``physiology_updated`` event
    to the transactional outbox (``SystemEvent`` + ``SystemEventOutbox``)
    in the same transaction as the ``AthletePhysiology`` update,
    ONLY when at least one parameter shifted by > 1 unit."""

    @pytest.mark.asyncio
    async def test_event_persisted_when_shift_exceeds_one_unit(
        self, db_session: AsyncSession
    ) -> None:
        """A posterior shift > 1 unit produces a ``SystemEvent`` row
        with ``event_type='physiology_updated'`` and a paired
        ``SystemEventOutbox`` row in PENDING status."""
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
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.0,
            weight=1.0,
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        assert PhysiologyParameter.LT2_HR in result.shifted_parameters
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
        assert event.athlete_id == athlete.id
        assert event.version == "v1"
        # Payload — exact keys per the architecture contract.
        assert event.payload["athlete_id"] == str(athlete.id)
        assert event.payload["parameters_updated"] == ["lt2_hr"]
        assert "lt2_hr" in event.payload["dominant_sources"]
        assert "lt2_hr" in event.payload["prior_weights"]
        # The dominant_source is the observation's source value
        # string (not the enum member).
        assert event.payload["dominant_sources"]["lt2_hr"] == (
            MeasurementSource.TRAINING_HR_DEFLECTION.value
        )
        # The prior_weight is the post-update total weight.
        assert event.payload["prior_weights"]["lt2_hr"] == pytest.approx(
            1.5
        )

    @pytest.mark.asyncio
    async def test_outbox_row_pending_status(
        self, db_session: AsyncSession
    ) -> None:
        """The paired ``SystemEventOutbox`` row exists with
        ``status='pending'`` — the platform publisher worker picks
        it up from there after commit."""
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

        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[_observation()],
        )
        await db_session.commit()

        event_ids = (
            await db_session.execute(
                select(SystemEvent.event_id).where(
                    SystemEvent.event_type == "physiology_updated",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(event_ids) == 1

        outbox_rows = (
            await db_session.execute(
                select(SystemEventOutbox).where(
                    SystemEventOutbox.event_id == event_ids[0]
                )
            )
        ).scalars().all()
        assert len(outbox_rows) == 1
        outbox = outbox_rows[0]
        assert outbox.status is EventPublicationStatus.PENDING
        assert outbox.attempts == 0

    @pytest.mark.asyncio
    async def test_event_not_persisted_when_shift_le_one_unit(
        self, db_session: AsyncSession
    ) -> None:
        """A posterior shift <= 1 unit does NOT produce a
        ``SystemEvent`` row. The measurement row is still written."""
        athlete = await make_athlete(db_session)
        # High prior weight keeps the posterior close to the prior.
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt2={
                "hr": _state(value=170.0, prior_weight=10.0),
                "power": None,
                "pace": None,
            },
        )
        service = PhysiologyUpdateService(db_session)
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.5,  # < 1 bpm shift
            weight=1.0,
        )

        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        assert result.shifted_parameters == []
        await db_session.commit()

        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "physiology_updated",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(events) == 0
        # No outbox row either.
        outbox_rows = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        assert len(outbox_rows) == 0
        # Measurement row was still written.
        measurements = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(measurements) == 1

    @pytest.mark.asyncio
    async def test_event_payload_includes_all_shifted_parameters(
        self, db_session: AsyncSession
    ) -> None:
        """When two parameters both shift > 1 unit, the event
        payload lists both in ``parameters_updated`` with their
        respective dominant_sources and prior_weights."""
        athlete = await make_athlete(db_session)
        await _create_physiology_row(
            db_session,
            athlete_id=athlete.id,
            lt1={
                "hr": _state(value=140.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
            lt2={
                "hr": _state(value=160.0, prior_weight=0.5),
                "power": None,
                "pace": None,
            },
        )
        service = PhysiologyUpdateService(db_session)
        observations = [
            _observation(
                parameter=PhysiologyParameter.LT1_HR,
                observed_value=148.0,
                weight=1.0,
            ),
            _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0,
                weight=1.0,
            ),
        ]

        await service.apply_observations(
            athlete_id=athlete.id,
            observations=observations,
        )
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
        # Both parameters in the payload — order is observation
        # order.
        assert event.payload["parameters_updated"] == ["lt1_hr", "lt2_hr"]
        assert "lt1_hr" in event.payload["dominant_sources"]
        assert "lt2_hr" in event.payload["dominant_sources"]
        assert "lt1_hr" in event.payload["prior_weights"]
        assert "lt2_hr" in event.payload["prior_weights"]

    @pytest.mark.asyncio
    async def test_event_atomicity_rolls_back_when_later_step_fails(
        self, db_session: AsyncSession
    ) -> None:
        """ADR-004 rule 'Event Persistence Atomicity' — the event
        row, the outbox row, the ``PhysiologyMeasurement`` row, and
        the ``AthletePhysiology`` update all land in the SAME
        transaction. A failure in any later step rolls back the
        whole batch.

        We trigger the failure by calling ``apply_observations``
        and then rolling back. A subsequent fresh session SELECT
        must see none of the new artefacts — the rollback unwinds
        everything in the second transaction.

        Implementation note: ``_create_physiology_row`` only
        flushes the fixture row, but the rollback test needs the
        fixture row to survive the rollback — otherwise the
        post-rollback SELECT returns an empty list and the
        ``scalars().all()[0]`` accessor raises ``IndexError``.
        Committing the fixture row in its own transaction isolates
        it from the subsequent ``apply_observations`` + rollback
        cycle, which is the correct ADR-004 boundary (the fixture
        row is committed state, the apply-observations batch is a
        new transaction that must roll back atomically).
        """
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
        # Commit the fixture row in its own transaction so it
        # survives the subsequent rollback. The apply_observations
        # call below opens a new transaction; its rollback must
        # unwind the observation batch but NOT the fixture row.
        await db_session.commit()
        service = PhysiologyUpdateService(db_session)

        await service.apply_observations(
            athlete_id=athlete.id,
            observations=[_observation()],
        )
        # Roll back instead of commit — simulates a downstream
        # failure in the worker task.
        #
        # Capture the athlete PK as a plain Python value BEFORE
        # the rollback. ``db_session.rollback()`` expires ALL ORM
        # instances tracked by the session, including the
        # ``athlete`` loaded above. Accessing ``athlete.id``
        # (or any other mapped attribute) on an expired instance
        # triggers an async lazy load, which fires outside the
        # greenlet context under async SQLAlchemy + NullPool,
        # raising ``MissingGreenlet``. The captured scalar
        # survives the rollback and is safe to use in subsequent
        # WHERE clauses. The pattern is recorded in
        # ``tests/README.md`` dated 2026-07-14 (pass 3, RC3) and
        # is first-class in ``tests/MOCKING_CONTRACT.md``
        # "Known Anti-Patterns".
        athlete_id = athlete.id
        await db_session.rollback()

        # No event row.
        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "physiology_updated",
                    SystemEvent.athlete_id == athlete_id,
                )
            )
        ).scalars().all()
        assert len(events) == 0
        # No measurement row.
        measurements = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete_id
                )
            )
        ).scalars().all()
        assert len(measurements) == 0
        # No outbox row.
        outbox_rows = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        assert len(outbox_rows) == 0
        # Physiology JSONB is unchanged — the rollback unwound the
        # update_in_place mutation.
        #
        # Use a column-level SELECT for the ``lt2`` JSONB value
        # instead of loading a full ``AthletePhysiology`` ORM
        # instance. After ``rollback()`` the session's connection
        # lifecycle is in a state where lazy attribute access on a
        # freshly-loaded instance triggers async IO outside the
        # greenlet context, raising ``MissingGreenlet``. Reading
        # the JSONB column directly returns the dict without going
        # through the ORM attribute layer, bypassing the hazard.
        # The pattern is recorded in ``tests/README.md`` dated
        # 2026-07-14 (pass 2, RC3) and is first-class in
        # ``tests/MOCKING_CONTRACT.md`` "Known Anti-Patterns".
        # The WHERE clause uses the captured ``athlete_id`` scalar
        # (see comment above) — accessing ``athlete.athlete_id``
        # on the expired instance would trigger the same
        # ``MissingGreenlet`` as the JSONB attribute access.
        fresh_lt2 = (
            await db_session.execute(
                select(AthletePhysiology.lt2).where(
                    AthletePhysiology.athlete_id == athlete_id
                )
            )
        ).scalar_one()
        assert fresh_lt2["hr"]["value"] == pytest.approx(160.0)
        assert fresh_lt2["hr"]["prior_weight"] == pytest.approx(0.5)
