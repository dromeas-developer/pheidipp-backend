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
  // Twin events
  | 'twin_recalibrated'
  | 'twin_confidence_upgraded'
  // Wellness events
  | 'wellness_record_ingested'
  | 'wellness_baseline_updated'
  | 'recovery_modifier_changed'
  // Planning events
  | 'onboarding_completed'
  | 'training_block_created'
  | 'training_plan_generated'
  | 'planned_session_generated'
  | 'session_skipped'
  | 'session_missed'
  | 'session_completed'
  // Coaching events
  | 'workout_generated'
  | 'post_workout_analysis_requested'
  | 'coaching_message_generated'
  | 'objective_updated'
  | 'physiology_updated'          // AthletePhysiology posterior shifted > 1 unit
  | 'physiology_lab_test_ingested' // lab_test measurement created
  | 'fitness_updated'              // AthleteFitness form shifted > 1 unit
  | 'fitness_time_constants_fitted' // individual Banister constants activated
  | 'race_prediction_updated'
  // Cycle events
  | 'cycle_day_one_logged'
  | 'cycle_phase_changed'
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
  training_block_id: string
  twin_state_id: string
  data_tier: number
  confidence_level: 'low'    // always low at onboarding
}
```
**Producer:** `OnboardingService`
**Consumers:** `PlanGenerationService`, `FirstMessageAgent`

---

### `training_plan_generated`
```typescript
type TrainingPlanGeneratedPayload = {
  training_plan_id: string
  training_block_id: string
  phase_count: number
  total_weeks: number
  supersedes_plan_id: string | null
  trigger: 'new_block' | 'goal_date_change' | 'confidence_upgrade' | 'session_dropout'
}
```
**Producer:** `PlanGenerationService`
**Consumers:** `ProactiveMessageService` (plan regeneration notification)

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
  training_block_id: string
  baseline_prediction_seconds: number
  confidence_level: 'medium' | 'high'
  update_trigger: 'activity_sync' | 'weather_update' | 'course_profile' | 'new_block'
}
```
**Producer:** `RacePredictionService`
**Consumers:** API layer (home screen refresh signal)

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

## Invariants
- All events are scoped to a single `athlete_id`
- `event_id` is a UUID, generated at the point of production
- All events are append-only — events are never updated or deleted
- Failed event processing is retried; events are not consumed destructively

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| System events | append-only event log | eventual | 90 days (operational window) |
| Event dead-letter queue | append-only | strong | 30 days |

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
