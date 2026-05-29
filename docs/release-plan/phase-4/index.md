# Phase 4 — Coaching Intelligence
*Execution analysis, objectives, session lifecycle, comparable sessions, race prediction*

## Hypothesis

After 8+ weeks of real data, does the coaching feel materially more personalised
and actionable? The coach should reference specific execution patterns from the
FIT file, track progress on named objectives, and manage the training plan
dynamically as life intervenes.

## Twin State at Completion

Layer 5 (Execution Patterns) beginning — session shape classification and basic
execution signals available. Full coaching layer complete: objectives seeded and
updating, comparable session identification active, race prediction live.

## Sub-Phases

| Sub-phase | Title | Key deliverable |
|---|---|---|
| 4a | ExecutionObservation | FIT-derived execution analysis, session shape classification |
| 4b | Comparable Session Identification | ComparableSessionService, historical references in coach messages |
| 4c | Objectives System | Objective + ObjectiveUpdate models, seeding, daily integration |
| 4d | Session Lifecycle | Skip, miss, redistribute, WorkoutLibrary, substitution flow |
| 4e | Proactive Coach Messages | Wellness alerts, phase transitions, plan notifications |
| 4f | Cycle Personalisation | Individual cycle length learning, personalised phase adjustments |
| 4g | Race Prediction | RacePrediction model, baseline formula, course and weather adjustment |

## Done Criteria

- Post-workout analysis references specific rep-level execution data from the FIT
  file — not just duration and HR zone compliance.
- Coach message references a comparable previous session with a specific observation.
- After seeding, an athlete has 3-5 active objectives. After a relevant session the
  objective shows directional movement in `ObjectiveUpdate`.
- An athlete skipping a session sees a substitution flow, selects an alternative,
  and the plan updates correctly.
- Race prediction is visible, non-null, and changes after a significant training block.

## Go / No-Go for Phase 5

- `ExecutionObservation` is created for every calibration-eligible activity.
- Comparable session identification returns null gracefully when no match meets
  the 0.50 similarity threshold — coach message does not fabricate a reference.
- Session lifecycle state machine handles all transitions without orphan records.
- `RacePrediction` suppressed at LOW confidence — not shown to athletes without
  sufficient threshold data.
