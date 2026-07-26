# Test Scenarios — Phase 1 Gap Analysis — Batch 3: Onboarding & Twin Bootstrap

## Source: docs/implementation/phase-1/gap-analysis-phase-1/overview.md
## Sub-Phases Covered: 1.3 (Onboarding & Twin Bootstrap)

---

## Step 1 — Onboarding Atomic Transaction (POST /athletes/{id}/onboarding)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | Complete onboarding creates all 8 entities atomically | Authenticated athlete (onboarding_complete=False), valid `OnboardingRequest` with profile (timezone="Europe/London"), preferences (sport_background=RUNNING_PRIMARY, hr_source=CHEST_STRAP_RR, power_source=NONE), goal (goal_type=RACE_EVENT, goal_event_type=MARATHON, goal_event_date=2026-12-06, goal_event_name="Berlin Marathon") | `OnboardingResult` with `twin_state` (confidence_level=LOW, trigger=QUESTIONNAIRE), `training_goal` (status=ACTIVE), `preferences`, `profile`, `data_tier=3`; `athlete.onboarding_complete=True`; `onboarding_completed` event in outbox with `training_goal_id`, `twin_state_id`, `data_tier=3`, `confidence_level="low"`; `twin_model_ready` event in outbox with `twin_state_id`, `data_tier=3`, `confidence_level="low"` | application-logic | db-session |
| 2 | Onboarding atomicity — mid-transaction failure rolls back all | Inject failure after AthletePhysiology insert but before AthleteFitness insert | No AthleteProfile update, no AthletePreferences, no TrainingGoal, no AthletePhysiology, no AthleteFitness, no TwinState committed; `athlete.onboarding_complete` remains False; no outbox events | application-logic | db-session |
| 3 | Re-onboarding returns 409 | Athlete with `onboarding_complete=True`, call `complete_onboarding` again | `OnboardingAlreadyCompleteError("onboarding has already been completed")` | application-logic | db-session |
| 4 | Athlete not found returns 404 | `athlete_id` that does not exist in `athletes` table | `AthleteNotFoundError("athlete not found")` | application-logic | db-session |
| 5 | Second active TrainingGoal returns 409 | Athlete already has an active goal; onboarding attempts to create another | `TrainingGoalConflictError("athlete already has an active training goal")` — partial unique index `ix_training_goals_athlete_active` fires, IntegrityError mapped | database + application-logic | db-session |

## Step 2 — Goal Type Whitelist

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 6 | race_event goal accepted | `goal_type=GoalType.RACE_EVENT` with required fields | Onboarding proceeds | application-logic | none |
| 7 | target_performance goal accepted | `goal_type=GoalType.TARGET_PERFORMANCE` with `target_distance_km=10.0`, `target_time_minutes=50` | Onboarding proceeds | application-logic | none |
| 8 | fitness_improvement goal rejected | `goal_type=GoalType.FITNESS_IMPROVEMENT` | `InvalidGoalTypeError("goal_type 'fitness_improvement' is not permitted at onboarding")` | application-logic | none |
| 9 | maintenance goal rejected | `goal_type=GoalType.MAINTENANCE` | `InvalidGoalTypeError` | application-logic | none |
| 10 | recovery goal rejected | `goal_type=GoalType.RECOVERY` | `InvalidGoalTypeError` | application-logic | none |

