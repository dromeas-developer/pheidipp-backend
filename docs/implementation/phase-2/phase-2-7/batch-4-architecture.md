# Architecture Documentation Updates — Phase 2.7 — Batch 4: Outbox Publisher Layering Fix

> **Status: APPLIED.** Every change in this handoff was applied by
> `p-vision-and-architect-author` as part of the ADR-013 (Path B)
> resolution to the Architecture Delta Proposal at
> `reports/phase-2-7_architecture-delta_outbox-publisher-layer.md`.
> This file exists for traceability — the coder never loads it.
> See the batch BRD (`batch-4-outbox-publisher-layer-fix.md`) for the
> coder-side scope.

## Triggering finding

`reports/phase-2-7_validation.md` — Layer 3 DEVIATION + Stack-Truth CRITICAL:
the Phase 2.7 Batch 2 plan prescribed a `worker → repository` direct access
in the `outbox_publisher` procrastinate task, violating ADR-001
(`WorkerIntegration`, `RepositoryAccess`). The coder followed the plan
faithfully; the defect was in the plan. The Architecture Delta Proposal
escalated the decision; the Architecture Author chose Path B — introduce a
named `OutboxPublisherService` ownership boundary between the worker and the
outbox repository. The fix is delivered as Phase 2.7 Batch 4 (see
`batch-4-outbox-publisher-layer-fix.md`); the Batch 2 BRD is frozen at its
shipped state.

## Permissioning ADR

### `docs/adr/013-outbox-publisher-service-ownership.md`
- NEW ADR (status: `accepted`), written by `p-vision-and-architect-author`
- **Rules:** `OutboxPublisherService` owns `publish_pending(limit)`; infrastructure-plumbing worker tasks are NOT an exception to ADR-001; `OutboxPublisherService` creates its own `AsyncSession` internally
- **Decision:** Separate `EventPublisher` (producer-side transaction) from `OutboxPublisherService` (publish-side status transition)
- **Cross-references:** ADR-001 (Layer Architecture), ADR-004 (Transactional Outbox)

## Affected architecture documents

### `docs/architecture/04-platform/system-event.md`

#### `## Mutation Rules`
- ADD publish-side ownership note under the existing Layer | Read | Write | Delete table:
  "The Service-tier write applies to two distinct services: `EventPublisher` owns the producer-side transaction (event + outbox insertion together with domain state), while `OutboxPublisherService` owns the publish-side transaction (status transition from `pending` to `published`). See ADR-013."

#### `## Runtime Flow`
- UPDATE mermaid sequence diagram participants to `Service`, `DB`, `OutboxPublisherService`, `PublisherTask`. Remove the generic `Publisher` participant.
- UPDATE the diagram's arrows:
  - `PublisherTask ->> OutboxPublisherService: publish_pending(limit)`
  - `OutboxPublisherService ->> DB: SELECT pending rows ORDER BY created_at LIMIT 100`
  - `loop for each pending row: OutboxPublisherService ->> DB: UPDATE outbox(status='published', published_at)`
  - `OutboxPublisherService ->> DB: COMMIT`
- UPDATE the "Current implementation" paragraph: name `OutboxPublisherService` invoked by the procrastinate periodic task `outbox_publisher` in `app/worker/app.py`.
- UPDATE the "Future bus insertion point" block: the chokepoint for external delivery is `OutboxPublisherService` (not "the publisher task"); injection / push-after-`mark_published` / ack-reflection steps reworded to name `OutboxPublisherService`.
- KEEP the legitimate future-option Redis mentions (e.g., "Future external consumers (Kafka, NATS, Redis) attach at the documented insertion point" and "Redis/Celery remains documented as a future migration option if queue contention warrants it"). These are NOT stale references — they describe future external consumers / upgrade paths, not the current publication target. Removing them would obscure the documented bus-insertion-point semantics.

#### `## Failure Semantics`
- UPDATE "Adding a bus (Kafka, NATS, Redis) is a localized change to `OutboxPublisherService`" (previously "to the publisher task").

#### `## Performance Constraints`
- UPDATE publisher-reads sentence: "`OutboxPublisherService` invoked by procrastinate periodic task, default every 15 seconds" (previously "procrastinate periodic task, default every 15 seconds").

#### `## Events → Consumed` / `## Idempotency` / `## Implementation Notes`
- Confirm each prose mention of the publisher is consistent with the new `OutboxPublisherService` boundary. No contract change; terminology alignment only.

## Cross-references added

- `system-event.md` `## Mutation Rules` → ADR-013 reference in the new publish-side ownership note
- `docs/adr/013-outbox-publisher-service-ownership.md` `## Cross-References` → ADR-001 and ADR-004 pointers

## Implementation plan consistency (per Implementation Architect post-ADR cleanup)

- `docs/implementation/phase-2/phase-2-7/batch-2-outbox-publisher.md` — **frozen at its shipped state** (`git` ref `cef0f5f`). The coder does not diff or re-edit this file; Batch 2's Step 2 prose still records the original worker → repository prescription, and the Layer 3 / Stack-Truth CRITICAL validator finding remains referenced as the rationale for Batch 4.
- `docs/implementation/phase-2/phase-2-7/batch-4-outbox-publisher-layer-fix.md` — NEW BRD carrying the ADR-013 Path B fix as a self-contained delta. Preconditions assume Batches 1–3 complete. Scope confines the change to `app/services/outbox_publisher_service.py` (NEW), `app/worker/app.py` (EXISTING — body re-routed), `app/services/__init__.py` (registration added).
- `docs/implementation/phase-2/phase-2-7/batch-4-outbox-publisher-layer-fix-tests.md` — NEW test-scenario companion. Includes the worker → repository layer-skip regression guard (Scenarios 13–15) plus regression-only re-runs of Batch 2's observable-behaviour scenarios against the re-routed implementation (Scenarios 19–25), so a single-pass validator can confirm layering is corrected AND observable behaviour is preserved.
- `docs/implementation/phase-2/phase-2-7/overview.md` — Scope adds a "Outbox publisher layer-fix (Batch 4)" bullet; Testing Requirements adds a Batch 4 entry; Architecture Contracts references ADR-013 with the `DECISION` label; Cross-Validation Summary RC4 row notes the fix is delivered as Batch 4 (not as an in-place Batch 2 rewrite); ADRs Written section records ADR-013.

## Verification (Architecture Author's responsibility — out of coder scope)

- Runtime Flow mermaid diagram renders with the four explicit participants and no `Publisher` or `MessageBus` participant.
- Mutation Rules table shows the publish-side ownership note citing ADR-013.
- No `system-event.md` reference describes the current publication target as Redis; legitimate future-option Redis mentions remain in place and are not violations.
- ADR-013 is linked from `system-event.md` Mutation Rules, and `system-event.md` is linked from ADR-013 Cross-References (bidirectional traceability).