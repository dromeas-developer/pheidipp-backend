> **Baseline — test companion for** `batch-1-workout-generation.md`, migrated from `docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements and verified against existing test files.

### Idempotency
- Given `POST /sessions/{sid}/generate-workout` called twice for same `(planned_session_id, date)`, second call returns 409 with existing `GeneratedWorkout` ID
- Given `GenerationEvent` count increases only on first call (second call skips LLM entirely)
- Given `GET /athletes/{id}/today` returns existing workout without re-calling LLM when one was previously generated

### Step Structure Validation
- Given a threshold session (`session_type = 'threshold'`), `WorkoutStep` records: exactly one `warmup` (order 1, intent `recovery`), N work steps (intent `threshold`), N-1 recovery steps between them (intent `recovery`), exactly one `cooldown` (last, intent `recovery`)
- Given every step has a non-null `physiological_intent`
- Given `step_order` values are sequential starting at 1
- Given `step_order` is unique within a `generated_workout_id`

### Data Tier Target Type
- Given Tier 1 athlete: `WorkoutStep.target` contains non-null `target_power_watts` in the primary range
- Given Tier 2 athlete: `target_power_watts` primary, `target_gap_sec_per_km` secondary
- Given Tier 3 athlete: `target_gap_sec_per_km` primary, `target_hr_zone` secondary
- Given Tier 4 athlete: `target_gap_sec_per_km` primary
- Given Tier 5 athlete: all numeric target fields are null, `description` carries the full coaching intent
- Given Tier 6 athlete: all numeric target fields are null, `description` is always non-empty

### Two-Column Targets Always Written
- Given every `GeneratedWorkout` has both `theoretical_targets` and `adjusted_targets` as non-null JSONB objects
- Given at this phase, their content is identical
- Given `ck_generated_workouts_targets_are_objects` check constraint is satisfied

### Twin State Linkage
- Given `GeneratedWorkout.twin_state_id` references the latest `TwinState` at time of generation
- Given if a newer `TwinState` exists after generation, the workout's `twin_state_id` is NOT updated (retroactive update not supported)

### GAP-Only Pace
- Given no `target` or `TargetSet` field contains raw pace values
- Given all pace fields use GAP (grade-adjusted pace) semantics

### LLM Failure Handling
- Given LiteLLM proxy returns an error, `GenerationEvent` written with `success=false` and `failure_reason` populated
- Given no `GeneratedWorkout` or `WorkoutStep` records are created on failure
- Given API returns 502 on LLM failure

### GET /today Behavior
- Given returns 404 when no session exists for today
- Given returns existing workout when one was previously generated
- Given triggers generation and returns new workout when session exists but no workout has been generated yet
- Given response includes `planned_session`, `generated_workout`, and `steps` list

### Cross-Athlete Access
- Given JWT for athlete A attempting to access athlete B's workout returns 403

### Event Production
- Given after successful generation, a `workout_generated` `SystemEvent` and corresponding `SystemEventOutbox` row exist in the database
- Given both are within the same transaction as the `GeneratedWorkout`
- Given publication occurs only after the transaction commits successfully

### SESSION_INTENT_MAP Completeness
- Given every `SessionType` enum value has a mapping to a `PhysiologicalIntent`
- Given `easy_run` → `low_aerobic`, `threshold` → `threshold`, `vo2max` → `vo2max`, etc.
- Given warmup, cooldown, and recovery step types always return `PhysiologicalIntent.RECOVERY` regardless of session type

### DATA_TIER_TARGET_TYPE Mapping
- Given `DataTier.TIER_1` → `'power'`, `DataTier.TIER_2` → `'power'`
- Given `DataTier.TIER_3` → `'gap'`, `DataTier.TIER_4` → `'gap'`
- Given `DataTier.TIER_5` → `'description'`, `DataTier.TIER_6` → `'description'`

### Context Budget
- Given `build_workout_context()` assembles session summary, readiness digest, data tier, target type
- Given 3000 token budget is enforced
- Given warning is logged when budget exceeds 3000 but full context is returned (no error)

### Workout Step Persistence
- Given `WorkoutStepRepository.insert_many()` inserts all steps in a single batch
- Given `get_by_workout()` returns steps ordered by `step_order ASC`
- Given `step_order` is positive (enforced by `ck_workout_steps_step_order_positive`)
- Given `duration_seconds` is non-negative when set
- Given `description` is always non-empty (enforced by `ck_workout_steps_description_non_empty`)

### Planned Session Query
- Given `PlannedSessionRepository.get_today_for_athlete()` joins through `WeeklyPlan` → `TrainingPlan` where `status = 'active'`
- Given multiple active plans for same athlete: only returns sessions from the active plan
- Given staleness join: does not return sessions from stale/inactive plans
