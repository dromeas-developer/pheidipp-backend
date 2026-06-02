# Load & Fatigue — Layer 1
*Three-dimensional tracking of the stresses training places on the body*

## Beyond a Single Fitness Score

The twin rejects the single-number fitness score approach. Different training sessions
stress different physiological systems with different accumulation and recovery timelines.
Treating them as one number produces a model that looks accurate on average but fails at
the edges — exactly where injury and overtraining happen.

Three separate load dimensions are tracked, each with its own accumulation and recovery
curve.

## The Three Dimensions

**Aerobic Load** — Cardiovascular and metabolic stress from sustained effort across aerobic
zones. Builds slowly and durably. Fatigue clears over roughly 10-15 days; fitness
accumulates over 40-60 days (individual constants are learned per athlete over time).
This is the best understood dimension with the most established science behind it.

**Neuromuscular Load** — Fast-twitch fibre recruitment, acceleration stress, and high
intensity neuromuscular demand. A session with short explosive efforts or sustained
high intensity accumulates neuromuscular stress disproportionate to its cardiovascular
signal. Clears faster than aerobic fatigue — roughly 3-5 days — but with a distinct
signature.

**Structural Load** — Tendon, connective tissue, and musculoskeletal stress from impact
and mechanical loading. The least understood dimension scientifically but critically
important, especially for athletes new to running. Accumulates and clears slowly — weeks,
not days. Key inputs are total impact count, elevation change, surface type, and how
quickly weekly volume is increasing.

## How the Dimensions Interact

High structural fatigue degrades neuromuscular output even when the aerobic system is
fully recovered — the "heavy legs" phenomenon where breathing feels fine but pace simply
is not there. The twin models this interaction rather than treating dimensions as
independent. A single fitness number cannot distinguish between these states.

## Data Quality and Load Computation

The richness of load computation depends on what data the athlete's hardware provides.
The twin always knows which tier it is working with and weights model confidence accordingly.

**Tier 1 — Running power meter + chest strap with RR intervals.** The richest signal.
Full mechanical and physiological data. Most precise load computation across all three
dimensions. The RR interval data also enables passive threshold tracking simultaneously.

**Tier 2 — Running power meter + optical HR.** Very strong for load calculation. Loses
the RR interval signal for threshold detection but power compensates significantly.

**Tier 3 — Chest strap HR + grade-adjusted pace + GPS.** No power meter, but the chest
strap provides RR interval data. Grade-adjusted pace serves as the mechanical work proxy.

**Tier 4 — Optical HR + grade-adjusted pace + GPS.** The realistic baseline for the core
athlete audience. A quality GPS watch with optical HR. Fully usable for load calculation
and zone tracking across all three dimensions.

**Tier 5 — Grade-adjusted pace + GPS only.** No HR data available. Session logged for
the training record but excluded from twin calibration.

**Tier 6 — Manual input only.** No device data at all. Session logged for the training
record only. Never used to update the twin model.

Note on optical HR: modern sensors in quality GPS watches are adequate for intent-range-based
load calculation. Their limitation versus chest strap is specifically the absence of RR interval
data for threshold detection — not HR accuracy for sustained aerobic efforts.

## Grade-Adjusted Pace — Always, Never Raw Pace

Raw pace without grade adjustment systematically misrepresents effort on varied terrain
and corrupts load calculations and historical comparisons. Grade-adjusted pace is the
standard input for all pace-based computations, target setting, and execution analysis
throughout the system.

## The Crossover Athlete Profile

Athletes transitioning from swimming or cycling carry a specific risk. Their aerobic load
tolerance is high — the cardiovascular system genuinely absorbs volume. But structural load
tolerance is low — tendons and connective tissue have not had years of running adaptation.

A model using only cardiovascular signals would look at their HR data, see them cruising,
and conclude they can handle more load. The three-dimensional model catches that structural
stress is accumulating at a rate their cardiovascular fitness masks. This profile is
identified at onboarding and structural capacity development is incorporated as an explicit
objective in the training plan.

## Individual Time Constants

Some athletes carry aerobic fatigue for 10+ days; others clear it in 5. Some build
fitness slowly and durably; others peak quickly but also detrain fast. The twin learns
these individual constants from observed response patterns over time rather than applying
population defaults that may be significantly wrong for a given person.

## Coach Communication of Load Patterns

When the twin detects concerning patterns — structural load accumulating faster than
demonstrated tolerance, neuromuscular fatigue not clearing between sessions — the coach
surfaces this in plain language. No raw numbers, no acronyms. A clear explanation of
what was observed and what adjustment has been made to the session.

If an athlete consistently produces sessions without device data, the coach surfaces this
as an opportunity to give the coaching system better data — never as criticism.

---

## Recovery Timing and Session Priority

Recovery windows are measured from primary session to primary session. Secondary sessions — whether a double-day PM session or a suggested non-running workout — do not reset the recovery clock.

This reflects physiological reality: a morning easy run followed by an evening threshold session provides more recovery between primary efforts than two hard sessions on consecutive days. The twin's recovery model accounts for this by tracking primary session spacing rather than total session count.

The weekly plan respects this when scheduling quality sessions: a double day with AM primary + PM secondary followed by a single primary session the next day provides adequate recovery for most athletes.
