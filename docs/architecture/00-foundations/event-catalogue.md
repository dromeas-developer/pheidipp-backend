# Event Catalogue — All System Events

## Purpose
- Provides the authoritative list of all events produced and consumed across the system
- Defines event schemas and the producer/consumer contract for each

## TypeScript Schema

```typescript
type SystemEvent<T = unknown> = {
  event_id: string          // UUID
  event_type: EventType
  version: string           // e.g. "v1"
  produced_at: string       // ISO 8601
  athlete_id: string        // UUID — all events are scoped to an athlete
  payload: T
}

type EventType =
  // Ingestion events
  | 'fit_file_received'
  | 'activity_ingested'
  | 'activity_calibration_eligible'
  // Auth events
  | 'athlete_registered'
  | 'athlete_logged_in'
  | 'auth_method_added'
  | 'auth_method_removed'
  // Twin events
  | 'twin_recalibrated'
  | 'twin_confidence_upgraded'
  | 'twin_model_ready'
  // Physiology events
  | 'physiology_updated'
  | 'physiology_lab_test_ingested'
  // Fitness events
  | 'fitness_updated'
  | 'fitness_time_constants_fitted'
  // Wellness events
  | 'wellness_record_ingested'
  | 'wellness_baseline_updated'
  | 'recovery_modifier_changed'
  // Planning events
  | 'onboarding_completed'
  | 'training_goal_created'
  | 'secondary_event_registered'
  | 'secondary_event_removed'
  | 'training_plan_generated'
  | 'planned_session_generated'
  | 'session_skipped'
  | 'session_missed'
  | 'session_completed'
  // Weekly synthesis events
  | 'pre_week_review_completed'
  | 'weekly_plan_created'
  | 'week_completed'
  // Coaching events
  | 'workout_generated'
  | 'post_workout_analysis_requested'
  | 'coaching_message_generated'
  | 'objective_updated'
  | 'race_prediction_updated'
  // Cycle events
  | 'cycle_day_one_logged'
  | 'cycle_phase_changed'
  // Checkpoint events
  | 'checkpoint_completed'
  // Execution events
  | 'execution_analysis_completed'
  // Integration events
  | 'integration_connected'
  | 'integration_disconnected'
```

### Payload Schemas

```typescript
// integration_connected
type IntegrationConnectedPayload = {
  athlete_id: string
  platform: 'intervals_icu' | 'garmin_connect'
}

// integration_disconnected
type IntegrationDisconnectedPayload = {
  athlete_id: string
  platform: 'intervals_icu' | 'garmin_connect'
}

// training_goal_created
type TrainingGoalCreatedPayload = {
  training_goal_id: string
  goal_type: GoalType
  goal_event_type: GoalEventType | null
  goal_event_date: string | null
  fitness_level: number
}

// objective_updated
type ObjectiveUpdatedPayload = {
  objective_id: string
  direction_of_change: ObjectiveDirectionOfChange
  is_milestone: boolean
}
```

## Event Schemas

### `fit_file_received`
```typescript
type FitFileReceivedPayload = {
  source: 'intervals_icu' | 'manual_upload' | 'garmin_direct'
  external_id: string | null
  fit_file_key: string
  raw_bytes_size: number
}
```
**Producer:** `FitIngestionTask`
**Consumers:** `LoadComputationService`, `SignalCleaningService`

---

### `athlete_registered`
```typescript
type AthleteRegisteredPayload = {
  auth_provider: 'email' | 'google' | 'strava'
  has_password: boolean              // false for OAuth-only accounts
  profile_completed: boolean         // was profile data provided at registration
}
```
**Producer:** `AuthService` (POST /auth/register or POST /auth/google or POST /auth/strava)
**Consumers:** Audit log, analytics pipeline

---

