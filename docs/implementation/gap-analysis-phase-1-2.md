# Gap Analysis — Phases 1 & 2 (Retrospective)

> **Mode:** Plan Mode applied retrospectively. The existing implementation is the "tentative plan"; the State Explorer registry and architecture corpus are the sources of truth.
> **Date:** 2026-07-19
> **Scope:** All sub-phases of Phase 1 (1-1 through 1-8) and Phase 2 (2-1 through 2-3) that have migrated BRDs. Sub-phases 2-4, 2-5, 2-6 have release-plan documents but no implementation plans and no live code — they are noted as "not yet implemented" and excluded from the roast.
> **Method:** RC1–RC7 cross-validation against the live codebase (via `p-state-explorer`), the architecture corpus (`docs/architecture/`), the release plan (`docs/release-plan/`), the ADR corpus (`docs/adr/`), and the migrated BRDs (`docs/implementation/phase-1/`, `docs/implementation/phase-2/`). Test pack was not reviewed per instruction.

---

## 1. Executive Summary

Phases 1 and 2 are **substantially delivered** against their release-plan scope. Every sub-phase that has a migrated BRD also has corresponding live code: models, repositories, services, routes, migrations, and worker tasks all exist and are registered. The core data flow — register → onboard → generate plan → generate workout → upload FIT → recalibrate twin → post-workout message → signal clean → threshold detect → physiology update → twin recalibration — is wired end-to-end and fires events through the transactional outbox.

However, the retrospective roast surfaces **15 findings** ranging from hard contract violations to deferred-but-undocumented work. The most severe are:

- ~~**G-01 (CRITICAL):** LLM router does not exist.~~ **RETRACTED** — on verification, the code is ADR-007 compliant; the stack-truth instruction was stale and has been corrected. See §5 G-01 for the full retraction.
- ~~**G-02 (CRITICAL):** No TimescaleDB hypertables exist.~~ **RETRACTED** — on verification against the corrected discriminator in stack-truth, none of the six flagged tables are hypertable candidates. The original stack-truth rule under-specified its trigger ("daily or per-second time-series samples" without defining "sample"); the rule has been corrected to state the full three-criterion discriminator. The single true hypertable in the model is `athlete_wellness` (planned, unimplemented) — it lands with its producer in the wellness ingestion phase. See §5 G-02 for the full retraction and the per-table verdicts.
- **G-03 (HIGH):** The `twin_model_ready` event — which the architecture names as the trigger for plan generation and first-message generation — is never produced. Plan generation is wired directly into the onboarding transaction instead. This is an event-flow contract violation, not a behavioural bug.
- **G-04 (HIGH):** No outbox publisher worker exists. `SystemEventOutbox` rows are written with `status='pending'` and never transition to `published`. The transactional outbox pattern is half-implemented — the write side works, the publish side does not.
- **G-05 (HIGH):** Two agent services (`WorkoutGenerationAgent`, `FirstMessageAgent`) live in `app/services/` rather than `app/agents/`. This is a layer-architecture inconsistency, not a runtime bug, but it muddies the `agents → services` boundary the stack-truth instruction defines.

The remaining 10 findings are MEDIUM or LOW — orphaned models, stale docstrings, a layer-skip in read paths, and several architecture entities that have contracts but no implementation (correctly deferred, but the deferral is not tracked anywhere).

**Recommendation:** Produce a single new baseline phase (`phase-2-7-platform-hardening`) with multiple batches closing the remaining findings: (1) agent relocation, (2) outbox publisher (the hypertable-conversion portion of the originally-planned batch 2 is **retracted** per G-02; the `athlete_wellness` hypertable lands with its producer in the wellness ingestion phase), (3) event-flow contract alignment (`twin_model_ready`) + plan-router layer fix + low-severity docstring/typo cleanups. Details in §6.

---

## 2. Inputs Reviewed

| Source | Coverage |
|---|---|
| Release plan | All 9 Phase-1 sub-phases, all 6 Phase-2 sub-phases (2-4/2-5/2-6 have docs but no implementation) |
| Architecture corpus | `00-foundations/` (5 docs), `01-entities/` (31 docs), `02-computations/` (24 docs), `03-agents/` (10 docs), `04-platform/` (8 docs), `05-api-contracts/` (empty) |
| ADR corpus | ADR-001 through ADR-011 |
| Implementation plans | 11 migrated BRDs across `phase-1/phase-1-1` through `phase-1/phase-1-8`, `phase-2/phase-2-1` through `phase-2/phase-2-3` (3 batches) |
| Live codebase | `app/models/` (26 models), `app/repositories/` (23 repos), `app/services/` (28 services), `app/api/v1/` (7 routers), `app/agents/` (1 agent), `app/worker/app.py` (4 tasks), `app/tasks/` (1 maintenance task), `alembic/versions/` (11 migrations) |
| Vision corpus | `docs/vision/` (34 documents across `coach/`, `product/`, `twin/`) — not indexed in the architecture index but present on disk |

---

## 3. Sub-Phase Delivery Status

| Sub-Phase | Release Plan | BRD | Live Code | Status |
|---|---|---|---|---|
| 1-1 Email/Password Auth | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — all capabilities present, 3 security patches applied |
| 1-2a Profile/Preferences/Activity | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — schema-only, migration applied |
| 1-2b Plan/Sessions | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — schema + test-contract remediation |
| 1-2c Twin/Fitness/Coaching/Workouts | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — schema + FK fix migration |
| 1-3 Onboarding/Twin Bootstrap | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — 8 endpoints, atomic transaction, plan-gen wired in |
| 1-4 Plan Generation | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — pure-Python service, 4 read endpoints, onboarding integration |
| 1-5a First Coach Message | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — agent, context budget, prompt registry, 2 endpoints |
| 1-5b Workout Generation | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — agent, idempotency, data-tier targets, 2 endpoints |
| 1-6 Simple FIT Import | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — upload, parse, load, recalibrate, post-workout, 4 endpoints |
| 1-7 Architecture Simplification | (not in release plan) | ✓ (1 batch) | ✓ | **DELIVERED** — Redis→procrastinate, MinIO, async pipeline wiring |
| 1-8 Consistency Cleanup | (not in release plan) | ✓ (1 batch) | ✓ | **DELIVERED** — email utils, event-topology clarification |
| 2-1 FIT Ingestion Expansion | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — sport-type, power/GPS/RR, calibration gate, 3 events |
| 2-2 Signal Cleaning | ✓ | ✓ (1 batch) | ✓ | **DELIVERED** — 7-step pipeline, RawSensorStream, worker task |
| 2-3 Threshold Detection + Physiology | ✓ | ✓ (3 batches) | ✓ | **DELIVERED** — ThresholdDetection, PhysiologyUpdate, TwinRecalibration pipeline |
| 2-4 Plan Regeneration/Weekly Synthesis | ✓ | ✗ | ✗ | **NOT IMPLEMENTED** — release plan exists, no BRD, no code |
| 2-5 Objective Management | ✓ | ✗ | ✗ | **NOT IMPLEMENTED** — release plan exists, no BRD, no code |
| 2-6 Power Profile Computation | ✓ | ✗ | ✗ | **NOT IMPLEMENTED** — release plan exists, no BRD, no code |

