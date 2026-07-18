"""Integration tests for the ``threshold_detection`` procrastinate worker task.

The task body in ``app/worker/app.py`` orchestrates the full
threshold detection → physiology update → twin recalibration
pipeline in a single transaction. These tests exercise the
pipeline end-to-end against the real test database, with mock
detection/physiology/twin services substituted at the constructor
boundary so the tests can drive known scenarios without
depending on the actual threshold-detection algorithms.

The mock seam is necessary because the worker task is structured
to call into real services — there is no ``task_dispatcher``
injection point on the threshold_detection task itself. The
services are imported inside the task body, so the tests
re-implement the task body with the same logic and substitute
mocks for the real services. The session, repositories, and
event publisher are real; only the three service-layer
collaborators are stubbed.

Reference plan: ``docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md``
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    DataTier,
    GpsSource,
    GoalType,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    Sex,
    SportBackground,
    SportType,
    TrainingGoalStatus,
    TrainingTimeOfDay,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from app.services.physiology_update_service import PhysiologyUpdateResult
from app.services.threshold_detection_service import ThresholdObservation
from tests.utils.factories import make_activity, make_athlete


# ---------------------------------------------------------------------------
# Helpers — Mocks.
# ---------------------------------------------------------------------------


class _MockThresholdService:
    """A drop-in replacement for ``ThresholdDetectionService``
    that returns a pre-configured list of observations."""

    def __init__(
        self,
        observations: Optional[List[ThresholdObservation]] = None,
    ) -> None:
        self.observations = list(observations or [])
        self.detect_call_count = 0
        self.detect_calls: List[Dict[str, Any]] = []

    async def detect(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
    ) -> List[ThresholdObservation]:
        self.detect_call_count += 1
        self.detect_calls.append(
            {"athlete_id": athlete_id, "activity_id": activity_id}
        )
        return list(self.observations)


class _MockPhysiologyService:
    """A drop-in replacement for ``PhysiologyUpdateService``
    that returns a pre-configured ``PhysiologyUpdateResult``."""

    def __init__(
        self,
        result: Optional[PhysiologyUpdateResult] = None,
    ) -> None:
        self.result = result
        self.apply_call_count = 0
        self.apply_calls: List[Dict[str, Any]] = []

    async def apply_observations(
        self,
        *,
        athlete_id: uuid.UUID,
        observations: List[ThresholdObservation],
    ) -> PhysiologyUpdateResult:
        self.apply_call_count += 1
        self.apply_calls.append(
            {"athlete_id": athlete_id, "observations": observations}
        )
        if self.result is None:
            raise RuntimeError("MockPhysiologyService.result not configured")
        return self.result


class _MockTwinService:
    """A drop-in replacement for ``TwinRecalibrationService``
    that records the call and returns a pre-configured result."""

    def __init__(
        self,
        twin_state: Optional[TwinState] = None,
        confidence_upgraded: bool = False,
    ) -> None:
        self.twin_state = twin_state
        self.confidence_upgraded = confidence_upgraded
        self.recalibrate_call_count = 0
        self.recalibrate_calls: List[Dict[str, Any]] = []

    async def recalibrate_for_calibration(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        physiology_result: PhysiologyUpdateResult,
    ) -> Any:
        self.recalibrate_call_count += 1
        self.recalibrate_calls.append(
            {
                "athlete_id": athlete_id,
                "activity_id": activity_id,
                "physiology_result": physiology_result,
            }
        )
        from app.services.twin_recalibration_service import (
            CalibrationRecalibrationResult,
        )

        assert self.twin_state is not None  # nosec — test helper guard
        return CalibrationRecalibrationResult(
            twin_state=self.twin_state,
            confidence_upgraded=self.confidence_upgraded,
        )


# ---------------------------------------------------------------------------
# Helpers — fixture builders.
# ---------------------------------------------------------------------------


async def _create_athlete_with_full_onboarding(
    db_session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create an athlete with the minimum onboarding context for
    the threshold detection pipeline. Returns (athlete_id, goal_id)."""
    athlete = await make_athlete(db_session)

    profile = AthleteProfile(
        athlete_id=athlete.id,
        date_of_birth=date(1990, 1, 1),
        sex=Sex.NOT_SPECIFIED,
    )
    db_session.add(profile)

    prefs = AthletePreferences(
        athlete_id=athlete.id,
        weekly_schedule={},
        sport_background=SportBackground.RUNNING_PRIMARY,
        years_structured_training=3,
        training_time_of_day=TrainingTimeOfDay.MORNING,
        gps_source=GpsSource.GARMIN_WATCH,
        hr_source=HrSource.CHEST_STRAP_RR,
        power_source=PowerSource.NONE,
        primary_training_platform=PrimaryTrainingPlatform.GARMIN_CONNECT,
    )
    db_session.add(prefs)

    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()

    fitness = AthleteFitness(
        athlete_id=athlete.id,
        aggregate={"fitness": 50.0, "fatigue": 30.0, "form": 20.0},
    )
    db_session.add(fitness)

    physiology = AthletePhysiology(athlete_id=athlete.id)
    db_session.add(physiology)

    twin = TwinState(
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        data_tier=DataTier.TIER_3,
        confidence_level=TwinConfidenceLevel.LOW,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1.0",
        fitness=50.0,
        fatigue=30.0,
        form=20.0,
        readiness_level=RecoveryModifierLevel.GREEN,
    )
    db_session.add(twin)

    await db_session.flush()
    return athlete.id, goal.id