### `athlete_logged_in`
```typescript
type AthleteLoggedInPayload = {
  auth_provider: 'email' | 'google' | 'strava'
  token_type: 'access' | 'refresh'
  ip_address: string | null
  user_agent: string | null
}
```
**Producer:** `AuthService` (POST /auth/login, POST /auth/login/google, or POST /auth/refresh)
**Consumers:** Security monitoring, audit log

---

### `auth_method_added`
```typescript
type AuthMethodAddedPayload = {
  provider: 'email' | 'google' | 'strava'
  is_primary: boolean
  has_password: boolean
}
```
**Producer:** `AuthService` (POST /athletes/{id}/auth/link)
**Consumers:** Audit log

---

### `auth_method_removed`
```typescript
type AuthMethodRemovedPayload = {
  provider: 'email' | 'google' | 'strava'
  remaining_methods: ('email' | 'google' | 'strava')[]
  was_primary: boolean
}
```
**Producer:** `AuthService` (DELETE /athletes/{id}/auth/link/{provider})
**Consumers:** Audit log

---

### `activity_ingested`
```typescript
type ActivityIngestedPayload = {
  activity_id: string
  activity_date: string      // YYYY-MM-DD
  duration_seconds: number
  has_hr: boolean
  has_rr_intervals: boolean
  has_power: boolean
  fit_file_key: string
  ingestion_pipeline_version: string
}
```
**Producer:** `FitIngestionTask` (after Activity record created)
**Consumers:** `LoadComputationService`, `CalibrationEligibilityService`

---

### `activity_calibration_eligible`
```typescript
type ActivityCalibrationEligiblePayload = {
  activity_id: string
  aerobic_load: number
  neuromuscular_load: number
  structural_load: number
}
```
**Producer:** `CalibrationEligibilityService`
**Consumers:** `TwinRecalibrationTask`, `ThresholdDetectionService`

---

### `execution_analysis_completed`
```typescript
type ExecutionAnalysisCompletedPayload = {
  activity_id: string
  execution_observation_id: string | null  // null if analysis failed or degraded to lap-only
  confidence_level: 'calibration' | 'analysis'
  degradation_mode: boolean  // true if fell back to lap-based analysis (no physiological segments)
  analysis_version: string
}
```
**Producer:** `ExecutionAnalysisTask` (after creating `ExecutionObservation` or falling back)
**Consumers:** `PostWorkoutTask` (waits for this event before proceeding)

**Trigger Timing:** Fires immediately after `ExecutionObservation` is persisted (or after fallback logic completes).

**Retry Semantics:** If `ExecutionAnalysisTask` fails, this event is **not** fired. `PostWorkoutTask` timeout logic handles the absence.

---

### `fitness_time_constants_fitted`
```typescript
type FitnessTimeConstantsFittedPayload = {
  athlete_id: string
  fitness_tau_days: number
  fatigue_tau_days: number
  fitting_r_squared: number
  sample_count: number
}
```
**Producer:** `GapCurveFittingTask` (after 20+ outdoor sessions)
**Consumers:** `AthleteProfile` update service

---

### `training_goal_created`
```typescript
type TrainingGoalCreatedPayload = {
  training_goal_id: string
  goal_type: GoalType
  goal_event_type: GoalEventType | null
  goal_event_date: string | null
  fitness_level: number
}
```
**Producer:** `TrainingGoal` entity (POST /training-goals)
**Consumers:** Audit log, analytics pipeline

---

### `planned_session_generated`
```typescript
type PlannedSessionGeneratedPayload = {
  planned_session_id: string
  weekly_plan_id: string
  target_date: string
  session_type: SessionType
}
```
**Producer:** `WeeklySynthesisAgent` (for each session in WeeklyPlan)
**Consumers:** `WorkoutPrefetchTask` (triggers day-of workout generation)

---

### `workout_generated`
```typescript
type WorkoutGeneratedPayload = {
  generated_workout_id: string
  planned_session_id: string
  session_type: SessionType
  step_count: number
}
```
**Producer:** `WorkoutGenerationAgent`
**Consumers:** API layer (home screen refresh), `WeatherForecastService` (prefetch cancellation)

