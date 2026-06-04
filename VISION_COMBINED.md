# Pheidipp Vision - Combined Documentation

Generated: 2026-06-03 17:19:32
*Document order based on reading-order.md*

---

## product > brand-philosophy

# Brand Philosophy

## The Name

Pheidipp takes its name from Pheidippides, the legendary Hemerodromoi — a professional long-distance runner of ancient Greece who ran from the battlefield of Marathon to Athens to deliver news of the Greek victory, roughly 40 kilometres. He is the original endurance athlete: a man who ran not for sport but with purpose, carrying something that mattered.

The Hemerodromoi were trained messengers capable of covering extraordinary distances across difficult terrain, day after day. Professional, disciplined, purposeful. The antithesis of the casual jogger.

The name reflects what Pheidipp aspires to be — not a generic fitness tracker but a purposeful coaching system built for athletes who train with intention, however fast or slow they may be.

## Core Vision

Pheidipp is an AI-powered coaching platform for self-coached runners — both serious and recreational. Most training apps suffer from data overload: they surface too many metrics and leave the athlete to make sense of them. Pheidipp inverts this. The complexity lives entirely in the backend; what the athlete sees is the conclusion, not the workings.

The product is intentionally focused on running. Multi-sport platforms trade accuracy for breadth — the models become generic, the coaching becomes shallow. Pheidipp does not make that trade. That focus is what makes the model accurate enough to be worth trusting.

## Design Philosophy

### The Blackboard Principle
The UI is minimalist — text-driven, no visual noise, no excessive charts or metric dashboards. Think of a coach's blackboard: the information that matters, written clearly, nothing else. This is a deliberate product decision, not a limitation.

### The Coach, Not the Dashboard
The role model is a great human coach, not a fitness app. A real coach doesn't show you a CTL/ATL chart — they say "you're carrying a lot of fatigue right now, let's keep this easy." The numbers informed that sentence but the athlete never sees them. Pheidipp aspires to that same experience.

### No AI-Feel Communication
All coach communication is in plain, natural language. No emojis, bullet points, headers, or generic AI-style output. The coach writes in paragraphs, the way a real coach speaks. The athlete should never feel like they are reading generated text.

### Data Processing Boundary
The LLM is a reasoning engine, not a data processor. All analytical computation — fitness scoring, threshold estimation, execution classification, load accumulation, trend analysis — is performed deterministically in Python before the LLM ever sees it. The LLM receives pre-computed metrics and structured summaries, then reasons about what they mean strategically.

Strategic planning is legitimate LLM territory: generating training hypotheses, evaluating methodology fit, selecting periodisation approaches, structuring weekly progression. These are reasoning tasks that benefit from natural language understanding and coaching philosophy.

What the LLM never does is take raw or semi-processed data and try to make sense of it. Calculations, cleanup, statistical analysis, and derived metrics are always pre-computed. The LLM reasons from conclusions, never from raw inputs.

## Coaching Expertise Boundaries

The coach has a defined area of expertise: running performance and training methodology. When something lands outside it, the response is a natural redirect — the way a knowledgeable coach with professional self-awareness would handle it, not the way a product hitting a constraint wall feels.

- **Sleep optimisation** → "That's really one for a sleep specialist — what I can tell you is how it's showing up in your readiness data."
- **Nutrition beyond training fuelling** → Basic fuelling around sessions is legitimate coaching territory. Dietary design, caloric targets, and weight management redirect to a sports dietitian.
- **Injury assessment** → "I'm not the right one to assess what's going on there — please get that looked at before we push the load. I've pulled back this week's targets in the meantime."

The boundary never feels like a wall. An athlete asking about sleep should leave feeling like they spoke to someone who knew exactly what they could and couldn't help with.

## product > global-invariants

# Global Invariants
*The immutable truths that govern all Pheidipp decisions — from product behaviour to coaching logic to architectural choices.*

---

This document defines the immutable truths of Pheidipp. These principles shape product behavior, coaching behavior, UX decisions, adaptation systems, and platform boundaries. Any feature or implementation that violates these invariants is misaligned with the product.

---

## Product Identity Invariants

These invariants define what Pheidipp is and is not. They protect the product's strategic clarity and prevent identity drift.

**Pheidipp is a coach, not a dashboard.** The product exists to guide athletes through expert running coaching, not to maximize metrics exposure or become an analytics platform. Data exists solely to support coaching decisions and athlete understanding.

**Complexity must remain hidden.** Internal sophistication should never create UX complexity. The athlete receives clarity, direction, and concise guidance because the system absorbs all complexity.

**The digital twin is the single source of truth.** The system continuously maintains an evolving, running-specific understanding of the athlete, and all adaptation, coaching, and recommendations flow through this twin. There is no parallel decision path — the twin is the intelligence layer of the product.

**Running performance requires sport-specific modeling.** General fitness proxies are insufficient for running adaptation, so running remains central to progression measurement, adaptation learning, and performance understanding. Other activities may influence recovery context but never calibrate the core model.

---

## Trust Invariants

These invariants protect the athlete's trust in the system. Trust is the product's most valuable asset and its most fragile.

**The system must never pretend certainty.** Confidence must match available evidence, which means low-confidence situations produce softer recommendations, cautious interpretation, and reduced decisiveness. False precision permanently damages trust.

**Conclusions matter more than metrics.** Athletes should rarely need to interpret raw data manually because the system synthesizes information into actionable guidance, clear decisions, and meaningful context. If coaching requires metric interpretation, it has failed.

**Trust compounds slowly and breaks instantly.** The system prioritizes honesty about limitations, transparency in reasoning, consistency in behavior, and predictability in outcomes. This is especially critical under uncertainty — the product never optimizes for short-term engagement over long-term trust.

**Simplicity compounds value.** Every additional setting, workflow, metric, chart, or customization surface must justify its existence against core coaching value. Minimalism is intentional and protective of the athlete experience.

**The athlete is never exposed to system complexity.** When services fail, data is temporarily unavailable, or processing is delayed, the athlete sees a calm, honest message — not an error code, not a loading spinner, not a technical explanation. The system absorbs its own complexity and presents only what the athlete needs to know. Failures are communicated as temporary pauses, not broken states. The coach pauses and asks again later; it does not panic or disappear.

---

## Physiological Safety Invariants

These invariants protect the athlete from training patterns that increase injury or overtraining risk. They are enforced by the plan generation system and respected by all coaching logic.

**No unsafe load spikes.** Weekly training load must not increase by more than 10%. This prevents the rapid volume or intensity progressions that precipitate overuse injuries. The rule applies to total weekly load and to individual session load.

**No incompatible intensity stacking.** No hard sessions on consecutive days. Intense efforts require neuromuscular recovery that a single easy day does not provide. The system enforces at least one easy or rest day between quality sessions.

**Minimum recovery spacing.** At least 48 hours between intense efforts. This ensures adequate neuromuscular and structural recovery regardless of session type. A hard session Monday followed by another hard session Tuesday violates this invariant.

**No overlapping tapers.** The system cannot taper for multiple races simultaneously. Tapering reduces training stress to preserve fitness for a specific event. Tapering for two events at once means neither receives adequate preparation. When races are too close, the system selects the higher-priority race for tapering.

---

## Race Priority Invariants

These invariants preserve the integrity of the athlete's primary goal when secondary events exist.

**A-race always takes precedence.** When a conflict arises between a B-race or C-race and the A-race, the A-race wins. B- and C-races are tools to prepare for the A-race, not independent goals that compete for resources.

**Secondary events outside A-race taper.** B-races and C-races cannot be scheduled within the A-race taper or race week. The taper is a delicate physiological window. Introducing race stress during this period compromises the peak the entire plan was designed to produce.

---

## Planning Boundary Invariants

These invariants define the boundaries of what the system will and will not plan.

**Training length gate.** Goals beyond the planning horizon for their goal type and experience level trigger an intermediate goal proposal. Each race distance has a maximum planning window — longer horizons produce unreliable plans because too many variables remain uncertain. See plan-generation for the full gate logic.

**Running-only twin model.** Non-running activities are excluded from twin calibration. This is an accuracy decision. Cross-modal conversions — swim sessions translated into equivalent running stress, strength sessions assigned arbitrary scores — introduce errors that compound over time. The twin holds its judgement on non-running sessions and waits for the next run.

**Honesty invariant.** Plans never pretend to know more than the twin knows. If confidence is low, the plan says so. If a metric is uncertain, the plan uses conservative ranges rather than false precision. Trust is built through honesty, not through the appearance of certainty.

---

## Schedule Invariants

These invariants protect the athlete's autonomy and the plan's structural integrity.

**Workouts only on available days and times.** The plan respects the athlete's stated availability. Sessions are never placed on days the athlete has marked as unavailable, regardless of optimisation pressure.

**Primary sessions are scheduled to allow adequate recovery. Secondary sessions on the same day are permitted when they don't interfere with the primary session's recovery.** This supports doubles scheduling where secondary sessions (non-running suggestions like strength, yoga, mobility) are placed in the PM slot after a primary running session, without compromising the recovery window measured between primary sessions.

## product > anti-goals

# Anti-Goals

This document defines what Pheidipp should explicitly avoid becoming. These anti-goals preserve strategic clarity, product identity, coaching focus, and long-term differentiation.

Pheidipp is not a social network. The product is not built around feeds, followers, likes, or public engagement loops. Training quality matters more than visibility, and social dynamics would distract from individual athletic development.

Pheidipp is not a workout marketplace. The system should not become a downloadable-plan marketplace, a creator ecosystem, or a coaching-content platform. The intelligence must remain integrated and adaptive rather than fragmented across external content sources.

Pheidipp is not a quantified-self dashboard. The product should not optimize for endless charting, raw metric exploration, or manual analysis workflows. Interpretation should happen inside the system, delivering conclusions rather than requiring athletes to become data analysts.

Pheidipp is not a generic AI assistant. The coach exists specifically to support training, not to become a general chatbot, productivity assistant, or social companion. Scope creep into adjacent domains would dilute coaching expertise and confuse the product's purpose.

Pheidipp is not infinitely customizable. The athlete should not need to configure algorithms, tune coaching systems, or manage complex preferences. The system should make intelligent defaults sufficient, avoiding the burden of choice that undermines coaching clarity.

Pheidipp is not engagement-maximization software. The product should avoid dopamine loops, streak obsession, artificial gamification, and manipulative retention systems. Long-term athletic development matters more than engagement metrics, and the coaching relationship should be built on trust rather than behavioral manipulation.

## product > differentiators

# Key Differentiators
*What makes Pheidipp distinct and why those distinctions are durable*

## Running-Specific Model Accuracy

The twin is built exclusively for running. Every signal, calculation, and comparison is clean because it always compares running to running. This eliminates the cross-modal conversion errors that corrupt multi-sport platforms — errors that are individually small but compound over time into a model that no longer accurately represents the athlete's running fitness.

This is not just a positioning choice. It is the technical foundation that makes the coaching worth trusting.

## Three-Dimensional Load Intelligence

Aerobic, neuromuscular, and structural load are tracked as separate dimensions with individual time constants. This catches risks that single-number models miss entirely — like structural fatigue accumulating in a crossover athlete while their cardiovascular fitness looks strong, or neuromuscular load not clearing between sessions while aerobic metrics appear fine.

## Women's Cycle-Aware Coaching

The only mainstream training platform that integrates menstrual cycle phase directly into the twin model and coaching decisions. Not a separate tracker bolted on — a genuine physiological input that adjusts load computation, session targets, adaptation tracking, and coach analysis across the full cycle. This makes the model more accurate for female athletes in a way that no platform currently does.

## Complexity Hidden, Conclusions Surfaced

The twin does the computational work; the athlete sees the coaching insight. No dashboards, no raw numbers, no acronyms without explanation. The interface is a conversation, not a data terminal.

## Same-Day Workout Generation

Future sessions in the plan show only high-level intent — type of session, approximate duration, training purpose. The specific workout is generated on the day from the freshest possible data about the athlete's current state. Generating precise interval targets six weeks in advance is false precision; Pheidipp does not pretend otherwise.

## Personalised Weather Response

Race day projections and session target adjustments are based on how this specific athlete responds to environmental conditions, learned from their actual execution history. Not a population average correction — a model of this individual's performance envelope across heat, cold, humidity, and wind.

## Historical Correlation in Every Coach Message

Every post-workout message connects this session to past patterns with specific references. "Three weeks ago on your last threshold session you faded in the final rep. Today you held it together." This requires the twin to know which previous session is actually comparable — not just any previous threshold session, but one in a similar phase, at a similar fitness level, with a similar target.

## Rep-Level Analysis

Granular enough to catch pacing errors, sandbagging, or execution drift within a single session. The coach can tell the difference between a well-executed controlled fade at the end of a VO2max session and an athlete who went out too hard and fell apart.

## Coach Voice

Plain language, no tech jargon, no AI-feel. Reads like a message from someone who watched you train. This is a product differentiator in practice — athletes who have used other coaching apps notice the difference within the first post-workout message.

## Living Objectives

Every session connects to a bigger picture. Training never feels like isolated data points. The objectives system gives each workout a purpose that the athlete can see and the coach can reference.

## twin > core

# The Digital Twin — Core Concept
*What it is, what it sees, and what it deliberately does not see*

## What the Twin Is

The Digital Twin is the engine underneath everything. It models the athlete's physiological state based on all available data — training history, wellness metrics, recovery trends, workout execution patterns. It is the source of truth for all coaching decisions and is continuously updated as new data arrives.

The twin is a running model. Every layer — load computation, threshold tracking, execution analysis, adaptation signature — is calibrated for running physiology, running mechanics, and running-specific data signals.

## The Running-Only Boundary

Non-running activities appear in the training record and the coach acknowledges them. The coach can prescribe aqua jogging during injury recovery, strength and conditioning sessions, yoga and mobility work. But these activities are excluded from twin calibration entirely.

They do not contribute to fitness or fatigue scores, threshold estimates, adaptation signature learning, or execution pattern analysis.

This is not a limitation — it is the decision that keeps the running model accurate. A twin that absorbs swimming and strength sessions alongside running introduces cross-modal conversion errors that corrupt the signals the model depends on. The boundary is clean: **the twin sees running; the training record sees everything.**

## The Twin Is Always Honest About Confidence

Every estimate the twin produces carries an evidence confidence level that affects downstream decisions. Conservative coaching language, target ranges rather than point estimates, and cautious plan structures are the natural output of a low-evidence-confidence twin. As real data accumulates and the model learns this specific athlete, evidence confidence grows and coaching becomes more precise.

The twin never pretends to know more than it does. This is an invariant, not a UX choice.

## twin > data-philosophy

# Twin Data Philosophy
*The deliberate accuracy decisions behind how the twin learns*

## Real Signals, Not Assumptions

The twin uses actual physiological data rather than estimated or inferred metrics wherever possible. Grade-adjusted pace replaces raw pace to handle terrain variations honestly. RR intervals are preferred over optical HR where available. Overnight minimum HR is used as the resting HR anchor rather than a morning spot measurement that athletes stop taking.

Lab/test uploads are accepted as valid calibration inputs when properly documented with provenance and measurement conditions. They represent the athlete's actual measured physiology and are weighted accordingly in the signal hierarchy.

Where high-quality data is unavailable, the twin works with what exists and is explicit about the resulting reduction in confidence.

## Data Quality Over Quantity

Sessions without device data — manual input, missing hardware — are logged for the training record but excluded from twin calibration. Noisy or incomplete data corrupts the model more than gaps do. A twin that learns from low-quality inputs drifts from reality gradually and silently.

The twin always knows the data quality tier of each session and weights its learning accordingly. The confidence level of its estimates reflects the quality of the data it has been trained on.

## Continuous Learning From Real Training

The twin updates from every real training session, getting smarter over time rather than applying static templates. Individual time constants, threshold estimates, adaptation patterns, and behavioural profiles all improve as data accumulates. An athlete training with Pheidipp for a year has a substantially more personalised twin than one who has trained for a month.

## Non-Running Data Does Not Corrupt the Running Model

