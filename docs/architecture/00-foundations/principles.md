# Principles — Architectural Invariants & Core Decisions

## Purpose
- Defines the non-negotiable rules every engineer must internalise before touching any part of the system
- Establishes the five-layer separation of concerns that governs all data flow
- Several invariants below implement philosophical commitments from `docs/vision/twin/data-philosophy.md` — see inline references in invariants #8, #9, #11, #14

## Invariants

1. **Activities are physiological observations, not workout summaries.** `Activity` stores what the twin model needs. It never stores avg_hr, avg_pace, avg_power, or lap dumps. The FIT file is the source of truth.

2. **The twin computes metrics deterministically in Python. The LLM reasons about structure and instantiates plans from pre-computed metrics. Python validates structural invariants.** All analytical computation — fitness scoring, threshold estimation, execution classification, load accumulation, wellness trend analysis — lives in Python services. LLM agents receive pre-computed metrics and twin state summary, then reason about plan structure (strategic hypotheses, week-by-week session placement) and generate narrative. Python validates all structural invariants during plan generation and session lifecycle.

3. **`fit_file_key` is a hard prerequisite.** No `Activity` record commits without its raw file stored in object storage. This is the reprocessing anchor. If object storage fails, the task retries. No exceptions.

4. **TwinState is append-only.** Every recalibration appends a new record. Old records are never updated or deleted. This is what makes coaching decisions auditable and reprocessing safe.

5. **Every analytical output is versioned.** `ingestion_pipeline_version`, `cleaning_pipeline_version`, `segmentation_version`, `analysis_version`, `model_version`. A version string is a frozen, reproducible pipeline snapshot — not a mutable label.

6. **No global session averages are persisted.** Average HR, pace, power — none of these are on `Activity`. Ever.

7. **All heavy processing is async.** FIT parsing, twin recalibration, post-workout analysis — all run in a worker queue (Celery or ARQ over Redis). API responses never wait for these.

8. **Non-running activities are excluded from twin calibration.** They appear in the training record. They never feed load computation, threshold detection, execution analysis, or adaptation modelling. *(Implements vision principle "Non-Running Data Does Not Corrupt the Running Model" from `docs/vision/twin/data-philosophy.md`.)*

9. **Raw pace is never used.** Grade-adjusted pace (GAP) is the standard input throughout. See `02-computations/effort-normalisation.md`. *(Implements vision principle "Real Signals, Not Assumptions" from `docs/vision/twin/data-philosophy.md`.)*

10. **Old analytical records are never deleted.** Superseded records receive `superseded_at`. New records are inserted alongside.

11. **Anti-goals are architectural constraints.** The following product boundaries are enforced through bounded models and API design: no dashboard UX, no raw-data-first experiences, no multi-sport conversion factors, no athlete-authored training plans. These are not merely product preferences — they are architectural governance boundaries. Future system evolution must be evaluated against these constraints. *(The "no multi-sport conversion factors" constraint implements the vision principle "Non-Running Data Does Not Corrupt the Running Model" from `docs/vision/twin/data-philosophy.md`.)*

12. **Premium features require architectural foresight.** Free Coach Chat (conversational agent), Group & Team Training (shared plan, individual twins), and Voice Companion (audio delivery surface) are defined in product vision but have no current architecture. When implemented, they must integrate with existing agent architecture, context budgeting, and coach voice constraints. These features should not bolt on as separate systems.

13. **Peer-similar bootstrap is a Tier 2 onboarding path.** For athletes without importable training history, the twin can bootstrap from anonymised models of similar athletes. This peer-similar model source, selection criteria, and application mechanism must be defined in architecture before implementation. The peer-similar path produces initial physiological estimates that are replaced by real training data as sessions accumulate.

