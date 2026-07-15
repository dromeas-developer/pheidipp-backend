"""Integration tests for ``PhysiologyUpdateService`` confidence transitions at the real-DB layer.

The unit tests in
``tests/unit/test_physiology_update_service_orchestration.py`` exercise
the confidence-transition branch with ``AsyncMock``-backed
repositories, so they only prove the in-memory branching is correct.
This integration layer exercises the *real* test database to confirm:

* The ``prior_weight`` accumulates across calls against the PERSISTED
  ``AthletePhysiology`` state — the second call sees the first call's
  mutation, not the in-memory snapshot it had at the start of the
  first call.
* The 4.0 (LOW→MEDIUM) and 8.0 (MEDIUM→HIGH) thresholds are crossed
  in the real JSONB column values, verified by a fresh SELECT after
  commit.
* The ``metric_confidence`` returned in ``PhysiologyUpdateResult``
  reports the correct level for the post-update state.
* The ``confidence_transitions`` dict keys by metric name with
  ``(from_level, to_level)`` tuples, as expected by Plan P3's
  ``TwinRecalibrationService``.
* Higher-weight sources (RR inflection, weight=2.5) cross the 4.0
  threshold faster than lower-weight sources (HR deflection,
  weight=1.0) — verified at the real-DB layer.

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/00-foundations/confidence-model.md
              docs/architecture/02-computations/evidence-mapping.md
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
from app.services.physiology_update_service import (
    PhysiologyUpdateResult,
    PhysiologyUpdateService,
)
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
    measurement_date: date = date(2026, 6, 15),
) -> ThresholdObservation:
    """Build a real ``ThresholdObservation`` with deterministic
    fields. ``activity_id`` defaults to ``None`` so the
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
        algorithm_used="hr_deflection_v1",
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
    """Insert a real ``AthletePhysiology`` row."""
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


async def _read_lt2_hr_prior_weight(
    db_session: AsyncSession, athlete_id: uuid.UUID
) -> float:
    """Read the ``lt2.hr.prior_weight`` from the DB after a commit."""
    fresh = (
        await db_session.execute(
            select(AthletePhysiology).where(
                AthletePhysiology.athlete_id == athlete_id
            )
        )
    ).scalars().all()[0]
    return float(fresh.lt2["hr"]["prior_weight"])


# ---------------------------------------------------------------------------
# LOW → MEDIUM transition (at prior_weight >= 4.0).
# ---------------------------------------------------------------------------


class TestLowToMediumTransition:
    """Four HR-deflection observations (weight=1.0 each) push
    ``prior_weight`` from 0.5 to 4.5, crossing the 4.0 threshold
    and triggering a LOW→MEDIUM transition."""

    @pytest.mark.asyncio
    async def test_four_observations_reach_prior_weight_4_point_5(
        self, db_session: AsyncSession
    ) -> None:
        """Four observations accumulate ``prior_weight`` from 0.5
        to 4.5 at the real-DB layer (0.5 + 4 × 1.0 = 4.5)."""
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

        # Four observations, each with weight=1.0, all dated
        # 2026-06-15. Same-day observations ensure the 42-day
        # decay factor is ``exp(-0/42) = 1.0`` between
        # observations, so the test's expected value of
        # ``0.5 + 4 × 1.0 = 4.5`` matches the implementation's
        # linear accumulation. Observations are distinguished by
        # ``observed_value`` (170.0, 170.1, 170.2, 170.3), so the
        # dedup key ``(parameter, source, measurement_date,
        # observed_value)`` does not catch subsequent observations.
        # The decay-between-observations behaviour is covered by
        # ``TestBayesianUpdatePriorDecay`` in the unit tests.
        for i in range(4):
            obs = _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0 + i * 0.1,
                weight=1.0,
                measurement_date=date(2026, 6, 15),
            )
            await service.apply_observations(
                athlete_id=athlete.id,
                observations=[obs],
            )
        await db_session.commit()

        # The prior_weight accumulated against the persisted state.
        assert await _read_lt2_hr_prior_weight(
            db_session, athlete.id
        ) == pytest.approx(4.5)

    @pytest.mark.asyncio
    async def test_four_observations_trigger_low_to_medium_transition(
        self, db_session: AsyncSession
    ) -> None:
        """The 4th observation (which crosses prior_weight=4.0)
        reports a ``lt2_hr`` LOW→MEDIUM transition in
        ``confidence_transitions``."""
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

        # First 3 observations: prior_weight grows 0.5 → 3.5. Still
        # LOW (< 4.0). No transition.
        result: PhysiologyUpdateResult | None = None
        for i in range(3):
            obs = _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0 + i * 0.1,
                weight=1.0,
                measurement_date=date(2026, 6, 15 + i),
            )
            result = await service.apply_observations(
                athlete_id=athlete.id,
                observations=[obs],
            )
            # The metric_confidence is "low" until prior_weight
            # crosses 4.0.
            assert result.metric_confidence["lt2_hr"] == "low"

        # 4th observation: prior_weight grows 3.5 → 4.5. Crosses
        # 4.0 → MEDIUM.
        obs = _observation(
            parameter=PhysiologyParameter.LT2_HR,
            observed_value=170.3,
            weight=1.0,
            measurement_date=date(2026, 6, 19),
        )
        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=[obs],
        )
        assert result is not None
        assert result.metric_confidence["lt2_hr"] == "medium"
        assert "lt2_hr" in result.confidence_transitions
        from_level, to_level = result.confidence_transitions["lt2_hr"]
        assert from_level == "low"
        assert to_level == "medium"


