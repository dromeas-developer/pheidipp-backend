# Gap Analysis Test Plan: Phase 1 — Full Vertical Slice
## Plan ID: GAP-PHASE-1-TESTS

## Sub-Phase Reference
Sub-Phase ID: Phase-1 (all sub-phases 1.1 through 1.6)
Sub-Phase Title: Phase 1 — Email/Password Auth through Simple FIT Import & Post-Workout

## Objective
This is a **retrospective gap-analysis test-definition plan**. The Phase 1
implementation is already complete. This plan does NOT produce implementation
steps for the coder — the code already exists. Its sole purpose is to
reverse-engineer architecture contracts, invariants, and event contracts from
the existing codebase, pin concrete numeric fixtures for every computational
invariant, classify the enforcement layer for every input, and draft test
scenarios the test architect can generate assertions from.

## Scope
- Reverse-engineered architecture contracts for all Phase 1 entities, events,
  and computations
- Computational invariant fixtures (concrete input → expected output → tolerance)
  for every formula, decay, threshold, ratio, and numeric transformation in
  Phase 1
- Enforcement-layer classification (type-system / database / application-logic)
  for every invariant and input
- Test scenarios with Enforcement + Mock Boundary columns, organized into six
  batches by ownership domain
- Cross-validation of the existing implementation against architecture, vision,
  release plan, and ADR corpus

## Out Of Scope
- Implementation steps for the coder (the code already exists)
- Batch BRDs with `## Steps` sections (no coder handoff)
- Architecture documentation updates (no `batch-N-architecture.md` files)
- Phase 2+ entities, events, or computations
- Test execution (this plan defines scenarios; the test architect generates and
  runs them)

## Architecture Contracts

Reverse-engineered from the live codebase (`app/models/`, `app/services/`,
`app/repositories/`, `app/agents/`) and cross-validated against the
architecture corpus (`docs/architecture/`).

### Entities (IMPLEMENTS — already built)

| Entity | Model File | Key Invariants |
|--------|-----------|----------------|
| `Athlete` | `app/models/athlete.py` | email unique (functional `lower(email)` index); `onboarding_complete` gate |
| `AthleteAuth` | `app/models/athlete_auth.py` | single primary per athlete (partial unique `WHERE is_primary=true`); unique `(athlete_id, provider)` |
| `RefreshToken` | `app/models/refresh_token.py` | append-only rotation ledger; 30-day expiry; `token_hash` never returned |
| `AthleteProfile` | `app/models/athlete_profile.py` | unique `athlete_id`; immutable `date_of_birth`, `sex`, `timezone` after creation |
| `AthletePreferences` | `app/models/athlete_preferences.py` | unique `athlete_id`; `years_structured_training >= 0` (CHECK); data tier inferred at read time |
| `Activity` | `app/models/activity.py` | no `avg_hr`/`avg_pace`/`avg_power` columns; dedup `(athlete_id, external_id, source)` partial unique `WHERE external_id IS NOT NULL` |
| `TrainingGoal` | `app/models/training_goal.py` | partial unique `(athlete_id) WHERE status='active'`; `fitness_level` 1-5 (CHECK); volume non-negative (CHECK) |
| `TrainingPlan` | `app/models/training_plan.py` | never deleted (`superseded_at` set); one active per goal |
| `WeeklyPlan` | `app/models/weekly_plan.py` | unique `(training_plan_id, week_number)`; sessions immutable once `status='active'` |
| `WeeklySession` | `app/models/weekly_plan.py` | child of WeeklyPlan; `planned_session_id` set lazily |
| `PlannedSession` | `app/models/planned_session.py` | `training_plan_id` denormalized (query via WeeklyPlan); `activity_id` set only when `status='completed'` |
| `Checkpoint` | `app/models/checkpoint.py` | `planned_session_id` one-to-one (unique FK); cannot be created retroactively |
| `TwinState` | `app/models/twin_state.py` | append-only (repository exposes only `insert`, `get_latest`, `get_by_activity`, `get_history`); `training_goal_id`/`model_version`/`activity_id` frozen |
| `AthletePhysiology` | `app/models/athlete_physiology.py` | unique `athlete_id`; mutable; `max_hr` bootstrapped from `220 - age` |
| `AthleteFitness` | `app/models/athlete_fitness.py` | unique `athlete_id`; `form = fitness - fatigue` (DB CHECK on JSONB aggregate + each dimension); `time_constants.source` ∈ {population_default, individual_fitted} (CHECK) |
| `CoachingMessage` | `app/models/coaching_message.py` | append-only (repo `insert`-only); `first_message` singleton per athlete (partial unique); `post_workout` singleton per activity (partial unique); `content` non-empty (CHECK) |
| `GenerationEvent` | `app/models/generation_event.py` | append-only; every LLM call writes one (success or failure); `failure_reason` non-null when `success=false` |
| `GeneratedWorkout` | `app/models/generated_workout.py` | append-only; unique `(planned_session_id, generation_date)`; `theoretical_targets` + `adjusted_targets` both NOT NULL JSONB objects (CHECK); `recovery_modifier_level` ∈ {green,amber,red} (CHECK) |
| `WorkoutStep` | `app/models/workout_step.py` | append-only; unique `(generated_workout_id, step_order)`; `physiological_intent` NOT NULL; `step_order >= 1` (CHECK); `description` non-empty (CHECK); `duration_seconds >= 0` (CHECK) |
| `SystemEvent` / `SystemEventOutbox` | `app/models/system_event.py` | `system_events` append-only; `system_event_outbox` mutable status; `athlete_id` NOT NULL; event + outbox in same transaction as domain state (ADR-004) |

