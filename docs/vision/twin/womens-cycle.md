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
