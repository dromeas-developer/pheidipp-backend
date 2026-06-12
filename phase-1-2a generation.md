# Phase-1-2a implementation plan

**Session ID:** ses_14b51fc96ffeNYi0jdKNfjSF9K
**Created:** 6/10/2026, 11:16:03 PM
**Updated:** 6/10/2026, 11:21:30 PM

---

## User

generate the implemenation plan for phase-1-2a as documented in the release plan

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 25.6s)

_Thinking:_


We need answer user wants generate implementation plan for phase-1-2a as documented in release plan. Need follow developer instructions. Need read sub-phase document fully before retrieval. Need find release plan phase 1.2a sub-phase document. Need inspect docs maybe via search. Need use tools. We need probably write implementation plan file. Need understand. We need use Read at least once before editing. Need maybe list release phases/features. User says phase-1-2a documented in release plan. Need locate sub-phase doc. Let's search release plan for "Phase-1.2a" or "1.2a".


**Tool: pheidipp-codebase-context_search_release_plan**

**Input:**
```json
{
  "entity_type": "feature",
  "phase": 1,
  "query": "Phase-1.2a sub-phase phase 1.2a",
  "top_k": 10
}
```

**Output:**
```
No results found.
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 14.8s)

_Thinking:_


Need list phases/features.


**Tool: pheidipp-codebase-context_list_release_plan_phases**

**Input:**
```json
{}
```

**Output:**
```
{
  "1": {
    "title": "Phase 1",
    "sub_phases": [
      {
        "entity": "phase-1-2a-profile-preferences-activity",
        "title": "Phase 1 \u2014 Core Models: Profile, Preferences, Activity",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-5b-workout-generation",
        "title": "Phase 1 \u2014 Workout Generation",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-3-onboarding-twin-bootstrap",
        "title": "Phase 1 \u2014 Onboarding & Twin Bootstrap",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-1-email-password-auth",
        "title": "Phase 1 \u2014 Email/Password Authentication",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-5a-first-coach-message",
        "title": "Phase 1 \u2014 First Coach Message",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-2b-plan-sessions",
        "title": "Phase 1 \u2014 Core Models: Plan & Sessions",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-4-plan-generation",
        "title": "Phase 1 \u2014 Plan Generation",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-6-simple-fit-import-post-workout",
        "title": "Phase 1 \u2014 Simple FIT Import & Post-Workout",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1-2c-twin-fitness-coaching-workouts",
        "title": "Phase 1 \u2014 Core Models: Twin, Fitness, Physiology, Coaching & Workouts",
        "feature_count": 0,
        "features": []
      },
      {
        "entity": "phase-1",
        "title": "Phase 1",
        "feature_count": 0,
        "features": []
      }
    ],
    "total_features": 0
  }
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 5.6s)

_Thinking:_


Need get phase context for 1 maybe includes subphase docs?


**Tool: pheidipp-codebase-context_get_phase_context**

**Input:**
```json
{
  "phase_number": 1
}
```

**Output:**
```
{
  "phase": 1,
  "sub_phases": [
    {
      "entity": "phase-1-2a-profile-preferences-activity",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Core Models: Profile, Preferences, Activity"
      },
      "sections": {
        "Objective": "Establish the supporting data structures that define who the athlete is (profile), how they train (preferences), and what they have done (activity). These entities are created during onboarding (1.3) and consumed by nearly every downstream system. `AthleteProfile` and `AthletePreferences` are each one-to-one with `Athlete`. `Activity` is the lean physiological observation \u2014 it represents a completed training session with minimal metadata, deferring rich signal storage to Phase 1.6.",
        "Challenge Notes": "This sub-phase isolates the athlete-context tables so the architect can focus on profile/preferences precision without being overwhelmed by the full schema. The `TrainingBlock` entity name from the initial draft has been superseded by `TrainingGoal` in the final Phase 1 design (handled in 1.2b).\n\nThe `athlete_profiles` table was created in Phase-1.1 with a minimal schema (demographics only \u2014 `date_of_birth`, `sex`, `height_cm`). This sub-phase extends it to the full schema via Alembic migration, adding the personalisation model columns (`gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`), location fields (`location_lat`, `location_lng`), `timezone`, `training_window`, `current_effort_generation`, `structural_risk_flag`, and `objective_thresholds`. The `athlete_profiles` table is never dropped and recreated \u2014 it is only extended.",
        "Capabilities Delivered": "- Schema for `AthleteProfile` (demographics, personalisation storage)\n- Schema for `AthletePreferences` (training configuration, data tier inference)\n- Schema for `Activity` (lean observation index)\n- Alembic migration for these tables and all required enums\n- All constraints, indexes, and enums defined",
        "Architectural Contracts Required": "- `01-entities/athlete-profile.md`\n- `01-entities/athlete-preferences.md`\n- `01-entities/activity.md`\n- `00-foundations/terminology.md` (enums)\n- `00-foundations/data-tiers.md` (data tier inference logic)",
        "Vision References Required": "- `twin/cold-start.md` \u2014 onboarding tier philosophy\n- `product/constraints.md` \u2014 running-only, no raw data surfaces",
        "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 `Athlete` and the minimal `athlete_profiles` table must exist. The `athlete_profiles` table was created in Phase-1.1 with a minimal schema (demographics only). This sub-phase extends it to the full schema via Alembic migration.",
        "Downstream Enablement": "- Phase-1.2b \u2014 `Activity` is referenced by `PlannedSession`\n- Phase-1.2c \u2014 `AthleteProfile` stores personalisation models (`gap_curve_model`, `weather_response_model`, `banister_constants`)\n- Phase-1.3 (Onboarding) \u2014 creates `AthleteProfile` and `AthletePreferences`\n- Phase-1.4 (Plan Generation) \u2014 `AthletePreferences.weekly_schedule` constrains session distribution\n- Phase-1.6 (FIT Import) \u2014 creates `Activity` records",
        "Invariants To Preserve": "- `AthleteProfile`: one per `Athlete`. Unique constraint on `athlete_id`.\n- `AthletePreferences`: one per `Athlete`. Unique constraint on `athlete_id`.\n- `Activity` has no `avg_hr`, `avg_pace`, `avg_power`, or lap data fields.\n- `Activity.source = 'manual_entry'` always has `calibration_eligible = false`, null load scores, null `fit_file_key`.\n- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null.",
        "Non-Goals": "- Data is not written to these tables in this sub-phase \u2014 only schema creation.\n- `AthleteIntegration` model (platform sync) \u2014 deferred to Phase 2.\n- `RawSensorStream` and `PhysiologicalSegment` \u2014 deferred to Phase 5/6.",
        "Exit Gate": "- All migrations run cleanly on a fresh database with no errors.\n- `Activity` has no `avg_hr`, `avg_pace`, `avg_power` columns.\n- `AthleteProfile` enforces unique constraint on `athlete_id`.\n- `AthletePreferences` enforces unique constraint on `athlete_id`.",
        "Risks": "- **Schema drift**: If 1.2b or 1.2c identify missing fields, migrations may need revision. Mitigation: expose schema early in each sub-phase.\n- **Enum alignment**: `ActivitySource`, `DataTier`, `PhysiologicalIntentState` and other enums must be correct now or downstream phases will break. Mitigation: copy exact from `terminology.md`."
      }
    },
    {
      "entity": "phase-1-5b-workout-generation",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Workout Generation"
      },
      "sections": {
        "Objective": "Enable the athlete to see their workout for the day, generated on-demand from the planned session and current twin state. At LOW confidence, targets are expressed as effort descriptions and broad ranges rather than precise numbers. The workout structure is a set of `WorkoutStep` records, each carrying a `physiological_intent`. This is the second major user-facing coaching moment \u2014 it must feel purposeful and appropriate to the athlete's data tier.",
        "Challenge Notes": "Early drafts included workout generation but used a JSON blob for the workout structure. The current architecture requires `WorkoutStep` records from day one \u2014 this is the foundation for all downstream session analysis. The `GeneratedWorkout` has a two-column target structure (`theoretical_targets` + `adjusted_targets`) that is always both written, even when identical. At this phase, `adjusted_targets` = `theoretical_targets` because no wellness or weather modifiers exist yet.\n\nThe architect must be aware of the data tier system. Tier 1-2 (power available) get power-based targets; Tier 3-4 (HR + GPS) get GAP-based targets; Tier 5-6 (no HR) get description-only workouts. The data tier is inferred from `AthletePreferences` during onboarding.",
        "Capabilities Delivered": "- `GET /athletes/{id}/today` \u2014 returns `GeneratedWorkout` for today's `PlannedSession`\n- `POST /athletes/{id}/sessions/{sid}/generate-workout` \u2014 explicit generation trigger\n- `WorkoutGenerationAgent` service (async, LLM)\n- Workout generation is idempotent for `(planned_session_id, date)`\n- `GeneratedWorkout` + `WorkoutStep` creation",
        "Architectural Contracts Required": "- `01-entities/generated-workout.md`\n- `01-entities/workout-step.md`\n- `01-entities/twin-state.md`\n- `01-entities/planned-session.md`\n- `00-foundations/data-tiers.md`\n- `03-agents/workout-generation-agent.md`\n- `04-platform/context-budget-service.md`",
        "Vision References Required": "- `coach/daily-view.md` \u2014 what the athlete sees (Today's Workout, Two-Column Target Display)\n- `twin/training-zones.md` \u2014 how targets are expressed at different confidence levels\n- `twin/confidence-and-uncertainty.md` \u2014 Tier 3 language tier",
        "Upstream Dependencies": "- Phase-1.3 (Onboarding) \u2014 `AthletePreferences` (data tier), `TwinState` (threshold estimates)\n- Phase-1.4 (Plan Generation) \u2014 `PlannedSession` must exist\n- Phase-1.5a (First Coach Message) \u2014 shared infrastructure (`ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler`)",
        "Downstream Enablement": "- Phase-1.6 (FIT Import) \u2014 athlete executes the workout, uploads FIT file, system compares actual to `GeneratedWorkout`\n- Phase-2 (Structured Workouts) \u2014 this is already using `WorkoutStep`, so 2c is mainly about richer structure",
        "Invariants To Preserve": "- `WorkoutStep.physiological_intent` is never null \u2014 every step has an intent.\n- `WorkoutStep.step_order` is unique within `GeneratedWorkout`.\n- `GeneratedWorkout` is idempotent for `(planned_session_id, generation_date)`. Calling twice returns the existing workout.\n- `theoretical_targets` and `adjusted_targets` always both written, even when identical.\n- `pace_sec_per_km` uses GAP values only. Never raw pace.\n- `twin_state_id` records which twin version drove generation. If twin recalibrates after generation, the workout is not retroactively updated.\n- Target type depends on data tier:\n  - Tier 1-2: `target_power_watts` primary, `target_gap_sec_per_km` secondary\n  - Tier 3-4: `target_gap_sec_per_km` primary, `target_hr_zone` secondary\n  - Tier 5-6: `description` only, numeric targets null\n- Recovery modifier defaults to `green`, reason null (modifiers not yet available).",
        "Non-Goals": "- Recovery modifier (wellness) on `adjusted_targets` \u2014 deferred to Phase 3\n- Weather modifier on `adjusted_targets` \u2014 deferred to Phase 3\n- Segmentation (PlannedSegment / PhysiologicalSegment) \u2014 deferred to Phase 5\n- Objectives in workout \u2014 deferred to Phase 4",
        "Exit Gate": "- `GET /athletes/{id}/today` returns a `GeneratedWorkout` with linked `WorkoutStep` records, each carrying a non-null `physiological_intent`.\n- A threshold session produces `WorkoutStep` records with appropriate states: warmup \u2192 low_aerobic \u2192 threshold (per rep) \u2192 recovery (between reps) \u2192 cooldown.\n- Targets are expressed in units appropriate to data tier (power for Tier 1-2, GAP for Tier 3-4, description for Tier 5-6).\n- Calling generation twice for the same `(planned_session_id, date)` returns the existing `GeneratedWorkout` without calling the LLM again.",
        "Risks": "- **Data tier edge cases**: An athlete says they have a power meter but doesn't. The system must gracefully fall back to lower-tier targets without crashing. Mitigation: validate data tier against actual hardware during FIT ingestion (Phase 2), but for now, trust what the athlete told us.\n- **Template vs genuine coaching**: At LOW confidence, targets are broad. The workout must still feel purposeful, not like a fill-in-the-blank template. The prompt engineering challenge is significant."
      }
    },
    {
      "entity": "phase-1-3-onboarding-twin-bootstrap",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Onboarding & Twin Bootstrap"
      },
      "sections": {
        "Objective": "Accept the onboarding questionnaire and produce the initial athlete state in one atomic transaction. This is the first sub-phase that writes to the database \u2014 all prior sub-phases established schema only. The twin is bootstrapped from population norms (Tier 3, questionnaire only, LOW confidence). No historical data, no peer matching, no LLM involvement. Pure Python computation.",
        "Challenge Notes": "Early drafts used `TrainingBlock` (single goal type). Current architecture has `TrainingGoal` with five goal types. For Phase 1, we support only `race_event` and `target_performance` \u2014 `fitness_improvement`, `maintenance`, and `recovery` are deferred because they require historical data, baseline fitness computation, or injury assessment that doesn't exist at Tier 3. The plan generation service (1.4) will call `plan-generation-race.md` (unified with `plan-generation-target-performance.md` in architecture).\n\nThe onboarding transaction is heavy \u2014 it creates `AthleteProfile`, `AthletePreferences`, `TrainingGoal`, `AthletePhysiology`, `AthleteFitness`, and `TwinState` atomically. If any step fails, all prior steps roll back. The `onboarding_complete` flag gates access to plan, coaching, and workout endpoints.",
        "Capabilities Delivered": "- `POST /athletes/{id}/onboarding` \u2014 atomic transaction creating:\n  1. `AthleteProfile` (demographics, structural risk flag)\n  2. `AthletePreferences` (training config, data tier inference)\n  3. `TrainingGoal` (`race_event` or `target_performance` only)\n  4. `AthletePhysiology` (bootstrapped from age-graded population norms, LOW confidence)\n  5. `AthleteFitness` (zero fitness/fatigue, population time constants)\n  6. `TwinState` (LOW confidence, `trigger = questionnaire`)\n  7. Sets `athlete.onboarding_complete = true`\n- `GET /athletes/{id}/onboarding` \u2014 returns current onboarding status\n- `GET /athletes/{id}/twin` \u2014 returns latest `TwinState`\n- `GET /athletes/{id}/twin/history` \u2014 all snapshots\n- `GET /athletes/{id}/profile` \u2014 read AthleteProfile\n- `PATCH /athletes/{id}/profile` \u2014 update mutable fields\n- `GET /athletes/{id}/preferences` \u2014 read AthletePreferences\n- `PATCH /athletes/{id}/preferences` \u2014 update mutable fields",
        "Architectural Contracts Required": "- `01-entities/athlete.md`\n- `01-entities/athlete-profile.md`\n- `01-entities/athlete-preferences.md`\n- `01-entities/training-goal.md`\n- `01-entities/training-plan.md`\n- `01-entities/twin-state.md`\n- `01-entities/athlete-physiology.md`\n- `01-entities/athlete-fitness.md`\n- `00-foundations/data-tiers.md` (data tier inference)\n- `00-foundations/confidence-model.md`",
        "Vision References Required": "- `product/plan-generation.md` \u2014 strategic roadmap concept\n- `twin/cold-start.md` \u2014 Tier 3 bootstrap philosophy\n- `twin/confidence-and-uncertainty.md` \u2014 communication under uncertainty\n- `coach/first-message.md` \u2014 voice and content of first coach message (prepared for in 1.5a)",
        "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 `Athlete` must exist and be authenticated\n- Phase-1.2a (Profile & Preferences) \u2014 schema must exist\n- Phase-1.21 (Plan & Sessions) \u2014 `TrainingGoal` schema must exist\n- Phase-1.2c (Twin & Fitness) \u2014 `TwinState`, `AthletePhysiology`, `AthleteFitness` schema must exist",
        "Downstream Enablement": "- Phase-1.4 (Plan Generation) \u2014 requires `TrainingGoal`, `TwinState`\n- Phase-1.5a (First Coach Message) \u2014 triggered after onboarding completes\n- Phase-1.5b (Workout Generation) \u2014 requires `TwinState` for target generation\n- Phase-1.6 (FIT Import) \u2014 updates `AthleteFitness` and creates new `TwinState`",
        "Invariants To Preserve": "- The entire onboarding sequence runs in one database transaction. If any step fails, all prior steps roll back. The athlete remains in `onboarding_complete = false` state.\n- `TwinBootstrapService` is pure Python. No LLM call, no external API call. Must complete within 200ms.\n- Re-onboarding is not supported. Calling `POST /athletes/{id}/onboarding` when `onboarding_complete = true` returns 409. Athletes update preferences via PATCH.\n- `TrainingGoal` enforces single active goal per athlete (409 on second creation).\n- `AthleteProfile.structural_risk_flag` is computed from `AthletePreferences.sport_background`.\n- Data tier is inferred from `hr_source` and `power_source` on `AthletePreferences`.\n- Threshold estimates (`lt1_*`, `lt2_*`, `max_hr`) are bootstrapped from age-graded population norms using `AthleteProfile.date_of_birth`.\n- `AthleteFitness` is initialised to zero fitness, zero fatigue.\n- `TwinState.confidence_level = low`, `trigger = questionnaire`.",
        "Non-Goals": "- `fitness_improvement`, `maintenance`, `recovery` goal types \u2014 deferred\n- `Objective` seeding \u2014 deferred to Phase 4 (requires data)\n- Menstrual cycle tracking (`CyclePhaseLog`) \u2014 deferred to Phase 3\n- WeeklPlan creation \u2014 this is plan generation (1.4), not onboarding\n- First coach message generation \u2014 this is 1.5a, not onboarding",
        "Exit Gate": "- Submitting a complete questionnaire creates all six entities in one transaction.\n- Simulating a failure mid-transaction leaves no partial records.\n- Attempting to onboard twice returns 409.\n- `GET /athletes/{id}/twin` returns a `TwinState` with `confidence_level = low` and non-null threshold estimates derived from population norms.",
        "Risks": "- **Heavy transaction**: 8 entities created in one transaction. Consider if any can be split (e.g., `AthleteProfile`/`AthletePreferences` as a separate \"profile creation\" step before the full onboarding). However, the atomicity invariant is strict \u2014 partial onboarding is worse than slow onboarding.\n- **Data tier inference edge cases**: If `hr_source` or `power_source` are not set, the data tier inference must have a sensible fallback. Mitigation: default to manual entry (Tier 6) and let the athlete update later."
      }
    },
    {
      "entity": "phase-1-1-email-password-auth",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Email/Password Authentication"
      },
      "sections": {
        "Objective": "Establish the authentication layer that all subsequent sub-phases build upon. This delivers a secure, token-based authentication system supporting email/password registration and login. OAuth providers (Google, Strava) are explicitly deferred to later phases \u2014 the schema in `AthleteAuth` is designed to accommodate them, but this sub-phase implements only the email/password provider.",
        "Challenge Notes": "OAuth providers (Google, Strava) and account linking are deferred to a later phase to reduce initial complexity. The `AthleteAuth` entity schema already supports multiple providers, so adding OAuth later is an extension, not a rewrite.\n\nRegistration atomically creates `Athlete` + `AthleteAuth` + `AthleteProfile`. The `AthleteProfile` table is created with a **minimal schema** containing only the demographics fields needed at registration (`date_of_birth`, `sex`, `height_cm`). The full schema (personalisation models, location, training window, etc.) is extended in Phase-1.2a. The architect can deduce the minimal schema from the API contracts in `athlete-auth.md` and `athlete.md`.",
        "Capabilities Delivered": "- Athlete can register with email + password (`POST /auth/register`)\n- Athlete can log in with email + password (`POST /auth/login`)\n- Access token (JWT, 15min expiry) and refresh token (30-day expiry, rotated on use) lifecycle\n- `require_self` route dependency for athlete-scoped endpoints\n- Secure password hashing (bcrypt)\n- Multi-device session support (via refresh token table)",
        "Architectural Contracts Required": "- `01-entities/athlete.md`\n- `01-entities/athlete-auth.md`\n- `01-entities/athlete-profile.md` (minimal schema \u2014 only demographics columns needed for registration; full schema completed in Phase-1.2a)",
        "Vision References Required": "- `product/brand-philosophy.md` \u2014 \"no AI-feel, no tech jargon\"\n- `product/constraints.md` \u2014 security constraints",
        "Upstream Dependencies": "None. This is the first sub-phase.",
        "Downstream Enablement": "- Phase-1.2a (Profile & Preferences) \u2014 registration creates the `Athlete` record\n- Phase-1.3 (Onboarding) \u2014 requires authenticated user to complete onboarding\n- All athlete-scoped endpoints require the auth layer",
        "Invariants To Preserve": "- `email` is unique across all athletes (case-insensitive)\n- `hashed_password` is never returned by any API endpoint or included in any log\n- Refresh tokens are rotated on every use \u2014 old token is revoked atomically with new token creation\n- Registration atomically creates `Athlete` and minimal `AthleteProfile`. If either fails, neither is committed.",
        "Non-Goals": "- OAuth (Google, Strava) \u2014 deferred to a later phase\n- Email verification flow\n- Password reset flow\n- Rate limiting (deferred to infrastructure hardening)",
        "Exit Gate": "- `POST /auth/register` creates an `Athlete` and returns a valid token pair.\n- `POST /auth/login` with wrong password returns 401; with correct password returns a new token pair.\n- An authenticated request to an athlete-scoped route with a JWT belonging to a different athlete returns 403.\n- A request with an expired access token returns 401.\n- Refresh token rotation: after `POST /auth/refresh`, the old refresh token is invalid and a new one is usable.",
        "Risks": "- **Password compromise**: bcrypt with appropriate work factor (12+) mitigates this.\n- **Token theft**: Short-lived access tokens + refresh token rotation limit window of exposure."
      }
    },
    {
      "entity": "phase-1-5a-first-coach-message",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 First Coach Message"
      },
      "sections": {
        "Objective": "Deliver the athlete's first meaningful interaction with the coach: a four-paragraph first message triggered after onboarding completes. This message must demonstrate that the coach has read and understood the athlete's specific data. At LOW confidence, the language tier is Tier 3: \"Based on what you've described...\" The trigger is the `onboarding_completed` event, and the message is created exactly once per active goal.",
        "Challenge Notes": "The first coach message sets the tone for the entire coaching relationship. If it feels generic or templated, the athlete will never fully trust the coach. If it feels genuinely personal \u2014 referencing specific background, goal, and structural risk \u2014 the athlete will engage. Vision reference: `coach/first-message.md` emphaseses that this is not about data dumping but about forming a coaching relationship.\n\nThe architect must be aware that `FirstMessageAgent` is an LLM agent, not a template. It requires `ContextBudgetService` (to stay within token limits), `PromptRegistry` (for prompt versioning), and `TwinContextAssembler` (to translate twin state into coaching language). Every LLM call writes a `GenerationEvent`. The `AthleteProfile` and `AthletePreferences` created during onboarding provide the specific data that makes the message personal.",
        "Capabilities Delivered": "- `POST /athletes/{id}/coach/first-message` \u2014 triggers `FirstMessageAgent`. Returns 409 if message already exists.\n- `GET /athletes/{id}/coach/messages` \u2014 returns all `CoachingMessage` records for the athlete, ordered by `generated_at` desc\n- `FirstMessageAgent` service (async, LLM)\n- `ContextBudgetService` (token budget enforcement, 3k-5k tokens)\n- `PromptRegistry` (loads and versions prompt templates)\n- `TwinContextAssembler` (translates `TwinState` into coaching-relevant language)\n- Every LLM call writes a `GenerationEvent` (success or failure)",
        "Architectural Contracts Required": "- `01-entities/coaching-message.md`\n- `01-entities/generation-event.md`\n- `01-entities/twin-state.md`\n- `01-entities/athlete-profile.md`\n- `01-entities/athlete-preferences.md`\n- `03-agents/first-message-agent.md`\n- `04-platform/context-budget-service.md`",
        "Vision References Required": "- `coach/first-message.md` \u2014 four-paragraph structure, voice constraints\n- `coach/voice-and-format.md` \u2014 global voice rules\n- `twin/confidence-and-uncertainty.md` \u2014 Tier 3 language tier",
        "Upstream Dependencies": "- Phase-1.3 (Onboarding) \u2014 `AthleteProfile`, `AthletePreferences`, `TrainingGoal`, `TwinState` must exist.\n- Phase-1.2c (Twin & Fitness) \u2014 `CoachingMessage`, `GenerationEvent` schema must exist.",
        "Downstream Enablement": "- Phase-1.5b (Workout Generation) \u2014 shares `ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler`\n- Phase-1.6 (FIT Import) \u2014 `PostWorkoutAgent` extends the agent foundation built here",
        "Invariants To Preserve": "- The first coach message must not be regenerated once it exists. The endpoint returns 409 on a second call. If quality is poor, the prompt must be improved and re-tested before re-enabling generation.\n- Four paragraphs: Welcome, What Was Found, The Plan, Closing.\n- No bullets, no headers, no emojis, no generic affirmations.\n- No acronyms without explanation (HR, LT1, GAP \u2014 all plain English).\n- Paragraph 2 MUST reference the athlete's specific `sport_background` and `structural_risk_flag` where applicable.\n- The message could NOT have been written without reading this athlete's specific data \u2014 if it reads as a template, it has failed.\n- Every LLM call \u2014 success or failure \u2014 writes a `GenerationEvent`. No silent failures.\n- Context windows are hard limits, not targets. `ContextBudgetService` enforces them before the API call.\n- `first_message` \u2014 only one per athlete per active goal. 409 on second call.",
        "Non-Goals": "- Objectives in the first message \u2014 deferred to Phase 4 (requires data)\n- Comparable session references \u2014 no sessions exist yet\n- Wellness or weather modifiers \u2014 deferred to Phase 3",
        "Exit Gate": "- `POST /athletes/{id}/coach/first-message` returns a four-paragraph message with no bullets, no headers, no emojis, and no generic affirmations.\n- The message references the athlete's specific sport background and structural risk flag where applicable.\n- A failed LLM call (e.g. API timeout) writes a `GenerationEvent` with `success = false` and returns a 503 to the caller \u2014 no silent data corruption.\n- Calling `POST /athletes/{id}/coach/first-message` twice returns 409 on the second call without calling the LLM.",
        "Risks": "- **Prompt quality gate**: The first message is the most important engineering asset in Phase 1. It must be developed and tested in isolation (script or notebook) before the endpoint is wired. Voice quality review is a go/no-go gate.\n- **Context budget overflow**: At LOW confidence, the twin state has many null fields. The `ContextBudgetService` must handle sparse data gracefully without exceeding token limits."
      }
    },
    {
      "entity": "phase-1-2b-plan-sessions",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Core Models: Plan & Sessions"
      },
      "sections": {
        "Objective": "Establish the schema for the training plan hierarchy: from the athlete's goal, through the strategic plan and weekly breakdown, to individual planned sessions and scheduled checkpoints. This is a purely schema sub-phase \u2014 no services or endpoints are built here. The plan generation logic (1.4) will populate these tables, and the coaching agents (1.5) will query them.",
        "Challenge Notes": "The plan generation service and the `TrainingPlan`/`PlannedSession` schema were initially treated as a single feature. This sub-phase separates the schema from the generation logic so the architect can reason about each independently. The `TrainingBlock` entity from early drafts has been replaced by `TrainingGoal` with a richer set of fields and support for multiple goal types. The `WeeklyPlan` / `WeeklySession` hierarchy is new in the current architecture \u2014 it implements the \"weekly coaching rhythm\" from the vision.",
        "Capabilities Delivered": "- Schema for `TrainingGoal` (goal definition, immutable after creation)\n- Schema for `TrainingPlan` (phase arc, checkpoint schedule)\n- Schema for `WeeklyPlan` (weekly session list, immutable once active)\n- Schema for `WeeklySession` (links `WeeklyPlan` to `PlannedSession`)\n- Schema for `PlannedSession` (individual session with intent, checkpoint flags)\n- Schema for `Checkpoint` (calibration, benchmark, race_simulation, secondary_race, progress_review)\n- All constraints, indexes, and enums (`GoalType`, `PhaseLabel`, `SessionType`, `CheckpointType`, etc.)",
        "Architectural Contracts Required": "- `01-entities/training-goal.md`\n- `01-entities/training-plan.md`\n- `01-entities/weekly-plan.md`\n- `01-entities/planned-session.md`\n- `01-entities/checkpoint.md`\n- `00-foundations/terminology.md`",
        "Vision References Required": "- `product/plan-generation.md` \u2014 strategic roadmap concept\n- `product/training-plan-checkpoints.md` \u2014 checkpoint hierarchy and scheduling\n- `coach/plan-visibility.md` \u2014 what the athlete sees",
        "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 `Athlete` must exist before `TrainingGoal` can reference it.\n- Phase-1.2a (Profile & Preferences) \u2014 `AthletePreferences.weekly_schedule` contains the `long_workout` day used by plan generation.",
        "Downstream Enablement": "- Phase-1.3 (Onboarding) \u2014 creates the `TrainingGoal`\n- Phase-1.4 (Plan Generation) \u2014 populates `TrainingPlan`, `WeeklyPlan`, `PlannedSession`, `Checkpoint`\n- Phase-1.5b (Workout Generation) \u2014 queries `PlannedSession` for `GeneratedWorkout`\n- Phase-1.6 (FIT Import) \u2014 `Activity.planned_session_id` FK links to `PlannedSession`",
        "Invariants To Preserve": "- `TrainingGoal`: one active per athlete (partial unique index on `athlete_id WHERE status = 'active'`).\n- `TrainingGoal` fields `goal_type`, `goal_event_type`, `fitness_level`, etc. are immutable after creation.\n- `TrainingPlan` is never deleted \u2014 `superseded_at` is set when replaced.\n- `WeeklyPlan`: one per `(training_plan_id, week_number)`. Sessions array is immutable once `status = active`.\n- `PlannedSession` records for a superseded `TrainingPlan` retain the old `training_plan_id` \u2014 queries for \"current plan sessions\" must join through `WeeklyPlan`.\n- `Checkpoint` cannot be created retroactively \u2014 scheduled during plan synthesis.\n- `Checkpoint` completion fields (`metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`) are set atomically.",
        "Non-Goals": "- Plan generation logic \u2014 deferred to 1.4\n- Session lifecycle (skip, miss, reschedule) \u2014 deferred to Phase 4\n- Workout library \u2014 deferred to Phase 4\n- Plan regeneration on confidence upgrade \u2014 deferred to Phase 2",
        "Exit Gate": "- All migrations run cleanly.\n- `TrainingGoal` enforces single active goal per athlete at DB level.\n- `WeeklyPlan` enforces one per `(training_plan_id, week_number)`.\n- `Checkpoint` enforces `planned_session_id` as one-to-one with `PlannedSession`.",
        "Risks": "- **Checkpoint-PlannedSession circular reference**: `Checkpoint` references `PlannedSession`, and `PlannedSession` has `checkpoint_type`/`checkpoint_metric` fields. The architect must decide whether `Checkpoint` is created first or atomically with the `PlannedSession`. Recommended approach: atomic creation in the plan generation service.\n- **Plan supersession cascade**: When a plan is superseded, `PlannedSession` records retain the old `training_plan_id`. If 1.2b misses the denormalisation warning, queries may return stale sessions. Mitigation: document the correct query pattern in the schema."
      }
    },
    {
      "entity": "phase-1-4-plan-generation",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Plan Generation"
      },
      "sections": {
        "Objective": "Generate a complete training plan from the bootstrapped twin and defined goal. This is a pure Python service \u2014 no LLM, no external API calls. The plan skeleton gives the coaching agents in 1.5 the phase context they need to generate meaningful messages and workouts. For Phase 1, only `race_event` and `target_performance` goal types are supported.",
        "Challenge Notes": "Early drafts only created `TrainingPlan` and `PlannedSession`. The current architecture adds `WeeklyPlan` and `WeeklySession` to implement the \"weekly coaching rhythm\" from the vision. This means 1.4 creates the full hierarchy: TrainingPlan \u2192 WeeklyPlan \u2192 WeeklySession \u2192 PlannedSession, plus Checkpoints. The architect must be aware of the `PlannedSession.training_plan_id` denormalisation caveat \u2014 the authoritative plan reference is always through `WeeklyPlan`.",
        "Capabilities Delivered": "- `TrainingPlan` with phase arc appropriate to `goal_type`\n- `WeeklyPlan` + `WeeklySession` for all weeks\n- `PlannedSession` records (with checkpoint flags) for all sessions\n- `Checkpoint` records (calibration, benchmark, progress_review)\n- `GET /athletes/{id}/plan` \u2014 returns plan with phases\n- `GET /athletes/{id}/plan/sessions` \u2014 all sessions\n- `GET /athletes/{id}/plan/upcoming` \u2014 next 5 sessions\n- `GET /athletes/{id}/plan/checkpoints` \u2014 all checkpoints",
        "Architectural Contracts Required": "- `01-entities/training-goal.md`\n- `01-entities/training-plan.md`\n- `01-entities/weekly-plan.md`\n- `01-entities/planned-session.md`\n- `01-entities/checkpoint.md`\n- `01-entities/twin-state.md`\n- `02-computations/plan-generation.md`\n- `02-computations/plan-generation-race.md`\n- `02-computations/plan-generation-target-performance.md`",
        "Vision References Required": "- `product/plan-generation.md` \u2014 strategic roadmap concept\n- `product/training-plan-checkpoints.md` \u2014 checkpoint hierarchy\n- `coach/plan-visibility.md` \u2014 what the athlete sees\n- `weekly-coaching-rhythm.md` \u2014 the weekly adjustment layer",
        "Upstream Dependencies": "- Phase-1.3 (Onboarding) \u2014 `TrainingGoal` and `TwinState` must exist\n- Phase-1.2b (Plan & Sessions) \u2014 schema must exist",
        "Downstream Enablement": "- Phase-1.5a (First Coach Message) \u2014 references plan phases\n- Phase-1.5b (Workout Generation) \u2014 generates workout for `PlannedSession`\n- Phase-1.6 (FIT Import) \u2014 `Activity` links to `PlannedSession`",
        "Invariants To Preserve": "- `PlanGenerationService` is pure Python \u2014 no LLM, no external API calls.\n- Phases have correct proportional duration (race_event example: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week).\n- `PlannedSession` records cover the full duration to the goal event with no gaps.\n- No two consecutive quality sessions appear in generated schedule.\n- Structural rules are invariant: long run always followed by rest or recovery, threshold always sandwiched between easy days.\n- Superseded `TrainingPlan` records are never deleted \u2014 `superseded_at` is set.\n- `Checkpoint` cannot be created retroactively \u2014 scheduled during plan synthesis, not after session completion.\n- `PlannedSession` records for a superseded `TrainingPlan` retain the old `training_plan_id` \u2014 queries for \"current plan sessions\" must join through `WeeklyPlan`.\n- `WeeklyPlan` sessions array is immutable once `status = active`.",
        "Non-Goals": "- `fitness_improvement`, `maintenance`, `recovery` goal types \u2014 deferred\n- Plan regeneration on confidence upgrade \u2014 deferred to Phase 2\n- Session lifecycle management (skip, miss, redistribute) \u2014 deferred to Phase 4\n- Workout library \u2014 deferred to Phase 4\n- Plan regeneration on goal date change > 7 days \u2014 keep minimal, just re-generate",
        "Exit Gate": "- After onboarding, `GET /athletes/{id}/plan` returns a `TrainingPlan` with correct phase sequence for the `goal_type`.\n- Phases have correct proportional durations.\n- `PlannedSession` records cover the full duration to the goal event with no gaps.\n- No two consecutive quality sessions appear in the generated schedule.\n- `GET /athletes/{id}/plan/checkpoints` returns scheduled checkpoints.",
        "Risks": "- **Mental model shift**: The architect may expect to generate only `TrainingPlan` + `PlannedSession`. The `WeeklyPlan` / `WeeklySession` hierarchy adds complexity but is required for the weekly rhythm. Must be clear in handoff.\n- **Checkpoint complexity**: Checkpoints are scheduled based on confidence gaps, race calendar, phase transitions, and regular intervals. The scheduling logic is non-trivial."
      }
    },
    {
      "entity": "phase-1-6-simple-fit-import-post-workout",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Simple FIT Import & Post-Workout"
      },
      "sections": {
        "Objective": "Close the loop: athlete uploads a FIT file, system extracts HR data, computes load, updates fitness/fatigue, produces a new TwinState snapshot, and generates a post-workout coach message. This is the first time real training data flows through the system. The scope is intentionally \"simple\" \u2014 HR data only, no calibration, no threshold detection, no segmentation. The goal is to prove end-to-end data flow before expanding to the full ingestion pipeline in Phase 2.",
        "Challenge Notes": "Early drafts used a manual entry system with a `PostWorkoutAgent` that produced analysis from typed notes. This sub-phase replaces manual entry with a simple FIT file upload and a much more meaningful analysis \u2014 the post-workout message now references actual HR data, duration, and load. The `Activity` model and its invariants were designed with FIT data in mind; we are now putting them to use for the first time.\n\nThe key simplifications are:\n- HR data only (not power, not GPS, not RR intervals)\n- Heuristic load computation (not threshold-referenced)\n- No calibration \u2014 all activities are `calibration_eligible = false`\n- No `RawSensorStream` (cleaned stream storage) \u2014 data is parsed on-the-fly\n- No `ExecutionObservation` or rep-level analysis \u2014 post-workout is just compliance + effort narrative\n- Object storage stores the raw FIT file but `RawSensorStream` entity is not created",
        "Capabilities Delivered": "- `POST /athletes/{id}/activities/upload` \u2014 accept FIT file, return 202 Accepted with task_id\n- `POST /athletes/{id}/activities/{aid}/analyse` \u2014 trigger `PostWorkoutAgent`\n- `GET /athletes/{id}/activities` \u2014 activity list\n- `GET /athletes/{id}/activities/{aid}` \u2014 single activity\n- `GET /athletes/{id}/activities/{aid}/analysis` \u2014 analysis + coaching message\n- `FitParserService` \u2014 extracts HR data, duration, start_time from FIT file\n- `ObjectStorageClient` \u2014 stores raw FIT file in object storage (first runtime use of storage)\n- `LoadComputationService` \u2014 computes `aerobic_load` from HR data (heuristic formula)\n- `TwinRecalibrationService` \u2014 updates `AthleteFitness` via Banister model\n- New `TwinState` with `trigger = activity_sync`\n- `ComplianceService` \u2014 compares actual session to `PlannedSession`\n- `PostWorkoutAgent` \u2014 generates three-paragraph post-workout message\n- `GenerationEvent` logging for every LLM call",
        "Architectural Contracts Required": "- `01-entities/activity.md`\n- `01-entities/twin-state.md`\n- `01-entities/athlete-fitness.md`\n- `01-entities/athlete-physiology.md`\n- `01-entities/coaching-message.md`\n- `01-entities/generation-event.md`\n- `01-entities/generated-workout.md`\n- `01-entities/planned-session.md`\n- `02-computations/load-computation.md`\n- `02-computations/banister-update.md`\n- `03-agents/post-workout-agent.md`\n- `04-platform/object-storage-client.md`",
        "Vision References Required": "- `coach/post-workout.md` \u2014 post-workout message content rules, three-paragraph structure\n- `coach/daily-view.md` \u2014 execution analysis for athlete\n- `twin/confidence-and-uncertainty.md` \u2014 how execution is described under uncertainty\n- `twin/training-zones.md` \u2014 how thresholds define zones",
        "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 authenticated user\n- Phase-1.2a (Profile & Activity) \u2014 `Activity` schema exists\n- Phase-1.2c (Twin & Fitness) \u2014 `TwinState`, `AthleteFitness`, `AthletePhysiology` schema exists\n- Phase-1.4 (Plan Generation) \u2014 `PlannedSession` must exist for compliance comparison\n- Phase-1.5 (Coaching Agents) \u2014 `PostWorkoutAgent` builds on agent infrastructure from .5a",
        "Downstream Enablement": "- Phase-2 (FIT Ingestion Pipeline) \u2014 expands from manual upload to auto-sync (intervals.icu, Garmin)\n- Phase-2b (Load Computation) \u2014 adds power, GPS, structural load; threshold-referenced formulas\n- Phase-4 (Execution Observation) \u2014 adds rep-level analysis, `ExecutionObservation` entity",
        "Invariants To Preserve": "- Object storage upload happens BEFORE `Activity` record creation. If upload fails, no `Activity` is created and the task retries.\n- `fit_file_key` is always set for `source != manual_entry`.\n- No averaged fields (`avg_hr`, `avg_pace`, etc.) are stored on `Activity`.\n- `LoadComputationService` must receive raw records from `FitParserService`, not summary stats.\n- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService`.\n- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden. For Phase 1.6, all sessions are NOT calibration-eligible.\n- `TwinState` is append-only. `TwinRecalibrationService` never updates the existing record.\n- `PostWorkoutAgent` is idempotent \u2014 calling the endpoint twice returns the same `CoachingMessage` without calling the LLM again.\n- Every LLM call writes a `GenerationEvent`.\n- `Activity` deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null.",
        "Simplifications (Deferrals to Phase 2+)": "- **No calibration**: `calibration_eligible = false` for all sessions. Threshold detection requires multiple sessions with specific structure.\n- **No signal cleaning**: Raw FIT HR data used directly. Cleaning pipeline (Phase 5) will refine this.\n- **No RawSensorStream**: Cleaned stream not stored. Data is parsed on-the-fly and discarded.\n- **No ExecutionObservation**: Rep-level analysis requires segmentation and `WorkoutStep` mapping. Phase 4.\n- **No comparable sessions**: Need history for this. Phase 4.\n- **No wellness/weather modifiers on load or targets**: Phase 3.",
        "Exit Gate": "- Uploading a valid FIT file creates an `Activity` with `source = manual_upload`, non-null `fit_file_key`, and populated load scores.\n- `GET /athletes/{id}/twin/history` shows a new `TwinState` after the upload, with updated `fitness` and `fatigue` scores.\n- `POST /athletes/{id}/activities/{aid}/analyse` returns a three-paragraph post-workout coach message.\n- Calling the analyse endpoint twice returns the same message \u2014 no second LLM call.\n- Simulating an object storage failure during upload does not create an `Activity` record.",
        "Risks": "- **FIT parser brittleness**: Different devices (Garmin, Coros, etc.) write slightly different FIT structures. The parser must handle the common subset robustly and fail gracefully on unsupported files.\n- **Load computation accuracy**: Heuristic formulas are imprecise but sufficient for Phase 1. The athlete must not be told these are definitive.\n- **Object storage first use**: This is the first runtime use of object storage. If bucket permissions or connectivity are misconfigured, the entire flow fails. Mitigation: test upload path independently of the full pipeline."
      }
    },
    {
      "entity": "phase-1-2c-twin-fitness-coaching-workouts",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1 \u2014 Core Models: Twin, Fitness, Physiology, Coaching & Workouts"
      },
      "sections": {
        "Objective": "Establish the schema for the athlete's digital twin (fitness, physiology, snapshots), coaching output (messages, generation events), and workout structure. This is the most complex schema sub-phase \u2014 it defines how the system tracks the athlete's physiological state over time, how coaching messages are stored, and how workouts are structured. No services or endpoints are built here; this is pure schema and migration.",
        "Challenge Notes": "This sub-phase isolates the twin/coaching/workout cluster so the architect can reason about append-only vs mutable storage, inline snapshot design, and the relationship between `TwinState`, `AthletePhysiology`, and `AthleteFitness` without being overwhelmed by the full schema. The initial design used `TrainingBlock` as a single entity; the Phase 1 plan separates `TrainingGoal` (in 1.2b) from `AthletePhysiology` and `AthleteFitness` (mutable current-state tables), with `TwinState` as an append-only inline snapshot.",
        "Capabilities Delivered": "- Schema for `TwinState` (append-only inline snapshots of fitness/fatigue/thresholds)\n- Schema for `AthletePhysiology` (per-dimension Bayesian state, mutable)\n- Schema for `AthleteFitness` (Banister scores, mutable)\n- Schema for `CoachingMessage` (write-once, append-only)\n- Schema for `GenerationEvent` (every LLM call, success or failure)\n- Schema for `GeneratedWorkout` (two-column target structure, immutable)\n- Schema for `WorkoutStep` (individual steps with physiological intent)\n- All constraints, indexes, and enums (`TwinConfidenceLevel`, `TwinTrigger`, `MessageType`, `PhysiologicalIntentState`, etc.)",
        "Architectural Contracts Required": "- `01-entities/twin-state.md`\n- `01-entities/athlete-physiology.md`\n- `01-entities/athlete-fitness.md`\n- `01-entities/coaching-message.md`\n- `01-entities/generation-event.md`\n- `01-entities/generated-workout.md`\n- `01-entities/workout-step.md`\n- `00-foundations/terminology.md`\n- `00-foundations/confidence-model.md`",
        "Vision References Required": "- `twin/confidence-and-uncertainty.md` \u2014 confidence levels and athlete communication\n- `twin/load-fatigue.md` \u2014 three-dimensional approach rationale\n- `coach/daily-view.md` \u2014 what the athlete sees on the daily screen",
        "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 `Athlete` must exist before any of these entities can reference it.\n- Phase-1.2b (Plan & Sessions) \u2014 `GeneratedWorkout` FKs to `PlannedSession`.",
        "Downstream Enablement": "- Phase-1.3 (Onboarding) \u2014 bootstraps `AthletePhysiology`, `AthleteFitness`, first `TwinState`\n- Phase-1.5 (Coaching Agents) \u2014 writes `CoachingMessage`, `GenerationEvent`, `GeneratedWorkout`, `WorkoutStep`\n- Phase-1.6 (FIT Import) \u2014 updates `AthleteFitness`, creates new `TwinState`, triggers `PostWorkoutAgent`",
        "Invariants To Preserve": "- `TwinState` is append-only \u2014 no UPDATE or DELETE. `TwinStateRepository` exposes only `insert`, `get_latest`, `get_history`.\n- `TwinState` `training_goal_id`, `model_version`, and `activity_id` are frozen at creation.\n- `TwinState.confidence_level` is derived as `min(LT1 HR, LT2 HR)` from `AthletePhysiology`.\n- `AthleteFitness`: one per athlete, mutable. `form` must always equal `fitness - fatigue`.\n- `AthletePhysiology`: one per athlete, mutable. `max_hr` bootstrapped from `220 - age`.\n- `CoachingMessage` is immutable after creation. `first_message` \u2014 only one per active goal. `post_workout` \u2014 one per `activity_id`.\n- `GenerationEvent` is written for every LLM call, success or failure. Records are never modified.\n- `GeneratedWorkout` is append-only. `theoretical_targets` and `adjusted_targets` always both written.\n- `WorkoutStep.physiological_intent` is never null.",
        "Non-Goals": "- No data is written to any of these tables in this sub-phase.\n- Services (load computation, twin recalibration, workout generation) \u2014 deferred to later sub-phases.\n- `ExecutionObservation`, `RawSensorStream`, `PhysiologicalSegment` \u2014 deferred to Phases 4-6.",
        "Exit Gate": "- All migrations run cleanly.\n- `TwinState` has no `update()` or `delete()` methods in the ORM.\n- `AthleteFitness` enduces `form = fitness - fatigue` at application level.\n- `GeneratedWorkout` enuces unique constraint on `(planned_session_id, generation_date)`.\n- `WorkoutStep` enuces unique constraint on `(generated_workout_id, step_order)`.",
        "Risks": "- **Schema drift**: The interaction between `TwinState` (append-only snapshots) and `AthleteFitness`/`AthletePhysiology` (mutable current state) is subtle. If the architect inverts the dependency (e.g., storing fitness scores directly on `TwinState` rather than snapshotting them), the system will be harder to audit.\n- **Missing enums**: `PhysiologicalIntentState` is the most important enum in the codebase and is used by every agent and computation. If it's wrong, every downstream phase breaks. Mitigation: copy exact values from `terminology.md`."
      }
    },
    {
      "entity": "phase-1",
      "metadata": {
        "type": "phase",
        "phase_number": 1,
        "features": [],
        "title": "Phase 1"
      },
      "sections": {}
    }
  ],
  "features": {}
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 23.4s)