Strength sessions, swimming, cycling, yoga — all logged, none calibrated into the twin. The temptation to assign arbitrary conversion factors ("this strength session was equivalent to X minutes of running stress") is resisted entirely. These conversions introduce small errors that compound over time into a model that no longer accurately represents running fitness.

The twin waits for the next run. That is the signal it trusts.

## The Honesty Invariant

The twin is always honest about its evidence confidence level. Conservative language, target ranges rather than point estimates, and cautious plan structures are the natural output of genuine uncertainty — not a product limitation. As evidence confidence grows through accumulated data, coaching becomes correspondingly more specific and more useful.

## twin > layers

# Twin Architecture — Five Layers
*What the five layers model and how they relate to each other*

## Overview

The Digital Twin models the athlete across five distinct layers. Each layer feeds into the others and together they form a complete physiological and behavioural portrait of the athlete at any given moment.

| Layer | Name | What It Models |
|---|---|---|
| 1 | Fitness & Fatigue State | Three-dimensional load and recovery tracking |
| 2 | Physiological Thresholds | Dynamic functional zones updated from training |
| 3 | Individual Adaptation Signature | How this athlete responds to stimulus over time |
| 4 | External Modifiers | Sleep, HRV, wellness signals, environmental context |
| 5 | Execution Patterns | What the athlete actually does versus what is prescribed |

> **Note:** These five layers describe what the twin models (physiological domains). They are independent from the five-layer separation of concerns in the architecture document, which describes how data flows through processing stages. The two taxonomies serve different purposes and should not be mapped to each other.

## How Layers Relate

Layer 4 modulates Layer 1 — a wellness-suppressed day adjusts the effective readiness the coach communicates, without changing the underlying fitness or fatigue state. The distinction matters: a hard week did not become easier because the athlete slept badly. What changes is whether today is the day to push against it.

Layer 3 reads Layer 1 history over time to build the adaptation signature. It is looking at how this athlete's fitness changes in response to different types of adaptation windows, not at any single session.

Layer 5 validates and refines Layers 1 and 2. If an athlete's execution data consistently shows they are performing better than their estimated threshold suggests, that is a signal the threshold estimate needs updating. Execution is the most honest signal of all — it cannot be self-reported incorrectly.

## Layers Become More Valuable Over Time

Layers 1 and 2 provide useful coaching from the first session. Layer 4 becomes meaningful after a few weeks of consistent wellness data. Layer 3 requires months of training history to develop genuine individual signal. Layer 5 builds a stable behavioural portrait across many sessions.

An athlete training with Pheidipp for two years has a substantially more personalised twin than one who has trained for two months — not because the product changed, but because the twin has had time to learn from their specific physiological record.

---

## From Observation to Prescription: The Three-Layer Hierarchy

The twin observes the athlete across five layers. But observation alone does not produce training. The coaching system translates observation into sessions through a three-layer hierarchy:

```
SessionType           = what the athlete does
PhysiologicalIntent   = what adaptation we seek
SessionPurpose        = why we are doing it
```

**Layer 1: SessionType** — What the athlete actually does. Sixteen concrete workout prescriptions that appear on the calendar. Maps to PhysiologicalIntent via SESSION_INTENT_MAP (many:1 mapping).

**Layer 2: PhysiologicalIntent** — What adaptation we seek. Six physiological targets: low_aerobic, high_aerobic, threshold, vo2max, neuromuscular, recovery. The primary coaching abstraction — the system works directly with intents, not zones.

**Layer 3: SessionPurpose** — Why we are doing it. Three contextual reasons: general, race_specific, calibration. Affects how results are interpreted, not compliance assessment.

Most training platforms collapse these three layers into one. Pheidipp separates them deliberately because the same physiological intent (threshold adaptation) can be pursued through different methodologies (frequent short sessions vs. sparse long sessions), producing different session distributions for the same adaptation target.

## twin > load-fatigue

# Load & Fatigue — Layer 1
*Three-dimensional tracking of the stresses training places on the body*

## Beyond a Single Fitness Score

The twin rejects the single-number fitness score approach. Different training sessions stress different physiological systems with different accumulation and recovery timelines. Treating them as one number produces a model that looks accurate on average but fails at the edges — exactly where injury and overtraining happen.

Three separate load dimensions are tracked, each with its own accumulation and recovery curve.

## The Three Dimensions

**Aerobic Load** — Cardiovascular and metabolic stress from sustained effort across aerobic zones. Builds slowly and durably. Fatigue clears over roughly 10-15 days; fitness accumulates over 40-60 days (individual constants are learned per athlete over time). This is the best understood dimension with the most established science behind it.

**Neuromuscular Load** — Fast-twitch fibre recruitment, acceleration stress, and high intensity neuromuscular demand. A session with short explosive efforts or sustained high intensity accumulates neuromuscular stress disproportionate to its cardiovascular signal. Clears faster than aerobic fatigue — roughly 3-5 days — but with a distinct signature.

**Structural Load** — Tendon, connective tissue, and musculoskeletal stress from impact and mechanical loading. The least understood dimension scientifically but critically important, especially for athletes new to running. Accumulates and clears slowly — weeks, not days. Key inputs are total impact count, elevation change, surface type, and how quickly weekly volume is increasing.

## How the Dimensions Interact

High structural fatigue degrades neuromuscular output even when the aerobic system is fully recovered — the "heavy legs" phenomenon where breathing feels fine but pace simply is not there. The twin models this interaction rather than treating dimensions as independent. A single fitness number cannot distinguish between these states.

## Data Quality and Load Computation

The richness of load computation depends on what data the athlete's hardware provides. The twin always knows which tier it is working with and weights model confidence accordingly.

**Tier 1 — Running power meter + chest strap with RR intervals.** The richest signal. Full mechanical and physiological data. Most precise load computation across all three dimensions. The RR interval data also enables passive threshold tracking simultaneously.

**Tier 2 — Running power meter + optical HR.** Very strong for load calculation. Loses the RR interval signal for threshold detection but power compensates significantly.

**Tier 3 — Chest strap HR + grade-adjusted pace + GPS.** No power meter, but the chest strap provides RR interval data. Grade-adjusted pace serves as the mechanical work proxy.

**Tier 4 — Optical HR + grade-adjusted pace + GPS.** The realistic baseline for the core athlete audience. A quality GPS watch with optical HR. Fully usable for load calculation and zone tracking across all three dimensions.

**Tier 5 — Grade-adjusted pace + GPS only.** No HR data available. Session logged for the training record but excluded from twin calibration.

**Tier 6 — Manual input only.** No device data at all. Session logged for the training record only. Never used to update the twin model.

Note on optical HR: modern sensors in quality GPS watches are adequate for intent-range-based load calculation. Their limitation versus chest strap is specifically the absence of RR interval data for threshold detection — not HR accuracy for sustained aerobic efforts.

## Grade-Adjusted Pace — Always, Never Raw Pace

Raw pace without grade adjustment systematically misrepresents effort on varied terrain and corrupts load calculations and historical comparisons. Grade-adjusted pace is the standard input for all pace-based computations, target setting, and execution analysis throughout the system.

## The Crossover Athlete Profile

Athletes transitioning from swimming or cycling carry a specific risk. Their aerobic load tolerance is high — the cardiovascular system genuinely absorbs volume. But structural load tolerance is low — tendons and connective tissue have not had years of running adaptation.

A model using only cardiovascular signals would look at their HR data, see them cruising, and conclude they can handle more load. The three-dimensional model catches that structural stress is accumulating at a rate their cardiovascular fitness masks. This profile is identified at onboarding and structural capacity development is incorporated as an explicit objective in the training plan.

## Individual Time Constants

Some athletes carry aerobic fatigue for 10+ days; others clear it in 5. Some build fitness slowly and durably; others peak quickly but also detrain fast. The twin learns these individual constants from observed response patterns over time rather than applying population defaults that may be significantly wrong for a given person.

## Coach Communication of Load Patterns

When the twin detects concerning patterns — structural load accumulating faster than demonstrated tolerance, neuromuscular fatigue not clearing between sessions — the coach surfaces this in plain language. No raw numbers, no acronyms. A clear explanation of what was observed and what adjustment has been made to the session.

If an athlete consistently produces sessions without device data, the coach surfaces this as an opportunity to give the coaching system better data — never as criticism.

---

## Recovery Timing and Session Priority

Recovery windows are measured from primary session to primary session. Secondary sessions — whether a double-day PM session or a suggested non-running workout — do not reset the recovery clock.

This reflects physiological reality: a morning easy run followed by an evening threshold session provides more recovery between primary efforts than two hard sessions on consecutive days. The twin's recovery model accounts for this by tracking primary session spacing rather than total session count.

The weekly plan respects this when scheduling quality sessions: a double day with AM primary + PM secondary followed by a single primary session the next day provides adequate recovery for most athletes.

## twin > training-zones

# Training Zones

## Philosophy

RPE is intentionally not a primary signal. It is too subjective and too noisy at the individual level — the same effort feels different after poor sleep, in heat, or at different points in a training block. The twin derives threshold estimates from objective signals captured during normal training.

Thresholds — LT1, LT2, CP, max HR, VO2max estimate — are not static numbers set at onboarding. They are living values, tracked continuously and updated from training data rather than waiting for dedicated test sessions.

## Signal Hierarchy

The richness of threshold detection depends on available hardware. The twin works with whatever signal is available and is explicit about the confidence level of its estimates.

**Raw RR intervals from chest strap** — the richest signal. The twin processes raw RR interval data, performs artifact detection and cleaning internally, and extracts HRV inflection points during appropriate workout types. This enables continuous passive threshold tracking — the athlete trains normally and the model updates without any dedicated test sessions required.

**HR-based signals without RR** — for athletes using optical HR or chest straps that do not expose RR data. The twin works with HR deflection patterns, pace or power at a given HR over time, and post-interval HR recovery curves. Less precise than RR-based detection but meaningful accumulated over enough sessions.

**Dedicated calibration sessions** — structured sessions designed to elicit clear threshold signals: progressive intensity blocks where the twin reads HR and power or pace response at each step. A field approximation of a lab test using a protocol the system designed and knows how to interpret. These are scheduled periodically, especially for athletes without RR data.

**Lab/Test Uploads** — athlete-provided physiological benchmarks from recent lab tests, field tests, or validated external assessments. These are treated as high-quality calibration events when properly timestamped and contextualized. Unlike pure athletic input, lab/test uploads carry documented provenance and measurement conditions that allow the twin to weight them appropriately in the signal hierarchy.

When lab/test values diverge from observed training execution, the coach addresses this through guided conversation rather than silent model adjustment. "Your recent 5K race suggests higher sustainable HR than your lab test indicated. Want to explore this in a calibration session?" This maintains the honesty invariant while respecting athlete expertise.

**Inference from training history** — for athletes with limited data. Threshold estimates derived from best efforts at various durations and the initial questionnaire inputs. Confidence is low and flagged accordingly.

## Calibration Confidence Degradation

### Calibration Freshness and Recommendation Strength

Threshold recommendation strength degrades over time without fresh calibration signal, even for athletes with extensive training history. Thresholds derived from lab tests or dedicated sessions lose certainty as months pass without re-measurement. The twin tracks the time since last calibration event and reflects this in its recommendation strength.

An athlete who uploaded a lab test 18 months ago should see coaching language that acknowledges staleness: wider target ranges, more frequent calibration sessions suggested, and coach language like "your lab test suggested X, but recent race performances indicate you may have shifted." The model does not silently expire calibration evidence, but it does reflect growing staleness through reduced recommendation strength and wider target ranges.

## Passive Calibration From Normal Training

The system continuously scans the training plan for sessions that will naturally produce strong threshold signal — progressive tempo runs, longer threshold interval sessions, time trial efforts. These are treated as dual-purpose sessions. The athlete executes their normal training; the twin reads it as a calibration event simultaneously. No extra burden on the athlete, no awareness required.

## New Athlete Calibration Period

Athletes with limited or no training history begin with a structured first period designed to give the twin enough signal across different intensity domains to establish initial threshold estimates with reasonable confidence. This is not framed as a test battery — it is presented as an introduction to training with Pheidipp. It also serves as the athlete's first full experience of the daily coaching voice, building the habit of engaging with the product before serious training begins.

## Dynamic Test Frequency

How often dedicated calibration sessions are scheduled depends on data richness per athlete. Athletes with RR interval data have passive monitoring every session, so dedicated tests are infrequent — roughly once per training block or when the model detects an anomaly that passive monitoring cannot resolve. Athletes without RR data receive more frequent calibration sessions woven into the training plan.

Lab/test uploads are always welcome as calibration refresh events, regardless of hardware tier. An athlete who completes a new threshold test should be able to upload results and immediately benefit from updated threshold confidence.

## Range-Based Targets, Not Zone Numbers

The athlete never sees "Zone 2" or "Zone 4". They see explicit numbers:
- `165-172 bpm` (HR)
- `250-280W` (power)
- `4:05-4:15/km` (GAP)

Zones are internal to the system — used for compliance assessment and adaptation tracking, never surfaced to athletes. The coach computes ranges from zone boundaries, and the ranges are what the athlete sees.

### Why This Is Better

| Zone-Based Model | Range-Based Model |
|------------------|-------------------|
| "Zone 4" | "250-280W" |
| Athlete must learn zone meanings | Athlete sees explicit numbers |
| Zones vary between platforms | Ranges are individualised |
| Zone compliance is abstract | Intent compliance is concrete |
| Zones obscure the target | Ranges clarify the target |

## Two-Column Target Display

Every generated workout shows two sets of targets side by side:
- **Theoretical targets** — derived from the athlete's current dynamic thresholds as modelled  by the twin. These reflect the twin's live understanding of the athlete's fitness state.
- **Adjusted targets** — the coach's recommendation for today, after applying current recovery and readiness state and the weather forecast for the athlete's training window.

The athlete always sees both. This distinction teaches the athlete over time how fatigue and conditions affect their numbers — building genuine self-awareness rather than just compliance with a single number.

## Signal-Aware Target Selection

The system selects the best signal type for each workout step based on:
- Session type
- Physiological intent
- Signal availability
- Signal quality
- Athlete calibration confidence

**Easy/recovery sessions**: HR is most meaningful (aerobic development is about cardiac load).
**Threshold sessions**: Power is most meaningful (sustainable mechanical output).
**VO2max sessions**: Power is most meaningful (maximal oxygen uptake).

When the primary signal is unavailable, the system automatically falls back to the next-best option.

### Why HR for Easy Runs, Power for Threshold

**Easy runs (HR)**: Aerobic development is about cardiac load, not mechanical output. An easy run at 200W means nothing if HR is in threshold zone. HR tells you whether the athlete is actually training aerobically.

**Threshold sessions (Power)**: Threshold is about sustainable mechanical output, not cardiac response. HR lags during threshold work; power is instantaneous. Power tells you whether the athlete is actually at threshold intensity.

**VO2max sessions (Power)**: VO2max is about maximal oxygen uptake, best expressed as power. HR at VO2max is near-max and noisy; power is precise.

## Multi-Dimensional Physiology

LT1 and LT2 are physiological states, not signal values. They can be expressed in multiple signal types:

```
LT2 (physiological state)
  ├── HR expression:    172 bpm
  ├── Power expression: 285 watts (if power meter available)
  └── Pace expression:  4:05/km GAP (from GAP model)
```

The athlete's physiology doesn't change based on which sensor you're reading. But the *expression* of that physiology in signal units does change.

### Critical Power (CP) vs LT2

- **CP is the primary performance anchor** for runners with power meters
- **LT2 is the primary physiological anchor** — ranges derive from LT2
- When direct LT2 power estimation is unavailable, CP may be used as a proxy
- If only CP is available, treat it as LT2_power with an explicit note that it's an approximation

## Intent Ranges: Computed From Physiology

Each physiological intent has a range for each signal type, derived from the athlete's individual thresholds:

```
low_aerobic:
  HR:    < LT1 × 0.95
  Power: < LT2 × 0.55
  GAP:   > LT1 × 1.10 (slower = higher sec/km)

high_aerobic:
  HR:    LT1 × 0.95 – LT1 × 1.05
  Power: LT2 × 0.55 – LT2 × 0.75
  GAP:   LT1 × 0.95 – LT1 × 1.10

threshold:
  HR:    LT2 × 0.95 – LT2 × 1.05
  Power: LT2 × 0.90 – LT2 × 1.05
  GAP:   LT2 × 0.95 – LT2 × 1.05

vo2max:
  HR:    > LT2 × 1.05
  Power: > LT2 × 1.05
  GAP:   < LT2 × 0.95 (faster = lower sec/km)

recovery:
  HR:    < LT1 × 0.85
  Power: < LT2 × 0.45
  GAP:   > LT1 × 1.20 (very slow)

neuromuscular:
  HR:    null (not meaningful)
  Power: null (too variable)
  GAP:   null (too variable)
```

Note: These ranges are architecture-level approximations. Exact multiplier constants belong in implementation and may vary by athlete type (beginner, elite, marathoner, 5K specialist).

## twin > cold-start

# Cold Start Strategy
*How the twin initialises before an athlete has real training data*

## Three Confidence Tiers

The twin starts from one of three tiers depending on what data is available at onboarding. The system is always honest about which tier it is operating from, and all downstream decisions — plan conservatism, target ranges, coaching certainty — are weighted accordingly.

**Tier 1 — Imported training history.** The athlete connects an existing training platform and the system ingests real historical workout data. The twin is built from actual physiology, not assumptions. This is the richest starting point and produces the most personalised initial coaching. Athletes in this tier can also supplement with lab/test uploads to provide additional threshold precision.

> **Implementation:** Tier 1 athletes start at LOW confidence but transition quickly (1–3 sessions to MEDIUM). See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for evidence weight thresholds and transition conditions.

**Tier 2 — Peer-similar athletes OR Lab/Test Uploads.** For athletes with no importable history, the twin bootstraps either from anonymised models of similar athletes OR from athlete-provided physiological benchmarks. Lab/test uploads provide higher threshold confidence than peer-based inference, but execution patterns and adaptation signatures still require real training data to develop.

> **Implementation:** Lab tests provide immediate high-weight evidence (12–15 units), often jumping tested metrics directly to MEDIUM. Peer-similar bootstrapping starts at LOW with faster transition than Tier 3. See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for threshold details.

Confidence transitions are quality-weighted. Each physiological parameter accumulates evidence independently based on observation quality. A single lab test carries more evidence than multiple easy sessions with optical HR. The system weighs observation quality when determining when to upgrade confidence levels — it is the quality of the data, not just the quantity, that drives confidence forward. For LT1 specifically, the system builds confidence passively from natural training patterns — analyzing HR response in easy runs, drift during long efforts, and recovery after stopping — without requiring special test sessions.

**Tier 3 — Questionnaire inputs only.** The most conservative baseline, built from onboarding responses alone. Initial targets are expressed as ranges or effort descriptions rather than precise numbers. The twin becomes more confident and specific as real training data accumulates over the following weeks.