14. **Algorithm improvements reprocess recent history.** When a calibration algorithm improves or a new metric becomes available, the system reprocesses recent calibration-eligible sessions through the new algorithm. This accelerates the benefit of improvements without waiting passively for new data. The current state (`AthletePhysiology`, `AthleteFitness`) updates to reflect the improved algorithm. Historical records (`TwinState`, `PhysiologyMeasurement`) remain untouched — the audit trail is preserved through version strings and append-only writes. The athlete receives a coaching communication explaining what changed and why. *(Implements vision principle "Continuous Learning From Real Training" from `docs/vision/twin/data-philosophy.md`.)*

## Five-Layer Separation of Concerns

```
┌──────────────────────────────────────────────────────┐
│  5. TWIN INTERPRETATION                              │
│     TwinState recalibration · coaching signals       │
├──────────────────────────────────────────────────────┤
│  4. ADAPTATION OBSERVATION                           │
│     Block-level response · yield profiles            │
├──────────────────────────────────────────────────────┤
│  3. PHYSIOLOGICAL ANALYSIS                           │
│     ExecutionObservation · segmentation              │
├──────────────────────────────────────────────────────┤
│  2. WORKOUT EXECUTION STRUCTURE                      │
│     PlannedSegment · DeviceSegment · PhysSegment     │
├──────────────────────────────────────────────────────┤
│  1. RAW SENSOR INGESTION                             │
│     FIT file · stream cleaning · load computation    │
└──────────────────────────────────────────────────────┘
```

Lower layers feed upper layers. Upper layers never reach down to read raw data directly. Each layer can be upgraded independently as long as its output interface remains stable.

## Runtime Ownership

**Owns:**
- All invariants listed above as system-wide constraints
- The five-layer dependency direction

**Does Not Own:**
- Individual entity contracts → `01-entities/`
- Computation algorithms → `02-computations/`
- Agent architecture → `03-agents/`
- Platform concerns → `04-platform/`

## Implementation Notes
- The layer independence invariant is what makes segmentation algorithm upgrades (Gen 1 → Gen 3) safe — `PhysiologicalSegment` schema is stable; only `segmentation_version` changes
- The append-only TwinState invariant is what makes it possible to explain any historical coaching decision
- The LLM narration rule keeps context windows small (2k–6k tokens) and keeps analytical logic auditable in Python

## Open Questions
- None. These invariants are settled.

---

## Vision Cross-References

This section maps product vision principles and constraints to their architecture implementations. These cross-references ensure architectural decisions trace back to intentional product philosophy.

### Vision Design Philosophy Mapping

Maps design philosophy from `docs/vision/product/brand-philosophy.md` to architecture enforcement mechanisms.

| Vision Principle | Architecture Implementation | Enforced By |
|---|---|---|
| **Blackboard Principle** — minimalist UI, text-driven, no visual noise | No dashboard UX anti-goal; API returns plain-language descriptors | Invariant #11, `form_descriptor` pattern in `athlete-fitness.md` |
| **Coach Not Dashboard** — athlete sees conclusions, not numbers | Fitness scores are internal; athletes see only `form_descriptor` | `athlete-fitness.md` API contract (raw scores never returned) |
| **No AI-Feel Communication** — plain language, no bullets/headers/emojis | Agent voice constraints enforce three natural paragraphs, no formatting | `post-workout-agent.md`, `first-message-agent.md` voice rules |
| **Data Processing Boundary** — Python computes, LLM reasons | Deterministic computation in Python; LLM receives pre-computed metrics | Invariant #2, `02-computations/` service layer |
| **Coaching Expertise Boundaries** — redirect outside running domain | *Not yet implemented in architecture* | Future: agent prompt constraints |

### Differentiator → Architecture Mapping

Maps differentiators from `docs/vision/product/differentiators.md` to architecture foundations. Each differentiator is a product promise; the architecture delivers it.

