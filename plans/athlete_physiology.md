# Plan: Athlete Physiology

## Overview
Implement versioned physiological metrics (`AthletePhysiology`) with effective date ranges, overlap validation, and full CRUD API.

---

## Models

### 1. AthletePhysiology ORM Model
- **Objective:** Define the `AthletePhysiology` table with versioned date ranges and athlete relationship.
- **File:** `app/models/physiology.py` [CREATE]
- **Actions:**
  - Create `AthletePhysiology` class inheriting from `Base`.
  - Table name: `athlete_physiology`.
  - Fields:
    - `id`: `Mapped[uuid.UUID]`, primary key, `server_default=text("gen_random_uuid()")`.
    - `athlete_id`: `Mapped[uuid.UUID]`, non-nullable, foreign key to `athletes.id` with `ondelete="CASCADE"`, indexed.
    - `ftp`: `Mapped[Optional[int]]`, nullable.
    - `lt1`: `Mapped[Optional[int]]`, nullable.
    - `lt2`: `Mapped[Optional[int]]`, nullable.
    - `vo2_max`: `Mapped[Optional[float]]`, nullable.
    - `max_hr`: `Mapped[Optional[int]]`, nullable.
    - `source`: `Mapped[WellnessSource]`, non-nullable, default `WellnessSource.MANUAL`, use `SAEnum(WellnessSource, native_enum=False, length=20)`.
    - `effective_from`: `Mapped[date]`, non-nullable, `Date`.
    - `effective_to`: `Mapped[Optional[date]]`, nullable, `Date`.
    - `created_at`: `Mapped[datetime]`, `DateTime(timezone=True)`, `server_default=func.now()`.
    - `updated_at`: `Mapped[datetime]`, `DateTime(timezone=True)`, `server_default=func.now()`, `onupdate=func.now()`.
  - Relationship: `athlete: Mapped["Athlete"] = relationship(back_populates="physiology_versions")`.
  - Add a composite index on `(athlete_id, effective_from, effective_to)` for overlap queries.

### 2. Wire AthletePhysiology into Athlete Model
- **Objective:** Add reverse relationship from `Athlete` to `AthletePhysiology`.
- **File:** `app/models/athlete.py` [MODIFY]
- **Actions:**
  - In the `TYPE_CHECKING` block, add `from app.models.physiology import AthletePhysiology`.
  - Add `physiology_versions: Mapped[list["AthletePhysiology"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")` to the `Athlete` class.

### 3. Export AthletePhysiology
- **Objective:** Expose the new model through the models package.
- **File:** `app/models/__init__.py` [MODIFY]
- **Actions:**
  - Add import: `from app.models.physiology import AthletePhysiology`.
  - Add `"AthletePhysiology"` to `__all__`.

---

## Schemas

### 4. AthletePhysiology Pydantic Schemas
- **Objective:** Define request/response contracts for the physiology API.
- **File:** `app/schemas/physiology.py` [CREATE]
- **Actions:**
  - `AthletePhysiologyBase`: fields `ftp`, `lt1`, `lt2`, `vo2_max`, `max_hr` as `Optional[int]` or `Optional[float]`; `source` as `WellnessSource` default `WellnessSource.MANUAL`; `effective_from` and `effective_to` as `date`.
  - `AthletePhysiologyCreate(AthletePhysiologyBase)`: inherits all fields, `effective_to` is `Optional[date]`.
  - `AthletePhysiologyUpdate`: all fields optional (same types as base but with `Optional` wrappers and no defaults).
  - `AthletePhysiologyResponse(AthletePhysiologyBase)`: adds `id` (`uuid.UUID`), `athlete_id` (`uuid.UUID`), `created_at` (`datetime`), `updated_at` (`datetime`). Set `model_config = ConfigDict(from_attributes=True)`. `effective_to` is `Optional[date]`.

---

## Repositories

### 5. Physiology Repository
- **Objective:** Provide data access for `AthletePhysiology` with overlap-aware queries.
- **File:** `app/repositories/physiology_repository.py` [CREATE]
- **Actions:**
  - Create `PhysiologyRepository(BaseRepository[AthletePhysiology])`.
  - Constructor accepts `AsyncSession` and passes `AthletePhysiology` to `BaseRepository`.
  - Add `async def get_by_athlete(self, athlete_id: UUID, skip: int = 0, limit: int = 50) -> list[AthletePhysiology]` ordered by `effective_from desc`.
  - Add `async def get_by_athlete_and_date(self, athlete_id: UUID, target_date: date) -> AthletePhysiology | None` returning the record where `effective_from <= target_date` and (`effective_to IS NULL` OR `effective_to >= target_date`), ordered by `effective_from desc`, limit 1.
  - Add `async def has_overlap(self, athlete_id: UUID, effective_from: date, effective_to: Optional[date], exclude_id: Optional[UUID] = None) -> bool` that queries for any existing record for the same athlete whose date range intersects with the given range. The overlap logic: existing record overlaps if `existing.effective_from <= effective_to (or given effective_to is NULL)` AND `(existing.effective_to IS NULL OR existing.effective_to >= given effective_from)`. Exclude the row with `exclude_id` when updating.

---

## Services

