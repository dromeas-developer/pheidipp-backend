# Pheidipp — System Architecture Index
*Entity-contract reference. Last updated May 2026.*

Every document in this index defines a precise contract: schema, invariants, events, APIs, storage model, mutation rules, failure semantics, and observability. Read only the documents relevant to the task at hand.

**No roadmap. No phase sequencing. No build planning.** For those, see `release-index.md`.
**No product behaviour or coach voice.** For those, see `vision-index.md`.

When this architecture conflicts with the release plan on technical design, this index is authoritative. When the release plan conflicts on sequencing or scope, the release plan is authoritative.

---

## Quick Reference — Authoritative Decisions

| Decision | Rule | Document |
|---|---|---|
| Activity model | Lean index only — no averages, no lap dumps | `principles.md` |
| `fit_file_key` | Required before Activity commits; never null for non-manual | `principles.md`, `01-entities/activity.md` |
| TwinState | Append-only; insert only; no UPDATE or DELETE | `01-entities/twin-state.md` |
| LLM role | Reasons about strategy from pre-computed metrics; never processes raw data | `principles.md` |
| LLM context | 2k–6k tokens per agent; `ContextBudgetService` enforces before call | `03-agents/context-budget-service.md` |
| `PhysiologicalIntent` | Shared enum across all layers; 6 values; session-level adaptation target | `00-foundations/terminology.md` |
| `PhysiologicalSegment` | Stable interface across all segmentation generations | `01-entities/physiological-segment.md` |
| Old analytical records | Never deleted; `superseded_at` on superseded records | `04-platform/versioning-and-reprocessing.md` |
| GAP | Always grade-adjusted pace; never raw pace | `02-computations/effort-normalisation.md` |
| Non-running activities | Logged in training record; excluded from twin calibration | `principles.md` |
| Processing | Async worker queue; API responses never wait for analysis | `04-platform/async-pipeline.md` |
| Calibration eligibility | Five-rule gate; always Python; never overridden manually | `02-computations/load-computation.md` |
| Confidence level | Evidence confidence ratchets up only; recommendation strength can decrease | `00-foundations/confidence-model.md` |
| Active TrainingGoal | One per athlete; partial unique index enforces | `01-entities/training-goal.md` |
| `block_id` = adaptation window | `block_id` groups on PlannedSession are the planning-level implementation of adaptation windows; `AdaptationBlockDetectionTask` detects the same pattern for observation | `01-entities/planned-session.md`, `01-entities/adaptation-observation.md` |
| AthletePhysiology | Mutable one-per-athlete; PhysiologyMeasurement is append-only history | `01-entities/athlete-physiology.md` |
| AthleteFitness | Mutable one-per-athlete; historical state captured in TwinState (inline values) | `01-entities/athlete-fitness.md` |
| Bayesian update | PhysiologyUpdateService applies observation weights and prior decay | `02-computations/physiology-update.md` |
| Banister update | FitnessUpdateService applies impulse-response formula with time constants | `02-computations/banister-update.md` |
| Lab/field test input | Updates AthletePhysiology only; AthleteFitness unchanged | `01-entities/athlete-physiology.md` |
| TwinState snapshot | Inline values (fitness, fatigue, form, thresholds, readiness) at snapshot time; no FK references to mutable records | `01-entities/twin-state.md` |
| Comparable session | Backend Python selects; LLM never chooses | `02-computations/comparable-sessions.md` |
| Race prediction | Not written at LOW confidence; not created for open training | `01-entities/race-prediction.md` |
| GenerationEvent | Written for every LLM call attempt including failures | `01-entities/generation-event.md` |
| Vision cross-references | Design philosophy, differentiators, and constraints mapped to architecture | `00-foundations/principles.md` (Vision Cross-References section) |

---

## 00-foundations/

### `00-foundations/principles.md`
The fourteen architectural invariants every engineer must internalise. The five-layer separation of concerns diagram with layer independence rule. Processing is always async. Vision cross-references mapping design philosophy, differentiators, and constraints to architecture implementations.
**Read for:** the non-negotiable rules; what the five layers are; the core activity-as-observation principle; how product vision maps to architecture.

