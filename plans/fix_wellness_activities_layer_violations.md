# Fix Wellness and Activities Router Layer Violations

## Problem Statement

Both `app/api/routes/wellness.py` and `app/api/routes/activities.py` violate stack-truth layer rules:
- **Route handlers MUST NOT call repositories directly for any reason, including counts.**

## Plan

### Services

1. **Add count method to `ActivityService`**
   - File: `app/services/activity_service.py` [MODIFY]
   - Objective: Move the direct SQL count from the activities router into the service layer.
   - Actions:
     - Add a new async method `count_by_athlete(self, athlete_id: UUID) -> int`.
     - Implement the count by delegating to `self.activity_repo.session.execute` with a `select(func.count()).where(Activity.athlete_id == athlete_id)` query, or add a `count_by_athlete` method to `ActivityRepository` and call it from the service. Prefer adding it to the repository first, then exposing it through the service.

2. **Expose count through `WellnessService`**
   - File: `app/services/wellness_service.py` [MODIFY]
   - Objective: Provide a service-layer method for counting wellness records so the router does not call the repository directly.
   - Actions:
     - Add a new async method `count_by_athlete(self, athlete_id: UUID) -> int`.
     - Delegate to `self.wellness_repo.count_by_athlete(athlete_id)`.

### Repositories

3. **Add `count_by_athlete` to `ActivityRepository`**
   - File: `app/repositories/activity_repository.py` [MODIFY]
   - Objective: Centralize the athlete-specific count query.
   - Actions:
     - Add a new async method `count_by_athlete(self, athlete_id: UUID) -> int`.
     - Use `select(func.count()).where(self.model.athlete_id == athlete_id)` and return the scalar result.

### API

4. **Refactor `app/api/routes/activities.py` to use dependency injection**
   - File: `app/api/routes/activities.py` [MODIFY]
   - Objective: Eliminate all direct repository imports, instantiation, and SQL queries from route handlers.
   - Actions:
     - Remove imports for `ActivityRepository` and `AthleteRepository`.
     - Add an import for `ActivityService` only.
     - Define a new `get_activity_service(db: AsyncSession = Depends(get_db)) -> ActivityService` dependency function that creates `ActivityRepository(db)`, `AthleteRepository(db)`, and returns `ActivityService(activity_repo, athlete_repo)`.
     - Update every route handler to accept `service: ActivityService = Depends(get_activity_service)`.
     - Remove all inline repository instantiation (`activity_repo = ActivityRepository(db)`, `athlete_repo = AthleteRepository(db)`, `service = ActivityService(...)`).
     - In `list_athlete_activities`, replace the inline `count_query` block with `total = await service.count_by_athlete(athlete_id)`.

5. **Refactor `app/api/routes/wellness.py` to use dependency injection**
   - File: `app/api/routes/wellness.py` [MODIFY]
   - Objective: Eliminate all direct repository imports, instantiation, and repository method calls from route handlers.
   - Actions:
     - Remove imports for `WellnessRepository` and `AthleteRepository`.
     - Add an import for `WellnessService` only.
     - Define a new `get_wellness_service(db: AsyncSession = Depends(get_db)) -> WellnessService` dependency function that creates `WellnessRepository(db)`, `AthleteRepository(db)`, and returns `WellnessService(wellness_repo, athlete_repo)`.
     - Update every route handler to accept `service: WellnessService = Depends(get_wellness_service)`.
     - Remove all inline repository instantiation (`wellness_repo = WellnessRepository(db)`, `athlete_repo = AthleteRepository(db)`, `service = WellnessService(...)`).
     - In `list_athlete_wellness`, replace `total = await wellness_repo.count_by_athlete(athlete_id)` with `total = await service.count_by_athlete(athlete_id)`.

## Validation Criteria

- `app/api/routes/wellness.py` contains zero imports from `app.repositories`.
- `app/api/routes/activities.py` contains zero imports from `app.repositories`.
- Neither router instantiates a repository class inside a route handler.
- Neither router executes raw SQLAlchemy queries for counts.