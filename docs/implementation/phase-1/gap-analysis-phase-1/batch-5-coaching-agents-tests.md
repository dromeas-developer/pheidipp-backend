# Test Scenarios — Phase 1 Gap Analysis — Batch 5: Coaching Agents

## Source: docs/implementation/phase-1/gap-analysis-phase-1/overview.md
## Sub-Phases Covered: 1.5a (First Coach Message), 1.5b (Workout Generation)

---

## Step 1 — FirstMessageAgent: Idempotency & Singleton (POST /athletes/{id}/coach/first-message)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | First message generated successfully | Athlete with completed onboarding, TwinState, TrainingGoal, AthleteProfile, AthletePreferences; no existing first_message | `CoachingMessage` with `message_type=FIRST_MESSAGE`, non-empty `content`, `prompt_version` set, `twin_state_id` linked; `coaching_message_generated` event in outbox; `GenerationEvent` written with `success=true` | application-logic | external-only (mock LLM proxy) |
| 2 | Second call returns 409 without calling LLM | Athlete already has a `first_message` CoachingMessage | `FirstMessageAlreadyExistsError` (409); no LLM call made (assert no new `GenerationEvent`); `CoachingMessageRepository.get_existing_first_message` returns existing row | application-logic | external-only (mock LLM proxy — assert NOT called) |
| 3 | DB partial unique index enforces singleton | Attempt direct insert of second `first_message` row | `IntegrityError` from `uq_coaching_messages_athlete_first_message` partial unique index | database | db-session |

## Step 2 — FirstMessageAgent: Four-Paragraph Structure & Voice

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 4 | Message has exactly four paragraphs | Mock LLM proxy returns a 4-paragraph message | Parsed `content` has exactly 4 paragraphs (split on double-newline) | application-logic | external-only (mock LLM proxy) |
| 5 | Message has no bullets | Mock LLM returns content with bullet characters | Post-parse validation rejects (or strips) bullets; content has no `- `, `* `, or `•` line-starts | application-logic | external-only (mock LLM proxy) |
| 6 | Message has no headers | Mock LLM returns content with markdown headers | Content has no lines starting with `#` | application-logic | external-only (mock LLM proxy) |
| 7 | Message has no emojis | Mock LLM returns content with emojis | Content has no emoji characters | application-logic | external-only (mock LLM proxy) |
| 8 | Message references sport_background | `AthletePreferences.sport_background=TRIATHLON_BACKGROUND` | Paragraph 2 ("What Was Found") references the athlete's specific sport background | application-logic | external-only (mock LLM proxy) |
| 9 | Message references structural_risk_flag when applicable | `AthleteProfile.structural_risk_flag=True` | Paragraph 2 references the structural risk flag | application-logic | external-only (mock LLM proxy) |
| 10 | Message is not generic/templated | Two athletes with different backgrounds | Messages differ in content — not identical templates | application-logic | external-only (mock LLM proxy) |

## Step 3 — FirstMessageAgent: LLM Failure Handling

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 11 | LLM timeout writes GenerationEvent(success=false) | Mock LLM proxy raises timeout exception | `GenerationEvent` row written with `success=false`, `failure_reason` non-null (describes timeout); 503 returned to caller; no `CoachingMessage` created | application-logic | external-only (mock LLM proxy to raise) |
| 12 | LLM returns malformed response | Mock LLM proxy returns empty or unparseable content | `GenerationEvent(success=false)` written; 503 returned; no CoachingMessage with empty content (CHECK `length(content)>0` would fire if attempted) | application-logic | external-only (mock LLM proxy) |
| 13 | No silent LLM failures | Any LLM call path | Every LLM call — success or failure — results in exactly one `GenerationEvent` row; no code path skips the GenerationEvent write | application-logic | external-only (mock LLM proxy) |

## Step 4 — FirstMessageAgent: LLM Proxy Routing (ADR-007)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 14 | Agent constructs AsyncOpenAI with proxy base_url | Inspect `FirstMessageAgent` LLM client construction | Client is `AsyncOpenAI(base_url=settings.LITELLM_BASE_URL, api_key=settings.LITELLM_API_KEY)`; no direct provider SDK (no `anthropic`, `cohere`, `openai` provider-specific imports) | application-logic | none |
| 15 | Model name uses logical identifier | Inspect model name passed to LLM call | Model name is `<provider>/<model>` format (e.g. `cohere/command-a-plus`); proxy strips provider prefix when routing | application-logic | none |

## Step 5 — WorkoutGenerationAgent: Idempotency (GET /athletes/{id}/today, POST .../generate-workout)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 16 | Workout generated successfully | Athlete with PlannedSession for today, TwinState exists, no existing GeneratedWorkout for (session, date) | `GeneratedWorkout` with `theoretical_targets` (JSONB object), `adjusted_targets` (JSONB object, identical to theoretical at Phase 1), `recovery_modifier_level=GREEN`, `twin_state_id` linked; `WorkoutStep[]` with non-null `physiological_intent`; `workout_generated` event in outbox | application-logic | external-only (mock LLM proxy) |
| 17 | Second generation for same (session, date) returns existing | Call `generate` twice with same `(planned_session_id, generation_date)` | Second call returns the existing `GeneratedWorkout` (200, not 201); no LLM call made; no new `GenerationEvent`; `GeneratedWorkoutRepository.get_by_session_and_date` returns existing row | application-logic | external-only (mock LLM proxy — assert NOT called on second) |
| 18 | DB unique constraint enforces idempotency | Attempt direct insert of duplicate `(planned_session_id, generation_date)` | `IntegrityError` from `uq_generated_workouts_planned_session_generation_date` | database | db-session |

