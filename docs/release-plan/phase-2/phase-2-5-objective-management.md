# Phase 2 — Objective Management & Updates
## Sub-Phase ID: Phase-2.5

## Objective
Implement the objective update pipeline that evaluates session execution against planned objectives and narrates progress. This completes the post-workout analysis by reporting directional movement on relevant objectives like "threshold pace," "zone discipline," and "recovery patterns."

## Challenge Notes
Objectives are evaluated from `ExecutionObservation.coaching_observations` and comparable session insights. The key insight from vision is that recurring patterns across sessions become coaching objectives — this phase enables pattern detection and objective progress tracking.

**Key decision:** Objective updates happen in a separate service (`ObjectiveUpdateService`) that runs before the `PostWorkoutAgent`. This keeps agent context clean and ensures objective evaluation is deterministic, not LLM-derived.

**Simplifications:**
- Initial objectives are coaching-evaluated, not athlete-defined
- Pattern detection uses execution observations only (no broader trend analysis)
- Longitudinal aggregation deferred (will come with more session history)

## Capabilities Delivered
- `ObjectiveUpdateService.evaluate_post_session()` evaluates objectives after execution analysis
- `intent_compliance[]` assessed for target adherence
- `coaching_observations` pattern flags contribute to objective evidence
- `objective_updates[]` array provided to `PostWorkoutAgent` context
- Directional movement: better, worse, unchanged
- Milestone detection when objective reaches 'achieved' state

## Architectural Contracts Required
- `02-computations/objective-management.md`
- `01-entities/execution-observation.md`
- `01-entities/training-goal.md`
- `03-agents/post-workout-agent.md`

## Vision References Required
- `coach/post-workout.md` — objective progress requirement (third paragraph)
- `twin/adaptation-signature.md` — long-term adaptation yield per stimulus

## Upstream Dependencies
- Phase-2.3 — TwinState shows updated `metric_confidence` for objective evaluation context
- Phase-1.6 — PostWorkoutAgent exists and receives context
- Phase-2.1 — Calibration-eligible activities provide threshold data for objective evaluation

## Downstream Enablement
- Future phases — Adaptation signature learning uses objective trend data
- Future phases — Plan generation adjusts targets based on objective progress

## Invariants To Preserve
- Objective direction is computed by Python service, not LLM
- Evidence from execution observations never fabricated
- Milestone detection triggers from actual pattern change, not arbitrary thresholds
- Objective updates only evaluate objectives relevant to that session type
- If `objective_updates = []`, paragraph 3 focuses on plan position (agent constraint)

## Exit Gate
- After a calibration-eligible threshold session, `objective_updates[]` includes entry for threshold pace objective with `direction_of_change` and `evidence` fields populated.
- When threshold pace improves, `direction_of_change = 'better'` with evidence like "LT2 HR held steady at target throughout session."
- When zone encroachment occurs, `direction_of_change = 'worse'` with evidence logged.
- Post-workout message paragraph 3 narrates objective movement when present, or plan context when absent.
- Milestone detection logs when objective achieves target state for first time.