_Thinking:_


We have subphase doc. Need generate implementation plan for phase-1-2a. Need retrieve referenced contracts in bulk: architecture entities athlete-profile, athlete-preferences, activity, terminology, data-tiers. Vision refs cold-start, constraints. Need maybe get vision context for vision docs. Need maybe get entity contexts. Use multi_context for concepts. Need maybe vision docs names. Use multi_context concepts? It fetches architecture, vision, release for named concepts. But vision docs are not "concepts"? Could use get_vision_context for exact names. Need fetch all referenced contracts in bulk. For architecture: multi_context concepts ["AthleteProfile","AthletePreferences","Activity","DataTier","ActivitySource"?]. But docs "00-foundations/terminology.md (enums)" and "data-tiers.md". Need architecture docs? Let's list entities to verify names.


**Tool: pheidipp-codebase-context_list_entities**

**Input:**
```json
{}
```

**Output:**
```
[
  "activity",
  "adaptation-observation",
  "adaptation-signature",
  "architecture-index",
  "async-pipeline",
  "athlete",
  "athlete-auth",
  "athlete-fitness",
  "athlete-integration",
  "athlete-physiology",
  "athlete-preferences",
  "athlete-profile",
  "athlete-wellness",
  "athlete-wellness-baseline",
  "banister-update",
  "checkpoint",
  "coaching-message",
  "comparable-sessions",
  "confidence-model",
  "context-budget-service",
  "cycle-phase-log",
  "data-tiers",
  "document-template",
  "effort-normalisation",
  "event-catalogue",
  "event-topology",
  "evidence-mapping",
  "execution-observation",
  "failure-handling",
  "first-message-agent",
  "generated-workout",
  "generation-event",
  "hypothesis-agent",
  "hypothesis-selector-agent",
  "load-computation",
  "lt1-detection",
  "objective",
  "objective-management",
  "observability",
  "physiological-segment",
  "physiology-update",
  "plan-generation",
  "plan-generation-fitness-improvement",
  "plan-generation-maintenance",
  "plan-generation-race",
  "plan-generation-recovery",
  "plan-generation-target-performance",
  "planned-session",
  "post-workout-agent",
  "pre-week-review-agent",
  "principles",
  "race-prediction",
  "raw-sensor-stream",
  "regeneration-task",
  "segmentation-heuristic",
  "segmentation-hmm",
  "session-count",
  "session-lifecycle",
  "signal-cleaning",
  "skip-conversation-agent",
  "storage-topology",
  "terminology",
  "threshold-detection",
  "training-goal",
  "training-plan",
  "twin-context-assembler",
  "twin-state",
  "versioning-and-reprocessing",
  "weather-forecast",
  "weekly-plan",
  "weekly-synthesis-agent",
  "wellness-alert-agent",
  "wellness-modifier",
  "workout-generation-agent",
  "workout-library-entry",
  "workout-step"
]
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 3.5s)

_Thinking:_


Need fetch multi_context for entities.


**Tool: pheidipp-codebase-context_multi_context**

**Input:**
```json
{
  "concepts": [
    "AthleteProfile",
    "AthletePreferences",
    "Activity",
    "Terminology",
    "DataTiers"
  ],
  "domains": [
    "architecture",
    "release_plan"
  ]
}
```

**Output:**
```
{
  "AthleteProfile": {
    "concept": "AthleteProfile",
    "found_domains": [],
    "architecture": {
      "not_found": true
    },
    "release_plan": {
      "not_found": true
    }
  },
  "AthletePreferences": {
    "concept": "AthletePreferences",
    "found_domains": [],
    "architecture": {
      "not_found": true
    },
    "release_plan": {
      "not_found": true
    }
  },
  "Activity": {
    "concept": "Activity",
    "found_domains": [
      "architecture",
      "release_plan"
    ],
    "architecture": {
      "entity_name": "activity",
      "context": {
        "entity": "activity",
        "graph": {
          "related_entities": [],
          "produces_events": [
            "`activity_ingested`",
            "`activity_calibration_eligible`"
          ],
          "consumes_events": [
            "`session_completed`"
          ],
          "used_by_agents": [],
          "invariants": [
            {
              "field": "fit_file_key",
              "rule": "`fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "avg_hr",
              "rule": "`avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` \u2014 these fields do not exist on `Activity`. They are never added.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "aerobic_load",
              "rule": "`aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "calibration_eligible",
              "rule": "`calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "manual_entry",
              "rule": "Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "external_id",
              "rule": "Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.",
              "type": "uniqueness",
              "enforcement": "application"
            }
          ],
          "api_endpoints": [
            {
              "method": "POST",
              "path": "/athletes/{athlete_id}/activities/upload",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "POST",
              "path": "/athletes/{athlete_id}/activities",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "GET",
              "path": "/athletes/{athlete_id}/activities",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "GET",
              "path": "/athletes/{athlete_id}/activities/{activity_id}",
              "auth": "Bearer JWT",
              "response_status": 200
            }
          ],
          "storage_models": [
            {
              "table": "activities` table",
              "strategy": "append-only (no update after load scores written)",
              "consistency": "strong",
              "retention": "indefinite"
            },
            {
              "table": "Raw FIT file",
              "strategy": "object storage, immutable",
              "consistency": "eventual",
              "retention": "indefinite"
            },
            {
              "table": "Cleaned stream",
              "strategy": "object storage, immutable",
              "consistency": "eventual",
              "retention": "indefinite"
            }
          ]
        },
        "sections": {
          "Purpose": "- Lean index record for a single completed training session, storing what the twin needs\n- Never stores workout summaries; the FIT file is the source of truth for everything else",
          "TypeScript Schema": "```typescript\ntype ActivitySource = 'intervals_icu' | 'manual_upload' | 'garmin_direct' | 'manual_entry'\n\ntype QualityFlags = {\n  hr_dropout_pct?: number           // if > 20%, disqualifies calibration eligibility\n  gps_loss?: boolean\n  sensor_malfunction?: boolean\n  elevated_laxity_risk?: boolean    // ovulatory phase flag (3c)\n}\n\ntype Activity = {\n  id: string                        // UUID, PK\n  athlete_id: string                // UUID, FK \u2192 Athlete\n  planned_session_id: string | null // FK \u2192 PlannedSession; null for unplanned\n  source: ActivitySource\n  external_id: string | null        // source platform ID; for deduplication\n  activity_date: string             // YYYY-MM-DD\n  start_time: string                // ISO 8601 datetime\n  duration_seconds: number\n\n  // Load scores \u2014 persisted for query performance (twin reads across weeks of history)\n  aerobic_load: number | null       // null for Tier 6; low-confidence for Tier 5\n  neuromuscular_load: number | null // null for Tier 5 and 6\n  structural_load: number | null    // null for Tier 6\n\n  // Signal availability\n  has_hr: boolean\n  has_rr_intervals: boolean\n  has_power: boolean\n\n  // Calibration\n  calibration_eligible: boolean\n  quality_flags: QualityFlags\n\n  // Reprocessing anchor \u2014 REQUIRED for all non-manual-entry sources\n  fit_file_key: string | null       // null ONLY for source = 'manual_entry'\n\n  // Versioning\n  ingestion_pipeline_version: string | null\n  cleaning_pipeline_version: string | null  // set after 5a cleaning pipeline runs\n  notes: string | null\n  created_at: string\n}\n```",
          "Invariants": "- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.\n- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` \u2014 these fields do not exist on `Activity`. They are never added.\n- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.\n- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.\n- Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.\n- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.",
          "State Transitions": "```mermaid\nstateDiagram-v2\n    [*] --> created : FIT ingestion task commits\n    created --> load_computed : LoadComputationService runs\n    load_computed --> calibration_evaluated : CalibrationEligibilityService runs\n    calibration_evaluated --> twin_updated : if calibration_eligible = true\n    calibration_evaluated --> record_only : if calibration_eligible = false\n    load_computed --> cleaned : SignalCleaningService runs\n    cleaned --> segmented : SegmentationTask runs\n```",
          "Events": "### Produced\n| Event | Trigger | Version | Payload |\n|---|---|---|---|\n| `activity_ingested` | Activity record created | v1 | `{activity_id, date, duration, has_hr, has_rr, has_power, fit_file_key}` |\n| `activity_calibration_eligible` | calibration_eligible set true | v1 | `{activity_id, aerobic_load, neuromuscular_load, structural_load}` |\n\n### Consumed\n| Event | Action | Version |\n|---|---|---|\n| `session_completed` | Sets `planned_session_id` FK | v1 |",
          "APIs": "```yaml\nPOST /athletes/{athlete_id}/activities/upload\nRequest: multipart/form-data\n  file: FIT file, required\n  planned_session_id?: UUID\nResponse: 202 Accepted\n  task_id: string  # track ingestion progress\nAuth: Bearer JWT, require_self\n\nPOST /athletes/{athlete_id}/activities\nRequest: (manual entry)\n  source: 'manual_entry'\n  activity_date: string\n  duration_seconds: number\n  planned_session_id?: UUID\n  has_hr?: boolean\n  notes?: string\nResponse: 201\n  activity: ActivityResponse\nAuth: Bearer JWT, require_self\n\nGET /athletes/{athlete_id}/activities\nQuery:\n  from?: date\n  to?: date\n  limit?: number (default 20, max 100)\n  offset?: number\nResponse: 200\n  activities: ActivityResponse[]\n  total: number\nAuth: Bearer JWT, require_self\n\nGET /athletes/{athlete_id}/activities/{activity_id}\nResponse: 200\n  activity: ActivityResponse\nAuth: Bearer JWT, require_self\n```",
          "Storage Model": "| Data | Strategy | Consistency | Retention |\n|---|---|---|---|\n| `activities` table | append-only (no UPDATE after load scores written) | strong | indefinite |\n| Raw FIT file | object storage, immutable | eventual | indefinite |\n| Cleaned stream | object storage, immutable | eventual | indefinite |",
          "Mutation Rules": "| Layer | Read | Write | Delete |\n|---|---|---|---|\n| API | Yes | Via upload/manual endpoints only | No |\n| Service | Yes | Load scores, calibration flag, version fields only | No |\n| Repository | Yes | Yes | No |",
          "Runtime Ownership": "Owns:\n- The lean observation index\n- The `fit_file_key` reprocessing anchor\n- Calibration eligibility flag\n\nDoes Not Own:\n- Load score formulas \u2192 `02-computations/load-computation.md`\n- Segmentation records \u2192 `01-entities/physiological-segment.md`\n- Execution analysis \u2192 `01-entities/execution-observation.md`\n- Session lifecycle (planned_session_id linkage) \u2192 `01-entities/planned-session.md`",
          "Idempotency": "- FIT file ingestion is idempotent for the same `(athlete_id, external_id, source)` \u2014 second call returns the existing Activity\n- Manual FIT upload: if the same file is uploaded twice, deduplication relies on the athlete to check; no automatic deduplication for `source = manual_upload`",
          "Authorization": "- All endpoints require `require_self`: JWT athlete_id must match path athlete_id\n- Activity data is never shared between athletes",
          "Failure Semantics": "- Object storage failure during FIT upload \u2192 task retries; no Activity record created; 202 Accepted returns a task_id; athlete can poll for status\n- `LoadComputationService` failure \u2192 Activity exists with null load scores; retry scheduled (up to 3\u00d7); `calibration_eligible = false` until recomputed; `activity.load_compute.failures` incremented; after max retries \u2192 `activity.load_compute.stuck.count` incremented + DLQ entry\n- FIT parsing failure (corrupt file) \u2192 Activity NOT created; 422 returned to caller with parse error detail",
          "Performance Constraints": "Synchronous API latency:\n- `POST /activities/upload`: p95 < 500ms (async; just stores file and enqueues task)\n- `GET /activities`: p95 < 200ms\n- `GET /activities/{id}`: p95 < 50ms\n\nAsynchronous operations:\n- Full ingestion pipeline (parse + load + clean): p95 < 30s\n- Segmentation task: p95 < 60s (runs after cleaning)",
          "Observability": "Metrics:\n- `activity.ingested.total`: by source\n- `activity.calibration_eligible.rate`: percentage of ingested activities that are eligible\n- `activity.ingestion.latency_ms`: time from FIT upload to load scores written\n- `activity.fit_parse.failures`: count of corrupt/unreadable files\n- `activity.load_compute.failures`: count of LoadComputationService failures\n- `activity.load_compute.retry.count`: retry attempts per activity\n- `activity.load_compute.stuck.count`: activities exceeding max retries (DLQ candidates)\nLogs:\n- `activity.ingested`: activity_id, source, has_hr, has_rr, has_power, calibration_eligible\n- `activity.fit_parse.failed`: athlete_id, source, error_type\nTraces:\n- `ingestion_pipeline`: fit_received \u2192 object_storage \u2192 parse \u2192 load_compute \u2192 calibration \u2192 twin_update",
          "Implementation Notes": "- The `fit_file_key` pattern `fit-files/{athlete_id}/{activity_date}/{uuid}.fit` ensures activities are retrievable by athlete without a DB query\n- Load scores are indexed on the `activities` table because `TwinRecalibrationService` queries them with a rolling window (e.g. last 90 days) \u2014 this passes the reprocessing test\n- The `cleaning_pipeline_version` null \u2192 non-null transition is the signal that a `RawSensorStream` has been created for this activity"
        }
      },
      "cross_references": {
        "related_entities": [],
        "produces_events": [
          "`activity_ingested`",
          "`activity_calibration_eligible`"
        ],
        "consumes_events": [
          "`session_completed`"
        ],
        "used_by_agents": [],
        "related_via_shared_events": {},
        "release_plan_features_introducing": [],
        "release_plan_features_modifying": []
      }
    },
    "release_plan": {
      "entity_name": "phase-1-2a-profile-preferences-activity",
      "type": "phase",
      "context": {
        "phase": 1,
        "sub_phases": [
          {
            "entity": "phase-1-2a-profile-preferences-activity",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 Core Models: Profile, Preferences, Activity"
            },
            "sections": {
              "Objective": "Establish the supporting data structures that define who the athlete is (profile), how they train (preferences), and what they have done (activity). These entities are created during onboarding (1.3) and consumed by nearly every downstream system. `AthleteProfile` and `AthletePreferences` are each one-to-one with `Athlete`. `Activity` is the lean physiological observation \u2014 it represents a completed training session with minimal metadata, deferring rich signal storage to Phase 1.6.",
              "Challenge Notes": "This sub-phase isolates the athlete-context tables so the architect can focus on profile/preferences precision without being overwhelmed by the full schema. The `TrainingBlock` entity name from the initial draft has been superseded by `TrainingGoal` in the final Phase 1 design (handled in 1.2b).\n\nThe `athlete_profiles` table was created in Phase-1.1 with a minimal schema (demographics only \u2014 `date_of_birth`, `sex`, `height_cm`). This sub-phase extends it to the full schema via Alembic migration, adding the personalisation model columns (`gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`), location fields (`location_lat`, `location_lng`), `timezone`, `training_window`, `current_effort_generation`, `structural_risk_flag`, and `objective_thresholds`. The `athlete_profiles` table is never dropped and recreated \u2014 it is only extended.",
              "Capabilities Delivered": "- Schema for `AthleteProfile` (demographics, personalisation storage)\n- Schema for `AthletePreferences` (training configuration, data tier inference)\n- Schema for `Activity` (lean observation index)\n- Alembic migration for these tables and all required enums\n- All constraints, indexes, and enums defined",
              "Architectural Contracts Required": "- `01-entities/athlete-profile.md`\n- `01-entities/athlete-preferences.md`\n- `01-entities/activity.md`\n- `00-foundations/terminology.md` (enums)\n- `00-foundations/data-tiers.md` (data tier inference logic)",
              "Vision References Required": "- `twin/cold-start.md` \u2014 onboarding tier philosophy\n- `product/constraints.md` \u2014 running-only, no raw data surfaces",
              "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 `Athlete` and the minimal `athlete_profiles` table must exist. The `athlete_profiles` table was created in Phase-1.1 with a minimal schema (demographics only). This sub-phase extends it to the full schema via Alembic migration.",
              "Downstream Enablement": "- Phase-1.2b \u2014 `Activity` is referenced by `PlannedSession`\n- Phase-1.2c \u2014 `AthleteProfile` stores personalisation models (`gap_curve_model`, `weather_response_model`, `banister_constants`)\n- Phase-1.3 (Onboarding) \u2014 creates `AthleteProfile` and `AthletePreferences`\n- Phase-1.4 (Plan Generation) \u2014 `AthletePreferences.weekly_schedule` constrains session distribution\n- Phase-1.6 (FIT Import) \u2014 creates `Activity` records",
              "Invariants To Preserve": "- `AthleteProfile`: one per `Athlete`. Unique constraint on `athlete_id`.\n- `AthletePreferences`: one per `Athlete`. Unique constraint on `athlete_id`.\n- `Activity` has no `avg_hr`, `avg_pace`, `avg_power`, or lap data fields.\n- `Activity.source = 'manual_entry'` always has `calibration_eligible = false`, null load scores, null `fit_file_key`.\n- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null.",
              "Non-Goals": "- Data is not written to these tables in this sub-phase \u2014 only schema creation.\n- `AthleteIntegration` model (platform sync) \u2014 deferred to Phase 2.\n- `RawSensorStream` and `PhysiologicalSegment` \u2014 deferred to Phase 5/6.",
              "Exit Gate": "- All migrations run cleanly on a fresh database with no errors.\n- `Activity` has no `avg_hr`, `avg_pace`, `avg_power` columns.\n- `AthleteProfile` enforces unique constraint on `athlete_id`.\n- `AthletePreferences` enforces unique constraint on `athlete_id`.",
              "Risks": "- **Schema drift**: If 1.2b or 1.2c identify missing fields, migrations may need revision. Mitigation: expose schema early in each sub-phase.\n- **Enum alignment**: `ActivitySource`, `DataTier`, `PhysiologicalIntentState` and other enums must be correct now or downstream phases will break. Mitigation: copy exact from `terminology.md`."
            }
          },
          {
            "entity": "phase-1-5b-workout-generation",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 Workout Generation"
            },
            "sections": {
              "Objective": "Enable the athlete to see their workout for the day, generated on-demand from the planned session and current twin state. At LOW confidence, targets are expressed as effort descriptions and broad ranges rather than precise numbers. The workout structure is a set of `WorkoutStep` records, each carrying a `physiological_intent`. This is the second major user-facing coaching moment \u2014 it must feel purposeful and appropriate to the athlete's data tier.",
              "Challenge Notes": "Early drafts included workout generation but used a JSON blob for the workout structure. The current architecture requires `WorkoutStep` records from day one \u2014 this is the foundation for all downstream session analysis. The `GeneratedWorkout` has a two-column target structure (`theoretical_targets` + `adjusted_targets`) that is always both written, even when identical. At this phase, `adjusted_targets` = `theoretical_targets` because no wellness or weather modifiers exist yet.\n\nThe architect must be aware of the data tier system. Tier 1-2 (power available) get power-based targets; Tier 3-4 (HR + GPS) get GAP-based targets; Tier 5-6 (no HR) get description-only workouts. The data tier is inferred from `AthletePreferences` during onboarding.",
              "Capabilities Delivered": "- `GET /athletes/{id}/today` \u2014 returns `GeneratedWorkout` for today's `PlannedSession`\n- `POST /athletes/{id}/sessions/{sid}/generate-workout` \u2014 explicit generation trigger\n- `WorkoutGenerationAgent` service (async, LLM)\n- Workout generation is idempotent for `(planned_session_id, date)`\n- `GeneratedWorkout` + `WorkoutStep` creation",
              "Architectural Contracts Required": "- `01-entities/generated-workout.md`\n- `01-entities/workout-step.md`\n- `01-entities/twin-state.md`\n- `01-entities/planned-session.md`\n- `00-foundations/data-tiers.md`\n- `03-agents/workout-generation-agent.md`\n- `04-platform/context-budget-service.md`",
              "Vision References Required": "- `coach/daily-view.md` \u2014 what the athlete sees (Today's Workout, Two-Column Target Display)\n- `twin/training-zones.md` \u2014 how targets are expressed at different confidence levels\n- `twin/confidence-and-uncertainty.md` \u2014 Tier 3 language tier",
              "Upstream Dependencies": "- Phase-1.3 (Onboarding) \u2014 `AthletePreferences` (data tier), `TwinState` (threshold estimates)\n- Phase-1.4 (Plan Generation) \u2014 `PlannedSession` must exist\n- Phase-1.5a (First Coach Message) \u2014 shared infrastructure (`ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler`)",
              "Downstream Enablement": "- Phase-1.6 (FIT Import) \u2014 athlete executes the workout, uploads FIT file, system compares actual to `GeneratedWorkout`\n- Phase-2 (Structured Workouts) \u2014 this is already using `WorkoutStep`, so 2c is mainly about richer structure",
              "Invariants To Preserve": "- `WorkoutStep.physiological_intent` is never null \u2014 every step has an intent.\n- `WorkoutStep.step_order` is unique within `GeneratedWorkout`.\n- `GeneratedWorkout` is idempotent for `(planned_session_id, generation_date)`. Calling twice returns the existing workout.\n- `theoretical_targets` and `adjusted_targets` always both written, even when identical.\n- `pace_sec_per_km` uses GAP values only. Never raw pace.\n- `twin_state_id` records which twin version drove generation. If twin recalibrates after generation, the workout is not retroactively updated.\n- Target type depends on data tier:\n  - Tier 1-2: `target_power_watts` primary, `target_gap_sec_per_km` secondary\n  - Tier 3-4: `target_gap_sec_per_km` primary, `target_hr_zone` secondary\n  - Tier 5-6: `description` only, numeric targets null\n- Recovery modifier defaults to `green`, reason null (modifiers not yet available).",
              "Non-Goals": "- Recovery modifier (wellness) on `adjusted_targets` \u2014 deferred to Phase 3\n- Weather modifier on `adjusted_targets` \u2014 deferred to Phase 3\n- Segmentation (PlannedSegment / PhysiologicalSegment) \u2014 deferred to Phase 5\n- Objectives in workout \u2014 deferred to Phase 4",
              "Exit Gate": "- `GET /athletes/{id}/today` returns a `GeneratedWorkout` with linked `WorkoutStep` records, each carrying a non-null `physiological_intent`.\n- A threshold session produces `WorkoutStep` records with appropriate states: warmup \u2192 low_aerobic \u2192 threshold (per rep) \u2192 recovery (between reps) \u2192 cooldown.\n- Targets are expressed in units appropriate to data tier (power for Tier 1-2, GAP for Tier 3-4, description for Tier 5-6).\n- Calling generation twice for the same `(planned_session_id, date)` returns the existing `GeneratedWorkout` without calling the LLM again.",
              "Risks": "- **Data tier edge cases**: An athlete says they have a power meter but doesn't. The system must gracefully fall back to lower-tier targets without crashing. Mitigation: validate data tier against actual hardware during FIT ingestion (Phase 2), but for now, trust what the athlete told us.\n- **Template vs genuine coaching**: At LOW confidence, targets are broad. The workout must still feel purposeful, not like a fill-in-the-blank template. The prompt engineering challenge is significant."
            }
          },
          {
            "entity": "phase-1-3-onboarding-twin-bootstrap",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 Onboarding & Twin Bootstrap"
            },
            "sections": {
              "Objective": "Accept the onboarding questionnaire and produce the initial athlete state in one atomic transaction. This is the first sub-phase that writes to the database \u2014 all prior sub-phases established schema only. The twin is bootstrapped from population norms (Tier 3, questionnaire only, LOW confidence). No historical data, no peer matching, no LLM involvement. Pure Python computation.",
              "Challenge Notes": "Early drafts used `TrainingBlock` (single goal type). Current architecture has `TrainingGoal` with five goal types. For Phase 1, we support only `race_event` and `target_performance` \u2014 `fitness_improvement`, `maintenance`, and `recovery` are deferred because they require historical data, baseline fitness computation, or injury assessment that doesn't exist at Tier 3. The plan generation service (1.4) will call `plan-generation-race.md` (unified with `plan-generation-target-performance.md` in architecture).\n\nThe onboarding transaction is heavy \u2014 it creates `AthleteProfile`, `AthletePreferences`, `TrainingGoal`, `AthletePhysiology`, `AthleteFitness`, and `TwinState` atomically. If any step fails, all prior steps roll back. The `onboarding_complete` flag gates access to plan, coaching, and workout endpoints.",
              "Capabilities Delivered": "- `POST /athletes/{id}/onboarding` \u2014 atomic transaction creating:\n  1. `AthleteProfile` (demographics, structural risk flag)\n  2. `AthletePreferences` (training config, data tier inference)\n  3. `TrainingGoal` (`race_event` or `target_performance` only)\n  4. `AthletePhysiology` (bootstrapped from age-graded population norms, LOW confidence)\n  5. `AthleteFitness` (zero fitness/fatigue, population time constants)\n  6. `TwinState` (LOW confidence, `trigger = questionnaire`)\n  7. Sets `athlete.onboarding_complete = true`\n- `GET /athletes/{id}/onboarding` \u2014 returns current onboarding status\n- `GET /athletes/{id}/twin` \u2014 returns latest `TwinState`\n- `GET /athletes/{id}/twin/history` \u2014 all snapshots\n- `GET /athletes/{id}/profile` \u2014 read AthleteProfile\n- `PATCH /athletes/{id}/profile` \u2014 update mutable fields\n- `GET /athletes/{id}/preferences` \u2014 read AthletePreferences\n- `PATCH /athletes/{id}/preferences` \u2014 update mutable fields",
              "Architectural Contracts Required": "- `01-entities/athlete.md`\n- `01-entities/athlete-profile.md`\n- `01-entities/athlete-preferences.md`\n- `01-entities/training-goal.md`\n- `01-entities/training-plan.md`\n- `01-entities/twin-state.md`\n- `01-entities/athlete-physiology.md`\n- `01-entities/athlete-fitness.md`\n- `00-foundations/data-tiers.md` (data tier inference)\n- `00-foundations/confidence-model.md`",
              "Vision References Required": "- `product/plan-generation.md` \u2014 strategic roadmap concept\n- `twin/cold-start.md` \u2014 Tier 3 bootstrap philosophy\n- `twin/confidence-and-uncertainty.md` \u2014 communication under uncertainty\n- `coach/first-message.md` \u2014 voice and content of first coach message (prepared for in 1.5a)",
              "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 `Athlete` must exist and be authenticated\n- Phase-1.2a (Profile & Preferences) \u2014 schema must exist\n- Phase-1.21 (Plan & Sessions) \u2014 `TrainingGoal` schema must exist\n- Phase-1.2c (Twin & Fitness) \u2014 `TwinState`, `AthletePhysiology`, `AthleteFitness` schema must exist",
              "Downstream Enablement": "- Phase-1.4 (Plan Generation) \u2014 requires `TrainingGoal`, `TwinState`\n- Phase-1.5a (First Coach Message) \u2014 triggered after onboarding completes\n- Phase-1.5b (Workout Generation) \u2014 requires `TwinState` for target generation\n- Phase-1.6 (FIT Import) \u2014 updates `AthleteFitness` and creates new `TwinState`",
              "Invariants To Preserve": "- The entire onboarding sequence runs in one database transaction. If any step fails, all prior steps roll back. The athlete remains in `onboarding_complete = false` state.\n- `TwinBootstrapService` is pure Python. No LLM call, no external API call. Must complete within 200ms.\n- Re-onboarding is not supported. Calling `POST /athletes/{id}/onboarding` when `onboarding_complete = true` returns 409. Athletes update preferences via PATCH.\n- `TrainingGoal` enforces single active goal per athlete (409 on second creation).\n- `AthleteProfile.structural_risk_flag` is computed from `AthletePreferences.sport_background`.\n- Data tier is inferred from `hr_source` and `power_source` on `AthletePreferences`.\n- Threshold estimates (`lt1_*`, `lt2_*`, `max_hr`) are bootstrapped from age-graded population norms using `AthleteProfile.date_of_birth`.\n- `AthleteFitness` is initialised to zero fitness, zero fatigue.\n- `TwinState.confidence_level = low`, `trigger = questionnaire`.",
              "Non-Goals": "- `fitness_improvement`, `maintenance`, `recovery` goal types \u2014 deferred\n- `Objective` seeding \u2014 deferred to Phase 4 (requires data)\n- Menstrual cycle tracking (`CyclePhaseLog`) \u2014 deferred to Phase 3\n- WeeklPlan creation \u2014 this is plan generation (1.4), not onboarding\n- First coach message generation \u2014 this is 1.5a, not onboarding",
              "Exit Gate": "- Submitting a complete questionnaire creates all six entities in one transaction.\n- Simulating a failure mid-transaction leaves no partial records.\n- Attempting to onboard twice returns 409.\n- `GET /athletes/{id}/twin` returns a `TwinState` with `confidence_level = low` and non-null threshold estimates derived from population norms.",
              "Risks": "- **Heavy transaction**: 8 entities created in one transaction. Consider if any can be split (e.g., `AthleteProfile`/`AthletePreferences` as a separate \"profile creation\" step before the full onboarding). However, the atomicity invariant is strict \u2014 partial onboarding is worse than slow onboarding.\n- **Data tier inference edge cases**: If `hr_source` or `power_source` are not set, the data tier inference must have a sensible fallback. Mitigation: default to manual entry (Tier 6) and let the athlete update later."
            }
          },
          {
            "entity": "phase-1-1-email-password-auth",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 Email/Password Authentication"
            },
            "sections": {
              "Objective": "Establish the authentication layer that all subsequent sub-phases build upon. This delivers a secure, token-based authentication system supporting email/password registration and login. OAuth providers (Google, Strava) are explicitly deferred to later phases \u2014 the schema in `AthleteAuth` is designed to accommodate them, but this sub-phase implements only the email/password provider.",
              "Challenge Notes": "OAuth providers (Google, Strava) and account linking are deferred to a later phase to reduce initial complexity. The `AthleteAuth` entity schema already supports multiple providers, so adding OAuth later is an extension, not a rewrite.\n\nRegistration atomically creates `Athlete` + `AthleteAuth` + `AthleteProfile`. The `AthleteProfile` table is created with a **minimal schema** containing only the demographics fields needed at registration (`date_of_birth`, `sex`, `height_cm`). The full schema (personalisation models, location, training window, etc.) is extended in Phase-1.2a. The architect can deduce the minimal schema from the API contracts in `athlete-auth.md` and `athlete.md`.",
              "Capabilities Delivered": "- Athlete can register with email + password (`POST /auth/register`)\n- Athlete can log in with email + password (`POST /auth/login`)\n- Access token (JWT, 15min expiry) and refresh token (30-day expiry, rotated on use) lifecycle\n- `require_self` route dependency for athlete-scoped endpoints\n- Secure password hashing (bcrypt)\n- Multi-device session support (via refresh token table)",
              "Architectural Contracts Required": "- `01-entities/athlete.md`\n- `01-entities/athlete-auth.md`\n- `01-entities/athlete-profile.md` (minimal schema \u2014 only demographics columns needed for registration; full schema completed in Phase-1.2a)",
              "Vision References Required": "- `product/brand-philosophy.md` \u2014 \"no AI-feel, no tech jargon\"\n- `product/constraints.md` \u2014 security constraints",
              "Upstream Dependencies": "None. This is the first sub-phase.",
              "Downstream Enablement": "- Phase-1.2a (Profile & Preferences) \u2014 registration creates the `Athlete` record\n- Phase-1.3 (Onboarding) \u2014 requires authenticated user to complete onboarding\n- All athlete-scoped endpoints require the auth layer",
              "Invariants To Preserve": "- `email` is unique across all athletes (case-insensitive)\n- `hashed_password` is never returned by any API endpoint or included in any log\n- Refresh tokens are rotated on every use \u2014 old token is revoked atomically with new token creation\n- Registration atomically creates `Athlete` and minimal `AthleteProfile`. If either fails, neither is committed.",
              "Non-Goals": "- OAuth (Google, Strava) \u2014 deferred to a later phase\n- Email verification flow\n- Password reset flow\n- Rate limiting (deferred to infrastructure hardening)",
              "Exit Gate": "- `POST /auth/register` creates an `Athlete` and returns a valid token pair.\n- `POST /auth/login` with wrong password returns 401; with correct password returns a new token pair.\n- An authenticated request to an athlete-scoped route with a JWT belonging to a different athlete returns 403.\n- A request with an expired access token returns 401.\n- Refresh token rotation: after `POST /auth/refresh`, the old refresh token is invalid and a new one is usable.",
              "Risks": "- **Password compromise**: bcrypt with appropriate work factor (12+) mitigates this.\n- **Token theft**: Short-lived access tokens + refresh token rotation limit window of exposure."
            }
          },
          {
            "entity": "phase-1-5a-first-coach-message",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 First Coach Message"
            },
            "sections": {
              "Objective": "Deliver the athlete's first meaningful interaction with the coach: a four-paragraph first message triggered after onboarding completes. This message must demonstrate that the coach has read and understood the athlete's specific data. At LOW confidence, the language tier is Tier 3: \"Based on what you've described...\" The trigger is the `onboarding_completed` event, and the message is created exactly once per active goal.",
              "Challenge Notes": "The first coach message sets the tone for the entire coaching relationship. If it feels generic or templated, the athlete will never fully trust the coach. If it feels genuinely personal \u2014 referencing specific background, goal, and structural risk \u2014 the athlete will engage. Vision reference: `coach/first-message.md` emphaseses that this is not about data dumping but about forming a coaching relationship.\n\nThe architect must be aware that `FirstMessageAgent` is an LLM agent, not a template. It requires `ContextBudgetService` (to stay within token limits), `PromptRegistry` (for prompt versioning), and `TwinContextAssembler` (to translate twin state into coaching language). Every LLM call writes a `GenerationEvent`. The `AthleteProfile` and `AthletePreferences` created during onboarding provide the specific data that makes the message personal.",
              "Capabilities Delivered": "- `POST /athletes/{id}/coach/first-message` \u2014 triggers `FirstMessageAgent`. Returns 409 if message already exists.\n- `GET /athletes/{id}/coach/messages` \u2014 returns all `CoachingMessage` records for the athlete, ordered by `generated_at` desc\n- `FirstMessageAgent` service (async, LLM)\n- `ContextBudgetService` (token budget enforcement, 3k-5k tokens)\n- `PromptRegistry` (loads and versions prompt templates)\n- `TwinContextAssembler` (translates `TwinState` into coaching-relevant language)\n- Every LLM call writes a `GenerationEvent` (success or failure)",
              "Architectural Contracts Required": "- `01-entities/coaching-message.md`\n- `01-entities/generation-event.md`\n- `01-entities/twin-state.md`\n- `01-entities/athlete-profile.md`\n- `01-entities/athlete-preferences.md`\n- `03-agents/first-message-agent.md`\n- `04-platform/context-budget-service.md`",
              "Vision References Required": "- `coach/first-message.md` \u2014 four-paragraph structure, voice constraints\n- `coach/voice-and-format.md` \u2014 global voice rules\n- `twin/confidence-and-uncertainty.md` \u2014 Tier 3 language tier",
              "Upstream Dependencies": "- Phase-1.3 (Onboarding) \u2014 `AthleteProfile`, `AthletePreferences`, `TrainingGoal`, `TwinState` must exist.\n- Phase-1.2c (Twin & Fitness) \u2014 `CoachingMessage`, `GenerationEvent` schema must exist.",
              "Downstream Enablement": "- Phase-1.5b (Workout Generation) \u2014 shares `ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler`\n- Phase-1.6 (FIT Import) \u2014 `PostWorkoutAgent` extends the agent foundation built here",
              "Invariants To Preserve": "- The first coach message must not be regenerated once it exists. The endpoint returns 409 on a second call. If quality is poor, the prompt must be improved and re-tested before re-enabling generation.\n- Four paragraphs: Welcome, What Was Found, The Plan, Closing.\n- No bullets, no headers, no emojis, no generic affirmations.\n- No acronyms without explanation (HR, LT1, GAP \u2014 all plain English).\n- Paragraph 2 MUST reference the athlete's specific `sport_background` and `structural_risk_flag` where applicable.\n- The message could NOT have been written without reading this athlete's specific data \u2014 if it reads as a template, it has failed.\n- Every LLM call \u2014 success or failure \u2014 writes a `GenerationEvent`. No silent failures.\n- Context windows are hard limits, not targets. `ContextBudgetService` enforces them before the API call.\n- `first_message` \u2014 only one per athlete per active goal. 409 on second call.",
              "Non-Goals": "- Objectives in the first message \u2014 deferred to Phase 4 (requires data)\n- Comparable session references \u2014 no sessions exist yet\n- Wellness or weather modifiers \u2014 deferred to Phase 3",
              "Exit Gate": "- `POST /athletes/{id}/coach/first-message` returns a four-paragraph message with no bullets, no headers, no emojis, and no generic affirmations.\n- The message references the athlete's specific sport background and structural risk flag where applicable.\n- A failed LLM call (e.g. API timeout) writes a `GenerationEvent` with `success = false` and returns a 503 to the caller \u2014 no silent data corruption.\n- Calling `POST /athletes/{id}/coach/first-message` twice returns 409 on the second call without calling the LLM.",
              "Risks": "- **Prompt quality gate**: The first message is the most important engineering asset in Phase 1. It must be developed and tested in isolation (script or notebook) before the endpoint is wired. Voice quality review is a go/no-go gate.\n- **Context budget overflow**: At LOW confidence, the twin state has many null fields. The `ContextBudgetService` must handle sparse data gracefully without exceeding token limits."
            }
          },
          {
            "entity": "phase-1-2b-plan-sessions",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 Core Models: Plan & Sessions"
            },
            "sections": {
              "Objective": "Establish the schema for the training plan hierarchy: from the athlete's goal, through the strategic plan and weekly breakdown, to individual planned sessions and scheduled checkpoints. This is a purely schema sub-phase \u2014 no services or endpoints are built here. The plan generation logic (1.4) will populate these tables, and the coaching agents (1.5) will query them.",
              "Challenge Notes": "The plan generation service and the `TrainingPlan`/`PlannedSession` schema were initially treated as a single feature. This sub-phase separates the schema from the generation logic so the architect can reason about each independently. The `TrainingBlock` entity from early drafts has been replaced by `TrainingGoal` with a richer set of fields and support for multiple goal types. The `WeeklyPlan` / `WeeklySession` hierarchy is new in the current architecture \u2014 it implements the \"weekly coaching rhythm\" from the vision.",
              "Capabilities Delivered": "- Schema for `TrainingGoal` (goal definition, immutable after creation)\n- Schema for `TrainingPlan` (phase arc, checkpoint schedule)\n- Schema for `WeeklyPlan` (weekly session list, immutable once active)\n- Schema for `WeeklySession` (links `WeeklyPlan` to `PlannedSession`)\n- Schema for `PlannedSession` (individual session with intent, checkpoint flags)\n- Schema for `Checkpoint` (calibration, benchmark, race_simulation, secondary_race, progress_review)\n- All constraints, indexes, and enums (`GoalType`, `PhaseLabel`, `SessionType`, `CheckpointType`, etc.)",
              "Architectural Contracts Required": "- `01-entities/training-goal.md`\n- `01-entities/training-plan.md`\n- `01-entities/weekly-plan.md`\n- `01-entities/planned-session.md`\n- `01-entities/checkpoint.md`\n- `00-foundations/terminology.md`",
              "Vision References Required": "- `product/plan-generation.md` \u2014 strategic roadmap concept\n- `product/training-plan-checkpoints.md` \u2014 checkpoint hierarchy and scheduling\n- `coach/plan-visibility.md` \u2014 what the athlete sees",
              "Upstream Dependencies": "- Phase-1.1 (Auth) \u2014 `Athlete` must exist before `TrainingGoal` can reference it.\n- Phase-1.2a (Profile & Preferences) \u2014 `AthletePreferences.weekly_schedule` contains the `long_workout` day used by plan generation.",
              "Downstream Enablement": "- Phase-1.3 (Onboarding) \u2014 creates the `TrainingGoal`\n- Phase-1.4 (Plan Generation) \u2014 populates `TrainingPlan`, `WeeklyPlan`, `PlannedSession`, `Checkpoint`\n- Phase-1.5b (Workout Generation) \u2014 queries `PlannedSession` for `GeneratedWorkout`\n- Phase-1.6 (FIT Import) \u2014 `Activity.planned_session_id` FK links to `PlannedSession`",
              "Invariants To Preserve": "- `TrainingGoal`: one active per athlete (partial unique index on `athlete_id WHERE status = 'active'`).\n- `TrainingGoal` fields `goal_type`, `goal_event_type`, `fitness_level`, etc. are immutable after creation.\n- `TrainingPlan` is never deleted \u2014 `superseded_at` is set when replaced.\n- `WeeklyPlan`: one per `(training_plan_id, week_number)`. Sessions array is immutable once `status = active`.\n- `PlannedSession` records for a superseded `TrainingPlan` retain the old `training_plan_id` \u2014 queries for \"current plan sessions\" must join through `WeeklyPlan`.\n- `Checkpoint` cannot be created retroactively \u2014 scheduled during plan synthesis.\n- `Checkpoint` completion fields (`metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`) are set atomically.",
              "Non-Goals": "- Plan generation logic \u2014 deferred to 1.4\n- Session lifecycle (skip, miss, reschedule) \u2014 deferred to Phase 4\n- Workout library \u2014 deferred to Phase 4\n- Plan regeneration on confidence upgrade \u2014 deferred to Phase 2",
              "Exit Gate": "- All migrations run cleanly.\n- `TrainingGoal` enforces single active goal per athlete at DB level.\n- `WeeklyPlan` enforces one per `(training_plan_id, week_number)`.\n- `Checkpoint` enforces `planned_session_id` as one-to-one with `PlannedSession`.",
              "Risks": "- **Checkpoint-PlannedSession circular reference**: `Checkpoint` references `PlannedSession`, and `PlannedSession` has `checkpoint_type`/`checkpoint_metric` fields. The architect must decide whether `Checkpoint` is created first or atomically with the `PlannedSession`. Recommended approach: atomic creation in the plan generation service.\n- **Plan supersession cascade**: When a plan is superseded, `PlannedSession` records retain the old `training_plan_id`. If 1.2b misses the denormalisation warning, queries may return stale sessions. Mitigation: document the correct query pattern in the schema."
            }
          },
          {
            "entity": "phase-1-4-plan-generation",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 Plan Generation"
            },
            "sections": {
              "Objective": "Generate a complete training plan from the bootstrapped twin and defined goal. This is a pure Python service \u2014 no LLM, no external API calls. The plan skeleton gives the coaching agents in 1.5 the phase context they need to generate meaningful messages and workouts. For Phase 1, only `race_event` and `target_performance` goal types are supported.",
              "Challenge Notes": "Early drafts only created `TrainingPlan` and `PlannedSession`. The current architecture adds `WeeklyPlan` and `WeeklySession` to implement the \"weekly coaching rhythm\" from the vision. This means 1.4 creates the full hierarchy: TrainingPlan \u2192 WeeklyPlan \u2192 WeeklySession \u2192 PlannedSession, plus Checkpoints. The architect must be aware of the `PlannedSession.training_plan_id` denormalisation caveat \u2014 the authoritative plan reference is always through `WeeklyPlan`.",
              "Capabilities Delivered": "- `TrainingPlan` with phase arc appropriate to `goal_type`\n- `WeeklyPlan` + `WeeklySession` for all weeks\n- `PlannedSession` records (with checkpoint flags) for all sessions\n- `Checkpoint` records (calibration, benchmark, progress_review)\n- `GET /athletes/{id}/plan` \u2014 returns plan with phases\n- `GET /athletes/{id}/plan/sessions` \u2014 all sessions\n- `GET /athletes/{id}/plan/upcoming` \u2014 next 5 sessions\n- `GET /athletes/{id}/plan/checkpoints` \u2014 all checkpoints",
              "Architectural Contracts Required": "- `01-entities/training-goal.md`\n- `01-entities/training-plan.md`\n- `01-entities/weekly-plan.md`\n- `01-entities/planned-session.md`\n- `01-entities/checkpoint.md`\n- `01-entities/twin-state.md`\n- `02-computations/plan-generation.md`\n- `02-computations/plan-generation-race.md`\n- `02-computations/plan-generation-target-performance.md`",
              "Vision References Required": "- `product/plan-generation.md` \u2014 strategic roadmap concept\n- `product/training-plan-checkpoints.md` \u2014 checkpoint hierarchy\n- `coach/plan-visibility.md` \u2014 what the athlete sees\n- `weekly-coaching-rhythm.md` \u2014 the weekly adjustment layer",
              "Upstream Dependencies": "- Phase-1.3 (Onboarding) \u2014 `TrainingGoal` and `TwinState` must exist\n- Phase-1.2b (Plan & Sessions) \u2014 schema must exist",
              "Downstream Enablement": "- Phase-1.5a (First Coach Message) \u2014 references plan phases\n- Phase-1.5b (Workout Generation) \u2014 generates workout for `PlannedSession`\n- Phase-1.6 (FIT Import) \u2014 `Activity` links to `PlannedSession`",
              "Invariants To Preserve": "- `PlanGenerationService` is pure Python \u2014 no LLM, no external API calls.\n- Phases have correct proportional duration (race_event example: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week).\n- `PlannedSession` records cover the full duration to the goal event with no gaps.\n- No two consecutive quality sessions appear in generated schedule.\n- Structural rules are invariant: long run always followed by rest or recovery, threshold always sandwiched between easy days.\n- Superseded `TrainingPlan` records are never deleted \u2014 `superseded_at` is set.\n- `Checkpoint` cannot be created retroactively \u2014 scheduled during plan synthesis, not after session completion.\n- `PlannedSession` records for a superseded `TrainingPlan` retain the old `training_plan_id` \u2014 queries for \"current plan sessions\" must join through `WeeklyPlan`.\n- `WeeklyPlan` sessions array is immutable once `status = active`.",
              "Non-Goals": "- `fitness_improvement`, `maintenance`, `recovery` goal types \u2014 deferred\n- Plan regeneration on confidence upgrade \u2014 deferred to Phase 2\n- Session lifecycle management (skip, miss, redistribute) \u2014 deferred to Phase 4\n- Workout library \u2014 deferred to Phase 4\n- Plan regeneration on goal date change > 7 days \u2014 keep minimal, just re-generate",
              "Exit Gate": "- After onboarding, `GET /athletes/{id}/plan` returns a `TrainingPlan` with correct phase sequence for the `goal_type`.\n- Phases have correct proportional durations.\n- `PlannedSession` records cover the full duration to the goal event with no gaps.\n- No two consecutive quality sessions appear in the generated schedule.\n- `GET /athletes/{id}/plan/checkpoints` returns scheduled checkpoints.",
              "Risks": "- **Mental model shift**: The architect may expect to generate only `TrainingPlan` + `PlannedSession`. The `WeeklyPlan` / `WeeklySession` hierarchy adds complexity but is required for the weekly rhythm. Must be clear in handoff.\n- **Checkpoint complexity**: Checkpoints are scheduled based on confidence gaps, race calendar, phase transitions, and regular intervals. The scheduling logic is non-trivial."
            }
          },
          {
            "entity": "phase-1-6-simple-fit-import-post-workout",
            "metadata": {
              "type": "phase",
              "phase_number": 1,
              "features": [],
              "title": "Phase 1 \u2014 Simple FIT Import & Post-Workout"
            },
            "sections": {

...39936 bytes truncated...

The tool call succeeded but the output was truncated. Full output saved to: /home/ruimendes/.local/share/opencode/tool-output/tool_eb4af1ffb001owNQPKpiQjxBsn
Use Grep to search the full content or Read with offset/limit to view specific sections.
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 4.9s)

_Thinking:_


multi_context didn't find AthleteProfile etc because concept names maybe lowercase? Need use lower-case.


**Tool: pheidipp-codebase-context_multi_context**

**Input:**
```json
{
  "concepts": [
    "athlete-profile",
    "athlete-preferences",
    "activity",
    "terminology",
    "data-tiers"
  ],
  "domains": [
    "architecture"
  ]
}
```

**Output:**
```
{
  "athlete-profile": {
    "concept": "athlete-profile",
    "found_domains": [
      "architecture"
    ],
    "architecture": {
      "entity_name": "athlete-profile",
      "context": {
        "entity": "athlete-profile",
        "graph": {
          "related_entities": [],
          "produces_events": [
            "None"
          ],
          "consumes_events": [
            "`activity_ingested` (outdoor, \u226520 sessions)",
            "`activity_ingested` (outdoor, \u226525 sessions, heat_index range \u226510\u00b0C)",
            "`cycle_day_one_logged` (\u22653 complete cycles)"
          ],
          "used_by_agents": [],
          "invariants": [
            {
              "field": "AthleteProfile",
              "rule": "One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.",
              "type": "uniqueness",
              "enforcement": "database"
            },
            {
              "field": "CyclePhaseLog",
              "rule": "`sex = 'female'` enables menstrual cycle tracking (`CyclePhaseLog`) and cycle modifier in wellness computation.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "gap_curve_model",
              "rule": "`gap_curve_model` is applied when `current_effort_generation >= 2`. Upgrade to Gen 2 requires `r_squared >= 0.70`; downgrade to Gen 1 requires `r_squared < 0.65`. See `02-computations/effort-normalisation.md` for the hysteresis state machine.",
              "type": "range",
              "enforcement": "application"
            },
            {
              "field": "weather_response_model",
              "rule": "`weather_response_model` is only applied when `r_squared >= 0.65`.",
              "type": "range",
              "enforcement": "application"
            },
            {
              "field": "banister_constants",
              "rule": "`banister_constants` stores per-athlete fitted time constants. When set, `AthleteFitness.time_constants` references these values (source='individual_fitted'). When null, `AthleteFitness.time_constants` uses population defaults (source='population_default').",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": null,
              "rule": "`cycle_personal_model.phase_sensitivity` of `0.0` means the model detected no phase correlation \u2014 cycle modifier is effectively zeroed for this athlete. This is a valid outcome.",
              "type": "range",
              "enforcement": "application"
            },
            {
              "field": "cycle_personal_model",
              "rule": "`cycle_personal_model.luteal_temp_sensitivity` of `1.0` means the population default thermoregulatory offset applies. Values <1.0 indicate lower-than-average thermal sensitivity; >1.0 indicate higher. When `cycle_personal_model` is null, `LUTEAL_TEMP_OFFSET_C` (0.35) applies at full population weight.",
              "type": "range",
              "enforcement": "application"
            },
            {
              "field": "timezone",
              "rule": "`timezone` is required at onboarding (validated against IANA tz database). Immutable after creation \u2014 changing timezone requires a support process. All scheduled tasks (MissedSessionSweepTask, WorkoutPrefetchTask) and date interpretations use this timezone.",
              "type": "behavioral",
              "enforcement": "database"
            },
            {
              "field": "training_window",
              "rule": "`training_window` defaults to 06:00\u201320:00 if not set. Mutable via PATCH. Only used by WorkoutPrefetchTask for prefetch timing. MissedSessionSweepTask uses timezone only, not training_window.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "structural_risk_flag",
              "rule": "`structural_risk_flag` is computed at onboarding from `AthletePreferences.sport_background`. When `true`, the structural load density penalty coefficient is 0.08 (vs 0.12 population default). See `02-computations/load-computation.md`.",
              "type": "range",
              "enforcement": "application"
            },
            {
              "field": "objective_thresholds",
              "rule": "`objective_thresholds` stores per-athlete evaluation thresholds for objective management. When null, population defaults are used (0.03 for pacing discipline, 3 for encroachment events). See `02-computations/objective-management.md`.",
              "type": "range",
              "enforcement": "application"
            }
          ],
          "api_endpoints": [
            {
              "method": "GET",
              "path": "/athletes/{athlete_id}/profile",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "PATCH",
              "path": "/athletes/{athlete_id}/profile",
              "auth": "Bearer JWT",
              "response_status": 200
            }
          ],
          "storage_models": [
            {
              "table": "athlete_profiles` table",
              "strategy": "mutable (patch for user fields)",
              "consistency": "strong",
              "retention": "indefinite"
            },
            {
              "table": "gap_curve_model` JSONB",
              "strategy": "mutable (overwritten on refit)",
              "consistency": "strong",
              "retention": "indefinite"
            },
            {
              "table": "cycle_personal_model` JSONB",
              "strategy": "mutable (overwritten on refit)",
              "consistency": "strong",
              "retention": "indefinite"
            }
          ]
        },
        "sections": {
          "Purpose": "- Stores stable physiological and demographic identity distinct from training preferences\n- Provides age and sex inputs required for Tier 3 twin bootstrap and cycle tracking\n\n**Design Note \u2014 Body Composition Exclusion:**\n\n`AthleteProfile` does not include `weight_kg` or other body composition metrics. These are time-series signals ingested via `AthleteWellness` and `BodyCompositionRecord` (see `01-entities/athlete-wellness.md`).\n\nRationale:\n- Weight fluctuates and requires longitudinal tracking with dates and sources\n- Body composition belongs to the wellness domain, not demographic identity\n- Registration friction is reduced by deferring weight collection to first wellness sync",
          "TypeScript Schema": "```typescript\ntype Sex = 'male' | 'female' | 'not_specified'\n\ntype AthleteProfile = {\n  id: string                         // UUID, PK\n  athlete_id: string          // UUID, FK \u2192 Athlete, one-to-one\n  date_of_birth: string       // ISO date YYYY-MM-DD\n  sex: Sex\n  height_cm: number | null\n  gap_curve_model: GapCurveModel | null           // per-athlete GAP curve (null = use population)\n  weather_response_model: WeatherResponseModel | null  // per-athlete weather response (null = use population)\n  banister_constants: BanisterConstants | null     // per-athlete fitted time constants (null = use population defaults in AthleteFitness)\n  cycle_personal_model: CyclePersonalModel | null  // per-athlete cycle model (null = no cycle tracking)\n  location_lat: number | null\n  location_lng: number | null\n  timezone: string                          // IANA timezone identifier, e.g. \"Australia/Sydney\", \"America/Los_Angeles\"\n  training_window: {                        // athlete's preferred training time window (local time)\n    start: string                           // HH:MM 24-hour, e.g. \"06:00\"\n    end: string                             // HH:MM 24-hour, e.g. \"20:00\"\n  } | null\n  updated_at: string          // ISO 8601\n\n  // Effort normalisation generation state (hysteresis)\n  current_effort_generation: 1 | 2 | 3  // maintained by GapCurveFittingService; default: 1\n\n  // Crossover athlete structural load adjustment\n  structural_risk_flag: boolean          // true for crossover athletes (non-running primary sport background)\n                                        // Computed at onboarding from AthletePreferences.sport_background\n                                        // Conditions structural load density penalty (0.08 vs 0.12)\n                                        // See 02-computations/load-computation.md\n\n  // Per-athlete objective evaluation thresholds\n  objective_thresholds: ObjectiveThresholds | null  // per-athlete thresholds for objective evaluation (null = use population defaults)\n}\n\ntype GapCurveModel = {\n  formula: 'population_v1' | 'per_athlete_v1'\n  coefficients: { a: number; b: number }\n  fitted_from_sessions: number\n  fitted_at: string\n  r_squared: number\n}\n\ntype WeatherResponseModel = {\n  heat_sensitivity_coeff: number      // population default: 0.006\n  fitted_from_sessions: number\n  fitted_at: string\n  r_squared: number\n  heat_index_range_observed: [number, number]\n}\n\ntype BanisterConstants = {\n  aerobic: {\n    fitness_tau_days: number          // population default: 42\n    fatigue_tau_days: number          // population default: 7\n  }\n  neuromuscular: {\n    fitness_tau_days: number          // population default: 21\n    fatigue_tau_days: number          // population default: 3\n  }\n  structural: {\n    fitness_tau_days: number          // population default: 56\n    fatigue_tau_days: number          // population default: 14\n  }\n  fitted_from_weeks: number\n  fitted_at: string\n}\n\ntype CyclePersonalModel = {\n  avg_cycle_length_days: number\n  phase_boundaries: {\n    menstrual_end: number\n    follicular_end: number\n    ovulatory_end: number\n  }\n  phase_sensitivity: {\n    menstrual: number    // 0.0\u20131.0; how strongly this athlete shows phase-correlated variation\n    follicular: number\n    ovulatory: number\n    luteal: number\n  }\n  luteal_temp_sensitivity: number  // multiplier on LUTEAL_TEMP_OFFSET_C (0.35); population default: 1.0\n  fitted_from_cycles: number       // number of complete cycles used for fitting\n  computed_at: string\n}\n\ntype ObjectiveThresholds = {\n  pacing_discipline?: number        // default: 0.03 (3% variance)\n  encroachment_events?: number      // default: 3 events\n  // ... other objective categories\n}\n```",
          "Invariants": "- One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.\n- `sex = 'female'` enables menstrual cycle tracking (`CyclePhaseLog`) and cycle modifier in wellness computation.\n- `gap_curve_model` is applied when `current_effort_generation >= 2`. Upgrade to Gen 2 requires `r_squared >= 0.70`; downgrade to Gen 1 requires `r_squared < 0.65`. See `02-computations/effort-normalisation.md` for the hysteresis state machine.\n- `weather_response_model` is only applied when `r_squared >= 0.65`.\n- `banister_constants` stores per-athlete fitted time constants. When set, `AthleteFitness.time_constants` references these values (source='individual_fitted'). When null, `AthleteFitness.time_constants` uses population defaults (source='population_default').\n- `cycle_personal_model.phase_sensitivity` of `0.0` means the model detected no phase correlation \u2014 cycle modifier is effectively zeroed for this athlete. This is a valid outcome.\n- `cycle_personal_model.luteal_temp_sensitivity` of `1.0` means the population default thermoregulatory offset applies. Values <1.0 indicate lower-than-average thermal sensitivity; >1.0 indicate higher. When `cycle_personal_model` is null, `LUTEAL_TEMP_OFFSET_C` (0.35) applies at full population weight.\n- `timezone` is required at onboarding (validated against IANA tz database). Immutable after creation \u2014 changing timezone requires a support process. All scheduled tasks (MissedSessionSweepTask, WorkoutPrefetchTask) and date interpretations use this timezone.\n- `training_window` defaults to 06:00\u201320:00 if not set. Mutable via PATCH. Only used by WorkoutPrefetchTask for prefetch timing. MissedSessionSweepTask uses timezone only, not training_window.\n- `structural_risk_flag` is computed at onboarding from `AthletePreferences.sport_background`. When `true`, the structural load density penalty coefficient is 0.08 (vs 0.12 population default). See `02-computations/load-computation.md`.\n- `objective_thresholds` stores per-athlete evaluation thresholds for objective management. When null, population defaults are used (0.03 for pacing discipline, 3 for encroachment events). See `02-computations/objective-management.md`.",
          "Events": "### Produced\n| Event | Trigger | Version | Payload |\n|---|---|---|---|\n| None | \u2014 | \u2014 | \u2014 |\n\n### Consumed\n| Event | Action | Version |\n|---|---|---|\n| `activity_ingested` (outdoor, \u226520 sessions) | Triggers `GapCurveFittingTask` | v1 |\n| `activity_ingested` (outdoor, \u226525 sessions, heat_index range \u226510\u00b0C) | Triggers `WeatherResponseCurveFittingTask` | v1 |\n| `cycle_day_one_logged` (\u22653 complete cycles) | Triggers `CyclePersonalisationTask` | v1 |",
          "Cycle Personalisation Fitting": "`CyclePersonalisationTask` runs when `cycle_day_one_logged` fires and \u22653 complete cycles exist. It produces `cycle_personal_model` \u2014 a JSONB field overwritten on each refit.\n\n### Fitting Stages\n\n**Stage 1 \u2014 Cycle length:** Compute median interval between consecutive `cycle_day_one_date` entries. Minimum 3 intervals (4 log entries). Stored as `avg_cycle_length_days`.\n\n**Stage 2 \u2014 Phase boundaries:** Analyse execution data (pace-at-HR ratio, GAP deviation, RPE) across cycles to detect phase transitions. Fit `menstrual_end`, `follicular_end`, `ovulatory_end` to observed transition points. Fallback: proportional boundaries (`cycle_length * 5/28`, etc.) if execution data is insufficient.\n\n**Stage 3 \u2014 Phase sensitivity:** For each phase, compare execution quality in that phase vs overall baseline. Compute `phase_sensitivity[phase]` as a multiplier on the population prior adjustment:\n- `0.0` = no phase correlation detected (adjustment zeroed)\n- `1.0` = full population effect\n- `>1.0` = stronger than population average\n\n**Stage 4 \u2014 Luteal thermoregulation:** Compare pace-at-HR in luteal vs follicular phases, controlling for ambient temperature (using `weather_response_model`). Compute `luteal_temp_sensitivity` as a multiplier on `LUTEAL_TEMP_OFFSET_C` (0.35). Population default: 1.0.\n\n### Fitting Prerequisites\n\n| Stage | Minimum data | Graceful fallback |\n|---|---|---|\n| Cycle length | 3 complete cycles (4 log entries) | Use 28-day default |\n| Phase boundaries | 3 cycles + \u22652 quality sessions per phase per cycle | Proportional boundaries from cycle length |\n| Phase sensitivity | 3 cycles + sufficient execution data per phase | `phase_sensitivity` = 1.0 (full population effect) |\n| Luteal thermoregulation | 3 cycles + outdoor sessions in both luteal and follicular at similar ambient temps | `luteal_temp_sensitivity` = 1.0 (population default) |\n\n### Refit Behaviour\n\n`cycle_personal_model` is overwritten on each refit (not accumulated). The fitting task re-runs when new cycle data arrives (\u22653 complete cycles). Earlier fits with fewer cycles produce less reliable models; later fits with more cycles produce more reliable models. The system always uses the most recent fit.",
          "APIs": "```yaml\nGET /athletes/{athlete_id}/profile\nResponse: 200\n  profile: AthleteProfile (gap_curve_model, weather_response_model, banister_constants excluded)\nAuth: Bearer JWT, require_self\n\nPATCH /athletes/{athlete_id}/profile\nRequest:\n  height_cm?: number\n  location_lat?: number\n  location_lng?: number\n  training_window?: { start: string; end: string }  // athlete's preferred training time window (local time)\nResponse: 200\n  profile: AthleteProfile\nAuth: Bearer JWT, require_self\nNote: date_of_birth, sex, and timezone are immutable after creation\n```",
          "Storage Model": "| Data | Strategy | Consistency | Retention |\n|---|---|---|---|\n| `athlete_profiles` table | mutable (PATCH for user fields) | strong | indefinite |\n| `gap_curve_model` JSONB | mutable (overwritten on refit) | strong | indefinite |\n| `cycle_personal_model` JSONB | mutable (overwritten on refit) | strong | indefinite |\n\nUnique constraint: `(athlete_id)` \u2014 one record per athlete.",
          "Mutation Rules": "| Layer | Read | Write | Delete |\n|---|---|---|---|\n| API | Yes (excluding model fields) | height_cm, location_lat, location_lng, training_window | No |\n| Service | Yes | Yes (all fields) | No |\n| Repository | Yes | Yes | No |",
          "Runtime Ownership": "Owns:\n- Stable demographic data\n- Fitted personalisation models (GAP curve, weather, Banister constants, cycle model)\n\nDoes Not Own:\n- Training preferences (mutable) \u2192 `01-entities/athlete-preferences.md`\n- When fitting tasks trigger \u2192 `02-computations/effort-normalisation.md`, `02-computations/adaptation-signature.md`",
          "Failure Semantics": "- If `GapCurveFittingService` produces `r_squared < 0.70` and `current_effort_generation == 1`, `gap_curve_model` is not updated. Population formula continues.\n- If `GapCurveFittingService` produces `r_squared < 0.65` and `current_effort_generation == 2`, `current_effort_generation` is downgraded to 1.\n- If `GapCurveFittingService` produces `r_squared >= 0.70` and `current_effort_generation == 1`, `current_effort_generation` is upgraded to 2.\n- If location is null, weather fetch is skipped gracefully. No error surfaced.",
          "Performance Constraints": "- `PATCH /athletes/{id}/profile`: p95 < 100ms",
          "Observability": "Metrics:\n- `athlete_profile.gap_curve.fitted`: count of athletes with `r_squared >= 0.70`\n- `athlete_profile.gap_curve.generation_transition`: count of generation upgrades and downgrades (by direction)\n- `athlete_profile.banister_constants.fitted`: count of athletes with individual constants\n- `athlete_profile.cycle_personal_model.fitted`: count of athletes with fitted cycle models\n- `athlete_profile.cycle_personal_model.sensitivity_zeroed`: count of athletes where `phase_sensitivity` = 0.0 for any phase (no correlation detected)\nLogs:\n- `athlete_profile.gap_curve.fitted`: athlete_id, r_squared, session_count\n- `athlete_profile.banister_constants.fitted`: athlete_id, fitted_from_weeks\n- `athlete_profile.cycle_personal_model.fitted`: athlete_id, fitted_from_cycles, avg_cycle_length_days",
          "Implementation Notes": "- `date_of_birth` and `sex` are immutable after creation. If an athlete needs to correct them, this requires a support process, not a self-service PATCH.\n- The personalisation model JSONB fields are written by background computation services, never by the athlete directly.\n- `location_lat/lng` is used only for weather fetch. It is populated from GPS tracks in recent Activity records if not explicitly set by the athlete."
        }
      },
      "cross_references": {
        "related_entities": [],
        "produces_events": [
          "None"
        ],
        "consumes_events": [
          "`activity_ingested` (outdoor, \u226520 sessions)",
          "`activity_ingested` (outdoor, \u226525 sessions, heat_index range \u226510\u00b0C)",
          "`cycle_day_one_logged` (\u22653 complete cycles)"
        ],
        "used_by_agents": [],
        "related_via_shared_events": {},
        "release_plan_features_introducing": [],
        "release_plan_features_modifying": []
      }
    }
  },
  "athlete-preferences": {
    "concept": "athlete-preferences",
    "found_domains": [
      "architecture"
    ],
    "architecture": {
      "entity_name": "athlete-preferences",
      "context": {
        "entity": "athlete-preferences",
        "graph": {
          "related_entities": [],
          "produces_events": [
            "None"
          ],
          "consumes_events": [
            "`onboarding_completed`"
          ],
          "used_by_agents": [],
          "invariants": [
            {
              "field": "AthletePreferences",
              "rule": "One `AthletePreferences` per `Athlete`. Created during onboarding. Enforced by unique constraint on `(athlete_id)`.",
              "type": "uniqueness",
              "enforcement": "database"
            },
            {
              "field": null,
              "rule": "`years_structured_training >= 0`. CHECK constraint at DB level.",
              "type": "range",
              "enforcement": "database"
            },
            {
              "field": null,
              "rule": "No DELETE endpoint. Preferences are always present once onboarding completes.",
              "type": "behavioral",
              "enforcement": "api"
            },
            {
              "field": "sport_background",
              "rule": "`sport_background` not `running_primary` activates the crossover athlete structural capacity ramp in plan generation. See `02-computations/plan-generation.md` (shared types) and `02-computations/plan-generation-race.md` (race mode ramp).",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "training_time_of_day",
              "rule": "`training_time_of_day` feeds the time-of-day modifier in `WellnessModifierService`. See `02-computations/wellness-modifier.md`.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "hr_source",
              "rule": "`hr_source` is the primary input for data tier inference. See `00-foundations/data-tiers.md`.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "hr_source",
              "rule": "Changes to `hr_source` or `power_source` affect the data tier of the next ingested Activity but do not retroactively alter historical Activities.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "weekly_schedule",
              "rule": "`weekly_schedule` is stored as structured JSONB. Each day's `available` and `max_hours` directly constrain `PlanGenerationService` session distribution. `long_workout` marks the day for long run placement. `doubles_eligible` marks the day as eligible for AM primary + PM secondary sessions.",
              "type": "behavioral",
              "enforcement": "application"
            }
          ],
          "api_endpoints": [
            {
              "method": "POST",
              "path": "/athletes/{athlete_id}/preferences",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "GET",
              "path": "/athletes/{athlete_id}/preferences",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "PATCH",
              "path": "/athletes/{athlete_id}/preferences",
              "auth": "Bearer JWT",
              "response_status": 200
            }
          ],
          "storage_models": [
            {
              "table": "athlete_preferences` table",
              "strategy": "mutable (patch)",
              "consistency": "strong",
              "retention": "indefinite"
            }
          ]
        },
        "sections": {
          "Purpose": "- Stores the athlete's training setup, hardware, schedule availability, and platform connections\n- Drives data tier inference, plan session distribution, and wellness modifier time-of-day correction\n- Mutable via PATCH; changes affect future plan generation but never historical analysis",
          "TypeScript Schema": "```typescript\ntype SportBackground =\n  | 'running_primary' | 'cycling' | 'swimming'\n  | 'triathlon' | 'team_sport' | 'gym_fitness' | 'none'\n\ntype TrainingTimeOfDay = 'morning' | 'afternoon' | 'evening' | 'variable'\n\ntype GpsSource =\n  | 'garmin_watch' | 'apple_watch' | 'polar'\n  | 'suunto' | 'coros' | 'other'\n\ntype HrSource =\n  | 'chest_strap_rr'      // enables RR intervals \u2192 Tier 1 or 3\n  | 'chest_strap_no_rr'   // HR only \u2192 Tier 4\n  | 'wrist_optical'       // HR only \u2192 Tier 4\n  | 'none'                // no HR \u2192 Tier 5\n\ntype PowerSource = 'running_power_meter' | 'none'\n\ntype PrimaryTrainingPlatform = 'intervals_icu' | 'garmin_connect' | 'manual'\n\ntype DaySchedule = {\n  available: boolean\n  max_hours: number        // ignored if available = false\n  long_workout: boolean    // marks the day as eligible for long run placement\n  doubles_eligible: boolean  // marks the day as eligible for AM primary + PM secondary sessions\n}\n\ntype WeeklySchedule = {\n  monday: DaySchedule\n  tuesday: DaySchedule\n  wednesday: DaySchedule\n  thursday: DaySchedule\n  friday: DaySchedule\n  saturday: DaySchedule\n  sunday: DaySchedule\n}\n\ntype AthletePreferences = {\n  id: string                        // UUID, PK\n  athlete_id: string               // UUID, FK \u2192 Athlete, one-to-one\n  sport_background: SportBackground\n  years_structured_training: number  // >= 0\n  training_time_of_day: TrainingTimeOfDay\n  weekly_schedule: WeeklySchedule\n  gps_source: GpsSource\n  hr_source: HrSource\n  power_source: PowerSource\n  primary_training_platform: PrimaryTrainingPlatform\n  updated_at: string               // ISO 8601\n}\n```",
          "Invariants": "- One `AthletePreferences` per `Athlete`. Created during onboarding. Enforced by unique constraint on `(athlete_id)`.\n- `years_structured_training >= 0`. CHECK constraint at DB level.\n- No DELETE endpoint. Preferences are always present once onboarding completes.\n- `sport_background` not `running_primary` activates the crossover athlete structural capacity ramp in plan generation. See `02-computations/plan-generation.md` (shared types) and `02-computations/plan-generation-race.md` (race mode ramp).\n- `training_time_of_day` feeds the time-of-day modifier in `WellnessModifierService`. See `02-computations/wellness-modifier.md`.\n- `hr_source` is the primary input for data tier inference. See `00-foundations/data-tiers.md`.\n- Changes to `hr_source` or `power_source` affect the data tier of the next ingested Activity but do not retroactively alter historical Activities.\n- `weekly_schedule` is stored as structured JSONB. Each day's `available` and `max_hours` directly constrain `PlanGenerationService` session distribution. `long_workout` marks the day for long run placement. `doubles_eligible` marks the day as eligible for AM primary + PM secondary sessions.",
          "Data Tier Inference": "```typescript\nfunction inferDataTier(prefs: AthletePreferences): DataTier {\n  if (prefs.power_source === 'running_power_meter') {\n    return prefs.hr_source === 'chest_strap_rr' ? 1 : 2\n  }\n  if (prefs.hr_source === 'chest_strap_rr') return 3\n  if (prefs.hr_source === 'chest_strap_no_rr' || prefs.hr_source === 'wrist_optical') return 4\n  if (prefs.hr_source === 'none') return 5\n  return 6\n}\n```",
          "Events": "### Produced\n| Event | Trigger | Version | Payload |\n|---|---|---|---|\n| None | \u2014 | \u2014 | \u2014 |\n\n### Consumed\n| Event | Action | Version |\n|---|---|---|\n| `onboarding_completed` | Preferences already written; no action | v1 |",
          "APIs": "```yaml\nPOST /athletes/{athlete_id}/preferences\nDescription: Created during onboarding; not a standalone endpoint\nResponse: embedded in onboarding response\n\nGET /athletes/{athlete_id}/preferences\nResponse: 200\n  preferences: AthletePreferences\nAuth: Bearer JWT, require_self\n\nPATCH /athletes/{athlete_id}/preferences\nRequest:\n  # any subset of AthletePreferences fields\n  sport_background?: SportBackground\n  years_structured_training?: number\n  training_time_of_day?: TrainingTimeOfDay\n  weekly_schedule?: Partial<WeeklySchedule>\n  gps_source?: GpsSource\n  hr_source?: HrSource\n  power_source?: PowerSource\n  primary_training_platform?: PrimaryTrainingPlatform\nResponse: 200\n  preferences: AthletePreferences\nNote: Changes to hr_source or power_source may trigger plan regeneration\n     if the data tier ceiling changes materially.\nAuth: Bearer JWT, require_self\n```",
          "Storage Model": "| Data | Strategy | Consistency | Retention |\n|---|---|---|---|\n| `athlete_preferences` table | mutable (PATCH) | strong | indefinite |\n\nUnique constraint: `(athlete_id)` \u2014 one record per athlete.\n\nChanges are not versioned \u2014 only `updated_at` is tracked. Historical preference states are not retained. This is intentional: preferences affect future plan generation, not historical analysis.",
          "Mutation Rules": "| Layer | Read | Write | Delete |\n|---|---|---|---|\n| API | Yes | PATCH only | No |\n| Service | Yes | Yes | No |\n| Repository | Yes | Yes | No |",
          "Runtime Ownership": "Owns:\n- Hardware and platform configuration\n- Weekly schedule availability\n- Data tier ceiling inference\n\nDoes Not Own:\n- Data tier assigned to a specific Activity (that is inferred per-session at ingestion)\n- Plan generation decisions \u2192 `02-computations/plan-generation.md`\n- Wellness modifier time-of-day correction \u2192 `02-computations/wellness-modifier.md`",
          "Failure Semantics": "- PATCH with invalid `weekly_schedule` (e.g. `max_hours < 0`) \u2192 422 Unprocessable Entity\n- PATCH that changes `hr_source` or `power_source` \u2192 triggers async plan regeneration check; PATCH response returns immediately",
          "Performance Constraints": "- `GET /athletes/{id}/preferences`: p95 < 50ms\n- `PATCH /athletes/{id}/preferences`: p95 < 100ms",
          "Observability": "Metrics:\n- `athlete_preferences.data_tier.distribution`: count by tier (monitoring hardware adoption)\nLogs:\n- `athlete_preferences.updated`: athlete_id, changed_fields, new_data_tier",
          "Implementation Notes": "- `weekly_schedule` partial PATCH merges at the day level \u2014 sending `{saturday: {available: false}}` disables Saturday without touching other days\n- Plan generation reads `weekly_schedule` to determine which days can receive sessions and which day receives the long run (`long_workout: true`)\n- The crossover athlete flag is derived from `sport_background !== 'running_primary'` \u2014 no separate boolean field"
        }
      },
      "cross_references": {
        "related_entities": [],
        "produces_events": [
          "None"
        ],
        "consumes_events": [
          "`onboarding_completed`"
        ],
        "used_by_agents": [],
        "related_via_shared_events": {},
        "release_plan_features_introducing": [],
        "release_plan_features_modifying": []
      }
    }
  },
  "activity": {
    "concept": "activity",
    "found_domains": [
      "architecture"
    ],
    "architecture": {
      "entity_name": "activity",
      "context": {
        "entity": "activity",
        "graph": {
          "related_entities": [],
          "produces_events": [
            "`activity_ingested`",
            "`activity_calibration_eligible`"
          ],
          "consumes_events": [
            "`session_completed`"
          ],
          "used_by_agents": [],
          "invariants": [
            {
              "field": "fit_file_key",
              "rule": "`fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "avg_hr",
              "rule": "`avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` \u2014 these fields do not exist on `Activity`. They are never added.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "aerobic_load",
              "rule": "`aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "calibration_eligible",
              "rule": "`calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "manual_entry",
              "rule": "Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.",
              "type": "behavioral",
              "enforcement": "application"
            },
            {
              "field": "external_id",
              "rule": "Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.",
              "type": "uniqueness",
              "enforcement": "application"
            }
          ],
          "api_endpoints": [
            {
              "method": "POST",
              "path": "/athletes/{athlete_id}/activities/upload",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "POST",
              "path": "/athletes/{athlete_id}/activities",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "GET",
              "path": "/athletes/{athlete_id}/activities",
              "auth": "Bearer JWT",
              "response_status": 200
            },
            {
              "method": "GET",
              "path": "/athletes/{athlete_id}/activities/{activity_id}",
              "auth": "Bearer JWT",
              "response_status": 200
            }
          ],
          "storage_models": [
            {
              "table": "activities` table",
              "strategy": "append-only (no update after load scores written)",
              "consistency": "strong",
              "retention": "indefinite"
            },
            {
              "table": "Raw FIT file",
              "strategy": "object storage, immutable",
              "consistency": "eventual",
              "retention": "indefinite"
            },
            {
              "table": "Cleaned stream",
              "strategy": "object storage, immutable",
              "consistency": "eventual",
              "retention": "indefinite"
            }
          ]
        },
        "sections": {
          "Purpose": "- Lean index record for a single completed training session, storing what the twin needs\n- Never stores workout summaries; the FIT file is the source of truth for everything else",
          "TypeScript Schema": "```typescript\ntype ActivitySource = 'intervals_icu' | 'manual_upload' | 'garmin_direct' | 'manual_entry'\n\ntype QualityFlags = {\n  hr_dropout_pct?: number           // if > 20%, disqualifies calibration eligibility\n  gps_loss?: boolean\n  sensor_malfunction?: boolean\n  elevated_laxity_risk?: boolean    // ovulatory phase flag (3c)\n}\n\ntype Activity = {\n  id: string                        // UUID, PK\n  athlete_id: string                // UUID, FK \u2192 Athlete\n  planned_session_id: string | null // FK \u2192 PlannedSession; null for unplanned\n  source: ActivitySource\n  external_id: string | null        // source platform ID; for deduplication\n  activity_date: string             // YYYY-MM-DD\n  start_time: string                // ISO 8601 datetime\n  duration_seconds: number\n\n  // Load scores \u2014 persisted for query performance (twin reads across weeks of history)\n  aerobic_load: number | null       // null for Tier 6; low-confidence for Tier 5\n  neuromuscular_load: number | null // null for Tier 5 and 6\n  structural_load: number | null    // null for Tier 6\n\n  // Signal availability\n  has_hr: boolean\n  has_rr_intervals: boolean\n  has_power: boolean\n\n  // Calibration\n  calibration_eligible: boolean\n  quality_flags: QualityFlags\n\n  // Reprocessing anchor \u2014 REQUIRED for all non-manual-entry sources\n  fit_file_key: string | null       // null ONLY for source = 'manual_entry'\n\n  // Versioning\n  ingestion_pipeline_version: string | null\n  cleaning_pipeline_version: string | null  // set after 5a cleaning pipeline runs\n  notes: string | null\n  created_at: string\n}\n```",
          "Invariants": "- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.\n- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` \u2014 these fields do not exist on `Activity`. They are never added.\n- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.\n- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.\n- Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.\n- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.",
          "State Transitions": "```mermaid\nstateDiagram-v2\n    [*] --> created : FIT ingestion task commits\n    created --> load_computed : LoadComputationService runs\n    load_computed --> calibration_evaluated : CalibrationEligibilityService runs\n    calibration_evaluated --> twin_updated : if calibration_eligible = true\n    calibration_evaluated --> record_only : if calibration_eligible = false\n    load_computed --> cleaned : SignalCleaningService runs\n    cleaned --> segmented : SegmentationTask runs\n```",
          "Events": "### Produced\n| Event | Trigger | Version | Payload |\n|---|---|---|---|\n| `activity_ingested` | Activity record created | v1 | `{activity_id, date, duration, has_hr, has_rr, has_power, fit_file_key}` |\n| `activity_calibration_eligible` | calibration_eligible set true | v1 | `{activity_id, aerobic_load, neuromuscular_load, structural_load}` |\n\n### Consumed\n| Event | Action | Version |\n|---|---|---|\n| `session_completed` | Sets `planned_session_id` FK | v1 |",
          "APIs": "```yaml\nPOST /athletes/{athlete_id}/activities/upload\nRequest: multipart/form-data\n  file: FIT file, required\n  planned_session_id?: UUID\nResponse: 202 Accepted\n  task_id: string  # track ingestion progress\nAuth: Bearer JWT, require_self\n\nPOST /athletes/{athlete_id}/activities\nRequest: (manual entry)\n  source: 'manual_entry'\n  activity_date: string\n  duration_seconds: number\n  planned_session_id?: UUID\n  has_hr?: boolean\n  notes?: string\nResponse: 201\n  activity: ActivityResponse\nAuth: Bearer JWT, require_self\n\nGET /athletes/{athlete_id}/activities\nQuery:\n  from?: date\n  to?: date\n  limit?: number (default 20, max 100)\n  offset?: number\nResponse: 200\n  activities: ActivityResponse[]\n  total: number\nAuth: Bearer JWT, require_self\n\nGET /athletes/{athlete_id}/activities/{activity_id}\nResponse: 200\n  activity: ActivityResponse\nAuth: Bearer JWT, require_self\n```",
          "Storage Model": "| Data | Strategy | Consistency | Retention |\n|---|---|---|---|\n| `activities` table | append-only (no UPDATE after load scores written) | strong | indefinite |\n| Raw FIT file | object storage, immutable | eventual | indefinite |\n| Cleaned stream | object storage, immutable | eventual | indefinite |",
          "Mutation Rules": "| Layer | Read | Write | Delete |\n|---|---|---|---|\n| API | Yes | Via upload/manual endpoints only | No |\n| Service | Yes | Load scores, calibration flag, version fields only | No |\n| Repository | Yes | Yes | No |",
          "Runtime Ownership": "Owns:\n- The lean observation index\n- The `fit_file_key` reprocessing anchor\n- Calibration eligibility flag\n\nDoes Not Own:\n- Load score formulas \u2192 `02-computations/load-computation.md`\n- Segmentation records \u2192 `01-entities/physiological-segment.md`\n- Execution analysis \u2192 `01-entities/execution-observation.md`\n- Session lifecycle (planned_session_id linkage) \u2192 `01-entities/planned-session.md`",
          "Idempotency": "- FIT file ingestion is idempotent for the same `(athlete_id, external_id, source)` \u2014 second call returns the existing Activity\n- Manual FIT upload: if the same file is uploaded twice, deduplication relies on the athlete to check; no automatic deduplication for `source = manual_upload`",
          "Authorization": "- All endpoints require `require_self`: JWT athlete_id must match path athlete_id\n- Activity data is never shared between athletes",
          "Failure Semantics": "- Object storage failure during FIT upload \u2192 task retries; no Activity record created; 202 Accepted returns a task_id; athlete can poll for status\n- `LoadComputationService` failure \u2192 Activity exists with null load scores; retry scheduled (up to 3\u00d7); `calibration_eligible = false` until recomputed; `activity.load_compute.failures` incremented; after max retries \u2192 `activity.load_compute.stuck.count` incremented + DLQ entry\n- FIT parsing failure (corrupt file) \u2192 Activity NOT created; 422 returned to caller with parse error detail",
          "Performance Constraints": "Synchronous API latency:\n- `POST /activities/upload`: p95 < 500ms (async; just stores file and enqueues task)\n- `GET /activities`: p95 < 200ms\n- `GET /activities/{id}`: p95 < 50ms\n\nAsynchronous operations:\n- Full ingestion pipeline (parse + load + clean): p95 < 30s\n- Segmentation task: p95 < 60s (runs after cleaning)",
          "Observability": "Metrics:\n- `activity.ingested.total`: by source\n- `activity.calibration_eligible.rate`: percentage of ingested activities that are eligible\n- `activity.ingestion.latency_ms`: time from FIT upload to load scores written\n- `activity.fit_parse.failures`: count of corrupt/unreadable files\n- `activity.load_compute.failures`: count of LoadComputationService failures\n- `activity.load_compute.retry.count`: retry attempts per activity\n- `activity.load_compute.stuck.count`: activities exceeding max retries (DLQ candidates)\nLogs:\n- `activity.ingested`: activity_id, source, has_hr, has_rr, has_power, calibration_eligible\n- `activity.fit_parse.failed`: athlete_id, source, error_type\nTraces:\n- `ingestion_pipeline`: fit_received \u2192 object_storage \u2192 parse \u2192 load_compute \u2192 calibration \u2192 twin_update",
          "Implementation Notes": "- The `fit_file_key` pattern `fit-files/{athlete_id}/{activity_date}/{uuid}.fit` ensures activities are retrievable by athlete without a DB query\n- Load scores are indexed on the `activities` table because `TwinRecalibrationService` queries them with a rolling window (e.g. last 90 days) \u2014 this passes the reprocessing test\n- The `cleaning_pipeline_version` null \u2192 non-null transition is the signal that a `RawSensorStream` has been created for this activity"
        }
      },
      "cross_references": {
        "related_entities": [],
        "produces_events": [
          "`activity_ingested`",
          "`activity_calibration_eligible`"
        ],
        "consumes_events": [
          "`session_completed`"
        ],
        "used_by_agents": [],
        "related_via_shared_events": {},
        "release_plan_features_introducing": [],
        "release_plan_features_modifying": []
      }
    }
  },
  "terminology": {
    "concept": "terminology",
    "found_domains": [
      "architecture"
    ],
    "architecture": {
      "entity_name": "terminology",
      "context": {
        "entity": "terminology",
        "graph": {
          "related_entities": [],
          "produces_events": [],
          "consumes_events": [],
          "used_by_agents": [],
          "invariants": [],
          "api_endpoints": [],
          "storage_models": []
        },
        "sections": {
          "Purpose": "- Defines every domain term used across architecture documents with precision\n- Eliminates ambiguity when terms have common meanings that differ from their Pheidipp meaning",
          "Core Domain Terms": "### Activity\nA lean physiological observation record for a single completed training session. Not a workout summary. Stores what the twin needs, never what Garmin already computed. See `01-entities/activity.md`.\n\n### Calibration-Eligible\nAn `Activity` that meets the five-rule gate for twin recalibration. See `02-computations/load-computation.md`. A session that is not calibration-eligible still exists in the training record but does not update the twin model.\n\n### Coaching Observation\nA pre-computed structured finding produced by the `ExecutionAnalysisService` and stored in `ExecutionObservation.coaching_observations`. The LLM receives this and writes narrative from it. The LLM does not produce the observation.\n\n### Confidence Level\nAn assertion about how much real training data the twin has learned from for a given athlete. **Per-metric**: each physiological parameter (LT1, LT2, CP) accumulates evidence independently. Global confidence level is derived as the minimum of LT1 HR and LT2 HR confidence for simple consumers. Three values: `low`, `medium`, `high`. Affects coaching language precision and whether race predictions are surfaced. See `00-foundations/confidence-model.md`.\n\n### Data Tier\nA classification of an athlete's hardware capability that determines which signals are available for load computation and threshold detection. Six tiers from Tier 1 (running power + chest strap RR) to Tier 6 (manual entry only). See `00-foundations/data-tiers.md`.\n\n### Digital Twin\nThe ensemble of all TwinState, ExecutionObservation, AdaptationObservation, AthleteWellness, and CyclePhaseLog records for an athlete, plus the computation services that interpret them. Not a single entity \u2014 a living model of the athlete's physiological state.\n\n### Effort Normalisation\nThe process of converting raw pace to a physiologically comparable effort measure, accounting for terrain grade and eventually individual biomechanics. Three generations: static GAP \u2192 per-athlete curve \u2192 personalised cost model. See `02-computations/effort-normalisation.md`.\n\n### FIT File\nThe binary file format produced by Garmin and other sports devices. The raw, immutable source record for all analytical computation. Stored in object storage; never modified; referenced by `fit_file_key` on every `Activity`.\n\n### `fit_file_key`\nThe object storage key referencing the raw FIT file for an Activity. The reprocessing anchor for the entire analytical pipeline. Required on every Activity that is not a manual entry.\n\n### GAP (Grade-Adjusted Pace)\nPace normalised for terrain gradient so that uphill and flat efforts are comparable. The system-wide standard for all pace-based computations. Raw pace is never used in any calculation. See `02-computations/effort-normalisation.md`.\n\n### Generation Event\nA log record written for every LLM API call attempt, whether successful or failed. The primary operational observability primitive for the coaching layer. See `01-entities/generation-event.md`.\n\n### Hard Block\nA training unit of two to three quality sessions in close succession. The atomic unit for adaptation signature computation. See `02-computations/adaptation-signature.md`.\n\n### LT1\nLactate threshold 1 \u2014 the intensity at which blood lactate first begins to rise above resting baseline. Corresponds to the aerobic threshold and the lower boundary of the high aerobic zone. Estimated by threshold detection from HR or RR signal.\n\n### LT2\nLactate threshold 2 \u2014 the intensity at which lactate accumulation exceeds the body's buffering capacity. Corresponds to the anaerobic threshold / functional threshold. The primary reference for threshold zone workout targets.\n\n### PhysiologicalIntent\nThe canonical enum representing the physiological adaptation a session targets. Six values: `low_aerobic`, `high_aerobic`, `threshold`, `vo2max`, `neuromuscular`, `recovery`. This is the middle layer of the three-layer hierarchy: MethodologyTraitVector \u2192 PhysiologicalIntent \u2192 SessionType. See `00-foundations/terminology.md` \u2192 Shared Enums.\n\n### Readiness\nThe twin's current assessment of an athlete's capacity for today's training, computed from the combination of TwinState fitness/fatigue scores and Layer 4 wellness modifier. Expressed as GREEN / AMBER / RED in the recovery modifier and as plain language in coaching messages.\n\n### Recovery Modifier\nThe GREEN / AMBER / RED classification of an athlete's current readiness relative to their wellness baseline. Computed by `WellnessModifierService`. Applied to `GeneratedWorkout.adjusted_targets`. See `02-computations/wellness-modifier.md`.\n\n### Reprocessing Anchor\nThe `fit_file_key` stored on every non-manual Activity. Because the raw FIT file is always available, any analytical record derived from it (load scores, segments, execution observations) can be regenerated through an improved algorithm. See `00-foundations/data-tiers.md` and `04-platform/versioning-and-reprocessing.md`.\n\n### Session Shape\nA classification of how a session unfolded relative to prescribed intent. Values: `steady`, `progressive_fade`, `positive_split`, `w_shape`, `strong_finish`. Computed by `ExecutionAnalysisService`; stored on `ExecutionObservation`.\n\n### Training Goal\nA period of goal-directed training with a defined start, status, and optional goal event. The temporal container for a `TrainingPlan`. One active goal per athlete at a time. See `01-entities/training-goal.md`.\n\n### TwinState\nAn append-only snapshot of the twin's understanding of an athlete at a point in time. Never updated in place. The most recent TwinState is the current state; older records are the audit trail. See `01-entities/twin-state.md`.\n\n### Version String\nA frozen identifier for a specific pipeline snapshot. Format: `v1`, `v1.1`, `v2-rr-threshold`. Stored on every analytical record. Enables offline reprocessing and historical record comparison. See `04-platform/versioning-and-reprocessing.md`.",

...34282 bytes truncated...

The tool call succeeded but the output was truncated. Full output saved to: /home/ruimendes/.local/share/opencode/tool-output/tool_eb4af32f8001pa6Z94NB5NVrTZ
Use Grep to search the full content or Read with offset/limit to view specific sections.
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 11.3s)

_Thinking:_


Output truncated but enough? Need exact terminology enums maybe use get_entity_context sections for terminology "Shared Enums" maybe. Need data-tiers. Need maybe vision contexts. Use get_entity_context sections for terminology, data-tiers.


**Tool: pheidipp-codebase-context_get_entity_context**

**Input:**
```json
{
  "entity_name": "terminology",
  "sections": [
    "Shared Enums"
  ]
}
```

**Output:**
```
{
  "entity": "terminology",
  "graph": {
    "related_entities": [],
    "produces_events": [],
    "consumes_events": [],
    "used_by_agents": [],
    "invariants": [],
    "api_endpoints": [],
    "storage_models": []
  },
  "sections": {
    "Shared Enums": "### PhysiologicalIntent\n```typescript\ntype PhysiologicalIntent =\n  | 'low_aerobic'\n  | 'high_aerobic'\n  | 'threshold'\n  | 'vo2max'\n  | 'neuromuscular'\n  | 'recovery'\n```\nThe physiological adaptation a session targets. Each workout step has exactly one intent. This is the primary coaching abstraction \u2014 the system works directly with intents, not zones. Many:1 mapping from SessionType (16 sessions \u2192 6 intents).\n\n### PhysiologyParameter\n```typescript\ntype PhysiologyParameter =\n  | 'lt1.hr'\n  | 'lt1.power'\n  | 'lt1.pace'\n  | 'lt2.hr'\n  | 'lt2.power'\n  | 'lt2.pace'\n  | 'cp'\n  | 'vo2max.ml_kg_min'\n  | 'vo2max.power'\n  | 'max_hr'\n```\nIdentifies a specific physiological parameter in event payloads and computation contexts. Dot notation reflects the nested structure of `AthletePhysiology` (e.g., `lt1.hr` is the HR-based LT1 threshold estimate). Used in `physiology_updated` and `physiology_lab_test_ingested` event payloads to specify which parameters were updated.\n\n**Compliance families:**\n- **Aerobic family** (intensity ladder): `recovery` \u2192 `low_aerobic` \u2192 `high_aerobic` \u2192 `threshold` \u2192 `vo2max`\n- **Neuromuscular family** (orthogonal): `neuromuscular`\n\nNeuromuscular efforts are not \"above VO2max\" or \"below threshold\" \u2014 they are a different physiological system entirely.\n\n### TwinConfidenceLevel\n```typescript\ntype TwinConfidenceLevel = 'low' | 'medium' | 'high'\n```\n\n### RecoveryModifierLevel\n```typescript\ntype RecoveryModifierLevel = 'green' | 'amber' | 'red'\n```\n\n### SessionType\n```typescript\ntype SessionType =\n  | 'rest'\n  | 'recovery_run'\n  | 'easy_run'\n  | 'long_run'\n  | 'medium_long_run'\n  | 'steady_state'\n  | 'tempo'\n  | 'threshold'\n  | 'vo2max'\n  | 'hill_repeats'\n  | 'fartlek'\n  | 'strides'\n  | 'drills_mobility'\n  | 'cross_training'\n  | 'test_session'\n  | 'optional_run'\n```\nThe concrete workout prescription. The coaching construct that appear on the calendar. Maps to PhysiologicalIntent via `SESSION_INTENT_MAP`.\n\nNote: `race_specific` is NOT a SessionType \u2014 it is a SessionPurpose. A marathon pace long run is `session_type: long_run, purpose: race_specific`.\n\n### SessionPurpose\n```typescript\ntype SessionPurpose =\n  | 'general'            // Standard training session\n  | 'race_specific'      // Race-pace, race strategy\n  | 'calibration'        // Test, time trial, benchmark\n```\nThe contextual reason for the session. Not the adaptation, but the coaching rationale. Affects how results are interpreted, not compliance assessment.\n\n**Interpretation rules:**\n- `general`: Standard compliance assessment (was intensity matched?)\n- `race_specific`: Execution quality assessment (did the athlete race well?)\n- `calibration`: Data quality assessment (was sufficient signal collected?)\n\n### SessionSlot\n```typescript\ntype SessionSlot = 'am' | 'pm'\n```\nUsed to distinguish AM/PM sessions on double-day schedules. Null for single-session days.\n\n### SessionPriority\n```typescript\ntype SessionPriority = 'primary' | 'secondary'\n```\nPrimary sessions receive full workout generation. Secondary sessions may be suggested without detailed targets (e.g. strength, yoga). Recovery time is measured from primary to primary.\n\n### InjurySeverity\n```typescript\ntype InjurySeverity = 'minor' | 'moderate' | 'major'\n```\nUsed when `goal_type = 'recovery'` to determine phase duration and load progression.\n\n### GoalType\n```typescript\ntype GoalType =\n  | 'race_event'        // periodised toward specific goal; peaking, tapering, race-specific preparation\n  | 'target_performance' // gap-analysis driven; athlete sets target time; system determines date\n  | 'fitness_improvement' // active development; progressive overload; measurable gains\n  | 'maintenance'       // consistency-focused; habit preservation; fitness preservation\n  | 'recovery'          // healing-focused; conservative load; protective coaching\n```\n\n### PhaseLabel\n```typescript\ntype PhaseLabel =\n  // Aerobic development\n  | 'aerobic_base'\n  | 'aerobic_foundation'\n  | 'aerobic_accumulation'\n  | 'aerobic_build'\n  \n  // Structural\n  | 'hill_phase'\n  | 'structural_tolerance'\n  \n  // Threshold\n  | 'threshold_build'\n  | 'threshold_peak'\n  | 'threshold_consolidation'\n  \n  // VO2max\n  | 'vo2max_development'\n  | 'vo2max_sharpening'\n  \n  // Race-specific\n  | 'special_endurance'\n  | 'specific_endurance'\n  | 'race_rehearsal'\n  \n  // Integration\n  | 'sharpening'\n  | 'taper'\n  | 'race_week'\n  \n  // Recovery\n  | 'recovery'\n  | 'transition'\n  \n  // Maintenance\n  | 'rolling_block'\n\n  // Legacy aliases (mapped to canonical labels by expansion layer)\n  | 'base_building'        // \u2192 'aerobic_base'\n  | 'threshold_development' // \u2192 'threshold_build'\n  | 'race_specific'        // \u2192 'specific_endurance'\n```\n\nClosed ontology \u2014 methodology-specific phase labels. The hypothesis agent selects from these labels to express methodology-specific phase intent. Legacy aliases (`base_building`, `threshold_development`, `race_specific`) are mapped to canonical labels by the deterministic expansion layer; new plans should use canonical labels directly.\n\n**Methodology mapping:**\n| Methodology | Typical Phase Sequence |\n|---|---|\n| Lydiard | `aerobic_base` \u2192 `hill_phase` \u2192 `anaerobic_phase` \u2192 `sharpening` |\n| Norwegian | `aerobic_foundation` \u2192 `threshold_build` \u2192 `threshold_peak` \u2192 `taper` |\n| Canova | `aerobic_build` \u2192 `special_endurance` \u2192 `specific_endurance` \u2192 `taper` |\n| Daniels | `aerobic_base` \u2192 `threshold_build` \u2192 `vo2max_development` \u2192 `sharpening` |\n| Pfitzinger | `aerobic_base` \u2192 `threshold_build` \u2192 `specific_endurance` \u2192 `taper` |\n| Hybrid | Any combination of the above, as long as the trajectory is coherent |\n\n### CyclePhase\n```typescript\ntype CyclePhase = 'menstrual' | 'follicular' | 'ovulatory' | 'luteal' | 'unknown'\n```\n\n### DataTier\n```typescript\ntype DataTier = 1 | 2 | 3 | 4 | 5 | 6\n```\nSee `00-foundations/data-tiers.md` for hardware mapping.\n\n### CheckpointType\n\n```typescript\ntype CheckpointType =\n  | 'calibration'        // test workout for specific metric\n  | 'benchmark'          // standardised progress measurement\n  | 'race_simulation'    // race-pace effort without full stress\n  | 'secondary_race'     // B-race or C-race as assessment\n  | 'progress_review'    // periodic adaptation check\n```\n\n### MethodologyTrait\n```typescript\ntype MethodologyTrait =\n  | 'high_aerobic_volume'\n  | 'low_intensity_dominant'\n  | 'threshold_density'\n  | 'high_intensity_sparse'\n  | 'high_frequency'\n  | 'structural_durability'\n  | 'race_specificity'\n  | 'variety_emphasis'\n  | 'neuromuscular_support'\n  | 'conservative_progression'\n```\nOne of ten fixed dimensions describing coaching philosophy expression. Closed ontology \u2014 not extensible. Hidden from athletes, optionally explainable in plain language.\n\n### MethodologyTraitVector\n```typescript\ntype MethodologyTraitVector = {\n  high_aerobic_volume: number        // 0.0 - 1.0 expression\n  low_intensity_dominant: number\n  threshold_density: number\n  high_intensity_sparse: number\n  high_frequency: number\n  structural_durability: number\n  race_specificity: number\n  variety_emphasis: number\n  neuromuscular_support: number\n  conservative_progression: number\n}\n```\nFixed vector \u2014 all traits present, omitted = zero. Expression/strength values (0.0\u20131.0), not weights. Highest layer of the three-layer hierarchy: MethodologyTraitVector \u2192 PhysiologicalIntent \u2192 SessionType. Phase-level evolution, not weekly.\n\n### SessionIntentMapping\n```typescript\ntype SessionIntentMapping = {\n  [key in SessionType]: PhysiologicalIntent\n}\n\nconst SESSION_INTENT_MAP: SessionIntentMapping = {\n  'rest': 'recovery',\n  'recovery_run': 'recovery',\n  'easy_run': 'low_aerobic',\n  'long_run': 'high_aerobic',\n  'medium_long_run': 'high_aerobic',\n  'steady_state': 'high_aerobic',\n  'tempo': 'threshold',\n  'threshold': 'threshold',\n  'vo2max': 'vo2max',\n  'hill_repeats': 'vo2max',\n  'fartlek': 'vo2max',\n  'strides': 'neuromuscular',\n  'drills_mobility': 'neuromuscular',\n  'cross_training': 'low_aerobic',\n  'test_session': 'vo2max',  // default; actual intent depends on test protocol\n  'optional_run': 'recovery'\n}\n```\nMany:1 mapping from 16 session types to 6 intents. Canonical reference for session\u2192intent derivation. Note: `test_session` intent depends on the specific test protocol \u2014 the default is `vo2max` but may be `threshold` or `high_aerobic` depending on the test.\n\n### WorkoutTarget\n```typescript\ntype WorkoutTarget = {\n  signal_type: 'power' | 'gap' | 'hr' | 'description'\n  primary: {\n    min: number | null\n    max: number | null\n    unit: string\n  }\n  fallback: WorkoutTarget | null\n  description: string  // always present; plain English\n}\n```\nRange-based target for a workout step. The athlete sees explicit numbers (e.g., \"250-280W\"), never zone numbers. The system selects the best signal type based on session type, physiological intent, signal availability, and signal quality.\n\n### IntentRange\n```typescript\ntype IntentRange = {\n  min: number\n  max: number | null  // null for open-ended ranges\n}\n\ntype IntentRanges = {\n  [key in PhysiologicalIntent]: {\n    hr: IntentRange | null\n    power: IntentRange | null\n    gap: IntentRange | null\n  }\n}\n```\nComputed on-the-fly from the athlete's current PhysiologyThresholds. Not stored as a separate entity. Architecture owns \"intent \u2192 physiological region\"; exact multiplier constants belong in implementation.\n\n**Vision \u2194 Architecture note:** Range width is driven by `PhysiologyParameterState.uncertainty`. As prior observations age (42-day decay in `bayesianUpdate()`), uncertainty increases and ranges widen. This implements the vision principle that \"calibration confidence degradation\" produces \"wider target ranges\" without silently expiring evidence. See `docs/vision/twin/training-zones.md` \u2192 Calibration Confidence Degradation.\n\n### ComplianceFamily\n```typescript\ntype ComplianceFamily =\n  | 'aerobic'        // recovery, low_aerobic, high_aerobic, threshold, vo2max\n  | 'neuromuscular'  // neuromuscular only\n```\nPhysiological intents belong to compliance families. Compliance is assessed within families only. Neuromuscular is orthogonal to the aerobic intensity ladder.\n\n### ComplianceResult\n```typescript\ntype ComplianceResult = {\n  step_id: string\n  prescribed_intent: PhysiologicalIntent\n  actual_intent: PhysiologicalIntent\n  compliance: 'compliant' | 'under' | 'over' | 'mismatch'\n  deviation: number\n  family: ComplianceFamily\n  session_purpose: SessionPurpose\n  purpose_interpretation: string\n}\n```\nStep-level compliance result. Prescribed vs actual intent, assessed within compliance families.\n\n### WorkoutComplianceSummary\n```typescript\ntype WorkoutComplianceSummary = {\n  workout_id: string\n  step_results: ComplianceResult[]\n  overall_compliance: 'compliant' | 'under' | 'over' | 'mixed'\n  intent_distribution: Record<PhysiologicalIntent, number>\n  purpose: SessionPurpose\n  summary: string  // plain English; narrated by agent\n}\n```\nSession-level compliance aggregation. Combines step-level results into an overall workout assessment.\n\n### PhaseDefinition (Three-Layer Model \u2014 Adaptation Strategy Layer)\n\nThe core structure that defines how a training plan progresses through phases. Replaces the former `PhaseArcEntry` as the plan-level adaptation strategy. The hypothesis agent generates 4\u20135 of these per hypothesis; a deterministic expansion function converts them to weekly distributions.\n\n```typescript\ntype PhaseDefinition = {\n  phase: PhaseLabel                    // expanded enum \u2014 methodology-specific label\n  objective: ObjectiveCategory[]       // shared with athlete objectives (same enum)\n  weeks: number\n  distribution: {\n    low_aerobic: number                // percentage of session time (0\u20131)\n    high_aerobic: number\n    threshold: number\n    vo2max: number\n    neuromuscular: number\n  }\n  specificity: number                  // independent attribute (0.0\u20131.0); see below\n  approach: 'linear' | 'undulating' | 'block' | 'step'\n  recovery_cycle: 'frequent' | 'moderate' | 'infrequent'\n}\n```\n\n**Specificity as a separate attribute:** Specificity is a property of the stimulus, not a training zone. A marathon-pace threshold session and a generic threshold session are both threshold work but have different specificity values. It overlaps with every load type and must not be included in `distribution`.\n\n| Session | Load Type | Specificity |\n|---|---|---|\n| Easy run | low_aerobic | 0.1 |\n| Marathon pace long run | high_aerobic | 0.9 |\n| Generic threshold intervals | threshold | 0.3 |\n| Race-pace threshold | threshold | 0.9 |\n| Hill sprints | neuromuscular | 0.2 |\n\n**Approach and recovery_cycle** operate at the within-phase timescale, not the weekly timescale. They control how sessions are arranged across weeks within the phase (ascending, undulating, clustered) and how recovery windows are spaced.\n\n**ObjectiveCategory values (shared with athlete objectives):**\n```typescript\ntype ObjectiveCategory =\n  | 'aerobic_base'\n  | 'threshold_quality'\n  | 'pacing_discipline'\n  | 'intensity_distribution'\n  | 'structural_tolerance'\n  | 'neuromuscular_sharpness'\n  | 'durability'\n  | 'intensity_compliance'\n  | 'recovery_efficiency'\n```\n\n**Distribution invariant:** `distribution` values across all five zones must sum to \u2264 1.0 per phase. The remaining budget is implicitly unallocated time (warmup, cooldown, transitions).\n\n### Weekly Distribution (Deterministic Expansion Output)\n\nPer-week distribution derived from phase definitions by the deterministic expansion layer. The weekly synthesis agent and pre-week review consume this, not the phase definitions directly.\n\n```typescript\ntype WeeklyDistribution = {\n  week_number: number\n  distribution: {\n    low_aerobic: number\n    high_aerobic: number\n    threshold: number\n    vo2max: number\n    neuromuscular: number\n  }\n  specificity: number\n  objective: ObjectiveCategory[]\n  is_recovery_week: boolean            // derived from recovery_cycle\n}\n```\n\n### Weekly Synthesis Types\n\n```typescript\ntype TargetDistribution = {\n  low_aerobic: number\n  high_aerobic: number\n  threshold: number\n  vo2max: number\n  neuromuscular: number\n}\n\ntype AdjustedWeeklyIntent = {\n  phase_label: PhaseLabel\n  methodology: MethodologyTraitVector\n  physiological_emphasis: string\n  target_distribution: TargetDistribution  // replaces intensity_bias enum\n  target_specificity: number           // from weekly distribution\n  objective: ObjectiveCategory[]       // from phase definition\n  session_count: number                // computed by PreWeekReviewService\n  adjustment_made: boolean\n  adjustment_reason: string | null\n  adjustment_source: 'plan_unchanged' | 'fatigue_correction' | 'schedule_constraint' | 'adaptation_acceleration' | 'checkpoint_result'\n  distribution_adjusted: boolean       // did pre-week review modify the distribution?\n  distribution_adjustment_reason: string | null\n  max_sessions: number | null\n  session_types_preferred: SessionType[] | null\n  avoid_session_types: SessionType[] | null\n}\n```\n\n**Backward compatibility:** The former `intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'` enum is replaced by `target_distribution`. The weekly synthesis agent reads the continuous distribution instead of mapping an enum to session type ratios. The `intensity_bias` values can be derived from the distribution if needed for backward-compatible consumers: `easy` \u2194 `low_aerobic \u2265 0.70`, `balanced` \u2194 `low_aerobic 0.60\u20130.70`, `moderate` \u2194 `low_aerobic 0.50\u20130.60`, `quality` \u2194 `low_aerobic < 0.50`.\n\n### Strategic Framework (Hypothesis Selector Output)\n\n```typescript\ntype StrategicFramework = {\n  strategic_rationale: {\n    primary_driver: string\n    methodology_summary: string\n    risk_notes: string[]\n  }\n  \n  macrocycle_structure: string         // plain English description\n  \n  // Phase definitions \u2014 the adaptation strategy\n  phase_definitions: PhaseDefinition[]\n  \n  // Derived: weekly distributions (computed by deterministic expansion)\n  weekly_distributions: WeeklyDistribution[]\n  \n  race_schedule: RaceScheduleEntry[]\n  checkpoint_schedule: CheckpointDescriptor[]\n  phase_adjustments: PhaseAdjustment[]\n  \n  progression_model: {\n    volume: string\n    intensity: string\n  }\n  \n  recovery_model: {\n    type: string\n    structure: string\n    race_recovery: Record<string, string>\n  }\n  \n  risk_mitigations: string[]\n}\n```\n\n**Note:** `StrategicRationale.intensity_distribution` (the former static plan-wide distribution) is removed. Per-phase distributions on `PhaseDefinition[]` replace it. The rationale still explains the methodology choice and risk mitigation in plain English.\n\n### Deterministic Expansion\n\nConverts phase definitions to weekly distributions. This is a pure function \u2014 same input always produces same output.\n\n```typescript\nfunction expandPhasesToWeekly(phases: PhaseDefinition[]): WeeklyDistribution[] {\n  const weekly: WeeklyDistribution[] = []\n  let weekOffset = 0\n  \n  for (const phase of phases) {\n    const phaseWeeks = expandSinglePhase(phase, weekOffset)\n    weekly.push(...phaseWeeks)\n    weekOffset += phase.weeks\n  }\n  \n  return weekly\n}\n\nfunction expandSinglePhase(phase: PhaseDefinition, startOffset: number): WeeklyDistribution[] {\n  const weeks: WeeklyDistribution[] = []\n  \n  for (let i = 0; i < phase.weeks; i++) {\n    const weekNum = startOffset + i + 1\n    const isRecovery = isRecoveryWeek(i, phase.weeks, phase.recovery_cycle)\n    \n    weeks.push({\n      week_number: weekNum,\n      distribution: applyApproach(phase.distribution, i, phase.weeks, phase.approach, isRecovery),\n      specificity: phase.specificity,\n      objective: phase.objective,\n      is_recovery_week: isRecovery,\n    })\n  }\n  \n  return weeks\n}\n\n// approach \u2192 how distribution shifts across weeks within phase\n// recovery_cycle \u2192 which weeks are recovery weeks\n// is_recovery \u2192 shifts distribution toward easy, reduces quality proportion\n```\n\n### Weekly Plan Types\n\n```typescript\ntype WeeklyPlanStatus = 'synthesised' | 'active' | 'completed'\n\ntype PriorWeekSummary = {\n  week_number: number\n  phase_label: PhaseLabel\n  planned_sessions: number\n  completed_sessions: number\n  missed_sessions: number\n  skipped_sessions: number\n  accumulated_fatigue_delta: number\n  average_recovery_modifier: RecoveryModifierLevel\n  adaptation_block_completed: boolean\n  checkpoint_completed: boolean\n  checkpoint_result?: {\n    metric_updated: boolean\n    confidence_changed: boolean\n  }\n  session_type_distribution: Record<SessionType, number>\n  actual_distribution?: {              // NEW \u2014 observed distribution for trajectory comparison\n    low_aerobic: number\n    high_aerobic: number\n    threshold: number\n    vo2max: number\n    neuromuscular: number\n  }\n  actual_specificity?: number          // NEW \u2014 observed specificity\n}\n```"
  }
}
```

**Tool: pheidipp-codebase-context_get_entity_context**

**Input:**
```json
{
  "entity_name": "data-tiers",
  "sections": [
    "Purpose",
    "Data Tiers",
    "Tier Inference"
  ]
}
```

**Output:**
```
{
  "entity": "data-tiers",
  "graph": {
    "related_entities": [],
    "produces_events": [],
    "consumes_events": [],
    "used_by_agents": [],
    "invariants": [
      {
        "field": "calibration_eligible",
        "rule": "Tier 5 and 6 activities are never `calibration_eligible`",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "aerobic_load",
        "rule": "Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "A session without GPS (`has_gps = false`) defaults to Tier 6 for structural load purposes even if HR is present",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "wrist_optical",
        "rule": "Optical HR (`wrist_optical`) is adequate for zone-based load calculation. Its limitation versus chest strap is specifically the absence of RR intervals for threshold detection \u2014 not HR accuracy for sustained aerobic efforts",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "Threshold detection capability is determined by data tier (see Tier Definitions table). Tiers 1\u20134 provide different levels of threshold detection; Tiers 5\u20136 provide none.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "Easy runs are calibration-eligible for load computation but do NOT provide threshold detection evidence (insufficient intensity variation for HR deflection/RR inflection algorithms)",
        "type": "behavioral",
        "enforcement": "application"
      }
    ],
    "api_endpoints": [],
    "storage_models": []
  },
  "sections": {
    "Purpose": "- Defines the six data tiers that determine what signals are available for computation\n- Establishes which tiers enable which analytical capabilities"
  }
}
```

**Tool: pheidipp-codebase-context_get_vision_context**

**Input:**
```json
{
  "entity_name": "cold-start",
  "sections": [
    "Purpose",
    "Tier 3 Cold Start",
    "Rules"
  ]
}
```

**Output:**
```
{
  "entity": "cold-start",
  "metadata": {
    "category": "twin",
    "file_path": "/home/ruimendes/projects/pheidipp/backend/docs/vision/twin/cold-start.md"
  },
  "sections": {}
}
```

**Tool: pheidipp-codebase-context_get_vision_context**

**Input:**
```json
{
  "entity_name": "constraints",
  "sections": [
    "Purpose",
    "Running-Only",
    "No Raw Data Surfaces",
    "Rules"
  ]
}
```

**Output:**
```
{
  "entity": "constraints",
  "metadata": {
    "category": "product",
    "file_path": "/home/ruimendes/projects/pheidipp/backend/docs/vision/product/constraints.md"
  },
  "sections": {
    "No Raw Data Surfaces": "Pheidipp does not display raw workout charts \u2014 HR over time, pace over time, power curves, cadence graphs. Athletes already have Garmin Connect, Strava, and intervals.icu for this, and those platforms do it well. Duplicating them inside Pheidipp would produce an inferior version of something the athlete already has and would pull the product toward the dashboard experience it is deliberately designed to avoid.\n\nEvery visualisation in Pheidipp must pass a single test: does this require the twin's context to produce? If it could be shown by Garmin or Strava, it does not belong here."
  }
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 17.3s)

_Thinking:_


Vision cold-start sections wrong names. Need list vision entities maybe get all? Use get_vision_context no sections for cold-start.


**Tool: pheidipp-codebase-context_get_vision_context**

**Input:**
```json
{
  "entity_name": "cold-start"
}
```

**Output:**
```
{
  "entity": "cold-start",
  "metadata": {
    "category": "twin",
    "file_path": "/home/ruimendes/projects/pheidipp/backend/docs/vision/twin/cold-start.md"
  },
  "sections": {
    "Three Confidence Tiers": "The twin starts from one of three tiers depending on what data is available at onboarding. The system is always honest about which tier it is operating from, and all downstream decisions \u2014 plan conservatism, target ranges, coaching certainty \u2014 are weighted accordingly.\n\n**Tier 1 \u2014 Imported training history.** The athlete connects an existing training platform and the system ingests real historical workout data. The twin is built from actual physiology, not assumptions. This is the richest starting point and produces the most personalised initial coaching. Athletes in this tier can also supplement with lab/test uploads to provide additional threshold precision.\n\n> **Implementation:** Tier 1 athletes start at LOW confidence but transition quickly (1\u20133 sessions to MEDIUM). See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for evidence weight thresholds and transition conditions.\n\n**Tier 2 \u2014 Peer-similar athletes OR Lab/Test Uploads.** For athletes with no importable history, the twin bootstraps either from anonymised models of similar athletes OR from athlete-provided physiological benchmarks. Lab/test uploads provide higher threshold confidence than peer-based inference, but execution patterns and adaptation signatures still require real training data to develop.\n\n> **Implementation:** Lab tests provide immediate high-weight evidence (12\u201315 units), often jumping tested metrics directly to MEDIUM. Peer-similar bootstrapping starts at LOW with faster transition than Tier 3. See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for threshold details.\n\nConfidence transitions are quality-weighted. Each physiological parameter accumulates evidence independently based on observation quality. A single lab test carries more evidence than multiple easy sessions with optical HR. The system weighs observation quality when determining when to upgrade confidence levels \u2014 it is the quality of the data, not just the quantity, that drives confidence forward. For LT1 specifically, the system builds confidence passively from natural training patterns \u2014 analyzing HR response in easy runs, drift during long efforts, and recovery after stopping \u2014 without requiring special test sessions.\n\n**Tier 3 \u2014 Questionnaire inputs only.** The most conservative baseline, built from onboarding responses alone. Initial targets are expressed as ranges or effort descriptions rather than precise numbers. The twin becomes more confident and specific as real training data accumulates over the following weeks.\n\n> **Implementation:** Initial confidence is LOW. This tier requires the most real training data to accumulate evidence (6\u201310 sessions to MEDIUM). See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for transition conditions and velocity estimates.",
    "What Honest Confidence Looks Like": "A Tier 3 athlete does not receive aggressive targets on day one. The coach language reflects genuine uncertainty: \"based on what you've described,\" \"let's see how this feels,\" \"we'll calibrate as we see your actual data.\" This is not a degraded experience \u2014 it is accurate coaching at the information level available.\n\nAs sessions accumulate and the twin observes real execution, threshold estimates, recovery patterns, and fatigue responses, confidence upgrades and the coaching becomes correspondingly more precise. The athlete earns specificity from the model by training with it.",
    "Onboarding Time to Value": "The model build takes a few minutes \u2014 not instant, not an hour. This communicates that something real is being computed, not a template being applied. While the model builds, the athlete explores the app and sets their goal race or objectives. When the model is ready, the first coach message appears."
  }
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 20.6s)

_Thinking:_


Need constraints maybe all.


**Tool: pheidipp-codebase-context_get_vision_context**

**Input:**
```json
{
  "entity_name": "constraints"
}
```

**Output:**
```
{
  "entity": "constraints",
  "metadata": {
    "category": "product",
    "file_path": "/home/ruimendes/projects/pheidipp/backend/docs/vision/product/constraints.md"
  },
  "sections": {
    "Running-Only Twin Model": "The Digital Twin is built for running and only running. This is an accuracy decision, not a limitation. Multi-sport platforms attempt to normalise load across activities using conversion factors \u2014 a swim session translated into equivalent running stress, a strength session assigned an arbitrary score. These conversions introduce errors that compound over time, gradually corrupting the model's understanding of actual running fitness and fatigue.\n\nPheidipp makes no such conversions. All twin calibration \u2014 load computation, threshold tracking, execution pattern analysis, adaptation signature \u2014 uses exclusively running data where physiological signals are clean and comparable across sessions.\n\nThe coach can and does prescribe non-running work when it serves the athlete's running goals: aqua jogging during injury, strength and conditioning, yoga and mobility sessions. These appear in the training record and the coach references them where relevant. But they are excluded from twin learning entirely. The twin holds its judgement on those sessions and waits for the next run to tell it what it needs to know.",
    "No Workout Builder": "Athletes cannot create, edit, or customise workouts. The coach owns all workout design. This is intentional, not missing functionality.\n\nThe athlete's agency over any given session is limited to three choices: accept the planned workout, substitute from coach-suggested alternatives, or skip. Skipped sessions are absorbed by the weekly coaching rhythm \u2014 the next week's planning accounts for the disruption without breaking the overall plan. This boundary prevents complexity spiral, maintains coaching quality control, and keeps the product honest about what it is \u2014 a coaching system, not a training tool.",
    "No Raw Data Surfaces": "Pheidipp does not display raw workout charts \u2014 HR over time, pace over time, power curves, cadence graphs. Athletes already have Garmin Connect, Strava, and intervals.icu for this, and those platforms do it well. Duplicating them inside Pheidipp would produce an inferior version of something the athlete already has and would pull the product toward the dashboard experience it is deliberately designed to avoid.\n\nEvery visualisation in Pheidipp must pass a single test: does this require the twin's context to produce? If it could be shown by Garmin or Strava, it does not belong here.",
    "Unsynced Workout Handling": "When data gaps occur \u2014 watch not synced, battery died, session not completed \u2014 the system asks before assuming. The coach surfaces a simple check-in rather than silently making assumptions that could corrupt the twin model.\n\nIf yes (completed): athlete is prompted to sync or upload. Plan holds while pending. If no (not completed): treated as a skip with rescheduling options.\nIf no response: system holds judgement and asks again at next app open.\n\nThis ambiguity-first approach protects model accuracy over convenience.\n\n---",
    "Same-Day Training Sessions": "Advanced athletes sometimes train twice a day \u2014 an easy morning run plus an evening intensity session, or a double threshold day. The system supports this through AM/PM session slots with primary and secondary designation.\n\nThe primary session receives full workout generation with precise targets. The secondary session may be a suggested non-running session (strength, yoga, mobility) without detailed targets. Recovery time is measured from primary session to primary session, not session to session, reflecting the physiological reality that a morning easy run plus an evening threshold session provides more recovery than two hard sessions on consecutive days.\n\nThe weekly plan accounts for total athlete availability, including doubles capacity, when defining macro load. This ensures the training load reflects what the athlete actually trains, not just session count."
  }
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 12.7s)

_Thinking:_


Need verify invariants for systems touched. Use search_invariants. Need maybe uniqueness, behavioral, range. We know. Use multi_search? The instructions say call search_invariants for systems touched. Use maybe three searches. Could use multi_tool? It only developer tools. But search_invariants has filters. We can call multiple in parallel. Need maybe exact invariants.


**Tool: pheidipp-codebase-context_search_invariants**

**Input:**
```json
{
  "enforcement": "database",
  "invariant_type": "uniqueness",
  "query": "AthleteProfile AthletePreferences unique constraint athlete_id one per athlete"
}
```

**Output:**
```
[
  {
    "entity": "athlete-wellness",
    "field": null,
    "rule": "Unique constraint on `(athlete_id, date)`. One record per day per athlete. **Upsert semantics:** a second ingestion for the same `(athlete_id, date)` updates non-null fields but does not overwrite existing non-null values with null. Different wearables may contribute different fields on the same day \u2014 the record is additive.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "athlete-preferences",
    "field": "AthletePreferences",
    "rule": "One `AthletePreferences` per `Athlete`. Created during onboarding. Enforced by unique constraint on `(athlete_id)`.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "athlete",
    "field": "email",
    "rule": "`email` is unique across all athletes. Case-insensitive uniqueness enforced at DB level via unique index on `lower(email)`.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "weather-forecast",
    "field": null,
    "rule": "Unique constraint on `(athlete_id, forecast_date)`. Upsert on conflict \u2014 a later fetch for the same date updates the record with a fresher forecast.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "training-goal",
    "field": "abandoned",
    "rule": "Enforced by a partial unique index on `(athlete_id) WHERE status = 'active'`. Attempting to create a second active goal returns `409 Conflict`. The existing goal must be explicitly closed (`status \u2192 completed` or `abandoned`) before a new one is created.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "workout-step",
    "field": "step_order",
    "rule": "`step_order` is unique within a `generated_workout_id`. Enforced by unique constraint on `(generated_workout_id, step_order)`.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "cycle-phase-log",
    "field": null,
    "rule": "No unique constraint on `(athlete_id, cycle_day_one_date)` \u2014 an athlete can correct a mis-entry by logging a new date. The most recent log is always the active one.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "athlete-profile",
    "field": "AthleteProfile",
    "rule": "One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "athlete-wellness-baseline",
    "field": "AthleteWellness",
    "rule": "Unique constraint on `(athlete_id, signal)` \u2014 one row per signal per athlete. Recomputed values **overwrite** the existing row (unlike `AthleteWellness` which is additive). The baseline is always a fresh window computation, not cumulative.",
    "type": "uniqueness",
    "enforcement": "database"
  },
  {
    "entity": "athlete-integration",
    "field": null,
    "rule": "Unique constraint on `(athlete_id, platform)`. One integration record per platform per athlete.",
    "type": "uniqueness",
    "enforcement": "database"
  }
]
```

**Tool: pheidipp-codebase-context_search_invariants**

**Input:**
```json
{
  "enforcement": "application",
  "invariant_type": "behavioral",
  "query": "Activity fit_file_key manual_entry load scores calibration_eligible no avg fields"
}
```

**Output:**
```
[
  {
    "entity": "confidence-model",
    "field": null,
    "rule": "Confidence is **per-metric**: each physiological parameter accumulates evidence independently. A field test for LT2 increases LT2 confidence, not LT1 confidence.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "event-catalogue",
    "field": null,
    "rule": "Failed event processing is retried; events are not consumed destructively",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "principles",
    "field": "Activity",
    "rule": "1. **Activities are physiological observations, not workout summaries.** `Activity` stores what the twin model needs. It never stores avg_hr, avg_pace, avg_power, or lap dumps. The FIT file is the source of truth.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "principles",
    "field": null,
    "rule": "2. **The twin computes metrics deterministically in Python. The LLM reasons about structure and instantiates plans from pre-computed metrics. Python validates structural invariants.** All analytical computation \u2014 fitness scoring, threshold estimation, execution classification, load accumulation, wellness trend analysis \u2014 lives in Python services. LLM agents receive pre-computed metrics and twin state summary, then reason about plan structure (strategic hypotheses, week-by-week session placement) and generate narrative. Python validates all structural invariants during plan generation and session lifecycle.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "principles",
    "field": "fit_file_key",
    "rule": "3. **`fit_file_key` is a hard prerequisite.** No `Activity` record commits without its raw file stored in object storage. This is the reprocessing anchor. If object storage fails, the task retries. No exceptions.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "principles",
    "field": "ingestion_pipeline_version",
    "rule": "5. **Every analytical output is versioned.** `ingestion_pipeline_version`, `cleaning_pipeline_version`, `segmentation_version`, `analysis_version`, `model_version`. A version string is a frozen, reproducible pipeline snapshot \u2014 not a mutable label.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "principles",
    "field": "Activity",
    "rule": "6. **No global session averages are persisted.** Average HR, pace, power \u2014 none of these are on `Activity`. Ever.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "principles",
    "field": null,
    "rule": "8. **Non-running activities are excluded from twin calibration.** They appear in the training record. They never feed load computation, threshold detection, execution analysis, or adaptation modelling. *(Implements vision principle \"Non-Running Data Does Not Corrupt the Running Model\" from `docs/vision/twin/data-philosophy.md`.)*",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "principles",
    "field": null,
    "rule": "9. **Raw pace is never used.** Grade-adjusted pace (GAP) is the standard input throughout. See `02-computations/effort-normalisation.md`. *(Implements vision principle \"Real Signals, Not Assumptions\" from `docs/vision/twin/data-philosophy.md`.)*",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "data-tiers",
    "field": "calibration_eligible",
    "rule": "Tier 5 and 6 activities are never `calibration_eligible`",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "data-tiers",
    "field": "aerobic_load",
    "rule": "Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "data-tiers",
    "field": null,
    "rule": "A session without GPS (`has_gps = false`) defaults to Tier 6 for structural load purposes even if HR is present",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "data-tiers",
    "field": "wrist_optical",
    "rule": "Optical HR (`wrist_optical`) is adequate for zone-based load calculation. Its limitation versus chest strap is specifically the absence of RR intervals for threshold detection \u2014 not HR accuracy for sustained aerobic efforts",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "data-tiers",
    "field": null,
    "rule": "Threshold detection capability is determined by data tier (see Tier Definitions table). Tiers 1\u20134 provide different levels of threshold detection; Tiers 5\u20136 provide none.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "data-tiers",
    "field": null,
    "rule": "Easy runs are calibration-eligible for load computation but do NOT provide threshold detection evidence (insufficient intensity variation for HR deflection/RR inflection algorithms)",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "comparable-sessions",
    "field": null,
    "rule": "The current activity is never selected as its own comparable (filtered by `a.id !== current_activity.id`).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "checkpoint",
    "field": "training_plan_id",
    "rule": "**One checkpoint per PlannedSession.** A PlannedSession may be flagged as a checkpoint, but a checkpoint cannot exist without a corresponding PlannedSession. The `training_plan_id` is derived from the PlannedSession's FK \u2014 no redundant FK on Checkpoint.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "checkpoint",
    "field": "metric_updated",
    "rule": "**Completion fields set atomically.** `metric_updated`, `confidence_changed`, `replan_triggered`, and `completed_at` are set together when status transitions to completed.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "checkpoint",
    "field": null,
    "rule": "**Checkpoint cannot be created retroactively.** Checkpoints are scheduled during plan synthesis, not after session completion.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "checkpoint",
    "field": "AdaptationSignature",
    "rule": "**Overshoot recovery uses static default until individual data is available.** The `+2 day` default applies unless `TwinState.confidence_level = 'high'` AND `AdaptationSignature` has \u2265 3 complete adaptation window observations. This prevents premature personalization from noisy data.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "generation-event",
    "field": "CoachingMessage",
    "rule": "**Every LLM call writes a GenerationEvent, whether successful or not.** A `CoachingMessage` created without a corresponding `GenerationEvent` indicates an instrumentation failure.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-wellness",
    "field": null,
    "rule": "No field is required to be non-null. Partial records (only some signals present) are valid and normal.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-preferences",
    "field": "sport_background",
    "rule": "`sport_background` not `running_primary` activates the crossover athlete structural capacity ramp in plan generation. See `02-computations/plan-generation.md` (shared types) and `02-computations/plan-generation-race.md` (race mode ramp).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-preferences",
    "field": "hr_source",
    "rule": "Changes to `hr_source` or `power_source` affect the data tier of the next ingested Activity but do not retroactively alter historical Activities.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete",
    "field": "AthleteAuth",
    "rule": "Authentication credentials are stored in `AthleteAuth`, not in `Athlete`. See `01-entities/athlete-auth.md`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "objective",
    "field": "training_goal_id",
    "rule": "Objectives are scoped to a `training_goal_id`. When a goal closes, objectives for that goal are not carried to the new goal \u2014 new objectives are seeded.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "training-goal",
    "field": null,
    "rule": "The following fields are **immutable** after creation to preserve the historical integrity of the goal context:",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "training-goal",
    "field": null,
    "rule": "**Rationale:** Changing these fields fundamentally alters the nature of the goal. If an athlete's intent changes (e.g., from \"marathon\" to \"10k\", or from \"race_event\" to \"fitness_improvement\"), they should close the current goal and create a new one. This preserves the audit trail of what the original plan was optimizing for.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "training-goal",
    "field": null,
    "rule": "Only the following fields can be updated via `PATCH /goals/{id}`:",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "training-goal",
    "field": "goal_description",
    "rule": "  `goal_description` (minor textual refinements)",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "twin-state",
    "field": "UPDATE",
    "rule": "No `UPDATE` or `DELETE` at any layer. `TwinStateRepository` exposes only `insert`, `get_latest`, `get_by_activity`, and `get_history`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "twin-state",
    "field": "activity_id",
    "rule": "`activity_id` is frozen \u2014 it links the snapshot to the specific triggering event (if applicable).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "activity",
    "field": "fit_file_key",
    "rule": "`fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "activity",
    "field": "avg_hr",
    "rule": "`avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` \u2014 these fields do not exist on `Activity`. They are never added.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "activity",
    "field": "aerobic_load",
    "rule": "`aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "activity",
    "field": "calibration_eligible",
    "rule": "`calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "activity",
    "field": "manual_entry",
    "rule": "Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "workout-step",
    "field": "description",
    "rule": "Numeric targets are null for Tier 5-6 athletes. `description` is always non-null and always carries the intent in plain language.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "raw-sensor-stream",
    "field": "RawSensorStream",
    "rule": "One `RawSensorStream` per `Activity`. Created atomically with the cleaned stream upload.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "raw-sensor-stream",
    "field": "RawSensorStream",
    "rule": "If cleaning fails (stream too short, all HR artifacts), no `RawSensorStream` is created. The Activity exists with null `cleaning_pipeline_version`. Segmentation is skipped for this activity.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "raw-sensor-stream",
    "field": "fit_file_key",
    "rule": "The `fit_file_key` on `RawSensorStream` is the cleaned stream key \u2014 different from `Activity.fit_file_key` (raw FIT). The naming is intentional: both entities use the same field name pointing to different keys.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "raw-sensor-stream",
    "field": "available_channels",
    "rule": "`available_channels` reflects what survived artifact removal \u2014 an activity that had HR but all values were flagged as artifacts will have `hr: false`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "workout-library-entry",
    "field": "EmbeddedStep",
    "rule": "`EmbeddedStep` uses the same field structure as `WorkoutStep` but is stored as JSONB within the entry, not as a FK-linked table. Library entries are templates, not parent-linked records.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "workout-library-entry",
    "field": null,
    "rule": "No athlete contributes to the library. `created_by = 'athlete'` does not exist.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-auth",
    "field": "AthleteAuth",
    "rule": "One `AthleteAuth` record per `(athlete_id, provider)`. An athlete cannot link the same provider twice.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-auth",
    "field": "ip_address",
    "rule": "`ip_address` in `RefreshToken` records is stored for audit only; if used for security analysis, it must be anonymized or hashed before logging.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-auth",
    "field": null,
    "rule": "Refresh tokens expire 30 days after issuance (`expires_at = created_at + 30 days`). Expired tokens are rejected even if not revoked.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": "activity_id",
    "rule": "**`activity_id` is set only when `status = 'completed'`.**",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": "redistributed_to_date",
    "rule": "**`redistributed_to_date` is set only when `status = 'redistributed'`.** A new `PlannedSession` is created for the target date when redistribution occurs \u2014 the original is not moved.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": null,
    "rule": "**Recovery time is measured from primary to primary.** Secondary sessions do not reset the recovery clock.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": null,
    "rule": "**Block members must all be quality sessions.** Rest, recovery_run, and easy sessions do not contribute to compound stimulus.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": null,
    "rule": "**Block cannot span more than 3 sessions.** Limits compound stimulus duration to prevent excessive fatigue accumulation and maintain observation window clarity.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": null,
    "rule": "**Block is optional.** Not all quality sessions need to be grouped; isolated quality sessions with full recovery are valid training structures.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": null,
    "rule": "**Key Principle:** Layer 2 block rules are derived from training physiology. Layer 4 observes what Layer 2 structures. If Layer 4's detection algorithm changes, Layer 2 rules do not change \u2014 Layer 4 adapts its observation window definition.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": "threshold",
    "rule": "No two quality sessions (`threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`, `long_run`) on consecutive dates **unless they share a `block_id`**. Blocks must include recovery after the final session.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "generated-workout",
    "field": "theoretical_targets",
    "rule": "`theoretical_targets` and `adjusted_targets` are always both written, even when identical (GREEN modifier with no weather).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "generated-workout",
    "field": "twin_state_id",
    "rule": "`twin_state_id` records which twin version drove target generation. If the twin is recalibrated after a workout is generated, the generated workout is not retroactively updated.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "generated-workout",
    "field": null,
    "rule": "**Idempotency over Freshness (Deliberate Tradeoff)** \u2014 Generation is idempotent for `(planned_session_id, date)`. If the twin recalibrates after workout generation, the generated workout is **not retroactively updated**. The athlete receives a workout based on the twin state at generation time.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "generated-workout",
    "field": null,
    "rule": "**Rationale:** Stability \u2014 the athlete sees a consistent plan for the day. Regeneration is triggered explicitly (confidence upgrade, checkpoint completion, coach action), not on every twin update.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "execution-observation",
    "field": "ExecutionObservation",
    "rule": "One `ExecutionObservation` per `Activity`. One-to-one.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "execution-observation",
    "field": "GeneratedWorkout",
    "rule": "Only created for `calibration_eligible = true` activities with a linked `GeneratedWorkout` (the prescribed intent must be known for compliance assessment). Activities without `planned_session_id` or without `calibration_eligible = true` receive a simplified analysis with null `per_rep_analysis` and `effort_compliance`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "cycle-phase-log",
    "field": null,
    "rule": "No DELETE. Logs accumulate as the training history of the coaching relationship.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "cycle-phase-log",
    "field": "unknown",
    "rule": "Phase computation returns `unknown` (not an error) when no log exists or the most recent log is stale (> 45 days). This is a valid, graceful state.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "cycle-phase-log",
    "field": "CyclePhaseLog",
    "rule": "**Mutability vs Immutability Tension:** `CyclePhaseLog` allows correction (new log with corrected `cycle_day_one_date` supersedes). `AdaptationObservation` is append-only and stores `cycle_phase` at observation time. If an athlete corrects their cycle day one date, all past `AdaptationObservation` records have incorrect `cycle_phase` values that **cannot be updated**.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "cycle-phase-log",
    "field": null,
    "rule": "1. `AdaptationObservation.cycle_phase` is a **point-in-time classification** based on the log active at observation time. It is not retroactively corrected.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "cycle-phase-log",
    "field": "cycle_phase",
    "rule": "3. For analysis requiring accurate historical phases: re-compute phase from the corrected log history at query time (not from stored `cycle_phase`).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "cycle-phase-log",
    "field": null,
    "rule": "**Audit trail:** `AdaptationObservation.cycle_phase_computation_basis` records whether phase was derived from default boundaries or personal model at observation time.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-profile",
    "field": "training_window",
    "rule": "`training_window` defaults to 06:00\u201320:00 if not set. Mutable via PATCH. Only used by WorkoutPrefetchTask for prefetch timing. MissedSessionSweepTask uses timezone only, not training_window.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-wellness-baseline",
    "field": "computed_to",
    "rule": "Baselines are always computed from the past 28 calendar days from `computed_to` date. The window does not slide mid-day.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "weekly-plan",
    "field": null,
    "rule": "**One WeeklyPlan per week per TrainingPlan.** Cannot create two plans for the same `(training_plan_id, week_number)`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "weekly-plan",
    "field": null,
    "rule": "**weekly_plan_created fires before the week starts.** The plan is synthesised in advance, not retroactively.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "weekly-plan",
    "field": "active",
    "rule": "**Sessions array is immutable once active.** No mid-week session additions after status transitions to `active`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "weekly-plan",
    "field": "planned_session_id",
    "rule": "**One WeeklySession per PlannedSession.** When a workout is generated for a session, the `planned_session_id` FK is set on the WeeklySession. This link is established lazily at workout generation time, not at WeeklyPlan creation. The WeeklyPlan is created with sessions; PlannedSession records are created later when the workout generation agent runs.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "weekly-plan",
    "field": "PlannedSession",
    "rule": "**PlannedSession.training_plan_id is denormalized and can be stale.** When a plan is superseded, `PlannedSession` records retain the old `training_plan_id`. The authoritative plan reference is always `WeeklyPlan.training_plan_id`. Queries for \"sessions in the current plan\" MUST join through `WeeklyPlan`, not filter `PlannedSession.training_plan_id` directly. *See `planned-session.md` schema for denormalization rationale and correct query pattern.*",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "physiological-segment",
    "field": null,
    "rule": "**`inferred_state = 'unknown'`** when `confidence < 0.45`. This is the correct output for ambiguous transitions \u2014 not a fallback or error state.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "physiological-segment",
    "field": "PlannedSegment",
    "rule": "**Unaligned segments** (no matching `PlannedSegment`) retain `planned_segment_id = null`. They are never discarded \u2014 they carry information about unplanned effort.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "physiological-segment",
    "field": "superseded_at",
    "rule": "**Superseded records** receive `superseded_at` when a higher-quality version is produced for the same activity. Old records are never deleted. Both old and new records coexist; consumers should use the most recent non-superseded record.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "physiological-segment",
    "field": "per_rep_analysis",
    "rule": "Segments with `confidence < 0.4` in `heuristic-v1` are not used in `per_rep_analysis` in `ExecutionObservation`. The coach makes no claims about unknown-state segments.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "adaptation-observation",
    "field": "AdaptationObservation",
    "rule": "`AdaptationObservation` is only created for athletes with \u2265 6 weeks of calibration-eligible sessions (earlier data lacks sufficient signal).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "adaptation-observation",
    "field": "yield_by_intent_state",
    "rule": "`yield_by_intent_state` only contains keys for states that appeared in the adaptation window's `PhysiologicalSegment` records. Missing keys mean no exposure to that state during the adaptation window.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "adaptation-observation",
    "field": "unit_type",
    "rule": "`unit_type` must match the pattern detected by `AdaptationBlockDetectionTask` \u2014 hard window requires 2+ quality sessions, isolated requires exactly 1 quality session flanked by easy days, recovery is not an observation trigger for stimulus measurement.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "adaptation-observation",
    "field": "fatigue_depth",
    "rule": "`fatigue_depth` must be null for `unit_type = 'recovery'` observations (no stimulus to measure fatigue against).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "adaptation-observation",
    "field": "execution_quality_delta",
    "rule": "`execution_quality_delta` must be null if no quality session occurred after the recovery window.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "training-plan",
    "field": "phase_definitions",
    "rule": "**`phase_definitions` contains the adaptation strategy.** No session-level detail. Session schedules live on `WeeklyPlan` records. Each phase definition provides the methodology, distribution, specificity, approach, recovery cycle, and objectives for the phase; the deterministic expansion converts these to weekly distributions; the weekly synthesis agent produces the actual sessions from those distributions.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "training-plan",
    "field": "strategic_rationale",
    "rule": "**`strategic_rationale` is set only for `race_event` and `target_performance` mode plans.** Contains the coach's rationale. Internal hypothesis exploration names are not persisted. For `fitness_improvement`, `maintenance`, and `recovery` modes, it is null. The former `intensity_distribution` field on `StrategicRationale` is removed \u2014 per-phase distributions on `phase_definitions` replace it.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-fitness",
    "field": "form",
    "rule": "Negative `form` is valid and normal. It indicates the athlete is in a training load phase. An athlete with `form = -20` is heavily loaded but not necessarily overreached.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "regeneration-task",
    "field": null,
    "rule": "note right of confirmed : Triggers plan regeneration\\nnew_training_plan_id set",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "regeneration-task",
    "field": "confirmed",
    "rule": "  **No reverts:** Once `confirmed`, `declined`, or `expired`, the task cannot return to `pending_confirmation`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "regeneration-task",
    "field": "pending_confirmation",
    "rule": "  **No skipping:** Cannot transition directly from `pending_confirmation` to `expired` without time elapsed (enforced by service logic).",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-physiology",
    "field": "dominant_source",
    "rule": "`dominant_source` on each parameter reflects the source that currently dominates the posterior. For a recently lab-tested athlete this is `lab_test`; for a well-trained athlete with no lab data this is `training_rr_inflection`.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-physiology",
    "field": "prior_weight",
    "rule": "`prior_weight` decays over time via the formula above. After ~3 years with no new observations, the prior weight approaches zero \u2014 the system becomes appropriately uncertain and reverts toward more conservative coaching language.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-physiology",
    "field": "dominant_source",
    "rule": "**Audit Gap: `dominant_source` Transition History Not Captured** \u2014 `dominant_source` reflects the source currently dominating the posterior (e.g., `lab_test`, `training_rr_inflection`). When Bayesian updates shift the dominant source, the transition is **not recorded**. **Available for audit:** `PhysiologyMeasurement` (raw observations, append-only) and `TwinState` (inline snapshot of parameter states at each trigger). **Missing:** Which source dominated at each step, and why the weighting shifted. **Future enhancement:** When `dominant_source` changes, persist the transition (from \u2192 to \u2192 evidence_weight \u2192 trigger) as either a new field on `PhysiologyMeasurement` or a dedicated `dominant_source_transitions` table. Low priority \u2014 current snapshots in `TwinState` allow reconstruction with effort.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "athlete-integration",
    "field": null,
    "rule": "DELETE is supported \u2014 disconnecting removes credentials but leaves Activity records intact.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "weekly-synthesis-agent",
    "field": null,
    "rule": "**Output is validated against hard invariants** before persistence: no back-to-back quality, 48h recovery, available days, long run recovery.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "weekly-synthesis-agent",
    "field": null,
    "rule": "**Session count is pre-computed by PreWeekReviewService.** The weekly synthesis agent reads `AdjustedWeeklyIntent.session_count` and distributes sessions \u2014 it does not recompute.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "context-budget-service",
    "field": null,
    "rule": "Token estimation uses `JSON.stringify(obj).length / 4` \u2014 deterministic, no external dependencies",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "context-budget-service",
    "field": null,
    "rule": "**Priority-Weighted Truncation:** Each context section declares a priority weight (1\u2013100). Truncation removes lowest-weight sections first. Priority weights are agent-specific, not global.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "context-budget-service",
    "field": "AGENT_PRIORITY_PROFILES",
    "rule": "**Agent-Specific Profiles:** Each agent type has its own priority profile. Profiles are defined in `AGENT_PRIORITY_PROFILES` and configured per agent, not hardcoded in truncation logic.",
    "type": "behavioral",
    "enforcement": "application"
  },
  {
    "entity": "context-budget-service",
    "field": null,
    "rule": "No errors thrown \u2014 degraded context is always returned",
    "type": "behavioral",
    "enforcement": "application"
  }
]
```

**Tool: pheidipp-codebase-context_search_invariants**

**Input:**
```json
{
  "enforcement": "application",
  "invariant_type": "uniqueness",
  "query": "Activity deduplication athlete_id external_id source unique non-null external_id"
}
```

**Output:**
```
[
  {
    "entity": "twin-state",
    "field": "activity_sync",
    "rule": "Multiple TwinStates per day are possible (e.g., `activity_sync` followed by `wellness_update`), but only **one** TwinState per `activity_id`. See \"Concurrency & Coordination\" for deduplication logic.",
    "type": "uniqueness",
    "enforcement": "application"
  },
  {
    "entity": "activity",
    "field": "external_id",
    "rule": "Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.",
    "type": "uniqueness",
    "enforcement": "application"
  },
  {
    "entity": "planned-session",
    "field": "session_slot",
    "rule": "**Multiple PlannedSession records per day are allowed.** Uniqueness is enforced on `(weekly_plan_id, target_date, session_slot)` where `session_slot` distinguishes AM/PM sessions.",
    "type": "uniqueness",
    "enforcement": "application"
  },
  {
    "entity": "coaching-message",
    "field": "post_workout",
    "rule": "`post_workout` \u2014 only one per `activity_id`. Idempotent: second call returns existing message.",
    "type": "uniqueness",
    "enforcement": "application"
  }
]
```

**Tool: pheidipp-codebase-context_search_invariants**

**Input:**
```json
{
  "enforcement": "database",
  "invariant_type": "range",
  "query": "AthletePreferences years_structured_training CHECK constraint non-negative"
}
```

**Output:**
```
[
  {
    "entity": "athlete-preferences",
    "field": null,
    "rule": "`years_structured_training >= 0`. CHECK constraint at DB level.",
    "type": "range",
    "enforcement": "database"
  }
]
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 4.6s)