# ---------------------------------------------------------------------------
# MEDIUM → HIGH transition (at prior_weight >= 8.0).
# ---------------------------------------------------------------------------


class TestMediumToHighTransition:
    """Eight HR-deflection observations (weight=1.0 each) push
    ``prior_weight`` from 0.5 to 8.5, crossing the 8.0 threshold
    and triggering a MEDIUM→HIGH transition."""

    @pytest.mark.asyncio
    async def test_eight_observations_reach_prior_weight_8_point_5(
        self, db_session: AsyncSession
    ) -> None:
        """Eight observations accumulate ``prior_weight`` from 0.5
        to 8.5 at the real-DB layer."""
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

        # Eight same-day observations — see
        # ``test_four_observations_reach_prior_weight_4_point_5``
        # for the rationale on same-day vs multi-day dates.
        for i in range(8):
            obs = _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0 + i * 0.1,
                weight=1.0,
                measurement_date=date(2026, 6, 15),
            )
            await service.apply_observations(
                athlete_id=athlete.id,
                observations=[obs],
            )
        await db_session.commit()

        assert await _read_lt2_hr_prior_weight(
            db_session, athlete.id
        ) == pytest.approx(8.5)

    @pytest.mark.asyncio
    async def test_eighth_observation_triggers_medium_to_high_transition(
        self, db_session: AsyncSession
    ) -> None:
        """The 8th observation (which crosses prior_weight=8.0)
        reports a ``lt2_hr`` MEDIUM→HIGH transition."""
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

        # Eight same-day observations — see
        # ``test_four_observations_reach_prior_weight_4_point_5``
        # for the rationale on same-day vs multi-day dates.
        result: PhysiologyUpdateResult | None = None
        for i in range(8):
            obs = _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0 + i * 0.1,
                weight=1.0,
                measurement_date=date(2026, 6, 15),
            )
            result = await service.apply_observations(
                athlete_id=athlete.id,
                observations=[obs],
            )

        # After the 8th observation, prior_weight=8.5 → HIGH.
        assert result is not None
        assert result.metric_confidence["lt2_hr"] == "high"
        assert "lt2_hr" in result.confidence_transitions
        from_level, to_level = result.confidence_transitions["lt2_hr"]
        assert from_level == "medium"
        assert to_level == "high"


# ---------------------------------------------------------------------------
# Higher-weight sources cross thresholds faster.
# ---------------------------------------------------------------------------