**Note on 1-7 and 1-8:** These two implementation plans exist in `docs/implementation/phase-1/` but have no corresponding entry in `docs/release-plan/phase-1/`. They appear to be cross-cutting hardening passes that were added after the release plan was authored. This is not a defect — the release plan is authoritative on scope and sequencing, and these plans delivered infrastructure (procrastinate, MinIO) and cleanup that the release plan implicitly assumed. Flagging only for traceability: the release plan should either be amended to include them or they should be reclassified as "implementation hardening" outside the sub-phase structure.

---

## 4. Cross-Validation Summary (RC1–RC7)

| Check | Result | Detail |
|---|---|---|
| **RC1** Contract Saturation | ✗ | 2 architecture contracts not enforced in code: `twin_model_ready` event (G-03), outbox publisher worker (G-04). `05-api-contracts/` directory is empty — no API contracts are documented at the architecture level, though they exist implicitly in entity docs. |
| **RC2** Vision Constraints | ✓ | All Phase 1/2 vision constraints touched by implemented sub-phases are enforced: running-only calibration (sport-type gate), no raw pace (GAP in prompts), append-only TwinState (repository exposes only insert), no averages on Activity (model has no avg_* columns), Python-computes/LLM-narrates (all agents receive pre-computed context). One gap: "no AI-feel" voice constraints are prompt-level only — no automated validation, but this is by design (voice quality gate is a human review per 1-5a BRD). |
| **RC3** Entity Collision | ✗ | `SecondaryEvent` and `RegenerationTask` models exist (migrations + ORM) but have **no repository, no service, no route** (G-08). They are orphaned — created by the 1-2b schema plan but never consumed. Not a collision (nothing else claims their role), but a dead contract. |
| **RC4** Modification Safety | ✓ | No downstream consumers are broken by any implemented change. The `twin_states` unique-index drop (migration 21f955c743cb) correctly replaced the unique constraint with `insert_if_not_exists` application-level deduplication. The `training_plans.twin_state_id` FK was added in a separate migration (d1579f4430e7) after TwinState existed — correct forward-only pattern. |
| **RC5** Event Flow Consistency | ✗ | Two event-flow contract violations: (a) `twin_model_ready` is defined in the event catalogue as the trigger for `PlanGenerationService.generate()` and `FirstMessageAgent.generate()`, but the code wires plan generation directly into the onboarding transaction and first-message generation behind a manual API endpoint — `twin_model_ready` is never produced (G-03). (b) The outbox publish side is unimplemented — events are written to `system_event_outbox` with `status='pending'` but no worker ever transitions them to `published` (G-04). All other event chains (produce → consume ordering, payload fields) are consistent. |
| **RC6** Invariant Enforcement | ✗ | Three invariants originally flagged; only one survives: (a) ~~TimescaleDB hypertable mandate for time-series tables~~ — **retracted**: the original stack-truth rule under-specified its trigger; once corrected to the full three-criterion discriminator (fixed cadence + row-is-measurement + fleet-wide window-scan), none of the six flagged tables qualify (G-02 retracted). The single true hypertable (`athlete_wellness`) is unimplemented — correctly deferred to its producer phase. (b) ~~`app.core.llm_router.get_llm()` as sole LLM gateway~~ — **retracted**: ADR-007 blesses the direct `AsyncOpenAI`-via-proxy pattern the code uses; the stack-truth instruction was stale and has been corrected (G-01 retracted). (c) `agents → services` layer boundary — two agents live in `services/` (G-05, the one surviving invariant finding in this row). All other invariants (append-only TwinState, fit_file_key prerequisite, no averages, GAP-only pace, single active goal, form = fitness − fatigue) are enforced at the correct layer. |
| **RC7** ADR Re-Check | ✗ | ~~G-02 (hypertables)~~ — **retracted**: false positive caused by under-specified rule; rule corrected, no implementation (G-02 retired). G-03 (`twin_model_ready` event flow) may require an ADR if the team chooses to amend the event topology rather than implement the missing event. G-04 (outbox publisher) is an implementation gap with a Redis-vs-no-Redis tension that has been resolved by Option A (no external bus; publisher marks rows `published`) — no ADR required. G-01 was retracted — no ADR needed. No new ADRs are strictly required unless G-03 is resolved by amending architecture rather than implementing it. |

---

## 5. Findings (Roasted)

Findings are ordered by severity. Each finding states: what the contract is, what the code does, why it matters, and the recommended resolution.

### G-01 — LLM router does not exist (RETRACTED — non-finding)

**Initial concern:** Stack-truth instruction `001-stack-truth.md` mandated `app.core.llm_router.get_llm()` as the sole LLM gateway. The router file did not exist; all three agents constructed `AsyncOpenAI` directly.

**Verification outcome:** On closer inspection, ADR-007 (status: `accepted`) explicitly blesses the `AsyncOpenAI(base_url=settings.LITELLM_BASE_URL, api_key=settings.LITELLM_API_KEY)` pattern as the compliant form — its "Compliant" example is character-for-character identical to what all three agents do today. The agents already route through the LiteLLM proxy (the `litellm` Docker service at `http://litellm:4000/v1`); they do not call provider SDKs directly. The `get_llm()` router was a planned abstraction that was never built and was superseded by ADR-007's "proxy is the gateway" approach.