### Computations (IMPLEMENTS — already built)

| Computation | Service File | Formula / Rule |
|-------------|-------------|----------------|
| Banister update (aerobic aggregate) | `app/services/twin_recalibration_service.py` (`apply_banister_update`) | `fitness(t) = fitness(t-1) × e^(-d/tau_f) + load`; `fatigue(t) = fatigue(t-1) × e^(-d/tau_fat) + load`; `form = fitness - fatigue`. Population tau: aerobic fitness=42d, fatigue=7d. Spec: `02-computations/banister-update.md`. |
| Aerobic load (HR-reserve) | `app/services/load_computation_service.py` (`_compute_aerobic_load`) | `Σ(exp(1.92 × hrr_pct) - 1) / 3600` where `hrr_pct = (hr - resting_hr) / (max_hr - resting_hr)`. The spec also states "1 hour at LT1 ≈ 100 units" implying a normalisation step beyond the raw formula. Spec: `02-computations/load-computation.md`. |
| Aerobic load (power-based, Tier 1-2) | `app/services/load_computation_service.py` (`_compute_power_aerobic_load`) | `Σ(watts/cp)^4 / 3600`. Spec: `02-computations/load-computation.md`. |
| Neuromuscular load | `app/services/load_computation_service.py` (`_compute_neuromuscular_load`) | `cv × duration_hours + (time_above_vo2 / 3600 × 2.5)`. Null for Tier 5-6. |
| Structural load | `app/services/load_computation_service.py` (`_compute_structural_load`) | `base + gradient_cost + density_penalty`. `base = distance_km × surface_modifier`; `gradient_cost = (ascent_m/100) × 0.18 × distance_km`; `density_penalty = min(recent_structural_72h × coefficient, 15)` where coefficient=0.12 (or 0.08 if `structural_risk_flag`). Null without GPS. |
| Calibration eligibility gate | `app/services/calibration_eligibility_service.py` | 6-condition AND: `sport_type==running` AND `has_hr` AND `source!=manual_entry` AND `duration>=1200s` AND `hr_dropout_pct<=0.20` AND `no gps_loss` AND `no sensor_malfunction` |
| Data tier inference | `app/models/athlete_preferences.py` (`infer_data_tier`) | 6-tier matrix from `(hr_source, power_source)` — see fixture F7 |
| Confidence level derivation | `app/services/twin_recalibration_service.py` (`derive_confidence_level`) | `min(lt1.hr.prior_weight, lt2.hr.prior_weight)` → LOW (<4.0), MEDIUM (≥4.0), HIGH (≥8.0). Spec: `00-foundations/confidence-model.md`. |
| Confidence ratchet (ADR-011) | `app/services/twin_recalibration_service.py` (`max_confidence_level`, `max_confidence_level_string`) | `max(stored_level, computed_level)` per metric; never decreases; previously-unmeasured metrics reflect new evidence. Spec: ADR-011. |
| max_hr bootstrap | `app/services/onboarding_service.py` (`age_in_years` + `220 - age`) | `max_hr = 220 - age` (spec: `01-entities/athlete-physiology.md`). LT1 and LT2 bootstrapped from "age-graded population norms" — spec does not name specific factors. `questionnaire_estimate` prior_weight = 0.5 (spec: `00-foundations/confidence-model.md`). |
| Plan phase proportions (race_event) | `app/services/plan_generation_templates.py` (`allocate_race_event_phases`) | 40% base, 30% threshold, 15% race-specific, 2w taper, 1w race-week. Spec: `02-computations/plan-generation.md`. Proportion application (rounding, residuals) not specified. |
| Training length gate | `app/services/plan_generation_templates.py` (`evaluate_training_length_gate`) | Per `(goal_event_type, experience_level)` threshold table; `weeks > threshold` → propose_intermediate; `weeks < 8 AND fitness_level <= 2` → propose_shorter_goal |
| Experience level | `app/services/plan_generation_templates.py` (`derive_experience_level`) | years < 2 → novice; 2-5 → intermediate; > 5 → experienced |
| Target performance gap | `app/services/plan_generation_service.py` (`_classify_gap`, `_estimate_weeks_to_target`) | ≤3% → small (4-6w); 3-8% → medium (6-10w); 8-15% → large (10-16w); >15% → very_large |
| Form descriptor mapping | `app/models/athlete_fitness.py` (documented in architecture) | form > 15 → "peaked"; > 5 → "building"; > -5 → "training load"; > -15 → "heavy load"; ≤ -15 → "overreached" |