## Step 3 — Pydantic Schema Validation (Type-System Enforcement)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 11 | Invalid timezone rejected | `timezone="Not/A_Timezone"` | `ValidationError` from `@field_validator("_validate_timezone")` — `ZoneInfoNotFoundError` caught and re-raised as `ValueError("unknown IANA timezone: Not/A_Timezone")` | type-system | none |
| 12 | Valid IANA timezone accepted | `timezone="America/New_York"` | Schema validation passes | type-system | none |
| 13 | Weekly schedule missing a day rejected | `weekly_schedule` with only 6 days (missing "sunday") | `ValidationError` from `@model_validator("_validate_weekly_schedule")` — "weekly_schedule must contain exactly the seven weekdays (missing: ['sunday'])" | type-system | none |
| 14 | Weekly schedule extra key rejected | `weekly_schedule` with 7 days + extra "funday" | `ValidationError` — "unexpected: ['funday']" | type-system | none |
| 15 | race_event missing goal_event_type rejected | `goal_type=RACE_EVENT`, `goal_event_type=None` | `ValidationError` from `@model_validator("_validate_required_fields")` — "race_event goal requires: goal_event_type" | type-system | none |
| 16 | race_event missing goal_event_date rejected | `goal_type=RACE_EVENT`, `goal_event_date=None` | `ValidationError` — "race_event goal requires: goal_event_date" | type-system | none |
| 17 | target_performance missing target_distance_km rejected | `goal_type=TARGET_PERFORMANCE`, `target_distance_km=None` | `ValidationError` — "target_performance goal requires: target_distance_km" | type-system | none |
| 18 | goal_event_date in past rejected | `goal_event_date=date.today()` (today, not future) | `ValidationError` from `@field_validator("_validate_event_date_in_future")` — "goal_event_date must be in the future" | type-system | none |
| 19 | years_structured_training > 80 rejected | `years_structured_training=85` | `ValidationError` (`Field(le=80)`) | type-system | none |
| 20 | fitness_level out of range rejected | `fitness_level=0` | `ValidationError` (`Field(ge=1)`) | type-system | none |
| 21 | fitness_level=6 rejected | `fitness_level=6` | `ValidationError` (`Field(le=5)`) | type-system | none |

## Step 4 — PATCH Profile / Preferences (Immutable Field Protection)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 22 | PATCH profile with date_of_birth rejected | `{"date_of_birth": "1995-01-01"}` | `ValidationError` from `@model_validator("_reject_immutable_fields")` — "profile fields are immutable after registration: date_of_birth" | type-system | none |
| 23 | PATCH profile with sex rejected | `{"sex": "female"}` | `ValidationError` — "profile fields are immutable after registration: sex" | type-system | none |
| 24 | PATCH profile with timezone rejected | `{"timezone": "UTC"}` | `ValidationError` — "profile fields are immutable after registration: timezone" | type-system | none |
| 25 | PATCH profile with height_cm accepted | `{"height_cm": 175}` | Profile updated; `height_cm=175.0` persisted | application-logic | db-session |
| 26 | PATCH profile with extra unknown field rejected | `{"unknown_field": "value"}` | `ValidationError` (`extra="forbid"`) | type-system | none |
| 27 | PATCH preferences weekly_schedule day-level merge | Existing schedule with `saturday={available:true, max_hours:2, long_workout:false, doubles_eligible:false}`; PATCH `{"weekly_schedule": {"saturday": {"available": false}}}` | Saturday merged to `{available:false, max_hours:2, long_workout:false, doubles_eligible:false}`; other 6 days unchanged | application-logic | db-session |

## Step 5 — Data Tier Inference (Fixture F7)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 28 | Tier 1: running power meter + chest strap RR | `hr_source=CHEST_STRAP_RR`, `power_source=RUNNING_POWER_METER` | `DataTier.TIER_1` | application-logic | none |
| 29 | Tier 2: running power meter + non-RR HR | `hr_source=WRIST_OPTICAL`, `power_source=RUNNING_POWER_METER` | `DataTier.TIER_2` | application-logic | none |
| 30 | Tier 3: chest strap RR, no power | `hr_source=CHEST_STRAP_RR`, `power_source=NONE` | `DataTier.TIER_3` | application-logic | none |
| 31 | Tier 4: chest strap no-RR | `hr_source=CHEST_STRAP_NO_RR`, `power_source=NONE` | `DataTier.TIER_4` | application-logic | none |
| 32 | Tier 4: wrist optical | `hr_source=WRIST_OPTICAL`, `power_source=NONE` | `DataTier.TIER_4` | application-logic | none |
| 33 | Tier 5: no HR | `hr_source=NONE`, `power_source=NONE` | `DataTier.TIER_5` | application-logic | none |
| 34 | Tier 6: fallback | `hr_source` and `power_source` values not matching any above | `DataTier.TIER_6` | application-logic | none |

