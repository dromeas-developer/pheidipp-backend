# Athlete Fitness Module — Implementation Plan

## Models

### 1. Create AthleteFitness ORM model
- **Objective**: Define the `AthleteFitness` table with daily training-load metrics.
- **File**: `app/models/fitness.py` [CREATE]
- **Actions**:
  - Define `AthleteFitness` class inheriting from `Base`.
  - Table name: `athlete_fitness`.
  - Columns:
    - `id`: `UUID` primary key, server default `gen_random_uuid()`.
    - `athlete_id`: `UUID`, foreign key to `athletes.id` with `ondelete="CASCADE"`, `nullable=False`, `index=True`.
    - `metric_date`: `Date`, `nullable=False`.
    - `tss`: `Float`, `nullable=True`.
    - `atl`: `Float`, `nullable=True`.
    - `ctl`: `Float`, `nullable=True`.
    - `tsb`: `Float`, `nullable=True`.
    - `source`: `WellnessSource` enum, `nullable=False`.
    - `created_at`: `DateTime(timezone=True)`, server default `func.now()`.
    - `updated_at`: `DateTime(timezone=True)`, server default `func.now()`, `onupdate=func.now()`.
  - Add relationship `athlete` mapped to `Athlete` with `back_populates="fitness_metrics"`.
  - Add `__table_args__` with `UniqueConstraint("athlete_id", "metric_date", name="uq_athlete_fitness_date")`.

### 2. Add fitness relationship to Athlete
- **Objective**: Wire the reverse relationship from `Athlete` to `AthleteFitness`.
- **File**: `app/models/athlete.py` [MODIFY]
- **Actions**:
  - In `Athlete` class, add `fitness_metrics: Mapped[list["AthleteFitness"]]` relationship with `back_populates="athlete"` and `cascade="all, delete-orphan"`.
  - Add `AthleteFitness` to the `TYPE_CHECKING` import block.

### 3. Export AthleteFitness from models package
- **Objective**: Expose the new model through the models `__init__`.
- **File**: `app/models/__init__.py` [MODIFY]
- **Actions**:
  - Add import `from app.models.fitness import AthleteFitness`.
  - Add `"AthleteFitness"` to `__all__`.

## Schemas

### 4. Create fitness Pydantic schemas
- **Objective**: Define request/response contracts for fitness records.
- **File**: `app/schemas/fitness.py` [CREATE]
- **Actions**:
  - `FitnessBase(BaseModel)` with fields: `metric_date: date`, `tss: Optional[float] = None`, `atl: Optional[float] = None`, `ctl: Optional[float] = None`, `tsb: Optional[float] = None`, `source: WellnessSource`.
  - `FitnessCreate(FitnessBase)` with additional field `athlete_id: UUID`.
  - `FitnessUpdate(BaseModel)` with all fields optional (same names as `FitnessBase`, all `Optional`).
  - `FitnessResponse(FitnessBase)` with additional fields: `id: UUID`, `athlete_id: UUID`, `created_at: datetime`, `updated_at: datetime`, and `model_config = ConfigDict(from_attributes=True)`.
  - `FitnessListParams(BaseModel)` with `date_from: Optional[date] = None`, `date_to: Optional[date] = None`, `limit: int = Field(default=50, ge=1, le=1000)`, `offset: int = Field(default=0, ge=0)`.
  - `FitnessListResponse(BaseModel)` with `items: list[FitnessResponse]` and `total: int`.

### 5. Export fitness schemas from schemas package
- **Objective**: Expose fitness schemas through the schemas `__init__`.
- **File**: `app/schemas/__init__.py` [MODIFY]
- **Actions**:
  - Add imports for all fitness schema classes from `app.schemas.fitness`.
  - Add all fitness schema names to `__all__`.

## Repositories

### 6. Create FitnessRepository
- **Objective**: Implement DB access for `AthleteFitness` following the wellness repository pattern.
- **File**: `app/repositories/fitness_repository.py` [CREATE]
- **Actions**:
  - Define `FitnessRepository(BaseRepository[AthleteFitness])` with `__init__` accepting `AsyncSession`.
  - Implement `get_by_id(self, fitness_id: UUID) -> Optional[AthleteFitness]`.
  - Implement `get_by_athlete_date(self, athlete_id: UUID, metric_date: date) -> Optional[AthleteFitness]`.
  - Implement `get_by_athlete(self, athlete_id: UUID, skip: int = 0, limit: int = 50, date_from: Optional[date] = None, date_to: Optional[date] = None) -> List[AthleteFitness]`, ordered by `metric_date.desc()`.
  - Implement `update_by_id(self, fitness_id: UUID, **kwargs) -> Optional[AthleteFitness]`.
  - Implement `delete_by_id(self, fitness_id: UUID) -> bool`.
  - Implement `count_by_athlete(self, athlete_id: UUID) -> int`.

