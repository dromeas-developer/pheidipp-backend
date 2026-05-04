# Fix Plan: Daily Wellness Metrics Validation Issues

## Models

1. Fix source field and constraint name in AthleteWellness model
   - **Objective:** Use SAEnum for source field and correct constraint name
   - **File:** `app/models/wellness.py` [MODIFY]
   - **Actions:**
     - Import SAEnum from sqlalchemy
     - Change `source` field from `mapped_column(String(20), nullable=False)` to `mapped_column(SAEnum(WellnessSource, native_enum=False, length=20), nullable=False)`
     - Change unique constraint name from `uq_athlete_metric_date` to `uq_athlete_wellness_date`

## Repositories

2. Add wellness_id-based methods to WellnessRepository
   - **Objective:** Support CRUD by wellness_id (primary key) as per plan
   - **File:** `app/repositories/wellness_repository.py` [MODIFY]
   - **Actions:**
     - Keep existing composite key methods for internal use
     - Add `async def get_by_id(self, wellness_id: UUID) -> Optional[AthleteWellness]` using parent's get_by_id pattern
     - Add `async def update_by_id(self, wellness_id: UUID, **kwargs) -> Optional[AthleteWellness]`
     - Add `async def delete_by_id(self, wellness_id: UUID) -> bool`
     - Refactor `update()` method to use `update_by_id` internally, keeping composite key support

## Services

3. Update WellnessService to use wellness_id primary key
   - **Objective:** Align service methods with plan specification
   - **File:** `app/services/wellness_service.py` [MODIFY]
   - **Actions:**
     - Change `get_wellness(self, athlete_id: UUID, metric_date: date)` to `get_wellness(self, wellness_id: UUID)`
     - Change `update_wellness(self, athlete_id: UUID, metric_date: date, data: WellnessUpdate)` to `update_wellness(self, wellness_id: UUID, data: WellnessUpdate)`
     - Change `delete_wellness(self, athlete_id: UUID, metric_date: date)` to `delete_wellness(self, wellness_id: UUID)`
     - Update all method bodies to use wellness_id instead of composite key lookup
     - Keep `create_wellness` unchanged
     - Keep `list_athlete_wellness` unchanged

## API

4. Fix API endpoints to use wellness_id as per plan
   - **Objective:** Align endpoints with plan specification - GET/UPDATE/DELETE by wellness_id
   - **File:** `app/api/routes/wellness.py` [MODIFY]
   - **Actions:**
     - Change `GET /athletes/{athlete_id}/wellness/{metric_date}` to `GET /{wellness_id}`
     - Change `PATCH /athletes/{athlete_id}/wellness/{metric_date}` to `PATCH /{wellness_id}`
     - Change `DELETE /athletes/{athlete_id}/wellness/{metric_date}` to `DELETE /{wellness_id}`
     - Update get_wellness endpoint to call service.get_wellness(wellness_id)
     - Update update_wellness endpoint to call service.update_wellness(wellness_id, payload)
     - Update delete_wellness endpoint to call service.delete_wellness(wellness_id)
     - Keep `GET /athletes/{athlete_id}/wellness` (list) endpoint unchanged
     - Keep `POST /` (create) endpoint unchanged

## Migration

5. Update migration for constraint name change
   - **Objective:** Update migration to reflect corrected constraint name
   - **File:** `migrations/versions/<generated>.py` [MODIFY]
   - **Actions:**
     - Update unique constraint name in migration from `uq_athlete_metric_date` to `uq_athlete_wellness_date`