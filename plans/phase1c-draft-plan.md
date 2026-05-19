# Phase 1c Implementation Plan: Simplified Twin Initialisation (Tier 3)

---

## Overview
**Objective**: Implement a simplified Digital Twin initialisation system (Tier 3) that computes fitness, fatigue, and threshold estimates from onboarding data using deterministic formulas. This phase replaces the Phase 1b onboarding endpoint stub with a real call to `TwinInitialisationService`, ensuring atomic twin creation within the same transaction as onboarding.

**Key Principles**:
- **Append-only**: `TwinState` records are never updated; each recalibration creates a new row.
- **Conservative Estimates**: All thresholds and HR estimates use population norms with low confidence (`LOW`).
- **Gender-Specific**: Max HR formulas account for biological differences (Gulati for female, Tanaka for male/other).
- **Crossover Athletes**: Cyclists/swimmers are flagged with lower structural capacity scores.
- **Atomicity**: Twin creation is part of the onboarding transaction (Phase 1b). If twin initialisation fails, the entire onboarding rolls back.
- **Terminology**: Uses `TrainingBlock` consistently (no `TrainingGoal` or `GoalCycle`).
- **Architecture**: Uses **Unit-of-Work pattern** for transaction management (no session leakage).

**Cold Start Tier**: Tier 3 (questionnaire-based, population-derived bootstrap). No real training data is available at this stage.

**Note on Existing Codebase Terminology**:
The current `TrainingBlock` model in `pheidipp-backend` contains fields prefixed with `goal_` (e.g., `goal_type`, `goal_event_type`). These are legacy naming artifacts and should be refactored in a future cleanup to use `block_*` prefixes for consistency. However, for Phase 1c, we use the canonical term `TrainingBlock` in all new code and documentation.

---

## Scope
### In Scope
- `UnitOfWork` abstraction for transaction management.
- `TwinState` model, schemas, repository, and service.
- `TwinInitialisationService` in `app/services/` (pure Python, no LLM).
- Atomic twin creation during onboarding via `UnitOfWork`.
- API endpoints:
  - `GET /athletes/{athlete_id}/twin` (current twin state).
  - `GET /athletes/{athlete_id}/twin/history` (all twin states for an athlete, **paginated**).
- Alembic migrations for `TwinState` and `AthleteProfile.gender`.
- Updates to **existing** services: `AthletePreferencesService`, `TrainingBlockService`, `AthleteService` (new UoW-compatible methods added).
- New service: `TwinInitialisationService` in `app/services/` (not `app/agents/`).

### Out of Scope
- LLM integration (Phase 1d+).
- Pace estimates (`lt1_pace_estimate`, `lt2_pace_estimate`) — deferred to Phase 2.
- Dynamic threshold updates from real data — deferred to Phase 2.
- Three-dimensional load model — deferred to Phase 4.
- Refactoring existing `goal_*` fields in `TrainingBlock` (track separately).

---

## Terminology Rules
| Term | Status | Replacement |
|------|--------|-------------|
| `TrainingGoal` | ❌ Deprecated | `TrainingBlock` |
| `GoalCycle` | ❌ Deprecated | Remove (Phase 2+) |
| `TrainingBlock` | ✅ Canonical | Keep |

---

## Architecture: Unit-of-Work Pattern

To avoid session leakage and centralize transaction management, we introduce a **Unit-of-Work (UoW)** abstraction with **explicit transaction control**.

### 1 — Create `app/core/unit_of_work.py` [CREATE]

```python
from sqlalchemy.ext.asyncio import AsyncSession

class UnitOfWork:
    """
    Centralizes transaction management and repository access.
    MUST be used with `async with UnitOfWork(session) as uow:`
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self._repos = {}

    async def __aenter__(self):
        # EXPLICIT TRANSACTION BEGIN (fixes autobegin ambiguity)
        await self.session.begin()
        
        from app.repositories import (
            AthleteRepository, AthletePreferencesRepository,
            TrainingBlockRepository, TwinStateRepository, AthleteProfileRepository
        )
        self._repos = {
            'athletes': AthleteRepository(self.session),
            'preferences': AthletePreferencesRepository(self.session),
            'blocks': TrainingBlockRepository(self.session),
            'twin_states': TwinStateRepository(self.session),
            'profiles': AthleteProfileRepository(self.session),
        }
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.rollback()
        else:
            await self.session.commit()

    def __getattr__(self, name):
        if not self._repos:
            raise RuntimeError(
                f"UnitOfWork repositories not initialised. "
                f"Use 'async with UnitOfWork(session) as uow:' "
                f"before accessing '{name}'.")
        if name in self._repos:
            return self._repos[name]
        raise AttributeError(
            f"No repository '{name}' in UnitOfWork. "
            f"Available: {list(self._repos.keys())}")
```

**Usage Rule**: Always use `async with UnitOfWork(session) as uow:` (never direct instantiation).

**Codebase alignment**: Existing services (`TrainingBlockService`, `AthletePreferencesService`, `AthleteService`) take a **repository**, not a session. `OnboardingService` takes **services** as dependencies. This pattern is preserved — no existing service constructors are modified.

