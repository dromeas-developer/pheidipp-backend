# Athlete Fitness Module Implementation Plan

## Models

### 1. AthleteFitness ORM Model
- **Objective:** Define the AthleteFitness hypertable with daily training load metrics and unique constraint on (athlete_id, metric_date).
- **File:** `app/models/fitness.py` [CREATE]
- **Actions:**
  - Create `AthleteFitness` class inheriting from `Base`.
  - Table name: `athlete_fitness`.
  - Primary key: `id` (UUID, server_default gen_random_uuid()).
  - Foreign key: `athlete_id` (UUID, nullable=False, index=True, ondelete CASCADE).
  - Columns: `metric_date` (Date, nullable=False), `tss` (Float, nullable=True), `atl` (Float, nullable=True), `ctl` (Float, nullable=True), `tsb` (Float, nullable=True), `source` (WellnessSource, nullable=False, SAEnum native_enum=False length=20), `created_at` (DateTime(timezone=True), server_default=func.now()), `updated_at` (DateTime(timezone=True), server_default=func.now(), onupdate=func.now()).
  - Relationship: `athlete: Mapped["Athlete"]` with `back_populates="fitness_metrics"`.
  - `__table_args__`: UniqueConstraint on (`athlete_id`, `metric_date`, name=`uq_athlete_fitness_date`).

### 2. Athlete Model — Fitness Relationship
- **Objective:** Wire the AthleteFitness relationship on the Athlete model.
- **File:** `app/models/athlete.py` [MODIFY]
- **Actions:**
  - Add `fitness_metrics: Mapped[list["AthleteFitness"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")`.
  - Add `from app.models.fitness import AthleteFitness` to the `if TYPE_CHECKING:` block.

### 3. Models Package Export
- **Objective:** Export the new model so Base.metadata sees it.
- **File:** `app/models/__init__.py` [MODIFY]
- **Actions:**
  - Import `AthleteFitness` from `app.models.fitness`.
  - Add `"AthleteFitness"` to `__all__`.

## Schemas

### 4. Fitness Pydantic Schemas
- **Objective:** Define request/response contracts mirroring the wellness pattern.
- **File:** `app/schemas/fitness.py` [CREATE]
- **Actions:**
  - `FitnessBase`: `metric_date` (date), `tss` (Optional[float]), `atl` (Optional[float]), `ctl` (Optional[float]), `tsb` (Optional[float]), `source` (WellnessSource).
  - `FitnessCreate(FitnessBase)`: add `athlete_id` (UUID).
  - `FitnessUpdate`: all fields Optional; `metric_date` Optional[date]; `source` Optional[WellnessSource].
  - `FitnessResponse(FitnessBase)`: add `id` (UUID), `athlete_id` (UUID), `created_at` (datetime), `updated_at` (datetime).
  - `FitnessListParams`: `date_from` Optional[date], `date_to` Optional[date], `limit` int = Field(50, ge=1, le=1000), `offset` int = Field(0, ge=0).
  - `FitnessListResponse`: `items` list[FitnessResponse], `total` int.

### 5. Schemas Package Export
- **Objective:** Wire the new schemas into the schemas package.
- **File:** `app/schemas/__init__.py` [MODIFY]
- **Actions:**
  - Import all fitness schema classes from `app.schemas.fitness`.
  - Add them to `__all__`.

## Repositories

### 6. FitnessRepository
- **Objective:** Provide DB access for athlete fitness records, including composite key lookups.
- **File:** `app/repositories/fitness_repository.py` [CREATE]
- **Actions:**
  - Class `FitnessRepository(BaseRepository[AthleteFitness])`.
  - `__init__(self, session)` stores session and model.
  - `get_by_id(self, fitness_id: UUID)`.
  - `get_by_athlete_date(self, athlete_id: UUID, metric_date: date)`.
  - `get_by_athlete(self, athlete_id, skip=0, limit=50, date_from=None, date_to=None)` ordered by metric_date desc.
  - `update_by_id(self, fitness_id, **kwargs)`.
  - `update(self, athlete_id, metric_date, **kwargs)` composite-key update.
  - `delete_by_id(self, fitness_id)`.
  - `delete_by_composite_key(self, athlete_id, metric_date)`.
  - `count_by_athlete(self, athlete_id)`.

