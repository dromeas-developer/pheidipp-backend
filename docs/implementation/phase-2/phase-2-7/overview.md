# Implementation Overview: Phase 2.7 — Platform Hardening (Gap-Closing)
## Plan ID: Phase-2-7

## Sub-Phase Reference
Sub-Phase ID: Phase-2.7
Sub-Phase Title: Platform Hardening — closes findings from the Phase 1 & 2 retrospective gap analysis (`docs/implementation/gap-analysis-phase-1-2.md`)

## Objective
Close the CRITICAL and HIGH findings surfaced by the retrospective gap analysis of Phases 1 and 2. This phase is not part of the original release plan — it is a gap-closing phase introduced after the baseline migration and roast. It addresses three categories of debt: (1) layer-architecture violations where agent classes live in `app/services/` instead of `app/agents/`, (2) a missing outbox publisher worker that leaves the transactional outbox pattern half-implemented, and (3) an event-flow contract violation where `twin_model_ready` is never produced plus a plan-router layer-skip. The phase is delivered in three batches, each closing a coherent cluster of findings.

**G-02 retraction note:** The original Phase 2.7 scope also included a TimescaleDB hypertable-conversion migration for six append-only tables. That finding (G-02) was a false positive caused by under-specification in the stack-truth `## Timescale / Hypertables` rule. The rule has been corrected to state the full three-criterion discriminator (fixed cadence AND row-is-measurement AND fleet-wide window-scan); none of the six flagged tables qualify. They remain standard append-only tables. The single true hypertable in the model (`athlete_wellness`) is unimplemented and is correctly deferred to the wellness ingestion phase that introduces its first writer — it is not in scope for Phase 2.7. See `docs/implementation/gap-analysis-phase-1-2.md` §5 G-02 for the full retraction and per-table verdicts.

## Scope
- **Agent relocation (Batch 1):** Move `WorkoutGenerationAgent` and `FirstMessageAgent` from `app/services/` to `app/agents/`. Update all import sites. Update `app/agents/__init__.py`, `app/agents/README.md`, `app/services/__init__.py`, `app/services/README.md`. No behavioural change — pure file relocation + import rewiring.
- **Outbox publisher (Batch 2):** Add the outbox publisher worker that transitions `SystemEventOutbox` rows from `pending` to `published`. The write side (services inserting event + outbox row in the producing transaction) was already correct; the publish side now exists. Update `docs/architecture/04-platform/system-event.md` to remove stale Redis references and align the documentation with the PostgreSQL-native reality, including an explicit insertion point for a future external bus.
- **Event-flow contract alignment + plan-router layer fix + low-severity cleanups (Batch 3):** Implement the `twin_model_ready` event as the architecture specifies (Option 1 — no ADR). Introduce a `PlanQueryService` to own the three read queries currently executed directly in `app/api/v1/plan.py`. Fix the stale `run_ingestion_pipeline` docstring. Verify the `TrainingGoalRepository_unique_violation` reference in `onboarding_service.py`.