_Thinking:_


Need determine change impact? Sub-phase modifies existing entity athlete-profile (extends table) maybe existing. Need call get_change_impact for athlete-profile? Also activity/athlete-preferences are new? athlete-profile existing from phase 1.1. Need change impact for athlete-profile maybe. Use get_change_impact.


**Tool: pheidipp-codebase-context_get_change_impact**

**Input:**
```json
{
  "concept": "athlete-profile"
}
```

**Output:**
```
{
  "concept": "athlete-profile",
  "architecture": {
    "entity": "athlete-profile",
    "related_entities": [],
    "reverse_related_entities": [],
    "event_coupling": {
      "consumers_of_produced": [],
      "producers_of_consumed": []
    },
    "used_by_agents": [],
    "invariants": [
      {
        "field": "AthleteProfile",
        "rule": "One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.",
        "type": "uniqueness",
        "enforcement": "database"
      },
      {
        "field": "CyclePhaseLog",
        "rule": "`sex = 'female'` enables menstrual cycle tracking (`CyclePhaseLog`) and cycle modifier in wellness computation.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "gap_curve_model",
        "rule": "`gap_curve_model` is applied when `current_effort_generation >= 2`. Upgrade to Gen 2 requires `r_squared >= 0.70`; downgrade to Gen 1 requires `r_squared < 0.65`. See `02-computations/effort-normalisation.md` for the hysteresis state machine.",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": "weather_response_model",
        "rule": "`weather_response_model` is only applied when `r_squared >= 0.65`.",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": "banister_constants",
        "rule": "`banister_constants` stores per-athlete fitted time constants. When set, `AthleteFitness.time_constants` references these values (source='individual_fitted'). When null, `AthleteFitness.time_constants` uses population defaults (source='population_default').",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "`cycle_personal_model.phase_sensitivity` of `0.0` means the model detected no phase correlation \u2014 cycle modifier is effectively zeroed for this athlete. This is a valid outcome.",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": "cycle_personal_model",
        "rule": "`cycle_personal_model.luteal_temp_sensitivity` of `1.0` means the population default thermoregulatory offset applies. Values <1.0 indicate lower-than-average thermal sensitivity; >1.0 indicate higher. When `cycle_personal_model` is null, `LUTEAL_TEMP_OFFSET_C` (0.35) applies at full population weight.",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": "timezone",
        "rule": "`timezone` is required at onboarding (validated against IANA tz database). Immutable after creation \u2014 changing timezone requires a support process. All scheduled tasks (MissedSessionSweepTask, WorkoutPrefetchTask) and date interpretations use this timezone.",
        "type": "behavioral",
        "enforcement": "database"
      },
      {
        "field": "training_window",
        "rule": "`training_window` defaults to 06:00\u201320:00 if not set. Mutable via PATCH. Only used by WorkoutPrefetchTask for prefetch timing. MissedSessionSweepTask uses timezone only, not training_window.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "structural_risk_flag",
        "rule": "`structural_risk_flag` is computed at onboarding from `AthletePreferences.sport_background`. When `true`, the structural load density penalty coefficient is 0.08 (vs 0.12 population default). See `02-computations/load-computation.md`.",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": "objective_thresholds",
        "rule": "`objective_thresholds` stores per-athlete evaluation thresholds for objective management. When null, population defaults are used (0.03 for pacing discipline, 3 for encroachment events). See `02-computations/objective-management.md`.",
        "type": "range",
        "enforcement": "application"
      }
    ],
    "api_endpoints": [
      {
        "method": "GET",
        "path": "/athletes/{athlete_id}/profile",
        "auth": "Bearer JWT",
        "response_status": 200
      },
      {
        "method": "PATCH",
        "path": "/athletes/{athlete_id}/profile",
        "auth": "Bearer JWT",
        "response_status": 200
      }
    ],
    "storage_models": [
      {
        "table": "athlete_profiles` table",
        "strategy": "mutable (patch for user fields)",
        "consistency": "strong",
        "retention": "indefinite"
      },
      {
        "table": "gap_curve_model` JSONB",
        "strategy": "mutable (overwritten on refit)",
        "consistency": "strong",
        "retention": "indefinite"
      },
      {
        "table": "cycle_personal_model` JSONB",
        "strategy": "mutable (overwritten on refit)",
        "consistency": "strong",
        "retention": "indefinite"
      }
    ],
    "all_affected_architecture_entities": []
  },
  "release_plan": {
    "not_found": true
  },
  "vision": {
    "architecture_references_vision": [
      "adaptation-signature"
    ]
  }
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 12.8s)