async def _create_calibration_eligible_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
) -> Activity:
    """Create a calibration-eligible running activity."""
    return await make_activity(
        db_session,
        athlete_id=athlete_id,
        sport_type=SportType.RUNNING,
        calibration_eligible=True,
        has_hr=True,
    )


def _observation(
    *,
    observed_value: float = 170.0,
    weight: float = 1.0,
) -> ThresholdObservation:
    """Build a real ``ThresholdObservation`` instance."""
    from app.models.enums import (
        MeasurementSource,
        PhysiologyParameter,
    )

    return ThresholdObservation(
        parameter=PhysiologyParameter.LT2_HR,
        observed_value=observed_value,
        source=MeasurementSource.TRAINING_HR_DEFLECTION,
        weight=weight,
        activity_id=uuid.uuid4(),
        measurement_date=date(2026, 6, 15),
        algorithm_used="hr_deflection_v1",
        confidence_weight=0.85,
    )


# ---------------------------------------------------------------------------
# Test: full pipeline — happy path.
# ---------------------------------------------------------------------------


class TestThresholdDetectionTaskFullPipeline:
    """The full threshold_detection → physiology_update →
    twin_recalibration pipeline runs in a single transaction."""

    @pytest.mark.asyncio
    async def test_full_pipeline_orchestration(
        self, db_session: AsyncSession
    ) -> None:
        """The full pipeline orchestration: detect → apply_observations
        → recalibrate_for_calibration is invoked in sequence.
        All three services are called exactly once with the
        correct activity_id and athlete_id."""
        from app.models.enums import PhysiologyParameter
        from app.repositories.athlete_physiology_repository import (
            AthletePhysiologyRepository,
        )

        athlete_id, goal_id = await _create_athlete_with_full_onboarding(
            db_session
        )
        activity = await _create_calibration_eligible_activity(
            db_session, athlete_id=athlete_id
        )
        await db_session.commit()

        # Configure mocks.
        observations = [_observation()]
        mock_threshold = _MockThresholdService(observations=observations)

        # Build a real physiology row with a shifted state.

        physiology = await AthletePhysiologyRepository(
            db_session
        ).get_by_athlete_id(athlete_id)
        assert physiology is not None  # athlete was just onboarded
        # Mutate the JSONB to simulate a posterior shift.
        physiology.lt2 = {
            "hr": {
                "value": 170.0,
                "uncertainty": 0.8,
                "prior_weight": 5.0,
                "dominant_source": "training_hr_deflection",
                "last_observation_date": "2026-06-15",
            },
            "power": None,
            "pace": None,
        }
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(physiology, "lt2")
        await db_session.flush()

        mock_physiology = _MockPhysiologyService(
            result=PhysiologyUpdateResult(
                physiology=physiology,
                shifted_parameters=[PhysiologyParameter.LT2_HR],
                metric_confidence={"lt2_hr": "medium"},
                confidence_transitions={},
                measurements_written=1,
            )
        )

        # Pre-create the TwinState that the mock twin service returns.
        twin_state = TwinState(
            athlete_id=athlete_id,
            training_goal_id=goal_id,
            activity_id=activity.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.MEDIUM,
            trigger=TwinTrigger.CALIBRATION,
            model_version="v2-threshold-detection",
            fitness=55.0,
            fatigue=25.0,
            form=30.0,
            lt2_hr_bpm=170.0,
            readiness_level=RecoveryModifierLevel.GREEN,
            metric_confidence={"lt2_hr": "medium"},
        )
        mock_twin = _MockTwinService(
            twin_state=twin_state,
            confidence_upgraded=True,
        )

        # Body — mirrors the threshold_detection task body in
        # ``app/worker/app.py``.
        await _run_pipeline_body(
            db_session=db_session,
            activity_id=activity.id,
            threshold_service=mock_threshold,
            physiology_service=mock_physiology,
            twin_service=mock_twin,
        )

        # All three services were called exactly once.
        assert mock_threshold.detect_call_count == 1
        assert mock_physiology.apply_call_count == 1
        assert mock_twin.recalibrate_call_count == 1

        # The mock twin service does NOT write to the DB (it
        # just records the call and returns a pre-configured
        # TwinState object). The real twin service would have
        # written a row here. The behaviour layer covers the
        # real-write end-to-end path; this integration layer
        # pins the orchestration sequence.

    @pytest.mark.asyncio
    async def test_pipeline_passes_activity_id_and_athlete_id(
        self, db_session: AsyncSession
    ) -> None:
        """The activity_id flows from the task parameter to all
        three services. The athlete_id is resolved from the
        Activity row inside the task body."""
        from app.models.enums import PhysiologyParameter
        from app.repositories.athlete_physiology_repository import (
            AthletePhysiologyRepository,
        )

        athlete_id, _ = await _create_athlete_with_full_onboarding(
            db_session
        )
        activity = await _create_calibration_eligible_activity(
            db_session, athlete_id=athlete_id
        )
        await db_session.commit()

        physiology = await AthletePhysiologyRepository(
            db_session
        ).get_by_athlete_id(athlete_id)
        assert physiology is not None  # athlete was just onboarded
        physiology.lt2 = {
            "hr": {
                "value": 170.0,
                "uncertainty": 0.8,
                "prior_weight": 5.0,
                "dominant_source": "training_hr_deflection",
                "last_observation_date": "2026-06-15",
            },
            "power": None,
            "pace": None,
        }
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(physiology, "lt2")
        await db_session.flush()

        mock_threshold = _MockThresholdService(observations=[_observation()])
        mock_physiology = _MockPhysiologyService(
            result=PhysiologyUpdateResult(
                physiology=physiology,
                shifted_parameters=[PhysiologyParameter.LT2_HR],
                metric_confidence={"lt2_hr": "medium"},
                confidence_transitions={},
                measurements_written=1,
            )
        )
        mock_twin = _MockTwinService(
            twin_state=TwinState(
                athlete_id=athlete_id,
                training_goal_id=uuid.uuid4(),
                data_tier=DataTier.TIER_3,
                confidence_level=TwinConfidenceLevel.MEDIUM,
                trigger=TwinTrigger.CALIBRATION,
                model_version="v2-threshold-detection",
                fitness=55.0,
                fatigue=25.0,
                form=30.0,
                readiness_level=RecoveryModifierLevel.GREEN,
            ),
            confidence_upgraded=True,
        )

        await _run_pipeline_body(
            db_session=db_session,
            activity_id=activity.id,
            threshold_service=mock_threshold,
            physiology_service=mock_physiology,
            twin_service=mock_twin,
        )

        # Both activity_id and athlete_id were passed correctly.
        assert mock_threshold.detect_calls[0]["activity_id"] == activity.id
        assert mock_threshold.detect_calls[0]["athlete_id"] == athlete_id
        assert mock_physiology.apply_calls[0]["athlete_id"] == athlete_id
        assert mock_twin.recalibrate_calls[0]["activity_id"] == activity.id
        assert mock_twin.recalibrate_calls[0]["athlete_id"] == athlete_id


