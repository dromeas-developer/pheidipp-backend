# dynamic-context

## Alembic Head
`unknown`

## Recent Migrations
  - `27f66963` — add coach messages table
  - `31ac2338` — phase1c twin initialisation v2
  - `681ac990` — add onboarding complete to athletes
  - `7a2b1c3d` — fix wellness table defaults
  - `4420f93c` — add athlete preferences and training 

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
  - `planned_workout_id` UUID
  - `notes` TEXT
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**athlete_fitness**
  - `id` UUID `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `metric_date` DATE `[NOT NULL]`
  - `tss` FLOAT
  - `atl` FLOAT
  - `ctl` FLOAT
  - `tsb` FLOAT
  - `source` VARCHAR(20) `[NOT NULL]`
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

**athlete_preferences**
  - `id` CHAR(32) `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `sport_background` VARCHAR(30)
  - `years_structured_training` FLOAT
  - `training_time_of_day` VARCHAR(20)
  - `weekly_schedule` JSONB
  - `gps_source` VARCHAR(20)
  - `hr_source` VARCHAR(20)
  - `power_source` VARCHAR(20)
  - `primary_training_platform` VARCHAR(30)
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**athlete_profiles**
  - `athlete_id` UUID `[PK, FK→athletes.id]`
  - `first_name` VARCHAR(100)
  - `last_name` VARCHAR(100)
  - `display_name` VARCHAR(100)
  - `date_of_birth` DATE
  - `gender` VARCHAR(20)
  - `country_code` VARCHAR(2)
  - `timezone` VARCHAR(100)
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
  - `onboarding_complete` BOOLEAN `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**coach_messages**
  - `id` UUID `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `twin_state_id` UUID `[FK→twin_states.id]`
  - `training_block_id` UUID `[FK→training_blocks.id]`
  - `message_type` VARCHAR(30) `[NOT NULL]`
  - `content` TEXT `[NOT NULL]`
  - `generation_metadata` JSONB `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`

**training_blocks**
  - `id` CHAR(32) `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `goal_type` VARCHAR(30)
  - `goal_event_type` VARCHAR(20)
  - `goal_event_name` VARCHAR(200)
  - `goal_event_date` DATE
  - `goal_description` VARCHAR(500)
  - `custom_distance_km` FLOAT
  - `weekly_volume_hours` FLOAT
  - `weekly_volume_km` FLOAT
  - `fitness_level` INTEGER
  - `recent_injury` BOOLEAN
  - `status` VARCHAR(20) `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

**twin_states**
  - `id` UUID `[PK]`
  - `athlete_id` UUID `[FK→athletes.id, NOT NULL]`
  - `athlete_preferences_id` UUID `[FK→athlete_preferences.id, NOT NULL]`
  - `trigger` VARCHAR(30) `[NOT NULL]`
  - `confidence_level` VARCHAR(10) `[NOT NULL]`
  - `data_tier` VARCHAR(10) `[NOT NULL]`
  - `fitness_score` FLOAT `[NOT NULL]`
  - `fatigue_score` FLOAT `[NOT NULL]`
  - `max_hr_estimate` FLOAT `[NOT NULL]`
  - `lt1_hr_estimate` FLOAT `[NOT NULL]`
  - `lt2_hr_estimate` FLOAT `[NOT NULL]`
  - `lt1_pace_estimate` FLOAT
  - `lt2_pace_estimate` FLOAT
  - `structural_capacity_score` FLOAT `[NOT NULL]`
  - `fitness_time_constant` FLOAT `[NOT NULL]`
  - `fatigue_time_constant` FLOAT `[NOT NULL]`
  - `computation_summary` TEXT `[NOT NULL]`
  - `computation_metadata` JSONB `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`

## Foreign Keys & Relationships

**activities**
  - `athlete_id` → `athletes.id`

**athlete_fitness**
  - `athlete_id` → `athletes.id`

**athlete_physiology**
  - `athlete_id` → `athletes.id`

**athlete_preferences**
  - `athlete_id` → `athletes.id`

**athlete_profiles**
  - `athlete_id` → `athletes.id`

**athlete_wellness**
  - `athlete_id` → `athletes.id`

**coach_messages**
  - `athlete_id` → `athletes.id`
  - `twin_state_id` → `twin_states.id`
  - `training_block_id` → `training_blocks.id`

**training_blocks**
  - `athlete_id` → `athletes.id`

**twin_states**
  - `athlete_id` → `athletes.id`
  - `athlete_preferences_id` → `athlete_preferences.id`

