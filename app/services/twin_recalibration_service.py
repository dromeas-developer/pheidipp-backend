"""Banister update + append-only TwinState."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import (
    DataTier,
    RecoveryModifierLevel,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.twin_state import TwinState
from app.repositories.athlete_fitness_repository import AthleteFitnessRepository
from app.repositories.athlete_physiology_repository import (
    AthletePhysiologyRepository,
)
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)
from app.repositories.system_event_repository import SystemEventRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.event_publisher import EventPublisher
from app.services.physiology_update_service import PhysiologyUpdateResult


POPULATION_TIME_CONSTANTS: Dict[str, int | str] = {
    "fitness_tau_days": 42,
    "fatigue_tau_days": 7,
    "source": "population_default",
}


@dataclass(frozen=True)
class BanisterUpdateResult:
    """Result of one Banister update step."""

    fitness: float
    fatigue: float
    form: float


@dataclass(frozen=True)
class RecalibrationResult:
    """Return value of TwinRecalibrationService.recalibrate."""

    twin_state: TwinState
    fitness: AthleteFitness
    updated_form: float


@dataclass(frozen=True)
class CalibrationRecalibrationResult:
    """Return value of TwinRecalibrationService.recalibrate_for_calibration."""

    twin_state: TwinState
    confidence_upgraded: bool


class TwinRecalibrationError(Exception):
    """Base class for twin-recalibration failures."""


class MissingTrainingGoalError(TwinRecalibrationError):
    """No active TrainingGoal for the athlete."""


class MissingAthleteFitnessError(TwinRecalibrationError):
    """No AthleteFitness row for the athlete."""


class TwinRecalibrationService:
    """Apply Banister update to AthleteFitness and append TwinState."""

    MODEL_VERSION = "v1-activity-sync"
    #: Model version for calibration-triggered TwinStates.
    MODEL_VERSION_CALIBRATION = "v2-threshold-detection"

    def __init__(
        self,
        session: AsyncSession,
        *,
        twin_states: TwinStateRepository | None = None,
        athlete_fitness: AthleteFitnessRepository | None = None,
        athlete_physiology: AthletePhysiologyRepository | None = None,
        training_goals: TrainingGoalRepository | None = None,
        events: EventPublisher | None = None,
    ) -> None:
        self.session = session
        self.twin_states = twin_states or TwinStateRepository(session)
        self.athlete_fitness = athlete_fitness or AthleteFitnessRepository(session)
        self.athlete_physiology = athlete_physiology or AthletePhysiologyRepository(
            session
        )
        self.training_goals = training_goals or TrainingGoalRepository(session)
        # ``EventPublisher`` is default-built from the session when
        # not injected (same pattern as ``ActivityIngestionService``
        # and ``PhysiologyUpdateService``); tests inject a fake to
        # assert event payloads without touching the
        # ``system_events`` / ``system_event_outbox`` tables.
        self.events = events or self._build_default_publisher(session)

    async def recalibrate(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        aerobic_load: Optional[float],
    ) -> RecalibrationResult:
        """Apply Banister update and append TwinState."""
        goal_row = await self.training_goals.get_active(athlete_id)
        if goal_row is None:
            raise MissingTrainingGoalError(
                f"no active training goal for athlete {athlete_id}"
            )

        fitness_row = await self.athlete_fitness.get_by_athlete_id(athlete_id)
        if fitness_row is None:
            raise MissingAthleteFitnessError(
                f"no athlete_fitness row for athlete {athlete_id}"
            )

        physiology_row = await self.athlete_physiology.get_by_athlete_id(
            athlete_id
        )

        updated = self.apply_banister_update(
            fitness_row=fitness_row,
            aerobic_load=aerobic_load or 0.0,
        )

        latest = await self.twin_states.get_latest(athlete_id)
        inline_snapshot = _build_inline_snapshot(
            updated=updated,
            physiology=physiology_row,
        )

        new_state = TwinState(
            athlete_id=athlete_id,
            training_goal_id=goal_row.id,
            activity_id=activity_id,
            data_tier=(
                DataTier(latest.data_tier)
                if latest is not None
                else DataTier.TIER_3
            ),
            confidence_level=(
                latest.confidence_level
                if latest is not None
                else TwinConfidenceLevel.LOW
            ),
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version=self.MODEL_VERSION,
            fitness=inline_snapshot["fitness"],
            fatigue=inline_snapshot["fatigue"],
            form=inline_snapshot["form"],
            lt1_pace_sec_per_km=(
                latest.lt1_pace_sec_per_km if latest is not None else None
            ),
            lt1_power_watts=(
                latest.lt1_power_watts if latest is not None else None
            ),
            lt1_hr_bpm=latest.lt1_hr_bpm if latest is not None else None,
            lt2_pace_sec_per_km=(
                latest.lt2_pace_sec_per_km if latest is not None else None
            ),
            lt2_power_watts=(
                latest.lt2_power_watts if latest is not None else None
            ),
            lt2_hr_bpm=latest.lt2_hr_bpm if latest is not None else None,
            cp_watts=latest.cp_watts if latest is not None else None,
            readiness_level=(
                latest.readiness_level
                if latest is not None
                else RecoveryModifierLevel.GREEN
            ),
            wellness_trend=latest.wellness_trend if latest is not None else None,
            metric_confidence=(
                latest.metric_confidence.copy()
                if latest is not None and latest.metric_confidence
                else {}
            ),
        )
        await self.twin_states.insert(new_state)

        return RecalibrationResult(
            twin_state=new_state,
            fitness=fitness_row,
            updated_form=updated.form,
        )

    async def insert_if_not_exists(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        trigger: TwinTrigger,
        new_state: TwinState,
    ) -> TwinState:
        """Append new_state unless a TwinState already covers the activity."""
        # Calibration supersedes everything — if a calibration record
        # already exists for this activity, skip the insert regardless
        # of the incoming trigger.
        existing_calibration = await self.twin_states.get_by_activity_and_trigger(
            activity_id=activity_id,
            trigger=TwinTrigger.CALIBRATION.value,
        )
        if existing_calibration is not None:
            return existing_calibration

        # No prior calibration — check for any existing TwinState for
        # this activity. If one exists and the incoming trigger is not
        # calibration, this is a duplicate non-calibration trigger and
        # must be skipped.
        existing = await self.twin_states.get_by_activity(activity_id)
        if existing is not None and trigger != TwinTrigger.CALIBRATION:
            return existing

        # Either no existing record, or the incoming trigger is
        # calibration (which supersedes a prior non-calibration record
        # — the prior record remains as history).
        return await self.twin_states.insert(new_state)

    async def recalibrate_for_calibration(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        physiology_result: PhysiologyUpdateResult,
    ) -> CalibrationRecalibrationResult:
        """Append a calibration-triggered ``TwinState`` and fire events.

        Distinct from :meth:`recalibrate` (which handles the
        ``activity_sync`` trigger with Banister-only updates).
        The calibration trigger carries the complete snapshot
        (thresholds + fitness) — the Banister update was already
        applied during ingestion by the ``activity_sync``
        recalibration, so this method only snapshots the current
        ``AthleteFitness`` values alongside the updated threshold
        values from ``AthletePhysiology``.

        Per-metric confidence monotonicity ratchet (ADR-011):
        for each metric key in ``metric_confidence``, the final
        stored value is
        ``max(previous_twin_state.metric_confidence[metric],
        computed_level)``. A metric that previously reached
        MEDIUM stays MEDIUM even if ``prior_weight`` has since
        decayed below 4.0. For metrics where the previous value
        is null (no power data before) and the computed value is
        non-null (power data now available), the computed value
        wins — null means "no data", not "low confidence".

        Event ordering within the ``threshold_detection``
        transaction (ADR-004):

        1. ``physiology_updated`` (from P2) — already written
           before this method is called.
        2. ``twin_recalibrated`` — fired here, after the
           TwinState insert.
        3. ``twin_confidence_upgraded`` — fired here, only when
           ``confidence_level`` increased relative to the
           previous TwinState.

        Both events are written to the transactional outbox in
        the same transaction as the TwinState insert. The
        external publisher reads them in insertion order after
        the producing transaction commits.

        Raises:
            MissingTrainingGoalError: no active ``TrainingGoal``.
            MissingAthleteFitnessError: no ``AthleteFitness`` row.
        """
        goal_row = await self.training_goals.get_active(athlete_id)
        if goal_row is None:
            raise MissingTrainingGoalError(
                f"no active training goal for athlete {athlete_id}"
            )

        fitness_row = await self.athlete_fitness.get_by_athlete_id(athlete_id)
        if fitness_row is None:
            raise MissingAthleteFitnessError(
                f"no athlete_fitness row for athlete {athlete_id}"
            )

        # Read the previous TwinState — the ratchet source for
        # both ``confidence_level`` and per-metric
        # ``metric_confidence``. ``None`` on the first snapshot.
        previous = await self.twin_states.get_latest(athlete_id)

        # -------------------------------------------------------------
        # 1. Derive confidence_level from the updated physiology.
        #    Global level = min(lt1.hr.prior_weight, lt2.hr.prior_weight)
        #    using the 4.0 / 8.0 thresholds. Monotonic ratchet:
        #    keep the higher of (previous, computed).
        # -------------------------------------------------------------
        computed_level = derive_confidence_level(
            physiology_result.physiology
        )
        old_level = (
            previous.confidence_level
            if previous is not None
            else TwinConfidenceLevel.LOW
        )
        confidence_level = max_confidence_level(old_level, computed_level)

        # -------------------------------------------------------------
        # 2. Per-metric monotonicity ratchet (ADR-011).
        #    For each metric key in the computed metric_confidence,
        #    the final stored value is
        #    max(previous_twin_state.metric_confidence[metric],
        #    computed_level). Null previous + non-null computed
        #    resolves to the computed value (null = "no data",
        #    not "low confidence").
        # -------------------------------------------------------------
        computed_metric_confidence = physiology_result.metric_confidence
        if previous is not None and previous.metric_confidence:
            metric_confidence = {
                metric: max_confidence_level_string(
                    previous.metric_confidence.get(metric),
                    computed_metric_confidence.get(metric),
                )
                for metric in computed_metric_confidence
            }
        else:
            metric_confidence = dict(computed_metric_confidence)

        # -------------------------------------------------------------
        # 3. Build the inline threshold snapshot from the updated
        #    ``AthletePhysiology``. Only the three documented
        #    threshold fields are populated at this phase
        #    (``lt1_hr_bpm``, ``lt2_hr_bpm``, ``cp_watts``); the
        #    remaining threshold fields fall back to the previous
        #    TwinState's values (or null on the first snapshot).
        # -------------------------------------------------------------
        physiology = physiology_result.physiology
        lt1_hr_bpm = extract_param_value(physiology.lt1, "hr")
        lt2_hr_bpm = extract_param_value(physiology.lt2, "hr")
        cp_watts = (
            float(physiology.cp["value"]) if physiology.cp else None
        )

        new_state = TwinState(
            athlete_id=athlete_id,
            training_goal_id=goal_row.id,
            activity_id=activity_id,
            data_tier=(
                DataTier(previous.data_tier)
                if previous is not None
                else DataTier.TIER_3
            ),
            confidence_level=confidence_level,
            trigger=TwinTrigger.CALIBRATION,
            model_version=self.MODEL_VERSION_CALIBRATION,
            fitness=float(fitness_row.aggregate.get("fitness", 0.0)),
            fatigue=float(fitness_row.aggregate.get("fatigue", 0.0)),
            form=float(fitness_row.aggregate.get("form", 0.0)),
            lt1_pace_sec_per_km=(
                previous.lt1_pace_sec_per_km if previous is not None else None
            ),
            lt1_power_watts=(
                previous.lt1_power_watts if previous is not None else None
            ),
            lt1_hr_bpm=lt1_hr_bpm,
            lt2_pace_sec_per_km=(
                previous.lt2_pace_sec_per_km if previous is not None else None
            ),
            lt2_power_watts=(
                previous.lt2_power_watts if previous is not None else None
            ),
            lt2_hr_bpm=lt2_hr_bpm,
            cp_watts=cp_watts,
            readiness_level=(
                previous.readiness_level
                if previous is not None
                else RecoveryModifierLevel.GREEN
            ),
            wellness_trend=(
                previous.wellness_trend if previous is not None else None
            ),
            metric_confidence=metric_confidence,
        )

        # -------------------------------------------------------------
        # 4. Append via the deduplication gate. Calibration
        #    supersedes a prior non-calibration record for the
        #    same activity; a prior calibration record is
        #    returned unchanged.
        # -------------------------------------------------------------
        inserted = await self.insert_if_not_exists(
            athlete_id=athlete_id,
            activity_id=activity_id,
            trigger=TwinTrigger.CALIBRATION,
            new_state=new_state,
        )

        # -------------------------------------------------------------
        # 5. Fire ``twin_recalibrated`` — every new calibration
        #    TwinState fires this event (no threshold gate, unlike
        #    ``physiology_updated`` which is gated by > 1 unit
        #    shift). The event is written to the transactional
        #    outbox in the same transaction as the TwinState
        #    insert.
        # -------------------------------------------------------------
        await self.events.publish(
            event_type="twin_recalibrated",
            athlete_id=athlete_id,
            payload={
                "athlete_id": str(athlete_id),
                "twin_state_id": str(inserted.id),
                "previous_twin_state_id": (
                    str(previous.id) if previous is not None else None
                ),
                "trigger": TwinTrigger.CALIBRATION.value,
                "confidence_level": inserted.confidence_level.value,
                "fitness_score": inserted.fitness,
                "fatigue_score": inserted.fatigue,
            },
        )

        # -------------------------------------------------------------
        # 6. Fire ``twin_confidence_upgraded`` only when the new
        #    TwinState's ``confidence_level`` is strictly higher
        #    than the previous TwinState's. Fires in addition to
        #    ``twin_recalibrated`` (not instead of). Same
        #    transaction; outbox insertion order is
        #    ``twin_recalibrated`` → ``twin_confidence_upgraded``.
        # -------------------------------------------------------------
        confidence_upgraded = confidence_rank(
            inserted.confidence_level
        ) > confidence_rank(old_level)
        if confidence_upgraded:
            await self.events.publish(
                event_type="twin_confidence_upgraded",
                athlete_id=athlete_id,
                payload={
                    "athlete_id": str(athlete_id),
                    "from_level": old_level.value,
                    "to_level": inserted.confidence_level.value,
                    "twin_state_id": str(inserted.id),
                },
            )

        return CalibrationRecalibrationResult(
            twin_state=inserted,
            confidence_upgraded=confidence_upgraded,
        )

    @staticmethod
    def _build_default_publisher(
        session: AsyncSession,
    ) -> EventPublisher:
        """Build the default EventPublisher for the session."""
        return EventPublisher(
            SystemEventRepository(session),
            SystemEventOutboxRepository(session),
        )

    @staticmethod
    def apply_banister_update(
        *,
        fitness_row: AthleteFitness,
        aerobic_load: float,
    ) -> BanisterUpdateResult:
        """Apply the Banister impulse-response update.

        Phase-1.6 only writes the aggregate block. The day-span
        parameter reflects primary-session spacing per the
        architecture note "Recovery windows are measured from
        primary session to primary session". At this phase the
        fitness / fatigue decay assumes ``days_since_last_update = 1``
        because the ingestion pipeline only fires once per
        activity; partial-day spacing is a Phase-2 refinement.
        """
        days_since_last_update = days_since(
            fitness_row.last_activity_id,
            reference=None,
        )
        constants = read_time_constants(fitness_row)
        # Decay since last update.
        fitness_decay = math.exp(
            -days_since_last_update / max(1, constants["fitness_tau_days"])
        )
        fatigue_decay = math.exp(
            -days_since_last_update / max(1, constants["fatigue_tau_days"])
        )

        # Aggregate fitness / fatigue are stored inside the JSONB
        # ``aggregate`` block per the architecture contract. Read the
        # current aggregate values, apply the update, write back.
        aggregate = dict(fitness_row.aggregate or {})
        current_fitness = float(aggregate.get("fitness", 0.0))
        current_fatigue = float(aggregate.get("fatigue", 0.0))

        new_fitness = current_fitness * fitness_decay + max(0.0, aerobic_load)
        new_fatigue = current_fatigue * fatigue_decay + max(0.0, aerobic_load)
        new_form = new_fitness - new_fatigue

        aggregate["fitness"] = new_fitness
        aggregate["fatigue"] = new_fatigue
        aggregate["form"] = new_form
        fitness_row.aggregate = aggregate

        return BanisterUpdateResult(
            fitness=new_fitness,
            fatigue=new_fatigue,
            form=new_form,
        )





def read_time_constants(fitness_row: AthleteFitness) -> Dict[str, Any]:
    """Extract the Banister time constants from ``fitness_row``.

    Falls back to the population defaults when the row has no
    inline ``time_constants`` JSONB. The ``source`` field defaults
    to ``"population_default"`` so the architecture's source-of-
    truth invariant (``ck_athlete_fitness_time_constants_source_valid``)
    remains satisfied.
    """
    if not fitness_row.time_constants:
        return dict(POPULATION_TIME_CONSTANTS)
    return {
        "fitness_tau_days": int(
            fitness_row.time_constants.get("fitness_tau_days", 42)
        ),
        "fatigue_tau_days": int(
            fitness_row.time_constants.get("fatigue_tau_days", 7)
        ),
        "source": str(
            fitness_row.time_constants.get("source", "population_default")
        ),
    }


def days_since(
    last_activity_id: Optional[uuid.UUID],
    *,
    reference: Optional[datetime],
) -> int:
    """Return the days-since-last-update for the Banister update.

    Phase-1.6 simplification: returns ``1`` because the ingestion
    pipeline fires once per activity; ``reference`` and
    ``last_activity_id`` are accepted so the Phase-2 refinement
    can compute partial-day spacing without changing the caller
    signature.
    """
    return 1


def _build_inline_snapshot(
    *,
    updated: BanisterUpdateResult,
    physiology: Optional[AthletePhysiology],
) -> Dict[str, float]:
    """Build the inline fitness / fatigue / form triple for ``TwinState``.

    Phase-1.6 only writes the aggregate scores; threshold values
    remain the latest snapshot's values (unchanged at this phase).
    """
    return {
        "fitness": updated.fitness,
        "fatigue": updated.fatigue,
        "form": updated.form,
    }


# ---------------------------------------------------------------------------
# Calibration-trigger helpers — confidence derivation, ratchet, and
# threshold extraction. Module-level so unit tests can exercise them
# directly without a session.
# ---------------------------------------------------------------------------

#: Numeric ordering of the :class:`TwinConfidenceLevel` enum, used
#: to detect monotonic upward transitions between old and new
#: confidence levels. Index ``0`` is the lowest tier. Mirrors the
#: ordering in :mod:`app.services.physiology_update_service` so the
#: ratchet semantics are consistent across the two services.
_CONFIDENCE_LEVEL_ORDER: Dict[str, int] = {
    TwinConfidenceLevel.LOW.value: 0,
    TwinConfidenceLevel.MEDIUM.value: 1,
    TwinConfidenceLevel.HIGH.value: 2,
}


def confidence_rank(level: TwinConfidenceLevel) -> int:
    """Return the numeric rank of ``level`` for monotonic comparisons.

    Returns ``0`` for unknown levels so a malformed enum value
    never causes the ratchet to silently downgrade.
    """
    return _CONFIDENCE_LEVEL_ORDER.get(level.value, 0)


def max_confidence_level(
    a: TwinConfidenceLevel,
    b: TwinConfidenceLevel,
) -> TwinConfidenceLevel:
    """Return the higher of two :class:`TwinConfidenceLevel` values.

    Used by the global ``confidence_level`` ratchet — the stored
    level never decreases, even when ``prior_weight`` decays
    below a threshold.
    """
    return a if confidence_rank(a) >= confidence_rank(b) else b


def max_confidence_level_string(
    previous: Optional[str],
    computed: Optional[str],
) -> Optional[str]:
    """Return the higher of two confidence-level strings.

    Used by the per-metric ``metric_confidence`` ratchet
    (ADR-011). A ``None`` previous value (no data before) is
    treated as "no data", not "low confidence" — the computed
    value wins in that case. A ``None`` computed value (no data
    now) is treated as "no data" — the previous value is kept
    if it was non-null, otherwise ``None`` is returned.
    """
    if previous is None:
        return computed
    if computed is None:
        return previous
    prev_rank = _CONFIDENCE_LEVEL_ORDER.get(previous, 0)
    comp_rank = _CONFIDENCE_LEVEL_ORDER.get(computed, 0)
    return previous if prev_rank >= comp_rank else computed


def derive_confidence_level(
    physiology: AthletePhysiology,
) -> TwinConfidenceLevel:
    """Derive the global ``confidence_level`` from ``physiology``.

    Per the architecture's confidence model, the global level is
    ``min(lt1.hr.prior_weight, lt2.hr.prior_weight)`` mapped
    through the 4.0 / 8.0 thresholds. A ``None`` prior weight
    (no HR data yet) resolves to ``LOW`` — the same default
    used by :func:`physiology_update_service._confidence_level`.
    """
    lt1 = physiology.lt1 or {}
    lt2 = physiology.lt2 or {}
    lt1_hr_weight = state_prior_weight(lt1.get("hr") if lt1 else None)
    lt2_hr_weight = state_prior_weight(lt2.get("hr") if lt2 else None)
    min_weight = min_prior_weight(lt1_hr_weight, lt2_hr_weight)
    return prior_weight_to_level(min_weight)


def state_prior_weight(state: Optional[Dict[str, Any]]) -> Optional[float]:
    """Return the ``prior_weight`` of a ``PhysiologyParameterState``.

    Handles ``None`` state and dicts missing the key defensively
    — the function returns ``None`` so the caller can map it to
    the LOW confidence level without raising.
    """
    if state is None:
        return None
    weight = state.get("prior_weight")
    return float(weight) if weight is not None else None


def min_prior_weight(
    a: Optional[float],
    b: Optional[float],
) -> Optional[float]:
    """Return the smaller of two prior weights, treating ``None`` as 0.

    The global ``confidence_level`` is the minimum across the
    HR parameters — the weakest link drives the global level.
    A ``None`` weight (no data yet) is treated as zero so the
    minimum is correctly ``LOW`` until both HR parameters have
    observations.
    """
    a_val = a if a is not None else 0.0
    b_val = b if b is not None else 0.0
    return min(a_val, b_val)


def prior_weight_to_level(prior_weight: Optional[float]) -> TwinConfidenceLevel:
    """Map a ``prior_weight`` to a :class:`TwinConfidenceLevel`.

    Thresholds are 4.0 (LOW→MEDIUM) and 8.0 (MEDIUM→HIGH) per
    ``docs/architecture/00-foundations/confidence-model.md`` —
    the 15.0/40.0 example in the TwinState spec is a stale
    placeholder per the implementation plan's clarification.

    A ``None`` ``prior_weight`` is treated as zero (no evidence
    yet) and resolves to ``LOW``.
    """
    if prior_weight is None:
        return TwinConfidenceLevel.LOW
    if prior_weight >= 8.0:
        return TwinConfidenceLevel.HIGH
    if prior_weight >= 4.0:
        return TwinConfidenceLevel.MEDIUM
    return TwinConfidenceLevel.LOW


def extract_param_value(
    container: Optional[dict[str, Any]],
    sub_key: str,
) -> Optional[float]:
    """Return the ``value`` field of a ``PhysiologyParameterState`` sub-state.

    Returns ``None`` when the outer container is null, the
    sub-state is null, or the sub-state is missing the ``value``
    key. Used to populate the inline threshold snapshot on the
    calibration TwinState (``lt1_hr_bpm``, ``lt2_hr_bpm``).
    """
    if not container:
        return None
    sub_state = container.get(sub_key)
    if not isinstance(sub_state, dict):
        return None
    ss: dict[str, Any] = cast(dict[str, Any], sub_state)
    value = ss.get("value")
    return float(value) if value is not None else None