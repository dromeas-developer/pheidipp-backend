# Implementation Plan: Daily Wellness Metrics

---

## Models

### 1. Add WellnessSource enum
- **Objective:** Define the source enum for wellness data ingestion
- **File:** `app/models/enums.py` [MODIFY]
- **Actions:**
  - Append `WellnessSource(str, enum.Enum)` with values: `manual`, `garmin`, `whoop`, `oura`, `polar`

### 2. Create AthleteWellness model
- **Objective:** Define the daily wellness metrics ORM table as a TimescaleDB hypertable
- **File:** `app/models/wellness.py` [CREATE]
- **Actions:**
  - Define `AthleteWellness(Base)` with:
    - `id`: `Mapped[uuid.UUID]`, `UUID(as_uuid=True)`, `primary_key=True`, `server_default=text("gen_random_uuid()")`
    - `athlete_id`: `Mapped[uuid.UUID]`, `ForeignKey("athletes.id", ondelete="CASCADE")`, index=True, nullable=False
    - `metric_date`: `Mapped[date]`, `Date`, nullable=False — hypertable time column (stored as UTC date)
    - `sleep_total`: `Mapped[Optional[int]]`, `Integer`, nullable=True — minutes
    - `sleep_light`: `Mapped[Optional[int]]`, `Integer`, nullable=True — minutes
    - `sleep_deep`: `Mapped[Optional[int]]`, `Integer`, nullable=True — minutes
    - `sleep_rem`: `Mapped[Optional[int]]`, `Integer`, nullable=True — minutes
    - `sleep_awake`: `Mapped[Optional[int]]`, `Integer`, nullable=True — minutes
    - `resting_hr`: `Mapped[Optional[int]]`, `Integer`, nullable=True — bpm
    - `hrv`: `Mapped[Optional[int]]`, `Integer`, nullable=True — ms
    - `weight`: `Mapped[Optional[float]]`, `Float`, nullable=True — kg
    - `source`: `Mapped[WellnessSource]`, `SAEnum(WellnessSource, native_enum=False, length=20)`, nullable=False
    - `timezone`: `Mapped[str]`, `String(100)`, nullable=False — IANA timezone string
    - `created_at`: `Mapped[datetime]`, `DateTime(timezone=True)`, `server_default=func.now()`
    - `updated_at`: `Mapped[datetime]`, `DateTime(timezone=True)`, `server_default=func.now()`, `onupdate=func.now()`
  - Add `UniqueConstraint("athlete_id", "metric_date", name="uq_athlete_wellness_date")`
  - Add relationship: `athlete: Mapped["Athlete"]` with back_populates="wellness_metrics" (update Athlete model accordingly)

### 3. Register wellness model in package exports
- **Objective:** Ensure ORM model is discoverable by Alembic
- **File:** `app/models/__init__.py` [MODIFY]
- **Actions:**
  - Add import: `from app.models.wellness import AthleteWellness`
  - Export `AthleteWellness` in `__all__`

### 4. Add wellness relationship to Athlete model
- **Objective:** Allow navigation from athlete to wellness records
- **File:** `app/models/athlete.py` [MODIFY]
- **Actions:**
  - Add `wellness_metrics: Mapped[list["AthleteWellness"]] = relationship(...)` to `Athlete` with appropriate `back_populates`

---

## Schemas

### 5. Create wellness Pydantic schemas
- **Objective:** Define request/response contracts for wellness endpoints
- **File:** `app/schemas/wellness.py` [CREATE]
- **Actions:**
  - Define `WellnessBase(BaseModel)` with:
    - `metric_date: date`
    - `sleep_total: Optional[int] = None`
    - `sleep_light: Optional[int] = None`
    - `sleep_deep: Optional[int] = None`
    - `sleep_rem: Optional[int] = None`
    - `sleep_awake: Optional[int] = None`
    - `resting_hr: Optional[int] = None`
    - `hrv: Optional[int] = None`
    - `weight: Optional[float] = None`
    - `source: WellnessSource`
    - `timezone: str` (max length 100 in validation)
  - Define `WellnessCreate(WellnessBase)` with `athlete_id: uuid.UUID`
  - Define `WellnessUpdate(BaseModel)` with all fields optional (same types as WellnessBase, `exclude_unset=True` compatible)
  - Define `WellnessResponse(WellnessBase)` with:
    - `id: uuid.UUID`
    - `athlete_id: uuid.UUID`
    - `created_at: datetime`
    - `updated_at: datetime`
    - `model_config = ConfigDict(from_attributes=True)`
  - Define `WellnessListParams(BaseModel)` with:
    - `date_from: Optional[date] = None`
    - `date_to: Optional[date] = None`
    - `limit: int = 50`
    - `offset: int = 0`
  - Define `WellnessListResponse(BaseModel)` with:
    - `items: list[WellnessResponse]`
    - `total: int`

### 6. Register wellness schemas in package exports
- **Objective:** Make schemas importable from app.schemas
- **File:** `app/schemas/__init__.py` [MODIFY]
- **Actions:**
  - Add imports for all wellness schema classes from `app.schemas.wellness`
  - Update `__all__` to include wellness exports

---

## Repositories