## Step 6 — WorkoutGenerationAgent: WorkoutStep Structure

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 19 | Every WorkoutStep has non-null physiological_intent | Generated workout with N steps | All N `WorkoutStep` rows have `physiological_intent` set to a valid `PhysiologicalIntent` enum value; warmup/cooldown/recovery steps = `RECOVERY`; work steps = derived from `SESSION_INTENT_MAP` | application-logic | external-only (mock LLM proxy) |
| 20 | WorkoutStep step_order unique and 1-indexed | Generated workout with N steps | `step_order` values are 1, 2, ..., N (no gaps, no duplicates) | database + application-logic | external-only (mock LLM proxy) |
| 21 | Threshold session produces correct step sequence | `PlannedSession.session_type=THRESHOLD` | Steps: warmup → low_aerobic → threshold (per rep) → recovery (between reps) → cooldown | application-logic | external-only (mock LLM proxy) |
| 22 | WorkoutStep description always non-empty | Any generated workout | Every `WorkoutStep.description` is a non-empty string | database (CHECK) + application-logic | external-only (mock LLM proxy) |

## Step 7 — WorkoutGenerationAgent: Target Type by Data Tier

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 23 | Tier 1-2: power primary, GAP secondary | `data_tier=TIER_1` or `TIER_2` | `WorkoutStep.target` contains `target_power_watts` as primary target; `target_gap_sec_per_km` as secondary | application-logic | external-only (mock LLM proxy) |
| 24 | Tier 3-4: GAP primary, HR zone secondary | `data_tier=TIER_3` or `TIER_4` | `WorkoutStep.target` contains `target_gap_sec_per_km` as primary; `target_hr_zone` as secondary | application-logic | external-only (mock LLM proxy) |
| 25 | Tier 5-6: description only, numeric targets null | `data_tier=TIER_5` or `TIER_6` | `WorkoutStep.target` has null numeric targets (`target_power_watts`, `target_gap_sec_per_km`, `target_hr_zone` all null); `description` is non-null and non-empty | application-logic | external-only (mock LLM proxy) |
| 26 | GAP values only — no raw pace | Any workout with pace targets | All pace values in `target` are `pace_sec_per_km` using GAP (grade-adjusted); no raw pace field exists | application-logic | external-only (mock LLM proxy) |

## Step 8 — WorkoutGenerationAgent: Two-Column Target Structure

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 27 | Both theoretical_targets and adjusted_targets written | Any workout generation | Both `theoretical_targets` and `adjusted_targets` are non-null JSONB objects; at Phase 1 they are identical (no wellness/weather modifiers) | database (CHECK) + application-logic | external-only (mock LLM proxy) |
| 28 | recovery_modifier_level defaults to GREEN | Any workout generation | `recovery_modifier_level=GREEN`, `recovery_modifier_reason=None` | application-logic | external-only (mock LLM proxy) |
| 29 | twin_state_id records generation version | Workout generated from TwinState T1; twin recalibrates to T2 after generation | `GeneratedWorkout.twin_state_id` still points to T1 (not retroactively updated to T2) | application-logic | external-only (mock LLM proxy) |

## Step 9 — WorkoutGenerationAgent: LLM Failure & GenerationEvent

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 30 | LLM failure writes GenerationEvent(success=false) | Mock LLM proxy raises exception | `GenerationEvent` with `success=false`, `failure_reason` non-null; 503 returned; no `GeneratedWorkout` or `WorkoutStep` created | application-logic | external-only (mock LLM proxy to raise) |
| 31 | GenerationEvent agent_name matches class name | Any agent LLM call | `GenerationEvent.agent_name` = `"WorkoutGenerationAgent"` (or `"FirstMessageAgent"` / `"PostWorkoutAgent"` for those agents) | application-logic | external-only (mock LLM proxy) |

## Step 10 — Context Budget Enforcement

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 32 | Context budget is a hard limit, not a target | Assembled context exceeds 5k tokens | `ContextBudgetService` truncates or rejects before the LLM call; the LLM call is never made with an oversized context | application-logic | external-only (mock LLM proxy) |
| 33 | Sparse data at LOW confidence handled gracefully | TwinState with many null fields (LOW confidence bootstrap) | Context assembly does not crash on null fields; budget stays within 3k-5k token range | application-logic | external-only (mock LLM proxy) |

## Step 11 — GET /athletes/{id}/coach/messages

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 34 | Messages returned ordered by generated_at desc | Athlete with 3 CoachingMessages at different timestamps | Response list ordered newest-first by `generated_at` | application-logic | db-session |
| 35 | Pagination with limit and offset | Athlete with 10 messages, `limit=5`, `offset=2` | Returns messages 3-7 (0-indexed offset 2, limit 5); `total` count = 10 | application-logic | db-session |