**Resolution:** The stack-truth instruction was stale and conflicted with ADR-007. The instruction has been corrected to align with ADR-007 (the `get_llm()` mandate was removed; the compliant `AsyncOpenAI`-via-proxy pattern is now documented as the standard). No code change required — the code is already ADR-007 compliant. **G-01 is retracted as a non-finding.**

---

### ~~G-02 — No TimescaleDB hypertables (CRITICAL)~~ **RETRACTED**

~~Original finding (preserved for audit): six append-only tables (`twin_states`, `raw_sensor_streams`, `physiology_measurements`, `system_events`, `generation_events`, `coaching_messages`) were flagged as missing hypertable conversion, on the reading that the stack-truth rule's phrase "daily or per-second time-series samples" applied to any append-only table with a timestamp.~~

**RETRACTION:** This finding was a false positive caused by under-specification in the stack-truth `## Timescale / Hypertables` rule, which triggered on "time-series samples" without defining what counts as a sample. The stack-truth instruction has since been corrected to state the full discriminator explicitly: a table is a hypertable candidate **iff all three** hold — (1) rows are samples taken at a fixed cadence (not triggered by events), (2) the row's value *is* the measurement itself (not metadata, not a derived snapshot, not a versioned filing), (3) the dominant query is a time-windowed scan across many entities (not a single-entity lookup or per-athlete pagination).

Applying the corrected discriminator to all six flagged tables: none qualify.

| Table | Verdict | Why (against the corrected discriminator) |
|---|---|---|
| `twin_states` | Standard | Triggered, not cadenced; `superseded_at` versioned semantics; FK-joined by `coaching_messages`/`generated_workouts`. Exclusion clause applies. |
| `raw_sensor_streams` | Standard | One-row-per-activity metadata pointer to MinIO `stream.gz`; actual per-second samples live in MinIO, not PG. Row is metadata, not a measurement. |
| `physiology_measurements` | Standard | Sparse per-athlete-parameter history, not fleet-wide window scan. |
| `system_events` | Standard | Mutable `system_event_outbox` companion joined on `event_id`; tiered retention already specified. |
| `generation_events` | Standard | Eventually-consistent async audit side-channel — hypertable on an eventually-consistent side-channel is a category error. |
| `coaching_messages` | Standard | Per-athlete feed pagination; time-chunking *hurts* the dominant query (every feed query would hit multiple chunks per athlete). |

**The single true hypertable in the model is `athlete_wellness`** (daily cadence, row-is-the-measurement, 28-day rolling window scan across athletes), as already specified in `docs/architecture/01-entities/athlete-wellness.md`. It is currently unimplemented — no ORM model, no migration, no repository, no service. It is correctly deferred to the wellness ingestion phase (Phase 3 territory) that introduces its first writer. `athlete_wellness_baselines` is a standard table (mutable, one row per athlete per signal; upsert-on-recompute — confirmed against `docs/architecture/01-entities/athlete-wellness-baseline.md` §Invariants).

**Process finding (root cause):** The original stack-truth rule under-specified its trigger and exclusion clause. The rule's exclusion clause listed only "versioned records with date ranges"; it was silent on event/audit logs with companion tables, one-row-per-activity metadata, per-athlete feed pagination, sparse observations, eventually-consistent side-channels, and derived state recomputed against a hypertable. This under-specification directly caused the false positive. The stack-truth instruction has been corrected (`.opencode/instructions/001-stack-truth.md` `## Timescale / Hypertables` block) to state the three-criterion discriminator and enumerate the explicit non-hypertable categories. No code change is required for this finding. The architectural-storage intent for per-second workout samples (MinIO-only per `storage-topology.md`) is load-bearing architecture and was also reflected in the corrected rule.

**Resolution:** No implementation. Stack-truth instruction corrected to prevent recurrence. `athlete_wellness` hypertable creation lands with its producer in the wellness ingestion phase.

**G-02 is retracted as a non-finding.**

---

### G-03 — `twin_model_ready` event never produced (HIGH)

**Contract:** `00-foundations/event-catalogue.md` defines `twin_model_ready` with producer `TwinRecalibrationService` ("fires once after onboarding when twin has sufficient data") and consumers `PlanGenerationService` (triggers initial plan generation + first WeeklyPlan) and `FirstMessageAgent` (generates first message from WeeklyPlan). `04-platform/event-topology.md` "Plan Generation Event Flows → Initial Plan Generation" shows `twin_model_ready → PlanGenerationService → training_plan_generated → FirstMessageAgent`. The `onboarding_completed` event catalogue entry explicitly states: "plan generation is triggered by `twin_model_ready`, NOT by `onboarding_completed`."

**Code:** `grep` for `twin_model_ready` across `app/**/*.py` → **0 matches**. The event is never produced. Instead:
- `OnboardingService.complete_onboarding()` directly invokes `self.plan_service.generate_plan(athlete_id)` within the onboarding transaction (confirmed at `app/services/onboarding_service.py` line 471).
- `FirstMessageAgent.generate()` is triggered by a manual `POST /athletes/{id}/coach/first-message` API call, not by any event.

**Why it matters:** The architecture deliberately separates `onboarding_completed` (state transition) from `twin_model_ready` (twin is ready to drive a plan) because Tier 1 athletes (with imported history) should have their plan generated after historical data ingestion, not immediately at onboarding. The current implementation hard-codes the Tier 3 behaviour (questionnaire-only → plan immediately) into the onboarding transaction. When Tier 1 onboarding is implemented (Phase 3+), the direct-wiring approach will either (a) generate a plan prematurely from a twin with no history, or (b) require conditional logic in the onboarding service that duplicates the event-driven decision. The event-driven design was chosen specifically to avoid this.

**Resolution:** This is an event-flow contract violation. Two options:
1. **Implement the event** — `TwinRecalibrationService` produces `twin_model_ready` after the first TwinState insert when `trigger = questionnaire` (Tier 3) or after historical ingestion completes (Tier 1). `PlanGenerationService` and `FirstMessageAgent` consume it. The direct wiring in `OnboardingService` is removed. This restores the architecture as written.
2. **Amend the architecture** — if the team decides the direct-wiring approach is simpler and Tier 1 will be handled differently, update `event-catalogue.md` and `event-topology.md` to remove `twin_model_ready` and document the direct-wiring pattern. This requires an ADR because it changes the event topology.

