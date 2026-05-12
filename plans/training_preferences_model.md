## Models

1. Add onboarding goal and equipment enums to `app/models/enums.py`
   - Objective: Extend the shared enum module with all new `TrainingPreferences`-related string enums.
   - File: `app/models/enums.py` [MODIFY]
   - Actions:
     - Append `GoalType` string enum with values `race`, `fitness_improvement`, `maintenance`, `recovery`.
     - Append `GoalEventType` string enum with values `5k`, `10k`, `half_marathon`, `marathon`, `ultra`, `custom`.
     - Append `SportBackground` string enum with values `running_primary`, `cycling_crossover`, `swimming_crossover`, `multi_sport`, `other`.
     - Append `TrainingTimeOfDay` string enum with values `morning`, `afternoon`, `mixed`.
     - Append `GpsSource` string enum with values `none`, `phone`, `watch`.
     - Append `HrSource` string enum with values `none`, `wrist_optical`, `chest_strap`.
     - Append `PowerSource` string enum with values `none`, `running_power`.
     - Append `PrimaryTrainingPlatform` string enum with values `unknown`, `garmin_connect`, `coros`, `polar_flow`, `suunto`, `intervals_icu`, `strava`, `trainingpeaks`, `other`.

2. Create `TrainingPreferences` model
   - Objective: Introduce the versioned training-preferences entity.
   - File: `app/models/training_preferences.py` [CREATE]
   - Actions:
     - Import `uuid`, `date`, `datetime`, `TYPE_CHECKING`, `Optional`, `JSONB`, `UUID`, `String`, `DateTime`, `Date`, `Float`, `Integer`, `ForeignKey`, `text`, `func`, `Enum as SAEnum`, `Mapped`, `mapped_column`, `relationship`, `Index`, `Base`, and the new enums from `app.models.enums`.
     - Define class `TrainingPreferences(Base)` with `__tablename__ = "training_preferences"`.
     - Add `id` as `Mapped[uuid.UUID]` primary key with `server_default=text("gen_random_uuid()")`.
     - Add `athlete_id` as `Mapped[uuid.UUID]` with `ForeignKey("athletes.id", ondelete="CASCADE")`, `nullable=False`, and `index=True`.
     - Add `goal_type` as `Mapped[Optional[GoalType]]` using `SAEnum(GoalType, native_enum=False, length=20)`.
     - Add `goal_event_type` as `Mapped[Optional[GoalEventType]]` using `SAEnum(GoalEventType, native_enum=False, length=20)`.
     - Add `custom_distance_km` as `Mapped[Optional[float]]` with `Float`.
     - Add `goal_event_date` as `Mapped[Optional[date]]` with `Date`.
     - Add `goal_description` as `Mapped[Optional[str]]` with `String(500)`.
     - Add `weekly_volume_hours` as `Mapped[Optional[float]]` with `Float`.
     - Add `weekly_volume_km` as `Mapped[Optional[float]]` with `Float`.
     - Add `years_structured_training` as `Mapped[Optional[float]]` with `Float`.
     - Add `sport_background` as `Mapped[Optional[SportBackground]]` using `SAEnum(SportBackground, native_enum=False, length=20)`.
     - Add `recent_injury` as `Mapped[Optional[bool]]`.
     - Add `weekly_schedule` as `Mapped[Optional[dict]]` with `mapped_column(JSONB)`.
     - Add `gps_source` as `Mapped[Optional[GpsSource]]` using `SAEnum(GpsSource, native_enum=False, length=20)`.
     - Add `hr_source` as `Mapped[Optional[HrSource]]` using `SAEnum(HrSource, native_enum=False, length=20)`.
     - Add `power_source` as `Mapped[Optional[PowerSource]]` using `SAEnum(PowerSource, native_enum=False, length=20)`.
     - Add `primary_training_platform` as `Mapped[Optional[PrimaryTrainingPlatform]]` using `SAEnum(PrimaryTrainingPlatform, native_enum=False, length=20)`.
     - Add `fitness_level` as `Mapped[Optional[int]]` with `Integer`.
     - Add `created_at` as `Mapped[datetime]` with `DateTime(timezone=True)` and `server_default=func.now()`.
     - Add `updated_at` as `Mapped[datetime]` with `DateTime(timezone=True)` and `server_default=func.now()`, `onupdate=func.now()`.
     - Add `athlete` relationship with `back_populates="training_preferences_versions"`.
     - Set `__table_args__` to include a composite index on `(athlete_id, created_at)` named `ix_training_preferences_athlete_created_at`.

