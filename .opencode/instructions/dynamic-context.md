<!-- auto-generated 2026-04-29 00:03 — do not edit manually -->
<!-- run `make context` or `python scripts/update_context.py` to refresh -->

# Dynamic Project Context

## Alembic Head
`122ca2b82d38 (head)`

## Recent Migrations
  - `122ca2b8` — add athlete and profile tables
  - `c39b83c0` — initial schema

## Database Schema

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

**athletes**
  - `id` UUID `[PK]`
  - `email` VARCHAR(255) `[NOT NULL]`
  - `hashed_password` VARCHAR(255)
  - `status` VARCHAR(20) `[NOT NULL]`
  - `created_at` DATETIME `[NOT NULL]`
  - `updated_at` DATETIME `[NOT NULL]`

## API Endpoints
  - POST / → `app/api/routes/athletes.py:create_athlete`
  - GET /{athlete_id} → `app/api/routes/athletes.py:get_athlete`
  - PATCH /{athlete_id} → `app/api/routes/athletes.py:update_athlete`
  - PUT /{athlete_id}/profile → `app/api/routes/athletes.py:upsert_profile`
  - GET /{athlete_id}/profile → `app/api/routes/athletes.py:get_profile`
  - GET /live → `app/api/routes/health.py:live`
  - GET /ready → `app/api/routes/health.py:ready`

## Modules

**app/api/**
  - `utils.py`

**app/models/**
  - `athlete.py`
  - `enums.py`

**app/schemas/**
  - `athlete.py`

**app/services/**
  - `athlete_service.py`
  - `base_service.py`
  - `health_service.py`

**app/repositories/**
  - `athlete_repository.py`
  - `base_repository.py`

**app/core/**
  - `security.py`

## Background Jobs (ARQ)
  (none)

## LangGraph Agents
  (none)