### Platform Services (DEPENDS ON)

| Service | File | Contract |
|---------|------|----------|
| `EventPublisher` | `app/services/event_publisher.py` | `publish(event_type, athlete_id, payload)` — writes `SystemEvent` + `SystemEventOutbox` atomically in caller's transaction (ADR-004) |
| `OutboxPublisherService` | `app/services/outbox_publisher_service.py` | `publish_pending(limit)` — own session, transitions `pending→published`, commits (ADR-013) |
| `ObjectStorageClient` | `app/services/object_storage_client.py` | MinIO-backed; `upload_fit`, `download_fit`, `delete_fit`, `exists`; bucket `pheidipp-fit-files` |
| `FitParserService` | `app/services/fit_parser_service.py` | `parse_fit(file_bytes) → ParsedFitData` via `asyncio.to_thread`; returns raw records (HR, power, GPS, RR), not summaries |
| `TokenService` | `app/core/security/token_service.py` | JWT access (15min) + refresh (30-day); `hash_refresh_token`, `generate_refresh_token`, `issue_access_token`, `refresh_expiry` |
| `PasswordHasher` | `app/core/security/password_hasher.py` | bcrypt; `hash(password)`, `verify(password, hash)` |
| `ContextBudgetService` | (referenced by agents) | Token budget enforcement (3k-5k tokens); hard limit before LLM call |
| `PromptRegistry` | (referenced by agents) | Prompt template loading and versioning |
| `TwinContextAssembler` | (referenced by agents) | Translates `TwinState` into coaching-relevant language |

### ADRs (DECISION — constrain the implementation)

| ADR | Title | Constraint |
|-----|-------|------------|
| ADR-001 | Layer Architecture | `api → services → repositories → models`; no layer skipping; worker → services → repos |
| ADR-004 | Transactional Outbox | Event + outbox row in same transaction as domain state; publication only after commit |
| ADR-005 | IP & Token Security | IP truncated to /24 (IPv4) or /64 (IPv6) before logging; discarded after 7 days; `token_hash` never returned or logged |
| ADR-007 | All LLM Calls Route Through LiteLLM Proxy | `AsyncOpenAI(base_url=settings.LITELLM_BASE_URL)`; no direct provider SDKs; proxy owns retry/rate-limit/cleaning/tracking |
| ADR-011 | Confidence Monotonicity Ratchet | Per-metric `max(stored, computed)` in `TwinRecalibrationService` (P3); never decreases |
| ADR-012 | twin_model_ready Producer Amendment | Producer = `OnboardingService` (not `TwinRecalibrationService`); fires after bootstrap TwinState insert for all tiers |
| ADR-013 | Outbox Publisher Service Ownership | `OutboxPublisherService` owns publish-side transaction; worker → service → repository |

## Invariants

Reverse-engineered from the codebase. Each invariant is classified by
enforcement layer.

### Database-enforced invariants (CHECK / UNIQUE / NOT NULL / partial index)

