# Batch BRD: Phase 2.7 — Batch 4 — Outbox Publisher Layering Fix
## Source: docs/implementation/phase-2/phase-2-7/overview.md

> **Why this batch exists.** The Phase 2.7 validator
> (`reports/phase-2-7_validation.md` → Layer 3 DEVIATION + Stack-Truth
> CRITICAL) found that the Batch 2 BRD Step 2 prescribed a
> `worker → repository` direct access in the `outbox_publisher`
> procrastinate task, violating ADR-001 `WorkerIntegration` /
> `RepositoryAccess`. The coder followed the plan faithfully — the
> defect was in the plan, not the coder's work. ADR-013 (Path B)
> resolved the architecture question by introducing a named
> `OutboxPublisherService` ownership boundary between the worker and
> the outbox repository. **This batch delivers that fix.** The Batch 2
> BRD is frozen at its shipped state; the coder receives this delta as
> a self-contained BRD rather than being asked to diff-and-reconcile
> the in-place edits against what it already shipped. The Tier-1 work
> below is the layering correction only — the observable behaviour of
> the publisher task is identical before and after this batch.

## Batch Objective
Introduce `OutboxPublisherService` as the publish-side transaction owner for `system_event_outbox` status transitions per ADR-013 (Path B), and re-route the already-shipped `outbox_publisher` procrastinate task to call that service instead of constructing `SystemEventOutboxRepository` directly. After this batch, the transactional outbox pattern is layer-correct (`worker → service → repository` per ADR-001 + ADR-013) with no behavioural change from the Batch 2 shipped state.

## Preconditions
Batches 1–3 are complete; their Batch Success Criteria hold. Specifically, the coder has already shipped the Batch 2 implementation that this batch corrects:

- `app/repositories/system_event_outbox_repository.py` exists with `get_pending(limit)` and `mark_published` (or equivalent) methods — added by Batch 2 Step 1.
- `app/worker/app.py` registers the `outbox_publisher` procrastinate periodic task — added by Batch 2 Step 2 in its shipped form, which currently constructs `SystemEventOutboxRepository` directly, opens its own `AsyncSession`, calls `get_pending(limit=100)`, iterates `mark_published`, commits, and returns the transitioned count. **This batch re-routes that task through `OutboxPublisherService`; the repository, the model, and the archive-side methods are not modified.**
- The validator CRITICAL finding against the shipped Batch 2 layering is open. ADR-013 is `accepted`.

No DevOps prerequisites. No migration — this batch is a code-layer change only.

## Scope
- **NEW file `app/services/outbox_publisher_service.py`** — `OutboxPublisherService` with `async def publish_pending(self, limit: int) -> int` per ADR-013: opens its own `AsyncSession` internally, calls `SystemEventOutboxRepository.get_pending(limit)`, iterates `mark_published(event_id)` per row, commits, returns the count of rows transitioned.
- **MODIFY `app/worker/app.py`** — change the existing `outbox_publisher` task body to call `OutboxPublisherService.publish_pending(limit=...)` and own no business logic. The task's registration, periodic schedule, error handling at the task boundary, and return value are preserved verbatim. The worker MUST NOT construct `SystemEventOutboxRepository`, open its own `AsyncSession`, or call `mark_published` itself — ADR-001 `WorkerIntegration` + ADR-013 forbid it.
- **Register `OutboxPublisherService`** in `app/services/__init__.py` `__all__` so the worker import resolves the established service-registry pattern.

