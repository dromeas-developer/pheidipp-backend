# Pheidipp — Product Vision Index (Agent-Optimized)
*Structured manifest of all vision documents for agentic consumption*

This index provides machine-readable metadata for all product vision documents.
Each entry defines what a document covers, its dependencies, boundaries, and usage context. All file paths are relative to `docs/vision/`.
**Primary audience: agents and automated systems.** For human reading, refer to individual documents.

---

## Vision Document Registry

- id: product.anti-goals
  path: product/anti-goals.md
  summary: Defines what Pheidipp explicitly avoids becoming to preserve strategic clarity, product identity, and coaching focus.
  tags: [anti-goals, scope-control, positioning]
  depends_on: [product.global-invariants]
  read_for: preventing feature creep; evaluating roadmap proposals; maintaining product clarity.
  scope_boundary: These are hard boundaries — features aligning with these anti-goals are out of scope regardless of market demand.

- id: product.brand-philosophy
  path: product/brand-philosophy.md
  summary: Defines Pheidipp's identity as a purposeful running coach that hides complexity and surfaces conclusions in plain language.
  tags: [brand, coach-voice, running-only, no-ai-feel]
  depends_on: []
  read_for: coach voice boundaries; why the product is minimalist; what the name means.
  scope_boundary: Coaching expertise limited to running performance; sleep/nutrition/injury redirected professionally.

- id: product.constraints
  path: product/constraints.md
  summary: Enforces three deliberate constraints: running-only twin model, no workout builder, and no raw data surfaces.
  tags: [constraints, running-only, data-quality, unsynced-workouts]
  depends_on: [twin.core]
  read_for: what Pheidipp deliberately does not do and why; the raw data visualisation rule.
  scope_boundary: Non-running activities excluded from twin calibration; athletes cannot create/edit workouts; no Garmin/Strava-style charts.

- id: product.differentiators
  path: product/differentiators.md
  summary: Lists twelve key differentiators including running-specific accuracy, 3D load, women's cycle integration, and same-day workout generation.
  tags: [differentiators, competitive-positioning]
  depends_on: []
  read_for: competitive positioning; what makes Pheidipp distinct and why it's durable.
  scope_boundary: Differentiators derive from core architecture choices, not superficial features.

- id: product.goal-modes
  path: product/goal-modes.md
  summary: Shifts coaching posture between race/event mode (periodised, urgent), fitness improvement mode (developmental, progressive), maintenance mode (consistent, patient), and recovery mode (protective, healing).
  tags: [goal-modes, coaching-posture, plan-structure]
  depends_on: [coach.plan-visibility]
  read_for: how coaching language and emphasis changes based on the athlete's goal context across all four modes; which coaching posture applies to fitness improvement, maintenance, and recovery scenarios.
  scope_boundary: Core analysis quality identical in both modes; only orientation differs.

- id: product.global-invariants
  path: product/global-invariants.md
  summary: Defines the immutable truths that govern all Pheidipp decisions — from product behavior to coaching logic to architectural choices.
  tags: [invariants, principles, identity, constraints]
  depends_on: []
  read_for: validating feature alignment; preserving product identity; understanding core constraints.
  scope_boundary: These are non-negotiable principles; features violating them are by definition out of scope.

- id: product.integrations
  path: product/integrations.md
  summary: Ingests raw data only (never processed metrics) from intervals.icu, FIT uploads, Garmin, and wellness platforms.
  tags: [integrations, data-quality, wellness, intervals-icu]
  depends_on: [twin.data-philosophy]
  read_for: integration philosophy; which platforms are connected and why; data quality rationale.
  scope_boundary: Does not compete with Garmin/Strava for raw data browsing; wellness data used only for recovery context.

- id: product.premium-features
  path: product/premium-features.md
  summary: Defines Free Coach Chat scope, group training model, and Voice Companion as premium extensions of core coaching.
  tags: [premium, coach-chat, group-training, voice]
  depends_on: [coach.voice-and-format]
  read_for: Free Coach Chat scope and redirect language; group training model; voice vision.
  scope_boundary: Coach Chat excludes sleep/nutrition/injury; group training has no social layer; voice is same content as text.