1. `Athlete.email` unique via functional `lower(email)` index
2. `AthleteAuth` single primary per athlete (partial unique `WHERE is_primary=true`)
3. `AthleteAuth` unique `(athlete_id, provider)`
4. `AthleteProfile` unique `athlete_id`
5. `AthletePreferences` unique `athlete_id`; `years_structured_training >= 0` (CHECK)
6. `Activity` dedup `(athlete_id, external_id, source)` partial unique `WHERE external_id IS NOT NULL`
7. `TrainingGoal` partial unique `(athlete_id) WHERE status='active'`; `fitness_level` 1-5 (CHECK); `weekly_volume_hours >= 0` (CHECK); `weekly_volume_km >= 0` (CHECK)
8. `AthleteFitness` unique `athlete_id`; `form = fitness - fatigue` (CHECK on aggregate + each dimension JSONB); `time_constants.source` ∈ {population_default, individual_fitted} (CHECK)
9. `CoachingMessage` `first_message` singleton (partial unique `WHERE message_type='first_message'`); `post_workout` singleton per activity (partial unique `WHERE message_type='post_workout' AND activity_id IS NOT NULL`); `content` non-empty (CHECK `length(content) > 0`)
10. `GeneratedWorkout` unique `(planned_session_id, generation_date)`; `theoretical_targets` and `adjusted_targets` are JSONB objects (CHECK `jsonb_typeof`); `recovery_modifier_level` ∈ {green, amber, red} (CHECK)
11. `WorkoutStep` unique `(generated_workout_id, step_order)`; `physiological_intent` NOT NULL; `step_order >= 1` (CHECK); `description` non-empty (CHECK); `duration_seconds >= 0` (CHECK)
12. `Checkpoint` `planned_session_id` unique (one-to-one FK)
13. `SystemEvent.athlete_id` NOT NULL

### Type-system-enforced invariants (Pydantic validators, Field constraints, Enum, Literal)

14. `RegisterRequest.password` min 8 chars, max 128; not blank/whitespace-only (`@field_validator`)
15. `RegisterRequest.email` `EmailStr` format
16. `RegisterProfileIn.height_cm` 50-300 (`Field(ge=50, le=300)`)
17. `OnboardingProfileIn.timezone` IANA validity (`@field_validator` + `ZoneInfo`)
18. `OnboardingPreferencesIn.years_structured_training` 0-80 (`Field(ge=0, le=80)`)
19. `OnboardingPreferencesIn.weekly_schedule` 7-day key completeness (`@model_validator`)
20. `OnboardingTrainingGoalIn.goal_event_date` must be in future (`@field_validator`)
21. `OnboardingTrainingGoalIn` per-goal-type required fields (`@model_validator`): race_event requires goal_event_type + goal_event_date + goal_event_name; target_performance requires target_distance_km + target_time_minutes
22. `OnboardingTrainingGoalIn.weekly_volume_hours` 0-80; `weekly_volume_km` 0-500; `fitness_level` 1-5; `custom_distance_km > 0`; `target_distance_km > 0`; `target_time_minutes > 0`
23. `AthleteProfilePatchIn` immutable fields rejected (`@model_validator` + `extra="forbid"`): date_of_birth, sex, timezone
24. `AthletePreferencesPatchIn` `extra="forbid"`; weekly_schedule patch keys validated
25. All enum fields (`SportBackground`, `HrSource`, `PowerSource`, `GoalType`, `Sex`, etc.) constrained to enum values via `SAEnum` / Pydantic enum

### Application-logic-enforced invariants (service-layer validation, business rules)