class TestHighWeightSourceCrossesThresholdFaster:
    """RR inflection observations carry weight=2.5 (per
    ``evidence-mapping.md``). Two such observations push
    ``prior_weight`` from 0.5 to 5.5, crossing the 4.0 threshold
    in a single call — faster than 4 HR-deflection observations
    (weight=1.0 each)."""

    @pytest.mark.asyncio
    async def test_two_rr_observations_reach_medium_confidence(
        self, db_session: AsyncSession
    ) -> None:
        """Two RR observations (weight=2.5 each) accumulate
        ``prior_weight`` from 0.5 to 5.5 → MEDIUM confidence."""
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

        # Two RR observations, dated one day apart so the dedup
        # window (from_date=measurement_date) does not catch the
        # second one.
        result: PhysiologyUpdateResult | None = None
        for i in range(2):
            obs = _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0 + i * 0.1,
                source=MeasurementSource.TRAINING_RR_INFLECTION,
                weight=2.5,
                measurement_date=date(2026, 6, 15 + i),
            )
            result = await service.apply_observations(
                athlete_id=athlete.id,
                observations=[obs],
            )

        # 0.5 + 2 × 2.5 = 5.5 → MEDIUM.
        assert result is not None
        assert result.metric_confidence["lt2_hr"] == "medium"
        assert "lt2_hr" in result.confidence_transitions
        from_level, to_level = result.confidence_transitions["lt2_hr"]
        assert from_level == "low"
        assert to_level == "medium"

    @pytest.mark.asyncio
    async def test_four_rr_observations_reach_high_confidence(
        self, db_session: AsyncSession
    ) -> None:
        """Four RR observations (weight=2.5 each) accumulate
        ``prior_weight`` from 0.5 to 10.5 → HIGH confidence.

        Implemented as a single ``apply_observations`` call with
        all four observations in one batch. The original loop
        pattern (one observation per call) cannot produce a
        ``("low", "high")`` transition on the 4th call: the 3rd
        call already crosses the 8.0 HIGH threshold (5.5 + 2.5
        = 8.0 with same-day dates; ~7.80 with 1-day gaps which
        is MEDIUM, not LOW), so the 4th call's pre-call level
        is never LOW. A batch call processes all 4 observations
        in one transaction and reports a single
        ``(pre_call_level, post_call_level)`` transition,
        making the ``("low", "high")`` transition observable.
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
        service = PhysiologyUpdateService(db_session)

        # Four observations in a single batch — same date, distinct
        # ``observed_value`` so the dedup key does not catch them.
        observations = [
            _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0 + i * 0.1,
                source=MeasurementSource.TRAINING_RR_INFLECTION,
                weight=2.5,
                measurement_date=date(2026, 6, 15),
            )
            for i in range(4)
        ]
        result = await service.apply_observations(
            athlete_id=athlete.id,
            observations=observations,
        )

        # 0.5 + 4 × 2.5 = 10.5 → HIGH. The batch transition is
        # ``(pre_call_level, post_call_level)`` — pre-call state was
        # LOW (prior_weight=0.5), post-call state is HIGH.
        assert result is not None
        assert result.metric_confidence["lt2_hr"] == "high"
        assert "lt2_hr" in result.confidence_transitions
        from_level, to_level = result.confidence_transitions["lt2_hr"]
        assert from_level == "low"
        assert to_level == "high"


# ---------------------------------------------------------------------------
# Subsequent calls continue to accumulate against the persisted state.
# ---------------------------------------------------------------------------


class TestSubsequentCallsAccumulateAgainstPersistedState:
    """Each ``apply_observations`` call sees the prior_weight
    accumulated by previous calls — the service does not carry
    in-memory state across calls."""

    @pytest.mark.asyncio
    async def test_three_calls_each_with_one_observation(
        self, db_session: AsyncSession
    ) -> None:
        """Three separate ``apply_observations`` calls, each with
        one observation, accumulate ``prior_weight`` from 0.5 to
        3.5 at the real-DB layer — verified after each commit."""
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

        # Three same-day observations — see
        # ``test_four_observations_reach_prior_weight_4_point_5``
        # for the rationale on same-day vs multi-day dates.
        for i in range(3):
            obs = _observation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=170.0 + i * 0.1,
                weight=1.0,
                measurement_date=date(2026, 6, 15),
            )
            await service.apply_observations(
                athlete_id=athlete.id,
                observations=[obs],
            )
            await db_session.commit()

            # After each call, the DB sees the accumulated weight.
            expected = 0.5 + (i + 1) * 1.0
            assert await _read_lt2_hr_prior_weight(
                db_session, athlete.id
            ) == pytest.approx(expected)
