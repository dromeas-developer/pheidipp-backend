"""Bayesian update of AthletePhysiology posterior state."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import MeasurementSource, PhysiologyParameter, TwinConfidenceLevel
from app.models.physiology_measurement import PhysiologyMeasurement
from app.repositories.athlete_physiology_repository import (
    UNSET_SENTINEL,
    AthletePhysiologyRepository,
)
from app.repositories.physiology_measurement_repository import (
    PhysiologyMeasurementRepository,
)
from app.services.event_publisher import EventPublisher
from app.services.threshold_detection_service import ThresholdObservation


# ---------------------------------------------------------------------------
# Pure compute constants — copied verbatim from
# ``docs/architecture/02-computations/physiology-update.md``.
# ---------------------------------------------------------------------------

#: Number of days over which an observation's prior weight decays
#: to ``1/e`` (~37%). The 42-day constant is aligned with the
#: aerobic-fitness time constant in the Banister model.
DECAY_TIME_CONSTANT_DAYS: float = 42.0

#: Posterior-uncertainty floor. Even with massive evidence, the
#: parameter uncertainty never drops below this value — it
#: represents irreducible measurement noise.
UNCERTAINTY_FLOOR: float = 0.5

#: Default uncertainty applied when bootstrapping a parameter state
#: from scratch (e.g. the first ``training_power_hr_ratio`` CP
#: observation against a previously-null ``physiology.cp``).
INITIAL_UNCERTAINTY: float = 1.0


# ---------------------------------------------------------------------------
# Pure compute — the Bayesian update formula.
# ---------------------------------------------------------------------------


def bayesian_update(
    current: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Apply the Bayesian update formula to one parameter state.

    Implements the formula in
    ``docs/architecture/02-computations/physiology-update.md``.

    Both ``current`` and ``observation`` are mapping-shaped. The
    shapes match the JSONB layout used throughout the
    ``AthletePhysiology`` columns:

    * ``current`` — a ``PhysiologyParameterState`` dict with keys
      ``value``, ``uncertainty``, ``prior_weight``,
      ``dominant_source``, ``last_observation_date``. The
      ``last_observation_date`` value is an ISO-8601 string (the
      shape written by :func:`OnboardingService._bootstrap_signal`
      and stored verbatim on subsequent updates).
    * ``observation`` — a single observation with keys ``value``,
      ``weight`` (source-specific), ``date`` (``datetime.date``
      instance — the schema column ``measurement_date`` is
      ``Date``, not ``DateTime``), and ``source`` (a
      ``MeasurementSource`` enum member or its ``.value`` string).

    The function is pure — no I/O, no side effects, no mutation
    of either input. The returned dict is a brand-new
    ``PhysiologyParameterState`` shape ready to be written back to
    the JSONB column by the calling service.

    Computation steps (per the architecture):

    1. ``days_since_last = days_between(current.last_observation_date,
       observation.date)`` — calendar-day delta.
    2. ``decay_factor = exp(-days_since_last / 42)`` — prior
       decays to ``1/e`` over 42 days.
    3. ``decayed_weight = current.prior_weight * decay_factor``.
    4. ``new_total_weight = decayed_weight + observation.weight``.
    5. ``posterior_mean = (current.value * decayed_weight +
       observation.value * observation.weight) / new_total_weight``.
    6. ``posterior_uncertainty = max(current.uncertainty *
       sqrt(decayed_weight / new_total_weight), 0.5)`` — floor at
       0.5 captures irreducible measurement noise.
    7. ``dominant_source = observation.source if
       observation.weight > decayed_weight else
       current.dominant_source`` — high-weight observations
       override the prior's dominant source.
    8. ``last_observation_date = observation.date`` — stored as
       ISO-8601 string to match the bootstrap shape.
    """
    current_date = parse_iso_date(current["last_observation_date"])
    observation_date = coerce_observation_date(observation["date"])
    days_since_last = max(
        0, (observation_date - current_date).days
    )

    decay_factor = math.exp(-days_since_last / DECAY_TIME_CONSTANT_DAYS)
    decayed_weight = float(current["prior_weight"]) * decay_factor
    new_total_weight = decayed_weight + float(observation["weight"])

    # Posterior mean — weighted blend of prior and observation.
    posterior_mean = (
        float(current["value"]) * decayed_weight
        + float(observation["value"]) * float(observation["weight"])
    ) / new_total_weight

    # Posterior uncertainty — shrinks as evidence accumulates, with
    # an irreducible floor of 0.5.
    scaled_uncertainty = float(current["uncertainty"]) * math.sqrt(
        decayed_weight / new_total_weight
    )
    posterior_uncertainty = max(scaled_uncertainty, UNCERTAINTY_FLOOR)

    # Dominant source — the observation wins only if it carries more
    # weight than the decayed prior. Stored as ``.value`` so the JSONB
    # column matches the shape produced by ``_bootstrap_signal``.
    if float(observation["weight"]) > decayed_weight:
        dominant_source = source_value(observation["source"])
    else:
        dominant_source = current["dominant_source"]

    return {
        "value": posterior_mean,
        "uncertainty": posterior_uncertainty,
        "prior_weight": new_total_weight,
        "dominant_source": dominant_source,
        "last_observation_date": observation_date.isoformat(),
    }