---

## Models

---
### 2 — Create `app/models/twin_state.py` [CREATE]

Append-only. No UPDATE operations on this table.

```python
from sqlalchemy import Float, ForeignKey, DateTime, func, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Enum as SAEnum, text
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from app.models.base import Base
from app.models.enums import TwinTrigger, ConfidenceLevel, DataTier

if TYPE_CHECKING:
    from app.models.athlete import Athlete
    from app.models.athlete_preferences import AthletePreferences

class TwinState(Base):
    __tablename__ = "twin_states"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()")  # FIX: UUID, not timestamp
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_preferences_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athlete_preferences.id", ondelete="CASCADE"),  # FIX: CASCADE (not SET NULL)
        nullable=False,
    )
    trigger: Mapped[TwinTrigger] = mapped_column(
        SAEnum(TwinTrigger, native_enum=False, length=30),
        nullable=False,
    )
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        SAEnum(ConfidenceLevel, native_enum=False, length=10),
        nullable=False,
        default=ConfidenceLevel.LOW,
    )
    data_tier: Mapped[DataTier] = mapped_column(
        SAEnum(DataTier, native_enum=False, length=10),
        nullable=False,
    )
    fitness_score: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_hr_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    lt1_hr_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    lt2_hr_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    lt1_pace_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lt2_pace_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    structural_capacity_score: Mapped[float] = mapped_column(Float, nullable=False)
    fitness_time_constant: Mapped[float] = mapped_column(Float, nullable=False, default=42.0)
    fatigue_time_constant: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    computation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    computation_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="twin_states")
    preferences: Mapped["AthletePreferences"] = relationship(back_populates="twin_states")

    __table_args__ = (
        # FIX: Add DB-level constraints
        CheckConstraint("fitness_score >= 0 AND fitness_score <= 100", name="ck_fitness_score_range"),
        CheckConstraint("max_hr_estimate >= 140 AND max_hr_estimate <= 220", name="ck_max_hr_range"),
        CheckConstraint("fatigue_score >= 0", name="ck_fatigue_non_negative"),
        CheckConstraint("structural_capacity_score >= 0 AND structural_capacity_score <= 1", name="ck_structural_capacity_range"),
    )
```

---
### 3 — Update `app/models/athlete_profile.py` [MODIFY]

Add `gender` field:

```python
from app.models.enums import Gender

gender: Mapped[Optional[Gender]] = mapped_column(
    SAEnum(Gender, native_enum=False, length=20),
    nullable=True,
)
```

---
### 4 — Update `app/models/enums.py` [MODIFY]

```python
from enum import Enum as PyEnum

class Gender(str, PyEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

class TwinTrigger(str, PyEnum):
    QUESTIONNAIRE = "questionnaire"
    CALIBRATION = "calibration"
    WELLNESS_UPDATE = "wellness_update"

class ConfidenceLevel(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class DataTier(str, PyEnum):
    TIER_1 = "tier1"
    TIER_2 = "tier2"
    TIER_3 = "tier3"
    TIER_4 = "tier4"
    TIER_5 = "tier5"

class SportBackground(str, PyEnum):
    RUNNING_PRIMARY = "running_primary"
    MULTI_SPORT = "multi_sport"
    CYCLING_CROSSOVER = "cycling_crossover"
    SWIMMING_CROSSOVER = "swimming_crossover"
    OTHER = "other"

class PowerSource(str, PyEnum):
    NONE = "none"
    RUNNING_POWER = "running_power"

class HrSource(str, PyEnum):
    NONE = "none"
    CHEST_STRAP = "chest_strap"
    WRIST_OPTICAL = "wrist_optical"
```

---
### 5 — Update `app/models/__init__.py` [MODIFY]

Add exports:
```python
from app.models.twin_state import TwinState
from app.models.enums import (
    Gender, TwinTrigger, ConfidenceLevel, DataTier,
    SportBackground, PowerSource, HrSource
)
```

---

## Schemas

---
### 6 — Create `app/schemas/twin_state.py` [CREATE]

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from app.models.enums import TwinTrigger, ConfidenceLevel, DataTier

class TwinStateBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # FIX: Pydantic v2 ORM compatibility
    
    athlete_id: uuid.UUID
    athlete_preferences_id: uuid.UUID
    trigger: TwinTrigger
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    data_tier: DataTier
    fitness_score: float = Field(ge=0, le=100)
    fatigue_score: float = Field(ge=0, default=0.0)
    max_hr_estimate: float
    lt1_hr_estimate: float
    lt2_hr_estimate: float
    lt1_pace_estimate: Optional[float] = None
    lt2_pace_estimate: Optional[float] = None
    structural_capacity_score: float = Field(ge=0, le=1)
    fitness_time_constant: float = 42.0
    fatigue_time_constant: float = 7.0
    computation_summary: str
    computation_metadata: dict

class TwinStateCreate(TwinStateBase):
    pass

