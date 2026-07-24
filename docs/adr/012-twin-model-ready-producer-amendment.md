---
id: ADR-012
status: accepted
tags: [events, onboarding, twin]
supersedes: ~
superseded-by: ~
---

# ADR 012: Twin Model Ready Event Producer Amendment

## Rules
**Producer Attribution**: `twin_model_ready` is produced by `OnboardingService` (via `TwinBootstrapService`) after the bootstrap TwinState insert.
**Trigger Timing**: The event fires immediately after onboarding completes for all tiers (1, 2, and 3).
**Tier 1 Plan Regeneration**: For Tier 1 athletes, plan refinement after historical ingestion is handled by `twin_confidence_upgraded`, not by deferring `twin_model_ready`.
**Consumer Wiring**: `PlanGenerationService.generate()` is triggered by `twin_model_ready`; `FirstMessageAgent` is triggered by `training_plan_generated`.

## Decision
The `twin_model_ready` event producer is amended from `TwinRecalibrationService` to `OnboardingService`, and the event fires immediately after the bootstrap TwinState insert for all onboarding tiers. This aligns the architecture catalogue with the implemented behavior and ensures all athletes receive an initial plan at onboarding while maintaining the ability to refine it as more data arrives via the existing `twin_confidence_upgraded` → plan regeneration path.

## Rationale
- **Immediate value delivery**: Athletes receive a plan immediately after onboarding, establishing the coaching relationship without delay. Waiting for "sufficient data" would leave Tier 3 athletes without a plan for days or weeks.
- **Existing regeneration mechanism**: The `twin_confidence_upgraded` event already handles plan regeneration when confidence improves, making a deferred `twin_model_ready` redundant for Tier 1 athletes.
- **Simplicity**: Single producer (`OnboardingService`) and single trigger point (bootstrap) is easier to reason about than tier-specific firing logic.
- **Consistency with implemented code**: The shipped Phase 2.7 Batch 3 code already fires `twin_model_ready` from `OnboardingService`; correcting the architecture to match is the appropriate fix.
- **Clear separation of concerns**: `twin_model_ready` signals "the twin exists and a plan can be generated"; `twin_confidence_upgraded` signals "the twin has improved and the plan should be regenerated."

## Alternatives Rejected
| Option | Why Rejected |
|---|---|
| Path A (TwinRecalibrationService producer with confidence gate) | Would delay plan generation for Tier 3 athletes until their first activity recalibrates the twin, harming time-to-value; adds complexity to coordinate producer across services. |
| Path C (Consumer-side confidence gate) | Would allow the event to fire but defer plan generation, creating confusing state where the event exists but no plan is generated; violates the principle that events should represent actionable state. |

## Tradeoffs
- **Pro**: All athletes receive immediate coaching value at onboarding.
- **Pro**: Simpler producer/consumer wiring with single trigger point.
- **Pro**: Aligns architecture with shipped implementation.
- **Con**: Tier 1 athletes receive a plan based on questionnaire-only data initially, which may be superseded after historical import.
- **Con**: The "sufficient data" language in the original catalogue is lost; the event now fires on existence, not quality.

## Cross-References
[ADR-004: Transactional Outbox for Event Persistence](./004-transactional-outbox-for-event-persistence.md) — defines the outbox pattern used for event publication
[ADR-011: Confidence Monotonicity Ratchet Location](./011-confidence-monotonicity-ratchet-location.md) — defines confidence level thresholds for `twin_confidence_upgraded`