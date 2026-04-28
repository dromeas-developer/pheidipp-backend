# Athlete and athlete-profile plan with enums

**Session ID:** ses_234d7491bffel4rI0SpYiZSJ2o
**Created:** 4/26/2026, 2:58:56 PM
**Updated:** 4/26/2026, 3:06:41 PM

---

1. Modernize Declarative Base and Define Domain Enums
   - Objective: Upgrade to SQLAlchemy 2.0 `DeclarativeBase` and establish the single source of truth for all athlete-related enums.
   - Files:
     - `app/db/base.py` [MODIFY]
     - `app/models/enums.py` [CREATE]
   - Actions:
     - Replace `app/db/base.py` contents with SQLAlchemy 2.0 class-style base:
       ```python
       from sqlalchemy.orm import DeclarativeBase
       class Base(DeclarativeBase):
           pass
       ```
     - Create `app/models/enums.py`. Store enums here as standard Python `(str, Enum)` subclasses. All application and schema layers import from this file only.
     - `AthleteStatus`: `ONBOARDING = "onboarding"`, `ACTIVE = "active"`, `INACTIVE = "inactive"`, `SUSPENDED = "suspended"`.
     - `Gender`: `MALE = "male"`, `FEMALE = "female"`, `NON_BINARY = "non_binary"`, `PREFER_NOT_TO_SAY = "prefer_not_to_say"`.
     - `UnitPreference`: `METRIC = "metric"`, `IMPERIAL = "imperial"`.
     - `CountryCode`: ISO 3166-1 alpha-2 codes; member name and value are identical uppercase strings (e.g., `AF = "AF"` through `ZW = "ZW"`). Include all valid codes.
     - `LanguageCode`: ISO 639-1 codes; member name and value are identical lowercase strings (e.g., `aa = "aa"` through `zu = "zu"`). Include all valid codes.
     - `Timezone`: canonical IANA timezone names; derive the Python identifier by replacing `/` and `-` with `_` (value retains original string, e.g., `Europe_Lisbon = "Europe/Lisbon"`). Include all canonical zones.
     - Enums are **accessed** via `from app.models.enums import <EnumName>`. In the ORM they map to `String` columns via `Enum(TheEnum, native_enum=False, length=...)`. No native PostgreSQL ENUM DDL is created.

2. Create Athlete and AthleteProfile ORM Models
   - Objective: Define the athlete account and profile extension tables with a strict 1:1 relationship and no health/wellness metrics.
   - Files:
     - `app/models/athlete.py` [CREATE]
     - `app/models/__init__.py` [MODIFY]
   - Actions:
     - Create `app/models/athlete.py` with imports for `uuid`, `datetime`, `typing.Optional`, `sqlalchemy` types (`UUID`, `String`, `DateTime`, `Date`, `ForeignKey`, `Enum as SAEnum`, `func`, `text`), and `sqlalchemy.orm` (`Mapped`, `mapped_column`, `relationship`).
     - `class Athlete(Base)`, `__tablename__ = "athletes"`:
       - `id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))`
       - `email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)`
       - `hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)`
       - `status: Mapped[AthleteStatus] = mapped_column(SAEnum(AthleteStatus, native_enum=False, length=20), default=AthleteStatus.ONBOARDING)`
       - `created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())`
       - `updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`
       - `profile: Mapped[Optional["AthleteProfile"]] = relationship(back_populates="athlete", uselist=False)`
     - `class AthleteProfile(Base)`, `__tablename__ = "athlete_profiles"`:
       - `athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)`
       - `first_name: Mapped[Optional[str]] = mapped_column(String(100))`
       - `last_name: Mapped[Optional[str]] = mapped_column(String(100))`
       - `display_name: Mapped[Optional[str]] = mapped_column(String(100))`
       - `date_of_birth: Mapped[Optional[datetime.date]] = mapped_column(Date)`
       - `gender: Mapped[Optional[Gender]] = mapped_column(SAEnum(Gender, native_enum=False, length=20))`
       - `country_code: Mapped[Optional[CountryCode]] = mapped_column(SAEnum(CountryCode, native_enum=False, length=5))`
       - `timezone: Mapped[Optional[Timezone]] = mapped_column(SAEnum(Timezone, native_enum=False, length=50))`
       - `language_code: Mapped[Optional[LanguageCode]] = mapped_column(SAEnum(LanguageCode, native_enum=False, length=5))`
       - `unit_preference: Mapped[UnitPreference] = mapped_column(SAEnum(UnitPreference, native_enum=False, length=20), default=UnitPreference.METRIC)`
       - `created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())`
       - `updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`
       - `athlete: Mapped["Athlete"] = relationship(back_populates="profile")`
     - Modify `app/models/__init__.py` to export `Athlete` and `AthleteProfile`.

