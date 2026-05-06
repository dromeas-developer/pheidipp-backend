<!-- auto-generated 2026-05-06 16:26 — do not edit manually -->
<!-- run `make context` or `python scripts/update_context.py` to refresh -->

# Dynamic Project Context

## Alembic Head
`34434d79ba41`

## Recent Migrations
  - `e2b4c9f9` — add athlete physiology table
  - `34434d79` — add athlete wellness hypertable
  - `29c40204` — add activities table
  - `122ca2b8` — add athlete and profile tables
  - `c39b83c0` — initial schema

## Database Schema

**activities**
  - `id` UUID `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `activity_type` VARCHAR(20) `[NOT NULL]`
  - `title` VARCHAR(255)
  - `description` TEXT
  - `started_at` DATETIME `[NOT NULL]`
  - `finished_at` DATETIME `[NOT NULL]`
  - `duration_seconds` INTEGER
  - `perceived_effort` VARCHAR(20)
  - `avg_heart_rate` INTEGER
  - `max_heart_rate` INTEGER
  - `avg_speed_m_per_s` FLOAT
  - `max_speed_m_per_s` FLOAT
  - `avg_power` INTEGER
  - `max_power` INTEGER
  - `distance_meters` FLOAT
  - `elevation_gain_meters` FLOAT
  - `elevation_loss_meters` FLOAT
  - `calories` INTEGER
  - `source` VARCHAR(50)
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**athlete_physiology**
  - `id` UUID `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `ftp` INTEGER
  - `lt1` INTEGER
  - `lt2` INTEGER
  - `vo2_max` FLOAT
  - `max_hr` INTEGER
  - `source` VARCHAR(20) `[NOT NULL]`
  - `effective_from` DATE `[NOT NULL]`
  - `effective_to` DATE
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**athlete_profiles**
  - `athlete_id` UUID `[PK, FK→athletes.id]`
  - `first_name` VARCHAR(100)
  - `last_name` VARCHAR(100)
  - `display_name` VARCHAR(100)
  - `date_of_birth` DATE
  - `gender` VARCHAR(20)
  - `country_code` VARCHAR(5)
  - `timezone` VARCHAR(50)
  - `language_code` VARCHAR(5)
  - `unit_preference` VARCHAR(20) `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**athlete_wellness**
  - `id` UUID `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `metric_date` DATE `[NOT NULL]`
  - `sleep_total` INTEGER
  - `sleep_light` INTEGER
  - `sleep_deep` INTEGER
  - `sleep_rem` INTEGER
  - `sleep_awake` INTEGER
  - `resting_hr` INTEGER
  - `hrv` INTEGER
  - `weight` FLOAT
  - `source` VARCHAR(20) `[NOT NULL]`
  - `timezone` VARCHAR(100) `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**athletes**
  - `id` UUID `[PK]`
  - `email` VARCHAR(255) `[NOT NULL]`
  - `hashed_password` VARCHAR(255)
  - `status` VARCHAR(20) `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

## Foreign Keys & Relationships

**activities**
  - `athlete_id` → `athletes.id`

**athlete_physiology**
  - `athlete_id` → `athletes.id`

**athlete_profiles**
  - `athlete_id` → `athletes.id`

**athlete_wellness**
  - `athlete_id` → `athletes.id`

## API Endpoints
  - POST / → `app/api/routes/physiology.py:create_physiology`
  - GET / → `app/api/routes/physiology.py:list_physiology`
  - GET /{physiology_id} → `app/api/routes/physiology.py:get_physiology`
  - GET /effective/{target_date} → `app/api/routes/physiology.py:get_effective_physiology`
  - PATCH /{physiology_id} → `app/api/routes/physiology.py:update_physiology`
  - DELETE /{physiology_id} → `app/api/routes/physiology.py:delete_physiology`
  - POST / → `app/api/routes/athletes.py:create_athlete`
  - GET /{athlete_id} → `app/api/routes/athletes.py:get_athlete`
  - PATCH /{athlete_id} → `app/api/routes/athletes.py:update_athlete`
  - PUT /{athlete_id}/profile → `app/api/routes/athletes.py:upsert_profile`
  - GET /{athlete_id}/profile → `app/api/routes/athletes.py:get_profile`
  - POST / → `app/api/routes/wellness.py:create_wellness`
  - GET /{wellness_id} → `app/api/routes/wellness.py:get_wellness`
  - GET /athletes/{athlete_id}/wellness → `app/api/routes/wellness.py:list_athlete_wellness`
  - PATCH /{wellness_id} → `app/api/routes/wellness.py:update_wellness`
  - DELETE /{wellness_id} → `app/api/routes/wellness.py:delete_wellness`
  - GET /live → `app/api/routes/health.py:live`
  - GET /ready → `app/api/routes/health.py:ready`
  - POST / → `app/api/routes/activities.py:create_activity`
  - GET /{activity_id} → `app/api/routes/activities.py:get_activity`
  - GET /athletes/{athlete_id}/activities → `app/api/routes/activities.py:list_athlete_activities`
  - PATCH /{activity_id} → `app/api/routes/activities.py:update_activity`
  - DELETE /{activity_id} → `app/api/routes/activities.py:delete_activity`

## Modules

**app/api/**
  - `__init__.py`
  - `utils.py`

**app/models/**
  - `__init__.py`
  - `activity.py`
  - `athlete.py`
  - `enums.py`
  - `physiology.py`
  - `wellness.py`

**app/schemas/**
  - `__init__.py`
  - `activity.py`
  - `athlete.py`
  - `physiology.py`
  - `wellness.py`

**app/services/**
  - `__init__.py`
  - `activity_service.py`
  - `athlete_service.py`
  - `base_service.py`
  - `health_service.py`
  - `physiology_service.py`
  - `wellness_service.py`

**app/repositories/**
  - `__init__.py`
  - `activity_repository.py`
  - `athlete_repository.py`
  - `base_repository.py`
  - `physiology_repository.py`
  - `wellness_repository.py`

**app/worker/**
  - `__init__.py`

**app/agents/**
  - `__init__.py`

**app/core/**
  - `__init__.py`
  - `security.py`

## Background Jobs (ARQ)
  (none)

## LangGraph Agents
  (none)
