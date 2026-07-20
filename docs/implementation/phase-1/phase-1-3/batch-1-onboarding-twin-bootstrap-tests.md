> **Baseline — test companion for** `batch-1-onboarding-twin-bootstrap.md`, migrated from `docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements and verified against existing test files.

### Atomic Success
- Given submitting complete onboarding request with `race_event` goal, exactly one `TrainingGoal` (status=`active`), one `AthletePhysiology`, one `AthleteFitness`, one `TwinState`, one `AthletePreferences` are created in a single committed transaction
- Given `athlete.onboarding_complete` is `true` after successful onboarding
- Given `TwinState` has `trigger = questionnaire`, `confidence_level = low`, `model_version = v1-questionnaire-bootstrap`, `fitness = 0`, `fatigue = 0`, `form = 0`
- Given `TwinState` has non-null `lt1_hr_bpm` and `lt2_hr_bpm` derived from age-graded formula (`max_hr = 220 - age_years`, `lt1_hr = 0.75 * max_hr`, `lt2_hr = 0.875 * max_hr`)
- Given `AthleteFitness.aggregate` = `{fitness: 0.0, fatigue: 0.0, form: 0.0}`
- Given `AthleteFitness.time_constants.source` = `population_default` with aerobic (42/7), neuromuscular (21/3), structural (56/14)
- Given `AthletePhysiology.lt1.hr.dominant_source` = `questionnaire_estimate`, `lt2.hr.dominant_source` = `questionnaire_estimate`
- Given `AthletePhysiology.cp` = `null`, `AthletePhysiology.vo2max` = `null` (never estimated from questionnaire)
- Given `structural_risk_flag` = `true` for crossover athletes, `false` for running-primary

### Event Production
- Given `onboarding_completed` `SystemEvent` row exists for the athlete with payload `{training_goal_id, twin_state_id, data_tier, confidence_level='low'}`
- Given paired `SystemEventOutbox` row exists with `status = 'pending'`
- Given both persisted in the same transaction as the domain state

### Mid-Transaction Rollback
- Given forcing a failure at any entity-creation step (e.g. corrupt JSONB for `lt1`), no `AthletePreferences`, `TrainingGoal`, `AthletePhysiology`, `AthleteFitness`, or `TwinState` rows exist for the athlete
- Given `onboarding_complete` is still `false`
- Given no `onboarding_completed` event row exists
- Given caught DB exception triggers `await session.rollback()` before re-raising (ADR-006)

### Idempotency Guard
- Given calling `POST /athletes/{id}/onboarding` twice, second call returns 409
- Given second call returns 409 with `OnboardingAlreadyCompleteError`
- Given no new rows are written in database
- Given no new outbox row is added

### TwinState Correctness
- Given `GET /athletes/{id}/twin` after onboarding returns `confidence_level = low`, `trigger = questionnaire`, `fitness = 0`, `fatigue = 0`, `form = 0`
- Given non-null `lt1_hr_bpm` and `lt2_hr_bpm` derived from athlete's DOB via documented formulae
- Given `readiness_level = green`, `wellness_trend = null`
- Given `data_tier` matches `infer_data_tier(hr_source, power_source)` — verify for all documented combinations
- Given `activity_id = null` (questionnaire trigger has no triggering activity)
- Given `metric_confidence` = `{lt1_hr: 'low', lt2_hr: 'low', lt1_power: null, lt1_pace: null, lt2_power: null, lt2_pace: null, cp: null}`
- Given `training_goal_id` references the created `TrainingGoal`

### Data Tier Wiring
- Given `infer_data_tier(hr_source=HrSource.CHEST_STRAP, power_source=PowerSource.POWER_METER)` → `TIER_1`
- Given `infer_data_tier(hr_source=HrSource.CHEST_STRAP, power_source=PowerSource.NONE)` → `TIER_3`
- Given `infer_data_tier(hr_source=HrSource.WRIST_OPTICAL, power_source=PowerSource.NONE)` → `TIER_4`
- Given `infer_data_tier(hr_source=HrSource.NONE, power_source=PowerSource.NONE)` → `TIER_5`
- Given `TwinState.data_tier` value matches inferred tier for every combination

### Goal-Type Restriction
- Given `goal_type = 'fitness_improvement'` → 422 with `InvalidGoalTypeError`
- Given `goal_type = 'maintenance'` → 422
- Given `goal_type = 'recovery'` → 422
- Given `goal_type = 'target_performance'` without `target_distance_km` and `target_time_minutes` → 422
- Given `goal_type = 'race_event'` without `goal_event_type`, `goal_event_date`, `goal_event_name` → 422

### Single-Active-Goal Invariant
- Given second `complete_onboarding` call for same athlete (bypassing `onboarding_complete` gate), `TrainingGoalConflictError` raised → 409
- Given partial unique index on `(athlete_id, goal_type) WHERE status = 'active'` enforces this

### Profile Patch Guard
- Given PATCHing `date_of_birth` in profile body → 422, stored value unchanged
- Given PATCHing `sex` → 422, stored value unchanged
- Given PATCHing `timezone` → 422, stored value unchanged (timezone is immutable post-creation)
- Given PATCHing `height_cm`, `location_lat`, `location_lng`, `training_window` → 200, values updated, `updated_at` set
- Given PATCHing with empty body → 200, no changes

### Preferences Patch Merge
- Given PATCHing `weekly_schedule` with `{saturday: {available: false}}`, only Saturday's `available` is flipped, other days unchanged
- Given PATCHing `weekly_schedule` with `{monday: {max_hours: 2.5}}`, only Monday's `max_hours` updated, other days unchanged
- Given PATCHing top-level field (not weekly_schedule), that field updates atomically
- Given PATCH is idempotent: re-applying same patch yields same state and response

### Twin / Profile Read Before Onboarding
- Given `GET /athletes/{id}/profile` before onboarding returns 200 with profile fields (populated from registration)
- Given `GET /athletes/{id}/preferences` before onboarding returns 404
- Given `GET /athletes/{id}/twin` before onboarding returns 404
- Given `GET /athletes/{id}/twin/history` before onboarding returns 404
- Given after onboarding completes, all GET endpoints return populated records

### Cross-Athlete Access
- Given JWT for athlete A accessing athlete B's `POST /onboarding` → 403
- Given JWT for athlete A accessing athlete B's `GET /onboarding` → 403
- Given JWT for athlete A accessing athlete B's `GET /profile` → 403
- Given JWT for athlete A accessing athlete B's `GET /twin` → 403
- Given all endpoints use `require_self` dependency

### TwinState Append-Only
- Given `TwinStateRepository` has no `update()` method
- Given `TwinStateRepository` has no `delete()` method
- Given only `insert`, `get_latest`, `get_history`, `get_by_activity`, `get_by_activity_and_trigger` are exposed

### Timezone Validation
- Given `timezone = "America/New_York"` (valid IANA) → accepted
- Given `timezone = "Europe/Lisbon"` → accepted
- Given `timezone = "invalid/timezone"` → 422 before any row is written
- Given timezone validation uses `zoneinfo.ZoneInfo`