def init_null_parameter_state(
    observation: Mapping[str, Any],
) -> Dict[str, Any]:
    """Bootstrap a ``PhysiologyParameterState`` from a single observation.

    Used for the first observation of a parameter that has never
    been observed for the athlete — e.g. the first
    ``training_power_hr_ratio`` observation against a
    previously-null ``physiology.cp`` column. The initial ``value``
    is the observed value, ``uncertainty`` is the population
    default, ``prior_weight`` is the observation weight,
    ``dominant_source`` is the observation source, and
    ``last_observation_date`` is the observation date.

    This is the same shape that
    :func:`OnboardingService._bootstrap_signal` produces for
    questionnaire-estimated parameters; the only difference is the
    ``dominant_source`` and ``prior_weight`` originate from the
    observation rather than the bootstrap constants.
    """
    observation_date = coerce_observation_date(observation["date"])
    return {
        "value": float(observation["value"]),
        "uncertainty": INITIAL_UNCERTAINTY,
        "prior_weight": float(observation["weight"]),
        "dominant_source": source_value(observation["source"]),
        "last_observation_date": observation_date.isoformat(),
    }


# ---------------------------------------------------------------------------
# Output dataclasses.
# ---------------------------------------------------------------------------


@dataclass
class PhysiologyUpdateResult:
    """Return value of ``PhysiologyUpdateService.apply_observations``.

    Carries the full outcome of a single Bayesian-update pass so
    the worker task can:

    * Append a fresh ``TwinState`` referencing the updated
      ``AthletePhysiology`` row (``twin_state.physiology`` FK is
      not a thing — the snapshot is built from the returned
      ``physiology`` row).
    * Fire the ``physiology_updated`` event when
      ``shifted_parameters`` is non-empty (the architecture's
      ``> 1 unit shift`` gating).
    * Surface confidence transitions to the coaching-message
      pipeline so the athlete can be told their targets have been
      recalibrated.

    The dataclass is not ``frozen`` because the worker appends a
    ``TwinState`` and may enrich the result with the freshly-built
    snapshot id. Field types are deliberately concrete (not
    ``Any``) so the worker compiles against a stable shape.
    """

    physiology: AthletePhysiology
    shifted_parameters: list[PhysiologyParameter] = field(
        default_factory=lambda: []  # type: ignore[reportUnknownVariableType]
    )
    metric_confidence: Dict[str, Optional[str]] = field(
        default_factory=lambda: {}  # type: ignore[reportUnknownVariableType]
    )
    confidence_transitions: Dict[str, tuple[Optional[str], Optional[str]]] = (
        field(default_factory=lambda: {})  # type: ignore[reportUnknownVariableType]
    )
    measurements_written: int = 0


# ---------------------------------------------------------------------------
# Module-level helpers.
# ---------------------------------------------------------------------------