## Out Of Scope
- **G-01 (LLM router):** Retracted — the code is ADR-007 compliant; the stack-truth instruction was stale and has been corrected.
- **G-02 (TimescaleDB hypertable conversion):** Retracted — the six flagged tables are not hypertable candidates per the corrected stack-truth discriminator. The single true hypertable in the model (`athlete_wellness`) is unimplemented and correctly deferred to the wellness ingestion phase that introduces its first writer. No `CREATE EXTENSION IF NOT EXISTS timescaledb;` is run in this phase. See the G-02 retraction note above and `docs/implementation/gap-analysis-phase-1-2.md` §5 G-02.
- **G-06 (empty `05-api-contracts/`):** Architecture documentation gap — escalated to the Architecture Author, not an implementation task.
- **G-08 (orphaned `SecondaryEvent` / `RegenerationTask`):** Correctly deferred — these models will be consumed when Phase 2-4 (plan regeneration) is implemented. No action in this phase.
- **G-10 (unused `AthleteProfile` JSONB columns):** Correctly deferred — populated by background computation services that don't exist yet.
- **G-11 (empty `relevant_objectives`):** Correctly deferred to Phase 2-5 (Objective Management).
- **G-12 (`CalibrationEligibilityService` signature drift):** Benign — the implementation is correct; the BRD was over-specified. No action.
- **G-14 (vision corpus not indexed):** Tooling/indexing task — run `reindex_vision`. Not an implementation task for this phase.
- **G-15 (Phase 1-7/1-8 have no release-plan entries):** Release-plan traceability gap — escalated to the Release Strategy Architect.
- **`athlete_wellness` hypertable creation:** Belongs to the wellness ingestion phase (Phase 3 territory) that introduces its first writer. Not in Phase 2.7.
- **Phases 2-4, 2-5, 2-6:** Future work, not gaps. Planned via the normal Plan Mode process when the team is ready.

## Architecture Contracts
- `docs/adr/007-litellm-proxy.md` — DEPENDS ON (Batch 1: confirms the `AsyncOpenAI`-via-proxy pattern the relocated agents use is the compliant form)
- Stack-truth instruction `001-stack-truth.md` → "Layers: agents/ → LangGraph DAGs" and "agents → services" — IMPLEMENTS (Batch 1: relocates agents to their correct layer)
- `04-platform/system-event.md` → "Publisher (post-commit) reads pending outbox entries and publishes" — IMPLEMENTS (Batch 2: outbox publisher worker)
- `04-platform/event-topology.md` → "Publication Mechanics" — IMPLEMENTS (Batch 2: publisher process — status transition without external bus)
- `00-foundations/event-catalogue.md` → `twin_model_ready` — IMPLEMENTS (Batch 3: produces the event as the architecture specifies)
- `04-platform/event-topology.md` → "Plan Generation Event Flows → Initial Plan Generation" — IMPLEMENTS (Batch 3: wires `twin_model_ready → PlanGenerationService → training_plan_generated → FirstMessageAgent`)
- Stack-truth instruction `001-stack-truth.md` → "No direct repository access outside services" and "Route handlers MUST NOT execute SQLAlchemy queries directly" — IMPLEMENTS (Batch 3: `PlanQueryService` owns plan read queries)