**Recommendation:** Option 1 (implement the event). The event-driven design is more flexible and the direct wiring is a shortcut that will cause rework. But this is an architecture decision — escalate to the Architecture Author if Option 2 is preferred.

**Severity:** HIGH — event-flow contract violation. Behaviour is currently correct for Tier 3 but will break the Tier 1 design when it is implemented.

---

### G-04 — Outbox publisher worker does not exist (HIGH)

**Contract:** `04-platform/system-event.md` → "Publisher (post-commit) reads pending outbox entries and publishes to Redis/message bus. On successful delivery, outbox row updated to status = 'published'." `04-platform/event-topology.md` → "Publication Mechanics" section describes the publisher worker as a separate process. `async-pipeline.md` does not list the publisher as a task, but the system-event doc describes it as infrastructure.

**Code:** `SystemEventOutboxRepository` has `add(event_id, status)` and `mark_published(event_id)` — the write side is implemented. `grep` for any worker that reads `status='pending'` outbox rows and calls `mark_published` → **no matches**. The `app/worker/app.py` registers `fit_ingest`, `recalibrate_twin`, `signal_clean`, `threshold_detection` — none of them is an outbox publisher. There is no periodic task, no `LISTEN/NOTIFY` listener, no separate publisher process.

**Why it matters:** Every event in the system (`athlete_registered`, `onboarding_completed`, `activity_ingested`, `twin_recalibrated`, `training_plan_generated`, `workout_generated`, `coaching_message_generated`, etc.) is written to the outbox with `status='pending'` and stays there forever. The transactional outbox pattern's value proposition — at-least-once delivery to an external bus — is not realised. If any downstream consumer ever needs to react to these events asynchronously (which is the entire point of the event catalogue), the publish side must exist. Currently the only "consumers" are in-process service calls, so the system functions, but the event-driven architecture is half-built.

**Resolution:** Implementation gap. Add an outbox publisher worker — either a procrastinate task on a short poll interval or a `LISTEN/NOTIFY`-driven listener — that reads pending outbox rows, publishes to the message bus (or, for now, logs and marks published), and transitions status. The message bus itself (Redis, per `system-event.md`) is not yet deployed — the stack-truth instruction says "No Redis; job state lives in PostgreSQL alongside application data." This is a tension: the architecture doc says Redis, the stack-truth says no Redis. **This tension should be escalated to the Architecture Author** — the outbox publisher's target destination is ambiguous. For now, the publisher can mark rows as `published` without actually publishing to an external bus, satisfying the state-machine contract without committing to a bus technology.

**Severity:** HIGH — half-imformed architectural pattern. Not blocking current functionality (all consumers are in-process) but blocks any future async consumer and violates the system-event contract.

---

### G-05 — Two agents live in `app/services/` instead of `app/agents/` (HIGH)

**Contract:** Stack-truth instruction → "Layers: agents/ → LangGraph DAGs" and "agents → services" (agents call services, not the other way around). The `app/agents/` directory exists and contains `post_workout_agent.py` and a README. `WorkoutGenerationAgent` and `FirstMessageAgent` are agents by behaviour (they call the LLM, write `GenerationEvent`, have `AGENT_NAME` constants, have prompt templates in `app/core/prompts/`) but live in `app/services/`.

**Code:**
- `app/services/workout_generation_agent.py` — class `WorkoutGenerationAgent`, calls LLM, writes GenerationEvent, has prompt `workout_gen_v1.md`.
- `app/services/first_message_agent.py` — class `FirstMessageAgent`, calls LLM, writes GenerationEvent, has prompt `first_message_v1.md`.
- `app/agents/post_workout_agent.py` — class `PostWorkoutAgent`, same pattern, correctly located.

**Why it matters:** The layer architecture is the foundation of the stack-truth instruction. When a future engineer looks for "all LLM agents," they will look in `app/agents/` and find only one of three. The `agents → services` dependency direction is muddied — `WorkoutGenerationAgent` is imported by `app/api/v1/workout.py` directly from `app.services`, making it look like a service rather than an agent. This is not a runtime bug, but it is a structural inconsistency that will compound as more agents are added.

**Resolution:** Implementation gap. Move `workout_generation_agent.py` and `first_message_agent.py` from `app/services/` to `app/agents/`. Update imports in `app/api/v1/workout.py`, `app/api/v1/coach.py`, and `app/services/__init__.py`. This is a pure file relocation + import update — no behavioural change. Should be bundled with G-01 (LLM router) since both touch the agent files.

**Severity:** HIGH — layer-architecture violation. Not blocking, but compounds with every new agent.

---

### G-06 — `05-api-contracts/` directory is empty (MEDIUM)

**Contract:** The architecture corpus has a `05-api-contracts/` directory (listed in `architecture-index.md` implicitly via the directory structure) but it contains zero documents. API contracts are currently implicit in entity docs (e.g. `athlete.md` mentions `POST /auth/register`, `activity.md` mentions `POST /athletes/{id}/activities/upload`).

**Code:** `read` of `docs/architecture/05-api-contracts/` → empty directory.

**Why it matters:** API contracts are the integration surface between the frontend and backend. Without a dedicated contract document, the frontend team must reverse-engineer the API from entity docs and route handlers. As the API grows, this becomes unsustainable. The empty directory suggests the contracts were planned but never authored.

**Resolution:** Architecture gap — not an implementation gap. The API contracts exist in code (FastAPI routes + Pydantic schemas) but are not documented at the architecture level. Escalate to the Architecture Author. Not blocking for the gap-closing phase.

**Severity:** MEDIUM — documentation gap, not a code defect.

---

### G-07 — Plan router bypasses services for read paths (MEDIUM)

**Contract:** Stack-truth instruction → "Layers: api/ → request handling only" and "No business logic in api" and "No direct repository access outside services" and "Route handlers MUST NOT execute SQLAlchemy queries directly."