_Thinking:_


Need maybe check related contracts for athlete-profile? It returned none. Need maybe for activity and preferences? Since subphase creates schemas. Could use get_related_contracts for primary entity? "primary entity" maybe Activity? But we have enough. Need maybe inspect actual repository structure? User wants generate implementation plan, not code. Need maybe write docs file. Need know next available implementation plan path. Need maybe list docs/implementation/phase-1. Use filesystem? Need tools only read/write/edit? We can use Read tool? We need read existing file before edit; if write new file not need read? But for existing? Need maybe use shell? There is no shell tool. Need use write tool. Need know if file exists. Could use list? No tool. Could maybe use grep? Not available. We can use Read on path maybe if exists? Read tool? We have functions namespace only pheidipp etc and write/edit. No Read tool defined? Wait tools list only pheidipp and write/edit/todowrite. There is no Read. But "Read tool at least once before editing" maybe maybe not available. We can use pheidipp get docs? Hmm no shell. Maybe can write new file; if existing would overwrite, but we don't know. Need maybe maybe use write to create new file. It says if existing file, must use Read first; but no read tool. However instructions say use native write. Maybe Read not available but write can overwrite. Need be careful. Could use edit only if read. We can write new file. Need maybe find docs/implementation existing? Use write? Maybe if path exists, it overwrites. But if no file, create. Need know next plan number. Since subphase phase-1-2a, likely one implementation plan. File path docs/implementation/phase-1/phase-1-2a-p1-core-models.md or phase-1-2a-p1-profile-preferences-activity.md. Developer format: docs/implementation/phase-N/phase-N-M-pY-<short-title>.md. Sub-phase ID maybe "Phase-1.2a" or "phase-1-2a-profile-preferences-activity". Example: phase-1-2-p1-activity-model. For subphase ID "Phase-1.2a", plan ID "Phase-1.2a-P1". File path docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md. Need maybe directory. We'll write. But first need maybe determine ADR? This is schema migration; no significant implementation decision? Need not ADR. Could maybe no ADR. Need maybe check architecture gaps? We have docs. Need maybe perhaps "AthleteProfile table was created in Phase 1.1 with minimal schema" but architecture doc says created at registration. Need plan to extend existing table via Alembic. Need implement only schema, no data writes. Need include exact invariants copied. Need include event contracts: subphase no events produced/consumed because schema only. Need mention none? Format says all events plan produces/consumes. For schema-only plan, "None — no events produced/consumed; do not emit events during migration." But maybe the plan touches Activity which produces events later; no event implementation. Need list not applicable.

