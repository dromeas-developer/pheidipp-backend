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