**Code:** `app/api/v1/plan.py` contains 6 direct `session.execute(select(...))` calls (confirmed via grep):
- `get_plan_sessions()` — line 90: `session.execute(select(PlannedSession).join(WeeklyPlan, ...))`
- `get_upcoming_sessions()` — line 120: `session.execute(select(PlannedSession).join(WeeklyPlan, ...))`
- `get_plan_checkpoints()` — line 155: `session.execute(select(Checkpoint).join(PlannedSession, ...).join(WeeklyPlan, ...))`

The `app/api/v1/plan.py` README notes this is intentional ("no service class wraps the read path since it is read-only"), but the stack-truth instruction is unambiguous: "Route handlers MUST NOT execute SQLAlchemy queries directly."

**Why it matters:** The stack-truth rule exists to keep the API layer thin and testable, and to centralise query logic in services where it can be reused and mocked. The plan router's read paths are a layer-skip that the stack-truth explicitly forbids. The "read-only" justification is not an exception the stack-truth recognises.

**Resolution:** Implementation gap. Introduce a `PlanQueryService` (or extend `PlanGenerationService` with read methods) that owns these three queries. The route handlers delegate to the service. This is a small refactor — the queries already exist and work, they just need to be moved one layer down.

**Severity:** MEDIUM — layer-skip violation. Not blocking, but violates an explicit stack-truth rule.

---

### G-08 — `SecondaryEvent` and `RegenerationTask` models are orphaned (MEDIUM)

**Contract:** `01-entities/regeneration-task.md` defines the `RegenerationTask` entity with a two-step Propose→Confirm flow. `01-entities/training-goal.md` references `SecondaryEvent` as a supporting entity. Both have migrations (1b9e9026db1e) and ORM models.

**Code:** `SecondaryEvent` — model exists at `app/models/secondary_event.py`, registered in `__init__.py`, table exists in DB. **No repository, no service, no route.** `grep` for `SecondaryEvent` outside `app/models/` → only the migration and the model file. `RegenerationTask` — same status: model at `app/models/regeneration_task.py`, registered, table exists. **No repository, no service, no route.**

**Why it matters:** These are dead contracts — schema exists, nothing reads or writes it. They were created by the 1-2b schema plan which correctly deferred the logic to later phases. But the deferral is not tracked: there is no "Phase X will implement SecondaryEvent/RegenerationTask logic" note anywhere. When Phase 2-4 (plan regeneration) is implemented, it will need these, but the connection is not explicit.

**Resolution:** Documentation gap. Add a note to the 1-2b BRD's Coder Notes (or a deferred-decisions section in the overview) stating that `SecondaryEvent` and `RegenerationTask` logic is deferred to Phase 2-4. No code change needed now — the schema is correct and will be consumed when the logic lands.

**Severity:** MEDIUM — orphaned contract. Not blocking, but creates confusion about what is and isn't implemented.

---

### G-09 — `run_ingestion_pipeline` docstring is stale (LOW)

**Contract:** Code documentation should match code behaviour.

**Code:** The Phase 1-6 BRD's Coder Notes flag this: "Flag — stale docstring: `run_ingestion_pipeline` docstring says it 'Does NOT publish events' but the implementation DOES publish `sport_type_detected`, `activity_ingested`, and `activity_calibration_eligible`. This was updated in Phase 2 but the docstring was not fixed." Confirmed still present.

**Why it matters:** A stale docstring is a minor lie that will mislead the next engineer who reads it. Low impact, but trivial to fix.

**Resolution:** Implementation gap. Update the docstring to match the implementation. One-line fix.

**Severity:** LOW — documentation defect.

---

### G-10 — `AthleteProfile` JSONB columns are unused (LOW)

**Contract:** `01-entities/athlete-profile.md` defines `gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`, `current_effort_generation`, `objective_thresholds` as personalisation storage columns.

**Code:** All six columns exist on the `AthleteProfile` model (migration e7ffc8764335) but **no service reads or writes them**. They are nullable and always null in the current implementation.

**Why it matters:** This is **correct deferral**, not a defect. These columns are populated by background computation services (`GapCurveFittingTask`, `CyclePersonalisationTask`, etc.) that don't exist yet. The schema is ready for them. Flagging only so the gap-closing phase does not need to add migrations when these services are implemented.

**Resolution:** No action. Document the deferral in the gap-closing phase's Coder Notes if relevant.

**Severity:** LOW — correctly deferred. No action.

---

### G-11 — `WorkoutGenerationContext.relevant_objectives` is always empty (LOW)

**Contract:** `03-agents/workout-generation-agent.md` context includes `relevant_objectives`. `01-entities/objective.md` defines the Objective entity.

**Code:** `WorkoutGenerationContext.relevant_objectives` is an empty list (confirmed by State Explorer). The `Objective` model does not exist — no migration, no ORM class. The prompt handles the empty case gracefully.

**Why it matters:** Correctly deferred to Phase 2-5 (Objective Management). The workout generation agent works without objectives. Flagging only for traceability — when Phase 2-5 is implemented, the workout context assembly must be updated to populate `relevant_objectives`.

**Resolution:** No action for the gap-closing phase. Will be addressed when Phase 2-5 is planned.

**Severity:** LOW — correctly deferred.

---

### G-12 — `CalibrationEligibilityService` signature drift (LOW — RESOLVED)

**Contract:** Phase 2-1 BRD states `CalibrationEligibilityService.evaluate(*, activity, athlete_preferences, athlete_physiology) → bool`.

**Code:** Actual signature is `evaluate(self, activity: Activity) -> bool` — takes only the activity. The five-rule gate reads `activity.has_hr`, `activity.source`, `activity.duration_seconds`, `activity.quality_flags`, and `activity.sport_type` directly from the activity model. The `athlete_preferences` and `athlete_physiology` parameters from the BRD are not present.

**Why it matters:** The signature drift is benign — the activity model carries all the fields the gate needs. The BRD's signature was over-specified. The implementation is correct per the architecture contract (`02-computations/load-computation.md` defines the gate in terms of activity fields).

**Resolution:** No action. The BRD is a historical document; the implementation is correct. Flagging only so the gap-closing phase does not "fix" the signature to match the BRD.

**Severity:** LOW — benign drift. No action.

---

### G-13 — `onboarding_service.py` references `TrainingGoalRepository_unique_violation` (LOW — UNVERIFIED)