## Out Of Scope
- **No behavioural change to the publisher.** The observable output of the `outbox_publisher` task is identical to Batch 2's shipped state: same row transitions (pending → published), same idempotency semantics, same empty-queue and partial-batch handling, same "no new domain events produced", same "no `EventPublisher.publish()` invocation". This batch is a layering correction, not a behavioural change.
- **No modification to `SystemEventOutboxRepository`.** The existing `get_pending` and `mark_published` methods are unchanged — Batch 2 Step 1 already shipped them; this batch only re-routes the caller.
- **No modification to `EventPublisher`.** The producer-side write path is unchanged.
- **No modification to any file under `docs/architecture/` or `docs/adr/`.** `docs/architecture/04-platform/system-event.md` has already been updated by `p-vision-and-architect-author` as part of the ADR-013 resolution (Runtime Flow redrawn with `OutboxPublisherService` + `PublisherTask` participants, Mutation Rules publish-side ownership note added, Failure Semantics / Performance Constraints / Future Bus Insertion Point re-anchored, ADR-013 cross-reference added) — see `batch-4-architecture.md`. The coder MUST NOT touch architecture docs in this batch.
- **No migration.** No schema change. No hypertable change. No `CREATE EXTENSION`. The DB schema is untouched.
- **No external bus.** `OutboxPublisherService` is a status transitioner, not a message-bus publisher. Do not import or require Redis, NATS, Kafka, or any message bus client. The future-bus insertion point is documented in `system-event.md` but not implemented here.
- **Batches 1, 2, 3** are out of scope and frozen at their shipped state. Their Success Criteria already hold.

## Steps

### Step 1 — Create `OutboxPublisherService` with `publish_pending(limit)`

1. [OWNER: Coder] Create `app/services/outbox_publisher_service.py` exporting `OutboxPublisherService`. The class owns:
   - An `async def publish_pending(self, limit: int) -> int` method (signature mandated by ADR-013)
   - Internal session lifecycle — opens its own `AsyncSession` from `AsyncSessionLocal` (the existing session factory pattern); do not accept a session as a method argument or as constructor injection (ADR-013 `SessionOwnership`)
   - Imports `SystemEventOutboxRepository` and constructs it inside the service, scoped to the service's own session — the repository remains a repository-tier component; only the service is allowed to instantiate it (ADR-001 `RepositoryAccess`)
   - Calls `SystemEventOutboxRepository.get_pending(limit)` to fetch a batch of pending rows
   - Iterates `mark_published(event_id)` per row to transition status to `published` and stamp `published_at` — reuse the existing `mark_published` helper per Batch 2's shipped interface, do not reimplement or duplicate it (see Batch 2 Coder Notes "mark_published reuse")
   - Commits the transaction
   - Returns the count of transitioned rows
   - The service is a status transitioner — it MUST NOT import or call `EventPublisher.publish()`, MUST NOT produce new domain events, and MUST NOT import any message bus client (Redis, NATS, Kafka)
2. [OWNER: Coder] Register `OutboxPublisherService` in `app/services/__init__.py` `__all__` so the import resolves the established service-registry pattern used by the rest of the codebase.

### Step 2 — Re-route the `outbox_publisher` task to call `OutboxPublisherService`

3. [OWNER: Coder] Modify the existing `outbox_publisher` task in `app/worker/app.py` so its body calls `OutboxPublisherService.publish_pending(limit=OUTBOX_PUBLISHER_BATCH_SIZE)` and returns the count returned by the service. Preserve:
   - The procrastinate periodic schedule registration (Batch 2 Step 2 shipped the registration; do not change the cron/interval) — ADR-013 specifies "default every 15 seconds"; Batch 2's implementation landed at 15 seconds, which is inside the 10–30 second band and is preserved
   - The task's error handling at the task boundary (log + return the same diagnostic the shipped task returned on error)
   - The task's registered name in the procrastinate `App` namespace
   The worker MUST NOT construct `SystemEventOutboxRepository`, open its own `AsyncSession`, call `get_pending`, or call `mark_published`. That path is forbidden under ADR-001 `WorkerIntegration` and ADR-013 `OutboxPublisherService`. The worker owns only task registration, scheduling, and graceful exception handling; all transaction and repository access must go through `OutboxPublisherService`. This is a regression guard against the original Phase 2.7 validator CRITICAL finding — see the regression-guard test in `batch-4-outbox-publisher-layer-fix-tests.md` Scenario 1.