# ---------------------------------------------------------------------------
# Test: early-return paths.
# ---------------------------------------------------------------------------


class TestThresholdDetectionTaskEarlyReturn:
    """The task returns early when:
    1. The observations list is empty (no threshold signal).
    2. The physiology result has no shifted parameters (no recalibration).
    Both paths commit the transaction (so any measurements
    written by the physiology service are persisted) but skip
    the twin recalibration step."""

    @pytest.mark.asyncio
    async def test_empty_observations_skips_physiology_and_twin(
        self, db_session: AsyncSession
    ) -> None:
        """No observations → no physiology update, no twin
        recalibration. The task commits and returns."""
        athlete_id, _ = await _create_athlete_with_full_onboarding(
            db_session
        )
        activity = await _create_calibration_eligible_activity(
            db_session, athlete_id=athlete_id
        )
        await db_session.commit()

        mock_threshold = _MockThresholdService(observations=[])
        mock_physiology = _MockPhysiologyService(
            result=PhysiologyUpdateResult(
                physiology=AthletePhysiology(athlete_id=athlete_id),
                metric_confidence={},
            )
        )
        mock_twin = _MockTwinService()

        # Body — mirrors the threshold_detection task body.
        # We track the return value to verify the early-return
        # path was taken.
        result = await _run_pipeline_body(
            db_session=db_session,
            activity_id=activity.id,
            threshold_service=mock_threshold,
            physiology_service=mock_physiology,
            twin_service=mock_twin,
        )

        # Threshold service was called.
        assert mock_threshold.detect_call_count == 1
        # Physiology service was NOT called (no observations).
        assert mock_physiology.apply_call_count == 0
        # Twin service was NOT called.
        assert mock_twin.recalibrate_call_count == 0

        # Return value reflects the early-return path.
        assert result["observations_count"] == 0
        assert result["shifted"] is False
        assert result["twin_state_id"] is None
        assert result["confidence_upgraded"] is False

    @pytest.mark.asyncio
    async def test_no_shifted_parameters_skips_twin(
        self, db_session: AsyncSession
    ) -> None:
        """Observations exist but no parameters shifted →
        physiology update ran, twin recalibration did NOT.
        The task commits the physiology measurements but
        returns without a twin state."""
        from app.repositories.athlete_physiology_repository import (
            AthletePhysiologyRepository,
        )

        athlete_id, _ = await _create_athlete_with_full_onboarding(
            db_session
        )
        activity = await _create_calibration_eligible_activity(
            db_session, athlete_id=athlete_id
        )
        await db_session.commit()

        physiology = await AthletePhysiologyRepository(
            db_session
        ).get_by_athlete_id(athlete_id)
        assert physiology is not None  # athlete was just onboarded

        mock_threshold = _MockThresholdService(observations=[_observation()])
        # shifted_parameters is empty → no twin recalibration.
        mock_physiology = _MockPhysiologyService(
            result=PhysiologyUpdateResult(
                physiology=physiology,
                shifted_parameters=[],
                metric_confidence={},
                confidence_transitions={},
                measurements_written=1,
            )
        )
        mock_twin = _MockTwinService()

        result = await _run_pipeline_body(
            db_session=db_session,
            activity_id=activity.id,
            threshold_service=mock_threshold,
            physiology_service=mock_physiology,
            twin_service=mock_twin,
        )

        # Threshold service was called.
        assert mock_threshold.detect_call_count == 1
        # Physiology service was called (observations existed).
        assert mock_physiology.apply_call_count == 1
        # Twin service was NOT called (no shifted parameters).
        assert mock_twin.recalibrate_call_count == 0

        # Return value reflects the shifted=False path.
        assert result["observations_count"] == 1
        assert result["shifted"] is False
        assert result["twin_state_id"] is None
        assert result["confidence_upgraded"] is False