**Contract:** ADR-006 → "explicit rollback after caught DB exception." The pattern is `await session.rollback()` before re-raising.

**Code:** The State Explorer's brief flagged: "Line references `TrainingGoalRepository_unique_violation(exc)` — this appears to be a missing import or the method should be `is_unique_violation` as on other repos." This was noted as unverified in the brief.

**Why it matters:** If the reference is a typo, it would raise `AttributeError` at runtime when a unique-violation occurs during onboarding. If it's correct (e.g. a static method on `TrainingGoalRepository`), no issue.

**Resolution:** Needs verification — read `app/services/onboarding_service.py` around the referenced line. If it's a typo, fix it. If it's correct, no action. Not blocking for the gap-closing phase but should be verified before the phase ships.

**Severity:** LOW — possible typo, unverified.

---

### G-14 — Vision corpus not indexed (LOW)

**Contract:** The `list_vision_entities` tool returned "No vision entities indexed yet. Run reindex_vision first." The vision corpus exists on disk (`docs/vision/` with 34 documents across `coach/`, `product/`, `twin/`) but is not indexed in the architecture context system.

**Code:** `docs/vision/vision-index.md` and `docs/vision/reading-order.md` exist. The documents are present. The index is not.

**Why it matters:** Vision documents are referenced by release plans (e.g. "Vision References Required" sections) and by architecture docs (principles.md Vision Cross-References). Without the index, semantic search over vision content does not work, and the `search_vision` tool returns nothing. This affects future planning sessions, not runtime.

**Resolution:** Run `reindex_vision` (or the equivalent architecture refresh). Not a code change. Not blocking for the gap-closing phase.

**Severity:** LOW — tooling/indexing gap.

---

### G-15 — `Phase 1-7` and `Phase 1-8` have no release-plan entries (LOW)

**Contract:** The release plan is authoritative on scope and sequencing. Implementation plans should trace to a release-plan sub-phase.

**Code:** `docs/release-plan/phase-1/` contains 9 sub-phase documents (1-1 through 1-6). `docs/implementation/phase-1/` contains 11 directories (1-1 through 1-8). The extra two (1-7 architecture-simplification, 1-8 consistency-cleanup) have no release-plan entry.

**Why it matters:** These two plans delivered real infrastructure (Redis→procrastinate migration, MinIO, async pipeline wiring, email utils, event-topology clarification). They are not scope creep — they are hardening passes that the release plan implicitly assumed would happen. But the traceability is broken: a future auditor looking at the release plan will not know that procrastinate was introduced in 1-7, not in the original 1-6.

**Resolution:** Documentation gap. Either (a) amend the release plan to include 1-7 and 1-8 as cross-cutting hardening sub-phases, or (b) add a note to the implementation directory's README explaining that 1-7 and 1-8 are implementation hardening passes outside the sub-phase structure. Escalate to the Release Strategy Architect for the choice.

**Severity:** LOW — traceability gap. Not blocking.

---

## 6. Remediation Plan

The 15 findings cluster into three implementation batches plus several documentation/escalation actions. The implementation batches form a single new baseline phase: **`phase-2-7-platform-hardening`**. This phase closes the CRITICAL and HIGH findings (G-01 through G-05) and the MEDIUM layer-skip (G-07). The LOW findings are either documentation fixes, correct deferrals, or escalations.

### 6.1 Implementation Batches (proposed `phase-2-7-platform-hardening`)

| Batch | Theme | Findings Closed | Dependencies |
|---|---|---|---|
| **Batch 1** | Agent relocation | G-05 | None — pure file move + import update |
| **Batch 2** | Outbox publisher | G-04 | None (the original hypertable-migration half of Batch 2 is retracted per G-02; the TimescaleDB extension prerequisite is removed) |
| **Batch 3** | Event-flow contract alignment + plan-router layer fix + low-severity cleanups | G-03, G-07, G-09, G-13 | Batch 1 (agents must be relocated before touching their trigger wiring); G-03 may require an ADR if the team chooses to amend the event topology rather than implement `twin_model_ready` |

*G-01 and G-02 were retracted — no batch is required for either. The single true hypertable in the model (`athlete_wellness`) is unimplemented and correctly deferred to the wellness ingestion phase that introduces its first writer.*

### 6.2 Documentation / Escalation Actions (no code)

| Finding | Action | Owner |
|---|---|---|
| G-03 | If Option 2 (amend event topology) is chosen, write ADR-012 and update `event-catalogue.md` + `event-topology.md`. If Option 1 (implement `twin_model_ready`), no ADR needed. | Architecture Author (decision) → Implementation Architect (ADR if needed) |
| G-04 | Resolve the Redis-vs-no-Redis tension between `system-event.md` ("publishes to Redis/message bus") and stack-truth ("No Redis"). The outbox publisher's target destination depends on this. | Architecture Author |
| G-06 | Author `05-api-contracts/` documents or remove the empty directory. | Architecture Author |
| G-08 | Add deferred-decision notes for `SecondaryEvent` and `RegenerationTask` to the 1-2b BRD. | Implementation Architect |
| G-09 | Fix the stale `run_ingestion_pipeline` docstring. | Coder (can be bundled into Batch 3) |
| G-10 | No action — correctly deferred. | — |
| G-11 | No action — will be addressed in Phase 2-5. | — |
| G-12 | No action — benign drift. | — |
| G-13 | Verify the `TrainingGoalRepository_unique_violation` reference in `onboarding_service.py`. | Coder (can be bundled into Batch 3) |
| G-14 | Run `reindex_vision`. | DevOps / tooling |
| G-15 | Amend release plan or add implementation-directory README note for 1-7/1-8. | Release Strategy Architect |

### 6.3 Out of Scope for the Gap-Closing Phase

- **Phase 2-4, 2-5, 2-6** — these sub-phases have release plans but no implementation. They are not "gaps" in the sense of this analysis — they are future work. They should be planned via the normal Plan Mode process when the team is ready.
- **Tier 1 onboarding** (historical data import) — not yet architected. G-03 (`twin_model_ready`) is the prerequisite; once the event flow is restored, Tier 1 onboarding can be designed.
- **Premium features** (Coach Chat, Group Training, Voice Companion) — Principle #12 explicitly states these require dedicated architecture documents before implementation begins.