- id: product.plan-generation
  path: product/plan-generation.md
  summary: Defines how Pheidipp generates a strategic roadmap (phase arc) for training — not a session schedule. Covers the four-tier coaching model, hypothesis selection, first-week atomic creation, and gating on twin readiness.
  tags: [plan-generation, strategic-roadmap, phase-arc, weekly-coaching]
  depends_on: [product.global-invariants, product.secondary-events, twin.confidence-and-uncertainty]
  read_for: how training plans are generated; the strategic roadmap concept; why sessions are not generated upfront; the four-tier coaching model.
  scope_boundary: Plan generation produces a phase arc; sessions are produced by the weekly coaching rhythm; coach decides, athlete accepts or abandons.

- id: product.hypothesis-selection
  path: product/hypothesis-selection.md
  summary: Defines how the coach explores three genuinely different strategic approaches, validates them against hard invariants, scores them, and selects the best one for the athlete.
  tags: [hypothesis-selection, strategic-exploration, scoring, coaching-philosophy]
  depends_on: [product.plan-generation, product.global-invariants]
  read_for: why three hypotheses; the four reasoning dimensions; constraint-first validation; scoring criteria; why the coach decides.
  scope_boundary: Each hypothesis differs in ≥2 dimensions; invalid hypotheses discarded before scoring; coach selects, athlete does not choose.

- id: product.weekly-coaching-rhythm
  path: product/weekly-coaching-rhythm.md
  summary: Defines the three-timescale coaching model (plan → weekly rhythm → daily workout) and how the weekly review adjusts emphasis based on accumulated reality without breaking the strategic roadmap.
  tags: [weekly-coaching, adaptive-planning, three-timescales, disruption-absorption]
  depends_on: [product.plan-generation]
  read_for: how the weekly rhythm works; what changes and what doesn't; how disruptions are absorbed; coach authority at the weekly level.
  scope_boundary: Weekly rhythm adjusts emphasis within the current phase; cannot change the strategic direction; most adaptation happens here, not through plan regeneration.

- id: product.training-plan-checkpoints
  path: product/training-plan-checkpoints.md
  summary: Defines the checkpoint hierarchy, scheduling logic, completion flow, adaptive recovery, and how evolution happens at the weekly level rather than through plan regeneration.
  tags: [checkpoints, calibration, benchmark, race-simulation, adaptive-evolution, weekly-absorption]
  depends_on: [product.plan-generation, product.weekly-coaching-rhythm, twin.confidence-and-uncertainty]
  read_for: checkpoint types and purposes; scheduling logic; completion flow; adaptive recovery rules; how disruptions are absorbed at the weekly level.
  scope_boundary: Checkpoints are recommended, not mandatory; declined checkpoints use conservative assumptions; session disruption absorbed by weekly rhythm, not plan regeneration.


- id: twin.adaptation-signature
  path: twin/adaptation-signature.md
  summary: Learns individual adaptation patterns by treating training blocks (not sessions) as atomic stimulus units with controlled recovery observation windows.
  tags: [adaptation, training-blocks, periodisation, data-collection]
  depends_on: [twin.load-fatigue, twin.training-zones, twin.external-modifiers]
  read_for: how the twin learns per-athlete adaptation; plan structural rules; data requirements.
  scope_boundary: Requires 6-8 weeks for meaningful signal; female cycle phase controlled for in adaptation measurements.

- id: twin.confidence-and-uncertainty
  path: twin/confidence-and-uncertainty.md
  summary: Defines how Pheidipp handles uncertainty in athlete modeling, with principles for confidence evolution, communication, and conservative adaptation.
  tags: [confidence, uncertainty, trust, probabilistic-modeling]
  depends_on: [twin.core, twin.load-fatigue]
  read_for: recommendation confidence; uncertainty handling; adaptation safety; trust systems.
  scope_boundary: Confidence applies per-model-component, not globally; all uncertainty handling prioritizes athlete safety over system assertiveness.

- id: twin.core
  path: twin/core.md
  summary: Establishes the Digital Twin as a running-only physiological model that excludes non-running activities from calibration.
  tags: [twin, running-only, honesty-invariant]
  depends_on: []
  read_for: the fundamental scope of the twin; why non-running activities are excluded.
  scope_boundary: Non-running activities logged but excluded from all twin learning; twin never pretends to know more than it does.

- id: twin.cold-start
  path: twin/cold-start.md
  summary: Initializes twin from three confidence tiers with honest uncertainty communication. Lab/test uploads elevate threshold confidence within Tier 1 (with training history) or serve as Tier 2 foundation (without training history).
  tags: [cold-start, onboarding, confidence-tiers, lab-upload]
  depends_on: [twin.core]
  read_for: how the twin initialises; lab/test upload handling; what Tier 2 is and when it becomes available; the model build UX decision.
  scope_boundary: Tier 3 uses conservative ranges; specificity earned through real training data over time.