### `00-foundations/terminology.md`
Canonical definitions for every domain term, with TypeScript schemas for all shared enums: `PhysiologicalIntentState`, `TwinConfidenceLevel`, `RecoveryModifierLevel`, `SessionType`, `PhaseLabel`, `CyclePhase`, `DataTier`.
**Read for:** any domain term definition; the `PhysiologicalIntentState` enum values; shared enum schemas.

### `00-foundations/data-tiers.md`
Tier 1–6 hardware classification table. Which tiers enable which analytical capabilities. Tier inference formula from `AthletePreferences`. Which load dimensions and threshold detection algorithms apply at each tier.
**Read for:** data tier definitions; which algorithms apply at which tier; tier inference logic.

### `00-foundations/confidence-model.md`
`TwinConfidenceLevel` state machine (LOW → MEDIUM → HIGH). Transition conditions and thresholds. Downstream effects per level on coaching language, workout targets, race prediction, and plan structure.
**Read for:** exactly when confidence transitions occur; what each level permits downstream.

### `00-foundations/event-catalogue.md`
All system events with TypeScript schemas, producers, and consumers. The authoritative integration contract between services.
**Read for:** what events exist; their payload schemas; which service produces/consumes each.

---

## 01-entities/

One document per persisted entity. Each defines the full contract: schema, invariants, state transitions, events produced/consumed, APIs, storage model, mutation rules, failure semantics, performance constraints, observability.

### `01-entities/athlete.md`
Root entity. Registration, `onboarding_complete` gate, `require_self` auth dependency. One-to-one with `AthleteProfile` and `AthletePreferences`.
**Read for:** registration flow; onboarding_complete semantics; require_self pattern.

### `01-entities/athlete-auth.md`
Authentication method storage. Provider abstraction (email, Google, Strava). Credential lifecycle. Multi-provider support and account linking.
**Read for:** how authentication is abstracted from identity; OAuth support; credential encryption; multi-provider linking.

### `01-entities/athlete-profile.md`
Stable demographics (DOB, sex, height, weight). Storage for fitted personalisation models: `gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`. Mutable only by background computation services.
**Read for:** where personalisation models are stored; `sex = 'female'` enabling cycle tracking; which profile fields are immutable.

### `01-entities/athlete-preferences.md`
Mutable training configuration. `weekly_schedule` JSONB structure. `hr_source` enum values and their data tier implications. `sport_background` crossover athlete flag.
**Read for:** `weekly_schedule` JSONB structure; `hr_source` enum; data tier inference from preferences.

### `01-entities/training-goal.md`
Goal context container. Partial unique index enforcing one active goal per athlete. Immutable semantic fields. PATCH restricted to status, goal_event_date, goal_description.
**Read for:** TrainingGoal field list; one-active-goal invariant; what is immutable after creation.

### `01-entities/training-plan.md`

Periodised plan for a TrainingGoal. `phases` JSONB structure. `phase_arc` — strategic intent per week (no session-level detail). Supersession chain (old plan marked `superseded_at`, never deleted). Regeneration triggers.
**Read for:** `phases` and `phase_arc` structure; supersession pattern; plan regeneration triggers.

### `01-entities/weekly-plan.md`

Weekly session schedule within a training plan. Created by the weekly synthesis agent. Contains `AdjustedWeeklyIntent` and `WeeklySession[]`. Status lifecycle: synthesised → active → completed. `accumulated_fatigue_delta` feeds forward to next pre-week review.
**Read for:** weekly plan schema; session schedule structure; how weekly plans relate to the training plan phase arc.

### `01-entities/planned-session.md`

Individual training session in a weekly plan. FK to `WeeklyPlan` (not directly to `TrainingPlan`). Full status machine: `pending → generated → completed / skipped / missed / redistributed`. Session lifecycle transitions. Structural distribution rules enforced by weekly synthesis agent.
**Read for:** `PlannedSession` status machine; skip/miss/redistribute transitions; relationship to WeeklyPlan.

### `01-entities/generated-workout.md`
Day-of workout. Two-column target storage (`theoretical_targets` and `adjusted_targets`). Modifier computation chain summary. `WorkoutStep` FK relationship. Idempotent generation.
**Read for:** two-column target structure; modifier chain; when theoretical equals adjusted; idempotency.