| Differentiator | Architecture Foundation | Key Entities |
|---|---|---|
| **Running-Specific Model Accuracy** — no cross-modal conversion errors | Running-only twin model; non-running excluded from calibration | `activity.md` invariant, principle #8 |
| **Three-Dimensional Load Intelligence** — aerobic/neuromuscular/structural tracked separately | Separate load dimensions with individual time constants | `activity.md` (load fields), `athlete-fitness.md` (dimensional scores) |
| **Women's Cycle-Aware Coaching** — physiological input into twin and coaching | Cycle phase integration into recovery modifier and workout targets | `cycle-phase-log.md`, `athlete-profile.md` (`cycle_personal_model`), `wellness-modifier.md` |
| **Complexity Hidden, Conclusions Surfaced** — athlete sees coaching insight, not data | Raw scores internal; plain-language `form_descriptor` returned | `athlete-fitness.md` API, agent voice constraints |
| **Same-Day Workout Generation** — specific workout generated day-of | Workout generated from freshest athlete state, not planned weeks ahead | `workout-generation-agent.md`, `generated-workout.md`, `planned-session.md` |
| **Personalised Weather Response** — athlete-specific environmental model | Individual weather performance model learned from execution history | `weather-forecast.md`, `wellness-modifier.md` |
| **Historical Correlation in Coach Messages** — session connected to past patterns | Comparable session matching with phase/fitness context | `comparable-sessions.md`, `execution-observation.md` (`coaching_observations`) |
| **Rep-Level Analysis** — granular interval execution examination | Per-rep execution analysis with pacing drift detection | `execution-observation.md` (`per_rep_analysis`) |
| **Coach Voice** — plain language, no tech jargon, reads like a human | Natural language constraints; no AI-feel formatting | Agent voice rules, `voice-and-format.md` vision |
| **Living Objectives** — sessions connect to bigger picture | Objectives seeded from twin analysis, updated weekly with evidence | `objective.md`, `objective-management.md` |

### Vision Constraints Mapping

Maps constraints from `docs/vision/product/constraints.md` to architecture enforcement. These are hard boundaries — the architecture prevents violation.

| Vision Constraint | Architecture Implementation | Enforced By |
|---|---|---|
| **Running-Only Twin Model** — no multi-sport conversion factors | Non-running activities logged in training record but excluded from twin calibration | Principle #8, `activity.md` calibration eligibility |
| **No Workout Builder** — athletes cannot create/edit workouts | Athletes have three choices: accept, substitute, or skip | Principle #11 (anti-goal), `planned-session.md` status machine |
| **No Raw Data Surfaces** — no HR/pace/power charts; only twin-context visualisations | Fitness API returns `form_descriptor` only; raw scores never exposed | `athlete-fitness.md` API contract, `form_descriptor` pattern |
| **Unsynced Workout Handling** — ask before assuming when data gaps occur | `fit_file_key` prerequisite; coach surfaces ambiguity-first check-in | `activity.md` invariant, agent prompt behavior |
| **Same-Day Training Sessions** — AM/PM slots with primary/secondary | Dual session support with recovery measured primary-to-primary | `planned-session.md` (AM/PM slots), `weekly-plan.md` |

### Vision → Architecture Reference Links

Additional explicit links between vision documents and architecture implementations:

| Vision Document | Architecture Document | Link Type |
|---|---|---|
| `docs/vision/twin/data-philosophy.md` | `principles.md` (invariants #8, #9, #11, #14) | Direct inline reference |
| `docs/vision/twin/womens-cycle.md` | `cycle-phase-log.md` (Vision Phase Mapping table) | Explicit mapping table |
| `docs/vision/coach/voice-and-format.md` | Agent voice constraints in `03-agents/*.md` | Prompt enforcement |
| `docs/vision/coach/post-workout.md` | `execution-observation.md` (Post-Workout Message Mapping) | Explicit mapping table |
| `docs/vision/coach/objectives.md` | `objective-management.md` (Vision ↔ Architecture Alignment) | Explicit mapping table |
| `docs/vision/coach/first-message.md` | `first-message-agent.md` (First Message Vision Mapping) | Explicit mapping table |
| `docs/vision/twin/external-modifiers.md` | `wellness-modifier.md` (Vision Signal Mapping) | Explicit mapping table |