26. Refresh token rotation atomicity: old token revoked + replacement inserted + FK wired in one transaction (`AuthService.rotate_refresh_token`)
27. `token_hash` never returned by any API endpoint (response schema excludes it)
28. IP address truncated before logging (`truncate_ip`); discarded after 7 days (`discard_old_ips` task)
29. Registration atomically creates `Athlete` + `AthleteAuth` + `AthleteProfile` + `RefreshToken` + outbox event; all commit or none
30. `TwinState` append-only: repository exposes only `insert`, `get_latest`, `get_by_activity`, `get_by_activity_and_trigger`, `get_history` — no `update`/`delete`
31. `TwinState` deduplication via `insert_if_not_exists`: calibration supersedes prior non-calibration; duplicate non-calibration trigger skipped
32. `form = fitness - fatigue` computed in `apply_banister_update` before DB CHECK validates
33. `TrainingGoal` immutable fields never updated by any service after creation
34. `TrainingPlan` never deleted — `superseded_at` set when replaced
35. `WeeklyPlan` sessions immutable once `status='active'`
36. `Checkpoint` cannot be created retroactively — scheduled during plan synthesis only
37. Onboarding atomicity: 8 entities created in one transaction; any failure rolls back all; `onboarding_complete` flipped only at end
38. Re-onboarding returns 409 (`OnboardingAlreadyCompleteError`)
39. Goal type whitelist: only `race_event` and `target_performance` at onboarding (`validate_goal_type`)
40. `structural_risk_flag` computed from `sport_background != RUNNING_PRIMARY`
41. Data tier inferred from `hr_source` + `power_source` at read time (no stored column)
42. `Activity.fit_file_key` required for `source != manual_entry` (enforced by ingestion service before commit)
43. `Activity` load scores null at creation, populated by `LoadComputationService`
44. `calibration_eligible` set by `CalibrationEligibilityService`, never manually overridden
45. `manual_entry` activities: `calibration_eligible=false`, null load scores, null `fit_file_key`
46. Non-running `sport_type` → `calibration_eligible=false`
47. Object storage upload happens BEFORE `Activity` record creation; upload failure → no Activity
48. `FitParserService` returns raw records, not summary stats
49. `FirstMessageAgent` singleton: 409 on second call (repo `get_existing_first_message` gate)
50. `PostWorkoutAgent` idempotent per `activity_id` (repo `get_by_activity_and_type` gate)
51. `WorkoutGenerationAgent` idempotent per `(planned_session_id, generation_date)` (repo `get_by_session_and_date` gate)
52. Every LLM call writes a `GenerationEvent` (success or failure); no silent failures
53. LLM calls route through LiteLLM proxy only (ADR-007); no direct provider SDKs
54. `WorkoutStep.physiological_intent` never null — warmup/cooldown/recovery = `recovery`, work = derived from `SESSION_INTENT_MAP`
55. GAP values only for pace targets; raw pace never used
56. Target type by data tier: Tier 1-2 power primary; Tier 3-4 GAP primary; Tier 5-6 description only
57. `GeneratedWorkout.twin_state_id` not retroactively updated after twin recalibration
58. `recovery_modifier_level` defaults to `green`, reason null
59. Plan generation is pure Python — no LLM, no external API calls
60. No two consecutive quality sessions in generated schedule
61. Long run always followed by rest or recovery
62. Threshold/VO2max always sandwiched between easy days
63. Confidence ratchet: `confidence_level` and per-metric `metric_confidence` never decrease (ADR-011)
64. `twin_model_ready` produced by `OnboardingService` after bootstrap TwinState insert (ADR-012)

## Cross-Validation Summary

| Check | Result | Detail |
|-------|--------|--------|
| RC1 Contract Saturation | ✓ | All Phase 1 entities, events, and computational invariants accounted for. 16 numeric fixtures pinned (F1-F16). Every computational invariant has a concrete input→expected output→tolerance triple. |
| RC2 Vision Constraints | ✓ | Brand-philosophy (no AI-feel/jargon), running-only twin, no raw data surfaces, cold-start Tier 3 language, confidence-never-decreases, GAP-not-raw-pace, 4-paragraph first message, 3-paragraph post-workout — all mapped to test scenarios in batches 3-6. |
| RC3 Entity Collision | — | N/A — retrospective gap analysis; all entities already exist in the registry. No CREATE/MODIFY collision. |
| RC4 Modification Safety | — | N/A — no modifications planned; test-definition plan for existing code. |
| RC5 Event Flow Consistency | ✓ | All Phase 1 event produce→consume chains traced and confirmed in code: `athlete_registered`→(audit), `athlete_logged_in`→(audit), `onboarding_completed`+`twin_model_ready`→`generate_plan` worker, `training_plan_generated`→`generate_first_message` worker, `activity_ingested`→(twin recalibrate), `workout_generated`/`coaching_message_generated`→(audit). ADR-012 producer (`OnboardingService`) confirmed in `onboarding_service.py` lines 447-459. |
| RC6 Invariant Enforcement | ✓ | Every invariant classified: 13 database-enforced (CHECK/UNIQUE/partial index), 12 type-system-enforced (Pydantic/Enum/Field), 39 application-logic-enforced (service business rules). Full table in Invariants section above. |
| RC7 ADR Re-Check | ✓ | No new ADRs required — test-definition plan, not implementation plan. ADR-012 (twin_model_ready producer) confirmed compliant in code. ADR-011 (confidence ratchet) confirmed in `max_confidence_level*` functions. ADR-007 (LLM proxy) confirmed in agent construction pattern. |

## Event Contracts

All events use `event_id` (UUID), `version` (string), `produced_at` (ISO 8601), `athlete_id` (UUID). Persisted via transactional outbox (ADR-004).

