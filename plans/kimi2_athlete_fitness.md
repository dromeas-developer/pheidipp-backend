# Athlete Fitness Module — Implementation Plan

## Overview
Implement the `athlete_fitness` module for daily training load metrics. Follows the established patterns from `athlete_wellness`.

## Models

### 1. Add `AthleteFitness` model
- **Objective:** Define the daily training load ORM entity.
- **File:** `app/models/fitness.py` [CREATE]
- **Actions:**
  - Create `AthleteFitness` class inheriting from `Base`.
  - Table name: `athlete_fitness`.
  - Fields:
    - `id`: `UUID(as_uuid=True)`, `server_default=text("gen_random_uuid()")`, nullable=False.
    - `athlete_id`: `UUID`, FK `athletes.id` with `ondelete="CASCADE"`, nullable=False, indexed.
    - `metric_date`: `Date`, nullable=False.
    - `tss`: `Float`, nullable=True.
    - `atl`: `Float`, nullable=True.
    - `ctl`: `Float`, nullable=True.
    - `tsb`: `Float`, nullable=True.
    - `source`: `WellnessSource` enum via `mapped_column(SAEnum(..., native_enum=False, length=20))`, nullable=False.
    - `created_at`: `DateTime(timezone=True)`, `server_default=func.now()`.
    - `updated_at`: `DateTime(timezone=True)`, `server_default=func.now()`, `onupdate=func.now()`.
  - Relationship: `athlete: Mapped["Athlete"] = relationship(back_populates="fitness_metrics")`.
  - Table args: composite unique constraint `("athlete_id", "metric_date", name="uq_athlete_fitness_date")`.

### 2. Export `AthleteFitness` in models init
- **Objective:** Ensure the new model is importable.
- **File:** `app/models/__init__.py` [MODIFY]
- **Actions:**
  - Add import: `from app.models.fitness import AthleteFitness`.
  - Add `"AthleteFitness"` to the `__all__` list.

### 3. Add `fitness_metrics` relationship to `Athlete`
- **Objective:** Wire bidirectional relationship.
- **File:** `app/models/athlete.py` [MODIFY]
- **Actions:**
  - Under `wellness_metrics`, add:
    - `fitness_metrics: Mapped[list["AthleteFitness"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")`
  - Add `AthleteFitness` to the `if TYPE_CHECKING` import block if absent.

## Schemas

### 4. Add fitness Pydantic schemas
- **Objective:** Define request/response contracts.
- **File:** `app/schemas/fitness.py` [CREATE]
- **Actions:**
  - Add `FitnessBase(BaseModel)` with fields:
    - `metric_date: date`
    - `tss: Optional[float] = None`
    - `atl: Optional[float] = None`
    - `ctl: Optional[float] = None`
    - `tsb: Optional[float] = None`
    - `source: WellnessSource`
  - Add `FitnessCreate(FitnessBase)` with:
    - `athlete_id: uuid.UUID`
  - Add `FitnessUpdate(BaseModel)` with all base fields optional (including `metric_date` and `source`).
  - Add `FitnessResponse(FitnessBase)` with:
    - `id: uuid.UUID`
    - `athlete_id: uuid.UUID`
    - `created_at: datetime`
    - `updated_at: datetime`
    - `model_config = ConfigDict(from_attributes=True)`
  - Add `FitnessListParams(BaseModel)` with:
    - `date_from: Optional[date] = None`
    - `date_to: Optional[date] = None`
    - `limit: int = Field(default=50, ge=1, le=1000)`
    - `offset: int = Field(default=0, ge=0)`
  - Add `FitnessListResponse(BaseModel)` with:
    - `items: list[FitnessResponse]`
    - `total: int`

### 5. Export fitness schemas in schemas init
- **Objective:** Surface schemas at the package level.
- **File:** `app/schemas/__init__.py` [MODIFY]
- **Actions:**
  - Import all new classes from `app.schemas.fitness`.
  - Add them to `__all__`.

## Repositories

### 6. Add `FitnessRepository`
- **Objective:** Encapsulate all DB access for fitness records.
- **File:** `app/repositories/fitness_repository.py` [CREATE]
- **Actions:**
  - Create `FitnessRepository(BaseRepository[AthleteFitness])`.
  - Implement:
    - `__init__(self, session: AsyncSession)` calling `super().__init__(session, AthleteFitness)`.
    - `get_by_id(self, fitness_id: UUID) -> Optional[AthleteFitness]` using `super().get_by_id`.
    - `get_by_athlete_date(self, athlete_id: UUID, metric_date: date) -> Optional[AthleteFitness]`.
    - `get_by_athlete(self, athlete_id: UUID, skip: int = 0, limit: int = 50, date_from: Optional[date] = None, date_to: Optional[date] = None) -> List[AthleteFitness]`, ordered by `metric_date.desc()`.
    - `update_by_id(self, fitness_id: UUID, **kwargs) -> Optional[AthleteFitness]` via `super().update`.
    - `update_by_composite_key(self, athlete_id: UUID, metric_date: date, **kwargs) -> Optional[AthleteFitness]`.
    - `delete_by_id(self, fitness_id: UUID) -> bool`.
    - `delete_by_composite_key(self, athlete_id: UUID, metric_date: date) -> bool`.
    - `count_by_athlete(self, athlete_id: UUID) -> int`.