class TwinStateResponse(TwinStateBase):
    id: uuid.UUID
    created_at: datetime
```

---
### 7 — Update `app/schemas/athlete_profile.py` [MODIFY]

Add `gender` field:
```python
from app.models.enums import Gender
from pydantic import ConfigDict

class AthleteProfileBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gender: Optional[Gender] = None
```

---
### 8 — Update `app/schemas/__init__.py` [MODIFY]

Add exports:
```python
from app.schemas.twin_state import TwinStateBase, TwinStateCreate, TwinStateResponse
```

---

## Repositories

---
### 9 — Create `app/repositories/twin_state_repository.py` [CREATE]

```python
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.twin_state import TwinState
from app.schemas.twin_state import TwinStateCreate
from typing import Optional, tuple

class TwinStateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = TwinState

    async def create(self, data: TwinStateCreate) -> TwinState:
        db_obj = self.model(**data.model_dump())
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def get_by_athlete_id(self, athlete_id: uuid.UUID) -> Optional[TwinState]:
        stmt = select(self.model).where(self.model.athlete_id == athlete_id).order_by(desc(self.model.created_at)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history_by_athlete_id(self, athlete_id: uuid.UUID, limit: int = 100, offset: int = 0) -> tuple[list[TwinState], int]:
        # FIX: Return tuple[list, int] for pagination
        count_stmt = select(func.count()).select_from(self.model).where(self.model.athlete_id == athlete_id)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar()
        
        stmt = (
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(desc(self.model.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return (result.scalars().all(), total)

    async def count_by_athlete_id(self, athlete_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(self.model).where(self.model.athlete_id == athlete_id)
        result = await self.session.execute(stmt)
        return result.scalar()
```

---
### 10 — Create `app/repositories/athlete_profile_repository.py` [CREATE]

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.athlete_profile import AthleteProfile
from typing import Optional

class AthleteProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = AthleteProfile

    async def get_by_athlete_id(self, athlete_id: uuid.UUID) -> Optional[AthleteProfile]:
        stmt = select(self.model).where(self.model.athlete_id == athlete_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

---
### 11 — Update `app/repositories/__init__.py` [MODIFY]

Add exports:
```python
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
```

---

## Services

---
### 12 — Update `app/services/athlete_preferences_service.py` [MODIFY]

This service already exists with `create_for_athlete`. No changes to existing methods.
Add the following UoW-compatible wrapper so `OnboardingService` can call it within a
managed transaction without bypassing the existing business logic:

```python
# ADD to existing AthletePreferencesService class:

async def create_for_athlete_uow(
    self,
    athlete_id: uuid.UUID,
    data: AthletePreferencesCreate,
    uow: UnitOfWork,
) -> AthletePreferences:
    """
    UoW-compatible wrapper around create_for_athlete.
    Uses flush (not commit) so the UoW context manager owns the transaction.
    """
    payload = data.model_dump(exclude_unset=True)
    payload["athlete_id"] = athlete_id
    obj = AthletePreferences(**payload)
    uow.preferences.session.add(obj)
    await uow.preferences.session.flush()
    return obj
```

---
### 13 — Update `app/services/training_block_service.py` [MODIFY]

This service already exists with `create_for_athlete`, which enforces business rules
(no duplicate active blocks, 409 if one exists). No changes to existing methods.
Add the following UoW-compatible wrapper:

```python
# ADD to existing TrainingBlockService class:

async def create_for_athlete_uow(
    self,
    athlete_id: uuid.UUID,
    data: TrainingBlockCreate,
    uow: UnitOfWork,
) -> TrainingBlock:
    """
    UoW-compatible wrapper around create_for_athlete.
    Enforces existing business rule: raises 409 if an active block already exists.
    Uses flush (not commit) so the UoW context manager owns the transaction.
    """
    existing = await uow.blocks.get_active_by_athlete(athlete_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Active training block already exists"
        )
    payload = data.model_dump(exclude_unset=True)
    payload["athlete_id"] = athlete_id
    payload["status"] = TrainingBlockStatus.ACTIVE
    obj = TrainingBlock(**payload)
    uow.blocks.session.add(obj)
    await uow.blocks.session.flush()
    return obj
```

---
### 14 — Update `app/services/athlete_service.py` [MODIFY]

This service already exists. Add the following two methods only — do not replace
any existing methods:

```python
# ADD to existing AthleteService class:

async def set_onboarding_complete(
    self, athlete_id: uuid.UUID, value: bool, uow: UnitOfWork
) -> None:
    """
    Sets onboarding_complete flag via repository update.
    Uses flush (not commit) so the UoW context manager owns the transaction.
    """
    await uow.athletes.update(athlete_id, onboarding_complete=value)

async def get_profile(
    self, athlete_id: uuid.UUID, uow: UnitOfWork
) -> Optional[AthleteProfile]:
    """Returns the AthleteProfile for this athlete, or None."""
    return await uow.profiles.get_by_athlete_id(athlete_id)
```

Also add to `app/repositories/athlete_repository.py` [MODIFY] — this repository
already exists. Add `get_with_profile` for eager loading:

```python
# ADD to existing AthleteRepository class:

async def get_with_profile(self, athlete_id: uuid.UUID) -> Optional[Athlete]:
    from sqlalchemy.orm import selectinload
    result = await self.session.execute(
        select(Athlete)
        .options(selectinload(Athlete.profile))
        .where(Athlete.id == athlete_id)
    )
    return result.scalar_one_or_none()
```

---
### 15 — Create `app/services/twin_state_service.py` [CREATE]

```python
from typing import Optional, tuple
from app.models.twin_state import TwinState
from app.schemas.twin_state import TwinStateResponse
from app.core.unit_of_work import UnitOfWork

class TwinStateService:
    async def get_current_twin_state(self, athlete_id: uuid.UUID, uow: UnitOfWork) -> Optional[TwinStateResponse]:
        twin_state = await uow.twin_states.get_by_athlete_id(athlete_id)
        return TwinStateResponse.model_validate(twin_state) if twin_state else None

    async def get_twin_state_history(
        self, athlete_id: uuid.UUID, uow: UnitOfWork, limit: int = 100, offset: int = 0
    ) -> tuple[list[TwinStateResponse], int]:
        # FIX: Return tuple[list, int] for pagination
        twin_states, total = await uow.twin_states.get_history_by_athlete_id(athlete_id, limit, offset)
        return ([TwinStateResponse.model_validate(ts) for ts in twin_states], total)
```

---

## Agent Service

---
### 16 — Create `app/services/twin_initialisation_service.py` [CREATE]

> **Location change from earlier drafts:** `TwinInitialisationService` is pure
> Python computation with no LLM calls. `app/agents/` is reserved for LLM-related
> logic per `stack-truth.md`. This service belongs in `app/services/`.

```python
import uuid
from datetime import date
from typing import Optional, tuple
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.training_block import TrainingBlock
from app.models.twin_state import TwinState
from app.models.enums import SportBackground, DataTier, ConfidenceLevel, TwinTrigger, Gender, PowerSource, HrSource
from app.core.unit_of_work import UnitOfWork

class TwinInitialisationService:
    async def initialise(
        self,
        athlete_id: uuid.UUID,
        preferences: AthletePreferences,
        training_block: TrainingBlock,
        profile: AthleteProfile,
        uow: UnitOfWork,
    ) -> TwinState:
        if not profile.date_of_birth:
            raise ValueError(f"AthleteProfile.date_of_birth missing for athlete {athlete_id}")

        age = self._compute_age(profile.date_of_birth)
        gender = profile.gender.value if profile.gender else None
        data_tier = self._infer_data_tier(preferences)

        fitness_score = self._calculate_fitness_score(
            weekly_volume_hours=training_block.weekly_volume_hours,
            years_structured_training=preferences.years_structured_training,
            sport_background=preferences.sport_background,
        )

        max_hr = self._max_hr(age, gender)
        lt1_hr, lt2_hr = self._calculate_thresholds(max_hr, fitness_score)
        structural_capacity_score = self._structural_capacity_score(preferences.sport_background)

        summary = self._build_summary(age, fitness_score, data_tier, structural_capacity_score, gender)
        metadata = self._build_metadata(age, fitness_score, data_tier, structural_capacity_score, gender)

        twin = TwinState(
            athlete_id=athlete_id,
            athlete_preferences_id=preferences.id,
            trigger=TwinTrigger.QUESTIONNAIRE,
            confidence_level=ConfidenceLevel.LOW,
            data_tier=data_tier,
            fitness_score=round(fitness_score, 2),
            fatigue_score=0.0,
            max_hr_estimate=round(max_hr, 1),
            lt1_hr_estimate=lt1_hr,
            lt2_hr_estimate=lt2_hr,
            lt1_pace_estimate=None,
            lt2_pace_estimate=None,
            structural_capacity_score=structural_capacity_score,
            fitness_time_constant=42.0,
            fatigue_time_constant=7.0,
            computation_summary=summary,
            computation_metadata=metadata,
        )
        uow.twin_states.session.add(twin)
        await uow.twin_states.session.flush()
        return twin

    @staticmethod
    def _compute_age(date_of_birth: date) -> int:
        today = date.today()
        return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))

    @staticmethod
    def _max_hr(age: int, gender: Optional[str]) -> float:
        return 206.0 - (0.88 * age) if gender == "female" else 208.0 - (0.7 * age)

    @staticmethod
    def _calculate_fitness_score(weekly_volume_hours: float, years_structured_training: int, 
                                  sport_background: SportBackground) -> float:
        base_score = (weekly_volume_hours * 2) + (years_structured_training * 5)
        if sport_background in [SportBackground.CYCLING_CROSSOVER, SportBackground.SWIMMING_CROSSOVER]:
            base_score *= 0.8
        return min(max(base_score, 0), 100)

    @staticmethod
    def _calculate_thresholds(max_hr: float, fitness_score: float) -> tuple[float, float]:
        thresholds = {0: (0.65, 0.80), 21: (0.70, 0.83), 51: (0.73, 0.85), 81: (0.76, 0.88)}
        for score, (lt1, lt2) in sorted(thresholds.items(), reverse=True):
            if fitness_score >= score:
                return (round(max_hr * lt1, 1), round(max_hr * lt2, 1))
        return (round(max_hr * 0.65, 1), round(max_hr * 0.80, 1))

    @staticmethod
    def _infer_data_tier(preferences: AthletePreferences) -> DataTier:
        has_running_power = preferences.power_source == PowerSource.RUNNING_POWER
        has_chest_strap = preferences.hr_source == HrSource.CHEST_STRAP
        has_optical_hr = preferences.hr_source == HrSource.WRIST_OPTICAL
        if has_running_power:
            return DataTier.TIER_1 if has_chest_strap else DataTier.TIER_2
        return DataTier.TIER_3 if has_chest_strap else DataTier.TIER_4 if has_optical_hr else DataTier.TIER_5

    @staticmethod
    def _structural_capacity_score(sport_background: SportBackground) -> float:
        return {
            SportBackground.RUNNING_PRIMARY: 0.7, SportBackground.MULTI_SPORT: 0.5,
            SportBackground.CYCLING_CROSSOVER: 0.2, SportBackground.SWIMMING_CROSSOVER: 0.2,
            SportBackground.OTHER: 0.5
        }.get(sport_background, 0.5)

    @staticmethod
    def _build_summary(age: int, fitness_score: float, data_tier: DataTier, 
                      structural_capacity_score: float, gender: Optional[str]) -> str:
        gender_str = gender or "not specified"
        formula = "Gulati" if gender == "female" else "Tanaka"
        return (f"Tier 3 twin initialisation for {age}-year-old {gender_str} athlete. "
                f"Fitness score: {fitness_score:.1f}/100, Data tier: {data_tier.value}, "
                f"Structural capacity: {structural_capacity_score:.1f}. Max HR formula: {formula}.")

    @staticmethod
    def _build_metadata(age: int, fitness_score: float, data_tier: DataTier, 
                       structural_capacity_score: float, gender: Optional[str]) -> dict:
        return {
            "age": age, "fitness_score": round(fitness_score, 2), "data_tier": data_tier.value,
            "structural_capacity_score": structural_capacity_score, "gender": gender,
            "max_hr_formula": "Gulati" if gender == "female" else "Tanaka"
        }
```

---

## API Routes

---
### 17 — Create `app/api/routes/twin_state.py` [CREATE]

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated, list
from app.services.twin_state_service import TwinStateService
from app.schemas.twin_state import TwinStateResponse
from app.core.unit_of_work import UnitOfWork
from app.core.db import async_session_maker

router = APIRouter(prefix="/athletes/{athlete_id}/twin", tags=["twin"])

@router.get("/", response_model=TwinStateResponse)
async def get_current_twin_state(
    athlete_id: uuid.UUID,
    service: TwinStateService = Depends(),
) -> TwinStateResponse:
    async with async_session_maker() as session:
        async with UnitOfWork(session) as uow:  # FIX: Use context manager
            twin_state = await service.get_current_twin_state(athlete_id, uow)
            if not twin_state:
                raise HTTPException(status_code=404, detail="TwinState not found")
            return twin_state

@router.get("/history", response_model=tuple[list[TwinStateResponse], int])
async def get_twin_state_history(
    athlete_id: uuid.UUID,
    service: TwinStateService = Depends(),
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[list[TwinStateResponse], int]:
    async with async_session_maker() as session:
        async with UnitOfWork(session) as uow:  # FIX: Use context manager
            return await service.get_twin_state_history(athlete_id, uow, limit, offset)
```

---
### 18 — Update `app/api/routes/__init__.py` [MODIFY]

Add the twin state router:
```python
from app.api.routes.twin_state import router as twin_state_router
api_router.include_router(twin_state_router)
```

---

## Wiring to Onboarding

---
### 19 — Update `app/services/onboarding_service.py` [MODIFY]

`OnboardingService` already exists from Phase 1b. Update it to:
- Accept services as constructor dependencies (not session — aligns with existing pattern)
- Call UoW-compatible wrappers on existing services
- Wire in twin initialisation and return a typed result

```python
from app.services.athlete_preferences_service import AthletePreferencesService
from app.services.training_block_service import TrainingBlockService
from app.services.twin_initialisation_service import TwinInitialisationService
from app.services.athlete_service import AthleteService
from app.core.unit_of_work import UnitOfWork
from app.schemas.onboarding import OnboardingRequest


class OnboardingService:
    """
    Takes services as constructor dependencies, not a session.
    Aligns with the existing pattern used by TrainingBlockService,
    AthletePreferencesService, and AthleteService.
    Transaction lifecycle is owned by the caller via UnitOfWork.
    """
    def __init__(
        self,
        athlete_service: AthleteService,
        athlete_preferences_service: AthletePreferencesService,
        training_block_service: TrainingBlockService,
        twin_initialisation_service: TwinInitialisationService,
    ):
        self.athlete_service = athlete_service
        self.athlete_preferences_service = athlete_preferences_service
        self.training_block_service = training_block_service
        self.twin_initialisation_service = twin_initialisation_service

    async def complete_onboarding(
        self,
        athlete_id: uuid.UUID,
        payload: OnboardingRequest,
        uow: UnitOfWork,
    ) -> tuple:
        """
        Orchestrates all onboarding writes within the caller's UoW transaction.
        Calls UoW-compatible wrappers (flush, not commit) on existing services.
        Returns (preferences, training_block, twin_state) for the route to
        construct a typed OnboardingResponse.
        """
        # Use UoW-compatible wrappers on existing services
        preferences = await self.athlete_preferences_service.create_for_athlete_uow(
            athlete_id, payload.preferences, uow
        )
        # Enforces existing 409 business rule via UoW-compatible wrapper
        training_block = await self.training_block_service.create_for_athlete_uow(
            athlete_id, payload.training_block, uow
        )
        profile = await self.athlete_service.get_profile(athlete_id, uow)
        if not profile or not profile.date_of_birth:
            raise ValueError(
                f"AthleteProfile.date_of_birth missing for athlete {athlete_id}. "
                "Cannot initialise twin without age."
            )

        twin_state = await self.twin_initialisation_service.initialise(
            athlete_id=athlete_id,
            preferences=preferences,
            training_block=training_block,
            profile=profile,
            uow=uow,
        )

        # Set flag LAST — only after all writes succeed.
        # If twin init fails, this never runs and onboarding_complete stays false.
        await self.athlete_service.set_onboarding_complete(athlete_id, True, uow)
        return preferences, training_block, twin_state
```

---
### 20 — Update `app/api/routes/onboarding.py` [MODIFY]

```python
from fastapi import APIRouter, Depends
from app.services.onboarding_service import OnboardingService
from app.core.unit_of_work import UnitOfWork
from app.core.db import async_session_maker

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["onboarding"])

@router.post("/onboarding", response_model=OnboardingResponse, status_code=201)
async def complete_onboarding(
    athlete_id: uuid.UUID,
    payload: OnboardingRequest,
    onboarding_service: OnboardingService = Depends(),
):
    async with async_session_maker() as session:
        async with UnitOfWork(session) as uow:
            preferences, training_block, twin_state = (
                await onboarding_service.complete_onboarding(
                    athlete_id,
                    {"preferences": payload.preferences, "training_block": payload.training_block},
                    uow,
                )
            )
    return OnboardingResponse(
        onboarding_complete=True,
        preferences=AthletePreferencesResponse.model_validate(preferences),
        training_block=TrainingBlockResponse.model_validate(training_block),
        twin_state=TwinStateResponse.model_validate(twin_state),
    )
```

---

## Migration

---
### 21 — Create Alembic Migration [CREATE]

File: `alembic/versions/<timestamp>_create_twin_state_and_add_gender.py`

```python
from alembic import op
import sqlalchemy as sa
from app.models.enums import Gender, DataTier, ConfidenceLevel, TwinTrigger

def upgrade():
    # Add gender to AthleteProfile
    op.add_column(
        "athlete_profiles",
        sa.Column("gender", sa.Enum(Gender), nullable=True)
    )

    # Create TwinState table with constraints
    op.create_table(
        "twin_states",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),  # FIX
        sa.Column("athlete_id", sa.Uuid(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("athlete_preferences_id", sa.Uuid(), sa.ForeignKey("athlete_preferences.id", ondelete="CASCADE"), nullable=False),  # FIX
        sa.Column("trigger", sa.Enum(TwinTrigger), nullable=False),
        sa.Column("confidence_level", sa.Enum(ConfidenceLevel), nullable=False, server_default=ConfidenceLevel.LOW.value),
        sa.Column("data_tier", sa.Enum(DataTier), nullable=False),
        sa.Column("fitness_score", sa.Float(), nullable=False),
        sa.Column("fatigue_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_hr_estimate", sa.Float(), nullable=False),
        sa.Column("lt1_hr_estimate", sa.Float(), nullable=False),
        sa.Column("lt2_hr_estimate", sa.Float(), nullable=False),
        sa.Column("lt1_pace_estimate", sa.Float(), nullable=True),
        sa.Column("lt2_pace_estimate", sa.Float(), nullable=True),
        sa.Column("structural_capacity_score", sa.Float(), nullable=False),
        sa.Column("fitness_time_constant", sa.Float(), nullable=False, server_default="42.0"),
        sa.Column("fatigue_time_constant", sa.Float(), nullable=False, server_default="7.0"),
        sa.Column("computation_summary", sa.Text(), nullable=False),
        sa.Column("computation_metadata", sa.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # FIX: Add DB constraints
        sa.CheckConstraint("fitness_score >= 0 AND fitness_score <= 100", name="ck_twin_states_fitness_score_range"),
        sa.CheckConstraint("max_hr_estimate >= 140 AND max_hr_estimate <= 220", name="ck_twin_states_max_hr_range"),
        sa.CheckConstraint("fatigue_score >= 0", name="ck_twin_states_fatigue_non_negative"),
        sa.CheckConstraint("structural_capacity_score >= 0 AND structural_capacity_score <= 1", name="ck_twin_states_structural_capacity_range"),
    )
    op.create_index(op.f("ix_twin_states_athlete_id"), "twin_states", ["athlete_id"])

def downgrade():
    op.drop_table("twin_states")
    op.drop_column("athlete_profiles", "gender")
```

---

## Computation Design

### Fitness Score
Numeric score (0-100):
```
fitness_score = (weekly_volume_hours * 2) + (years_structured_training * 5)
```
- Crossover adjustment: ×0.8 for cycling/swimming backgrounds
- Clamped to 0-100

### Max HR Estimate
- Female: `206 - (0.88 * age)` (Gulati et al. 2010)
- Male/Other: `208 - (0.7 * age)` (Tanaka et al. 2001)

### Threshold Estimates
| Fitness Score Range | LT1 % | LT2 % |
|---------------------|-------|-------|
| 0-20 (Beginner)      | 0.65  | 0.80  |
| 21-50 (Intermediate) | 0.70  | 0.83  |
| 51-80 (Advanced)     | 0.73  | 0.85  |
| 81-100 (Elite)       | 0.76  | 0.88  |

LT2 ceiling capped at 88%. At Tier 3, overestimating threshold is more dangerous
than underestimating — pushed workouts, injury risk, early loss of trust.

### Data Tier
- **TIER1**: Running power + chest strap HR
- **TIER2**: Running power + optical HR
- **TIER3**: Chest strap HR only
- **TIER4**: Optical HR only
- **TIER5**: No HR

### Structural Capacity
- Running primary: **0.7**
- Multi-sport: **0.5**
- Cycling/swimming crossover: **0.2**
- Other: **0.5**

---

## Validation Rules

### Model-Level Constraints
- `fitness_score`: **0–100** (enforced by DB `CheckConstraint`)
- `fatigue_score`: **≥ 0** (enforced by DB `CheckConstraint`)
- `max_hr_estimate`: **140–220 bpm** (enforced by DB `CheckConstraint`)
- `lt1_hr_estimate`/`lt2_hr_estimate`: **≤ `max_hr_estimate`**
- `structural_capacity_score`: **0.0–1.0** (enforced by DB `CheckConstraint`)

### Service-Level Rules
- Missing `AthleteProfile.date_of_birth`: **Raises `ValueError`**
- Missing `AthleteProfile.gender`: **Defaults to Tanaka formula**
- Invalid `sport_background`: **Defaults to `OTHER`**

---

## Testing

### Unit Tests
1. **`TwinInitialisationService`**:
   - `_compute_age` with edge cases (e.g., birthday today)
   - `_max_hr` for all genders/ages
   - `_calculate_fitness_score` with min/max inputs, clamping, crossover adjustments
   - `_calculate_thresholds` for all `fitness_score` ranges
   - `_infer_data_tier` for all sensor combinations

2. **`TwinStateRepository`**:
   - `create` and `get_by_athlete_id`
   - `get_history_by_athlete_id` returns `(items, total_count)`

3. **`TwinStateService`**:
   - `get_current_twin_state` returns `None` for non-existent athlete
   - `get_twin_state_history` returns `(items, total_count)`

4. **New Services**:
   - `AthletePreferencesService.create()`
   - `TrainingBlockService.create()`
   - `AthleteService.set_onboarding_complete()` and `get_profile()`

5. **Unit-of-Work**:
   - Transaction rollback on failure
   - Commit on success
   - Repository access via `async with`

### Integration Tests
1. **Onboarding Transaction**:
   - `TwinState` created atomically with `AthletePreferences` and `TrainingBlock`
   - Rollback if `TwinState` creation fails

2. **API Endpoints**:
   - `GET /twin` returns 404 pre-onboarding
   - `GET /twin/history` returns `(items, total_count)` with pagination

### Edge Cases
| Scenario | Expected Behavior |
|----------|-------------------|
| `gender = None` | Uses Tanaka formula (unisex) |
| `date_of_birth = None` | Raises `ValueError` |
| `fitness_score < 0` | Clamped to 0 |
| `fitness_score > 100` | Clamped to 100 |
| `max_hr_estimate > 220` | Clamped to 220 |

---

## Dependencies

### Internal Dependencies
| Component | Depends On |
|-----------|------------|
| `UnitOfWork` | `AsyncSession`, all repositories |
| `TwinState` | `Athlete`, `AthletePreferences` |
| `TwinStateRepository` | `TwinState`, `AsyncSession` |
| `TwinInitialisationService` | `UnitOfWork`, `AthletePreferences`, `TrainingBlock`, `AthleteProfile` |
| `TwinStateService` | `UnitOfWork` |
| `OnboardingService` | `AthletePreferencesService`, `TrainingBlockService`, `AthleteService`, `TwinInitialisationService` |
| API routes | `TwinStateService`, `OnboardingService` |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| `UnitOfWork` not used with `async with` | **Code review**: Enforce context manager usage |
| Transaction lifecycle ambiguity | **Explicit**: `await session.begin()` in `__aenter__` |
| Service/UoW lifecycle coupling | **Document**: Add usage examples |
| Route-level ceremony | **Deferred**: Add `get_uow` DI factory to `app/api/dependencies/` as part of the pre-Phase 2 dependency extraction. Current explicit session pattern is acceptable for Phase 1c. |
| `TwinState.id` with `func.now()` | **Fixed**: Uses `gen_random_uuid()` |
| `SET NULL` + `nullable=False` | **Fixed**: Uses `CASCADE` |
| Missing DB constraints | **Fixed**: Added `CheckConstraint` |
| Missing `from_attributes=True` | **Fixed**: Added to all Pydantic models |

---

## Done Criteria

### Functional
- [ ] `POST /onboarding` returns populated `twin_state`
- [ ] `TwinState` created atomically with `AthletePreferences` and `TrainingBlock`
- [ ] `onboarding_complete` is set **after** `TwinState` is written — if twin init fails, flag stays false and athlete can retry cleanly
- [ ] `GET /twin` returns current state after onboarding
- [ ] `GET /twin/history` returns `(items, total_count)` with pagination
- [ ] For 30-year-old male, `fitness_score=52` (Advanced band: 51–80):
  - `max_hr_estimate` ≈ 187 (208 − 0.7×30)
  - `lt1_hr_estimate` ≈ 137 (187 × 0.73)
  - `lt2_hr_estimate` ≈ 159 (187 × 0.85)
- [ ] For 30-year-old female, `fitness_score=52` (Advanced band: 51–80):
  - `max_hr_estimate` ≈ 179 (206 − 0.88×30)
  - `lt1_hr_estimate` ≈ 131 (179 × 0.73)
  - `lt2_hr_estimate` ≈ 152 (179 × 0.85)
- [ ] Crossover athletes have `structural_capacity_score=0.2`
- [ ] `computation_metadata` contains all required fields
- [ ] No direct repository access in services
- [ ] All `UnitOfWork` usage via `async with`

### Non-Functional
- [ ] Migration applies and rolls back cleanly
- [ ] No regressions on existing endpoints
- [ ] All DB access uses `AsyncSession`
- [ ] No business logic in API routes
- [ ] Pagination on `/twin/history` returns `tuple[list, int]`

---

## Appendices

### A. Example Calculations

#### Male Athlete, 30 Years Old, `fitness_score=52` (Advanced band: 51–80)
- **Max HR**: `208 − (0.7 × 30) = 187`
- **LT1**: `187 × 0.73 = 137`
- **LT2**: `187 × 0.85 = 159`
- **Data Tier**: `TIER3` (if `hr_source=chest_strap`)
- **Structural Capacity**: `0.7` (if `sport_background=running_primary`)

#### Female Athlete, 30 Years Old, `fitness_score=25` (Beginner band: 0–20)
- **Max HR**: `206 − (0.88 × 30) = 179`
- **LT1**: `179 × 0.65 = 116`
- **LT2**: `179 × 0.80 = 143`
- **Data Tier**: `TIER4` (if `hr_source=wrist_optical`)
- **Structural Capacity**: `0.2` (if `sport_background=cycling_crossover`)

---
### B. Architecture Diagram

```
Route Handler
     │
     ▼
async with async_session_maker() as session:
     │
     ▼
async with UnitOfWork(session) as uow:  # Transaction + Repos
     │
     ├───▶ ap_service.create_for_athlete_uow()   # existing service + UoW wrapper
     │
     ├───▶ tb_service.create_for_athlete_uow()   # existing service + UoW wrapper
     │
     ├───▶ twin_service.initialise()              # new service in app/services/
     │
     └───▶ athlete_service.set_onboarding_complete()  # LAST: only after all writes
            │
            ▼
     Transaction Commit/Rollback
     # onboarding_complete=True only persists if every prior step succeeded
```

---
### C. Terminology Audit
- [x] No `TrainingGoal` in new code
- [x] No `GoalCycle` in new code
- [x] `TrainingBlock` used consistently
- [ ] Legacy `goal_*` fields in `TrainingBlock` (track for Phase 2)

---
### D. Glossary

| Term | Definition |
|------|------------|
| **Tier 3** | Cold-start twin initialisation using questionnaire data and population norms |
| **Fitness Score** | Numeric estimate of aerobic fitness (0–100) from volume + experience |
| **Structural Capacity** | Measure of injury risk based on sport background (0.0–1.0) |
| **Data Tier** | Classification of data quality based on available sensors (1–5) |
| **Append-Only** | `TwinState` records are never updated; new rows added for recalibrations |
| **Atomic Transaction** | All onboarding steps succeed or fail together |
| **Unit-of-Work** | Centralizes transaction management and repository access |