def parse_iso_date(value: str | date | datetime) -> date:
    """Parse the ISO-8601 ``last_observation_date`` JSONB string.

    Accepts the full ``datetime.isoformat()`` form
    (``"2024-05-12T08:30:00+00:00"``) produced by
    :func:`OnboardingService._bootstrap_signal` and the bare
    ``"YYYY-MM-DD"`` form produced by the Bayesian update return
    value.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    # ISO-8601 strings may include a time component; ``fromisoformat``
    # handles both bare-date and full-datetime forms in Python 3.11+.
    return datetime.fromisoformat(value).date()


def coerce_observation_date(value: date | datetime) -> date:
    """Coerce an observation ``date`` value to a ``datetime.date``.

    The ``PhysiologyMeasurement.measurement_date`` column is
    ``Date``; the Bayesian update only needs calendar-day
    granularity. A ``datetime`` is truncated to its date component.
    """
    if isinstance(value, datetime):
        return value.date()
    return value


def source_value(source: MeasurementSource | str) -> str:
    """Return the ``MeasurementSource.value`` string for ``source``.

    Accepts either a ``MeasurementSource`` enum member (preferred
    — produced by threshold detection) or a pre-stringified value
    (defensive — JSONB round-trips can hand back plain strings).
    """
    if isinstance(source, MeasurementSource):
        return source.value
    return str(source)


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class MissingAthletePhysiologyError(Exception):
    """The athlete has no ``AthletePhysiology`` row.

    The Phase-1.3 onboarding bootstrap always creates one — a
    missing row at update time is a data-integrity failure
    rather than a recoverable user error.
    """


# ---------------------------------------------------------------------------
# Parameter → JSONB path mapping.
# ---------------------------------------------------------------------------

#: Maps a :class:`PhysiologyParameter` to ``(outer_column, sub_key)``
#: on the ``AthletePhysiology`` row. ``outer_column`` is the JSONB
#: column name (``lt1``, ``lt2``, ``cp``, ``max_hr``); ``sub_key``
#: is the dict key inside the ``lt1`` / ``lt2`` container
#: (``hr``, ``power``, ``pace``) or ``None`` for single-state
#: columns (``cp``, ``max_hr``).
#:
#: Power/pace parameters (LT1_POWER, LT1_PACE, LT2_POWER, LT2_PACE,
#: VO2MAX_ML_KG_MIN, VO2MAX_POWER) are wired here so future
#: algorithm expansion does not require changing the service
#: — only the algorithms producing the observations.
_PARAMETER_PATH: Dict[PhysiologyParameter, Tuple[str, Optional[str]]] = {
    PhysiologyParameter.LT1_HR: ("lt1", "hr"),
    PhysiologyParameter.LT1_POWER: ("lt1", "power"),
    PhysiologyParameter.LT1_PACE: ("lt1", "pace"),
    PhysiologyParameter.LT2_HR: ("lt2", "hr"),
    PhysiologyParameter.LT2_POWER: ("lt2", "power"),
    PhysiologyParameter.LT2_PACE: ("lt2", "pace"),
    PhysiologyParameter.CP: ("cp", None),
    PhysiologyParameter.VO2MAX_ML_KG_MIN: ("vo2max", "ml_kg_min"),
    PhysiologyParameter.VO2MAX_POWER: ("vo2max", "power"),
    PhysiologyParameter.MAX_HR: ("max_hr", None),
}


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------


class PhysiologyUpdateService:
    """Apply threshold observations to ``AthletePhysiology`` posterior state.

    The service is the Phase-2.3-P2 owner of the in-place
    posterior mutation flow. It loads the athlete's existing
    ``AthletePhysiology`` row, dedups duplicate observations
    (writing the ``PhysiologyMeasurement`` audit row but
    skipping the Bayesian update and event contribution for
    the duplicate), routes each :class:`ThresholdObservation`
    to the right JSONB parameter path, runs the Bayesian
    update (or bootstraps a fresh state for a previously-null
    parameter), persists the ``PhysiologyMeasurement`` audit
    record, mutates the JSONB columns in place via
    ``flag_modified``, detects posterior shifts above the
    1-unit threshold, detects monotonic per-metric confidence
    transitions (LOW→MEDIUM→HIGH), and fires the
    ``physiology_updated`` event via :class:`EventPublisher`
    when at least one parameter shifted.

    The service is constructed with dependency-injected
    repositories and an optional :class:`EventPublisher` (the
    default is built from the session using the same
    ``SystemEvent`` + ``SystemEventOutbox`` pattern as
    :class:`ActivityIngestionService`). The whole
    ``apply_observations`` call writes to the database via a
    single ``AsyncSession`` so the ``AthletePhysiology``
    mutation, the ``PhysiologyMeasurement`` audit rows, and
    the ``physiology_updated`` outbox row are committed
    atomically by the worker task that owns the session.

    Public surface:

    * :meth:`apply_observations` — single async entry point.
      Returns a :class:`PhysiologyUpdateResult` summarising the
      pass.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        athlete_physiology_repository: Optional[
            AthletePhysiologyRepository
        ] = None,
        physiology_measurement_repository: Optional[
            PhysiologyMeasurementRepository
        ] = None,
        events: Optional[EventPublisher] = None,
    ) -> None:
        # The session is retained for repository construction by
        # default; the optional repository arguments let tests
        # inject mocks.
        self.session = session
        self.athlete_physiology = (
            athlete_physiology_repository
            or AthletePhysiologyRepository(session)
        )
        self.physiology_measurements = (
            physiology_measurement_repository
            or PhysiologyMeasurementRepository(session)
        )
        # The ``EventPublisher`` is default-built from the session when
        # not injected (same pattern as ``ActivityIngestionService``);
        # tests inject a fake to assert event payloads without
        # touching the ``system_events`` / ``system_event_outbox``
        # tables.
        self.events = events or self._build_default_publisher(session)

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------

    async def apply_observations(
        self,
        athlete_id: uuid.UUID,
        observations: List[ThresholdObservation],
    ) -> PhysiologyUpdateResult:
        """Apply a batch of threshold observations to one athlete.

        Per-observation flow:

        1. **Idempotency check** — if ``obs`` matches an existing
           ``PhysiologyMeasurement`` on
           ``(athlete_id, activity_id, parameter, source,
           measurement_date, observed_value)``, the
           ``PhysiologyMeasurement`` row is still written (for
           audit completeness) but the Bayesian update is
           skipped and the observation does NOT contribute to
           the ``physiology_updated`` event. This is the
           architecture's idempotency contract: "Submitting
           identical lab test measurements twice creates two
           ``PhysiologyMeasurement`` records but shifts the
           posterior only once from the first."
        2. Resolve the current ``PhysiologyParameterState`` for
           ``obs.parameter`` on the loaded ``AthletePhysiology``
           row. If the column / sub-state is null (the first
           qualifying observation for that parameter), bootstrap
           a fresh state via :func:`init_null_parameter_state`.
        3. Apply :func:`bayesian_update` to compute the new
           state.
        4. Persist the new state in the in-memory row's JSONB
           column (and call :func:`flag_modified` so SQLAlchemy
           persists the change at flush time).
        5. Write the ``PhysiologyMeasurement`` audit record —
           this is unconditional, even when the posterior does
           not shift.
        6. Compare the new posterior mean to the old one. If
           the shift exceeds 1 unit (bpm for HR, watts for CP /
           power), record the parameter as shifted for downstream
           event publication.

        After all observations are processed, the updated
        ``AthletePhysiology`` row is flushed via
        :meth:`AthletePhysiologyRepository.update_in_place` so
        the ``updated_at`` ``onupdate=`` hook fires, the
        per-metric confidence is recomputed, monotonic
        LOW→MEDIUM→HIGH transitions are detected, and the
        ``physiology_updated`` event is fired (only when at
        least one parameter shifted by > 1 unit). The event is
        written to the transactional outbox
        (``SystemEvent`` + ``SystemEventOutbox``) in the same
        transaction as the ``AthletePhysiology`` update —
        following the ``EventPublisher`` pattern used by
        :class:`ActivityIngestionService` and
        :class:`OnboardingService`.

        The caller (worker task in Phase-2.3-P3) owns the commit
        boundary.

        Raises:
            MissingAthletePhysiologyError: no ``AthletePhysiology``
                row exists for ``athlete_id``. The onboarding
                bootstrap always creates one — this is a
                data-integrity failure.
        """
        physiology = await self.athlete_physiology.get_by_athlete_id(
            athlete_id
        )
        if physiology is None:
            raise MissingAthletePhysiologyError(
                f"no AthletePhysiology row for athlete {athlete_id}"
            )

        # Snapshot the per-metric confidence BEFORE applying any
        # observations — the transition detector compares this
        # against the post-update snapshot to identify monotonic
        # upward transitions (LOW→MEDIUM, MEDIUM→HIGH). The
        # stored ``prior_weight`` only ever grows across
        # observations, so in practice the level only goes up;
        # the explicit comparison in
        # :func:`detect_confidence_transitions` is one-way to
        # preserve the "Confidence Does Not Decrease" invariant.
        old_confidence = compute_metric_confidence(physiology)

        # Work on a deep copy of each touched JSONB column so the
        # ``flag_modified`` write-back is a clean assignment of a
        # new dict (rather than relying on SQLAlchemy tracking
        # every nested-key mutation).
        working_state: Dict[PhysiologyParameter, Dict[str, Any]] = {}

        # ``shifted_parameters`` preserves observation order (for
        # the event payload), ``shifted_parameters_set`` enables
        # O(1) membership checks during the loop. The pair is
        # required because a parameter may shift on the first
        # observation of the batch but receive a second observation
        # that does not shift it again — the parameter must still
        # appear in the event payload.
        shifted_parameters: List[PhysiologyParameter] = []
        shifted_parameters_set: set[PhysiologyParameter] = set()
        # Per-parameter metadata for the ``physiology_updated``
        # event payload — updated for every non-duplicate
        # observation so the final posterior state is captured
        # even when multiple observations of the same parameter
        # land in one batch.
        dominant_sources: Dict[PhysiologyParameter, str] = {}
        prior_weights: Dict[PhysiologyParameter, float] = {}
        measurements_written = 0

        for obs in observations:
            # Idempotency check — duplicate observations still
            # write the audit row but skip the Bayesian update
            # and the event contribution. The dedup lookup uses
            # the same session so a duplicate within the same
            # ``apply_observations`` call (e.g. an observation
            # appearing twice in the input list) is correctly
            # detected after the first insert flushes.
            if await self._is_duplicate(athlete_id=athlete_id, obs=obs):
                await self._write_measurement(athlete_id=athlete_id, obs=obs)
                measurements_written += 1
                continue

            # Resolve the current state — null for previously
            # unobserved parameters. When a prior observation in
            # this same call already updated ``working_state`` for
            # ``obs.parameter``, that running posterior becomes the
            # new prior so the batch accumulates instead of every
            # iteration re-reading the original column value.
            current_state = working_state.get(
                obs.parameter,
                self.get_parameter_state(physiology, obs.parameter),
            )

            # Apply Bayesian update — bootstrap a fresh state for
            # previously-null parameters.
            observation_payload = {
                "value": obs.observed_value,
                "weight": obs.weight,
                "date": obs.measurement_date,
                "source": obs.source,
            }
            if current_state is None:
                new_state = init_null_parameter_state(observation_payload)
            else:
                new_state = bayesian_update(current_state, observation_payload)

            working_state[obs.parameter] = new_state

            # Persist the ``PhysiologyMeasurement`` audit record —
            # unconditional, even when the posterior does not shift.
            await self._write_measurement(athlete_id=athlete_id, obs=obs)
            measurements_written += 1

            # Shift detection — compare new vs old posterior mean.
            # Previously-null parameters always count as a shift on
            # the first observation because the posterior moved
            # from "no estimate" to "a number"; the architecture
            # requires the ``> 1 unit`` gate only for parameters
            # with an existing estimate, so this is correctly
            # suppressed by the ``current_state is None`` check.
            if current_state is not None:
                shift = abs(
                    float(new_state["value"])
                    - float(current_state["value"])
                )
                if (
                    shift > 1.0
                    and obs.parameter not in shifted_parameters_set
                ):
                    shifted_parameters_set.add(obs.parameter)
                    shifted_parameters.append(obs.parameter)

            # Track per-parameter metadata for the event payload.
            # Updated for every non-duplicate observation so a
            # second observation of an already-shifted parameter
            # captures the final posterior state in the event
            # payload (the last write to the dict wins).
            dominant_sources[obs.parameter] = new_state["dominant_source"]
            prior_weights[obs.parameter] = float(new_state["prior_weight"])

        # Apply the working state to the in-memory row and flush.
        # ``flag_modified`` is called on every column that was
        # touched so SQLAlchemy persists the JSONB mutation.
        if working_state:
            self.apply_updated_states(physiology, working_state)
            # Only pass the JSONB columns that were actually
            # touched in this call — the repository's
            # ``update_in_place`` already supports partial writes
            # (``if lt1 is not None``, ``if cp is not _UNSET``).
            # For ``lt1``/``lt2`` (non-nullable) ``None`` means
            # "do not touch"; for ``cp``/``max_hr`` (nullable) the
            # ``UNSET_SENTINEL`` distinguishes "do not touch" from
            # a legitimate ``None`` clear. This satisfies Plan
            # Step 6's "minimise write amplification" requirement.
            touched_columns = {
                _PARAMETER_PATH[parameter][0]
                for parameter in working_state
            }
            await self.athlete_physiology.update_in_place(
                athlete_id=athlete_id,
                lt1=physiology.lt1 if "lt1" in touched_columns else None,
                lt2=physiology.lt2 if "lt2" in touched_columns else None,
                cp=(
                    physiology.cp
                    if "cp" in touched_columns
                    else UNSET_SENTINEL
                ),
                max_hr=(
                    physiology.max_hr
                    if "max_hr" in touched_columns
                    else UNSET_SENTINEL
                ),
            )

        # Recompute per-metric confidence AFTER applying the
        # update — the diff against ``old_confidence`` identifies
        # the monotonic upward transitions Plan P3's
        # ``TwinRecalibrationService`` consumes to fire
        # ``twin_confidence_upgraded``.
        new_confidence = compute_metric_confidence(physiology)
        confidence_transitions = detect_confidence_transitions(
            old_confidence, new_confidence
        )

        # Fire ``physiology_updated`` only when at least one
        # parameter posterior shifted by > 1 unit — the
        # architecture's gate that keeps the topic from
        # producing noise on minor fluctuations. The event is
        # written to the transactional outbox in the same
        # transaction as the ``AthletePhysiology`` update
        # (the ``EventPublisher`` follows the same
        # ``SystemEvent`` + ``SystemEventOutbox`` pattern as
        # ``ActivityIngestionService`` and
        # ``OnboardingService`` — see ADR-004).
        if shifted_parameters:
            event_payload = {
                "athlete_id": str(athlete_id),
                "parameters_updated": [
                    param.value for param in shifted_parameters
                ],
                "dominant_sources": {
                    param.value: dominant_sources[param]
                    for param in shifted_parameters
                },
                "prior_weights": {
                    param.value: prior_weights[param]
                    for param in shifted_parameters
                },
            }
            await self.events.publish(
                event_type="physiology_updated",
                athlete_id=athlete_id,
                payload=event_payload,
            )

        return PhysiologyUpdateResult(
            physiology=physiology,
            shifted_parameters=shifted_parameters,
            metric_confidence=new_confidence,
            confidence_transitions=confidence_transitions,
            measurements_written=measurements_written,
        )

    # ------------------------------------------------------------------
    # Private helpers — JSONB path navigation and write-back.
    # ------------------------------------------------------------------

    @staticmethod
    def get_parameter_state(
        physiology: AthletePhysiology,
        parameter: PhysiologyParameter,
    ) -> Optional[Dict[str, Any]]:
        """Return the current ``PhysiologyParameterState`` for ``parameter``.

        Returns ``None`` when the outer column or the sub-state
        is null — the calling code treats this as the "first
        observation" path and bootstraps a fresh state via
        :func:`init_null_parameter_state`. The function never
        raises on a missing sub-state; the per-parameter path
        is fixed by the :data:`_PARAMETER_PATH` table.
        """
        if parameter not in _PARAMETER_PATH:
            raise ValueError(
                f"unsupported physiology parameter: {parameter!r}"
            )
        column_name, sub_key = _PARAMETER_PATH[parameter]
        column_value = getattr(physiology, column_name)
        if column_value is None:
            return None
        if sub_key is None:
            # Single-state column (cp, max_hr). Return a shallow
            # copy so the Bayesian update's returned dict is the
            # only mutation that lands in the working_state.
            return dict(column_value)
        sub_value = column_value.get(sub_key)
        if sub_value is None:
            return None
        return dict(sub_value)

    @staticmethod
    def apply_updated_states(
        physiology: AthletePhysiology,
        updated_states: Mapping[PhysiologyParameter, Dict[str, Any]],
    ) -> None:
        """Write the new states back to the in-memory row's JSONB columns.

        For ``lt1`` / ``lt2`` the sub-state is replaced inside the
        existing container (shallow-copied first to avoid mutating
        the column that other code may still be holding a
        reference to). For ``cp`` / ``max_hr`` the column is
        replaced wholesale. ``flag_modified`` is called on every
        touched column so SQLAlchemy emits the JSONB mutation at
        flush time — without this, the in-place dict assignment
        would not be picked up by the dirty tracker.
        """
        # Group updates by outer column so we only flag each
        # column once even if multiple sub-states changed.
        touched_columns: Dict[str, bool] = {}
        for parameter, new_state in updated_states.items():
            column_name, sub_key = _PARAMETER_PATH[parameter]
            touched_columns[column_name] = True
            if sub_key is None:
                # Single-state column — full replacement.
                setattr(physiology, column_name, dict(new_state))
                continue
            current_container = getattr(physiology, column_name)
            if current_container is None:
                # Container itself is null — build a fresh dict
                # with the new sub-state. The remaining null
                # sub-states stay null.
                fresh: Dict[str, Any] = {
                    "hr": None,
                    "power": None,
                    "pace": None,
                }
                fresh[sub_key] = dict(new_state)
                setattr(physiology, column_name, fresh)
                continue
            # Container exists — shallow-copy and replace the
            # single sub-state to avoid mutating the old dict in
            # place (defensive; SQLAlchemy's JSONB type tracks
            # top-level assignment only).
            new_container = dict(current_container)
            new_container[sub_key] = dict(new_state)
            setattr(physiology, column_name, new_container)

        for column_name in touched_columns:
            flag_modified(physiology, column_name)

    async def _write_measurement(
        self,
        *,
        athlete_id: uuid.UUID,
        obs: ThresholdObservation,
    ) -> PhysiologyMeasurement:
        """Persist the ``PhysiologyMeasurement`` audit record for ``obs``.

        The measurement record is the complete observation
        history — written unconditionally, even when the
        posterior does not shift. The
        ``raw_data_reference`` / ``notes`` columns are null for
        training-derived observations (the architecture reserves
        them for lab/field test manual ingestion flows).
        """
        measurement = PhysiologyMeasurement(
            athlete_id=athlete_id,
            activity_id=obs.activity_id,
            parameter=obs.parameter,
            observed_value=obs.observed_value,
            source=obs.source,
            measurement_date=obs.measurement_date,
            algorithm_used=obs.algorithm_used,
            confidence_weight=obs.confidence_weight,
            raw_data_reference=None,
            notes=None,
        )
        return await self.physiology_measurements.insert(measurement)

    @staticmethod
    def _build_default_publisher(
        session: AsyncSession,
    ) -> EventPublisher:
        """Build the default :class:`EventPublisher` for the session.

        Mirrors the pattern in
        :meth:`ActivityIngestionService._build_default_publisher` —
        the publisher writes ``SystemEvent`` + ``SystemEventOutbox``
        rows in the caller's transaction (transactional outbox,
        ADR-004). Returns a publisher bound to the same session
        as the service so the surrounding transaction commits
        everything atomically.
        """
        from app.repositories.system_event_outbox_repository import (
            SystemEventOutboxRepository,
        )
        from app.repositories.system_event_repository import SystemEventRepository

        return EventPublisher(
            SystemEventRepository(session),
            SystemEventOutboxRepository(session),
        )

    async def _is_duplicate(
        self,
        *,
        athlete_id: uuid.UUID,
        obs: ThresholdObservation,
    ) -> bool:
        """Return ``True`` if ``obs`` is a duplicate of an existing measurement.

        The architecture's idempotency contract
        (``docs/architecture/01-entities/athlete-physiology.md`` →
        Idempotency) defines a duplicate as the same
        ``(parameter, observed_value, measurement_date, source)``
        tuple. This service extends the match to include
        ``(athlete_id, activity_id)`` so a duplicate within the
        same activity is detected even when the algorithm runs
        twice in the same session.

        The lookup uses
        :meth:`PhysiologyMeasurementRepository.get_recent_for_parameter`
        with ``from_date=obs.measurement_date`` (the index covers
        ``(athlete_id, parameter, source, measurement_date)``) and
        then performs an exact-tuple Python-side filter on
        ``observed_value`` and ``activity_id``. A ``limit`` of 10
        is more than enough to catch any in-window duplicate
        while keeping the read bounded.
        """
        recent = await self.physiology_measurements.get_recent_for_parameter(
            athlete_id=athlete_id,
            parameter=obs.parameter,
            source=obs.source,
            from_date=obs.measurement_date,
            limit=10,
        )
        for record in recent:
            if (
                record.measurement_date == obs.measurement_date
                and float(record.observed_value) == float(obs.observed_value)
                and record.activity_id == obs.activity_id
            ):
                return True
        return False


