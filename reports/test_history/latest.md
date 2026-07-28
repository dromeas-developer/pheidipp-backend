date: 2026-07-28T00:01:18Z
plan: GAP-PHASE-1-TESTS
execution_group: feature
total: 137
passed: 118
failed: 19
skipped: 0
duration_seconds: 175
failures:
  - test: test_tier6_unhandled_combination_falls_back
    error: assert TIER_2 == TIER_6 for (NONE, RUNNING_POWER_METER)
    root_cause: RC2
  - test: test_fitness_improvement_rejected
    error: error message format mismatch
    root_cause: RC1
  - test: test_maintenance_rejected
    error: error message format mismatch
    root_cause: RC1
  - test: test_recovery_rejected
    error: error message format mismatch
    root_cause: RC1
  - test: test_second_active_goal_raises_conflict
    error: duplicate key on athlete_preferences
    root_cause: RC4
  - test: test_generate_plan_defer_failure_does_not_break_onboarding
    error: RuntimeError not caught by service
    root_cause: RC5
  - test: test_failure_after_physiology_insert_rolls_back_all
    error: MissingGreenlet from monkeypatch pattern
    root_cause: RC6
  - test: test_failure_after_fitness_insert_rolls_back
    error: MissingGreenlet from monkeypatch pattern
    root_cause: RC6
  - test: test_failure_keeps_profile_state_unchanged
    error: MissingGreenlet from monkeypatch pattern
    root_cause: RC6
  - test: test_post_onboarding_201_returns_response
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_post_onboarding_409_when_already_complete
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_get_status_after_onboarding_returns_true
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_get_preferences_returns_after_onboarding
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_patch_preferences_merges_day_level
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_patch_preferences_updates_top_level
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_patch_preferences_rejects_unknown_field
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_get_twin_returns_bootstrap_state
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_get_twin_history_returns_after_onboarding
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
  - test: test_full_journey_register_to_get_twin
    error: WeeklyScheduleDayIn not JSON serializable
    root_cause: RC3