- id: twin.data-philosophy
  path: twin/data-philosophy.md
  summary: Prioritizes real signals over assumptions, data quality over quantity, and continuous learning while excluding non-running data from the running model. Lab/test uploads accepted as valid calibration inputs.
  tags: [data-philosophy, data-quality, honesty-invariant, lab-upload]
  depends_on: [twin.core]
  read_for: why certain data is excluded; lab/test upload handling; the accuracy-first philosophy.
  scope_boundary: Manual/low-quality sessions excluded from twin calibration; no cross-modal conversion factors ever applied.

- id: twin.external-modifiers
  path: twin/external-modifiers.md
  summary: Uses passive wellness signals (sleep, HRV, menstrual cycle, time-of-day) as trend-based modifiers to readiness without subjective input.
  tags: [wellness, sleep, hrv, womens-cycle, time-of-day]
  depends_on: [twin.load-fatigue]
  read_for: all sleep and wellness signal detail; resting HR definition; trend thresholds.
  scope_boundary: Single-night anomalies ignored; overnight min HR used (not morning spot checks); cycle phase weighted by individual correlation.

- id: twin.execution-patterns
  path: twin/execution-patterns.md
  summary: Analyzes rep-level execution patterns (drift, fade, sandbagging) and session shapes to build behavioural profiles from actual training data.
  tags: [execution-analysis, rep-level, session-shape, behavioural-profile]
  depends_on: [twin.load-fatigue, twin.training-zones]
  read_for: how execution is analysed by session type; recovery interval analysis rules.
  scope_boundary: Recovery intervals analyzed via pace/power pullback or HR trajectory—not HR zone; macro consistency required for valid comparisons.

- id: twin.layers
  path: twin/layers.md
  summary: Describes the five-layer twin architecture (fitness/fatigue, thresholds, adaptation, external modifiers, execution patterns) and their interactions.
  tags: [twin, layers, architecture]
  depends_on: [twin.core]
  read_for: the five-layer structure as an overview; how layers feed each other.
  scope_boundary: Layers require minimum data quality and duration to become meaningful; Layer 5 validates Layers 1-2.

- id: twin.load-fatigue
  path: twin/load-fatigue.md
  summary: Models three load dimensions (aerobic, neuromuscular, structural) with individual recovery time constants and data-quality-aware computation.
  tags: [load-model, data-quality, gap-rule, crossover-athlete, womens-cycle]
  depends_on: [twin.core, twin.data-philosophy]
  read_for: load computation logic; data tier definitions; crossover athlete risk; GAP rule.
  scope_boundary: Non-running activities excluded from load calibration; sessions without device data (Tiers 5-6) logged but not used for twin updates.

- id: twin.training-zones
  path: twin/training-zones.md
  summary: Tracks dynamic physiological thresholds using signal hierarchy (RR intervals > HR > lab/test uploads > calibration sessions > inference) with passive updates from normal training. Handles confidence degradation and execution-data divergence for lab-provided values.
  tags: [zones, thresholds, rr-intervals, calibration, lab-upload]
  depends_on: [twin.core, twin.data-philosophy]
  read_for: how thresholds are detected and updated; signal hierarchy; lab/test upload handling; two-column display rationale.
  scope_boundary: RPE not used as primary signal; optical HR sufficient for zone tracking but not RR-based threshold detection.

- id: twin.womens-cycle
  path: twin/womens-cycle.md
  summary: Integrates menstrual cycle phase as a first-class physiological modifier affecting load, readiness, thermoregulation, and injury risk.
  tags: [womens-cycle, hormonal-model, thermoregulation, injury-risk]
  depends_on: [twin.external-modifiers]
  read_for: cycle phase effects; implementation approach; coach language guidance.
  scope_boundary: Low-friction input (day-one flag only); individual variation learned from execution data; not a separate tracker.


- id: coach.daily-view
  path: coach/daily-view.md
  summary: Presents a living pre-session briefing showing today's workout, weather impact, recovery status, and relevant objectives with two-column targets.
  tags: [daily-view, home-screen, two-column-targets, weather-adjustment]
  depends_on: [twin.load-fatigue, twin.external-modifiers, coach.plan-visibility]
  read_for: home screen structure and content; navigation model; what appears and when.
  scope_boundary: Future sessions show intent only (no specific targets); navigation is backward snapshots, not scroll feed.