## API Endpoints
  - POST / → `app/api/routes/physiology.py:create_physiology`
  - GET /{physiology_id} → `app/api/routes/physiology.py:get_physiology`
  - PATCH /{physiology_id} → `app/api/routes/physiology.py:update_physiology`
  - DELETE /{physiology_id} → `app/api/routes/physiology.py:delete_physiology`
  - POST / → `app/api/routes/fitness.py:create_fitness`
  - GET /{fitness_id} → `app/api/routes/fitness.py:get_fitness`
  - PATCH /{fitness_id} → `app/api/routes/fitness.py:update_fitness`
  - DELETE /{fitness_id} → `app/api/routes/fitness.py:delete_fitness`
  - POST / → `app/api/routes/athletes.py:create_athlete`
  - GET /{athlete_id} → `app/api/routes/athletes.py:get_athlete`
  - PATCH /{athlete_id} → `app/api/routes/athletes.py:update_athlete`
  - PUT /{athlete_id}/profile → `app/api/routes/athletes.py:upsert_profile`
  - GET /{athlete_id}/profile → `app/api/routes/athletes.py:get_profile`
  - GET /{athlete_id}/activities → `app/api/routes/athletes.py:list_athlete_activities`
  - GET /{athlete_id}/wellness → `app/api/routes/athletes.py:list_athlete_wellness`
  - GET /{athlete_id}/fitness → `app/api/routes/athletes.py:list_athlete_fitness`
  - GET /{athlete_id}/physiology → `app/api/routes/athletes.py:list_athlete_physiology` (docs/architecture/definitions/athlete_physiology.md)
  - GET /{athlete_id}/physiology/effective → `app/api/routes/athletes.py:get_effective_physiology`
  - GET /{athlete_id}/preferences → `app/api/routes/athletes.py:get_athlete_preferences`
  - GET /{athlete_id}/training-blocks → `app/api/routes/athletes.py:list_training_blocks`
  - GET /{athlete_id}/training-blocks/active → `app/api/routes/athletes.py:get_active_training_block`
  - POST /{athlete_id}/onboarding → `app/api/routes/athletes.py:onboard_athlete`
  - GET /{athlete_id}/onboarding/status → `app/api/routes/athletes.py:get_onboarding_status`
  - GET / → `app/api/routes/twin_state.py:get_current_twin_state`
  - GET /history → `app/api/routes/twin_state.py:get_twin_state_history`
  - GET /{block_id} → `app/api/routes/training_blocks.py:get_block`
  - PATCH /{block_id} → `app/api/routes/training_blocks.py:update_block`
  - POST / → `app/api/routes/wellness.py:create_wellness`
  - GET /{wellness_id} → `app/api/routes/wellness.py:get_wellness`
  - PATCH /{wellness_id} → `app/api/routes/wellness.py:update_wellness`
  - ... and 12 more

## Modules

**app/api/**
  - `__init__.py`
  - `utils.py`

**app/models/**
  - `__init__.py`
  - `activity.py`
  - `athlete.py`
  - `athlete_preferences.py`
  - `athlete_profile.py`
  - `coach_message.py`
  - `enums.py`
  - `fitness.py`
  - `physiology.py`
  - `training_block.py`
  - `twin_state.py`
  - `wellness.py`

**app/schemas/**
  - `__init__.py`
  - `activity.py`
  - `athlete.py`
  - `athlete_preferences.py`
  - `athlete_profile.py`
  - `coach_message.py`
  - `fitness.py`
  - `onboarding.py`
  - `physiology.py`
  - `training_block.py`
  - `twin_state.py`
  - `wellness.py`

**app/services/**
  - `__init__.py`
  - `activity_service.py`
  - `athlete_preferences_service.py`
  - `athlete_profile_service.py`
  - `athlete_service.py`
  - `base_service.py`
  - `coach_message_service.py`
  - `first_message_brief_builder.py`
  - `fitness_service.py`
  - `health_service.py`
  - `onboarding_service.py`
  - `physiology_service.py`
  - `training_block_service.py`
  - `twin_initialisation_service.py`
  - `twin_state_service.py`
  - `wellness_service.py`

**app/repositories/**
  - `__init__.py`
  - `activity_repository.py`
  - `athlete_preferences_repository.py`
  - `athlete_profile_repository.py`
  - `athlete_repository.py`
  - `base_repository.py`
  - `coach_message_repository.py`
  - `fitness_repository.py`
  - `physiology_repository.py`
  - `training_block_repository.py`
  - `twin_state_repository.py`
  - `wellness_repository.py`

**app/worker/**
  - `__init__.py`

**app/agents/**
  - `__init__.py`
  - `first_message_agent.py`

**app/core/**
  - `__init__.py`
  - `llm.py`
  - `security.py`
  - `telemetry.py`
  - `unit_of_work.py`

## Background Jobs (ARQ)
  (none)

## LangGraph Agents
  (none)
