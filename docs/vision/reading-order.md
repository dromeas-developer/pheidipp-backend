# Pheidipp — Vision Reading Order

*Logical sequence for understanding the product vision. Start here if you're new to Pheidipp.*

This document provides a human-readable order for consuming the vision documents. Each section builds on the previous. For machine-readable metadata, see `vision-index.md`.

---

## I. Identity & Philosophy

*What Pheidipp is, what it isn't, and why.*

| # | Document | Purpose |
|---|----------|---------|
| 1 | [brand-philosophy](product/brand-philosophy.md) | Defines identity — the name, the minimalist approach, why the product exists. |
| 2 | [global-invariants](product/global-invariants.md) | The immutable truths. Non-negotiable principles that govern all decisions. |
| 3 | [anti-goals](product/anti-goals.md) | What Pheidipp explicitly avoids becoming. Scope boundaries that prevent feature creep. |
| 4 | [differentiators](product/differentiators.md) | What makes it distinct and why those differences are durable. |

*Read these first. Every subsequent document assumes you understand the identity layer.*

---

## II. The Digital Twin

*The physiological model that feeds everything the coach says.*

| # | Document | Purpose |
|---|----------|---------|
| 5 | [core](twin/core.md) | Foundation — running-only scope, honesty invariant. Everything twin-related depends on this. |
| 6 | [data-philosophy](twin/data-philosophy.md) | How data is prioritized and filtered. Accuracy-first lens for all downstream layers. |
| 7 | [layers](twin/layers.md) | The five-layer architecture overview. Provides the map before diving into each layer. |
| 8 | [load-fatigue](twin/load-fatigue.md) | Three load dimensions (aerobic, neuromuscular, structural) with individual recovery constants. |
| 9 | [training-zones](twin/training-zones.md) | Threshold detection and signal hierarchy. Pairs with load-fatigue as the core physiological model. |
| 10 | [cold-start](twin/cold-start.md) | How the twin initializes — confidence tiers, lab upload handling. |
| 11 | [external-modifiers](twin/external-modifiers.md) | Passive wellness signals (sleep, HRV, cycle, time-of-day). Builds on load-fatigue. |
| 12 | [execution-patterns](twin/execution-patterns.md) | Rep-level execution analysis. Builds on load-fatigue and training-zones. |
| 13 | [confidence-and-uncertainty](twin/confidence-and-uncertainty.md) | How uncertainty is handled across all models. Cross-cutting concern. |
| 14 | [adaptation-signature](twin/adaptation-signature.md) | How the twin learns individual adaptation patterns. The capstone of the twin layer. |
| 15 | [womens-cycle](twin/womens-cycle.md) | Cycle integration as a first-class modifier. Builds on external-modifiers. |

*The twin is the source of truth. Read this before coach-facing documents to understand what feeds every message.*

---

## III. Product Decisions & Planning

*How coaching works at a strategic level — the mechanisms behind the plan.*

| # | Document | Purpose |
|---|----------|---------|
| 16 | [constraints](product/constraints.md) | Running-only, no workout builder, no raw data surfaces. Bridges twin fundamentals to product behavior. |
| 17 | [integrations](product/integrations.md) | Data ingestion philosophy. Which platforms, why, and data quality rationale. |
| 18 | [plan-generation](product/plan-generation.md) | The strategic roadmap (not a session schedule). Core planning concept. |
| 19 | [secondary-events](product/secondary-events.md) | B-races and C-races — how they fit without compromising the A-race. |
| 20 | [hypothesis-selection](product/hypothesis-selection.md) | How three hypotheses are explored, scored, and selected. Extends plan-generation. |
| 21 | [weekly-coaching-rhythm](product/weekly-coaching-rhythm.md) | The weekly adjustment layer. Where most adaptation actually happens. |
| 22 | [training-plan-checkpoints](product/training-plan-checkpoints.md) | Checkpoint hierarchy, scheduling, and adaptive evolution at the weekly level. |
| 23 | [goal-modes](product/goal-modes.md) | Coaching posture shifts (race, fitness, maintenance, recovery). |

*These documents explain how the plan is built, adjusted, and maintained over time.*

---

## IV. Coach Experience

*What the athlete sees and how the coach communicates.*

| # | Document | Purpose |
|---|----------|---------|
| 24 | [voice-and-format](coach/voice-and-format.md) | Message formatting rules — no AI-feel, no acronyms, three-paragraph structure. Foundation for all coach-facing docs. |
| 25 | [plan-visibility](coach/plan-visibility.md) | What the athlete sees — phase arc, near-term sessions, daily targets. Bridges planning to UX. |
| 26 | [decision-authority](coach/decision-authority.md) | Autonomy vs. authority balance. How coaching decisions are made and communicated. |
| 27 | [daily-view](coach/daily-view.md) | Home screen — today's workout, weather, recovery, objectives. The primary touchpoint. |
| 28 | [first-message](coach/first-message.md) | Four-paragraph onboarding message. Establishes trust through genuine data analysis. |
| 29 | [post-workout](coach/post-workout.md) | Post-session analysis — compliance, execution story, historical correlation. |
| 30 | [objectives](coach/objectives.md) | Living objectives connecting sessions to long-term development. |
| 31 | [substitution](coach/substitution.md) | Workout substitution, illness, injury, unsynced workouts. Practical coaching conversations. |
| 32 | [race-prediction](coach/race-prediction.md) | Living race predictions with weather/course adjustment. |
| 33 | [visualisation](coach/visualisation.md) | What visualisations exist — comparative overlays, session shapes, fitness trends. The "twin-context-only" rule. |

*These documents define the athlete-facing experience.*

---

## V. Advanced & Premium

*Extensions of core coaching into premium territory.*

| # | Document | Purpose |
|---|----------|---------|
| 34 | [premium-features](product/premium-features.md) | Coach Chat, group training, voice companion. Read last to avoid premature scope assumptions. |

*Premium features extend core coaching. Understanding the full product first prevents confusion about baseline vs. extended.*

---

## Reading Tips

- **Short on time?** Read I.1–I.4, II.5–II.7, III.18, IV.24–IV.27. This covers identity, twin fundamentals, plan generation, and the daily experience.
- **Evaluating a feature?** Check I.2 (global-invariants) and I.3 (anti-goals) first — they define hard boundaries.
- **Understanding coaching messages?** Start with IV.24 (voice-and-format), then read the specific message type (first-message, post-workout, etc.).
- **Debugging twin behavior?** Read II.5–II.9 in order. The twin builds layer by layer.