### 6. Physiology Service
- **Objective:** Encapsulate business logic, enforce date-range rules, and prevent overlaps.
- **File:** `app/services/physiology_service.py` [CREATE]
- **Actions:**
  - Create `PhysiologyService` class accepting `PhysiologyRepository` and `AthleteRepository` in its constructor.
  - Add private helper `async def _validate(self, athlete_id: UUID, effective_from: date, effective_to: Optional[date], exclude_id: Optional[UUID] = None)` that:
    - Verifies the athlete exists via `AthleteRepository.get_by_id`; raise `ValueError("Athlete not found")` if missing.
    - Validates `effective_from <= effective_to` when `effective_to` is not `None`; raise `ValueError("effective_from must be <= effective_to")` if violated.
    - Calls `PhysiologyRepository.has_overlap`; raise `ValueError("Date range overlaps with an existing physiology record")` if true.
  - `async def create(self, athlete_id: UUID, data: AthletePhysiologyCreate) -> AthletePhysiology`:
    - Call `_validate`.
    - Build a dict from `data.model_dump()`, inject `athlete_id`, and call `physiology_repo.create(**...)`.
  - `async def list_by_athlete(self, athlete_id: UUID, skip: int = 0, limit: int = 50) -> list[AthletePhysiology]`:
    - Verify athlete exists; raise `ValueError` if not.
    - Return `physiology_repo.get_by_athlete(...)`.
  - `async def get_by_id(self, physiology_id: UUID) -> AthletePhysiology | None`:
    - Return `physiology_repo.get_by_id(physiology_id)`.
  - `async def get_effective(self, athlete_id: UUID, target_date: date) -> AthletePhysiology | None`:
    - Return `physiology_repo.get_by_athlete_and_date(athlete_id, target_date)`.
  - `async def update(self, physiology_id: UUID, data: AthletePhysiologyUpdate) -> AthletePhysiology | None`:
    - Fetch existing record; return `None` if missing.
    - Extract `effective_from` and `effective_to` from `data.model_dump(exclude_unset=True)`, falling back to existing values.
    - Call `_validate` with `exclude_id=physiology_id`.
    - Call `physiology_repo.update(physiology_id, **update_data)`.
  - `async def delete(self, physiology_id: UUID) -> bool`:
    - Return `physiology_repo.delete(physiology_id)` (delegate to base repository).

---

## API

### 7. Physiology Routes
- **Objective:** Expose REST endpoints for physiology CRUD under the athlete namespace.
- **File:** `app/api/routes/physiology.py` [CREATE]
- **Actions:**
  - Create router with `prefix="/athletes/{athlete_id}/physiology"` and `tags=["physiology"]`.
  - Dependency: `get_physiology_service(db)` that instantiates `PhysiologyRepository`, `AthleteRepository`, and returns `PhysiologyService(...)`.
  - Endpoints:
    - `POST /` — `create_physiology(athlete_id: UUID, payload: AthletePhysiologyCreate, service: PhysiologyService = Depends(get_physiology_service))` — returns `AthletePhysiologyResponse`. Catch `ValueError` and raise `HTTPException(status_code=400, detail=str(e))`.
    - `GET /` — `list_physiology(athlete_id: UUID, skip: int = 0, limit: int = 50, service: ...)` — returns `list[AthletePhysiologyResponse]`. Catch `ValueError` → `404`.
    - `GET /{physiology_id}` — `get_physiology(athlete_id: UUID, physiology_id: UUID, service: ...)` — returns `AthletePhysiologyResponse`; `404` if not found.
    - `GET /effective/{target_date}` — `get_effective_physiology(athlete_id: UUID, target_date: date, service: ...)` — returns `AthletePhysiologyResponse`; `404` if no effective record.
    - `PATCH /{physiology_id}` — `update_physiology(athlete_id: UUID, physiology_id: UUID, payload: AthletePhysiologyUpdate, service: ...)` — returns `AthletePhysiologyResponse`; `404` if not found; `400` on `ValueError`.
    - `DELETE /{physiology_id}` — `delete_physiology(athlete_id: UUID, physiology_id: UUID, service: ...)` — returns `204` on success, `404` if not found.
  - Note: `athlete_id` in the path is validated by the service/repository layer (existence check).

### 8. Register Physiology Router
- **Objective:** Wire the new router into the FastAPI application.
- **File:** `app/main.py` [MODIFY]
- **Actions:**
  - Add import: `from app.api.routes.physiology import router as physiology_router`.
  - Add `app.include_router(physiology_router)` after the wellness router.

---

## Migration

### 9. Alembic Migration for AthletePhysiology
- **Objective:** Generate and verify the database migration for the new table.
- **File:** `alembic/versions/xxx_add_athlete_physiology.py` [CREATE]
- **Actions:**
  - Use `bash scripts/db-revision.sh "add_athlete_physiology_table"` to generate the migration file.
  - Review the generated script to confirm it creates the `athlete_physiology` table with all columns, primary key, foreign key, indexes, and enum handling consistent with existing models.
  - Ensure the migration uses `op.create_table(...)` and does **not** create a hypertable (per stack-truth: `athlete_physiology` is a standard table, not time-series).

---

## Summary of New Files
- `app/models/physiology.py`
- `app/schemas/physiology.py`
- `app/repositories/physiology_repository.py`
- `app/services/physiology_service.py`
- `app/api/routes/physiology.py`
- `alembic/versions/xxx_add_athlete_physiology_table.py`

## Summary of Modified Files
- `app/models/athlete.py` (add `physiology_versions` relationship)
- `app/models/__init__.py` (export new model)
- `app/main.py` (register router)
