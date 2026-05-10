# Daily Training Load Metrics — Athlete Fitness Module

## Models

### 1. AthleteFitness model
- **Objective:** Define the SQLAlchemy ORM model for daily training load metrics.
- **File:** `app/models/fitness.py` [CREATE]
- **Actions:**
  - Import `uuid`, `date`, `datetime`, `TYPE_CHECKING`, `Optional`.
  - Import `UUID`, `String`, `DateTime`, `Date`, `Float`, `ForeignKey`, `text`, `func`, `Enum as SAEnum`, `UniqueConstraint as UC` from SQLAlchemy.
  - Import `Mapped`, `mapped_column`, `relationship` from SQLAlchemy ORM.
  - Import `Base` from `app.db.base`.
  - Import `WellnessSource` from `app.models.enums`.
  - Under `if TYPE_CHECKING:`, import `Athlete` from `app.models.athlete`.
  - Create `AthleteFitness` class inheriting from `Base` with `__tablename__ = "athlete_fitness"`.
  - Add `id: Mapped[uuid.UUID]` as primary key with `server_default=text("gen_random_uuid()")`.
  - Add `athlete_id: Mapped[uuid.UUID]` foreign key to `athletes.id` with `ondelete="CASCADE"`, `nullable=False`, `index=True`.
  - Add `metric_date: Mapped[date]` as `Date`, `nullable=False`.
  - Add `tss: Mapped[Optional[float]]` as `Float`, nullable.
  - Add `atl: Mapped[Optional[float]]` as `Float`, nullable.
  - Add `ctl: Mapped[Optional[float]]` as `Float`, nullable.
  - Add `tsb: Mapped[Optional[float]]` as `Float`, nullable.
  - Add `source: Mapped[WellnessSource]` using `SAEnum(WellnessSource, native_enum=False, length=20)`, `nullable=False`.
  - Add `created_at: Mapped[datetime]` as `DateTime(timezone=True)`, `server_default=func.now()`.
  - Add `updated_at: Mapped[datetime]` as `DateTime(timezone=True)`, `server_default=func.now()`, `onupdate=func.now()`.
  - Add `athlete: Mapped["Athlete"]` relationship with `back_populates="fitness_metrics"`.
  - Define `__table_args__` with `UC("athlete_id", "metric_date", name="uq_athlete_fitness_date")`.

### 2. Wire AthleteFitness into models package
- **Objective:** Export the new model from the models package.
- **File:** `app/models/__init__.py` [MODIFY]
- **Actions:**
  - Add import: `from app.models.fitness import AthleteFitness`.
  - Add `"AthleteFitness"` to `__all__`.

### 3. Add fitness_metrics relationship to Athlete
- **Objective:** Link the Athlete model to the new fitness records.
- **File:** `app/models/athlete.py` [MODIFY]
- **Actions:**
  - Inside the existing `if TYPE_CHECKING:` block, add `from app.models.fitness import AthleteFitness`.
  - Add `fitness_metrics: Mapped[list["AthleteFitness"]]` relationship with `back_populates="athlete"` and `cascade="all, delete-orphan"`.

---

## Schemas

### 4. Fitness schemas
- **Objective:** Define Pydantic request/response schemas for fitness data.
- **File:** `app/schemas/fitness.py` [CREATE]
- **Actions:**
  - Create `FitnessBase` with fields: `metric_date: date`, `tss: Optional[float] = None`, `atl: Optional[float] = None`, `ctl: Optional[float] = None`, `tsb: Optional[float] = None`, `source: WellnessSource`.
  - Create `FitnessCreate` inheriting from `FitnessBase`, adding `athlete_id: uuid.UUID`.
  - Create `FitnessUpdate` with all fields optional (same set as `FitnessBase` but every field is `Optional`).
  - Create `FitnessResponse` inheriting from `FitnessBase`, adding `id: uuid.UUID`, `athlete_id: uuid.UUID`, `created_at: datetime`, `updated_at: datetime`, and `model_config = ConfigDict(from_attributes=True)`.
  - Create `FitnessListParams` with `date_from: Optional[date] = None`, `date_to: Optional[date] = None`, `limit: int = Field(default=50, ge=1, le=1000)`, `offset: int = Field(default=0, ge=0)`.
  - Create `FitnessListResponse` with `items: list[FitnessResponse]`, `total: int`.

### 5. Wire fitness schemas into schemas package
- **Objective:** Export new schemas from the schemas package.
- **File:** `app/schemas/__init__.py` [MODIFY]
- **Actions:**
  - Add imports for `FitnessBase`, `FitnessCreate`, `FitnessUpdate`, `FitnessResponse`, `FitnessListParams`, `FitnessListResponse` from `app.schemas.fitness`.
  - Add the imported names to `__all__`.

---

## Repositories