## Step 6 — Twin Bootstrap: max_hr / LT1 / LT2 (Fixture F10)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 35 | max_hr bootstrap from age | `date_of_birth=1990-01-15`, `today=2026-07-25` | `age_in_years=36`, `max_hr_est=184` (220-36) | application-logic | none |
| 36 | LT1 bootstrapped from population norms — must be positive | `max_hr_est=184` | `tol>0`; `LT1 < max_hr(184)`. The spec ("age-graded population norms") does not name specific factors — test ordering, not a specific ratio. | application-logic | none |
| 37 | LT2 bootstrapped from population norms — must be between LT1 and max_hr | `max_hr_est=184` | `tol>0`; `LT1 < LT2 < max_hr(184)`. Test strict ordering: `0 < LT1 < LT2 < max_hr`. | application-logic | none |
| 38 | Bootstrap prior_weight = 0.5 | Any bootstrap signal | `bootstrap_signal()` returns `{"prior_weight": 0.5, "uncertainty": 1.0, "dominant_source": "questionnaire_estimate", ...}` | application-logic | none |
| 39 | Bootstrap metric_confidence all low/null | `bootstrap_metric_confidence()` | `{"lt1_hr": "low", "lt1_power": null, "lt1_pace": null, "lt2_hr": "low", "lt2_power": null, "lt2_pace": null, "cp": null}` | application-logic | none |
| 40 | AthleteFitness initialized to zero | Onboarding completes | `AthleteFitness.aggregate={"fitness": 0.0, "fatigue": 0.0, "form": 0.0}`; `aerobic=None`, `neuromuscular=None`, `structural=None`; `time_constants.source="population_default"` with aerobic {42, 7}, neuromuscular {21, 3}, structural {56, 14} | application-logic | db-session |
| 41 | TwinState bootstrap trigger and confidence | Onboarding completes | `TwinState.trigger=QUESTIONNAIRE`, `confidence_level=LOW`, `model_version="v1-questionnaire-bootstrap"`, `fitness=0.0`, `fatigue=0.0`, `form=0.0`, `lt1_hr_bpm` and `lt2_hr_bpm` are positive finite values derived from age-graded population norms (F10) | application-logic | db-session |

## Step 7 — structural_risk_flag Computation

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 42 | RUNNING_PRIMARY → structural_risk_flag=False | `sport_background=RUNNING_PRIMARY` | `profile.structural_risk_flag=False` | application-logic | none |
| 43 | Non-running background → structural_risk_flag=True | `sport_background=TRIATHLON_BACKGROUND` (or any non-RUNNING_PRIMARY) | `profile.structural_risk_flag=True` | application-logic | none |

## Step 8 — twin_model_ready Event (ADR-012)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 44 | twin_model_ready produced by OnboardingService | Complete onboarding | `twin_model_ready` event in outbox with `twin_state_id`, `data_tier`, `confidence_level="low"`; producer is `OnboardingService` (not `TwinRecalibrationService`) | application-logic | db-session |
| 45 | twin_model_ready fires after bootstrap TwinState insert | Inspect ordering in `complete_onboarding` | `twin_model_ready` published after TwinState insert, in same transaction as `onboarding_completed`, before commit | application-logic | db-session |
| 46 | generate_plan deferred post-commit | Complete onboarding | `generate_plan` procrastinate task deferred AFTER `session.commit()`; if defer fails, onboarding commit is unaffected (swallow-and-log) | application-logic | external-only (mock procrastinate defer) |