### `01-entities/workout-step.md`
Individual step within a GeneratedWorkout. `physiological_intent` is never null. Target type rules by data tier. How `physiological_intent` connects to `PlannedSegment` and compliance analysis.
**Read for:** `physiological_intent` invariant; which targets are populated at which data tier; step structure.

### `01-entities/activity.md`
The lean physiological observation index. `fit_file_key` hard prerequisite. No global averages — ever. Load score fields (null at creation; populated by LoadComputationService). Calibration eligibility flag. Full ingestion state diagram.
**Read for:** Activity field list; `fit_file_key` invariant; why no averages are stored; ingestion state diagram.

### `01-entities/twin-state.md`
Snapshot assembler — inlines actual values (fitness, fatigue, form, thresholds, readiness) at snapshot time rather than holding FK references to mutable records. Five recalibration triggers including the new `physiology_input` trigger for lab/field tests. Confidence level computation from `AthletePhysiology.lt2.prior_weight`. When a new TwinState is and is not written (form shift > 1 unit threshold). Context assembly digest for agents.
**Read for:** TwinState schema; why it inlines values instead of using FKs; when TwinStates are written; context assembly output; confidence computation.

### `01-entities/athlete-physiology.md`
Per-athlete physiological parameter estimates: LT1, LT2, CP, VO2max, max HR. Mutable current-state entity with historical state captured in TwinState (inline values). Append-only `PhysiologyMeasurement` history for raw measurement data. `MeasurementSource` enum. State transition diagram from bootstrapped through lab_calibrated. API: `POST /physiology/measurements` accepts lab_test and field_test sources only.
**Read for:** parameter schema; observation history structure; TwinState inline snapshot design; how lab tests flow through (high-level); state transitions; what parameters are null at onboarding.

### `01-entities/athlete-fitness.md`
Per-athlete Banister model rolling state: fitness, fatigue, and form per dimension. Mutable one-per-athlete; historical state captured in TwinState (inline values). Form-to-readiness-descriptor mapping (form scores never exposed to athletes or agents). Three-dimensional activation (Phase 6c: nullable aerobic/neuromuscular/structural columns).
**Read for:** fitness/fatigue/form schema; why fitness scores are never exposed as numbers; TwinState inline snapshot design; how AthleteFitness relates to AthletePhysiology.

### `01-entities/athlete-wellness.md`
Daily passive wellness record. Upsert/additive-merge semantics. `min_sleeping_hr_bpm` as resting HR anchor. `hrv_overnight_avg_ms` preferred over morning measurement.
**Read for:** wellness field list; upsert semantics; why min_sleeping_hr is the resting HR anchor.

### `01-entities/athlete-wellness-baseline.md`
Cached rolling baseline per signal. 14-value minimum gate. Median/IQR formula. Signal weights table for recovery modifier composite.
**Read for:** baseline computation formula; signal weights used in recovery modifier; minimum sample count gate.

### `01-entities/cycle-phase-log.md`
Menstrual cycle start date log. Phase computation logic. Population composite adjustments per phase. Luteal thermoregulatory modifier. Ovulatory structural load flag.
**Read for:** cycle phase computation; population composite adjustments; luteal temperature offset; structural load flag.

### `01-entities/weather-forecast.md`
Weather per athlete per training date. Heat index computation formula. Heat and wind adjustment formulas. Luteal temperature offset stacking. Graceful degradation on fetch failure.
**Read for:** heat index formula; weather adjustment formulas; how luteal modifier stacks; failure degradation.

### `01-entities/execution-observation.md`
Pre-computed execution findings. Python-derived; never LLM-derived. Phase evolution (lap-v1 → segment-v1). `coaching_observations` schema. Null handling for manual entries.
**Read for:** `coaching_observations` structure; what is Python-computed vs LLM-written; phase evolution of analysis depth.

### `01-entities/physiological-segment.md`
Stable interface across all segmentation generations. Three segment types: `PlannedSegment` (intended), `DeviceSegment` (device-recorded), `PhysiologicalSegment` (inferred). `state_probabilities` null in Gen 1, populated in Gen 3. Supersession pattern.
**Read for:** segment schema; three-way planned/device/physiological comparison; `state_probabilities` availability; supersession.