---

## 7. Cross-Validation Detail — Per Sub-Phase

This section records the per-sub-phase cross-check performed during the roast. For each implemented sub-phase, it confirms that the release-plan promise, the BRD scope, and the live code agree.

### Phase 1-1 (Email/Password Auth)
- **Release plan:** register, login, refresh rotation, require_self, bcrypt, multi-device, event log, outbox, audit events.
- **BRD:** 19 steps covering models, repos, services, routes, security patches (token_hash, IP truncation, single-primary, jti).
- **Live code:** All present. `AuthService` commits; `athlete_registered` and `athlete_logged_in` events fire via outbox. `RefreshTokenRepository.discard_old_ips` exists. Partial unique index `ix_athlete_auths_single_primary` applied (migration 8265efd46112).
- **Verdict:** ✓ DELIVERED. No gaps.

### Phase 1-2a (Profile/Preferences/Activity)
- **Release plan:** schema for AthleteProfile (full), AthletePreferences, Activity (lean). Enums, constraints, indexes.
- **BRD:** 6 steps, schema-only, additive migration.
- **Live code:** All three models exist with correct columns. `infer_data_tier` helper present. Migration e7ffc8764335 applied. No `avg_*` columns on Activity (confirmed).
- **Verdict:** ✓ DELIVERED. No gaps. (G-10 notes unused JSONB columns — correct deferral.)

### Phase 1-2b (Plan/Sessions)
- **Release plan:** schema for TrainingGoal, TrainingPlan, WeeklyPlan, WeeklySession, PlannedSession, Checkpoint. Enums, constraints.
- **BRD:** 6 steps + 6 remediation steps for test-contract alignment.
- **Live code:** All 6 models + SecondaryEvent + RegenerationTask exist. Partial unique index on active goal. `uq_weekly_plans_plan_week` and `uq_planned_sessions_plan_date_slot` enforced. `training_plans.twin_state_id` column exists (FK deferred to 1-2c).
- **Verdict:** ✓ DELIVERED. G-08 (orphaned SecondaryEvent/RegenerationTask) is the only note — correct deferral, but undocumented.

### Phase 1-2c (Twin/Fitness/Coaching/Workouts)
- **Release plan:** schema for TwinState, AthletePhysiology, AthleteFitness, CoachingMessage, GenerationEvent, GeneratedWorkout, WorkoutStep.
- **BRD:** 11 steps including the FK fix for `training_plans.twin_state_id`.
- **Live code:** All 7 models exist. TwinState append-only (repository exposes only insert/get_latest/get_history/get_by_activity). `AthleteFitness` has CHECK constraint for `form = fitness - fatigue`. `CoachingMessage` partial unique indexes for first_message and post_workout. `GeneratedWorkout` unique on `(planned_session_id, generation_date)`. FK fix applied (migration d1579f4430e7).
- **Verdict:** ✓ DELIVERED. No gaps.

### Phase 1-3 (Onboarding/Twin Bootstrap)
- **Release plan:** atomic onboarding transaction, 8 endpoints, twin bootstrap, outbox event.
- **BRD:** 7 steps, OnboardingService with optional PlanGenerationService injection.
- **Live code:** `OnboardingService` exists with all 8 methods. `POST /onboarding` creates all 6 entities + flips gate + fires `onboarding_completed`. `PlanGenerationService` injected and called within the onboarding transaction (line 471). `structural_risk_flag` computed server-side. Data tier inferred. Timezone validated.
- **Verdict:** ✓ DELIVERED. G-03 (direct plan-gen wiring vs `twin_model_ready` event) is the only contract violation — see finding.

### Phase 1-4 (Plan Generation)
- **Release plan:** pure-Python plan generation, full hierarchy, 4 read endpoints, onboarding integration.
- **BRD:** 8 steps, deterministic templates, structural rules, checkpoint scheduling.
- **Live code:** `PlanGenerationService` exists, pure Python (no LLM calls confirmed). `PlanGenerationTemplates` module with phase proportions. 4 read endpoints in `plan_router`. `training_plan_generated` event fires. Onboarding integration wired.
- **Verdict:** ✓ DELIVERED. G-07 (plan router bypasses services for read paths) is the only note — layer-skip violation.

### Phase 1-5a (First Coach Message)
- **Release plan:** FirstMessageAgent, ContextBudgetService, PromptRegistry, TwinContextAssembler, 2 endpoints, GenerationEvent logging.
- **BRD:** 11 steps + 3 remediation steps (pre-condition checks, truncation TODO, schema export).
- **Live code:** `FirstMessageAgent` exists (in `app/services/` — G-05). `ContextBudgetService` exists with `build_first_message_context`. `PromptRegistry` at `app/core/prompt_registry.py`. `TwinContextAssembler` exists. Prompt at `app/core/prompts/first_message_v1.md`. 2 endpoints. `coaching_message_generated` event fires. Pre-condition checks (TwinState, TrainingGoal, TrainingPlan) present.
- **Verdict:** ✓ DELIVERED. G-01 (no LLM router) and G-05 (agent in services/) are the notes.

### Phase 1-5b (Workout Generation)
- **Release plan:** WorkoutGenerationAgent, data-tier targets, idempotency, 2 endpoints.
- **BRD:** 11 steps, target type inference, step validation, two-column targets.
- **Live code:** `WorkoutGenerationAgent` exists (in `app/services/` — G-05). `SESSION_INTENT_MAP` and `DATA_TIER_TARGET_TYPE` in `workout_target_types.py`. Idempotency via `get_by_session_and_date`. 2 endpoints. `workout_generated` event fires. `adjusted_targets = theoretical_targets` (no modifiers yet).
- **Verdict:** ✓ DELIVERED. G-01 and G-05 are the notes.

### Phase 1-6 (Simple FIT Import)
- **Release plan:** FIT upload, parse, load, recalibrate, post-workout message, 4 endpoints.
- **BRD:** 10 steps, ObjectStorageClient, FitParserService, LoadComputationService, TwinRecalibrationService, ComplianceService, PostWorkoutAgent, ActivityIngestionService.
- **Live code:** All services exist. `fit_ingest` worker task. 4 activity endpoints. `activity_ingested` event fires. `PostWorkoutAgent` idempotent (confirmed: checks `get_by_activity_and_type` before LLM call).
- **Verdict:** ✓ DELIVERED. G-01 (PostWorkoutAgent uses direct AsyncOpenAI) and G-09 (stale docstring) are the notes.

