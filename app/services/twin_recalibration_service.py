"""TwinRecalibrationService — Banister update + append-only TwinState.

Implements the Phase-1.6 contract from
``docs/architecture/02-computations/banister-update.md` and the
``TwinState`` append-only invariant from
``docs/architecture/01-entities/twin-state.md`.

Atomicity guarantees:

* The service runs every write through the per-entity repositories
  on a single shared ``AsyncSession`` and never commits; the caller
  (``ActivityIngestionService``) owns the commit boundary. Raising
  any exception rolls back the session automatically — partial
  state is never visible to other readers.

* ``TwinState`` is append-only: ``TwinStateRepository`` exposes no
  ``update()`` / ``delete()`` methods. The recalibration service
  inserts a fresh ``TwinState`` row with ``trigger = activity_sync``
  every time. Existing snapshots stay immutable for audit.

* ``AthleteFitness`` is mutable — the Banister update writes
  fitness / fatigue / form in place. The ``form = fitness - fatigue``
  invariant is enforced at the DB layer by ``CheckConstraint``
  (``ck_athlete_fitness_*_form_invariant``) — every dimensional
  block plus the aggregate block has its own constraint.

Phase-1.6 simplification:

* Only the aggregate ``DimensionalScores`` block is populated by
  this service. The per-dimension blocks (``aerobic``, ``neuromuscular``,
  ``structural``) stay ``null`` until Phase 2b wires up
  per-dimension Banister updates with their own load scores.
* Threshold / physiology updates are NOT recomputed at this phase
  (``calibration_eligible = false`` everywhere per the
  Phase-1.6 invariants). ``ThresholdDetectionService` lands in
  Phase 2.
* Calibration eligibility is therefore irrelevant for the
  recalibration path in this phase — but the service still produces
  a new ``TwinState`` so the home view can reflect updated
  fitness / fatigue from the heuristic load.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

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
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.twin_state_repository import TwinStateRepository


# ---------------------------------------------------------------------------
# Population defaults — Banister time constants.
# Source: ``docs/architecture/02-computations/banister-update.md``.
# ---------------------------------------------------------------------------

POPULATION_TIME_CONSTANTS: Dict[str, int | str] = {
    "fitness_tau_days": 42,
    "fatigue_tau_days": 7,
    "source": "population_default",
}


# ---------------------------------------------------------------------------
# Output dataclasses.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BanisterUpdateResult:
    """Result of one Banister update step.

    Carries the new fitness / fatigue / form so callers can serialise
    them into the new ``TwinState`` inline snapshot.
    """

    fitness: float
    fatigue: float
    form: float


@dataclass(frozen=True)
class RecalibrationResult:
    """Return value of :meth:`TwinRecalibrationService.recalibrate`.

    Carries the freshly created ``TwinState`` so the caller can
    pass it to the post-workout agent (the ``CoachingMessage``
    FKs back to the ``TwinState`` at generation time).
    """

    twin_state: TwinState
    fitness: AthleteFitness
    updated_form: float


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class TwinRecalibrationError(Exception):
    """Base class for twin-recalibration failures."""


class MissingTrainingGoalError(TwinRecalibrationError):
    """The athlete has no active ``TrainingGoal`` — twin state cannot
    be appended because the FK is non-null."""


class MissingAthleteFitnessError(TwinRecalibrationError):
    """The athlete has no ``AthleteFitness`` row — Banister update
    has no anchor. The onboarding bootstrap always creates one;
    this is a data-integrity failure rather than a user error.
    """


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------


class TwinRecalibrationService:
    """Apply a Banister update to ``AthleteFitness`` and append a
    new ``TwinState`` snapshot.

    The service is constructed with the per-request
    ``AsyncSession`` so all writes participate in the caller's
    transaction. The session is NOT committed here — the
    ingestion pipeline owns the commit boundary.
    """

    MODEL_VERSION = "v1-activity-sync"

    def __init__(
        self,
        session: AsyncSession,
        *,
        twin_states: TwinStateRepository | None = None,
        athlete_fitness: AthleteFitnessRepository | None = None,
        athlete_physiology: AthletePhysiologyRepository | None = None,
        training_goals: TrainingGoalRepository | None = None,
    ) -> None:
        self.session = session
        self.twin_states = twin_states or TwinStateRepository(session)
        self.athlete_fitness = athlete_fitness or AthleteFitnessRepository(session)
        self.athlete_physiology = athlete_physiology or AthletePhysiologyRepository(
            session
        )
        self.training_goals = training_goals or TrainingGoalRepository(session)

    async def recalibrate(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        aerobic_load: Optional[float],
    ) -> RecalibrationResult:
        """Apply the Banister update and append a ``TwinState``.

        Parameters
        ----------
        athlete_id:
            Path athlete.
        activity_id:
            ``Activity.id`` driving the recalibration. The new
            ``TwinState`` records this on its ``activity_id`` FK so
            the partial unique index
            ``uq_twin_states_athlete_activity`` enforces one
            snapshot per activity.
        aerobic_load:
            ``Activity.aerobic_load`` value. ``None`` is treated as
            zero load — the Banister update still runs (decay-only)
            so the snapshot timestamp stays accurate.

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

        physiology_row = await self.athlete_physiology.get_by_athlete_id(
            athlete_id
        )

        # -------------------------------------------------------------
        # 1. Banister update — applied in place to AthleteFitness.
        # -------------------------------------------------------------
        updated = self._apply_banister_update(
            fitness_row=fitness_row,
            aerobic_load=aerobic_load or 0.0,
        )

        # -------------------------------------------------------------
        # 2. Append a new TwinState with the inline snapshot.
        # -------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Pure compute — exposed as a static method for unit-test access.
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_banister_update(
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
        days_since_last_update = _days_since(
            fitness_row.last_activity_id,
            reference=None,
        )
        constants = _read_time_constants(fitness_row)
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


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _read_time_constants(fitness_row: AthleteFitness) -> Dict[str, Any]:
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


def _days_since(
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