---

### `post_workout_analysis_requested`
```typescript
type PostWorkoutAnalysisRequestedPayload = {
  activity_id: string
  planned_session_id: string | null
  is_manual: boolean
}
```
**Producer:** `SessionLifecycleService` (when session transitions to completed)
**Consumers:** `PostWorkoutTask` (triggers context assembly)

---

### `cycle_phase_changed`
```typescript
type CyclePhaseChangedPayload = {
  cycle_phase_log_id: string
  athlete_id: string
  phase: CyclePhase
  cycle_day: number
  computation_basis: 'default_boundaries' | 'personal_model'
}
```
**Producer:** `CyclePhaseLog` entity (when new period start date logged)
**Consumers:** `WellnessModifierService` (cycle composite adjustments), `WeatherForecastService` (luteal thermal offset)

---

### `twin_recalibrated`
```typescript
type TwinRecalibratedPayload = {
  twin_state_id: string
  previous_twin_state_id: string | null
  trigger: 'questionnaire' | 'activity_sync' | 'calibration' | 'wellness_update'
  confidence_level: 'low' | 'medium' | 'high'
  fitness_score: number
  fatigue_score: number
}
```
**Producer:** `TwinRecalibrationService`
**Consumers:** `PlanGenerationService` (on confidence upgrade), `WorkoutGenerationAgent` (next workout), `RacePredictionService`

---

### `twin_confidence_upgraded`
```typescript
type TwinConfidenceUpgradedPayload = {
  twin_state_id: string
  from: 'low' | 'medium'
  to: 'medium' | 'high'
}
```
**Producer:** `TwinRecalibrationService` (only when confidence level increases)
**Consumers:** `PlanGenerationService` (triggers plan regeneration), `ProactiveMessageService`

---

### `wellness_record_ingested`
```typescript
type WellnessRecordIngestedPayload = {
  date: string               // YYYY-MM-DD
  source: string
  signals_present: string[]  // which fields are non-null
}
```
**Producer:** `WellnessIngestionService`
**Consumers:** `BaselineComputationTask` (scheduled, not per-event)

---

### `recovery_modifier_changed`
```typescript
type RecoveryModifierChangedPayload = {
  previous_level: 'green' | 'amber' | 'red' | null
  new_level: 'green' | 'amber' | 'red'
  driving_signals: string[]  // which signals exceeded threshold
}
```
**Producer:** `WellnessModifierService`
**Consumers:** `TwinRecalibrationService` (wellness_update trigger if AMBER/RED), `ProactiveMessageService`

---

### `onboarding_completed`

```typescript
type OnboardingCompletedPayload = {
  training_goal_id: string
  twin_state_id: string
  data_tier: number
  confidence_level: 'low'    // always low at onboarding
}
```

**Producer:** `OnboardingService`
**Consumers:** `TwinBootstrapService` (starts twin model build). Note: plan generation is triggered by `twin_model_ready`, NOT by `onboarding_completed`. For Tier 1 athletes, `twin_model_ready` fires after historical data ingestion completes.

---

### `training_plan_generated`

```typescript
type TrainingPlanGeneratedPayload = {
  training_plan_id: string
  training_goal_id: string
  phase_count: number
  total_weeks: number
  supersedes_plan_id: string | null
  trigger: 'new_goal' | 'goal_date_change' | 'confidence_upgrade'
}
```

**Producer:** `TrainingGoal` entity (via `PlanGenerationService`)
**Consumers:** `PreWeekReviewAgent` (schedules first weekly synthesis), `FirstMessageAgent` (generates first message from WeeklyPlan), `ProactiveMessageService` (plan regeneration notification), `WeatherForecastService` (prefetch for upcoming session dates)

---