- id: coach.decision-authority
  path: coach/decision-authority.md
  summary: Defines the relationship between athlete autonomy and coaching authority, ensuring decisive guidance without controlling behavior.
  tags: [authority, autonomy, recommendations, coaching-behavior]
  depends_on: [coach.voice-and-format, twin.confidence-and-uncertainty]
  read_for: recommendation systems; coaching behavior; athlete interaction; UX guidance.
  scope_boundary: Authority is always conditional on confidence and athlete trust; the system never assumes control over training decisions.

- id: coach.first-message
  path: coach/first-message.md
  summary: Delivers a four-paragraph first message that demonstrates genuine data analysis, plan rationale, and concrete preview to establish trust.
  tags: [first-message, onboarding, trust-building]
  depends_on: [twin.cold-start, coach.voice-and-format]
  read_for: first message structure; what "genuinely seen" means in practice; quality bar.
  scope_boundary: Must contain specific observations from real data; never generic or templated; model build wait is intentional.

- id: coach.objectives
  path: coach/objectives.md
  summary: Maintains living objectives that connect sessions to long-term development, seeded from twin analysis and updated weekly.
  tags: [objectives, strengths-gaps, progress-tracking]
  depends_on: [twin.adaptation-signature]
  read_for: objectives system design; how strengths and gaps are framed; update cadence.
  scope_boundary: Objectives go beyond PBs to physiological insights; only relevant objectives shown per session.

- id: coach.plan-visibility
  path: coach/plan-visibility.md
  summary: Shows the macro plan view (phase arc), near-term sessions from the weekly plan, today's session with two-column targets, and checkpoint visibility. Data sources are clearly separated: phase arc for the big picture, weekly plan for near-term sessions.
  tags: [plan-visibility, phase-arc, near-term-sessions, checkpoint-visibility, data-sources]
  depends_on: [product.plan-generation, product.weekly-coaching-rhythm]
  read_for: what the athlete can see of their plan; how data sources are separated; phase transitions as coaching moments; why raw data is not shown.
  scope_boundary: Macro view shows phase arc; near-term sessions come from weekly plan; daily targets generated on the day; no raw data charts.

- id: coach.post-workout
  path: coach/post-workout.md
  summary: Generates three-paragraph post-session analysis covering compliance, rep-level execution story, historical correlation, and objective progress.
  tags: [post-workout, execution-analysis, historical-correlation, objectives]
  depends_on: [twin.execution-patterns, twin.adaptation-signature, coach.voice-and-format]
  read_for: post-workout message content; historical correlation importance; format rules.
  scope_boundary: Never uses raw numbers without context, acronyms, or generic encouragement; requires comparable session identification from twin.

- id: coach.race-prediction
  path: coach/race-prediction.md
  summary: Provides living race predictions adjusted for personalised weather response, course profile, and current twin fitness estimates.
  tags: [race-prediction, weather-response, course-profile]
  depends_on: [twin.load-fatigue, twin.external-modifiers]
  read_for: race prediction components; weather response modelling; how conditions affect training design.
  scope_boundary: Weather adjustment based on individual execution history (not population averages); course data triggers terrain-specific sessions.

- id: coach.substitution
  path: coach/substitution.md
  summary: Handles workout substitution, illness, injury, and unsynced workouts through bounded conversations and conservative plan adjustments.
  tags: [substitution, illness, injury, unsynced-workouts]
  depends_on: [twin.load-fatigue, twin.external-modifiers]
  read_for: full substitution and skip logic; illness vs injury handling; unsynced workout rules.
  scope_boundary: Workout library is curated (not athlete-contributed); injury flow never assesses/diagnoses; unsynced workouts ask before assuming.

- id: coach.visualisation
  path: coach/visualisation.md
  summary: Shows only visualisations requiring twin context (comparative overlays, session shapes, contextual zone compliance, fitness trends).
  tags: [visualisation, comparative-analysis, session-shape]
  depends_on: [twin.execution-patterns, twin.adaptation-signature]
  read_for: visualisation scope; what Pheidipp shows vs defers to existing tools.
  scope_boundary: No raw charts (pace/HR over time); if it could be a Strava screenshot, it doesn't exist here.

- id: coach.voice-and-format
  path: coach/voice-and-format.md
  summary: Enforces natural-language, three-paragraph coach messages that avoid AI-feel, acronyms, raw numbers, and generic encouragement.
  tags: [coach-voice, message-format, no-ai-feel]
  depends_on: []
  read_for: all coach message formatting rules; what the coach must and must not say.
  scope_boundary: Never uses bullets/headers/emojis; always names specific patterns and connects to past sessions.