# ---------------------------------------------------------------------------
# Per-metric confidence level derivation.
# ---------------------------------------------------------------------------


def confidence_level(prior_weight: Optional[float]) -> str:
    """Map a ``prior_weight`` to a ``TwinConfidenceLevel`` value string.

    Thresholds are 4.0 (LOW→MEDIUM) and 8.0 (MEDIUM→HIGH) per
    ``docs/architecture/00-foundations/confidence-model.md`` —
    the 15.0/40.0 example in the TwinState spec is a stale
    placeholder per the implementation plan's clarification.

    A ``None`` ``prior_weight`` is treated as zero (no evidence
    yet) and resolves to ``low``. This matches the bootstrap
    metric-confidence shape where only the questionnaire-derived
    HR parameters carry a non-null level.
    """
    if prior_weight is None:
        return TwinConfidenceLevel.LOW.value
    if prior_weight >= 8.0:
        return TwinConfidenceLevel.HIGH.value
    if prior_weight >= 4.0:
        return TwinConfidenceLevel.MEDIUM.value
    return TwinConfidenceLevel.LOW.value


def state_prior_weight(state: Optional[Mapping[str, Any]]) -> Optional[float]:
    """Return the ``prior_weight`` of a ``PhysiologyParameterState``.

    Handles ``None`` state and dicts missing the key defensively
    — the function returns ``None`` so the caller can map it to
    the LOW confidence level without raising.
    """
    if state is None:
        return None
    weight = state.get("prior_weight")
    return float(weight) if weight is not None else None