### `session_completed`
```typescript
type SessionCompletedPayload = {
  planned_session_id: string
  activity_id: string
  session_type: string
  calibration_eligible: boolean
}
```
**Producer:** `SessionLifecycleService`
**Consumers:** `PostWorkoutAgent`, `ObjectiveUpdateService`

---

### `session_skipped`
```typescript
type SessionSkippedPayload = {
  planned_session_id: string
  skip_reason: string
  redistributed_to_date: string | null
}
```
**Producer:** `SessionLifecycleService`
**Consumers:** `SkipConversationAgent`

---

### `coaching_message_generated`
```typescript
type CoachingMessageGeneratedPayload = {
  coaching_message_id: string
  message_type: string
  generation_event_id: string
  prompt_version: string
}
```
**Producer:** All coach agents
**Consumers:** API layer (notification delivery)

---

### `race_prediction_updated`
```typescript
type RacePredictionUpdatedPayload = {
  race_prediction_id: string
  training_goal_id: string
  baseline_prediction_seconds: number
  confidence_level: 'medium' | 'high'
  update_trigger: 'activity_sync' | 'weather_update' | 'course_profile' | 'new_goal' | 'secondary_event_added' | 'secondary_event_removed'
}
```
**Producer:** `RacePredictionService`
**Consumers:** API layer (home screen refresh signal)

---

### `secondary_event_registered`
```typescript
type SecondaryEventRegisteredPayload = {
  secondary_event_id: string
  training_goal_id: string
  event_type: SecondaryEventType
  event_date: string
  priority: SecondaryEventPriority
}
```

**Producer:** `TrainingGoal` entity (secondary event endpoint)
**Consumers:** `PlanGenerationService`, `RacePredictionService`

---

### `secondary_event_removed`
```typescript
type SecondaryEventRemovedPayload = {
  secondary_event_id: string
  training_goal_id: string
  event_date: string
}
```

**Producer:** `TrainingGoal` entity (secondary event endpoint)
**Consumers:** `PlanGenerationService`, `RacePredictionService`

---

### `checkpoint_completed`
```typescript
type CheckpointCompletedPayload = {
  checkpoint_id: string
  planned_session_id: string
  checkpoint_type: CheckpointType
  target_metric: string
  metric_updated: boolean
  confidence_changed: boolean
  replan_triggered: boolean
}
```
**Producer:** `SessionLifecycleService` (when a checkpoint session completes)
**Consumers:** `PlanGenerationService` (replan if needed), `ProactiveMessageService` (athlete notification)

---

### `physiology_updated`
```typescript
type PhysiologyUpdatedPayload = {
  parameters_updated: PhysiologyParameter[]
  dominant_sources: Partial<Record<PhysiologyParameter, MeasurementSource>>
  prior_weights: Partial<Record<PhysiologyParameter, number>>
}
```
**Producer:** `PhysiologyUpdateService`
**Consumers:** `TwinRecalibrationService` (appends new TwinState)

---

### `physiology_lab_test_ingested`
```typescript
type PhysiologyLabTestIngestedPayload = {
  parameters_measured: PhysiologyParameter[]
  measurement_date: string
  source: 'lab_test' | 'field_test'
}
```
**Producer:** `PhysiologyInputService`
**Consumers:** `PhysiologyUpdateService`, `ProactiveMessageService`

---

### `fitness_updated`

```typescript
type FitnessUpdatedPayload = {
  aggregate_form: number
  form_descriptor: string
  last_activity_id: string
}
```

**Producer:** `FitnessUpdateService`
**Consumers:** `TwinRecalibrationService` (if form shift > 1)

---

### `twin_model_ready`

```typescript
type TwinModelReadyPayload = {
  twin_state_id: string
  data_tier: DataTier
  confidence_level: TwinConfidenceLevel
}
```

**Producer:** `TwinRecalibrationService` (fires once after onboarding when twin has sufficient data)
**Consumers:** `PlanGenerationService` (triggers initial plan generation + first WeeklyPlan)