3. Create Pydantic Request/Response Schemas
   - Objective: Define Pydantic v2 contracts for athlete and profile CRUD, reusing the same domain enums for input validation.
   - Files:
     - `app/schemas/athlete.py` [CREATE]
     - `app/schemas/__init__.py` [MODIFY]
   - Actions:
     - Create `app/schemas/athlete.py`:
       - `class AthleteBase(BaseModel)`: `email: EmailStr`
       - `class AthleteCreate(AthleteBase)`: `password: Optional[str] = Field(default=None, min_length=8)`
       - `class AthleteUpdate(BaseModel)`: `status: Optional[AthleteStatus] = None`; `password: Optional[str] = Field(default=None, min_length=8)`
       - `class AthleteResponse(AthleteBase)`: `id: uuid.UUID`, `status: AthleteStatus`, `created_at: datetime.datetime`, `updated_at: datetime.datetime`. Set `model_config = ConfigDict(from_attributes=True)`.
       - `class AthleteProfileBase(BaseModel)`: `first_name`, `last_name`, `display_name` (each `Optional[str]` with `max_length=100`), `date_of_birth: Optional[datetime.date]`, `gender: Optional[Gender]`, `country_code: Optional[CountryCode]`, `timezone: Optional[Timezone]`, `language_code: Optional[LanguageCode]`, `unit_preference: Optional[UnitPreference] = UnitPreference.METRIC`.
       - `class AthleteProfileCreate(AthleteProfileBase)`: inherits all optional fields.
       - `class AthleteProfileUpdate(BaseModel)`: same fields as `AthleteProfileBase` but every field is `Optional` and defaults to `None` (no required defaults).
       - `class AthleteProfileResponse(AthleteProfileBase)`: `athlete_id: uuid.UUID`, `created_at: datetime.datetime`, `updated_at: datetime.datetime`. Set `model_config = ConfigDict(from_attributes=True)`.
       - `class AthleteWithProfileResponse(AthleteResponse)`: `profile: Optional[AthleteProfileResponse] = None`
     - Modify `app/schemas/__init__.py` to export all classes.

4. Create Athlete Repository and Service
   - Objective: Implement async data access (repositories) and business logic (service) for athlete and profile operations.
   - Files:
     - `app/repositories/athlete_repository.py` [CREATE]
     - `app/repositories/__init__.py` [MODIFY]
     - `app/services/athlete_service.py` [CREATE]
     - `app/services/__init__.py` [MODIFY]
   - Actions:
     - `AthleteRepository(BaseRepository[Athlete])`:
       - `def __init__(self, session: AsyncSession)` → `super().__init__(session, Athlete)`
       - `async def get_by_email(self, email: str) -> Athlete | None`
     - `AthleteProfileRepository(BaseRepository[AthleteProfile])`:
       - `def __init__(self, session: AsyncSession)` → `super().__init__(session, AthleteProfile)`
       - `async def get_by_athlete_id(self, athlete_id: uuid.UUID) -> AthleteProfile | None`
     - `AthleteService` (plain class, no forced `BaseService` inheritance):
       - `def __init__(self, athlete_repo: AthleteRepository, profile_repo: AthleteProfileRepository)`
       - `async def create_athlete(self, data: AthleteCreate) -> Athlete`: hash the plain password before persisting, then create via `athlete_repo.create(...)`.
       - `async def get_athlete(self, athlete_id: uuid.UUID) -> Athlete | None`
       - `async def get_athlete_with_profile(self, athlete_id: uuid.UUID) -> Athlete | None`: eager-load `profile` via `select(Athlete).options(selectinload(Athlete.profile)).where(Athlete.id == athlete_id)`.
       - `async def update_athlete(self, athlete_id: uuid.UUID, data: AthleteUpdate) -> Athlete | None`: build a dict of non-None fields (re-hash password if provided) and call `athlete_repo.update`.
       - `async def get_profile(self, athlete_id: uuid.UUID) -> AthleteProfile | None`
       - `async def upsert_profile(self, athlete_id: uuid.UUID, data: AthleteProfileUpdate) -> AthleteProfile`: fetch existing profile; if found call `profile_repo.update`, else call `profile_repo.create`.
     - Update `app/repositories/__init__.py` and `app/services/__init__.py` to export the new classes.

5. Create Athlete API Routes and Database Migration
   - Objective: Expose REST endpoints for athlete/profile management and generate the corresponding Alembic migration.
   - Files:
     - `app/api/routes/athletes.py` [CREATE]
     - `app/main.py` [MODIFY]
   - Actions:
     - Create `app/api/routes/athletes.py` with `router = APIRouter(prefix="/athletes", tags=["athletes"])`:
       - `POST /`: `async def create_athlete(payload: AthleteCreate, db: AsyncSession = Depends(get_db)) -> AthleteResponse`
         - Instantiate repositories and service inside the handler; delegate to `service.create_athlete`; return `AthleteResponse.model_validate(result)`.
       - `GET /{athlete_id}`: `async def get_athlete(athlete_id: UUID, db: AsyncSession = Depends(get_db)) -> AthleteWithProfileResponse`
       - `PATCH /{athlete_id}`: `async def update_athlete(athlete_id: UUID, payload: AthleteUpdate, db: AsyncSession = Depends(get_db)) -> AthleteResponse`
       - `PUT /{athlete_id}/profile`: `async def upsert_profile(athlete_id: UUID, payload: AthleteProfileUpdate, db: AsyncSession = Depends(get_db)) -> AthleteProfileResponse`
       - `GET /{athlete_id}/profile`: `async def get_profile(athlete_id: UUID, db: AsyncSession = Depends(get_db)) -> AthleteProfileResponse`
     - Modify `app/main.py` to import and `app.include_router(...)` the new athletes router.
     - Run `scripts/db-revision.sh "add_athlete_and_profile_tables"` to generate the migration. Verify it produces `op.create_table('athletes', ...)` and `op.create_table('athlete_profiles', ...)` with correct columns, indexes, and the foreign key. Then apply with `scripts/db-upgrade.sh`.