3. Wire `TrainingPreferences` relationship into `Athlete`
   - Objective: Allow an athlete to own a collection of versioned training preferences.
   - File: `app/models/athlete.py` [MODIFY]
   - Actions:
     - In `TYPE_CHECKING`, import `TrainingPreferences` from `app.models.training_preferences`.
     - In the `Athlete` class, add `training_preferences_versions: Mapped[list["TrainingPreferences"]]` relationship with `back_populates="athlete"` and `cascade="all, delete-orphan"`.

4. Update `app/models/__init__.py`
   - Objective: Export new enums and the `TrainingPreferences` model.
   - File: `app/models/__init__.py` [MODIFY]
   - Actions:
     - Import the new enums from `app.models.enums`.
     - Import `TrainingPreferences` from `app.models.training_preferences`.
     - Add all new symbols to `__all__`.

## Schemas

5. Create Pydantic schemas for `TrainingPreferences`
   - Objective: Define create, update, and response schemas for the onboarding questionnaire data.
   - File: `app/schemas/training_preferences.py` [CREATE]
   - Actions:
     - Import `uuid`, `date`, `datetime`, `Optional`, `Literal`, `BaseModel`, `Field`, `ConfigDict`, and all relevant enums from `app.models.enums`.
     - Define `TrainingPreferencesBase(BaseModel)` with every field from the model as `Optional` (default `None`), using `Field` where helpful (e.g., max length on `goal_description`).
     - Define `TrainingPreferencesCreate(TrainingPreferencesBase)`.
     - Define `TrainingPreferencesUpdate(BaseModel)` with all fields `Optional` (default `None`) to permit partial updates.
     - Define `TrainingPreferencesResponse(TrainingPreferencesBase)` with additional required fields: `id: uuid.UUID`, `athlete_id: uuid.UUID`, `created_at: datetime`, `updated_at: datetime`, and set `model_config = ConfigDict(from_attributes=True)`.

6. Update `app/schemas/__init__.py`
   - Objective: Expose the new schemas to the rest of the application.
   - File: `app/schemas/__init__.py` [MODIFY]
   - Actions:
     - Import `TrainingPreferencesCreate`, `TrainingPreferencesUpdate`, `TrainingPreferencesResponse` from `app.schemas.training_preferences`.
     - Append them to `__all__`.

## Repositories

7. Create `TrainingPreferencesRepository`
   - Objective: Provide CRUD and the custom "active" lookup for training preferences.
   - File: `app/repositories/training_preferences_repository.py` [CREATE]
   - Actions:
     - Import `AsyncSession`, `select`, `desc`, `uuid`, `BaseRepository`, and `TrainingPreferences`.
     - Define `TrainingPreferencesRepository(BaseRepository[TrainingPreferences])` whose `__init__` passes `session` and `TrainingPreferences` to the base constructor.
     - Add `async def list_by_athlete(self, athlete_id: uuid.UUID)` which executes a `select` ordered by `created_at DESC, id DESC` and returns all records.
     - Add `async def get_active_by_athlete(self, athlete_id: uuid.UUID)` which executes the same ordering but limits to 1 row and returns the scalar (or `None`).

8. Update `app/repositories/__init__.py`
   - Objective: Register the new repository in the layer package.
   - File: `app/repositories/__init__.py` [MODIFY]
   - Actions:
     - Import `TrainingPreferencesRepository` from `app.repositories.training_preferences_repository`.
     - Append it to `__all__`.

## Services