## Context Needed
Step 1:
  Primary:    `app/services/outbox_publisher_service.py` (new file — `OutboxPublisherService` contract per ADR-013), `docs/adr/013-outbox-publisher-service-ownership.md` (the permissioning ADR — Rules section names the exact `publish_pending(limit)` signature and forbids worker-side repository access), `app/repositories/system_event_outbox_repository.py` (existing `get_pending` and `mark_published` methods that the service will call — these are unchanged)
  Secondary:  `app/models/system_event.py` for `SystemEventOutbox` column names (`status`, `created_at`, `published_at`, `event_id`) the service's commit will stamp, an existing service in `app/services/` that owns its own `AsyncSession` as the pattern to mirror (e.g. the `OnboardingService` OpenOwnSession convention)
  Fallback:   `docs/architecture/04-platform/system-event.md` Mutation Rules (publish-side ownership note) and Runtime Flow (OutboxPublisherService + PublisherTask participants) for the architecture's authoritative description of the boundary
  Forbidden:  Do not modify `EventPublisher.publish()` — the producer-side write path is unchanged. Do not modify `SystemEventOutboxRepository` — `get_pending` and `mark_published` already exist; the service calls them, it does not modify them. Do not modify `SystemEventOutbox` model. Do not import any message bus client (Redis, NATS, Kafka).

Step 2:
  Primary:    `app/worker/app.py` (the existing `outbox_publisher` task body to be re-routed — preserves the procrastinate periodic schedule, error handling, and registered name verbatim), `app/services/outbox_publisher_service.py` (output of Step 1 — the service the worker will call), `docs/adr/013-outbox-publisher-service-ownership.md` (the ADR forbidding worker-side repository construction)
  Secondary:  `docs/adr/001-layer-architecture.md` (`WorkerIntegration` and `RepositoryAccess` rules — the base layer rule ADR-013 builds on)
  Fallback:   `docs/architecture/04-platform/system-event.md` Runtime Flow diagram showing the redrawn `PublisherTask` → `OutboxPublisherService` → `DB` sequence as the architecture's authoritative description of the corrected flow
  Forbidden:  Do not modify `EventPublisher.publish()` — the producer-side write path is unchanged. Do not modify any file under `docs/architecture/` — the `system-event.md` update is owned by `p-vision-and-architect-author` via `batch-4-architecture.md` (already applied). Do not construct `SystemEventOutboxRepository` inside the worker task — ADR-001 `WorkerIntegration` + ADR-013 forbid it; all repository access goes through `OutboxPublisherService`. Do not change the procrastinate periodic schedule interval (Batch 2 landed at 15s; preserve).

(This is everything relevant to the steps above. Primary items are fetched together in Pre-Flight Step 3; Secondary and Fallback are requested only on demand.)

## Batch Success Criteria
Batch 4 complete when:
- `OutboxPublisherService.publish_pending(limit: int) -> int` exists at `app/services/outbox_publisher_service.py`, opens its own `AsyncSession` internally, calls `SystemEventOutboxRepository.get_pending(limit)`, iterates `mark_published(event_id)` per row, commits, and returns the transitioned count
- `OutboxPublisherService` is registered in `app/services/__init__.py` `__all__`
- The procrastinate `outbox_publisher` task in `app/worker/app.py` calls `OutboxPublisherService.publish_pending(limit=...)` and does NOT construct `SystemEventOutboxRepository`, open its own `AsyncSession`, call `get_pending`, or call `mark_published` itself — `worker → service → repository` enforced per ADR-001 `WorkerIntegration` + ADR-013 `OutboxPublisherService`
- The procrastinate periodic schedule registration, the registered task name, and the task-level error handling from the shipped Batch 2 `outbox_publisher` task are preserved verbatim
- The observable behaviour from Batch 2's Success Criteria is preserved: running the publisher task transitions pending rows to `published` (`published_at` non-null where the model defines that field); idempotent (a second run on the same row set transitions 0 rows); handles an empty pending queue gracefully (returns 0, no error, no rows modified); handles a partial batch (`limit` rows transitioned, the rest stay `pending`; subsequent runs transition the rest); does not modify `EventPublisher.publish()` or any event-producing service; does not produce new domain events
- The batch's coder steps do not modify any file under `docs/architecture/` or `docs/adr/` — the `system-event.md` update is owned by `p-vision-and-architect-author` and is already applied via `batch-4-architecture.md`
- The full existing test suite passes — Batch 4 is a layering correction to net-new code paths already passed by Batch 2; no test logic changes are required for the batch's own correctness, only the additions named in `batch-4-outbox-publisher-layer-fix-tests.md`