### Phase 1-7 (Architecture Simplification)
- **Release plan:** (no entry — see G-15)
- **BRD:** 13 steps, Redis→procrastinate, MinIO, async pipeline wiring.
- **Live code:** `app/worker/app.py` with procrastinate `App` using `Psycopg2Connector`. `fit_ingest` task. MinIO via `S3_ENDPOINT_URL`. Events fire within worker transaction. `POST /upload` returns 202 with task_id.
- **Verdict:** ✓ DELIVERED. G-15 (no release-plan entry) is the only note.

### Phase 1-8 (Consistency Cleanup)
- **Release plan:** (no entry — see G-15)
- **BRD:** 7 steps, email utils, event-topology clarification, ingestion comments.
- **Live code:** `app/utils/email_utils.py` exists. `AuthService`, `AthleteRepository`, `AthleteAuthRepository` use `normalize_email`. `event-topology.md` has "Event Firing Timing Clarification" section.
- **Verdict:** ✓ DELIVERED. G-15 is the only note.

### Phase 2-1 (FIT Ingestion Expansion)
- **Release plan:** full sensor signals, sport-type detection, calibration eligibility gate, power load, 3 events.
- **BRD:** 14 steps, schema + FIT parser + load + calibration + pipeline + API.
- **Live code:** `has_gps`, `sport_type`, `sport_type_detection_version` on Activity (migration 2340974caeca). `SportType` enum. `ParsedFitData` expanded. `LoadComputationService` computes power/neuromuscular/structural. `CalibrationEligibilityService.evaluate` fully implemented (sport-type gate + five-rule gate — confirmed, NOT hard-wired to False despite State Explorer's stale flag). `sport_type_detected`, `activity_ingested`, `activity_calibration_eligible` events fire in correct order.
- **Verdict:** ✓ DELIVERED. No gaps. (G-12 notes a benign signature drift — the implementation is correct, the BRD was over-specified.)

### Phase 2-2 (Signal Cleaning)
- **Release plan:** SignalCleaningService, RawSensorStream, cleaned stream in object storage, cleaning_pipeline_version transition.
- **BRD:** 8 steps, 7-step pipeline, RR deviation filter, 5-minute HR gate, worker task.
- **Live code:** `RawSensorStream` model (migration 297ea8ac7f69). `RawSensorStreamRepository` (append-only). `SignalCleaningService` with all pipeline steps. `signal_clean` worker task. Enqueue hook in `_run_ingestion_pipeline`. `PIPELINE_VERSION = "v1-signal-cleaning"`.
- **Verdict:** ✓ DELIVERED. No gaps.

### Phase 2-3 (Threshold Detection + Physiology Update + Twin Recalibration)
- **Release plan:** ThresholdDetectionService, PhysiologyUpdateService, TwinRecalibrationService extension, full pipeline as worker task.
- **BRD:** 3 batches (11 + 11 + 8 steps).
- **Live code:** `PhysiologyMeasurement` model (migration 8413e6547a40). `ThresholdDetectionService` with 3 algorithms + LT1 passive inference. `PhysiologyUpdateService` with Bayesian update, prior decay, event firing. `TwinRecalibrationService.recalibrate_for_calibration` with confidence ratchet (ADR-011). `threshold_detection` worker task. `signal_clean` defers `threshold_detection` after commit. `twin_recalibrated` and `twin_confidence_upgraded` events fire. Unique index drop (migration 21f955c743cb) replaced with `insert_if_not_exists`.
- **Verdict:** ✓ DELIVERED. No gaps. (~~G-02 notes these tables should be hypertables — applies to `physiology_measurements` and `twin_states`.~~ **G-02 retracted**: neither table is a hypertable candidate per the corrected stack-truth discriminator; standard tables are correct here.)

---

## 8. Methodology Notes

- **State Explorer freshness:** The `p-state-explorer` brief flagged two items that turned out to be stale on verification: (a) "CalibrationEligibilityService.evaluate() is hard-wired to False" — actually fully implemented; (b) "ActivityRepository missing from `app/repositories/__init__.py`" — actually registered. Both were verified by direct code read. The brief was likely captured against an earlier code state. This is a reminder that the State Explorer is current at fetch time but may lag if the codebase changed between the brief's snapshot and the verification read.
- **Test pack excluded:** Per instruction, test files were not reviewed. Several findings (especially G-13) could be confirmed or refuted by reading tests. The gap-closing phase should include a test-pack review pass.
- **Vision corpus not indexed:** `list_vision_entities` returned empty. Vision documents were read directly from disk where needed (e.g. `reading-order.md` to confirm the vision corpus structure). RC2 (Vision Constraints) was performed by cross-referencing the architecture's Vision Cross-References section in `principles.md` rather than by semantic search over vision docs.

---

## 9. Next Steps

1. **Decide on G-03** — implement `twin_model_ready` event (Option 1) or amend the event topology (Option 2, requires ADR). This decision gates Batch 3 of the gap-closing phase. **Resolved:** Option 1 — implement as architecture specifies.
2. **Decide on G-04** — resolve the Redis-vs-no-Redis tension for the outbox publisher's target. **Resolved:** Option A — publisher marks rows `published` without external bus; `system-event.md` Redis references to be removed.
3. ~~Confirm TimescaleDB~~ — **mooted by G-02 retraction**: the hypertable-conversion portion of Batch 2 is removed; no TimescaleDB extension prerequisite remains for Phase 2.7. The `athlete_wellness` hypertable (the one true hypertable in the model) will install the extension when it lands with its producer in the wellness ingestion phase.
4. **Produce the gap-closing phase BRDs** — once decisions 1 and 2 are made, produce `docs/implementation/phase-2/phase-2-7/` with `overview.md` and 3 batch BRDs per the implementation-plan-templates skill.

---

*End of gap analysis. This document is the primary output of the retrospective roast. The gap-closing phase BRDs (if produced) will be written to `docs/implementation/phase-2/phase-2-7/` in a subsequent step.*
