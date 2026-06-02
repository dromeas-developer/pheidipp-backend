# Cold Start Strategy
*How the twin initialises before an athlete has real training data*

## Three Confidence Tiers

The twin starts from one of three tiers depending on what data is available at onboarding.
The system is always honest about which tier it is operating from, and all downstream
decisions — plan conservatism, target ranges, coaching certainty — are weighted accordingly.

**Tier 1 — Imported training history.** The athlete connects an existing training platform
and the system ingests real historical workout data. The twin is built from actual
physiology, not assumptions. This is the richest starting point and produces the most
personalised initial coaching. Athletes in this tier can also supplement with lab/test uploads
to provide additional threshold precision.

**Tier 2 — Peer-similar athletes OR Lab/Test Uploads.** For athletes with no importable
history, the twin bootstraps either from anonymised models of similar athletes OR from
athlete-provided physiological benchmarks. Lab/test uploads provide higher threshold confidence
than peer-based inference, but execution patterns and adaptation signatures still require
real training data to develop.

Confidence transitions are quality-weighted, not session-count-based. A single lab test carries more evidence than multiple easy sessions with optical HR. The system weighs observation quality when determining when to upgrade confidence levels — it is the quality of the data, not just the quantity, that drives confidence forward.

**Tier 3 — Questionnaire inputs only.** The most conservative baseline, built from
onboarding responses alone. Initial targets are expressed as ranges or effort descriptions
rather than precise numbers. The twin becomes more confident and specific as real training
data accumulates over the following weeks.

## What Honest Confidence Looks Like

A Tier 3 athlete does not receive aggressive targets on day one. The coach language
reflects genuine uncertainty: "based on what you've described," "let's see how this feels,"
"we'll calibrate as we see your actual data." This is not a degraded experience — it is
accurate coaching at the information level available.

As sessions accumulate and the twin observes real execution, threshold estimates, recovery
patterns, and fatigue responses, confidence upgrades and the coaching becomes correspondingly
more precise. The athlete earns specificity from the model by training with it.

## Onboarding Time to Value

The model build takes a few minutes — not instant, not an hour. This communicates that
something real is being computed, not a template being applied. While the model builds,
the athlete explores the app and sets their goal race or objectives. When the model is
ready, the first coach message appears.