Need maybe retrieve architecture docs enough. Need maybe exact schemas for athlete-profile, athlete-preferences, activity. We have from context. Need maybe "all constraints, indexes, enums" exact. Need maybe "Terminology" shared enums for ActivitySource? It includes DataTier and maybe not ActivitySource. Need find ActivitySource enum in terminology maybe not in Shared Enums? Search architecture.


**Tool: pheidipp-codebase-context_search_architecture**

**Input:**
```json
{
  "query": "ActivitySource enum manual_entry intervals_icu manual_upload garmin_direct terminology",
  "section": "Shared Enums",
  "top_k": 5
}
```

**Output:**
```

FILE: terminology.md
ENTITY: terminology
SECTION: shared enums
SCORE: 0.613

### PhysiologicalIntent
```typescript
type PhysiologicalIntent =
  | 'low_aerobic'
  | 'high_aerobic'
  | 'threshold'
  | 'vo2max'
  | 'neuromuscular'
  | 'recovery'
```
The physiological adaptation a session targets. Each workout step has exactly one intent. This is the primary coaching abstraction — the system works directly with intents, not zones. Many:1 mapping from SessionType (16 sessions → 6 intents).

### PhysiologyParameter
```typescript
type PhysiologyParameter =
  | 'lt1.hr'
  | 'lt1.power'
  | 'lt1.pace'
  | 'lt2.hr'
  | 'lt2.power'
  | 'lt2.pace'
  | 'cp'
  | 'vo2max.ml_kg_min'
  | 'vo2max.power'
  | 'max_hr'
