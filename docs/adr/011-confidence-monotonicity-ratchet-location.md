---
id: ADR-011
status: accepted
tags: [confidence, twin-state, physiology, monotonicity]
supersedes: ~
superseded-by: ~
---

# ADR 011: Confidence Monotonicity Ratchet Lives in TwinRecalibrationService

## Rules
**Per-metric ratchet in P3**: The monotonic confidence ratchet (`max(stored_level, computed_level)` per metric) is enforced in `TwinRecalibrationService` (Plan P3), not in `PhysiologyUpdateService` (Plan P2).
**P2 outputs computed level only**: `PhysiologyUpdateService` returns the raw `metric_confidence` computed from current `prior_weight` — this is the "computed level" input to P3, not the final stored value.
**P3 reads previous TwinState**: `TwinRecalibrationService` reads the previous TwinState's `metric_confidence` via `TwinStateRepository.get_latest` and applies `max()` per metric before inserting the new TwinState.
**No TwinState access in P2**: `PhysiologyUpdateService` must not depend on `TwinStateRepository` — the ratchet is a TwinState-level concern, not a physiology-level concern.
**Global and per-metric both ratcheted**: The ratchet applies to both `confidence_level` (global) and every key in `metric_confidence` (per-metric) — both use `max(previous, computed)`.

## Decision
The confidence monotonicity ratchet — the rule that confidence levels never decrease even when `prior_weight` decays below a threshold — is enforced in `TwinRecalibrationService` (Plan P3), not in `PhysiologyUpdateService` (Plan P2). P2 computes the raw confidence level from current `prior_weight` and returns it as part of `PhysiologyUpdateResult`; P3 reads the previous TwinState's stored confidence and applies `max(stored_level, computed_level)` per metric before writing the new TwinState. This keeps the ratchet in the system that owns TwinState history and avoids coupling the physiology update service to twin state records.

## Rationale
- `metric_confidence` is an inline snapshot field on `TwinState` (append-only). The "highest confidence ever achieved" is a historical aggregate that requires reading previous TwinState records — `AthletePhysiology` does not store historical confidence levels, only the current decaying `prior_weight`.
- `TwinRecalibrationService` already depends on `TwinStateRepository` and already reads the previous TwinState via `get_latest` for `confidence_level` ratcheting. Extending the same ratchet to per-metric `metric_confidence` is a natural extension of existing logic, not a new coupling.
- `PhysiologyUpdateService` has no `TwinStateRepository` dependency. Adding one to enforce the ratchet would cross the ownership boundary between the physiology update system (operational current state) and the twin state system (historical audit trail).
- The architecture's separation of concerns is explicit: `AthletePhysiology` is mutable current-state (decays), `TwinState` is immutable historical (ratchets). The ratchet is inherently a historical-layer operation.
- P2's `confidence_transitions` output (LOW→MEDIUM, MEDIUM→HIGH within a single call) remains useful for firing `twin_confidence_upgraded` — it detects whether a transition occurred in this update, which P3 uses for event firing. The ratchet is orthogonal: it prevents decay-driven downgrades across calls.

## Alternatives Rejected
| Option | Why Rejected |
|--------|-------------|
| Ratchet in P2 (`PhysiologyUpdateService`) | P2 has no `TwinStateRepository` and no access to previous TwinState records; adding it couples the physiology service to twin history, violating the ownership boundary. |
| Ratchet in a shared helper called by both P2 and P3 | P2 cannot contribute to the ratchet without TwinState access; a shared helper that only P3 calls is just P3 logic with indirection. |
| Accept decay-driven downgrade (no ratchet) | The architecture explicitly states "Confidence ratchets upward only. It does not decrease even if the athlete stops training" (`confidence-model.md`). Rejecting the ratchet violates an architecture invariant. |
| Store highest-achieved level on `AthletePhysiology` | `AthletePhysiology` is a mutable current-state entity; adding a `highest_confidence` field would duplicate information already derivable from TwinState history and create a second source of truth for confidence levels. |

## Tradeoffs
- **Pro**: Keeps the ratchet in the system that owns TwinState history — no new coupling.
- **Pro**: P2 remains a pure physiology computation service — testable without TwinState fixtures.
- **Pro**: The ratchet logic is centralized in one place (`TwinRecalibrationService`), not split across two services.
- **Con**: P2's `PhysiologyUpdateResult.metric_confidence` is not the final stored value — a consumer that reads it directly (without P3's ratchet) could see a lower level than the previous TwinState. This is acceptable because the only consumer is P3.
- **Con**: If a future service calls P2 without P3 (e.g., a read-only physiology endpoint that returns confidence), it would return the raw computed level, not the ratcheted level. Such a service would need to apply its own ratchet or read from TwinState instead.

## Compliance
```python
# Compliant — P3 applies per-metric ratchet
async def recalibrate_for_calibration(self, athlete_id, activity_id, physiology_result):
    previous = await self.twin_states.get_latest(athlete_id)
    computed_metric_confidence = _derive_metric_confidence(physiology_result.physiology)

    if previous and previous.metric_confidence:
        metric_confidence = {
            k: _max_level(previous.metric_confidence.get(k), computed_metric_confidence.get(k))
            for k in computed_metric_confidence
        }
    else:
        metric_confidence = computed_metric_confidence

    # confidence_level ratchet (already specified in P3 plan)
    computed_level = _derive_confidence_level(physiology_result.physiology)
    old_level = previous.confidence_level if previous else TwinConfidenceLevel.LOW
    confidence_level = _max_level(old_level, computed_level)
```

```python
# Non-compliant — P2 tries to ratchet without TwinState access
async def apply_observations(self, athlete_id, observations):
    # ... bayesian update ...
    new_confidence = _compute_metric_confidence(physiology)
    # WRONG: P2 has no access to previous TwinState to enforce the ratchet
    previous = await self.twin_states.get_latest(athlete_id)  # no such dependency
    metric_confidence = {
        k: max(previous.metric_confidence[k], new_confidence[k])
        for k in new_confidence
    }
```

## Cross-References
- [ADR-004: Transactional Outbox for Event Persistence](./004-transactional-outbox-for-event-persistence.md) — event ordering within the `threshold_detection` transaction: `physiology_updated` (P2) → `twin_recalibrated` (P3) → `twin_confidence_upgraded` (P3)
- `00-foundations/confidence-model.md` — "Confidence Does Not Decrease" section: the invariant this ADR implements
- `01-entities/twin-state.md` — Invariant #4: `confidence_level` recomputed at each snapshot; `metric_confidence` as inline snapshot