### 7. Repositories Package Export
- **Objective:** Make FitnessRepository importable from the package.
- **File:** `app/repositories/__init__.py` [MODIFY]
- **Actions:**
  - Import `FitnessRepository` from `app.repositories.fitness_repository`.
  - Add it to `__all__`.

## Services

### 8. FitnessService
- **Objective:** Implement business logic for fitness record lifecycle with unique-date enforcement per athlete.
- **File:** `app/services/fitness_service.py` [CREATE]
- **Actions:**
  - Class `FitnessService` initialized with `FitnessRepository` and `AthleteRepository`.
  - `create_fitness(data: FitnessCreate)` — validate athlete exists, check duplicate (athlete_id, metric_date), then create.
  - `get_fitness(fitness_id: UUID)` — fetch by primary key.
  - `list_athlete_fitness(athlete_id: UUID, params: FitnessListParams)` — delegate to repo.
  - `update_fitness(fitness_id: UUID, data: FitnessUpdate)` — update by primary key; if metric_date changes, verify no conflict for that athlete+date.
  - `delete_fitness(fitness_id: UUID)` — delete by primary key.

### 9. Services Package Export
- **Objective:** Make FitnessService importable from the package.
- **File:** `app/services/__init__.py` [MODIFY]
- **Actions:**
  - Import `FitnessService` from `app.services.fitness_service`.
  - Add it to `__all__`.

## API

### 10. Fitness Router
- **Objective:** Expose CRUD endpoints for athlete fitness records.
- **File:** `app/api/routes/fitness.py` [CREATE]
- **Actions:**
  - Router prefix `/fitness`, tags `["fitness"]`.
  - `POST /` — `create_fitness`, status 201, response model `FitnessResponse`.
  - `GET /{fitness_id}` — `get_fitness`, response model `FitnessResponse`.
  - `GET /athletes/{athlete_id}/fitness` — `list_athlete_fitness`, response model `FitnessListResponse`.
  - `PATCH /{fitness_id}` — `update_fitness`, response model `FitnessResponse`.
  - `DELETE /{fitness_id}` — `delete_fitness`, status 204.
  - All routes use `get_db` dependency, instantiate `FitnessRepository`, `AthleteRepository`, and `FitnessService`, and translate ValueError to 400 and missing records to 404.

### 11. Application Router Wiring
- **Objective:** Mount the fitness router in the FastAPI application.
- **File:** `app/main.py` [MODIFY]
- **Actions:**
  - Import `router as fitness_router` from `app.api.routes.fitness`.
  - Add `app.include_router(fitness_router)`.

## Migration

### 12. AthleteFitness Hypertable Migration
- **Objective:** Create the athlete_fitness table as a TimescaleDB hypertable.
- **File:** `migrations/versions/<generated>_add_athlete_fitness_hypertable.py` [CREATE]
- **Actions:**
  - In `upgrade()`:
    1. `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")`
    2. `op.execute("CREATE EXTENSION IF NOT EXISTS vector;")`
    3. `op.create_table('athlete_fitness', ...)` with all columns matching the ORM model.
    4. Add `UniqueConstraint('athlete_id', 'metric_date', name='uq_athlete_fitness_date')`.
    5. Add `op.create_index(...)` on `athlete_id` (unique=False).
    6. `op.execute("SELECT create_hypertable('athlete_fitness', 'metric_date', if_not_exists => TRUE);")`
  - In `downgrade()`:
    1. `op.execute("SELECT drop_hypertable('athlete_fitness', if_exists => TRUE, cascade => TRUE);")`
    2. `op.drop_index(...)` on athlete_fitness athlete_id index.
    3. `op.drop_table('athlete_fitness')`.
    4. Do NOT drop extensions.