9. Create `TrainingPreferencesService`
   - Objective: Encapsulate business logic for creating and retrieving training preferences versions.
   - File: `app/services/training_preferences_service.py` [CREATE]
   - Actions:
     - Import `uuid`, `TrainingPreferencesRepository`, and the Pydantic schemas.
     - Define `TrainingPreferencesService` whose `__init__` accepts `repo: TrainingPreferencesRepository`.
     - Add `async def create(self, data: TrainingPreferencesCreate)` which calls `self.repo.create(**data.model_dump(exclude_unset=True))`.
     - Add `async def get_by_id(self, pref_id: uuid.UUID)` which delegates to `self.repo.get_by_id`.
     - Add `async def list_by_athlete(self, athlete_id: uuid.UUID)` which delegates to `self.repo.list_by_athlete`.
     - Add `async def get_active_by_athlete(self, athlete_id: uuid.UUID)` which delegates to `self.repo.get_active_by_athlete`.
     - Add `async def update(self, pref_id: uuid.UUID, data: TrainingPreferencesUpdate)` which calls `self.repo.update(pref_id, **data.model_dump(exclude_unset=True))`.
     - Add `async def delete(self, pref_id: uuid.UUID)` which calls `self.repo.delete`.

10. Update `app/services/__init__.py`
    - Objective: Register the new service in the layer package.
    - File: `app/services/__init__.py` [MODIFY]
    - Actions:
      - Import `TrainingPreferencesService` from `app.services.training_preferences_service`.
      - Append it to `__all__`.

## API

11. Add athlete-scoped training-preferences endpoints to `app/api/routes/athletes.py`
    - Objective: Expose athlete-dependent routes under the existing athlete prefix, following the fitness/wellness/activities pattern.
    - File: `app/api/routes/athletes.py` [MODIFY]
    - Actions:
      - Import `TrainingPreferencesRepository`, `TrainingPreferencesService`, `TrainingPreferencesCreate`, `TrainingPreferencesUpdate`, `TrainingPreferencesResponse`.
      - Add `async def get_training_preferences_service(db: AsyncSession = Depends(get_db)) -> TrainingPreferencesService` that instantiates `TrainingPreferencesRepository(db)` and returns `TrainingPreferencesService(repo)`.
      - Add `POST /{athlete_id}/training-preferences` endpoint: accept `TrainingPreferencesCreate`, use `get_training_preferences_service`, inject `athlete_id`, call `service.create()`, return `TrainingPreferencesResponse`.
      - Add `GET /{athlete_id}/training-preferences` endpoint: call `service.list_by_athlete()`, return list of `TrainingPreferencesResponse`.
      - Add `GET /{athlete_id}/training-preferences/active` endpoint: call `service.get_active_by_athlete()`, raise `404` if not found, return `TrainingPreferencesResponse`.

12. Create dedicated router for pref-id endpoints in `app/api/routes/training_preferences.py`
    - Objective: Expose GET / PATCH / DELETE by `pref_id` without needing an `athlete_id` path parameter.
    - File: `app/api/routes/training_preferences.py` [CREATE]
    - Actions:
      - Import `APIRouter`, `Depends`, `HTTPException`, `AsyncSession`, `UUID`, `get_db`, `TrainingPreferencesRepository`, `TrainingPreferencesService`, and the Pydantic schemas.
      - Define `router = APIRouter(prefix="/training-preferences", tags=["training-preferences"])`.
      - Add `GET /{pref_id}` endpoint: call `service.get_by_id()`, raise `404` if not found, return `TrainingPreferencesResponse`.
      - Add `PATCH /{pref_id}` endpoint: accept `TrainingPreferencesUpdate`, call `service.update()`, raise `404` if not found, return `TrainingPreferencesResponse`.
      - Add `DELETE /{pref_id}` endpoint: call `service.delete()`, raise `404` if not found, return `204 No Content`.

13. Register both routers in `app/main.py`
    - Objective: Mount the athlete-scoped routes and the dedicated training-preferences router under the FastAPI application.
    - File: `app/main.py` [MODIFY]
    - Actions:
      - Import `router as training_preferences_router` from `app.api.routes.training_preferences`.
      - Call `app.include_router(training_preferences_router)`.

## Migration

14. Create Alembic migration for `training_preferences`
    - Objective: Generate the table and indexes for the new model.
    - File: `alembic/versions/<autogenerated>_add_training_preferences_table.py` [CREATE — migration generated by p-devops]
    - Actions:
      - Note that `upgrade()` should call `op.create_table('training_preferences', ...)` with all columns matching the ORM model (all fields, types, nullability, defaults, and foreign key to `athletes.id`).
      - Note that `upgrade()` should call `op.create_index(...)` for `ix_training_preferences_athlete_created_at` on columns `athlete_id` and `created_at`.
      - Note that `downgrade()` must drop the index first, then `op.drop_table('training_preferences')`.