## Relevant Architecture Contracts
- `docs/adr/013-outbox-publisher-service-ownership.md` — DECISION (`OutboxPublisherService` owns `publish_pending(limit)`; infrastructure-plumbing worker tasks are NOT an exception to ADR-001; `OutboxPublisherService` creates its own `AsyncSession` internally)
- `docs/adr/001-layer-architecture.md` — DEPENDS ON (`WorkerIntegration`: background jobs interact through the services layer; `RepositoryAccess`: repository access exclusively from services)
- `docs/adr/004-transactional-outbox-for-event-persistence.md` — DEPENDS ON (publication timing, idempotent consumer, atomicity preserved — this batch only changes which layer owns the publish-side transaction, not its transactional semantics)
- `04-platform/system-event.md` → Mutation Rules "Publish-side ownership note" naming `EventPublisher` (producer-side) and `OutboxPublisherService` (publish-side) — IMPLEMENTS (this batch delivers the `OutboxPublisherService` half)
- `04-platform/system-event.md` → Runtime Flow mermaid diagram with `PublisherTask` → `OutboxPublisherService` → `DB` sequence — IMPLEMENTS

## Relevant Invariants
- **Transactional outbox atomicity:** Event and outbox row are inserted in the same database transaction as the domain state change; rollback removes both. Publication occurs only after the producing transaction commits successfully. — `OutboxPublisherService` reads only `status='pending'` rows, which are only visible after the producing transaction has committed. The service's own commit transitions the status; this is a separate transaction from the producing one, which is correct — the service does not participate in the producing transaction. **Preserved across this batch:** the transactional region ownership moves from the worker to the service, but the transactional semantics (own-session, status='pending' filter, post-commit visibility) are identical.
- **Append-only tables remain append-only:** `OutboxPublisherService`'s status transition is the only UPDATE in the outbox system and applies to `system_event_outbox` only, which is NOT one of the append-only event-log tables. The append-only tables (`system_events`, `twin_states`, `raw_sensor_streams`, `physiology_measurements`, `generation_events`, `coaching_messages`) remain append-only — this batch does not introduce any UPDATE or DELETE path on them.
- **Layer architecture (non-negotiable):** `worker → services → repositories → models`. No layer skipping. ADR-001 `WorkerIntegration` and `RepositoryAccess` are satisfied when the worker calls the service and the service calls the repository.

## Relevant Event Contracts
None produced or consumed by this batch's code. `OutboxPublisherService` reads `SystemEventOutbox` rows and transitions status; it does not produce new domain events.

## Relevant Notes
**Implementation Clarifications** — `OutboxPublisherService` runs in its own transaction, separate from the producing transaction. This is correct and required by the transactional outbox pattern: the service must not see `pending` rows from transactions that have not yet committed, and must not participate in the producing transaction's commit/rollback. The `status='pending'` filter naturally enforces this — uncommitted rows are not visible to the service's session. The exact same semantics were promised by Batch 2 Step 2's shipped implementation; this batch moves the ownership of those semantics from the worker to the service without changing them.

**Known Risks** — The publisher runs every 15 seconds (per ADR-013), so event publication latency is bounded by the polling interval. If lower latency is ever required, a `LISTEN/NOTIFY`-driven publisher is the natural next step (out of scope here). Until then, consumers that need to react to an event should be triggered by procrastinate task deferral from the producer (the existing pattern), not by polling the outbox. The outbox's role is audit + future external consumer support, not low-latency fanout.

**Implementation Clarifications** — The `mark_published` method (or equivalent) already exists on `SystemEventOutboxRepository` per the Batch 2 Step 1 shipped implementation. The service reuses it, not reimplements it. If the existing method signature differs from what the service needs (e.g. it expects a different argument shape), widen the existing method rather than creating a parallel one.

**Why Batch 4 rather than retro-editing Batch 2** — The Phase 2.7 plan originally prescribed worker → repository direct access in Batch 2 Step 2; the coder followed the plan faithfully; the validator flagged it CRITICAL. The architecture question was escalated and resolved as ADR-013 (Path B). The fix is delivered as this separate batch rather than as an in-place edit to the already-shipped Batch 2 BRD so the coder receives a self-contained delta whose preconditions reference the completed Batch 2 — the coder does not have to diff the BRD against what it already implemented to reconstruct what changed.