| Event | Producer | Consumer(s) | Payload Fields | Ordering |
|-------|----------|-------------|----------------|----------|
| `athlete_registered` | `AuthService.register` | (audit) | `auth_provider`, `has_password`, `profile_completed` | After Athlete+Auth+Profile+RefreshToken insert, before commit |
| `athlete_logged_in` | `AuthService.login`, `AuthService.rotate_refresh_token` | (audit) | `auth_provider`, `token_type` ("access" or "refresh"), `ip_address` (truncated), `user_agent` | After credential validation / rotation, before commit |
| `onboarding_completed` | `OnboardingService.complete_onboarding` | (audit; plan pipeline trigger) | `training_goal_id`, `twin_state_id`, `data_tier`, `confidence_level` ("low") | After all 8 entities created, before commit |
| `twin_model_ready` | `OnboardingService.complete_onboarding` (ADR-012) | `generate_plan` worker task (deferred post-commit) | `twin_state_id`, `data_tier`, `confidence_level` ("low") | After bootstrap TwinState insert, same transaction as onboarding_completed |
| `training_plan_generated` | `PlanGenerationService._persist_full_plan` | `generate_first_message` worker task (deferred) | `training_plan_id`, `training_goal_id`, `phase_count`, `total_weeks`, `supersedes_plan_id`, `trigger` | After plan + weekly + sessions + checkpoints persisted, before commit |
| `activity_ingested` | `ActivityIngestionService` | (audit; recalibration trigger) | `activity_id`, `date`, `duration`, `has_hr`, `has_rr`, `has_power`, `sport_type`, `fit_file_key`, `ingestion_pipeline_version` | After ingestion pipeline completes, before worker commit |
| `activity_calibration_eligible` | `CalibrationEligibilityService` (via ingestion) | (audit) | `activity_id`, `aerobic_load`, `neuromuscular_load`, `structural_load` | When activity qualifies for calibration |
| `twin_recalibrated` | `TwinRecalibrationService.recalibrate` / `recalibrate_for_calibration` | (audit) | `athlete_id`, `twin_state_id`, `activity_id`, `trigger`, `confidence_level`, `fitness`, `fatigue`, `form`, `readiness_level` | After TwinState insert, before commit |
| `twin_confidence_upgraded` | `TwinRecalibrationService.recalibrate_for_calibration` | (audit) | `athlete_id`, `from_level`, `to_level`, `twin_state_id` | Only when `confidence_level` increased relative to previous TwinState |
| `workout_generated` | `WorkoutGenerationAgent.generate` | (audit) | `generated_workout_id`, `planned_session_id`, `session_type`, `step_count` | After GeneratedWorkout + WorkoutStep insert, before commit |
| `coaching_message_generated` | `FirstMessageAgent.generate`, `PostWorkoutAgent.generate` | (audit) | `coaching_message_id`, `message_type`, `generation_event_id`, `prompt_version` | After CoachingMessage + GenerationEvent insert, before commit |

## Testing Requirements

This plan produces six `batch-N-<theme>-tests.md` files, one per ownership
domain. Each contains concrete test scenarios with Enforcement and Mock
Boundary classifications. The test architect loads these alongside the
contracts in this overview.

**Batch grouping:**

| Batch | Theme | Sub-Phases | Test File |
|-------|-------|------------|-----------|
| 1 | Auth & Identity | 1.1 | `batch-1-auth-identity-tests.md` |
| 2 | Core Schema Invariants | 1.2a, 1.2b, 1.2c | `batch-2-schema-invariants-tests.md` |
| 3 | Onboarding & Twin Bootstrap | 1.3 | `batch-3-onboarding-bootstrap-tests.md` |
| 4 | Plan Generation | 1.4 | `batch-4-plan-generation-tests.md` |
| 5 | Coaching Agents | 1.5a, 1.5b | `batch-5-coaching-agents-tests.md` |
| 6 | FIT Import & Post-Workout | 1.6 | `batch-6-fit-import-post-workout-tests.md` |

### Computational Invariant Fixtures (F1-F16)

Every computational invariant below has at least one concrete input→expected
output→tolerance triple derived from the **architecture specification**
(`docs/architecture/02-computations/`, `docs/architecture/00-foundations/`).
Where the architecture is silent on a specific constant, the fixture validates
a structural property the spec demands (monotonicity, ordering, approximate
magnitude) rather than an implementation-specific value. The test architect
must not re-derive approximations.