### `01-entities/raw-sensor-stream.md`
Cleaned stream metadata record. Separate object storage key from raw FIT. `available_channels` after artifact removal. When `RawSensorStream` is not created (cleaning failure).
**Read for:** cleaned stream key pattern; channel availability semantics; cleaning failure handling.

### `01-entities/objective.md`
Per-goal coaching objective. `Objective` and `ObjectiveUpdate` schemas. Seeding rules (≤5, ≥1 maintain). Post-session update flow (Python evaluates; LLM narrates). Day-of filter by `session_types_relevant`.
**Read for:** objective and objective_update schemas; seeding invariants; evaluation timing relative to agent.

### `01-entities/race-prediction.md`
Living race prediction. Baseline formula (observed LT2 pace + endurance factor). Course and weather adjustment. Confidence gating (204 at LOW). Update triggers.
**Read for:** prediction formula inputs; confidence gating; update triggers; `weather_adjusted_seconds` timing.

### `01-entities/athlete-integration.md`
Third-party platform connection (intervals.icu, Garmin). Credentials encrypted; never returned by API. Sync cursor. DELETE removes credentials but retains Activity records.
**Read for:** integration field list; credential handling; what DELETE does.

### `01-entities/workout-library-entry.md`
Curated substitution template. `EmbeddedStep` structure. Substitution query filters and ranking. Promotion criteria (≥3 offers, ≥0.6 acceptance rate).
**Read for:** library entry schema; substitution query logic; promotion conditions.

### `01-entities/adaptation-observation.md`
Block-level adaptation signal. `yield_by_intent_state` JSONB. Recovery trajectory measurement. Plan personalisation from accumulated observations.
**Read for:** adaptation observation schema; what yield profiles contain; how they feed plan generation.

### `01-entities/checkpoint.md`
Scheduled assessment point within a training plan. Five types: calibration, benchmark, race_simulation, secondary_race, progress_review. One-to-one with PlannedSession. Status lifecycle: scheduled → completed/skipped. Completion fields set atomically. Produces `checkpoint_completed` event.
**Read for:** checkpoint types; scheduling logic; completion flow; event contract.

### `01-entities/regeneration-task.md`
Two-step Propose→Confirm flow for target_performance date changes. Enforces coach authority boundary via distinct API endpoints. One pending proposal per training_goal_id (unique partial index). 14-day expiration window. Plain English rationale stored with each proposal.
**Read for:** regeneration trigger conditions; proposal/confirm/decline API contracts; authority boundary enforcement; expiration handling.

---

## 02-computations/

One document per computation algorithm. Inputs → outputs → formulas → version history.

### `02-computations/load-computation.md`
Aerobic, neuromuscular, and structural load formulas. Calibration eligibility five-rule gate. Version history from heuristic to threshold-referenced to personalised.
**Read for:** exact load formulas; calibration eligibility rules.

### `02-computations/banister-update.md`
Banister impulse-response update formula. Population default time constants (fitness τ = 42 days, fatigue τ = 7 days). Individual time constant fitting. Form-to-descriptor mapping for LLM agents. How load scores from Activity feed into fitness/fatigue scores.
**Read for:** Banister update formula; time constant semantics; individual fitting; form descriptor mapping.

### `02-computations/threshold-detection.md`
HR deflection algorithm. HRV inflection algorithm. Power-to-HR ratio. Confidence transition thresholds.
**Read for:** threshold detection algorithms; when each algorithm applies.

### `02-computations/physiology-update.md`
Bayesian update mechanism for physiological parameters. Observation weights by source (questionnaire 0.5 → lab_test 12–15). Prior decay (42-day time constant). Lab test and field test ingestion flows. Training-derived continuous updates. How observations from threshold-detection feed into the posterior.
**Read for:** Bayesian update formula; observation weights; lab/field test flows; training-derived update pipeline.

### `02-computations/effort-normalisation.md`
GAP invariant. Generation 1 static formula. Generation 2 per-athlete curve (≥20 sessions, R²≥0.70). Generation 3 personalised cost model. Active generation selection logic. Downstream consumers.
**Read for:** GAP formula; generation selection logic; what changes between generations; all consumers.