#: Numeric ordering of the :class:`TwinConfidenceLevel` enum, used
#: to detect monotonic upward transitions between old and new
#: confidence levels. Index ``0`` is the lowest tier.
_CONFIDENCE_LEVEL_ORDER: Dict[str, int] = {
    TwinConfidenceLevel.LOW.value: 0,
    TwinConfidenceLevel.MEDIUM.value: 1,
    TwinConfidenceLevel.HIGH.value: 2,
}


def detect_confidence_transitions(
    old: Mapping[str, Optional[str]],
    new: Mapping[str, Optional[str]],
) -> Dict[str, tuple[Optional[str], Optional[str]]]:
    """Return the per-metric confidence transitions between ``old`` and ``new``.

    A transition is a monotonic *upward* change in the per-metric
    confidence level (LOW→MEDIUM or MEDIUM→HIGH). Downward
    changes are never transitions — confidence is ratcheting,
    per the architecture's "Confidence Does Not Decrease"
    invariant; the prior decay affects recommendation strength,
    not the confidence enum. The ``stored`` ``prior_weight``
    only ever grows across observations, so in practice the
    level only goes up, but the comparison is explicitly
    one-directional so any future change to the storage
    convention does not silently break the contract.

    The returned dict has one entry per metric that transitioned
    up, keyed by metric name with a ``(from_level, to_level)``
    tuple as the value. ``None`` old or new levels are mapped to
    ``"low"`` for the comparison so a metric that has just
    acquired its first observation (new level MEDIUM, old level
    ``None``) is correctly identified as a transition.

    This dict is consumed by Plan P3's
    :class:`TwinRecalibrationService` to fire
    ``twin_confidence_upgraded`` for each upgraded metric.
    """
    transitions: Dict[str, tuple[Optional[str], Optional[str]]] = {}
    for metric, new_level in new.items():
        old_level = old.get(metric)
        # Normalise ``None`` to LOW for the comparison; matches the
        # ``confidence_level`` default for missing prior weights.
        old_rank = _CONFIDENCE_LEVEL_ORDER.get(
            old_level if old_level is not None else TwinConfidenceLevel.LOW.value
        )
        new_rank = _CONFIDENCE_LEVEL_ORDER.get(
            new_level if new_level is not None else TwinConfidenceLevel.LOW.value
        )
        if old_rank is None or new_rank is None:
            # Defensive — an unknown level string is treated as
            # "no transition" so the surrounding pipeline does
            # not crash on a malformed JSONB value.
            continue
        if new_rank > old_rank:
            transitions[metric] = (old_level, new_level)
    return transitions