### 7. Export `FitnessRepository` in repositories init
- **Objective:** Package-level import.
- **File:** `app/repositories/__init__.py` [MODIFY]
- **Actions:**
  - Add import for `FitnessRepository`.
  - Add to `__all__`.

## Services

### 8. Add `FitnessService`
- **Objective:** Implement create/read/update/delete business logic and enforce uniqueness.
- **File:** `app/services/fitness_service.py` [CREATE]
- **Actions:**
  - Create `FitnessService` accepting `fitness_repo: FitnessRepository` and `athlete_repo: AthleteRepository`.
  - Implement `create_fitness(self, data: FitnessCreate) -> AthleteFitness`:
    - Verify athlete exists.
    - Verify no existing record for `(athlete_id, metric_date)`; raise `ValueError` if duplicate.
    - Call `fitness_repo.create(**data.model_dump())`.
  - Implement `get_fitness(self, fitness_id: UUID) -> AthleteFitness | None`.
  - Implement `list_athlete_fitness(self, athlete_id: UUID, params: FitnessListParams) -> list[AthleteFitness]`.
  - Implement `update_fitness(self, fitness_id: UUID, data: FitnessUpdate) -> AthleteFitness | None`:
    - If `metric_date` changed, verify uniqueness on new date; raise `ValueError` if collision.
    - Apply update via `fitness_repo.update_by_id`.
  - Implement `delete_fitness(self, fitness_id: UUID) -> bool`.

### 9. Export `FitnessService` in services init
- **Objective:** Package-level import.
- **File:** `app/services/__init__.py` [MODIFY]
- **Actions:**
  - Add import for `FitnessService`.
  - Add to `__all__`.

## API

### 10. Add fitness router
- **Objective:** Expose REST endpoints.
- **File:** `app/api/routes/fitness.py` [CREATE]
- **Actions:**
  - Create `router = APIRouter(prefix="/fitness", tags=["fitness"])`.
  - Endpoints:
    - `POST /` — `create_fitness`, returns `FitnessResponse`, 201. Catch `ValueError` → 400.
    - `GET /{fitness_id}` — `get_fitness`, returns `FitnessResponse`. 404 if missing.
    - `GET /athletes/{athlete_id}/fitness` — `list_athlete_fitness`, returns `FitnessListResponse`. Compute `total` via `repo.count_by_athlete`.
    - `PATCH /{fitness_id}` — `update_fitness`, returns `FitnessResponse`. Catch `ValueError` → 400. 404 if missing.
    - `DELETE /{fitness_id}` — `delete_fitness`, 204. 404 if missing.
  - Each handler instantiates `FitnessRepository`, `AthleteRepository`, `FitnessService`.

### 11. Wire fitness router into the app
- **Objective:** Register routes with FastAPI.
- **File:** `app/main.py` [MODIFY]
- **Actions:**
  - Import `router as fitness_router` from `app.api.routes.fitness`.
  - Add `app.include_router(fitness_router)`.

## Migration

### 12. Generate and apply Alembic migration for `athlete_fitness` hypertable
- **Objective:** Create the hypertable in the database.
- **File:** `migrations/versions/<generated>_add_athlete_fitness_hypertable.py` [CREATE via script]
- **Actions (inside migration `upgrade()`):**
  - `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")`
  - `op.execute("CREATE EXTENSION IF NOT EXISTS vector;")`
  - `op.create_table('athlete_fitness', ...)` with columns:
    - `id` — `sa.UUID(), nullable=False`
    - `athlete_id` — `sa.UUID(), nullable=False`
    - `metric_date` — `sa.Date(), nullable=False`
    - `tss` — `sa.Float(), nullable=True`
    - `atl` — `sa.Float(), nullable=True`
    - `ctl` — `sa.Float(), nullable=True`
    - `tsb` — `sa.Float(), nullable=True`
    - `source` — `sa.String(length=20), nullable=False`
    - `created_at` — `sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False`
    - `updated_at` — `sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False`
  - Constraints:
    - `sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE')`
    - `sa.PrimaryKeyConstraint('athlete_id', 'metric_date')`
    - `sa.UniqueConstraint('athlete_id', 'metric_date', name='uq_athlete_fitness_date')`
  - Index:
    - `op.create_index(op.f('ix_athlete_fitness_athlete_id'), 'athlete_fitness', ['athlete_id'], unique=False)`
  - `op.execute("SELECT create_hypertable('athlete_fitness', 'metric_date', if_not_exists => TRUE);")`
- **Actions (inside `downgrade()`):**
  - `op.execute("SELECT drop_hypertable('athlete_fitness', if_exists => TRUE, cascade => TRUE);")`
  - `op.drop_index(...)`
  - `op.drop_table('athlete_fitness')`
- **Process:**
  - Run `bash scripts/db-revision.sh "add_athlete_fitness_hypertable"`.
  - Verify the migration is not empty.
  - Run `bash scripts/db-upgrade.sh`.
  - Run `make context` to update dynamic context.
