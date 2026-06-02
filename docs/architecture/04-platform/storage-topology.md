# Storage Topology — Database, Object Storage, and Cache

## Purpose
- Defines what lives where, why, and what consistency guarantees each layer provides
- Single authoritative reference for storage decisions

## Storage Systems

### PostgreSQL (Primary Database)
All relational entity data. Strong consistency. Indefinite retention.

**Schema conventions:**
- UUIDs for all primary keys
- `created_at` on every table (immutable after insert)
- `updated_at` on mutable tables
- Soft-delete via status fields (never hard DELETE on domain entities)
- JSONB for semi-structured fields (weekly_schedule, quality_flags, personalisation models)

**Tables by retention category:**

*Append-only (no UPDATE except version/status fields):*
- `twin_states`, `coaching_messages`, `generation_events`
- `objective_updates`, `cycle_phase_logs`
- `physiological_segments` (+ `superseded_at`)
- `race_predictions`, `adaptation_observations`
- `checkpoints` (status + completion fields mutable)

*Mutable:*
- `athletes`, `athlete_profiles`, `athlete_preferences`
- `athlete_auths` (credentials encrypted; mutable for token refresh and last_login_at)
- `training_blocks` (status only), `training_plans` (status + superseded_at)
- `planned_sessions` (status + linkage fields)
- `generated_workouts`, `workout_steps` (immutable after creation)
- `athlete_wellness` (upsert/additive merge)
- `athlete_wellness_baselines` (overwritten on recompute)
- `athlete_integrations` (sync cursor)
- `workout_library_entries` (acceptance counters)

### Object Storage (S3-compatible)
Large binary data. Eventual consistency. Indefinite retention.

```
fit-files/{athlete_id}/{activity_date}/{uuid}.fit        → raw FIT files (immutable)
cleaned-streams/{athlete_id}/{activity_id}/stream.gz      → cleaned sensor streams
models/hmm/population_v1.pkl                              → HMM population model
models/hmm/athlete_{id}_v1.pkl                            → per-athlete HMM models
```

**Invariant:** Raw FIT files are never overwritten or deleted. They are the reprocessing anchor.

### Redis (Cache + Queue)
- **Queue backend:** Celery/ARQ task queues and dead-letter queue
- **Cache:** short-lived; session tokens, rate limiting, frequently-read TwinState (latest only)

```typescript
// Cache strategy for TwinState (most frequently read):
// Key: twin_state:latest:{athlete_id}
// TTL: 60 seconds (refreshed on every TwinState insert)
// Fallback: PostgreSQL query on cache miss
```

## Key Design Decisions

**Why JSONB for personalisation models:** `AthleteProfile.gap_curve_model`, `banister_constants`, `cycle_personal_model`, `weather_response_model` are infrequently read (only during workout generation and plan generation), never queried across athletes, and have evolving schemas. JSONB avoids migrations as these models gain fields.

**Why object storage for cleaned streams:** Cleaned time-series data is large (typically 5-50MB per session) and rarely accessed (only during segmentation and reprocessing). Storing in PostgreSQL BYTEA would balloon the DB size; object storage is cheaper and more appropriate for large binary data.

**Why Redis for the task queue (not PostgreSQL):** PostgreSQL-backed queues (using SELECT FOR UPDATE SKIP LOCKED) are viable but add contention to the primary database. Redis provides lower-latency queue operations and native pub/sub for event routing without DB load.

## Index Strategy

```sql
-- High-frequency queries and their indexes:

-- Latest TwinState (most common query in the system)
CREATE INDEX idx_twin_states_athlete_created ON twin_states (athlete_id, created_at DESC);

-- Upcoming planned sessions
CREATE INDEX idx_planned_sessions_plan_date ON planned_sessions (training_plan_id, target_date);
CREATE INDEX idx_planned_sessions_status_date ON planned_sessions (athlete_id, status, target_date)
  WHERE status IN ('pending', 'generated');

-- Active training goal (one-per-athlete partial unique index)
CREATE UNIQUE INDEX idx_training_goals_active ON training_goals (athlete_id)
  WHERE status = 'active';

-- Recent activities for twin recalibration (rolling 90-day window)
CREATE INDEX idx_activities_athlete_date ON activities (athlete_id, activity_date DESC)
  WHERE calibration_eligible = true;

-- Latest PhysiologicalSegment (most recent non-superseded)
CREATE INDEX idx_phys_segments_activity_version ON physiological_segments
  (activity_id, segmentation_version, superseded_at NULLS FIRST);

-- Wellness baseline lookup
CREATE UNIQUE INDEX idx_wellness_baselines_signal ON athlete_wellness_baselines
  (athlete_id, signal);

-- Auth provider lookup (one per athlete per provider)
CREATE UNIQUE INDEX idx_athlete_auths_provider ON athlete_auths
  (athlete_id, provider);

-- OAuth account lookup (nullable; only set for OAuth providers)
CREATE INDEX idx_athlete_auths_provider_user ON athlete_auths
  (provider, provider_user_id)
  WHERE provider_user_id IS NOT NULL;
```

## Cross-References
- Append-only invariant: `00-foundations/principles.md`
- Versioning and supersession: `04-platform/versioning-and-reprocessing.md`
- Async task queue: `04-platform/async-pipeline.md`