Trigger criteria by onboarding tier:
- **Tier 1** (imported history): Fires after historical data ingestion completes and first `activity_sync` or `calibration` TwinState is created
- **Tier 2** (peer-similar or lab test): Fires immediately after twin bootstrap
- **Tier 3** (questionnaire only): Fires immediately after twin bootstrap

---

### `session_missed`

```typescript
type SessionMissedPayload = {
  planned_session_id: string
  target_date: string
  session_type: string
}
```

**Producer:** `MissedSessionSweepTask` (nightly sweep)
**Consumers:** `WeeklyPlanService` (updates WeeklySession status; checks if week is complete)

---

### `pre_week_review_completed`

```typescript
type PreWeekReviewCompletedPayload = {
  training_plan_id: string
  week_number: number
  adjustment_made: boolean
  adjustment_source: 'plan_unchanged' | 'fatigue_correction' | 'schedule_constraint' | 'adaptation_acceleration' | 'checkpoint_result'
}
```

**Producer:** `PreWeekReviewAgent`
**Consumers:** `WeeklySynthesisAgent` (creates WeeklyPlan from AdjustedWeeklyIntent)

Note: Payload contains `training_plan_id` and `week_number`, NOT `weekly_plan_id` — the WeeklyPlan does not exist yet at the time of the review.

---

### `weekly_plan_created`

```typescript
type WeeklyPlanCreatedPayload = {
  weekly_plan_id: string
  training_plan_id: string
  week_number: number
  session_count: number
}
```

**Producer:** `WeeklySynthesisAgent`
**Consumers:** `WorkoutGenerationAgent` (reads today's session from new WeeklyPlan), `WeatherForecastService` (prefetch for session dates)

---

### `week_completed`

```typescript
type WeekCompletedPayload = {
  weekly_plan_id: string
  week_number: number
  sessions_completed: number
  sessions_missed: number
  accumulated_fatigue_delta: number
}
```

**Producer:** `WeeklyPlanService` (when all sessions in week are completed or missed)
**Consumers:** `PreWeekReviewAgent` (reviews next week's intent), `AdaptationBlockDetectionTask` (checks if hard block completed)

---

### `wellness_baseline_updated`

```typescript
type WellnessBaselineUpdatedPayload = {
  athlete_id: string
  signals_updated: string[]
  sample_counts: Record<string, number>
}
```

**Producer:** `BaselineComputationTask`
**Consumers:** `WellnessModifierService` (recovers modifier with updated baselines)

---

## Invariants
- All events are scoped to a single `athlete_id`
- `event_id` is a UUID, generated at the point of production
- All events are append-only — events are never updated or deleted
- Failed event processing is retried; events are not consumed destructively
## Storage Model

| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| System events | append-only event log | eventual | 90 days (operational window) |
| Trigger events (TwinState causal) | append-only event log | eventual | 1 year |
| Event dead-letter queue | append-only | strong | 30 days |

> **Trigger Event Retention:**
> 
> System events that trigger `TwinState` creation are retained for 1 year (low-volume, high-audit-value):
> - `activity_calibration_eligible`
> - `physiology_updated`
> - `fitness_updated`
> - `race_prediction_updated`
> 
> Other system events are retained for 90 days.
> 
> **Audit Trail:** `TwinState.trigger` + inline snapshots provide the primary audit path. For full reconstruction, `PhysiologyMeasurement` (append-only) and `Activity` (load scores + FIT file) are retained indefinitely.

## Runtime Ownership
Owns:
- Event schema definitions and versioning
- Producer/consumer mapping

Does Not Own:
- Event routing infrastructure → `04-platform/event-topology.md`
- Retry and failure handling → `04-platform/failure-handling.md`

## Implementation Notes
- Events are the primary mechanism for decoupling async pipeline stages
- The event catalogue is the source of truth for integration contracts between services
- When a new service needs to react to something another service does, an event is the correct mechanism — not a direct service call