### `02-computations/wellness-modifier.md`
Baseline → deviation → composite → GREEN/AMBER/RED pipeline. Signal weights. Recovery modifier thresholds. Cycle composite adjustments. Luteal thermal offset. Weather adjustment formulas. `wellness_update` TwinState trigger.
**Read for:** full wellness modifier pipeline; signal weights; cycle adjustments; weather formulas.

### `02-computations/signal-cleaning.md`
All 7 preprocessing steps in order with code. Artifact removal thresholds. Smoothing parameters (HR EMA α=0.1; power/pace Savitzky-Golay). Derived metrics. Rolling feature windows. Failure conditions.
**Read for:** exact preprocessing steps; artifact thresholds; smoothing parameters; failure handling.

### `02-computations/segmentation-heuristic.md`
Generation 1 threshold-based segmentation. HR zone classification. Confidence computation. Known failure modes (ambiguous transitions, noisy HR, recovery interval misclassification).
**Read for:** Gen 1 algorithm; why confidence is low for ambiguous transitions; Gen 1 failure modes.

### `02-computations/segmentation-hmm.md`
Generation 3 HMM. Why HMM fits (four reasons). Architecture: 7 states, feature vectors, transition matrix, Gaussian emissions. Viterbi + forward-backward inference. Population vs per-athlete model. Fallback chain.
**Read for:** HMM architecture; why HMM was chosen; inference algorithms; model training and fallback.

### `02-computations/session-count.md`
Deterministic session count computation from target distribution and athlete preference. Pure Python function — no LLM reasoning required.
**Read for:** session count rules; how target distribution intensity profile affects session count; invariant: lower of computed and preference wins.

### `02-computations/plan-generation.md`
Hub document for plan generation. Defines shared types (PhaseArcEntry, CheckpointDescriptor), inputs (PlanGenerationInputs), persistence logic (persistPlan, createFirstWeeklyPlan), and regeneration triggers. Mode-specific computation is split across four files:
- `plan-generation-race.md` — LLM-driven hypothesis generation with constraint-first validation
- `plan-generation-fitness-improvement.md` — objective-driven rolling blocks, block renewal, checkpoint scheduling
- `plan-generation-maintenance.md` — rolling 4-week block, consistency tracking, transition detection
- `plan-generation-recovery.md` — severity-driven 3-phase arc, healing assessment, setback detection
**Read for:** shared types and inputs; persistence logic; regeneration triggers; navigation to mode-specific files.

### `02-computations/adaptation-signature.md`
Hard adaptation window definition. Three adaptation signal dimensions (fatigue depth, recovery trajectory, next-session execution). Yield profile computation. How yield feeds plan personalisation. Plan structure as data collection.
**Read for:** how adaptation is measured; yield profile computation; how results feed plan personalisation.

### `02-computations/comparable-sessions.md`
Two-pass algorithm: hard filters then weighted similarity (0.35 fitness + 0.25 duration + 0.25 load + 0.15 phase position). 0.50 minimum threshold. Agent context block structure. Null handling.
**Read for:** comparable session algorithm; similarity weights; minimum threshold; what the agent receives.

### `02-computations/objective-management.md`
Seeding rules (max 5, ≥1 maintain, tier-based categories). Post-session evaluation code. Objective achievement detection. Weekly review cadence.
**Read for:** seeding logic; how direction_of_change is computed; achievement criteria; update timing.

---

## 03-agents/

One document per LLM agent. Context inputs, output contract, voice constraints, idempotency, failure semantics.

### `03-agents/first-message-agent.md`
Context budget ~3k–5k tokens. Full context type. Output: four paragraphs. Must reference `sport_background` and `structural_risk_flag`. One per goal; 409 on second call.
**Read for:** first message context structure; four-paragraph output contract; idempotency; quality bar.

### `03-agents/workout-generation-agent.md`
Context budget ~2k–3k tokens. Target type rules by data tier. `physiological_intent` derivation from session type. Full modifier chain (Python-computed before agent runs). Idempotent generation.
**Read for:** workout context structure; target type by tier; how modifier chain reaches the agent; step intent derivation.

### `03-agents/post-workout-agent.md`
Context budget ~3k–6k tokens. Null handling for execution, comparable session, and objective updates. Three-paragraph output structure. Pre-conditions (ObjectiveUpdateService must run first). Prompt version history.
**Read for:** post-workout context structure; null handling rules; pre-condition ordering; paragraph structure.

