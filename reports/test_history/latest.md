date: 2026-07-26T16:41:00Z
plan: GAP-PHASE-1-TESTS
execution_group: feature
total: 48
passed: 36
failed: 12
skipped: 0
duration_seconds: 127
failures:
  - test: test_training_goal_plan_db.py::TestWeeklyPlanUniquePlanWeek::test_duplicate_plan_week_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_training_goal_plan_db.py::TestCheckpointUniquePlannedSession::test_duplicate_planned_session_id_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestGeneratedWorkoutUniquePlanDate::test_duplicate_plan_date_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestGeneratedWorkoutTargetsCheck::test_theoretical_targets_not_object_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestGeneratedWorkoutTargetsCheck::test_adjusted_targets_null_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestGeneratedWorkoutRecoveryModifierCheck::test_invalid_recovery_modifier_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestWorkoutStepUniqueWorkoutOrder::test_duplicate_step_order_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestWorkoutStepPhysiologicalIntentNotNull::test_null_physiological_intent_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestWorkoutStepStepOrderCheck::test_step_order_zero_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestWorkoutStepDescriptionCheck::test_empty_description_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestWorkoutStepDurationSecondsCheck::test_negative_duration_raises_integrity_error
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
  - test: test_coaching_workout_db.py::TestWorkoutStepDurationSecondsCheck::test_null_duration_succeeds
    error: "TypeError: 'athlete_id' is an invalid keyword argument for TrainingPlan"
    root_cause: RC1