| # | Spec Source | Property Under Test | Fixture |
|---|-------------|--------------------|---------|
| F1 | `02-computations/banister-update.md` | Banister decay formula: `fitness(t)=fitness(t-1)×exp(-d/tau_f)+load`, `fatigue(t)=fatigue(t-1)×exp(-d/tau_fat)+load`, `form=fitness-fatigue`. Population tau: fitness=42d, fatigue=7d (aerobic). | **days_since=3, load=50**: `fitness=100×e^(-3/42)+50=100×0.93107+50=143.107`, `fatigue=40×e^(-3/7)+50=40×0.65144+50=76.058`, `form=67.049` (±0.05). **days_since=0, load=50**: `fitness=150`, `fatigue=90`, `form=60` (no decay). **load=0, days_since=1**: pure decay — `fitness=97.631`, `fatigue=34.675`, `form=62.956` (±0.05, formula verification only — not a specific days_since spec requirement). |
| F2 | `02-computations/load-computation.md` | Aerobic load formula: `Σ(exp(1.92×hrr_pct)−1)/3600`. The spec also states "1 hour at LT1 ≈ 100 units." | **hrr_pct=0.85, 3600 samples**: per-sample weight `e^(1.92×0.85)−1=e^1.632−1≈4.114`; raw formula total `=3600×4.114/3600=4.114`. The spec's ≈100 reference implies normalisation. Test: (a) output proportional to sample count (doubling→doubles), (b) monotonic with hrr_pct, (c) hrr_pct=0→≈0 contribution, (d) final normalised output for 1hr@LT1 ∈ [80, 120] (range check per spec's ≈100, not pinning the normalisation constant). |
| F3 | `02-computations/load-computation.md` | Power-based aerobic load: `Σ(watts/cp)^4 / 3600` (3600 IS in the spec). | **cp=300, 3600 samples @ 300W**: `Σ(300/300)^4/3600=3600×1.0/3600=1.0` (±0.001). **Half intensity (cp=300, watts=150)**: `Σ(150/300)^4/3600=3600×0.0625/3600=0.0625`. Test: monotonic with intensity, proportional to duration. |
| F4 | `02-computations/load-computation.md` | Structural load with gradient + density. Gradient cost factor 0.18, density coefficient 0.12 (0.08 if risk_flag), max penalty 15 — all from spec. | `distance=10km, surface=1.0, ascent=100m, recent_72h=50, risk_flag=false` → `base=10`, `gradient=(100/100)×0.18×10=1.8`, `density=min(50×0.12,15)=6.0`, `total=17.8` (±0.01). |
| F5 | `02-computations/load-computation.md` | Structural load: risk_flag halves density coefficient (0.08 vs 0.12 from spec). | Same as F4, `risk_flag=true` → `density=min(50×0.08,15)=4.0`, `total=15.8` (±0.01). |
| F6 | `02-computations/load-computation.md` | Structural load: density cap at 15 (from spec). | `recent_72h=200, risk_flag=false` → `density=min(200×0.12,15)=15.0` (capped). |
| F7 | `00-foundations/data-tiers.md` | Data tier 6-level inference matrix. | `(CHEST_STRAP_RR, RUNNING_POWER_METER)→T1`; `(WRIST_OPTICAL, RUNNING_POWER_METER)→T2`; `(CHEST_STRAP_RR, NONE)→T3`; `(CHEST_STRAP_NO_RR, NONE)→T4`; `(WRIST_OPTICAL, NONE)→T4`; `(NONE, NONE)→T5`; any other→T6. Exact (all rows in matrix). |
| F8 | `00-foundations/confidence-model.md` | Confidence level = `min(lt1.hr.prior_weight, lt2.hr.prior_weight)`. Thresholds: 4.0→MEDIUM, 8.0→HIGH. | `lt1=4.0, lt2=6.0 → min=4.0 → MEDIUM`. `lt1=9.0, lt2=10.0 → min=9.0 → HIGH`. `lt1=3.0, lt2=5.0 → min=3.0 → LOW`. **Conservative default**: when either lt1.hr or lt2.hr has no observations (null/missing/absent), output must be LOW — no data cannot produce confidence. |
| F9 | ADR-011 | Confidence ratchet: per-metric `max(stored, computed)`. Never decreases. | `stored=MEDIUM, computed=LOW → stored remains MEDIUM`. `stored=LOW, computed=HIGH → stored becomes HIGH`. When a previously-unmeasured metric acquires data: must reflect the new evidence (not stay at bootstrapped LOW). |
| F10 | `01-entities/athlete-physiology.md`, `00-foundations/confidence-model.md` | max_hr = 220 − age (from spec). LT1, LT2 bootstrapped from "age-graded population norms" — spec does not name specific factors. `questionnaire_estimate` prior_weight = 0.5 (from confidence model spec). | `dob=1990-01-15, today=2026-07-25 → age=36 → max_hr=184 (≥120)`. `0 < LT1 < LT2 < max_hr` (strict ordering). `prior_weight=0.5` at bootstrap. LT1, LT2 positive and finite. |
| F11 | `01-entities/athlete-fitness.md` | Form descriptor mapping: >15→"peaked", >5→"building", >-5→"training load", >-15→"heavy load", ≤-15→"overreached". | Boundary tests: `form=20→"peaked"`, `form=8→"building"`, `form=0→"training load"`, `form=-10→"heavy load"`, `form=-20→"overreached"`. Edge: `form=15→"building"` (not "peaked" — 15 is not >15). |
| F12 | `02-computations/plan-generation.md` | Phase proportions (race_event): 40% base, 30% threshold, 15% race-specific, 2w taper, 1w race-week. Spec does not name a proportion scaling factor. | `total_weeks=24 → taper=2, race=1, flexible=21`. Approx: base≈8 (≈38%), threshold≈6 (≈29%), race_specific≈7 (≈33%) — exact allocation may round. Structural invariants: (a) phase order base→threshold→race_specific→taper→race_week, (b) taper=2 and race_week=1 fixed, (c) sum = total_weeks, (d) total weeks ≥ 3. |
| F13 | `02-computations/load-computation.md` | Calibration eligibility: 6-condition AND gate. | `running+has_hr+not_manual+duration≥1200+hr_dropout≤0.20+no_gps_loss+no_sensor_malfunction→true`. Any single condition false→false. Boundaries: duration=1200→eligible, =1199→not; dropout=0.20→eligible, =0.21→not. |
| F14 | `02-computations/plan-generation.md` | Training length gate thresholds. | `marathon+novice: 20w→proceed, 21w→propose_intermediate`. `5k+experienced: 16w→proceed, 17w→propose_intermediate`. `weeks<8 AND fitness_level≤2→propose_shorter_goal`. Exact thresholds per `(event, experience)` table in spec. |
| F15 | `02-computations/plan-generation.md` | Experience level: years<2→novice, 2-5→intermediate, >5→experienced. | `years=1→novice, years=2→intermediate, years=5→intermediate, years=6→experienced`. |
| F16 | `02-computations/plan-generation.md` | Target performance gap: ≤3%→small, 3-8%→medium, 8-15%→large, >15%→very_large. | `gap=2%→small, gap=5%→medium, gap=12%→large, gap=20%→very_large`. Also test gap formula: `((target-current)/current)×100`. |