### `03-agents/skip-conversation-agent.md`
Context budget ~1k token. SkipReason classification. SkipFlow routing to redistribution, injury, or illness handling.
**Read for:** skip reason enum; how classification drives lifecycle flow.

### `03-agents/wellness-alert-agent.md`
Wellness alert (2k tokens), phase transition (1k), plan regeneration (1k). Frequency gates per message type. Output: one paragraph each.
**Read for:** proactive message triggers; frequency gates; context per message type.

### `03-agents/hypothesis-agent.md`
Context budget ~3k–5k tokens. Generates three strategic approaches using four reasoning dimensions. Produces hypotheses with rationale, intensity balance, and risk notes. Not idempotent.
**Read for:** hypothesis generation context; four reasoning dimensions; distinctness rule; output format.

### `03-agents/hypothesis-selector-agent.md`

Context budget ~4k–6k tokens. Scores and selects best approach. Synthesizes strategic framework with phase arc, race schedule, checkpoint schedule, intensity balance. Scoring: twin alignment (35%), goal fit (25%), objective alignment (25%), injury safety (15%).
**Read for:** scoring criteria; constraint-first validation; framework synthesis with phase arc; checkpoint scheduling logic.

### `03-agents/pre-week-review-agent.md` (Python service)

**Python service, not an LLM agent.** Evaluates the plan's intent for the upcoming week against accumulated execution data and current athlete state. All decision logic is deterministic — no LLM reasoning required.
**Read for:** adjustment sources (fatigue correction, schedule constraint, adaptation acceleration); deterministic decision logic; constraints on what can/cannot be adjusted.

### `03-agents/weekly-synthesis-agent.md`

Context budget ~3k–5k tokens. Produces the actual session schedule for a single week. Reads adjusted intent from pre-week review (Python service) and current athlete state. Outputs WeeklyPlan with session count, types, days, and approximate duration. Inherits all session placement rules from the deprecated session-planner-agent. Session count is a pre-computed input — the agent does not compute it.
**Read for:** session placement rules; intensity bias → session type distribution; race week handling; template fallback.

### `03-agents/context-budget-service.md`
`ContextBudgetService` implementation for all three primary agents. Token budget enforcement before API call. Priority truncation ordering per agent.
**Read for:** how context is assembled; how budgets are enforced; truncation priority ordering.

---

## 04-platform/

### `04-platform/async-pipeline.md`
Full task inventory with triggers, steps, retry policies, and timeouts. Execution guarantees (at-least-once; tasks must be idempotent). DLQ routing. Task status visibility API.
**Read for:** every task that exists; retry policies; what triggers each task; idempotency requirements.

### `04-platform/event-topology.md`
End-to-end event flow diagram from athlete action to coach message. Scheduled task cron expressions. Consumer fanout for multi-consumer events. Ordering constraints between tasks.
**Read for:** the full pipeline wiring; which events trigger which tasks; ordering guarantees.

### `04-platform/versioning-and-reprocessing.md`
Version string format and registry. The reprocessing test. Supersession protocol (insert new, mark old `superseded_at`). Alternative pattern for Activity load scores (in-place update with version tracking). Offline reprocessing guarantees.
**Read for:** version string format; when to persist vs not; supersession protocol; load score design rationale.

### `04-platform/storage-topology.md`
PostgreSQL table classification (append-only vs mutable). Object storage key patterns. Redis usage (queue + cache). JSONB usage rationale. All critical indexes.
**Read for:** where each entity lives; object storage key patterns; index definitions; JSONB rationale.

### `04-platform/failure-handling.md`
Four failure classes (data integrity, analysis, LLM, external). Per-failure response table. DLQ schema. Athlete-visible vs silent failure classification. GenerationEvent invariant.
**Read for:** how each failure mode is handled; what is silenced vs surfaced; DLQ structure.

### `04-platform/observability.md`
Core dashboards (ingestion health, coaching quality, twin model health, session lifecycle). Structured log event schemas. P1/P2/P3 alert conditions and thresholds. Distributed trace spans for critical path.
**Read for:** what metrics to build dashboards from; alert thresholds; log event schemas; trace spans.