### 6. FitnessRepository
- **Objective:** Implement CRUD and athlete/date-specific queries for fitness records.
- **File:** `app/repositories/fitness_repository.py` [CREATE]
- **Actions:**
  - Define `FitnessRepository` inheriting from `BaseRepository[AthleteFitness]`.
  - Constructor accepts `AsyncSession` and passes `AthleteFitness` to the base class.
  - Implement `get_by_id(self, fitness_id: UUID) -> Optional[AthleteFitness]`.
  - Implement `get_by_athlete_date(self, athlete_id: UUID, metric_date: date) -> Optional[AthleteFitness]`.
  - Implement `get_by_athlete(self, athlete_id: UUID, skip=0, limit=50, date_from=None, date_to=None) -> List[AthleteFitness]`, ordered by `metric_date.desc()`.
  - Implement `update(self, athlete_id: UUID, metric_date: date, **kwargs) -> Optional[AthleteFitness]` — this method updates by composite key `(athlete_id, metric_date)`, identical in pattern to `WellnessRepository.update`.
  - Implement `delete_by_composite_key(self, athlete_id: UUID, metric_date: date) -> bool`.
  - Implement `count_by_athlete(self, athlete_id: UUID) -> int`.

### 7. Wire FitnessRepository into repositories package
- **Objective:** Export the new repository.
- **File:** `app/repositories/__init__.py` [MODIFY]
- **Actions:**
  - Add import: `from app.repositories.fitness_repository import FitnessRepository`.
  - Add `"FitnessRepository"` to `__all__`.

---

## Services

### 8. FitnessService
- **Objective:** Implement business logic including duplicate-date validation.
- **File:** `app/services/fitness_service.py` [CREATE]
- **Actions:**
  - Define `FitnessService` with `__init__` accepting `FitnessRepository` and `AthleteRepository`.
  - Implement `create_fitness(self, data: FitnessCreate) -> AthleteFitness`:
    - Verify athlete exists via `AthleteRepository.get_by_id`.
    - Verify no existing fitness record exists for `(athlete_id, metric_date)` via `FitnessRepository.get_by_athlete_date`.
    - Raise `ValueError` for missing athlete or duplicate record.
    - Call `fitness_repo.create(**data.model_dump())`.
  - Implement `get_fitness(self, fitness_id: UUID) -> AthleteFitness | None`.
  - Implement `list_athlete_fitness(self, athlete_id: UUID, params: FitnessListParams) -> list[AthleteFitness]`.
  - Implement `update_fitness(self, fitness_id: UUID, data: FitnessUpdate) -> AthleteFitness | None`:
    - Load existing by primary key.
    - Build update payload with `data.model_dump(exclude_unset=True)`.
    - If `metric_date` is present in the payload and differs from the existing record, verify no other record exists for the new date (same athlete).
    - Raise `ValueError` on conflict.
    - Apply update via `fitness_repo.update_by_id`.
  - Implement `delete_fitness(self, fitness_id: UUID) -> bool`.
  - Implement `count_by_athlete(self, athlete_id: UUID) -> int`.

### 9. Wire FitnessService into services package
- **Objective:** Export the new service.
- **File:** `app/services/__init__.py` [MODIFY]
- **Actions:**
  - Add import: `from app.services.fitness_service import FitnessService`.
  - Add `"FitnessService"` to `__all__`.

---

## API

### 10. Fitness router
- **Objective:** Expose REST endpoints for daily training load metrics.
- **File:** `app/api/routes/fitness.py` [CREATE]
- **Actions:**
  - Create `APIRouter(prefix="/fitness", tags=["fitness"])`.
  - Define dependency `get_fitness_service(db)` that instantiates `FitnessRepository`, `AthleteRepository`, and `FitnessService`.
  - `POST /` — accepts `FitnessCreate`, calls `service.create_fitness`, returns `FitnessResponse` with `201`. Catch `ValueError` → `400`.
  - `GET /{fitness_id}` — returns `FitnessResponse` using `FitnessResponse.model_validate`. `404` if missing.
  - `GET /athletes/{athlete_id}/fitness` — accepts `FitnessListParams`, returns `FitnessListResponse` with items serialized via `FitnessResponse.model_validate` and total count.
  - `PATCH /{fitness_id}` — accepts `FitnessUpdate`, passes payload serialized with `exclude_unset=True`, returns `FitnessResponse` using `model_validate`. Catch `ValueError` → `400`. `404` if missing.
  - `DELETE /{fitness_id}` — returns `204`. `404` if missing.

### 11. Register fitness router in main application
- **Objective:** Mount the fitness router.
- **File:** `app/main.py` [MODIFY]
- **Actions:**
  - Add import: `from app.api.routes.fitness import router as fitness_router`.
  - Add `app.include_router(fitness_router)`.

---

## Migration

### 12. Create athlete_fitness hypertable migration
- **Objective:** Generate and verify the Alembic migration for the new hypertable.
- **File:** `alembic/versions/<generated>_add_athlete_fitness_table.py` [CREATE]
- **Actions:**
  - Generate the migration using `bash scripts/db-revision.sh "add_athlete_fitness_table"`.
  - In `upgrade()`:
    - `op.create_table('athlete_fitness', ...)` with all columns matching the ORM model.
    - `op.create_index('ix_athlete_fitness_athlete_id', 'athlete_fitness', ['athlete_id'])`.
    - `op.create_index('ix_athlete_fitness_metric_date', 'athlete_fitness', ['metric_date'])`.
    - Unique constraint on `(athlete_id, metric_date)`.
    - `op.execute("SELECT create_hypertable('athlete_fitness', 'metric_date', if_not_exists => TRUE);")`.
  - In `downgrade()`:
    - `op.execute("SELECT drop_hypertable('athlete_fitness');")`.
    - Drop indexes.
    - `op.drop_table('athlete_fitness')`.