```
Identifies a specific physiological parameter in event payloads and computation contexts. Dot notation reflects the nested structure of `AthletePhysiology` (e.g., `lt1.hr` is the HR-based LT1 threshold estimate). Used in `physiology_updated` and `physiology_lab_test_ingested` event payloads to specify which parameters were updated.

**Compliance families:**
- **Aerobic family** (intensity ladder): `recovery` → `low_aerobic` → `high_aerobic` → `threshold` → `vo2max`
- **Neuromuscular family** (orthogonal): `neuromuscular`

Neuromuscular efforts are not "above 
[truncated]

```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 8.1s)

_Thinking:_


Search truncated. Need maybe ActivitySource in activity doc. We have. Need maybe DataTier exact definitions not in data-tiers context because sections wrong. Need get full data-tiers maybe use search.


**Tool: pheidipp-codebase-context_search_architecture**

**Input:**
```json
{
  "query": "Data tier definitions Tier 1 Tier 2 Tier 3 Tier 4 Tier 5 Tier 6 hr_source power_source",
  "section": "Tier Definitions",
  "top_k": 5
}
```

**Output:**
```
No results found.
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 5.8s)

_Thinking:_


Need maybe get entity context data-tiers full?


**Tool: pheidipp-codebase-context_get_entity_context**

**Input:**
```json
{
  "entity_name": "data-tiers"
}
```

**Output:**
```
{
  "entity": "data-tiers",
  "graph": {
    "related_entities": [],
    "produces_events": [],
    "consumes_events": [],
    "used_by_agents": [],
    "invariants": [
      {
        "field": "calibration_eligible",
        "rule": "Tier 5 and 6 activities are never `calibration_eligible`",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "aerobic_load",
        "rule": "Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "A session without GPS (`has_gps = false`) defaults to Tier 6 for structural load purposes even if HR is present",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "wrist_optical",
        "rule": "Optical HR (`wrist_optical`) is adequate for zone-based load calculation. Its limitation versus chest strap is specifically the absence of RR intervals for threshold detection \u2014 not HR accuracy for sustained aerobic efforts",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "Threshold detection capability is determined by data tier (see Tier Definitions table). Tiers 1\u20134 provide different levels of threshold detection; Tiers 5\u20136 provide none.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "Easy runs are calibration-eligible for load computation but do NOT provide threshold detection evidence (insufficient intensity variation for HR deflection/RR inflection algorithms)",
        "type": "behavioral",
        "enforcement": "application"
      }
    ],
    "api_endpoints": [],
    "storage_models": []
  },
  "sections": {
    "Purpose": "- Defines the six data tiers that determine what signals are available for computation\n- Establishes which tiers enable which analytical capabilities",
    "TypeScript Schema": "```typescript\ntype DataTier = 1 | 2 | 3 | 4 | 5 | 6\n\ntype DataTierCapabilities = {\n  tier: DataTier\n  hardware: string\n  has_power: boolean\n  has_rr_intervals: boolean\n  has_hr: boolean\n  has_gps: boolean\n  calibration_eligible: boolean\n  load_dimensions_available: ('aerobic' | 'neuromuscular' | 'structural')[]\n  threshold_detection: 'rrv_inflection' | 'hr_deflection' | 'inferred_only' | 'none'\n  notes: string\n}\n```",
    "Tier Definitions": "| Tier | Hardware | Power | RR | HR | GPS | Calibration | Threshold Detection | Notes |\n|---|---|---|---|---|---|---|---|---|\n| 1 | Running power meter + chest strap (RR) | \u2713 | \u2713 | \u2713 | \u2713 | \u2713 | HR deflection + RR inflection + power-to-HR ratio | Most precise. Passive threshold tracking via RR. |\n| 2 | Running power meter + optical HR | \u2713 | \u2717 | \u2713 | \u2713 | \u2713 | HR deflection + power-to-HR ratio only | Very strong for load. No RR for inflection detection. |\n| 3 | Chest strap (RR) + GAP + GPS | \u2717 | \u2713 | \u2713 | \u2713 | \u2713 | HR deflection + RR inflection | RR data available. GAP as mechanical proxy. |\n| 4 | Optical HR + GAP + GPS | \u2717 | \u2717 | \u2713 | \u2713 | \u2713 | HR deflection only | Realistic baseline for core audience. Fully usable. |\n| 5 | GAP + GPS only (no HR) | \u2717 | \u2717 | \u2717 | \u2713 | \u2717 | None (no HR signal) | Logged for record. Excluded from twin calibration. |\n| 6 | Manual entry only | \u2717 | \u2717 | \u2717 | \u2717 | \u2717 | None | Training record only. No analytical value. |\n\n**Key insight**: Threshold detection requires intensity variation, not just HR accuracy. Easy runs are calibration-eligible (meet the five-rule gate) but do NOT provide threshold detection evidence because they lack the intensity variation needed for HR deflection/RR inflection algorithms. A calibration-eligible easy run contributes to fitness/fatigue scores, not threshold confidence.",
    "Load Dimensions by Tier": "| Tier | Aerobic Load | Neuromuscular Load | Structural Load |\n|---|---|---|---|\n| 1 | Power-based (most precise) | \u2713 | \u2713 |\n| 2 | Power-based | \u2713 | \u2713 |\n| 3 | HR reserve integration | \u2713 | \u2713 |\n| 4 | HR reserve integration | \u2713 | \u2713 |\n| 5 | GAP-estimated (low confidence) | \u2713 | \u2713 |\n| 6 | None | None | None |",
    "Threshold Detection by Tier": "| Tier | Algorithm | Confidence Weight |\n|---|---|---|\n| 1, 3 | HRV inflection point (RR) | High |\n| 1, 2 | Power-to-HR ratio analysis | Supplementary only |\n| 2, 4 | HR deflection analysis | Moderate |\n| 5, 6 | Historical inference only | No update |\n\n**Vision \u2194 Architecture note:** This table implements the vision's \"Signal Hierarchy\" from `docs/vision/twin/training-zones.md`. The vision describes five conceptual tiers (RR intervals \u2192 HR-based \u2192 Dedicated calibration \u2192 Lab/Test \u2192 Inference). This architecture table maps those to hardware-based data tiers:\n\n| Vision Signal Tier | Architecture Equivalent | Observation Weight |\n|---|---|---|\n| Raw RR intervals (chest strap) | Tier 1, 3 \u2192 `training_rr_inflection` | 2.5 |\n| HR-based signals without RR | Tier 2, 4 \u2192 `training_hr_deflection` | 1.0 |\n| Dedicated calibration sessions | Calibration-eligible sessions with intensity variation \u2192 `field_test` | 2.0\u20135.0 |\n| Lab/Test Uploads | `lab_test` source | 12.0\u201315.0 |\n| Inference from training history | `questionnaire_estimate` source | 0.5 |\n\nThe vision's hierarchy is about signal quality. The architecture's tiers are about hardware capability. They overlap but are not identical \u2014 a Tier 1 athlete (power + RR) can still produce low-quality RR data if the chest strap is faulty, and a Tier 4 athlete (optical HR) can produce high-quality HR deflection data over many sessions.",
    "Vision \u2194 Architecture: Data Philosophy": "This section maps the five principles from `docs/vision/twin/data-philosophy.md` to their architectural implementations in this document and across the architecture layer. These principles are the design rationale behind the tier structure, invariants, and observation weights defined above.\n\n### 1. Real Signals, Not Assumptions\n\nThe vision commits to using actual physiological data rather than estimated or inferred metrics. Grade-adjusted pace replaces raw pace. RR intervals are preferred over optical HR. Lab/test uploads are accepted with provenance.\n\n| Philosophy Element | Architecture Implementation |\n|---|---|\n| GAP replaces raw pace | Invariant #9 in `principles.md`: \"Raw pace is never used.\" |\n| RR intervals preferred | Tier 1\u20133 have `has_rr = true`; RR enables `training_rr_inflection` (observation weight 2.5) vs `training_hr_deflection` (weight 1.0) |\n| Lab/test uploads with provenance | `lab_test` source receives the highest observation weight (12.0\u201315.0) in the system |\n| Honest confidence when data is poor | Tier 5\u20136 have `threshold_detection: 'none'`; `calibration_eligible = false` |\n\n### 2. Data Quality Over Quantity\n\nThe vision commits to excluding sessions without device data from twin calibration. Noisy or incomplete data corrupts the model more than gaps do. The twin always knows the data quality tier and weights learning accordingly.\n\n| Philosophy Element | Architecture Implementation |\n|---|---|\n| Manual entry excluded from calibration | `calibration_eligible = false` for `manual_entry` source; Tier 6 invariant |\n| Noisy data excluded | Tier 5\u20136 never calibration-eligible; Tier 6 null loads |\n| Quality-aware weighting | Observation weights by source (0.5\u201315.0 range encodes quality into Bayesian update) |\n| Confidence reflects data quality | Per-metric confidence from prior weights; `metric_confidence` on TwinState |\n\n### 3. Continuous Learning From Real Training\n\nThe vision commits to updating the twin from every real training session. Individual time constants, threshold estimates, and adaptation patterns improve as data accumulates.\n\n| Philosophy Element | Architecture Implementation |\n|---|---|\n| Every session updates the twin | TwinState is append-only (invariant #4 in `principles.md`); recalibration appends new record |\n| Continuous improvement over time | Bayesian update with observation weights; confidence transitions LOW \u2192 MEDIUM \u2192 HIGH |\n| Historical reprocessing | Algorithm improvements reprocess recent history (invariant #14 in `principles.md`) |\n| Auditability of learning | Append-only + version strings make every historical decision explainable |\n\n### 4. Non-Running Data Does Not Corrupt the Running Model\n\nThe vision commits to logging non-running activities but never calibrating them into the twin. No arbitrary conversion factors. The twin waits for the next run.\n\n| Philosophy Element | Architecture Implementation |\n|---|---|\n| Non-running excluded from calibration | Invariant #8 in `principles.md`: \"Non-running activities are excluded from twin calibration\" |\n| No conversion factors | Anti-goal #11 in `principles.md`: \"no multi-sport conversion factors\" enforced as architectural constraint |\n| Activities logged but not calibrated | `calibration_eligible = false` for non-running; Activity record exists but twin does not learn from it |\n\n### 5. The Honesty Invariant\n\nThe vision commits to always being honest about evidence confidence. Conservative language, target ranges rather than point estimates, cautious plan structures. As evidence confidence grows, coaching becomes more specific.\n\n| Philosophy Element | Architecture Implementation |\n|---|---|\n| Conservative at low confidence | RacePrediction returns null at LOW confidence (204, no record) |\n| Per-metric honesty | Confidence is per-metric, not global; each parameter accumulates independently |\n| Unknown states preserved | `inferred_state = 'unknown'` when confidence < 0.45; coach makes no claims about unknown segments |\n| Range over point estimates | Bayesian posterior distributions (`state_probabilities`); confidence intervals on thresholds |\n| Plans reflect confidence level | `twin_state_id` on TrainingPlan records which twin version produced it; LOW confidence \u2192 different phase structures |\n\n### Summary: Why the Tier Structure Exists\n\nThe six-tier hardware classification is not an arbitrary technical decision. It is the architectural expression of five philosophical commitments:\n\n1. **Tiers exist** because real signals vary in quality, and the system must be explicit about what it can and cannot know.\n2. **Tier 5\u20136 exclusion** exists because gaps are preferred over noise \u2014 the system refuses to learn from data it cannot trust.\n3. **Observation weights vary by source** because not all evidence is equal, and the Bayesian update must reflect that.\n4. **Non-running activities are logged but not calibrated** because the running model must not be corrupted by signals it was not designed to process.\n5. **Confidence is per-metric and visible** because the system must never overstate what it knows.",
    "Tier Inference from AthletePreferences": "Tier is inferred from `AthletePreferences.hr_source` and `power_source`:\n\n```typescript\nfunction inferDataTier(hrSource: HrSource, powerSource: PowerSource): DataTier {\n  if (powerSource === 'running_power_meter') {\n    return hrSource === 'chest_strap_rr' ? 1 : 2\n  }\n  if (hrSource === 'chest_strap_rr') return 3\n  if (hrSource === 'chest_strap_no_rr' || hrSource === 'wrist_optical') return 4\n  if (hrSource === 'none') return 5\n  return 6  // manual entry\n}\n```",
    "Invariants": "- Tier 5 and 6 activities are never `calibration_eligible`\n- Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`\n- A session without GPS (`has_gps = false`) defaults to Tier 6 for structural load purposes even if HR is present\n- Optical HR (`wrist_optical`) is adequate for zone-based load calculation. Its limitation versus chest strap is specifically the absence of RR intervals for threshold detection \u2014 not HR accuracy for sustained aerobic efforts\n- Threshold detection capability is determined by data tier (see Tier Definitions table). Tiers 1\u20134 provide different levels of threshold detection; Tiers 5\u20136 provide none.\n- Easy runs are calibration-eligible for load computation but do NOT provide threshold detection evidence (insufficient intensity variation for HR deflection/RR inflection algorithms)",
    "Runtime Ownership": "Owns:\n- Tier classification from hardware signals\n- Which analytical capabilities each tier enables\n\nDoes Not Own:\n- The load formulas themselves \u2192 `02-computations/load-computation.md`\n- The threshold detection algorithms \u2192 `02-computations/threshold-detection.md`",
    "Implementation Notes": "- Tier is stored on `TwinState.data_tier` at the time of the TwinState creation\n- If an athlete upgrades their hardware (e.g. adds a power meter), the new tier is reflected in the next TwinState after an activity is processed\n- The tier ceiling is determined at onboarding from preferences but may differ per-session if the athlete forgets their chest strap (Tier 4 session for a Tier 3 athlete)"
  }
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 4.3s)

