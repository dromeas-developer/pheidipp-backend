# Test Scenarios — Phase 1 Gap Analysis — Batch 4: Plan Generation

## Source: docs/implementation/phase-1/gap-analysis-phase-1/overview.md
## Sub-Phases Covered: 1.4 (Plan Generation)

---

## Step 1 — Plan Generation Entry & Goal Type Validation

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | race_event plan generated successfully | Athlete with active `TrainingGoal(goal_type=RACE_EVENT, goal_event_type=MARATHON, goal_event_date=2026-12-06)`, `TwinState` exists, `AthletePreferences` exist | `PlanGenerationResult` with `TrainingPlan` (status=ACTIVE), `WeeklyPlan[]`, `WeeklySession[]`, `PlannedSession[]`, `Checkpoint[]`; `training_plan_generated` event in outbox | application-logic | db-session |
| 2 | target_performance plan generated successfully | Athlete with active `TrainingGoal(goal_type=TARGET_PERFORMANCE, target_distance_km=10.0, target_time_minutes=50)`, TwinState exists | `PlanGenerationResult` with full hierarchy; `goal_event_type` in event payload = "custom" | application-logic | db-session |
| 3 | Unsupported goal type rejected | `TrainingGoal(goal_type=FITNESS_IMPROVEMENT)` | `InvalidGoalTypeError("goal_type 'fitness_improvement' is not supported by plan generation")` | application-logic | none |
| 4 | No active TrainingGoal | Athlete with no active goal | `PlanGenerationError("no active training goal for athlete")` | application-logic | none |
| 5 | No TwinState | Athlete with active goal but no TwinState | `PlanGenerationError("no twin state available for athlete")` | application-logic | none |
| 6 | No AthletePreferences | Athlete with active goal + TwinState but no preferences | `PlanGenerationError("no athlete preferences available")` | application-logic | none |
| 7 | race_event missing goal_event_date | `TrainingGoal(goal_type=RACE_EVENT, goal_event_date=None)` | `PlanGenerationError("race_event requires goal_event_date and goal_event_type")` | application-logic | none |

## Step 2 — Plan Supersession

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 8 | Existing active plan superseded | Athlete has existing active `TrainingPlan`; generate new plan | Previous plan `superseded_at` set to now; new plan `status=ACTIVE`; `training_plan_generated` event payload includes `supersedes_plan_id` = previous plan's id | application-logic | db-session |
| 9 | Superseded plan not deleted | After supersession | Previous `TrainingPlan` row still exists in DB (never deleted); `superseded_at` is non-null | application-logic | db-session |
| 10 | PlannedSession retains old training_plan_id | After supersession | `PlannedSession` rows from the old plan retain the old `training_plan_id` (denormalized); queries for "current plan sessions" must join through `WeeklyPlan` | application-logic | db-session |

## Step 3 — Phase Proportions (Fixture F12)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 11 | 24-week race_event plan phase allocation | `total_weeks=24` | `allocate_race_event_phases(24)`: taper=2, race=1 (fixed per spec). flexible=21. Per spec proportions (40/30/15 of flexible): base≈8, threshold≈6, race_specific≈7 (exact allocation may round). Sum=8+6+7+2+1=24. Structural invariants: phase order [BASE, THRESHOLD, RACE_SPECIFIC, TAPER, RACE_WEEK]; base ≥ threshold ≥ race_specific; sum matches total_weeks. | application-logic | none |
| 12 | 16-week race_event plan phase allocation | `total_weeks=16` | flexible=13. Approx: base≈5, threshold≈4, race_specific≈4 (exact allocation may vary). Sum=5+4+4+2+1=16. Invariants: phase order correct, sum matches, taper=2, race_week=1. | application-logic | none |
| 13 | Short plan (≤3 weeks) falls back to taper + race week | `total_weeks=3` | Returns [TAPER(2), RACE_WEEK(1)] only — no base/threshold/race_specific phases | application-logic | none |
| 14 | Phase labels correct | `total_weeks=24` | Phase labels in order: AEROBIC_BASE, THRESHOLD_BUILD, SPECIFIC_ENDURANCE, TAPER, RACE_WEEK | application-logic | none |
| 15 | Phase specificity values | `total_weeks=24` | base=0.1, threshold=0.4, race_specific=0.7, taper=0.5, race_week=1.0 | application-logic | none |

## Step 4 — Training Length Gate (Fixture F14)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 16 | Marathon novice at threshold (20 weeks) | `weeks_until_goal=20`, `fitness_level=3`, `goal_event_type="marathon"`, `experience_level="novice"` (years<2) | `action="proceed"` (20 is not > 20) | application-logic | none |
| 17 | Marathon novice above threshold (21 weeks) | `weeks_until_goal=21`, `goal_event_type="marathon"`, `experience_level="novice"` | `action="propose_intermediate"`, `gate_reason="goal_too_far"` | application-logic | none |
| 18 | 5K experienced at threshold (16 weeks) | `weeks_until_goal=16`, `goal_event_type="5k"`, `experience_level="experienced"` (years>5) | `action="proceed"` (16 is not > 16) | application-logic | none |
| 19 | 5K experienced above threshold (17 weeks) | `weeks_until_goal=17`, `goal_event_type="5k"`, `experience_level="experienced"` | `action="propose_intermediate"` | application-logic | none |
| 20 | Ultra intermediate threshold (30 weeks) | `weeks_until_goal=30`, `goal_event_type="ultra"`, `experience_level="intermediate"` | `action="proceed"` (30 is not > 30) | application-logic | none |
| 21 | Short goal with low fitness | `weeks_until_goal=6`, `fitness_level=2`, `goal_event_type="marathon"` | `action="propose_shorter_goal"`, `gate_reason="fitness_insufficient_for_distance"` (weeks < 8 AND fitness_level <= 2) | application-logic | none |
| 22 | Short goal with adequate fitness proceeds | `weeks_until_goal=6`, `fitness_level=3`, `goal_event_type="5k"` | `action="proceed"` (weeks < 8 but fitness_level > 2) | application-logic | none |
| 23 | Unknown goal_event_type uses default threshold (24) | `goal_event_type="unknown_type"`, `experience_level="novice"` | Threshold = 24 (TRAINING_LENGTH_GATE_DEFAULT_WEEKS) | application-logic | none |

