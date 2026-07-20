> **Baseline — test companion for** `batch-1-plan-generation.md`, migrated from `docs/implementation/phase-1/phase-1-4-p1-plan-generation.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements and verified against existing test files.

### Plan Generation Service — Race Event
- Given `goal_type = race_event` with `goal_event_date` 16 weeks out, generates TrainingPlan with correct phase proportions (40% base ≈ 6.4 weeks, 30% threshold ≈ 4.8 weeks, 15% race-specific ≈ 2.4 weeks, 2 weeks taper, 1 week race-week)
- Given phase date ranges are non-overlapping and contiguous covering from today to `goal_event_date`
- Given each phase has `label`, `start_date`, `end_date`, `weeks`, `primary_focus`, `weekly_session_count`
- Given `strategic_rationale` contains `primary_driver`, `methodology_summary`, `risk_notes`
- Given all `PlannedSession` records have `status = 'scheduled'`

### Plan Generation Service — Target Performance
- Given `goal_type = target_performance` with target distance and time, computes gap from current fitness estimate
- Given gap classification (small/medium/large/very_large) maps to appropriate weeks-to-target
- Given system-determined goal date is set based on gap analysis
- Given phase proportions follow the same template as race_event
- Given checkpoint descriptors include `trajectory_status` and `proposal` fields

### Training Length Gate
- Given goal event 52 weeks away with minimal experience, gate rejects with appropriate action
- Given goal event 8 weeks away with adequate fitness, gate proceeds
- Given `TrainingLengthGateError` raised when gate fails, preventing plan creation

### Structural Rules
- Given no two consecutive quality sessions (`threshold`, `vo2max`, `tempo`, `interval`, `race_pace`) on consecutive dates in any generated week
- Given quality sessions CAN be consecutive when they share a `block_id`
- Given long run session is always followed by `rest` or `recovery_run` in every week
- Given threshold and vo2max sessions have `easy_run`, `recovery_run`, or `rest` on both the day before and after
- Given one rest day per week minimum
- Given session count per week matches athlete's `weekly_schedule.available` days (4-6 sessions)

### Checkpoint Scheduling
- Given a 16+ week race_event plan, at least one `calibration` checkpoint exists (at phase transitions)
- Given at least one `benchmark` checkpoint exists (at 4-week mark and phase starts)
- Given at least one `progress_review` checkpoint exists (every 3-4 weeks)
- Given a `race_simulation` checkpoint exists in the race-specific phase (2-3 weeks before goal event)
- Given no two checkpoints in the same week
- Given no checkpoint on the first or last day of a phase
- Given all `Checkpoint` records have `status = 'scheduled'`
- Given every checkpoint's `PlannedSession` has `checkpoint_type` and `checkpoint_metric` set

### Supersession
- Given generating a second plan for the same `TrainingGoal`, first plan's `status` changes to `superseded`
- Given first plan's `superseded_at` is set to a non-null timestamp
- Given old plan is never deleted from the database
- Given both supersession and new plan creation happen in the same transaction
- Given `training_plan_generated` event payload includes `supersedes_plan_id` referencing the old plan

### API Endpoints — Happy Path
- Given `GET /athletes/{id}/plan` returns `TrainingPlanResponse` with correct phase sequence for goal type
- Given response includes `phases_summary`, `phase_definitions`, `weekly_distributions`, `checkpoint_schedule`
- Given `GET /athletes/{id}/plan/sessions` returns `PlannedSessionResponse[]` covering full duration to goal event
- Given sessions are ordered by `target_date` then `session_slot`
- Given `GET /athletes/{id}/plan/upcoming` returns next 5 sessions from today onwards
- Given upcoming sessions are ordered by `target_date ASC` then `session_slot ASC`
- Given `GET /athletes/{id}/plan/checkpoints` returns all scheduled checkpoints

### API Endpoints — Error States
- Given all four endpoints return 404 when no active TrainingPlan exists
- Given all four endpoints require `require_self` authorization
- Given all four endpoints return 403 when JWT `athlete_id` does not match path parameter
- Given all endpoints return 401 without JWT

### Onboarding Integration
- Given `complete_onboarding` with valid goal and twin state, plan is generated as part of onboarding
- Given `training_plan_generated` event is persisted in the same transaction as `onboarding_completed`
- Given if plan generation fails (e.g., training length gate rejection), onboarding rolls back and `onboarding_complete` remains `False`
- Given `PlanGenerationService` injected as optional dependency — when `None` (unit tests), plan generation is skipped gracefully

### Event Production
- Given `training_plan_generated` event has payload: `training_plan_id`, `training_goal_id`, `phase_definitions_count`, `total_weeks`, `supersedes_plan_id`, `trigger`
- Given event is published via `EventPublisher.publish()` — `SystemEvent` + `SystemEventOutbox` in same transaction
- Given event fires via transactional outbox per ADR-004

### Query Patterns — Staleness Joins
- Given `GET /plan/sessions` joins through `WeeklyPlan.training_plan_id` (not filtering `PlannedSession.training_plan_id` directly)
- Given `GET /plan/upcoming` uses the same staleness-join pattern
- Given `GET /plan/checkpoints` joins through `PlannedSession → WeeklyPlan → TrainingPlan`

### No LLM Verification
- Given `PlanGenerationService` contains no imports of `openai`, `AsyncOpenAI`, any LLM client, or any agent module
- Given `PlanGenerationService` contains no `await llm_client.chat.completions.create()` calls or similar
- Given no `GenerationEvent` records are created by plan generation