### 7. Create wellness repository
- **Objective:** Encapsulate database access for wellness records
- **File:** `app/repositories/wellness_repository.py` [CREATE]
- **Actions:**
  - Define `WellnessRepository(BaseRepository[AthleteWellness])`
  - Constructor calls `super().__init__(session, AthleteWellness)`
  - Add `async def get_by_athlete_date(self, athlete_id: UUID, metric_date: date) -> Optional[AthleteWellness]`
  - Add `async def get_by_athlete(self, athlete_id: UUID, skip: int = 0, limit: int = 50, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[AthleteWellness]` — order by `metric_date.desc()`
  - Add `async def count_by_athlete(self, athlete_id: UUID) -> int`

### 8. Register wellness repository in package exports
- **Objective:** Make repository importable from app.repositories
- **File:** `app/repositories/__init__.py` [MODIFY]
- **Actions:**
  - Add import for `WellnessRepository` from `app.repositories.wellness_repository`

---

## Services

### 9. Create wellness service
- **Objective:** Implement business logic for wellness CRUD and uniqueness rules
- **File:** `app/services/wellness_service.py` [CREATE]
- **Actions:**
  - Define `WellnessService` accepting `WellnessRepository` and `AthleteRepository`
  - Add `async def create_wellness(self, data: WellnessCreate) -> AthleteWellness`:
    - Verify athlete exists via `AthleteRepository.get_by_id`
    - Check for existing wellness record for the same `athlete_id` + `metric_date` combination
    - If duplicate exists, raise `ValueError` with message indicating unique constraint violation
    - Call `wellness_repo.create(**data.model_dump())`
  - Add `async def get_wellness(self, wellness_id: UUID) -> Optional[AthleteWellness]`
  - Add `async def list_athlete_wellness(self, athlete_id: UUID, params: WellnessListParams) -> list[AthleteWellness]`
  - Add `async def update_wellness(self, wellness_id: UUID, data: WellnessUpdate) -> Optional[AthleteWellness]`:
    - If `metric_date` is being updated, verify no conflicting record exists for the same athlete and new date
    - If conflict, raise `ValueError`
    - Apply update via `wellness_repo.update`
  - Add `async def delete_wellness(self, wellness_id: UUID) -> bool`

### 10. Register wellness service in package exports
- **Objective:** Make service importable from app.services
- **File:** `app/services/__init__.py` [MODIFY]
- **Actions:**
  - Add import for `WellnessService` from `app.services.wellness_service`

---

## API

### 11. Create wellness API router
- **Objective:** Expose HTTP endpoints for wellness CRUD under /wellness
- **File:** `app/api/routes/wellness.py` [CREATE]
- **Actions:**
  - Create `APIRouter` with `prefix="/wellness"`, `tags=["wellness"]`
  - `POST /` — `create_wellness`:
    - Accepts `WellnessCreate`, injects `AsyncSession`
    - Instantiates repos + service, calls `service.create_wellness`
    - Returns `WellnessResponse`
    - On `ValueError`, returns 400 Bad Request
  - `GET /{wellness_id}` — `get_wellness`:
    - Returns `WellnessResponse`
    - 404 if not found
  - `GET /athletes/{athlete_id}/wellness` — `list_athlete_wellness`:
    - Query params via `WellnessListParams`
    - Returns `WellnessListResponse` with items + total count
  - `PATCH /{wellness_id}` — `update_wellness`:
    - Accepts `WellnessUpdate`
    - Returns `WellnessResponse`
    - 404 if not found, 400 on `ValueError`
  - `DELETE /{wellness_id}` — `delete_wellness`:
    - Returns 204 on success, 404 if not found

### 12. Register wellness router in application
- **Objective:** Attach wellness routes to the FastAPI app
- **File:** `app/main.py` [MODIFY]
- **Actions:**
  - Import wellness router in `app/main.py`
  - Add `app.include_router(wellness_router)` after existing routers

---

## Migration

### 13. Create Alembic migration for AthleteWellness hypertable
- **Objective:** Generate and verify database migration
- **File:** `migrations/versions/<generated>.py`via `bash scripts/db-revision.sh` and manual verification [CREATE]
- **Actions:**
  - Ensure `app/models/__init__.py` imports `AthleteWellness`
  - Run `bash scripts/db-revision.sh "add_athlete_wellness_hypertable"`
  - In the generated migration `upgrade()`, verify operations follow this exact sequence:
    1. `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")`
    2. `op.execute("CREATE EXTENSION IF NOT EXISTS vector;")`
    3. `op.create_table('athlete_wellness', ...)` with all columns defined in the model, including the composite unique constraint on `(athlete_id, metric_date)`
    4. `op.create_index` for `athlete_id` and any other indices
    5. `op.execute("SELECT create_hypertable('athlete_wellness', 'metric_date', if_not_exists => TRUE);")`
  - In `downgrade()`, include:
    - `op.execute("SELECT drop_hypertable('athlete_wellness');")` or `op.drop_table('athlete_wellness')`, whichever the generated migration produces after verification
    - Dropping extensions is optional/omitted (extensions are shared)
  - Run `bash scripts/db-upgrade.sh` to apply