### 7. Export FitnessRepository from repositories package
- **Objective**: Expose the new repository through the repositories `__init__`.
- **File**: `app/repositories/__init__.py` [MODIFY]
- **Actions**:
  - Add import `from app.repositories.fitness_repository import FitnessRepository`.
  - Add `"FitnessRepository"` to `__all__`.

## Services

### 8. Create FitnessService
- **Objective**: Implement business logic for fitness records.
- **File**: `app/services/fitness_service.py` [CREATE]
- **Actions**:
  - Define `FitnessService` with `__init__` accepting `FitnessRepository` and `AthleteRepository`.
  - `create_fitness(data: FitnessCreate) -> AthleteFitness`:
    - Verify athlete exists via `athlete_repo.get_by_id`.
    - Verify no existing record for `(athlete_id, metric_date)` via `fitness_repo.get_by_athlete_date`.
    - Raise `ValueError` on duplicate or missing athlete.
    - Create record via `fitness_repo.create`.
  - `get_fitness(fitness_id: UUID) -> AthleteFitness | None`.
  - `list_athlete_fitness(athlete_id: UUID, params: FitnessListParams) -> list[AthleteFitness]`.
  - `update_fitness(fitness_id: UUID, data: FitnessUpdate) -> AthleteFitness | None`:
    - If `metric_date` is updated, verify no conflict with another record for the same athlete and new date.
    - Raise `ValueError` on conflict.
  - `delete_fitness(fitness_id: UUID) -> bool`.

### 9. Export FitnessService from services package
- **Objective**: Expose the new service through the services `__init__`.
- **File**: `app/services/__init__.py` [MODIFY]
- **Actions**:
  - Add import `from app.services.fitness_service import FitnessService`.
  - Add `"FitnessService"` to `__all__`.

## API

### 10. Create fitness API routes
- **Objective**: Expose REST endpoints for fitness CRUD.
- **File**: `app/api/routes/fitness.py` [CREATE]
- **Actions**:
  - Create `APIRouter(prefix="/fitness", tags=["fitness"])`.
  - `POST /` — `create_fitness`, accepts `FitnessCreate`, returns `FitnessResponse` with `201`. Catch `ValueError` → `400`.
  - `GET /{fitness_id}` — `get_fitness`, returns `FitnessResponse` or `404`.
  - `GET /athletes/{athlete_id}/fitness` — `list_athlete_fitness`, accepts `FitnessListParams` via `Depends()`, returns `FitnessListResponse`. Compute `total` via `fitness_repo.count_by_athlete`.
  - `PATCH /{fitness_id}` — `update_fitness`, accepts `FitnessUpdate`, returns `FitnessResponse`. Catch `ValueError` → `400`; missing record → `404`.
  - `DELETE /{fitness_id}` — `delete_fitness`, returns `204` or `404`.
  - In each endpoint, instantiate `FitnessRepository(db)`, `AthleteRepository(db)`, and `FitnessService(...)`.

### 11. Register fitness router in main application
- **Objective**: Wire the fitness router into the FastAPI app.
- **File**: `app/main.py` [MODIFY]
- **Actions**:
  - Add import `from app.api.routes.fitness import router as fitness_router`.
  - Add `app.include_router(fitness_router)`.

## Migration

### 12. Create Alembic migration for athlete_fitness hypertable
- **Objective**: Generate a migration that creates the `athlete_fitness` table as a TimescaleDB hypertable.
- **File**: `alembic/versions/..._add_athlete_fitness.py` [CREATE]
- **Actions**:
  - In `upgrade()`:
    1. `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")`.
    2. `op.execute("CREATE EXTENSION IF NOT EXISTS vector;")`.
    3. `op.create_table("athlete_fitness", ...)` with all columns matching the ORM model (autogenerate will fill DDL).
    4. `op.create_index("ix_athlete_fitness_athlete_id", "athlete_fitness", ["athlete_id"])`.
    5. `op.execute("SELECT create_hypertable('athlete_fitness', 'metric_date', if_not_exists => TRUE);")`.
  - In `downgrade()`:
    1. `op.execute("SELECT drop_hypertable('athlete_fitness');")`.
    2. `op.drop_index("ix_athlete_fitness_athlete_id", table_name="athlete_fitness")`.
    3. `op.drop_table("athlete_fitness")`.