**Architecture documentation handoff** — Architecture documentation updates for `docs/architecture/04-platform/system-event.md` are in `batch-4-architecture.md` — routed to `p-vision-and-architect-author`. The handoff has **already been applied** as part of the ADR-013 resolution (Runtime Flow redrawn with `OutboxPublisherService` + `PublisherTask` participants; Mutation Rules publish-side ownership note added citing ADR-013; Failure Semantics, Performance Constraints, and Future Bus Insertion Point re-anchored to `OutboxPublisherService`; ADR-004 cross-reference added). The coder does not modify `system-event.md`; the BRD's Batch Success Criteria require only that the coder's own steps leave `docs/architecture/` untouched. See `batch-4-architecture.md` for the full change list.

## Relevant Pseudocode
Not applicable — the flow is linear (worker calls one service method, the service does one transaction): see Step 1 and Step 2 prose.

## Files Expected To Change
- `[NEW] app/services/outbox_publisher_service.py` — `OutboxPublisherService` with `publish_pending(limit)` method
- `[EXISTING — modified] app/worker/app.py` — body of the existing `outbox_publisher` task re-routed to call `OutboxPublisherService.publish_pending(limit)` instead of constructing `SystemEventOutboxRepository` directly
- `[EXISTING — modified] app/services/__init__.py` — add `OutboxPublisherService` to `__all__`

Files **not** changed by this batch (notwithstanding the original Batch 2 BRD listing `docs/architecture/04-platform/system-event.md`): the architecture document update is owned by `p-vision-and-architect-author` via `batch-4-architecture.md` and is already applied.

## Coder Notes
- **No migration this batch.** No schema change. The DB schema is untouched.
- **Worker → service → repository, not worker → repository.** ADR-001 (`WorkerIntegration`, `RepositoryAccess`) and ADR-013 (`OutboxPublisherService`) mandate that the procrastinate `outbox_publisher` task calls `OutboxPublisherService.publish_pending(limit)`. The worker MUST NOT construct `SystemEventOutboxRepository`, open its own `AsyncSession`, call `get_pending`, or call `mark_published`. The worker owns only task registration, scheduling, and graceful exception handling. This is a regression guard against the worker → repository layer-skip that was retracted after the Phase-2-7 validator CRITICAL finding.
- **No behavioural change.** This batch is a layering correction only. The observable output of the `outbox_publisher` task is identical to the Batch 2 shipped state. The coder should run the Batch 2 test scenarios (1–17 in `batch-2-outbox-publisher-tests.md`) against the re-routed implementation and confirm they still pass — plus the new layer-guard scenario in `batch-4-outbox-publisher-layer-fix-tests.md`.
- **`mark_published` reuse.** `SystemEventOutboxRepository` already has `get_pending(limit)` and `mark_published` (or equivalent) from Batch 2 Step 1. The service calls them; it does not modify them. If the existing method signature differs from what the service needs, widen the existing method rather than creating a parallel one.
- **Architecture docs are out of scope for the coder.** Do not modify any file under `docs/architecture/` in this batch — that work is owned by `p-vision-and-architect-author` via `batch-4-architecture.md` and is already applied. If the test suite turns up a `system-event.md` inconsistency, route it back rather than editing the doc.
- **Do not introduce external bus dependencies.** `OutboxPublisherService` MUST NOT import or require Redis, NATS, Kafka, or any message bus client. The service is a status transitioner. The architecture document (`system-event.md`, already updated) makes the future-bus insertion point explicit so that adding a bus later is a localized change to `OutboxPublisherService`, not a redesign. Legitimate future-option mentions of Redis (as a possible external consumer or migration option) remain in `system-event.md` by design — they are not stale references; do not remove them and do not flag them as violations.
- **Schedule interval preservation.** Batch 2's shipped `outbox_publisher` task landed at a 15-second periodic schedule, which is inside the ADR-013-specified "default every 15 seconds" band. This batch preserves that interval verbatim; do not change it.
- **Procrastinate compatibility.** The existing worker setup uses procrastinate. The re-routed worker must present the same procrastinate task identity, periodic schedule registration, and registered name verbatim so the running job queue treats this configuration as the same task — only the body changes.