# app/models/

## Purpose
ORM schema source of truth for Pheidipp. Every table is declared as a
SQLAlchemy `Base` subclass here; alembic autogenerate derives migrations
from these definitions. No business logic or service-layer decisions —
this layer owns only table shape, constraints, and foreign-key topology.

## Contents
### Identity & Auth
| File | Responsibility |
|---|---|
| `athlete.py` | `Athlete` — root identity entity with case-insensitive email uniqueness |
| `athlete_auth.py` | `AthleteAuth` — authentication credentials per athlete-provider pair with partial-unique primary constraint |
| `refresh_token.py` | `RefreshToken` — append-only revocation ledger with self-referencing rotation chain |

### Athlete Profile & Physiology
| File | Responsibility |
|---|---|
| `athlete_fitness.py` | `AthleteFitness` — Banister-model rolling fitness/fatigue scores with dimensional JSONB and `form = fitness - fatigue` CHECK invariants |
| `athlete_physiology.py` | `AthletePhysiology` — current posterior estimates per parameter (LT1, LT2, CP, VO2max, max HR) |
| `athlete_preferences.py` | `AthletePreferences` — mutable training configuration (hardware, schedule, platform) with `infer_data_tier` helper |
| `athlete_profile.py` | `AthleteProfile` — stable demographic identity with fitted personalisation model JSONBs |
| `physiology_measurement.py` | `PhysiologyMeasurement` — append-only observation record per (athlete, parameter, source) tuple |

### Training Plan
| File | Responsibility |
|---|---|
| `checkpoint.py` | `Checkpoint` — planned assessment point with one-to-one FK to PlannedSession |
| `planned_session.py` | `PlannedSession` — workout operability row with denormalized training_plan_id and slot/date uniqueness |
| `regeneration_task.py` | `RegenerationTask` — coach-proposed date change with 14-day TTL and pending-confirmation lifecycle |
| `secondary_event.py` | `SecondaryEvent` — B-race / C-race storage linked to a TrainingGoal |
| `training_goal.py` | `TrainingGoal` — goal-directed training period with partial-unique active-per-athlete constraint |
| `training_plan.py` | `TrainingPlan` — periodised training structure with phase definitions, weekly distributions, and checkpoint schedule |
| `weekly_plan.py` | `WeeklyPlan` + `WeeklySession` — single-week schedule with adjusted intent, execution counters, and child sessions |

### Activity & Workout
| File | Responsibility |
|---|---|
| `activity.py` | `Activity` — lean observation index with signal-availability flags, load scores, and deduplication |
| `generated_workout.py` | `GeneratedWorkout` — day-of workout per (planned_session, generation_date) with two-column target structure |
| `raw_sensor_stream.py` | `RawSensorStream` — append-only metadata index for cleaned sensor streams in object storage |
| `twin_state.py` | `TwinState` — append-only snapshot of fitness/fatigue/thresholds/readiness inline with the producing activity |
| `workout_step.py` | `WorkoutStep` — one ordered segment inside a GeneratedWorkout with three-layer type hierarchy |

### Platform
| File | Responsibility |
|---|---|
| `coaching_message.py` | `CoachingMessage` — append-only LLM-generated coach message with partial-unique deduplication indexes |
| `enums.py` | All closed-ontology enums shared across models (~45 enum classes in three phase groups) |
| `generation_event.py` | `GenerationEvent` — append-only LLM API call audit log with token counts and failure-reason consistency CHECK |
| `system_event.py` | `SystemEvent` + `SystemEventOutbox` — append-only event log with mutable outbox for at-least-once delivery |

## Architecture Notes
- All enum columns use `native_enum=False` — values stored as strings, enabling enum evolution without
  PostgreSQL DDL on the enum type itself.
- `values_callable=enum_str_values` from `_enum_helpers.py` replaces bare lambdas so basedpyright
  strict-mode type checking passes on every `SAEnum` column definition.
- Append-only tables (RefreshToken, TwinState, CoachingMessage, GenerationEvent, SystemEvent,
  PhysiologyMeasurement, RawSensorStream, WorkoutStep, GeneratedWorkout) carry no `updated_at`
  column and their repository contracts restrict to INSERT-only operations.
- Partial unique indexes with `postgresql_where` enforce conditional uniqueness — used for
  deduplication (`Activity.external_id`), one-active-per-athlete (`TrainingGoal.status`),
  and single-primary-auth-provider (`AthleteAuth.is_primary`) invariants.
- `PlannedSession.training_plan_id` is denormalized from `WeeklyPlan` — queries for current-plan
  sessions MUST join through `WeeklyPlan.training_plan_id` as the source of truth.

## Cross-References
- [ADR-004: Event Persistence and Outbox](../../docs/architecture/04-platform/system-event.md) — `system_event.py`
- [Entity Architecture: Athlete](../../docs/architecture/01-entities/athlete.md) — `athlete.py`
- [Entity Architecture: Training Goal](../../docs/architecture/01-entities/training-goal.md) — `training_goal.py`, `secondary_event.py`, `regeneration_task.py`
- [Foundations: Data Tiers](../../docs/architecture/00-foundations/data-tiers.md) — `athlete_preferences.py`, `enums.py`
- [Foundations: Terminology](../../docs/architecture/00-foundations/terminology.md) — `enums.py`
