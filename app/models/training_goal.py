"""TrainingGoal — period of goal-directed training.

Implements the Phase-1.2b schema contract from
docs/architecture/01-entities/training-goal.md.

Schema-only foundation: no creation, closure, or PATCH endpoints are
added by this plan. The model exposes only the storage shape so
Phase-1.2b's Alembic migration can bring up the table without
introducing a service layer that would couple this plan to plan
generation.

Invariants codified at the database layer:

* One active goal per athlete — enforced by partial unique index
  ``ix_training_goals_athlete_active`` on ``(athlete_id) WHERE
  status = 'active'``.
* Immutable semantic fields (``goal_type``, ``goal_event_type``,
  ``goal_event_name``, ``custom_distance_km``, ``weekly_volume_hours``,
  ``weekly_volume_km``, ``fitness_level``, ``recent_injury``,
  ``injury_severity``, ``target_distance_km``,
  ``target_time_minutes``) are simply defined as non-null columns;
  the behavioral invariant that they are not updated after creation
  is enforced at the application layer in later phases.
* Volume‐field non-negative checks (``weekly_volume_hours >= 0``,
  ``weekly_volume_km >= 0``) and ``fitness_level`` range (1..5) are
  enforced via CHECK constraints.
* ``target_distance_km`` and ``target_time_minutes`` are nullable
  but constrained positive when present (matches ``> 0`` semantics
  for ``target_performance`` goals).
* ``custom_distance_km`` is constrained positive when present
  (``> 0`` for ``goal_event_type = 'custom'``).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import (
    GoalEventType,
    GoalType,
    InjurySeverity,
    TrainingGoalStatus,
)


class TrainingGoal(Base):
    """Period of goal-directed training for a single ``Athlete``.

    Will be referenced by ``SecondaryEvent``, ``RegenerationTask``,
    and ``TrainingPlan`` child entities (created by Phase-1.2b's
    sibling tables). The relationship side will be wired in those
    model files.
    """

    __tablename__ = "training_goals"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Goal definition — immutable after creation (enforced at app layer).
    #
    # ``goal_event_type`` and ``goal_event_name`` are null unless
    # ``goal_type = 'race_event'``.
    # ``custom_distance_km`` is set only when ``goal_event_type =
    # 'custom'`` and must be positive when present.
    # ``goal_event_date`` is null for non-race-event goal types.
    # ------------------------------------------------------------------
    goal_type: Mapped[GoalType] = mapped_column(
        SAEnum(
            GoalType,
            name="goal_type",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    goal_event_type: Mapped[GoalEventType | None] = mapped_column(
        SAEnum(
            GoalEventType,
            name="goal_event_type",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=True,
    )
    goal_event_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    goal_event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    custom_distance_km: Mapped[float | None] = mapped_column(nullable=True)
    goal_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Self-reported context — immutable after creation.
    # ------------------------------------------------------------------
    weekly_volume_hours: Mapped[float] = mapped_column(nullable=False)
    weekly_volume_km: Mapped[float] = mapped_column(nullable=False)
    fitness_level: Mapped[int] = mapped_column(nullable=False)
    recent_injury: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Recovery context — required when ``goal_type = 'recovery'``.
    # Closed-ontology enum from
    # docs/architecture/00-foundations/terminology.md → InjurySeverity.
    # The set {minor, moderate, major} is enforced by the SAEnum
    # column type; the application layer additionally guards
    # ``NUL`` for non-recovery goal types.
    # ------------------------------------------------------------------
    injury_severity: Mapped[InjurySeverity | None] = mapped_column(
        SAEnum(
            InjurySeverity,
            name="injury_severity",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Target performance — required when ``goal_type = 'target_performance'``.
    # ------------------------------------------------------------------
    target_distance_km: Mapped[float | None] = mapped_column(nullable=True)
    target_time_minutes: Mapped[int | None] = mapped_column(nullable=True)

    # ------------------------------------------------------------------
    # Status — the only mutable field set via direct PATCH.
    # ------------------------------------------------------------------
    status: Mapped[TrainingGoalStatus] = mapped_column(
        SAEnum(
            TrainingGoalStatus,
            name="training_goal_status",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # Volume fields must be non-negative.
        CheckConstraint(
            "weekly_volume_hours >= 0",
            name="ck_training_goals_weekly_volume_hours_non_negative",
        ),
        CheckConstraint(
            "weekly_volume_km >= 0",
            name="ck_training_goals_weekly_volume_km_non_negative",
        ),
        # ``fitness_level`` is a 1..5 integer per architecture contract.
        CheckConstraint(
            "fitness_level >= 1 AND fitness_level <= 5",
            name="ck_training_goals_fitness_level_1_to_5",
        ),
        # ``custom_distance_km`` is null or positive (positive when
        # goal_event_type = 'custom').
        CheckConstraint(
            "custom_distance_km IS NULL OR custom_distance_km > 0",
            name="ck_training_goals_custom_distance_positive",
        ),
        # ``target_distance_km`` and ``target_time_minutes`` are null
        # or positive when ``goal_type = 'target_performance'``.
        CheckConstraint(
            "target_distance_km IS NULL OR target_distance_km > 0",
            name="ck_training_goals_target_distance_positive",
        ),
        CheckConstraint(
            "target_time_minutes IS NULL OR target_time_minutes > 0",
            name="ck_training_goals_target_time_positive",
        ),
        # Partial unique index — one active goal per athlete.
        Index(
            "ix_training_goals_athlete_active",
            "athlete_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_training_goals_athlete_created", "athlete_id", "created_at"),
    )