_Thinking:_


Need maybe full athlete profile maybe enough. Need maybe exact "DataTier" enum only. Need maybe "ActivitySource" not in terminology but in Activity schema. Good.

Need maybe check docs/implementation/phase-1 existing? We can't list but maybe use write. Need maybe maybe "phase-1-2a-p1-core-models.md" if not exists. But if exists, write overwrites. We need avoid destructive if existing. Could maybe use search_release_plan? Not implementation. Maybe no existing. But maybe we need read? Hmm.

Need maybe create implementation plan. But before write, maybe use todowrite? Task is multi-step (read subphase, retrieve, plan, write). We didn't use initially. Instructions say use proactively when task 3+ distinct steps. Need use now. Mark in_progress maybe.


**Tool: todowrite**

**Input:**
```json
{
  "todos": [
    {
      "content": "Read Phase-1.2a release-plan sub-phase document and identify referenced contracts",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Retrieve architecture and vision contracts required by Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Verify relevant invariants and dependency impact for Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Write the implementation plan for Phase-1.2a",
      "priority": "high",
      "status": "in_progress"
    },
    {
      "content": "Refresh architecture index after writing the implementation plan",
      "priority": "medium",
      "status": "pending"
    }
  ]
}
```

**Output:**
```
[
  {
    "content": "Read Phase-1.2a release-plan sub-phase document and identify referenced contracts",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Retrieve architecture and vision contracts required by Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Verify relevant invariants and dependency impact for Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Write the implementation plan for Phase-1.2a",
    "status": "in_progress",
    "priority": "high"
  },
  {
    "content": "Refresh architecture index after writing the implementation plan",
    "status": "pending",
    "priority": "medium"
  }
]
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 50.3s)

_Thinking:_


Need write implementation plan. Need maybe consider "phase-1-2a" vs "Phase-1.2a". Need plan title. Since subphase objective "Core Models: Profile, Preferences, Activity". Plan title maybe "Core Models: Profile, Preferences, Activity". File "docs/implementation/phase-1/phase-1-2a-p1-core-models.md". Need exact format.

Need include Sub-Phase Reference: Sub-Phase ID: Phase-1.2a; Title: Phase 1 — Core Models: Profile, Preferences, Activity. Plan ID: Phase-1.2a-P1.

Need Objective one paragraph. Scope exactly in scope: extend athlete_profiles table, create athlete_preferences table, create activities table, enums and constraints, indexes, migration, no data writes. Out of scope: services/endpoints, data writes, object storage, load computation, onboarding, planned sessions, raw streams.

Architecture Contracts: entities, events, computations. Since plan implements schema only:
- 01-entities/athlete-profile.md — IMPLEMENTS schema extension (full schema)
- 01-entities/athlete-preferences.md — IMPLEMENTS schema
- 01-entities/activity.md — IMPLEMENTS schema
- 00-foundations/terminology.md — DEPENDS ON enums? "shared enum values; DataTier etc"
- 00-foundations/data-tiers.md — DEPENDS ON data tier inference logic
- docs/vision/twin/cold-start.md — DEPENDS ON tier philosophy
- docs/vision/product/constraints.md — DEPENDS ON running-only, no raw data surfaces
Need maybe "00-foundations/data-tiers.md" is architecture not vision. Good.
No ADR.

Invariants: Copy exact text from architecture docs. Need include exact text:
- One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.
- One `AthletePreferences` per `Athlete`. Created during onboarding. Enforced by unique constraint on `(athlete_id)`.
- `years_structured_training >= 0`. CHECK constraint at DB level.
- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.
- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` — these fields do not exist on `Activity`. They are never added.
- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.
- Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.
- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.
- `timezone` is required at onboarding (validated against IANA tz database). Immutable after creation — changing timezone requires a support process. All scheduled tasks ... use this timezone. (Need maybe in profile)
- `training_window` defaults to 06:00–20:00 if not set...
- `structural_risk_flag` is computed at onboarding from `AthletePreferences.sport_background`. When true... (Maybe schema only, but include)
- Data tiers: Tier 5 and 6 activities are never `calibration_eligible`; Tier 6 activities have null load scores; session without GPS defaults to Tier 6 for structural load; optical HR etc maybe not schema.

Need Implementation Steps ordered. Since schema only:
1. Confirm Phase-1.1 baseline: Athlete and minimal athlete_profiles table exist; do not drop/recreate athlete_profiles; migration extends.
2. Define enums: ActivitySource, Sex, SportBackground, TrainingTimeOfDay, GpsSource, HrSource, PowerSource, PrimaryTrainingPlatform, DataTier maybe? Need "all required enums" from terminology. Need maybe `ActivitySource` exact values: intervals_icu, manual_upload, garmin_direct, manual_entry. `Sex`: male, female, not_specified. `SportBackground`: running_primary, cycling, swimming, triathlon, team_sport, gym_fitness, none. `TrainingTimeOfDay`: morning, afternoon, evening, variable. `GpsSource`: garmin_watch, apple_watch, polar, suunto, coros, other. `HrSource`: chest_strap_rr, chest_strap_no_rr, wrist_optical, none. `PowerSource`: running_power_meter, none. `PrimaryTrainingPlatform`: intervals_icu, garmin_connect, manual. `DataTier`: 1-6. Maybe `DaySchedule` not enum.
3. Implement migration to extend athlete_profiles:
 - existing fields date_of_birth, sex, height_cm maybe keep. Add gap_curve_model JSONB null, weather_response_model JSONB null, banister_constants JSONB null, cycle_personal_model JSONB null, location_lat/long nullable, timezone string not null? But if table existing with rows? Phase 1.1 maybe minimal profiles created at registration, maybe timezone not required at registration? Subphase schema only; but architecture says required at onboarding. Need not enforce NOT NULL? Hmm Phase 1.2a schema only, but "timezone is required at onboarding" not necessarily DB not null. But "schema for AthleteProfile full". Should we set timezone NOT NULL? The table exists maybe rows from phase 1.1 without timezone. Migration may need nullable default? Need careful. The release plan says `athlete_profiles` table created minimal schema (date_of_birth, sex, height_cm), extends full schema. If there may be existing rows, adding `timezone` NOT NULL requires default. But Phase 1.2a is schema only, no data writes. It can set default? Need architecture says timezone required at onboarding, immutable. But for existing profiles from Phase 1.1, not onboarding complete. Could set nullable to allow schema-only migration, then Phase 1.3 onboarding API validates. But subphase exit gate says all constraints and indexes. "timezone is required at onboarding" maybe API validation not DB. Hmm.

Need maybe plan not choose too much? We can state coder should align with existing migration baseline and not introduce data migration. If adding required columns to existing rows, use nullable/default where necessary and enforce required at onboarding later. But exit gate says all constraints. Could use DB-level unique constraints and check constraints. For timezone required at onboarding, maybe `timezone` nullable now to preserve existing Phase 1.1 rows, but add CHECK? "timezone IS NULL OR valid IANA"? Hard in DB. Maybe application validation. But subphase is schema only. Need not build endpoints. But "constraints, indexes, and enums defined" likely DB. Could define timezone as nullable until Phase 1.3? Hmm.

Need perhaps "Schema for AthleteProfile" full schema, but no data. Since "athlete_profiles table was created in Phase-1.1 with minimal schema. This sub-phase extends it to full schema via Alembic migration, adding personalisation model columns..." It doesn't say constraints. Need plan implement migration adding columns with appropriate nullability. We can include "Do not add a NOT NULL column without a safe default/backfill; Phase 1.3 onboarding validation enforces required-at-onboarding." But this may be implementation detail. Need maybe not leave decisions to coder? We can specify: For existing rows, columns that are not known at registration remain nullable; onboarding service later validates required fields. But "full schema" includes timezone required. How to enforce? If no onboarding rows? We can say "Add DB constraints for invariants that can be enforced safely without data writes: unique athlete_id, years_structured_training CHECK, Activity unique partial index, no prohibited Activity columns. Defer timezone requiredness to onboarding API because Phase 1.2a writes no data and existing Phase 1.1 rows may lack it." Is that an architecture gap? Maybe not. But plan should execute.

Need maybe "Do not create endpoints or services." Good.

Need Event Contracts: None produced/consumed; schema-only. But mention Activity events later:
- Does not implement activity_ingested, activity_calibration_eligible, session_completed.
- No event contract changes.

Pseudocode: For migrations, maybe:
```
extend_athlete_profiles_migration
  confirm baseline columns...
  add nullable JSONB columns...
  add location/timezone/training_window...
  add current_effort_generation default 1...
  add structural_risk_flag default false...
  create unique index...
create_athlete_preferences_table
  create table...
  unique athlete_id...
  check years_structured_training >= 0...
create_activity_table
  create table...
  ensure no avg columns...
  create unique partial index...
```
Need not production code. Good.

Testing Requirements:
- Fresh DB migrations run cleanly.
- `athlete_profiles` table has full columns and unique constraint on athlete_id.
- `athlete_preferences` table exists with unique constraint and years check.
- `activities` table exists with no avg_hr/avg_pace/avg_power/lap_data.
- `activities` source enum accepts exact values; manual_entry row can have null fit_file_key, false calibration, null load scores; non-manual source requires fit_file_key? DB can enforce? Could add check constraint. Need testing maybe "attempt insert manual_entry with null fit_file_key succeeds; attempt insert intervals_icu with null fit_file_key fails".
- Partial unique index `(athlete_id, external_id, source)` where external_id not null enforces duplicates.
- Data tier inference values can be represented exactly (enum).
- No data seeded.

Need Coder Handoff Notes:
- This is schema-only; no data writes, no endpoints.
- Do not drop/recreate athlete_profiles.
- Do not add avg fields.
- Do not implement load computation or calibration services.
- Ensure enum values exact.
- If existing Phase 1.1 rows exist, migration must be backward-compatible; no destructive migration.
- Running-only/no raw data surfaces: Activity remains lean observation index; no raw charts fields.
- Fit_file_key invariant.
- Phase 1.2b depends on Activity planned_session_id FK? But PlannedSession table not created yet. In Phase 1.2a, Activity schema includes planned_session_id FK to PlannedSession, but Phase 1.2b creates PlannedSession. Need migration ordering? This is important! Subphase 1.2a includes Activity schema with planned_session_id FK to PlannedSession. But planned_session table created in 1.2b. How can 1.2a migration create FK to non-existing table? Need architecture? The subphase document says Activity schema includes planned_session_id FK -> PlannedSession. But 1.2b downstream creates PlannedSession. "Phase-1.2b — Activity is referenced by PlannedSession" actually says Activity referenced by PlannedSession? In phase 1.6 says Activity.planned_session_id FK links to PlannedSession. If 1.2a creates Activity before PlannedSession, cannot add FK unless migration order in 1.2b creates table and then 1.2a migration? But subphase order has 1.2a before 1.2b. Need inspect planned-session architecture maybe FK direction.


**Tool: pheidipp-codebase-context_get_entity_context**

**Input:**
```json
{
  "entity_name": "planned-session",
  "sections": [
    "TypeScript Schema",
    "Storage Model",
    "Invariants"
  ]
}
```

