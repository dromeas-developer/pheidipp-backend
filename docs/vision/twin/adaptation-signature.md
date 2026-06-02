# Individual Adaptation Signature — Layer 3
*Learning how this specific athlete responds to training stimulus over time*

## Philosophy

Layer 3 is the most differentiating and longest-horizon layer of the twin. It models how
this specific athlete responds and adapts to training stimulus — not how athletes in general
respond, but the unique physiological fingerprint of this individual. A human coach builds
this understanding intuitively over years of working with someone. The twin builds it
systematically from data.

Perfect attribution of cause and effect in training is impossible. Sessions overlap, fatigue
compounds, and recovery signals reflect the sum of multiple stimuli. Layer 3 accepts this
reality and works with it rather than pretending it can be solved.

## The Training Block as the Atomic Unit

Individual sessions are not the unit of analysis for adaptation learning. The **adaptation
window** is.

A hard adaptation window is two or three quality sessions in close succession — threshold work,
intervals, long runs — treated as a single compound stimulus. The twin does not attempt
to decompose the individual contribution of each session within an adaptation window. It treats the
adaptation window as one unit with a defined start, a defined end, and a measurable intensity profile.

This makes the attribution problem tractable: one compound stimulus, one clean recovery
observation window, one readable response.

## Three Training Unit Types

**Hard adaptation windows.** Two to three quality sessions in close succession. The stimulus unit.
Characterised by type (interval-dominant, threshold-dominant, volume-dominant), total
load across all three dimensions from Layer 1, and internal structure.

**Isolated sessions.** A single quality session with easy days either side. The cleanest
signal available — one stimulus, one recovery window, minimal confounding. The twin weights
isolated sessions more heavily than sessions embedded in adaptation windows when learning adaptation
patterns because the experimental conditions are more controlled.

**Recovery and easy periods.** Not filler between hard work — active observation windows.
This is where the twin reads how the athlete is responding to what came before. The length
and quality of the recovery window before wellness signals return to baseline is the
primary adaptation signal.

## Plan Structure as Data Collection

Good training periodisation and good data collection for the adaptation signature require
the same structural rules. By encoding best-practice coaching patterns into plan design,
the system simultaneously optimises training quality and creates the clean experimental
conditions needed for adaptation learning.

Core structural rules that serve both purposes:

Long runs are always followed by a rest day or genuine recovery session. This provides
a clean 24-48 hour window to observe structural and aerobic fatigue response without
interference from subsequent training.

Threshold and interval sessions are sandwiched between easy days. Easy days before ensure
the athlete arrives fresh — removing accumulated fatigue as a confounding variable and
creating consistent pre-session baselines. Easy days after create clean recovery
observation windows.

Hard adaptation windows are deliberate and periodic, not the default structure. When prescribed, the
twin treats the entire adaptation window as a single stimulus and reads the recovery response at adaptation window
level. At the planning level, these are implemented as `block_id` groups on PlannedSession records. The weekly
synthesis agent creates `block_id` groups of 2-3 consecutive quality sessions; the adaptation signature layer then
observes the recovery response to those groups.

## What the Twin Measures After Each Block

After every hard adaptation window or isolated quality session, the twin monitors three response
dimensions:

**Short-term fatigue depth.** How much do wellness signals drop immediately — HRV
suppression, elevated sleeping HR, reduced sleep quality. The magnitude relative to the
adaptation window's load profile is the fatigue sensitivity signal.

**Recovery trajectory.** How quickly do wellness signals return to personal baseline.
Some athletes bounce back within 24 hours; others take 72 hours or more. This recovery
rate directly determines how much separation the plan needs to build between hard efforts.

**Execution quality at the next quality session.** How does the athlete perform on the
first quality session after the recovery window, relative to their recent baseline for
that session type. Full recovery with strong execution confirms the window was adequate.
Degraded execution suggests the window was insufficient.

For female athletes, all three dimensions are read through the lens of current cycle phase.
Late luteal suppression is a different signal to mid-follicular suppression — the former
is partly hormonal, the latter is more likely a genuine load response. The twin controls
for cycle phase to avoid corrupting the adaptation signature.

## Long-Term Adaptation Yield

For each training emphasis — threshold work, aerobic volume, interval intensity — the twin
accumulates observations of load applied versus fitness change produced. Over time this
builds a per-athlete, per-stimulus adaptation yield profile.

Some athletes respond disproportionately well to threshold work. Others need volume to
move the needle. This yield profile directly informs plan design: training is personalised
not just to the athlete's current state but to their demonstrated physiological response
patterns.

## Confidence and Data Requirements

The adaptation signature takes the longest of any layer to become reliable. Meaningful
individual signal typically emerges after six to eight weeks of consistent training with
adequate data quality. Full confidence requires a complete training cycle — build,
peak, recovery — ideally repeated more than once.

Low confidence means the plan is more conservative and the coach communicates less
certainty in adaptation-related observations. High confidence unlocks more precise
individualisation of load, recovery windows, and training emphasis.

The plan structure itself evolves as confidence grows. If the twin observes that this
athlete consistently requires 72 hours to recover from a threshold block when the model
initially assumed 48, the recovery buffers in the plan automatically widen. Personalisation
improves without manual intervention.
