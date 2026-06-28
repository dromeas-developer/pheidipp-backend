"""OnboardingService — atomic onboarding transaction and twin-bootstrap reads.

Implements the Phase-1.3 contract from
docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md
and the architecture contracts in
``docs/architecture/01-entities/{athlete-profile,athlete-preferences,
training-goal,athlete-physiology,athlete-fitness,twin-state}.md``.

Atomicity guarantees:

* ``complete_onboarding`` is the sole owner of the onboarding
  transaction. It runs every write through the per-entity repositories
  on a single shared ``AsyncSession`` and commits exactly once at the
  end of the method. Raising any exception before the commit causes
  SQLAlchemy to roll back the session automatically — partial state is
  never visible to other readers and ``onboarding_complete`` stays
  ``False``.
* The ``onboarding_completed`` event is persisted via the transactional
  outbox (``SystemEvent`` + ``SystemEventOutbox`` rows) inside the SAME
  transaction as the producing domain state, per ADR-004. Publication
  to the message bus belongs to the platform publisher worker and
  runs strictly after this transaction commits.

Bootstrap rules enforced here:

* Only ``race_event`` and ``target_performance`` are accepted at
  onboarding; other ``GoalType`` values raise ``InvalidGoalTypeError``
  (HTTP 422).
* The IANA ``timezone`` identifier is validated at the Pydantic schema
  layer (``OnboardingProfileIn``) using ``zoneinfo`` so an invalid
  identifier is rejected with HTTP 422 before this service runs.
* Threshold estimates (``lt1.hr``, ``lt2.hr``, ``max_hr``) are
  bootstrapped from age-graded population norms using
  ``AthleteProfile.date_of_birth`` (220-age; 0.75× and 0.875× factors).
* ``cp`` and ``vo2max`` are NEVER estimated from the questionnaire;
  they remain ``null`` at bootstrap.
* ``TwinState`` is append-only — created via ``TwinStateRepository.insert``
  and never updated afterwards (the repository exposes no
  ``update``/``delete`` methods).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional, TYPE_CHECKING

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import (
    AthletePreferences,
    infer_data_tier,
)
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    GoalType,
    MeasurementSource,
    RecoveryModifierLevel,
    SportBackground,
    TrainingGoalStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from app.repositories.athlete_fitness_repository import AthleteFitnessRepository
from app.repositories.athlete_physiology_repository import (
    AthletePhysiologyRepository,
)
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.event_publisher import EventPublisher
from app.services.onboarding_errors import (
    AthleteNotFoundError,
    InvalidGoalTypeError,
    OnboardingAlreadyCompleteError,
    TrainingGoalConflictError,
)
from app.services.onboarding_results import (
    OnboardingResult,
    OnboardingStatus,
)

if TYPE_CHECKING:
    # Imported only for type-checking so the runtime dependency graph
    # between the onboarding and plan-generation services stays
    # one-way. ``OnboardingService.__init__`` accepts an optional
    # ``PlanGenerationService`` instance built on the same
    # ``AsyncSession`` so the two services share a single transaction.
    from app.services.plan_generation_service import PlanGenerationService

# ---------------------------------------------------------------------------
# Constants — bootstrapped from architecture documents.
# ---------------------------------------------------------------------------

# Goal types accepted at onboarding. ``fitness_improvement`` /
# ``maintenance`` / ``recovery`` are rejected with 422.
ALLOWED_ONBOARDING_GOAL_TYPES: frozenset[GoalType] = frozenset(
    {GoalType.RACE_EVENT, GoalType.TARGET_PERFORMANCE}
)

# Twin model version string for the bootstrap snapshot.
BOOTSTRAP_MODEL_VERSION = "v1-questionnaire-bootstrap"

# Population time constants per the architecture's Banister contract.
# Source: ``docs/architecture/01-entities/athlete-fitness.md``
POPULATION_TAU = {
    "aerobic": {"fitness_tau_days": 42, "fatigue_tau_days": 7},
    "neuromuscular": {"fitness_tau_days": 21, "fatigue_tau_days": 3},
    "structural": {"fitness_tau_days": 56, "fatigue_tau_days": 14},
}

# Threshold factor for LT1 (75% of max HR) and LT2 (87.5% of max HR)
# per the architecture's confidence model.
LT1_FACTOR = 0.75
LT2_FACTOR = 0.875

# Default uncertainty applied to bootstrap posterior states — population
# priors are high-uncertainty until individual observations arrive.
BOOTSTRAP_UNCERTAINTY = 1.0

# Default prior weight for bootstrap posterior states (uniform weight 0.5
# per the architecture's Bayesian contract).
BOOTSTRAP_PRIOR_WEIGHT = 0.5


# ---------------------------------------------------------------------------
# Input payload contracts — typed dicts that the API layer maps from
# Pydantic schemas. The service is HTTP-framework agnostic.
# ---------------------------------------------------------------------------


class _ProfileInput:
    """Subset of profile fields the onboarding transaction mutates."""

    __slots__ = ("timezone", "training_window", "height_cm")

    def __init__(
        self,
        *,
        timezone: str,
        training_window: Optional[dict],
        height_cm: Optional[float],
    ) -> None:
        self.timezone = timezone
        self.training_window = training_window
        self.height_cm = height_cm


class _PreferencesInput:
    """Full AthletePreferences payload the onboarding transaction creates."""

    __slots__ = (
        "sport_background",
        "years_structured_training",
        "training_time_of_day",
        "weekly_schedule",
        "gps_source",
        "hr_source",
        "power_source",
        "primary_training_platform",
    )

    def __init__(
        self,
        *,
        sport_background: SportBackground,
        years_structured_training: int,
        training_time_of_day: str,
        weekly_schedule: dict,
        gps_source: str,
        hr_source: str,
        power_source: str,
        primary_training_platform: str,
    ) -> None:
        self.sport_background = sport_background
        self.years_structured_training = years_structured_training
        self.training_time_of_day = training_time_of_day
        self.weekly_schedule = weekly_schedule
        self.gps_source = gps_source
        self.hr_source = hr_source
        self.power_source = power_source
        self.primary_training_platform = primary_training_platform


class _GoalInput:
    """Full TrainingGoal payload the onboarding transaction creates."""

    __slots__ = (
        "goal_type",
        "goal_event_type",
        "goal_event_name",
        "goal_event_date",
        "custom_distance_km",
        "goal_description",
        "weekly_volume_hours",
        "weekly_volume_km",
        "fitness_level",
        "recent_injury",
        "injury_severity",
        "target_distance_km",
        "target_time_minutes",
    )

    def __init__(
        self,
        *,
        goal_type: GoalType,
        goal_event_type: Any,
        goal_event_name: Optional[str],
        goal_event_date: Optional[date],
        custom_distance_km: Optional[float],
        goal_description: Optional[str],
        weekly_volume_hours: float,
        weekly_volume_km: float,
        fitness_level: int,
        recent_injury: Optional[str],
        injury_severity: Any,
        target_distance_km: Optional[float],
        target_time_minutes: Optional[int],
    ) -> None:
        self.goal_type = goal_type
        self.goal_event_type = goal_event_type
        self.goal_event_name = goal_event_name
        self.goal_event_date = goal_event_date
        self.custom_distance_km = custom_distance_km
        self.goal_description = goal_description
        self.weekly_volume_hours = weekly_volume_hours
        self.weekly_volume_km = weekly_volume_km
        self.fitness_level = fitness_level
        self.recent_injury = recent_injury
        self.injury_severity = injury_severity
        self.target_distance_km = target_distance_km
        self.target_time_minutes = target_time_minutes


class OnboardingService:
    """Own the onboarding transaction and the read endpoints it enables.

    The service is constructed with a per-request ``AsyncSession`` so
    every operation participates in a single transaction. The session
    is committed exactly once — inside ``complete_onboarding`` —
    after the full bootstrap sequence has landed and the
    ``onboarding_completed`` event has been written through the
    transactional outbox.

    Phase-1.4 onboarding integration: when ``plan_service`` is
    provided, plan generation is wired into the same transaction so
    the plan and onboarding land atomically. The commit boundary is
    then moved to ``plan_service.generate_plan`` (the plan service
    owns the final ``commit``); when ``plan_service is None``,
    ``complete_onboarding`` commits directly. This is the only way
    plan-service failures roll back onboarding state.
    """

    def __init__(
        self,
        session: AsyncSession,
        events: Optional[EventPublisher] = None,
        plan_service: Optional["PlanGenerationService"] = None,
    ) -> None:
        self.session = session
        self.athletes = AthleteRepository(session)
        self.profiles = AthleteProfileRepository(session)
        self.preferences = AthletePreferencesRepository(session)
        self.training_goals = TrainingGoalRepository(session)
        self.physiology = AthletePhysiologyRepository(session)
        self.fitness = AthleteFitnessRepository(session)
        self.twin_states = TwinStateRepository(session)
        self.plan_service = plan_service
        if events is None:
            # Build a real publisher on demand — keep the constructor
            # signature thin while preserving atomic event writes.
            from app.repositories.system_event_outbox_repository import (
                SystemEventOutboxRepository,
            )
            from app.repositories.system_event_repository import (
                SystemEventRepository,
            )

            self.events = EventPublisher(
                SystemEventRepository(session),
                SystemEventOutboxRepository(session),
            )
        else:
            self.events = events

    # ------------------------------------------------------------------
    # Onboarding transaction — sole owner of the write sequence.
    # ------------------------------------------------------------------

    async def complete_onboarding(
        self,
        *,
        athlete_id: uuid.UUID,
        profile_input: _ProfileInput,
        prefs_input: _PreferencesInput,
        goal_input: _GoalInput,
    ) -> OnboardingResult:
        """Run the full bootstrap sequence in one atomic transaction.

        Ordering matters because of FK constraints and to keep
        ``onboarding_complete`` flipped only at the very end so that
        any mid-transaction failure leaves the gate at ``False``
        alongside rolled-back state.

        Raises:
            AthleteNotFoundError: path athlete_id does not match an
                ``Athlete`` row.
            OnboardingAlreadyCompleteError: gate already ``True`` (409).
            InvalidGoalTypeError: ``goal_type`` outside the onboarding
                whitelist (422).
            TrainingGoalConflictError: a second active goal was inserted
                for the same athlete (409, partial unique index fires).
        """
        athlete = await self.athletes.get_by_id(athlete_id)
        if athlete is None:
            raise AthleteNotFoundError("athlete not found")
        if athlete.onboarding_complete:
            raise OnboardingAlreadyCompleteError(
                "onboarding has already been completed"
            )

        self._validate_goal_type(goal_input.goal_type)

        # 1. Update the AthleteProfile row created during registration.
        profile_row = await self.profiles.get_by_athlete_id(athlete_id)
        if profile_row is None:
            # Phase-1.1 registration always creates a profile; missing
            # here means the athlete exists but the registration path
            # did not run — treat as a not-found for the athlete's
            # onboarding surface.
            raise AthleteNotFoundError("athlete profile missing")

        profile_row.timezone = profile_input.timezone
        if profile_input.training_window is not None:
            profile_row.training_window = profile_input.training_window
        if profile_input.height_cm is not None:
            profile_row.height_cm = profile_input.height_cm
        profile_row.structural_risk_flag = (
            prefs_input.sport_background != SportBackground.RUNNING_PRIMARY
        )
        await self.session.flush()

        # 2. Create AthletePreferences.
        prefs_row = AthletePreferences(
            athlete_id=athlete_id,
            sport_background=prefs_input.sport_background,
            years_structured_training=prefs_input.years_structured_training,
            training_time_of_day=prefs_input.training_time_of_day,
            weekly_schedule=prefs_input.weekly_schedule,
            gps_source=prefs_input.gps_source,
            hr_source=prefs_input.hr_source,
            power_source=prefs_input.power_source,
            primary_training_platform=prefs_input.primary_training_platform,
        )
        await self.preferences.add(prefs_row)

        # 3. Create the active TrainingGoal. The partial unique index
        #    ``ix_training_goals_athlete_active`` raises IntegrityError
        #    on conflict — mapped to TrainingGoalConflictError (409).
        goal_row = TrainingGoal(
            athlete_id=athlete_id,
            goal_type=goal_input.goal_type,
            goal_event_type=goal_input.goal_event_type,
            goal_event_name=goal_input.goal_event_name,
            goal_event_date=goal_input.goal_event_date,
            custom_distance_km=goal_input.custom_distance_km,
            goal_description=goal_input.goal_description,
            weekly_volume_hours=goal_input.weekly_volume_hours,
            weekly_volume_km=goal_input.weekly_volume_km,
            fitness_level=goal_input.fitness_level,
            recent_injury=goal_input.recent_injury,
            injury_severity=goal_input.injury_severity,
            target_distance_km=goal_input.target_distance_km,
            target_time_minutes=goal_input.target_time_minutes,
            status=TrainingGoalStatus.ACTIVE,
        )
        try:
            await self.training_goals.add(goal_row)
        except IntegrityError as exc:
            await self.session.rollback()
            if TrainingGoalRepository_unique_violation(exc):
                raise TrainingGoalConflictError(
                    "athlete already has an active training goal"
                ) from exc
            raise

        # 4. Bootstrap AthletePhysiology — age-graded threshold estimates
        #    derived from date_of_birth. ``cp`` and ``vo2max`` stay null.
        today = datetime.now(timezone.utc)
        age_years = _age_in_years(profile_row.date_of_birth, today)
        max_hr_est = 220 - age_years
        lt1_hr_est = round(max_hr_est * LT1_FACTOR, 2)
        lt2_hr_est = round(max_hr_est * LT2_FACTOR, 2)

        physio_row = AthletePhysiology(
            athlete_id=athlete_id,
            lt1={
                "hr": _bootstrap_signal(
                    value=lt1_hr_est, observation_date=today
                ),
                "power": None,
                "pace": None,
            },
            lt2={
                "hr": _bootstrap_signal(
                    value=lt2_hr_est, observation_date=today
                ),
                "power": None,
                "pace": None,
            },
            cp=None,
            vo2max=None,
            max_hr=_bootstrap_signal(
                value=float(max_hr_est), observation_date=today
            ),
        )
        await self.physiology.add(physio_row)

        # 5. Bootstrap AthleteFitness — zero fitness / fatigue / form,
        #    population time constants, no dimensional blocks.
        fitness_row = AthleteFitness(
            athlete_id=athlete_id,
            aggregate={
                "fitness": 0.0,
                "fatigue": 0.0,
                "form": 0.0,
            },
            aerobic=None,
            neuromuscular=None,
            structural=None,
            time_constants={
                "source": "population_default",
                "aerobic": POPULATION_TAU["aerobic"],
                "neuromuscular": POPULATION_TAU["neuromuscular"],
                "structural": POPULATION_TAU["structural"],
                "fitted_at": today.isoformat(),
            },
            last_activity_id=None,
        )
        await self.fitness.add(fitness_row)

        # 6. Append the first TwinState — append-only insert.
        data_tier = infer_data_tier(prefs_input.hr_source, prefs_input.power_source)
        metric_confidence = _bootstrap_metric_confidence()
        twin_state = TwinState(
            athlete_id=athlete_id,
            training_goal_id=goal_row.id,
            activity_id=None,
            data_tier=data_tier,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.QUESTIONNAIRE,
            model_version=BOOTSTRAP_MODEL_VERSION,
            fitness=0.0,
            fatigue=0.0,
            form=0.0,
            lt1_pace_sec_per_km=None,
            lt1_power_watts=None,
            lt1_hr_bpm=float(lt1_hr_est),
            lt2_pace_sec_per_km=None,
            lt2_power_watts=None,
            lt2_hr_bpm=float(lt2_hr_est),
            cp_watts=None,
            readiness_level=RecoveryModifierLevel.GREEN,
            wellness_trend=None,
            metric_confidence=metric_confidence,
        )
        await self.twin_states.insert(twin_state)

        # 7. Flip the gate.
        athlete.onboarding_complete = True
        await self.session.flush()

        # 8. Persist the onboarding_completed event via the outbox.
        await self.events.publish(
            event_type="onboarding_completed",
            athlete_id=athlete_id,
            payload={
                "training_goal_id": str(goal_row.id),
                "twin_state_id": str(twin_state.id),
                "data_tier": int(data_tier.value),
                "confidence_level": TwinConfidenceLevel.LOW.value,
            },
        )

        # 9. Plan generation — Phase-1.4. When ``plan_service`` is
        #    wired, atomically generate the initial plan in this same
        #    transaction. The plan service commits once at the end of
        #    its work, so we skip the standalone commit below; any
        #    plan-generation error rolls the entire transaction back
        #    so ``onboarding_complete`` stays ``False``.
        #    When ``plan_service is None``, onboarding commits directly
        #    (graceful degradation for unit tests that do not exercise
        #    the plan path).
        if self.plan_service is not None:
            await self.plan_service.generate_plan(athlete_id=athlete_id)
            return OnboardingResult(
                twin_state=twin_state,
                training_goal=goal_row,
                preferences=prefs_row,
                profile=profile_row,
                data_tier=int(data_tier.value),
            )

        # 9. Commit the whole bootstrap atomically.
        await self.session.commit()

        return OnboardingResult(
            twin_state=twin_state,
            training_goal=goal_row,
            preferences=prefs_row,
            profile=profile_row,
            data_tier=int(data_tier.value),
        )

    # ------------------------------------------------------------------
    # Status + read endpoints.
    # ------------------------------------------------------------------

    async def get_onboarding_status(
        self, athlete_id: uuid.UUID
    ) -> OnboardingStatus:
        """Return the per-entity existence flags for an athlete.

        Used by ``GET /athletes/{id}/onboarding`` to render a status
        summary whether or not onboarding has run. Every lookup is a
        single targeted query; the service does NOT mutate state.
        """
        athlete = await self.athletes.get_by_id(athlete_id)
        if athlete is None:
            raise AthleteNotFoundError("athlete not found")
        profile_row = await self.profiles.get_by_athlete_id(athlete_id)
        prefs_row = await self.preferences.get_by_athlete_id(athlete_id)
        goal_row = await self.training_goals.get_active(athlete_id)
        twin_row = await self.twin_states.get_latest(athlete_id)
        return OnboardingStatus(
            onboarding_complete=athlete.onboarding_complete,
            has_profile=profile_row is not None,
            has_preferences=prefs_row is not None,
            has_training_goal=goal_row is not None,
            has_twin_state=twin_row is not None,
        )

    async def get_profile(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthleteProfile]:
        """Return the ``AthleteProfile`` row, or ``None``.

        A profile row always exists post-registration (Phase-1.1
        contract), so this method returning ``None`` would mean the
        athlete record is missing — the API layer treats the absence
        as 404. The API layer maps the row into the public response
        via ``AthleteProfileResponse.model_validate(row)`` to keep
        the ORM→DTO conversion in one place.
        """
        return await self.profiles.get_by_athlete_id(athlete_id)

    async def update_profile(
        self,
        athlete_id: uuid.UUID,
        *,
        height_cm: Optional[float] = None,
        location_lat: Optional[float] = None,
        location_lng: Optional[float] = None,
        training_window: Optional[dict] = None,
    ) -> AthleteProfile:
        """PATCH the mutable subset of ``AthleteProfile``.

        The mutable subset is ``height_cm``, ``location_lat``,
        ``location_lng``, ``training_window``. The immutable fields
        (``date_of_birth``, ``sex``, ``timezone``) are rejected by
        the API layer with HTTP 422 — they never reach this method.

        The freshly-updated row is returned so the API layer can map
        it into the response via ``model_validate`` without a second
        lookup. ``update_at`` is populated by SQLAlchemy's
        ``onupdate=`` hook at commit time.

        Raises:
            AthleteNotFoundError: no profile row exists for the athlete.
        """
        row = await self.profiles.get_by_athlete_id(athlete_id)
        if row is None:
            raise AthleteNotFoundError("athlete profile missing")

        if height_cm is not None:
            row.height_cm = height_cm
        if location_lat is not None:
            row.location_lat = location_lat
        if location_lng is not None:
            row.location_lng = location_lng
        if training_window is not None:
            row.training_window = training_window

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_preferences(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthletePreferences]:
        """Return the ``AthletePreferences`` row, or ``None``.

        ``None`` indicates that onboarding has not yet created the row —
        the API layer maps this to HTTP 404 with a descriptive detail.
        """
        return await self.preferences.get_by_athlete_id(athlete_id)

    async def update_preferences(
        self,
        athlete_id: uuid.UUID,
        patch: Mapping[str, Any],
    ) -> AthletePreferences:
        """PATCH ``AthletePreferences`` at the field level.

        ``weekly_schedule`` is the only nested field; it merges at the
        day level per the architecture note — a PATCH of
        ``{"saturday": {"available": false}}`` flips Saturday without
        touching the other six days. All other top-level fields are
        overwritten when present in the patch payload.

        The freshly-updated row is returned so the API layer can map
        it into the response via ``model_validate`` without a second
        lookup.

        Raises:
            AthleteNotFoundError: no preferences row exists for the
                athlete (i.e. onboarding has not yet run).
        """
        row = await self.preferences.get_by_athlete_id(athlete_id)
        if row is None:
            raise AthleteNotFoundError("athlete preferences missing")

        for key, value in patch.items():
            if key == "weekly_schedule":
                # Day-level merge: shallow-merge the per-day subdict.
                merged = dict(row.weekly_schedule or {})
                for day, day_patch in value.items():
                    merged[day] = {
                        **(merged.get(day) or {}),
                        **(day_patch or {}),
                    }
                row.weekly_schedule = merged
            elif key == "sport_background":
                row.sport_background = value
            elif key == "years_structured_training":
                row.years_structured_training = value
            elif key == "training_time_of_day":
                row.training_time_of_day = value
            elif key == "gps_source":
                row.gps_source = value
            elif key == "hr_source":
                row.hr_source = value
            elif key == "power_source":
                row.power_source = value
            elif key == "primary_training_platform":
                row.primary_training_platform = value
            # Unknown keys are ignored — keep PATCH forward-compatible.

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_twin_state(
        self, athlete_id: uuid.UUID
    ) -> Optional[TwinState]:
        """Return the latest TwinState for *athlete_id*, or ``None``.

        The repository guarantees ordering by ``created_at`` descending
        via the ``idx_twin_states_latest`` index — no further sorting
        required here.
        """
        return await self.twin_states.get_latest(athlete_id)

    async def get_twin_history(
        self, athlete_id: uuid.UUID, limit: int = 20
    ) -> list[TwinState]:
        """Return up to *limit* TwinState rows for *athlete_id*, newest first.

        Empty list returned when no records exist. ``limit`` is
        caller-bounded (the API layer clamps to 100).
        """
        return await self.twin_states.get_history(athlete_id, limit=limit)

    # ------------------------------------------------------------------
    # Validation helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_goal_type(goal_type: GoalType) -> None:
        """Reject ``GoalType`` values outside the onboarding whitelist.

        The IANA timezone identifier is validated by the Pydantic schema
        layer (``OnboardingProfileIn``) so an invalid timezone is
        rejected with HTTP 422 before the service is ever called.
        """
        if not isinstance(goal_type, GoalType):
            raise TypeError(
                f"goal_type must be a GoalType enum member, got {type(goal_type).__name__}"
            )
        if goal_type not in ALLOWED_ONBOARDING_GOAL_TYPES:
            raise InvalidGoalTypeError(
                f"goal_type '{goal_type.value}' is not permitted at onboarding"
            )


# ---------------------------------------------------------------------------
# Module-level helpers — kept outside the class so unit tests can exercise
# them in isolation.
# ---------------------------------------------------------------------------


def TrainingGoalRepository_unique_violation(error: IntegrityError) -> bool:
    """Return True if *error* is a 23505 unique-constraint violation.

    Mirrors :meth:`app.repositories.athlete_repository.AthleteRepository.is_unique_violation`.
    Kept module-level so it can be reused if a future repository needs
    the same PostgreSQL error-code detection.
    """
    orig = getattr(error, "orig", None)
    if orig is None:
        return False
    pgcode = getattr(orig, "pgcode", None)
    return pgcode == "23505"


def _age_in_years(dob: date, now: datetime) -> int:
    """Compute completed years between *dob* and *now*.

    Mirrors the standard birthday-based computation. Negative ages are
    never produced because ``date_of_birth`` is required at
    registration and validated against the future.
    """
    age = now.year - dob.year
    if (now.month, now.day) < (dob.month, dob.day):
        age -= 1
    return max(0, age)


def _bootstrap_signal(*, value: float, observation_date: datetime) -> dict:
    """Return the ``PhysiologyParameterState`` JSON shape for a
    bootstrap posterior — ``value``, ``uncertainty`` (population-level
    wide prior), ``prior_weight`` 0.5, ``dominant_source`` set to
    ``questionnaire_estimate``, and ``last_observation_date`` set to
    the bootstrap timestamp.
    """
    return {
        "value": value,
        "uncertainty": BOOTSTRAP_UNCERTAINTY,
        "prior_weight": BOOTSTRAP_PRIOR_WEIGHT,
        "dominant_source": MeasurementSource.QUESTIONNAIRE_ESTIMATE.value,
        "last_observation_date": observation_date.isoformat(),
    }


def _bootstrap_metric_confidence() -> dict:
    """Return the per-metric confidence JSONB for the bootstrap twin state.

    Only ``lt1_hr`` and ``lt2_hr`` are populated at bootstrap (both
    ``low``). All other metric keys are explicitly ``null`` — never
    missing — per the architecture contract.
    """
    return {
        "lt1_hr": TwinConfidenceLevel.LOW.value,
        "lt1_power": None,
        "lt1_pace": None,
        "lt2_hr": TwinConfidenceLevel.LOW.value,
        "lt2_power": None,
        "lt2_pace": None,
        "cp": None,
    }