**Output:**
```
{
  "entity": "planned-session",
  "graph": {
    "related_entities": [],
    "produces_events": [
      "`planned_session_generated`",
      "`session_completed`",
      "`session_skipped`",
      "`session_missed`"
    ],
    "consumes_events": [
      "`activity_ingested`",
      "`workout_generated`"
    ],
    "used_by_agents": [],
    "invariants": [
      {
        "field": "session_slot",
        "rule": "**Multiple PlannedSession records per day are allowed.** Uniqueness is enforced on `(weekly_plan_id, target_date, session_slot)` where `session_slot` distinguishes AM/PM sessions.",
        "type": "uniqueness",
        "enforcement": "application"
      },
      {
        "field": "activity_id",
        "rule": "**`activity_id` is set only when `status = 'completed'`.**",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "redistributed_to_date",
        "rule": "**`redistributed_to_date` is set only when `status = 'redistributed'`.** A new `PlannedSession` is created for the target date when redistribution occurs \u2014 the original is not moved.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Primary sessions receive full workout generation.** Secondary sessions may be suggested without detailed targets (e.g. \"Strength & conditioning \u2014 30 min\").",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Recovery time is measured from primary to primary.** Secondary sessions do not reset the recovery clock.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Same-day doubles: AM primary + PM secondary is preferred.** This provides adequate recovery between sessions. Reverse ordering (PM primary + AM primary next day) provides longer recovery.",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Training Structure Rationale (Layer 2 \u2014 standalone):**",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Block members must be consecutive dates.** Consecutive quality sessions create compound training stimuli that require structured recovery.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Block members must all be quality sessions.** Rest, recovery_run, and easy sessions do not contribute to compound stimulus.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Block cannot span more than 3 sessions.** Limits compound stimulus duration to prevent excessive fatigue accumulation and maintain observation window clarity.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Block must include recovery after the last session.** The recovery session is part of the block structure \u2014 it completes the stimulus-recovery cycle.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Block is optional.** Not all quality sessions need to be grouped; isolated quality sessions with full recovery are valid training structures.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Block Size Enforcement:**",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "candidates",
        "rule": "The `identifyBlockCandidates()` function MUST enforce the 3-session cap. When `currentBlock.length` reaches 3, the function MUST push the block to `candidates` and reset `currentBlock`, even if the next session is also quality. Implementation: `03-agents/weekly-synthesis-agent.md` \u2192 Block Creation Logic.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Adaptation Observation Compatibility (Layer 4 \u2014 informational):**",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "block_id",
        "rule": "The `block_id` groups created by the above training-structure rules are *compatible with* observation by the adaptation signature layer (Layer 4). The adaptation layer observes recovery response to these compound stimuli as adaptation windows. See `01-entities/adaptation-observation.md`.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "**Key Principle:** Layer 2 block rules are derived from training physiology. Layer 4 observes what Layer 2 structures. If Layer 4's detection algorithm changes, Layer 2 rules do not change \u2014 Layer 4 adapts its observation window definition.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": "WeeklySynthesisAgent",
        "rule": "(Enforced by `WeeklySynthesisAgent` at creation and by `SessionLifecycleService` when redistributing):",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "Long runs are always followed by a rest or recovery_run session",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "Threshold and vo2max sessions are sandwiched between easy or rest days",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": "threshold",
        "rule": "No two quality sessions (`threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`, `long_run`) on consecutive dates **unless they share a `block_id`**. Blocks must include recovery after the final session.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "These rules protect training quality (adequate recovery between hard efforts). The block rules are derived from training physiology; they are not driven by the adaptation observation layer's requirements.",
        "type": "range",
        "enforcement": "application"
      },
      {
        "field": "block_id",
        "rule": "**The `block_id` groups created by these rules are observed by the adaptation signature layer as adaptation windows.** The weekly synthesis agent creates `block_id` groups of 2-3 consecutive quality sessions; the adaptation signature layer then observes the recovery response to those groups. See `01-entities/adaptation-observation.md`.",
        "type": "behavioral",
        "enforcement": "application"
      },
      {
        "field": null,
        "rule": "---",
        "type": "behavioral",
        "enforcement": "application"
      }
    ],
    "api_endpoints": [
      {
        "method": "GET",
        "path": "/athletes/{athlete_id}/plan/sessions/{session_id}",
        "auth": "Bearer JWT",
        "response_status": 200
      },
      {
        "method": "POST",
        "path": "/athletes/{athlete_id}/plan/sessions/{session_id}/skip",
        "auth": "Bearer JWT",
        "response_status": 200
      },
      {
        "method": "POST",
        "path": "/athletes/{athlete_id}/plan/sessions/{session_id}/redistribute",
        "auth": "Bearer JWT",
        "response_status": 200
      },
      {
        "method": "GET",
        "path": "/athletes/{athlete_id}/plan/sessions/{session_id}/substitutes",
        "auth": "Bearer JWT",
        "response_status": 200
      },
      {
        "method": "POST",
        "path": "/athletes/{athlete_id}/plan/sessions/{session_id}/accept-substitute",
        "auth": "Bearer JWT",
        "response_status": 200
      }
    ],
    "storage_models": [
      {
        "table": "planned_sessions` table",
        "strategy": "append-only (status/linkage fields mutable)",
        "consistency": "strong",
        "retention": "indefinite"
      }
    ]
  },
  "sections": {
    "TypeScript Schema": "```typescript\ntype SessionSlot = 'am' | 'pm'\n\ntype SessionPriority = 'primary' | 'secondary'\n\ntype PlannedSession = {\n  id: string                       // UUID, PK\n  weekly_plan_id: string           // UUID, FK \u2192 WeeklyPlan (weekly synthesis creates these)\n  training_plan_id: string         // UUID, FK \u2192 TrainingPlan (denormalized for query performance)\n                                   // DENORMALIZED \u2014 source of truth is WeeklyPlan.training_plan_id\n                                   // STALENESS RISK: when a plan is superseded, existing PlannedSession records retain the old training_plan_id\n                                   // CORRECT QUERY PATTERN: join via WeeklyPlan \u2192 WeeklyPlan.training_plan_id (always current)\n                                   // The index (training_plan_id, target_date, session_slot) will hit superseded plans if used directly\n  target_date: string              // YYYY-MM-DD\n  week_number: number              // 1-indexed; derived from WeeklyPlan\n  phase_label: PhaseLabel          // derived from WeeklyPlan.adjusted_intent\n  session_type: SessionType        // canonical type enum\n  intent_description: string       // plain English; shown in near-term preview\n  approximate_duration_minutes: number\n\n  // Checkpoint metadata (set if this session is a checkpoint)\n  checkpoint_type: CheckpointType | null   // null = not a checkpoint\n  checkpoint_metric: string | null         // primary metric being assessed\n\n  // Status lifecycle\n  status: PlannedSessionStatus\n  skip_reason: string | null       // set when status \u2192 skipped\n  redistributed_to_date: string | null  // set when status \u2192 redistributed\n\n  // Completion linkage\n  activity_id: string | null       // FK \u2192 Activity; set when status \u2192 completed\n\n  // Slot designation\n  session_slot: SessionSlot | null     // null = single session day; 'am'/'pm' = double day\n  session_priority: SessionPriority    // default: 'primary'\n\n  // Block membership\n  block_id: string | null          // null = standalone session; non-null = part of a block\n  block_position: 'first' | 'middle' | 'last' | null  // position within block\n  block_session_count: number | null  // total sessions in this block (set on all block members)\n\n  // Non-running session support\n  is_suggested: boolean               // true = suggested session (e.g. strength, yoga); false = full workout generated\n}\n```\n\n---",
    "Invariants": "- **Multiple PlannedSession records per day are allowed.** Uniqueness is enforced on `(weekly_plan_id, target_date, session_slot)` where `session_slot` distinguishes AM/PM sessions.\n- **`activity_id` is set only when `status = 'completed'`.**\n- **`redistributed_to_date` is set only when `status = 'redistributed'`.** A new `PlannedSession` is created for the target date when redistribution occurs \u2014 the original is not moved.\n- **Primary sessions receive full workout generation.** Secondary sessions may be suggested without detailed targets (e.g. \"Strength & conditioning \u2014 30 min\").\n- **Recovery time is measured from primary to primary.** Secondary sessions do not reset the recovery clock.\n- **Same-day doubles: AM primary + PM secondary is preferred.** This provides adequate recovery between sessions. Reverse ordering (PM primary + AM primary next day) provides longer recovery.\n\n### Block Invariants\n\n**Training Structure Rationale (Layer 2 \u2014 standalone):**\n\n- **Block members must be consecutive dates.** Consecutive quality sessions create compound training stimuli that require structured recovery.\n- **Block members must all be quality sessions.** Rest, recovery_run, and easy sessions do not contribute to compound stimulus.\n- **Block cannot span more than 3 sessions.** Limits compound stimulus duration to prevent excessive fatigue accumulation and maintain observation window clarity.\n- **Block must include recovery after the last session.** The recovery session is part of the block structure \u2014 it completes the stimulus-recovery cycle.\n- **Block is optional.** Not all quality sessions need to be grouped; isolated quality sessions with full recovery are valid training structures.\n\n**Block Size Enforcement:**\n\nThe `identifyBlockCandidates()` function MUST enforce the 3-session cap. When `currentBlock.length` reaches 3, the function MUST push the block to `candidates` and reset `currentBlock`, even if the next session is also quality. Implementation: `03-agents/weekly-synthesis-agent.md` \u2192 Block Creation Logic.\n\n**Adaptation Observation Compatibility (Layer 4 \u2014 informational):**\n\nThe `block_id` groups created by the above training-structure rules are *compatible with* observation by the adaptation signature layer (Layer 4). The adaptation layer observes recovery response to these compound stimuli as adaptation windows. See `01-entities/adaptation-observation.md`.\n\n**Key Principle:** Layer 2 block rules are derived from training physiology. Layer 4 observes what Layer 2 structures. If Layer 4's detection algorithm changes, Layer 2 rules do not change \u2014 Layer 4 adapts its observation window definition.\n\n### Structural Session Distribution Rules\n\n(Enforced by `WeeklySynthesisAgent` at creation and by `SessionLifecycleService` when redistributing):\n\n- Long runs are always followed by a rest or recovery_run session\n- Threshold and vo2max sessions are sandwiched between easy or rest days\n- No two quality sessions (`threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`, `long_run`) on consecutive dates **unless they share a `block_id`**. Blocks must include recovery after the final session.\n\nThese rules protect training quality (adequate recovery between hard efforts). The block rules are derived from training physiology; they are not driven by the adaptation observation layer's requirements.\n\n**The `block_id` groups created by these rules are observed by the adaptation signature layer as adaptation windows.** The weekly synthesis agent creates `block_id` groups of 2-3 consecutive quality sessions; the adaptation signature layer then observes the recovery response to those groups. See `01-entities/adaptation-observation.md`.\n\n---",
    "Storage Model": "| Data | Strategy | Consistency | Retention |\n|---|---|---|---|\n| `planned_sessions` table | append-only (status/linkage fields mutable) | strong | indefinite |\n\nIndex: `(training_plan_id, target_date, session_slot)` for plan retrieval.\nIndex: `(athlete_id via plan join, status, target_date)` for upcoming session queries.\nIndex: `(weekly_plan_id)` for weekly plan session lookups.\n\n---"
  }
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 4.5s)

_Thinking:_


Important. Activity has planned_session_id FK to PlannedSession, but planned_session has activity_id FK to Activity. Circular FK. Architecture subphase 1.2a before 1.2b. Need plan maybe create Activity table without FK constraint in 1.2a, then Phase 1.2b adds FK after planned_sessions exists? But subphase says "All constraints, indexes, and enums defined." This is a significant architecture inconsistency? Need resolve architecture gap before handoff. The subphase structure says 1.2a before 1.2b, Activity schema includes planned_session_id FK. But 1.2b creates PlannedSession with activity_id FK. Circular reference. The release plan challenge notes for 1.2b mention Checkpoint-PlannedSession circular reference, not Activity. We need maybe inspect activity schema in docs maybe says FK to PlannedSession. It does. Could create `planned_session_id` column nullable in 1.2a with FK not created until 1.2b? But "all constraints defined" in 1.2a maybe not. Could create separate migration in 1.2b to add FK after both tables exist. But 1.2a "Activity is referenced by PlannedSession" maybe from planned-session perspective. Hmm.

Need maybe get related_contracts for activity?


**Tool: pheidipp-codebase-context_get_related_contracts**

**Input:**
```json
{
  "entity_name": "activity"
}
```

**Output:**
```
{
  "entity": "activity",
  "related_entities": [],
  "produces_events": [
    "`activity_ingested`",
    "`activity_calibration_eligible`"
  ],
  "consumes_events": [
    "`session_completed`"
  ],
  "used_by_agents": []
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 4.3s)

_Thinking:_


Need maybe get related for planned-session.


**Tool: pheidipp-codebase-context_get_related_contracts**

**Input:**
```json
{
  "entity_name": "planned-session"
}
```

**Output:**
```
{
  "entity": "planned-session",
  "related_entities": [],
  "produces_events": [
    "`planned_session_generated`",
    "`session_completed`",
    "`session_skipped`",
    "`session_missed`"
  ],
  "consumes_events": [
    "`activity_ingested`",
    "`workout_generated`"
  ],
  "used_by_agents": []
}
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 57.3s)

_Thinking:_


Need maybe architecture gap significant? Could be missing migration coordination. But user asked generate implementation plan, not code. We can include plan to avoid circular FK in 1.2a: add nullable column without FK; Phase 1.2b will add FK? But subphase says all constraints. Is this changing scope? We can classify as minor gap? Hmm. Need maybe "Activity.planned_session_id FK links to PlannedSession" in 1.6. Since 1.2b creates PlannedSession later, cannot enforce FK in 1.2a without forward reference. However in Alembic, you can create `planned_sessions` table in 1.2a? That would violate scope (1.2b). Or create FK in 1.2b. This is an architecture inconsistency/missing contract. We need "Resolve Architecture Gaps Before Handoff": If retrieval reveals missing contract, ambiguous ownership, stale invariant, fix documentation before handoff. Could update architecture? But maybe not necessary if plan notes. Need maybe use edit? Need read before editing; no Read tool. But maybe pheidipp get context counts as read? The edit tool requires Read tool at least once? We don't have. Hmm.

Maybe no need to fix docs? But if "all constraints" ambiguous, we can make implementation plan explicit: implement column in 1.2a, add FK in Phase 1.2b when planned_sessions table exists. This is a schema sequencing constraint, not redesign. But exit gate for 1.2a says all constraints defined. If we don't define FK, maybe fail. But perhaps all constraints defined in plan includes a deferred FK as not in scope? Hmm.

Need maybe inspect docs/implementation maybe existing? no. Need maybe maybe create plan with "Architecture Gap Resolved" in Coder Handoff: because Activity and PlannedSession have circular FK, Phase 1.2a must not create FK; Phase 1.2b must add it once both tables exist. But exit gate says all constraints. Maybe update release plan? No.

Maybe better: In Phase 1.2a, create activities table with `planned_session_id UUID NULL` and a CHECK? But no FK. In Phase 1.2b, when planned_sessions table exists, add foreign key constraint to activities.planned_session_id. This preserves subphase sequencing. Is it within scope? It implements schema for Activity and constraints where possible. It doesn't create 1.2b table. But "all constraints" maybe not. Could create a `NOT VALID` FK? In Postgres, adding a foreign key to nonexistent table impossible. Could create unvalidated FK to planned_sessions if table exists? No.

Need maybe maybe planned_session_id FK not required in Phase 1.2a because planned_session table not yet exists; but subphase "Activity schema" includes field. Hmm.

Need maybe include "This plan does not enforce the Activity.planned_session_id foreign key until Phase-1.2b; this is a documented sequencing constraint, not a runtime gap." But exit gate? Testing "Activity schema includes nullable planned_session_id column; foreign key to planned_sessions is deferred to Phase-1.2b due to table ordering." That may be accepted.

Need maybe another gap: Activity table has `has_power` boolean but no `has_gps` field, yet data-tiers says session without GPS defaults to Tier 6 for structural load. Activity schema has no has_gps, only has_power. Hmm. Maybe GPS availability inferred from fit_file? No. Not relevant to schema? But data tier inference from preferences, not Activity. Phase 1.6 needs has_gps maybe not in schema. This could be missing field. But subphase specifically says schema for Activity. Should we add has_gps? Architecture contract doesn't. Don't change. Not our job. But maybe plan says do not add has_gps. Good.

Need maybe "Activity.source = manual_entry always has calibration_eligible=false..." We need DB check constraints? Could implement check constraint. But `source` enum, `fit_file_key` check:
```
CHECK (
 (source = 'manual_entry' AND calibration_eligible = false AND fit_file_key IS NULL AND aerobic_load IS NULL AND neuromuscular_load IS NULL AND structural_load IS NULL)
 OR (source <> 'manual_entry' AND fit_file_key IS NOT NULL)
)
```
But for Phase 1.2a, load scores null at initial creation; non-manual row with load scores populated later allowed. This check enforces manual_entry invariants. Could be DB constraint. For non-manual with null fit_file_key fail. Good.
Need partial unique index:
```
CREATE UNIQUE INDEX activities_external_id_source_unique ON activities (athlete_id, external_id, source) WHERE external_id IS NOT NULL;
```
Need maybe indexes: athlete_id, activity_date, planned_session_id, maybe created_at. Need maybe unique constraints for profile and preferences.
Need maybe JSONB columns. Need maybe "training_window JSONB" with check start/end? Could add JSONB check? Maybe not necessary? But "constraints" maybe. Could use CHECK for `training_window` shape if JSONB? Hard. Could use JSONB type. For `current_effort_generation` check 1-3. `structural_risk_flag` boolean. `objective_thresholds` JSONB.
Need maybe "sex = female enables cycle tracking" not DB? It's behavioral.

Need maybe "AthletePreferences.weekly_schedule JSONB with days available/max_hours/long_workout/doubles_eligible". Could add check? Hard. But maybe schema only.
Need maybe "DataTier inference logic" not schema? Need maybe no service. But maybe create enum DataTier? Data tier inferred from prefs, not stored in preferences. No data_tier column in prefs. But "all required enums" includes DataTier? If no table, no DB enum needed. But maybe for future. The subphase says "all required enums" including ActivitySource, DataTier, PhysiologicalIntentState? Wait risk says `ActivitySource`, `DataTier`, `PhysiologicalIntentState` and other enums. But 1.2a doesn't touch PhysiologicalIntentState. Maybe "copy exact from terminology." Need plan maybe create only enums needed by schemas: Sex, SportBackground, TrainingTimeOfDay, GpsSource, HrSource, PowerSource, PrimaryTrainingPlatform, ActivitySource, DataTier. Do not create PhysiologicalIntentState in 1.2a (used in 1.2c/1.5b). But the subphase risk says "ActivitySource, DataTier, PhysiologicalIntentState and other enums" maybe from all Phase 1. Hmm. But 1.2a "all required enums" for these tables. DataTier not stored on table? Could create DB enum if future. But no table. Need maybe not create unused enum? "All required enums" maybe includes DataTier as shared. But no field. Hmm.

Need maybe "ActivitySource" stored in Activity; "HrSource/PowerSource/etc" stored in preferences; "Sex" stored in profile. DataTier not a column in these schemas. But perhaps database enum useful? No need. But release plan risk says DataTier. Could include "Create DataTier enum only if platform enum convention requires shared enum; do not add a data_tier column to AthletePreferences." Good.

Need maybe "No endpoints" but architecture docs list endpoints for Activity later. Phase 1.2a no endpoints. Need out of scope.

Need maybe "Testing requirements" can include "No service code or endpoints are required; tests are migration/schema tests."

Need maybe "Pseudocode" maybe not "production code". Good.

Need maybe "Architecture Contracts" relationships: "IMPLEMENTS", "DEPENDS ON". For vision "DEPENDS ON". No event. Good.

Need maybe "Event Contracts" all events this plan produces/consumes. For schema-only:
- `None` — PRODUCES? no.
Maybe table:
| Event | PRODUCES/CONSUMES | Payload | Ordering assumptions |
| None | None | None | This sub-phase is schema-only; no event producers/consumers are implemented. |
Need maybe mention future Activity events not implemented.

Need maybe "Implementation Steps" mention "Create Alembic migration(s) named..." Not file structure? "Do not specify file structures" but migration naming okay? Maybe "Implement Alembic migration(s)" not exact file. Good.

Need maybe "Use native write tool." We'll write. Need no emojis. Need maybe no code block? Pseudocode can be code block. Fine.

Need maybe after write call refresh_architecture. But first write. Need maybe if directory doesn't exist, write tool can create? It says create directory if it does not exist. Does write tool create dirs? Maybe no? It says use native write; create directory if not exists but no shell. Maybe write tool will fail if dir missing? Need maybe maybe directory exists. We can write. If fails, need maybe cannot create dirs. But likely docs/implementation/phase-1 exists? We can write.


**Tool: write**

**Input:**
```json
{
  "content": "# Implementation Plan: Phase-1.2a — Core Models: Profile, Preferences, Activity\n## Plan ID: Phase-1.2a-P1\n\n## Sub-Phase Reference\nSub-Phase ID: Phase-1.2a\nSub-Phase Title: Phase 1 — Core Models: Profile, Preferences, Activity\n\n## Objective\nImplement the schema-only foundation for the athlete-context tables used by onboarding and downstream coaching systems: extend the existing `athlete_profiles` table to the full `AthleteProfile` schema, create the `AthletePreferences` table, and create the lean `Activity` observation table. This plan does not write data, expose APIs, compute load, or implement ingestion services; it prepares the database contracts that Phase-1.3, Phase-1.4, and Phase-1.6 will consume.\n\n## Scope\n- Extend the existing `athlete_profiles` table from the Phase-1.1 minimal demographics schema to the full `AthleteProfile` schema.\n- Create the `athlete_preferences` table with one-to-one linkage to `Athlete`.\n- Create the `activities` table as a lean observation index.\n- Define required database enums and check constraints for `AthleteProfile`, `AthletePreferences`, and `Activity`.\n- Define required unique constraints and indexes, including the `Activity` external deduplication rule.\n- Preserve the Phase-1.1 `athlete_profiles` table by extending it only; do not drop and recreate it.\n- Keep the plan schema-only: no data seeding, no service logic, no endpoint implementation, no FIT parsing, no load computation, and no calibration logic.\n\n## Out Of Scope\n- Implementing onboarding, profile, preferences, or activity endpoints.\n- Creating or writing `AthleteIntegration`, `RawSensorStream`, `PhysiologicalSegment`, `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, or `PlannedSession`.\n- Implementing object storage, FIT parsing, load computation, calibration eligibility, twin recalibration, or post-workout analysis.\n- Adding averaged workout fields to `Activity`.\n- Adding raw data surfaces, workout charts, lap dumps, or dashboard-style summaries.\n- Changing release sequencing or merging this schema work into Phase-1.2b.\n\n## Architecture Contracts\n- `01-entities/athlete-profile.md` — IMPLEMENTS the full `AthleteProfile` schema and preserves the existing one-to-one profile relationship.\n- `01-entities/athlete-preferences.md` — IMPLEMENTS the `AthletePreferences` schema and data-tier-related preference fields.\n- `01-entities/activity.md` — IMPLEMENTS the lean `Activity` observation index schema.\n- `00-foundations/terminology.md` — DEPENDS ON shared enum values and domain terminology.\n- `00-foundations/data-tiers.md` — DEPENDS ON data tier capability model and preference-based tier inference fields.\n- `docs/vision/twin/cold-start.md` — DEPENDS ON honest low-confidence onboarding tier philosophy.\n- `docs/vision/product/constraints.md` — DEPENDS ON running-only twin model and no raw data surfaces.\n\n## Invariants\n- One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.\n- One `AthletePreferences` per `Athlete`. Created during onboarding. Enforced by unique constraint on `(athlete_id)`.\n- `years_structured_training >= 0`. CHECK constraint at DB level.\n- `timezone` is required at onboarding (validated against IANA tz database). Immutable after creation — changing timezone requires a support process. All scheduled tasks (MissedSessionSweepTask, WorkoutPrefetchTask) and date interpretations use this timezone.\n- `training_window` defaults to 06:00–20:00 if not set. Mutable via PATCH. Only used by WorkoutPrefetchTask for prefetch timing. MissedSessionSweepTask uses timezone only, not training_window.\n- `structural_risk_flag` is computed at onboarding from `AthletePreferences.sport_background`. When `true`, the structural load density penalty coefficient is 0.08 (vs 0.12 population default). See `02-computations/load-computation.md`.\n- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.\n- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` — these fields do not exist on `Activity`. They are never added.\n- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.\n- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.\n- Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.\n- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.\n- Tier 5 and 6 activities are never `calibration_eligible`.\n- Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`.\n\n## Implementation Steps\n1. Confirm the Phase-1.1 baseline: `Athlete` exists and `athlete_profiles` already contains the minimal registration columns `date_of_birth`, `sex`, and `height_cm`. Do not drop, rename, or recreate `athlete_profiles`.\n2. Define or update shared database enums from the architecture contracts: `Sex`, `SportBackground`, `TrainingTimeOfDay`, `GpsSource`, `HrSource`, `PowerSource`, `PrimaryTrainingPlatform`, and `ActivitySource`.\n3. Extend `athlete_profiles` with the full schema fields: `gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`, `location_lat`, `location_lng`, `timezone`, `training_window`, `current_effort_generation`, `structural_risk_flag`, and `objective_thresholds`.\n4. Add safe defaults and nullability for the profile extension so existing Phase-1.1 rows remain valid: `current_effort_generation` defaults to `1`, `structural_risk_flag` defaults to `false`, and fields not known at registration remain nullable until Phase-1.3 onboarding validation supplies them.\n5. Enforce `AthleteProfile` one-to-one ownership by ensuring a unique constraint or unique index exists on `(athlete_id)`.\n6. Create `athlete_preferences` with `athlete_id` as the one-to-one FK to `Athlete`, and enforce a unique constraint on `(athlete_id)`.\n7. Add `athlete_preferences` fields for `sport_background`, `years_structured_training`, `training_time_of_day`, `weekly_schedule`, `gps_source`, `hr_source`, `power_source`, `primary_training_platform`, and `updated_at`.\n8. Add the `years_structured_training >= 0` CHECK constraint at DB level.\n9. Create `activities` with the lean observation fields: `id`, `athlete_id`, `planned_session_id`, `source`, `external_id`, `activity_date`, `start_time`, `duration_seconds`, `aerobic_load`, `neuromuscular_load`, `structural_load`, `has_hr`, `has_rr_intervals`, `has_power`, `calibration_eligible`, `quality_flags`, `fit_file_key`, `ingestion_pipeline_version`, `cleaning_pipeline_version`, `notes`, and `created_at`.\n10. Do not add `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or `lap_data` columns to `activities`.\n11. Add `Activity` check constraints for source semantics: `manual_entry` must have `calibration_eligible = false`, null load scores, and null `fit_file_key`; non-manual sources must have a non-null `fit_file_key`.\n12. Add the partial unique index for Activity deduplication: `(athlete_id, external_id, source)` where `external_id IS NOT NULL`.\n13. Add useful query indexes for downstream phases: `athlete_id`, `activity_date`, `planned_session_id`, `created_at`, and the deduplication partial index.\n14. For `activities.planned_session_id`, create the nullable column in this sub-phase but do not create the FK constraint until Phase-1.2b, because `planned_sessions` is created later and the schema currently has a circular linkage direction.\n15. Run the migration suite on a fresh database and verify that no Phase-1.2a data is seeded or written.\n\n## Event Contracts\n| Event | PRODUCES or CONSUMES | Payload fields required by this plan | Ordering assumptions |\n|---|---|---|---|\n| None | None | None | This sub-phase is schema-only. Do not emit, consume, or alter event contracts. |\n\nFuture `Activity` events (`activity_ingested`, `activity_calibration_eligible`) are not implemented by this plan. Future `PlannedSession` event handling is not implemented by this plan.\n\n## Pseudocode\n```text\nrun_phase_1_2a_schema_migration\n  verify athlete_profiles baseline exists\n  extend athlete_profiles\n    add personalisation JSONB fields\n    add location/timezone/training_window fields\n    add current_effort_generation default 1\n    add structural_risk_flag default false\n    add objective_thresholds JSONB\n    ensure unique athlete_id constraint\n\n  create athlete_preferences\n    add athlete_id FK to athletes\n    add preference fields\n    ensure unique athlete_id constraint\n    add years_structured_training >= 0 check\n\n  create activities\n    add athlete_id FK to athletes\n    add nullable planned_session_id column only\n    add source enum and activity fields\n    ensure no avg or lap columns exist\n    add manual_entry semantic check\n    add non-manual fit_file_key check\n    add partial unique index on (athlete_id, external_id, source) where external_id is not null\n    add downstream query indexes\n\n  verify migration on fresh database\n```\n\n## Testing Requirements\n- Fresh database migration succeeds with no errors and no destructive recreation of `athlete_profiles`.\n- `athlete_profiles` contains the full Phase-1.2a schema fields and still enforces one record per `athlete_id`.\n- Existing Phase-1.1-style `athlete_profiles` rows remain valid after the extension migration.\n- `athlete_preferences` enforces one record per `athlete_id`.\n- Inserting `athlete_preferences.years_structured_training < 0` fails at the DB constraint layer.\n- `activities` has no `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or `lap_data` columns.\n- Inserting an `activities` row with `source = 'manual_entry'`, `calibration_eligible = false`, null load scores, and null `fit_file_key` succeeds.\n- Inserting an `activities` row with `source != 'manual_entry'` and null `fit_file_key` fails at the DB constraint layer.\n- Inserting duplicate `activities` rows with the same non-null `(athlete_id, external_id, source)` fails.\n- The `activities.planned_session_id` column exists as nullable, but its FK constraint is not required in Phase-1.2a because `planned_sessions` is created in Phase-1.2b.\n- No data is inserted into `athlete_profiles`, `athlete_preferences`, or `activities` by the Phase-1.2a migration.\n\n## Coder Handoff Notes\n- This is a schema-only plan. If a step requires service logic, endpoint logic, or data writes, it belongs to a later sub-phase.\n- The most important preservation rule is: do not drop and recreate `athlete_profiles`; extend the existing Phase-1.1 table.\n- Do not add raw or averaged workout fields to `Activity`. The table is a lean observation index, not a workout dashboard.\n- `fit_file_key` is a hard prerequisite for non-manual activities. Preserve the non-manual `fit_file_key IS NOT NULL` constraint even though FIT ingestion is implemented later.\n- `manual_entry` is a valid non-error state: `calibration_eligible = false`, null load scores, and null `fit_file_key`.\n- Because `planned_sessions` is created in Phase-1.2b, do not try to force an FK from `activities.planned_session_id` in Phase-1.2a. That FK must be added after `planned_sessions` exists.\n- Copy enum values exactly from the architecture contracts; downstream phases depend on these values being stable.\n- The migration must leave the database ready for Phase-1.3 onboarding, but it must not perform onboarding or create default preference records.\n",
  "filePath": "/home/ruimendes/projects/pheidipp/backend/docs/implementation/phase-1/phase-1-2a-p1-core-models.md"
}
```

**Output:**
```
Wrote file successfully.
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 5.3s)

_Thinking:_


Need refresh architecture after writing implementation plan. Update todo.


**Tool: todowrite**

**Input:**
```json
{
  "todos": [
    {
      "content": "Read Phase-1.2a release-plan sub-phase document and identify referenced contracts",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Retrieve architecture and vision contracts required by Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Verify relevant invariants and dependency impact for Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Write the implementation plan for Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Refresh architecture index after writing the implementation plan",
      "priority": "medium",
      "status": "in_progress"
    }
  ]
}
```

**Output:**
```
[
  {
    "content": "Read Phase-1.2a release-plan sub-phase document and identify referenced contracts",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Retrieve architecture and vision contracts required by Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Verify relevant invariants and dependency impact for Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Write the implementation plan for Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Refresh architecture index after writing the implementation plan",
    "status": "in_progress",
    "priority": "medium"
  }
]
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 12.6s)

_Thinking:_





**Tool: pheidipp-codebase-context_refresh_architecture**

**Input:**
```json
{
  "refresh_architecture": "{}"
}
```

**Output:**
```
ArchitectureTools refreshed in 0.62s
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 15.2s)

_Thinking:_


Need mark todo completed.


**Tool: todowrite**

**Input:**
```json
{
  "todos": [
    {
      "content": "Read Phase-1.2a release-plan sub-phase document and identify referenced contracts",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Retrieve architecture and vision contracts required by Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Verify relevant invariants and dependency impact for Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Write the implementation plan for Phase-1.2a",
      "priority": "high",
      "status": "completed"
    },
    {
      "content": "Refresh architecture index after writing the implementation plan",
      "priority": "medium",
      "status": "completed"
    }
  ]
}
```

**Output:**
```
[
  {
    "content": "Read Phase-1.2a release-plan sub-phase document and identify referenced contracts",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Retrieve architecture and vision contracts required by Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Verify relevant invariants and dependency impact for Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Write the implementation plan for Phase-1.2a",
    "status": "completed",
    "priority": "high"
  },
  {
    "content": "Refresh architecture index after writing the implementation plan",
    "status": "completed",
    "priority": "medium"
  }
]
```

---

## Assistant (P-Implementation-Architect · Nex r2-pro (openrouter) · 2.3s)

_Thinking:_





Generated and wrote the implementation plan for Phase-1.2a:

`docs/implementation/phase-1/phase-1-2a-p1-core-models.md`

I also refreshed the architecture index after writing it.

---