def compute_metric_confidence(
    physiology: AthletePhysiology,
) -> Dict[str, Optional[str]]:
    """Return the per-metric confidence dict in ``TwinState`` shape.

    Mirrors :func:`OnboardingService._bootstrap_metric_confidence`
    — the same eight keys, with confidence levels derived from
    the current ``prior_weight`` of each parameter's posterior
    state. The ``vo2max`` keys are deliberately omitted at this
    phase (VO2max is not yet wired into the worker pipeline);
    they land when Plan P3's update flow reaches the VO2max
    dimension.

    The ``cp`` key reads from ``physiology.cp`` (single-state
    column) and is ``None`` until the first qualifying
    observation arrives — the architecture invariant
    "cp and vo2max are null until a qualifying observation is
    made" applies to the per-metric confidence shape too.
    """
    lt1 = physiology.lt1 or {}
    lt2 = physiology.lt2 or {}
    return {
        "lt1_hr": confidence_level(
            state_prior_weight(lt1.get("hr") if lt1 else None)
        ),
        "lt1_power": confidence_level(
            state_prior_weight(lt1.get("power") if lt1 else None)
        ),
        "lt1_pace": confidence_level(
            state_prior_weight(lt1.get("pace") if lt1 else None)
        ),
        "lt2_hr": confidence_level(
            state_prior_weight(lt2.get("hr") if lt2 else None)
        ),
        "lt2_power": confidence_level(
            state_prior_weight(lt2.get("power") if lt2 else None)
        ),
        "lt2_pace": confidence_level(
            state_prior_weight(lt2.get("pace") if lt2 else None)
        ),
        "cp": confidence_level(state_prior_weight(physiology.cp)),
    }


# ---------------------------------------------------------------------------
# Re-exported symbols — used by the worker task and by the unit
# tests that exercise the Bayesian update in isolation.
# ---------------------------------------------------------------------------

__all__ = [
    "DECAY_TIME_CONSTANT_DAYS",
    "UNCERTAINTY_FLOOR",
    "INITIAL_UNCERTAINTY",
    "MissingAthletePhysiologyError",
    "PhysiologyUpdateResult",
    "PhysiologyUpdateService",
    "bayesian_update",
    "init_null_parameter_state",
]