> **Implementation:** Initial confidence is LOW. This tier requires the most real training data to accumulate evidence (6–10 sessions to MEDIUM). See [`confidence-model.md`](../../architecture/00-foundations/confidence-model.md#initial-confidence-by-onboarding-tier) for transition conditions and velocity estimates.

## What Honest Confidence Looks Like

A Tier 3 athlete does not receive aggressive targets on day one. The coach language reflects genuine uncertainty: "based on what you've described," "let's see how this feels," "we'll calibrate as we see your actual data." This is not a degraded experience — it is accurate coaching at the information level available.

As sessions accumulate and the twin observes real execution, threshold estimates, recovery patterns, and fatigue responses, confidence upgrades and the coaching becomes correspondingly more precise. The athlete earns specificity from the model by training with it.

## Onboarding Time to Value

The model build takes a few minutes — not instant, not an hour. This communicates that something real is being computed, not a template being applied. While the model builds, the athlete explores the app and sets their goal race or objectives. When the model is ready, the first coach message appears.

## twin > external-modifiers

# External Modifiers — Layer 4
*Understanding that training happens in a life, not in isolation*

## Philosophy

Subjective daily wellness questionnaires are intentionally avoided as a primary input. Compliance drops sharply after the first few days. All wellness signals are captured passively where possible, from data the athlete is already generating through their wearable during sleep and rest. The athlete should not have to tell the system how they feel — the system should already have the physiological evidence.

## Core Sleep Metrics

Sleep is the most important recovery signal. The twin tracks multiple dimensions, each telling a different story.

**Total sleep duration** — the volume of recovery time available. Trends over multiple nights matter more than any single night.

**Deep sleep duration** — physical recovery and tissue repair. Consistently low deep sleep is an early warning for accumulated fatigue, often appearing before the athlete consciously notices anything wrong.

**REM proportion** — cognitive and emotional recovery. Relevant for motivation, perceived effort, and decision-making capacity, particularly relevant for race situations.

**Average sleeping HR** — the primary trend signal for recovery state. Rising average sleeping HR over several consecutive nights is one of the most reliable early indicators of overreaching or illness onset, often appearing three to four days before the athlete consciously feels fatigued.

**Minimum sleeping HR** — the true physiological floor, recorded during the deepest sleep phases. Used as the resting HR anchor for zone calculations. More stable than average sleeping HR and less influenced by external factors.

The time-of-day modifier is part of the wellness modifier pipeline in architecture. It adjusts the correlation between wellness signals and execution quality based on whether the athlete trains in the morning or afternoon, avoiding misattribution of life stress to fitness state.

## Resting HR — A Definition That Matters

Three distinct measurements are commonly conflated under "resting HR":

- **Overnight minimum HR** — most stable, passively capturable, the measurement Pheidipp   uses for all intent range calculations
- **True resting HR** (supine, morning, before rising) — reproducible but requires   deliberate capture that athletes stop doing consistently
- **Standing or ambient HR** — most variable, least useful for precision inputs

The overnight minimum is the right choice: it requires nothing from the athlete and produces the most consistent baseline.

## HRV

Average overnight HRV is preferred over a dedicated morning measurement. Wearables that capture continuous overnight HRV provide a more stable and consistent reading than a 1-5 minute morning test, which athletes perform inconsistently and eventually abandon.

The twin monitors overnight HRV trends across rolling 3, 7, and 14 day windows. It never reacts to a single-night value — individual nights are noisy and can be disrupted by factors entirely unrelated to training load.

## Menstrual Cycle Phase

For female athletes, menstrual cycle phase is a named physiological modifier within Layer 4, tracked on equal footing with HRV and sleep. The cycle operates on a roughly 28-day rhythm with four phases, each producing measurable effects on readiness, thermoregulation, perceived effort, and sleep quality.

The luteal phase elevates core body temperature roughly 0.3-0.5°C, which shifts the pace-at-HR relationship in the same way warm weather does. The twin applies a thermoregulatory modifier during this phase identical in structure to its weather adjustment. Late luteal sleep quality degradation compounds with any existing sleep debt, producing a combined readiness signal the twin reads as worse than either in isolation.

Cycle phase signals are never interpreted in isolation. Phase context is one input among several, weighted by how strongly this individual athlete has shown phase-correlated variation in her own data. The model learns the individual pattern.

Full detail on the four cycle phases and their training implications: see `womens-cycle.md`.

## Training Time of Day

Whether an athlete trains in the morning or afternoon is a meaningful contextual modifier that most platforms ignore.

Morning athletes train before daily life accumulates — no nutritional variation from the day, no work stress, no decision fatigue. Wellness signals correlate more directly with workout execution because the noise sources are more predictable.

Afternoon athletes train at the end of a full day of external stressors. Suppressed HRV or elevated resting HR may reflect life stress rather than training load. The twin applies a time-of-day modifier when correlating wellness signals to execution quality, avoiding misattributing life fatigue to fitness state.

## Trend-Based Interpretation

All Layer 4 signals are interpreted as trends against the athlete's own baseline — never as absolute values compared to population norms. Individual baselines vary enormously. What matters is deviation from this athlete's recent normal.

Single-night anomalies are treated as noise. Patterns across three or more consecutive nights trigger model adjustments. Patterns across seven or more nights may prompt proactive coach communication and plan restructuring.

## How the Coach Communicates Wellness Patterns

When the twin detects a concerning wellness pattern it surfaces this proactively in plain language. No medical language, no diagnoses, no acronyms. A clear explanation of what was observed, why it matters for training, and what adjustment has already been made.

Example: "Your sleep has been fragmented the last three nights and your overnight heart rate has been running a little higher than your recent baseline. That kind of pattern usually means your body is working harder than normal just to recover. I've taken the intensity targets down a notch for today's session — let's get the work in without adding to the load your system is already managing."

The adjustment is communicated as already made — not as a question of whether to make it. The coach acts and explains, rather than asking permission.

## Downstream Effects

Layer 4 signals feed directly into session target adjustment, plan load management, and rest day recommendations. A sustained negative wellness trend can trigger a proposed recovery day — the coach proposes it, explains why, and asks about weekly availability to redistribute load if appropriate.

## twin > execution-patterns

# Execution Patterns — Layer 5
*What the athlete actually does reveals truths self-reported data never will*

## Philosophy

Execution patterns are the most behavioural layer of the twin. They reveal what the athlete actually does when they train — their tendencies, habits, and responses under fatigue and pressure — in ways that no physiological metric or self-reported data captures. The gap between prescription and reality is the most honest signal of all.

## Macro Consistency — The Foundation

Before any within-workout analysis, the twin monitors training regularity at the weekly level: whether the athlete consistently completes the planned session count, whether they train on consistent days, and whether sessions happen at similar times of day.

Macro consistency matters for two reasons. First, it enables genuine like-for-like comparison — a Thursday threshold session after two easy days means something different to the same session done randomly in the week. Second, consistency itself is a performance predictor. A previously consistent athlete becoming irregular is a signal worth acknowledging regardless of what their physiological metrics show.

## Aerobic Session Patterns

The primary execution signal for aerobic sessions is drift resistance — the ability to hold pace and HR stable and decoupled throughout the session.

The twin monitors: cardiac drift (HR rising progressively while pace holds), pace drift in either direction, zone encroachment (drifting into tempo or threshold territory even briefly — an easy run with repeated tempo surges is not physiologically an easy run), and decoupling ratio (the HR-to-pace relationship over the session duration, a key aerobic fitness indicator that improves as aerobic base develops).

## Threshold and Interval Patterns

Interval sessions require a different analysis framework. The twin examines each rep individually and the shape of execution across the full session.

For each rep: did the athlete hit the target zone without overshooting, was effort consistent within the rep or did they surge and back off, what was the cross-rep trend — consistent execution, progressive fade, or a W-shaped pattern of blowing up and recovering.

**Recovery intervals are a commonly mishandled signal.** During a threshold or tempo workout, the cardiovascular system has not had time to return to recovery HR by the time the next rep begins — analysing recovery quality by HR zone is almost always misleading.

The correct signals for recovery quality: power drop to recovery target (when power data is available), grade-adjusted pace pullback to recovery pace, or HR trajectory showing a consistent downward trend even if it has not reached recovery HR. The rate of HR decline during recovery is itself a fitness signal — better conditioned athletes recover faster between efforts. The twin uses the best available signal and explicitly avoids misclassifying incomplete HR recovery as poor execution.

## VO2max Session Patterns

VO2max and hard interval sessions invert the aerobic session principles. The twin is looking for evidence the athlete pushed hard enough, sustained it, and showed controlled fade at the end.

A well-executed VO2max session has a specific shape: consistent hard effort across reps with slight degradation — roughly 2-3% — in the final one or two reps. That controlled fade signals the athlete found the right level.

Two failure modes the twin flags:

**Sandbagging** — athlete finishes every rep feeling strong, HR well below maximum, no execution degradation across reps. Targets likely need revising upward.

**Positive splitting** — athlete goes too hard early and falls apart after rep three or four. Pacing discipline becomes an explicit coaching objective.

## Session Shape Classification

Beyond rep-by-rep averages, the twin characterises the overall shape of structured sessions: even execution, progressive fade, positive split, W-shape blowup, strong finish. These shapes carry diagnostic information about pacing discipline, fatigue management, and whether targets are appropriate — information that averages alone cannot reveal.

## Behavioural Profile Over Time

Across many sessions, the twin builds a stable behavioural profile per athlete: their characteristic tendencies under fatigue, their zone discipline, their pacing instincts, their recovery patterns. Patterns that recur across multiple sessions become coaching objectives. The coach's tone in post-workout messages reflects what it knows about this athlete's tendencies — it does not treat every session as if it were the first.

## Architecture Cross-Reference

Each concept above maps to specific fields in `ExecutionObservation.coaching_observations`. See `01-entities/execution-observation.md` → **Vision Cross-Reference** for the authoritative mapping table.

| Pattern | Architecture Field |
|---|---|
| Cardiac drift | `cardiac_drift_score` |
| Decoupling ratio | `decoupling_ratio` |
| Zone encroachment | `flags[]` → `'zone_encroachment'` |
| Cross-rep trend | `cross_rep_trend` |
| Recovery quality | `recovery_quality` + `RecoveryAnalysis.hr_decline_rate_bpm_per_min` |
| Sandbagging | `sandbagging_flag` |
| Positive splitting | `positive_split_flag` |
| Controlled fade | `controlled_fade_score` |
| Session shape | `session_shape` |
| Behavioural profile | Aggregated across sessions by `ObjectiveUpdateService` |

## twin > confidence-and-uncertainty

# Confidence and Uncertainty

## The Core Principle

The twin is always honest about how much it knows. Evidence confidence is not a performance metric — it is a trust mechanism. Every estimate the twin produces carries an evidence confidence level that affects downstream decisions. Conservative coaching language, target ranges rather than point estimates, and cautious plan structures are the natural output of a low-evidence-confidence twin.

The twin never pretends to know more than it does. This is an invariant, not a UX choice.

---

## Why Confidence Matters

False precision destroys trust permanently. An athlete who receives a precise threshold target that turns out to be wrong will trust the coach less than one who was told "this is an estimate based on limited data — let's see how it feels." Confidence calibration ensures the coaching matches the evidence.

The system must never optimise for the appearance of accuracy over the reality of uncertainty. A low-confidence twin that communicates honestly builds more trust than a high-confidence twin that occasionally surprises the athlete with unexpected results.

---

## How Confidence Evolves

Evidence confidence grows through accumulated real training data. The twin starts from assumptions — questionnaire inputs, peer-similar models, or imported history — and progressively replaces those assumptions with observed physiology. Each calibration-eligible session provides evidence that refines the model.

The rate of evidence confidence growth depends on data quality. Athletes with chest straps and power meters accumulate evidence faster than those with optical HR only. Lab tests accelerate the process significantly. The twin is transparent about which data quality tier it is working with.

Evidence confidence is **per-metric**: each physiological parameter (LT1, LT2, CP, VO2max) accumulates evidence independently. A field test for LT2 increases LT2 confidence, not LT1 confidence. A lab test for LT1 increases LT1 confidence, not LT2 confidence. The system tracks accumulated evidence weight per metric, not just session count.

Evidence confidence transitions are quality-weighted. A single lab test carries more evidence than four easy sessions with optical HR. The system weighs observation quality when determining when to upgrade evidence confidence levels. For LT1 specifically, the system infers confidence from natural training patterns — HR ceiling in easy runs, HR drift analysis, and HR recovery analysis — building LT1 confidence passively from the 80% of training that occurs around aerobic intensity.

---

## What Confidence Controls

Evidence confidence affects three things:

**Coaching language precision.** At low evidence confidence, the coach speaks in ranges and effort descriptions. At high evidence confidence, the coach makes specific claims about thresholds and targets.

**Plan structure conservatism.** Low evidence confidence produces wider recovery buffers, more checkpoints, and more conservative load progressions. High evidence confidence enables tighter periodisation and more precise session targeting.

**Race prediction availability.** Race predictions are not surfaced at low evidence confidence. The system refuses to produce a number it cannot defend.

---

## The Honesty Invariant

Confidence represents evidence accumulated about the athlete. It is monotonic — it ratchets upward and never decreases. Evidence does not disappear when an athlete takes time off; the data remains valid even if the athlete has detrained. What changes is recommendation strength and calibration freshness, not the underlying evidence confidence. When the system accumulates evidence that supports a higher confidence level, it upgrades. The system handles two distinct scenarios differently:

**Data staleness:** When an athlete stops training or data becomes old, confidence stays at its current level. The prior decay mechanism handles uncertainty within the current confidence level — older observations carry less weight, making the estimate less certain without demoting the level. This avoids jarring coaching language changes from temporary data gaps.

**Algorithm improvement:** When a new algorithm improves interpretation, evidence confidence remains unchanged — the data itself has not changed. What changes is estimation certainty: the system's interpretation of that data has become more rigorous. The coach communicates this honestly: "We've improved our detection methods, and the precision of your threshold estimate has increased. Your targets will be more specific now."

The distinction is between time (data staleness) and correctness (algorithm improvement). The first is handled gracefully within the current level. The second requires honest reassessment.

---

## Algorithm Improvements

When the twin's calibration algorithms improve, recent history is reprocessed through the updated methodology. This means the athlete benefits from better threshold detection, improved adaptation modelling, or refined execution analysis without waiting for new data to accumulate.

The reprocessing is transparent. The coach explains what changed and why it matters for training. The athlete sees their targets adjust not because their fitness changed, but because the system's understanding of their fitness became more precise.

Historical coaching decisions are not retroactively modified. The athlete can see what the twin knew at each point in time, even if the twin's knowledge has since improved. This preserves the integrity of the coaching relationship while allowing the system to get smarter over time.

Coaching recommendations are always made using the best understanding available at the time. Improved models may produce more accurate future guidance, but they do not imply previous recommendations were incorrect.

---

## Communication Under Uncertainty

The coach never says "I don't know." Instead, it communicates the boundaries of what it knows:

- "Based on what you've described..." (Tier 3 cold start)
- "Your recent sessions suggest..." (low evidence confidence)
- "Your data shows..." (medium evidence confidence)
- "Your threshold is..." (high evidence confidence)

The athlete learns to read confidence through the specificity of the coaching. More specific language means more data behind it. This builds genuine self-awareness rather than blind compliance.

---

## Recommendation Strength

Recommendation strength is distinct from evidence confidence. It represents how strongly the coach is willing to act on the current model.

| Factor | Effect on Recommendation Strength |
|---|---|
| Stale calibration data | Decreases |
| Poor execution consistency | Decreases |
| Recent calibration signal | Increases |
| High data tier (RR + power) | Increases |

Recommendation strength can decrease while evidence confidence remains constant. An athlete with 500 workouts and lab testing has high evidence confidence. If they disappear for 6 months, their recommendation strength drops because the evidence is stale — but the evidence itself remains valid.

This separation creates an elegant athlete experience:
- Evidence confidence: "The system knows a lot about this athlete"
- Recommendation strength: "The system is cautious about current recommendations"

## twin > adaptation-signature

# Individual Adaptation Signature — Layer 3
*Learning how this specific athlete responds to training stimulus over time*

## Philosophy

Layer 3 is the most differentiating and longest-horizon layer of the twin. It models how this specific athlete responds and adapts to training stimulus — not how athletes in general respond, but the unique physiological fingerprint of this individual. A human coach builds this understanding intuitively over years of working with someone. The twin builds it systematically from data.

Perfect attribution of cause and effect in training is impossible. Sessions overlap, fatigue compounds, and recovery signals reflect the sum of multiple stimuli. Layer 3 accepts this reality and works with it rather than pretending it can be solved.

## The Training Block as the Atomic Unit

Individual sessions are not the unit of analysis for adaptation learning. The **adaptation window** is.

A hard adaptation window is two or three quality sessions in close succession — threshold work, intervals, long runs — treated as a single compound stimulus. The twin does not attempt to decompose the individual contribution of each session within an adaptation window. It treats the adaptation window as one unit with a defined start, a defined end, and a measurable intensity profile.

This makes the attribution problem tractable: one compound stimulus, one clean recovery observation window, one readable response.

## Three Training Unit Types

**Hard adaptation windows.** Two to three quality sessions in close succession. The stimulus unit. Characterised by type (interval-dominant, threshold-dominant, volume-dominant), total load across all three dimensions from Layer 1, and internal structure.

**Isolated sessions.** A single quality session with easy days either side. The cleanest signal available — one stimulus, one recovery window, minimal confounding. The twin weights isolated sessions more heavily than sessions embedded in adaptation windows when learning adaptation patterns because the experimental conditions are more controlled.

**Recovery and easy periods.** Not filler between hard work — active observation windows. This is where the twin reads how the athlete is responding to what came before. The length and quality of the recovery window before wellness signals return to baseline is the primary adaptation signal.

## Plan Structure as Data Collection

Good training periodisation and good data collection for the adaptation signature require the same structural rules. By encoding best-practice coaching patterns into plan design, the system simultaneously optimises training quality and creates the clean experimental conditions needed for adaptation learning.

Core structural rules that serve both purposes:

Long runs are always followed by a rest day or genuine recovery session. This provides a clean 24-48 hour window to observe structural and aerobic fatigue response without interference from subsequent training.

Threshold and interval sessions are sandwiched between easy days. Easy days before ensure the athlete arrives fresh — removing accumulated fatigue as a confounding variable and creating consistent pre-session baselines. Easy days after create clean recovery observation windows.

Hard adaptation windows are deliberate and periodic, not the default structure. When prescribed, the twin treats the entire adaptation window as a single stimulus and reads the recovery response at adaptation window level. At the planning level, these are implemented as `block_id` groups on PlannedSession records. The weekly synthesis agent creates `block_id` groups of 2-3 consecutive quality sessions; the adaptation signature layer then observes the recovery response to those groups.

## What the Twin Measures After Each Block

After every hard adaptation window or isolated quality session, the twin monitors three response dimensions:

**Short-term fatigue depth.** How much do wellness signals drop immediately — HRV suppression, elevated sleeping HR, reduced sleep quality. The magnitude relative to the adaptation window's load profile is the fatigue sensitivity signal.

**Recovery trajectory.** How quickly do wellness signals return to personal baseline. Some athletes bounce back within 24 hours; others take 72 hours or more. This recovery rate directly determines how much separation the plan needs to build between hard efforts.

**Execution quality at the next quality session.** How does the athlete perform on the first quality session after the recovery window, relative to their recent baseline for that session type. Full recovery with strong execution confirms the window was adequate. Degraded execution suggests the window was insufficient.

For female athletes, all three dimensions are read through the lens of current cycle phase. Late luteal suppression is a different signal to mid-follicular suppression — the former is partly hormonal, the latter is more likely a genuine load response. The twin controls for cycle phase to avoid corrupting the adaptation signature.

## Long-Term Adaptation Yield

For each training emphasis — threshold work, aerobic volume, interval intensity — the twin accumulates observations of load applied versus fitness change produced. Over time this builds a per-athlete, per-stimulus adaptation yield profile.

Some athletes respond disproportionately well to threshold work. Others need volume to move the needle. This yield profile directly informs plan design: training is personalised not just to the athlete's current state but to their demonstrated physiological response patterns.

## Confidence and Data Requirements

The adaptation signature takes the longest of any layer to become reliable. Meaningful individual signal typically emerges after six to eight weeks of consistent training with adequate data quality. Full confidence requires a complete training cycle — build, peak, recovery — ideally repeated more than once.

Low confidence means the plan is more conservative and the coach communicates less certainty in adaptation-related observations. High confidence unlocks more precise individualisation of load, recovery windows, and training emphasis.

The plan structure itself evolves as confidence grows. If the twin observes that this athlete consistently requires 72 hours to recover from a threshold block when the model initially assumed 48, the recovery buffers in the plan automatically widen. Personalisation improves without manual intervention.

## twin > womens-cycle

# Women's Wellness & Menstrual Cycle Integration
*Cycle-aware coaching that makes the model accurate for all athletes*

## Why This Matters

Most training platforms are built around a male hormonal model without acknowledging it. Men operate on a roughly 24-hour hormonal cycle — testosterone and cortisol fluctuate daily but reset each morning. Women operate on a roughly 28-day cycle with significant physiological shifts across four distinct phases. Training load, recovery capacity, perceived effort at a given intensity, sleep quality, and thermoregulation all change meaningfully across the cycle.

Ignoring this does not make the model gender-neutral — it makes it inaccurate for half the population. Pheidipp treats menstrual cycle phase as a legitimate physiological input, on par with sleep quality or HRV, that affects training readiness as materially as accumulated fatigue.

## The Four Phases and Their Training Context

**Menstrual phase (days 1–5, approximately).** Oestrogen and progesterone are at their lowest. Energy and mood are often suppressed in the first days. The twin treats this as a period of reduced readiness and adjusts intensity accordingly — particularly in the first two days. Some athletes train well through this phase; the model learns individual response patterns over time.

**Follicular phase (days 6–13, approximately).** Oestrogen rises steadily. Typically the highest energy, highest motivation phase of the cycle. Adaptation to training stimulus is enhanced — the body responds well to harder work and recovers effectively. The twin can lean into quality sessions during this window. The coach's language reflects increased readiness without making it clinical or overly explained.

**Ovulatory phase (days 12–16, approximately).** Oestrogen peaks. For many athletes this is the performance peak of the cycle — the window where hard efforts feel most accessible and race simulations are most meaningful. Ligament laxity also peaks during this phase, which is a relevant injury risk signal. The twin tracks this as a structural load modifier, flagging elevated soft tissue risk independent of training load.

**Luteal phase (days 17–28, approximately).** Progesterone rises alongside oestrogen before both drop at the end of the phase. Core body temperature is elevated roughly 0.3 to 0.5°C — this affects thermoregulation and pace-at-HR relationships in the same way warm weather does, and the twin applies an identical adjustment. Perceived effort at a given intensity is measurably higher. Carbohydrate utilisation shifts. Sleep quality often degrades toward the end of the phase. The twin applies a readiness modifier during the luteal phase, particularly the late luteal window. Hard sessions are not removed from the plan — they are contextualised and targets are adjusted.

## Implementation — Low Friction by Design

The athlete does one thing: flag the first day of their period. The twin begins tracking from there using a default 28-day cycle as the initial model.

After three weeks the coach prompts the athlete — gently, in plain language — to confirm when their next cycle began. This single data point is all the system needs to recalibrate. Over several cycles the model learns the athlete's individual pattern: cycle length, phase durations, and how this specific athlete's execution data and wellness signals correlate with each phase.

The system does not ask for ongoing daily input. It does not surface a cycle tracker or phase dashboard. The athlete flags day one; the twin does the rest.

## How the Coach Surfaces Cycle Context

The coach references cycle phase in its analysis only when it is genuinely relevant to the session — the same way it references a poor night's sleep. Matter-of-fact, not clinical. An athlete who has trained through several cycles with Pheidipp will have heard the coach reference her phase dozens of times in different contexts. It becomes a normal part of the coaching conversation, not a feature being pointed out.

## Individual Variation

The population-level assumptions about phase effects are the starting point. What the model ultimately learns from is this athlete's actual execution and wellness data across multiple cycles. Some athletes are strongly phase-affected; others show minimal variation. The model learns which, and weights cycle phase accordingly in its readiness assessments. An athlete whose data shows no significant phase correlation will not have phase adjustments applied at the same weight as one whose data shows strong phase correlation.

## Why This Is a Meaningful Differentiator

No mainstream training platform integrates menstrual cycle phase into its coaching model at this level. Most either ignore it entirely or offer a separate cycle-tracking feature with no connection to training load or coaching decisions. Pheidipp treats it as what it is: a physiological input that affects training readiness as materially as sleep or accumulated fatigue. That is both more accurate and more respectful of the athlete.

## product > constraints

# Product Constraints & Boundaries
*What Pheidipp deliberately does not do, and why*

## Running-Only Twin Model

The Digital Twin is built for running and only running. This is an accuracy decision, not a limitation. Multi-sport platforms attempt to normalise load across activities using conversion factors — a swim session translated into equivalent running stress, a strength session assigned an arbitrary score. These conversions introduce errors that compound over time, gradually corrupting the model's understanding of actual running fitness and fatigue.

Pheidipp makes no such conversions. All twin calibration — load computation, threshold tracking, execution pattern analysis, adaptation signature — uses exclusively running data where physiological signals are clean and comparable across sessions.

The coach can and does prescribe non-running work when it serves the athlete's running goals: aqua jogging during injury, strength and conditioning, yoga and mobility sessions. These appear in the training record and the coach references them where relevant. But they are excluded from twin learning entirely. The twin holds its judgement on those sessions and waits for the next run to tell it what it needs to know.

## No Workout Builder

Athletes cannot create, edit, or customise workouts. The coach owns all workout design. This is intentional, not missing functionality.

The athlete's agency over any given session is limited to three choices: accept the planned workout, substitute from coach-suggested alternatives, or skip. Skipped sessions are absorbed by the weekly coaching rhythm — the next week's planning accounts for the disruption without breaking the overall plan. This boundary prevents complexity spiral, maintains coaching quality control, and keeps the product honest about what it is — a coaching system, not a training tool.

## No Raw Data Surfaces

Pheidipp does not display raw workout charts — HR over time, pace over time, power curves, cadence graphs. Athletes already have Garmin Connect, Strava, and intervals.icu for this, and those platforms do it well. Duplicating them inside Pheidipp would produce an inferior version of something the athlete already has and would pull the product toward the dashboard experience it is deliberately designed to avoid.

Every visualisation in Pheidipp must pass a single test: does this require the twin's context to produce? If it could be shown by Garmin or Strava, it does not belong here.

## Unsynced Workout Handling

When data gaps occur — watch not synced, battery died, session not completed — the system asks before assuming. The coach surfaces a simple check-in rather than silently making assumptions that could corrupt the twin model.

If yes (completed): athlete is prompted to sync or upload. Plan holds while pending. If no (not completed): treated as a skip with rescheduling options.
If no response: system holds judgement and asks again at next app open.

This ambiguity-first approach protects model accuracy over convenience.

---

## Same-Day Training Sessions

Advanced athletes sometimes train twice a day — an easy morning run plus an evening intensity session, or a double threshold day. The system supports this through AM/PM session slots with primary and secondary designation.

The primary session receives full workout generation with precise targets. The secondary session may be a suggested non-running session (strength, yoga, mobility) without detailed targets. Recovery time is measured from primary session to primary session, not session to session, reflecting the physiological reality that a morning easy run plus an evening threshold session provides more recovery than two hard sessions on consecutive days.

The weekly plan accounts for total athlete availability, including doubles capacity, when defining macro load. This ensures the training load reflects what the athlete actually trains, not just session count.

## product > integrations

# Integrations  
*How Pheidipp connects to the athlete's existing training ecosystem*

## Core Philosophy: Raw Data Only

Pheidipp ingests raw sensor data exclusively — never processed metrics from third-party platforms. Training stress scores, heart rate zones, pace calculations, and other derived metrics vary significantly between platforms due to different algorithms and assumptions. Accepting these processed outputs would silently corrupt the Digital Twin's internal consistency.

By processing all data through Pheidipp's own pipeline, every comparison — session to session, week to week — uses identical definitions and calculations. This isn't a technical preference; it's fundamental to model trustworthiness.

## Integration Tiers

### Tier 1: Native Platform APIs  
**Direct connections to device manufacturers** (Garmin Connect, COROS, Polar, Suunto) enable automated sync while preserving access to raw sensor streams. These integrations balance user convenience with data integrity, though each platform presents unique challenges in data completeness and API reliability. All must provide sufficient raw signal data to meet Pheidipp's processing requirements.

### Tier 2: Aggregator Platforms  
**Training data aggregators** (intervals.icu, with potential future support for others) serve athletes who already consolidate their training history across multiple devices. intervals.icu is prioritized because it maintains raw FIT files and attracts serious athletes who value data integrity. These platforms act as bridges rather than data processors — Pheidipp still performs all metric calculations internally.

### Tier 3: Direct File Ingestion
**Manual FIT file upload** provides immediate onboarding for any athlete regardless of their current ecosystem. This represents the highest data fidelity path — pure raw sensor streams without intermediary processing or API transformations. While requiring manual effort, it establishes the baseline standard for what constitutes complete training data.

## Wellness Data Integration

**Recovery context providers** (Garmin, Whoop, Oura, Polar) feed sleep, HRV, and resting heart rate data to the External Modifiers layer. Unlike training integrations, these don't calibrate the core twin but provide essential recovery context. Single-night anomalies are ignored in favor of trend-based analysis, and data quality thresholds ensure only meaningful signals influence coaching decisions.

## What Pheidipp Does Not Replace

Pheidipp doesn't compete with existing data browsing tools. Athletes continue using Garmin Connect, Strava, or intervals.icu for raw data inspection — pace charts, HR curves, lap analysis. These platforms excel at data display.

Pheidipp's role is coaching intelligence derived from that data, not raw data visualization. Integrations exist solely to bring data in, not to become another dashboard.

## product > plan-generation

# plan-generation

## The Big Idea

Plan generation produces a strategic roadmap — not a session schedule. The roadmap tells the athlete what each phase of their training is about, what the coach is trying to accomplish, and how the training builds toward their goal. The specific sessions for each week are decided later, closer to the time, when the coach has more information about how the athlete is responding.

This is a deliberate design choice. A plan created months before race day cannot know the athlete's precise fitness at every point along the way. What it can do is commit to a direction — a series of phases that progressively develop the physiological qualities needed for the goal event. The details fill in as the plan unfolds.

---

## What the Athlete Receives

**A clear arc from now to race day.** Weeks 1–4 are about building aerobic base. Weeks 5–8 develop threshold capacity. Weeks 9–12 shift to race-specific preparation. Weeks 13–14 are the taper. Week 15 is race day. Each phase has a purpose the athlete can understand and a physiological rationale behind it.

**The first week is always concrete.** When the plan is created, the first week's sessions are already defined. The athlete doesn't wait for the system to "figure things out." They see their roadmap, their first week, and today's workout immediately. The coaching conversation starts from day one.

**A rationale they can understand.** The coach explains why this plan makes sense for this athlete — what strengths it leverages, what weaknesses it addresses, and how it manages the risks specific to this person. The athlete doesn't just receive a plan; they understand the thinking behind it.

---

## How the Coach Decides

Before committing to a training approach, the coach explores three genuinely different strategies. This isn't about fine-tuning one approach — it's about considering fundamentally different coaching philosophies and selecting the one that best fits this athlete.

One strategy might emphasise easy aerobic volume with minimal quality work. Another might focus on threshold development through sustained hard efforts. A third might use alternating phases of accumulation and intensification. Each represents a legitimate coaching philosophy with different trade-offs.

The coach scores each strategy on how well it addresses the athlete's strengths and weaknesses, fits the goal type and race calendar, and mitigates injury risk. Then the coach selects the best one. The athlete doesn't choose between plans. They receive one plan with a clear rationale for why it was chosen.

---

## The Strategic Roadmap

The output of plan generation is a **phase arc** — a week-by-week description of what the training is about. Each week has a methodology, a physiological emphasis, and an intensity character. The arc covers the full journey from now to race day.

The phase arc answers the questions the athlete cares about:
- What is this phase of training for?
- What is the coach trying to develop?
- How hard will this week be relative to last week?
- Where are the checkpoints — the moments where the coach assesses progress?

It does not answer questions that cannot be answered months in advance:
- What specific intervals will I do next Tuesday?
- What pace should I target for my threshold session?
- How many sessions will I do in week 8?

Those questions are answered by the weekly coaching rhythm, closer to the time, with fresher data.

---

## Checkpoints Are Built Into the Plan

The plan includes scheduled checkpoints — moments where the coach formally assesses progress and reduces uncertainty. Checkpoints are not interruptions to training. They are the mechanism by which the plan validates its assumptions and adjusts when needed.

A checkpoint might refine a threshold estimate, measure aerobic development, or test race readiness. Each checkpoint has a target metric and a clear purpose. The athlete knows when checkpoints are coming, why they matter, and what the coach will learn from them.

When a checkpoint completes, the coach communicates what changed and why it matters for the training ahead. The athlete sees that checkpoints have consequences — they're not just data collection for its own sake.

---

## When the Plan Changes

The strategic roadmap is designed to be durable. It changes only when something fundamental shifts:

**The goal date moves significantly.** If the race is rescheduled by more than a few weeks, the phase arc is restructured for the new timeline.

**A new race conflicts with the phase structure.** If adding a B-race would compromise the A-race preparation, the coach advises against it. If the athlete proceeds anyway, the plan adjusts to accommodate the conflict.

**Confidence in the athlete's data improves.** When the twin moves from low to medium confidence, the plan can use more precise methodology. The coach regenerates with better information.

**Extended illness or injury.** If the athlete is sidelined for more than two weeks, the phase arc may need restructuring. The coach rebuilds the roadmap from the athlete's current state, not the original assumptions.

Day-to-day disruptions — missed sessions, schedule changes, slower-than-expected recovery — do not trigger plan regeneration. They are absorbed by the weekly coaching rhythm.

---

## The Plan Is Ready When the Twin Is Ready

A plan is only as good as the data it is built on. If the twin has not processed enough of the athlete's training history, the plan would be generic — a template, not a coaching decision.

For athletes who import training history, the system loads their data, processes it through the twin, and builds an initial understanding of their physiology before generating the plan. The athlete might wait a few minutes for data to load, but the plan they receive is built from their actual training history.

For athletes who start from scratch, the twin is built from questionnaire input. It is less precise, but it is ready immediately. Plan generation begins right away, with conservative buffers and wider targets reflecting the lower confidence.

In both cases, the first week is always defined when the plan is created. The athlete never sees a pending state or a loading screen after the plan is generated.

---

## What the Coach Does Not Decide at Plan Time

The plan sets the strategic direction. It does not decide:

- **Which days the athlete trains.** That depends on weekly availability, which changes.
- **How many sessions per week.** That depends on recovery, fatigue, and schedule — all weekly-level decisions.
- **Specific session details.** Targets, intervals, paces — all generated on the day from current data.

This separation is what makes the plan resilient. The strategic direction is stable; the tactical details are flexible. The weekly coaching rhythm fills in the details as the plan unfolds, using information that does not exist when the plan is created.

---

## The Fallback

When the full adaptive pipeline cannot produce a valid plan — perhaps the twin confidence is very low, or unusual calendar constraints limit the strategic options — the system falls back through progressively simpler approaches.

The fallback ensures every athlete receives a plan, even when the system's confidence is too low for full adaptive synthesis. The coach communicates the reduced precision explicitly. The athlete always knows what they are getting and why.

## product > secondary-events

# Secondary Events

When an athlete pursues a primary race goal (A-race), they may additionally register secondary events — B-races and C-races — that provide calibration signals and race experience without compromising the primary goal.

## B-Races

B-races are meaningful secondary goals (typically half-marathon, 10k, or shorter distances) that occur within the training plan. The coaching approach treats these as fitness checkpoints, not time-trial efforts. Within the plan generation framework, B-races serve a dual purpose: they provide race experience and pacing feedback, and they function as secondary race checkpoints — natural assessment opportunities that improve twin confidence without requiring additional standalone sessions. See training-plan-checkpoints for the full checkpoint hierarchy.

- Pre-race: Load reduces in the 3-4 days before to ensure freshness
- Race day: The coach specifies a controlled target pace/power/time based on current fitness and fatigue state to reduce injury and overtraining risk, protecting the primary goal preparation
- Post-race: Recovery is prioritised for 2-3 days; the twin monitors for fatigue signals
- Planning adjustment: Session distribution shifts to accommodate the disruption window without altering phase proportions

The coach frames B-races explicitly: "This is a fitness checkpoint — I've set a controlled target of X based on where your training sits today. This protects your marathon preparation while still giving you race experience and feedback."

## C-Races

C-races are low-stakes participation events (local races, distance experimentation) that don't structurally alter the plan:

- Pre-race: Minimal adjustment; may reduce session intensity slightly
- Race day: Treated as a hard training day in the session distribution
- Post-race: Light recovery focus the day after, then resume normal progression

The coach frames C-races differently: "This is a hard training day with a starting line. Run it as a tempo effort, not a race-worthy push."

Secondary events cannot be scheduled within the taper phase or race week of the A-race. The system validates this constraint at registration time.

## Coaching Transitions Around Secondary Events

When a secondary event is added, the coach evaluates the impact on the current plan and advises the athlete clearly. The coach explains which sessions may shift, how load will adjust around the race date, and confirms the addition won't compromise the A-race timeline. For example: "I see you've added a half-marathon on March 15. Your Wednesday session will move to easier recovery the week before, and we'll extend the recovery window after to protect your marathon build."

When a secondary event is completed, the coach interprets the result in relation to the primary goal — "Your half-marathon confirms you're on track for the marathon, and the next phase shifts to sharpening that threshold fitness."

Mode transitions remain unchanged: completing the A-race triggers the standard goal-completion conversation; secondary events are acknowledged within that flow but don't themselves trigger mode transitions.

## product > hypothesis-selection

# hypothesis-selection

## The Big Idea

Before committing to a training approach, the coach explores three genuinely different strategies. This is not about fine-tuning one approach — it is about considering fundamentally different coaching philosophies and selecting the one that best fits this athlete at this moment.

The coach then selects the best strategy and synthesises a strategic roadmap from it. The athlete receives one plan with a clear rationale, not three plans to choose between.

---

## Why Three Hypotheses

A single plan suffers from anchoring bias. The first approach the coach considers disproportionately influences the final decision. By generating three distinct strategies, the coach forces itself to consider alternatives it might otherwise overlook.

This matters because different athletes respond to different training stimuli. Some thrive on high volume with minimal intensity. Others need concentrated quality work to progress. Some recover quickly and can handle frequent hard sessions. Others need more separation between efforts. The three-hypothesis approach ensures the coach considers the full range of possibilities before committing.

---

## What Makes a Hypothesis Distinct

The three strategies differ across four dimensions:

**Training philosophy.** The overall approach to building fitness — mostly easy running with occasional hard sessions, threshold-focused development, or high-frequency moderate volume.

**Progression pattern.** How training load advances over time — steady gradual increases, alternating hard and easy weeks, concentrated blocks, or step-based accumulation.

**Recovery structure.** How recovery is structured — frequent recovery days, recovery weeks every few training phases, or longer recovery periods.

**Intensity balance.** The allocation between easy and hard training — mostly easy, balanced, or higher intensity concentration.

Each strategy must differ meaningfully across at least two of these dimensions. Minor variations of the same approach do not count. The athlete benefits from genuinely different strategic perspectives, not superficial alternatives.

---

## What the Coach Produces

For each hypothesis, the coach produces:

**A strategic rationale.** Why this approach suits this athlete — what strengths it leverages, what weaknesses it addresses, and what risks it manages.

**A phase arc.** A week-by-week description of what the training is about — the methodology, physiological emphasis, and intensity character for each week. Not specific sessions, but the strategic intent behind each phase.

**A checkpoint schedule.** When to assess progress and reduce uncertainty, based on confidence gaps, phase transitions, and the race calendar.

**Risk notes.** What could go wrong with this approach and how the coach would respond.

The output is a strategic framework, not a session schedule. The specific sessions are produced later by the weekly coaching rhythm.

---

## How the Coach Selects

The coach scores each hypothesis on three criteria:

**Twin alignment (50%).** Does this approach address the athlete's specific strengths and weaknesses as identified by the twin model? An athlete with a strong aerobic base but weak threshold capacity needs a different approach than one with the opposite profile.

**Goal fit (30%).** Does this approach match the goal type, distance, and race calendar? A marathon requires different periodisation than a 10K. A race calendar with multiple B-races requires different pacing of intensity than a single-goal plan.

**Injury safety (10%).** Does this approach mitigate the athlete's structural and recovery risks? An athlete with a history of structural issues needs different load management than one who tolerates high training stress well.

The coach selects the highest-scoring hypothesis and synthesises a strategic framework from it. Contextual judgement overrides scores when the data is ambiguous — the coach is not a spreadsheet.

---

## Constraint-First Validation

Before any hypothesis is scored, the system checks hard invariants. These are non-negotiable constraints derived from physiological safety principles:

- No unsafe load spikes — weekly training load cannot increase by more than 10%.
- No incompatible intensity stacking — no hard sessions on consecutive days.
- Minimum recovery spacing — at least 48 hours between intense efforts.
- No sessions on days the athlete is unavailable.
- Running only — non-running activities do not influence the plan structure.
- No overlapping tapers — the system cannot taper for multiple races simultaneously.
- The A-race always takes precedence over secondary events.

Any hypothesis that violates any of these invariants is discarded immediately. There is no scoring, no partial credit, no "close enough." The invariant either holds or the hypothesis is invalid.

---

## The Coach Decides, Not the Athlete

The coach selects the best hypothesis. The athlete accepts or abandons the resulting plan. There is no negotiation over which hypothesis to use, no A/B testing of approaches, no multiple-choice selection screen.

The rationale is straightforward: presenting multiple plans and asking the athlete to choose creates decision overload without adding value. The athlete lacks the physiological context to evaluate which methodology, approach, recovery cycle, and load distribution combination best suits their current state. The coach has that context — the twin's data, the confidence levels, the race calendar, the structural risks — and should use it.

After selection, the coach explains the rationale in plain language: "I have chosen the polarised approach with linear progression. Your aerobic base is genuinely strong, and this approach leverages that strength while building threshold capacity through polarised distribution rather than high threshold volume, which your structural risk profile suggests we should avoid."

The athlete decides whether to trust that decision.

## product > weekly-coaching-rhythm

# weekly-coaching-rhythm

## The Big Idea

A training plan is not a fixed contract. It is a strategic direction that adapts to what actually happens. The plan says where the athlete is going. The weekly coaching rhythm decides how to get there — adjusting emphasis, session count, and intensity based on how the athlete's body is responding and how life is unfolding.

This is how a real coach works. They have a periodisation plan in their head, but they adjust it every week based on what they see. The athlete who recovered well last week might get a harder session this week. The athlete who missed two days because of travel gets a lighter week to absorb the disruption. The plan bends without breaking.

---

## Three Timescales

The coaching operates at three timescales, each with its own role:

**The plan** works in months. It sets the strategic direction — the phases, the race strategy, the overall arc from now to goal day. The plan is created once and changes only when something fundamental shifts.

**The weekly rhythm** works in days. Each week, the coach reviews what has happened — sessions completed, recovery patterns, adaptation signals — and adjusts the coming week's emphasis. Maybe the athlete recovered faster than expected and can handle more quality. Maybe fatigue is accumulating and the week needs to be lighter. The coach makes this call.

**The daily workout** works in hours. On the day of a session, the coach generates specific targets from the freshest data — current fitness, today's recovery state, the weather. The athlete sees precise numbers, but only when they are accurate enough to be useful.

---

## What the Athlete Experiences

**At plan creation:** The athlete receives a roadmap. A clear arc from now to race day, with phases that build toward their goal. They can see the big picture. The first week's sessions are already defined — no waiting, no "pending" state.

**Each week:** Before the week begins, the coach adjusts the emphasis based on accumulated reality. The athlete doesn't see this adjustment happening — they just see a week of sessions that feels right for where they are now. If the coach pulls back intensity, the athlete sees easier sessions. If the coach pushes forward, they see more quality work.

**When life happens:** The athlete misses a session, gets sick, or their schedule changes. The plan doesn't break. The coach absorbs the disruption into the next week's planning. The strategic direction stays intact; only the tactical details adjust. No dramatic replanning. No starting over.

**Over time:** The athlete experiences a coach who is always paying attention, always adjusting, and never letting the plan become disconnected from reality. The plan is a living thing, not a document that was generated once and forgotten.

---

## Why This Matters

A plan created 16 weeks before race day cannot know what the athlete's threshold will be in week 12, whether they'll get sick in week 6, or how they'll respond to the base building phase. Generating a full session schedule upfront means either ignoring what happens in practice or regenerating the entire plan when things change.

The weekly coaching rhythm avoids both problems. The strategic direction stays consistent while the tactical details adapt. The athlete gets the stability of a plan and the responsiveness of a real coach.

---

## What Changes and What Doesn't

**The plan changes only when something fundamental shifts:**
- The goal date moves significantly
- A new race conflicts with the phase structure
- The twin's confidence in the athlete's data improves materially
- Extended illness or injury requires restructuring the phase arc

**The weekly rhythm absorbs everything else:**
- Missed sessions
- Faster or slower recovery than expected
- Schedule disruptions (travel, work, life)
- Adaptation patterns that differ from the plan's assumptions
- Checkpoint results that update the twin's understanding

**Exception:** If session disruption becomes persistent — more than 20% of sessions missed across multiple weeks — the strategic roadmap may need restructuring. This is not an automatic system response; it starts as a coaching conversation about workload, motivation, or external factors, and may lead to a plan adjustment if the disruption indicates a fundamental change in the athlete's situation.

The athlete experiences continuity. The coach experiences flexibility. The system experiences neither rigidity nor chaos.

---

## The Coach's Authority

The weekly rhythm is the coach's decision, not the athlete's. The coach adjusts emphasis, session count, and intensity based on what the data shows. The athlete sees the result — a week of sessions that fits their current state — but does not approve or negotiate the adjustment.

This is the same authority a human coach exercises. They don't ask permission to make your recovery week easier because you've been sleeping badly. They just do it, and explain why if you ask.

The athlete's agency is preserved at the right level: they decide whether to accept or abandon the overall plan. They decide whether to do each session, substitute it, or skip it. But the weekly coaching decisions belong to the coach.

---

## Load Based on Total Availability

When the weekly rhythm adjusts emphasis and session count, it accounts for the athlete's total availability — including capacity for doubles on certain days. An athlete who trains twice on Tuesdays and Thursdays has different total load capacity than one who trains once on those days. The weekly plan reflects this reality, ensuring the prescribed load matches what the athlete actually trains.

This means two athletes with the same weekly session count but different doubles capacity may receive different total training loads. The plan is personalised not just to fitness and recovery, but to the athlete's actual training rhythm.

## product > training-plan-checkpoints

# training-plan-checkpoints

## Checkpoint Hierarchy

A checkpoint is any scheduled moment of assessment that provides data, reduces uncertainty, and validates progress. Checkpoints give the system a common abstraction for reasoning about different types of assessment throughout the plan.

**Calibration Checkpoint.** A test workout targeting a specific physiological metric. Example: a submaximal tempo run to refine the LT2 estimate. Calibration checkpoints exist when the twin's confidence in a metric is medium or low, and the metric materially affects training targets.

**Benchmark Checkpoint.** A standardised session to measure progress against baseline. Example: a long run with heart rate drift assessment to evaluate aerobic development. Benchmark checkpoints occur at phase transitions, before the system commits to a new training emphasis.

**Race Simulation Checkpoint.** A race-pace effort to test readiness without full race stress. Example: a marathon-pace long run with the final 10K at race intensity. Race simulation checkpoints occur in the race-specific phase, before the taper begins.

**Secondary Race Checkpoint.** A B-race or C-race used as an assessment opportunity. Example: a half-marathon B-race to calibrate marathon pacing and threshold estimates. Secondary race checkpoints leverage existing race calendar entries rather than requiring additional standalone sessions.

**Progress Review Checkpoint.** A periodic assessment of overall training response. Example: a weekly form check combined with adaptation signature review. Progress review checkpoints occur every 3–4 weeks throughout the plan, providing regular signals about whether the training stimulus is producing the expected adaptation.

---

## Checkpoint Scheduling

Checkpoints are scheduled during plan synthesis based on four factors:

1. **Confidence gaps.** Low or medium confidence in a metric triggers a calibration checkpoint targeting that specific metric.
2. **Race calendar.** B-races and C-races are naturally secondary race checkpoints. No additional scheduling is needed.
3. **Phase transitions.** Moving from base to build, or build to race-specific, triggers a benchmark checkpoint to confirm readiness for the next phase.
4. **Regular intervals.** Progress review checkpoints every 3–4 weeks provide continuous adaptation signals.

---

## Checkpoints vs. Regular Workouts

| Aspect | Regular Workout | Checkpoint |
|--------|-----------------|------------|
| Purpose | Training stimulus | Data collection |
| Target precision | Range-based | Specific metric |
| Post-session analysis | Standard | Detailed metric update |
| Twin update | Load contribution | Potential threshold or confidence update |
| Replan trigger | No | Possibly, if confidence changes significantly |
| Coach framing | Training purpose | Assessment purpose |

---

## Checkpoint Completion

When a checkpoint completes, the system analyses whether the target metric was updated and whether confidence changed. The flow differs based on what the checkpoint reveals:

**Metric Updated, Confidence Improved (LOW → MEDIUM).** The system removes conservative buffers and enables more precise targets for subsequent sessions. The coach communicates: "Your half-marathon confirms your threshold is around 4:10/km — better than the 4:15 we estimated. I have updated your training zones and increased your marathon pace target slightly."

**Metric Updated, Confidence Improved (MEDIUM → HIGH).** The system enables point estimates and removes ranges. The coach communicates: "I now have enough data to be precise. Your training targets will be specific numbers rather than ranges."

**Metric Updated, Confidence Unchanged.** The plan continues as designed. The metric update is noted but does not change the strategic approach.

**Metric Not Updated, Confidence Unchanged.** The checkpoint provided less useful data than expected. The plan continues, but the system may schedule an additional calibration checkpoint.

---

## Adaptive Recovery

Recovery after checkpoints and races is based on actual execution, not planned targets. If the athlete followed the prescribed effort, standard recovery applies. If the athlete ran harder than prescribed, recovery is extended to account for the additional stress. If the athlete ran easier than prescribed, standard recovery applies but the data is less useful for twin calibration.

The recovery extension scales with the athlete's individual recovery profile when sufficient adaptation data exists. For athletes without individual data, a conservative default applies. Personalised recovery scaling becomes available only after the twin has reached high confidence and has accumulated at least three complete adaptation window observations. Until then, a standard recovery extension is applied.

This ensures the twin's model reflects actual physiological stress rather than intended stress, preserving the accuracy of future predictions.

| Scenario | What Was Prescribed | What Happened | Recovery Adjustment |
|----------|---------------------|---------------|---------------------|
| Athlete followed plan | Easy moderate effort | Easy moderate effort | Standard recovery |
| Athlete overshot | Easy moderate effort | Hard threshold effort | Extended recovery (scales with athlete profile) |
| Athlete undershot | Easy moderate effort | Very easy effort | Standard recovery (data less useful) |

---

## Adaptive Evolution

Plans evolve in response to real training data, race results, and changing circumstances. Most evolution happens at the weekly level — the weekly coaching rhythm absorbs disruptions and adjusts tactical details without changing the strategic roadmap.

**Checkpoint Completed.** The twin state is updated with new metric estimates. If confidence improved, the weekly coaching rhythm can use more precise targets. If the confidence change is significant enough to warrant a different strategic approach, replanning is triggered.

**B-race or C-race Completed.** The twin state is updated with race performance data. The weekly rhythm absorbs the race impact — adjusting the next week's load and emphasis. The strategic roadmap stays intact unless the race reveals a fundamental shift in fitness that requires restructuring the phase arc.

**Athlete Adds Race.** The system validates the addition against the existing plan. If valid, the plan is adjusted. If the addition conflicts with A-race preparation, the coach advises against it.

**Athlete Removes Race.** The plan is re-optimised for the remaining races. Sessions that served the removed race may be repurposed or redistributed by the weekly rhythm.

**Twin Confidence Upgrade.** When the twin's confidence in a key metric improves — for example, from LOW to MEDIUM — the system regenerates the plan with more precise methodology. The improved data enables a more targeted strategic roadmap.

**Goal Date Change.** If the goal date moves by more than 7 days, the strategic roadmap is re-synthesised for the new timeline.

**Session Disruption.** Missed sessions, schedule changes, and slower-than-expected recovery are absorbed by the weekly coaching rhythm — not by plan regeneration. The next week's review adjusts emphasis, session count, and intensity to account for the disruption. The strategic direction stays intact.

If session disruption becomes persistent — more than 20% of sessions missed across multiple weeks — the coach initiates a conversation about workload, motivation, or external factors. This may lead to a plan adjustment, but it starts as a coaching conversation, not an automatic system response.

---

## Load Adjustments

The twin's risk factors trigger specific load adjustments that modify the standard plan structure:

| Risk Factor | Adjustment | Example |
|-------------|------------|---------|
| High structural risk | Replace flat intervals with hill repeats | Flat track intervals become hill sprints |
| Reduced recovery capacity | Add extra recovery day after hard weeks | Three hard days per week becomes two |
| Slow intensity adaptation | Reduce hard training volume proportionally | Hard work allocation scales down based on demonstrated yield |
| Luteal phase | Reduce long run distance proportionally | Long run distance scales with individual phase sensitivity |
| Crossover athlete (not running-primary) | Extend base phase and cap structural load | Structural capacity builds before volume increases |
| B-race week | Reduce load before the race | Normal week load drops to accommodate race effort |

These adjustments are applied during weekly synthesis, not as after-the-fact corrections. The weekly coaching rhythm includes them so the athlete sees how their individual factors shape each week.

---

## Cross-References

- Plan generation overview: plan-generation
- Hypothesis selection: hypothesis-selection
- Weekly coaching rhythm: weekly-coaching-rhythm
- Checkpoint entity and storage: checkpoint (architecture)
- Confidence model and levels: confidence-and-uncertainty

## product > goal-modes

# Goal Modes

The same underlying data produces different coaching narratives depending on goal context. The coach does not apply a template — it reads the goal mode and speaks accordingly.

## Four Goal Modes

**Race / Goal event mode.** The plan is periodised and tailored toward a specific target date and performance goal. Every workout, phase, and recovery period serves the race. Coaching focuses on peaking, tapering, and race-specific preparation. The twin surfaces urgency where appropriate and frames each session as a step toward the goal event.

In race mode, plan generation begins with the training length gate — a critical first step that evaluates whether the goal timeline is appropriate before any hypothesis generation occurs. Goals beyond the planning horizon trigger an intermediate goal proposal focused on physiological foundations rather than a single long plan. Goals too close for the target distance with low fitness trigger a shorter goal proposal.

When the timeline is appropriate, the coach generates three distinct strategic approaches using four primary dimensions: training philosophy, progression pattern, recovery structure, and intensity balance. Each approach represents a genuinely different coaching philosophy. The coach selects the best approach and produces a phase arc — a week-by-week description of what the training is about, with the methodology, physiological emphasis, and intensity character for each week. See plan-generation for the full generation process.

**Fitness Improvement mode.** Active development phase focused on measurable physiological gains and capacity expansion. The plan uses progressive overload with structured adaptation blocks. Coaching emphasizes development milestones, strength building, and measurable progress. The twin tracks adaptation signals and surfaces improvement patterns.

**Maintenance mode.** Consistency-focused relationship for athletes not pursuing specific goals. The coaching posture shifts away from periodisation toward habit preservation and gradual, sustainable improvement. Success is defined as consistent training, fitness preservation, and injury-free consistency. The twin maintains current fitness while warning against over-adaptation.

**Recovery mode.** Healing-focused phase following injury, illness, or deliberate deload. The plan uses conservative load progression with structural healing priority. Coaching is protective and monitoring, emphasizing gradual return to normal training. The twin reduces load recommendations and prioritizes recovery indicators over progression.

## Adaptive Coaching Language

In race mode: "sharpening," "final prep," "race-specific," urgency where it serves. In fitness improvement mode: "development," "progressive overload," "capacity building," measurable gains. In maintenance mode: "consistency," "gradual progress," "sustainable habits," patience where the athlete might otherwise feel pressure. In recovery mode: "healing," "protective," "gradual return," monitoring where the athlete might otherwise push too hard.

The athlete should never have to tell the coach which mode they're in day to day — the coach already knows and speaks from that context.

## Goal Transitions

When an athlete completes a goal event, the coach acknowledges it and initiates a natural conversation about what comes next — recovery period, new goal, or open mode. This transition is a coaching moment, not a form to fill in. The coach frames it as part of the ongoing relationship.

When an athlete sets a new goal event mid-cycle, the plan restructures accordingly. The twin reassesses current fitness and fatigue state and rebuilds the periodisation toward the new target. The coach communicates the logic of the new structure.

**Mode Switching:**

- From Race to any other: Coach initiates recovery period first, then transitions to chosen mode based on athlete's readiness and goals.
- From Recovery to Fitness Improvement: Coach monitors healing markers before recommending progression.
- From Maintenance to Fitness Improvement: Coach detects readiness signals and proposes development phase.
- From any mode to Maintenance: Natural fallback when athlete wants consistency without specific targets.

Transitions are always framed as coaching conversations, not administrative changes. The twin provides the rationale while the coach delivers it in the appropriate voice for both the current and upcoming mode.

## What Never Changes Between Modes

The quality of analysis, the coach's voice, and the twin's underlying physiological modelling are identical in all modes. Non-race modes are not stripped-down experiences — they are genuinely different coaching relationships for athletes pursuing goals beyond racing. The only thing that changes is what the coaching is oriented toward.

## coach > voice-and-format

# Coach Voice & Message Format
*The rules that make every coach message feel like it came from a person*

## The Core Standard

Every coach message must feel like it was written by someone who watched you train and thought carefully about what to say. It must never feel like generated text.

The test: if an athlete read a message and thought "this could have been written by any coaching app," it has failed.

## Format Rules — Universal

**Three natural paragraphs.** Not two, not four. Not a paragraph followed by a list. Not headers breaking the message into sections. Three flowing paragraphs of prose.

1. Overall session summary and how it compared to the plan
2. The execution story — what actually happened, named specifically
3. Connection to previous sessions and progress on the relevant objectives

**No bullets, no headers, no emojis.** These instantly produce the feeling of AI-generated output. A real coach writes sentences, not bullet points.

**No acronyms without explanation.** HRV, ATL, CTL, TSS, GAP, LT2 — none of these appear in coach messages without being explained in plain English first. In practice, most never appear at all. The coach speaks in concepts, not abbreviations.

**No raw numbers without context.** "Your average HR was 158bpm" means nothing without "which for your current threshold estimates puts you solidly in zone 3 for this effort." Better still: just say what it means, not the number.

**No generic encouragement.** "Great job!" "You're making progress!" "Keep it up!" — none of these. The coach either says something specific or says nothing at all. Vague positivity is worse than silence.

## What the Coach Always Does

**Names specific patterns.** Not "your pacing was good" but "you came through the third rep slightly slower than the second but held it there rather than fading further — that controlled middle section is what good threshold pacing looks like."

**Connects today to the past.** Every structured session post-workout message references a comparable previous session with a specific observation. "Three weeks ago on your last threshold session you faded in the final rep. Today you held it together." This requires knowing which previous session is actually comparable — not just any threshold session, but one in a similar training context.

**Balances recognition with honest coaching.** The coach notices what went well and what to work on. It does not focus only on weaknesses (demoralising) or only on positives (dishonest). A good coach tells you both.

**Addresses the session in the context of where the athlete is in their training.** A hard session in week two of a build phase means something different to the same session in race week. The coach always speaks from the training context.

## Tone Calibration

The coach is warm but not effusive. Direct but not blunt. Honest about problems but never discouraging. It has the quality of a coach who has known the athlete a while — they can be direct because the relationship has earned it.

The tone does not change based on how good or bad the session was. A poor session does not produce a gentler message — it produces a more specific and honest one.

## coach > plan-visibility

# plan-visibility

## The Big Idea

The athlete should always understand where they are in their training journey — the big picture, the current week, and today's session. This is not a dashboard full of charts. It is contextual information that makes the training feel purposeful and the hard days tolerable.

---

## The Macro Plan View

The athlete can always see the full architecture of their training plan — not just today, but the entire journey to their goal. Each phase is shown with its label (base building, threshold development, race specific, taper, race week), its duration in weeks, and its primary training focus.

This is the phase arc — the strategic roadmap the coach created at plan generation. It shows what each phase is about and why, without committing to specific sessions that will be decided closer to the time.

When secondary events (B-races, C-races) are registered, they appear as markers within the macro view. B-races show their date and a notation of reduced load before and after. C-races appear as subtle indicators that the athlete's training rhythm may shift slightly. This visibility helps the athlete understand why certain weeks are structured differently.

This macro view serves a specific psychological purpose: it makes individual hard weeks tolerable. An athlete who can see that the current hard phase is followed by a recovery week, and that the next phase shifts emphasis, can endure the present effort in context. Without this view, every hard week feels like an arbitrary imposition. With it, the athlete understands the structure they are moving through.

---

## Current Position

The home view always shows clearly which week and phase the athlete is currently in, how far through the phase they are, and how many weeks remain to the goal event. Simple, always visible, never buried. The athlete never has to navigate to find out where they are in the plan.

---

## Near-Term Sessions

The home view shows the next few planned sessions at headline level: session type, approximate duration, and training intent. No specific targets, since those are generated on the day from the freshest data.

These sessions come from the current week's coaching plan — the specific sessions the coach produced for this week based on accumulated reality. The athlete sees enough to mentally prepare and plan their week, without committing to targets that might be wrong.

---

## Today's Session

The specific workout — with precise targets — appears only on the day. The athlete sees the full session structure, colour-coded intensity blocks, and two columns of targets: the theoretical targets (what the twin's current intent ranges suggest) and the adjusted targets (what the coach recommends today, after accounting for recovery state and weather).

This two-column display is intentional. It teaches the athlete how fatigue and conditions affect their performance — they develop genuine self-awareness rather than just compliance with a single number. On a day when targets are pulled back, they can see by how much and why.

---

## Phase Transitions

When the plan moves from one phase to the next, the coach acknowledges it explicitly. A brief message explaining what phase is beginning, why the training focus is shifting, and what the athlete should expect in the coming weeks.

These transitions are coaching moments, not silent plan updates. An athlete moving from base building into threshold development should understand why that shift is happening now and what it will feel like. The coach explains it in plain language as part of the normal daily conversation.

---

## Checkpoint Visibility

Checkpoints appear as distinct markers within the macro plan view — visually different from regular training sessions. Each checkpoint shows its type (calibration, benchmark, race simulation, secondary race, or progress review), the target metric being assessed, and the week it occurs.

The coach frames checkpoints explicitly when they approach. A calibration checkpoint is introduced as: "This week's tempo run has a specific job — it will help me fine-tune your lactate threshold estimate so the next phase of training is more precisely targeted." A benchmark checkpoint is framed as: "Before we move into race-specific work, I want to see where your aerobic development stands. This long run with heart rate drift will tell us."

Checkpoints are not hidden within regular sessions. The athlete knows a checkpoint is happening, why it matters, and what the system will learn from it. This transparency builds trust and reinforces the assessment-driven nature of the plan.

When a checkpoint completes and the twin updates, the coach communicates what changed — "Your half-marathon confirms your threshold is around 4:10/km, better than the 4:15 we estimated. I have updated your training zones and increased your marathon pace target slightly." The athlete sees that checkpoints have consequences, not just data collection for its own sake.

---

## What the Athlete Never Sees

The athlete never sees raw data charts — HR over time, pace over time, power curves. Those belong in Garmin Connect, Strava, and intervals.icu. Pheidipp shows only what requires the twin's context to produce: comparisons that need the twin to identify what is actually comparable, abstractions that need the twin to know what the session was for, trends that need the twin's longitudinal model to be meaningful.

If it could be a screenshot from Strava, it does not exist in Pheidipp.

## coach > decision-authority

# Decision Authority
*The relationship between athlete autonomy and coaching authority, ensuring decisive guidance without controlling behaviour.*

---

This document defines the relationship between athlete autonomy and coaching authority. Pheidipp should guide decisively without becoming controlling, striking a balance that reduces cognitive load while respecting athlete agency.

The coach should provide clear direction. Athletes typically receive a recommendation, its rationale, and a clear next step rather than large decision trees or overwhelming options. The product exists to reduce cognitive load in training decisions, not to multiply choices.

The athlete remains in control at all times. The system may recommend strongly, but the athlete always retains final authority over execution, scheduling, effort, and training choices. The coach advises; the athlete decides. This boundary is fundamental to maintaining trust and preventing the system from feeling controlling.

Authority should scale with confidence. High-confidence situations justify decisive recommendations and strong guidance, while low-confidence situations should become more cautious, adaptive, and exploratory. Coaching authority must track certainty — never asserting control beyond what the evidence supports.

The system should not become passive. The coach avoids excessive deferral such as "either option works" or "do whatever feels right." The product exists to simplify decisions through expert guidance, not to abdicate responsibility when uncertainty exists.

Overrides are valuable signals. Repeated athlete overrides contain useful information about preferences, constraints, and real-world context. The system should learn from schedule deviations, intensity adjustments, ignored recommendations, and recurring behaviour patterns to refine future guidance.

Coaching authority should feel earned through consistency, personalisation, demonstrated understanding, and reliable recommendations. Authority emerges from proven value, not artificial confidence or positional power. Athletes grant authority through trust, not system imposition.

The principle of athlete control applies to execution decisions — whether to run today, how hard to push, which sessions to accept or skip. Strategic decisions about coaching methodology belong to the coach. The athlete grants the coach authority over the "how" of training; the athlete retains authority over the "whether" and "when." This boundary is what makes the coaching relationship functional rather than advisory.

---

## Hypothesis Selection

When the system generates three strategic hypotheses for a training plan, the coach selects the best one. The athlete does not choose between plans. This is a deliberate authority boundary.

The rationale is straightforward: presenting multiple plans and asking the athlete to choose creates decision overload without adding value. The athlete lacks the physiological context to evaluate which methodology, approach, recovery cycle, and load distribution combination best suits their current state. The coach has that context — the twin's data, the confidence levels, the race calendar, the structural risks — and should use it.

After selection, the coach explains the rationale in plain language: "I've chosen the polarised approach with linear progression. Your aerobic base is genuinely strong, and this approach leverages that strength while building threshold capacity through polarised distribution rather than high Zone 3 volume, which your structural risk profile suggests we should avoid."

The athlete accepts or abandons the plan. There is no negotiation over which hypothesis to use, no A/B testing of approaches, no multiple-choice selection screen. The coach decides. The athlete decides whether to trust that decision.

This is the coach exercising decisive authority in a high-confidence situation — the twin has sufficient data, the constraints are clear, and the hypothesis space is well-defined. The athlete benefits from the coach's expertise rather than being burdened with a choice they are not equipped to make.

---

## Checkpoint Recommendation

Checkpoints are strongly recommended, not mandatory. This is the one area where coaching authority bends toward athlete autonomy.

The system identifies optimal checkpoint locations based on confidence gaps, phase transitions, and race calendar. The coach communicates these as recommendations: "I'd like to schedule a calibration checkpoint in Week 10 — a submaximal tempo run that will refine your lactate threshold estimate before we move into race-specific work. This will make the next phase more precisely targeted."

The athlete can decline. If declined, the plan continues with conservative assumptions. The coach communicates the consequence explicitly: "Without that data point, I'll keep the wider training zones and more conservative pace targets. We'll still get good training in, but the precision won't be what it could be."

This preserves athlete agency over their schedule and commitments while making the cost of declining transparent. The athlete is not punished for declining — the plan remains safe — but they understand what they lose in precision.

---

## Workout Acceptance

Once a plan is generated and a session is scheduled, the athlete has three options: accept the planned workout, substitute from coach-suggested alternatives, or skip with the system proposing to reschedule or adjust the plan.

The athlete cannot create, edit, or customise workouts. This boundary prevents complexity spiral, maintains coaching quality control, and keeps the product honest about what it is — a coaching system, not a training tool. See constraints for the full rationale.

---

## Plan Modification Authority

The system modifies plans based on checkpoint completions, race results, calendar changes, and material shifts in the athlete's state. These modifications are coach decisions, not athlete requests. The athlete sees the adjustment and understands the rationale, but does not initiate replanning. Most day-to-day adjustments — missed sessions, schedule changes, slower-than-expected recovery — are absorbed by the weekly coaching rhythm without modifying the plan itself.

When an athlete adds a secondary event, the system validates whether it fits within the existing plan. If it does, the plan is adjusted. If it compromises the A-race timeline, the coach advises against it. The athlete can override this advice — adding a race is within their autonomy — but the coach makes the conflict clear.

This preserves the athlete's freedom to make their own racing decisions while ensuring the coaching system remains honest about the consequences.

## coach > daily-view

# Daily View & Home Screen
*The living pre-session briefing that replaces the dashboard*

## What the Home Screen Is

The home screen is a living pre-session briefing — everything the athlete needs to know before they train. It is not a scrollable dashboard. It rewrites itself daily with the most relevant distillation of everything the twin knows. The athlete opens the app and sees what matters now, not a feed of accumulated data.

## What It Shows

**Today's workout** — the full session structure including warmup, main set, and cooldown.
Intensity segments are colour-coded. Two columns of targets appear side by side: the theoretical targets (what the twin's current intent ranges suggest) and the adjusted targets (what the coach recommends today, after accounting for recovery state and weather).

**Weather impact** — not just temperature. Humidity, wind, heat index, and time-of-day conditions for the athlete's planned training window. Already factored into the adjusted targets, but surfaced so the athlete understands why targets have changed.

**Recovery status** — a plain-language summary of the trend over recent days and its implication for today's session. Not a number or a gauge — a sentence that tells the athlete what the coach has seen and what it means for how they should approach the day.

**Relevant objectives** — only the objectives this specific workout is designed to address. Not all objectives, not the full list. The ones that are in play today.

## Navigation

The home screen does not scroll through history. Daily snapshots are saved and the athlete can navigate backward to see what the coach said on any previous day. The current view always shows the most relevant synthesis of recent history — history is compressed into what matters now, not appended to the bottom.

## Two-Column Target Display

The two-column display is intentional. The athlete sees both what their theoretical fitness suggests and what the coach recommends for today. Over time, this teaches the athlete how fatigue and conditions affect their performance — they develop genuine self-awareness rather than just compliance with a single number. On a day when targets are pulled back, they can see by how much and why.

## Plan Position Visibility

The home view always shows clearly which week and phase of the plan the athlete is currently in, how far through the phase they are, and how far from the goal event. Simple, always visible, never buried. This macro orientation makes individual hard sessions more tolerable — the athlete can see that the hard week is followed by a recovery week, that the next phase will shift emphasis, that the taper is coming.

## Near-Term Session Preview

The home view shows the next four to five planned sessions at headline level: session type, approximate duration, and training intent. These sessions come from the current week's coaching plan — the specific sessions the coach produced for this week based on accumulated reality. No specific targets, since those are generated on the day. Enough for the athlete to mentally prepare and plan their week around the training structure.

## coach > first-message

# The First Coach Message
*The most important message in the entire coaching relationship*

## Why It Matters

The first coach message sets the tone for everything that follows. An athlete who reads it and feels genuinely seen — not profiled, not templated, but seen — will trust the coach from that point. An athlete who reads something generic will never fully trust it, no matter how good the subsequent coaching is.

The first message must feel personal, specific, and purposeful. It must demonstrate that the twin has actually done something with the athlete's data, not just acknowledged it.

## Four Components — Four Natural Paragraphs

**Welcome.** Warm and brief. Acknowledges that the athlete has arrived and that the coach has been reading their history. Not effusive. Not a list of product features. One short paragraph that opens the relationship.

**What was found.** Specific observations from the historical analysis — genuine strengths identified and named, genuine gaps or opportunities identified and named. This is where the twin's depth matters most.

Not "your 5K time is X." Not "you've been running for Y years." Something the athlete could not have told themselves just by looking at their own data: an observation about aerobic base quality relative to their threshold estimates, about structural load history suggesting elevated injury risk, about training consistency patterns that reveal something about how they actually train versus how they plan to train.

The athlete should read this paragraph and feel genuinely seen. Not profiled by a template — seen. If it could have been written without reading their specific data, it has failed.

**The plan.** An overview of the training plan structure built for this athlete toward their goal. How many phases, what each focuses on, the overall arc from now to race day. Why this specific structure makes sense given what was found. The athlete should understand not just what the plan does but why it does it. When secondary events are registered, the first message references them as fitness checkpoints that provide calibration signals without compromising the primary goal timeline.

**The first block.** A specific preview of the first two to three weeks. What the focus will be, what the key sessions will look like, what the coach is trying to accomplish in this opening period. This gives the athlete something concrete to orient around immediately and demonstrates that the plan is already in motion, not a vague future promise.

## What the First Message Must Not Do

Reference generic coaching principles without connecting them to this athlete. Use numbers without context. Use acronyms without explanation. Sound like it could be sent to any new athlete. Express enthusiasm about the coaching journey ahead — that's the product talking, not the coach.

## Onboarding Time to Value

The model build takes a few minutes — not instant, not an hour. This is intentional. It communicates that something real is being computed. While the model builds, the athlete explores the app and sets their goal race or objectives. When the model is ready, the first coach message appears. The wait is part of establishing trust that the system is doing genuine work.

## coach > post-workout

# Post-Workout Analysis
*What the coach says after every session, and how it says it*

## What the Analysis Covers

**Session compliance.** Did the athlete execute the planned session? If not, what diverged and why does it matter? Compliance is not binary — the coach distinguishes between an athlete who ran the right distance at the wrong intensity, one who cut the session short due to fatigue, and one who added extra work because they felt good.

**Rep-by-rep story for structured sessions.** Each interval is examined individually. Was pacing even within the rep? Did they go out too hard? Did they fade? Was there something left in the tank at the end? The coach names specific patterns from specific reps, not general impressions.

**Historical correlation — the most important element.** Every post-workout message connects this session to a comparable previous one. "Three weeks ago on your last threshold session you faded in the final rep. Today you held it together." This requires the twin to identify which previous session is actually comparable — not just the most recent session of that type, but one where the athlete was in a similar physiological state. The twin matches sessions based on how the athlete was (fitness level, load accumulation, recovery state) not just what the session looked like (type, phase, intensity). Two threshold sessions at the same pace mean something very different when one follows a rest week and the other follows a hard session.

**Objective progress.** A specific update on the objectives this workout was designed to address. Not all objectives — the ones in play for this session. Expressed in plain language with directional movement: better, worse, unchanged, and why.

## Format

Three natural paragraphs. No headers, no bullets, no emojis.

1. Overall session summary and how it compared to the plan
2. The execution story — what happened across the session, named specifically
3. Connection to previous similar sessions and movement on the relevant objectives

## What the Coach Never Says

Raw numbers without context. Acronyms without explanation. Generic encouragement — "great job," "well done," "you're making progress." Anything that could have been written without reading the actual workout data. Anything that sounds like it came from a template.

## The Trigger

Post-workout analysis fires when the session data is available. The athlete should open the app after a run and find the coach has already read it and written the message. For athletes who prefer to initiate the analysis themselves, this is a user-controlled setting — but the default is automatic so the experience requires no extra steps.

## coach > objectives

# Objectives System
*Every session connects to a bigger picture*

## What Objectives Are

Objectives are the bridge between individual sessions and long-term development. They give each workout a purpose the athlete can see and the coach can track. Without objectives, training is a sequence of isolated efforts. With them, it is a directed programme.

Objectives go beyond basic metrics like personal bests. They address the physiological insights that the twin can see and the athlete usually cannot: aerobic base quality relative to threshold, pacing discipline under fatigue, intensity distribution balance, durability across longer sessions, neuromuscular sharpness.

## Initial Seeding

The first coach message seeds an initial set of objectives based on the twin model analysis. These reflect what was actually found in the athlete's data — genuine strengths to build on and genuine gaps to address.

The coach surfaces strengths explicitly alongside improvement opportunities. Focusing only on weaknesses is demoralising and incomplete. An athlete who knows their aerobic base is genuinely strong trains with different confidence than one who only hears about their threshold limitations. Both are true; both matter.

## Living Updates

Objectives update on a slower rhythm than workouts — weekly or after significant sessions, not after every run. This is deliberate. Training progress is not visible day to day; it accumulates over weeks. Updating objectives too frequently creates noise; updating them too infrequently loses the connection between sessions and goals.

After each relevant workout, the coach briefly connects the session to the applicable objective — not a full update, just an acknowledgement that the session served a purpose.

When an objective is achieved or superseded, that moment is acknowledged explicitly in the daily journal. A small milestone before setting the next challenge. The coach does not silently update the list — it marks the completion as a genuine moment in the coaching relationship.

Achievement is determined by sustained improvement, not a single session. The system looks for consistent positive movement across multiple recent updates before declaring an objective achieved. This prevents premature celebration from a single good session and ensures achievements reflect genuine, sustained progress.

## Daily View Integration

**Pre-workout:** Only the objectives this specific workout is designed to address are surfaced. Not the full list, not all of them — the ones relevant to today. An athlete about to do a threshold session sees the objectives related to threshold and pacing discipline, not their aerobic base objectives.

**Post-workout:** The coach message explicitly addresses movement on those same objectives. The athlete knows what this session was for before they run it, and receives a specific update on whether they moved toward it after they run it. Training has a clear purpose and visible feedback.

## coach > substitution

# Session Substitution, Injury & Illness Handling
*What happens when the plan meets reality*

## Workout Substitution Flow

**Initiation.** The athlete signals via a button — "I don't feel like this today" — or free text. The button lowers the activation energy required: the athlete does not need to articulate anything, just signal intent. This matters because a fatigued athlete who has to explain themselves before getting help is more likely to simply skip.

**Short conversation.** A brief branching conversation — three to four exchanges — to understand the constraint: fatigue, time pressure, motivation, injury concern. This determines what type of substitution is appropriate. The conversation is not a form — it is the coach asking sensible questions a real coach would ask.

**Resolution.** Once the constraint is understood, the system draws from the pre-built workout library rather than generating a new workout from scratch. The alternative session preserves the training intent where possible — if the athlete can still run but needs shorter duration, the substitution maintains the physiological purpose. If the constraint is injury-related, the substitution may shift to cross-training.

**Post-hoc detection.** If the athlete uploads session data that does not match the planned session structure, the system detects the mismatch and opens a conversation after the fact to understand what happened. Athletes do not need to declare upfront — the system catches it afterward.

> **Architecture:** `SkipConversationAgent` classifies the skip reason and routes to `SkipFlow`. Resolution phase queries `WorkoutLibraryEntry` via `WorkoutLibraryService.find_substitutes()`. Post-hoc detection is a separate service not owned by the skip agent.

## Rest Days

If an athlete requests a rest day, the system asks whether there is availability elsewhere in the week to redistribute the load. If yes, the plan adjusts and the session moves. If no, the rest day is logged and future load is recalculated accordingly. The framing is always about making the week work, never about a missed session. Missing a session is a normal part of training; treating it as failure achieves nothing.

> **Architecture:** `SkipConversationAgent` classifies as `fatigue` or `external_constraint` → routes to `no_redistribution` (no availability) or `offer_redistribution` (find window). Redistribution logic lives in `SessionLifecycleService`.

## Workout Library

Substitutions draw from a library of curated sessions. The library is not a marketplace — athletes do not contribute to it, cannot browse it, and have no visibility into it. It is a coaching resource, not a feature. Sessions that work well as substitutes in specific contexts surface more frequently over time as the system learns from outcomes.

> **Architecture:** `WorkoutLibraryEntry` entity. Queried by `WorkoutLibraryService.find_substitutes()` when `SkipFlow` is `offer_redistribution`. Acceptance learning maps to `acceptance_rate` sorting. Promotion from `GeneratedWorkout` runs nightly.

## Illness Flow

The coach asks how the athlete is feeling and roughly how long they expect to be affected. Short illness — one to three days — results in the plan holding and easy sessions being replaced with rest. Longer illness triggers plan restructuring designed to bring the athlete back smoothly: very easy aerobic work before any reintroduction of structure.

The return-to-training ramp is conservative. The twin treats the illness period as forced detraining, adjusting fitness and fatigue estimates accordingly before the first session back so that targets are appropriate for the athlete's actual current state.

> **Architecture:** `SkipConversationAgent` classifies as `illness` → routes to `illness_handling`. `PlanGenerationService.regenerate()` restructures the plan. Conservative return ramp enforced by post-regeneration session type constraints (`easy_aerobic`, `recovery_run` for first 3 sessions back).

## Injury Flow

More complex, because type and severity vary enormously. The coach asks enough to understand the nature of the issue: where it is, how long it has been present, and critically whether the athlete can cross-train or needs complete rest. A calf strain has very different implications to a knee niggle.

The system is not a medical tool and never frames it that way. The coach asks the questions a sensible human coach would ask. Based on the responses the plan restructures around what the athlete can do. Cross-training alternatives are suggested where appropriate to maintain aerobic fitness during the injury window.

Return to running is gradual, with the twin watching execution quality closely in the first sessions back for signs that the issue persists. Neither illness nor injury flow ever feels clinical or alarming. The coach tone is calm, practical, and focused on making the best of the situation.

> **Architecture:** `SkipConversationAgent` classifies as `injury_concern` → routes to `injury_escalation`. `PlanGenerationService.regenerate()` restructures with `{ injury_flag }`. Cross-training alternatives are non-running session prescriptions owned by a separate layer.

## Unsynced Workout Handling

When an expected workout has not appeared in the system, the coach surfaces a simple check-in: "I haven't seen your session from yesterday yet — did you get it done?" rather than making assumptions. The athlete responds with one tap.

If yes: sync or upload is prompted. Plan continues normally.
If no: the standard skip flow handles it — reschedule or let the plan adjust.
If no response: the system holds its judgement and asks again at the next app open.

When the athlete's actual data arrives, any estimates are replaced by real values throughout the model. The full post-workout analysis triggers retroactively.

> **Architecture:** Not owned by `SkipConversationAgent`. This is a distinct check-in flow triggered by missing expected data. The "if no" branch feeds into the standard skip classification pipeline. Ownership of the detection and check-in layer should be identified in the architecture.

---

## Non-Running Session Suggestions

The coach can prescribe non-running work when it serves the athlete's running goals: strength and conditioning, yoga and mobility, cross-training during injury recovery. These appear in the weekly plan as secondary sessions with type and duration only — no detailed workout targets are generated.

The athlete sees these suggestions alongside their primary running sessions. They know which sessions are primary (full workout generated) and which are secondary (suggestions). The athlete decides whether to complete the secondary sessions based on their schedule and energy.

This boundary is intentional: the coaching system owns running workout design. Non-running work is prescribed at the level of type and duration, leaving execution details to the athlete or their strength coach.

> **Architecture:** Not owned by `SkipConversationAgent` or `WorkoutLibraryEntry`. Prescription of non-running sessions is a plan generation concern — the system adds secondary session entries with type and duration only. Ownership of this prescription layer should be identified in the architecture.

## coach > race-prediction

# Predicted Race Time & Weather Response
*A living estimate that improves as the athlete does*

## The Predicted Race Time

The twin continuously produces a predicted finish time for the athlete's goal event. This is a living number that updates as fitness evolves through the training plan — not a one-time estimate calculated at onboarding and forgotten.

The predicted time is visible on the home view. Watching it improve as fitness builds through a training plan is one of the most quietly motivating elements of the product. The number makes abstract fitness gains concrete and visible.

For athletes pursuing race goals with registered B-races, secondary predictions are also produced. See secondary-events for the coaching approach. These appear alongside the primary prediction and serve a different coaching purpose. Where the primary prediction shows "what you're aiming for," the B-race prediction shows "what I recommend targeting" — a conservative, controlled effort based on your current fatigue state and fitness level. The coach message specifies the exact pace/power/time target to ensure the B-race provides valuable feedback while protecting your primary goal preparation. This preserves the training plan integrity while still providing meaningful race experience.

## Baseline Prediction

Derived from the twin's current threshold estimates, aerobic capacity indicators, and running economy signals. Assumes standard conditions: flat course, moderate weather, well-rested athlete. Updated after every significant training block as the twin's fitness estimates shift.

## Weather-Adjusted Prediction

In the weeks before the race, the system fetches the race day weather forecast and applies the athlete's personalised weather response to produce a weather-adjusted estimate. Both the baseline and weather-adjusted predictions are shown with a plain-language explanation of the difference. "Based on the forecast for race day — 26°C and humid — your adjusted target is around two minutes slower than your baseline estimate."

This is not a generic calculator correction. It is a projection based on this athlete's actual execution history in similar conditions, not a population average adjustment.

## Course Profile Adjustment

If the race course profile is available — ideally provided by the athlete at goal-setting — the prediction incorporates elevation data. A hilly course with significant climbing adjusts the target time based on the athlete's demonstrated performance on grade-adjusted efforts.

Course data is also a training input: a race with substantial elevation triggers hill-specific sessions in the plan, downhill running practice for quad conditioning, and appropriate adjustment of volume distribution across terrain types.

## Personalised Weather Response Modelling

The twin accumulates data on how this specific athlete's performance responds to environmental conditions across every session. Not how athletes in general respond to heat — how this athlete responds. Some are heat resilient. Others degrade significantly above 18°C. Some are affected more by humidity than dry heat. These individual response curves are learned from actual execution data, not assumed from population averages.

After every session the post-workout analysis includes the environmental conditions as context for interpreting execution. A pace that looks slow in isolation looks different when the system notes it was 28°C with 80% humidity. Over time this builds a rich picture of the athlete's performance envelope across conditions.

The weather response model also feeds back into training design. If an athlete consistently trains in mild conditions but their goal race is in summer heat, the system identifies this as a preparation gap and proactively suggests deliberate heat exposure sessions as part of the plan.

## coach > visualisation

# Workout Visualisation
*What Pheidipp shows — and what it deliberately does not*

## The Core Test

Every visualisation in Pheidipp must pass a single test: does this require the twin's context to produce? If it could be shown by Garmin Connect, Strava, or intervals.icu, it does not belong here.

Athletes already have access to raw data charts — HR over time, pace over time, power curves, cadence graphs. Those platforms do this well. Duplicating them inside Pheidipp would produce an inferior version of something the athlete already has, and would pull the product toward the dashboard experience it is deliberately designed to avoid.

Pheidipp does not compete with those platforms on raw data display. Its role is coaching intelligence derived from that data.

## What Pheidipp Shows

**Comparative session overlay.** A narrative comparison of this session against the most recent comparable one — same session type, similar phase of training, similar target intensity. Not raw data plotted twice: a coaching description of execution shape. Did the athlete hold pace better through the back half? Did effort distribute more evenly across reps? Where did the fade begin versus last time?

This requires the twin to identify which previous session is actually comparable — not just any previous threshold session, but one in similar training context and at a similar fitness level. That identification is what makes this comparison impossible for Garmin to show. The comparison is surfaced through the coach voice, not as a separate visual component.

**Session shape classification.** A single coaching observation summarising how the session unfolded: even execution, progressive fade, positive split, W-shape blowup, strong finish. The same pattern the coach describes in words, computed from the raw signal but not the raw signal itself. The athlete receives this as a sentence in their post-workout message, not as a chart.

**Zone compliance in context.** Not a time-in-zone pie chart — that exists in Garmin already. Instead: a coaching note on whether the athlete landed where they were meant to for this specific session intent. A threshold session where 40% of time was spent in Zone 2 tells a different story to an easy aerobic run with the same distribution. The context that makes the number meaningful comes from the twin's understanding of what the session was for. This appears as part of the coach's narrative, not as a separate metric display.

**Fitness and fatigue trend with session marked.** The rolling twin state over the last six to eight weeks — a coaching description of the athlete's form arc — with today's session placed in context. Shows the athlete where this session sits in the block: early build, mid-block accumulation, pre-race sharpening. This perspective requires weeks of data and is invisible in any single-session view. The trend is communicated through the coach's voice as part of the ongoing training narrative.

## The Principle

Raw data belongs in the athlete's existing tools. Pheidipp surfaces only what requires coaching intelligence to produce — comparisons that need the twin to identify what is actually comparable, abstractions that need the twin to know what the session was for, trends that need the twin's longitudinal model to be meaningful.

These insights are delivered through the coach voice as natural language, not as separate visual components or UI widgets. The architecture computes these signals deterministically; the coach narrative presents them to the athlete in context.

If it could be a screenshot from Strava, it should not exist in Pheidipp.

## product > premium-features

# Premium & Future Features
*Capabilities beyond the core coaching loop*

## Free Coach Chat

### What It Is
The standard Pheidipp experience is one-directional: the coach reads data, generates analysis, and writes to the athlete. Free Coach Chat opens a bounded conversational layer as a premium feature. The athlete can ask the coach questions and receive answers in the same voice and with the same depth as the generated analysis. It is not a generic AI assistant — it is the same coach, answering questions that fall within their expertise.

### In Scope
Training methodology: how periodisation works, the polarised versus threshold training debate, zone model differences, what a taper is actually doing physiologically, why recovery weeks exist. Plan rationale: why a session is structured a particular way, what a recovery phase is accomplishing, how a phase connects to the race. Race strategy, pacing, heat acclimatisation, altitude, racing on tired legs. Cross-training from a running lens: how cycling preserves aerobic fitness during injury, why swimming does not replicate running adaptation, what strength work contributes to running economy.

The coach answers all of this with the same specificity it brings to generated analysis — referencing the athlete's current training context and individual history where relevant.

### Out of Scope — and How the Coach Redirects
The coach redirects naturally, not mechanically. The athlete should feel they spoke to someone with professional self-awareness, not hit a product constraint.

**Sleep optimisation:** The twin uses sleep as a training input, and the coach will tell an athlete how fragmented sleep is affecting their readiness. What it won't do is advise on sleep hygiene, sleep architecture, or supplementation. "That's one for a sleep specialist — here's how it's showing up in your training data."

**Nutrition beyond training fuelling:** Carbohydrate timing around sessions and hydration in heat are legitimate coaching territory. Dietary design, caloric targets, and weight management are not. Redirects to a sports dietitian.

**Injury assessment:** The coach can acknowledge a concern, adjust load in response, and recommend professional attention. It cannot assess, diagnose, or suggest treatment.
"I'm not the right one to look at this — please get it seen before we push the load. I've pulled back this week's targets in the meantime."

### Premium Positioning
Free Coach Chat is not part of the core experience. The core loop — plan, generate, log, analyse — remains fully functional without it. Free Coach Chat is for athletes who want active dialogue with their coach rather than generated analysis only.

---

## Group & Team Training

### The Use Case
A group of athletes training together toward the same event — friends targeting the same marathon, a running club with a shared goal race. They want the accountability and shared purpose of training as a group, without the homogenisation of following a single programme that ignores individual fitness levels and recovery rates.

### How It Works
The group shares a macro training plan — the same periodisation phases, the same race timetable, the same broad weekly structure. What is not shared is anything below that level. Day-of workout targets are generated individually from each athlete's own twin model. Post-workout analysis is entirely personal. The group shares a destination and a map; each athlete walks their own path to get there.

### Coach Uses Group Context Sparingly
Where group context meaningfully enriches individual coaching, the coach uses it — knowing that training partners are also in a recovery week adds a layer of social normalisation. Group references are never used for comparison or competition. No athlete ever reads that they are behind someone else in the group.

### No Social Layer
There is no group feed, no leaderboard, no shared activity stream. Pheidipp is not a social platform. The shared experience lives in the real world — training together, racing together, holding each other accountable in conversation. The app's job is to make each individual athlete as prepared as possible for the shared goal.

---

## Voice Companion

A future extension where coaching content is delivered as audio alongside the existing text layer. Daily pre-session briefing as a voice note during the commute or warm-up. Post-workout analysis as audio while stretching. Hands-free workout substitution before heading out the door.

This is not a separate product — it is an additional surface for the same coaching content the text layer already produces. The investment in coach voice quality throughout the core product is what makes this extension natural rather than bolted on.

---
*End of combined documentation*