## Step 5 — Experience Level Derivation (Fixture F15)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 24 | Novice: years < 2 | `years_structured_training=1` | `"novice"` | application-logic | none |
| 25 | Intermediate boundary: years = 2 | `years_structured_training=2` | `"intermediate"` (2 <= 5) | application-logic | none |
| 26 | Intermediate boundary: years = 5 | `years_structured_training=5` | `"intermediate"` (5 <= 5) | application-logic | none |
| 27 | Experienced: years > 5 | `years_structured_training=6` | `"experienced"` | application-logic | none |
| 28 | Zero years | `years_structured_training=0` | `"novice"` | application-logic | none |

## Step 6 — Target Performance Gap Classification (Fixture F16)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 29 | Small gap (≤3%) | `gap_pct=2.0` | `"small"`, estimated weeks 4-6 | application-logic | none |
| 30 | Medium gap (3-8%) | `gap_pct=5.0` | `"medium"`, estimated weeks 6-10 | application-logic | none |
| 31 | Large gap (8-15%) | `gap_pct=12.0` | `"large"`, estimated weeks 10-16 | application-logic | none |
| 32 | Very large gap (>15%) | `gap_pct=20.0` | `"very_large"` → propose fitness_improvement | application-logic | none |
| 33 | Gap percentage computation | `current_estimate_min=50`, `target_time_min=53` | `gap_pct = ((53-50)/50)*100 = 6.0` → "medium" | application-logic | none |
| 34 | Negative gap (target faster than current) | `current_estimate_min=50`, `target_time_min=48` | `gap_pct = ((48-50)/50)*100 = -4.0` → negative gap (target already achieved or exceeded) | application-logic | none |

## Step 7 — Session Structure Rules

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 35 | No two consecutive quality sessions | Generated plan with `total_weeks=24` | For every pair of consecutive days with sessions, at least one is not in `QUALITY_SESSION_TYPES` {THRESHOLD, VO2MAX, TEMPO, LONG_RUN, MEDIUM_LONG_RUN, HILL_REPEATS, FARTLEK}; unless they share a `block_id` | application-logic | none |
| 36 | Long run followed by rest or recovery | Generated plan | Every `LONG_RUN` session is followed by a `REST` or `RECOVERY_RUN` session (or no session) on the next day | application-logic | none |
| 37 | Threshold sandwiched between easy days | Generated plan | Every `THRESHOLD` or `VO2MAX` session has an `EASY_RUN` or `REST` on both adjacent days | application-logic | none |
| 38 | Plan covers full duration with no gaps | Generated plan from `plan_start` to `goal_event_date` | Phase date ranges are non-overlapping, ordered, and cover the full range from `plan_start` to `goal_event_date` without gaps; every week from week 1 to `total_weeks` has a `WeeklyPlan` | application-logic | db-session |

## Step 8 — Checkpoint Scheduling

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 39 | Calibration checkpoint at phase transition with low confidence | `twin_metric_confidence={"lt2_hr": "low", "lt1_hr": "low", "cp": null}` | At least one `CALIBRATION` checkpoint scheduled at a phase transition | application-logic | none |
| 40 | Benchmark checkpoint at week 4 | `total_weeks >= 4` | One `BENCHMARK` checkpoint at week 4 (or last week if plan shorter) | application-logic | none |
| 41 | Progress review every 3-4 weeks | `total_weeks=24` | `PROGRESS_REVIEW` checkpoints at weeks 3, 7, 11, 15, 19 (cursor starts at 3, increments by 4, stops at total_weeks-2) | application-logic | none |
| 42 | Race simulation 2 weeks before goal | `total_weeks=24`, `goal_event_type="marathon"` | `RACE_SIMULATION` checkpoint at week 22 (total_weeks - 2) | application-logic | none |
| 43 | Checkpoint cannot be created retroactively | Inspect `CheckpointRepository` and `PlanGenerationService` | Checkpoints are only created during `_persist_full_plan`; no code path creates a Checkpoint after session completion | application-logic | none |
| 44 | Checkpoints sorted by week_number | `schedule_checkpoints(...)` output | Records sorted by `week_number` ascending | application-logic | none |

## Step 9 — Plan Generation Purity (No LLM, No External API)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 45 | PlanGenerationService makes no LLM calls | Generate plan for any valid athlete | No `GenerationEvent` rows created by plan generation; no `AsyncOpenAI` client instantiated; no HTTP calls to LiteLLM proxy | application-logic | none |
| 46 | PlanGenerationService makes no external API calls | Generate plan | No outbound HTTP requests (assert via mock or network spy) | application-logic | external-only (mock HTTP if spying) |