## Notes

### Architecture Clarifications
- The `form = fitness - fatigue` invariant is enforced at TWO layers: the
  `apply_banister_update` method computes it in application logic, and the
  `ck_athlete_fitness_aggregate_form_invariant` CHECK constraint validates it
  at the database layer. Both must be tested — the application test confirms
  the computation is correct; the integration test confirms the CHECK fires
  on a direct insert with a mismatched form.
- The aerobic load formula in the spec (`02-computations/load-computation.md`)
  is `Σ(exp(1.92 × hrr_pct) - 1) / 3600`. The spec also states "1 hour at LT1
  ≈ 100 units". These two statements are inconsistent (the raw formula yields
  ≈4.1, not 100). The test should validate the raw formula directly and
  check that the normalised output falls in [80, 120] for 1hr at LT1 —
  validating the spec's intent without pinning an unstated normalisation
  constant.

### Known Risks
- **FIT parser device variability**: Different devices (Garmin, Coros, Wahoo)
  write slightly different FIT structures. The parser handles the common
  subset. Tests should use a representative fixture FIT file, not a synthetic
  byte array, to validate the parse path end-to-end.
- **LLM proxy mocking boundary**: All agent tests must mock the LiteLLM proxy
  (external boundary) but let the agent's internal orchestration, repository
  calls, and GenerationEvent writing run real. Mocking the agent's internal
  service calls would hide idempotency-gate and event-writing bugs.
- **Structural load density cap**: The `min(..., 15.0)` cap from the spec
  (`02-computations/load-computation.md`) is easy to miss. A test with
  `recent_structural_72h=200` and `coefficient=0.12` would naively expect
  24.0 but the cap returns 15.0. The cap test is a required scenario (F6).
- **Normalisation divergence**: The aerobic load formula in the spec
  (`Σ(exp(1.92×hrr_pct)−1)/3600`) and the "1hr@LT1≈100 units" statement are
  inconsistent — the formula alone yields ~4.1, not 100. The normalised value
  depends on an implementation-specific constant not stated in the spec.
  Tests should validate the raw formula output AND the approximate magnitude,
  not a specific normalised value.