## Invariants
- **Layer architecture (non-negotiable):** `api → services → repositories → models` and `agents → services`. No business logic in api. No direct repository access outside services. No layer skipping or reversal. (Batch 1 enforces the `agents/` location; Batch 3 enforces the service-layer ownership of plan reads.)
- **Transactional outbox atomicity:** Event and outbox row are inserted in the same database transaction as the domain state change; rollback removes both. Publication occurs only after the producing transaction commits successfully. (Batch 2 — the publisher must not break this; the publisher's `status='pending'` filter naturally only sees committed rows.)
- **Append-only tables remain append-only:** The publisher's status transition applies to `system_event_outbox` only (which is NOT one of the append-only event-log tables — it is the mutable outbox state machine). The append-only tables (`system_events`, `twin_states`, `raw_sensor_streams`, `physiology_measurements`, `generation_events`, `coaching_messages`) remain append-only across all batches.
- **No behavioural change in Batch 1:** Agent relocation is a pure file move + import update. The agents' runtime behaviour, transaction boundaries, event production, and idempotency must be identical before and after.

## Cross-Validation Summary

| Check | Result | Detail |
|-------|--------|--------|
| RC1 Contract Saturation | ✓ | All contracts for Batches 1–2 accounted for. Batch 1: ADR-007 + stack-truth layer rule. Batch 2: `system-event.md` publisher contract + `event-topology.md` publication mechanics. Batch 3: pending its own revalidation after the G-03 decision is applied (the decision is Option 1 — implement `twin_model_ready` as specified, no ADR). |
| RC2 Vision Constraints | N/A | This phase is infrastructure hardening — no vision constraints are touched. |
| RC3 Entity Collision | ✓ | Batch 1: no new entities; relocated agents already exist. Batch 2: no new entities; the publisher is a procrastinate task on an existing repository. The retracted hypertable conversion would have created no new entities either. |
| RC4 Modification Safety | ✓ | Batch 1: import sites verified (3 files import the two agents). Batch 2: the publisher adds net-new code; the only modification is to `system-event.md` (documentation) and the outbox repository (additive method). No schema change. The retracted hypertable migration would have required FK drops and composite-PK changes — that risk is now removed. |
| RC5 Event Flow | ✓ | Batch 1: no event changes. Batch 2: publisher does not alter event production — it only transitions outbox row status; no new domain events produced. Batch 3: pending its own revalidation after the G-03 decision is applied. |
| RC6 Invariant Enforcement | ✓ | Batch 1 enforces layer-architecture invariant. Batch 2 enforces transactional outbox atomicity (the `status='pending'` filter only sees committed rows; the publisher's commit is separate from the producer's). The retracted hypertable mandate no longer applies to any table in this phase. Batch 3 enforces no-direct-query rule via `PlanQueryService`. |
| RC7 ADR Re-Check | ✓ | No new ADRs required for Batch 1. Batch 2: G-04 resolved by Option A (no external bus; publisher marks rows `published`) — no ADR. Batch 3: G-03 resolved by Option 1 (implement `twin_model_ready` as architecture specifies) — no ADR. |

## Event Contracts
- **Batch 1:** None — agent relocation does not touch event production or consumption.
- **Batch 2:** None produced/consumed by this batch's code. The outbox publisher reads `SystemEventOutbox` rows and transitions status; it does not produce new domain events.
- **Batch 3:** `twin_model_ready` — PRODUCES by `TwinRecalibrationService`/`OnboardingService` after the first TwinState insert; CONSUMES by the `generate_plan` and `generate_first_message` procrastinate tasks (which then invoke `PlanGenerationService.generate()` and `FirstMessageAgent.generate()` respectively). The neighbour events `training_plan_generated` and `onboarding_completed` are unchanged in their existing contracts.

## Pseudocode
Not applicable for Batch 1 (pure relocation) or Batch 2 (a single procrastinate task with linear flow — Step 2 BRD contains the inline pseudocode in its prose). Batch 3 pseudocode appears in the Batch 3 BRD.

## Testing Requirements
- **Batch 1:** All existing tests pass without modification. The three LLM agent entry points behave identically before and after relocation. `from app.agents import WorkoutGenerationAgent, FirstMessageAgent` resolves. `from app.services import WorkoutGenerationAgent` raises `ImportError`.
- **Batch 2:** `SystemEventOutboxRepository.get_pending(limit)` returns pending rows ordered by `created_at`, excludes `published` rows, and respects the limit argument. The publisher task is registered in `app/worker/app.py`, transitions pending rows to `published`, is idempotent (a second run on the same row set transitions 0 rows), handles an empty queue without error, handles partial batches (leaves rows beyond the limit `pending` for the next run), and does not produce new domain events. `system-event.md` has zero matches for "Redis" and documents the future-bus insertion point. `event-catalogue.md` and `event-topology.md` are unchanged.
- **Batch 3:** *(Specified in the Batch 3 BRD.)*

## Notes

**Implementation Clarifications** — Batch 1 is a pure file relocation. The two agent files (`workout_generation_agent.py`, `first_message_agent.py`) move from `app/services/` to `app/agents/` verbatim — no code changes inside the files. The only edits are to import statements in consuming files and to the `__init__.py` / `README.md` files of both directories. The error modules (`workout_generation_errors.py`, `first_message_agent`'s `FirstMessageAlreadyExistsError` / `LLMServiceUnavailableError`) stay in `app/services/` — they are domain exceptions, not agents, and the stack-truth places exceptions alongside services.

**Implementation Clarifications** — Batch 2's publisher task runs in its own transaction, separate from the producing transaction. This is correct and required by the transactional outbox pattern: the publisher must not see `pending` rows from transactions that have not yet committed, and must not participate in the producing transaction's commit/rollback. The `status='pending'` filter naturally enforces this — uncommitted rows are not visible to the publisher's session.

**Deferred Decisions** — `athlete_wellness` hypertable creation is explicitly out of scope for this phase. It belongs to the wellness ingestion phase (Phase 3 territory) that introduces its first writer — the wellness ingestion route + `WellnessBaselineService` + recovery modifier chain. That phase will install `CREATE EXTENSION IF NOT EXISTS timescaledb;` and the first `create_hypertable()` call as part of the migration that creates the `athlete_wellness` table. Pre-staging either the extension or the empty hypertable in Phase 2.7 was considered and rejected: it would ship a hypertable with zero writers, and the first consumer needs to land in the same migration boundary as the table.

**Known Risks** — The `app/services/__init__.py` re-exports `WorkoutGenerationAgent` and `FirstMessageAgent` (lines 108 and 39). If any consumer imports them via `from app.services import ...` rather than the direct module path, those imports will break. The grep confirmed the direct module path is used in all three consumers (`app/api/v1/workout.py`, `app/api/v1/coach.py`, `app/services/__init__.py` itself), so the risk is contained — but the coder must verify no test file uses the `from app.services import WorkoutGenerationAgent` form.

**Known Risks** — The Batch 2 publisher runs every 10-30 seconds, so event publication latency is bounded by the polling interval. If lower latency is ever required, a `LISTEN/NOTIFY`-driven publisher is the natural next step (out of scope here). Until then, consumers that need to react to an event should be triggered by procrastinate task deferral from the producer (the existing pattern), not by polling the outbox. The outbox's role is audit + future external consumer support, not low-latency fanout.

## ADRs Written
None. G-03 resolved by Option 1 (implement `twin_model_ready` as architecture specifies — no ADR). G-04 resolved by Option A (no external bus; publisher marks rows `published` — no ADR). G-02 retracted — no ADR.

## Gap Escalations — Resolved

- **G-03 (`twin_model_ready` event flow) — RESOLVED.** Decision: Option 1 — implement the event as the architecture specifies. `TwinRecalibrationService`/`OnboardingService` produces `twin_model_ready` after the first TwinState insert; `PlanGenerationService` and `FirstMessageAgent` consume it via procrastinate task deferral. The direct `PlanGenerationService.generate_plan()` call is removed from `OnboardingService`. No ADR required — the architecture is being implemented as written.
- **G-04 (outbox publisher target destination) — RESOLVED.** Decision: Option A — the publisher marks rows `published` without an external bus. The Redis-to-procrastinate migration was already done during implementation; `system-event.md` references to Redis are stale. Batch 2 includes the documentation update to `system-event.md` removing Redis references and aligning with the PostgreSQL-native reality, with an explicit insertion point for a future external message bus. A future architecture update (escalated to the Architecture Author) should formally amend `system-event.md` to describe the publisher as a PostgreSQL-native status transitioner.
- **G-02 (TimescaleDB hypertable conversion) — RETRACTED.** The original finding was a false positive caused by under-specification in the stack-truth `## Timescale / Hypertables` rule. The rule has been corrected to state the full three-criterion discriminator (fixed cadence + row-is-measurement + fleet-wide window-scan); none of the six flagged tables qualify. They remain standard append-only tables. The single true hypertable in the model (`athlete_wellness`) is unimplemented and correctly deferred to the wellness ingestion phase that introduces its first writer. No migration, no `CREATE EXTENSION`, no schema change for G-02 in Phase 2.7. See `docs/implementation/gap-analysis-phase-1-2.md` §5 G-02 for the full retraction and per-table verdicts, and the corrected `001-stack-truth.md` `## Timescale / Hypertables` block for the updated rule.
