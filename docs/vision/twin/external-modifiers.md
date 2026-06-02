# External Modifiers — Layer 4
*Understanding that training happens in a life, not in isolation*

## Philosophy

Subjective daily wellness questionnaires are intentionally avoided as a primary input.
Compliance drops sharply after the first few days. All wellness signals are captured
passively where possible, from data the athlete is already generating through their
wearable during sleep and rest. The athlete should not have to tell the system how they
feel — the system should already have the physiological evidence.

## Core Sleep Metrics

Sleep is the most important recovery signal. The twin tracks multiple dimensions, each
telling a different story.

**Total sleep duration** — the volume of recovery time available. Trends over multiple
nights matter more than any single night.

**Deep sleep duration** — physical recovery and tissue repair. Consistently low deep sleep
is an early warning for accumulated fatigue, often appearing before the athlete consciously
notices anything wrong.

**REM proportion** — cognitive and emotional recovery. Relevant for motivation, perceived
effort, and decision-making capacity, particularly relevant for race situations.

**Average sleeping HR** — the primary trend signal for recovery state. Rising average
sleeping HR over several consecutive nights is one of the most reliable early indicators
of overreaching or illness onset, often appearing three to four days before the athlete
consciously feels fatigued.

**Minimum sleeping HR** — the true physiological floor, recorded during the deepest sleep
phases. Used as the resting HR anchor for zone calculations. More stable than average
sleeping HR and less influenced by external factors.

The time-of-day modifier is part of the wellness modifier pipeline in architecture. It adjusts the correlation between wellness signals and execution quality based on whether the athlete trains in the morning or afternoon, avoiding misattribution of life stress to fitness state.

## Resting HR — A Definition That Matters

Three distinct measurements are commonly conflated under "resting HR":

- **Overnight minimum HR** — most stable, passively capturable, the measurement Pheidipp
  uses for all intent range calculations
- **True resting HR** (supine, morning, before rising) — reproducible but requires
  deliberate capture that athletes stop doing consistently
- **Standing or ambient HR** — most variable, least useful for precision inputs

The overnight minimum is the right choice: it requires nothing from the athlete and
produces the most consistent baseline.

## HRV

Average overnight HRV is preferred over a dedicated morning measurement. Wearables that
capture continuous overnight HRV provide a more stable and consistent reading than a
1-5 minute morning test, which athletes perform inconsistently and eventually abandon.

The twin monitors overnight HRV trends across rolling 3, 7, and 14 day windows. It never
reacts to a single-night value — individual nights are noisy and can be disrupted by
factors entirely unrelated to training load.

## Menstrual Cycle Phase

For female athletes, menstrual cycle phase is a named physiological modifier within Layer 4,
tracked on equal footing with HRV and sleep. The cycle operates on a roughly 28-day
rhythm with four phases, each producing measurable effects on readiness, thermoregulation,
perceived effort, and sleep quality.

The luteal phase elevates core body temperature roughly 0.3-0.5°C, which shifts the
pace-at-HR relationship in the same way warm weather does. The twin applies a
thermoregulatory modifier during this phase identical in structure to its weather
adjustment. Late luteal sleep quality degradation compounds with any existing sleep debt,
producing a combined readiness signal the twin reads as worse than either in isolation.

Cycle phase signals are never interpreted in isolation. Phase context is one input among
several, weighted by how strongly this individual athlete has shown phase-correlated
variation in her own data. The model learns the individual pattern.

Full detail on the four cycle phases and their training implications: see `womens-cycle.md`.

## Training Time of Day

Whether an athlete trains in the morning or afternoon is a meaningful contextual modifier
that most platforms ignore.

Morning athletes train before daily life accumulates — no nutritional variation from the
day, no work stress, no decision fatigue. Wellness signals correlate more directly with
workout execution because the noise sources are more predictable.

Afternoon athletes train at the end of a full day of external stressors. Suppressed HRV
or elevated resting HR may reflect life stress rather than training load. The twin applies
a time-of-day modifier when correlating wellness signals to execution quality, avoiding
misattributing life fatigue to fitness state.

## Trend-Based Interpretation

All Layer 4 signals are interpreted as trends against the athlete's own baseline — never
as absolute values compared to population norms. Individual baselines vary enormously.
What matters is deviation from this athlete's recent normal.

Single-night anomalies are treated as noise. Patterns across three or more consecutive
nights trigger model adjustments. Patterns across seven or more nights may prompt
proactive coach communication and plan restructuring.

## How the Coach Communicates Wellness Patterns

When the twin detects a concerning wellness pattern it surfaces this proactively in plain
language. No medical language, no diagnoses, no acronyms. A clear explanation of what was
observed, why it matters for training, and what adjustment has already been made.

Example: "Your sleep has been fragmented the last three nights and your overnight heart
rate has been running a little higher than your recent baseline. That kind of pattern
usually means your body is working harder than normal just to recover. I've taken the
intensity targets down a notch for today's session — let's get the work in without adding
to the load your system is already managing."

The adjustment is communicated as already made — not as a question of whether to make it.
The coach acts and explains, rather than asking permission.

## Downstream Effects

Layer 4 signals feed directly into session target adjustment, plan load management, and
rest day recommendations. A sustained negative wellness trend can trigger a proposed
recovery day — the coach proposes it, explains why, and asks about weekly availability
to redistribute load if appropriate.