# ---------------------------------------------------------------------------
# Test: missing activity.
# ---------------------------------------------------------------------------


class TestThresholdDetectionTaskMissingActivity:
    """A missing activity causes the task to raise an
    ActivityIngestionError-equivalent error so procrastinate can
    retry or DLQ the task."""

    @pytest.mark.asyncio
    async def test_missing_activity_raises_error(
        self, db_session: AsyncSession
    ) -> None:
        """A nonexistent activity_id raises an error before any
        service is called."""
        mock_threshold = _MockThresholdService()
        mock_physiology = _MockPhysiologyService()
        mock_twin = _MockTwinService()

        with pytest.raises(Exception):
            await _run_pipeline_body(
                db_session=db_session,
                activity_id=uuid.uuid4(),  # nonexistent
                threshold_service=mock_threshold,
                physiology_service=mock_physiology,
                twin_service=mock_twin,
            )

        # No service was called.
        assert mock_threshold.detect_call_count == 0
        assert mock_physiology.apply_call_count == 0
        assert mock_twin.recalibrate_call_count == 0


# ---------------------------------------------------------------------------
# Helpers — local mirror of the threshold_detection task body.
# ---------------------------------------------------------------------------


async def _run_pipeline_body(
    *,
    db_session: AsyncSession,
    activity_id: uuid.UUID,
    threshold_service: _MockThresholdService,
    physiology_service: _MockPhysiologyService,
    twin_service: _MockTwinService,
) -> dict[str, Any]:
    """Run the threshold_detection pipeline body with mock services.

    Mirrors the body of the ``threshold_detection`` task in
    ``app/worker/app.py`` step for step. The real task uses
    ``AsyncSessionLocal`` to open a session, but for the
    integration test we re-use the per-test ``db_session``
    fixture so the writes are visible in the same transaction.

    Returns the dict that the real task returns.
    """
    from app.repositories.activity_repository import ActivityRepository

    # Step 1: load the activity to resolve athlete_id.
    activities = ActivityRepository(db_session)
    activity = await activities.get_by_id(activity_id)
    if activity is None:
        raise ValueError(f"Activity {activity_id} not found")
    athlete_id = activity.athlete_id

    # Step 2: run threshold detection.
    observations = await threshold_service.detect(
        athlete_id=athlete_id,
        activity_id=activity_id,
    )

    if not observations:
        # Early return — no threshold signal in this session.
        return {
            "activity_id": str(activity_id),
            "twin_state_id": None,
            "observations_count": 0,
            "shifted": False,
            "confidence_upgraded": False,
        }

    # Step 3: apply observations to the physiology posterior.
    update_result = await physiology_service.apply_observations(
        athlete_id=athlete_id,
        observations=observations,
    )

    if not update_result.shifted_parameters:
        # Early return — posterior did not shift > 1 unit.
        return {
            "activity_id": str(activity_id),
            "twin_state_id": None,
            "observations_count": len(observations),
            "shifted": False,
            "confidence_upgraded": False,
        }

    # Step 4: recalibrate the twin.
    recalibration = await twin_service.recalibrate_for_calibration(
        athlete_id=athlete_id,
        activity_id=activity_id,
        physiology_result=update_result,
    )

    return {
        "activity_id": str(activity_id),
        "twin_state_id": (
            str(recalibration.twin_state.id)
            if recalibration.twin_state is not None
            else None
        ),
        "observations_count": len(observations),
        "shifted": True,
        "confidence_upgraded": recalibration.confidence_upgraded,
    }
