# Pheidipp Release Plan — Phase 1: Foundation

## Overview

Phase 1 establishes the complete foundational infrastructure of the Pheidipp coaching platform. An athlete can register, complete onboarding, receive a bootstrapped twin (Tier 3, LOW confidence, questionnaire-only), see their training plan, receive their first coach message and daily workout, and upload a FIT file to receive post-workout analysis.

## Target Outcome at End of Phase 1

An athlete can:
1. Register and log in with email/password
2. Complete onboarding (questionnaire → goal definition → twin bootstrap)
3. See their training plan with phase arc and weekly structure
4. Receive a first coach message that references their specific data
5. See today's workout with targets appropriate to their data tier
6. Upload a FIT file and receive post-workout analysis with updated fitness/fatigue

## Sub-Phases

### Phase-1.1 — Email/Password Authentication
- **ID:** Phase-1.1
- **Objective:** Secure token-based authentication (JWT), registration, login, refresh, logout
- **Key Entities:** `Athlete`, `AthleteAuth`
- **File:** `phase-1/phase-1-1-email-password-auth.md`

### Phase-1.2a — Core Models: Profile, Preferences, Activity
- **ID:** Phase-1.2a
- **Objective:** Schema for athlete profile, training preferences, and lean activity index
- **Key Entities:** `AthleteProfile`, `AthletePreferences`, `Activity`
- **File:** `phase-1/phase-1-2a-profile-preferences-activity.md`

### Phase-1.2b — Core Models: Plan & Sessions
- **ID:** Phase-1.2b
- **Objective:** Schema for training plan hierarchy and checkpoint scheduling
- **Key Entities:** `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, `WeeklySession`, `PlannedSession`, `Checkpoint`
- **File:** `phase-1/phase-1-2b-plan-sessions.md`

### Phase-1.2c — Core Models: Twin, Fitness, Coaching, Workouts
- **ID:** Phase-1.2c
- **Objective:** Schema for twin snapshots, fitness/physiology state, coaching messages, and workout structure
- **Key Entities:** `TwinState`, `AthleteFitness`, `AthletePhysiology`, `CoachingMessage`, `GenerationEvent`, `GeneratedWorkout`, `WorkoutStep`
- **File:** `phase-1/phase-1-2c-twin-fitness-coaching-workouts.md`

### Phase-1.3 — Onboarding & Twin Bootstrap
- **ID:** Phase-1.3
- **Objective:** Atomic onboarding transaction: questionnaire → `AthleteProfile` + `AthletePreferences` + `TrainingGoal` + `AthletePhysiology` + `AthleteFitness` + `TwinState`
- **Key Entities:** All of 1.2a, 1.2b, 1.2c
- **File:** `phase-1/phase-1-3-onboarding-twin-bootstrap.md`

### Phase-1.4 — Plan Generation
- **ID:** Phase-1.4
- **Objective:** Pure-Python generation of complete training plan: `TrainingPlan` → `WeeklyPlan` → `PlannedSession` + `Checkpoint`
- **Key Entities:** `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, `PlannedSession`, `Checkpoint`
- **File:** `phase-1/phase-1-4-plan-generation.md`

### Phase-1.5a — First Coach Message
- **ID:** Phase-1.5a
- **Objective:** First coach message triggered after onboarding. Four paragraphs, Tier 3 language (LOW confidence)
- **Key Entities:** `CoachingMessage`, `GenerationEvent`
- **File:** `phase-1/phase-1-5a-first-coach-message.md`

### Phase-1.5b — Workout Generation
- **ID:** Phase-1.5b
- **Objective:** Day-of workout generation with `WorkoutStep`s and targets appropriate to data tier
- **Key Entities:** `GeneratedWorkout`, `WorkoutStep`
- **File:** `phase-1/phase-1-5b-workout-generation.md`

### Phase-1.6 — Simple FIT Import & Post-Workout
- **ID:** Phase-1.6
- **Objective:** FIT file upload, HR-based load computation, `AthleteFitness` update, post-workout coach message
- **Key Entities:** `Activity`, `AthleteFitness`, `TwinState`, `CoachingMessage`, `GenerationEvent`
- **File:** `phase-1/phase-1-6-simple-fit-import-post-workout.md`

## Scope Inclusions
- Email/password authentication only (OAuth deferred)
- `race_event` and `target_performance` goal types only (`fitness_improvement`, `_started`, `maintenance`, `recovery` deferred)
- Tier 3 bootstrap (questionnaire only, LOW confidence, no historical data, no peer matching)
- Heuristic load computation (not threshold-referenced)
- HR data only from FIT files (no power, GPS, RR intervals yet)
- No calibration, no threshold detection, no segmentation, no `ExecutionObservation`
- No wellness, weather, or cycle modifiers on targets
- Object storage schema defined in 1.2 but first runtime use in 1.6

## Scope Exclusions
- OAuth (Google, Strava, etc.)
- `fitness_improvement`, `maintenance`, `recovery` goal types
- Auto-sync from intervals.icu, Garmin, etc. (Phase 2)
- Calibration and threshold detection (Phase 2)
- Segmentation, `ExecutionObservation`, rep-level analysis (Phase 4-5)
- Wellness, weather, cycle modifiers (Phase 3)
- RawSensorStream and full signal cleaning pipeline (Phase 5)
- Structured workout upgrades (Phase 2c builds on 1.5b)
- Objectives system (Phase 4c)
- Session lifecycle (skip, miss, redistribute) (Phase 4d)
- Workout library (Phase 4d)
- Comparable sessions (Phase 4b)
- Race prediction (Phase 4g)
- Proactive coach messages (Phase 4e)
- HMM segmentation, personalised models (Phase 6)

